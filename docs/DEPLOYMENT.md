# Production Deployment Guide

**Target Audience**: DevOps engineers, SRE teams, self-hosting users
**Time to Deploy**: 30-60 minutes (basic) | 2-4 hours (production-ready)
**Difficulty**: Intermediate to Advanced

This guide covers deploying Janua authentication platform to production environments with Docker, Kubernetes, and cloud providers.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Deployment Options](#deployment-options)
  - [Docker Compose (Recommended for Getting Started)](#docker-compose)
  - [Docker Production Deployment](#docker-production)
  - [Kubernetes Deployment](#kubernetes-deployment)
  - [Cloud Platforms](#cloud-platforms)
- [Environment Configuration](#environment-configuration)
- [Database Setup](#database-setup)
- [Security Hardening](#security-hardening)
- [Monitoring & Observability](#monitoring--observability)
- [Backup & Disaster Recovery](#backup--disaster-recovery)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

For a quick production deployment with Docker Compose:

```bash
# 1. Clone the repository
git clone https://github.com/madfam-io/janua.git
cd janua

# 2. Copy production environment template
cp .env.production.example .env.production

# 3. Generate secrets
export SECRET_KEY=$(openssl rand -hex 32)
export JWT_PRIVATE_KEY=$(openssl genrsa 2048)
export DATABASE_PASSWORD=$(openssl rand -base64 32)
export REDIS_PASSWORD=$(openssl rand -base64 32)

# 4. Update .env.production with your values
nano .env.production

# 5. Deploy with Docker Compose
docker-compose -f deployment/docker-compose.production.yml up -d

# 6. Run database migrations
docker-compose exec api alembic upgrade head

# 7. Verify deployment
curl http://localhost:8000/health
```

**⚠️ Important**: This quick start is for evaluation. See [Production Deployment](#docker-production) for hardened production setup.

---

## Prerequisites

### System Requirements

**Minimum** (supports ~1,000 MAU):
- CPU: 2 cores
- RAM: 4GB
- Storage: 20GB SSD
- Network: 100 Mbps

**Recommended** (supports ~10,000 MAU):
- CPU: 4 cores
- RAM: 8GB
- Storage: 100GB SSD
- Network: 1 Gbps

**Production** (supports 100,000+ MAU):
- CPU: 8+ cores
- RAM: 16GB+
- Storage: 500GB+ SSD
- Network: 10 Gbps
- Load balancer
- Multi-region deployment

### Software Dependencies

- Docker 24.0+ and Docker Compose 2.20+
- PostgreSQL 15+ (managed or self-hosted)
- Redis 7+ (managed or self-hosted)
- SSL certificate (Let's Encrypt recommended)
- Domain with DNS access

### Optional but Recommended

- Kubernetes 1.28+ (for container orchestration)
- Cloudflare account (CDN, DDoS protection, R2 storage)
- Monitoring tools (DataDog, Prometheus, Grafana)
- Email service (SendGrid, Postmark, AWS SES)
- Object storage (S3, R2, MinIO)

---

## Deployment Options

### Docker Compose

**Best for**: Small to medium deployments, getting started, development staging

#### Production-Ready Docker Compose Setup

**1. Create production compose file** (`docker-compose.production.yml`):

```yaml
version: '3.9'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: janua-postgres-prod
    environment:
      POSTGRES_USER: ${DATABASE_USER}
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
      POSTGRES_DB: janua_production
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DATABASE_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: always
    networks:
      - janua-network
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G

  # Redis Cache & Sessions
  redis:
    image: redis:7-alpine
    container_name: janua-redis-prod
    command: >
      redis-server
      --appendonly yes
      --requirepass ${REDIS_PASSWORD}
      --maxmemory 2gb
      --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "--pass", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: always
    networks:
      - janua-network
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G

  # Janua API Service
  api:
    build:
      context: ./apps/api
      dockerfile: Dockerfile.production
    container_name: janua-api-prod
    env_file: .env.production
    environment:
      DATABASE_URL: postgresql://${DATABASE_USER}:${DATABASE_PASSWORD}@postgres:5432/janua_production
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: always
    networks:
      - janua-network
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G

  # Nginx Reverse Proxy with SSL
  nginx:
    image: nginx:alpine
    container_name: janua-nginx-prod
    volumes:
      - ./deployment/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./deployment/ssl:/etc/nginx/ssl:ro
      - ./deployment/dhparam.pem:/etc/nginx/dhparam.pem:ro
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - api
    restart: always
    networks:
      - janua-network

networks:
  janua-network:
    driver: bridge

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
```

**2. Create production Dockerfile** (`apps/api/Dockerfile.production`):

```dockerfile
# Multi-stage build for optimized production image
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    pkg-config \
    libxml2-dev \
    libxmlsec1-dev \
    libxslt-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libpq5 \
    libxmlsec1 \
    libxml2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 janua && \
    chown -R janua:janua /app && \
    chmod +x /app/scripts/*.sh

USER janua

# Add Python packages to PATH
ENV PATH=/root/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run with production settings
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--access-log"]
```

**3. Deploy to production**:

```bash
# Build and start services
docker-compose -f docker-compose.production.yml build
docker-compose -f docker-compose.production.yml up -d

# Run database migrations
docker-compose -f docker-compose.production.yml exec api alembic upgrade head

# Check service health
docker-compose -f docker-compose.production.yml ps
docker-compose -f docker-compose.production.yml logs -f api

# View logs
docker-compose -f docker-compose.production.yml logs -f --tail=100
```

---

### Docker Production

**Best for**: Single-server production deployments, custom infrastructure

#### Building Production Image

```bash
# Build optimized production image
cd apps/api
docker build -f Dockerfile.production -t janua/api:latest .

# Tag for version
docker tag janua/api:latest janua/api:1.0.0

# Test image locally
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  -e REDIS_URL=redis://host:6379/0 \
  -e SECRET_KEY=your-secret-key \
  janua/api:latest
```

#### Running Production Container

```bash
# Run with production settings
docker run -d \
  --name janua-api \
  --restart always \
  -p 8000:8000 \
  -e DATABASE_URL=${DATABASE_URL} \
  -e REDIS_URL=${REDIS_URL} \
  -e SECRET_KEY=${SECRET_KEY} \
  -e JWT_PRIVATE_KEY="${JWT_PRIVATE_KEY}" \
  -e ENVIRONMENT=production \
  -e LOG_LEVEL=info \
  --health-cmd="curl -f http://localhost:8000/health || exit 1" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  --cpus=4 \
  --memory=8g \
  janua/api:1.0.0

# View logs
docker logs -f janua-api

# Execute commands in container
docker exec -it janua-api /bin/bash

# Run database migrations
docker exec janua-api alembic upgrade head
```

---

### Kubernetes Deployment

**Best for**: Large-scale deployments, multi-region, high availability

#### Kubernetes Manifests

**1. Namespace** (`k8s/namespace.yaml`):

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: janua
  labels:
    name: janua
    environment: production
```

**2. ConfigMap** (`k8s/configmap.yaml`):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: janua-config
  namespace: janua
data:
  ENVIRONMENT: "production"
  LOG_LEVEL: "info"
  API_VERSION: "v1"
  ENABLE_DOCS: "false"
  CORS_ORIGINS: "https://janua.dev,https://app.janua.dev"
```

**3. Secret** (`k8s/secret.yaml`):

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: janua-secrets
  namespace: janua
type: Opaque
stringData:
  DATABASE_URL: "postgresql://user:password@postgres-service:5432/janua"
  REDIS_URL: "redis://:password@redis-service:6379/0"
  SECRET_KEY: "your-secret-key-here"
  JWT_PRIVATE_KEY: |
    -----BEGIN RSA PRIVATE KEY-----
    ... your private key ...
    -----END RSA PRIVATE KEY-----
```

**4. Deployment** (`k8s/deployment.yaml`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: janua-api
  namespace: janua
  labels:
    app: janua-api
    version: v1
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: janua-api
  template:
    metadata:
      labels:
        app: janua-api
        version: v1
    spec:
      containers:
      - name: api
        image: janua/api:1.0.0
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
          protocol: TCP
        envFrom:
        - configMapRef:
            name: janua-config
        - secretRef:
            name: janua-secrets
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 4Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          successThreshold: 1
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 15"]
      terminationGracePeriodSeconds: 30
```

**5. Service** (`k8s/service.yaml`):

```yaml
apiVersion: v1
kind: Service
metadata:
  name: janua-api-service
  namespace: janua
spec:
  type: ClusterIP
  selector:
    app: janua-api
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
```

**6. Ingress** (`k8s/ingress.yaml`):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: janua-ingress
  namespace: janua
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - api.janua.dev
    secretName: janua-tls
  rules:
  - host: api.janua.dev
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: janua-api-service
            port:
              number: 8000
```

**7. HorizontalPodAutoscaler** (`k8s/hpa.yaml`):

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: janua-api-hpa
  namespace: janua
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: janua-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 30
```

#### Deploy to Kubernetes

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Create secrets (use sealed secrets in production)
kubectl apply -f k8s/secret.yaml

# Apply configuration
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml

# Check deployment status
kubectl get pods -n janua
kubectl get svc -n janua
kubectl describe deployment janua-api -n janua

# View logs
kubectl logs -f -l app=janua-api -n janua

# Scale manually if needed
kubectl scale deployment janua-api --replicas=5 -n janua

# Run database migrations
kubectl exec -it $(kubectl get pod -l app=janua-api -n janua -o jsonpath='{.items[0].metadata.name}') -n janua -- alembic upgrade head
```

---

### Hetzner + Enclii Deployment (Recommended)

**Best for**: Full infrastructure control, data sovereignty, cost-effective at scale

Janua's primary production deployment uses MADFAM's self-hosted infrastructure on Hetzner bare metal servers with Cloudflare Tunnel for zero-trust ingress.

#### Architecture
```
Cloudflare Edge (DNS + WAF) → Cloudflare Tunnel → Hetzner Server → Docker Compose
```

#### Port Allocation (MADFAM Standard 4100-4199)
| Service | Port | Domain |
|---------|------|--------|
| API | 4100 | api.janua.dev |
| Dashboard | 4101 | app.janua.dev |
| Admin | 4102 | admin.janua.dev |
| Docs | 4103 | docs.janua.dev |
| Website | 4104 | janua.dev |

#### Container-to-Container Communication

**Critical**: Next.js API routes must communicate with the FastAPI backend using Docker internal networking:

```yaml
# docker-compose.production.yml
janua-dashboard:
  environment:
    # Server-side API calls (runtime) - Docker network hostname
    - INTERNAL_API_URL=http://janua-api:8000
    # Client-side API calls (build-time) - Public URL
    - NEXT_PUBLIC_API_URL=https://api.janua.dev
```

#### CI/CD Pipeline

GitHub Actions builds Docker images and deploys via Enclii webhook:

```yaml
# .github/workflows/deploy.yml
deploy:
  steps:
    - name: Deploy via Enclii
      run: |
        curl -X POST "${{ secrets.ENCLII_DEPLOY_WEBHOOK }}" \
          -H "Authorization: Bearer ${{ secrets.ENCLII_DEPLOY_TOKEN }}" \
          -d '{"service": "janua", "tag": "${{ github.sha }}"}'
```

#### Cloudflare Tunnel Configuration

```yaml
# /etc/cloudflared/config.yml
tunnel: janua-tunnel
credentials-file: /etc/cloudflared/credentials.json

ingress:
  - hostname: api.janua.dev
    service: http://localhost:4100
  - hostname: app.janua.dev
    service: http://localhost:4101
  - hostname: janua.dev
    service: http://localhost:4104
  - service: http_status:404
```

See [deployment/DEPLOYMENT.md](deployment/DEPLOYMENT.md) for complete Hetzner/Enclii deployment guide.

---

### Alternative Deployments (Optional)

#### Kubernetes

Kubernetes manifests are provided for organizations requiring container orchestration. See the Kubernetes section above.

#### Other Cloud Platforms

While Janua is designed for self-hosting, it can run on any platform supporting Docker:
- AWS ECS/Fargate
- Google Cloud Run
- Azure Container Apps

Consult platform-specific documentation for deployment details.

---

## Environment Configuration

### Required Environment Variables

```bash
# Core
ENVIRONMENT=production
SECRET_KEY=<min-32-char-random-string>
LOG_LEVEL=info

# Database
DATABASE_URL=postgresql://user:pass@host:5432/janua
DATABASE_POOL_SIZE=50

# Redis
REDIS_URL=redis://user:pass@host:6379/0
REDIS_POOL_SIZE=20

# JWT
JWT_PRIVATE_KEY=<RSA-private-key>
JWT_PUBLIC_KEY=<RSA-public-key>
JWT_ALGORITHM=RS256
```

### Generating Secrets

```bash
# Generate SECRET_KEY (32+ characters)
openssl rand -hex 32

# Generate JWT RSA key pair
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem

# Read keys for environment variables
export JWT_PRIVATE_KEY=$(cat private.pem)
export JWT_PUBLIC_KEY=$(cat public.pem)

# Generate database password
openssl rand -base64 32

# Generate Redis password
openssl rand -base64 32
```

### Environment File Template

Create `.env.production`:

```bash
# Copy from template
cp .env.production.example .env.production

# Edit with your values
nano .env.production
```

See [`.env.production.example`](../.env.production.example) for complete configuration reference.

---

## Database Setup

### PostgreSQL Production Configuration

**1. Create database and user**:

```sql
-- Connect as superuser
psql postgres

-- Create database
CREATE DATABASE janua_production;

-- Create user with strong password
CREATE USER janua_user WITH ENCRYPTED PASSWORD 'strong-random-password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE janua_production TO janua_user;
ALTER DATABASE janua_production OWNER TO janua_user;

-- Enable required extensions
\c janua_production
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
```

**2. Run migrations**:

```bash
# With Docker
docker exec janua-api alembic upgrade head

# With local alembic
cd apps/api
alembic upgrade head

# Check migration status
alembic current
alembic history
```

**3. Connection pooling** (recommended for production):

Use [PgBouncer](https://www.pgbouncer.org/) or managed connection pooling:

```bash
# PgBouncer configuration
[databases]
janua = host=postgres port=5432 dbname=janua_production

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
```

---

## Security Hardening

### Production Security Checklist

- [ ] **Secrets Management**: Use secrets manager (AWS Secrets Manager, HashiCorp Vault, Railway variables)
- [ ] **HTTPS Only**: Enforce SSL/TLS with valid certificates (Let's Encrypt, Cloudflare)
- [ ] **Firewall Rules**: Restrict database/Redis to application subnet only
- [ ] **Rate Limiting**: Enable Redis-backed rate limiting (configured in `.env.production`)
- [ ] **CORS**: Whitelist only your domains in `CORS_ORIGINS`
- [ ] **Disable Debug**: Set `DEBUG=false` and `API_DOCS_ENABLED=false`
- [ ] **Security Headers**: Enable HSTS, CSP, X-Frame-Options via nginx/CDN
- [ ] **Database Encryption**: Enable encryption at rest for PostgreSQL
- [ ] **Redis Password**: Set strong password with `requirepass`
- [ ] **JWT Security**: Use RS256 algorithm, rotate keys regularly
- [ ] **Session Security**: Set `SESSION_COOKIE_SECURE=true`, `SESSION_COOKIE_HTTPONLY=true`
- [ ] **Vulnerability Scanning**: Run `safety check` for Python dependencies
- [ ] **Container Security**: Scan images with Trivy, Snyk, or Clair
- [ ] **Audit Logging**: Enable comprehensive audit logs to immutable storage (R2, S3)
- [ ] **Backup Encryption**: Encrypt all backups with strong keys

### Nginx Security Configuration

```nginx
# /etc/nginx/nginx.conf
http {
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Hide nginx version
    server_tokens off;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/s;

    server {
        listen 443 ssl http2;
        server_name api.janua.dev;

        # SSL configuration
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_prefer_server_ciphers on;
        ssl_dhparam /etc/nginx/dhparam.pem;

        # OCSP stapling
        ssl_stapling on;
        ssl_stapling_verify on;

        location /api/v1/auth {
            limit_req zone=auth_limit burst=10 nodelay;
            proxy_pass http://janua-api:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location / {
            limit_req zone=api_limit burst=20 nodelay;
            proxy_pass http://janua-api:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
```

---

## Monitoring & Observability

### Health Checks

```bash
# Application health
curl https://api.janua.dev/health

# Database health
curl https://api.janua.dev/health/db

# Redis health
curl https://api.janua.dev/health/redis

# System metrics
curl https://api.janua.dev/metrics
```

### Prometheus Metrics

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'janua-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### Logging

**Structured JSON logging** (already configured in Janua):

```json
{
  "timestamp": "2025-11-16T10:30:00Z",
  "level": "info",
  "service": "janua-api",
  "event": "user_login",
  "user_id": "uuid",
  "ip": "1.2.3.4",
  "duration_ms": 45
}
```

**Log aggregation options**:
- **Self-hosted**: ELK Stack (Elasticsearch, Logstash, Kibana)
- **Cloud**: DataDog, New Relic, Papertrail, Loggly
- **Cloudflare**: Logpush to R2 for long-term storage

---

## Backup & Disaster Recovery

### PostgreSQL Backups

**Automated daily backups**:

```bash
#!/bin/bash
# backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_NAME="janua_production"

# Create backup
pg_dump -h postgres -U janua_user -Fc $DB_NAME > $BACKUP_DIR/janua_$DATE.dump

# Encrypt backup
openssl enc -aes-256-cbc -salt -in $BACKUP_DIR/janua_$DATE.dump -out $BACKUP_DIR/janua_$DATE.dump.enc -pass pass:$BACKUP_PASSWORD

# Upload to S3/R2
aws s3 cp $BACKUP_DIR/janua_$DATE.dump.enc s3://janua-backups-prod/

# Delete local backup
rm $BACKUP_DIR/janua_$DATE.dump $BACKUP_DIR/janua_$DATE.dump.enc

# Keep only last 30 days on S3
aws s3 ls s3://janua-backups-prod/ | awk '{print $4}' | sort | head -n -30 | xargs -I {} aws s3 rm s3://janua-backups-prod/{}
```

**Cron schedule**:

```bash
# Daily at 2 AM
0 2 * * * /app/scripts/backup.sh >> /var/log/backup.log 2>&1
```

### Restore from Backup

```bash
# Download from S3
aws s3 cp s3://janua-backups-prod/janua_20251116_020000.dump.enc .

# Decrypt
openssl enc -aes-256-cbc -d -in janua_20251116_020000.dump.enc -out janua_20251116_020000.dump -pass pass:$BACKUP_PASSWORD

# Restore (WARNING: drops existing database)
pg_restore -h postgres -U janua_user -d janua_production --clean janua_20251116_020000.dump
```

### Redis Backups

Redis persistence with AOF (Append-Only File):

```bash
# redis.conf
appendonly yes
appendfilename "appendonly.aof"
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

---

## Troubleshooting

### Common Issues

**1. Database connection failed**

```bash
# Check database is accessible
docker exec janua-api pg_isready -h postgres -U janua_user

# Check DATABASE_URL format
echo $DATABASE_URL
# Should be: postgresql://user:pass@host:5432/dbname

# Test connection
docker exec janua-api psql $DATABASE_URL -c "SELECT 1"
```

**2. Redis connection failed**

```bash
# Check Redis is accessible
docker exec janua-api redis-cli -h redis -a $REDIS_PASSWORD ping

# Check REDIS_URL format
echo $REDIS_URL
# Should be: redis://:password@host:6379/0
```

**3. API returns 502 Bad Gateway**

```bash
# Check API is running
docker ps | grep janua-api

# Check API logs
docker logs janua-api --tail=100

# Check API health endpoint
curl http://localhost:8000/health

# Restart API container
docker restart janua-api
```

**4. Migrations fail**

```bash
# Check current migration status
docker exec janua-api alembic current

# Check migration history
docker exec janua-api alembic history

# Manually run specific migration
docker exec janua-api alembic upgrade <revision>

# Rollback to previous version
docker exec janua-api alembic downgrade -1
```

**5. High memory usage**

```bash
# Check container stats
docker stats janua-api

# Reduce worker count in uvicorn
# Edit: CMD ["uvicorn", "main:app", "--workers", "2"]

# Check for memory leaks in logs
docker logs janua-api | grep -i "memory\|oom"
```

### Debug Mode

**Enable debug logging temporarily**:

```bash
# Restart with debug logging
docker exec janua-api sh -c "LOG_LEVEL=debug uvicorn main:app --reload"

# View debug logs
docker logs -f janua-api
```

**⚠️ Important**: Never enable `DEBUG=true` in production. Use `LOG_LEVEL=debug` only.

---

## Performance Optimization

### Application Tuning

```python
# uvicorn workers (apps/api/main.py)
# Workers = (2 x CPU cores) + 1
# Example: 4 cores → 9 workers

uvicorn main:app --workers 9 --worker-class uvicorn.workers.UvicornWorker
```

### Database Tuning

```sql
-- PostgreSQL configuration for production
ALTER SYSTEM SET shared_buffers = '2GB';
ALTER SYSTEM SET effective_cache_size = '6GB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';
ALTER SYSTEM SET max_connections = 200;

-- Reload configuration
SELECT pg_reload_conf();
```

### Redis Tuning

```bash
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
save ""  # Disable RDB snapshots for session data
appendonly yes
appendfsync everysec
```

---

## Support & Resources

- **Documentation**: https://docs.janua.dev
- **API Reference**: https://api.janua.dev/docs
- **GitHub Issues**: https://github.com/madfam-io/janua/issues
- **Discord Community**: https://discord.gg/janua
- **Email Support**: support@janua.dev
- **Security Issues**: security@janua.dev

---

## License

Janua is licensed under AGPL-3.0:
- **AGPL-3.0 License**: GNU Affero General Public License v3.0
- **Copyright**: (C) 2025 Innovaciones MADFAM SAS de CV
- **Infrastructure Sovereignty**: Mandatory copyleft for network software

See [LICENSE](../LICENSE) for details.

---

**Deployment Status**: Ready for production ✅

**Next Steps**:
1. Review [Security Checklist](#production-security-checklist)
2. Set up [Monitoring](#monitoring--observability)
3. Configure [Backups](#backup--disaster-recovery)
4. Test with [Troubleshooting Guide](#troubleshooting)

**Questions?** Join our [Discord](https://discord.gg/janua) or email support@janua.dev
