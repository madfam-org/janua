# Development Workflow Guide

## Enterprise Architecture Implementation

This document outlines the development workflow for the new enterprise-grade architecture with proper separation of concerns.

## Quick Start

### 1. Infrastructure Setup
```bash
# Start all backend services with Docker
cd deployment
docker-compose up -d

# Verify services are running
docker-compose ps
curl http://localhost:8000/health  # Core API
curl http://localhost:8001/health  # Auth Service
curl http://localhost:8002/health  # Mock API
curl http://localhost:8003/health  # Webhook Service
```

### 2. Frontend Development
```bash
# Install dependencies
yarn install

# Start all frontend applications
yarn dev:all

# Or start individual applications
yarn workspace @plinto/marketing dev      # Port 3000
yarn workspace @plinto/dashboard dev      # Port 3001  
yarn workspace @plinto/demo dev           # Port 3002
yarn workspace @plinto/docs dev           # Port 3003
yarn workspace @plinto/admin dev          # Port 3004
```

### 3. Application URLs
- **Marketing**: http://localhost:3000
- **Dashboard**: http://localhost:3001
- **Demo**: http://localhost:3002
- **Documentation**: http://localhost:3003  
- **Admin**: http://localhost:3004
- **Core API**: http://localhost:8000
- **Auth Service**: http://localhost:8001
- **Mock API**: http://localhost:8002
- **Webhook Service**: http://localhost:8003
- **Mail UI**: http://localhost:8025

## Development Commands

### Package Scripts
```bash
# Development
yarn dev:all              # Start all services
yarn dev:frontend         # Frontend apps only
yarn dev:backend          # Backend services only

# Building
yarn build:all             # Build all apps
yarn build:frontend        # Frontend apps only
yarn build:packages        # Shared packages only

# Testing
yarn test:all              # Run all tests
yarn test:unit             # Unit tests only
yarn test:e2e              # E2E tests only

# Linting & Formatting
yarn lint:all              # Lint all code
yarn format:all            # Format all code
yarn typecheck:all         # TypeScript checking
```

### Individual Workspace Commands
```bash
# Marketing Site
yarn workspace @plinto/marketing dev
yarn workspace @plinto/marketing build
yarn workspace @plinto/marketing test

# Dashboard App  
yarn workspace @plinto/dashboard dev
yarn workspace @plinto/dashboard build
yarn workspace @plinto/dashboard test

# Demo App
yarn workspace @plinto/demo dev
yarn workspace @plinto/demo build
yarn workspace @plinto/demo test

# Documentation
yarn workspace @plinto/docs dev
yarn workspace @plinto/docs build

# Admin Portal
yarn workspace @plinto/admin dev
yarn workspace @plinto/admin build

# Shared Packages
yarn workspace @plinto/ui build
yarn workspace @plinto/react-sdk build
yarn workspace @plinto/sdk build
yarn workspace @plinto/edge build
```

## Environment Configuration

### Development (.env.local)
```bash
# Shared configuration for all frontend apps
NEXT_PUBLIC_PLINTO_ISSUER=http://localhost:8000
NEXT_PUBLIC_PLINTO_API_URL=http://localhost:8000
NEXT_PUBLIC_ENVIRONMENT=development
NEXT_PUBLIC_MOCK_API_URL=http://localhost:8002
```

### Demo-specific (.env.demo)
```bash
NEXT_PUBLIC_PLINTO_ISSUER=http://localhost:8002
NEXT_PUBLIC_PLINTO_API_URL=http://localhost:8002
NEXT_PUBLIC_ENVIRONMENT=demo
NEXT_PUBLIC_MOCK_DELAY=true
```

### Backend Services (.env)
```bash
# Database
DATABASE_URL=postgresql://plinto:plinto_dev@localhost:5432/plinto
REDIS_URL=redis://localhost:6379/0

# Authentication
JWT_AUDIENCE=localhost:3000
JWT_ISSUER=http://localhost:8000
JWT_SECRET=dev_secret_key_change_in_production

# Email (Development)
EMAIL_PROVIDER=smtp
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=

# Development flags
PLINTO_ENV=development
DEBUG=true
AUTO_MIGRATE=true
ENABLE_DOCS=true
```

## Service Communication

### Frontend → Backend
- **Direct HTTP calls** to service ports during development
- **Proxy through Vercel** rewrites in production
- **Environment-aware URLs** through configuration

### Backend → Backend  
- **Internal service communication** via localhost during development
- **Service discovery** through Railway networking in production
- **Health check dependencies** defined in docker-compose

### Development vs Production URLs

| Service | Development | Production |
|---------|-------------|------------|
| Marketing | localhost:3000 | plinto.dev |
| Dashboard | localhost:3001 | app.plinto.dev |
| Demo | localhost:3002 | demo.plinto.dev |
| Docs | localhost:3003 | docs.plinto.dev |
| Admin | localhost:3004 | admin.plinto.dev |
| Core API | localhost:8000 | api.plinto.dev |
| Auth Service | localhost:8001 | auth.plinto.dev |
| Webhook Service | localhost:8003 | webhooks.plinto.dev |

## Testing Strategy

### Unit Tests
```bash
# Run all unit tests
yarn test:unit

# Run tests with coverage
yarn test:coverage

# Watch mode for development
yarn test:watch
```

### Integration Tests
```bash
# Test API endpoints
yarn test:api

# Test frontend integration
yarn test:frontend

# Test service communication
yarn test:integration
```

### E2E Tests
```bash
# Run all E2E tests
yarn test:e2e

# Run specific flow tests  
yarn test:e2e:auth
yarn test:e2e:dashboard
yarn test:e2e:demo
```

## Deployment Workflows

### Staging Deployment
```bash
# Deploy to staging
yarn deploy:staging

# Individual service deployment
yarn deploy:staging:marketing
yarn deploy:staging:api
```

### Production Deployment
```bash
# Full production deployment
yarn deploy:production

# Zero-downtime backend deployment
yarn deploy:production:api --zero-downtime
```

### Rollback Procedures
```bash
# Rollback to previous version
yarn rollback:production

# Rollback specific service
yarn rollback:production:api --version=v1.2.3
```

## Monitoring & Debugging

### Health Checks
```bash
# Check all services
yarn health:all

# Check specific service
yarn health:api
yarn health:frontend
```

### Log Monitoring
```bash
# View all service logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f core-api
docker-compose logs -f auth-service
```

### Database Operations
```bash
# Connect to development database
yarn db:connect

# Run migrations
yarn db:migrate

# Reset database
yarn db:reset

# Seed test data
yarn db:seed
```

## Security Considerations

### Development Security
- **Local HTTPS** for authentication testing
- **Test certificates** for SSL/TLS development
- **Mock external services** to avoid production data exposure
- **Audit trail testing** with non-sensitive data

### Production Security Checklist
- [ ] Environment variables secured
- [ ] Database credentials rotated
- [ ] SSL certificates validated
- [ ] CORS origins configured
- [ ] Rate limiting enabled
- [ ] Security headers implemented
- [ ] Audit logging activated

## Performance Optimization

### Development Performance
```bash
# Bundle analysis
yarn analyze:bundle

# Performance testing
yarn test:performance

# Memory profiling
yarn profile:memory
```

### Production Optimization
- **CDN caching** for static assets
- **Edge verification** with sub-50ms target
- **Database connection pooling**
- **Redis caching** for sessions and JWKS
- **Gzip compression** for API responses

## Troubleshooting

### Common Issues

**Port conflicts:**
```bash
# Kill processes on specific ports
lsof -ti:3000 | xargs kill -9
lsof -ti:8000 | xargs kill -9
```

**Database connection issues:**
```bash
# Reset Docker containers
docker-compose down -v
docker-compose up -d postgres redis
```

**Build errors:**
```bash
# Clean install
rm -rf node_modules package-lock.json yarn.lock
yarn install

# Clear Next.js cache
yarn workspace @plinto/marketing clean
```

**Service communication errors:**
```bash
# Verify service health
curl http://localhost:8000/health
curl http://localhost:8001/health

# Check Docker container logs
docker-compose logs core-api
docker-compose logs auth-service
```

## Migration Guide

### From Current Architecture
1. **Backup current code** and database
2. **Update package.json** with new workspace structure
3. **Migrate environment variables** to new format
4. **Update import paths** for shared packages
5. **Test service communication** end-to-end
6. **Update deployment configurations**
7. **Migrate production domains** gradually

### Rollback Plan
1. **Keep current architecture** running in parallel
2. **DNS switching** for quick rollback
3. **Database schema compatibility** maintained
4. **Feature flags** for gradual migration
5. **Monitoring alerts** for early issue detection