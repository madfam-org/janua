# Frequently Asked Questions

> **Common questions and answers about the Janua API**

This FAQ addresses the most common questions about implementing, deploying, and using the Janua authentication platform.

## 🚀 Getting Started

### Q: What is Janua API?
**A:** Janua API is a modern, enterprise-grade authentication and identity management platform built with FastAPI. It provides comprehensive authentication services including JWT tokens, WebAuthn/Passkeys, multi-factor authentication, and enterprise SSO.

### Q: What are the system requirements?
**A:**
- **Python 3.11+** for the API server
- **PostgreSQL 14+** for data persistence
- **Redis 6+** for caching and sessions
- **2GB+ RAM** for production deployment
- **TLS/SSL certificate** for production (HTTPS)

### Q: How do I get started quickly?
**A:** Follow our [Quick Start Guide](development/getting-started.md):
1. Clone the repository
2. Set up Python virtual environment
3. Install dependencies with `pip install -r requirements.txt`
4. Configure environment variables in `.env`
5. Run database migrations with `alembic upgrade head`
6. Start the server with `uvicorn app.main:app --reload`

### Q: Is there a hosted version available?
**A:** Yes! We offer a fully managed cloud service at [janua.dev](https://janua.dev). You can also self-host using our deployment guides.

## 🔐 Authentication & Security

### Q: What authentication methods are supported?
**A:** Janua supports multiple authentication methods:
- **JWT Tokens** (RS256/HS256) for API access
- **WebAuthn/Passkeys** for passwordless authentication
- **Multi-Factor Authentication** (TOTP, SMS, email)
- **OAuth 2.0/OpenID Connect** for third-party integration
- **SAML SSO** for enterprise authentication
- **API Keys** for service-to-service authentication

### Q: How secure are the default settings?
**A:** Very secure! Default settings include:
- **bcrypt** password hashing with 12 rounds
- **RS256** JWT signing for production
- **15-minute** access token expiry
- **Rate limiting** on all endpoints
- **HTTPS enforcement** in production
- **Security headers** (HSTS, CSP, etc.)
- **Comprehensive audit logging**

### Q: Can I use my own JWT signing keys?
**A:** Yes! You can provide your own RSA key pair:
```env
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY=DUMMY_PRIVATE_KEY_BEGIN_REMOVED...
JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----...
```

### Q: How do I implement rate limiting?
**A:** Rate limiting is enabled by default. Configure limits in your environment:
```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
```

### Q: What's the password policy?
**A:** Default password requirements:
- Minimum 12 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character
- No common passwords (checked against breach databases)

## 🏢 Enterprise Features

### Q: What enterprise features are available?
**A:** Enterprise features include:
- **SAML 2.0 SSO** with multiple providers
- **SCIM 2.0** user provisioning
- **Multi-tenancy** with organization isolation
- **Advanced audit logging** and compliance reporting
- **Custom branding** and white-labeling
- **SLA guarantees** and priority support

### Q: How do I set up SAML SSO?
**A:** Follow our [SSO Integration Guide](api/sso-integration.md):
1. Configure your identity provider (IdP)
2. Add SSO provider configuration in Janua
3. Test the SAML authentication flow
4. Configure user attribute mapping
5. Enable SSO for your organization

### Q: What is SCIM and do I need it?
**A:** SCIM (System for Cross-domain Identity Management) enables automatic user provisioning from identity providers like Okta, Azure AD, or Google Workspace. You need it if you want to:
- Automatically create users when they're added to your IdP
- Sync user information (name, email, groups) automatically
- Deactivate users when they're removed from your IdP

### Q: How does multi-tenancy work?
**A:** Janua provides organization-level isolation:
- Each organization has its own data space
- Users can belong to multiple organizations
- Row-level security ensures data isolation
- Each organization can have different settings and branding

## 🔧 Technical Implementation

### Q: What's the difference between access and refresh tokens?
**A:**
- **Access tokens**: Short-lived (15 minutes), used for API requests
- **Refresh tokens**: Longer-lived (7 days), used to get new access tokens
- **Benefits**: Improved security, automatic token rotation, session management

### Q: How do I handle token expiration?
**A:** Implement automatic token refresh in your client:
```javascript
// JavaScript example
async function apiRequest(url, options = {}) {
  let response = await fetch(url, {
    ...options,
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      ...options.headers
    }
  });

  if (response.status === 401) {
    // Token expired, refresh it
    await refreshAccessToken();

    // Retry the request
    response = await fetch(url, {
      ...options,
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        ...options.headers
      }
    });
  }

  return response;
}
```

### Q: How do I implement WebAuthn/Passkeys?
**A:** Follow our [WebAuthn Guide](api/webauthn.md):
1. Get registration options from `/api/v1/passkeys/register/options`
2. Use WebAuthn browser API to create credential
3. Send credential to `/api/v1/passkeys/register`
4. For authentication, get options from `/api/v1/passkeys/authenticate/options`
5. Use WebAuthn API to authenticate and send response

### Q: Can I customize the user data model?
**A:** Yes! Extend the base user model:
```python
from app.models.user import User
from sqlalchemy import Column, String, JSON

class CustomUser(User):
    __tablename__ = "users"

    # Add custom fields
    department = Column(String(100))
    custom_attributes = Column(JSON)
    employee_id = Column(String(50), unique=True)
```

### Q: How do I add custom endpoints?
**A:** Create custom routers and include them in the main app:
```python
# app/routers/custom.py
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/v1/custom")

@router.get("/my-endpoint")
async def my_endpoint():
    return {"message": "Custom endpoint"}

# In app/main.py
from app.routers import custom
app.include_router(custom.router)
```

## 📊 Deployment & Operations

### Q: What deployment options are available?
**A:** Multiple deployment options:
- **Railway** (recommended for quick setup)
- **Docker** containers (single or multi-container)
- **Kubernetes** (for enterprise scale)
- **Traditional VPS** (Ubuntu/CentOS/etc.)
- **Cloud providers** (AWS, GCP, Azure)

### Q: How do I scale the API horizontally?
**A:** The API is designed for horizontal scaling:
1. Use **stateless** application servers
2. Store sessions in **Redis** (not in memory)
3. Use a **load balancer** to distribute requests
4. Scale database with **read replicas**
5. Use **Redis clustering** for high availability

### Q: What monitoring is available?
**A:** Comprehensive monitoring options:
- **Health checks** at `/health` and `/ready`
- **Prometheus metrics** at `/metrics`
- **Structured logging** with correlation IDs
- **Performance monitoring** with request tracing
- **Error tracking** with Sentry integration
- **Custom dashboards** with Grafana

### Q: How do I backup and restore data?
**A:** Follow our [Backup Guide](deployment/backup-recovery.md):
- **Database**: Use `pg_dump` for PostgreSQL backups
- **Redis**: Use `redis-cli --rdb` for point-in-time snapshots
- **Files**: Backup uploaded files and certificates
- **Automated**: Set up automated daily backups
- **Testing**: Regularly test restore procedures

### Q: What are the performance characteristics?
**A:** Performance metrics:
- **Throughput**: 1000+ requests/second on modest hardware
- **Latency**: <50ms P95 response time for most endpoints
- **Concurrency**: Handles 1000+ concurrent connections
- **Async**: Non-blocking I/O for high performance
- **Caching**: Redis caching reduces database load

## 🐛 Troubleshooting

### Q: I'm getting "Connection refused" errors
**A:** Check these common issues:
1. **Database**: Is PostgreSQL running and accessible?
2. **Redis**: Is Redis running and accessible?
3. **Ports**: Are the default ports (5432, 6379) available?
4. **Environment**: Are DATABASE_URL and REDIS_URL correct?
5. **Firewall**: Are there firewall rules blocking connections?

### Q: Authentication isn't working
**A:** Debug authentication issues:
1. **Check logs**: Look for authentication errors in logs
2. **Token format**: Ensure `Authorization: Bearer <token>` format
3. **Token expiry**: Check if tokens are expired
4. **Secret keys**: Verify JWT_SECRET_KEY is consistent
5. **Algorithm**: Ensure JWT_ALGORITHM matches your setup

### Q: How do I enable debug logging?
**A:** Set debug environment variables:
```env
DEBUG=true
LOG_LEVEL=DEBUG
SQLALCHEMY_ECHO=true  # For SQL query logging
```

### Q: Database migrations are failing
**A:** Common migration issues:
1. **Check syntax**: Review the generated migration file
2. **Dependencies**: Ensure all dependencies are available
3. **Permissions**: Check database user permissions
4. **Conflicts**: Resolve any conflicting schema changes
5. **Rollback**: Use `alembic downgrade` if needed

### Q: How do I reset a user's password?
**A:** Use the admin interface or direct database access:
```python
# Admin script example
from app.services.auth_service import AuthService
from app.core.database import get_session

async def reset_password(email: str, new_password: str):
    auth_service = AuthService()
    user = await auth_service.get_user_by_email(email)
    await auth_service.update_password(user, new_password)
```

## 📚 Development

### Q: How do I contribute to Janua?
**A:** We welcome contributions! See our [Contributing Guide](CONTRIBUTING.md):
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run quality checks (`make check`)
5. Submit a pull request

### Q: What's the testing strategy?
**A:** Comprehensive testing approach:
- **Unit tests**: Test individual functions and classes
- **Integration tests**: Test component interactions
- **End-to-end tests**: Test complete user workflows
- **Performance tests**: Benchmark critical paths
- **Security tests**: Automated security scanning

### Q: How do I add a new authentication method?
**A:** Follow the plugin architecture:
1. Create authenticator class implementing `BaseAuthenticator`
2. Add configuration options to `Settings`
3. Register the authenticator in the factory
4. Add endpoints for the new method
5. Add comprehensive tests

### Q: Can I modify the database schema?
**A:** Yes, but follow migration best practices:
1. Use Alembic for all schema changes
2. Test migrations in development first
3. Plan for zero-downtime deployments
4. Always provide rollback migrations
5. Document schema changes

## 🎯 Best Practices

### Q: What are the security best practices?
**A:** Key security recommendations:
- **Use HTTPS** in production (never HTTP)
- **Strong secrets**: Use cryptographically secure random keys
- **Regular updates**: Keep dependencies current
- **Least privilege**: Grant minimum required permissions
- **Monitor logs**: Watch for suspicious activity
- **Rate limiting**: Protect against abuse
- **Input validation**: Validate all user inputs

### Q: How should I structure my client applications?
**A:** Client architecture recommendations:
- **Token storage**: Use secure storage (keychain, secure cookies)
- **Error handling**: Handle all error scenarios gracefully
- **Retry logic**: Implement exponential backoff for retries
- **State management**: Maintain authentication state consistently
- **Security**: Never log tokens or sensitive data

### Q: What are the performance best practices?
**A:** Performance optimization tips:
- **Caching**: Cache frequently accessed data
- **Connection pooling**: Use database connection pools
- **Async operations**: Use async/await for I/O operations
- **Pagination**: Paginate large result sets
- **Indexing**: Add database indexes for frequent queries
- **Monitoring**: Monitor and optimize slow queries

## 📞 Support

### Q: How do I get help?
**A:** Multiple support channels:
- **Documentation**: Check our comprehensive docs
- **GitHub Issues**: Report bugs and request features
- **GitHub Discussions**: Community Q&A
- **Discord**: Real-time community chat
- **Email**: Direct contact for complex issues

### Q: Do you offer commercial support?
**A:** Yes! We offer:
- **Priority support** with guaranteed response times
- **Professional services** for implementation assistance
- **Custom development** for specific requirements
- **Training** for your development team
- **SLA agreements** for enterprise customers

### Q: How do I report security issues?
**A:** For security issues:
- **Email**: [security@janua.dev](mailto:security@janua.dev)
- **PGP**: Use our [public key](https://janua.dev/.well-known/security.txt)
- **Responsible disclosure**: Allow time for fixes before public disclosure
- **Bug bounty**: We offer rewards for valid security reports

### Q: What's the roadmap for new features?
**A:** Check our public roadmap:
- **GitHub Projects**: View planned features and timeline
- **Release notes**: See what's included in each release
- **Community input**: Vote on features and provide feedback
- **Regular updates**: Quarterly roadmap reviews

---

## 💡 Still Have Questions?

Can't find what you're looking for? Here's how to get help:

1. **Search Documentation**: Use the search function in our docs
2. **Check Issues**: Look through [GitHub Issues](https://github.com/madfam-org/janua/issues)
3. **Ask Community**: Post in [GitHub Discussions](https://github.com/madfam-org/janua/discussions)
4. **Join Discord**: Real-time chat at [discord.gg/janua-dev](https://discord.gg/janua-dev)
5. **Contact Support**: Email [support@janua.dev](mailto:support@janua.dev)

---

<div align="center">

**[⬅️ Documentation Home](README.md)** • **[🚀 Getting Started](development/getting-started.md)** • **[📞 Support](mailto:support@janua.dev)**

</div>