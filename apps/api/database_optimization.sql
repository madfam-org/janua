-- Database Optimization Strategy for Plinto Platform
-- Phase 2: Performance Optimization - Database Indexing and Query Optimization
-- Target: Sub-100ms API response times

-- =============================================
-- CRITICAL HIGH-TRAFFIC QUERY OPTIMIZATIONS
-- =============================================

-- 1. Authentication Queries (Most Critical - Every API Call)
-- User lookup by email (signin, password reset)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_status ON users(email, status) WHERE status = 'active';

-- User lookup by ID and status (JWT validation)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_id_status ON users(id, status) WHERE status = 'active';

-- Session validation (Every authenticated request)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_access_token_jti ON sessions(access_token_jti) WHERE status = 'active' AND revoked = false;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_refresh_token_jti ON sessions(refresh_token_jti) WHERE status = 'active' AND revoked = false;

-- Session cleanup queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at) WHERE status = 'active';
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_user_status ON sessions(user_id, status, expires_at);

-- 2. Organization Queries (Multi-tenant access patterns)
-- Organization member lookup (RBAC checks)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_org_members_user_org ON organization_members(user_id, organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_org_members_org_role ON organization_members(organization_id, role);

-- Organization lookup by slug (URL routing)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_organizations_slug_active ON organizations(slug) WHERE slug IS NOT NULL;

-- 3. Activity Logging (High-volume writes)
-- Activity log queries by user and time
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_logs_user_created ON activity_logs(user_id, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_logs_action_created ON activity_logs(action, created_at DESC);

-- 4. Token and Verification Tables (Security-critical)
-- Magic link token validation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_magic_links_token_active ON magic_links(token) WHERE used = false;

-- Password reset token validation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_password_resets_token_active ON password_resets(token) WHERE used = false;

-- Email verification token validation
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_email_verifications_token_active ON email_verifications(token) WHERE verified = false;

-- 5. OAuth Account Lookups
-- OAuth provider account lookup (OAuth signin)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_accounts_provider_user_id ON oauth_accounts(provider, provider_user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_accounts_user_provider ON oauth_accounts(user_id, provider);

-- =============================================
-- ENTERPRISE FEATURE OPTIMIZATIONS
-- =============================================

-- 6. SCIM and Enterprise Directory Sync
-- User lookup by external ID (SCIM provisioning)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_user_metadata_external_id ON users USING GIN ((user_metadata->'external_id')) WHERE user_metadata ? 'external_id';

-- Organization SCIM resource queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scim_resources_org_type ON scim_resources(organization_id, resource_type) WHERE organization_id IS NOT NULL;

-- 7. Webhook Delivery Optimization
-- Webhook event processing
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhook_events_type_created ON webhook_events(type, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhook_events_org_type ON webhook_events(organization_id, type) WHERE organization_id IS NOT NULL;

-- Webhook delivery status tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhook_deliveries_status_created ON webhook_deliveries(status, created_at DESC);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhook_deliveries_endpoint_status ON webhook_deliveries(endpoint_id, status);

-- 8. Audit and Compliance
-- Audit log queries by organization and time
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_org_created ON audit_logs(organization_id, created_at DESC) WHERE organization_id IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_logs_event_type_created ON audit_logs(event_type, created_at DESC);

-- =============================================
-- PARTIAL INDEXES FOR QUERY OPTIMIZATION
-- =============================================

-- Active sessions only (most common query pattern)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_active_user ON sessions(user_id, last_active_at DESC) WHERE status = 'active' AND revoked = false;

-- Pending invitations (organization management)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_org_invitations_pending ON organization_invitations(organization_id, email) WHERE status = 'pending';

-- Active webhook endpoints
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhook_endpoints_active ON webhook_endpoints(organization_id, is_active) WHERE is_active = true;

-- Unverified users (cleanup and onboarding flows)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_unverified ON users(created_at DESC) WHERE email_verified = false;

-- =============================================
-- COMPOSITE INDEXES FOR COMPLEX QUERIES
-- =============================================

-- User profile updates (common in user management)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_profile_lookup ON users(email, username, status, email_verified);

-- Organization member management
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_org_members_full ON organization_members(organization_id, user_id, role, joined_at);

-- Session management and cleanup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_management ON sessions(user_id, status, expires_at, created_at);

-- =============================================
-- JSONB INDEXES FOR METADATA QUERIES
-- =============================================

-- User metadata searches (custom fields, integrations)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_metadata_gin ON users USING GIN (user_metadata) WHERE user_metadata IS NOT NULL;

-- Organization settings queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_organizations_settings_gin ON organizations USING GIN (settings) WHERE settings IS NOT NULL;

-- Policy attribute queries (ABAC authorization)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_policies_attributes_gin ON policies USING GIN (attributes) WHERE attributes IS NOT NULL;

-- =============================================
-- TIME-BASED PARTITIONING PREPARATION
-- =============================================

-- Activity logs partitioning (high-volume table)
-- Note: This would require migration to implement partitioning
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_activity_logs_partition_key ON activity_logs(created_at, user_id);

-- Webhook events partitioning
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhook_events_partition_key ON webhook_events(created_at, organization_id);

-- =============================================
-- FOREIGN KEY CONSTRAINT INDEXES
-- =============================================

-- Ensure all foreign key columns have indexes for join performance
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_oauth_accounts_user_id ON oauth_accounts(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_passkeys_user_id ON passkeys(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_magic_links_user_id ON magic_links(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_password_resets_user_id ON password_resets(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_email_verifications_user_id ON email_verifications(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_organizations_owner_id ON organizations(owner_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_org_invitations_organization_id ON organization_invitations(organization_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_org_invitations_invited_by ON organization_invitations(invited_by);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhook_endpoints_user_id ON webhook_endpoints(user_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_webhook_endpoints_organization_id ON webhook_endpoints(organization_id);

-- =============================================
-- DATABASE CONFIGURATION OPTIMIZATIONS
-- =============================================

-- Connection and memory settings for performance
-- These would be applied in postgresql.conf

-- Connection pooling optimization
-- max_connections = 200
-- shared_buffers = 256MB (25% of available RAM for dedicated DB server)
-- effective_cache_size = 1GB (75% of available RAM)

-- Query performance settings  
-- work_mem = 4MB (for sorting and hash operations)
-- maintenance_work_mem = 64MB (for index builds and VACUUM)
-- checkpoint_completion_target = 0.9
-- wal_buffers = 16MB

-- Logging for performance monitoring
-- log_min_duration_statement = 100ms (log slow queries)
-- log_statement = 'ddl' (log schema changes)
-- log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '

-- =============================================
-- MAINTENANCE AND MONITORING QUERIES
-- =============================================

-- Index usage monitoring query:
-- SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
-- FROM pg_stat_user_indexes 
-- ORDER BY idx_scan DESC;

-- Table size monitoring:
-- SELECT schemaname, tablename, 
--        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
--        pg_stat_get_live_tuples(c.oid) as live_tuples
-- FROM pg_tables pt, pg_class c, pg_namespace n
-- WHERE pt.tablename = c.relname 
--   AND n.nspname = pt.schemaname 
--   AND c.relnamespace = n.oid
--   AND schemaname = 'public'
-- ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Query performance monitoring:
-- SELECT query, calls, total_time, mean_time, rows
-- FROM pg_stat_statements 
-- WHERE mean_time > 100 
-- ORDER BY mean_time DESC 
-- LIMIT 20;