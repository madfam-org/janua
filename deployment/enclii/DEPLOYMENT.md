# Janua Deployment Guide for Enclii

> [!IMPORTANT]
> MADFAM-ENCLII-FIRST-LEGACY-RAW v1: This document contains legacy raw infrastructure command examples.
> Routine production operations must use Enclii web, API, or CLI. Treat raw
> `kubectl`, `helm`, SSH, provider CLI/API, `docker exec`, and direct container
> access as platform bootstrap or documented break-glass only, and record any
> missing Enclii adapter gap.


This guide covers deploying Janua authentication platform using Enclii, MADFAM's DevOps solution.

## Prerequisites

- Docker 24.0+ installed
- Access to Enclii platform
- Cloudflare tunnel configured for domains
- SSL certificates (managed by Cloudflare)

## Quick Start

```bash
# 1. Clone and navigate to deployment
cd /opt/solarpunk/janua
git clone https://github.com/madfam-org/janua.git .
cd deployment/enclii

# 2. Configure environment
cp .env.example .env
nano .env  # Fill in your secrets

# 3. Deploy with Enclii
enclii deploy --manifest enclii.yaml

# Or with Docker Compose directly
docker-compose -f docker-compose.prod.yml up -d
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Cloudflare Tunnel                           │
│  janua.dev → 4104    admin.janua.dev → 4102                    │
│  api.janua.dev → 4100    app.janua.dev → 4101                  │
│  docs.janua.dev → 4103                                          │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                      Host Server                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ janua-api   │ │janua-dash   │ │janua-admin  │               │
│  │   :4100     │ │   :4101     │ │   :4102     │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│  ┌─────────────┐ ┌─────────────┐                               │
│  │ janua-docs  │ │janua-website│                               │
│  │   :4103     │ │   :4104     │                               │
│  └─────────────┘ └─────────────┘                               │
│                                                                  │
│  ┌─────────────┐ ┌─────────────┐                               │
│  │  postgres   │ │    redis    │                               │
│  │   :5432     │ │    :6379    │                               │
│  └─────────────┘ └─────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

## Port Allocation (MADFAM Standard)

| Port | Service | Domain | Description |
|------|---------|--------|-------------|
| 4100 | janua-api | api.janua.dev | FastAPI backend |
| 4101 | janua-dashboard | app.janua.dev | User dashboard |
| 4102 | janua-admin | admin.janua.dev | Admin panel |
| 4103 | janua-docs | docs.janua.dev | Documentation |
| 4104 | janua-website | janua.dev | Marketing site |

## Files

```
deployment/enclii/
├── docker-compose.prod.yml   # Docker Compose for Enclii
├── enclii.yaml               # Enclii service manifest
├── .env.example              # Environment template
├── .env                      # Your secrets (gitignored)
└── DEPLOYMENT.md             # This file
```

## Configuration

### Environment Variables

Required secrets (store in `.env` or Vault):

```bash
# Database
DATABASE_URL=postgresql://janua:PASSWORD@localhost:5432/janua
POSTGRES_PASSWORD=<secure-password>

# Redis
REDIS_URL=redis://:PASSWORD@localhost:6379/0
REDIS_PASSWORD=<secure-password>

# Security Keys
JWT_SECRET_KEY=<64-char-hex>        # openssl rand -hex 64
SECRET_KEY=<32-char-hex>             # openssl rand -hex 32
INTERNAL_API_KEY=<random-string>

# Email
RESEND_API_KEY=re_xxx               # MADFAM centralized email
```

### Generate Secrets

```bash
# JWT Secret (64 hex chars = 256 bits)
openssl rand -hex 64

# Application Secret
openssl rand -hex 32

# Database Password (alphanumeric, 32 chars)
openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32
```

## Operations

### Deploy All Services

```bash
# Enclii
enclii deploy --manifest enclii.yaml

# Docker Compose
docker-compose -f docker-compose.prod.yml up -d
```

### Update Single Service

```bash
# Enclii
enclii deploy --service janua-api

# Docker Compose
docker-compose -f docker-compose.prod.yml up -d --no-deps janua-api
```

### View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Single service
docker logs -f janua-api

# Filter by tag
docker logs janua-api 2>&1 | grep ERROR
```

### Check Health

```bash
# All containers
docker ps --format "table {{.Names}}\t{{.Status}}"

# Specific endpoints
curl -s http://localhost:4100/ | head -1    # API
curl -s http://localhost:4101/ | head -1    # Dashboard
curl -s http://localhost:4102/ | head -1    # Admin
curl -s http://localhost:4103/ | head -1    # Docs
curl -s http://localhost:4104/ | head -1    # Website
```

### Rollback

```bash
# Enclii (automatic on failure)
enclii rollback --service janua-api

# Docker (manual)
docker stop janua-api
docker run -d --name janua-api janua/api:previous-tag
```

## Monitoring

### Health Check Endpoints

All services expose root path (`/`) for health checks:

```bash
# API returns JSON response
curl http://localhost:4100/

# Next.js apps return HTML
curl -I http://localhost:4101/
```

### Prometheus Metrics

API exposes metrics at `/metrics` (port 4190 if configured).

### Log Aggregation

Logs are JSON-formatted with tags for Loki/Grafana:

```json
{"time":"2025-12-05T12:00:00Z","level":"info","msg":"Request processed","tag":"janua-api"}
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs janua-api --tail 50

# Check health
docker inspect --format='{{.State.Health.Status}}' janua-api

# Check ports
lsof -i :4100
```

### Health Check Failing

1. Verify internal port matches health check:
   ```yaml
   environment:
     - PORT=4100  # Must match healthcheck port
   healthcheck:
     test: ["CMD", "wget", "...", "http://localhost:4100/"]
   ```

2. Wait for start period (60s for Next.js cold starts)

3. Check if app is binding to 0.0.0.0:
   ```yaml
   environment:
     - HOSTNAME=0.0.0.0  # Required for host network
   ```

### Database Connection Issues

```bash
# Check postgres is running
docker logs janua-postgres

# Test connection
docker exec janua-postgres pg_isready -U janua

# Check DATABASE_URL format
# postgresql://USER:PASSWORD@HOST:PORT/DATABASE
```

### Cloudflare Tunnel Issues

```bash
# Check tunnel status
cloudflared tunnel list

# Test local port
curl -I http://localhost:4100/

# Check DNS resolution
dig api.janua.dev
```

## Security Checklist

- [ ] Strong passwords (32+ chars) for PostgreSQL and Redis
- [ ] JWT secret is 256 bits (64 hex chars)
- [ ] Admin panel has IP whitelist or additional auth
- [ ] Environment file has restrictive permissions (600)
- [ ] Secrets not committed to git
- [ ] Backups configured for postgres_data volume

## Maintenance

### Backup Database

```bash
docker exec janua-postgres pg_dump -U janua janua > backup.sql
```

### Restore Database

```bash
cat backup.sql | docker exec -i janua-postgres psql -U janua janua
```

### Update Images

```bash
# Pull latest
docker-compose -f docker-compose.prod.yml pull

# Recreate with new images
docker-compose -f docker-compose.prod.yml up -d --force-recreate
```

### Clean Old Images

```bash
docker image prune -a --filter "until=168h"  # Remove images older than 1 week
```

## Support

- Documentation: https://docs.janua.dev
- Issues: https://github.com/madfam-org/janua/issues
- Enclii: https://enclii.madfam.io
