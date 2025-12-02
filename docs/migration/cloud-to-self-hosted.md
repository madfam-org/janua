# Janua Cloud → Self-Hosted Migration Guide ("Eject Button")

**Target Audience**: Organizations migrating from Janua managed cloud to self-hosted deployment
**Migration Time**: 2-4 hours (depending on data volume)
**Downtime**: Zero (with proper planning)
**Difficulty**: Intermediate

This guide provides a step-by-step process for migrating from Janua Cloud (managed) to self-hosted Janua OSS, preserving all user data, organizations, and configurations.

---

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Phase 1: Export Data](#phase-1-export-data)
- [Phase 2: Deploy Self-Hosted](#phase-2-deploy-self-hosted)
- [Phase 3: Import Data](#phase-3-import-data)
- [Phase 4: Cutover & Verification](#phase-4-cutover--verification)
- [Rollback Plan](#rollback-plan)
- [Troubleshooting](#troubleshooting)

---

## Overview

### What This Migration Includes

✅ **User Data**: All user profiles, authentication credentials, sessions
✅ **Organizations**: Multi-tenant data, team memberships, roles
✅ **Configuration**: MFA settings, SSO configs, webhooks, API keys
✅ **Audit Logs**: Activity history (subject to retention policy)
✅ **Custom Data**: Metadata, custom attributes, tags

### What This Migration Requires

- **Infrastructure**: Server/VM with Docker (see [requirements](#prerequisites))
- **Database**: PostgreSQL 15+ instance
- **DNS Access**: Ability to update DNS records
- **API Access**: Janua Cloud API key with export permissions

### Migration Strategy

We use a **zero-downtime dual-write approach**:

1. **Export** data from Janua Cloud
2. **Deploy** self-hosted instance in parallel
3. **Import** data to self-hosted
4. **Verify** data integrity
5. **Cutover** DNS to self-hosted
6. **Monitor** for 24-48 hours

---

## Prerequisites

### Infrastructure Requirements

**Minimum** (up to 1,000 users):
```yaml
Server Specs:
  - CPU: 2 cores
  - RAM: 4GB
  - Storage: 20GB SSD
  - Network: 100 Mbps

Software:
  - Docker 24.0+
  - Docker Compose 2.20+
  - PostgreSQL 15+ (self-hosted or managed)
  - Redis 7+ (self-hosted or managed)
```

**Recommended** (up to 10,000 users):
```yaml
Server Specs:
  - CPU: 4 cores
  - RAM: 8GB
  - Storage: 100GB SSD
  - Network: 1 Gbps

Software:
  - Same as minimum
  - Load balancer (optional)
  - Backup solution
```

### Required Access

- [ ] Janua Cloud API key with `export:all` permission
- [ ] DNS management access for your domain
- [ ] SSH access to target server
- [ ] SSL certificate for your domain (Let's Encrypt recommended)

### Before You Begin

**⚠️ Important Pre-Migration Steps**:

1. **Backup Existing Data**: Even though Janua Cloud retains data, create local backup
2. **Review Data Volume**: Check current user count and data size
3. **Schedule Downtime Window**: Optional but recommended (maintenance mode)
4. **Test Server Access**: Ensure SSH and Docker are working
5. **Notify Users**: Inform team about upcoming migration (if applicable)

---

## Phase 1: Export Data

### Step 1.1: Generate Export API Key

```bash
# Log in to Janua Cloud dashboard
https://cloud.janua.dev/dashboard

# Navigate to: Settings → API Keys → Create Export Key
# Permissions: export:users, export:organizations, export:audit_logs
# Copy the API key (starts with "janua_export_...")
```

### Step 1.2: Export User Data

```bash
# Export all users
curl -X POST https://api.janua.cloud/v1/export/users \
  -H "Authorization: Bearer janua_export_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "json",
    "include_credentials": true,
    "include_sessions": true,
    "include_mfa": true
  }' \
  -o janua_users_export.json

# Verify export
jq '.metadata' janua_users_export.json
# Should show: total_users, export_version, export_date
```

**Export Response Structure**:
```json
{
  "metadata": {
    "export_version": "2.0",
    "export_date": "2025-11-16T10:30:00Z",
    "total_users": 1523,
    "total_organizations": 45
  },
  "users": [
    {
      "id": "usr_...",
      "email": "user@example.com",
      "email_verified": true,
      "profile": { ... },
      "auth": {
        "password_hash": "...",
        "mfa_enabled": true,
        "mfa_secret": "...",
        "passkeys": [ ... ]
      },
      "organizations": [ ... ],
      "created_at": "2025-01-15T08:00:00Z"
    }
  ]
}
```

### Step 1.3: Export Organization Data

```bash
# Export all organizations
curl -X POST https://api.janua.cloud/v1/export/organizations \
  -H "Authorization: Bearer janua_export_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "format": "json",
    "include_members": true,
    "include_roles": true,
    "include_sso_configs": true
  }' \
  -o janua_organizations_export.json

# Verify export
jq '.metadata' janua_organizations_export.json
```

### Step 1.4: Export Configuration

```bash
# Export webhooks, API keys, SSO configs
curl -X POST https://api.janua.cloud/v1/export/config \
  -H "Authorization: Bearer janua_export_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -o janua_config_export.json

# Verify export
jq '.metadata' janua_config_export.json
```

### Step 1.5: Create Encrypted Archive

```bash
# Combine all exports into encrypted archive
tar czf - janua_*_export.json | \
  openssl enc -aes-256-cbc -pbkdf2 -out janua_export.tar.gz.enc

# Enter encryption password when prompted
# Store password securely (you'll need it for import)

# Verify archive
ls -lh janua_export.tar.gz.enc
```

---

## Phase 2: Deploy Self-Hosted

### Step 2.1: Clone Janua Repository

```bash
# SSH into your target server
ssh user@your-server.com

# Clone Janua repository
git clone https://github.com/madfam-io/janua.git
cd janua

# Checkout latest stable release
git checkout v1.0.0  # Replace with latest version
```

### Step 2.2: Configure Environment

```bash
# Copy production environment template
cp .env.production.example .env.production

# Generate secure secrets
export SECRET_KEY=$(openssl rand -hex 32)
export JWT_PRIVATE_KEY=$(openssl genrsa 2048)
export DATABASE_PASSWORD=$(openssl rand -base64 32)
export REDIS_PASSWORD=$(openssl rand -base64 32)

# Edit environment file
nano .env.production
```

**Required Environment Variables**:
```bash
# Database
DATABASE_URL=postgresql://janua:${DATABASE_PASSWORD}@postgres:5432/janua_production

# Redis
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

# Security
SECRET_KEY=${SECRET_KEY}
JWT_PRIVATE_KEY=${JWT_PRIVATE_KEY}

# Application
APP_NAME=Janua
DOMAIN=auth.yourdomain.com
FRONTEND_URL=https://auth.yourdomain.com
ENVIRONMENT=production

# Email (configure your provider)
EMAIL_PROVIDER=resend  # or sendgrid, postmark, ses
EMAIL_FROM=noreply@yourdomain.com
RESEND_API_KEY=your_resend_key

# Optional: Object Storage
STORAGE_PROVIDER=s3  # or r2, gcs, local
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
AWS_BUCKET=janua-uploads
```

### Step 2.3: Deploy with Docker Compose

```bash
# Deploy Janua stack
docker-compose -f deployment/docker-compose.production.yml up -d

# Check service health
docker-compose ps

# Should show:
# - janua-api (healthy)
# - janua-postgres (healthy)
# - janua-redis (healthy)
```

### Step 2.4: Run Database Migrations

```bash
# Run migrations
docker-compose exec api alembic upgrade head

# Verify database schema
docker-compose exec postgres psql -U janua -d janua_production -c "\dt"

# Should show all Janua tables:
# - users
# - organizations
# - sessions
# - passkeys
# - sso_configurations
# - audit_logs
# etc.
```

### Step 2.5: Verify API Health

```bash
# Check API health endpoint
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "version": "1.0.0"
}
```

---

## Phase 3: Import Data

### Step 3.1: Transfer Export Archive

```bash
# From your local machine, transfer export to server
scp janua_export.tar.gz.enc user@your-server.com:~/janua/

# SSH into server
ssh user@your-server.com
cd janua
```

### Step 3.2: Decrypt and Extract

```bash
# Decrypt archive
openssl enc -aes-256-cbc -pbkdf2 -d -in janua_export.tar.gz.enc | tar xzf -

# Verify extracted files
ls -lh janua_*_export.json
```

### Step 3.3: Run Import Script

```bash
# Run import script (included in Janua repo)
docker-compose exec api python scripts/import_from_cloud.py \
  --users janua_users_export.json \
  --organizations janua_organizations_export.json \
  --config janua_config_export.json \
  --verify-integrity

# Expected output:
# ✅ Validating export files...
# ✅ Importing 1523 users...
# ✅ Importing 45 organizations...
# ✅ Importing 12 SSO configurations...
# ✅ Importing 234 webhooks...
# ✅ Verifying data integrity...
# ✅ Import completed successfully!
#
# Summary:
#   Users: 1523 imported, 0 failed
#   Organizations: 45 imported, 0 failed
#   SSO Configs: 12 imported, 0 failed
#   Webhooks: 234 imported, 0 failed
```

### Step 3.4: Verify Data Import

```bash
# Verify user count
docker-compose exec api python -c "
from app.database import AsyncSessionLocal
from app.models import User
from sqlalchemy import select

async def count_users():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        print(f'Total users: {len(users)}')

import asyncio
asyncio.run(count_users())
"

# Should match export count (1523)
```

### Step 3.5: Test Authentication Flows

```bash
# Test user login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "existing_password"
  }'

# Should return JWT token and user data
```

---

## Phase 4: Cutover & Verification

### Step 4.1: Configure SSL/TLS

```bash
# Install Certbot for Let's Encrypt
sudo apt-get install certbot

# Generate SSL certificate
sudo certbot certonly --standalone \
  -d auth.yourdomain.com \
  --email admin@yourdomain.com \
  --agree-tos

# Update nginx/caddy configuration with certificate paths
```

### Step 4.2: Update DNS Records

**Before DNS Update**:
```
auth.yourdomain.com → Janua Cloud (1.2.3.4)
```

**After DNS Update**:
```
auth.yourdomain.com → Your Server (5.6.7.8)
```

**DNS Update Steps**:
1. Lower TTL to 60 seconds (1 hour before cutover)
2. Update A record to point to your server IP
3. Wait for DNS propagation (check with `dig auth.yourdomain.com`)
4. Monitor traffic switching

### Step 4.3: Enable Production Mode

```bash
# Update environment to production
nano .env.production

# Set:
ENVIRONMENT=production
DEBUG=false

# Restart services
docker-compose restart api
```

### Step 4.4: Monitor Cutover

```bash
# Watch API logs
docker-compose logs -f api

# Monitor authentication requests
watch -n 5 'docker-compose exec api python -c "
from app.database import AsyncSessionLocal
from app.models import Session
from sqlalchemy import select, desc
from datetime import datetime, timedelta

async def recent_logins():
    async with AsyncSessionLocal() as session:
        since = datetime.utcnow() - timedelta(minutes=5)
        result = await session.execute(
            select(Session)
            .where(Session.created_at > since)
            .order_by(desc(Session.created_at))
        )
        sessions = result.scalars().all()
        print(f'Logins in last 5 minutes: {len(sessions)}')

import asyncio
asyncio.run(recent_logins())
"'
```

### Step 4.5: Verification Checklist

**Critical Checks (First Hour)**:
- [ ] Users can log in with existing credentials
- [ ] MFA codes work (TOTP, SMS, passkeys)
- [ ] SSO authentication flows work (SAML, OIDC)
- [ ] Organization switching works
- [ ] API endpoints respond correctly
- [ ] Webhooks fire correctly
- [ ] Email notifications send

**Extended Checks (First 24 Hours)**:
- [ ] Session persistence works
- [ ] Password reset flows work
- [ ] User profile updates work
- [ ] Team invitations work
- [ ] Audit logs record events
- [ ] No authentication errors in logs

**Performance Checks**:
- [ ] API response times < 200ms (p95)
- [ ] Database queries optimized
- [ ] Redis cache hit rate > 80%
- [ ] CPU usage < 50%
- [ ] Memory usage stable

---

## Rollback Plan

If issues arise during cutover, follow this rollback procedure:

### Quick Rollback (< 5 minutes)

```bash
# 1. Revert DNS to Janua Cloud
# Update A record: auth.yourdomain.com → Janua Cloud IP

# 2. Wait for DNS propagation
dig auth.yourdomain.com

# 3. Verify traffic flowing to Janua Cloud
# Check Janua Cloud dashboard for incoming requests

# 4. Your self-hosted instance remains available for debugging
```

### Investigation

```bash
# Check API logs for errors
docker-compose logs api | grep ERROR

# Check database connectivity
docker-compose exec postgres psql -U janua -d janua_production -c "SELECT COUNT(*) FROM users;"

# Check Redis connectivity
docker-compose exec redis redis-cli PING

# Test authentication manually
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "test_password"}'
```

---

## Troubleshooting

### Issue: Users Can't Log In

**Symptoms**: Login returns 401 Unauthorized

**Diagnosis**:
```bash
# Check if user exists
docker-compose exec api python -c "
from app.database import AsyncSessionLocal
from app.models import User
from sqlalchemy import select

async def check_user():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == 'test@example.com')
        )
        user = result.scalar_one_or_none()
        if user:
            print(f'User found: {user.id}')
            print(f'Email verified: {user.email_verified}')
        else:
            print('User not found')

import asyncio
asyncio.run(check_user())
"
```

**Solutions**:
- [ ] Verify user data imported correctly
- [ ] Check password hash format compatibility
- [ ] Ensure JWT_PRIVATE_KEY is configured correctly
- [ ] Verify database migrations ran successfully

---

### Issue: MFA Codes Don't Work

**Symptoms**: TOTP codes rejected as invalid

**Diagnosis**:
```bash
# Check server time synchronization
date -u
# Should match current UTC time

# Install NTP if time is off
sudo apt-get install ntp
sudo systemctl start ntp
sudo systemctl enable ntp
```

**Solutions**:
- [ ] Ensure server time is synchronized (NTP)
- [ ] Verify MFA secrets imported correctly
- [ ] Check time drift (max 30 seconds allowed)
- [ ] Test with multiple TOTP codes

---

### Issue: SSO Authentication Fails

**Symptoms**: SAML/OIDC redirects fail or error

**Diagnosis**:
```bash
# Check SSO configuration imported
docker-compose exec api python -c "
from app.database import AsyncSessionLocal
from app.models import SSOConfiguration
from sqlalchemy import select

async def check_sso():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(SSOConfiguration))
        configs = result.scalars().all()
        print(f'SSO configs: {len(configs)}')
        for config in configs:
            print(f'  - {config.provider_name} ({config.protocol})')

import asyncio
asyncio.run(check_sso())
"
```

**Solutions**:
- [ ] Update SSO redirect URLs in IdP (point to new domain)
- [ ] Verify SSL certificates valid
- [ ] Check DOMAIN and FRONTEND_URL environment variables
- [ ] Test SAML assertion endpoint: `/api/v1/sso/saml/acs`

---

### Issue: High Memory Usage

**Symptoms**: Server running out of memory

**Diagnosis**:
```bash
# Check memory usage
docker stats

# Check for memory leaks
docker-compose exec api python -c "
import psutil
print(f'Memory: {psutil.virtual_memory().percent}%')
print(f'CPU: {psutil.cpu_percent()}%')
"
```

**Solutions**:
- [ ] Increase server RAM
- [ ] Enable Redis cache for sessions
- [ ] Optimize database query patterns
- [ ] Reduce worker count if needed
- [ ] Enable connection pooling

---

## Post-Migration Tasks

### Week 1: Monitoring

- [ ] Monitor API response times daily
- [ ] Check error rates in logs
- [ ] Verify backup automation working
- [ ] Test disaster recovery procedure
- [ ] Document any custom configurations

### Week 2-4: Optimization

- [ ] Tune database performance (indexes, query optimization)
- [ ] Optimize Redis cache hit rates
- [ ] Set up monitoring/alerting (Prometheus, Grafana, DataDog)
- [ ] Configure log aggregation (ELK, Loki, CloudWatch)
- [ ] Load test for peak capacity

### Ongoing

- [ ] Schedule regular backups (daily database dumps)
- [ ] Plan for Janua version upgrades
- [ ] Review and optimize infrastructure costs
- [ ] Consider high-availability setup (multi-region, load balancing)

---

## Cost Comparison: Janua Cloud vs Self-Hosted

**Janua Cloud (Professional - 10,000 MAU)**:
```
Monthly Cost: $99/mo
Annual Cost: $1,188/year
```

**Self-Hosted (10,000 MAU)**:
```
Server (4 cores, 8GB RAM): $40-80/mo
PostgreSQL (managed): $25-50/mo
Redis (managed): $15-30/mo
SSL Certificate (Let's Encrypt): $0/mo
Backups (S3): $5-10/mo
------------------------
Total Monthly: $85-170/mo
Annual Cost: $1,020-2,040/year

Savings: $0-$168/year (similar cost but full control)
```

**Self-Hosted (100,000 MAU)**:
```
Server (8 cores, 16GB RAM): $160-300/mo
PostgreSQL (managed): $100-200/mo
Redis (managed): $50-80/mo
Load Balancer: $20-40/mo
Backups (S3): $20-30/mo
------------------------
Total Monthly: $350-650/mo
Annual Cost: $4,200-7,800/year

vs Janua Cloud Enterprise: $2,000-5,000/mo ($24,000-60,000/year)
Savings: $16,200-$52,200/year (67-87% cost reduction)
```

---

## Support & Resources

**Self-Hosting Community**:
- GitHub Discussions: https://github.com/madfam-io/janua/discussions
- Discord Server: https://discord.gg/janua
- Documentation: https://docs.janua.dev

**Professional Migration Support**:
- Email: migration@janua.dev
- Enterprise Support: enterprise@janua.dev (for paid migration assistance)

**Related Guides**:
- [Production Deployment Guide](../DEPLOYMENT.md)
- [Database Migration Guide](../enterprise/migration-data-portability.md)
- [Backup & Disaster Recovery](../deployment/backup-recovery.md)

---

## Appendix: Import Script Usage

The `scripts/import_from_cloud.py` script supports additional options:

```bash
python scripts/import_from_cloud.py \
  --users janua_users_export.json \
  --organizations janua_organizations_export.json \
  --config janua_config_export.json \
  --verify-integrity \
  --dry-run  # Test import without committing
  --batch-size 100  # Import in batches of 100
  --skip-existing  # Skip users/orgs that already exist
  --log-level DEBUG  # Verbose logging
```

**Dry Run Mode**:
```bash
# Test import without making changes
python scripts/import_from_cloud.py \
  --users janua_users_export.json \
  --dry-run

# Output shows what WOULD be imported
```

---

**Migration completed successfully? Welcome to self-hosted Janua! You now have complete control over your authentication infrastructure with zero vendor lock-in.** 🎉
