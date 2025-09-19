# Changelog

All notable changes to the Plinto platform and SDKs will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-18

### 🎉 Initial Public Release

This is the first public release of the Plinto authentication and identity platform.

### Added

#### Core Platform Features
- **Authentication**: Complete authentication system with multiple methods
  - Email/password authentication with secure hashing
  - Magic link authentication via email
  - OAuth 2.0 providers (Google, GitHub, Microsoft, Discord, Twitter)
  - Multi-factor authentication (MFA) with TOTP support
  - Passkey/WebAuthn support for passwordless authentication
  - Session management with refresh token rotation

- **User Management**: Comprehensive user lifecycle management
  - User registration and profile management
  - Email verification and password reset
  - Account suspension and deletion
  - User avatars and profile customization
  - Session tracking and device management

- **Organization Management**: Multi-tenant organization support
  - Organization creation and management
  - Member invitation system with role-based access
  - Team creation and hierarchy
  - Organization-level settings and customization
  - Billing and subscription management

- **Security Features**: Enterprise-grade security
  - JWT token management with automatic refresh
  - Rate limiting and throttling
  - Audit logging for compliance
  - IP-based access controls
  - Suspicious activity detection

- **Developer Experience**: Modern SDK ecosystem
  - TypeScript SDK with full type safety
  - React SDK with hooks and components
  - Python SDK with async/await support
  - Vue.js SDK for Vue 3 applications
  - Next.js SDK with App Router support
  - React Native SDK for mobile apps
  - Flutter SDK for cross-platform mobile
  - Go SDK for backend services

- **Infrastructure**: Production-ready architecture
  - Edge-native design for <30ms global verification
  - PostgreSQL database with migration support
  - Redis for caching and rate limiting
  - Webhook system for event notifications
  - Comprehensive error handling

### SDK Versions at Launch

| Package | Version | Status |
|---------|---------|--------|
| @plinto/typescript-sdk | 1.0.0 | Stable |
| @plinto/react-sdk | 1.0.0 | Stable |
| @plinto/vue-sdk | 1.0.0 | Stable |
| @plinto/nextjs-sdk | 1.0.0 | Stable |
| @plinto/react-native-sdk | 1.0.0 | Stable |
| @plinto/flutter-sdk | 1.0.0 | Stable |
| @plinto/go-sdk | 1.0.0 | Stable |
| plinto-sdk (Python) | 1.0.0 | Stable |
| @plinto/core | 1.0.0 | Stable |
| @plinto/ui | 1.0.0 | Stable |
| @plinto/jwt-utils | 1.0.0 | Stable |
| @plinto/edge | 1.0.0 | Stable |
| @plinto/monitoring | 1.0.0 | Stable |

### Known Limitations
- SAML SSO implementation pending (planned for v1.1.0)
- SCIM provisioning not yet available (planned for v1.2.0)
- Advanced compliance reports in development

### Migration Support
- Migration guides from Auth0, Clerk, Firebase Auth, and Supabase Auth
- Data import tools for user migration
- Session continuity during migration

### Documentation
- Comprehensive API reference documentation
- SDK quick-start guides for all languages
- Integration examples and best practices
- Architecture and security documentation

### Infrastructure
- Docker support for local development
- GitHub Actions CI/CD pipeline
- NPM and PyPI package publishing
- Automated testing and quality checks

## Version History Guidelines

### Version Numbering
We follow Semantic Versioning (MAJOR.MINOR.PATCH):
- **MAJOR**: Breaking API changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### Release Cadence
- **Patch releases**: As needed for bug fixes
- **Minor releases**: Monthly with new features
- **Major releases**: Annually or for breaking changes

### Deprecation Policy
- Features are deprecated with 6 months notice
- Deprecated features include migration guides
- Breaking changes only in major versions

### Support Policy
- **Current version**: Full support
- **Previous minor**: Security updates for 6 months
- **Previous major**: Security updates for 1 year

---

For detailed release notes and migration guides, visit [docs.plinto.dev/changelog](https://docs.plinto.dev/changelog)