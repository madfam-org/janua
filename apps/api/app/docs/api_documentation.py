"""
Interactive API Documentation Generator
Generates comprehensive OpenAPI documentation with examples, schemas, and interactive features
"""

from typing import Any, Dict
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """
    Generate enhanced OpenAPI schema with comprehensive documentation
    """

    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Janua API",
        version="1.0.0",
        description="""
# Janua API Documentation

## Overview
Janua is an enterprise-grade authentication and identity management platform that provides comprehensive security features including multi-factor authentication, single sign-on, and advanced user management.

## Features
- 🔐 **Authentication**: JWT-based authentication with refresh tokens
- 🔑 **Passkeys/WebAuthn**: Passwordless authentication support
- 📱 **Multi-Factor Authentication**: TOTP, SMS, and backup codes
- 🌐 **Single Sign-On**: SAML 2.0 and OAuth 2.0/OIDC
- 🏢 **Multi-Tenancy**: Built-in organization and tenant management
- 🛡️ **Security**: Rate limiting, input validation, and audit logging
- 📊 **Compliance**: GDPR, SOC2, HIPAA, and PCI-DSS support
- 🔄 **Session Management**: Distributed session handling with Redis
- 🎯 **RBAC**: Fine-grained role-based access control
- 🌍 **Localization**: Multi-language support with i18n

## Authentication
Most endpoints require authentication using a Bearer token in the Authorization header:
```
Authorization: Bearer <your_access_token>
```

## Rate Limiting
All endpoints are rate-limited to prevent abuse. Rate limit information is included in response headers:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

## Error Handling
The API uses standard HTTP status codes and returns error details in a consistent format:
```json
{
  "detail": "Error message",
  "error": "error_code",
  "context": {...}
}
```

## Pagination
List endpoints support pagination using query parameters:
- `limit`: Number of items per page (default: 20, max: 100)
- `offset`: Number of items to skip
- `page`: Page number (alternative to offset)

## Versioning
The API is versioned using URL path versioning. Current version: v1
        """,
        routes=app.routes,
        tags=[
            {
                "name": "Authentication",
                "description": "User authentication and session management",
                "externalDocs": {
                    "description": "Authentication Guide",
                    "url": "https://docs.janua.dev/authentication",
                },
            },
            {
                "name": "MFA",
                "description": "Multi-factor authentication setup and verification",
                "externalDocs": {
                    "description": "MFA Documentation",
                    "url": "https://docs.janua.dev/mfa",
                },
            },
            {
                "name": "Passkeys",
                "description": "WebAuthn/Passkey management for passwordless authentication",
                "externalDocs": {
                    "description": "Passkeys Guide",
                    "url": "https://docs.janua.dev/passkeys",
                },
            },
            {
                "name": "OAuth",
                "description": "OAuth 2.0 and OpenID Connect endpoints",
                "externalDocs": {
                    "description": "OAuth Documentation",
                    "url": "https://docs.janua.dev/oauth",
                },
            },
            {
                "name": "SSO",
                "description": "Single Sign-On with SAML 2.0",
                "externalDocs": {
                    "description": "SSO Setup Guide",
                    "url": "https://docs.janua.dev/sso",
                },
            },
            {"name": "Users", "description": "User profile and account management"},
            {"name": "Organizations", "description": "Multi-tenant organization management"},
            {"name": "Sessions", "description": "Active session management and monitoring"},
            {"name": "Compliance", "description": "GDPR, SOC2, HIPAA compliance endpoints"},
            {"name": "Admin", "description": "Administrative functions and system management"},
            {"name": "Webhooks", "description": "Webhook configuration and event subscriptions"},
            {"name": "Audit Logs", "description": "Security audit trail and activity logging"},
        ],
        servers=[
            {"url": "https://api.janua.dev", "description": "Production server"},
            {"url": "https://staging-api.janua.dev", "description": "Staging server"},
            {"url": "http://localhost:8000", "description": "Development server"},
        ],
        components={
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT authentication with Bearer token",
                },
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "API key authentication for service accounts",
                },
                "OAuth2": {
                    "type": "oauth2",
                    "flows": {
                        "authorizationCode": {
                            "authorizationUrl": "https://api.janua.dev/api/v1/oauth/authorize",
                            "tokenUrl": "https://api.janua.dev/api/v1/oauth/token",
                            "refreshUrl": "https://api.janua.dev/api/v1/oauth/refresh",
                            "scopes": {
                                "read:user": "Read user information",
                                "write:user": "Modify user information",
                                "read:org": "Read organization data",
                                "write:org": "Modify organization data",
                                "admin": "Full administrative access",
                            },
                        },
                        "clientCredentials": {
                            "tokenUrl": "https://api.janua.dev/api/v1/oauth/token",
                            "scopes": {"service": "Service-to-service authentication"},
                        },
                    },
                },
            },
            "responses": {
                "UnauthorizedError": {
                    "description": "Authentication required",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "detail": {"type": "string"},
                                    "error": {"type": "string", "example": "unauthorized"},
                                },
                            }
                        }
                    },
                },
                "ForbiddenError": {
                    "description": "Insufficient permissions",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "detail": {"type": "string"},
                                    "error": {"type": "string", "example": "forbidden"},
                                },
                            }
                        }
                    },
                },
                "NotFoundError": {
                    "description": "Resource not found",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "detail": {"type": "string"},
                                    "error": {"type": "string", "example": "not_found"},
                                },
                            }
                        }
                    },
                },
                "ValidationError": {
                    "description": "Validation error",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "detail": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "loc": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                                "msg": {"type": "string"},
                                                "type": {"type": "string"},
                                            },
                                        },
                                    }
                                },
                            }
                        }
                    },
                },
                "RateLimitError": {
                    "description": "Rate limit exceeded",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "detail": {"type": "string"},
                                    "error": {"type": "string", "example": "rate_limit_exceeded"},
                                    "retry_after": {"type": "integer"},
                                },
                            }
                        }
                    },
                    "headers": {
                        "X-RateLimit-Limit": {
                            "description": "Request limit per time window",
                            "schema": {"type": "integer"},
                        },
                        "X-RateLimit-Remaining": {
                            "description": "Remaining requests in current window",
                            "schema": {"type": "integer"},
                        },
                        "X-RateLimit-Reset": {
                            "description": "Time when rate limit resets (Unix timestamp)",
                            "schema": {"type": "integer"},
                        },
                        "Retry-After": {
                            "description": "Seconds until rate limit resets",
                            "schema": {"type": "integer"},
                        },
                    },
                },
            },
        },
    )

    # Add custom x-code-samples for interactive documentation
    add_code_samples(openapi_schema)

    # Add webhook schemas
    add_webhook_schemas(openapi_schema)

    app.openapi_schema = openapi_schema
    return app.openapi_schema


def add_code_samples(openapi_schema: Dict[str, Any]):
    """Add code samples for each endpoint"""

    code_samples = {
        "/api/v1/auth/signup": {
            "post": [
                {
                    "lang": "Python",
                    "source": """import janua

client = janua.Client(api_key="your_api_key")

user = client.auth.signup(
    email="user@example.com",
    password="SecurePassword123!",
    first_name="John",
    last_name="Doe"
)
print(f"User created: {user.id}")""",
                },
                {
                    "lang": "JavaScript",
                    "source": """const janua = require('janua-js');

const client = new janua.Client({ apiKey: 'your_api_key' });

const user = await client.auth.signup({
    email: 'user@example.com',
    password: 'SecurePassword123!',
    firstName: 'John',
    lastName: 'Doe'
});
console.log(`User created: ${user.id}`);""",
                },
                {
                    "lang": "cURL",
                    "source": """curl -X POST https://api.janua.dev/api/v1/auth/signup \\
  -H "Content-Type: application/json" \\
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!",
    "first_name": "John",
    "last_name": "Doe"
  }'""",
                },
            ]
        },
        "/api/v1/auth/signin": {
            "post": [
                {
                    "lang": "Python",
                    "source": """import janua

client = janua.Client()

auth = client.auth.signin(
    email="user@example.com",
    password="SecurePassword123!"
)
print(f"Access token: {auth.access_token}")""",
                },
                {
                    "lang": "JavaScript",
                    "source": """const janua = require('janua-js');

const client = new janua.Client();

const auth = await client.auth.signin({
    email: 'user@example.com',
    password: 'SecurePassword123!'
});
console.log(`Access token: ${auth.accessToken}`);""",
                },
                {
                    "lang": "cURL",
                    "source": """curl -X POST https://api.janua.dev/api/v1/auth/signin \\
  -H "Content-Type: application/json" \\
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'""",
                },
            ]
        },
    }

    # Add code samples to paths
    for path, methods in openapi_schema.get("paths", {}).items():
        if path in code_samples:
            for method, samples in code_samples[path].items():
                if method in methods:
                    methods[method]["x-code-samples"] = samples


def add_webhook_schemas(openapi_schema: Dict[str, Any]):
    """Add webhook event schemas"""

    webhook_schemas = {
        "webhooks": {
            "user.created": {
                "post": {
                    "requestBody": {
                        "description": "User created event",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "event": {"type": "string", "example": "user.created"},
                                        "timestamp": {"type": "string", "format": "date-time"},
                                        "data": {
                                            "type": "object",
                                            "properties": {
                                                "user_id": {"type": "string", "format": "uuid"},
                                                "email": {"type": "string", "format": "email"},
                                                "created_at": {
                                                    "type": "string",
                                                    "format": "date-time",
                                                },
                                            },
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Event processed successfully"}},
                }
            },
            "user.login": {
                "post": {
                    "requestBody": {
                        "description": "User login event",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "event": {"type": "string", "example": "user.login"},
                                        "timestamp": {"type": "string", "format": "date-time"},
                                        "data": {
                                            "type": "object",
                                            "properties": {
                                                "user_id": {"type": "string", "format": "uuid"},
                                                "ip_address": {"type": "string"},
                                                "user_agent": {"type": "string"},
                                                "session_id": {"type": "string", "format": "uuid"},
                                            },
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Event processed successfully"}},
                }
            },
            "mfa.enabled": {
                "post": {
                    "requestBody": {
                        "description": "MFA enabled event",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "event": {"type": "string", "example": "mfa.enabled"},
                                        "timestamp": {"type": "string", "format": "date-time"},
                                        "data": {
                                            "type": "object",
                                            "properties": {
                                                "user_id": {"type": "string", "format": "uuid"},
                                                "method": {
                                                    "type": "string",
                                                    "enum": ["totp", "sms", "passkey"],
                                                },
                                            },
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "Event processed successfully"}},
                }
            },
        }
    }

    openapi_schema.update(webhook_schemas)


def get_custom_swagger_ui_html() -> str:
    """Generate custom Swagger UI HTML with branding"""

    return """
    <!DOCTYPE html>
    <html>
    <head>
        <link type="text/css" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
        <title>Janua API - Swagger UI</title>
        <style>
            .swagger-ui .topbar { display: none }
            .swagger-ui .info .title { color: #6366f1 }
            .swagger-ui .btn.authorize { background-color: #6366f1; border-color: #6366f1 }
            .swagger-ui .btn.authorize:hover { background-color: #4f46e5; border-color: #4f46e5 }
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
        <script>
            window.onload = () => {
                window.ui = SwaggerUIBundle({
                    url: '/openapi.json',
                    dom_id: '#swagger-ui',
                    presets: [
                        SwaggerUIBundle.presets.apis,
                        SwaggerUIBundle.SwaggerUIStandalonePreset
                    ],
                    layout: "StandaloneLayout",
                    deepLinking: true,
                    showExtensions: true,
                    showCommonExtensions: true,
                    tryItOutEnabled: true,
                    supportedSubmitMethods: ['get', 'post', 'put', 'delete', 'patch'],
                    onComplete: () => {
                        console.log("Swagger UI loaded");
                    }
                });
            }
        </script>
    </body>
    </html>
    """


def get_custom_redoc_html() -> str:
    """Generate custom ReDoc HTML with branding"""

    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Janua API Documentation</title>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { margin: 0; padding: 0; }
            .menu-content { background: #fafafa !important; }
            [data-section-id] h1 { color: #6366f1 !important; }
        </style>
    </head>
    <body>
        <redoc spec-url="/openapi.json" 
               hide-download-button
               native-scrollbars
               theme='{
                   "colors": {
                       "primary": { "main": "#6366f1" },
                       "success": { "main": "#10b981" },
                       "warning": { "main": "#f59e0b" },
                       "error": { "main": "#ef4444" },
                       "text": { "primary": "#1f2937" }
                   },
                   "typography": {
                       "fontSize": "14px",
                       "lineHeight": "1.5",
                       "code": { "fontSize": "13px" }
                   },
                   "sidebar": { "backgroundColor": "#fafafa" }
               }'></redoc>
        <script src="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"></script>
    </body>
    </html>
    """
