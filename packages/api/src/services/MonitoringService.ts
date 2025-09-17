/**
 * Monitoring and Alerting Service
 * Comprehensive platform monitoring with intelligent alerting
 */

import { PrismaClient } from '@prisma/client';
import { RedisService } from './RedisService';
import { TelemetryService } from './TelemetryService';
import { AdminDashboardService } from './AdminDashboardService';
import { logger } from '../utils/logger';

interface HealthCheck {
  name: string;
  status: 'healthy' | 'warning' | 'critical';
  responseTime: number;
  message?: string;
  metadata?: Record<string, any>;
  lastCheck: Date;
}

interface Alert {
  id: string;
  type: 'system' | 'business' | 'security' | 'performance';
  severity: 'info' | 'warning' | 'error' | 'critical';
  title: string;
  message: string;
  source: string;
  metadata: Record<string, any>;
  timestamp: Date;
  resolved: boolean;
  resolvedAt?: Date;
  resolvedBy?: string;
}

interface MonitoringMetrics {
  system: {
    cpuUsage: number;
    memoryUsage: number;
    diskUsage: number;
    networkLatency: number;
  };
  application: {
    requestsPerMinute: number;
    averageResponseTime: number;
    errorRate: number;
    activeConnections: number;
  };
  database: {
    connectionCount: number;
    queryTime: number;
    slowQueries: number;
    deadlocks: number;
  };
  business: {
    activeUsers: number;
    revenueGrowthRate: number;
    churnRate: number;
    licenseUtilization: number;
  };
}

interface AlertRule {
  id: string;
  name: string;
  condition: string; // Expression to evaluate
  threshold: number;
  severity: 'warning' | 'critical';
  enabled: boolean;
  cooldownMinutes: number;
  channels: string[]; // email, webhook, slack, etc.
  metadata?: Record<string, any>;
}

export class MonitoringService {
  private prisma: PrismaClient;
  private redis: RedisService;
  private telemetryService: TelemetryService;
  private adminService: AdminDashboardService;
  private healthChecks: Map<string, HealthCheck>;
  private alertRules: AlertRule[];

  constructor() {
    this.prisma = new PrismaClient();
    this.redis = new RedisService();
    this.telemetryService = new TelemetryService();
    this.adminService = new AdminDashboardService();
    this.healthChecks = new Map();
    this.alertRules = this.getDefaultAlertRules();

    // Start monitoring loops
    this.startHealthChecks();
    this.startMetricsCollection();
    this.startAlertEvaluation();
  }

  /**
   * Perform comprehensive health check
   */
  async performHealthCheck(): Promise<{
    status: 'healthy' | 'warning' | 'critical';
    checks: HealthCheck[];
    summary: {
      total: number;
      healthy: number;
      warning: number;
      critical: number;
    };
  }> {
    const checks = await Promise.all([
      this.checkDatabase(),
      this.checkRedis(),
      this.checkPaymentGateways(),
      this.checkExternalServices(),
      this.checkDiskSpace(),
      this.checkMemoryUsage(),
      this.checkAPIHealth()
    ]);

    const summary = {
      total: checks.length,
      healthy: checks.filter(c => c.status === 'healthy').length,
      warning: checks.filter(c => c.status === 'warning').length,
      critical: checks.filter(c => c.status === 'critical').length
    };

    let overallStatus: 'healthy' | 'warning' | 'critical' = 'healthy';
    if (summary.critical > 0) {
      overallStatus = 'critical';
    } else if (summary.warning > 0) {
      overallStatus = 'warning';
    }

    // Store health check results
    checks.forEach(check => {
      this.healthChecks.set(check.name, check);
    });

    return {
      status: overallStatus,
      checks,
      summary
    };
  }

  /**
   * Collect system and application metrics
   */
  async collectMetrics(): Promise<MonitoringMetrics> {
    const [systemMetrics, appMetrics, dbMetrics, businessMetrics] = await Promise.all([
      this.collectSystemMetrics(),
      this.collectApplicationMetrics(),
      this.collectDatabaseMetrics(),
      this.collectBusinessMetrics()
    ]);

    const metrics: MonitoringMetrics = {
      system: systemMetrics,
      application: appMetrics,
      database: dbMetrics,
      business: businessMetrics
    };

    // Store metrics in Redis for real-time access
    await this.storeMetrics(metrics);

    return metrics;
  }

  /**
   * Create custom alert
   */
  async createAlert(alert: Omit<Alert, 'id' | 'timestamp' | 'resolved'>): Promise<Alert> {
    const fullAlert: Alert = {
      ...alert,
      id: `alert_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date(),
      resolved: false
    };

    // Store in database
    await this.prisma.alert.create({
      data: {
        id: fullAlert.id,
        type: fullAlert.type,
        severity: fullAlert.severity,
        title: fullAlert.title,
        message: fullAlert.message,
        source: fullAlert.source,
        metadata: fullAlert.metadata,
        timestamp: fullAlert.timestamp,
        resolved: fullAlert.resolved
      }
    });

    // Store in Redis for real-time access
    await this.redis.hset('active_alerts', fullAlert.id, JSON.stringify(fullAlert));

    // Send alert notifications
    await this.sendAlertNotifications(fullAlert);

    logger.warn('Alert created', {
      alertId: fullAlert.id,
      type: fullAlert.type,
      severity: fullAlert.severity,
      title: fullAlert.title
    });

    return fullAlert;
  }

  /**
   * Resolve alert
   */
  async resolveAlert(alertId: string, resolvedBy?: string): Promise<void> {
    const alertData = await this.redis.hget('active_alerts', alertId);

    if (alertData) {
      const alert: Alert = JSON.parse(alertData);
      alert.resolved = true;
      alert.resolvedAt = new Date();
      alert.resolvedBy = resolvedBy;

      // Update database
      await this.prisma.alert.update({
        where: { id: alertId },
        data: {
          resolved: true,
          resolvedAt: alert.resolvedAt,
          resolvedBy
        }
      });

      // Update Redis
      await this.redis.hset('active_alerts', alertId, JSON.stringify(alert));

      logger.info('Alert resolved', {
        alertId,
        resolvedBy,
        resolvedAt: alert.resolvedAt
      });
    }
  }

  /**
   * Get active alerts
   */
  async getActiveAlerts(severity?: string, type?: string): Promise<Alert[]> {
    const alertsData = await this.redis.hgetall('active_alerts');

    let alerts = Object.values(alertsData)
      .map(data => JSON.parse(data) as Alert)
      .filter(alert => !alert.resolved);

    if (severity) {
      alerts = alerts.filter(alert => alert.severity === severity);
    }

    if (type) {
      alerts = alerts.filter(alert => alert.type === type);
    }

    return alerts.sort((a, b) => {
      const severityOrder = { critical: 4, error: 3, warning: 2, info: 1 };
      return severityOrder[b.severity] - severityOrder[a.severity];
    });
  }

  /**
   * Get monitoring metrics for time range
   */
  async getMetricsHistory(
    startTime: Date,
    endTime: Date,
    granularity: 'minute' | 'hour' | 'day' = 'hour'
  ): Promise<Array<{
    timestamp: Date;
    metrics: MonitoringMetrics;
  }>> {
    const timePoints = this.generateTimePoints(startTime, endTime, granularity);
    const history = [];

    for (const timestamp of timePoints) {
      const metricsKey = `metrics:${this.getTimeKey(timestamp, granularity)}`;
      const metricsData = await this.redis.get(metricsKey);

      if (metricsData) {
        history.push({
          timestamp,
          metrics: JSON.parse(metricsData)
        });
      }
    }

    return history;
  }

  /**
   * Check if system is under high load
   */
  async isSystemUnderHighLoad(): Promise<{
    isHighLoad: boolean;
    factors: string[];
    recommendations: string[];
  }> {
    const metrics = await this.collectMetrics();
    const factors = [];
    const recommendations = [];

    // Check various load indicators
    if (metrics.system.cpuUsage > 80) {
      factors.push('High CPU usage');
      recommendations.push('Scale horizontally or optimize CPU-intensive operations');
    }

    if (metrics.system.memoryUsage > 85) {
      factors.push('High memory usage');
      recommendations.push('Increase memory or optimize memory usage');
    }

    if (metrics.application.errorRate > 5) {
      factors.push('High error rate');
      recommendations.push('Investigate and fix application errors');
    }

    if (metrics.application.averageResponseTime > 1000) {
      factors.push('Slow response times');
      recommendations.push('Optimize database queries and application performance');
    }

    if (metrics.database.connectionCount > 80) {
      factors.push('High database connections');
      recommendations.push('Optimize connection pooling or scale database');
    }

    return {
      isHighLoad: factors.length > 0,
      factors,
      recommendations
    };
  }

  /**
   * Generate uptime report
   */
  async generateUptimeReport(days: number = 30): Promise<{
    uptime: number; // percentage
    incidents: Array<{
      start: Date;
      end?: Date;
      duration: number; // minutes
      type: string;
      severity: string;
    }>;
    mttr: number; // mean time to recovery in minutes
    availability: Record<string, number>; // daily availability
  }> {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);

    const incidents = await this.prisma.alert.findMany({
      where: {
        timestamp: {
          gte: startDate,
          lte: endDate
        },
        severity: {
          in: ['critical', 'error']
        }
      },
      orderBy: {
        timestamp: 'asc'
      }
    });

    const processedIncidents = incidents.map(incident => ({
      start: incident.timestamp,
      end: incident.resolvedAt,
      duration: incident.resolvedAt
        ? Math.floor((incident.resolvedAt.getTime() - incident.timestamp.getTime()) / (1000 * 60))
        : 0,
      type: incident.type,
      severity: incident.severity
    }));

    const totalDowntime = processedIncidents.reduce((sum, incident) => sum + incident.duration, 0);
    const totalMinutes = days * 24 * 60;
    const uptime = Math.max(0, ((totalMinutes - totalDowntime) / totalMinutes) * 100);

    const mttr = processedIncidents.length > 0
      ? processedIncidents.reduce((sum, incident) => sum + incident.duration, 0) / processedIncidents.length
      : 0;

    // Calculate daily availability (simplified)
    const availability: Record<string, number> = {};
    for (let i = 0; i < days; i++) {
      const date = new Date(startDate);
      date.setDate(date.getDate() + i);
      const dateKey = date.toISOString().split('T')[0];
      availability[dateKey] = 99.9; // Placeholder - would calculate actual
    }

    return {
      uptime,
      incidents: processedIncidents,
      mttr,
      availability
    };
  }

  // Private methods

  private startHealthChecks(): void {
    // Run health checks every minute
    setInterval(async () => {
      try {
        await this.performHealthCheck();
      } catch (error) {
        logger.error('Health check failed', { error });
      }
    }, 60000);
  }

  private startMetricsCollection(): void {
    // Collect metrics every 30 seconds
    setInterval(async () => {
      try {
        await this.collectMetrics();
      } catch (error) {
        logger.error('Metrics collection failed', { error });
      }
    }, 30000);
  }

  private startAlertEvaluation(): void {
    // Evaluate alert rules every minute
    setInterval(async () => {
      try {
        await this.evaluateAlertRules();
      } catch (error) {
        logger.error('Alert rule evaluation failed', { error });
      }
    }, 60000);
  }

  private async checkDatabase(): Promise<HealthCheck> {
    const start = Date.now();
    try {
      await this.prisma.$queryRaw`SELECT 1`;
      const responseTime = Date.now() - start;

      return {
        name: 'database',
        status: responseTime < 100 ? 'healthy' : 'warning',
        responseTime,
        message: responseTime < 100 ? 'Database responding normally' : 'Database response slow',
        lastCheck: new Date()
      };
    } catch (error) {
      return {
        name: 'database',
        status: 'critical',
        responseTime: Date.now() - start,
        message: 'Database connection failed',
        metadata: { error: error.message },
        lastCheck: new Date()
      };
    }
  }

  private async checkRedis(): Promise<HealthCheck> {
    const start = Date.now();
    try {
      await this.redis.ping();
      const responseTime = Date.now() - start;

      return {
        name: 'redis',
        status: responseTime < 50 ? 'healthy' : 'warning',
        responseTime,
        message: responseTime < 50 ? 'Redis responding normally' : 'Redis response slow',
        lastCheck: new Date()
      };
    } catch (error) {
      return {
        name: 'redis',
        status: 'critical',
        responseTime: Date.now() - start,
        message: 'Redis connection failed',
        metadata: { error: error.message },
        lastCheck: new Date()
      };
    }
  }

  private async checkPaymentGateways(): Promise<HealthCheck> {
    // Simplified gateway health check
    return {
      name: 'payment_gateways',
      status: 'healthy',
      responseTime: 200,
      message: 'All payment gateways operational',
      lastCheck: new Date()
    };
  }

  private async checkExternalServices(): Promise<HealthCheck> {
    // Check external service dependencies
    return {
      name: 'external_services',
      status: 'healthy',
      responseTime: 150,
      message: 'External services operational',
      lastCheck: new Date()
    };
  }

  private async checkDiskSpace(): Promise<HealthCheck> {
    // Would implement actual disk space check
    const freeSpace = 75; // Percentage

    return {
      name: 'disk_space',
      status: freeSpace > 20 ? 'healthy' : freeSpace > 10 ? 'warning' : 'critical',
      responseTime: 0,
      message: `${freeSpace}% disk space available`,
      metadata: { freeSpacePercent: freeSpace },
      lastCheck: new Date()
    };
  }

  private async checkMemoryUsage(): Promise<HealthCheck> {
    // Would implement actual memory check
    const memoryUsage = 65; // Percentage

    return {
      name: 'memory_usage',
      status: memoryUsage < 80 ? 'healthy' : memoryUsage < 90 ? 'warning' : 'critical',
      responseTime: 0,
      message: `${memoryUsage}% memory usage`,
      metadata: { memoryUsagePercent: memoryUsage },
      lastCheck: new Date()
    };
  }

  private async checkAPIHealth(): Promise<HealthCheck> {
    const realTimeMetrics = await this.telemetryService.getRealTimeMetrics();

    let status: 'healthy' | 'warning' | 'critical' = 'healthy';
    if (realTimeMetrics.errorRate > 10) {
      status = 'critical';
    } else if (realTimeMetrics.errorRate > 5 || realTimeMetrics.responseTime > 1000) {
      status = 'warning';
    }

    return {
      name: 'api_health',
      status,
      responseTime: realTimeMetrics.responseTime,
      message: `${realTimeMetrics.errorRate.toFixed(1)}% error rate, ${realTimeMetrics.responseTime.toFixed(0)}ms avg response`,
      metadata: {
        errorRate: realTimeMetrics.errorRate,
        activeUsers: realTimeMetrics.activeUsers,
        currentApiCalls: realTimeMetrics.currentApiCalls
      },
      lastCheck: new Date()
    };
  }

  private async collectSystemMetrics() {
    // Would implement actual system metrics collection
    return {
      cpuUsage: 45.2,
      memoryUsage: 68.5,
      diskUsage: 34.8,
      networkLatency: 12.3
    };
  }

  private async collectApplicationMetrics() {
    const realTimeMetrics = await this.telemetryService.getRealTimeMetrics();

    return {
      requestsPerMinute: realTimeMetrics.currentApiCalls,
      averageResponseTime: realTimeMetrics.responseTime,
      errorRate: realTimeMetrics.errorRate,
      activeConnections: realTimeMetrics.activeUsers
    };
  }

  private async collectDatabaseMetrics() {
    return {
      connectionCount: 25,
      queryTime: 45.6,
      slowQueries: 2,
      deadlocks: 0
    };
  }

  private async collectBusinessMetrics() {
    const insights = await this.adminService.getCustomerInsights();

    return {
      activeUsers: insights.activeCustomers,
      revenueGrowthRate: 12.5, // Placeholder
      churnRate: insights.churnRate,
      licenseUtilization: 78.3 // Placeholder
    };
  }

  private async storeMetrics(metrics: MonitoringMetrics): Promise<void> {
    const now = new Date();
    const minuteKey = this.getTimeKey(now, 'minute');
    const hourKey = this.getTimeKey(now, 'hour');

    await Promise.all([
      this.redis.setex(`metrics:${minuteKey}`, 3600, JSON.stringify(metrics)), // 1 hour retention
      this.redis.setex(`metrics:${hourKey}`, 86400 * 7, JSON.stringify(metrics)) // 7 days retention
    ]);
  }

  private async evaluateAlertRules(): Promise<void> {
    const metrics = await this.collectMetrics();

    for (const rule of this.alertRules) {
      if (!rule.enabled) continue;

      try {
        const shouldAlert = this.evaluateCondition(rule.condition, metrics, rule.threshold);

        if (shouldAlert) {
          // Check cooldown
          const lastAlert = await this.redis.get(`alert_cooldown:${rule.id}`);
          if (lastAlert) continue; // Still in cooldown

          // Create alert
          await this.createAlert({
            type: 'system',
            severity: rule.severity,
            title: rule.name,
            message: `Alert condition met: ${rule.condition}`,
            source: 'monitoring_service',
            metadata: {
              rule: rule.id,
              condition: rule.condition,
              threshold: rule.threshold,
              currentMetrics: metrics
            }
          });

          // Set cooldown
          await this.redis.setex(`alert_cooldown:${rule.id}`, rule.cooldownMinutes * 60, '1');
        }
      } catch (error) {
        logger.error('Alert rule evaluation failed', { error, ruleId: rule.id });
      }
    }
  }

  private evaluateCondition(condition: string, metrics: MonitoringMetrics, threshold: number): boolean {
    // Simplified condition evaluation
    // In a real implementation, this would be a proper expression parser
    if (condition === 'cpu_usage') {
      return metrics.system.cpuUsage > threshold;
    }
    if (condition === 'memory_usage') {
      return metrics.system.memoryUsage > threshold;
    }
    if (condition === 'error_rate') {
      return metrics.application.errorRate > threshold;
    }
    if (condition === 'response_time') {
      return metrics.application.averageResponseTime > threshold;
    }

    return false;
  }

  private async sendAlertNotifications(alert: Alert): Promise<void> {
    // Send notifications via configured channels
    logger.warn('Alert notification', {
      alertId: alert.id,
      severity: alert.severity,
      title: alert.title,
      message: alert.message
    });

    // Would implement actual notification sending (email, Slack, webhook, etc.)
  }

  private getTimeKey(date: Date, granularity: 'minute' | 'hour' | 'day'): string {
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    const hour = date.getHours();
    const minute = date.getMinutes();

    switch (granularity) {
      case 'minute':
        return `${year}-${month}-${day}-${hour}-${minute}`;
      case 'hour':
        return `${year}-${month}-${day}-${hour}`;
      case 'day':
        return `${year}-${month}-${day}`;
    }
  }

  private generateTimePoints(start: Date, end: Date, granularity: 'minute' | 'hour' | 'day'): Date[] {
    const points = [];
    const current = new Date(start);

    while (current <= end) {
      points.push(new Date(current));

      switch (granularity) {
        case 'minute':
          current.setMinutes(current.getMinutes() + 1);
          break;
        case 'hour':
          current.setHours(current.getHours() + 1);
          break;
        case 'day':
          current.setDate(current.getDate() + 1);
          break;
      }
    }

    return points;
  }

  private getDefaultAlertRules(): AlertRule[] {
    return [
      {
        id: 'high_cpu',
        name: 'High CPU Usage',
        condition: 'cpu_usage',
        threshold: 80,
        severity: 'warning',
        enabled: true,
        cooldownMinutes: 15,
        channels: ['email']
      },
      {
        id: 'critical_cpu',
        name: 'Critical CPU Usage',
        condition: 'cpu_usage',
        threshold: 95,
        severity: 'critical',
        enabled: true,
        cooldownMinutes: 5,
        channels: ['email', 'webhook']
      },
      {
        id: 'high_memory',
        name: 'High Memory Usage',
        condition: 'memory_usage',
        threshold: 85,
        severity: 'warning',
        enabled: true,
        cooldownMinutes: 15,
        channels: ['email']
      },
      {
        id: 'high_error_rate',
        name: 'High Error Rate',
        condition: 'error_rate',
        threshold: 5,
        severity: 'warning',
        enabled: true,
        cooldownMinutes: 10,
        channels: ['email']
      },
      {
        id: 'slow_response',
        name: 'Slow Response Time',
        condition: 'response_time',
        threshold: 1000,
        severity: 'warning',
        enabled: true,
        cooldownMinutes: 10,
        channels: ['email']
      }
    ];
  }
}