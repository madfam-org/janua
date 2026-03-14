# Solarpunk Foundry Infrastructure Reference Guide

> **Layer 1: "The Soil"** - Foundation infrastructure for the MADFAM ecosystem

**Document Version**: 1.0
**Last Updated**: 2025-12-02
**Classification**: Internal Operations

---

## Table of Contents

1. [Hardware Specifications](#1-hardware-specifications-the-bedrock)
2. [OS & Storage Architecture](#2-os--storage-architecture-the-soil)
3. [Container Engine](#3-the-container-engine)
4. [Application Layer](#4-application-layer-the-organs)
5. [Security & Fixes Log](#5-security--fixes-log-tribal-knowledge)
6. [Port Allocation](#6-port-allocation)
7. [Maintenance Procedures](#7-maintenance-procedures)

---

## 1. Hardware Specifications ("The Bedrock")

### Server Details

| Specification | Value | Rationale |
|---------------|-------|-----------|
| **Model** | Hetzner dedicated server | Optimal cost-to-performance ratio |
| **Location** | Finland (HEL1) | Green energy profile, EU data residency |
| **Hostname** | `enclii-core` | Primary infrastructure node |
| **IP Address** | `<CONTROL_PLANE_IP>` | Static IPv4 |

### Compute Resources

| Component | Specification | Selection Rationale |
|-----------|---------------|---------------------|
| **CPU** | <CPU_MODEL> | High single-core performance for auth handshakes |
| **RAM** | 64 GB ECC DDR4 | ECC prevents bit-rot/corruption in treasury ledger and identity tables |
| **Storage** | 2x 512 GB NVMe SSD | High IOPS for container builds |

> **Critical Note**: ECC memory was specifically chosen to ensure data integrity for:
> - Dhanam treasury ledger transactions
> - Janua identity and session tables
> - PostgreSQL WAL consistency

---

## 2. OS & Storage Architecture ("The Soil")

### Operating System

| Property | Value |
|----------|-------|
| **Distribution** | Ubuntu 24.04 LTS |
| **Kernel** | Linux 6.x |
| **Init System** | systemd |

### Partitioning Strategy: "Trojan Horse" Method

Standard Hetzner provisioning requires ext4 partitions. We employed a post-installation conversion:

```
1. Install via `installimage` with standard ext4 partitions (passes validation)
2. Boot into installed system
3. Destroy data partition
4. Replace with ZFS pool
```

### ZFS Pool Configuration

**Pool Name**: `rpool`
**Topology**: Mirror (RAID 1)
**Self-Healing**: Enabled via checksumming

```bash
# Pool status verification
zpool status rpool
```

### Dataset Configuration ("Biological Datasets")

Each dataset is tuned for its specific workload characteristics:

| Dataset | Mount Point | Configuration | Rationale |
|---------|-------------|---------------|-----------|
| `rpool/data/postgres` | `/data/postgres` | `recordsize=16k`, `atime=off`, `logbias=latency` | Aligned to PostgreSQL 16KB page size; prevents write amplification |
| `rpool/data/builds` | `/data/builds` | `compression=lz4` | High compression ratio for build artifacts and text logs |
| `rpool/data/assets` | `/data/assets` | `quota=150G` | Hard cap prevents asset uploads from starving system |
| `rpool/data/registry` | `/data/registry` | `compression=lz4` | Docker registry layer deduplication |

### ZFS Dataset Creation Reference

```bash
# PostgreSQL - Optimized for database workloads
zfs create -o recordsize=16k -o atime=off -o logbias=latency rpool/data/postgres

# Build artifacts - High compression
zfs create -o compression=lz4 rpool/data/builds

# Media assets - Quota-limited
zfs create -o quota=150G rpool/data/assets

# Docker registry - Compressed with dedup potential
zfs create -o compression=lz4 rpool/data/registry
```

### ZFS Advantages for This Deployment

1. **Self-Healing**: Automatic detection and correction of silent data corruption
2. **Instant Snapshots**: Sub-second backup points for rollback capability
3. **Copy-on-Write**: Safe updates without risk of partial writes
4. **Native Compression**: Reduced storage footprint for logs and builds
5. **Docker Integration**: Native ZFS storage driver for efficient container layers

---

## 3. The Container Engine

### Runtime Configuration

| Component | Value |
|-----------|-------|
| **Runtime** | Docker Engine |
| **Orchestration** | Docker Compose |
| **Storage Driver** | ZFS (Native) |

### Docker Daemon Configuration

**File**: `/etc/docker/daemon.json`

```json
{
  "storage-driver": "zfs",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "default-address-pools": [
    {
      "base": "172.18.0.0/16",
      "size": 24
    }
  ]
}
```

### ZFS Storage Driver Benefits

- **Instant Container Creation**: Copy-on-write cloning
- **Layer Deduplication**: Shared base images consume minimal space
- **Snapshot Integration**: Container state can be snapshotted with ZFS
- **Performance**: Native filesystem operations without overlay overhead

### Network Configuration

| Network | Subnet | Purpose |
|---------|--------|---------|
| `janua-network` | `172.18.2.0/24` | Janua services internal communication |
| `enclii-network` | `172.18.3.0/24` | Enclii PaaS services |
| `shared-network` | `172.18.1.0/24` | Cross-project shared services |

---

## 4. Application Layer ("The Organs")

### Shared Infrastructure Services

| Service | Container | Port | Volume Mount |
|---------|-----------|------|--------------|
| PostgreSQL | `postgres-shared` | 5432 | `/data/postgres` |
| Redis | `redis-shared` | 6379 | `/data/redis` |

### Janua (Identity & Authentication)

**Purpose**: OAuth2/OIDC identity platform for the MADFAM ecosystem

| Component | Container | Port | Domain |
|-----------|-----------|------|--------|
| API | `janua-api` | 4100 | `api.janua.dev` |
| Dashboard | `janua-dashboard` | 4101 | `app.janua.dev` |
| Admin | `janua-admin` | 4102 | `admin.janua.dev` |
| Docs | `janua-docs` | 4103 | `docs.janua.dev` |
| Website | `janua-website` | 4104 | `janua.dev` |

**Database**: `janua_prod` on `postgres-shared`

### Enclii (PaaS Platform)

**Purpose**: Container deployment and management platform

| Component | Container | Port | Volume Mount |
|-----------|-----------|------|--------------|
| Core | `enclii-core` | 4200 | - |
| Registry | `enclii-registry` | 4201 | `/data/registry` |
| Builder | `enclii-builder` | - | `/data/builds` |

### Inter-Service Communication

```
┌─────────────────────────────────────────────────────────────┐
│                    Cloudflare Edge                          │
│              (DNS + WAF + DDoS Protection)                  │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              Cloudflare Tunnel (cloudflared)                │
│                  Zero-Trust Ingress                         │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                   Docker Networks                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Janua     │  │   Enclii    │  │   Shared    │         │
│  │  Network    │  │  Network    │  │  Services   │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┴────────────────┘                 │
│                          │                                  │
│              ┌───────────▼───────────┐                      │
│              │   postgres-shared     │                      │
│              │   redis-shared        │                      │
│              └───────────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Security & Fixes Log (Tribal Knowledge)

### Firewall Configuration (UFW)

**Policy**: Default Deny Incoming

```bash
# Current ruleset
ufw status verbose

# Standard configuration
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp    # HTTP (Cloudflare)
ufw allow 443/tcp   # HTTPS (Cloudflare)
```

> **Note**: Application ports (4100-4199, 4200-4299) are NOT exposed directly.
> All traffic routes through Cloudflare Tunnel.

### CORS Configuration Fix

**Issue**: Dashboard unable to communicate with API
**Symptom**: CORS preflight failures in browser console

**Resolution**: Added Dashboard origin to API CORS configuration

```python
# apps/api/app/main.py
CORS_ORIGINS = [
    "https://janua.dev",
    "https://app.janua.dev",      # Dashboard
    "https://admin.janua.dev",    # Admin panel
    "https://api.janua.dev",
]
```

### Content Security Policy Fix

**Issue**: Swagger UI documentation page blank
**Symptom**: CSP blocking CDN resources for Swagger UI

**Resolution**: Updated CSP headers to allow Swagger UI CDN sources

```python
# Security headers middleware
"script-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
"style-src": "'self' 'unsafe-inline' https://cdn.jsdelivr.net",
```

### TrustedHostMiddleware Fix

**Issue**: Container-to-container communication blocked
**Symptom**: Dashboard API routes returning 400 Bad Request

**Resolution**: Added Docker internal hostnames to allowed hosts

```python
# apps/api/app/main.py
allowed_hosts = [
    "janua.dev",
    "*.janua.dev",
    "localhost",
    "127.0.0.1",
    # Docker internal hostnames
    "janua-api",
    "janua-api:8000",
]
```

### The Key Ceremony (Admin Bootstrap)

**Incident**: Initial admin user creation via direct SQL injection caused authentication failures

**Root Cause**:
- Direct SQL `INSERT` used system `crypt()` function
- Application expects `bcrypt` hash with specific salt/rounds format
- Hash format mismatch caused 500 errors on login

**Resolution**:
1. Deleted malformed admin user from database
2. Recreated admin via application's internal Python logic:

```python
from app.services.user_service import UserService
from app.database import get_db_session

async with get_db_session() as db:
    admin = await UserService.create(
        db,
        email="admin@janua.dev",
        password="<secure-password>",  # From Bitwarden
        is_admin=True
    )
```

**Current State**: Admin credentials secured in Bitwarden vault

### Database Permissions Fix

**Issue**: API returning DATABASE_ERROR on queries
**Root Cause**: Tables owned by `postgres` user, `janua` user lacked permissions

**Resolution**:
```sql
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO janua;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO janua;
```

---

## 6. Port Allocation

### MADFAM Ecosystem Port Blocks

| Block | Range | Project |
|-------|-------|---------|
| 4100-4199 | Janua | Identity & Authentication |
| 4200-4299 | Enclii | PaaS Platform |
| 4300-4399 | Dhanam | Treasury & Payments |
| 4400-4499 | Avala | Analytics |
| 4500-4599 | Reserved | Future projects |

### Janua Port Assignments

| Port | Service | Container |
|------|---------|-----------|
| 4100 | API | `janua-api` |
| 4101 | Dashboard | `janua-dashboard` |
| 4102 | Admin | `janua-admin` |
| 4103 | Docs | `janua-docs` |
| 4104 | Website | `janua-website` |
| 4105 | Demo | `janua-demo` |
| 4110 | Email Worker | `janua-worker-email` |
| 4120 | WebSocket | `janua-ws` |
| 4190 | Metrics | `janua-metrics` |

---

## 7. Maintenance Procedures

### ZFS Health Check

```bash
# Check pool status
zpool status rpool

# Check for errors
zpool status -x

# Scrub (monthly recommended)
zpool scrub rpool
```

### ZFS Snapshots

```bash
# Create snapshot
zfs snapshot rpool/data/postgres@$(date +%Y%m%d-%H%M%S)

# List snapshots
zfs list -t snapshot

# Rollback (CAUTION: destroys newer data)
zfs rollback rpool/data/postgres@<snapshot-name>
```

### Container Management

```bash
# View all Janua containers
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep janua

# View logs
docker logs janua-api --tail 100 -f

# Restart service
docker restart janua-api

# Rebuild and deploy
cd /opt/solarpunk/janua
git pull origin main
docker build -f apps/api/Dockerfile -t janua-api:latest apps/api/
docker stop janua-api && docker rm janua-api
docker run -d --name janua-api --network janua-network \
  -p 4100:8000 --env-file .env.production \
  --restart unless-stopped janua-api:latest
```

### Backup Procedures

```bash
# PostgreSQL logical backup
docker exec postgres-shared pg_dump -U janua janua_prod > backup.sql

# ZFS snapshot (preferred - instant, consistent)
zfs snapshot rpool/data/postgres@backup-$(date +%Y%m%d)

# Send snapshot to remote (disaster recovery)
zfs send rpool/data/postgres@backup-20251202 | ssh backup-server zfs recv backup/postgres
```

### Emergency Contacts

| Role | Contact | Scope |
|------|---------|-------|
| Infrastructure | Enclii alerts | Server, network, storage |
| Application | Janua logs | Auth, API, dashboard |
| Security | Bitwarden vault | Credentials, secrets |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-12-02 | Claude/MADFAM | Initial documentation |

---

*Solarpunk Foundry - Building sustainable digital infrastructure*
