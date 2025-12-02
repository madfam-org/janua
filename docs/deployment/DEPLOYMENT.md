# Janua Production Deployment Guide

> **Self-Hosted on Hetzner via Enclii Infrastructure**

This guide covers deploying Janua to production using MADFAM's self-hosted infrastructure on Hetzner bare metal servers with Cloudflare Tunnel for zero-trust ingress.

---

## Architecture Overview

```
                              ┌─────────────────────────────────────┐
                              │         Cloudflare Edge             │
                              │     (DNS + WAF + DDoS Protection)   │
                              └──────────────┬──────────────────────┘
                                             │
                              ┌──────────────▼──────────────────────┐
                              │       Cloudflare Tunnel (cloudflared)│
                              │         Zero-Trust Ingress          │
                              └──────────────┬──────────────────────┘
                                             │
┌────────────────────────────────────────────▼────────────────────────────────────┐
│                           Hetzner Bare Metal Server                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        Docker Compose Stack                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │   │
│  │  │  janua-api   │  │janua-dashboard│  │janua-website │  │ janua-docs │  │   │
│  │  │   :4100      │  │    :4101      │  │    :4104     │  │   :4103    │  │   │
│  │  │  (FastAPI)   │  │  (Next.js)    │  │  (Next.js)   │  │ (Next.js)  │  │   │
│  │  └──────┬───────┘  └──────┬────────┘  └──────────────┘  └────────────┘  │   │
│  │         │                 │                                              │   │
│  │         │    INTERNAL_API_URL (http://janua-api:8000)                   │   │
│  │         │                 │                                              │   │
│  │  ┌──────▼─────────────────▼──────────────────────────────────────────┐  │   │
│  │  │                    Docker Internal Network                         │  │   │
│  │  └────────────────────────────────────────────────────────────────────┘  │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │   │
│  │  │  PostgreSQL  │  │    Redis     │  │  Prometheus  │                   │   │
│  │  │    :5432     │  │    :6379     │  │    :4190     │                   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## Port Allocation (MADFAM Standard)

Per [MADFAM Ecosystem Port Standard](https://github.com/madfam-io/solarpunk-foundry/blob/main/docs/PORT_ALLOCATION.md), Janua uses the **4100-4199 block**:

| Service | Port | Container Name | Public Domain |
|---------|------|----------------|---------------|
| API | 4100 | janua-api | api.janua.dev |
| Dashboard | 4101 | janua-dashboard | app.janua.dev |
| Admin | 4102 | janua-admin | admin.janua.dev |
| Docs | 4103 | janua-docs | docs.janua.dev |
| Website | 4104 | janua-website | janua.dev |
| Demo | 4105 | janua-demo | demo.janua.dev |
| Email Worker | 4110 | janua-worker-email | - |
| WebSocket | 4120 | janua-ws | - |
| Metrics | 4190 | janua-metrics | - |

---

## Prerequisites

### Server Requirements
- Hetzner dedicated server or VPS (minimum 4 vCPU, 8GB RAM)
- Ubuntu 22.04 LTS or newer
- Docker 24+ and Docker Compose v2
- Git

### Domain Configuration
- Cloudflare account with janua.dev domain
- Cloudflare Tunnel configured (see Enclii setup guide)

### Container Registry Access
```bash
# GitHub Container Registry (ghcr.io)
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

---

## Quick Start

### 1. Clone and Configure

```bash
# Clone repository
git clone https://github.com/madfam-io/janua.git
cd janua

# Copy and configure production environment
cp .env.production.example .env.production
# Edit .env.production with your secrets
```

### 2. Pull Container Images

```bash
# Pull latest images from GitHub Container Registry
docker pull ghcr.io/madfam-io/janua-api:latest
docker pull ghcr.io/madfam-io/janua-dashboard:latest
docker pull ghcr.io/madfam-io/janua-website:latest
docker pull ghcr.io/madfam-io/janua-docs:latest
```

### 3. Start Infrastructure

```bash
# Start PostgreSQL and Redis first
cd deployment/production
docker compose -f docker-compose.production.yml up -d postgres redis

# Wait for databases to initialize
sleep 10

# Run database migrations
docker compose -f docker-compose.production.yml run --rm janua-api alembic upgrade head

# Start all services
docker compose -f docker-compose.production.yml up -d
```

### 4. Verify Deployment

```bash
# Check all containers are running
docker compose -f docker-compose.production.yml ps

# Check API health
curl -s http://localhost:4100/health | jq

# Check OIDC discovery
curl -s http://localhost:4100/.well-known/openid-configuration | jq
```

---

## Environment Configuration

### Critical Environment Variables

```bash
# Database (PostgreSQL)
DATABASE_URL=postgresql://janua:${DB_PASSWORD}@postgres:5432/janua_prod

# Cache (Redis)
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379

# JWT Keys (RS256)
JWT_PRIVATE_KEY=${JWT_PRIVATE_KEY}
JWT_PUBLIC_KEY=${JWT_PUBLIC_KEY}

# API URLs
# Client-side (browser) - Public URLs
NEXT_PUBLIC_API_URL=https://api.janua.dev
NEXT_PUBLIC_APP_URL=https://app.janua.dev

# Server-side (container-to-container) - Internal Docker network
# CRITICAL: This must be set for Dashboard/Website API routes to work
INTERNAL_API_URL=http://janua-api:8000

# Security
SECRET_KEY=${SECRET_KEY}
SESSION_COOKIE_DOMAIN=.janua.dev
```

### Container-to-Container Communication

The `INTERNAL_API_URL` variable is **critical** for production:

- **Problem**: Next.js API routes proxy requests to the FastAPI backend
- **In containers**: `localhost` doesn't work - containers are isolated
- **Solution**: Use Docker network hostname `http://janua-api:8000`

```yaml
# docker-compose.production.yml
janua-dashboard:
  environment:
    # Server-side API calls (runtime)
    - INTERNAL_API_URL=http://janua-api:8000
    # Client-side API calls (build-time)
    - NEXT_PUBLIC_API_URL=https://api.janua.dev
```

---

## CI/CD Pipeline

### GitHub Actions Workflow

The `.github/workflows/deploy.yml` builds and pushes Docker images on main branch:

```yaml
# Simplified workflow
jobs:
  build-api:
    steps:
      - uses: docker/build-push-action@v5
        with:
          file: ./Dockerfile.api
          push: true
          tags: ghcr.io/madfam-io/janua-api:latest

  deploy:
    needs: [build-api, build-dashboard, build-website, build-docs]
    steps:
      - name: Deploy via Enclii
        run: |
          curl -X POST "${{ secrets.ENCLII_DEPLOY_WEBHOOK }}" \
            -H "Authorization: Bearer ${{ secrets.ENCLII_DEPLOY_TOKEN }}" \
            -d '{"service": "janua", "tag": "${{ github.sha }}"}'
```

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `GITHUB_TOKEN` | Auto-provided, for ghcr.io push |
| `ENCLII_DEPLOY_WEBHOOK` | Enclii deployment trigger URL |
| `ENCLII_DEPLOY_TOKEN` | Authentication for Enclii |

---

## Health Check Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Basic liveness check |
| `GET /health/ready` | Readiness (DB + Redis connected) |
| `GET /health/live` | Kubernetes liveness probe |
| `GET /.well-known/openid-configuration` | OIDC Discovery |
| `GET /metrics` | Prometheus metrics (port 4190) |

### Example Health Check

```bash
curl -s https://api.janua.dev/health | jq
# {
#   "status": "healthy",
#   "version": "1.0.0",
#   "database": "connected",
#   "redis": "connected"
# }
```

---

## Cloudflare Tunnel Configuration

### Tunnel Routes

Configure in Cloudflare Zero Trust dashboard:

| Hostname | Service |
|----------|---------|
| api.janua.dev | http://localhost:4100 |
| app.janua.dev | http://localhost:4101 |
| admin.janua.dev | http://localhost:4102 |
| docs.janua.dev | http://localhost:4103 |
| janua.dev | http://localhost:4104 |

### cloudflared Config

```yaml
# /etc/cloudflared/config.yml
tunnel: janua-tunnel
credentials-file: /etc/cloudflared/credentials.json

ingress:
  - hostname: api.janua.dev
    service: http://localhost:4100
  - hostname: app.janua.dev
    service: http://localhost:4101
  - hostname: admin.janua.dev
    service: http://localhost:4102
  - hostname: docs.janua.dev
    service: http://localhost:4103
  - hostname: janua.dev
    service: http://localhost:4104
  - service: http_status:404
```

---

## Database Management

### Migrations

```bash
# Run pending migrations
docker compose exec janua-api alembic upgrade head

# Create new migration
docker compose exec janua-api alembic revision --autogenerate -m "description"

# Rollback last migration
docker compose exec janua-api alembic downgrade -1
```

### Backups

```bash
# Backup database
docker compose exec postgres pg_dump -U janua janua_prod > backup_$(date +%Y%m%d).sql

# Restore database
docker compose exec -T postgres psql -U janua janua_prod < backup.sql
```

---

## Troubleshooting

### Login Returns 500 Error

**Symptom**: `POST /api/auth/login` returns 500 Internal Server Error

**Cause**: Missing `INTERNAL_API_URL` environment variable

**Solution**:
```yaml
# In docker-compose.production.yml
janua-dashboard:
  environment:
    - INTERNAL_API_URL=http://janua-api:8000
```

Then restart:
```bash
docker compose -f docker-compose.production.yml up -d janua-dashboard
```

### Container Can't Connect to Database

**Symptom**: API fails to start, database connection errors

**Solution**: Ensure containers are on same Docker network:
```yaml
networks:
  janua-network:
    driver: bridge

services:
  janua-api:
    networks:
      - janua-network
  postgres:
    networks:
      - janua-network
```

### CORS Errors

**Symptom**: Browser console shows CORS policy errors

**Solution**: Verify CORS_ORIGINS in .env.production:
```bash
CORS_ORIGINS=["https://janua.dev","https://app.janua.dev","https://admin.janua.dev"]
```

### Check Container Logs

```bash
# View API logs
docker compose -f docker-compose.production.yml logs -f janua-api

# View all logs
docker compose -f docker-compose.production.yml logs -f

# Check specific container
docker logs janua-dashboard --tail 100
```

---

## Monitoring

### Prometheus Metrics

Available at `http://localhost:4190/metrics`:

- `http_requests_total` - Total HTTP requests
- `http_request_duration_seconds` - Request latency histogram
- `active_sessions` - Current active user sessions
- `rate_limit_hits` - Rate limiting events

### Grafana Dashboards

Access Grafana at `http://localhost:3000` (internal only):
- Default credentials: admin / `${GRAFANA_PASSWORD}`
- Import Janua dashboard from `deployment/grafana/dashboards/`

---

## Security Checklist

- [ ] Generate strong secrets: `openssl rand -hex 32`
- [ ] Generate RS256 JWT keys: `openssl genrsa -out private.pem 2048`
- [ ] Configure CORS for production domains only
- [ ] Enable session cookie secure flag
- [ ] Set appropriate rate limits per tenant tier
- [ ] Configure Cloudflare WAF rules
- [ ] Enable audit logging
- [ ] Set up backup schedule

---

## Support

- **Documentation**: https://docs.janua.dev
- **GitHub Issues**: https://github.com/madfam-io/janua/issues
- **Email**: support@janua.dev

---

*Janua - Self-Hosted Authentication for Developers Who Own Their Infrastructure*
