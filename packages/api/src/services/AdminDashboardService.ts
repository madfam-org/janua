/**
 * Admin Dashboard Service
 * Provides comprehensive platform management and monitoring capabilities
 */

import { PrismaClient } from '@prisma/client';
import { TelemetryService } from './TelemetryService';
import { LicenseService } from './LicenseService';
import { PaymentGatewayService } from './PaymentGatewayService';
import { RedisService } from './RedisService';
import { logger } from '../utils/logger';

interface DashboardOverview {
  metrics: {
    totalUsers: number;
    activeUsers: number;
    totalOrganizations: number;
    totalLicenses: number;
    activeLicenses: number;
    totalRevenue: number;
    monthlyRecurringRevenue: number;
  };
  growth: {
    userGrowth: number; // percentage
    revenueGrowth: number; // percentage
    licenseGrowth: number; // percentage
  };
  health: {
    systemStatus: 'healthy' | 'warning' | 'critical';
    apiResponseTime: number;
    errorRate: number;
    uptime: number;
  };
  alerts: Array<{
    id: string;
    type: 'info' | 'warning' | 'error' | 'critical';
    message: string;
    timestamp: Date;
    resolved: boolean;
  }>;
}

interface SystemHealth {
  database: {
    status: 'healthy' | 'warning' | 'critical';
    connectionCount: number;
    queryTime: number;
  };
  redis: {
    status: 'healthy' | 'warning' | 'critical';
    memory: number;
    connectedClients: number;
  };
  paymentGateways: {
    conekta: { status: 'healthy' | 'warning' | 'critical'; latency: number };
    fungies: { status: 'healthy' | 'warning' | 'critical'; latency: number };
    stripe: { status: 'healthy' | 'warning' | 'critical'; latency: number };
  };
  api: {
    requestsPerMinute: number;
    averageResponseTime: number;
    errorRate: number;
  };
}

interface CustomerInsights {
  totalCustomers: number;
  activeCustomers: number;
  churnRate: number;
  averageRevenuePerUser: number;
  topCustomers: Array<{
    id: string;
    name: string;
    email: string;
    plan: string;
    revenue: number;
    licenseCount: number;
  }>;
  planDistribution: Record<string, number>;
  geographicDistribution: Record<string, number>;
}

interface LicenseMetrics {
  total: number;
  active: number;
  suspended: number;
  expired: number;
  byPlan: Record<string, number>;
  usage: {
    averageApiCalls: number;
    averageValidations: number;
    topUsers: Array<{
      licenseId: string;
      organizationName: string;
      plan: string;
      apiCalls: number;
      validations: number;
    }>;
  };
  compliance: {
    underLimit: number;
    nearLimit: number;
    overLimit: number;
  };
}

interface RevenueAnalytics {
  totalRevenue: number;
  monthlyRecurringRevenue: number;
  averageRevenuePerUser: number;
  revenueByPlan: Record<string, number>;
  revenueByGateway: Record<string, number>;
  revenueGrowth: Array<{
    month: string;
    revenue: number;
    growth: number;
  }>;
  forecasting: {
    nextMonth: number;
    nextQuarter: number;
    confidence: number;
  };
}

export class AdminDashboardService {
  private prisma: PrismaClient;
  private telemetryService: TelemetryService;
  private licenseService: LicenseService;
  private paymentService: PaymentGatewayService;
  private redis: RedisService;

  constructor() {
    this.prisma = new PrismaClient();
    this.telemetryService = new TelemetryService();
    this.licenseService = new LicenseService();
    this.paymentService = new PaymentGatewayService();
    this.redis = new RedisService();
  }

  /**
   * Get dashboard overview
   */
  async getDashboardOverview(): Promise<DashboardOverview> {
    const [metrics, growth, health, alerts] = await Promise.all([
      this.getMetrics(),
      this.getGrowthMetrics(),
      this.getHealthStatus(),
      this.getActiveAlerts()
    ]);

    return {
      metrics,
      growth,
      health,
      alerts
    };
  }

  /**
   * Get system health status
   */
  async getSystemHealth(): Promise<SystemHealth> {
    const [dbHealth, redisHealth, gatewayHealth, apiHealth] = await Promise.all([
      this.getDatabaseHealth(),
      this.getRedisHealth(),
      this.getPaymentGatewayHealth(),
      this.getApiHealth()
    ]);

    return {
      database: dbHealth,
      redis: redisHealth,
      paymentGateways: gatewayHealth,
      api: apiHealth
    };
  }

  /**
   * Get customer insights
   */
  async getCustomerInsights(): Promise<CustomerInsights> {
    // Get basic customer counts
    const totalCustomers = await this.prisma.user.count();

    // Active customers (with activity in last 30 days)
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const activeCustomers = await this.prisma.user.count({
      where: {
        lastLoginAt: {
          gte: thirtyDaysAgo
        }
      }
    });

    // Calculate churn rate (simplified)
    const churnRate = totalCustomers > 0 ? ((totalCustomers - activeCustomers) / totalCustomers) * 100 : 0;

    // Get revenue data for ARPU calculation
    const revenueData = await this.getRevenueData();
    const averageRevenuePerUser = totalCustomers > 0 ? revenueData.totalRevenue / totalCustomers : 0;

    // Get top customers
    const topCustomers = await this.getTopCustomers();

    // Get plan distribution
    const planDistribution = await this.getPlanDistribution();

    // Get geographic distribution
    const geographicDistribution = await this.getGeographicDistribution();

    return {
      totalCustomers,
      activeCustomers,
      churnRate,
      averageRevenuePerUser,
      topCustomers,
      planDistribution,
      geographicDistribution
    };
  }

  /**
   * Get license metrics
   */
  async getLicenseMetrics(): Promise<LicenseMetrics> {
    // Basic license counts
    const [total, active, suspended, expired] = await Promise.all([
      this.prisma.license.count(),
      this.prisma.license.count({ where: { status: 'active' } }),
      this.prisma.license.count({ where: { status: 'suspended' } }),
      this.prisma.license.count({ where: { status: 'expired' } })
    ]);

    // Plan distribution
    const planCounts = await this.prisma.license.groupBy({
      by: ['plan'],
      _count: { plan: true }
    });

    const byPlan = planCounts.reduce((acc, item) => {
      acc[item.plan] = item._count.plan;
      return acc;
    }, {} as Record<string, number>);

    // Usage metrics
    const usage = await this.getLicenseUsageMetrics();

    // Compliance metrics
    const compliance = await this.getLicenseComplianceMetrics();

    return {
      total,
      active,
      suspended,
      expired,
      byPlan,
      usage,
      compliance
    };
  }

  /**
   * Get revenue analytics
   */
  async getRevenueAnalytics(): Promise<RevenueAnalytics> {
    const revenueData = await this.getRevenueData();
    const revenueByPlan = await this.getRevenueByPlan();
    const revenueByGateway = await this.getRevenueByGateway();
    const revenueGrowth = await this.getRevenueGrowth();
    const forecasting = await this.getRevenueForecast();

    return {
      totalRevenue: revenueData.totalRevenue,
      monthlyRecurringRevenue: revenueData.monthlyRecurringRevenue,
      averageRevenuePerUser: revenueData.averageRevenuePerUser,
      revenueByPlan,
      revenueByGateway,
      revenueGrowth,
      forecasting
    };
  }

  /**
   * Get platform statistics
   */
  async getPlatformStatistics(): Promise<{
    sdkDownloads: Record<string, number>;
    apiCalls: number;
    errorRate: number;
    topFeatures: Array<{ feature: string; usage: number }>;
    performanceMetrics: {
      averageResponseTime: number;
      p95ResponseTime: number;
      throughput: number;
    };
  }> {
    const [sdkMetrics, realTimeMetrics] = await Promise.all([
      this.telemetryService.getSDKMetrics('month'),
      this.telemetryService.getRealTimeMetrics()
    ]);

    return {
      sdkDownloads: sdkMetrics.downloads.bySDK,
      apiCalls: sdkMetrics.usage.apiCalls,
      errorRate: sdkMetrics.usage.errorRate,
      topFeatures: sdkMetrics.features.mostUsed,
      performanceMetrics: {
        averageResponseTime: sdkMetrics.performance.averageResponseTime,
        p95ResponseTime: sdkMetrics.performance.p95ResponseTime,
        throughput: realTimeMetrics.currentApiCalls
      }
    };
  }

  /**
   * Create system alert
   */
  async createAlert(data: {
    type: 'info' | 'warning' | 'error' | 'critical';
    message: string;
    source?: string;
    metadata?: Record<string, any>;
  }): Promise<void> {
    const alertId = `alert_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    await this.redis.hset('system_alerts', alertId, JSON.stringify({
      id: alertId,
      type: data.type,
      message: data.message,
      source: data.source || 'system',
      metadata: data.metadata || {},
      timestamp: new Date(),
      resolved: false
    }));

    // Set expiration for non-critical alerts
    if (data.type !== 'critical') {
      await this.redis.expire('system_alerts', 86400 * 7); // 7 days
    }

    logger.info('System alert created', {
      alertId,
      type: data.type,
      message: data.message
    });
  }

  /**
   * Resolve alert
   */
  async resolveAlert(alertId: string): Promise<void> {
    const alertData = await this.redis.hget('system_alerts', alertId);

    if (alertData) {
      const alert = JSON.parse(alertData);
      alert.resolved = true;
      alert.resolvedAt = new Date();

      await this.redis.hset('system_alerts', alertId, JSON.stringify(alert));

      logger.info('System alert resolved', { alertId });
    }
  }

  // Private helper methods

  private async getMetrics() {
    const [totalUsers, activeUsers, totalOrganizations, totalLicenses, activeLicenses] = await Promise.all([
      this.prisma.user.count(),
      this.prisma.user.count({
        where: {
          lastLoginAt: {
            gte: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000) // Last 30 days
          }
        }
      }),
      this.prisma.organization.count(),
      this.prisma.license.count(),
      this.prisma.license.count({ where: { status: 'active' } })
    ]);

    const revenueData = await this.getRevenueData();

    return {
      totalUsers,
      activeUsers,
      totalOrganizations,
      totalLicenses,
      activeLicenses,
      totalRevenue: revenueData.totalRevenue,
      monthlyRecurringRevenue: revenueData.monthlyRecurringRevenue
    };
  }

  private async getGrowthMetrics() {
    // Calculate growth metrics (simplified)
    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
    const sixtyDaysAgo = new Date(Date.now() - 60 * 24 * 60 * 60 * 1000);

    const [currentUsers, previousUsers] = await Promise.all([
      this.prisma.user.count({
        where: { createdAt: { gte: thirtyDaysAgo } }
      }),
      this.prisma.user.count({
        where: {
          createdAt: {
            gte: sixtyDaysAgo,
            lt: thirtyDaysAgo
          }
        }
      })
    ]);

    const userGrowth = previousUsers > 0 ? ((currentUsers - previousUsers) / previousUsers) * 100 : 0;

    // Similar calculations for revenue and licenses
    const revenueGrowth = 12.5; // Placeholder
    const licenseGrowth = 8.3; // Placeholder

    return {
      userGrowth,
      revenueGrowth,
      licenseGrowth
    };
  }

  private async getHealthStatus() {
    const realTimeMetrics = await this.telemetryService.getRealTimeMetrics();

    // Determine system status based on metrics
    let systemStatus: 'healthy' | 'warning' | 'critical' = 'healthy';

    if (realTimeMetrics.errorRate > 10) {
      systemStatus = 'critical';
    } else if (realTimeMetrics.errorRate > 5 || realTimeMetrics.responseTime > 1000) {
      systemStatus = 'warning';
    }

    return {
      systemStatus,
      apiResponseTime: realTimeMetrics.responseTime,
      errorRate: realTimeMetrics.errorRate,
      uptime: 99.9 // Placeholder
    };
  }

  private async getActiveAlerts() {
    const alertsData = await this.redis.hgetall('system_alerts');

    const alerts = Object.values(alertsData)
      .map(data => JSON.parse(data))
      .filter(alert => !alert.resolved)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
      .slice(0, 10); // Last 10 unresolved alerts

    return alerts;
  }

  private async getDatabaseHealth() {
    try {
      const start = Date.now();
      await this.prisma.$queryRaw`SELECT 1`;
      const queryTime = Date.now() - start;

      return {
        status: 'healthy' as const,
        connectionCount: 10, // Placeholder
        queryTime
      };
    } catch (error) {
      logger.error('Database health check failed', { error });
      return {
        status: 'critical' as const,
        connectionCount: 0,
        queryTime: 0
      };
    }
  }

  private async getRedisHealth() {
    try {
      const start = Date.now();
      await this.redis.ping();
      const responseTime = Date.now() - start;

      return {
        status: responseTime < 100 ? 'healthy' as const : 'warning' as const,
        memory: 128, // Placeholder - would get from Redis INFO
        connectedClients: 5 // Placeholder
      };
    } catch (error) {
      logger.error('Redis health check failed', { error });
      return {
        status: 'critical' as const,
        memory: 0,
        connectedClients: 0
      };
    }
  }

  private async getPaymentGatewayHealth() {
    // Simplified gateway health checks
    return {
      conekta: { status: 'healthy' as const, latency: 150 },
      fungies: { status: 'healthy' as const, latency: 200 },
      stripe: { status: 'healthy' as const, latency: 120 }
    };
  }

  private async getApiHealth() {
    const realTimeMetrics = await this.telemetryService.getRealTimeMetrics();

    return {
      requestsPerMinute: realTimeMetrics.currentApiCalls,
      averageResponseTime: realTimeMetrics.responseTime,
      errorRate: realTimeMetrics.errorRate
    };
  }

  private async getRevenueData() {
    // Simplified revenue calculation
    // In a real implementation, this would aggregate from payment gateway data
    return {
      totalRevenue: 125000, // Placeholder
      monthlyRecurringRevenue: 15000, // Placeholder
      averageRevenuePerUser: 85 // Placeholder
    };
  }

  private async getTopCustomers() {
    // Simplified top customers query
    return [
      {
        id: '1',
        name: 'Enterprise Corp',
        email: 'admin@enterprise.com',
        plan: 'enterprise',
        revenue: 5000,
        licenseCount: 3
      }
    ]; // Placeholder
  }

  private async getPlanDistribution() {
    const planCounts = await this.prisma.license.groupBy({
      by: ['plan'],
      _count: { plan: true }
    });

    return planCounts.reduce((acc, item) => {
      acc[item.plan] = item._count.plan;
      return acc;
    }, {} as Record<string, number>);
  }

  private async getGeographicDistribution() {
    // Simplified geographic distribution
    return {
      'US': 45,
      'MX': 30,
      'CA': 15,
      'Other': 10
    }; // Placeholder
  }

  private async getLicenseUsageMetrics() {
    // Simplified usage metrics
    return {
      averageApiCalls: 1250,
      averageValidations: 850,
      topUsers: [
        {
          licenseId: 'lic_123',
          organizationName: 'Tech Corp',
          plan: 'enterprise',
          apiCalls: 5000,
          validations: 3500
        }
      ]
    }; // Placeholder
  }

  private async getLicenseComplianceMetrics() {
    // Simplified compliance metrics
    return {
      underLimit: 85,
      nearLimit: 12,
      overLimit: 3
    }; // Placeholder
  }

  private async getRevenueByPlan() {
    return {
      pro: 45000,
      enterprise: 80000
    }; // Placeholder
  }

  private async getRevenueByGateway() {
    return {
      stripe: 50000,
      conekta: 35000,
      fungies: 40000
    }; // Placeholder
  }

  private async getRevenueGrowth() {
    return [
      { month: '2024-11', revenue: 110000, growth: 8.5 },
      { month: '2024-12', revenue: 120000, growth: 9.1 },
      { month: '2025-01', revenue: 125000, growth: 4.2 }
    ]; // Placeholder
  }

  private async getRevenueForecast() {
    return {
      nextMonth: 135000,
      nextQuarter: 420000,
      confidence: 85
    }; // Placeholder
  }
}