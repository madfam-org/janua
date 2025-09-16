import { EventEmitter } from 'events';
import { RedisService, getRedis } from './redis.service';

interface TenantConfig {
  id: string;
  name: string;
  slug: string;
  domain?: string;
  subdomain?: string;
  database?: {
    host?: string;
    port?: number;
    name?: string;
    schema?: string;
  };
  storage?: {
    bucket?: string;
    prefix?: string;
  };
  features?: {
    [key: string]: boolean | string | number;
  };
  limits?: {
    users?: number;
    storage?: number; // bytes
    api_calls?: number;
    custom_roles?: number;
    teams?: number;
  };
  settings?: Record<string, any>;
  metadata?: Record<string, any>;
}

interface TenantContext {
  tenant: TenantConfig;
  user_id?: string;
  permissions?: string[];
  ip?: string;
  user_agent?: string;
  request_id?: string;
}

interface DataPartition {
  strategy: 'schema' | 'database' | 'table' | 'row';
  identifier: string;
}

interface TenantIsolation {
  level: 'shared' | 'semi-isolated' | 'fully-isolated';
  database: DataPartition;
  storage: DataPartition;
  compute?: 'shared' | 'dedicated';
}

export class MultiTenancyService extends EventEmitter {
  private redis: RedisService;
  private tenants: Map<string, TenantConfig> = new Map();
  private tenantsByDomain: Map<string, string> = new Map();
  private tenantsBySlug: Map<string, string> = new Map();
  private currentContext: TenantContext | null = null;
  
  constructor() {
    super();
    this.redis = getRedis();
    this.loadTenants();
  }
  
  // Tenant Management
  async createTenant(config: Omit<TenantConfig, 'id'>): Promise<TenantConfig> {
    const tenantId = this.generateTenantId();
    const tenant: TenantConfig = {
      id: tenantId,
      ...config,
      features: config.features || {},
      limits: config.limits || this.getDefaultLimits(),
      settings: config.settings || {},
      metadata: {
        ...config.metadata,
        created_at: new Date().toISOString(),
        status: 'active'
      }
    };
    
    // Validate slug uniqueness
    if (this.tenantsBySlug.has(tenant.slug)) {
      throw new Error(`Tenant slug '${tenant.slug}' already exists`);
    }
    
    // Validate domain uniqueness
    if (tenant.domain && this.tenantsByDomain.has(tenant.domain)) {
      throw new Error(`Domain '${tenant.domain}' is already in use`);
    }
    
    // Store tenant
    await this.storeTenant(tenant);
    
    // Initialize tenant resources
    await this.initializeTenantResources(tenant);
    
    // Emit event
    this.emit('tenant_created', {
      tenant_id: tenantId,
      name: tenant.name,
      slug: tenant.slug,
      timestamp: new Date()
    });
    
    return tenant;
  }
  
  async updateTenant(
    tenantId: string,
    updates: Partial<Omit<TenantConfig, 'id'>>
  ): Promise<TenantConfig> {
    const tenant = await this.getTenant(tenantId);
    if (!tenant) {
      throw new Error(`Tenant '${tenantId}' not found`);
    }
    
    // Validate slug change
    if (updates.slug && updates.slug !== tenant.slug) {
      if (this.tenantsBySlug.has(updates.slug)) {
        throw new Error(`Tenant slug '${updates.slug}' already exists`);
      }
    }
    
    // Validate domain change
    if (updates.domain && updates.domain !== tenant.domain) {
      if (this.tenantsByDomain.has(updates.domain)) {
        throw new Error(`Domain '${updates.domain}' is already in use`);
      }
    }
    
    // Update tenant
    const updatedTenant: TenantConfig = {
      ...tenant,
      ...updates,
      metadata: {
        ...tenant.metadata,
        ...updates.metadata,
        updated_at: new Date().toISOString()
      }
    };
    
    await this.storeTenant(updatedTenant);
    
    // Update indexes
    if (updates.slug && updates.slug !== tenant.slug) {
      this.tenantsBySlug.delete(tenant.slug);
      this.tenantsBySlug.set(updates.slug, tenantId);
    }
    
    if (updates.domain) {
      if (tenant.domain) {
        this.tenantsByDomain.delete(tenant.domain);
      }
      this.tenantsByDomain.set(updates.domain, tenantId);
    }
    
    // Emit event
    this.emit('tenant_updated', {
      tenant_id: tenantId,
      changes: updates,
      timestamp: new Date()
    });
    
    return updatedTenant;
  }
  
  async deleteTenant(tenantId: string): Promise<void> {
    const tenant = await this.getTenant(tenantId);
    if (!tenant) {
      throw new Error(`Tenant '${tenantId}' not found`);
    }
    
    // Clean up resources
    await this.cleanupTenantResources(tenant);
    
    // Remove from storage
    await this.redis.hdel('tenants', tenantId);
    
    // Remove from memory
    this.tenants.delete(tenantId);
    this.tenantsBySlug.delete(tenant.slug);
    if (tenant.domain) {
      this.tenantsByDomain.delete(tenant.domain);
    }
    
    // Emit event
    this.emit('tenant_deleted', {
      tenant_id: tenantId,
      timestamp: new Date()
    });
  }
  
  // Tenant Resolution
  async getTenant(tenantId: string): Promise<TenantConfig | null> {
    // Check memory cache
    if (this.tenants.has(tenantId)) {
      return this.tenants.get(tenantId)!;
    }
    
    // Check Redis
    const tenant = await this.redis.hget<TenantConfig>('tenants', tenantId);
    if (tenant) {
      this.cacheTenant(tenant);
      return tenant;
    }
    
    return null;
  }
  
  async getTenantBySlug(slug: string): Promise<TenantConfig | null> {
    const tenantId = this.tenantsBySlug.get(slug);
    if (!tenantId) {
      // Try Redis
      const tenantId = await this.redis.hget<string>('tenant_slugs', slug);
      if (!tenantId) return null;
    }
    
    return this.getTenant(tenantId!);
  }
  
  async getTenantByDomain(domain: string): Promise<TenantConfig | null> {
    const tenantId = this.tenantsByDomain.get(domain);
    if (!tenantId) {
      // Try Redis
      const tenantId = await this.redis.hget<string>('tenant_domains', domain);
      if (!tenantId) return null;
    }
    
    return this.getTenant(tenantId!);
  }
  
  async resolveTenant(identifier: {
    id?: string;
    slug?: string;
    domain?: string;
    subdomain?: string;
    headers?: Record<string, string>;
  }): Promise<TenantConfig | null> {
    // Priority: id > domain > subdomain > slug > header
    if (identifier.id) {
      return this.getTenant(identifier.id);
    }
    
    if (identifier.domain) {
      return this.getTenantByDomain(identifier.domain);
    }
    
    if (identifier.subdomain) {
      const domain = `${identifier.subdomain}.${this.getBaseDomain()}`;
      return this.getTenantByDomain(domain);
    }
    
    if (identifier.slug) {
      return this.getTenantBySlug(identifier.slug);
    }
    
    // Check custom header
    if (identifier.headers?.['x-tenant-id']) {
      return this.getTenant(identifier.headers['x-tenant-id']);
    }
    
    return null;
  }
  
  // Context Management
  setContext(context: TenantContext): void {
    this.currentContext = context;
    this.emit('context_set', context);
  }
  
  getContext(): TenantContext | null {
    return this.currentContext;
  }
  
  clearContext(): void {
    this.currentContext = null;
    this.emit('context_cleared');
  }
  
  withContext<T>(
    context: TenantContext,
    fn: () => T | Promise<T>
  ): T | Promise<T> {
    const previousContext = this.currentContext;
    this.setContext(context);
    
    try {
      const result = fn();
      if (result instanceof Promise) {
        return result.finally(() => {
          this.currentContext = previousContext;
        });
      }
      return result;
    } finally {
      this.currentContext = previousContext;
    }
  }
  
  // Data Isolation
  getTenantDatabase(tenantId: string): string {
    const tenant = this.tenants.get(tenantId);
    if (!tenant) {
      throw new Error(`Tenant '${tenantId}' not found`);
    }
    
    if (tenant.database?.name) {
      return tenant.database.name;
    }
    
    // Default: use tenant ID as database suffix
    return `db_${tenantId.replace(/-/g, '_')}`;
  }
  
  getTenantSchema(tenantId: string): string {
    const tenant = this.tenants.get(tenantId);
    if (!tenant) {
      throw new Error(`Tenant '${tenantId}' not found`);
    }
    
    if (tenant.database?.schema) {
      return tenant.database.schema;
    }
    
    // Default: use tenant slug as schema
    return `tenant_${tenant.slug.replace(/-/g, '_')}`;
  }
  
  getTenantTablePrefix(tenantId: string): string {
    return `t_${tenantId.substring(0, 8)}_`;
  }
  
  getIsolationLevel(tenantId: string): TenantIsolation {
    const tenant = this.tenants.get(tenantId);
    if (!tenant) {
      throw new Error(`Tenant '${tenantId}' not found`);
    }
    
    // Determine based on billing plan or settings
    const plan = tenant.metadata?.billing_plan || 'free';
    
    switch (plan) {
      case 'enterprise':
        return {
          level: 'fully-isolated',
          database: {
            strategy: 'database',
            identifier: this.getTenantDatabase(tenantId)
          },
          storage: {
            strategy: 'database',
            identifier: tenant.storage?.bucket || `tenant-${tenantId}`
          },
          compute: 'dedicated'
        };
      
      case 'professional':
        return {
          level: 'semi-isolated',
          database: {
            strategy: 'schema',
            identifier: this.getTenantSchema(tenantId)
          },
          storage: {
            strategy: 'table',
            identifier: tenant.storage?.prefix || `${tenantId}/`
          },
          compute: 'shared'
        };
      
      default:
        return {
          level: 'shared',
          database: {
            strategy: 'row',
            identifier: tenantId
          },
          storage: {
            strategy: 'row',
            identifier: tenantId
          },
          compute: 'shared'
        };
    }
  }
  
  // Resource Management
  private async initializeTenantResources(tenant: TenantConfig): Promise<void> {
    const isolation = this.getIsolationLevel(tenant.id);
    
    // Initialize database
    if (isolation.database.strategy === 'database') {
      await this.createTenantDatabase(tenant.id);
    } else if (isolation.database.strategy === 'schema') {
      await this.createTenantSchema(tenant.id);
    }
    
    // Initialize storage
    if (isolation.storage.strategy === 'database') {
      await this.createTenantStorageBucket(tenant.id);
    }
    
    // Initialize cache namespace
    await this.redis.set(`tenant:initialized:${tenant.id}`, true);
  }
  
  private async cleanupTenantResources(tenant: TenantConfig): Promise<void> {
    const isolation = this.getIsolationLevel(tenant.id);
    
    // Cleanup database
    if (isolation.database.strategy === 'database') {
      await this.dropTenantDatabase(tenant.id);
    } else if (isolation.database.strategy === 'schema') {
      await this.dropTenantSchema(tenant.id);
    }
    
    // Cleanup storage
    if (isolation.storage.strategy === 'database') {
      await this.deleteTenantStorageBucket(tenant.id);
    }
    
    // Cleanup cache
    await this.redis.deleteByPattern(`tenant:${tenant.id}:*`);
  }
  
  // Feature Flags & Limits
  async checkFeature(tenantId: string, feature: string): Promise<boolean> {
    const tenant = await this.getTenant(tenantId);
    if (!tenant) return false;
    
    const value = tenant.features?.[feature];
    return value === true || value === 'enabled';
  }
  
  async checkLimit(
    tenantId: string,
    resource: keyof NonNullable<TenantConfig['limits']>,
    current: number
  ): Promise<{ allowed: boolean; limit: number; remaining: number }> {
    const tenant = await this.getTenant(tenantId);
    if (!tenant) {
      return { allowed: false, limit: 0, remaining: 0 };
    }
    
    const limit = tenant.limits?.[resource] || this.getDefaultLimits()[resource] || 0;
    const remaining = Math.max(0, limit - current);
    
    return {
      allowed: current < limit,
      limit,
      remaining
    };
  }
  
  async enforceRateLimit(
    tenantId: string,
    resource: string,
    limit: number,
    window: number = 60
  ): Promise<{ allowed: boolean; remaining: number; reset_at: number }> {
    const key = `ratelimit:tenant:${tenantId}:${resource}`;
    return this.redis.checkRateLimit(key, limit, window);
  }
  
  // Usage Tracking
  async trackUsage(
    tenantId: string,
    metric: string,
    value: number = 1
  ): Promise<void> {
    const key = `usage:${tenantId}:${metric}`;
    const today = new Date().toISOString().split('T')[0];
    
    // Increment daily counter
    await this.redis.hincrby(`${key}:${today}`, 'count', value);
    
    // Update monthly aggregate
    const month = today.substring(0, 7);
    await this.redis.hincrby(`${key}:${month}`, 'total', value);
    
    // Check if limit exceeded
    const tenant = await this.getTenant(tenantId);
    if (tenant?.limits && metric in tenant.limits) {
      const current = await this.redis.hget<number>(`${key}:${month}`, 'total') || 0;
      const limit = tenant.limits[metric as keyof typeof tenant.limits];
      
      if (current > limit!) {
        this.emit('limit_exceeded', {
          tenant_id: tenantId,
          metric,
          current,
          limit,
          timestamp: new Date()
        });
      }
    }
  }
  
  async getUsage(
    tenantId: string,
    metric: string,
    period: 'day' | 'month' | 'year' = 'month'
  ): Promise<{ value: number; period: string }> {
    const key = `usage:${tenantId}:${metric}`;
    let periodKey: string;
    
    const now = new Date();
    switch (period) {
      case 'day':
        periodKey = now.toISOString().split('T')[0];
        break;
      case 'month':
        periodKey = now.toISOString().substring(0, 7);
        break;
      case 'year':
        periodKey = now.getFullYear().toString();
        break;
    }
    
    const value = await this.redis.hget<number>(`${key}:${periodKey}`, 'total') || 0;
    
    return { value, period: periodKey };
  }
  
  // Cross-Tenant Security
  validateCrossTenantAccess(
    sourceTenantId: string,
    targetTenantId: string,
    operation: string
  ): boolean {
    // Prevent cross-tenant access by default
    if (sourceTenantId !== targetTenantId) {
      this.emit('cross_tenant_access_denied', {
        source: sourceTenantId,
        target: targetTenantId,
        operation,
        timestamp: new Date()
      });
      return false;
    }
    
    return true;
  }
  
  // Helper Methods
  private generateTenantId(): string {
    return `tenant_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
  }
  
  private getDefaultLimits(): NonNullable<TenantConfig['limits']> {
    return {
      users: 10,
      storage: 1073741824, // 1GB
      api_calls: 10000,
      custom_roles: 5,
      teams: 3
    };
  }
  
  private getBaseDomain(): string {
    return process.env.BASE_DOMAIN || 'example.com';
  }
  
  private async storeTenant(tenant: TenantConfig): Promise<void> {
    // Store in Redis
    await this.redis.hset('tenants', tenant.id, tenant);
    await this.redis.hset('tenant_slugs', tenant.slug, tenant.id);
    
    if (tenant.domain) {
      await this.redis.hset('tenant_domains', tenant.domain, tenant.id);
    }
    
    // Update memory cache
    this.cacheTenant(tenant);
  }
  
  private cacheTenant(tenant: TenantConfig): void {
    this.tenants.set(tenant.id, tenant);
    this.tenantsBySlug.set(tenant.slug, tenant.id);
    
    if (tenant.domain) {
      this.tenantsByDomain.set(tenant.domain, tenant.id);
    }
  }
  
  private async loadTenants(): Promise<void> {
    // Load all tenants from Redis on startup
    const tenants = await this.redis.hgetall<TenantConfig>('tenants');
    
    for (const tenant of Object.values(tenants)) {
      this.cacheTenant(tenant);
    }
  }
  
  // Database operations (implementations would be database-specific)
  private async createTenantDatabase(tenantId: string): Promise<void> {
    // Implementation depends on database type
    console.log(`Creating database for tenant ${tenantId}`);
  }
  
  private async dropTenantDatabase(tenantId: string): Promise<void> {
    // Implementation depends on database type
    console.log(`Dropping database for tenant ${tenantId}`);
  }
  
  private async createTenantSchema(tenantId: string): Promise<void> {
    // Implementation depends on database type
    console.log(`Creating schema for tenant ${tenantId}`);
  }
  
  private async dropTenantSchema(tenantId: string): Promise<void> {
    // Implementation depends on database type
    console.log(`Dropping schema for tenant ${tenantId}`);
  }
  
  private async createTenantStorageBucket(tenantId: string): Promise<void> {
    // Implementation depends on storage provider
    console.log(`Creating storage bucket for tenant ${tenantId}`);
  }
  
  private async deleteTenantStorageBucket(tenantId: string): Promise<void> {
    // Implementation depends on storage provider
    console.log(`Deleting storage bucket for tenant ${tenantId}`);
  }
}

// Export singleton instance
let multiTenancyService: MultiTenancyService | null = null;

export function getMultiTenancyService(): MultiTenancyService {
  if (!multiTenancyService) {
    multiTenancyService = new MultiTenancyService();
  }
  return multiTenancyService;
}