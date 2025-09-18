# Project Documentation Index

> **Complete documentation map** for the Plinto monorepo

**Last Updated:** January 2025 · **Status:** Active Development

## 📚 Documentation Structure

### Quick Navigation

- 🏗️ [Architecture](#architecture)
- 💻 [Technical](#technical)
- 🚀 [Deployment](#deployment)
- 📡 [API](#api)
- 🧪 [Testing](#testing)
- 📊 [Business](#business)
- 🛠️ [Operations](#operations)

---

## 🏗️ Architecture

### System Design
- [System Architecture Overview](./architecture/system-overview.md) - High-level system design
- [Microservices Architecture](./architecture/microservices.md) - Service decomposition
- [Database Design](./architecture/database-design.md) - Schema and relationships
- [Security Architecture](./architecture/security-model.md) - Security layers and patterns

### Technical Decisions
- [Technology Stack](./technical/tech-stack.md) - Framework and library choices
- [Monorepo Structure](./technical/monorepo-structure.md) - Workspace organization
- [Design Patterns](./architecture/design-patterns.md) - Architectural patterns used

## 💻 Technical

### Development
- [Development Setup](./guides/development-setup.md) - Local environment configuration
- [Coding Standards](./technical/coding-standards.md) - Style guides and conventions
- [Testing Strategy](./technical/testing-strategy.md) - **NEW** Comprehensive testing approach
- [Performance Guidelines](./technical/performance.md) - Optimization strategies

### Codebase
- [Codebase Analysis](./technical/codebase-analysis.md) - Code structure and quality
- [Dependencies](./technical/dependencies.md) - Package management
- [Build System](./technical/build-system.md) - Turbo and compilation

## 🚀 Deployment

### Platform Guides
- [Railway Deployment](./deployment/railway-setup.md) - **UPDATED** Backend deployment
- [Vercel Deployment](./deployment/vercel-setup.md) - Frontend deployment
- [Cloudflare Integration](./deployment/cloudflare.md) - CDN and edge services
- [Docker Configuration](./deployment/docker.md) - Container setup

### CI/CD
- [GitHub Actions](./deployment/github-actions.md) - Automation workflows
- [Release Process](./deployment/release-process.md) - Version management
- [Environment Management](./deployment/environments.md) - Dev/staging/prod setup

## 📡 API

### Documentation
- [API Overview](./api/overview.md) - RESTful API design
- [Authentication](./api/authentication.md) - Auth flows and security
- [Endpoints Reference](./api/endpoints.md) - Complete endpoint documentation
- [WebSocket Events](./api/websockets.md) - Real-time communication

### Integration
- [SDK Documentation](./api/sdk-docs.md) - Client library usage
- [Webhooks](./api/webhooks.md) - Event notifications
- [Rate Limiting](./api/rate-limiting.md) - API throttling rules

## 🧪 Testing

### Test Documentation
- [Testing Strategy](./technical/testing-strategy.md) - **NEW** Comprehensive testing approach
- [Unit Testing Guide](./testing/unit-tests.md) - Component testing
- [Integration Testing](./testing/integration-tests.md) - System testing
- [E2E Testing](./testing/e2e-tests.md) - User journey testing

### Quality Assurance
- [Coverage Reports](../coverage/) - Test coverage metrics
- [Performance Testing](./testing/performance.md) - Load and stress testing
- [Security Testing](./testing/security.md) - Vulnerability assessment

## 📊 Business

### Strategy
- [Go-to-Market Strategy](./business/gtm-strategy.md) - Market approach
- [Pricing Model](./business/pricing.md) - Monetization strategy
- [Competitive Analysis](./business/competitive-analysis.md) - Market positioning

### Product
- [Product Roadmap](./business/roadmap.md) - Feature timeline
- [User Personas](./business/user-personas.md) - Target audience
- [Use Cases](./business/use-cases.md) - Application scenarios

## 🛠️ Operations

### Production
- [Production Readiness](./operations/production-readiness.md) - Launch checklist
- [Monitoring & Alerts](./operations/monitoring.md) - Observability setup
- [Incident Response](./operations/incident-response.md) - Emergency procedures
- [Backup & Recovery](./operations/backup-recovery.md) - Data protection

### Maintenance
- [Troubleshooting Guide](./operations/troubleshooting.md) - Common issues
- [Performance Tuning](./operations/performance-tuning.md) - Optimization
- [Security Updates](./operations/security-updates.md) - Patch management

## 📂 Application-Specific Documentation

### Frontend Applications

#### Dashboard (`apps/dashboard`)
- **README:** [Dashboard README](../apps/dashboard/README.md) - *To be created*
- **Port:** 3001
- **Domain:** app.plinto.dev
- **Stack:** Next.js 14, TanStack Query

#### Admin Panel (`apps/admin`)
- **README:** [Admin README](../apps/admin/README.md) - *To be created*
- **Port:** 3004
- **Domain:** admin.plinto.dev
- **Stack:** Next.js 14, Enhanced security

#### Marketing Site (`apps/marketing`)
- **README:** [Marketing README](../apps/marketing/README.md) - *To be created*
- **Port:** 3003
- **Domain:** plinto.dev
- **Stack:** Next.js 14, Three.js

#### Demo App (`apps/demo`)
- **README:** [Demo README](../apps/demo/README.md) - *To be created*
- **Port:** 3002
- **Domain:** demo.plinto.dev
- **Stack:** Next.js 14, Framer Motion

#### Documentation (`apps/docs`)
- **README:** [Docs README](../apps/docs/README.md) - *To be created*
- **Port:** 3003 ⚠️ (conflict with marketing)
- **Domain:** docs.plinto.dev
- **Stack:** Next.js 14, MDX

### Backend Applications

#### API (`apps/api`)
- **README:** [API README](../apps/api/README.md) - **✅ CREATED**
- **Port:** 8000
- **Domain:** api.plinto.dev
- **Stack:** FastAPI, PostgreSQL, Redis
- **Coverage:** 22% (target: 100%)

#### Edge Verify (`apps/edge-verify`)
- **README:** [Edge Verify README](../apps/edge-verify/README.md) - *To be created*
- **Purpose:** Edge runtime verification
- **Stack:** Vercel Edge Functions

## 📦 Package Documentation

### UI/Component Libraries

#### @plinto/ui
- **README:** [UI Package README](../packages/ui/README.md) - *To be created*
- **Purpose:** Shared design system
- **Stack:** Radix UI, Tailwind CSS

#### @plinto/react-sdk
- **README:** [React Package README](../packages/react/README.md) - *To be created*
- **Purpose:** React hooks and utilities
- **Dependencies:** React 18+

### SDK Libraries

#### @plinto/sdk
- **README:** [SDK README](../packages/sdk/README.md) - *To be created*
- **Purpose:** Core JavaScript SDK
- **Support:** Browser & Node.js

#### @plinto/sdk-js
- **README:** [SDK-JS README](../packages/sdk-js/README.md) - *To be created*
- **Purpose:** Alternative SDK implementation
- **Status:** In development

### Utility Packages

#### @plinto/core
- **README:** [Core README](../packages/core/README.md) - *To be created*
- **Purpose:** Shared business logic
- **Status:** Placeholder

#### @plinto/database
- **README:** [Database README](../packages/database/README.md) - *To be created*
- **Purpose:** Database utilities
- **Status:** Placeholder

#### @plinto/monitoring
- **README:** [Monitoring README](../packages/monitoring/README.md) - *To be created*
- **Purpose:** Observability utilities
- **Stack:** OpenTelemetry

#### @plinto/mock-api
- **README:** [Mock API README](../packages/mock-api/README.md) - *To be created*
- **Purpose:** Development API server
- **Port:** 4000

## 📈 Documentation Status

### Coverage Summary

| Category | Status | Completion |
|----------|--------|------------|
| Architecture | ✅ Complete | 100% |
| Technical | 🚧 In Progress | 85% |
| Deployment | ✅ Complete | 100% |
| API | 🚧 In Progress | 70% |
| Testing | ✅ Complete | 100% |
| Business | ✅ Complete | 100% |
| Operations | 🚧 In Progress | 80% |
| App READMEs | ⚠️ Needs Work | 14% (1/7) |
| Package READMEs | ❌ Missing | 0% (0/9) |

### Priority Items

1. **High Priority**
   - Create README files for all applications
   - Create README files for core packages (@plinto/ui, @plinto/sdk)
   - Complete API endpoint documentation
   - Resolve port conflict (docs/marketing)

2. **Medium Priority**
   - Document SDK usage examples
   - Create component library documentation
   - Add troubleshooting guides

3. **Low Priority**
   - Add architecture diagrams
   - Create video tutorials
   - Expand use case documentation

## 🔄 Maintenance

### Update Schedule

- **Weekly:** Update deployment status, test coverage
- **Bi-weekly:** Review and update technical documentation
- **Monthly:** Update architecture and design docs
- **Quarterly:** Full documentation audit

### Contributing

To contribute to documentation:
1. Follow the [Documentation Style Guide](./guides/documentation-style.md)
2. Update this index when adding new documents
3. Ensure cross-references are valid
4. Submit PR with documentation label

---

**Document Owner:** Engineering Team  
**Last Audit:** January 2025  
**Next Audit:** April 2025