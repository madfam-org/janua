# Plinto - Self-Hosted Authentication

**Open-source authentication for developers who want to own their auth infrastructure.**

MIT licensed. No features locked behind paid tiers. No SaaS required.

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com)

---

## What is this?

A self-hosted authentication platform built with FastAPI and modern web technologies. Think Auth0 or Clerk, but you run it on your own infrastructure and the source code is yours.

**What works:**
- ✅ Email/password authentication
- ✅ OAuth (Google, GitHub, Microsoft, etc.)
- ✅ SAML 2.0 SSO
- ✅ TOTP/SMS multi-factor authentication
- ✅ WebAuthn/Passkeys (FIDO2)
- ✅ Multi-tenancy with organizations and RBAC
- ✅ REST API with SDKs for React, Vue, Next.js, Python, Go, Flutter

**What's still rough:**
- ⚠️ Documentation is incomplete in places
- ⚠️ Not battle-tested at massive scale yet
- ⚠️ Some edge cases probably exist (file issues!)
- ⚠️ UI components need polish

**What doesn't exist:**
- ❌ Managed hosting (you need to self-host)
- ❌ Enterprise support contracts
- ❌ SOC 2 compliance reports

---

## Why build this?

**The problem:** Auth0 charges $2,000+/month for SSO. Clerk is beautiful but SaaS-only. Keycloak is powerful but has terrible developer experience.

**Our take:** Authentication features shouldn't cost enterprise prices. Self-hosting shouldn't mean suffering through Keycloak's Java-era UI.

So we built this. All features are free and open source. MIT licensed.

---

## Quick Start

### Try it locally (5 minutes)

```bash
# Clone the repository
git clone https://github.com/madfam-io/plinto.git
cd plinto

# Start the backend (PostgreSQL + Redis + FastAPI)
cd apps/api
docker-compose up -d postgres redis
pip install -r requirements.txt
uvicorn app.main:app --reload

# In another terminal, start the demo app
cd apps/demo
npm install
npm run dev

# Open http://localhost:3000
```

**That's it.** You now have working auth with SSO, MFA, and passkeys.

---

## What you get

### Backend (FastAPI + PostgreSQL)
- **202 REST endpoints** for complete auth management
- **Async Python** with SQLAlchemy 2.x
- **Redis caching** for sessions and rate limiting
- **JWT tokens** with RS256 signing
- **Audit logging** for security events
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

### Self-hosting (Production)

**Docker Compose** (Recommended):
```bash
# Clone and configure
git clone https://github.com/madfam-io/plinto.git
cd plinto/apps/api
cp .env.example .env
# Edit .env with your settings

# Start services
docker-compose up -d

# Run migrations
docker-compose exec api alembic upgrade head

# Create admin user
docker-compose exec api python scripts/create_admin.py
```

**Kubernetes:**
```bash
# Helm chart available in deployment/helm
helm install plinto ./deployment/helm/plinto \
  --set postgresql.enabled=true \
  --set redis.enabled=true
```

**Configuration:**
- See [Deployment Guide](docs/DEPLOYMENT.md) for production setup
- See [Environment Variables](docs/guides/CONFIGURATION.md) for options

---

## Using the SDKs

### React
```tsx
import { PlintoProvider, useAuth } from '@plinto/react-sdk';

function App() {
  return (
    <PlintoProvider baseURL="https://your-api.com">
      <YourApp />
    </PlintoProvider>
  );
}

function Profile() {
  const { user, signOut } = useAuth();
  return <div>Welcome, {user?.email}</div>;
}
```

### Python
```python
from plinto import PlintoClient

client = PlintoClient(base_url="https://your-api.com")

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
// app/api/auth/[...plinto]/route.ts
import { PlintoNextAuth } from '@plinto/nextjs-sdk';

export const { GET, POST } = PlintoNextAuth({
  baseURL: process.env.PLINTO_API_URL!,
});
```

---

## Architecture

```
┌─────────────────────────────────────────┐
│   Your Application (React/Vue/Next.js) │
│         Uses: @plinto/sdk               │
└────────────────┬────────────────────────┘
                 │ HTTPS/JSON
                 ▼
┌─────────────────────────────────────────┐
│      Plinto API (FastAPI)               │
│   • JWT authentication                  │
│   • OAuth/SAML/WebAuthn                 │
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

**Honest answer:** It depends.

**What we know works:**
- Core authentication flows (tested with 150+ unit tests)
- SSO integrations (SAML/OIDC tested with Okta, Azure AD)
- MFA implementations (TOTP, SMS, WebAuthn)
- Multi-tenancy and RBAC

**What we don't know yet:**
- How it performs at 100K+ users (we haven't run it there)
- Every edge case in every browser (help us test!)
- Long-term upgrade paths (we're <1 year old)

**Our recommendation:**
- ✅ Use it if you want to self-host and can debug issues
- ✅ Use it if you're okay filing bugs when you find them
- ⚠️ Don't use it if you need guaranteed uptime SLAs
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
- Adding tests for edge cases

**What we're NOT doing:**
- Building a managed SaaS version (yet)
- Chasing every feature request
- Trying to be Auth0

**Future (when we have >5K stars and prove this is valuable):**
- Managed hosting option
- Migration tools from Auth0/Clerk
- Enterprise support contracts

We'll build what the community needs. Tell us what you need.

---

## Comparison to alternatives

**vs. Auth0/Okta:**
- ✅ You own the infrastructure
- ✅ No per-user pricing
- ❌ No managed service (you run it)
- ❌ No compliance reports (yet)

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

MIT License - use it however you want.

See [LICENSE](LICENSE) for details.

---

## Support

- 📖 **Documentation:** [docs/](docs/)
- 🐛 **Bug Reports:** [GitHub Issues](https://github.com/madfam-io/plinto/issues)
- 💬 **Questions:** [GitHub Discussions](https://github.com/madfam-io/plinto/discussions)
- 📧 **Security Issues:** security@plinto.dev

**No Discord/Slack yet.** We'll create them when we have enough users to justify it.

---

## Current Status

- **Stars:** Just getting started (star us if you find this useful!)
- **Production users:** Unknown (tell us if you're using it!)
- **Contributors:** Looking for more
- **Funding:** None (bootstrapped, MIT licensed)

**We're building this in public.** The good, the bad, and the bugs.

---

*Built by developers who got tired of auth pricing and wanted to own their stack.*
