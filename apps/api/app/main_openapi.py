"""The FastAPI application's metadata (split out of app/main.py).

Moved verbatim on 2026-11-19 to keep app/main.py under the repository's
800-line pre-commit limit; `app = FastAPI(**API_METADATA)` builds the same app.
"""

from app.config import settings

API_METADATA = {
    "title": "Janua Authentication API",
    "version": "0.1.0",
    "description": """
# Janua Authentication Platform

Modern, open-core authentication and identity management platform with enterprise features.

## Features

* 🔐 **Complete Authentication**: Email/password, OAuth (Google, GitHub, Microsoft, Apple), Magic Links, Passkeys
* 🛡️ **MFA & Security**: TOTP, SMS, Backup codes, Device fingerprinting
* 👥 **Multi-Tenancy**: Organizations, RBAC, Team management
* 🔄 **Session Management**: Multi-device tracking, Revocation, Security warnings
* 🎯 **Enterprise Features**: SAML/SSO, SCIM, Compliance (GDPR, SOC 2), Webhooks
* 📊 **Developer Experience**: TypeScript SDK, React UI Components, Comprehensive docs

## Getting Started

1. **Sign Up**: `POST /api/v1/auth/signup` - Create your account
2. **Get Token**: Receive JWT access + refresh tokens
3. **Authenticate**: Add `Authorization: Bearer {token}` header to requests
4. **Integrate**: Use our TypeScript SDK or REST API directly

## Authentication

All protected endpoints require a JWT access token in the Authorization header:

```
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

Get tokens via:
- Email/password: `POST /api/v1/auth/signin`
- OAuth: `POST /api/v1/oauth/{provider}/callback`
- Magic link: `POST /api/v1/auth/magic-link/verify`

## Rate Limiting

All endpoints are rate-limited for security:
- Sign up: 3 requests/minute
- Sign in: 5 requests/minute
- Password reset: 3 requests/hour
- General endpoints: 100 requests/minute

Rate limit headers returned in response:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Environments

- **Production**: https://api.janua.dev
- **Staging**: https://staging-api.janua.dev
- **Development**: http://localhost:4100

## Support

- Documentation: https://docs.janua.dev
- GitHub: https://github.com/madfam-org/janua
- Discord: https://discord.gg/janua
- Email: support@madfam.io

## SDK Libraries

- **TypeScript**: `npm install @janua/typescript-sdk`
- **React UI**: `npm install @janua/ui`
- **Python**: `pip install janua` (coming soon)
- **Go**: `go get github.com/madfam-org/janua-go` (coming soon)
    """,
    "docs_url": "/docs" if settings.ENABLE_DOCS else None,
    "redoc_url": "/redoc" if settings.ENABLE_DOCS else None,
    "openapi_tags": [
        {
            "name": "Authentication",
            "description": "User authentication endpoints including sign up, sign in, password management, email verification, and magic links.",
        },
        {
            "name": "OAuth",
            "description": "Social authentication with Google, GitHub, Microsoft, and Apple OAuth providers.",
        },
        {
            "name": "Users",
            "description": "User profile management including updates, deletion, and profile information.",
        },
        {
            "name": "Sessions",
            "description": "Session management across multiple devices with tracking, listing, and revocation capabilities.",
        },
        {
            "name": "Organizations",
            "description": "Multi-tenant organization management with members, roles, and settings.",
        },
        {
            "name": "MFA",
            "description": "Multi-factor authentication with TOTP, SMS, and backup codes for enhanced security.",
        },
        {
            "name": "Passkeys",
            "description": "WebAuthn/FIDO2 passkey authentication for passwordless secure login.",
        },
        {
            "name": "Admin",
            "description": "Administrative endpoints for system monitoring, user management, and statistics.",
        },
        {
            "name": "Webhooks",
            "description": "Event-driven webhooks for user actions, authentication events, and system notifications.",
        },
        {
            "name": "RBAC",
            "description": "Role-based access control for fine-grained permission management.",
        },
        {
            "name": "Policies",
            "description": "Security policies for password requirements, session timeouts, and access controls.",
        },
        {
            "name": "Audit Logs",
            "description": "Comprehensive audit logging for compliance and security monitoring.",
        },
        {
            "name": "SSO",
            "description": "Enterprise Single Sign-On with SAML 2.0 and OIDC support.",
        },
        {
            "name": "SCIM",
            "description": "System for Cross-domain Identity Management for automated user provisioning.",
        },
        {
            "name": "Compliance",
            "description": "GDPR, SOC 2, and regulatory compliance features including data export and deletion.",
        },
        {
            "name": "API Keys",
            "description": "API key management for programmatic access with scoped permissions.",
        },
    ],
    "contact": {
        "name": "Janua Support",
        "url": "https://janua.dev/support",
        "email": "support@madfam.io",
    },
    "license_info": {
        "name": "AGPL-3.0",
        "url": "https://github.com/madfam-org/janua/blob/main/LICENSE",
    },
    "servers": [
        {
            "url": "https://api.janua.dev",
            "description": "Production server",
        },
        {
            "url": "https://staging-api.janua.dev",
            "description": "Staging server",
        },
        {
            "url": "http://localhost:4100",
            "description": "Local development server",
        },
    ],
}
