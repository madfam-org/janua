/**
 * Query Cache Service
 * Handles caching of analytics query results
 * Extracted from AnalyticsReportingService
 */

import crypto from 'crypto';
import { EventEmitter } from 'events';
import {
  AnalyticsQuery,
  QueryResult
} from '../core/types';

interface CacheEntry {
  result: QueryResult;
  expires: Date;
  createdAt: Date;
  hits: number;
}

export class QueryCacheService extends EventEmitter {
  private cache: Map<string, CacheEntry> = new Map();
  private cleanupTimer?: NodeJS.Timeout;

  constructor(
    private readonly config: {
      ttlSeconds?: number;
      maxEntries?: number;
      cleanupInterval?: number;
    } = {}
  ) {
    super();

    // Start cleanup timer
    const cleanupInterval = this.config.cleanupInterval || 60000; // 1 minute
    this.cleanupTimer = setInterval(() => {
      this.cleanupExpired();
    }, cleanupInterval);
  }

  /**
   * Get cached query result
   */
  get(query: AnalyticsQuery): QueryResult | null {
    const key = this.getCacheKey(query);
    const entry = this.cache.get(key);

    if (!entry) {
      this.emit('cache:miss', { query, key });
      return null;
    }

    if (entry.expires < new Date()) {
      // Expired
      this.cache.delete(key);
      this.emit('cache:expired', { query, key });
      return null;
    }

    // Hit - update stats
    entry.hits++;
    this.emit('cache:hit', { query, key, hits: entry.hits });

    return {
      ...entry.result,
      metadata: {
        ...entry.result.metadata,
        cache_hit: true
      }
    };
  }

  /**
   * Store query result in cache
   */
  set(query: AnalyticsQuery, result: QueryResult): void {
    const key = this.getCacheKey(query);
    const ttl = this.config.ttlSeconds || 300; // Default 5 minutes

    const entry: CacheEntry = {
      result,
      expires: new Date(Date.now() + ttl * 1000),
      createdAt: new Date(),
      hits: 0
    };

    // Check max entries
    if (this.config.maxEntries && this.cache.size >= this.config.maxEntries) {
      this.evictLRU();
    }

    this.cache.set(key, entry);
    this.emit('cache:set', { query, key, ttl });
  }

  /**
   * Invalidate cache entries
   */
  invalidate(pattern?: string): number {
    let invalidatedCount = 0;

    if (!pattern) {
      // Clear all
      invalidatedCount = this.cache.size;
      this.cache.clear();
      this.emit('cache:cleared', { count: invalidatedCount });
      return invalidatedCount;
    }

    // Invalidate matching keys
    const regex = new RegExp(pattern);
    for (const [key, _entry] of this.cache.entries()) {
      if (regex.test(key)) {
        this.cache.delete(key);
        invalidatedCount++;
      }
    }

    if (invalidatedCount > 0) {
      this.emit('cache:invalidated', { pattern, count: invalidatedCount });
    }

    return invalidatedCount;
  }

  /**
   * Get cache statistics
   */
  getStats(): {
    size: number;
    maxSize: number;
    hitRate: number;
    entries: Array<{
      key: string;
      hits: number;
      age: number;
      ttl: number;
    }>;
  } {
    const now = new Date();
    let totalHits = 0;
    let totalRequests = 0;

    const entries = Array.from(this.cache.entries()).map(([key, entry]) => {
      totalHits += entry.hits;
      totalRequests += entry.hits + 1; // +1 for initial miss

      return {
        key,
        hits: entry.hits,
        age: now.getTime() - entry.createdAt.getTime(),
        ttl: entry.expires.getTime() - now.getTime()
      };
    });

    return {
      size: this.cache.size,
      maxSize: this.config.maxEntries || Infinity,
      hitRate: totalRequests > 0 ? totalHits / totalRequests : 0,
      entries: entries.sort((a, b) => b.hits - a.hits) // Sort by hits descending
    };
  }

  /**
   * Private: Generate cache key from query
   */
  private getCacheKey(query: AnalyticsQuery): string {
    return crypto
      .createHash('md5')
      .update(JSON.stringify(query))
      .digest('hex');
  }

  /**
   * Private: Cleanup expired entries
   */
  private cleanupExpired(): void {
    const now = new Date();
    let expiredCount = 0;

    for (const [key, entry] of this.cache.entries()) {
      if (entry.expires < now) {
        this.cache.delete(key);
        expiredCount++;
      }
    }

    if (expiredCount > 0) {
      this.emit('cache:cleanup', { expired: expiredCount });
    }
  }

  /**
   * Private: Evict least recently used entry
   */
  private evictLRU(): void {
    let lruKey: string | null = null;
    let lruHits = Infinity;
    let lruAge = 0;

    const now = new Date();

    for (const [key, entry] of this.cache.entries()) {
      const age = now.getTime() - entry.createdAt.getTime();

      // Find entry with lowest hits and oldest age
      if (entry.hits < lruHits || (entry.hits === lruHits && age > lruAge)) {
        lruKey = key;
        lruHits = entry.hits;
        lruAge = age;
      }
    }

    if (lruKey) {
      this.cache.delete(lruKey);
      this.emit('cache:evicted', { key: lruKey, hits: lruHits });
    }
  }

  /**
   * Cleanup
   */
  destroy(): void {
    if (this.cleanupTimer) {
      clearInterval(this.cleanupTimer);
    }
    this.cache.clear();
    this.removeAllListeners();
  }
}
