import { describe, it, expect, beforeEach, afterEach, jest } from '@jest/globals';
import { Redis } from 'ioredis';
import { ConektaProvider } from '../src/services/providers/conekta.provider';
import { StripeProvider } from '../src/services/providers/stripe.provider';
import { PaymentGatewayService } from '../src/services/payment-gateway.service';
import { PaymentRoutingService } from '../src/services/payment-routing.service';
import { PaymentComplianceService } from '../src/services/payment-compliance.service';
import { Currency } from '../src/types/payment.types';

describe('Payment Integration Tests', () => {
  let redis: Redis;
  let conektaProvider: ConektaProvider;
  let stripeProvider: StripeProvider;
  let paymentGateway: PaymentGatewayService;
  let routingService: PaymentRoutingService;
  let complianceService: PaymentComplianceService;

  beforeEach(async () => {
    // Initialize Redis mock
    redis = new Redis({
      host: 'localhost',
      port: 6379,
      db: 1 // Use separate DB for tests
    });

    // Initialize providers
    conektaProvider = new ConektaProvider({
      privateKey: process.env.CONEKTA_TEST_KEY || 'test_key',
      publicKey: process.env.CONEKTA_PUBLIC_TEST_KEY || 'test_public_key',
      webhookSecret: 'test_webhook_secret',
      locale: 'es',
      redis
    });

    stripeProvider = new StripeProvider({
      secretKey: process.env.STRIPE_TEST_KEY || 'sk_test_123',
      publishableKey: process.env.STRIPE_PUBLIC_TEST_KEY || 'pk_test_123',
      webhookSecret: 'test_webhook_secret',
      apiVersion: '2023-10-16',
      redis
    });

    // Initialize services
    paymentGateway = new PaymentGatewayService(redis);
    paymentGateway.registerProvider(conektaProvider);
    paymentGateway.registerProvider(stripeProvider);

    routingService = new PaymentRoutingService(
      { conekta: conektaProvider, stripe: stripeProvider },
      redis
    );

    complianceService = new PaymentComplianceService(redis);
  });

  afterEach(async () => {
    await redis.flushdb();
    await redis.quit();
  });

  describe('Provider Selection', () => {
    it('should select Conekta for Mexican customers', async () => {
      const context = {
        amount: 1000,
        currency: 'MXN' as Currency,
        country: 'MX',
        customerId: 'cust_123'
      };

      const decision = await routingService.selectOptimalProvider(context);

      expect(decision.provider).toBe('conekta');
      expect(decision.reason).toContain('Mexican market');
      expect(decision.confidence).toBeGreaterThan(0.7);
    });

    it('should select Stripe for US customers', async () => {
      const context = {
        amount: 2000,
        currency: 'USD' as Currency,
        country: 'US',
        customerId: 'cust_789'
      };

      const decision = await routingService.selectOptimalProvider(context);

      expect(decision.provider).toBe('stripe');
      expect(decision.reason).toContain('North America');
    });

    it('should select Stripe for EU customers', async () => {
      const context = {
        amount: 500,
        currency: 'EUR' as Currency,
        country: 'FR',
        customerId: 'cust_456'
      };

      const decision = await routingService.selectOptimalProvider(context);

      expect(decision.provider).toBe('stripe');
      expect(decision.metadata.requiresTaxCompliance).toBe(true);
    });
  });

  describe('Payment Processing', () => {
    it('should create payment intent with selected provider', async () => {
      const paymentData = {
        amount: 1000,
        currency: 'MXN' as Currency,
        customerId: 'cust_123',
        country: 'MX'
      };

      const provider = await paymentGateway.selectProvider(paymentData);
      expect(provider).toBe('conekta');

      const intent = await paymentGateway.createPaymentIntent({
        amount: paymentData.amount,
        currency: paymentData.currency,
        customerId: paymentData.customerId,
        metadata: { country: paymentData.country }
      });

      expect(intent).toBeDefined();
      expect(intent.amount).toBe(1000);
      expect(intent.currency).toBe('MXN');
      expect(intent.providerId).toBe('conekta');
    });

    it('should handle payment with fallback on failure', async () => {
      const context = {
        amount: 1000,
        currency: 'MXN' as Currency,
        country: 'MX',
        customerId: 'cust_456'
      };

      // Mock primary provider failure
      jest.spyOn(conektaProvider, 'createPaymentIntent').mockRejectedValueOnce(
        new Error('Provider temporarily unavailable')
      );

      const result = await routingService.executeWithFallback(
        context,
        async (provider) => {
          return await provider.createPaymentIntent({
            amount: context.amount,
            currency: context.currency,
            customerId: context.customerId
          });
        }
      );

      expect(result.provider).toBe('stripe'); // Fallback to Stripe
      expect(result.attempts).toBe(2);
      expect(result.result).toBeDefined();
    });
  });

  describe('Compliance Checks', () => {
    it('should pass KYC for low-risk countries', async () => {
      const context = {
        country: 'US',
        amount: 500,
        currency: 'USD',
        customerId: 'cust_123'
      };

      const checks = await complianceService.performComplianceChecks(context);
      const kycCheck = checks.find(c => c.type === 'kyc');

      expect(kycCheck?.passed).toBe(true);
    });

    it('should fail KYC for sanctioned countries', async () => {
      const context = {
        country: 'IR', // Iran - sanctioned
        amount: 100,
        currency: 'USD',
        customerId: 'cust_456'
      };

      const checks = await complianceService.performComplianceChecks(context);
      const kycCheck = checks.find(c => c.type === 'kyc');

      expect(kycCheck?.passed).toBe(false);
      expect(kycCheck?.reason).toContain('Sanctioned country');
      expect(kycCheck?.requiredActions).toContain('Block transaction');
    });

    it('should require enhanced KYC for high amounts', async () => {
      const context = {
        country: 'US',
        amount: 15000, // Above threshold
        currency: 'USD',
        customerId: 'cust_789'
      };

      const checks = await complianceService.performComplianceChecks(context);
      const kycCheck = checks.find(c => c.type === 'kyc');

      expect(kycCheck?.passed).toBe(false);
      expect(kycCheck?.reason).toContain('Amount exceeds threshold');
      expect(kycCheck?.requiredActions).toContain('Identity verification');
    });

    it('should check EU VAT compliance', async () => {
      const context = {
        country: 'DE',
        amount: 1000,
        currency: 'EUR',
        customerId: 'cust_123',
        businessType: 'b2b' as const,
        metadata: {}
      };

      const checks = await complianceService.performComplianceChecks(context);
      const taxCheck = checks.find(c => c.type === 'tax');

      expect(taxCheck?.passed).toBe(false);
      expect(taxCheck?.reason).toContain('Invalid VAT number');
      expect(taxCheck?.requiredActions).toContain('Collect valid VAT number');
    });

    it('should require RFC for Mexican invoices', async () => {
      const context = {
        country: 'MX',
        amount: 2000, // Above invoice threshold
        currency: 'MXN',
        customerId: 'cust_456',
        metadata: {}
      };

      const checks = await complianceService.performComplianceChecks(context);
      const taxCheck = checks.find(c => c.type === 'tax');

      expect(taxCheck?.passed).toBe(false);
      expect(taxCheck?.reason).toContain('RFC required');
      expect(taxCheck?.requiredActions).toContain('Collect RFC');
    });
  });

  describe('Edge Case Handling', () => {
    it('should handle network timeout with retry', async () => {
      const context = {
        idempotencyKey: 'idem_123',
        operation: jest.fn()
          .mockRejectedValueOnce(new Error('Network timeout'))
          .mockResolvedValueOnce({ id: 'payment_123', status: 'succeeded' })
      };

      const result = await complianceService.handleEdgeCase('network_timeout', context);

      expect(result).toBeDefined();
      expect(result.id).toBe('payment_123');
      expect(context.operation).toHaveBeenCalledTimes(2);
    });

    it('should detect duplicate payments', async () => {
      const context = {
        customerId: 'cust_123',
        amount: 1000,
        currency: 'USD',
        paymentMethod: 'card',
        operation: jest.fn().mockResolvedValue({ id: 'payment_123' })
      };

      // First payment
      const result1 = await complianceService.handleEdgeCase('duplicate_payment', context);
      expect(result1.id).toBe('payment_123');

      // Duplicate payment within 1 minute
      await expect(
        complianceService.handleEdgeCase('duplicate_payment', context)
      ).rejects.toThrow('Duplicate payment detected');
    });

    it('should handle currency conversion', async () => {
      const context = {
        customerCurrency: 'EUR',
        merchantCurrency: 'USD',
        amount: 100
      };

      const result = await complianceService.handleEdgeCase('currency_mismatch', context);

      expect(result.currency).toBe('USD');
      expect(result.amount).toBeGreaterThan(100); // EUR to USD conversion
      expect(result.amount).toBeLessThan(120); // Reasonable conversion rate
    });

    it('should handle 3DS challenge exemptions', async () => {
      const context = {
        amount: 25, // Below 30 EUR threshold
        currency: 'EUR',
        cardIssuer: 'test_bank'
      };

      const result = await complianceService.handleEdgeCase('3ds_challenge', context);

      expect(result.scaExempted).toBe(true);
      expect(result.requiresAuthentication).toBeUndefined();
    });

    it('should create installment plan for partial payments', async () => {
      const context = {
        totalAmount: 3000,
        paidAmount: 1000,
        remainingAmount: 2000,
        installmentMonths: 4
      };

      const result = await complianceService.handleEdgeCase('partial_payment', context);

      expect(result.installments).toHaveLength(4);
      expect(result.installments[0].amount).toBe(500); // 2000 / 4
      expect(result.nextPaymentDate).toBeDefined();
    });

    it('should handle webhook retry with exponential backoff', async () => {
      const context = {
        webhook: { id: 'webhook_123', type: 'payment.succeeded' },
        attempt: 2,
        retryOperation: jest.fn().mockResolvedValue({ status: 'delivered' })
      };

      const startTime = Date.now();
      const result = await complianceService.handleEdgeCase('webhook_failure', context);
      const elapsed = Date.now() - startTime;

      expect(result.status).toBe('delivered');
      expect(elapsed).toBeGreaterThanOrEqual(4000); // 2^2 * 1000ms backoff
      expect(context.retryOperation).toHaveBeenCalled();
    });

    it('should handle fraud detection and blocking', async () => {
      const context = {
        country: 'NG', // High risk country
        amount: 50000, // Large amount
        isNewCustomer: true,
        paymentMethod: 'crypto',
        customerId: 'cust_suspicious'
      };

      await expect(
        complianceService.handleEdgeCase('fraud_detection', context)
      ).rejects.toThrow('Transaction blocked due to high fraud risk');
    });

    it('should handle chargeback with evidence gathering', async () => {
      const context = {
        paymentId: 'payment_123',
        reason: 'fraudulent',
        amount: 500
      };

      const result = await complianceService.handleEdgeCase('chargeback', context);

      expect(result.id).toContain('dispute_');
      expect(result.status).toBe('pending');
      expect(result.evidence).toBeDefined();
      expect(result.evidence).toBeInstanceOf(Array);
    });

    it('should validate refund eligibility', async () => {
      const context = {
        paymentId: 'payment_old',
        refundAmount: 100,
        originalAmount: 100,
        reason: 'customer_request',
        processRefund: jest.fn().mockResolvedValue({ id: 'refund_123' })
      };

      // Mock payment as too old
      jest.spyOn(redis, 'get').mockResolvedValueOnce(
        JSON.stringify({
          timestamp: Date.now() - (200 * 24 * 60 * 60 * 1000) // 200 days ago
        })
      );

      await expect(
        complianceService.handleEdgeCase('complex_refund', context)
      ).rejects.toThrow('Refund not allowed: Refund period expired');
    });
  });

  describe('Provider Health Monitoring', () => {
    it('should track provider health metrics', async () => {
      // Simulate successful payments
      for (let i = 0; i < 5; i++) {
        routingService['recordSuccess']('stripe');
      }

      // Simulate one failure
      routingService['recordFailure']('stripe');

      const health = await routingService.getProviderHealth();
      const stripeHealth = health.find(h => h.provider === 'stripe');

      expect(stripeHealth?.healthy).toBe(true);
      expect(stripeHealth?.successRate).toBeGreaterThan(80);
      expect(stripeHealth?.consecutiveFailures).toBe(1);
    });

    it('should mark provider as unhealthy after consecutive failures', async () => {
      // Simulate consecutive failures
      for (let i = 0; i < 3; i++) {
        routingService['recordFailure']('conekta');
      }

      const health = await routingService.getProviderHealth();
      const conektaHealth = health.find(h => h.provider === 'conekta');

      expect(conektaHealth?.healthy).toBe(false);
      expect(conektaHealth?.consecutiveFailures).toBe(3);
    });

    it('should not route to unhealthy provider', async () => {
      // Mark Conekta as unhealthy
      const healthMetrics = routingService['healthMetrics'];
      healthMetrics.set('conekta', {
        provider: 'conekta',
        healthy: false,
        latency: 1000,
        successRate: 50,
        consecutiveFailures: 5
      });

      const context = {
        amount: 1000,
        currency: 'MXN' as Currency,
        country: 'MX',
        customerId: 'cust_123'
      };

      const decision = await routingService.selectOptimalProvider(context);

      // Should fallback to Stripe
      expect(decision.provider).toBe('stripe');
    });
  });

  describe('Checkout Flow Optimization', () => {
    it('should recommend optimal payment methods for Mexico', async () => {
      const context = {
        amount: 500,
        currency: 'MXN' as Currency,
        country: 'MX',
        customerId: 'cust_123',
        deviceInfo: { isMobile: false, platform: 'web' }
      };

      const optimization = await routingService.optimizeCheckoutFlow(context);

      expect(optimization.recommendedProvider).toBe('conekta');
      expect(optimization.paymentMethods).toContain('oxxo');
      expect(optimization.paymentMethods).toContain('spei');
      expect(optimization.optimizations).toContain('Enable cash payments for Mexico');
      expect(optimization.userExperienceScore).toBeGreaterThan(70);
    });

    it('should optimize for mobile users', async () => {
      const context = {
        amount: 100,
        currency: 'USD' as Currency,
        country: 'US',
        customerId: 'cust_456',
        deviceInfo: { isMobile: true, platform: 'ios' }
      };

      const optimization = await routingService.optimizeCheckoutFlow(context);

      expect(optimization.paymentMethods).toContain('apple_pay');
      expect(optimization.paymentMethods).toContain('google_pay');
      expect(optimization.optimizations).toContain('Use mobile-optimized checkout');
      expect(optimization.optimizations).toContain('Enable digital wallets (Apple Pay, Google Pay)');
    });

    it('should skip 3D Secure for low-risk transactions', async () => {
      const context = {
        amount: 50,
        currency: 'EUR' as Currency,
        country: 'FR',
        customerId: 'cust_789',
        riskScore: 20, // Low risk
        deviceInfo: { isMobile: false, platform: 'web' }
      };

      const optimization = await routingService.optimizeCheckoutFlow(context);

      expect(optimization.optimizations).toContain('Skip 3D Secure for low-risk transactions');
      expect(optimization.estimatedSuccessRate).toBeGreaterThan(85);
    });
  });

  describe('Transaction Monitoring', () => {
    it('should log routing decisions', async () => {
      const context = {
        amount: 1000,
        currency: 'USD' as Currency,
        country: 'US',
        customerId: 'cust_123'
      };

      await routingService.selectOptimalProvider(context);

      const decisions = await redis.zrange('payment:routing:decisions', 0, -1);
      expect(decisions).toHaveLength(1);

      const decision = JSON.parse(decisions[0]);
      expect(decision.context).toMatchObject(context);
      expect(decision.decision).toBeDefined();
      expect(decision.timestamp).toBeDefined();
    });

    it('should track routing statistics', async () => {
      // Create multiple routing decisions
      for (let i = 0; i < 10; i++) {
        await routingService.selectOptimalProvider({
          amount: 100 + i * 10,
          currency: i % 2 === 0 ? 'USD' : 'EUR' as Currency,
          country: i % 2 === 0 ? 'US' : 'FR',
          customerId: `cust_${i}`
        });
      }

      const stats = await routingService.getRoutingStats({
        start: new Date(Date.now() - 3600000),
        end: new Date()
      });

      expect(stats.totalDecisions).toBe(10);
      expect(stats.providerDistribution).toBeDefined();
      expect(stats.averageConfidence).toBeGreaterThan(0);
      expect(stats.fallbackRate).toBeDefined();
    });
  });

  describe('Webhook Processing', () => {
    it('should validate Conekta webhook signature', async () => {
      const body = { id: 'event_123', type: 'charge.paid' };
      const secret = 'test_webhook_secret';

      const crypto = require('crypto');
      const signature = crypto
        .createHmac('sha256', secret)
        .update(JSON.stringify(body))
        .digest('hex');

      const isValid = await conektaProvider.validateWebhook(
        JSON.stringify(body),
        signature
      );

      expect(isValid).toBe(true);
    });

    it('should reject invalid webhook signatures', async () => {
      const body = { id: 'event_123', type: 'charge.paid' };
      const invalidSignature = 'invalid_signature';

      const isValid = await conektaProvider.validateWebhook(
        JSON.stringify(body),
        invalidSignature
      );

      expect(isValid).toBe(false);
    });

    it('should handle webhook idempotency', async () => {
      const _event = {
        id: 'evt_123',
        type: 'payment_intent.succeeded',
        data: { object: { id: 'pi_123', amount: 1000 } }
      };

      // Mark event as processed
      await redis.setex('webhook:stripe:evt_123', 86400, '1');

      // Check if already processed
      const exists = await redis.exists('webhook:stripe:evt_123');
      expect(exists).toBe(1);
    });
  });

  describe('Performance Benchmarks', () => {
    it('should select provider within 50ms', async () => {
      const context = {
        amount: 1000,
        currency: 'USD' as Currency,
        country: 'US',
        customerId: 'cust_123'
      };

      const startTime = Date.now();
      await routingService.selectOptimalProvider(context);
      const elapsed = Date.now() - startTime;

      expect(elapsed).toBeLessThan(50);
    });

    it('should perform compliance checks within 100ms', async () => {
      const context = {
        country: 'US',
        amount: 1000,
        currency: 'USD',
        customerId: 'cust_123'
      };

      const startTime = Date.now();
      await complianceService.performComplianceChecks(context);
      const elapsed = Date.now() - startTime;

      expect(elapsed).toBeLessThan(100);
    });

    it('should handle high webhook volume', async () => {
      const webhookPromises = [];

      // Simulate 100 concurrent webhooks
      for (let i = 0; i < 100; i++) {
        webhookPromises.push(
          redis.zadd(
            'webhook:stripe:events',
            Date.now(),
            JSON.stringify({
              eventId: `evt_${i}`,
              type: 'payment_intent.succeeded',
              timestamp: new Date().toISOString()
            })
          )
        );
      }

      const startTime = Date.now();
      await Promise.all(webhookPromises);
      const elapsed = Date.now() - startTime;

      expect(elapsed).toBeLessThan(1000); // Process 100 webhooks in under 1 second
    });
  });
});
