#!/usr/bin/env tsx

import { execFileSync, execSync } from 'child_process'
import { join } from 'path'

/**
 * Database Migration and Setup Script
 *
 * This script handles:
 * 1. Initial database setup
 * 2. Migration generation and application
 * 3. Row-Level Security (RLS) setup for multi-tenancy
 * 4. Performance optimization indexes
 * 5. Tenant database provisioning
 */

interface MigrationOptions {
  reset?: boolean
  seed?: boolean
  rls?: boolean
  indexes?: boolean
  tenant?: string
}

class DatabaseMigrator {
  private readonly schemaPath: string
  private readonly migrationsPath: string

  constructor() {
    this.schemaPath = join(__dirname, 'schema.prisma')
    this.migrationsPath = join(__dirname, 'migrations')
  }

  /**
   * Run complete database setup
   */
  async setup(options: MigrationOptions = {}): Promise<void> {
    console.log('🚀 Starting database setup...')

    try {
      if (options.reset) {
        await this.reset()
      }

      await this.generateMigration()
      await this.applyMigrations()

      if (options.rls) {
        await this.setupRowLevelSecurity()
      }

      if (options.indexes) {
        await this.createPerformanceIndexes()
      }

      if (options.seed) {
        await this.seedDatabase()
      }

      if (options.tenant) {
        await this.provisionTenantDatabase(options.tenant)
      }

      await this.generateClient()

      console.log('✅ Database setup completed successfully!')
    } catch (error) {
      console.error('❌ Database setup failed:', error)
      process.exit(1)
    }
  }

  /**
   * Reset database
   */
  private async reset(): Promise<void> {
    console.log('🗑️  Resetting database...')
    execSync('npx prisma migrate reset --force', { stdio: 'inherit' })
  }

  /**
   * Generate migration from schema changes
   */
  private async generateMigration(): Promise<void> {
    console.log('📝 Generating migration...')
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0]
    const migrationName = `${timestamp}-initial-schema`

    try {
      execSync(`npx prisma migrate dev --name ${migrationName}`, { stdio: 'inherit' })
    } catch (error) {
      console.log('Migration already exists or no changes detected')
    }
  }

  /**
   * Apply pending migrations
   */
  private async applyMigrations(): Promise<void> {
    console.log('🔄 Applying migrations...')
    execSync('npx prisma migrate deploy', { stdio: 'inherit' })
  }

  /**
   * Setup Row-Level Security for multi-tenancy
   */
  private async setupRowLevelSecurity(): Promise<void> {
    console.log('🔒 Setting up Row-Level Security...')

    const rlsSQL = `
-- Enable Row-Level Security for tenant-aware tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_endpoints ENABLE ROW LEVEL SECURITY;

-- Create application role
CREATE ROLE app_role;

-- Grant necessary permissions to application role
GRANT CONNECT ON DATABASE ${process.env.DB_NAME || 'janua_db'} TO app_role;
GRANT USAGE ON SCHEMA public TO app_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_role;

-- Create RLS policies for tenant isolation
CREATE POLICY tenant_isolation_users ON users
    FOR ALL TO app_role
    USING (tenant_id = current_setting('app.current_tenant', true)::text);

CREATE POLICY tenant_isolation_teams ON teams
    FOR ALL TO app_role
    USING (tenant_id = current_setting('app.current_tenant', true)::text);

CREATE POLICY tenant_isolation_audit_logs ON audit_logs
    FOR ALL TO app_role
    USING (tenant_id = current_setting('app.current_tenant', true)::text OR tenant_id IS NULL);

CREATE POLICY tenant_isolation_sessions ON sessions
    FOR ALL TO app_role
    USING (tenant_id = current_setting('app.current_tenant', true)::text OR tenant_id IS NULL);

-- Add similar policies for other tenant-aware tables
-- (Additional policies would be added here for all tenant-aware tables)

-- Create function to set tenant context
CREATE OR REPLACE FUNCTION set_tenant_context(tenant_id TEXT)
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_tenant', tenant_id, true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create function to get current tenant
CREATE OR REPLACE FUNCTION get_current_tenant()
RETURNS TEXT AS $$
BEGIN
    RETURN current_setting('app.current_tenant', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
`

    await this.executeSQLFile(rlsSQL)
  }

  /**
   * Create performance optimization indexes
   */
  private async createPerformanceIndexes(): Promise<void> {
    console.log('⚡ Creating performance indexes...')

    const indexSQL = `
-- Additional composite indexes for performance optimization

-- User activity tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_tenant_last_login
ON users (tenant_id, last_login_at DESC) WHERE status = 'active';

-- Team hierarchy queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_teams_hierarchy
ON teams (tenant_id, parent_team_id) WHERE parent_team_id IS NOT NULL;

-- Role assignment lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_role_assignments_principal_scope
ON role_assignments (principal_type, principal_id, scope_type, scope_id);

-- Session management
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_user_active
ON sessions (user_id, is_active, expires_at DESC) WHERE is_active = true;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_cleanup
ON sessions (expires_at) WHERE is_active = true;

-- Audit log analysis
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_analysis
ON audit_logs (tenant_id, timestamp DESC, action, outcome);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_risk
ON audit_logs (risk_score DESC, timestamp DESC) WHERE risk_score > 0.5;

-- Billing and usage tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_usage_records_tenant_metric_time
ON usage_records (tenant_id, metric, timestamp DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_billing_subscriptions_status_period
ON billing_subscriptions (status, current_period_end) WHERE status IN ('active', 'trialing');

-- Payment processing
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payment_intents_customer_status
ON payment_intents (customer_id, status, created_at DESC);

-- MFA and security
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_mfa_methods_user_enabled
ON mfa_methods (user_id, enabled, type) WHERE enabled = true;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_passkeys_user_last_used
ON passkeys (user_id, last_used_at DESC NULLS LAST);

-- Team membership queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_team_members_user_teams
ON team_members (user_id, team_id, role);

-- API key management
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_keys_tenant_active
ON api_keys (tenant_id, is_active, expires_at) WHERE is_active = true;

-- Webhook delivery tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhook_deliveries_retry
ON webhook_deliveries (status, next_retry_at) WHERE status = 'retrying';

-- Audit log partitioning preparation (for future partitioning)
-- This creates an index that aligns with common partitioning strategies
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_partition_ready
ON audit_logs (DATE(timestamp), tenant_id, timestamp DESC);
`

    await this.executeSQLFile(indexSQL)
  }

  /**
   * Seed database with initial data
   */
  private async seedDatabase(): Promise<void> {
    console.log('🌱 Seeding database...')

    const seedSQL = `
-- Insert system tenant for global resources
INSERT INTO tenants (id, name, slug, isolation_level, status, created_at, updated_at)
VALUES ('system', 'System', 'system', 'shared', 'active', NOW(), NOW())
ON CONFLICT (slug) DO NOTHING;

-- Insert default billing plans
INSERT INTO billing_plans (id, name, display_name, description, price_amount, price_currency, price_interval, features, is_active, is_default, created_at, updated_at)
VALUES
  ('free', 'free', 'Free', 'Perfect for trying out Janua', 0, 'USD', 'monthly',
   '{"users":5,"teams":1,"storage":1073741824,"api_calls":1000,"custom_roles":0,"audit_retention_days":7,"support_level":"community","sla":false,"custom_domain":false,"sso":false,"advanced_security":false}',
   true, true, NOW(), NOW()),
  ('startup', 'startup', 'Startup', 'For growing teams', 4900, 'USD', 'monthly',
   '{"users":20,"teams":5,"storage":10737418240,"api_calls":10000,"custom_roles":5,"audit_retention_days":30,"support_level":"email","sla":false,"custom_domain":true,"sso":false,"advanced_security":true}',
   true, false, NOW(), NOW()),
  ('professional', 'professional', 'Professional', 'For established organizations', 14900, 'USD', 'monthly',
   '{"users":100,"teams":20,"storage":107374182400,"api_calls":100000,"custom_roles":20,"audit_retention_days":90,"support_level":"priority","sla":true,"custom_domain":true,"sso":true,"advanced_security":true}',
   true, false, NOW(), NOW()),
  ('enterprise', 'enterprise', 'Enterprise', 'Custom solutions for large organizations', 49900, 'USD', 'monthly',
   '{"users":-1,"teams":-1,"storage":-1,"api_calls":-1,"custom_roles":-1,"audit_retention_days":365,"support_level":"dedicated","sla":true,"custom_domain":true,"sso":true,"advanced_security":true}',
   true, false, NOW(), NOW())
ON CONFLICT (name) DO NOTHING;

-- Insert system configurations
INSERT INTO system_configurations (id, key, value, description, category, created_at, updated_at, updated_by)
VALUES
  ('config_1', 'max_login_attempts', '5', 'Maximum failed login attempts before account lockout', 'security', NOW(), NOW(), 'system'),
  ('config_2', 'session_timeout', '3600', 'Session timeout in seconds', 'security', NOW(), NOW(), 'system'),
  ('config_3', 'mfa_grace_period', '300', 'MFA grace period in seconds', 'security', NOW(), NOW(), 'system'),
  ('config_4', 'audit_retention_days', '2555', 'Default audit log retention in days', 'compliance', NOW(), NOW(), 'system')
ON CONFLICT (key) DO NOTHING;
`

    await this.executeSQLFile(seedSQL)
  }

  /**
   * Provision a new tenant database (for fully-isolated tenants)
   */
  private async provisionTenantDatabase(tenantId: string): Promise<void> {
    console.log(`🏢 Provisioning database for tenant: ${tenantId}...`)

    // This would create a new database for fully-isolated tenants
    const dbName = `janua_tenant_${tenantId.replace(/[^a-zA-Z0-9]/g, '_')}`

    try {
      // Create database
      await this.executeSQL(`CREATE DATABASE "${dbName}";`)

      // Run migrations on the new database
      const tenantDatabaseUrl = process.env.DATABASE_URL!.replace(/\/[^/]+$/, `/${dbName}`)

      // Pass DATABASE_URL via env-only (no shell interpolation) to avoid
      // command-line injection if the URL contains shell metacharacters.
      execFileSync('npx', ['prisma', 'migrate', 'deploy'], {
        stdio: 'inherit',
        env: { ...process.env, DATABASE_URL: tenantDatabaseUrl }
      })

      console.log(`✅ Tenant database ${dbName} provisioned successfully`)
    } catch (error) {
      console.error(`❌ Failed to provision tenant database: ${error}`)
      throw error
    }
  }

  /**
   * Generate Prisma client
   */
  private async generateClient(): Promise<void> {
    console.log('🔧 Generating Prisma client...')
    execSync('npx prisma generate', { stdio: 'inherit' })
  }

  /**
   * Execute SQL commands
   */
  private async executeSQL(sql: string): Promise<void> {
    const { Client } = require('pg')
    const client = new Client({
      connectionString: process.env.DATABASE_URL,
    })

    try {
      await client.connect()
      await client.query(sql)
    } finally {
      await client.end()
    }
  }

  /**
   * Execute SQL from string
   */
  private async executeSQLFile(sql: string): Promise<void> {
    const statements = sql
      .split(';')
      .map(s => s.trim())
      .filter(s => s.length > 0 && !s.startsWith('--'))

    for (const statement of statements) {
      try {
        await this.executeSQL(statement)
      } catch (error) {
        console.warn(`Warning: SQL statement failed (might be expected): ${error}`)
      }
    }
  }
}

// CLI interface
async function main() {
  const args = process.argv.slice(2)
  const options: MigrationOptions = {}

  // Parse command line arguments
  for (const arg of args) {
    switch (arg) {
      case '--reset':
        options.reset = true
        break
      case '--seed':
        options.seed = true
        break
      case '--rls':
        options.rls = true
        break
      case '--indexes':
        options.indexes = true
        break
      case '--all':
        options.seed = true
        options.rls = true
        options.indexes = true
        break
      default:
        if (arg.startsWith('--tenant=')) {
          options.tenant = arg.split('=')[1]
        }
    }
  }

  const migrator = new DatabaseMigrator()
  await migrator.setup(options)
}

if (require.main === module) {
  main().catch(console.error)
}

export { DatabaseMigrator }