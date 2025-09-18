# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Plinto** is a secure identity platform providing edge-fast verification and full control. Currently in private alpha stage, operating entirely on the single domain `plinto.dev`.

**Company**: Plinto by Aureo Labs (a MADFAM company)
**Status**: Private alpha
**Domain**: https://plinto.dev

## Critical Context

### Business Model
- **Product-led growth** with enterprise overlay
- **Tiers**: Community (free, 2k MAU) → Pro ($69/mo, 10k MAU) → Scale ($299/mo, 50k MAU) → Enterprise (custom)
- **Payment**: Conekta for Mexico (MXN), Fungies.io as MoR for international
- **Internal adoption**: Replace Clerk in Forge Sight first, then MADFAM-wide rollout

### Architecture & Stack

**Infrastructure Stack**:
- **Vercel**: Next.js app hosting (marketing, docs, admin UI at plinto.dev)
- **Railway**: Core API services (FastAPI/Python), Postgres, Redis, workers
- **Cloudflare**: WAF/CDN, R2 for audit storage, Turnstile for bot protection, JWKS caching

**Core Components**:
- **Auth API (Plinto Core)**: FastAPI + SuperTokens core + OPA for policy
- **Edge Adapters**: Vercel Middleware + Cloudflare Workers for token verification
- **Admin UI**: Next.js app with RBAC-gated operations
- **SDKs**: `@plinto/nextjs`, `@plinto/react-sdk`, `@plinto/edge`, `@plinto/node`, `@plinto/core`

**Data Layer**:
- **Postgres**: Primary database (users, tenants, orgs, sessions, policies)
- **Redis**: Session cache, rate limiting, JTI blacklist
- **R2**: Long-term audit logs and exports

### Domain Routing (Single Domain Strategy)

All services operate on `plinto.dev`:
- `/` - Public site and documentation (Next.js on Vercel)
- `/docs` - Documentation
- `/admin` - Admin dashboard (RBAC-gated)
- `/api/v1/...` - Core API (proxied to Railway)
- `/.well-known/jwks.json` - JWKS endpoint (CDN-cached)
- `/.well-known/openid-configuration` - OIDC metadata

### Development Commands

Since this is currently a specification/planning repository without implementation:

```bash
# No build/test commands yet - project is in planning phase
# Implementation will include:
# - npm/pnpm commands for Next.js frontend
# - Python/FastAPI commands for backend
# - Docker compose for local development
```

### Key Technical Decisions

1. **Single-domain architecture** during alpha - everything on plinto.dev
2. **Per-tenant signing keys** with region pinning (US/EU)
3. **Edge verification** with p95 < 50ms target using cached JWKS
4. **WebAuthn/Passkeys** as primary auth method, email+password as fallback
5. **Token strategy**: Short-lived access (≤15m), refresh rotation with reuse detection

### Security Requirements

- **Passkeys/WebAuthn** preferred over passwords
- **Turnstile** on risky flows (signup, password reset)
- **Per-tenant isolation** with tenant_id everywhere
- **Audit trail** - append-only, hash-chained per user
- **HMAC-signed webhooks** with timestamp validation
- **Rate limiting** per-IP and per-tenant

### API Patterns

Base URL: `https://plinto.dev/api/v1`

Key endpoints:
- `/auth/signup`, `/auth/signin`, `/auth/signout` - Core auth flows
- `/auth/passkeys/register` - WebAuthn registration
- `/sessions/verify` - Token introspection
- `/orgs`, `/roles` - Organization and RBAC management
- `/policy/evaluate` - OPA-based policy evaluation
- `/webhooks` - Event subscriptions

### Performance Targets

- **Uptime**: 99.95% SLO
- **Auth issuance**: p95 < 120ms
- **Edge verification**: p95 < 50ms (hot cache)
- **Cold start**: < 500ms
- **DB queries**: p95 < 20ms for critical paths

### Integration Timeline

**Gate 0** (2 weeks): Passkeys + email, sessions, JWKS rotation demo
**Gate 1** (MVP, month 2): Replace auth in Forge Sight
**Gate 2** (Parity, month 4): Social logins, orgs/RBAC, webhooks, audit
**Gate 3** (Enterprise, month 6): SAML/OIDC, SCIM, data residency
**Gate 4** (GA, month 7+): Full documentation, billing, SLAs

### SDK Integration Pattern (Next.js)

The project provides a streamlined integration for Next.js apps:

1. Install: `@plinto/nextjs` and `@plinto/react-sdk`
2. Add edge middleware for route protection
3. Wrap app with `PlintoProvider`
4. Use prebuilt UI components (`<SignIn/>`, `<SignUp/>`)
5. Protect routes with `getSession()` in server components

### Environment Variables

Required for Plinto Core:
```
PLINTO_ENV=prod
DATABASE_URL=postgres://...
REDIS_URL=redis://...
EMAIL_PROVIDER=ses|sendgrid
TURNSTILE_SECRET=...
KMS_KEY_ARN=...
JWT_AUDIENCE=plinto.dev
JWT_ISSUER=https://plinto.dev
COOKIE_DOMAIN=plinto.dev
```

For client apps:
```
PLINTO_ISSUER=https://plinto.dev
PLINTO_AUDIENCE=plinto.dev
PLINTO_TENANT_ID=tenant_123
PLINTO_JWKS_URL=https://plinto.dev/.well-known/jwks.json
```

### Current Project State

This repository currently contains:
- **README.md**: Product documentation and quick start guide
- **SOFTWARE_SPEC.md**: Detailed technical architecture (v1.1)
- **BIZ_DEV.md**: Business strategy, pricing, and GTM plans (v1.0)

The actual implementation has not yet begun. The project is in the specification and planning phase.