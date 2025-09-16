import { Request, Response, NextFunction } from 'express';
import { Redis } from 'ioredis';
import crypto from 'crypto';
import { ConektaProvider } from '@plinto/core/services/providers/conekta.provider';
import { FungiesProvider } from '@plinto/core/services/providers/fungies.provider';
import { StripeProvider } from '@plinto/core/services/providers/stripe.provider';
import { PaymentGatewayService } from '@plinto/core/services/payment-gateway.service';

interface WebhookConfig {
  conekta: {
    secret: string;
    tolerance: number;
  };
  fungies: {
    secret: string;
    tolerance: number;
  };
  stripe: {
    secret: string;
    tolerance: number;
  };
}

export class WebhookController {
  private redis: Redis;
  private config: WebhookConfig;
  private providers: {
    conekta: ConektaProvider;
    fungies: FungiesProvider;
    stripe: StripeProvider;
  };
  private paymentGateway: PaymentGatewayService;

  constructor(
    redis: Redis,
    config: WebhookConfig,
    providers: {
      conekta: ConektaProvider;
      fungies: FungiesProvider;
      stripe: StripeProvider;
    },
    paymentGateway: PaymentGatewayService
  ) {
    this.redis = redis;
    this.config = config;
    this.providers = providers;
    this.paymentGateway = paymentGateway;
  }

  // Conekta webhook handler
  async handleConektaWebhook(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      // Validate signature
      const signature = req.headers['x-conekta-signature'] as string;
      const rawBody = req.body; // Requires raw body middleware

      const isValid = await this.validateConektaSignature(rawBody, signature);
      if (!isValid) {
        res.status(401).json({ error: 'Invalid webhook signature' });
        return;
      }

      // Check for duplicate processing (idempotency)
      const eventId = req.body.id;
      const processed = await this.isEventProcessed('conekta', eventId);
      if (processed) {
        res.status(200).json({ status: 'already_processed' });
        return;
      }

      // Process webhook event
      const event = this.parseConektaEvent(req.body);
      await this.processWebhookEvent('conekta', event);

      // Mark as processed
      await this.markEventProcessed('conekta', eventId);

      // Log for monitoring
      await this.logWebhookEvent('conekta', event);

      res.status(200).json({ status: 'success' });
    } catch (error) {
      await this.handleWebhookError('conekta', error as Error, req.body);
      next(error);
    }
  }

  // Fungies webhook handler
  async handleFungiesWebhook(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      // Validate signature
      const signature = req.headers['x-fungies-signature'] as string;
      const rawBody = JSON.stringify(req.body);

      const isValid = await this.validateFungiesSignature(rawBody, signature);
      if (!isValid) {
        res.status(401).json({ error: 'Invalid webhook signature' });
        return;
      }

      // Check for duplicate processing
      const eventId = req.body.event_id;
      const processed = await this.isEventProcessed('fungies', eventId);
      if (processed) {
        res.status(200).json({ status: 'already_processed' });
        return;
      }

      // Process webhook event
      const event = this.parseFungiesEvent(req.body);
      await this.processWebhookEvent('fungies', event);

      // Mark as processed
      await this.markEventProcessed('fungies', eventId);

      // Log for monitoring
      await this.logWebhookEvent('fungies', event);

      res.status(200).json({ status: 'success' });
    } catch (error) {
      await this.handleWebhookError('fungies', error as Error, req.body);
      next(error);
    }
  }

  // Stripe webhook handler
  async handleStripeWebhook(req: Request, res: Response, next: NextFunction): Promise<void> {
    try {
      // Validate signature
      const signature = req.headers['stripe-signature'] as string;
      const rawBody = req.body; // Requires raw body middleware

      const isValid = await this.validateStripeSignature(rawBody, signature);
      if (!isValid) {
        res.status(401).json({ error: 'Invalid webhook signature' });
        return;
      }

      // Stripe SDK handles event construction
      const stripe = require('stripe')(this.config.stripe.secret);
      const event = stripe.webhooks.constructEvent(
        rawBody,
        signature,
        this.config.stripe.secret
      );

      // Check for duplicate processing
      const eventId = event.id;
      const processed = await this.isEventProcessed('stripe', eventId);
      if (processed) {
        res.status(200).json({ status: 'already_processed' });
        return;
      }

      // Process webhook event
      await this.processWebhookEvent('stripe', event);

      // Mark as processed
      await this.markEventProcessed('stripe', eventId);

      // Log for monitoring
      await this.logWebhookEvent('stripe', event);

      res.status(200).json({ status: 'success' });
    } catch (error) {
      await this.handleWebhookError('stripe', error as Error, req.body);
      next(error);
    }
  }

  // Unified webhook processor
  private async processWebhookEvent(provider: string, event: any): Promise<void> {
    const startTime = Date.now();

    try {
      switch (event.type) {
        // Payment events
        case 'payment_intent.succeeded':
        case 'charge.succeeded':
        case 'payment.succeeded':
          await this.handlePaymentSuccess(provider, event);
          break;

        case 'payment_intent.payment_failed':
        case 'charge.failed':
        case 'payment.failed':
          await this.handlePaymentFailure(provider, event);
          break;

        case 'payment_intent.processing':
        case 'charge.pending':
        case 'payment.processing':
          await this.handlePaymentProcessing(provider, event);
          break;

        // Refund events
        case 'charge.refunded':
        case 'refund.created':
        case 'refund.succeeded':
          await this.handleRefundSuccess(provider, event);
          break;

        case 'refund.failed':
          await this.handleRefundFailure(provider, event);
          break;

        // Subscription events
        case 'customer.subscription.created':
        case 'subscription.created':
          await this.handleSubscriptionCreated(provider, event);
          break;

        case 'customer.subscription.updated':
        case 'subscription.updated':
          await this.handleSubscriptionUpdated(provider, event);
          break;

        case 'customer.subscription.deleted':
        case 'subscription.cancelled':
          await this.handleSubscriptionCancelled(provider, event);
          break;

        // Dispute/Chargeback events
        case 'charge.dispute.created':
        case 'dispute.created':
        case 'chargeback.created':
          await this.handleDisputeCreated(provider, event);
          break;

        case 'charge.dispute.updated':
        case 'dispute.updated':
          await this.handleDisputeUpdated(provider, event);
          break;

        // Invoice events
        case 'invoice.payment_succeeded':
        case 'invoice.paid':
          await this.handleInvoicePaid(provider, event);
          break;

        case 'invoice.payment_failed':
        case 'invoice.failed':
          await this.handleInvoiceFailed(provider, event);
          break;

        // Customer events
        case 'customer.created':
          await this.handleCustomerCreated(provider, event);
          break;

        case 'customer.updated':
          await this.handleCustomerUpdated(provider, event);
          break;

        // Compliance events (Fungies specific)
        case 'tax_calculation.completed':
          await this.handleTaxCalculation(provider, event);
          break;

        case 'compliance.document_required':
          await this.handleComplianceRequest(provider, event);
          break;

        // Conekta specific events
        case 'order.paid':
          await this.handleConektaOrderPaid(provider, event);
          break;

        case 'oxxo.payment_received':
          await this.handleOxxoPayment(provider, event);
          break;

        case 'spei.received':
          await this.handleSpeiPayment(provider, event);
          break;

        default:
          await this.handleUnknownEvent(provider, event);
      }

      // Record processing time
      const processingTime = Date.now() - startTime;
      await this.recordWebhookMetrics(provider, event.type, processingTime, 'success');

    } catch (error) {
      const processingTime = Date.now() - startTime;
      await this.recordWebhookMetrics(provider, event.type, processingTime, 'failure');
      throw error;
    }
  }

  // Payment success handler
  private async handlePaymentSuccess(provider: string, event: any): Promise<void> {
    const paymentData = this.extractPaymentData(provider, event);

    // Update payment status in database
    await this.updatePaymentStatus(paymentData.paymentId, 'succeeded');

    // Update customer balance if applicable
    if (paymentData.customerId) {
      await this.updateCustomerBalance(paymentData.customerId, paymentData.amount);
    }

    // Send confirmation email
    await this.sendPaymentConfirmation(paymentData);

    // Trigger post-payment workflows
    await this.triggerPostPaymentWorkflows(paymentData);

    // Emit event for other services
    this.emitPaymentEvent('payment.succeeded', paymentData);
  }

  // Payment failure handler
  private async handlePaymentFailure(provider: string, event: any): Promise<void> {
    const paymentData = this.extractPaymentData(provider, event);

    // Update payment status
    await this.updatePaymentStatus(paymentData.paymentId, 'failed');

    // Log failure reason
    await this.logPaymentFailure(paymentData, event.data?.failure_message);

    // Send failure notification
    await this.sendPaymentFailureNotification(paymentData);

    // Check for retry eligibility
    if (await this.isRetryEligible(paymentData)) {
      await this.schedulePaymentRetry(paymentData);
    }

    // Emit event
    this.emitPaymentEvent('payment.failed', paymentData);
  }

  // Subscription created handler
  private async handleSubscriptionCreated(provider: string, event: any): Promise<void> {
    const subscriptionData = this.extractSubscriptionData(provider, event);

    // Create subscription record
    await this.createSubscriptionRecord(subscriptionData);

    // Provision services
    await this.provisionSubscriptionServices(subscriptionData);

    // Send welcome email
    await this.sendSubscriptionWelcome(subscriptionData);

    // Emit event
    this.emitPaymentEvent('subscription.created', subscriptionData);
  }

  // Dispute created handler
  private async handleDisputeCreated(provider: string, event: any): Promise<void> {
    const disputeData = this.extractDisputeData(provider, event);

    // Create dispute record
    await this.createDisputeRecord(disputeData);

    // Gather evidence automatically
    const evidence = await this.gatherDisputeEvidence(disputeData.paymentId);

    // Submit evidence if available
    if (evidence.length > 0) {
      await this.submitDisputeEvidence(provider, disputeData.disputeId, evidence);
    }

    // Alert finance team
    await this.alertFinanceTeam(disputeData);

    // Emit event
    this.emitPaymentEvent('dispute.created', disputeData);
  }

  // Compliance request handler (Fungies specific)
  private async handleComplianceRequest(provider: string, event: any): Promise<void> {
    const complianceData = event.data;

    // Create compliance task
    await this.createComplianceTask({
      customerId: complianceData.customer_id,
      documents: complianceData.required_documents,
      deadline: complianceData.deadline,
      reason: complianceData.reason
    });

    // Notify customer
    await this.sendComplianceNotification(complianceData.customer_id, complianceData);

    // Alert compliance team
    await this.alertComplianceTeam(complianceData);
  }

  // OXXO payment handler (Conekta specific)
  private async handleOxxoPayment(provider: string, event: any): Promise<void> {
    const paymentData = event.data?.object;

    // Update payment status
    await this.updatePaymentStatus(paymentData.id, 'processing');

    // Send confirmation with reference
    await this.sendOxxoConfirmation({
      orderId: paymentData.order_id,
      reference: paymentData.payment_method?.reference,
      amount: paymentData.amount / 100,
      expiresAt: paymentData.payment_method?.expires_at
    });

    // Schedule expiration check
    await this.scheduleOxxoExpirationCheck(paymentData.id, paymentData.payment_method?.expires_at);
  }

  // Signature validation methods
  private async validateConektaSignature(body: any, signature: string): Promise<boolean> {
    const hmac = crypto.createHmac('sha256', this.config.conekta.secret);
    hmac.update(JSON.stringify(body));
    const digest = hmac.digest('hex');
    return digest === signature;
  }

  private async validateFungiesSignature(body: string, signature: string): Promise<boolean> {
    const hmac = crypto.createHmac('sha256', this.config.fungies.secret);
    hmac.update(body);
    const digest = hmac.digest('hex');
    return digest === signature;
  }

  private async validateStripeSignature(body: any, signature: string): Promise<boolean> {
    // Stripe validation is handled by the SDK in handleStripeWebhook
    return true;
  }

  // Event parsing methods
  private parseConektaEvent(body: any): any {
    return {
      id: body.id,
      type: body.type,
      data: body.data,
      created_at: body.created_at
    };
  }

  private parseFungiesEvent(body: any): any {
    return {
      id: body.event_id,
      type: body.event_type,
      data: body.data,
      created_at: body.timestamp
    };
  }

  // Helper methods
  private async isEventProcessed(provider: string, eventId: string): Promise<boolean> {
    const key = `webhook:${provider}:${eventId}`;
    const exists = await this.redis.exists(key);
    return exists === 1;
  }

  private async markEventProcessed(provider: string, eventId: string): Promise<void> {
    const key = `webhook:${provider}:${eventId}`;
    await this.redis.setex(key, 86400 * 7, '1'); // Keep for 7 days
  }

  private async logWebhookEvent(provider: string, event: any): Promise<void> {
    await this.redis.zadd(
      `webhook:${provider}:events`,
      Date.now(),
      JSON.stringify({
        eventId: event.id,
        type: event.type,
        timestamp: new Date().toISOString()
      })
    );
  }

  private async handleWebhookError(provider: string, error: Error, body: any): Promise<void> {
    await this.redis.zadd(
      `webhook:${provider}:errors`,
      Date.now(),
      JSON.stringify({
        error: error.message,
        body,
        timestamp: new Date().toISOString()
      })
    );

    // Alert monitoring
    console.error(`Webhook error for ${provider}:`, error);
  }

  private async recordWebhookMetrics(
    provider: string,
    eventType: string,
    processingTime: number,
    status: 'success' | 'failure'
  ): Promise<void> {
    const key = `webhook:metrics:${provider}:${eventType}`;
    await this.redis.hincrby(key, `${status}_count`, 1);
    await this.redis.hincrby(key, 'total_processing_time', processingTime);
  }

  private extractPaymentData(provider: string, event: any): any {
    // Provider-specific data extraction
    switch (provider) {
      case 'conekta':
        return {
          paymentId: event.data?.object?.id,
          customerId: event.data?.object?.customer_id,
          amount: event.data?.object?.amount / 100,
          currency: event.data?.object?.currency
        };
      case 'fungies':
        return {
          paymentId: event.data?.payment_intent_id,
          customerId: event.data?.customer_id,
          amount: event.data?.amount,
          currency: event.data?.currency
        };
      case 'stripe':
        return {
          paymentId: event.data?.object?.id,
          customerId: event.data?.object?.customer,
          amount: event.data?.object?.amount / 100,
          currency: event.data?.object?.currency
        };
      default:
        return {};
    }
  }

  private extractSubscriptionData(provider: string, event: any): any {
    // Provider-specific subscription data extraction
    return {
      subscriptionId: event.data?.object?.id || event.data?.subscription_id,
      customerId: event.data?.object?.customer || event.data?.customer_id,
      planId: event.data?.object?.plan?.id || event.data?.plan_id,
      status: event.data?.object?.status || event.data?.status
    };
  }

  private extractDisputeData(provider: string, event: any): any {
    // Provider-specific dispute data extraction
    return {
      disputeId: event.data?.object?.id || event.data?.dispute_id,
      paymentId: event.data?.object?.charge || event.data?.payment_id,
      amount: event.data?.object?.amount || event.data?.amount,
      reason: event.data?.object?.reason || event.data?.reason
    };
  }

  // Database operations (stubs for actual implementation)
  private async updatePaymentStatus(paymentId: string, status: string): Promise<void> {
    // Update payment status in database
    console.log(`Updating payment ${paymentId} to status ${status}`);
  }

  private async updateCustomerBalance(customerId: string, amount: number): Promise<void> {
    // Update customer balance
    console.log(`Updating balance for customer ${customerId} by ${amount}`);
  }

  private async createSubscriptionRecord(data: any): Promise<void> {
    // Create subscription in database
    console.log('Creating subscription record:', data);
  }

  private async createDisputeRecord(data: any): Promise<void> {
    // Create dispute in database
    console.log('Creating dispute record:', data);
  }

  private async createComplianceTask(data: any): Promise<void> {
    // Create compliance task
    console.log('Creating compliance task:', data);
  }

  // Notification methods (stubs)
  private async sendPaymentConfirmation(data: any): Promise<void> {
    console.log('Sending payment confirmation:', data);
  }

  private async sendPaymentFailureNotification(data: any): Promise<void> {
    console.log('Sending payment failure notification:', data);
  }

  private async sendSubscriptionWelcome(data: any): Promise<void> {
    console.log('Sending subscription welcome:', data);
  }

  private async sendComplianceNotification(customerId: string, data: any): Promise<void> {
    console.log('Sending compliance notification:', customerId, data);
  }

  private async sendOxxoConfirmation(data: any): Promise<void> {
    console.log('Sending OXXO confirmation:', data);
  }

  // Workflow methods (stubs)
  private async triggerPostPaymentWorkflows(data: any): Promise<void> {
    console.log('Triggering post-payment workflows:', data);
  }

  private async provisionSubscriptionServices(data: any): Promise<void> {
    console.log('Provisioning subscription services:', data);
  }

  private async gatherDisputeEvidence(paymentId: string): Promise<any[]> {
    console.log('Gathering dispute evidence for:', paymentId);
    return [];
  }

  private async submitDisputeEvidence(provider: string, disputeId: string, evidence: any[]): Promise<void> {
    console.log('Submitting dispute evidence:', provider, disputeId, evidence);
  }

  // Alert methods (stubs)
  private async alertFinanceTeam(data: any): Promise<void> {
    console.log('Alerting finance team:', data);
  }

  private async alertComplianceTeam(data: any): Promise<void> {
    console.log('Alerting compliance team:', data);
  }

  // Retry methods (stubs)
  private async isRetryEligible(data: any): Promise<boolean> {
    // Check if payment is eligible for retry
    return false;
  }

  private async schedulePaymentRetry(data: any): Promise<void> {
    console.log('Scheduling payment retry:', data);
  }

  private async scheduleOxxoExpirationCheck(paymentId: string, expiresAt: string): Promise<void> {
    console.log('Scheduling OXXO expiration check:', paymentId, expiresAt);
  }

  // Event emission
  private emitPaymentEvent(eventType: string, data: any): void {
    // Emit event for other services
    console.log('Emitting event:', eventType, data);
  }

  // Unknown event handler
  private async handleUnknownEvent(provider: string, event: any): Promise<void> {
    console.log(`Unknown event from ${provider}:`, event.type);
    await this.redis.zadd(
      `webhook:${provider}:unknown`,
      Date.now(),
      JSON.stringify(event)
    );
  }

  private async handlePaymentProcessing(provider: string, event: any): Promise<void> {
    const paymentData = this.extractPaymentData(provider, event);
    await this.updatePaymentStatus(paymentData.paymentId, 'processing');
    this.emitPaymentEvent('payment.processing', paymentData);
  }

  private async handleRefundSuccess(provider: string, event: any): Promise<void> {
    const refundData = this.extractRefundData(provider, event);
    await this.updateRefundStatus(refundData.refundId, 'succeeded');
    await this.sendRefundConfirmation(refundData);
    this.emitPaymentEvent('refund.succeeded', refundData);
  }

  private async handleRefundFailure(provider: string, event: any): Promise<void> {
    const refundData = this.extractRefundData(provider, event);
    await this.updateRefundStatus(refundData.refundId, 'failed');
    await this.sendRefundFailureNotification(refundData);
    this.emitPaymentEvent('refund.failed', refundData);
  }

  private async handleSubscriptionUpdated(provider: string, event: any): Promise<void> {
    const subscriptionData = this.extractSubscriptionData(provider, event);
    await this.updateSubscriptionRecord(subscriptionData);
    this.emitPaymentEvent('subscription.updated', subscriptionData);
  }

  private async handleSubscriptionCancelled(provider: string, event: any): Promise<void> {
    const subscriptionData = this.extractSubscriptionData(provider, event);
    await this.cancelSubscriptionServices(subscriptionData);
    await this.sendSubscriptionCancellationConfirmation(subscriptionData);
    this.emitPaymentEvent('subscription.cancelled', subscriptionData);
  }

  private async handleDisputeUpdated(provider: string, event: any): Promise<void> {
    const disputeData = this.extractDisputeData(provider, event);
    await this.updateDisputeRecord(disputeData);
    this.emitPaymentEvent('dispute.updated', disputeData);
  }

  private async handleInvoicePaid(provider: string, event: any): Promise<void> {
    const invoiceData = this.extractInvoiceData(provider, event);
    await this.markInvoiceAsPaid(invoiceData);
    await this.sendInvoiceReceipt(invoiceData);
    this.emitPaymentEvent('invoice.paid', invoiceData);
  }

  private async handleInvoiceFailed(provider: string, event: any): Promise<void> {
    const invoiceData = this.extractInvoiceData(provider, event);
    await this.markInvoiceAsFailed(invoiceData);
    await this.sendInvoiceFailureNotification(invoiceData);
    this.emitPaymentEvent('invoice.failed', invoiceData);
  }

  private async handleCustomerCreated(provider: string, event: any): Promise<void> {
    const customerData = this.extractCustomerData(provider, event);
    await this.createCustomerRecord(customerData);
    this.emitPaymentEvent('customer.created', customerData);
  }

  private async handleCustomerUpdated(provider: string, event: any): Promise<void> {
    const customerData = this.extractCustomerData(provider, event);
    await this.updateCustomerRecord(customerData);
    this.emitPaymentEvent('customer.updated', customerData);
  }

  private async handleTaxCalculation(provider: string, event: any): Promise<void> {
    const taxData = event.data;
    await this.storeTaxCalculation(taxData);
    this.emitPaymentEvent('tax.calculated', taxData);
  }

  private async handleConektaOrderPaid(provider: string, event: any): Promise<void> {
    const orderData = event.data?.object;
    await this.updateOrderStatus(orderData.id, 'paid');
    await this.sendOrderConfirmation(orderData);
    this.emitPaymentEvent('order.paid', orderData);
  }

  private async handleSpeiPayment(provider: string, event: any): Promise<void> {
    const paymentData = event.data?.object;
    await this.updatePaymentStatus(paymentData.id, 'processing');
    await this.sendSpeiConfirmation(paymentData);
    this.emitPaymentEvent('spei.received', paymentData);
  }

  // Additional extraction methods
  private extractRefundData(provider: string, event: any): any {
    return {
      refundId: event.data?.object?.id || event.data?.refund_id,
      paymentId: event.data?.object?.charge || event.data?.payment_id,
      amount: event.data?.object?.amount || event.data?.amount,
      status: event.data?.object?.status || event.data?.status
    };
  }

  private extractInvoiceData(provider: string, event: any): any {
    return {
      invoiceId: event.data?.object?.id || event.data?.invoice_id,
      customerId: event.data?.object?.customer || event.data?.customer_id,
      amount: event.data?.object?.amount_paid || event.data?.amount,
      status: event.data?.object?.status || event.data?.status
    };
  }

  private extractCustomerData(provider: string, event: any): any {
    return {
      customerId: event.data?.object?.id || event.data?.customer_id,
      email: event.data?.object?.email || event.data?.email,
      name: event.data?.object?.name || event.data?.name,
      metadata: event.data?.object?.metadata || event.data?.metadata
    };
  }

  // Additional database operations (stubs)
  private async updateRefundStatus(refundId: string, status: string): Promise<void> {
    console.log(`Updating refund ${refundId} to status ${status}`);
  }

  private async updateSubscriptionRecord(data: any): Promise<void> {
    console.log('Updating subscription record:', data);
  }

  private async cancelSubscriptionServices(data: any): Promise<void> {
    console.log('Cancelling subscription services:', data);
  }

  private async updateDisputeRecord(data: any): Promise<void> {
    console.log('Updating dispute record:', data);
  }

  private async markInvoiceAsPaid(data: any): Promise<void> {
    console.log('Marking invoice as paid:', data);
  }

  private async markInvoiceAsFailed(data: any): Promise<void> {
    console.log('Marking invoice as failed:', data);
  }

  private async createCustomerRecord(data: any): Promise<void> {
    console.log('Creating customer record:', data);
  }

  private async updateCustomerRecord(data: any): Promise<void> {
    console.log('Updating customer record:', data);
  }

  private async storeTaxCalculation(data: any): Promise<void> {
    console.log('Storing tax calculation:', data);
  }

  private async updateOrderStatus(orderId: string, status: string): Promise<void> {
    console.log(`Updating order ${orderId} to status ${status}`);
  }

  // Additional notification methods (stubs)
  private async sendRefundConfirmation(data: any): Promise<void> {
    console.log('Sending refund confirmation:', data);
  }

  private async sendRefundFailureNotification(data: any): Promise<void> {
    console.log('Sending refund failure notification:', data);
  }

  private async sendSubscriptionCancellationConfirmation(data: any): Promise<void> {
    console.log('Sending subscription cancellation confirmation:', data);
  }

  private async sendInvoiceReceipt(data: any): Promise<void> {
    console.log('Sending invoice receipt:', data);
  }

  private async sendInvoiceFailureNotification(data: any): Promise<void> {
    console.log('Sending invoice failure notification:', data);
  }

  private async sendOrderConfirmation(data: any): Promise<void> {
    console.log('Sending order confirmation:', data);
  }

  private async sendSpeiConfirmation(data: any): Promise<void> {
    console.log('Sending SPEI confirmation:', data);
  }
}