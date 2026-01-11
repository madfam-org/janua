# Performance Tuning Guide

This guide covers performance optimization for Janua deployments, from development through production scale.

## Table of Contents

1. [Performance Overview](#performance-overview)
2. [Database Optimization](#database-optimization)
3. [Redis and Caching](#redis-and-caching)
4. [API Performance](#api-performance)
5. [JWT and Session Optimization](#jwt-and-session-optimization)
6. [Rate Limiting Configuration](#rate-limiting-configuration)
7. [Monitoring and Metrics](#monitoring-and-metrics)
8. [Production Scaling](#production-scaling)
9. [Troubleshooting Performance Issues](#troubleshooting-performance-issues)

---

## Performance Overview

### Performance Targets

| Metric | Target | Description |
|--------|--------|-------------|
| API Response Time (P50) | < 50ms | Median response time for authenticated endpoints |
| API Response Time (P95) | < 100ms | 95th percentile response time |
| API Response Time (P99) | < 200ms | 99th percentile response time |
| Token Validation | < 5ms | JWT validation time (cached JWKS) |
| Cache Hit Rate | > 85% | Redis cache hit rate for hot paths |
| Database Query (P50) | < 10ms | Median database query time |
| Database Query (P95) | < 50ms | 95th percentile database query time |

### Architecture Overview

```
                      ┌─────────────────────────────────────────┐
                      │           Janua API Layer              │
                      │  ┌─────────────────────────────────┐   │
                      │  │     Performance Middleware      │   │
                      │  │  - Request timing & logging     │   │
                      │  │  - Response time headers        │   │
                      │  │  - Slow query detection         │   │
                      │  └─────────────────────────────────┘   │
                      │                  │                      │
       ┌──────────────┼──────────────────┼──────────────────────┤
       │              │                  │                      │
       ▼              ▼                  ▼                      │
┌─────────────┐ ┌───────────┐    ┌─────────────┐               │
│  L1 Cache   │ │  L2 Cache │    │   Database  │               │
│  (Memory)   │ │  (Redis)  │    │ (PostgreSQL)│               │
│  < 1ms      │ │  < 5ms    │    │   < 50ms    │               │
└─────────────┘ └───────────┘    └─────────────┘               │
                      │                                         │
                      └─────────────────────────────────────────┘
```

---

## Database Optimization

### Connection Pool Configuration

Configure the database connection pool based on your workload:

```bash
# Environment variables
DATABASE_URL=postgresql://user:pass@host:5432/janua
DATABASE_POOL_SIZE=20       # Base connections to maintain
DATABASE_MAX_OVERFLOW=10    # Additional connections under load
DATABASE_POOL_TIMEOUT=30    # Seconds to wait for connection
```

#### Pool Size Guidelines

| Deployment Size | Pool Size | Max Overflow | Total Max |
|-----------------|-----------|--------------|-----------|
| Development | 5 | 5 | 10 |
| Small (< 100 req/s) | 10 | 10 | 20 |
| Medium (100-500 req/s) | 20 | 20 | 40 |
| Large (500-2000 req/s) | 50 | 50 | 100 |
| Enterprise (> 2000 req/s) | 100+ | 50 | 150+ |

**Note**: Total connections should not exceed PostgreSQL's `max_connections` (typically 100-200 default).

### PostgreSQL Configuration

For production PostgreSQL, tune these parameters:

```sql
-- postgresql.conf or ALTER SYSTEM SET

-- Memory (adjust based on available RAM)
shared_buffers = '256MB'           -- 25% of RAM up to 1GB
effective_cache_size = '768MB'     -- 75% of RAM
work_mem = '16MB'                  -- Per-query memory
maintenance_work_mem = '128MB'     -- For maintenance operations

-- Connections
max_connections = 200              -- Match your pool total
superuser_reserved_connections = 3

-- Query Planner
random_page_cost = 1.1             -- For SSD storage
effective_io_concurrency = 200     -- For SSD storage

-- Write Ahead Log
wal_level = 'replica'
max_wal_size = '1GB'
min_wal_size = '80MB'

-- Checkpoints
checkpoint_completion_target = 0.9
checkpoint_timeout = '15min'

-- Logging (for performance analysis)
log_min_duration_statement = 100   -- Log queries > 100ms
log_checkpoints = on
log_connections = on
log_disconnections = on
```

### Query Optimization

Enable query statistics for analysis:

```sql
-- Enable pg_stat_statements extension
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- View slow queries
SELECT
    query,
    calls,
    total_time / calls AS avg_time_ms,
    rows / calls AS avg_rows
FROM pg_stat_statements
WHERE mean_time > 50
AND query NOT LIKE '%pg_stat_statements%'
ORDER BY mean_time DESC
LIMIT 20;
```

#### Common Index Recommendations

```sql
-- User lookup by email (most common)
CREATE INDEX CONCURRENTLY idx_users_email_lower
ON users(LOWER(email));

-- Session lookup by token
CREATE INDEX CONCURRENTLY idx_sessions_token_active
ON sessions(token) WHERE is_active = true;

-- Organization member lookup
CREATE INDEX CONCURRENTLY idx_org_members_user_org
ON organization_members(user_id, organization_id);

-- Audit log time-based queries
CREATE INDEX CONCURRENTLY idx_audit_logs_created
ON audit_logs(created_at DESC);

-- API token lookup
CREATE INDEX CONCURRENTLY idx_api_tokens_hash_active
ON api_tokens(token_hash) WHERE is_active = true AND expires_at > NOW();
```

---

## Redis and Caching

### Redis Configuration

```bash
# Environment variables
REDIS_URL=redis://localhost:6379/0
REDIS_POOL_SIZE=10
REDIS_DECODE_RESPONSES=true
```

#### Redis Server Configuration

For production Redis, tune these parameters:

```conf
# redis.conf

# Memory
maxmemory 512mb
maxmemory-policy allkeys-lru

# Connections
maxclients 10000
timeout 300

# Persistence (choose based on needs)
# RDB snapshots
save 900 1
save 300 10
save 60 10000

# AOF for durability
appendonly no  # Enable if session durability needed
appendfsync everysec

# Performance
tcp-keepalive 300
activedefrag yes
```

### Caching Strategies

Janua uses a two-tier caching strategy:

| Cache Level | Storage | TTL | Use Case |
|-------------|---------|-----|----------|
| L1 (Memory) | In-process | 60s-300s | Ultra-hot paths |
| L2 (Redis) | Redis | 300s-3600s | Shared cache across instances |

#### Default TTL Settings

| Data Type | Default TTL | Recommended Range |
|-----------|-------------|-------------------|
| User Profile | 5 minutes | 2-10 minutes |
| Session Validation | 1 minute | 30s-2 minutes |
| Organization | 10 minutes | 5-30 minutes |
| Settings/Config | 30 minutes | 15-60 minutes |
| SSO Configuration | 30 minutes | 15-60 minutes |
| Permissions | 5 minutes | 2-10 minutes |
| JWKS | 1 hour | 30m-2 hours |

### Using Cache Decorators

```python
from app.core.caching import cached, cache_user, cache_organization, cache_permissions

# Basic caching
@cached(ttl=600)  # 10 minutes
async def get_user_profile(user_id: str) -> dict:
    return await db.get_user(user_id)

# User-specific caching (10 minutes default)
@cache_user(ttl=600)
async def get_user_by_id(user_id: str, db: AsyncSession) -> User:
    return await db.query(User).filter(User.id == user_id).first()

# Organization caching (1 hour default)
@cache_organization(ttl=3600)
async def get_organization(org_id: str) -> Organization:
    return await db.query(Organization).filter(Organization.id == org_id).first()

# Permission caching (5 minutes default)
@cache_permissions(ttl=300)
async def check_permission(user_id: str, resource: str, action: str) -> bool:
    return await rbac.check(user_id, resource, action)
```

### Cache Invalidation

```python
from app.core.caching import cache_manager

# Invalidate specific key
await cache_manager.invalidate(f"user:{user_id}")

# Warm cache with new data
await cache_manager.warm_cache(
    f"user:{user_id}",
    user.to_dict(),
    ttl=600
)

# Pattern invalidation (use sparingly)
await cache_manager.invalidate_pattern(f"org:{org_id}:*")
```

### Circuit Breaker for Redis

Redis operations are protected by a circuit breaker to prevent cascading failures:

```python
# Circuit breaker configuration
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5      # Open after 5 failures
CIRCUIT_BREAKER_RECOVERY_TIMEOUT = 30      # Try recovery after 30s
CIRCUIT_BREAKER_EXPECTED_EXCEPTION = Exception

# Behavior when Redis is down:
# - Cache lookups return None (cache miss)
# - Operations continue without caching
# - Circuit opens after threshold failures
# - Periodic recovery attempts
```

---

## API Performance

### Performance Monitoring Middleware

The `PerformanceMonitoringMiddleware` automatically tracks:

- Request duration
- Slow endpoint detection (> 100ms default)
- Response time headers (`X-Response-Time`)
- Endpoint performance statistics

```python
# Enable in main.py (already enabled by default)
from app.core.performance import PerformanceMonitoringMiddleware

app.add_middleware(
    PerformanceMonitoringMiddleware,
    slow_threshold_ms=100.0  # Customize threshold
)
```

### Response Time Headers

All responses include:

```http
X-Response-Time: 23.45ms
X-Request-ID: uuid-here
```

### Endpoint Optimization Priorities

Focus optimization efforts on these high-traffic endpoints:

| Priority | Endpoint | Target | Optimization |
|----------|----------|--------|--------------|
| P0 | `POST /auth/signin` | < 100ms | Session caching, connection pooling |
| P0 | `GET /auth/me` | < 20ms | User profile caching |
| P0 | `POST /auth/refresh` | < 50ms | Token validation caching |
| P1 | `GET /organizations/:id` | < 30ms | Organization caching |
| P1 | `GET /users/:id` | < 30ms | User caching |
| P2 | `GET /organizations/:id/members` | < 50ms | Pagination, eager loading |
| P2 | `GET /sessions` | < 50ms | Session list caching |

---

## JWT and Session Optimization

### JWT Configuration

```bash
# Token lifetimes
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15   # Short-lived access tokens
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7      # Long-lived refresh tokens
JWT_ALGORITHM=RS256                  # Use RS256 for production
```

### JWKS Caching

The JWKS endpoint is highly cacheable:

```python
# JWKS caching configuration
JWKS_CACHE_TTL = 3600  # 1 hour
JWKS_REFRESH_INTERVAL = 1800  # Refresh every 30 minutes

# Client-side caching headers
Cache-Control: public, max-age=3600
```

### Session Optimization

```bash
# Session configuration
SESSION_COOKIE_SECURE=true           # HTTPS only
SESSION_COOKIE_HTTPONLY=true         # No JavaScript access
SESSION_COOKIE_SAMESITE=lax          # CSRF protection
COOKIE_DOMAIN=.janua.dev             # Cross-subdomain SSO
```

---

## Rate Limiting Configuration

### Configuration Options

```bash
# Rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60         # Requests per minute per IP
RATE_LIMIT_PER_HOUR=1000         # Requests per hour per IP
RATE_LIMIT_WHITELIST=127.0.0.1,::1,10.0.0.0/8  # Exempt IPs
TRUSTED_PROXIES=10.0.0.1,10.0.0.2  # Load balancer IPs
```

### Endpoint-Specific Limits

| Endpoint Category | Per Minute | Per Hour | Rationale |
|-------------------|------------|----------|-----------|
| Authentication | 10 | 100 | Prevent brute force |
| Password Reset | 5 | 20 | Prevent enumeration |
| Token Refresh | 30 | 300 | Allow normal token cycling |
| User Operations | 60 | 1000 | Standard API usage |
| Admin Operations | 120 | 2000 | Higher for admin tools |
| Webhooks | 1000 | 10000 | High volume events |

### Rate Limit Headers

Responses include rate limit information:

```http
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640000000
Retry-After: 30  # When rate limited
```

---

## Monitoring and Metrics

### Performance Metrics Endpoint

```http
GET /metrics
Authorization: Bearer <admin-token>
```

Response:

```json
{
  "cache_stats": {
    "hits": 15234,
    "misses": 1823,
    "sets": 2045,
    "hit_rate_percent": 89.3,
    "l1_cache_size": 156,
    "redis_connected": true
  },
  "endpoint_performance": {
    "POST:/api/v1/auth/signin": {
      "count": 5234,
      "total_time": 125634.5,
      "min_time": 12.3,
      "max_time": 234.5,
      "avg_time": 24.0,
      "error_count": 12
    }
  },
  "database": {
    "connection_pool": {
      "active": 15,
      "idle": 5,
      "pending": 0
    }
  },
  "timestamp": "2025-01-11T12:00:00Z"
}
```

### Health Check Endpoints

```http
# Liveness probe (fast, no dependencies)
GET /health
{"status": "healthy"}

# Readiness probe (checks dependencies)
GET /ready
{
  "status": "ready",
  "checks": {
    "database": "ok",
    "redis": "ok"
  }
}
```

### Logging for Performance Analysis

```bash
# Enable structured logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Log slow queries (ms)
LOG_SLOW_QUERY_THRESHOLD=100

# Log slow requests (ms)
LOG_SLOW_REQUEST_THRESHOLD=200
```

Example log output:

```json
{
  "timestamp": "2025-01-11T12:00:00.000Z",
  "level": "warning",
  "message": "Slow request detected",
  "method": "GET",
  "path": "/api/v1/organizations/abc123/members",
  "duration_ms": 234.5,
  "status_code": 200
}
```

### Prometheus Metrics

If using Prometheus, these metrics are available:

```
# Request latency histogram
janua_http_request_duration_seconds_bucket{method="POST",path="/auth/signin",le="0.1"}

# Request counter
janua_http_requests_total{method="POST",path="/auth/signin",status="200"}

# Cache metrics
janua_cache_hits_total
janua_cache_misses_total
janua_cache_hit_rate

# Database connection pool
janua_db_connections_active
janua_db_connections_idle
janua_db_connections_pending
```

---

## Production Scaling

### Horizontal Scaling

Janua is designed for horizontal scaling:

```yaml
# Kubernetes deployment example
apiVersion: apps/v1
kind: Deployment
metadata:
  name: janua-api
spec:
  replicas: 3  # Start with 3 replicas
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  template:
    spec:
      containers:
      - name: janua-api
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "1000m"
```

### Scaling Guidelines

| Metric | Action Threshold | Scale Action |
|--------|------------------|--------------|
| CPU Usage | > 70% sustained | Add replicas |
| Memory Usage | > 80% | Add replicas or increase limits |
| Response Time P95 | > 200ms | Add replicas, optimize queries |
| Connection Pool Wait | > 1s | Increase pool size or replicas |
| Cache Hit Rate | < 70% | Increase Redis memory, review TTLs |

### Load Balancing

Recommended load balancer configuration:

```nginx
upstream janua_api {
    least_conn;  # Use least connections

    server api1.janua.local:4100;
    server api2.janua.local:4100;
    server api3.janua.local:4100;

    keepalive 32;  # Connection pooling
}

server {
    location /api/ {
        proxy_pass http://janua_api;

        # Connection reuse
        proxy_http_version 1.1;
        proxy_set_header Connection "";

        # Timeouts
        proxy_connect_timeout 5s;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
```

### Redis Clustering

For high availability Redis:

```bash
# Redis Sentinel for HA
REDIS_URL=redis+sentinel://sentinel1:26379,sentinel2:26379,sentinel3:26379/mymaster/0

# Or Redis Cluster
REDIS_URL=redis://node1:6379,node2:6379,node3:6379
```

---

## Troubleshooting Performance Issues

### Common Issues and Solutions

#### High Database Connection Wait Times

**Symptoms**: Requests timeout waiting for database connections

**Solutions**:
1. Increase `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW`
2. Check for connection leaks (unclosed sessions)
3. Optimize slow queries consuming connections
4. Add read replicas for read-heavy workloads

```bash
# Diagnose connection issues
psql -c "SELECT * FROM pg_stat_activity WHERE datname = 'janua';"
```

#### Low Cache Hit Rate

**Symptoms**: Cache hit rate below 70%, slow response times

**Solutions**:
1. Review and adjust TTL values
2. Ensure cache keys are consistent
3. Check Redis memory usage and eviction
4. Verify cache invalidation isn't too aggressive

```bash
# Check Redis memory
redis-cli INFO memory

# Check evicted keys
redis-cli INFO stats | grep evicted
```

#### Slow Authentication Endpoints

**Symptoms**: Login/signin takes > 100ms

**Solutions**:
1. Enable session caching
2. Optimize password hashing (reduce `BCRYPT_ROUNDS` if acceptable)
3. Cache user profiles
4. Use connection pooling

```bash
# Current bcrypt rounds
BCRYPT_ROUNDS=12  # ~250ms per hash

# Faster (but less secure)
BCRYPT_ROUNDS=10  # ~60ms per hash
```

#### Memory Growth

**Symptoms**: API memory usage grows over time

**Solutions**:
1. Check L1 cache size limits
2. Review for memory leaks in custom code
3. Ensure proper session cleanup
4. Monitor background task memory

```python
# Get L1 cache stats
from app.core.performance import cache_manager
stats = cache_manager.get_stats()
print(f"L1 cache entries: {stats['l1_cache_size']}")
```

### Performance Debugging Checklist

```markdown
[ ] Check response time headers (X-Response-Time)
[ ] Review slow query logs
[ ] Check cache hit rates
[ ] Verify connection pool utilization
[ ] Review error rates and types
[ ] Check Redis connection status
[ ] Verify database indexes exist
[ ] Monitor memory and CPU usage
[ ] Check network latency between services
[ ] Review recent deployments for regressions
```

### Performance Testing

Before production deployment, run load tests:

```bash
# Using wrk for load testing
wrk -t12 -c400 -d30s \
  -H "Authorization: Bearer $TOKEN" \
  https://api.janua.dev/api/v1/auth/me

# Using k6 for more detailed testing
k6 run --vus 100 --duration 30s performance-test.js
```

Example k6 test script:

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 100 },  // Ramp up
    { duration: '1m', target: 100 },   // Sustain
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<100'],  // 95% under 100ms
    http_req_failed: ['rate<0.01'],    // <1% errors
  },
};

export default function () {
  const response = http.get('https://api.janua.dev/api/v1/auth/me', {
    headers: { Authorization: `Bearer ${__ENV.TOKEN}` },
  });

  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 100ms': (r) => r.timings.duration < 100,
  });

  sleep(1);
}
```

---

## Quick Reference

### Environment Variables Summary

```bash
# Database
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_POOL_TIMEOUT=30

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_POOL_SIZE=10

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# JWT
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Security
BCRYPT_ROUNDS=12

# Logging
LOG_LEVEL=INFO
LOG_SLOW_QUERY_THRESHOLD=100
LOG_SLOW_REQUEST_THRESHOLD=200
```

### Performance Optimization Checklist

```markdown
**Database**
[ ] Connection pool sized appropriately
[ ] Key indexes created
[ ] Slow query logging enabled
[ ] pg_stat_statements extension enabled

**Caching**
[ ] Redis connected and configured
[ ] TTLs set appropriately
[ ] Cache invalidation implemented
[ ] Circuit breaker configured

**API**
[ ] Performance middleware enabled
[ ] Rate limiting configured
[ ] Response compression enabled
[ ] Connection keep-alive enabled

**Infrastructure**
[ ] Horizontal scaling configured
[ ] Health checks implemented
[ ] Monitoring dashboards created
[ ] Alerting thresholds set
```

---

## Related Documentation

- [Deployment Guide](../deployment/README.md)
- [Security Best Practices](./SECURITY_CHECKLIST.md)
- [Monitoring Setup](../operations/MONITORING.md)
- [Database Migration Guide](./database-migration.md)
