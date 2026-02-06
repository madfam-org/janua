# Production Deployment Guide

Complete guide for deploying Janua to production environments with enterprise-grade configuration.

## 🎯 Overview

This guide covers production deployment of Janua identity platform across major cloud providers with high availability, security, and scalability considerations.

## 📋 Prerequisites

### Infrastructure Requirements
- **Database**: PostgreSQL 15+ with replication support
- **Cache**: Redis 7+ with clustering capability
- **Load Balancer**: SSL termination support
- **CDN**: Global content delivery network
- **Monitoring**: Prometheus + Grafana compatible metrics

### Security Requirements
- SSL/TLS certificates (wildcard recommended)
- Firewall rules and network security groups
- Identity and access management (IAM) roles
- Secret management system
- Backup and disaster recovery plan

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │────│   Web Servers   │────│   API Servers   │
│   (SSL Term)    │    │   (Frontend)    │    │   (Backend)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                              ┌─────────────────────────┼─────────────────────────┐
                              │                         │                         │
                    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
                    │   PostgreSQL    │    │   Redis Cache   │    │   File Storage  │
                    │   (Primary)     │    │   (Cluster)     │    │   (S3/GCS)      │
                    └─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │   (Replica)     │
                    └─────────────────┘
```

## ☁️ Cloud Provider Deployment

### AWS Deployment

#### 1. Infrastructure Setup
```bash
# Deploy infrastructure using Terraform
cd deployment/terraform/aws
terraform init
terraform plan -var-file="production.tfvars"
terraform apply
```

#### 2. Database Configuration
```yaml
# RDS PostgreSQL Configuration
engine: postgres
version: "15.3"
instance_class: db.r6g.xlarge
allocated_storage: 500
backup_retention: 30
multi_az: true
encryption: true
```

#### 3. Application Deployment
```bash
# Deploy API using ECS Fargate
aws ecs update-service \
  --cluster janua-production \
  --service janua-api \
  --desired-count 3

# Deploy frontend to CloudFront + S3
npm run build:production
aws s3 sync dist/ s3://janua-production-assets
aws cloudfront create-invalidation --distribution-id E123456789 --paths "/*"
```

### Google Cloud Platform

#### 1. Infrastructure Setup
```bash
# Deploy using Cloud Deployment Manager
gcloud deployment-manager deployments create janua-production \
  --config deployment/gcp/production.yaml
```

#### 2. Database Configuration
```yaml
# Cloud SQL PostgreSQL
tier: db-custom-4-16384
availability_type: REGIONAL
backup_start_time: "02:00"
binary_log_enabled: true
```

#### 3. Application Deployment
```bash
# Deploy to Cloud Run
gcloud run deploy janua-api \
  --image gcr.io/project-id/janua-api:latest \
  --platform managed \
  --region us-central1 \
  --min-instances 2 \
  --max-instances 100
```

### Microsoft Azure

#### 1. Infrastructure Setup
```bash
# Deploy using ARM templates
az deployment group create \
  --resource-group janua-production \
  --template-file deployment/azure/production.json \
  --parameters @deployment/azure/production.parameters.json
```

#### 2. Database Configuration
```yaml
# Azure Database for PostgreSQL
sku_name: GP_Gen5_4
storage_mb: 512000
backup_retention_days: 35
geo_redundant_backup: true
```

## 🔧 Configuration Management

### Environment Variables
```bash
# Core API Configuration
DATABASE_URL=postgresql://user:pass@host:5432/janua
REDIS_URL=redis://host:6379/0
JWT_SECRET=your-jwt-secret-key
ENCRYPTION_KEY=your-encryption-key

# Security Configuration
RATE_LIMIT_ENABLED=true
WAF_ENABLED=true
CORS_ALLOWED_ORIGINS=https://app.janua.dev,https://dashboard.janua.dev

# Monitoring Configuration
PROMETHEUS_ENABLED=true
JAEGER_ENABLED=true
LOG_LEVEL=info
```

### SSL/TLS Configuration
```nginx
# Nginx SSL Configuration
server {
    listen 443 ssl http2;
    server_name api.janua.dev;

    ssl_certificate /etc/ssl/certs/janua.crt;
    ssl_certificate_key /etc/ssl/private/janua.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;

    location / {
        proxy_pass http://janua-api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 📊 Monitoring & Observability

### Prometheus Configuration
```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'janua-api'
    static_configs:
      - targets: ['janua-api:8000']
    metrics_path: '/metrics'

  - job_name: 'janua-frontend'
    static_configs:
      - targets: ['janua-frontend:3000']
```

### Grafana Dashboards
- **API Performance**: Response times, error rates, throughput
- **Database Metrics**: Connection pool, query performance, replication lag
- **Redis Metrics**: Memory usage, key eviction, cluster health
- **Business Metrics**: User registrations, authentications, organization growth

### Alerting Rules
```yaml
# Critical Alerts
- alert: HighErrorRate
  expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
  for: 5m

- alert: DatabaseDown
  expr: up{job="postgres"} == 0
  for: 1m

- alert: HighMemoryUsage
  expr: memory_usage_percent > 90
  for: 10m
```

## 🔐 Security Hardening

### Network Security
```yaml
# Security Group Rules (AWS)
ingress:
  - protocol: tcp
    from_port: 443
    to_port: 443
    cidr_blocks: ["0.0.0.0/0"]
  - protocol: tcp
    from_port: 80
    to_port: 80
    cidr_blocks: ["0.0.0.0/0"]

egress:
  - protocol: -1
    cidr_blocks: ["0.0.0.0/0"]
```

### WAF Configuration
```yaml
# CloudFlare WAF Rules
rules:
  - action: block
    expression: '(http.request.uri.path contains "/admin" and not ip.src in {192.168.1.0/24})'
  - action: challenge
    expression: '(cf.threat_score > 50)'
  - action: rate_limit
    expression: '(true)'
    rate_limit:
      threshold: 100
      period: 60
```

## 📈 Scaling Configuration

### Auto Scaling Policies
```yaml
# Kubernetes HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: janua-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: janua-api
  minReplicas: 3
  maxReplicas: 100
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Database Scaling
```sql
-- Read Replica Configuration
CREATE REPLICA janua_replica_1
FROM janua_primary
WITH (
    host = 'replica1.janua.internal',
    port = 5432,
    synchronous_commit = 'remote_apply'
);
```

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow
```yaml
name: Production Deployment
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Production
        run: |
          # Run tests
          npm test
          # Build and deploy
          docker build -t janua-api:${{ github.sha }} .
          docker push janua-api:${{ github.sha }}
          # Update production
          kubectl set image deployment/janua-api api=janua-api:${{ github.sha }}
```

## 📝 Maintenance Procedures

### Database Maintenance
```bash
# Weekly backup verification
pg_dump -h production-db -U postgres janua > backup_$(date +%Y%m%d).sql

# Monthly index optimization
REINDEX DATABASE janua;
VACUUM ANALYZE;
```

### Log Rotation
```yaml
# Logrotate configuration
/var/log/janua/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 www-data www-data
}
```

## 🚨 Disaster Recovery

### Backup Strategy
- **Database**: Daily full backups, continuous WAL archiving
- **Redis**: Daily snapshots, AOF persistence enabled
- **Application Data**: Daily incremental backups to object storage
- **Configuration**: Version controlled in Git

### Recovery Procedures
1. **Database Recovery**: Point-in-time recovery from WAL archives
2. **Cache Recovery**: Rebuild from database, Redis snapshots as fallback
3. **Application Recovery**: Blue-green deployment from last known good state

### RTO/RPO Targets
- **Recovery Time Objective (RTO)**: < 30 minutes
- **Recovery Point Objective (RPO)**: < 5 minutes data loss

## 📞 Support & Troubleshooting

### Common Issues
- **High CPU Usage**: Check for expensive queries, optimize indexes
- **Memory Leaks**: Monitor application metrics, restart if necessary
- **Connection Pool Exhaustion**: Increase pool size, check connection leaks

### Emergency Contacts
- **On-call Engineer**: alerts@aureo.io
- **Database Team**: dba@aureo.io
- **Security Team**: security@aureo.io

### Escalation Procedures
1. **Level 1**: Automated alerts and basic troubleshooting
2. **Level 2**: On-call engineer investigation
3. **Level 3**: Senior engineering team involvement
4. **Level 4**: Executive escalation for business-critical issues

---

## 📚 Additional Resources

- [Infrastructure](../../infra/)
- [Security Configuration Guide](../security/)
- [Monitoring Setup](../../infra/monitoring/)
- [Performance Optimization](../performance/)
- [Troubleshooting Runbook](../troubleshooting/)

For questions or support, contact: [support@janua.dev](mailto:support@janua.dev)