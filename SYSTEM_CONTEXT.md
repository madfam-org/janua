# Janua - System Context

**Version:** 1.0.0
**Last Updated:** 2026-01-21

## Overview

Janua is MADFAM's SSO (Single Sign-On) identity provider. It handles authentication and authorization for all applications in the Galaxy ecosystem.

## Architecture

| Component | Port | Domain | Description |
|-----------|------|--------|-------------|
| Janua API | 8000 (container) / 80 (K8s service) | api.janua.dev, auth.madfam.io | OAuth 2.0 / OIDC provider |
| Janua Dashboard | 4101 (container) / 80 (K8s service) | app.janua.dev, dashboard.madfam.io | User management UI |
| Janua Admin | 4102 (container) / 80 (K8s service) | admin.janua.dev, admin.madfam.io | Admin console |

## Key Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/.well-known/openid-configuration` | OIDC discovery document |
| `/.well-known/jwks.json` | Public keys for JWT verification |
| `/oauth/authorize` | OAuth authorization endpoint |
| `/oauth/token` | Token exchange endpoint |
| `/oauth/userinfo` | User profile endpoint |
| `/api/health` | Health check |

## Integration Points

### Dependent Applications
- **Enclii** (app.enclii.dev, admin.enclii.dev) - Uses Janua for platform authentication
- **Dhanam** (app.dhan.am) - Uses Janua for SSO login

### Configuration Required for Clients
Clients integrating with Janua need:
- `OIDC_ISSUER`: `https://auth.madfam.io`
- `OIDC_CLIENT_ID`: Janua-generated client ID (format: `jnc_*`)
- `OIDC_CLIENT_SECRET`: Client secret (stored in K8s secrets)

## Kubernetes Resources

| Resource | Namespace | Purpose |
|----------|-----------|---------|
| `janua-api` | janua | Main API deployment |
| `janua-dashboard` | janua | User dashboard |
| `janua-admin` | janua | Admin interface |
| `janua-secrets` | janua | Credentials and keys |

## Critical Configuration

### Environment Variables (janua-api)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis for sessions
- `JWT_SIGNING_KEY`: RS256 private key for token signing
- `GITHUB_CLIENT_ID/SECRET`: GitHub OAuth integration

## Troubleshooting

### Verify OIDC is working
```bash
curl -s https://auth.madfam.io/.well-known/openid-configuration | jq '.issuer'
# Expected: "https://auth.madfam.io"
```

### Check JWKS endpoint
```bash
curl -s https://auth.madfam.io/.well-known/jwks.json | jq '.keys[0].kid'
```

### View API logs
```bash
kubectl logs -n janua -l app=janua-api -f
```

## Related Documentation
- [Janua API Docs](https://docs.janua.dev)
- [Enclii CLAUDE.md](/Users/aldoruizluna/labspace/enclii/CLAUDE.md)
- [Dhanam CLAUDE.md](/Users/aldoruizluna/labspace/dhanam/CLAUDE.md)
