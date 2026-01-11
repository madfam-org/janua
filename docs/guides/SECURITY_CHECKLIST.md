# Security Implementation Checklist

A comprehensive checklist for securely deploying and operating Janua in production environments.

## Table of Contents

1. [Pre-Deployment Security](#pre-deployment-security)
2. [Authentication Configuration](#authentication-configuration)
3. [API Security](#api-security)
4. [Database Security](#database-security)
5. [Infrastructure Security](#infrastructure-security)
6. [Monitoring and Incident Response](#monitoring-and-incident-response)
7. [Compliance Checklist](#compliance-checklist)
8. [Security Testing](#security-testing)

---

## Pre-Deployment Security

### Secrets Management

```
[ ] Generate cryptographically secure secrets
[ ] Store secrets in a secrets manager (Vault, AWS Secrets Manager, etc.)
[ ] Never commit secrets to version control
[ ] Rotate secrets on a regular schedule
[ ] Implement secret rotation without downtime
```

#### Required Secrets

| Secret | Length | Rotation | Notes |
|--------|--------|----------|-------|
| `SECRET_KEY` | 32+ bytes | 90 days | Application secret key |
| `JWT_PRIVATE_KEY` | RSA-2048+ | Yearly | JWT signing key |
| `DATABASE_URL` | N/A | 90 days | Database credentials |
| `REDIS_URL` | N/A | 90 days | Redis credentials (if auth enabled) |
| `ENCRYPTION_KEY` | 32 bytes | Yearly | Data encryption key |

#### Generate Secrets

```bash
# Generate secure random secret
openssl rand -base64 32

# Generate RSA key pair for JWT
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem

# Verify key strength
openssl rsa -in private.pem -text -noout | head -1
# Should show: Private-Key: (2048 bit, 2 primes)
```

### Environment Configuration

```
[ ] Set ENVIRONMENT=production
[ ] Set DEBUG=false
[ ] Configure production BASE_URL
[ ] Set SECURE_COOKIES=true
[ ] Configure CORS_ORIGINS restrictively
[ ] Set appropriate TRUSTED_PROXIES
```

#### Production Environment Template

```bash
# Core settings
ENVIRONMENT=production
DEBUG=false
BASE_URL=https://auth.yourcompany.com
API_BASE_URL=https://api.yourcompany.com

# Security
SECRET_KEY=<generated-32-byte-secret>
SECURE_COOKIES=true
COOKIE_DOMAIN=.yourcompany.com

# CORS (restrictive)
CORS_ORIGINS=https://app.yourcompany.com,https://admin.yourcompany.com

# JWT (RS256 for production)
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY=<base64-encoded-private-key>
JWT_PUBLIC_KEY=<base64-encoded-public-key>
JWT_ISSUER=https://api.yourcompany.com
JWT_AUDIENCE=yourcompany.com
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
TRUSTED_PROXIES=10.0.0.1,10.0.0.2
```

---

## Authentication Configuration

### Password Policy

```
[ ] Minimum 12 characters enforced
[ ] Require uppercase letters
[ ] Require lowercase letters
[ ] Require numbers
[ ] Require special characters
[ ] Implement password strength meter
[ ] Check against breached password lists
```

#### Configuration

```bash
PASSWORD_MIN_LENGTH=12
PASSWORD_REQUIRE_UPPERCASE=true
PASSWORD_REQUIRE_LOWERCASE=true
PASSWORD_REQUIRE_NUMBERS=true
PASSWORD_REQUIRE_SPECIAL=true
```

### Account Protection

```
[ ] Account lockout after failed attempts
[ ] Progressive lockout duration
[ ] Lockout notification to user
[ ] Admin override capability
[ ] Lockout logging and monitoring
```

#### Lockout Configuration

```bash
ACCOUNT_LOCKOUT_ENABLED=true
ACCOUNT_LOCKOUT_THRESHOLD=5        # Lock after 5 failed attempts
ACCOUNT_LOCKOUT_DURATION_MINUTES=15 # Lock for 15 minutes
ACCOUNT_LOCKOUT_RESET_ON_SUCCESS=true
```

### Multi-Factor Authentication

```
[ ] MFA available for all users
[ ] MFA enforced for admin accounts
[ ] MFA enforced for sensitive operations
[ ] TOTP (authenticator app) support
[ ] Backup codes generated and stored securely
[ ] MFA recovery process documented
```

#### MFA Best Practices

```yaml
mfa_configuration:
  # Methods available
  totp_enabled: true
  sms_enabled: false  # SMS is less secure, avoid if possible
  backup_codes_count: 10

  # Enforcement
  admin_mfa_required: true
  sensitive_operations_require_mfa:
    - password_change
    - email_change
    - api_key_creation
    - organization_settings_change
    - user_deletion
```

### Session Security

```
[ ] Secure session cookies
[ ] HttpOnly flag on all auth cookies
[ ] SameSite attribute set appropriately
[ ] Session timeout configured
[ ] Concurrent session limit (optional)
[ ] Session revocation capability
```

#### Session Configuration

```bash
# Cookie settings
SECURE_COOKIES=true
SESSION_COOKIE_SAMESITE=lax
SESSION_COOKIE_HTTPONLY=true

# Session timeouts
SESSION_IDLE_TIMEOUT_MINUTES=30
SESSION_ABSOLUTE_TIMEOUT_HOURS=24
MAX_CONCURRENT_SESSIONS=5  # Optional limit
```

### OAuth/OIDC Security

```
[ ] Use RS256 for JWT signing (not HS256)
[ ] Validate redirect URIs exactly
[ ] Use state parameter for CSRF protection
[ ] Use PKCE for public clients
[ ] Short authorization code lifetime
[ ] Token rotation on refresh
```

#### OAuth Configuration

```bash
# JWT
JWT_ALGORITHM=RS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# OAuth security
OAUTH_AUTHORIZATION_CODE_EXPIRE_SECONDS=60
OAUTH_REQUIRE_PKCE_FOR_PUBLIC_CLIENTS=true
OAUTH_STRICT_REDIRECT_URI_MATCHING=true
```

---

## API Security

### Rate Limiting

```
[ ] Global rate limiting enabled
[ ] Per-endpoint rate limits for sensitive routes
[ ] Rate limit headers in responses
[ ] Rate limit bypass for internal services
[ ] DDoS protection at edge
```

#### Rate Limit Configuration

| Endpoint Category | Per Minute | Per Hour |
|-------------------|------------|----------|
| Authentication | 10 | 100 |
| Password Reset | 5 | 20 |
| Token Refresh | 30 | 300 |
| API Operations | 60 | 1000 |
| Admin Operations | 120 | 2000 |

### Input Validation

```
[ ] All inputs validated and sanitized
[ ] SQL injection prevention (parameterized queries)
[ ] NoSQL injection prevention
[ ] Command injection prevention
[ ] Path traversal prevention
[ ] File upload validation
```

#### Validation Checklist

```python
# Example validation patterns
from pydantic import BaseModel, EmailStr, constr, validator

class UserCreate(BaseModel):
    email: EmailStr  # Validates email format
    password: constr(min_length=12, max_length=128)  # Length limits
    first_name: constr(max_length=100, regex=r'^[\w\s-]+$')  # Alphanumeric only

    @validator('password')
    def password_strength(cls, v):
        # Check complexity requirements
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain lowercase')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        if not any(c in '!@#$%^&*()_+-=' for c in v):
            raise ValueError('Password must contain special character')
        return v
```

### Security Headers

```
[ ] Strict-Transport-Security (HSTS)
[ ] Content-Security-Policy (CSP)
[ ] X-Content-Type-Options
[ ] X-Frame-Options
[ ] X-XSS-Protection
[ ] Referrer-Policy
[ ] Permissions-Policy
```

#### Header Configuration

```python
# Security headers middleware
SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https://api.yourcompany.com; "
        "frame-ancestors 'none'; "
        "form-action 'self';"
    ),
}
```

### API Authentication

```
[ ] All endpoints require authentication (except public)
[ ] Token validation on every request
[ ] Token expiration enforced
[ ] Revoked token checking
[ ] API key hashing (never store plaintext)
```

---

## Database Security

### Connection Security

```
[ ] TLS/SSL for database connections
[ ] Certificate verification enabled
[ ] Connection credentials rotated regularly
[ ] Minimal privileges for application user
[ ] Separate read/write users if needed
```

#### PostgreSQL SSL Configuration

```bash
# Enable SSL in connection string
DATABASE_URL=postgresql://user:pass@host:5432/janua?sslmode=verify-full&sslrootcert=/path/to/ca.crt

# PostgreSQL server configuration
ssl = on
ssl_cert_file = '/path/to/server.crt'
ssl_key_file = '/path/to/server.key'
ssl_ca_file = '/path/to/ca.crt'
```

### Data Encryption

```
[ ] Sensitive data encrypted at rest
[ ] Encryption keys managed securely
[ ] Key rotation process documented
[ ] Backup encryption enabled
```

#### Encrypted Fields

| Field | Encryption | Notes |
|-------|------------|-------|
| Passwords | bcrypt (rounds=12) | One-way hash |
| API Keys | SHA-256 | Token hash stored |
| MFA Secrets | AES-256-GCM | Reversible encryption |
| Backup Codes | bcrypt | One-way hash |
| OAuth Secrets | AES-256-GCM | Reversible encryption |

### Access Control

```
[ ] Principle of least privilege
[ ] Row-level security where applicable
[ ] Audit logging for data access
[ ] No direct database access from internet
```

#### PostgreSQL User Setup

```sql
-- Application user (minimal privileges)
CREATE USER janua_app WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE janua TO janua_app;
GRANT USAGE ON SCHEMA public TO janua_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO janua_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO janua_app;

-- Read-only user for reporting
CREATE USER janua_readonly WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE janua TO janua_readonly;
GRANT USAGE ON SCHEMA public TO janua_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO janua_readonly;
```

---

## Infrastructure Security

### Network Security

```
[ ] API not directly exposed to internet
[ ] Load balancer/reverse proxy in front
[ ] Internal services on private network
[ ] Database on private network only
[ ] Redis on private network only
[ ] Firewall rules configured
```

#### Network Architecture

```
                      Internet
                          │
                          ▼
                ┌─────────────────┐
                │  Load Balancer  │ ◄── TLS termination
                │  (Cloudflare)   │
                └────────┬────────┘
                         │ Internal network
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │ API Pod  │   │ API Pod  │   │ API Pod  │
   └────┬─────┘   └────┬─────┘   └────┬─────┘
        │              │              │
        └──────────────┼──────────────┘
                       │ Private network
         ┌─────────────┼─────────────┐
         ▼                           ▼
   ┌──────────┐               ┌──────────┐
   │PostgreSQL│               │  Redis   │
   └──────────┘               └──────────┘
```

### Kubernetes Security

```
[ ] Pod security policies/standards
[ ] Network policies for pod isolation
[ ] Secrets stored in K8s secrets or external
[ ] No privileged containers
[ ] Read-only root filesystem
[ ] Resource limits set
```

#### Security Context

```yaml
# deployment.yaml
spec:
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: janua-api
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
              - ALL
        resources:
          limits:
            memory: "512Mi"
            cpu: "1000m"
          requests:
            memory: "256Mi"
            cpu: "250m"
```

#### Network Policy

```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: janua-api-policy
spec:
  podSelector:
    matchLabels:
      app: janua-api
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: cloudflare-tunnel
    ports:
    - port: 4100
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgresql
    ports:
    - port: 5432
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - port: 6379
```

### Container Security

```
[ ] Minimal base images (distroless/alpine)
[ ] No secrets in image layers
[ ] Image vulnerability scanning
[ ] Signed images (optional)
[ ] Regular base image updates
```

#### Dockerfile Security

```dockerfile
# Use minimal base image
FROM python:3.11-slim-bookworm AS base

# Create non-root user
RUN groupadd -r janua && useradd -r -g janua janua

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=janua:janua . .

# Switch to non-root user
USER janua

# No secrets in ENV, use runtime injection
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4100"]
```

---

## Monitoring and Incident Response

### Audit Logging

```
[ ] Authentication events logged
[ ] Authorization decisions logged
[ ] Data access logged
[ ] Admin actions logged
[ ] Log integrity protected
[ ] Logs shipped to SIEM
```

#### Events to Log

| Event | Severity | Details |
|-------|----------|---------|
| Login success | INFO | User ID, IP, timestamp |
| Login failure | WARNING | Email, IP, failure reason |
| Password change | INFO | User ID, IP, method |
| MFA enabled/disabled | INFO | User ID, method |
| Session revoked | INFO | User ID, session ID, reason |
| API key created | INFO | User ID, key prefix, permissions |
| Permission denied | WARNING | User ID, resource, action |
| Account locked | WARNING | User ID, IP, attempt count |
| Admin action | INFO | Admin ID, action, target |

### Security Monitoring

```
[ ] Failed login attempt monitoring
[ ] Unusual access patterns detected
[ ] Rate limit violations tracked
[ ] Geographic anomaly detection
[ ] Real-time alerting configured
```

#### Alert Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Failed logins (per IP) | 10/hour | 50/hour | Block IP |
| Failed logins (per user) | 3/hour | 10/hour | Lock account |
| Rate limit hits | 100/min | 500/min | Investigate |
| 4xx errors | 10% | 25% | Investigate |
| 5xx errors | 1% | 5% | Page on-call |

### Incident Response

```
[ ] Incident response plan documented
[ ] On-call rotation established
[ ] Communication channels defined
[ ] Runbooks for common incidents
[ ] Post-incident review process
```

#### Incident Response Runbook Template

```markdown
## Incident: [Title]

### Detection
- How was it detected?
- When was it detected?
- Who detected it?

### Containment
1. [ ] Assess scope of impact
2. [ ] Isolate affected systems
3. [ ] Preserve evidence

### Eradication
1. [ ] Identify root cause
2. [ ] Remove threat/vulnerability
3. [ ] Patch/fix applied

### Recovery
1. [ ] Restore from backup if needed
2. [ ] Verify system integrity
3. [ ] Resume normal operations

### Lessons Learned
- What went well?
- What could improve?
- Action items
```

---

## Compliance Checklist

### GDPR (EU)

```
[ ] Privacy policy published
[ ] Consent mechanisms implemented
[ ] Data subject rights implemented
  [ ] Right to access
  [ ] Right to rectification
  [ ] Right to erasure
  [ ] Right to data portability
[ ] Data processing agreements in place
[ ] Breach notification process (72 hours)
[ ] Data retention policies defined
[ ] DPO designated (if required)
```

### SOC 2

```
[ ] Access controls documented
[ ] Encryption at rest and in transit
[ ] Audit logging enabled
[ ] Incident response plan
[ ] Vendor management process
[ ] Change management process
[ ] Risk assessment conducted
[ ] Security awareness training
```

### HIPAA (if applicable)

```
[ ] Business Associate Agreements
[ ] PHI encryption
[ ] Access audit trails
[ ] Minimum necessary access
[ ] Workforce training
[ ] Incident response plan
[ ] Risk analysis documented
```

---

## Security Testing

### Pre-Deployment Testing

```
[ ] Static Application Security Testing (SAST)
[ ] Dependency vulnerability scanning
[ ] Secret scanning in codebase
[ ] Container image scanning
[ ] Infrastructure as Code scanning
```

#### Automated Scanning

```bash
# Dependency scanning (Python)
pip-audit --require-hashes

# Dependency scanning (Node)
npm audit --production

# Secret scanning
gitleaks detect --source .

# Container scanning
trivy image janua-api:latest

# SAST
bandit -r app/
```

### Penetration Testing

```
[ ] Annual penetration test scheduled
[ ] Scope defined with vendor
[ ] Remediation timeline agreed
[ ] Findings tracked to closure
[ ] Retest after remediation
```

#### Penetration Test Scope

```markdown
## In Scope
- Authentication endpoints (/auth/*)
- User management endpoints (/users/*)
- Organization endpoints (/organizations/*)
- OAuth/OIDC flows
- Session management
- API key authentication
- MFA implementation

## Out of Scope
- Third-party integrations
- Physical security
- Social engineering
- DDoS testing
```

### Ongoing Security Testing

```
[ ] Regular dependency updates
[ ] Automated vulnerability scanning in CI/CD
[ ] Bug bounty program (optional)
[ ] Red team exercises (optional)
```

---

## Quick Reference

### Security Configuration Checklist

```bash
# Copy this to your deployment checklist

## Environment
[ ] ENVIRONMENT=production
[ ] DEBUG=false
[ ] SECURE_COOKIES=true

## Authentication
[ ] JWT_ALGORITHM=RS256
[ ] JWT keys generated and stored securely
[ ] PASSWORD_MIN_LENGTH=12
[ ] ACCOUNT_LOCKOUT_ENABLED=true
[ ] RATE_LIMIT_ENABLED=true

## Database
[ ] SSL enabled for connections
[ ] Credentials in secrets manager
[ ] Application user has minimal privileges

## Network
[ ] TLS 1.2+ only
[ ] Database on private network
[ ] Firewall rules configured
[ ] Security headers set

## Monitoring
[ ] Audit logging enabled
[ ] Log shipping configured
[ ] Alerts set up
[ ] Incident response plan ready
```

### Emergency Contacts

```yaml
# Update with your team's information
security_contacts:
  primary:
    name: "Security Team Lead"
    email: "security@yourcompany.com"
    phone: "+1-XXX-XXX-XXXX"

  escalation:
    - name: "CTO"
      email: "cto@yourcompany.com"
    - name: "CEO"
      email: "ceo@yourcompany.com"

external_contacts:
  incident_response: "vendor@security-firm.com"
  legal: "legal@law-firm.com"
```

---

## Related Documentation

- [Security Policy](../security/SECURITY.md)
- [Performance Tuning Guide](./PERFORMANCE_TUNING_GUIDE.md)
- [Deployment Guide](../deployment/README.md)
- [MFA Implementation Guide](./mfa-2fa-implementation-guide.md)
- [Enterprise SSO Setup](./enterprise-sso-saml-setup-guide.md)
