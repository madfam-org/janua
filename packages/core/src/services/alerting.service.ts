import { EventEmitter } from 'events';
import { Redis } from 'ioredis';
import { createLogger } from '../utils/logger';

const logger = createLogger('Alerting');

export interface Alert {
  id: string;
  severity: 'info' | 'warning' | 'critical';
  title: string;
  description: string;
  metric: string;
  threshold: number;
  currentValue: number;
  timestamp: Date;
  acknowledged: boolean;
}

export class AlertingService extends EventEmitter {
  private redis: Redis;
  private alerts: Map<string, Alert> = new Map();

  constructor(redis: Redis) {
    super();
    this.redis = redis;
  }

  async createAlert(data: {
    severity: 'info' | 'warning' | 'critical';
    title: string;
    description: string;
    metric: string;
    threshold: number;
    currentValue: number;
  }): Promise<Alert> {
    const alert: Alert = {
      id: `alert_${Date.now()}`,
      severity: data.severity,
      title: data.title,
      description: data.description,
      metric: data.metric,
      threshold: data.threshold,
      currentValue: data.currentValue,
      timestamp: new Date(),
      acknowledged: false
    };

    this.alerts.set(alert.id, alert);

    // Store in Redis
    await this.redis.zadd(
      'monitoring:alerts:active',
      Date.now(),
      JSON.stringify(alert)
    );

    // Send notifications
    await this.sendAlertNotifications(alert);

    this.emit('alert_created', alert);

    return alert;
  }

  async acknowledgeAlert(alertId: string): Promise<void> {
    const alert = this.alerts.get(alertId);
    if (alert) {
      alert.acknowledged = true;

      // Update in Redis
      await this.redis.zrem('monitoring:alerts:active', JSON.stringify(alert));
      await this.redis.zadd(
        'monitoring:alerts:acknowledged',
        Date.now(),
        JSON.stringify(alert)
      );

      this.emit('alert_acknowledged', alert);
    }
  }

  async getActiveAlerts(): Promise<Alert[]> {
    const alerts = await this.redis.zrange('monitoring:alerts:active', 0, -1);
    return alerts.map(a => JSON.parse(a));
  }

  async getAcknowledgedAlerts(): Promise<Alert[]> {
    const alerts = await this.redis.zrange('monitoring:alerts:acknowledged', 0, -1);
    return alerts.map(a => JSON.parse(a));
  }

  async checkPaymentAlerts(data: {
    provider: string;
    amount: number;
    currency: string;
    status: string;
  }, recentPayments: any[]): Promise<void> {
    // Check for high failure rate
    const failureRate = recentPayments.filter(p => p.status === 'failed').length / recentPayments.length;

    if (failureRate > 0.2) { // 20% failure rate
      await this.createAlert({
        severity: 'critical',
        title: `High Failure Rate for ${data.provider}`,
        description: `Payment failure rate is ${(failureRate * 100).toFixed(1)}%`,
        metric: 'payment_failure_rate',
        threshold: 20,
        currentValue: failureRate * 100
      });
    }

    // Check for large transaction
    if (data.amount > 10000) {
      await this.createAlert({
        severity: 'info',
        title: 'Large Transaction Processed',
        description: `Transaction of ${data.amount} ${data.currency} processed via ${data.provider}`,
        metric: 'transaction_amount',
        threshold: 10000,
        currentValue: data.amount
      });
    }
  }

  private async sendAlertNotifications(alert: Alert): Promise<void> {
    // Send to different channels based on severity
    switch (alert.severity) {
      case 'critical':
        // Send to PagerDuty, Slack, Email
        logger.error('CRITICAL ALERT', undefined, { alert });
        break;
      case 'warning':
        // Send to Slack, Email
        logger.warn('WARNING ALERT', { alert });
        break;
      case 'info':
        // Send to monitoring dashboard only
        console.info('INFO ALERT:', alert);
        break;
    }

    this.emit('alert_notification_sent', alert);
  }
}

// Export singleton
let alertingService: AlertingService | null = null;

export function getAlertingService(redis: Redis): AlertingService {
  if (!alertingService) {
    alertingService = new AlertingService(redis);
  }
  return alertingService;
}
