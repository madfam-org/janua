/**
 * API Rate Limiting and Throttling Service
 * Manages request rate limits, throttling, and API quota enforcement
 */

import { EventEmitter } from 'events';
import crypto from 'crypto';

export interface RateLimitConfig {
  id: string;
  name: string;
  description?: string;
  window_ms: number;          // Time window in milliseconds
  max_requests: number;        // Max requests per window
  max_burst?: number;          // Max burst size for token bucket
  min_interval_ms?: number;    // Min interval between requests
  strategy: 'sliding-window' | 'fixed-window' | 'token-bucket' | 'leaky-bucket';
  scope: 'global' | 'user' | 'organization' | 'ip' | 'api-key';
  tier?: 'free' | 'pro' | 'enterprise' | 'custom';
  enabled: boolean;
  skip_conditions?: SkipCondition[];
  headers_enabled: boolean;    // Include rate limit headers in response
  distributed?: boolean;        // Enable distributed rate limiting
}

export interface SkipCondition {
  type: 'ip' | 'user' | 'organization' | 'api-key' | 'path' | 'header';
  operator: 'equals' | 'contains' | 'matches' | 'in';
  value: string | string[] | RegExp;
}

export interface RateLimitRequest {
  id: string;
  key: string;                // Unique identifier (user_id, ip, etc.)
  path: string;
  method: string;
  ip_address: string;
  user_id?: string;
  organization_id?: string;
  api_key_id?: string;
  headers: Record<string, string>;
  timestamp: Date;
}

export interface RateLimitResult {
  allowed: boolean;
  limit: number;
  remaining: number;
  reset_at: Date;
  retry_after?: number;        // Seconds until next allowed request
  bucket_state?: BucketState;
  reason?: string;
}

export interface BucketState {
  tokens: number;
  last_refill: Date;
  next_refill: Date;
}

export interface ThrottleConfig {
  id: string;
  name: string;
  target_rps: number;          // Target requests per second
  burst_size: number;          // Max burst above target
  queue_size: number;          // Max queued requests
  queue_timeout_ms: number;    // Max time in queue
  priority_levels: number;     // Number of priority levels
  adaptive: boolean;           // Enable adaptive throttling
  backpressure_threshold: number; // Queue size to trigger backpressure
}

export interface ThrottleRequest extends RateLimitRequest {
  priority: number;            // 0 = highest priority
  weight?: number;             // Request weight/cost
  timeout_ms?: number;         // Custom timeout
}

export interface ThrottleResult {
  accepted: boolean;
  queued: boolean;
  queue_position?: number;
  estimated_wait_ms?: number;
  rejected_reason?: 'rate_limit' | 'queue_full' | 'timeout' | 'backpressure';
}

export interface UsageMetrics {
  window_start: Date;
  window_end: Date;
  total_requests: number;
  allowed_requests: number;
  blocked_requests: number;
  throttled_requests: number;
  average_rps: number;
  peak_rps: number;
  p95_response_time_ms: number;
  p99_response_time_ms: number;
  unique_users: number;
  unique_ips: number;
  top_users: Array<{ user_id: string; requests: number }>;
  top_paths: Array<{ path: string; requests: number }>;
  violations: RateLimitViolation[];
}

export interface RateLimitViolation {
  id: string;
  timestamp: Date;
  key: string;
  limit_config_id: string;
  requests_made: number;
  limit_exceeded_by: number;
  action_taken: 'blocked' | 'throttled' | 'warned';
  metadata?: Record<string, any>;
}

class TokenBucket {
  private tokens: number;
  private lastRefill: Date;

  constructor(
    private readonly capacity: number,
    private readonly refillRate: number, // tokens per second
    private readonly refillInterval: number = 1000 // ms
  ) {
    this.tokens = capacity;
    this.lastRefill = new Date();
  }

  consume(tokens: number = 1): boolean {
    this.refill();
    
    if (this.tokens >= tokens) {
      this.tokens -= tokens;
      return true;
    }
    
    return false;
  }

  private refill(): void {
    const now = new Date();
    const elapsed = now.getTime() - this.lastRefill.getTime();
    const tokensToAdd = (elapsed / 1000) * this.refillRate;
    
    this.tokens = Math.min(this.capacity, this.tokens + tokensToAdd);
    this.lastRefill = now;
  }

  getState(): BucketState {
    this.refill();
    return {
      tokens: this.tokens,
      last_refill: this.lastRefill,
      next_refill: new Date(this.lastRefill.getTime() + this.refillInterval)
    };
  }
}

class SlidingWindow {
  private requests: Date[] = [];

  constructor(
    private readonly windowMs: number,
    private readonly maxRequests: number
  ) {}

  addRequest(): boolean {
    const now = new Date();
    const windowStart = new Date(now.getTime() - this.windowMs);
    
    // Remove old requests outside the window
    this.requests = this.requests.filter(r => r > windowStart);
    
    if (this.requests.length < this.maxRequests) {
      this.requests.push(now);
      return true;
    }
    
    return false;
  }

  getRemaining(): number {
    const now = new Date();
    const windowStart = new Date(now.getTime() - this.windowMs);
    
    this.requests = this.requests.filter(r => r > windowStart);
    return Math.max(0, this.maxRequests - this.requests.length);
  }

  getResetTime(): Date {
    if (this.requests.length === 0) {
      return new Date();
    }
    
    return new Date(this.requests[0].getTime() + this.windowMs);
  }
}

class ThrottleQueue {
  private queue: Array<{
    request: ThrottleRequest;
    callback: (result: ThrottleResult) => void;
    timestamp: Date;
  }> = [];

  constructor(
    private readonly maxSize: number,
    private readonly timeoutMs: number
  ) {}

  enqueue(
    request: ThrottleRequest,
    callback: (result: ThrottleResult) => void
  ): boolean {
    if (this.queue.length >= this.maxSize) {
      return false;
    }

    // Insert based on priority
    const entry = {
      request,
      callback,
      timestamp: new Date()
    };

    const insertIndex = this.queue.findIndex(
      e => e.request.priority > request.priority
    );

    if (insertIndex === -1) {
      this.queue.push(entry);
    } else {
      this.queue.splice(insertIndex, 0, entry);
    }

    return true;
  }

  dequeue(): typeof this.queue[0] | null {
    // Remove timed out entries
    const now = new Date();
    this.queue = this.queue.filter(e => {
      const elapsed = now.getTime() - e.timestamp.getTime();
      if (elapsed > this.timeoutMs) {
        e.callback({
          accepted: false,
          queued: false,
          rejected_reason: 'timeout'
        });
        return false;
      }
      return true;
    });

    return this.queue.shift() || null;
  }

  size(): number {
    return this.queue.length;
  }

  getPosition(requestId: string): number {
    return this.queue.findIndex(e => e.request.id === requestId);
  }
}

export class RateLimiterService extends EventEmitter {
  private configs: Map<string, RateLimitConfig> = new Map();
  private buckets: Map<string, TokenBucket> = new Map();
  private windows: Map<string, SlidingWindow> = new Map();
  private throttleConfigs: Map<string, ThrottleConfig> = new Map();
  private throttleQueues: Map<string, ThrottleQueue> = new Map();
  private metrics: Map<string, UsageMetrics> = new Map();
  private violations: RateLimitViolation[] = [];

  constructor(
    private readonly config: {
      redis_client?: any;           // Redis client for distributed limiting
      default_strategy?: RateLimitConfig['strategy'];
      default_window_ms?: number;
      default_max_requests?: number;
      enable_metrics?: boolean;
      metrics_retention_days?: number;
      violation_threshold?: number;  // Number of violations before escalation
      auto_block_duration_ms?: number;
    } = {}
  ) {
    super();
    this.initializeDefaultConfigs();
    this.startMetricsAggregation();
  }

  /**
   * Check rate limit
   */
  async checkRateLimit(
    request: RateLimitRequest,
    configId?: string
  ): Promise<RateLimitResult> {
    // Get applicable config
    const config = configId 
      ? this.configs.get(configId)
      : this.getApplicableConfig(request);

    if (!config || !config.enabled) {
      return {
        allowed: true,
        limit: Infinity,
        remaining: Infinity,
        reset_at: new Date()
      };
    }

    // Check skip conditions
    if (this.shouldSkip(request, config)) {
      return {
        allowed: true,
        limit: config.max_requests,
        remaining: config.max_requests,
        reset_at: new Date()
      };
    }

    // Get rate limit key
    const key = this.getRateLimitKey(request, config);

    // Apply rate limiting based on strategy
    let result: RateLimitResult;
    
    switch (config.strategy) {
      case 'token-bucket':
        result = await this.checkTokenBucket(key, config);
        break;
      case 'sliding-window':
        result = await this.checkSlidingWindow(key, config);
        break;
      case 'fixed-window':
        result = await this.checkFixedWindow(key, config);
        break;
      case 'leaky-bucket':
        result = await this.checkLeakyBucket(key, config);
        break;
      default:
        result = await this.checkSlidingWindow(key, config);
    }

    // Record metrics
    if (this.config.enable_metrics) {
      this.recordMetrics(request, result, config);
    }

    // Handle violations
    if (!result.allowed) {
      this.handleViolation(request, config, result);
    }

    return result;
  }

  /**
   * Apply throttling
   */
  async throttle(
    request: ThrottleRequest,
    configId: string
  ): Promise<ThrottleResult> {
    const config = this.throttleConfigs.get(configId);
    
    if (!config) {
      return { accepted: true, queued: false };
    }

    // Check if request can be processed immediately
    const rateLimitResult = await this.checkRateLimit(request);
    
    if (!rateLimitResult.allowed) {
      // Try to queue the request
      const queue = this.getThrottleQueue(configId);
      
      if (queue.size() >= config.queue_size) {
        return {
          accepted: false,
          queued: false,
          rejected_reason: 'queue_full'
        };
      }

      // Check backpressure
      if (queue.size() >= config.backpressure_threshold) {
        this.emit('throttle:backpressure', {
          config_id: configId,
          queue_size: queue.size(),
          threshold: config.backpressure_threshold
        });

        if (request.priority > 0) { // Only high priority allowed during backpressure
          return {
            accepted: false,
            queued: false,
            rejected_reason: 'backpressure'
          };
        }
      }

      // Queue the request
      const queued = queue.enqueue(request, (result) => {
        this.emit('throttle:processed', { request_id: request.id, result });
      });

      if (queued) {
        return {
          accepted: false,
          queued: true,
          queue_position: queue.getPosition(request.id),
          estimated_wait_ms: this.estimateWaitTime(configId, queue.getPosition(request.id))
        };
      } else {
        return {
          accepted: false,
          queued: false,
          rejected_reason: 'queue_full'
        };
      }
    }

    return { accepted: true, queued: false };
  }

  /**
   * Process throttle queue
   */
  async processThrottleQueue(configId: string): Promise<number> {
    const config = this.throttleConfigs.get(configId);
    const queue = this.throttleQueues.get(configId);
    
    if (!config || !queue) return 0;

    let processed = 0;
    const targetRps = config.target_rps;
    const interval = 1000 / targetRps;

    while (queue.size() > 0 && processed < config.burst_size) {
      const entry = queue.dequeue();
      if (!entry) break;

      const rateLimitResult = await this.checkRateLimit(entry.request);
      
      if (rateLimitResult.allowed) {
        entry.callback({ accepted: true, queued: false });
        processed++;
        
        // Delay to maintain target RPS
        if (config.adaptive) {
          const adaptiveDelay = this.calculateAdaptiveDelay(configId);
          await this.delay(adaptiveDelay);
        } else {
          await this.delay(interval);
        }
      } else {
        // Requeue if still within timeout
        const elapsed = Date.now() - entry.timestamp.getTime();
        if (elapsed < config.queue_timeout_ms) {
          queue.enqueue(entry.request, entry.callback);
        } else {
          entry.callback({
            accepted: false,
            queued: false,
            rejected_reason: 'timeout'
          });
        }
      }
    }

    return processed;
  }

  /**
   * Create or update rate limit config
   */
  createRateLimitConfig(config: RateLimitConfig): void {
    this.configs.set(config.id, config);
    
    this.emit('config:created', { config_id: config.id });
  }

  /**
   * Create throttle config
   */
  createThrottleConfig(config: ThrottleConfig): void {
    this.throttleConfigs.set(config.id, config);
    this.throttleQueues.set(config.id, new ThrottleQueue(config.queue_size, config.queue_timeout_ms));
    
    this.emit('throttle-config:created', { config_id: config.id });
  }

  /**
   * Get usage metrics
   */
  getUsageMetrics(
    key?: string,
    since?: Date
  ): UsageMetrics | UsageMetrics[] {
    if (key) {
      return this.metrics.get(key) || this.createEmptyMetrics();
    }

    const allMetrics = Array.from(this.metrics.values());
    
    if (since) {
      return allMetrics.filter(m => m.window_start >= since);
    }

    return allMetrics;
  }

  /**
   * Get violations
   */
  getViolations(
    filters?: {
      key?: string;
      since?: Date;
      limit_config_id?: string;
    }
  ): RateLimitViolation[] {
    let violations = [...this.violations];

    if (filters) {
      if (filters.key) {
        violations = violations.filter(v => v.key === filters.key);
      }
      if (filters.since) {
        violations = violations.filter(v => v.timestamp >= filters.since!);
      }
      if (filters.limit_config_id) {
        violations = violations.filter(v => v.limit_config_id === filters.limit_config_id);
      }
    }

    return violations.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
  }

  /**
   * Reset rate limit for a key
   */
  resetRateLimit(key: string): void {
    this.buckets.delete(key);
    this.windows.delete(key);
    
    this.emit('rate-limit:reset', { key });
  }

  /**
   * Block a key temporarily
   */
  blockKey(
    key: string,
    duration_ms: number,
    reason: string
  ): void {
    // In production, store in Redis or database
    const unblockAt = new Date(Date.now() + duration_ms);
    
    this.emit('key:blocked', { key, unblock_at: unblockAt, reason });
  }

  /**
   * Private: Check token bucket
   */
  private async checkTokenBucket(
    key: string,
    config: RateLimitConfig
  ): Promise<RateLimitResult> {
    let bucket = this.buckets.get(key);
    
    if (!bucket) {
      bucket = new TokenBucket(
        config.max_burst || config.max_requests,
        config.max_requests / (config.window_ms / 1000)
      );
      this.buckets.set(key, bucket);
    }

    const allowed = bucket.consume();
    const state = bucket.getState();

    return {
      allowed,
      limit: config.max_requests,
      remaining: Math.floor(state.tokens),
      reset_at: state.next_refill,
      bucket_state: state,
      retry_after: allowed ? undefined : Math.ceil((1 - state.tokens) / (config.max_requests / (config.window_ms / 1000)))
    };
  }

  /**
   * Private: Check sliding window
   */
  private async checkSlidingWindow(
    key: string,
    config: RateLimitConfig
  ): Promise<RateLimitResult> {
    let window = this.windows.get(key);
    
    if (!window) {
      window = new SlidingWindow(config.window_ms, config.max_requests);
      this.windows.set(key, window);
    }

    const allowed = window.addRequest();
    const remaining = window.getRemaining();
    const resetAt = window.getResetTime();

    return {
      allowed,
      limit: config.max_requests,
      remaining,
      reset_at: resetAt,
      retry_after: allowed ? undefined : Math.ceil((resetAt.getTime() - Date.now()) / 1000)
    };
  }

  /**
   * Private: Check fixed window
   */
  private async checkFixedWindow(
    key: string,
    config: RateLimitConfig
  ): Promise<RateLimitResult> {
    // Simplified fixed window implementation
    // In production, use Redis with EXPIRE
    const windowKey = `${key}:${Math.floor(Date.now() / config.window_ms)}`;
    let count = this.getWindowCount(windowKey);
    
    if (count < config.max_requests) {
      this.incrementWindowCount(windowKey);
      count++;
      
      return {
        allowed: true,
        limit: config.max_requests,
        remaining: config.max_requests - count,
        reset_at: new Date(Math.ceil(Date.now() / config.window_ms) * config.window_ms)
      };
    }

    return {
      allowed: false,
      limit: config.max_requests,
      remaining: 0,
      reset_at: new Date(Math.ceil(Date.now() / config.window_ms) * config.window_ms),
      retry_after: Math.ceil((Math.ceil(Date.now() / config.window_ms) * config.window_ms - Date.now()) / 1000)
    };
  }

  /**
   * Private: Check leaky bucket
   */
  private async checkLeakyBucket(
    key: string,
    config: RateLimitConfig
  ): Promise<RateLimitResult> {
    // Simplified leaky bucket - similar to token bucket but with constant drain
    return this.checkTokenBucket(key, config);
  }

  /**
   * Private: Get applicable config
   */
  private getApplicableConfig(request: RateLimitRequest): RateLimitConfig | null {
    // Priority order: api-key > user > organization > ip > global
    for (const config of this.configs.values()) {
      if (!config.enabled) continue;

      if (config.scope === 'api-key' && request.api_key_id) {
        return config;
      }
      if (config.scope === 'user' && request.user_id) {
        return config;
      }
      if (config.scope === 'organization' && request.organization_id) {
        return config;
      }
      if (config.scope === 'ip') {
        return config;
      }
      if (config.scope === 'global') {
        return config;
      }
    }

    return null;
  }

  /**
   * Private: Get rate limit key
   */
  private getRateLimitKey(request: RateLimitRequest, config: RateLimitConfig): string {
    switch (config.scope) {
      case 'user':
        return `user:${request.user_id}`;
      case 'organization':
        return `org:${request.organization_id}`;
      case 'ip':
        return `ip:${request.ip_address}`;
      case 'api-key':
        return `key:${request.api_key_id}`;
      case 'global':
        return 'global';
      default:
        return `unknown:${request.id}`;
    }
  }

  /**
   * Private: Should skip rate limiting
   */
  private shouldSkip(request: RateLimitRequest, config: RateLimitConfig): boolean {
    if (!config.skip_conditions) return false;

    for (const condition of config.skip_conditions) {
      let value: string | undefined;

      switch (condition.type) {
        case 'ip':
          value = request.ip_address;
          break;
        case 'user':
          value = request.user_id;
          break;
        case 'organization':
          value = request.organization_id;
          break;
        case 'api-key':
          value = request.api_key_id;
          break;
        case 'path':
          value = request.path;
          break;
        case 'header':
          // Assuming condition.value contains header name
          value = request.headers[condition.value as string];
          break;
      }

      if (!value) continue;

      switch (condition.operator) {
        case 'equals':
          if (value === condition.value) return true;
          break;
        case 'contains':
          if (value.includes(condition.value as string)) return true;
          break;
        case 'matches':
          if ((condition.value as RegExp).test(value)) return true;
          break;
        case 'in':
          if ((condition.value as string[]).includes(value)) return true;
          break;
      }
    }

    return false;
  }

  /**
   * Private: Handle violation
   */
  private handleViolation(
    request: RateLimitRequest,
    config: RateLimitConfig,
    result: RateLimitResult
  ): void {
    const violation: RateLimitViolation = {
      id: crypto.randomUUID(),
      timestamp: new Date(),
      key: this.getRateLimitKey(request, config),
      limit_config_id: config.id,
      requests_made: config.max_requests + 1,
      limit_exceeded_by: 1,
      action_taken: 'blocked'
    };

    this.violations.push(violation);

    // Check for repeated violations
    const recentViolations = this.violations.filter(
      v => v.key === violation.key &&
           v.timestamp.getTime() > Date.now() - 3600000 // Last hour
    );

    if (recentViolations.length >= (this.config.violation_threshold || 10)) {
      // Auto-block for repeated violations
      if (this.config.auto_block_duration_ms) {
        this.blockKey(
          violation.key,
          this.config.auto_block_duration_ms,
          'Repeated rate limit violations'
        );
      }

      this.emit('violation:escalated', {
        key: violation.key,
        violations: recentViolations.length
      });
    }

    this.emit('violation:recorded', violation);
  }

  /**
   * Private: Initialize default configs
   */
  private initializeDefaultConfigs(): void {
    const defaultConfigs: RateLimitConfig[] = [
      {
        id: 'global',
        name: 'Global Rate Limit',
        window_ms: 60000, // 1 minute
        max_requests: 1000,
        strategy: 'sliding-window',
        scope: 'global',
        enabled: true,
        headers_enabled: true
      },
      {
        id: 'per-user',
        name: 'Per User Rate Limit',
        window_ms: 60000,
        max_requests: 100,
        strategy: 'token-bucket',
        max_burst: 20,
        scope: 'user',
        enabled: true,
        headers_enabled: true
      },
      {
        id: 'per-ip',
        name: 'Per IP Rate Limit',
        window_ms: 60000,
        max_requests: 60,
        strategy: 'sliding-window',
        scope: 'ip',
        enabled: true,
        headers_enabled: true,
        skip_conditions: [
          { type: 'ip', operator: 'in', value: ['127.0.0.1', '::1'] } // Skip localhost
        ]
      }
    ];

    for (const config of defaultConfigs) {
      this.configs.set(config.id, config);
    }
  }

  /**
   * Private: Helper functions
   */
  private windowCounts: Map<string, number> = new Map();

  private getWindowCount(key: string): number {
    return this.windowCounts.get(key) || 0;
  }

  private incrementWindowCount(key: string): void {
    this.windowCounts.set(key, this.getWindowCount(key) + 1);
  }

  private getThrottleQueue(configId: string): ThrottleQueue {
    let queue = this.throttleQueues.get(configId);
    if (!queue) {
      const config = this.throttleConfigs.get(configId);
      if (config) {
        queue = new ThrottleQueue(config.queue_size, config.queue_timeout_ms);
        this.throttleQueues.set(configId, queue);
      }
    }
    return queue!;
  }

  private estimateWaitTime(configId: string, position: number): number {
    const config = this.throttleConfigs.get(configId);
    if (!config) return 0;

    const processingRate = config.target_rps;
    return Math.ceil((position / processingRate) * 1000);
  }

  private calculateAdaptiveDelay(configId: string): number {
    // Implement adaptive delay based on system load
    // For now, return fixed interval
    const config = this.throttleConfigs.get(configId);
    if (!config) return 0;

    return 1000 / config.target_rps;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private createEmptyMetrics(): UsageMetrics {
    return {
      window_start: new Date(),
      window_end: new Date(),
      total_requests: 0,
      allowed_requests: 0,
      blocked_requests: 0,
      throttled_requests: 0,
      average_rps: 0,
      peak_rps: 0,
      p95_response_time_ms: 0,
      p99_response_time_ms: 0,
      unique_users: 0,
      unique_ips: 0,
      top_users: [],
      top_paths: [],
      violations: []
    };
  }

  private recordMetrics(
    request: RateLimitRequest,
    result: RateLimitResult,
    config: RateLimitConfig
  ): void {
    // Simplified metrics recording
    // In production, aggregate properly
    const key = this.getRateLimitKey(request, config);
    let metrics = this.metrics.get(key);
    
    if (!metrics) {
      metrics = this.createEmptyMetrics();
      this.metrics.set(key, metrics);
    }

    metrics.total_requests++;
    if (result.allowed) {
      metrics.allowed_requests++;
    } else {
      metrics.blocked_requests++;
    }
  }

  private startMetricsAggregation(): void {
    // Clean up old metrics periodically
    setInterval(() => {
      const retentionMs = (this.config.metrics_retention_days || 7) * 86400000;
      const cutoff = new Date(Date.now() - retentionMs);

      // Clean violations
      this.violations = this.violations.filter(v => v.timestamp > cutoff);

      // Clean metrics
      for (const [key, metrics] of this.metrics) {
        if (metrics.window_end < cutoff) {
          this.metrics.delete(key);
        }
      }
    }, 3600000); // Every hour
  }
}

// Export factory function
export function createRateLimiterService(config?: any): RateLimiterService {
  return new RateLimiterService(config);
}