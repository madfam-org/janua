# Janua - Self-Hosted Authentication

> [!IMPORTANT]
> Janua is the ecosystem identity provider. Keep examples placeholder-only; do
> not commit or paste user records, OAuth client secrets, session/refresh/access
> tokens, JWKS/private keys, MFA/passkey/backup-code material, SAML/SCIM
> metadata, webhook payloads, migration exports, database URLs, npm tokens,
> GitHub tokens, or production credentials.

> [!IMPORTANT]
> MADFAM-ENCLII-FIRST-LEGACY-RAW v1: This document contains legacy raw infrastructure command examples.
> Routine production operations must use Enclii web, API, or CLI. Treat raw
> `kubectl`, `helm`, SSH, provider CLI/API, `docker exec`, and direct container
> access as platform bootstrap or documented break-glass only, and record any
> missing Enclii adapter gap.


> **The Auth0 alternative you can run on your own infrastructure.**
> *Zero per-user pricing. Complete control. Currently in private alpha.*

[![License](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com)
[![Status](https://img.shields.io/badge/status-private%20alpha-orange)](docs/enterprise/GA_CLAIM_MATRIX.md)
[![Coverage](https://codecov.io/gh/madfam-org/janua/branch/main/graph/badge.svg)](https://codecov.io/gh/madfam-org/janua)

**Website:** [janua.dev](https://janua.dev) | **Docs:** [docs.janua.dev](https://docs.janua.dev) | **Demo:** [demo.janua.dev](https://demo.janua.dev)

---

## Production Status

Janua runs in production today as the identity provider for the MADFAM
ecosystem — our own infrastructure, dogfooded daily. External availability is
**private alpha for design partners**. The
[GA claim matrix](docs/enterprise/GA_CLAIM_MATRIX.md) is the source of truth
for what is supported, beta, or roadmap; this README follows it.

| Service | Domain | Status |
|---------|--------|--------|
| API / OIDC Provider | `auth.madfam.io` | ✅ Running on Enclii |
| Admin Dashboard | `admin.janua.dev` | ✅ Running on Enclii |
| User Dashboard | `app.janua.dev` | ✅ Running on Enclii |
| Documentation | `docs.janua.dev` | ✅ Running on Enclii |
| Website | `janua.dev` | ✅ Running on Enclii |

**Infrastructure**: 2-Node Hetzner Cluster via [Enclii PaaS](https://github.com/madfam-org/enclii)
- Production workloads on "The Sanctuary" (dedicated server)
- CI/CD builds on "The Forge" (CPX11)
- Zero-trust ingress via Cloudflare Tunnel

**Active SSO Integrations**:
- [Enclii Dashboard](https://app.enclii.dev) (`enclii-web`)
- [Enclii Admin/Dispatch](https://admin.enclii.dev) (`dispatch-admin`)
- [Dhanam Ledger](https://dhanam.com) (`dhanam-ledger`)
- [Dhanam Admin](https://admin.dhanam.com) (`dhanam-admin`)

---

## What is this?

A self-hosted authentication platform built with FastAPI and modern web technologies. Think Auth0 or Clerk, but you run it on your own infrastructure and the source code is yours.

Every capability below is labeled against our
[GA claim matrix](docs/enterprise/GA_CLAIM_MATRIX.md): "running today" means
it powers MADFAM production SSO right now; "hardening" means the code is
implemented and in daily use, but we are still filing the hosted proof
(synthetics, E2E journeys, runbooks) we require before calling it generally
available.

**✅ Running in production today** (Janua is the SSO for the MADFAM ecosystem):

- Self-hosted OAuth2/OIDC identity provider (authorization code + PKCE)
- OpenID Connect discovery (`/.well-known/openid-configuration`) and published JWKS
- RS256-signed JWTs — verify tokens anywhere against our public keys
- Email/password authentication with secure hashing
- OAuth 2.0 social login (Google, GitHub, Microsoft, Apple, Discord, Twitter, LinkedIn, Slack)
- Magic links (passwordless email authentication), including a **hosted hop**
  for destinations outside the estate cookie domain — the link lands on Janua
  for one browser hop so the issuer can set its own first-party cookie, then
  forwards to the product ([`docs/architecture/SILENT_SSO_SESSION.md`](./docs/architecture/SILENT_SSO_SESSION.md))
- Per-tenant sending identity: a vCTO client's mail can carry its own From line
  and even send on the client's **own provider account**, as a config change
  rather than a migration ([`docs/EMAIL_SENDER_POLICY.md`](./docs/EMAIL_SENDER_POLICY.md))
- Email delivery events and first-party measurement: a signed Resend webhook
  receiver per provider account (`/api/v1/email/webhooks/resend/{account}`), and
  open/click measurement for opted-in mail that carries no sign-in or reset
  link, served from a tracking host on the tenant's own domain that answers
  nothing but the pixel and the click redirect. No recipient address, IP or
  user agent is stored ([`docs/runbooks/resend-email-events.md`](./docs/runbooks/resend-email-events.md))
- Hosted health endpoints for operations

**🔧 Implemented, hardening in progress** (in daily use; GA evidence being filed):

- Multi-factor authentication: TOTP, WebAuthn/passkeys (FIDO2), backup codes
- Multi-tenancy with organization hierarchy
- RBAC with granular permissions (treat as beta until tenant-isolation proof is current)
- Audit logging (treat as beta until retention/export proof lands)
- Admin org/user/app operations
- Client-credentials token exchange, session refresh/logout journey evidence
- Webhooks and JIT (Just-In-Time) provisioning

**🛠️ Developer experience:**

- Extensive REST API with generated OpenAPI reference at `/docs`
- SDKs: React, Vue, Next.js, TypeScript, Python, Go, Flutter, React Native
- Auth0 migration tooling (beta — dry-run first; see below)

**🗺️ Roadmap — not GA today** (details in [Roadmap](#roadmap)):

- SAML 2.0 SSO — implementation exists in the tree; commercial support is roadmap/beta until per-customer proof exists
- SCIM 2.0 user provisioning
- Compliance exports, SOC 2 Type II program, HIPAA/BAA
- Uptime SLAs and enterprise support contracts

**What we're improving:**
- ⚠️ Documentation completeness (ongoing)
- ⚠️ Scale testing beyond 100K users (planned)
- ⚠️ UI component polish (ongoing)

**Not available (by design):**
- ❌ Managed SaaS hosting (self-host only - that's the point)

---

## Role in the MADFAM monetization engine

Beyond being the ecosystem's identity provider, Janua is where **a purchase becomes access**. Catalog, checkout,
and payment are owned by other platforms; once a payment is confirmed, Janua is the component that grants the
resulting entitlement — and from then on it is the authority every other product asks *"may this user do this?"*.

That gives Janua two commercial jobs:

- **Entitlement grant** — turning a confirmed purchase into a durable `(product, tier)` grant on the buyer's identity.
- **Enforcement** — being the one place other products check before serving a paid capability, so entitlement logic
  is not re-implemented per product.

**API shape contributors should know:** an entitlement grant today resolves to a **single `(product, tier)` pair —
one purchase grants one product**. Multi-product purchases and bundles are therefore not expressible against the
current entitlement API. Supporting them is a change to this repository, not a configuration choice somewhere
upstream.

> **Boundary note.** This is a deliberately sanitized summary of the repository's *designed* role. It is not a
> statement about the live state of any deployment. The canonical end-to-end description of the monetization
> pipeline is private and lives in the `internal-devops` repository at `docs/monetization-engine.md`. Payment-side
> routes and event names, credential and signing-secret names, deployment topology, and tax/invoicing
> configuration belong there and must not be added to this repository.

_Last Updated: 2026-07-26_

---

## Why build this?

**The problem:** Auth0 charges $2,000+/month for SSO. Clerk is beautiful but SaaS-only. Keycloak is powerful but has terrible developer experience.

**Our take:** Authentication features shouldn't cost enterprise prices. Self-hosting shouldn't mean suffering through Keycloak's Java-era UI.

So we built this. All features are free and open source. AGPL v3 licensed.

---

## 💰 Migrating from Auth0?

**We built a migration tool to help you escape Auth0's pricing.**

**Status: Beta.** Per our [GA claim matrix](docs/enterprise/GA_CLAIM_MATRIX.md),
migration assistance is offered after an import/export **dry-run** for your
scope, with rollback and integrity evidence — we don't commit dates before that.

If you're paying **$2,000-5,000/month** for Auth0 (or more with SSO/SCIM), you can migrate to self-hosted Janua and run it for **~$170/month**.

**Estimated savings: $24,000-58,000/year**, depending on your Auth0 plan.

### Migration Tool Features

- ✅ **Export all users** from Auth0 (via Management API)
- ✅ **Import to Janua** with automatic data mapping
- ✅ **Preserve user data** - email, name, phone, metadata
- ✅ **Migration report** showing success/failures
- ✅ **Zero-downtime strategy** guide included

**Quick migration:**
```bash
cd scripts/migration
pip install -r requirements.txt
python auth0_migrate.py --config config.json
```

**📖 Full guide:** [scripts/migration/README.md](scripts/migration/README.md)

**Note:** Password hashes can't be migrated from Auth0 (this is normal). Users reset passwords on first login.

---

## Quick Start

### Try it locally (5 minutes)

```bash
# Clone the repository
git clone https://github.com/madfam-org/janua.git
cd janua

# Install dependencies (pnpm monorepo)
pnpm install

# Start infrastructure (PostgreSQL + Redis)
cd apps/api
docker-compose up -d postgres redis

# Setup Python environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start API
uvicorn app.main:app --reload --port 8000

# In another terminal, start the website
cd apps/website
pnpm dev

# Open http://localhost:3001 (website) or http://localhost:8000/docs (API)
```

**That's it.** You now have a working OAuth2/OIDC provider with MFA and passkeys.

---

## Monorepo Structure

This is a **pnpm workspace monorepo**. All apps and packages are managed together.

```
janua/
├── apps/
│   ├── api/          # FastAPI backend (Python)
│   ├── dashboard/    # User management UI (Next.js)
│   ├── website/      # Public website + demos (Next.js)
│   ├── admin/        # Internal admin tools
│   └── docs/         # Documentation site
├── packages/
│   ├── ui/           # Shared React components (@janua/ui)
│   ├── sdk/          # Client SDK (@janua/sdk)
│   ├── database/     # Database schemas
│   └── config/       # Shared configs
└── deployment/
    └── production/   # Docker, nginx, monitoring
```

### Monorepo Commands

```bash
# Install all dependencies
pnpm install

# Build all packages
pnpm build

# Run all apps in dev mode
pnpm dev

# Run specific app
pnpm --filter @janua/website dev
pnpm --filter @janua/dashboard dev

# Lint/typecheck
pnpm lint
pnpm typecheck
```

---

## What you get

### Backend (FastAPI + PostgreSQL)
- **Full REST API** for auth, user, org, and MFA management
- **Async Python** with SQLAlchemy 2.x
- **Redis caching** for sessions and rate limiting
- **JWT tokens** with RS256 signing and published JWKS
- **Audit logging** for security events (beta)
- **OpenAPI docs** at `/docs`

### Frontend SDKs
- **React SDK** - Hooks and components
- **Vue SDK** - Composables for Vue 3
- **Next.js SDK** - App Router support
- **TypeScript SDK** - Type-safe client
- **Python SDK** - For backend integration
- **Go SDK** - For Go services
- **Flutter SDK** - For mobile apps

### UI Components (React)
- **15 pre-built components** - SignIn, SignUp, MFA, etc.
- **Radix UI primitives** - Accessible by default
- **Customizable styling** - Bring your own CSS

---

## Installation

### NPM Registry Configuration

Janua SDKs are published to MADFAM's private npm registry. Configure your `.npmrc` before installing:

```bash
# Add to your project's .npmrc or ~/.npmrc
@janua:registry=https://npm.madfam.io
//npm.madfam.io/:_authToken=${NPM_MADFAM_TOKEN}
```

For CI/CD environments, set the `NPM_MADFAM_TOKEN` secret in your GitHub Actions or CI platform.

### Self-hosting (Production)

**Docker Compose** (Recommended):
```bash
# Clone and configure
git clone https://github.com/madfam-org/janua.git
cd janua

# Copy environment files
cp .env.example .env
cp apps/api/.env.example apps/api/.env
cp apps/dashboard/.env.example apps/dashboard/.env
cp apps/website/.env.example apps/website/.env

# Edit .env files with your settings

# Start all services
cd deployment/production
docker-compose -f docker-compose.production.yml up -d

# Run migrations
docker-compose exec janua-api alembic upgrade head
```

> MADFAM's hosted production does not run migrations on deploy: each revision is
> applied by hand before the image that needs it is promoted, and
> `apps/api/alembic/PROD_ALEMBIC_STATE.json` records what production was last
> verified at, which the promote guard checks
> ([`docs/runbooks/ALEMBIC_CONVERGENCE.md`](docs/runbooks/ALEMBIC_CONVERGENCE.md)).

**Build Docker Images:**
```bash
# From project root
docker build -f Dockerfile.api -t janua/api:latest .
docker build -f Dockerfile.dashboard -t janua/dashboard:latest .
docker build -f Dockerfile.website -t janua/website:latest .
```

**Kubernetes:**
```bash
# Helm chart available in deployment/helm
helm install janua ./deployment/helm/janua \
  --set postgresql.enabled=true \
  --set redis.enabled=true
```

**Configuration:**
- See [Production Deployment Guide](deployment/production/README.md) for bare metal/VPS setup
- See [Deployment Guide](docs/DEPLOYMENT.md) for cloud deployment
- See [Environment Variables](docs/guides/CONFIGURATION.md) for options

---

## Using the SDKs

### Install SDKs

```bash
# React SDK
npm install @janua/react-sdk

# Vue SDK
npm install @janua/vue-sdk

# Next.js SDK
npm install @janua/nextjs-sdk

# TypeScript SDK (core client)
npm install @janua/typescript-sdk
```

### React
```tsx
import { JanuaProvider, useAuth } from '@janua/react-sdk';

function App() {
  return (
    <JanuaProvider baseURL="https://your-api.com">
      <YourApp />
    </JanuaProvider>
  );
}

function Profile() {
  const { user, signOut } = useAuth();
  return <div>Welcome, {user?.email}</div>;
}
```

### Python
```python
from janua import JanuaClient

client = JanuaClient(base_url="https://your-api.com")

# Authenticate
result = await client.auth.sign_in(
    email="user@example.com",
    password="password"
)

# Get user
user = await client.users.get_current_user()
```

### Next.js
```typescript
// app/api/auth/[...janua]/route.ts
import { JanuaNextAuth } from '@janua/nextjs-sdk';

export const { GET, POST } = JanuaNextAuth({
  baseURL: process.env.JANUA_API_URL!,
});
```

---

## Architecture

```
┌─────────────────────────────────────────┐
│   Your Application (React/Vue/Next.js) │
│         Uses: @janua/sdk               │
└────────────────┬────────────────────────┘
                 │ HTTPS/JSON
                 ▼
┌─────────────────────────────────────────┐
│      Janua API (FastAPI)               │
│   • JWT authentication                  │
│   • OAuth/OIDC/WebAuthn                 │
│   • User/org management                 │
│   • Audit logging                       │
└─────┬──────────────────────┬────────────┘
      │                      │
      ▼                      ▼
┌──────────┐          ┌─────────────┐
│PostgreSQL│          │    Redis    │
│ (users,  │          │ (sessions,  │
│  orgs)   │          │  cache)     │
└──────────┘          └─────────────┘
```

**You control everything.** Your database, your infrastructure, your data.

---

## Is this production-ready?

**Honest answer:** it runs our production, and we hold ourselves to a written
standard — the [GA claim matrix](docs/enterprise/GA_CLAIM_MATRIX.md) — before
claiming it can run yours.

**What runs in production today:**
- Janua is the identity provider for the MADFAM ecosystem (Enclii, Dhanam, and more) — OIDC discovery, JWKS, and hosted health checks are exercised daily
- Core authentication flows, covered by the unit/integration test suite
- MFA implementations (TOTP, WebAuthn/passkeys, backup codes)

**What we require before calling a capability GA:**
- Hosted synthetic or E2E journey evidence (login, session refresh/logout, admin operations)
- Tenant-isolation and role test matrices for RBAC
- Retention/export proof for audit logs
- A support runbook and named ownership

**What we don't know yet:**
- How it performs at 100K+ users (we haven't run it there)
- Every edge case in every browser (help us test!)
- Long-term upgrade paths (the project is young)

**Our recommendation:**
- ✅ Use it if you want to self-host and can debug issues
- ✅ Use it if you're okay filing bugs when you find them
- ✅ Talk to us about the design-partner program if you need SAML/SCIM/compliance on a committed timeline
- ⚠️ Don't use it if you need guaranteed uptime SLAs today
- ⚠️ Don't use it if you can't troubleshoot Docker/PostgreSQL

---

## Contributing

We need help. This is a big project and we're a small team.

**Where we need help most:**
- 🐛 **Testing** - Run it, break it, file issues
- 📚 **Documentation** - Fill in gaps, fix errors
- 🎨 **UI Polish** - Make components more accessible
- 🔧 **Bug Fixes** - Pick an issue, submit a PR
- 💬 **Support** - Help others on GitHub issues

**How to contribute:**
1. Read [CONTRIBUTING.md](CONTRIBUTING.md)
2. Pick an issue or file a new one
3. Submit a PR
4. We'll review and merge

**We're friendly to first-time contributors.** Seriously.

---

## Roadmap

**What we're focused on now:**
- Making setup easier (one-command installs)
- Improving documentation
- Fixing bugs as they're reported
- Testing the Auth0 migration tool with real users (beta)

**Enterprise track** — gated by the [GA claim matrix](docs/enterprise/GA_CLAIM_MATRIX.md); each item ships when its hosted proof is filed:
- SAML 2.0 SSO commercial support (implementation exists; needs per-customer IdP proof and a support runbook)
- SCIM 2.0 provisioning (needs create/update/deactivate synthetics)
- Compliance exports (needs export/delete evidence and a retention policy)
- SOC 2 Type II program; HIPAA/BAA legal review
- Published uptime SLA (needs 30-day evidence and a support schedule)

**What we're NOT doing:**
- Building a managed SaaS version (yet)
- Chasing every feature request
- Trying to be Auth0

**What we just shipped:**
- ✅ Auth0 migration tool (help us test it!)

**Future (when we have >5K stars and prove this is valuable):**
- Managed hosting option
- Clerk/Firebase migration tools
- Enterprise support contracts

We'll build what the community needs. Tell us what you need.

---

## Comparison to alternatives

**vs. Auth0/Okta:**
- ✅ You own the infrastructure
- ✅ No per-user pricing (est. $24K-58K/year savings)
- ✅ Migration tool included (beta — export users from Auth0)
- ❌ No managed service (you run it)
- ❌ No compliance reports (SOC 2 is on the roadmap, not a current certification)

**vs. Clerk:**
- ✅ Self-hostable
- ✅ Direct database access (no webhooks)
- ❌ UI components are less polished
- ❌ No managed option (yet)

**vs. Keycloak:**
- ✅ Better developer experience
- ✅ Modern tech stack (FastAPI vs Java)
- ❌ Less mature (Keycloak is 10+ years old)
- ❌ Smaller community

**vs. Better-Auth:**
- ✅ Full backend included (not just SDK)
- ✅ UI components included
- ❌ More opinionated (FastAPI + PostgreSQL)

**Bottom line:** Use this if you want to self-host and modern DX matters to you.

---

## License

AGPL-3.0 License - GNU Affero General Public License v3.0

Copyright (C) 2025 Innovaciones MADFAM SAS de CV

See [LICENSE](LICENSE) for details.

---

## Support

- 📖 **Documentation:** [docs/](docs/)
- 🐛 **Bug Reports:** [GitHub Issues](https://github.com/madfam-org/janua/issues)
- 💬 **Questions:** [GitHub Discussions](https://github.com/madfam-org/janua/discussions)
- 📧 **Security Issues:** security@janua.dev

**No Discord/Slack yet.** We'll create them when we have enough users to justify it.

---

## LLM-Friendly

Janua provides [llmstxt.org](https://llmstxt.org) standardized documentation for AI agents:
- [llms.txt](llms.txt) — Quick navigation
- [llms-full.txt](llms-full.txt) — Complete reference

---

## Current Status

- **Stars:** Just getting started (star us if you find this useful!)
- **Production users:** Unknown (tell us if you're using it!)
- **Contributors:** Looking for more
- **Funding:** None (bootstrapped, AGPL v3 licensed)

**We're building this in public.** The good, the bad, and the bugs.

---

*Built by developers who got tired of auth pricing and wanted to own their stack.*
# Build trigger 1768191189
