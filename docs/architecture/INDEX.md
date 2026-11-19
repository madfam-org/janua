# Architecture Documentation Index

> **Navigation hub** for all Janua architecture documentation

## Quick Links

| Document | Description |
|----------|-------------|
| [Architecture Overview](./ARCHITECTURE.md) | System design and component relationships |
| [API Structure](./API_STRUCTURE.md) | FastAPI router organization and patterns |
| [Subdomain Architecture](./SUBDOMAIN_ARCHITECTURE.md) | Multi-domain deployment strategy |
| [Universal Keyring (ADR-002)](./ADR-002_UNIVERSAL_KEYRING.md) | Cross-project authentication design |
| [Silent SSO Session](./SILENT_SSO_SESSION.md) | Where the browser session comes from on a magic-link login (B1–B8), the estate cookie, account switching, and silent sign-in for marked public clients (B8) |
| [Claims de organización y service principals](./CLAIMS_DE_ORGANIZACION_Y_SERVICE_PRINCIPALS.md) | Organization, role and tier claims on session and OIDC tokens (Spanish) |
| [Issuer, JWKS and audience](../reference/ISSUER_AND_JWKS.md) | How resource servers verify Janua tokens |

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Client Applications                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │  React  │ │ Next.js │ │   Vue   │ │ Mobile  │           │
│  │   SDK   │ │   SDK   │ │   SDK   │ │  SDKs   │           │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │
└───────│──────────│──────────│──────────│────────────────────┘
        │          │          │          │
        └──────────┴──────────┴──────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                     API Gateway Layer                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              FastAPI Application                     │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │    │
│  │  │  Auth   │ │  Users  │ │  Orgs   │ │   MFA   │   │    │
│  │  │ Router  │ │ Router  │ │ Router  │ │ Router  │   │    │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │    │
│  │       └──────────┴──────────┴──────────┘           │    │
│  │                     │                               │    │
│  │              ┌──────▼──────┐                        │    │
│  │              │   Services   │                        │    │
│  │              │    Layer     │                        │    │
│  │              └──────┬──────┘                        │    │
│  └─────────────────────│───────────────────────────────┘    │
└────────────────────────│────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Data & Infrastructure                      │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │ PostgreSQL│  │   Redis   │  │   MinIO   │               │
│  │  (Users,  │  │ (Sessions,│  │  (Files,  │               │
│  │   Orgs)   │  │   Cache)  │  │  Avatars) │               │
│  └───────────┘  └───────────┘  └───────────┘               │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### API Layer (`/apps/api`)

The FastAPI backend handles all authentication and user management:

| Path | Purpose |
|------|---------|
| `app/routers/v1/` | API endpoint handlers |
| `app/services/` | Business logic layer |
| `app/models/` | SQLAlchemy ORM models |
| `app/schemas/` | Pydantic request/response schemas |
| `app/middleware/` | Request processing middleware |
| `app/core/` | Core utilities (exceptions, config, etc.) |
| `app/sso/` | SAML/SSO implementation |

### Frontend Applications

| App | Port | Purpose |
|-----|------|---------|
| Dashboard | 4101 | User-facing management UI |
| Admin | 4102 | Platform administration |
| Docs | 4103 | Documentation site |
| Website | 4104 | Marketing/landing page |
| Demo | 4105 | Demo application |

### SDKs (`/packages`)

| SDK | Platform | Key Files |
|-----|----------|-----------|
| `react-sdk` | React 18+ | `src/hooks/`, `src/components/` |
| `nextjs-sdk` | Next.js 13+ | `src/server/`, `src/client/` |
| `vue-sdk` | Vue 3+ | `src/composables/` |
| `typescript-sdk` | Any JS/TS | `src/client.ts`, `src/types.ts` |
| `python-sdk` | Python 3.8+ | `src/janua/client.py` |
| `go-sdk` | Go 1.21+ | `janua/client.go` |
| `flutter-sdk` | Flutter 3+ | `lib/src/` |
| `react-native-sdk` | RN 0.70+ | `src/` |

## Architecture Decision Records (ADRs)

ADRs document significant architectural decisions:

| ADR | Title | Status |
|-----|-------|--------|
| ADR-001 | [Auth Flow Design](./ADR-001_AUTH_FLOW.md) | Proposed |
| ADR-002 | [Universal Keyring](./ADR-002_UNIVERSAL_KEYRING.md) | Accepted |
| ADR-003 | [Multi-tenancy Strategy](./ADR-003_MULTITENANCY.md) | Proposed |
| ADR-004 | [Capability Links](./ADR-004_CAPABILITY_LINKS.md) | Proposed |

## Key Design Decisions

### Authentication Flow

1. **Token Strategy**: RS256 JWT with short-lived access tokens (15min) and long-lived refresh tokens (7 days)
2. **Session Storage**: Redis for session data with PostgreSQL backup for audit
3. **MFA**: TOTP primary, SMS secondary, backup codes for recovery

### Multi-Tenancy

1. **Organization-based**: Users belong to organizations with role-based permissions
2. **Data Isolation**: Row-level security with organization_id in all relevant tables
3. **Rate Limiting**: Per-tenant limits based on billing plan

### Scalability

1. **Stateless API**: All state in database/Redis, horizontal scaling ready
2. **Connection Pooling**: SQLAlchemy async with connection pooling
3. **Caching**: Redis caching for frequently accessed data

## Security Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Security Layers                       │
├─────────────────────────────────────────────────────────┤
│ Layer 1: Edge                                           │
│   - Cloudflare WAF & DDoS protection                    │
│   - TLS 1.3 termination                                 │
│   - Geographic blocking                                  │
├─────────────────────────────────────────────────────────┤
│ Layer 2: Application                                     │
│   - Rate limiting (IP + tenant + endpoint)              │
│   - Input validation (Pydantic schemas)                 │
│   - CORS policy enforcement                             │
├─────────────────────────────────────────────────────────┤
│ Layer 3: Authentication                                  │
│   - JWT verification with RS256                         │
│   - MFA enforcement                                      │
│   - Session validation                                   │
├─────────────────────────────────────────────────────────┤
│ Layer 4: Authorization                                   │
│   - RBAC with organization context                      │
│   - Policy-based access control                         │
│   - Resource-level permissions                          │
├─────────────────────────────────────────────────────────┤
│ Layer 5: Data                                           │
│   - Row-level security                                   │
│   - Encryption at rest (PostgreSQL)                     │
│   - Audit logging                                        │
└─────────────────────────────────────────────────────────┘
```

## Related Documentation

- [API Endpoints Reference](/apps/api/docs/api/endpoints-reference.md)
- [Security Guidelines](/docs/security/SECURITY.md)
- [Deployment Guide](/docs/deployment/)
- [Performance Tuning](/docs/guides/PERFORMANCE_TUNING_GUIDE.md)
- [Troubleshooting](/docs/guides/TROUBLESHOOTING_GUIDE.md)

## Key File Locations

### Backend Critical Paths

| Purpose | Path |
|---------|------|
| App entry point | `apps/api/app/main.py` |
| Configuration | `apps/api/app/config.py` |
| Auth service | `apps/api/app/services/auth_service.py` |
| JWT handling | `apps/api/app/services/jwt_service.py` |
| Rate limiting | `apps/api/app/middleware/rate_limit.py` |
| Database models | `apps/api/app/models/` |
| API routers | `apps/api/app/routers/v1/` |
| Error handling | `apps/api/app/core/errors.py` |

### Database

| Purpose | Path |
|---------|------|
| Migrations | `apps/api/alembic/versions/` |
| Alembic config | `apps/api/alembic.ini` |
| Model definitions | `apps/api/app/models/*.py` |

### Infrastructure

| Purpose | Path |
|---------|------|
| Docker Compose | `apps/api/docker-compose.yml` |
| Kubernetes manifests | `k8s/` |
| Cloudflare tunnel | `enclii/infra/k8s/production/cloudflared-unified.yaml` |
