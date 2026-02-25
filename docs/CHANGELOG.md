# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial package structure for PyPI distribution
- Comprehensive CLI interface with `janua` command
- Middleware stack for easy FastAPI integration
- Complete package documentation and examples
- MFA challenge verify endpoint (`POST /mfa/challenge/verify`) for completing MFA during sign-in

### Security
- **MFA before token issuance**: Sign-in now requires MFA verification before issuing session tokens for MFA-enabled users
- **Session invalidation on password change**: All active sessions (except current) are revoked when a user changes their password
- **Security headers for website and docs**: Full CSP, HSTS, Referrer-Policy, Permissions-Policy, X-Frame-Options, X-Content-Type-Options for all public-facing Next.js apps
- **Admin CSP hardened**: Removed `unsafe-eval` from production CSP in admin panel (kept for dev HMR only)
- **Admin next.config.js headers**: Added defense-in-depth security headers alongside middleware headers
- **CI security gates**: Removed `continue-on-error: true` from security-critical CI steps (Bandit, Safety, pip-audit, pnpm audit, Snyk, Trivy) so vulnerabilities block PRs
- **Explicit bcrypt rounds**: Wired `settings.BCRYPT_ROUNDS` into `pwd_context` for auditability
- **RS256 production guard**: RS256→HS256 silent fallback now raises `ValueError` in production; dev-only fallback logs a warning
- **Email verification grace period**: Reduced default from 24 hours to 1 hour to limit unverified email abuse window

### Fixed
- `reset_password` endpoint used non-existent `AuthService.validate_password()` — corrected to `validate_password_strength()`
- `X-XSS-Protection` header updated from deprecated `1; mode=block` to `0` across admin middleware and docs config (CSP replaces the legacy filter)
- Quarantine config test `test_default_settings` now disables `.env` file loading to test true defaults

## [0.1.0] - 2025-01-19

### Added
- Initial release of Janua authentication platform
- Core authentication services (AuthService, JWTService, CacheService)
- User and organization management models
- Multi-tenancy support with organization-based access
- JWT token authentication with refresh token support
- Password hashing with bcrypt
- Redis caching integration
- Database models with SQLAlchemy async support
- Rate limiting middleware
- Security headers middleware
- CORS middleware with configurable origins
- Audit logging system
- Comprehensive exception handling
- FastAPI integration utilities
- Settings management with Pydantic
- Multi-factor authentication (MFA) support
- WebAuthn/Passkey authentication
- OAuth provider integration
- SAML SSO support
- Session management
- User status and role management
- Email verification system
- Password reset functionality
- Comprehensive test suite with 95%+ coverage
- API documentation with OpenAPI/Swagger
- Development tooling (Black, Ruff, MyPy, Pytest)

### Security
- Secure password hashing with configurable rounds
- JWT signing with RS256/HS256 algorithms
- Rate limiting to prevent abuse
- Security headers for XSS/CSRF protection
- Input validation and sanitization
- Audit logging for security events
- Session security with proper expiration
- CORS protection with origin validation

### Performance
- Async/await support throughout
- Redis caching for session and user data
- Database connection pooling
- Optimized database queries
- Background task processing
- Response compression middleware

### Developer Experience
- Comprehensive CLI tools for management
- Easy FastAPI integration
- Extensive documentation
- Code examples and tutorials
- Type hints throughout
- Developer-friendly error messages
- Hot reload support in development
- Testing utilities and fixtures

### Enterprise Features
- Multi-tenancy with organization isolation
- Role-based access control (RBAC)
- SAML SSO integration
- OAuth provider support
- Audit logging and compliance
- Admin user management
- Bulk user operations
- Organization management
- Custom authentication flows

## Package Distribution Features

### Added in Package Release
- **PyPI Distribution**: Available via `pip install janua`
- **CLI Interface**: Complete command-line tools for deployment and management
- **Middleware Stack**: Pre-configured FastAPI middleware for easy integration
- **Optional Dependencies**: Modular installation with `janua[email]`, `janua[sso]`, `janua[dev]`
- **Entry Points**: Package scripts and FastAPI middleware entry points
- **Development Tools**: Integrated linting, formatting, and testing tools
- **Docker Support**: Container-ready deployment configuration
- **Production Ready**: Environment configuration and deployment guides

### Installation
```bash
pip install janua
```

### Quick Start
```python
from janua import create_app
app = create_app(title="My App")
```

### CLI Usage
```bash
janua server --host 0.0.0.0 --port 8000
janua migrate
janua create-user --email admin@example.com --admin
```

---

## Development Notes

### Version Numbering
- Major version (X.y.z): Breaking changes
- Minor version (x.Y.z): New features, backwards compatible
- Patch version (x.y.Z): Bug fixes, backwards compatible

### Release Process
1. Update version in `app/__init__.py`
2. Update CHANGELOG.md with new features and fixes
3. Create git tag with version number
4. Build and publish to PyPI
5. Create GitHub release with changelog

### Dependencies
- Python 3.9+ required
- FastAPI for web framework
- SQLAlchemy for database ORM
- Pydantic for data validation
- Redis for caching
- PostgreSQL for primary database
- See `pyproject.toml` for complete dependency list

### Support
- Documentation: https://docs.janua.dev
- Issues: https://github.com/madfam-org/janua/issues
- Community: https://discord.gg/janua
- Security: security@janua.dev