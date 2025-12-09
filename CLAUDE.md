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

Per [MADFAM Ecosystem Standard](https://github.com/madfam-io/solarpunk-foundry/blob/main/docs/PORT_ALLOCATION.md), Janua uses the 4100-4199 block.

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
go get github.com/madfam-io/janua/packages/go-sdk
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
**Server**: foundry-core (95.217.198.239) via Cloudflare Tunnel `ssh.madfam.io`
**K8s Cluster**: K3s single-node
**Namespace**: janua

**Active Services**:
| Service | Type | Notes |
|---------|------|-------|
| janua-api | Deployment | Port 4100, ClusterIP |
| janua-dashboard | Deployment | Port 4101 |
| janua-admin | Deployment | Port 4102 |
| janua-docs | Deployment | Port 4103 |
| janua-website | Deployment | Port 4104 |

**Cloudflare Tunnels**:
- `janua-prod` - Routes api.janua.dev, auth.madfam.io, app.janua.dev, etc.
- `foundry-prod` - Routes ssh.madfam.io (SSH access)

**SystemD Services**:
- `janua-port-forward.service` - kubectl port-forward for API
- `cloudflared-janua.service` - Cloudflare tunnel connector

---

## Related Resources

- **Website**: [janua.dev](https://janua.dev)
- **GitHub**: [madfam-io/janua](https://github.com/madfam-io/janua)
- **Docs**: 204 markdown files in `docs/`
- **License**: AGPL v3

---

*Janua - The Gatekeeper | One key for the whole city*
