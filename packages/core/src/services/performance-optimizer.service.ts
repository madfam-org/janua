import { EventEmitter } from 'events';
import LRUCache from 'lru-cache';
import { Worker } from 'worker_threads';
import cluster from 'cluster';
import { promisify } from 'util';
import { gzip, gunzip } from 'zlib';

const gzipAsync = promisify(gzip);
const gunzipAsync = promisify(gunzip);

interface CacheConfig {
  maxSize: number;
  ttl: number;
  updateAgeOnGet?: boolean;
  updateAgeOnHas?: boolean;
}

interface QueryOptimization {
  query: string;
  optimized: string;
  indexesUsed: string[];
  estimatedCost: number;
  executionPlan: any;
}

interface PerformanceMetrics {
  timestamp: Date;
  cpu: {
    usage: number;
    load: number[];
  };
  memory: {
    used: number;
    available: number;
    percentage: number;
  };
  cache: {
    hits: number;
    misses: number;
    hitRate: number;
  };
  queries: {
    total: number;
    slow: number;
    optimized: number;
  };
  connections: {
    active: number;
    idle: number;
    total: number;
  };
}

interface OptimizationRule {
  id: string;
  name: string;
  condition: (metrics: PerformanceMetrics) => boolean;
  action: () => Promise<void>;
  priority: number;
  cooldown: number;
  lastExecuted?: Date;
}

export class PerformanceOptimizerService extends EventEmitter {
  private caches: Map<string, LRUCache<string, any>>;
  private queryCache: LRUCache<string, any>;
  private compressionCache: LRUCache<string, Buffer>;
  private workers: Worker[];
  private metrics!: PerformanceMetrics;
  private optimizationRules: OptimizationRule[];
  private monitoring: boolean;
  private dbConnectionPool: any;
  private queryOptimizer: any;

  constructor(private config: {
    enableCaching?: boolean;
    enableCompression?: boolean;
    enableWorkers?: boolean;
    enableClustering?: boolean;
    maxWorkers?: number;
    cacheConfigs?: Map<string, CacheConfig>;
    compressionLevel?: number;
    databaseUrl?: string;
    monitoringInterval?: number;
  }) {
    super();
    this.caches = new Map();
    this.workers = [];
    this.optimizationRules = [];
    this.monitoring = false;
    
    // Initialize query cache
    this.queryCache = new LRUCache<string, any>({
      max: 1000,
      ttl: 1000 * 60 * 5 // 5 minutes
    });
    
    // Initialize compression cache  
    this.compressionCache = new LRUCache<string, Buffer>({
      max: 500,
      ttl: 1000 * 60 * 60 // 1 hour
    });
    
    this.initialize();
  }

  private initialize(): void {
    // Initialize custom caches
    if (this.config.cacheConfigs) {
      for (const [name, config] of this.config.cacheConfigs) {
        this.caches.set(name, new LRUCache(config));
      }
    }

    // Default application cache
    this.caches.set('default', new LRUCache({
      max: 5000,
      ttl: 1000 * 60 * 15, // 15 minutes
    }));
  }

  // Cache Management
  async cache<T>(
    key: string,
    factory: () => Promise<T>,
    cacheName: string = 'default',
    ttl?: number
  ): Promise<T> {
    const cache = this.caches.get(cacheName);
    if (!cache) {
      throw new Error(`Cache ${cacheName} not found`);
    }

    const cached = cache.get(key);
    if (cached !== undefined) {
      this.metrics.cache.hits++;
      return cached;
    }

    this.metrics.cache.misses++;
    const value = await factory();
    
    if (ttl) {
      cache.set(key, value, { ttl });
    } else {
      cache.set(key, value);
    }

    return value;
  }

  invalidateCache(pattern?: string, cacheName?: string): void {
    if (cacheName) {
      const cache = this.caches.get(cacheName);
      if (cache) {
        if (pattern) {
          // Invalidate matching keys
          for (const key of cache.keys()) {
            if (key.includes(pattern)) {
              cache.delete(key);
            }
          }
        } else {
          cache.clear();
        }
      }
    } else {
      // Invalidate all caches
      for (const cache of this.caches.values()) {
        cache.clear();
      }
      this.queryCache.clear();
      this.compressionCache.clear();
    }
  }

  // Query Optimization
  async optimizeQuery(query: string, params?: any[]): Promise<QueryOptimization> {
    const cacheKey = `query:${query}:${JSON.stringify(params)}`;
    const cached = this.queryCache.get(cacheKey);
    if (cached) {
      return cached;
    }

    const optimization = await this.analyzeQuery(query);
    
    if (optimization.estimatedCost < 100) {
      this.queryCache.set(cacheKey, optimization);
    }

    this.metrics.queries.optimized++;
    return optimization;
  }

  private async analyzeQuery(query: string): Promise<QueryOptimization> {
    // Simulate query analysis (would connect to actual query planner)
    const optimizations: QueryOptimization = {
      query,
      optimized: query,
      indexesUsed: [],
      estimatedCost: 0,
      executionPlan: {},
    };

    // Check for missing indexes
    if (query.includes('WHERE') && !query.includes('INDEX')) {
      optimizations.optimized = query.replace('SELECT', 'SELECT /*+ INDEX */');
      optimizations.indexesUsed.push('suggested_index');
    }

    // Check for N+1 queries
    if (query.includes('IN (SELECT')) {
      optimizations.optimized = query.replace('IN (SELECT', 'JOIN (SELECT');
      optimizations.estimatedCost = 50;
    }

    return optimizations;
  }

  // Compression
  async compress(data: any): Promise<Buffer> {
    if (!this.config.enableCompression) {
      return Buffer.from(JSON.stringify(data));
    }

    const key = JSON.stringify(data).substring(0, 100);
    const cached = this.compressionCache.get(key);
    if (cached) {
      return cached;
    }

    const compressed = await gzipAsync(JSON.stringify(data));
    this.compressionCache.set(key, compressed);
    return compressed;
  }

  async decompress(data: Buffer): Promise<any> {
    if (!this.config.enableCompression) {
      return JSON.parse(data.toString());
    }

    const decompressed = await gunzipAsync(data);
    return JSON.parse(decompressed.toString());
  }

  // Worker Management
  async executeInWorker<T>(task: any): Promise<T> {
    if (!this.config.enableWorkers || this.workers.length === 0) {
      throw new Error('Workers not enabled or initialized');
    }

    const worker = this.getLeastBusyWorker();
    return new Promise((resolve, reject) => {
      const id = Math.random().toString(36).substring(7);
      
      const handler = (msg: any) => {
        if (msg.id === id) {
          worker.off('message', handler);
          if (msg.error) {
            reject(new Error(msg.error));
          } else {
            resolve(msg.result);
          }
        }
      };

      worker.on('message', handler);
      worker.postMessage({ id, task });

      // Timeout after 30 seconds
      setTimeout(() => {
        worker.off('message', handler);
        reject(new Error('Worker timeout'));
      }, 30000);
    });
  }

  private getLeastBusyWorker(): Worker {
    // Simple round-robin for now
    const worker = this.workers.shift()!;
    this.workers.push(worker);
    return worker;
  }

  private handleWorkerMessage(msg: any): void {
    this.emit('worker:message', msg);
  }

  private handleWorkerError(err: Error): void {
    this.emit('worker:error', err);
  }

  // Auto-optimization
  private startAutoOptimization(): void {
    this.monitoring = true;
    
    setInterval(() => {
      this.updateMetrics();
      this.applyOptimizationRules();
    }, this.config.monitoringInterval || 60000); // 1 minute default
  }

  private async updateMetrics(): Promise<void> {
    const memUsage = process.memoryUsage();
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const totalMem = require('os').totalmem();
    
    this.metrics = {
      timestamp: new Date(),
      cpu: {
        usage: process.cpuUsage().user / 1000000,
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        load: require('os').loadavg(),
      },
      memory: {
        used: memUsage.heapUsed,
        available: totalMem - memUsage.rss,
        percentage: (memUsage.rss / totalMem) * 100,
      },
      cache: {
        hits: this.metrics.cache.hits,
        misses: this.metrics.cache.misses,
        hitRate: this.metrics.cache.hits / (this.metrics.cache.hits + this.metrics.cache.misses || 1),
      },
      queries: this.metrics.queries,
      connections: await this.getConnectionMetrics(),
    };

    this.emit('metrics:updated', this.metrics);
  }

  private async getConnectionMetrics(): Promise<any> {
    // Would connect to actual database pool
    return {
      active: 5,
      idle: 10,
      total: 15,
    };
  }

  private async applyOptimizationRules(): Promise<void> {
    const sortedRules = [...this.optimizationRules].sort((a, b) => a.priority - b.priority);
    
    for (const rule of sortedRules) {
      if (this.shouldApplyRule(rule)) {
        try {
          await rule.action();
          rule.lastExecuted = new Date();
          this.emit('optimization:applied', rule);
        } catch (error) {
          this.emit('optimization:error', { rule, error });
        }
      }
    }
  }

  private shouldApplyRule(rule: OptimizationRule): boolean {
    if (!rule.condition(this.metrics)) {
      return false;
    }

    if (rule.lastExecuted) {
      const timeSinceLastExecution = Date.now() - rule.lastExecuted.getTime();
      if (timeSinceLastExecution < rule.cooldown) {
        return false;
      }
    }

    return true;
  }

  // Optimization Actions
  private async warmupCache(): Promise<void> {
    // Load frequently accessed data into cache
    const frequentQueries = [
      'SELECT * FROM users WHERE active = true LIMIT 100',
      'SELECT * FROM organizations LIMIT 50',
      'SELECT * FROM sessions WHERE expires_at > NOW() LIMIT 200',
    ];

    for (const query of frequentQueries) {
      const result = await this.simulateQuery(query);
      this.queryCache.set(query, result);
    }
  }

  private async optimizeSlowQueries(): Promise<void> {
    // Analyze and optimize slow queries
    const slowQueries = await this.getSlowQueries();
    
    for (const query of slowQueries) {
      const optimization = await this.optimizeQuery(query);
      if (optimization.estimatedCost < 100) {
        // Apply optimization
        this.emit('query:optimized', optimization);
      }
    }
  }

  private async adjustConnectionPool(): Promise<void> {
    // Adjust database connection pool size
    const metrics = await this.getConnectionMetrics();
    
    if (metrics.idle < 2) {
      // Increase pool size
      this.emit('pool:resize', { action: 'increase', size: 5 });
    } else if (metrics.idle > 20) {
      // Decrease pool size
      this.emit('pool:resize', { action: 'decrease', size: 5 });
    }
  }

  private async cleanupMemory(): Promise<void> {
    // Clear caches and run garbage collection
    for (const cache of this.caches.values()) {
      cache.clear();
    }
    
    this.queryCache.clear();
    this.compressionCache.clear();
    
    if (global.gc) {
      global.gc();
    }
    
    this.emit('memory:cleaned');
  }

  private async getSlowQueries(): Promise<string[]> {
    // Would fetch from actual monitoring system
    return [
      'SELECT * FROM large_table WHERE unindexed_column = ?',
      'SELECT * FROM users u JOIN orders o ON u.id = o.user_id WHERE o.status = ?',
    ];
  }

  private async simulateQuery(query: string): Promise<any> {
    // Simulate database query
    return { data: [], executionTime: Math.random() * 100 };
  }

  // Clustering Support
  setupClustering(): void {
    if (!this.config.enableClustering) return;

    if (cluster.isPrimary) {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const numCPUs = require('os').cpus().length;
      
      for (let i = 0; i < numCPUs; i++) {
        cluster.fork();
      }

      cluster.on('exit', (worker: any, code: any, signal: any) => {
        cluster.fork(); // Restart worker
      });

      // Master process metrics aggregation
      this.aggregateClusterMetrics();
    }
  }

  private aggregateClusterMetrics(): void {
    const clusterMetrics: Map<number, PerformanceMetrics> = new Map();
    
    for (const id in (cluster as any).workers) {
      const worker = (cluster as any).workers[id];
      if (worker) {
        worker.on('message', (msg: any) => {
          if (msg.type === 'metrics') {
            clusterMetrics.set(worker.process.pid!, msg.data);
            this.emit('cluster:metrics', Array.from(clusterMetrics.values()));
          }
        });
      }
    }
  }

  // Profiling
  async profile<T>(
    name: string,
    fn: () => Promise<T>
  ): Promise<{ result: T; profile: any }> {
    const start = process.hrtime.bigint();
    const startMemory = process.memoryUsage();
    
    const result = await fn();
    
    const end = process.hrtime.bigint();
    const endMemory = process.memoryUsage();
    
    const profile = {
      name,
      duration: Number(end - start) / 1000000, // Convert to milliseconds
      memory: {
        heapUsed: endMemory.heapUsed - startMemory.heapUsed,
        external: endMemory.external - startMemory.external,
      },
      timestamp: new Date(),
    };

    this.emit('profile:complete', profile);
    return { result, profile };
  }

  // Batch Processing
  async processBatch<T, R>(
    items: T[],
    processor: (item: T) => Promise<R>,
    options: {
      batchSize?: number;
      concurrency?: number;
      onProgress?: (processed: number, total: number) => void;
    } = {}
  ): Promise<R[]> {
    const batchSize = options.batchSize || 100;
    const concurrency = options.concurrency || 5;
    const results: R[] = [];
    
    for (let i = 0; i < items.length; i += batchSize) {
      const batch = items.slice(i, i + batchSize);
      const promises: Promise<R>[] = [];
      
      for (let j = 0; j < batch.length; j += concurrency) {
        const concurrent = batch.slice(j, j + concurrency);
        promises.push(...concurrent.map(processor));
      }
      
      const batchResults = await Promise.all(promises);
      results.push(...batchResults);
      
      if (options.onProgress) {
        options.onProgress(results.length, items.length);
      }
    }
    
    return results;
  }

  // Resource Monitoring
  getResourceUsage(): PerformanceMetrics {
    return this.metrics;
  }

  getOptimizationHistory(): any[] {
    // Would fetch from storage
    return [];
  }

  // Cleanup
  async shutdown(): Promise<void> {
    this.monitoring = false;
    
    // Terminate workers
    for (const worker of this.workers) {
      await worker.terminate();
    }
    
    // Clear all caches
    this.invalidateCache();
    
    // Remove all listeners
    this.removeAllListeners();
  }
}

// Factory function
export function createPerformanceOptimizer(config?: any): PerformanceOptimizerService {
  return new PerformanceOptimizerService(config);
}

// Export types
export type {
  CacheConfig,
  QueryOptimization,
  PerformanceMetrics,
  OptimizationRule,
};