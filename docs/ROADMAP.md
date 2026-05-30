# Janua Development Roadmap

**Last Updated**: November 17, 2025  
**Based On**: Strategic Positioning Audit (November 2025)

This roadmap prioritizes features and improvements based on competitive differentiation, production readiness, and strategic positioning validation.

---

## ✅ Completed (Current State)

### Core Platform
- ✅ **Enterprise SSO** (SAML, OIDC, OAuth 2.0) - 513 lines, fully implemented
- ✅ **SCIM 2.0** (automated user provisioning) - 686 lines, spec-compliant
- ✅ **Multi-Factor Authentication** (TOTP, SMS, backup codes) - 491 lines
- ✅ **Passkeys/WebAuthn** (FIDO2, biometric auth) - 500 lines
- ✅ **Organizations** (multi-tenancy, role-based access) - 315 lines
- ✅ **15 UI Components** (SignIn, SignUp, MFA, etc. with Radix UI)
- ✅ **Synchronous Database** (direct PostgreSQL writes via SQLAlchemy)

### SDKs & Frameworks
- ✅ **React SDK** (~2,000 lines)
- ✅ **Vue 3 SDK** (~1,500 lines)
- ✅ **Next.js SDK** (~1,800 lines)
- ✅ **TypeScript SDK** (~3,000 lines)
- ✅ **Python SDK** (~2,500 lines)
- ✅ **Go SDK** (~2,000 lines)
- ✅ **React Native SDK** (~1,200 lines)
- ✅ **Flutter SDK** (planned structure)

### Testing & Quality
- ✅ **152 test files** (unit + integration)
- ✅ **94+ E2E scenarios** (Playwright)
- ✅ **Test coverage baseline: 23.8%** (377 passing, 422 errors to fix)
- ✅ **Maintenance automation** (quality checks, doc verification)
- ✅ **Zero production console.logs** (professional code quality)

### Documentation
- ✅ **18KB migration guide** (Cloud → Self-hosted "eject button")
- ✅ **Comprehensive API docs** (OpenAPI/Swagger)
- ✅ **50+ documentation pages**

---

## 🔥 Week 1-2: Critical Strategic Fixes (November 18-29, 2025)

**Theme**: Strategic messaging clarity and code quality

### 1. SSO Messaging Update ✅ **COMPLETED**
- [x] Update README.md hero section (emphasize "100% features free")
- [x] Add "Enterprise SSO free" to comparison table
- [x] Clarify competitive differentiation vs Auth0/Clerk
- **Impact**: Removes strategic contradiction, strengthens positioning

### 2. Pricing Clarity Page ✅ **COMPLETED**
- [x] Create `docs/pricing/tiers.md` (complete transparency)
- [x] Define OSS, Cloud, Enterprise tiers clearly
- [x] Explain "charge for convenience, not capabilities" philosophy
- [x] Add FAQ section addressing common concerns
- **Impact**: Clear value proposition for each tier

### 3. Console.log Cleanup ✅ **COMPLETED**
- [x] Create cleanup script (`scripts/maintenance/cleanup-console-logs.sh`)
- [x] Remove debug console.logs from showcase pages (13 files cleaned)
- [x] Remove console.logs from production services (4 files cleaned)
- [x] **Result: 0 production console.logs** (exceeded <50 target)
- **Impact**: Professional production-ready code quality

### 4. Roadmap Documentation ✅ **THIS DOCUMENT**
- [x] Create comprehensive roadmap with clear priorities
- [x] Align with strategic positioning audit findings
- [x] Set measurable success metrics
- **Impact**: Clear direction for team and community

---

## 📋 Weeks 3-6: Production Readiness (December 2025)

**Theme**: Polish, testing, and documentation

### Week 3: Test Coverage Expansion ✅ **PHASE 1 COMPLETE**
**Goal**: Establish baseline and improvement plan (60% → 70%)

**Completed**:
- [x] **Console.log cleanup** (225 → 0 production statements)
- [x] **Generate coverage baseline** (23.8% overall, 35.3% critical paths)
- [x] **Critical path analysis** (8 core modules identified)
- [x] **Test improvement roadmap** (4-6 week realistic timeline)

**Findings**:
- Current coverage: 23.8% (lower than expected 60%)
- Test infrastructure: 422 errors preventing test execution
- Critical path coverage: 35.3% (needs 625 lines to reach 90%)
- Realistic timeline: 4-6 weeks to reach 70% (not 1 week)

**Remaining Week 3 Work** (November 18-24):
- [ ] Fix auth service test failures (18 tests)
- [ ] Fix session/JWT test failures
- [ ] Resolve top 50 test errors
- [ ] Achieve 40% overall coverage
- [ ] Achieve 60% critical path coverage

**Documentation**:
- `docs/implementation-reports/week3-test-coverage-analysis-2025-11-17.md` (15KB)
- `docs/implementation-reports/week3-summary-2025-11-17.md` (4KB)

**Success Metrics** (Updated):
- Overall coverage: 40% (Week 3) → 70% (Week 6)
- Critical paths: 60% (Week 3) → 90% (Week 6)
- Test errors: <50 (Week 3) → 0 (Week 6)

### Week 4: API Documentation Completion
**Goal**: Production-grade API documentation

- [ ] **Complete OpenAPI specs** for all 30 routers
- [ ] **Add request/response examples** to all endpoints
- [ ] **Document error responses** (standardized error format)
- [ ] **Add rate limit information** to endpoint docs
- [ ] **Create API guides**:
  - [ ] Authentication guide (JWT, OAuth, SSO flows)
  - [ ] Organizations guide (multi-tenancy patterns)
  - [ ] Webhooks guide (event types, retry logic)
  - [ ] Rate limiting guide (quotas, headers)
- [ ] **Export Postman collection**

**Success Metrics**:
- 100% of endpoints documented
- 4 comprehensive API guides
- Postman collection available

### Week 5: "Deploy to X" Buttons (Interim Cloud Solution)
**Goal**: Make self-hosting easier while building Janua Cloud

- [ ] **Railway Integration**:
  - [ ] Create Railway blueprint template
  - [ ] Configure environment variables
  - [ ] Add "Deploy to Railway" button to README
  - [ ] Test one-click deployment
- [ ] **Render Integration**:
  - [ ] Create Render blueprint
  - [ ] Configure PostgreSQL + Redis
  - [ ] Add "Deploy to Render" button
- [ ] **Documentation**:
  - [ ] Quick deploy guide for each platform
  - [ ] Cost estimation ($5-25/mo)

**Success Metrics**:
- One-click deploy working on 2 platforms
- Deployment time: <10 minutes
- User cost: <$30/mo for small deployments

### Week 6: Performance Benchmarking
**Goal**: Validate "production-ready" claims with data

- [ ] **Set up benchmarking infrastructure**:
  - [ ] k6 or Apache Bench for load testing
  - [ ] Prometheus + Grafana for monitoring
- [ ] **Run baseline benchmarks**:
  - [ ] API response times (target p95 <200ms)
  - [ ] Database query performance
  - [ ] SDK bundle sizes
- [ ] **Document performance**:
  - [ ] Add performance metrics to README
  - [ ] Create `docs/performance/benchmarks.md`
  - [ ] Set up continuous performance monitoring

**Success Metrics**:
- API p95 response time: <200ms
- Database queries: <20ms average
- SDK bundle: <50KB gzipped

---

## 🚀 Q1 2026: Competitive Differentiation (January-March 2026)

**Theme**: Feature parity with Better-Auth + Clerk differentiation

### January 2026: Prisma/Drizzle Adapters
**Goal**: Match Better-Auth's "bring your own ORM" capability

- [ ] **Prisma Adapter** (~800 lines):
  - [ ] `PrismaJanuaAdapter` class
  - [ ] User CRUD operations
  - [ ] Session management
  - [ ] Organization queries
  - [ ] Type-safe query builders
- [ ] **Drizzle Adapter** (~700 lines):
  - [ ] `DrizzleJanuaAdapter` class
  - [ ] Same interface as Prisma adapter
  - [ ] Query builders for Drizzle ORM
- [ ] **Documentation**:
  - [ ] Adapter usage guide
  - [ ] Migration guide (FastAPI → Prisma/Drizzle)
  - [ ] Example projects
- [ ] **Testing**:
  - [ ] Integration tests for each adapter
  - [ ] E2E tests with real databases

**Success Metrics**:
- 2 working adapters (Prisma, Drizzle)
- 100% test coverage for adapters
- Documentation with examples

**Competitive Impact**: Closes gap with Better-Auth, enables "use your existing ORM" pitch

### February 2026: Svelte/Astro SDKs
**Goal**: Differentiate from Clerk (React-only) and capture growing market

- [ ] **Svelte SDK** (~1,200 lines):
  - [ ] Svelte stores for auth state
  - [ ] `$user`, `$isAuthenticated`, `$isLoading` stores
  - [ ] `signIn`, `signOut`, `signUp` functions
  - [ ] SSR support (SvelteKit)
- [ ] **Svelte UI Components** (~2,000 lines):
  - [ ] SignIn.svelte, SignUp.svelte
  - [ ] MFASetup.svelte, MFAChallenge.svelte
  - [ ] UserProfile.svelte, OrganizationSwitcher.svelte
  - [ ] Tailwind CSS styling (customizable)
- [ ] **Astro Integration** (~600 lines):
  - [ ] Middleware for session verification
  - [ ] Server-side auth helpers
  - [ ] Client-side auth components
- [ ] **Documentation**:
  - [ ] Svelte quickstart guide
  - [ ] Astro integration guide
  - [ ] Example projects (SvelteKit + Astro)

**Success Metrics**:
- 2 new framework SDKs (Svelte, Astro)
- UI component library for Svelte
- Example projects demonstrating usage

**Competitive Impact**: Captures Svelte/Astro developers (Clerk can't serve), grows TAM

### March 2026: Janua Cloud MVP
**Goal**: Launch managed hosting offering (primary revenue stream)

**Infrastructure**:
- [ ] **Deployment Pipeline**:
  - [ ] Git integration (GitHub, GitLab)
  - [ ] Automatic builds on push
  - [ ] Preview deployments for PRs
- [ ] **Managed Services**:
  - [ ] PostgreSQL clusters (managed)
  - [ ] Redis clusters (managed)
  - [ ] Load balancing (automatic)
  - [ ] SSL/TLS provisioning (Let's Encrypt)
- [ ] **Dashboard** (Next.js):
  - [ ] Project overview (status, logs, metrics)
  - [ ] Environment variables management
  - [ ] Team collaboration (invite members)
  - [ ] Usage monitoring (MAU, API calls)
  - [ ] Backup/restore UI

**Deployment Options**:
- [ ] Kubernetes (for scale)
- [ ] Or partner with Railway/Render/Fly.io

**Pricing Launch**:
- [ ] Starter: $99/mo (10K MAU)
- [ ] Professional: $299/mo (100K MAU)
- [ ] Scale: $499/mo (500K MAU)

**Success Metrics**:
- 100+ waitlist signups
- 10+ paying customers (beta)
- 99.9% uptime in beta period

**Competitive Impact**: Completes "Clerk DX" positioning with managed offering

---

## 🏢 Q2 2026: Enterprise Readiness (April-June 2026)

**Theme**: Compliance certifications and enterprise services

### April 2026: SOC 2 Type II Kickoff
**Goal**: Begin compliance certification process

- [ ] **Select Provider** (Vanta, Drata, or Secureframe)
- [ ] **Implement Controls**:
  - [ ] Access control (SSO for team, MFA required)
  - [ ] Audit logging (all admin actions)
  - [ ] Change management (documented deploy process)
  - [ ] Incident response (runbooks, on-call)
- [ ] **Documentation**:
  - [ ] Security policies
  - [ ] Vendor management
  - [ ] Risk assessments
- [ ] **Timeline**: 6-9 months (completion Q4 2026)
- [ ] **Cost**: $20k-50k

**Success Metrics**:
- SOC 2 Type II report issued (Q4 2026)
- 100% control compliance
- Zero critical findings

**Competitive Impact**: Required for enterprise sales, enables upmarket expansion

### May 2026: GDPR Compliance Package
**Goal**: European market readiness

- [ ] **Legal Review** (EU data protection counsel)
- [ ] **Implement GDPR Features**:
  - [ ] Data export API (already exists ✅)
  - [ ] Right to deletion (implement)
  - [ ] Consent management (implement)
  - [ ] Data processing records
- [ ] **Documentation**:
  - [ ] Data Processing Agreement (DPA)
  - [ ] Privacy policy template
  - [ ] GDPR compliance guide
- [ ] **Cost**: $5k-15k (legal review)

**Success Metrics**:
- GDPR compliance certification
- DPA template available for customers
- Privacy policy reviewed by EU counsel

**Competitive Impact**: Enables European enterprise sales

### June 2026: Enterprise Support Infrastructure
**Goal**: Premium support tier for revenue

- [ ] **Support Tooling**:
  - [ ] Zendesk or Intercom (ticketing)
  - [ ] Slack Connect (enterprise customers)
  - [ ] Status page (status.janua.dev)
- [ ] **Support Tiers**:
  - [ ] Community (free): GitHub + Discord
  - [ ] Professional ($499/mo): Email 24hr SLA
  - [ ] Enterprise (custom): Dedicated engineer, 4hr SLA
- [ ] **Customer Success**:
  - [ ] Hire first customer success manager
  - [ ] Create onboarding playbooks
  - [ ] Quarterly business review templates

**Success Metrics**:
- <24hr response time (Professional)
- <4hr response time (Enterprise)
- >4.5/5 customer satisfaction

**Competitive Impact**: Creates Enterprise tier differentiation (charge for service, not features)

---

## 🌍 Q3 2026: Market Expansion (July-September 2026)

**Theme**: Additional language SDKs and integration ecosystem

### July 2026: Rust SDK
**Goal**: Capture Rust backend market (growing)

- [ ] **Rust SDK** (~2,500 lines):
  - [ ] Type-safe API client
  - [ ] Async/await support (Tokio)
  - [ ] Actix-web integration
  - [ ] Axum integration
- [ ] **Documentation**:
  - [ ] Rust quickstart
  - [ ] Web framework guides
  - [ ] Example projects

**Success Metrics**:
- Rust SDK on crates.io
- 100+ downloads in first month
- Example Actix + Axum projects

**Competitive Impact**: No major auth provider has Rust SDK (first-mover advantage)

### August 2026: Ruby SDK
**Goal**: Capture Rails ecosystem (large existing market)

- [ ] **Ruby SDK** (~1,800 lines):
  - [ ] Gem package
  - [ ] Rails integration (generators)
  - [ ] Devise migration guide
- [ ] **Documentation**:
  - [ ] Rails quickstart
  - [ ] Devise → Janua migration
  - [ ] Example Rails app

**Success Metrics**:
- Ruby gem published
- 500+ downloads in first month
- Devise migration guide

**Competitive Impact**: Auth0/Okta replacement for Rails shops

### September 2026: Integration Marketplace Launch
**Goal**: Reduce time-to-value with pre-built integrations

**Initial Integrations** (5 to launch):
- [ ] **Identity Providers**:
  - [ ] Google OAuth (one-click setup)
  - [ ] GitHub OAuth
  - [ ] Microsoft Azure AD
- [ ] **Communication**:
  - [ ] Twilio (SMS MFA)
  - [ ] Resend (email delivery)

**Marketplace Features**:
- [ ] One-click integration activation
- [ ] Configuration templates
- [ ] Usage analytics
- [ ] Integration documentation

**Success Metrics**:
- 5 integrations live
- 100+ integration activations
- <5 minute setup time per integration

**Competitive Impact**: Ecosystem moat, increases switching costs (in good way)

---

## 🔮 Q4 2026 and Beyond: Future Vision

### Planned Features (Backlog)
- [ ] **PHP SDK** (WordPress, Laravel ecosystems)
- [ ] **Java/Kotlin SDK** (enterprise backend, Android)
- [ ] **HIPAA Compliance** (healthcare vertical)
- [ ] **ISO 27001 Certification** (global enterprise sales)
- [ ] **Multi-region deployment** (global low-latency)
- [ ] **Advanced Analytics** (user behavior insights)
- [ ] **Custom Integration Development** (enterprise services)
- [ ] **AI-powered security** (anomaly detection, fraud prevention)

### Community Goals
- [ ] **10,000+ GitHub stars**
- [ ] **1,000+ Discord members**
- [ ] **100+ community contributors**
- [ ] **Monthly community calls**
- [ ] **Annual Janua conference** (virtual or in-person)

---

## 📊 Success Metrics (6-Month Targets)

### Technical Metrics
| Metric | Current | Week 6 | Q1 2026 | Q2 2026 |
|--------|---------|--------|---------|---------|
| Test Coverage (Overall) | 23.8% | 70% | 75% | 80% |
| Critical Path Coverage | 35.3% | 90% | 95% | 95% |
| console.log Count | 0 ✅ | 0 | 0 | 0 |
| Test Errors | 422 | 0 | 0 | 0 |
| API Response Time (p95) | TBD | <200ms | <150ms | <100ms |

### Product Metrics
| Metric | Current | Q1 2026 | Q2 2026 | Q3 2026 |
|--------|---------|---------|---------|---------|
| Framework SDKs | 8 | 11 | 11 | 13 |
| UI Components | 15 | 20 | 25 | 30 |
| Documentation Pages | 50 | 100 | 150 | 200 |
| Integrations | 0 | 0 | 5 | 10 |

### Business Metrics
| Metric | Current | Q1 2026 | Q2 2026 | Q3 2026 |
|--------|---------|---------|---------|---------|
| GitHub Stars | TBD | +500 | +1,000 | +2,000 |
| Cloud Waitlist | 0 | 100 | - | - |
| Paying Customers | 0 | 10 | 50 | 100 |
| Monthly Recurring Revenue | $0 | $5k | $25k | $50k |

---

## 🎯 Strategic Priorities

### Must-Have (Non-Negotiable)
1. **100% features free in OSS** (AGPL v3 license, no gates)
2. **Anti-lock-in guarantee** (migration path documented)
3. **Synchronous database writes** (no webhook sync)
4. **Production-ready quality** (comprehensive testing, documentation)

### Should-Have (Competitive Advantages)
5. **Multi-framework support** (React, Vue, Svelte, etc.)
6. **Enterprise SSO/SCIM free** (unique in market)
7. **Clerk-quality UI components** (accessibility, polish)
8. **Prisma/Drizzle adapters** (Better-Auth parity)

### Nice-to-Have (Future Enhancements)
9. **Additional language SDKs** (Rust, Ruby, PHP, Java)
10. **Integration marketplace** (ecosystem moat)
11. **Advanced analytics** (user insights)
12. **AI-powered security** (fraud detection)

---

## 📞 Community & Feedback

We build in public and welcome community input:

- **GitHub Discussions**: https://github.com/madfam-org/janua/discussions
- **Discord**: https://discord.gg/janua
- **Roadmap Feedback**: roadmap@janua.dev
- **Feature Requests**: Use GitHub Issues with `enhancement` label

**How to Influence the Roadmap**:
1. Submit feature requests with clear use cases
2. Vote on existing feature requests (GitHub reactions)
3. Contribute PRs for features you need
4. Join monthly community calls
5. Become an enterprise customer (direct roadmap input)

---

## Coupler Program — ConnectedAccount / Keyring (Jun–Jul 2026)

**Objective:** Universal Keyring (ADR-002) so Coupler can execute delegated SaaS tools without storing refresh tokens in the tool plane.

| Milestone | Target | Doc |
|-----------|--------|-----|
| ADR-002 implementation kickoff | 2026-06-16 | [ADR-002](./architecture/ADR-002_UNIVERSAL_KEYRING.md) |
| Connections CRUD + encryption | 2026-07-05 | [COUPLER_PROGRAM.md](./COUPLER_PROGRAM.md) |
| OAuth GitHub + Slack + token API | 2026-07-25 | P1 gate — Coupler staging execute |

**Blocks:** Coupler P2 production execute (not Enclii Commercial GA).

Runs parallel to Q2 2026 roadmap items below.

---

**Last Updated**: May 30, 2026  
**Next Review**: July 1, 2026  
**Maintained By**: Janua Core Team
