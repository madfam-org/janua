# Janua Documentation Index

**Last Updated**: November 26, 2025

This index provides a navigable structure for all Janua documentation. Organized by purpose and audience.

## 📚 Primary Documentation

### Getting Started
- [README.md](../README.md) - Project overview and quick start
- [QUICK_START.md](guides/QUICK_START.md) - 5-minute setup guide
- [DEMO_WALKTHROUGH.md](guides/DEMO_WALKTHROUGH.md) - Interactive demo guide

### Implementation Reports (Current)
- [Week 5 Final Summary](implementation-reports/week5-final-summary.md) - E2E testing completion
- [Week 6 Day 1 API Integration](implementation-reports/week6-day1-api-integration.md) - Full stack setup
- [Week 6 Day 2 Complete](implementation-reports/week6-day2-session-final-summary.md) - Enterprise E2E tests
- [Maintenance System 2025-11-17](implementation-reports/maintenance-system-2025-11-17.md) - Automated maintenance infrastructure
- [Comprehensive Audit 2025-11-17](CLEANUP_SUMMARY_2025-11-17.md) - Documentation cleanup and audit
- [Cleanup Report 2025-11-17](implementation-reports/cleanup-report-2025-11-17.md) - Latest maintenance

### Technical Architecture
- [Architecture Overview](architecture/README.md) - System design and components
- [API Documentation](api/README.md) - Backend API reference
- [SDK Documentation](sdks/README.md) - Client library guides

## 🔍 Reference Documentation

### Development Guides
- [Development Guide](development/DEVELOPMENT.md) - Setup and workflows
- [API Deployment Status](development/api-deployment-status.md) - Current deployment state

### Feature Documentation  
- [Authentication Features](features/authentication.md) - Auth methods and flows
- [Organization Management](features/organizations.md) - Multi-tenancy guide
- [Enterprise Features](features/enterprise.md) - SSO, SCIM, RBAC

### Billing & Payments
- [Billing Integration Guide](guides/BILLING_INTEGRATION_GUIDE.md) - Payment providers overview, subscriptions, webhooks
- [Polar Integration Guide](guides/POLAR_INTEGRATION_GUIDE.md) - **NEW** Merchant of Record, global tax compliance, usage billing
- [Payment Infrastructure Roadmap](roadmap/PAYMENT_INFRASTRUCTURE_ROADMAP.md) - Multi-provider strategy and future enhancements
- [Polar Integration Design](design/POLAR_INTEGRATION_DESIGN.md) - Original design document (reference)

## 📊 Project Status & Analysis

### Current Assessment (January 2026)
- **Production Readiness**: 75-80%
- **Infrastructure**: K3s single-node on Hetzner dedicated server (see internal-devops for pricing)
- **Status**: All 5 Janua services healthy and operational

## 🗄️ Documentation Archive Policy

Historical documentation has been archived to git history as of January 2026.
Use `git log` to access previous versions if needed.

## 📖 Documentation Categories

### By Audience
- **Developers**: API docs, SDK guides, development setup
- **DevOps**: Deployment guides, infrastructure docs
- **Product**: Feature docs, roadmaps, implementation reports
- **Leadership**: Executive summaries, production readiness assessments

### By Type
- **Guides**: How-to documentation and tutorials
- **Reference**: API specs, SDK documentation, command references  
- **Reports**: Implementation progress, analysis summaries
- **Architecture**: System design, technical decisions

## 🔄 Documentation Maintenance

### Active Documentation
All files in root `docs/` and `docs/implementation-reports/` are current and maintained.

### Archive Policy
- Outdated documentation is removed and preserved in git history
- Use `git log --all --full-history -- <path>` to find archived content

### Quality Standards
- ✅ Evidence-based claims with verification
- ✅ Current metrics updated regularly
- ✅ Clear archival when superseded
- ✅ Warnings on outdated/incorrect information

## 📝 Contributing to Documentation

1. Update this index when adding new docs
2. Archive old docs rather than deleting
3. Mark inaccurate docs with clear warnings
4. Keep implementation reports chronological
5. Maintain evidence-based assessments

---

**For Questions**: See [CLAUDE.md](../CLAUDE.md) for development commands
**For Updates**: Contact project maintainers or submit PR

## 🔧 Maintenance & Operations

### Maintenance System
- [Maintenance Schedule](MAINTENANCE_SCHEDULE.md) - Daily, weekly, monthly checklists
- [Maintenance Scripts](../scripts/maintenance/README.md) - Automated quality checks
- [GitHub Actions Workflow](../.github/workflows/maintenance.yml) - CI/CD automation

### Quality Monitoring
- **Code Quality**: `./scripts/maintenance/check-code-quality.sh`
- **Documentation**: `./scripts/maintenance/check-docs.sh`  
- **Memory Updates**: `./scripts/maintenance/update-memory.sh`

### Key Metrics (as of 2025-11-17)
- TODO/FIXME count: 45 (threshold: 60) ✅
- console.log count: ~100 (threshold: 100) ⚠️
- Build success: 5/6 SDKs (83%) - Vue SDK fixed ✅
- Test files: 152
- Production readiness: 75-80%