import { EventEmitter } from 'events';
import { Redis } from 'ioredis';
import { Registry, Counter, Histogram, Gauge, Summary } from 'prom-client';
import { createLogger } from '../utils/logger';
import { AlertingService, Alert } from './alerting.service';

const logger = createLogger('Monitoring');

interface MetricPoint {
  timestamp: number;
  value: number;
  labels?: Record<string, string>;
}

interface HealthStatus {
  service: string;
  status: 'healthy' | 'degraded' | 'unhealthy';
  lastCheck: Date;
  uptime: number;
  errorRate: number;
  latency: {
    p50: number;
    p95: number;
    p99: number;
  };
}

// Alert interface moved to alerting.service.ts

export class MonitoringService extends EventEmitter {
  private redis: Redis;
  private registry: Registry;
  private alertingService: AlertingService;
  private metrics: Map<string, any>;
  private healthChecks: Map<string, () => Promise<boolean>>;

  // Payment metrics
  private paymentCounter!: Counter;
  private paymentAmountHistogram!: Histogram;
  private paymentDurationHistogram!: Histogram;
  private paymentSuccessRate!: Gauge;
  private activePaymentsGauge!: Gauge;

  // Provider metrics
  private providerLatency!: Histogram;
  private providerErrorRate!: Gauge;
  private providerAvailability!: Gauge;

  // Business metrics
  private revenueGauge!: Gauge;
  private customerGauge!: Gauge;
  private subscriptionGauge!: Gauge;
  private churnRate!: Gauge;

  // System metrics
  private apiLatency!: Histogram;
  private apiRequestRate!: Counter;
  private errorRate!: Counter;
  private queueSize!: Gauge;

  // Compliance metrics
  private complianceCheckCounter!: Counter;
  private fraudDetectionCounter!: Counter;
  private kycProcessingTime!: Histogram;

  constructor(redis: Redis) {
    super();
    this.redis = redis;
    this.registry = new Registry();
    this.alertingService = new AlertingService(redis);
    this.metrics = new Map();
    this.healthChecks = new Map();

    this.initializeMetrics();
    this.startMetricsCollection();
    this.startHealthChecks();
  }

  private initializeMetrics(): void {
    // Payment metrics
    this.paymentCounter = new Counter({
      name: 'payments_total',
      help: 'Total number of payments processed',
      labelNames: ['provider', 'status', 'currency', 'country'],
      registers: [this.registry]
    });

    this.paymentAmountHistogram = new Histogram({
      name: 'payment_amount',
      help: 'Distribution of payment amounts',
      labelNames: ['currency', 'provider'],
      buckets: [10, 50, 100, 500, 1000, 5000, 10000, 50000],
      registers: [this.registry]
    });

    this.paymentDurationHistogram = new Histogram({
      name: 'payment_duration_seconds',
      help: 'Time to process payments',
      labelNames: ['provider', 'status'],
      buckets: [0.1, 0.5, 1, 2, 5, 10, 30],
      registers: [this.registry]
    });

    this.paymentSuccessRate = new Gauge({
      name: 'payment_success_rate',
      help: 'Current payment success rate',
      labelNames: ['provider', 'period'],
      registers: [this.registry]
    });

    this.activePaymentsGauge = new Gauge({
      name: 'active_payments',
      help: 'Number of payments currently processing',
      labelNames: ['provider'],
      registers: [this.registry]
    });

    // Provider metrics
    this.providerLatency = new Histogram({
      name: 'provider_latency_seconds',
      help: 'Provider API latency',
      labelNames: ['provider', 'operation'],
      buckets: [0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
      registers: [this.registry]
    });

    this.providerErrorRate = new Gauge({
      name: 'provider_error_rate',
      help: 'Provider error rate',
      labelNames: ['provider'],
      registers: [this.registry]
    });

    this.providerAvailability = new Gauge({
      name: 'provider_availability',
      help: 'Provider availability (0-1)',
      labelNames: ['provider'],
      registers: [this.registry]
    });

    // Business metrics
    this.revenueGauge = new Gauge({
      name: 'revenue_total',
      help: 'Total revenue',
      labelNames: ['currency', 'period'],
      registers: [this.registry]
    });

    this.customerGauge = new Gauge({
      name: 'customers_total',
      help: 'Total number of customers',
      labelNames: ['type', 'status'],
      registers: [this.registry]
    });

    this.subscriptionGauge = new Gauge({
      name: 'subscriptions_total',
      help: 'Total number of subscriptions',
      labelNames: ['plan', 'status'],
      registers: [this.registry]
    });

    this.churnRate = new Gauge({
      name: 'churn_rate',
      help: 'Customer churn rate',
      labelNames: ['period', 'segment'],
      registers: [this.registry]
    });

    // System metrics
    this.apiLatency = new Histogram({
      name: 'api_latency_seconds',
      help: 'API endpoint latency',
      labelNames: ['method', 'endpoint', 'status'],
      buckets: [0.01, 0.05, 0.1, 0.5, 1, 5],
      registers: [this.registry]
    });

    this.apiRequestRate = new Counter({
      name: 'api_requests_total',
      help: 'Total API requests',
      labelNames: ['method', 'endpoint', 'status'],
      registers: [this.registry]
    });

    this.errorRate = new Counter({
      name: 'errors_total',
      help: 'Total errors',
      labelNames: ['type', 'severity', 'service'],
      registers: [this.registry]
    });

    this.queueSize = new Gauge({
      name: 'queue_size',
      help: 'Size of processing queues',
      labelNames: ['queue', 'priority'],
      registers: [this.registry]
    });

    // Compliance metrics
    this.complianceCheckCounter = new Counter({
      name: 'compliance_checks_total',
      help: 'Total compliance checks performed',
      labelNames: ['type', 'result', 'country'],
      registers: [this.registry]
    });

    this.fraudDetectionCounter = new Counter({
      name: 'fraud_detections_total',
      help: 'Total fraud detections',
      labelNames: ['severity', 'action', 'provider'],
      registers: [this.registry]
    });

    this.kycProcessingTime = new Histogram({
      name: 'kyc_processing_seconds',
      help: 'KYC processing time',
      labelNames: ['level', 'result'],
      buckets: [1, 5, 10, 30, 60, 300],
      registers: [this.registry]
    });
  }

  // Real-time metrics recording
  async recordPayment(data: {
    provider: string;
    status: 'succeeded' | 'failed' | 'pending';
    amount: number;
    currency: string;
    country: string;
    duration: number;
  }): Promise<void> {
    // Update counters
    this.paymentCounter.inc({
      provider: data.provider,
      status: data.status,
      currency: data.currency,
      country: data.country
    });

    // Update histograms
    this.paymentAmountHistogram.observe(
      { currency: data.currency, provider: data.provider },
      data.amount
    );

    this.paymentDurationHistogram.observe(
      { provider: data.provider, status: data.status },
      data.duration
    );

    // Update active payments
    if (data.status === 'pending') {
      this.activePaymentsGauge.inc({ provider: data.provider });
    } else {
      // Payment completed (either succeeded or failed)
      this.activePaymentsGauge.dec({ provider: data.provider });
    }

    // Store in time series
    await this.storeTimeSeries('payments', {
      timestamp: Date.now(),
      value: data.amount,
      labels: {
        provider: data.provider,
        status: data.status,
        currency: data.currency,
        country: data.country
      }
    });

    // Calculate and update success rate
    await this.updateSuccessRate(data.provider);

    // Check for alerts
    await this.checkPaymentAlerts(data);
  }

  async recordProviderMetrics(data: {
    provider: string;
    operation: string;
    latency: number;
    success: boolean;
    error?: string;
  }): Promise<void> {
    // Record latency
    this.providerLatency.observe(
      { provider: data.provider, operation: data.operation },
      data.latency
    );

    // Update error rate
    if (!data.success) {
      await this.incrementProviderErrors(data.provider);
    }

    // Store provider health
    await this.updateProviderHealth(data.provider, data.latency, data.success);
  }

  async recordBusinessMetrics(data: {
    revenue?: { amount: number; currency: string };
    newCustomers?: number;
    churnedCustomers?: number;
    newSubscriptions?: number;
    cancelledSubscriptions?: number;
  }): Promise<void> {
    if (data.revenue) {
      this.revenueGauge.inc(
        { currency: data.revenue.currency, period: 'daily' },
        data.revenue.amount
      );
    }

    if (data.newCustomers) {
      this.customerGauge.inc(
        { type: 'regular', status: 'active' },
        data.newCustomers
      );
    }

    if (data.churnedCustomers) {
      this.customerGauge.dec(
        { type: 'regular', status: 'active' },
        data.churnedCustomers
      );
    }

    if (data.newSubscriptions) {
      this.subscriptionGauge.inc(
        { plan: 'standard', status: 'active' },
        data.newSubscriptions
      );
    }

    if (data.cancelledSubscriptions) {
      this.subscriptionGauge.dec(
        { plan: 'standard', status: 'active' },
        data.cancelledSubscriptions
      );
    }

    // Calculate and update churn rate
    await this.updateChurnRate();
  }

  async recordAPIMetrics(data: {
    method: string;
    endpoint: string;
    status: number;
    latency: number;
  }): Promise<void> {
    // Record request
    this.apiRequestRate.inc({
      method: data.method,
      endpoint: data.endpoint,
      status: data.status.toString()
    });

    // Record latency
    this.apiLatency.observe(
      {
        method: data.method,
        endpoint: data.endpoint,
        status: data.status.toString()
      },
      data.latency
    );

    // Track errors
    if (data.status >= 400) {
      this.errorRate.inc({
        type: data.status >= 500 ? 'server' : 'client',
        severity: data.status >= 500 ? 'high' : 'medium',
        service: 'api'
      });
    }
  }

  async recordComplianceMetrics(data: {
    type: 'kyc' | 'aml' | 'tax' | 'regulatory';
    result: 'passed' | 'failed' | 'manual_review';
    country: string;
    processingTime?: number;
  }): Promise<void> {
    this.complianceCheckCounter.inc({
      type: data.type,
      result: data.result,
      country: data.country
    });

    if (data.type === 'kyc' && data.processingTime) {
      this.kycProcessingTime.observe(
        { level: 'standard', result: data.result },
        data.processingTime
      );
    }
  }

  async recordFraudDetection(data: {
    severity: 'low' | 'medium' | 'high';
    action: 'blocked' | 'flagged' | 'allowed';
    provider: string;
    riskScore: number;
  }): Promise<void> {
    this.fraudDetectionCounter.inc({
      severity: data.severity,
      action: data.action,
      provider: data.provider
    });

    // Store fraud event
    await this.redis.zadd(
      'monitoring:fraud:events',
      Date.now(),
      JSON.stringify({
        ...data,
        timestamp: new Date().toISOString()
      })
    );

    // Check if we need to alert
    if (data.severity === 'high' && data.action === 'blocked') {
      await this.createAlert({
        severity: 'warning',
        title: 'High Risk Transaction Blocked',
        description: `Blocked transaction with risk score ${data.riskScore}`,
        metric: 'fraud_detection',
        threshold: 80,
        currentValue: data.riskScore
      });
    }
  }

  // Dashboard data aggregation
  async getDashboardMetrics(timeRange: { start: Date; end: Date }): Promise<{
    overview: {
      totalPayments: number;
      totalRevenue: number;
      successRate: number;
      activeCustomers: number;
    };
    providers: {
      name: string;
      health: HealthStatus;
      volume: number;
      revenue: number;
      successRate: number;
    }[];
    trends: {
      payments: MetricPoint[];
      revenue: MetricPoint[];
      successRate: MetricPoint[];
    };
    alerts: Alert[];
  }> {
    // Get payment totals
    const payments = await this.getTimeSeriesData('payments', timeRange);
    const totalPayments = payments.length;
    const totalRevenue = payments.reduce((sum, p) => sum + p.value, 0);

    // Calculate success rate
    const successfulPayments = payments.filter(p => p.labels?.status === 'succeeded');
    const successRate = (successfulPayments.length / totalPayments) * 100;

    // Get active customers
    const activeCustomers = await this.getActiveCustomerCount();

    // Get provider metrics
    const providers = await this.getProviderMetrics(timeRange);

    // Get trend data
    const trends = await this.getTrendData(timeRange);

    // Get active alerts
    const alerts = await this.getActiveAlerts();

    return {
      overview: {
        totalPayments,
        totalRevenue,
        successRate,
        activeCustomers
      },
      providers,
      trends,
      alerts
    };
  }

  async getProviderHealthDashboard(): Promise<{
    providers: {
      name: string;
      status: 'healthy' | 'degraded' | 'unhealthy';
      uptime: number;
      latency: { p50: number; p95: number; p99: number };
      errorRate: number;
      lastIncident?: Date;
    }[];
    systemHealth: {
      api: HealthStatus;
      database: HealthStatus;
      redis: HealthStatus;
      queues: HealthStatus;
    };
  }> {
    const providers = ['conekta', 'stripe'];
    const providerHealth = await Promise.all(
      providers.map(async (provider) => {
        const health = await this.getProviderHealth(provider);
        const incidents = await this.getRecentIncidents(provider);

        return {
          name: provider,
          status: health.status,
          uptime: health.uptime,
          latency: health.latency,
          errorRate: health.errorRate,
          lastIncident: incidents[0]?.timestamp
        };
      })
    );

    const systemHealth = {
      api: await this.getServiceHealth('api'),
      database: await this.getServiceHealth('database'),
      redis: await this.getServiceHealth('redis'),
      queues: await this.getServiceHealth('queues')
    };

    return { providers: providerHealth, systemHealth };
  }

  async getTransactionAnalytics(filters: {
    startDate: Date;
    endDate: Date;
    provider?: string;
    country?: string;
    status?: string;
  }): Promise<{
    summary: {
      count: number;
      volume: number;
      avgTicket: number;
      successRate: number;
    };
    breakdown: {
      byProvider: Record<string, { count: number; volume: number }>;
      byCountry: Record<string, { count: number; volume: number }>;
      byCurrency: Record<string, { count: number; volume: number }>;
      byHour: Record<number, { count: number; volume: number }>;
    };
    topMetrics: {
      topCountries: { country: string; volume: number }[];
      topPaymentMethods: { method: string; count: number }[];
      peakHours: { hour: number; volume: number }[];
    };
  }> {
    const transactions = await this.getFilteredTransactions(filters);

    // Calculate summary
    const summary = {
      count: transactions.length,
      volume: transactions.reduce((sum, t) => sum + t.amount, 0),
      avgTicket: transactions.length ?
        transactions.reduce((sum, t) => sum + t.amount, 0) / transactions.length : 0,
      successRate: (transactions.filter(t => t.status === 'succeeded').length / transactions.length) * 100
    };

    // Calculate breakdowns
    const breakdown = {
      byProvider: this.groupBy(transactions, 'provider'),
      byCountry: this.groupBy(transactions, 'country'),
      byCurrency: this.groupBy(transactions, 'currency'),
      byHour: this.groupByHour(transactions)
    };

    // Calculate top metrics
    const topMetrics = {
      topCountries: this.getTop(breakdown.byCountry, 5),
      topPaymentMethods: await this.getTopPaymentMethods(transactions),
      peakHours: this.getTop(breakdown.byHour, 3)
    };

    return { summary, breakdown, topMetrics };
  }

  // Alert management - Delegated to AlertingService
  async createAlert(data: {
    severity: 'info' | 'warning' | 'critical';
    title: string;
    description: string;
    metric: string;
    threshold: number;
    currentValue: number;
  }): Promise<Alert> {
    return await this.alertingService.createAlert(data);
  }

  async acknowledgeAlert(alertId: string): Promise<void> {
    return await this.alertingService.acknowledgeAlert(alertId);
  }

  // Health checks
  registerHealthCheck(service: string, check: () => Promise<boolean>): void {
    this.healthChecks.set(service, check);
  }

  private async performHealthCheck(service: string): Promise<HealthStatus> {
    const check = this.healthChecks.get(service);
    if (!check) {
      return {
        service,
        status: 'unhealthy',
        lastCheck: new Date(),
        uptime: 0,
        errorRate: 100,
        latency: { p50: 0, p95: 0, p99: 0 }
      };
    }

    const startTime = Date.now();
    let healthy = false;

    try {
      healthy = await check();
    } catch (error) {
      healthy = false;
    }

    const latency = Date.now() - startTime;

    // Get historical data
    const history = await this.getServiceHealthHistory(service);
    const uptime = this.calculateUptime(history);
    const errorRate = this.calculateErrorRate(history);
    const latencyStats = this.calculateLatencyPercentiles(history);

    return {
      service,
      status: healthy ? 'healthy' : errorRate > 50 ? 'unhealthy' : 'degraded',
      lastCheck: new Date(),
      uptime,
      errorRate,
      latency: latencyStats
    };
  }

  // Prometheus metrics export
  async getMetrics(): Promise<string> {
    return this.registry.metrics();
  }

  // Private helper methods
  private startMetricsCollection(): void {
    // Collect metrics every 10 seconds
    setInterval(async () => {
      await this.collectSystemMetrics();
      await this.collectBusinessMetrics();
    }, 10000);
  }

  private startHealthChecks(): void {
    // Perform health checks every 30 seconds
    setInterval(async () => {
      for (const [service] of this.healthChecks) {
        const health = await this.performHealthCheck(service);
        await this.storeHealthStatus(service, health);
      }
    }, 30000);
  }

  private async collectSystemMetrics(): Promise<void> {
    // Collect queue sizes
    const queues = ['payments', 'webhooks', 'compliance', 'refunds'];
    for (const queue of queues) {
      const size = await this.redis.llen(`queue:${queue}`);
      this.queueSize.set({ queue, priority: 'normal' }, size);
    }
  }

  private async collectBusinessMetrics(): Promise<void> {
    // This would connect to your database to get real metrics
    // For now, we'll use Redis counters
    const dailyRevenue = await this.redis.get('metrics:revenue:daily');
    if (dailyRevenue) {
      this.revenueGauge.set(
        { currency: 'USD', period: 'daily' },
        parseFloat(dailyRevenue)
      );
    }
  }

  private async storeTimeSeries(
    metric: string,
    point: MetricPoint
  ): Promise<void> {
    const key = `metrics:${metric}:${Math.floor(point.timestamp / 60000)}`;
    await this.redis.zadd(key, point.timestamp, JSON.stringify(point));
    await this.redis.expire(key, 86400 * 7); // Keep for 7 days
  }

  private async getTimeSeriesData(
    metric: string,
    timeRange: { start: Date; end: Date }
  ): Promise<MetricPoint[]> {
    const startMinute = Math.floor(timeRange.start.getTime() / 60000);
    const endMinute = Math.floor(timeRange.end.getTime() / 60000);
    const points: MetricPoint[] = [];

    for (let minute = startMinute; minute <= endMinute; minute++) {
      const key = `metrics:${metric}:${minute}`;
      const data = await this.redis.zrange(key, 0, -1);
      points.push(...data.map(d => JSON.parse(d)));
    }

    return points;
  }

  private async updateSuccessRate(provider: string): Promise<void> {
    const hourAgo = Date.now() - 3600000;
    const payments = await this.getTimeSeriesData('payments', {
      start: new Date(hourAgo),
      end: new Date()
    });

    const providerPayments = payments.filter(p => p.labels?.provider === provider);
    const successful = providerPayments.filter(p => p.labels?.status === 'succeeded');

    const rate = providerPayments.length > 0
      ? (successful.length / providerPayments.length) * 100
      : 0;

    this.paymentSuccessRate.set(
      { provider, period: 'hourly' },
      rate
    );
  }

  private async incrementProviderErrors(provider: string): Promise<void> {
    await this.redis.hincrby(`provider:${provider}:errors`, 'count', 1);
    await this.redis.hset(`provider:${provider}:errors`, 'lastError', Date.now());
  }

  private async updateProviderHealth(
    provider: string,
    latency: number,
    success: boolean
  ): Promise<void> {
    const key = `provider:${provider}:health`;

    // Update latency samples
    await this.redis.lpush(`${key}:latency`, latency);
    await this.redis.ltrim(`${key}:latency`, 0, 999); // Keep last 1000 samples

    // Update success/failure counts
    if (success) {
      await this.redis.hincrby(key, 'success', 1);
    } else {
      await this.redis.hincrby(key, 'failure', 1);
    }

    // Calculate availability
    const successCount = parseInt(await this.redis.hget(key, 'success') || '0');
    const failureCount = parseInt(await this.redis.hget(key, 'failure') || '0');
    const total = successCount + failureCount;

    if (total > 0) {
      const availability = successCount / total;
      this.providerAvailability.set({ provider }, availability);

      const errorRate = failureCount / total;
      this.providerErrorRate.set({ provider }, errorRate);
    }
  }

  private async checkPaymentAlerts(data: any): Promise<void> {
    const recentPayments = await this.getRecentPayments(data.provider, 100);
    await this.alertingService.checkPaymentAlerts(data, recentPayments);
  }

  private async getActiveCustomerCount(): Promise<number> {
    return parseInt(await this.redis.get('metrics:customers:active') || '0');
  }

  private async getProviderMetrics(timeRange: any): Promise<any[]> {
    const providers = ['conekta', 'stripe'];

    return Promise.all(providers.map(async (provider) => {
      const health = await this.getProviderHealth(provider);
      const payments = await this.getTimeSeriesData('payments', timeRange);
      const providerPayments = payments.filter(p => p.labels?.provider === provider);

      return {
        name: provider,
        health,
        volume: providerPayments.length,
        revenue: providerPayments.reduce((sum, p) => sum + p.value, 0),
        successRate: (providerPayments.filter(p => p.labels?.status === 'succeeded').length / providerPayments.length) * 100
      };
    }));
  }

  private async getProviderHealth(provider: string): Promise<HealthStatus> {
    const key = `provider:${provider}:health`;
    const latencies = await this.redis.lrange(`${key}:latency`, 0, -1);
    const success = parseInt(await this.redis.hget(key, 'success') || '0');
    const failure = parseInt(await this.redis.hget(key, 'failure') || '0');

    const latencyValues = latencies.map(l => parseFloat(l)).sort((a, b) => a - b);
    const p50 = latencyValues[Math.floor(latencyValues.length * 0.5)] || 0;
    const p95 = latencyValues[Math.floor(latencyValues.length * 0.95)] || 0;
    const p99 = latencyValues[Math.floor(latencyValues.length * 0.99)] || 0;

    const total = success + failure;
    const errorRate = total > 0 ? (failure / total) * 100 : 0;
    const uptime = total > 0 ? (success / total) * 100 : 100;

    return {
      service: provider,
      status: errorRate > 10 ? 'unhealthy' : errorRate > 5 ? 'degraded' : 'healthy',
      lastCheck: new Date(),
      uptime,
      errorRate,
      latency: { p50, p95, p99 }
    };
  }

  private async getTrendData(timeRange: any): Promise<any> {
    const payments = await this.getTimeSeriesData('payments', timeRange);

    // Group by hour for trends
    const hourlyData = new Map<number, { payments: number; revenue: number; successful: number }>();

    for (const payment of payments) {
      const hour = Math.floor(payment.timestamp / 3600000);
      const existing = hourlyData.get(hour) || { payments: 0, revenue: 0, successful: 0 };

      existing.payments++;
      existing.revenue += payment.value;
      if (payment.labels?.status === 'succeeded') {
        existing.successful++;
      }

      hourlyData.set(hour, existing);
    }

    const paymentTrend: MetricPoint[] = [];
    const revenueTrend: MetricPoint[] = [];
    const successRateTrend: MetricPoint[] = [];

    for (const [hour, data] of hourlyData) {
      paymentTrend.push({ timestamp: hour * 3600000, value: data.payments });
      revenueTrend.push({ timestamp: hour * 3600000, value: data.revenue });
      successRateTrend.push({
        timestamp: hour * 3600000,
        value: data.payments > 0 ? (data.successful / data.payments) * 100 : 0
      });
    }

    return {
      payments: paymentTrend,
      revenue: revenueTrend,
      successRate: successRateTrend
    };
  }

  private async getActiveAlerts(): Promise<Alert[]> {
    return await this.alertingService.getActiveAlerts();
  }

  private async getRecentIncidents(provider: string): Promise<any[]> {
    const incidents = await this.redis.zrange(
      `provider:${provider}:incidents`,
      Date.now() - 86400000,
      Date.now(),
      'BYSCORE'
    );
    return incidents.map(i => JSON.parse(i));
  }

  private async getServiceHealth(service: string): Promise<HealthStatus> {
    return this.performHealthCheck(service);
  }

  private async getFilteredTransactions(filters: any): Promise<any[]> {
    const transactions = await this.getTimeSeriesData('payments', {
      start: filters.startDate,
      end: filters.endDate
    });

    return transactions.filter(t => {
      if (filters.provider && t.labels?.provider !== filters.provider) return false;
      if (filters.country && t.labels?.country !== filters.country) return false;
      if (filters.status && t.labels?.status !== filters.status) return false;
      return true;
    });
  }

  private groupBy(items: any[], key: string): Record<string, any> {
    const groups: Record<string, any> = {};

    for (const item of items) {
      const groupKey = item.labels?.[key] || item[key] || 'unknown';
      if (!groups[groupKey]) {
        groups[groupKey] = { count: 0, volume: 0 };
      }
      groups[groupKey].count++;
      groups[groupKey].volume += item.amount || item.value || 0;
    }

    return groups;
  }

  private groupByHour(items: any[]): Record<number, any> {
    const groups: Record<number, any> = {};

    for (const item of items) {
      const hour = new Date(item.timestamp).getHours();
      if (!groups[hour]) {
        groups[hour] = { count: 0, volume: 0 };
      }
      groups[hour].count++;
      groups[hour].volume += item.amount || item.value || 0;
    }

    return groups;
  }

  private getTop(data: Record<string, any>, limit: number): any[] {
    return Object.entries(data)
      .map(([key, value]: [string, any]) => ({
        [key.includes('hour') ? 'hour' : key.includes('country') ? 'country' : 'method']: key,
        ...value
      }))
      .sort((a, b) => b.volume - a.volume)
      .slice(0, limit);
  }

  private async getTopPaymentMethods(transactions: any[]): Promise<any[]> {
    const methods: Record<string, number> = {};

    for (const t of transactions) {
      const method = t.labels?.paymentMethod || 'card';
      methods[method] = (methods[method] || 0) + 1;
    }

    return Object.entries(methods)
      .map(([method, count]) => ({ method, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);
  }

  private async getRecentPayments(provider: string, limit: number): Promise<any[]> {
    const payments = await this.redis.zrange(
      `provider:${provider}:payments`,
      -limit,
      -1
    );
    return payments.map(p => JSON.parse(p));
  }

  private async storeHealthStatus(service: string, health: HealthStatus): Promise<void> {
    await this.redis.hset(
      `service:${service}:health`,
      'status',
      health.status
    );
    await this.redis.hset(
      `service:${service}:health`,
      'lastCheck',
      health.lastCheck.toISOString()
    );
  }

  private async getServiceHealthHistory(service: string): Promise<any[]> {
    const history = await this.redis.zrange(
      `service:${service}:health:history`,
      Date.now() - 86400000,
      Date.now(),
      'BYSCORE'
    );
    return history.map(h => JSON.parse(h));
  }

  private calculateUptime(history: any[]): number {
    if (history.length === 0) return 100;

    const successful = history.filter(h => h.healthy).length;
    return (successful / history.length) * 100;
  }

  private calculateErrorRate(history: any[]): number {
    if (history.length === 0) return 0;

    const errors = history.filter(h => !h.healthy).length;
    return (errors / history.length) * 100;
  }

  private calculateLatencyPercentiles(history: any[]): { p50: number; p95: number; p99: number } {
    const latencies = history.map(h => h.latency).sort((a, b) => a - b);

    return {
      p50: latencies[Math.floor(latencies.length * 0.5)] || 0,
      p95: latencies[Math.floor(latencies.length * 0.95)] || 0,
      p99: latencies[Math.floor(latencies.length * 0.99)] || 0
    };
  }

  private async updateChurnRate(): Promise<void> {
    const activeCustomers = await this.getActiveCustomerCount();
    const churnedToday = parseInt(await this.redis.get('metrics:customers:churned:today') || '0');

    if (activeCustomers > 0) {
      const rate = (churnedToday / activeCustomers) * 100;
      this.churnRate.set({ period: 'daily', segment: 'all' }, rate);
    }
  }
}
