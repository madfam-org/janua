# Janua Production Deployment

Production infrastructure documentation for Janua on bare metal (Hetzner).

---

## Infrastructure Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Internet                                 │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    Cloudflare (DNS + CDN)                        │
│  • DNS: chin.ns.cloudflare.com, woz.ns.cloudflare.com           │
│  • Proxy: SSL termination, DDoS protection, caching             │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    Cloudflare Tunnel                             │
│  • Runs as systemd service on server                            │
│  • No exposed ports required                                     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│               Hetzner Bare Metal (enclii-core)                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ janua-api   │ │janua-dashb. │ │janua-website│               │
│  │  :4100      │ │   :4101     │ │   :4104     │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐               │
│  │ janua-docs  │ │  postgres   │ │    redis    │               │
│  │  :4103      │ │   :5432     │ │    :6379    │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

> **Port Standard**: Janua uses ports 4100-4199 per the [MADFAM Ecosystem Port Allocation](https://github.com/madfam-org/solarpunk-foundry/blob/main/docs/PORT_ALLOCATION.md).

---

## Server Access

### SSH Connection

```bash
# Via Cloudflare Zero Trust tunnel (recommended)
ssh ssh.madfam.io
# User: solarpunk (use sudo for admin commands)

# Requires: cloudflared installed + ~/.ssh/config configured
# See: solarpunk-foundry/docs/SSH_ACCESS.md for setup
```

**Server Details:**
| Property | Value |
|----------|-------|
| Control Plane | foundry-cp (37.27.235.104) |
| Worker Node | foundry-worker-01 (95.217.198.239) |
| SSH Host | ssh.madfam.io |
| OS | Ubuntu 24.04 LTS |
| Provider | Hetzner |
| Location | Helsinki, Finland |

### Project Location

```bash
cd /opt/solarpunk/janua
```

---

## Domain Routing

### Cloudflare Tunnel Configuration

**Bare Metal Deployment** (this guide): Routes traffic directly to Docker containers on localhost.

| Domain | Target | Service |
|--------|--------|---------|
| janua.dev | localhost:4104 | Website |
| www.janua.dev | localhost:4104 | Website |
| api.janua.dev | localhost:4100 | FastAPI Backend |
| app.janua.dev | localhost:4101 | Dashboard |
| docs.janua.dev | localhost:4103 | Documentation |

> **Note for K8s Deployments**: When running on Kubernetes, Cloudflare tunnel should route to K8s Service ports (typically port 80), NOT container ports. For K8s routing configuration, see [janua CLAUDE.md](../../CLAUDE.md#deployment) which documents the correct Service:Port mapping. The K8s Services expose port 80 and forward to the container ports internally via `targetPort`.

### DNS Configuration

Nameservers delegated to Cloudflare in Porkbun:
- `chin.ns.cloudflare.com`
- `woz.ns.cloudflare.com`

---

## Services

### Docker Containers

```bash
# View running containers
docker ps

# View logs
docker logs janua-api -f
docker logs janua-website -f
docker logs janua-dashboard -f

# Restart a service
docker restart janua-api
```

### Cloudflare Tunnel

```bash
# Check tunnel status
systemctl status cloudflared

# View tunnel logs
journalctl -u cloudflared -f

# Restart tunnel
systemctl restart cloudflared
```

---

## Deployment

### Update from Git

```bash
cd /opt/solarpunk/janua
git pull origin main
```

### Rebuild Containers

```bash
# API (FastAPI)
docker build -f Dockerfile.api -t janua/api:latest .
docker stop janua-api && docker rm janua-api
docker run -d --name janua-api --network janua-network -p 4100:8000 \
  --env-file .env.production janua/api:latest

# Website (Next.js)
docker build -f Dockerfile.website -t janua/website:latest .
docker stop janua-website && docker rm janua-website
docker run -d --name janua-website --network janua-network -p 4104:3000 \
  -e NODE_ENV=production \
  -e NEXT_PUBLIC_API_URL=https://api.janua.dev \
  -e NEXT_PUBLIC_APP_URL=https://app.janua.dev \
  janua/website:latest

# Dashboard (Next.js)
docker build -f Dockerfile.dashboard -t janua/dashboard:latest .
docker stop janua-dashboard && docker rm janua-dashboard
docker run -d --name janua-dashboard --network janua-network -p 4101:3000 \
  -e NODE_ENV=production \
  -e NEXT_PUBLIC_API_URL=https://api.janua.dev \
  -e INTERNAL_API_URL=http://janua-api:8000 \
  janua/dashboard:latest

# Docs (Next.js)
docker build -f Dockerfile.docs -t janua/docs:latest .
docker stop janua-docs && docker rm janua-docs
docker run -d --name janua-docs --network janua-network -p 4103:3000 \
  -e NODE_ENV=production \
  janua/docs:latest
```

### Using Docker Compose

```bash
cd /opt/solarpunk/janua/deployment/production
docker-compose -f docker-compose.production.yml up -d
```

---

## Monitoring

### Health Checks

```bash
# API health (port 4100)
curl http://localhost:4100/health

# Dashboard health (port 4101)
curl http://localhost:4101/health

# Docs health (port 4103)
curl http://localhost:4103/health

# Website health (port 4104)
curl http://localhost:4104/health

# External (through Cloudflare)
curl https://api.janua.dev/health
curl https://app.janua.dev
curl https://docs.janua.dev
curl https://janua.dev
```

### Resource Usage

```bash
# Docker stats
docker stats

# System resources
htop
df -h
free -h
```

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs janua-api --tail 100

# Check if port is in use
netstat -tlnp | grep 4100  # API
netstat -tlnp | grep 4101  # Dashboard
netstat -tlnp | grep 4103  # Docs
netstat -tlnp | grep 4104  # Website

# Check Docker network
docker network inspect janua-network
```

### Tunnel not routing

```bash
# Check tunnel status
systemctl status cloudflared

# Check tunnel config (ensure ports match MADFAM standard)
cat /etc/cloudflared/config.yml

# Expected ingress configuration:
# ingress:
#   - hostname: api.janua.dev
#     service: http://localhost:4100
#   - hostname: app.janua.dev
#     service: http://localhost:4101
#   - hostname: docs.janua.dev
#     service: http://localhost:4103
#   - hostname: janua.dev
#     service: http://localhost:4104
#   - hostname: www.janua.dev
#     service: http://localhost:4104
#   - service: http_status:404

# Restart tunnel after config changes
systemctl restart cloudflared
```

### DNS not resolving

```bash
# Check with external DNS
dig @8.8.8.8 janua.dev
dig @1.1.1.1 janua.dev

# Expected: Cloudflare IPs (104.x.x.x, 172.x.x.x)
```

---

## Environment Variables

Production environment variables are stored in:
- `/opt/solarpunk/janua/.env.production` (main config)
- Docker container environment (runtime)

**Required variables:**
```bash
# Database
DATABASE_URL=postgresql://...
REDIS_URL=redis://...

# Security
JWT_SECRET_KEY=...
SECRET_KEY=...

# Email
RESEND_API_KEY=...

# Internal
INTERNAL_API_KEY=...
```

See `.env.production.example` for full list.

---

## Backup

### Database Backup

```bash
# Manual backup
docker exec janua-postgres pg_dump -U janua janua > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20241201.sql | docker exec -i janua-postgres psql -U janua janua
```

### Redis Backup

```bash
# Trigger save
docker exec janua-redis redis-cli BGSAVE

# Copy RDB file
docker cp janua-redis:/data/dump.rdb ./redis_backup_$(date +%Y%m%d).rdb
```

---

## Security Notes

- SSH key authentication only (password auth disabled)
- Firewall allows only SSH (22), HTTP (80), HTTPS (443)
- All traffic routed through Cloudflare tunnel
- No direct port exposure to internet
- SSL/TLS handled by Cloudflare

---

## Enclii Integration

### Service Discovery Endpoints

For Enclii orchestration, Janua exposes the following endpoints:

| Endpoint | URL | Purpose |
|----------|-----|---------|
| API Health | `http://janua-api:8000/health` | Container health check |
| API Docs | `http://janua-api:8000/docs` | OpenAPI specification |
| Dashboard | `http://janua-dashboard:3001/` | User management UI |
| Website | `http://janua-website:3000/` | Public marketing site |

### Internal Network Configuration

```yaml
# Enclii service definition
services:
  janua:
    api:
      container: janua-api
      internal_port: 8000
      external_port: 4100
      health_check: /health
      network: janua-network

    dashboard:
      container: janua-dashboard
      internal_port: 3001
      external_port: 4101
      network: janua-network

    website:
      container: janua-website
      internal_port: 3000
      external_port: 4104
      network: janua-network

# Shared infrastructure
dependencies:
  postgres:
    container: postgres-shared
    port: 5432
    database: janua

  redis:
    container: redis-shared
    port: 6379
    db: 0
```

### Environment Variables for Enclii

```bash
# Required for Janua API in Enclii deployment
ENVIRONMENT=production
DATABASE_URL=postgresql://janua:${DB_PASSWORD}@postgres-shared:5432/janua
REDIS_URL=redis://:${REDIS_PASSWORD}@redis-shared:6379/0
JWT_SECRET_KEY=${JANUA_JWT_SECRET}
SECRET_KEY=${JANUA_SECRET_KEY}
EMAIL_PROVIDER=resend
RESEND_API_KEY=${RESEND_API_KEY}
INTERNAL_API_KEY=${INTERNAL_API_KEY}

# Required for Dashboard/Website
NEXT_PUBLIC_API_URL=https://api.janua.dev
NEXT_PUBLIC_APP_URL=https://app.janua.dev
INTERNAL_API_URL=http://janua-api:8000
```

### Health Check Integration

Enclii can monitor Janua services using:

```bash
# API health (returns JSON with status, version, environment)
curl -f http://janua-api:8000/health

# Dashboard/Website health (HTTP 200 = healthy)
curl -f http://janua-dashboard:3001/
curl -f http://janua-website:3000/
```

---

## Contact

For infrastructure issues, contact the DevOps team or check the `#infrastructure` channel.
