/**
 * Webhook Retry Service with Dead Letter Queue
 * Implements exponential backoff and reliable webhook delivery
 */

import { EventEmitter } from 'events';
import axios, { AxiosError } from 'axios';
import { createHmac } from 'crypto';
import { logger } from '../utils/logger';

export interface WebhookEvent {
  id: string;
  url: string;
  method: 'POST' | 'PUT';
  headers: Record<string, string>;
  payload: any;
  secret?: string;
  metadata: {
    eventType: string;
    organizationId?: string;
    userId?: string;
    timestamp: Date;
  };
}

export interface WebhookDelivery {
  id: string;
  eventId: string;
  attempt: number;
  status: 'pending' | 'success' | 'failed' | 'dlq';
  statusCode?: number;
  responseBody?: string;
  error?: string;
  latency?: number;
  nextRetryAt?: Date;
  completedAt?: Date;
}

export interface RetryConfig {
  maxRetries: number;
  initialDelayMs: number;
  maxDelayMs: number;
  backoffMultiplier: number;
  timeout: number;
  dlqThreshold: number;
}

export class WebhookRetryService extends EventEmitter {
  private queue: Map<string, WebhookEvent> = new Map();
  private deliveries: Map<string, WebhookDelivery[]> = new Map();
  private dlq: Map<string, WebhookEvent> = new Map();
  private retryTimers: Map<string, NodeJS.Timeout> = new Map();
  private config: RetryConfig;
  private redisService: any;

  constructor(config?: Partial<RetryConfig>, redisService?: any) {
    super();
    this.config = {
      maxRetries: config?.maxRetries || 5,
      initialDelayMs: config?.initialDelayMs || 1000, // 1 second
      maxDelayMs: config?.maxDelayMs || 3600000, // 1 hour
      backoffMultiplier: config?.backoffMultiplier || 2,
      timeout: config?.timeout || 30000, // 30 seconds
      dlqThreshold: config?.dlqThreshold || 3, // Move to DLQ after 3 consecutive failures
      ...config,
    };
    this.redisService = redisService;
    this.startQueueProcessor();
  }

  /**
   * Send webhook with retry logic
   */
  async sendWebhook(event: WebhookEvent): Promise<WebhookDelivery> {
    // Add to queue
    this.queue.set(event.id, event);

    // Initialize delivery tracking
    if (!this.deliveries.has(event.id)) {
      this.deliveries.set(event.id, []);
    }

    // Create initial delivery attempt
    const delivery: WebhookDelivery = {
      id: this.generateDeliveryId(),
      eventId: event.id,
      attempt: 1,
      status: 'pending',
    };

    this.deliveries.get(event.id)!.push(delivery);

    // Store in Redis for persistence
    if (this.redisService) {
      await this.storeEventInRedis(event);
    }

    // Attempt delivery
    const result = await this.attemptDelivery(event, delivery);

    if (result.status === 'failed') {
      // Schedule retry
      this.scheduleRetry(event, result);
    }

    return result;
  }

  /**
   * Attempt webhook delivery
   */
  private async attemptDelivery(
    event: WebhookEvent,
    delivery: WebhookDelivery
  ): Promise<WebhookDelivery> {
    const startTime = Date.now();

    try {
      // Prepare headers
      const headers = {
        ...event.headers,
        'Content-Type': 'application/json',
        'X-Webhook-Id': event.id,
        'X-Webhook-Timestamp': event.metadata.timestamp.toISOString(),
        'X-Webhook-Attempt': delivery.attempt.toString(),
      };

      // Add signature if secret provided
      if (event.secret) {
        const signature = this.generateSignature(event.payload, event.secret);
        (headers as any)['X-Webhook-Signature'] = signature;
      }

      // Make request
      const response = await axios({
        method: event.method,
        url: event.url,
        data: event.payload,
        headers,
        timeout: this.config.timeout,
        validateStatus: () => true, // Don't throw on any status
      });

      const latency = Date.now() - startTime;

      // Update delivery
      delivery.status = response.status >= 200 && response.status < 300 ? 'success' : 'failed';
      delivery.statusCode = response.status;
      delivery.responseBody = JSON.stringify(response.data).substring(0, 1000); // Limit response size
      delivery.latency = latency;
      delivery.completedAt = new Date();

      // Success
      if (delivery.status === 'success') {
        this.queue.delete(event.id);
        this.emit('webhook:delivered', {
          event,
          delivery,
        });

        logger.info('Webhook delivered successfully', {
          eventId: event.id,
          url: event.url,
          attempt: delivery.attempt,
          statusCode: response.status,
          latency,
        });
      } else {
        // Non-2xx response
        logger.warn('Webhook delivery failed with non-2xx status', {
          eventId: event.id,
          url: event.url,
          statusCode: response.status,
          attempt: delivery.attempt,
        });
      }

      return delivery;
    } catch (error) {
      const latency = Date.now() - startTime;
      const axiosError = error as AxiosError;

      // Update delivery with error
      delivery.status = 'failed';
      delivery.error = axiosError.message;
      delivery.latency = latency;

      if (axiosError.response) {
        delivery.statusCode = axiosError.response.status;
        delivery.responseBody = JSON.stringify(axiosError.response.data).substring(0, 1000);
      }

      logger.error('Webhook delivery failed', error as Error, {
        eventId: event.id,
        url: event.url,
        attempt: delivery.attempt,
      });

      return delivery;
    }
  }

  /**
   * Schedule retry with exponential backoff
   */
  private scheduleRetry(event: WebhookEvent, lastDelivery: WebhookDelivery): void {
    const attempts = this.deliveries.get(event.id)?.length || 1;

    // Check if should move to DLQ
    if (attempts >= this.config.dlqThreshold) {
      const consecutiveFailures = this.getConsecutiveFailures(event.id);
      if (consecutiveFailures >= this.config.dlqThreshold) {
        this.moveToDeadLetterQueue(event, 'Max consecutive failures reached');
        return;
      }
    }

    // Check max retries
    if (attempts >= this.config.maxRetries) {
      this.moveToDeadLetterQueue(event, 'Max retries exceeded');
      return;
    }

    // Calculate delay with exponential backoff
    const delay = Math.min(
      this.config.initialDelayMs * Math.pow(this.config.backoffMultiplier, attempts - 1),
      this.config.maxDelayMs
    );

    const nextRetryAt = new Date(Date.now() + delay);

    // Update delivery
    lastDelivery.nextRetryAt = nextRetryAt;

    // Schedule retry
    const timer = setTimeout(async () => {
      this.retryTimers.delete(event.id);
      await this.retry(event);
    }, delay);

    this.retryTimers.set(event.id, timer);

    logger.info('Webhook retry scheduled', {
      eventId: event.id,
      attempt: attempts + 1,
      delayMs: delay,
      nextRetryAt,
    });

    this.emit('webhook:retry-scheduled', {
      event,
      attempt: attempts + 1,
      nextRetryAt,
    });
  }

  /**
   * Retry webhook delivery
   */
  private async retry(event: WebhookEvent): Promise<void> {
    const deliveries = this.deliveries.get(event.id) || [];
    const attempt = deliveries.length + 1;

    const delivery: WebhookDelivery = {
      id: this.generateDeliveryId(),
      eventId: event.id,
      attempt,
      status: 'pending',
    };

    deliveries.push(delivery);

    const result = await this.attemptDelivery(event, delivery);

    if (result.status === 'failed') {
      this.scheduleRetry(event, result);
    }
  }

  /**
   * Move event to Dead Letter Queue
   */
  private moveToDeadLetterQueue(event: WebhookEvent, reason: string): void {
    this.dlq.set(event.id, event);
    this.queue.delete(event.id);

    // Cancel any pending retries
    const timer = this.retryTimers.get(event.id);
    if (timer) {
      clearTimeout(timer);
      this.retryTimers.delete(event.id);
    }

    // Update last delivery status
    const deliveries = this.deliveries.get(event.id);
    if (deliveries && deliveries.length > 0) {
      deliveries[deliveries.length - 1].status = 'dlq';
    }

    // Store in Redis DLQ
    if (this.redisService) {
      this.redisService.set(
        `webhook:dlq:${event.id}`,
        JSON.stringify({
          event,
          reason,
          movedAt: new Date().toISOString(),
          deliveries: this.deliveries.get(event.id),
        })
      );
    }

    logger.warn('Webhook moved to Dead Letter Queue', {
      eventId: event.id,
      url: event.url,
      reason,
      attempts: deliveries?.length || 0,
    });

    this.emit('webhook:dlq', {
      event,
      reason,
      deliveries: this.deliveries.get(event.id),
    });
  }

  /**
   * Retry event from Dead Letter Queue
   */
  async retryFromDLQ(eventId: string): Promise<WebhookDelivery> {
    const event = this.dlq.get(eventId);
    
    if (!event) {
      throw new Error(`Event ${eventId} not found in Dead Letter Queue`);
    }

    // Move back to active queue
    this.dlq.delete(eventId);
    this.queue.set(eventId, event);

    // Reset deliveries for this retry attempt
    this.deliveries.set(eventId, []);

    // Attempt delivery
    return this.sendWebhook(event);
  }

  /**
   * Get Dead Letter Queue items
   */
  async getDLQItems(params?: {
    page?: number;
    limit?: number;
  }): Promise<{
    items: Array<{
      event: WebhookEvent;
      deliveries: WebhookDelivery[];
    }>;
    total: number;
  }> {
    const items: Array<{
      event: WebhookEvent;
      deliveries: WebhookDelivery[];
    }> = [];

    const dlqArray = Array.from(this.dlq.values());
    const total = dlqArray.length;

    const page = params?.page || 1;
    const limit = params?.limit || 20;
    const start = (page - 1) * limit;
    const end = start + limit;

    const pageItems = dlqArray.slice(start, end);

    for (const event of pageItems) {
      items.push({
        event,
        deliveries: this.deliveries.get(event.id) || [],
      });
    }

    return { items, total };
  }

  /**
   * Clear Dead Letter Queue
   */
  async clearDLQ(filter?: (event: WebhookEvent) => boolean): Promise<number> {
    let cleared = 0;

    for (const [id, event] of this.dlq.entries()) {
      if (!filter || filter(event)) {
        this.dlq.delete(id);
        this.deliveries.delete(id);
        
        if (this.redisService) {
          await this.redisService.del(`webhook:dlq:${id}`);
        }

        cleared++;
      }
    }

    logger.info('Dead Letter Queue cleared', { cleared });

    return cleared;
  }

  /**
   * Get webhook delivery history
   */
  getDeliveryHistory(eventId: string): WebhookDelivery[] {
    return this.deliveries.get(eventId) || [];
  }

  /**
   * Get queue statistics
   */
  getStatistics(): {
    queueSize: number;
    dlqSize: number;
    pendingRetries: number;
    totalDeliveries: number;
    successRate: number;
  } {
    let totalDeliveries = 0;
    let successfulDeliveries = 0;

    for (const deliveries of this.deliveries.values()) {
      totalDeliveries += deliveries.length;
      successfulDeliveries += deliveries.filter(d => d.status === 'success').length;
    }

    return {
      queueSize: this.queue.size,
      dlqSize: this.dlq.size,
      pendingRetries: this.retryTimers.size,
      totalDeliveries,
      successRate: totalDeliveries > 0 ? (successfulDeliveries / totalDeliveries) * 100 : 0,
    };
  }

  /**
   * Helper methods
   */

  private generateDeliveryId(): string {
    return `delivery_${Date.now()}_${Math.random().toString(36).substring(7)}`;
  }

  private generateSignature(payload: any, secret: string): string {
    const hmac = createHmac('sha256', secret);
    hmac.update(JSON.stringify(payload));
    return `sha256=${hmac.digest('hex')}`;
  }

  private getConsecutiveFailures(eventId: string): number {
    const deliveries = this.deliveries.get(eventId) || [];
    let consecutive = 0;

    for (let i = deliveries.length - 1; i >= 0; i--) {
      if (deliveries[i].status === 'failed') {
        consecutive++;
      } else {
        break;
      }
    }

    return consecutive;
  }

  private async storeEventInRedis(event: WebhookEvent): Promise<void> {
    if (!this.redisService) return;

    await this.redisService.set(
      `webhook:event:${event.id}`,
      JSON.stringify(event),
      86400 // 24 hours
    );
  }

  private startQueueProcessor(): void {
    // Process queue every 10 seconds for any orphaned events
    setInterval(() => {
      this.processOrphanedEvents();
    }, 10000);
  }

  private async processOrphanedEvents(): Promise<void> {
    for (const [eventId, event] of this.queue.entries()) {
      // Check if event has a pending retry
      if (!this.retryTimers.has(eventId)) {
        const deliveries = this.deliveries.get(eventId) || [];
        const lastDelivery = deliveries[deliveries.length - 1];

        if (lastDelivery && lastDelivery.status === 'failed') {
          // Check if we should retry
          const now = Date.now();
          const nextRetryTime = lastDelivery.nextRetryAt?.getTime() || now;

          if (nextRetryTime <= now) {
            await this.retry(event);
          }
        }
      }
    }
  }

  /**
   * Cleanup resources
   */
  destroy(): void {
    // Clear all retry timers
    for (const timer of this.retryTimers.values()) {
      clearTimeout(timer);
    }
    this.retryTimers.clear();
  }
}