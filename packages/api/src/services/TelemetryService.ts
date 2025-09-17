/**
 * Telemetry and Analytics Service
 * Tracks SDK usage, customer behavior, and platform metrics
 */

import { PrismaClient } from '@prisma/client';
import { RedisService } from './RedisService';
import { logger } from '../utils/logger';

interface TelemetryEvent {
  eventType: string;
  userId?: string;
  organizationId?: string;
  licenseId?: string;
  sessionId?: string;
  properties: Record<string, any>;
  context: {
    sdk?: string;
    version?: string;
    platform?: string;
    environment?: string;
    ip?: string;
    userAgent?: string;
    country?: string;
    timestamp: Date;
  };
}

interface AnalyticsQuery {
  eventTypes?: string[];
  organizationId?: string;
  licenseId?: string;
  startDate: Date;
  endDate: Date;
  granularity: 'hour' | 'day' | 'week' | 'month';
  limit?: number;
}

interface AnalyticsResult {
  period: {
    start: Date;
    end: Date;
    granularity: string;
  };
  totalEvents: number;
  uniqueUsers: number;
  uniqueOrganizations: number;
  topEvents: Array<{
    eventType: string;
    count: number;
  }>;
  timeline: Array<{
    timestamp: Date;
    events: number;
    uniqueUsers: number;
  }>;
  breakdown: {
    bySDK: Record<string, number>;
    byPlatform: Record<string, number>;
    byCountry: Record<string, number>;
    byEnvironment: Record<string, number>;
  };
}

interface SDKMetrics {
  downloads: {
    total: number;
    byVersion: Record<string, number>;
    bySDK: Record<string, number>;
  };
  usage: {
    activeUsers: number;
    activeOrganizations: number;
    apiCalls: number;
    errorRate: number;
  };
  features: {
    mostUsed: Array<{ feature: string; count: number }>;
    adoption: Record<string, number>;
  };
  performance: {
    averageResponseTime: number;
    p95ResponseTime: number;
    errorsByType: Record<string, number>;
  };
}

export class TelemetryService {
  private prisma: PrismaClient;
  private redis: RedisService;

  constructor() {
    this.prisma = new PrismaClient();
    this.redis = new RedisService();
  }

  /**
   * Track a telemetry event
   */
  async trackEvent(event: TelemetryEvent): Promise<void> {
    try {
      // Store in database for long-term analytics
      await this.prisma.telemetryEvent.create({
        data: {
          eventType: event.eventType,
          userId: event.userId,
          organizationId: event.organizationId,
          licenseId: event.licenseId,
          sessionId: event.sessionId,
          properties: event.properties,
          context: event.context,
          timestamp: event.context.timestamp
        }
      });

      // Store in Redis for real-time analytics
      await this.updateRealTimeMetrics(event);

      // Update aggregated metrics
      await this.updateAggregatedMetrics(event);

    } catch (error) {
      logger.error('Error tracking telemetry event', { error, event });
    }
  }

  /**
   * Track SDK download
   */
  async trackDownload(data: {
    sdk: string;
    version: string;
    platform?: string;
    ip?: string;
    userAgent?: string;
    country?: string;
  }): Promise<void> {
    const event: TelemetryEvent = {
      eventType: 'sdk_download',
      properties: {
        sdk: data.sdk,
        version: data.version
      },
      context: {
        sdk: data.sdk,
        version: data.version,
        platform: data.platform,
        ip: data.ip,
        userAgent: data.userAgent,
        country: data.country,
        timestamp: new Date()
      }
    };

    await this.trackEvent(event);
  }

  /**
   * Track API call
   */
  async trackApiCall(data: {
    endpoint: string;
    method: string;
    statusCode: number;
    responseTime: number;
    userId?: string;
    organizationId?: string;
    licenseId?: string;
    sdk?: string;
    version?: string;
    ip?: string;
  }): Promise<void> {
    const event: TelemetryEvent = {
      eventType: 'api_call',
      userId: data.userId,
      organizationId: data.organizationId,
      licenseId: data.licenseId,
      properties: {
        endpoint: data.endpoint,
        method: data.method,
        statusCode: data.statusCode,
        responseTime: data.responseTime,
        success: data.statusCode < 400
      },
      context: {
        sdk: data.sdk,
        version: data.version,
        ip: data.ip,
        timestamp: new Date()
      }
    };

    await this.trackEvent(event);
  }

  /**
   * Track feature usage
   */
  async trackFeatureUsage(data: {
    feature: string;
    action: string;
    userId?: string;
    organizationId?: string;
    licenseId?: string;
    sdk?: string;
    version?: string;
    metadata?: Record<string, any>;
  }): Promise<void> {
    const event: TelemetryEvent = {
      eventType: 'feature_usage',
      userId: data.userId,
      organizationId: data.organizationId,
      licenseId: data.licenseId,
      properties: {
        feature: data.feature,
        action: data.action,
        ...data.metadata
      },
      context: {
        sdk: data.sdk,
        version: data.version,
        timestamp: new Date()
      }
    };

    await this.trackEvent(event);
  }

  /**
   * Track error
   */
  async trackError(data: {
    errorType: string;
    errorMessage: string;
    stackTrace?: string;
    userId?: string;
    organizationId?: string;
    licenseId?: string;
    sdk?: string;
    version?: string;
    context?: Record<string, any>;
  }): Promise<void> {
    const event: TelemetryEvent = {
      eventType: 'error',
      userId: data.userId,
      organizationId: data.organizationId,
      licenseId: data.licenseId,
      properties: {
        errorType: data.errorType,
        errorMessage: data.errorMessage,
        stackTrace: data.stackTrace,
        ...data.context
      },
      context: {
        sdk: data.sdk,
        version: data.version,
        timestamp: new Date()
      }
    };

    await this.trackEvent(event);
  }

  /**
   * Get analytics data
   */
  async getAnalytics(query: AnalyticsQuery): Promise<AnalyticsResult> {
    const whereClause: any = {
      timestamp: {
        gte: query.startDate,
        lte: query.endDate
      }
    };

    if (query.eventTypes?.length) {
      whereClause.eventType = { in: query.eventTypes };
    }

    if (query.organizationId) {
      whereClause.organizationId = query.organizationId;
    }

    if (query.licenseId) {
      whereClause.licenseId = query.licenseId;
    }

    // Get total events
    const totalEvents = await this.prisma.telemetryEvent.count({ where: whereClause });

    // Get unique users and organizations
    const uniqueUsers = await this.prisma.telemetryEvent.findMany({
      where: whereClause,
      select: { userId: true },
      distinct: ['userId']
    });

    const uniqueOrganizations = await this.prisma.telemetryEvent.findMany({
      where: whereClause,
      select: { organizationId: true },
      distinct: ['organizationId']
    });

    // Get top events
    const topEvents = await this.prisma.telemetryEvent.groupBy({
      by: ['eventType'],
      where: whereClause,
      _count: { eventType: true },
      orderBy: { _count: { eventType: 'desc' } },
      take: 10
    });

    // Generate timeline
    const timeline = await this.generateTimeline(query);

    // Get breakdown data
    const breakdown = await this.getBreakdownData(whereClause);

    return {
      period: {
        start: query.startDate,
        end: query.endDate,
        granularity: query.granularity
      },
      totalEvents,
      uniqueUsers: uniqueUsers.filter(u => u.userId).length,
      uniqueOrganizations: uniqueOrganizations.filter(o => o.organizationId).length,
      topEvents: topEvents.map(e => ({
        eventType: e.eventType,
        count: e._count.eventType
      })),
      timeline,
      breakdown
    };
  }

  /**
   * Get SDK metrics
   */
  async getSDKMetrics(timeframe: 'day' | 'week' | 'month' = 'week'): Promise<SDKMetrics> {
    const startDate = new Date();
    switch (timeframe) {
      case 'day':
        startDate.setDate(startDate.getDate() - 1);
        break;
      case 'week':
        startDate.setDate(startDate.getDate() - 7);
        break;
      case 'month':
        startDate.setMonth(startDate.getMonth() - 1);
        break;
    }

    const whereClause = {
      timestamp: { gte: startDate }
    };

    // Downloads
    const downloads = await this.prisma.telemetryEvent.findMany({
      where: {
        ...whereClause,
        eventType: 'sdk_download'
      },
      select: {
        context: true
      }
    });

    const downloadsByVersion: Record<string, number> = {};
    const downloadsBySDK: Record<string, number> = {};

    downloads.forEach(d => {
      const context = d.context as any;
      const version = context.version || 'unknown';
      const sdk = context.sdk || 'unknown';

      downloadsByVersion[version] = (downloadsByVersion[version] || 0) + 1;
      downloadsBySDK[sdk] = (downloadsBySDK[sdk] || 0) + 1;
    });

    // API usage
    const apiCalls = await this.prisma.telemetryEvent.count({
      where: {
        ...whereClause,
        eventType: 'api_call'
      }
    });

    const activeUsers = await this.prisma.telemetryEvent.findMany({
      where: whereClause,
      select: { userId: true },
      distinct: ['userId']
    }).then(users => users.filter(u => u.userId).length);

    const activeOrganizations = await this.prisma.telemetryEvent.findMany({
      where: whereClause,
      select: { organizationId: true },
      distinct: ['organizationId']
    }).then(orgs => orgs.filter(o => o.organizationId).length);

    // Error rate
    const errors = await this.prisma.telemetryEvent.count({
      where: {
        ...whereClause,
        eventType: 'error'
      }
    });

    const errorRate = apiCalls > 0 ? (errors / apiCalls) * 100 : 0;

    // Feature usage
    const featureUsage = await this.prisma.telemetryEvent.findMany({
      where: {
        ...whereClause,
        eventType: 'feature_usage'
      },
      select: { properties: true }
    });

    const featureCounts: Record<string, number> = {};
    featureUsage.forEach(f => {
      const properties = f.properties as any;
      const feature = properties.feature;
      if (feature) {
        featureCounts[feature] = (featureCounts[feature] || 0) + 1;
      }
    });

    const mostUsedFeatures = Object.entries(featureCounts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, 10)
      .map(([feature, count]) => ({ feature, count }));

    // Performance metrics
    const performanceData = await this.getPerformanceMetrics(whereClause);

    return {
      downloads: {
        total: downloads.length,
        byVersion: downloadsByVersion,
        bySDK: downloadsBySDK
      },
      usage: {
        activeUsers,
        activeOrganizations,
        apiCalls,
        errorRate
      },
      features: {
        mostUsed: mostUsedFeatures,
        adoption: featureCounts
      },
      performance: performanceData
    };
  }

  /**
   * Get real-time metrics from Redis
   */
  async getRealTimeMetrics(): Promise<{
    activeUsers: number;
    currentApiCalls: number;
    errorRate: number;
    responseTime: number;
  }> {
    const now = new Date();
    const fiveMinutesAgo = new Date(now.getTime() - 5 * 60 * 1000);

    const [activeUsers, apiCalls, errors, responseTimes] = await Promise.all([
      this.redis.zcard('active_users'),
      this.redis.get('api_calls:current') || '0',
      this.redis.get('errors:current') || '0',
      this.redis.lrange('response_times', 0, 99) // Last 100 response times
    ]);

    const responseTime = responseTimes.length > 0
      ? responseTimes.reduce((sum, time) => sum + parseFloat(time), 0) / responseTimes.length
      : 0;

    const currentApiCalls = parseInt(apiCalls);
    const currentErrors = parseInt(errors);
    const errorRate = currentApiCalls > 0 ? (currentErrors / currentApiCalls) * 100 : 0;

    return {
      activeUsers,
      currentApiCalls,
      errorRate,
      responseTime
    };
  }

  // Private helper methods

  private async updateRealTimeMetrics(event: TelemetryEvent): Promise<void> {
    const now = new Date();
    const minute = Math.floor(now.getTime() / 60000);

    // Track active users (expires in 5 minutes)
    if (event.userId) {
      await this.redis.zadd('active_users', now.getTime(), event.userId);
      await this.redis.expire('active_users', 300);
    }

    // Track API calls
    if (event.eventType === 'api_call') {
      await this.redis.incr('api_calls:current');
      await this.redis.expire('api_calls:current', 300);

      // Track response times
      const responseTime = event.properties.responseTime;
      if (responseTime) {
        await this.redis.lpush('response_times', responseTime.toString());
        await this.redis.ltrim('response_times', 0, 99); // Keep last 100
      }
    }

    // Track errors
    if (event.eventType === 'error') {
      await this.redis.incr('errors:current');
      await this.redis.expire('errors:current', 300);
    }
  }

  private async updateAggregatedMetrics(event: TelemetryEvent): Promise<void> {
    const day = new Date(event.context.timestamp).toISOString().split('T')[0];
    const hour = new Date(event.context.timestamp).toISOString().split('T')[0] + ':' +
                 new Date(event.context.timestamp).getHours();

    // Daily aggregates
    await this.redis.hincrby(`metrics:daily:${day}`, event.eventType, 1);
    await this.redis.expire(`metrics:daily:${day}`, 86400 * 90); // 90 days

    // Hourly aggregates
    await this.redis.hincrby(`metrics:hourly:${hour}`, event.eventType, 1);
    await this.redis.expire(`metrics:hourly:${hour}`, 86400 * 7); // 7 days

    // Organization metrics
    if (event.organizationId) {
      await this.redis.hincrby(`metrics:org:${event.organizationId}:${day}`, event.eventType, 1);
      await this.redis.expire(`metrics:org:${event.organizationId}:${day}`, 86400 * 30);
    }
  }

  private async generateTimeline(query: AnalyticsQuery): Promise<Array<{
    timestamp: Date;
    events: number;
    uniqueUsers: number;
  }>> {
    // Implementation would depend on the granularity
    // For now, return empty array
    return [];
  }

  private async getBreakdownData(whereClause: any): Promise<{
    bySDK: Record<string, number>;
    byPlatform: Record<string, number>;
    byCountry: Record<string, number>;
    byEnvironment: Record<string, number>;
  }> {
    const events = await this.prisma.telemetryEvent.findMany({
      where: whereClause,
      select: { context: true }
    });

    const bySDK: Record<string, number> = {};
    const byPlatform: Record<string, number> = {};
    const byCountry: Record<string, number> = {};
    const byEnvironment: Record<string, number> = {};

    events.forEach(event => {
      const context = event.context as any;

      if (context.sdk) {
        bySDK[context.sdk] = (bySDK[context.sdk] || 0) + 1;
      }
      if (context.platform) {
        byPlatform[context.platform] = (byPlatform[context.platform] || 0) + 1;
      }
      if (context.country) {
        byCountry[context.country] = (byCountry[context.country] || 0) + 1;
      }
      if (context.environment) {
        byEnvironment[context.environment] = (byEnvironment[context.environment] || 0) + 1;
      }
    });

    return { bySDK, byPlatform, byCountry, byEnvironment };
  }

  private async getPerformanceMetrics(whereClause: any): Promise<{
    averageResponseTime: number;
    p95ResponseTime: number;
    errorsByType: Record<string, number>;
  }> {
    const apiCalls = await this.prisma.telemetryEvent.findMany({
      where: {
        ...whereClause,
        eventType: 'api_call'
      },
      select: { properties: true }
    });

    const responseTimes = apiCalls
      .map(call => (call.properties as any).responseTime)
      .filter(time => typeof time === 'number')
      .sort((a, b) => a - b);

    const averageResponseTime = responseTimes.length > 0
      ? responseTimes.reduce((sum, time) => sum + time, 0) / responseTimes.length
      : 0;

    const p95Index = Math.floor(responseTimes.length * 0.95);
    const p95ResponseTime = responseTimes.length > 0 ? responseTimes[p95Index] || 0 : 0;

    const errors = await this.prisma.telemetryEvent.findMany({
      where: {
        ...whereClause,
        eventType: 'error'
      },
      select: { properties: true }
    });

    const errorsByType: Record<string, number> = {};
    errors.forEach(error => {
      const errorType = (error.properties as any).errorType || 'unknown';
      errorsByType[errorType] = (errorsByType[errorType] || 0) + 1;
    });

    return {
      averageResponseTime,
      p95ResponseTime,
      errorsByType
    };
  }
}