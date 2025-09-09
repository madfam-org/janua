# 📚 Plinto Project Index

## 🏗️ Project Overview
**Plinto** - Secure identity platform providing edge-fast verification with full control  
**Status**: Private Alpha  
**Repository**: [github.com/madfam-io/plinto](https://github.com/madfam-io/plinto)

---

## 📖 Documentation Map

### Core Documentation
| Document | Purpose | Key Topics |
|----------|---------|------------|
| [`README.md`](../README.md) | Project overview & quick start | Installation, usage, features |
| [`ARCHITECTURE.md`](./architecture/ARCHITECTURE.md) | System design & technical architecture | Hexagonal architecture, domain model, deployment |
| [`SUBDOMAIN_ARCHITECTURE.md`](./architecture/SUBDOMAIN_ARCHITECTURE.md) | Domain mapping & folder structure | Subdomains, deployment strategy, DNS |
| [`SOFTWARE_SPEC.md`](./technical/SOFTWARE_SPEC.md) | Technical specification (v1.1) | Requirements, constraints, milestones |
| [`BIZ_DEV.md`](./business/BIZ_DEV.md) | Business strategy & GTM plan | Pricing, positioning, growth strategy |

### Technical Documentation
| Document | Purpose | Key Topics |
|----------|---------|------------|
| [`API_SPECIFICATION.md`](./reference/API_SPECIFICATION.md) | API design & endpoints | REST API, authentication flows, webhooks |
| [`DATABASE_DESIGN.md`](./technical/DATABASE_DESIGN.md) | Database schema & models | PostgreSQL schema, relationships, indexes |
| [`IMPLEMENTATION_GUIDE.md`](./guides/IMPLEMENTATION_GUIDE.md) | Development roadmap | Gate milestones, feature priorities |
| [`MARKETING_DESIGN.md`](./guides/MARKETING_DESIGN.md) | Marketing site design | UI/UX, components, content structure |
| [`CLAUDE.md`](./guides/CLAUDE.md) | AI assistant guidelines | Development patterns, conventions |

---

## 🗂️ Project Structure

### Applications (`/apps`)
| App | Subdomain | Port | Purpose | Status |
|-----|-----------|------|---------|--------|
| **marketing** | plinto.dev | 3003 | Public website & landing pages | ✅ Deployed |
| **dashboard** | app.plinto.dev | 3001 | Customer tenant management | 🔧 In Development |
| **admin** | admin.plinto.dev | 3002 | Internal superadmin tools | 🔧 In Development |
| **api** | api.plinto.dev | 8000 | Core API (FastAPI/Python) | 📝 Planned |

### Packages (`/packages`)
| Package | Name | Purpose | Status |
|---------|------|---------|--------|
| **ui** | @plinto/ui | Shared UI component library | ✅ Active |
| **sdk-js** | @plinto/sdk | JavaScript/TypeScript SDK | ✅ Active |
| **react** | @plinto/react | React hooks & components | ✅ Active |

### Infrastructure
```
infrastructure/
├── vercel/          # Frontend deployment configs
├── railway/         # API deployment configs
└── docker/          # Container configurations
```

---

## 🚀 Quick Navigation

### For Developers
- **Getting Started**: [`README.md`](../README.md#quick-start)
- **API Reference**: [`API_SPECIFICATION.md`](./reference/API_SPECIFICATION.md)
- **Database Schema**: [`DATABASE_DESIGN.md`](./technical/DATABASE_DESIGN.md)
- **Implementation Roadmap**: [`IMPLEMENTATION_GUIDE.md`](./guides/IMPLEMENTATION_GUIDE.md)

### For Business/Product
- **Business Strategy**: [`BIZ_DEV.md`](./business/BIZ_DEV.md)
- **Marketing Design**: [`MARKETING_DESIGN.md`](./guides/MARKETING_DESIGN.md)
- **Pricing & Tiers**: [`BIZ_DEV.md#pricing-tiers`](./business/BIZ_DEV.md)

### For DevOps/Infrastructure
- **Architecture Overview**: [`ARCHITECTURE.md`](./architecture/ARCHITECTURE.md)
- **Subdomain Strategy**: [`SUBDOMAIN_ARCHITECTURE.md`](./architecture/SUBDOMAIN_ARCHITECTURE.md)
- **Deployment Guide**: [`SUBDOMAIN_ARCHITECTURE.md#deployment-commands`](./architecture/SUBDOMAIN_ARCHITECTURE.md)

---

## 🔗 Key API Endpoints

### Authentication
- `POST /api/v1/auth/signup` - User registration
- `POST /api/v1/auth/signin` - User login
- `POST /api/v1/auth/signout` - User logout
- `POST /api/v1/auth/refresh` - Token refresh
- `POST /api/v1/auth/passkeys/register` - Register passkey
- `POST /api/v1/auth/passkeys/authenticate` - Authenticate with passkey

### Session Management
- `GET /api/v1/sessions/verify` - Verify JWT token
- `GET /api/v1/sessions/current` - Get current session
- `DELETE /api/v1/sessions/{id}` - Revoke session

### Organization & RBAC
- `GET /api/v1/orgs` - List organizations
- `POST /api/v1/orgs` - Create organization
- `GET /api/v1/orgs/{id}/members` - List members
- `POST /api/v1/orgs/{id}/invites` - Send invitation

Full API documentation: [`API_SPECIFICATION.md`](./reference/API_SPECIFICATION.md)

---

## 🎯 Development Milestones

### Gate 0: Foundation (2 weeks)
- [x] Basic authentication (email + passkeys)
- [x] Session management
- [ ] JWKS endpoint & rotation
- [ ] Basic SDK (TypeScript)

### Gate 1: MVP (Month 2)
- [ ] Replace Forge Sight auth
- [ ] Production deployment
- [ ] Monitoring & alerting
- [ ] Basic documentation

### Gate 2: Feature Parity (Month 4)
- [ ] Social logins (Google, GitHub)
- [ ] Organizations & RBAC
- [ ] Webhooks
- [ ] Audit logging
- [ ] Admin dashboard

### Gate 3: Enterprise (Month 6)
- [ ] SAML/OIDC providers
- [ ] SCIM provisioning
- [ ] Data residency (EU/US)
- [ ] Advanced security features

Full roadmap: [`IMPLEMENTATION_GUIDE.md`](./guides/IMPLEMENTATION_GUIDE.md)

---

## 🛠️ Development Commands

### Setup
```bash
# Install dependencies
yarn install

# Setup environment
cp .env.example .env.local
```

### Development
```bash
# Run all apps
yarn dev

# Run specific apps
yarn workspace @plinto/marketing dev     # http://localhost:3003
yarn workspace @plinto/dashboard dev     # http://localhost:3001
yarn workspace @plinto/admin dev         # http://localhost:3002

# API (Python/FastAPI)
cd apps/api && uvicorn main:app --reload # http://localhost:8000
```

### Build & Deploy
```bash
# Build all
yarn build

# Deploy marketing
cd apps/marketing && vercel --prod

# Deploy dashboard
cd apps/dashboard && vercel --prod --scope plinto

# Deploy API
railway up -p plinto-api
```

---

## 📊 Technical Stack

### Frontend
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Library**: Radix UI + Custom components
- **State**: React Query + Zustand

### Backend
- **API**: FastAPI (Python)
- **Database**: PostgreSQL
- **Cache**: Redis
- **Auth Engine**: SuperTokens Core
- **Policy Engine**: Open Policy Agent (OPA)

### Infrastructure
- **Frontend Hosting**: Vercel
- **API Hosting**: Railway
- **CDN/WAF**: Cloudflare
- **Storage**: Cloudflare R2
- **Monitoring**: Datadog / Sentry

---

## 🔐 Security & Compliance

### Security Features
- **Passkeys/WebAuthn** as primary auth
- **Per-tenant signing keys**
- **JWT rotation** with short-lived tokens
- **Rate limiting** at edge and API
- **Audit logging** with hash-chaining

### Compliance
- **SOC 2 Type II** (planned)
- **GDPR & CCPA** compliant
- **HIPAA** ready architecture
- **Data residency** options (EU/US)

---

## 📈 Business Model

### Pricing Tiers
| Tier | Price | MAU | Features |
|------|-------|-----|----------|
| **Community** | Free | 2,000 | Basic features, community support |
| **Pro** | $69/mo | 10,000 | Custom domains, email support |
| **Scale** | $299/mo | 50,000 | Priority support, advanced features |
| **Enterprise** | Custom | Unlimited | SAML, SCIM, dedicated support |

Full pricing: [`BIZ_DEV.md#pricing-tiers`](./business/BIZ_DEV.md)

---

## 🤝 Contributing

### Development Workflow
1. Create feature branch from `main`
2. Follow conventions in [`CLAUDE.md`](./guides/CLAUDE.md)
3. Test locally with `yarn test`
4. Submit PR with description

### Key Conventions
- **Commit format**: `type: description` (e.g., `fix: authentication flow`)
- **Branch naming**: `feature/description` or `fix/issue`
- **Code style**: ESLint + Prettier (auto-formatted)

---

## 📞 Support & Resources

### Internal Resources
- **Documentation**: This index and linked documents
- **Slack**: #plinto-dev channel
- **GitHub Issues**: [github.com/madfam-io/plinto/issues](https://github.com/madfam-io/plinto/issues)

### External Resources
- **Production**: [plinto.dev](https://plinto.dev)
- **Dashboard**: [app.plinto.dev](https://app.plinto.dev)
- **Status**: [status.plinto.dev](https://status.plinto.dev)
- **API**: [api.plinto.dev](https://api.plinto.dev)

---

*Last updated: January 9, 2025*  
*Version: 0.1.0 (Private Alpha)*