# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial package structure for PyPI distribution
- Comprehensive CLI interface with `plinto` command
- Middleware stack for easy FastAPI integration
- Complete package documentation and examples

## [0.1.0] - 2025-01-19

### Added
- Initial release of Plinto authentication platform
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
- **PyPI Distribution**: Available via `pip install plinto`
- **CLI Interface**: Complete command-line tools for deployment and management
- **Middleware Stack**: Pre-configured FastAPI middleware for easy integration
- **Optional Dependencies**: Modular installation with `plinto[email]`, `plinto[sso]`, `plinto[dev]`
- **Entry Points**: Package scripts and FastAPI middleware entry points
- **Development Tools**: Integrated linting, formatting, and testing tools
- **Docker Support**: Container-ready deployment configuration
- **Production Ready**: Environment configuration and deployment guides

### Installation
```bash
pip install plinto
```

### Quick Start
```python
from plinto import create_app
app = create_app(title="My App")
```

### CLI Usage
```bash
plinto server --host 0.0.0.0 --port 8000
plinto migrate
plinto create-user --email admin@example.com --admin
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
- Documentation: https://docs.plinto.dev
- Issues: https://github.com/madfam-io/plinto/issues
- Community: https://discord.gg/plinto
- Security: security@plinto.dev