import { EventEmitter } from 'events';
import { Redis } from 'ioredis';
import { createLogger } from '../utils/logger';

const logger = createLogger('HealthCheck');

export interface HealthStatus {
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

export class HealthCheckService extends EventEmitter {
  private redis: Redis;
  private healthChecks: Map<string, () => Promise<boolean>> = new Map();
  private healthCheckInterval: NodeJS.Timeout | null = null;

  constructor(redis: Redis) {
    super();
    this.redis = redis;
  }

  registerHealthCheck(service: string, check: () => Promise<boolean>): void {
    this.healthChecks.set(service, check);
    logger.info(`Health check registered for ${service}`);
  }

  startHealthChecks(): void {
    // Perform health checks every 30 seconds
    this.healthCheckInterval = setInterval(async () => {
      for (const [service] of this.healthChecks) {
        const health = await this.performHealthCheck(service);
        await this.storeHealthStatus(service, health);
      }
    }, 30000);
  }

  stopHealthChecks(): void {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
  }

  async performHealthCheck(service: string): Promise<HealthStatus> {
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

    const _latency = Date.now() - startTime;

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

  async getServiceHealth(service: string): Promise<HealthStatus> {
    return this.performHealthCheck(service);
  }

  async getProviderHealth(provider: string): Promise<HealthStatus> {
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

    const healthyChecks = history.filter(h => h.status === 'healthy').length;
    return (healthyChecks / history.length) * 100;
  }

  private calculateErrorRate(history: any[]): number {
    if (history.length === 0) return 0;

    const unhealthyChecks = history.filter(h => h.status === 'unhealthy').length;
    return (unhealthyChecks / history.length) * 100;
  }

  private calculateLatencyPercentiles(history: any[]): { p50: number; p95: number; p99: number } {
    if (history.length === 0) {
      return { p50: 0, p95: 0, p99: 0 };
    }

    const latencies = history
      .map(h => h.latency || 0)
      .sort((a, b) => a - b);

    return {
      p50: latencies[Math.floor(latencies.length * 0.5)] || 0,
      p95: latencies[Math.floor(latencies.length * 0.95)] || 0,
      p99: latencies[Math.floor(latencies.length * 0.99)] || 0
    };
  }
}

// Export singleton
let healthCheckService: HealthCheckService | null = null;

export function getHealthCheckService(redis: Redis): HealthCheckService {
  if (!healthCheckService) {
    healthCheckService = new HealthCheckService(redis);
  }
  return healthCheckService;
}
