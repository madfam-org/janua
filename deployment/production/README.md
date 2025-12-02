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
│  │  :8000      │ │   :8010     │ │   :3001     │               │
│  └─────────────┘ └─────────────┘ └─────────────┘               │
│  ┌─────────────┐ ┌─────────────┐                                │
│  │  postgres   │ │    redis    │                                │
│  │   :5432     │ │    :6379    │                                │
│  └─────────────┘ └─────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Server Access

### SSH Connection

```bash
ssh -i ~/.ssh/id_ed25519 root@95.217.198.239
```

**Server Details:**
| Property | Value |
|----------|-------|
| Hostname | enclii-core |
| IP | 95.217.198.239 |
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

The tunnel routes traffic to local Docker containers:

| Domain | Target | Service |
|--------|--------|---------|
| janua.dev | localhost:3001 | Website |
| www.janua.dev | localhost:3001 | Website |
| api.janua.dev | localhost:8000 | Hono API |
| app.janua.dev | localhost:8010 | Dashboard |

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
# API (Python/Hono)
docker build -f Dockerfile.api -t janua/api:latest .
docker stop janua-api && docker rm janua-api
docker run -d --name janua-api --network janua-network -p 8000:8000 \
  --env-file .env.production janua/api:latest

# Website (Next.js)
docker build -f Dockerfile.website -t janua/website:latest .
docker stop janua-website && docker rm janua-website
docker run -d --name janua-website --network janua-network -p 3001:3000 \
  -e NODE_ENV=production \
  -e NEXT_PUBLIC_API_URL=https://api.janua.dev \
  -e NEXT_PUBLIC_APP_URL=https://app.janua.dev \
  janua/website:latest

# Dashboard (Next.js)
docker build -f Dockerfile.dashboard -t janua/dashboard:latest .
docker stop janua-dashboard && docker rm janua-dashboard
docker run -d --name janua-dashboard --network janua-network -p 8010:3000 \
  -e NODE_ENV=production \
  -e NEXT_PUBLIC_API_URL=https://api.janua.dev \
  -e INTERNAL_API_URL=http://janua-api:8000 \
  janua/dashboard:latest
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
# API health
curl http://localhost:8000/health

# Website health
curl http://localhost:3001/health

# Dashboard health
curl http://localhost:8010/health

# External (through Cloudflare)
curl https://api.janua.dev/health
curl https://janua.dev
curl https://app.janua.dev
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
netstat -tlnp | grep 8000

# Check Docker network
docker network inspect janua-network
```

### Tunnel not routing

```bash
# Check tunnel status
systemctl status cloudflared

# Check tunnel config
cat /etc/cloudflared/config.yml

# Restart tunnel
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

## Contact

For infrastructure issues, contact the DevOps team or check the `#infrastructure` channel.
