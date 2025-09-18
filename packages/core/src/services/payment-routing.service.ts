import { EventEmitter } from 'events';
import { Redis } from 'ioredis';
import { ConektaProvider } from './providers/conekta.provider';
import { FungiesProvider } from './providers/fungies.provider';
import { StripeProvider } from './providers/stripe.provider';
import {
  PaymentProvider,
  Currency,
  PaymentIntent,
  CheckoutSession
} from '../types/payment.types';

interface RoutingDecision {
  provider: string;
  reason: string;
  confidence: number;
  fallbacks: string[];
  metadata: {
    requiresTaxCompliance: boolean;
    supportsLocalPaymentMethods: boolean;
    estimatedFees: number;
    estimatedSettlementDays: number;
  };
}

interface PaymentContext {
  amount: number;
  currency: Currency;
  country: string;
  customerId?: string;
  isB2B?: boolean;
  requiresInvoice?: boolean;
  preferredPaymentMethod?: string;
  userLanguage?: string;
  deviceInfo?: {
    isMobile: boolean;
    platform: string;
  };
  riskScore?: number;
}

interface ProviderHealth {
  provider: string;
  healthy: boolean;
  latency: number;
  successRate: number;
  lastError?: Date;
  consecutiveFailures: number;
}

export class PaymentRoutingService extends EventEmitter {
  private providers: Map<string, ConektaProvider | FungiesProvider | StripeProvider>;
  private redis: Redis;
  private healthMetrics: Map<string, ProviderHealth>;
  private routingCache: Map<string, RoutingDecision>;

  // Provider cost structure (percentage + fixed fee in USD)
  private providerFees = {
    conekta: {
      card: { percentage: 3.6, fixed: 3.00, currency: 'MXN' },
      oxxo: { percentage: 2.5, fixed: 10.00, currency: 'MXN' },
      spei: { percentage: 1.0, fixed: 8.00, currency: 'MXN' }
    },
    fungies: {
      card: { percentage: 2.9, fixed: 0.30, currency: 'USD' },
      sepa: { percentage: 1.4, fixed: 0.25, currency: 'EUR' }
    },
    stripe: {
      card: { percentage: 2.9, fixed: 0.30, currency: 'USD' },
      ach: { percentage: 0.8, fixed: 0, currency: 'USD' }
    }
  };

  // Settlement times in days
  private settlementTimes = {
    conekta: { card: 2, oxxo: 3, spei: 1 },
    fungies: { card: 2, sepa: 3 },
    stripe: { card: 2, ach: 4 }
  };

  constructor(
    providers: { conekta: ConektaProvider; fungies: FungiesProvider; stripe: StripeProvider },
    redis: Redis
  ) {
    super();
    this.redis = redis;
    this.providers = new Map([
      ['conekta', providers.conekta],
      ['fungies', providers.fungies],
      ['stripe', providers.stripe]
    ] as [string, ConektaProvider | FungiesProvider | StripeProvider][]);
    this.healthMetrics = new Map();
    this.routingCache = new Map();

    this.initializeHealthMonitoring();
  }

  private initializeHealthMonitoring(): void {
    // Initialize health metrics for each provider
    for (const [name, provider] of this.providers) {
      this.healthMetrics.set(name, {
        provider: name,
        healthy: true,
        latency: 0,
        successRate: 100,
        consecutiveFailures: 0
      });

      // TODO: Monitor provider events (providers need to extend EventEmitter)
      // provider.on('payment_succeeded', () => this.recordSuccess(name));
      // provider.on('payment_failed', () => this.recordFailure(name));
    }

    // Periodic health checks
    setInterval(() => this.performHealthChecks(), 60000); // Every minute
  }

  async selectOptimalProvider(context: PaymentContext): Promise<RoutingDecision> {
    // Check cache first
    const cacheKey = this.generateCacheKey(context);
    const cached = this.routingCache.get(cacheKey);
    if (cached && this.isCacheValid(cached)) {
      return cached;
    }

    // Build routing decision
    const decision = await this.buildRoutingDecision(context);

    // Cache the decision
    this.routingCache.set(cacheKey, decision);
    setTimeout(() => this.routingCache.delete(cacheKey), 300000); // 5 min cache

    // Log routing decision for analytics
    await this.logRoutingDecision(decision, context);

    return decision;
  }

  private async buildRoutingDecision(context: PaymentContext): Promise<RoutingDecision> {
    const candidates: Array<{
      provider: string;
      score: number;
      reasons: string[];
    }> = [];

    // Evaluate each provider
    for (const [name, provider] of this.providers) {
      const evaluation = await this.evaluateProvider(name, provider, context);
      if (evaluation.eligible) {
        candidates.push(evaluation);
      }
    }

    // Sort by score (higher is better)
    candidates.sort((a, b) => b.score - a.score);

    if (candidates.length === 0) {
      throw new Error('No payment provider available for this transaction');
    }

    const selected = candidates[0];
    const fallbacks = candidates.slice(1).map(c => c.provider);

    // Build metadata
    const metadata = await this.buildMetadata(selected.provider, context);

    return {
      provider: selected.provider,
      reason: selected.reasons[0],
      confidence: selected.score / 100,
      fallbacks,
      metadata
    };
  }

  private async evaluateProvider(
    name: string,
    provider: ConektaProvider | FungiesProvider | StripeProvider,
    context: PaymentContext
  ): Promise<{ provider: string; eligible: boolean; score: number; reasons: string[] }> {
    const reasons: string[] = [];
    let score = 50; // Base score

    // Check basic availability
    if (!(provider as any).isAvailable || !(provider as any).isAvailable(context.country, context.currency)) {
      return { provider: name, eligible: false, score: 0, reasons: ['Not available'] };
    }

    // Check health
    const health = this.healthMetrics.get(name)!;
    if (!health.healthy) {
      return { provider: name, eligible: false, score: 0, reasons: ['Provider unhealthy'] };
    }

    // RULE 1: Mexico/LATAM with MXN = Conekta priority
    if (name === 'conekta' && (context.country === 'MX' || context.currency === 'MXN')) {
      score += 40;
      reasons.push('Optimal for Mexican market');

      // Bonus for cash payments
      if (context.preferredPaymentMethod === 'oxxo') {
        score += 10;
        reasons.push('OXXO payment available');
      }
    }

    // RULE 2: EU/International tax compliance = Fungies priority
    if (name === 'fungies') {
      if (this.isEUCountry(context.country)) {
        score += 30;
        reasons.push('EU VAT compliance handled');
      }

      if (context.isB2B && context.requiresInvoice) {
        score += 20;
        reasons.push('B2B invoicing and tax handling');
      }

      if (!['MX', 'US', 'CA'].includes(context.country)) {
        score += 15;
        reasons.push('International MoR compliance');
      }
    }

    // RULE 3: Stripe as reliable fallback
    if (name === 'stripe') {
      score += 10; // Base reliability bonus
      reasons.push('Global coverage and reliability');

      // Stripe excels in US/CA
      if (['US', 'CA'].includes(context.country)) {
        score += 25;
        reasons.push('Optimal for North America');
      }

      // Better fraud detection
      if (context.riskScore && context.riskScore > 50) {
        score += 15;
        reasons.push('Advanced fraud detection (Radar)');
      }
    }

    // Performance scoring
    score += Math.max(0, 10 - health.latency / 100); // Lower latency = higher score
    score += health.successRate / 10; // Success rate contribution

    // Cost optimization
    const estimatedFee = this.calculateFee(name, context);
    const feeScore = Math.max(0, 10 - estimatedFee); // Lower fees = higher score
    score += feeScore;

    // Mobile optimization
    if (context.deviceInfo?.isMobile) {
      if (name === 'stripe') {
        score += 5; // Stripe has excellent mobile SDKs
      }
    }

    // Language and localization
    if (context.userLanguage === 'es' && name === 'conekta') {
      score += 5;
      reasons.push('Spanish language support');
    }

    return {
      provider: name,
      eligible: true,
      score: Math.min(100, score),
      reasons
    };
  }

  private async buildMetadata(
    providerName: string,
    context: PaymentContext
  ): Promise<RoutingDecision['metadata']> {
    const requiresTaxCompliance = this.requiresTaxCompliance(context.country);
    const supportsLocalPaymentMethods = this.supportsLocalPaymentMethods(
      providerName,
      context.country
    );
    const estimatedFees = this.calculateFee(providerName, context);
    const estimatedSettlementDays = this.getSettlementTime(providerName, context);

    return {
      requiresTaxCompliance,
      supportsLocalPaymentMethods,
      estimatedFees,
      estimatedSettlementDays
    };
  }

  // Intelligent fallback handling
  async executeWithFallback<T>(
    context: PaymentContext,
    operation: (provider: PaymentProvider) => Promise<T>
  ): Promise<{ result: T; provider: string; attempts: number }> {
    const routing = await this.selectOptimalProvider(context);
    const providers = [routing.provider, ...routing.fallbacks];
    let lastError: Error | undefined;
    let attempts = 0;

    for (const providerName of providers) {
      const provider = this.providers.get(providerName);
      if (!provider) continue;

      attempts++;

      try {
        // Add timeout protection
        const timeout = new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Operation timeout')), 30000)
        );

        const result = await Promise.race([
          operation(providerName as PaymentProvider),
          timeout
        ]) as T;

        // Record success
        this.recordSuccess(providerName);

        return {
          result,
          provider: providerName,
          attempts
        };
      } catch (error: any) {
        lastError = error;
        this.recordFailure(providerName);

        // Log failure for monitoring
        await this.logFailure(providerName, error, context);

        // If it's a critical error, don't try fallback
        if (this.isCriticalError(error)) {
          throw error;
        }

        // Continue to next provider
        this.emit('provider_fallback', {
          failed: providerName,
          next: providers[attempts] || null,
          error: error.message
        });
      }
    }

    throw new Error(
      `All payment providers failed. Last error: ${lastError?.message}`
    );
  }

  // Health monitoring
  private async performHealthChecks(): Promise<void> {
    for (const [name, provider] of this.providers) {
      try {
        const start = Date.now();

        // Simple health check - attempt to validate webhook
        await (provider as any).validateWebhook?.('test', 'test');

        const latency = Date.now() - start;
        const health = this.healthMetrics.get(name)!;

        health.latency = (health.latency * 0.9 + latency * 0.1); // Weighted average
        health.healthy = true;
        health.consecutiveFailures = 0;
      } catch (error) {
        const health = this.healthMetrics.get(name)!;
        health.consecutiveFailures++;

        if (health.consecutiveFailures >= 3) {
          health.healthy = false;
          this.emit('provider_unhealthy', { provider: name });
        }
      }
    }
  }

  private recordSuccess(provider: string): void {
    const health = this.healthMetrics.get(provider);
    if (health) {
      health.successRate = Math.min(100, health.successRate * 0.95 + 5);
      health.consecutiveFailures = 0;
      health.healthy = true;
    }
  }

  private recordFailure(provider: string): void {
    const health = this.healthMetrics.get(provider);
    if (health) {
      health.successRate = Math.max(0, health.successRate * 0.95);
      health.consecutiveFailures++;
      health.lastError = new Date();

      if (health.consecutiveFailures >= 3) {
        health.healthy = false;
      }
    }
  }

  // Helper methods
  private calculateFee(provider: string, context: PaymentContext): number {
    const fees = this.providerFees[provider as keyof typeof this.providerFees];
    if (!fees) return 5; // Default fee estimate

    const method = context.preferredPaymentMethod || 'card';
    const fee = fees[method as keyof typeof fees] || fees.card;

    const percentageFee = (context.amount * fee.percentage) / 100;
    const fixedFee = this.convertCurrency(fee.fixed, fee.currency, context.currency);

    return percentageFee + fixedFee;
  }

  private getSettlementTime(provider: string, context: PaymentContext): number {
    const times = this.settlementTimes[provider as keyof typeof this.settlementTimes];
    if (!times) return 3; // Default settlement time

    const method = context.preferredPaymentMethod || 'card';
    return times[method as keyof typeof times] || times.card || 3;
  }

  private convertCurrency(amount: number, from: string, to: string): number {
    // Simplified currency conversion (in production, use real rates)
    const rates: Record<string, number> = {
      'USD': 1,
      'EUR': 0.92,
      'MXN': 17.5,
      'GBP': 0.79,
      'CAD': 1.35
    };

    const usdAmount = amount / (rates[from] || 1);
    return usdAmount * (rates[to] || 1);
  }

  private isEUCountry(country: string): boolean {
    const euCountries = [
      'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
      'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
      'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
    ];
    return euCountries.includes(country);
  }

  private requiresTaxCompliance(country: string): boolean {
    // Countries requiring special tax compliance
    return this.isEUCountry(country) ||
           ['GB', 'AU', 'NZ', 'JP', 'KR', 'SG', 'IN'].includes(country);
  }

  private supportsLocalPaymentMethods(provider: string, country: string): boolean {
    if (provider === 'conekta' && country === 'MX') return true;
    if (provider === 'fungies' && this.isEUCountry(country)) return true;
    if (provider === 'stripe') return true; // Stripe has wide coverage
    return false;
  }

  private isCriticalError(error: Error): boolean {
    const criticalMessages = [
      'insufficient_funds',
      'card_declined',
      'fraudulent',
      'invalid_account',
      'compliance_violation'
    ];

    return criticalMessages.some(msg =>
      error.message.toLowerCase().includes(msg)
    );
  }

  private generateCacheKey(context: PaymentContext): string {
    return `${context.country}-${context.currency}-${context.amount}-${context.preferredPaymentMethod || 'any'}`;
  }

  private isCacheValid(decision: RoutingDecision): boolean {
    const health = this.healthMetrics.get(decision.provider);
    return health?.healthy || false;
  }

  private async logRoutingDecision(
    decision: RoutingDecision,
    context: PaymentContext
  ): Promise<void> {
    await this.redis.zadd(
      'payment:routing:decisions',
      Date.now(),
      JSON.stringify({
        decision,
        context,
        timestamp: new Date().toISOString()
      })
    );
  }

  private async logFailure(
    provider: string,
    error: Error,
    context: PaymentContext
  ): Promise<void> {
    await this.redis.zadd(
      'payment:routing:failures',
      Date.now(),
      JSON.stringify({
        provider,
        error: error.message,
        context,
        timestamp: new Date().toISOString()
      })
    );
  }

  // Public methods for monitoring
  async getProviderHealth(): Promise<ProviderHealth[]> {
    return Array.from(this.healthMetrics.values());
  }

  async getRoutingStats(timeRange: { start: Date; end: Date }): Promise<{
    totalDecisions: number;
    providerDistribution: Record<string, number>;
    averageConfidence: number;
    fallbackRate: number;
  }> {
    const decisions = await this.redis.zrangebyscore(
      'payment:routing:decisions',
      timeRange.start.getTime(),
      timeRange.end.getTime()
    );

    const stats = {
      totalDecisions: decisions.length,
      providerDistribution: {} as Record<string, number>,
      averageConfidence: 0,
      fallbackRate: 0
    };

    let totalConfidence = 0;
    let fallbackCount = 0;

    for (const entry of decisions) {
      const data = JSON.parse(entry);
      const provider = data.decision.provider;

      stats.providerDistribution[provider] =
        (stats.providerDistribution[provider] || 0) + 1;

      totalConfidence += data.decision.confidence;

      if (data.decision.fallbacks.length > 0) {
        fallbackCount++;
      }
    }

    stats.averageConfidence = totalConfidence / decisions.length;
    stats.fallbackRate = fallbackCount / decisions.length;

    return stats;
  }

  // Smart checkout optimization
  async optimizeCheckoutFlow(context: PaymentContext): Promise<{
    recommendedProvider: string;
    paymentMethods: string[];
    estimatedSuccessRate: number;
    userExperienceScore: number;
    optimizations: string[];
  }> {
    const routing = await this.selectOptimalProvider(context);
    const provider = this.providers.get(routing.provider)!;

    const optimizations: string[] = [];
    let uxScore = 70; // Base UX score

    // Payment method recommendations
    const paymentMethods: string[] = ['card']; // Always include card

    if (context.country === 'MX') {
      paymentMethods.push('oxxo', 'spei');
      optimizations.push('Enable cash payments for Mexico');
      uxScore += 10;
    }

    if (this.isEUCountry(context.country)) {
      paymentMethods.push('sepa_debit', 'ideal');
      optimizations.push('Enable SEPA for EU customers');
      uxScore += 5;
    }

    // Mobile optimizations
    if (context.deviceInfo?.isMobile) {
      optimizations.push('Use mobile-optimized checkout');
      optimizations.push('Enable digital wallets (Apple Pay, Google Pay)');
      paymentMethods.push('apple_pay', 'google_pay');
      uxScore += 10;
    }

    // Risk-based optimizations
    if (context.riskScore && context.riskScore < 30) {
      optimizations.push('Skip 3D Secure for low-risk transactions');
      uxScore += 5;
    }

    // Language optimizations
    if (context.userLanguage === 'es' && routing.provider === 'conekta') {
      optimizations.push('Display in Spanish for better conversion');
      uxScore += 5;
    }

    // Calculate estimated success rate
    const health = this.healthMetrics.get(routing.provider)!;
    const estimatedSuccessRate = health.successRate * 0.9; // Conservative estimate

    return {
      recommendedProvider: routing.provider,
      paymentMethods,
      estimatedSuccessRate,
      userExperienceScore: Math.min(100, uxScore),
      optimizations
    };
  }
}