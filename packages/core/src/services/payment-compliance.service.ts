import { EventEmitter } from 'events';
import { Redis } from 'ioredis';

interface ComplianceCheck {
  type: 'kyc' | 'aml' | 'tax' | 'regulatory' | 'data_privacy';
  passed: boolean;
  reason?: string;
  requiredActions?: string[];
  metadata?: Record<string, any>;
}

interface EdgeCaseHandler {
  scenario: string;
  handler: (context: any) => Promise<any>;
  fallback?: (error: Error, context: any) => Promise<any>;
}

export class PaymentComplianceService extends EventEmitter {
  private redis: Redis;
  private edgeCaseHandlers: Map<string, EdgeCaseHandler>;

  // Regulatory requirements by country
  private regulatoryRequirements = {
    EU: {
      PSD2: { sca: true, exemptionThreshold: 30 },
      GDPR: { consentRequired: true, dataRetention: 730 },
      VAT: { reverseCharge: true, ossThreshold: 10000 }
    },
    US: {
      PATRIOT_ACT: { kycRequired: true, thresholds: { daily: 10000, monthly: 50000 } },
      FATCA: { reportingRequired: true },
      STATE_TAXES: { nexusTracking: true }
    },
    MX: {
      CFDI: { invoiceRequired: true, rfcRequired: true },
      AML: { reportThreshold: 100000 }, // MXN
      SAT: { monthlyReporting: true }
    },
    BR: {
      FISCAL_COMPLIANCE: { cpfCnpjRequired: true },
      IOF_TAX: { rate: 0.38 },
      NOTA_FISCAL: { required: true }
    }
  };

  // Sanctions and embargoed countries
  private sanctionedCountries = ['KP', 'IR', 'SY', 'CU', 'VE', 'RU', 'BY'];
  private highRiskCountries = ['AF', 'YE', 'LY', 'SO', 'SD', 'CD', 'ZW'];

  constructor(redis: Redis) {
    super();
    this.redis = redis;
    this.edgeCaseHandlers = new Map();
    this.initializeEdgeCaseHandlers();
  }

  private initializeEdgeCaseHandlers(): void {
    // Network timeout handling
    this.registerEdgeCase('network_timeout', {
      scenario: 'Network timeout during payment',
      handler: async (context) => {
        // Implement idempotency check
        const idempotencyKey = context.idempotencyKey;
        const cached = await this.redis.get(`payment:idempotent:${idempotencyKey}`);

        if (cached) {
          return JSON.parse(cached);
        }

        // Retry with exponential backoff
        const maxRetries = 3;
        let delay = 1000;

        for (let i = 0; i < maxRetries; i++) {
          try {
            const result = await context.operation();
            await this.redis.setex(
              `payment:idempotent:${idempotencyKey}`,
              3600,
              JSON.stringify(result)
            );
            return result;
          } catch (error: any) {
            if (i === maxRetries - 1) throw error;
            await new Promise(resolve => setTimeout(resolve, delay));
            delay *= 2;
          }
        }
      },
      fallback: async (error, context) => {
        // Queue for manual review
        await this.queueForManualReview('network_timeout', context);
        return { status: 'pending_review', reason: 'Network timeout' };
      }
    });

    // Duplicate payment detection
    this.registerEdgeCase('duplicate_payment', {
      scenario: 'Duplicate payment attempt',
      handler: async (context) => {
        const fingerprint = this.generatePaymentFingerprint(context);
        const existing = await this.redis.get(`payment:fingerprint:${fingerprint}`);

        if (existing) {
          const existingPayment = JSON.parse(existing);
          const timeDiff = Date.now() - existingPayment.timestamp;

          if (timeDiff < 60000) { // Within 1 minute
            throw new Error('Duplicate payment detected');
          }
        }

        // Proceed with payment
        const result = await context.operation();

        // Store fingerprint
        await this.redis.setex(
          `payment:fingerprint:${fingerprint}`,
          300,
          JSON.stringify({
            paymentId: result.id,
            timestamp: Date.now()
          })
        );

        return result;
      }
    });

    // Currency conversion edge cases
    this.registerEdgeCase('currency_mismatch', {
      scenario: 'Currency mismatch between customer and merchant',
      handler: async (context) => {
        const { customerCurrency, merchantCurrency, amount } = context;

        // Get real-time exchange rate
        const rate = await this.getExchangeRate(customerCurrency, merchantCurrency);

        // Apply conversion with markup
        const convertedAmount = amount * rate * 1.02; // 2% markup

        // Store conversion details for audit
        await this.redis.zadd(
          'payment:conversions',
          Date.now(),
          JSON.stringify({
            original: { amount, currency: customerCurrency },
            converted: { amount: convertedAmount, currency: merchantCurrency },
            rate,
            timestamp: new Date().toISOString()
          })
        );

        return { ...context, amount: convertedAmount, currency: merchantCurrency };
      }
    });

    // 3D Secure challenges
    this.registerEdgeCase('3ds_challenge', {
      scenario: '3D Secure authentication required',
      handler: async (context) => {
        const { amount, currency, cardIssuer } = context;

        // Check for SCA exemptions
        if (await this.qualifiesForSCAExemption(amount, currency, context)) {
          return { ...context, scaExempted: true };
        }

        // Initiate 3DS challenge
        return {
          requiresAuthentication: true,
          authenticationUrl: context.authUrl,
          timeout: 600000 // 10 minutes
        };
      }
    });

    // Partial payment scenarios
    this.registerEdgeCase('partial_payment', {
      scenario: 'Partial payment or installments',
      handler: async (context) => {
        const { totalAmount, paidAmount, remainingAmount } = context;

        // Create payment plan
        const plan = {
          id: `plan_${Date.now()}`,
          totalAmount,
          paidAmount,
          remainingAmount,
          installments: this.calculateInstallments(remainingAmount, context),
          nextPaymentDate: this.calculateNextPaymentDate(context)
        };

        // Store plan
        await this.redis.setex(
          `payment:plan:${plan.id}`,
          86400 * 30,
          JSON.stringify(plan)
        );

        return plan;
      }
    });

    // Failed webhook delivery
    this.registerEdgeCase('webhook_failure', {
      scenario: 'Webhook delivery failure',
      handler: async (context) => {
        const { webhook, attempt } = context;
        const maxAttempts = 5;

        if (attempt >= maxAttempts) {
          // Queue for manual intervention
          await this.queueForManualReview('webhook_failure', context);
          return { status: 'failed', reason: 'Max webhook attempts exceeded' };
        }

        // Exponential backoff retry
        const delay = Math.pow(2, attempt) * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));

        // Retry webhook
        return await context.retryOperation();
      }
    });

    // Fraud detection
    this.registerEdgeCase('fraud_detection', {
      scenario: 'High fraud risk detected',
      handler: async (context) => {
        const riskScore = await this.calculateRiskScore(context);

        if (riskScore > 80) {
          // Block transaction
          await this.blockTransaction(context, 'High fraud risk');
          throw new Error('Transaction blocked due to high fraud risk');
        }

        if (riskScore > 60) {
          // Require additional verification
          return {
            requiresVerification: true,
            verificationMethods: ['3ds', 'phone', 'email'],
            riskScore
          };
        }

        return { ...context, riskScore };
      }
    });

    // Chargeback handling
    this.registerEdgeCase('chargeback', {
      scenario: 'Chargeback received',
      handler: async (context) => {
        const { paymentId, reason, amount } = context;

        // Create dispute case
        const dispute = {
          id: `dispute_${Date.now()}`,
          paymentId,
          reason,
          amount,
          status: 'pending',
          evidence: [] as any[]
        };

        // Gather evidence automatically
        const evidence = await this.gatherDisputeEvidence(paymentId);
        dispute.evidence = evidence;

        // Store dispute
        await this.redis.setex(
          `payment:dispute:${dispute.id}`,
          86400 * 90,
          JSON.stringify(dispute)
        );

        // Notify relevant parties
        this.emit('dispute_created', dispute);

        return dispute;
      }
    });

    // Refund edge cases
    this.registerEdgeCase('complex_refund', {
      scenario: 'Complex refund scenario',
      handler: async (context) => {
        const { paymentId, refundAmount, originalAmount, reason } = context;

        // Check refund eligibility
        const eligible = await this.checkRefundEligibility(paymentId);
        if (!eligible.allowed) {
          throw new Error(`Refund not allowed: ${eligible.reason}`);
        }

        // Handle partial vs full refund
        const isPartial = refundAmount < originalAmount;

        if (isPartial) {
          // Track partial refund
          await this.trackPartialRefund(paymentId, refundAmount);
        }

        // Process refund with provider
        const refund = await context.processRefund();

        // Handle tax refund if applicable
        if (context.includesTax) {
          await this.processTaxRefund(paymentId, refundAmount);
        }

        return refund;
      }
    });
  }

  // Compliance check methods
  async performComplianceChecks(
    context: {
      country: string;
      amount: number;
      currency: string;
      customerId: string;
      businessType?: 'b2c' | 'b2b';
      metadata?: Record<string, any>;
    }
  ): Promise<ComplianceCheck[]> {
    const checks: ComplianceCheck[] = [];

    // KYC Check
    checks.push(await this.performKYCCheck(context));

    // AML Check
    checks.push(await this.performAMLCheck(context));

    // Tax Compliance
    checks.push(await this.performTaxComplianceCheck(context));

    // Regulatory Compliance
    checks.push(await this.performRegulatoryCheck(context));

    // Data Privacy
    checks.push(await this.performDataPrivacyCheck(context));

    // Log compliance results
    await this.logComplianceChecks(context, checks);

    return checks;
  }

  private async performKYCCheck(context: any): Promise<ComplianceCheck> {
    // Check if country is sanctioned
    if (this.sanctionedCountries.includes(context.country)) {
      return {
        type: 'kyc',
        passed: false,
        reason: 'Sanctioned country',
        requiredActions: ['Block transaction']
      };
    }

    // Check if high-risk country
    if (this.highRiskCountries.includes(context.country)) {
      return {
        type: 'kyc',
        passed: false,
        reason: 'High-risk country',
        requiredActions: ['Enhanced due diligence', 'Manual review']
      };
    }

    // Check transaction thresholds
    const thresholds = this.getKYCThresholds(context.country);
    if (context.amount > thresholds.enhanced) {
      return {
        type: 'kyc',
        passed: false,
        reason: 'Amount exceeds threshold',
        requiredActions: ['Identity verification', 'Source of funds']
      };
    }

    return {
      type: 'kyc',
      passed: true
    };
  }

  private async performAMLCheck(context: any): Promise<ComplianceCheck> {
    // Check against watchlists
    const onWatchlist = await this.checkWatchlists(context.customerId);
    if (onWatchlist) {
      return {
        type: 'aml',
        passed: false,
        reason: 'Customer on watchlist',
        requiredActions: ['Block transaction', 'File SAR']
      };
    }

    // Check transaction patterns
    const suspicious = await this.detectSuspiciousPatterns(context);
    if (suspicious) {
      return {
        type: 'aml',
        passed: false,
        reason: 'Suspicious transaction pattern',
        requiredActions: ['Manual review', 'Enhanced monitoring']
      };
    }

    return {
      type: 'aml',
      passed: true
    };
  }

  private async performTaxComplianceCheck(context: any): Promise<ComplianceCheck> {
    // EU VAT compliance
    if (this.isEUCountry(context.country)) {
      const vatValid = await this.validateVATNumber(context.metadata?.vatNumber);
      if (context.businessType === 'b2b' && !vatValid) {
        return {
          type: 'tax',
          passed: false,
          reason: 'Invalid VAT number',
          requiredActions: ['Collect valid VAT number']
        };
      }
    }

    // Mexico CFDI compliance
    if (context.country === 'MX' && context.amount > 1000) {
      if (!context.metadata?.rfc) {
        return {
          type: 'tax',
          passed: false,
          reason: 'RFC required for invoice',
          requiredActions: ['Collect RFC']
        };
      }
    }

    // Brazil tax compliance
    if (context.country === 'BR') {
      if (!context.metadata?.cpf && !context.metadata?.cnpj) {
        return {
          type: 'tax',
          passed: false,
          reason: 'CPF/CNPJ required',
          requiredActions: ['Collect tax identification']
        };
      }
    }

    return {
      type: 'tax',
      passed: true
    };
  }

  private async performRegulatoryCheck(context: any): Promise<ComplianceCheck> {
    // PSD2 SCA requirements
    if (this.isEUCountry(context.country)) {
      const scaRequired = !(await this.qualifiesForSCAExemption(
        context.amount,
        context.currency,
        context
      ));

      if (scaRequired && !context.metadata?.scaCompleted) {
        return {
          type: 'regulatory',
          passed: false,
          reason: 'SCA required',
          requiredActions: ['Complete 3D Secure authentication']
        };
      }
    }

    // US Patriot Act
    if (context.country === 'US') {
      const requirements = this.regulatoryRequirements.US.PATRIOT_ACT;
      if (context.amount > requirements.thresholds.daily) {
        return {
          type: 'regulatory',
          passed: false,
          reason: 'Patriot Act threshold exceeded',
          requiredActions: ['Enhanced KYC', 'CTR filing']
        };
      }
    }

    return {
      type: 'regulatory',
      passed: true
    };
  }

  private async performDataPrivacyCheck(context: any): Promise<ComplianceCheck> {
    // GDPR compliance
    if (this.isEUCountry(context.country)) {
      if (!context.metadata?.gdprConsent) {
        return {
          type: 'data_privacy',
          passed: false,
          reason: 'GDPR consent required',
          requiredActions: ['Obtain data processing consent']
        };
      }
    }

    // CCPA compliance
    if (context.country === 'US' && context.metadata?.state === 'CA') {
      if (!context.metadata?.ccpaNotice) {
        return {
          type: 'data_privacy',
          passed: false,
          reason: 'CCPA notice required',
          requiredActions: ['Provide privacy notice']
        };
      }
    }

    return {
      type: 'data_privacy',
      passed: true
    };
  }

  // Helper methods
  private registerEdgeCase(name: string, handler: EdgeCaseHandler): void {
    this.edgeCaseHandlers.set(name, handler);
  }

  async handleEdgeCase(scenario: string, context: any): Promise<any> {
    const handler = this.edgeCaseHandlers.get(scenario);
    if (!handler) {
      throw new Error(`No handler for edge case: ${scenario}`);
    }

    try {
      return await handler.handler(context);
    } catch (error: any) {
      if (handler.fallback) {
        return await handler.fallback(error, context);
      }
      throw error;
    }
  }

  private async queueForManualReview(reason: string, context: any): Promise<void> {
    await this.redis.zadd(
      'payment:manual_review',
      Date.now(),
      JSON.stringify({
        reason,
        context,
        timestamp: new Date().toISOString()
      })
    );

    this.emit('manual_review_required', { reason, context });
  }

  private generatePaymentFingerprint(context: any): string {
    const crypto = require('crypto');
    const data = `${context.customerId}-${context.amount}-${context.currency}-${context.paymentMethod}`;
    return crypto.createHash('sha256').update(data).digest('hex');
  }

  private async getExchangeRate(from: string, to: string): Promise<number> {
    // In production, use real exchange rate API
    const rates: Record<string, number> = {
      'USD': 1,
      'EUR': 0.92,
      'MXN': 17.5,
      'GBP': 0.79,
      'CAD': 1.35,
      'BRL': 5.0,
      'ARS': 350,
      'CLP': 900,
      'COP': 4000,
      'PEN': 3.8,
      'UYU': 39
    };

    const fromRate = rates[from] || 1;
    const toRate = rates[to] || 1;

    return toRate / fromRate;
  }

  private async qualifiesForSCAExemption(amount: number, currency: string, context: any): Promise<boolean> {
    // Low-value exemption (< 30 EUR)
    const exchangeRate = await this.getExchangeRate(currency, 'EUR');
    const eurAmount = amount / exchangeRate;
    if (eurAmount < 30) return true;

    // Trusted beneficiary exemption
    if (context.trustedBeneficiary) return true;

    // Corporate payment exemption
    if (context.businessType === 'b2b') return true;

    // Recurring transaction exemption
    if (context.isRecurring && context.recurringAuthCompleted) return true;

    return false;
  }

  private calculateInstallments(amount: number, context: any): any[] {
    const { installmentMonths = 3 } = context;
    const monthlyAmount = amount / installmentMonths;

    const installments = [];
    for (let i = 1; i <= installmentMonths; i++) {
      installments.push({
        number: i,
        amount: monthlyAmount,
        dueDate: new Date(Date.now() + (i * 30 * 24 * 60 * 60 * 1000))
      });
    }

    return installments;
  }

  private calculateNextPaymentDate(context: any): Date {
    const { frequency = 'monthly' } = context;
    const now = new Date();

    switch (frequency) {
      case 'weekly':
        return new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
      case 'biweekly':
        return new Date(now.getTime() + 14 * 24 * 60 * 60 * 1000);
      case 'monthly':
        return new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
      case 'quarterly':
        return new Date(now.getTime() + 90 * 24 * 60 * 60 * 1000);
      default:
        return new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);
    }
  }

  private async calculateRiskScore(context: any): Promise<number> {
    let score = 0;

    // Country risk
    if (this.highRiskCountries.includes(context.country)) score += 30;
    if (this.sanctionedCountries.includes(context.country)) score += 50;

    // Amount risk
    if (context.amount > 10000) score += 20;
    if (context.amount > 50000) score += 30;

    // Velocity risk
    const velocity = await this.checkVelocity(context.customerId);
    if (velocity.transactionsToday > 5) score += 15;
    if (velocity.amountToday > 10000) score += 20;

    // New customer risk
    if (context.isNewCustomer) score += 10;

    // Payment method risk
    if (context.paymentMethod === 'crypto') score += 25;
    if (context.paymentMethod === 'wire') score += 15;

    return Math.min(100, score);
  }

  private async blockTransaction(context: any, reason: string): Promise<void> {
    await this.redis.zadd(
      'payment:blocked',
      Date.now(),
      JSON.stringify({
        context,
        reason,
        timestamp: new Date().toISOString()
      })
    );

    this.emit('transaction_blocked', { context, reason });
  }

  private async gatherDisputeEvidence(paymentId: string): Promise<any[]> {
    const evidence = [];

    // Get transaction details
    const transaction = await this.redis.get(`payment:transaction:${paymentId}`);
    if (transaction) evidence.push({ type: 'transaction', data: JSON.parse(transaction) });

    // Get customer communications
    const communications = await this.redis.zrange(`payment:communications:${paymentId}`, 0, -1);
    evidence.push({ type: 'communications', data: communications });

    // Get delivery confirmation
    const delivery = await this.redis.get(`payment:delivery:${paymentId}`);
    if (delivery) evidence.push({ type: 'delivery', data: JSON.parse(delivery) });

    return evidence;
  }

  private async checkRefundEligibility(paymentId: string): Promise<{
    allowed: boolean;
    reason?: string;
  }> {
    // Check if already refunded
    const refunded = await this.redis.get(`payment:refunded:${paymentId}`);
    if (refunded) {
      return { allowed: false, reason: 'Already refunded' };
    }

    // Check time limit (e.g., 180 days)
    const payment = await this.redis.get(`payment:transaction:${paymentId}`);
    if (payment) {
      const paymentData = JSON.parse(payment);
      const daysSince = (Date.now() - paymentData.timestamp) / (24 * 60 * 60 * 1000);
      if (daysSince > 180) {
        return { allowed: false, reason: 'Refund period expired' };
      }
    }

    return { allowed: true };
  }

  private async trackPartialRefund(paymentId: string, amount: number): Promise<void> {
    const key = `payment:partial_refunds:${paymentId}`;
    await this.redis.zadd(key, Date.now(), JSON.stringify({ amount, timestamp: Date.now() }));
  }

  private async processTaxRefund(paymentId: string, refundAmount: number): Promise<void> {
    // Calculate tax portion of refund
    // In production, this would integrate with tax calculation service
    const taxAmount = refundAmount * 0.16; // Example tax rate

    await this.redis.zadd(
      'payment:tax_refunds',
      Date.now(),
      JSON.stringify({
        paymentId,
        refundAmount,
        taxAmount,
        timestamp: new Date().toISOString()
      })
    );
  }

  private async checkWatchlists(customerId: string): Promise<boolean> {
    // In production, integrate with watchlist APIs
    // This is a simplified example
    const watchlist = await this.redis.sismember('compliance:watchlist', customerId);
    return watchlist === 1;
  }

  private async detectSuspiciousPatterns(context: any): Promise<boolean> {
    // Check for structuring
    const recentTransactions = await this.getRecentTransactions(context.customerId);
    const structuring = this.detectStructuring(recentTransactions);
    if (structuring) return true;

    // Check for rapid movement
    const rapidMovement = this.detectRapidMovement(recentTransactions);
    if (rapidMovement) return true;

    // Check for unusual patterns
    const unusual = await this.detectUnusualPatterns(context);
    if (unusual) return true;

    return false;
  }

  private async getRecentTransactions(customerId: string): Promise<any[]> {
    const transactions = await this.redis.zrange(
      `payment:customer:${customerId}:transactions`,
      Date.now() - 86400000, // Last 24 hours
      Date.now(),
      'BYSCORE'
    );

    return transactions.map(t => JSON.parse(t));
  }

  private detectStructuring(transactions: any[]): boolean {
    // Check for multiple transactions just below reporting threshold
    const threshold = 10000;
    const nearThreshold = transactions.filter(t =>
      t.amount > threshold * 0.8 && t.amount < threshold
    );

    return nearThreshold.length >= 3;
  }

  private detectRapidMovement(transactions: any[]): boolean {
    // Check for rapid in-and-out pattern
    if (transactions.length < 2) return false;

    const deposits = transactions.filter(t => t.type === 'deposit');
    const withdrawals = transactions.filter(t => t.type === 'withdrawal');

    // If deposit followed by immediate withdrawal
    for (const deposit of deposits) {
      const quickWithdrawal = withdrawals.find(w =>
        Math.abs(w.timestamp - deposit.timestamp) < 3600000 && // Within 1 hour
        Math.abs(w.amount - deposit.amount) < deposit.amount * 0.1 // Similar amount
      );

      if (quickWithdrawal) return true;
    }

    return false;
  }

  private async detectUnusualPatterns(context: any): Promise<boolean> {
    // Get customer profile
    const profile = await this.redis.get(`payment:customer:${context.customerId}:profile`);
    if (!profile) return false;

    const customerProfile = JSON.parse(profile);

    // Check for unusual amount
    if (context.amount > customerProfile.averageTransaction * 10) return true;

    // Check for unusual time
    const hour = new Date().getHours();
    if (customerProfile.typicalHours && !customerProfile.typicalHours.includes(hour)) {
      return true;
    }

    // Check for unusual location
    if (context.country !== customerProfile.primaryCountry) {
      return true;
    }

    return false;
  }

  private async validateVATNumber(vatNumber?: string): Promise<boolean> {
    if (!vatNumber) return false;

    // In production, use VIES API for validation
    // This is a simplified validation
    const vatPattern = /^[A-Z]{2}[0-9A-Z]+$/;
    return vatPattern.test(vatNumber);
  }

  private getKYCThresholds(country: string): { basic: number; enhanced: number } {
    const thresholds: Record<string, { basic: number; enhanced: number }> = {
      US: { basic: 3000, enhanced: 10000 },
      EU: { basic: 1000, enhanced: 15000 },
      MX: { basic: 50000, enhanced: 100000 }, // MXN
      BR: { basic: 10000, enhanced: 50000 }, // BRL
      DEFAULT: { basic: 5000, enhanced: 25000 }
    };

    if (this.isEUCountry(country)) {
      return thresholds.EU;
    }

    return thresholds[country] || thresholds.DEFAULT;
  }

  private async checkVelocity(customerId: string): Promise<{
    transactionsToday: number;
    amountToday: number;
  }> {
    const today = new Date().setHours(0, 0, 0, 0);
    const transactions = await this.redis.zrangebyscore(
      `payment:customer:${customerId}:transactions`,
      today,
      Date.now()
    );

    let totalAmount = 0;
    for (const t of transactions) {
      const transaction = JSON.parse(t);
      totalAmount += transaction.amount;
    }

    return {
      transactionsToday: transactions.length,
      amountToday: totalAmount
    };
  }

  private async logComplianceChecks(context: any, checks: ComplianceCheck[]): Promise<void> {
    await this.redis.zadd(
      'payment:compliance:checks',
      Date.now(),
      JSON.stringify({
        context,
        checks,
        passed: checks.every(c => c.passed),
        timestamp: new Date().toISOString()
      })
    );
  }

  private isEUCountry(country: string): boolean {
    const euCountries = [
      'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
      'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
      'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
    ];
    return euCountries.includes(country);
  }
}