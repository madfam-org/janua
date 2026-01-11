# Janua - CLAUDE.md

> **Self-Hosted Authentication for Developers Who Own Their Infrastructure**

## Overview

**Status**: 🟢 Production Ready  
**Purpose**: Open-source OAuth2/OIDC identity platform  
**License**: AGPL v3  
**Domain**: [janua.dev](https://janua.dev)

Janua is a self-hosted authentication platform built with FastAPI and modern web technologies. Think Auth0 or Clerk, but you run it on your own infrastructure. **All features are free and open source.**

---

## Quick Start

```bash
# Clone and setup
cd janua

# Start backend infrastructure
cd apps/api
docker-compose up -d postgres redis
pip install -r requirements.txt
uvicorn app.main:app --reload --port 4100

# Start demo app (separate terminal)
cd apps/demo
npm install
npm run dev

# Open http://localhost:4101
```

---

## Project Structure

```
janua/
├── apps/
│   ├── api/              # FastAPI backend (Python 3.11+)
│   ├── admin/            # Admin dashboard
│   ├── dashboard/        # User management UI
│   ├── demo/             # Demo application
│   ├── docs/             # Documentation site
│   ├── edge-verify/      # Edge token verification
│   ├── landing/          # Marketing landing page
│   └── marketing/        # Marketing site
├── packages/
│   ├── core/             # Shared TypeScript utilities
│   ├── database/         # Prisma schema and migrations
│   ├── ui/               # Shared React components
│   ├── config/           # Shared configuration
│   ├── jwt-utils/        # JWT utilities
│   ├── monitoring/       # Observability utilities
│   ├── feature-flags/    # Feature flag system
│   └── mock-api/         # Testing mock API
├── packages/ (SDKs)
│   ├── nextjs-sdk/       # Next.js App Router SDK
│   ├── react-sdk/        # React hooks and components
│   ├── vue-sdk/          # Vue 3 composables
│   ├── typescript-sdk/   # Type-safe API client
│   ├── python-sdk/       # Python integration
│   ├── go-sdk/           # Go service integration
│   ├── flutter-sdk/      # Mobile Flutter SDK
│   └── react-native-sdk/ # React Native SDK
├── scripts/
│   └── migration/        # Auth0 migration tools
└── docs/                 # 204 markdown documentation files
```

---

## Development Commands

### Backend (FastAPI)
```bash
cd apps/api

# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Database
docker-compose up -d postgres redis
alembic upgrade head

# Run server
uvicorn app.main:app --reload --port 4100

# Run tests
pytest
pytest --cov=app tests/
```

### Frontend Apps
```bash
# Any frontend app
cd apps/<app-name>
pnpm install
pnpm dev

# Build for production
pnpm build
```

### SDK Development
```bash
cd packages/<sdk-name>
pnpm install
pnpm build
pnpm test
```

### Monorepo Commands (from root)
```bash
pnpm install          # Install all dependencies
pnpm build            # Build all packages
pnpm dev              # Run all in dev mode
pnpm test             # Run all tests
pnpm lint             # Lint all packages
```

---

## Port Allocation

Per [MADFAM Ecosystem Standard](https://github.com/madfam-org/solarpunk-foundry/blob/main/docs/PORT_ALLOCATION.md), Janua uses the 4100-4199 block.

| Service | Port | Container | Public Domain |
|---------|------|-----------|---------------|
| API | 4100 | janua-api | api.janua.dev |
| Dashboard | 4101 | janua-dashboard | app.janua.dev |
| Admin | 4102 | janua-admin | admin.janua.dev |
| Docs | 4103 | janua-docs | docs.janua.dev |
| Website | 4104 | janua-website | janua.dev |
| Demo | 4105 | janua-demo | demo.janua.dev |
| Email Worker | 4110 | janua-worker-email | - |
| WebSocket | 4120 | janua-ws | - |
| Metrics | 4190 | janua-metrics | - |

**Note**: Production now uses standard MADFAM ports. API runs on port 4100 via kubectl port-forward service (`janua-port-forward.service`).

---

## Features

### ✅ Working
- Email/password authentication
- OAuth (Google, GitHub, Microsoft, etc.)
- SAML 2.0 SSO
- TOTP/SMS multi-factor authentication
- WebAuthn/Passkeys (FIDO2)
- Multi-tenancy with organizations and RBAC
- REST API (202 endpoints)
- SDKs: React, Vue, Next.js, Python, Go, Flutter

### ⚠️ In Progress
- Documentation completeness
- Scale testing
- Edge case handling
- UI component polish

### ❌ Not Available
- Managed hosting (self-host only)
- Enterprise support contracts
- SOC 2 compliance reports

---

## API Reference

**Local Base URL**: `http://localhost:4100`
**Production Base URL**: `https://api.janua.dev`
**OpenAPI Docs**: `/docs`

### Production Endpoints
- `https://api.janua.dev` - Main API
- `https://auth.madfam.io` - Auth alias (same API)

### Key Endpoints
```
POST   /api/v1/auth/login          # Email/password login
POST   /api/v1/auth/register       # User registration
POST   /api/v1/auth/token/refresh  # Refresh JWT
GET    /api/v1/auth/me             # Current user
POST   /api/v1/auth/mfa/setup      # Setup MFA
POST   /api/v1/auth/passkey/register # Register passkey

GET    /api/v1/users               # List users (admin)
GET    /api/v1/organizations       # List organizations
POST   /api/v1/organizations       # Create organization
```

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/janua
REDIS_URL=redis://localhost:6379

# JWT (RS256 with RSA-2048 keys)
JWT_SECRET_KEY=your-secret-key       # For HS256 fallback
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY_PATH=./keys/private.pem
JWT_PUBLIC_KEY_PATH=./keys/public.pem
ACCESS_TOKEN_EXPIRE_MINUTES=15       # Default: 15min
REFRESH_TOKEN_EXPIRE_DAYS=7          # Default: 7 days

# Admin Bootstrap (optional - creates admin@madfam.io on first run)
ADMIN_BOOTSTRAP_PASSWORD=your-secure-password

# OAuth Providers
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...

# Email
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_FROM=noreply@janua.dev
```

### Admin Bootstrap

Set `ADMIN_BOOTSTRAP_PASSWORD` to automatically create an admin user on first startup:

```bash
# Creates admin@madfam.io with is_admin=true, email_verified=true
ADMIN_BOOTSTRAP_PASSWORD='SecurePassword123!' uvicorn app.main:app --port 4100
```

---

## SDK Installation

### NPM Registry Configuration
```bash
# Add to .npmrc
@janua:registry=https://npm.madfam.io
//npm.madfam.io/:_authToken=${NPM_MADFAM_TOKEN}
```

### React/Next.js
```bash
npm install @janua/react-sdk
# or
npm install @janua/nextjs-sdk
```

### Python
```bash
pip install janua-sdk
```

### Go
```bash
go get github.com/madfam-org/janua/packages/go-sdk
```

---

## Auth0 Migration

Migrating from Auth0? Use our migration tool:

```bash
cd scripts/migration
pip install -r requirements.txt
python auth0_migrate.py --config config.json
```

**Savings**: $24,000-58,000/year vs Auth0 enterprise pricing.

See `scripts/migration/README.md` for full guide.

---

## Testing

```bash
# Backend tests
cd apps/api
pytest                           # All tests
pytest tests/unit/               # Unit tests only
pytest tests/integration/        # Integration tests
pytest --cov=app --cov-report=html  # Coverage report

# Frontend tests
cd apps/dashboard
pnpm test
pnpm test:e2e                    # Playwright E2E
```

---

## Key Documentation

| Document | Path |
|----------|------|
| API Reference | `apps/api/docs/` |
| SDK Guides | `packages/*/README.md` |
| Migration Guide | `scripts/migration/README.md` |
| Architecture | `docs/architecture/` |
| Deployment | `docs/deployment/` |

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Client Apps                       │
│  (React, Vue, Next.js, Mobile, Backend Services)    │
└─────────────────────┬───────────────────────────────┘
                      │ SDKs
┌─────────────────────▼───────────────────────────────┐
│                  Janua API                           │
│         FastAPI + SQLAlchemy + Redis                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │  Auth   │ │  Users  │ │  Orgs   │ │   MFA   │   │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘   │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│              PostgreSQL + Redis                      │
│         (Sessions, Users, Organizations)             │
└─────────────────────────────────────────────────────┘
```

---

## Deployment

### Docker Compose (Recommended)
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes
```bash
kubectl apply -f k8s/
```

### Enclii (MADFAM Infrastructure)
```bash
enclii deploy --service janua
```

### Production Infrastructure
**Server**: foundry-core (95.217.198.239) via Cloudflare Tunnel
**K8s Cluster**: K3s (3-node Hetzner)
**Namespace**: janua

**Active Services**:
| Service | Type | Notes |
|---------|------|-------|
| janua-api | Deployment | Port 4100, ClusterIP |
| janua-dashboard | Deployment | Port 4101 |
| janua-admin | Deployment | Port 4102 |
| janua-docs | Deployment | Port 4103 |
| janua-website | Deployment | Port 4104 |

**Cloudflare Tunnel Routing** (via unified `enclii-production` tunnel):

| Public Domain | Internal Service |
|---------------|------------------|
| auth.madfam.io | janua-api.janua.svc.cluster.local:4100 |
| dashboard.madfam.io | janua-dashboard.janua.svc.cluster.local:4101 |
| admin.madfam.io | janua-admin.janua.svc.cluster.local:4102 |
| docs.madfam.io | janua-docs.janua.svc.cluster.local:4103 |
| madfam.io | janua-website.janua.svc.cluster.local:4104 |

See `enclii/infra/k8s/production/cloudflared-unified.yaml` for routing configuration.

**NetworkPolicy**: Requires `allow-cloudflared-ingress` policy to permit traffic from cloudflare-tunnel namespace.

---

## Common Workflows

### Adding a New API Endpoint

1. **Create route handler** in `apps/api/app/routers/v1/`
   ```python
   # apps/api/app/routers/v1/my_feature.py
   from fastapi import APIRouter, Depends
   from app.dependencies import get_current_user

   router = APIRouter(prefix="/my-feature", tags=["my-feature"])

   @router.get("/")
   async def list_items(user = Depends(get_current_user)):
       return {"items": []}
   ```

2. **Register router** in `apps/api/app/main.py`
   ```python
   from app.routers.v1 import my_feature
   app.include_router(my_feature.router, prefix="/api/v1")
   ```

3. **Add tests** in `apps/api/tests/unit/routers/`
4. **Update OpenAPI** by checking `/docs` endpoint
5. **Validate**: `pytest tests/unit/routers/test_my_feature.py`

### Adding OAuth Provider

1. **Configure provider** in `apps/api/app/config.py`
2. **Add provider handler** in `apps/api/app/services/oauth_service.py`
3. **Register routes** in `apps/api/app/routers/v1/oauth.py`
4. **Update SDK types** in `packages/typescript-sdk/src/types.ts`
5. **Add to UI** in `packages/ui/src/components/auth/`

### Database Migration

```bash
cd apps/api

# Create migration
alembic revision --autogenerate -m "add_user_preferences"

# Review generated migration
cat alembic/versions/*_add_user_preferences.py

# Apply locally
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

### SDK Updates

```bash
# After API changes, update TypeScript types
cd packages/typescript-sdk
pnpm build

# Rebuild dependent packages
cd packages/react-sdk && pnpm build
cd packages/nextjs-sdk && pnpm build

# Update frontend apps
cd apps/demo && pnpm build
cd apps/dashboard && pnpm build
```

### Running Specific Test Suites

```bash
cd apps/api

# Run by category
pytest tests/unit/                    # Unit tests
pytest tests/integration/             # Integration tests
pytest tests/unit/services/           # Service tests only
pytest tests/unit/routers/            # Router tests only

# Run by marker
pytest -m "not slow"                  # Skip slow tests
pytest -m "security"                  # Security tests only

# Run with coverage
pytest --cov=app --cov-report=html tests/
open htmlcov/index.html
```

---

## Debugging Guide

### Enable Debug Logging

```bash
# Full debug mode
DEBUG=true LOG_LEVEL=DEBUG uvicorn app.main:app --reload --port 4100

# SQL query logging
SQLALCHEMY_ECHO=true uvicorn app.main:app --reload --port 4100

# Both
DEBUG=true LOG_LEVEL=DEBUG SQLALCHEMY_ECHO=true uvicorn app.main:app --reload
```

### API Debugging

```bash
# Health check
curl http://localhost:4100/health | jq

# Detailed health with dependencies
curl http://localhost:4100/health/detailed | jq

# Test authentication flow
curl -X POST http://localhost:4100/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'

# Test with JWT
TOKEN="your-jwt-token"
curl http://localhost:4100/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Database Debugging

```bash
# Connect to local database
psql postgresql://user:pass@localhost:5432/janua

# Check active connections
psql -c "SELECT pid, usename, state, query FROM pg_stat_activity WHERE datname='janua';"

# Check table sizes
psql -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;"

# Check migration status
alembic current
alembic history --verbose
```

### Redis Debugging

```bash
# Connect to Redis
redis-cli -h localhost -p 6379

# Check session keys
redis-cli KEYS "session:*"

# Check cache keys
redis-cli KEYS "cache:*"

# Monitor in real-time
redis-cli MONITOR

# Memory stats
redis-cli INFO memory
```

### JWT Token Debugging

```bash
# Decode JWT (without verification)
echo $TOKEN | cut -d'.' -f2 | base64 -d 2>/dev/null | jq

# Verify with public key
python3 << 'EOF'
import jwt
token = "your-jwt-token"
public_key = open("keys/public.pem").read()
try:
    payload = jwt.decode(token, public_key, algorithms=["RS256"])
    print("Valid:", payload)
except jwt.ExpiredSignatureError:
    print("Token expired")
except jwt.InvalidTokenError as e:
    print("Invalid:", str(e))
EOF
```

### Common Issues

| Symptom | Check | Fix |
|---------|-------|-----|
| 500 errors | API logs, `DEBUG=true` | Check exception traceback |
| Auth fails | Token expiry, algorithm | Refresh token, check JWT_ALGORITHM |
| DB connection | PostgreSQL status | `docker-compose up -d postgres` |
| Cache miss | Redis connection | `docker-compose up -d redis` |
| CORS errors | allowed_origins in config | Add frontend URL to CORS |
| SSO fails | Certificate, clock sync | Check IdP cert, NTP sync |

---

## Key File Locations

### API (FastAPI Backend)

| Purpose | Location |
|---------|----------|
| Entry point | `apps/api/app/main.py` |
| Configuration | `apps/api/app/config.py` |
| Routes | `apps/api/app/routers/v1/` |
| Services | `apps/api/app/services/` |
| Models | `apps/api/app/models/` |
| Schemas | `apps/api/app/schemas/` |
| Middleware | `apps/api/app/middleware/` |
| Dependencies | `apps/api/app/dependencies.py` |
| Exceptions | `apps/api/app/core/exceptions.py` |
| Error handling | `apps/api/app/core/errors.py` |
| Caching | `apps/api/app/core/caching.py` |
| Performance | `apps/api/app/core/performance.py` |
| Database migrations | `apps/api/alembic/versions/` |

### Authentication

| Purpose | Location |
|---------|----------|
| Auth router | `apps/api/app/routers/v1/auth.py` |
| Auth service | `apps/api/app/services/auth_service.py` |
| JWT handling | `apps/api/app/services/jwt_service.py` |
| MFA service | `apps/api/app/services/mfa_service.py` |
| OAuth service | `apps/api/app/services/oauth_service.py` |
| Passkey/WebAuthn | `apps/api/app/routers/v1/passkeys.py` |
| SSO/SAML | `apps/api/app/sso/` |

### SDKs

| SDK | Main File | Types |
|-----|-----------|-------|
| TypeScript | `packages/typescript-sdk/src/client.ts` | `packages/typescript-sdk/src/types.ts` |
| React | `packages/react-sdk/src/index.tsx` | `packages/react-sdk/src/types.ts` |
| Next.js | `packages/nextjs-sdk/src/index.ts` | `packages/nextjs-sdk/src/types.ts` |
| Python | `packages/python-sdk/src/janua/client.py` | `packages/python-sdk/src/janua/types.py` |
| Go | `packages/go-sdk/janua/client.go` | `packages/go-sdk/janua/types.go` |

### Frontend Apps

| App | Main Entry | Config |
|-----|------------|--------|
| Dashboard | `apps/dashboard/app/page.tsx` | `apps/dashboard/lib/janua-client.ts` |
| Admin | `apps/admin/app/page.tsx` | `apps/admin/lib/janua-client.ts` |
| Demo | `apps/demo/app/page.tsx` | `apps/demo/lib/janua-client.ts` |

### Documentation

| Doc Type | Location |
|----------|----------|
| API FAQ | `apps/api/docs/FAQ.md` |
| Guides | `docs/guides/` |
| Architecture | `docs/architecture/` |
| Security | `docs/security/` |
| Deployment | `docs/deployment/` |

---

## Error Codes Reference

### API Error Codes

| HTTP | Code | Meaning |
|------|------|---------|
| 400 | `BAD_REQUEST` | Invalid request |
| 401 | `AUTHENTICATION_ERROR` | Auth failed |
| 401 | `TOKEN_ERROR` | Invalid/expired token |
| 403 | `AUTHORIZATION_ERROR` | Permission denied |
| 404 | `NOT_FOUND_ERROR` | Resource not found |
| 409 | `CONFLICT_ERROR` | Duplicate resource |
| 422 | `VALIDATION_ERROR` | Invalid input |
| 429 | `RATE_LIMIT_ERROR` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |

### SSO Error Codes

| Code | Meaning |
|------|---------|
| `SSO_AUTHENTICATION_ERROR` | SAML authentication failed |
| `SSO_VALIDATION_ERROR` | Configuration invalid |
| `SSO_CONFIGURATION_ERROR` | Provider setup incomplete |
| `SSO_METADATA_ERROR` | SAML metadata parsing failed |
| `SSO_CERTIFICATE_ERROR` | Certificate validation failed |
| `SSO_PROVISIONING_ERROR` | User provisioning failed |

---

## Production Operations

### Kubernetes Commands

```bash
# Set namespace
export NS=janua

# Check pod status
kubectl get pods -n $NS

# View logs
kubectl logs -n $NS -l app=janua-api -f

# Check events
kubectl get events -n $NS --sort-by='.lastTimestamp'

# Restart deployment
kubectl rollout restart deployment/janua-api -n $NS

# Scale deployment
kubectl scale deployment/janua-api -n $NS --replicas=3

# Port forward for debugging
kubectl port-forward svc/janua-api -n $NS 4100:4100
```

### Health Checks

```bash
# Local
curl http://localhost:4100/health

# Production (via tunnel)
curl https://api.janua.dev/health

# Check all dependencies
curl https://api.janua.dev/health/detailed | jq
```

### Backup Procedures

```bash
# Database backup
pg_dump $DATABASE_URL > janua_backup_$(date +%Y%m%d).sql

# Redis backup
redis-cli BGSAVE

# Verify backup
pg_restore --list janua_backup_*.sql | head
```

---

## Related Resources

- **Website**: [janua.dev](https://janua.dev)
- **GitHub**: [madfam-org/janua](https://github.com/madfam-org/janua)
- **Documentation**: `docs/` (204 markdown files)
- **Troubleshooting**: `docs/guides/TROUBLESHOOTING_GUIDE.md`
- **Security**: `docs/guides/SECURITY_CHECKLIST.md`
- **Performance**: `docs/guides/PERFORMANCE_TUNING_GUIDE.md`
- **License**: AGPL v3

---

*Janua - The Gatekeeper | One key for the whole city*
