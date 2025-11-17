import { EventEmitter } from 'events';
import Redis from 'ioredis';

interface RedisConfig {
  host: string;
  port: number;
  password?: string;
  db?: number;
  keyPrefix?: string;
  retryStrategy?: (times: number) => number | null;
  enableOfflineQueue?: boolean;
  maxRetriesPerRequest?: number;
}

interface CacheEntry<T = any> {
  value: T;
  ttl?: number;
  tags?: string[];
  metadata?: Record<string, any>;
}

export class RedisService extends EventEmitter {
  private client: Redis;
  private subscriber: Redis;
  private publisher: Redis;
  private config: RedisConfig;
  private isConnected: boolean = false;

  constructor(config: RedisConfig) {
    super();
    this.config = {
      enableOfflineQueue: false,
      maxRetriesPerRequest: 3,
      retryStrategy: (times: number) => {
        const delay = Math.min(times * 100, 3000);
        return delay;
      },
      ...config
    };

    // Initialize Redis clients
    this.client = new Redis(this.config);
    this.subscriber = new Redis(this.config);
    this.publisher = new Redis(this.config);

    this.setupEventHandlers();
  }

  private setupEventHandlers(): void {
    this.client.on('connect', () => {
      this.isConnected = true;
      this.emit('connected');
    });

    this.client.on('error', (error) => {
      this.emit('error', error);
    });

    this.client.on('close', () => {
      this.isConnected = false;
      this.emit('disconnected');
    });

    // Setup subscriber
    this.subscriber.on('message', (channel, message) => {
      this.emit('message', { channel, message: JSON.parse(message) });
    });
  }

  // WebAuthn Challenge Management
  async storeWebAuthnChallenge(
    userId: string,
    challenge: string,
    type: 'registration' | 'authentication',
    ttl: number = 300 // 5 minutes default
  ): Promise<void> {
    const key = `webauthn:${type}:${userId}`;
    await this.client.setex(key, ttl, challenge);
  }

  async getWebAuthnChallenge(
    userId: string,
    type: 'registration' | 'authentication'
  ): Promise<string | null> {
    const key = `webauthn:${type}:${userId}`;
    const challenge = await this.client.get(key);

    if (challenge) {
      // Delete after retrieval for security
      await this.client.del(key);
    }

    return challenge;
  }

  // Session Management
  async storeSession(
    sessionId: string,
    data: Record<string, any>,
    ttl: number = 3600 // 1 hour default
  ): Promise<void> {
    const key = `session:${sessionId}`;
    await this.client.setex(key, ttl, JSON.stringify(data));
  }

  async getSession(sessionId: string): Promise<Record<string, any> | null> {
    const key = `session:${sessionId}`;
    const data = await this.client.get(key);
    return data ? JSON.parse(data) : null;
  }

  async refreshSession(sessionId: string, ttl: number = 3600): Promise<boolean> {
    const key = `session:${sessionId}`;
    const result = await this.client.expire(key, ttl);
    return result === 1;
  }

  async deleteSession(sessionId: string): Promise<boolean> {
    const key = `session:${sessionId}`;
    const result = await this.client.del(key);
    return result === 1;
  }

  // MFA Code Management
  async storeMFACode(
    userId: string,
    code: string,
    method: string,
    ttl: number = 300 // 5 minutes
  ): Promise<void> {
    const key = `mfa:${method}:${userId}`;
    const data = {
      code,
      attempts: 0,
      created_at: Date.now()
    };
    await this.client.setex(key, ttl, JSON.stringify(data));
  }

  async verifyMFACode(
    userId: string,
    code: string,
    method: string,
    maxAttempts: number = 3
  ): Promise<boolean> {
    const key = `mfa:${method}:${userId}`;
    const data = await this.client.get(key);

    if (!data) {
      return false;
    }

    const stored = JSON.parse(data);

    // Check attempts
    if (stored.attempts >= maxAttempts) {
      await this.client.del(key);
      return false;
    }

    // Increment attempts
    stored.attempts++;
    await this.client.set(key, JSON.stringify(stored));

    if (stored.code === code) {
      // Delete on successful verification
      await this.client.del(key);
      return true;
    }

    return false;
  }

  // Rate Limiting
  async checkRateLimit(
    identifier: string,
    limit: number,
    window: number = 60 // seconds
  ): Promise<{ allowed: boolean; remaining: number; resetAt: number }> {
    const key = `ratelimit:${identifier}`;
    const now = Date.now();
    const windowStart = now - (window * 1000);

    // Remove old entries
    await this.client.zremrangebyscore(key, '-inf', windowStart);

    // Count requests in window
    const count = await this.client.zcard(key);

    if (count < limit) {
      // Add current request
      await this.client.zadd(key, now, `${now}-${Math.random()}`);
      await this.client.expire(key, window);

      return {
        allowed: true,
        remaining: limit - count - 1,
        resetAt: now + (window * 1000)
      };
    }

    // Get oldest entry to determine reset time
    const oldest = await this.client.zrange(key, 0, 0, 'WITHSCORES');
    const resetAt = oldest.length > 1 ? parseInt(oldest[1]) + (window * 1000) : now + (window * 1000);

    return {
      allowed: false,
      remaining: 0,
      resetAt
    };
  }

  // Generic Cache Operations
  async set<T>(key: string, value: T, ttl?: number): Promise<void> {
    const data = JSON.stringify(value);
    if (ttl) {
      await this.client.setex(key, ttl, data);
    } else {
      await this.client.set(key, data);
    }
  }

  async get<T>(key: string): Promise<T | null> {
    const data = await this.client.get(key);
    return data ? JSON.parse(data) : null;
  }

  async delete(key: string | string[]): Promise<number> {
    if (Array.isArray(key)) {
      return await this.client.del(...key);
    }
    return await this.client.del(key);
  }

  async exists(key: string): Promise<boolean> {
    const result = await this.client.exists(key);
    return result === 1;
  }

  async ttl(key: string): Promise<number> {
    return await this.client.ttl(key);
  }

  async expire(key: string, ttl: number): Promise<boolean> {
    const result = await this.client.expire(key, ttl);
    return result === 1;
  }

  // Pub/Sub Operations
  async publish(channel: string, message: any): Promise<void> {
    await this.publisher.publish(channel, JSON.stringify(message));
  }

  async subscribe(channels: string | string[]): Promise<void> {
    if (Array.isArray(channels)) {
      await this.subscriber.subscribe(...channels);
    } else {
      await this.subscriber.subscribe(channels);
    }
  }

  async unsubscribe(channels?: string | string[]): Promise<void> {
    if (channels) {
      if (Array.isArray(channels)) {
        await this.subscriber.unsubscribe(...channels);
      } else {
        await this.subscriber.unsubscribe(channels);
      }
    } else {
      await this.subscriber.unsubscribe();
    }
  }

  // List Operations
  async lpush(key: string, ...values: any[]): Promise<number> {
    const serialized = values.map(v => JSON.stringify(v));
    return await this.client.lpush(key, ...serialized);
  }

  async rpush(key: string, ...values: any[]): Promise<number> {
    const serialized = values.map(v => JSON.stringify(v));
    return await this.client.rpush(key, ...serialized);
  }

  async ltrim(key: string, start: number, stop: number): Promise<string> {
    return await this.client.ltrim(key, start, stop);
  }

  async lpop<T>(key: string): Promise<T | null> {
    const data = await this.client.lpop(key);
    return data ? JSON.parse(data) : null;
  }

  async rpop<T>(key: string): Promise<T | null> {
    const data = await this.client.rpop(key);
    return data ? JSON.parse(data) : null;
  }

  async lrange<T>(key: string, start: number, stop: number): Promise<T[]> {
    const data = await this.client.lrange(key, start, stop);
    return data.map(item => JSON.parse(item));
  }

  async llen(key: string): Promise<number> {
    return await this.client.llen(key);
  }

  // Set Operations
  async sadd(key: string, ...members: any[]): Promise<number> {
    const serialized = members.map(m => JSON.stringify(m));
    return await this.client.sadd(key, ...serialized);
  }

  async srem(key: string, ...members: any[]): Promise<number> {
    const serialized = members.map(m => JSON.stringify(m));
    return await this.client.srem(key, ...serialized);
  }

  async smembers<T>(key: string): Promise<T[]> {
    const members = await this.client.smembers(key);
    return members.map(m => JSON.parse(m));
  }

  async sismember(key: string, member: any): Promise<boolean> {
    const result = await this.client.sismember(key, JSON.stringify(member));
    return result === 1;
  }

  // Hash Operations
  async hset(key: string, field: string, value: any): Promise<number> {
    return await this.client.hset(key, field, JSON.stringify(value));
  }

  async hget<T>(key: string, field: string): Promise<T | null> {
    const data = await this.client.hget(key, field);
    return data ? JSON.parse(data) : null;
  }

  async hgetall<T = any>(key: string): Promise<Record<string, T>> {
    const data = await this.client.hgetall(key);
    const result: Record<string, T> = {};
    for (const [field, value] of Object.entries(data)) {
      result[field] = JSON.parse(value);
    }
    return result;
  }

  async hdel(key: string, ...fields: string[]): Promise<number> {
    return await this.client.hdel(key, ...fields);
  }

  // Atomic Operations
  async incr(key: string): Promise<number> {
    return await this.client.incr(key);
  }

  async decr(key: string): Promise<number> {
    return await this.client.decr(key);
  }

  async incrby(key: string, increment: number): Promise<number> {
    return await this.client.incrby(key, increment);
  }

  async hincrby(key: string, field: string, increment: number): Promise<number> {
    return await this.client.hincrby(key, field, increment);
  }

  async decrby(key: string, decrement: number): Promise<number> {
    return await this.client.decrby(key, decrement);
  }

  // Lock Operations for Distributed Systems
  async acquireLock(
    resource: string,
    ttl: number = 10000, // 10 seconds default
    retries: number = 10,
    retryDelay: number = 100
  ): Promise<{ lockId: string; unlock: () => Promise<void> } | null> {
    const lockId = `${Date.now()}-${Math.random()}`;
    const lockKey = `lock:${resource}`;

    for (let i = 0; i < retries; i++) {
      const result = await this.client.set(
        lockKey,
        lockId,
        'PX',
        ttl,
        'NX'
      );

      if (result === 'OK') {
        return {
          lockId,
          unlock: async () => {
            // Lua script for atomic unlock
            const script = `
              if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
              else
                return 0
              end
            `;
            await this.client.eval(script, 1, lockKey, lockId);
          }
        };
      }

      await new Promise(resolve => setTimeout(resolve, retryDelay));
    }

    return null;
  }

  // Cleanup
  async disconnect(): Promise<void> {
    await this.client.quit();
    await this.subscriber.quit();
    await this.publisher.quit();
    this.isConnected = false;
  }

  // Health Check
  async ping(): Promise<boolean> {
    try {
      const result = await this.client.ping();
      return result === 'PONG';
    } catch {
      return false;
    }
  }

  // Bulk Operations
  async mget<T>(keys: string[]): Promise<(T | null)[]> {
    const values = await this.client.mget(...keys);
    return values.map(v => v ? JSON.parse(v) : null);
  }

  async mset(keyValuePairs: Record<string, any>): Promise<void> {
    const args: string[] = [];
    for (const [key, value] of Object.entries(keyValuePairs)) {
      args.push(key, JSON.stringify(value));
    }
    await this.client.mset(...args);
  }

  // Pattern Operations
  async keys(pattern: string): Promise<string[]> {
    return await this.client.keys(pattern);
  }

  async deleteByPattern(pattern: string): Promise<number> {
    const keys = await this.keys(pattern);
    if (keys.length > 0) {
      return await this.delete(keys);
    }
    return 0;
  }

  // Metrics
  async getInfo(): Promise<string> {
    return await this.client.info();
  }

  async getMemoryUsage(key?: string): Promise<number | null> {
    if (key) {
      return await this.client.memory('USAGE', key);
    }
    const info = await this.client.info('memory');
    const match = info.match(/used_memory:(\d+)/);
    return match ? parseInt(match[1]) : null;
  }

  // Getter for raw Redis client (for providers that need direct access)
  getClient(): Redis {
    return this.client;
  }
}

// Export singleton instance
let redisInstance: RedisService | null = null;

export function initializeRedis(config: RedisConfig): RedisService {
  if (!redisInstance) {
    redisInstance = new RedisService(config);
  }
  return redisInstance;
}

export function getRedis(): RedisService {
  if (!redisInstance) {
    throw new Error('Redis not initialized. Call initializeRedis first.');
  }
  return redisInstance;
}
