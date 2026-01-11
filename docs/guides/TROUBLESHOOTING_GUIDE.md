# Janua Troubleshooting Guide

> **Comprehensive guide to diagnosing and resolving common issues**

This guide covers common issues, their root causes, and solutions for Janua authentication platform.

---

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [HTTP Status Codes Reference](#http-status-codes-reference)
3. [Authentication Issues](#authentication-issues)
4. [JWT/Token Problems](#jwttoken-problems)
5. [Database Issues](#database-issues)
6. [Redis/Caching Issues](#rediscaching-issues)
7. [SSO/SAML Problems](#ssosaml-problems)
8. [MFA Issues](#mfa-issues)
9. [WebAuthn/Passkeys Issues](#webauthnpasskeys-issues)
10. [SDK Integration Issues](#sdk-integration-issues)
11. [Email Issues](#email-issues)
12. [Performance Problems](#performance-problems)
13. [Deployment Issues](#deployment-issues)
14. [Debugging Techniques](#debugging-techniques)

---

## Quick Diagnostics

### Health Check Endpoints

```bash
# API Health
curl https://api.janua.dev/health

# Detailed health with dependencies
curl https://api.janua.dev/health/detailed

# Ready check (for Kubernetes)
curl https://api.janua.dev/ready
```

### Expected Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "dependencies": {
    "database": "healthy",
    "redis": "healthy",
    "email": "healthy"
  }
}
```

### Common Status Indicators

| Status | Meaning | Action |
|--------|---------|--------|
| `healthy` | All systems operational | None |
| `degraded` | Some features affected | Check dependencies |
| `unhealthy` | Critical issues | Immediate investigation |

---

## HTTP Status Codes Reference

### Error Code Matrix

| HTTP Code | Error Code | Meaning | Common Causes |
|-----------|------------|---------|---------------|
| **400** | `BAD_REQUEST` | Invalid request format | Malformed JSON, missing fields |
| **401** | `AUTHENTICATION_ERROR` | Authentication failed | Invalid credentials, expired token |
| **401** | `TOKEN_ERROR` | Token validation failed | Expired, malformed, or revoked token |
| **403** | `AUTHORIZATION_ERROR` | Permission denied | Insufficient role/permissions |
| **404** | `NOT_FOUND_ERROR` | Resource not found | Invalid ID, deleted resource |
| **409** | `CONFLICT_ERROR` | Resource conflict | Duplicate email, existing user |
| **422** | `VALIDATION_ERROR` | Validation failed | Invalid email format, weak password |
| **429** | `RATE_LIMIT_ERROR` | Too many requests | Rate limit exceeded |
| **500** | `INTERNAL_ERROR` | Server error | Bug, dependency failure |
| **502** | `EXTERNAL_SERVICE_ERROR` | External service failed | OAuth provider, email service down |
| **503** | `SERVICE_UNAVAILABLE` | Service temporarily down | Maintenance, overload |

### Error Response Format

```json
{
  "error": "AUTHENTICATION_ERROR",
  "message": "Invalid credentials",
  "status_code": 401,
  "timestamp": "2025-01-11T10:30:00Z",
  "request_id": "req_abc123",
  "details": {
    "field": "password",
    "reason": "Password does not match"
  }
}
```

---

## Authentication Issues

### Issue: "Invalid credentials" on login

**Symptoms:**
- 401 response with `INVALID_CREDENTIALS`
- User cannot log in despite correct password

**Possible Causes & Solutions:**

1. **Password mismatch**
   ```bash
   # Verify user exists
   curl -X GET "https://api.janua.dev/api/v1/admin/users?email=user@example.com" \
     -H "Authorization: Bearer $ADMIN_TOKEN"
   ```

2. **Account not verified**
   ```json
   {
     "error": "EMAIL_NOT_VERIFIED",
     "message": "Please verify your email before logging in"
   }
   ```
   **Solution:** Check `email_verified` field, resend verification email

3. **Account locked**
   ```json
   {
     "error": "ACCOUNT_LOCKED",
     "message": "Account locked due to multiple failed attempts"
   }
   ```
   **Solution:** Wait for lockout period (default: 30 minutes) or admin unlock

4. **Case sensitivity**
   - Emails are normalized to lowercase
   - Usernames are case-sensitive

### Issue: "User already exists" on registration

**Symptoms:**
- 409 Conflict response
- Registration fails

**Solutions:**

```python
# Check for existing user
from app.services.user_service import UserService

user = await user_service.get_by_email("email@example.com")
if user:
    # Option 1: Trigger password reset
    await auth_service.send_password_reset(user.email)

    # Option 2: Merge accounts (if OAuth)
    await auth_service.link_account(user.id, oauth_data)
```

### Issue: Session not persisting

**Symptoms:**
- User gets logged out unexpectedly
- "Session expired" messages

**Causes & Solutions:**

1. **Redis connection issues**
   ```bash
   # Test Redis connectivity
   redis-cli -h $REDIS_HOST -p $REDIS_PORT ping
   ```

2. **Cookie configuration**
   ```env
   # Ensure correct settings
   SESSION_COOKIE_SECURE=true          # HTTPS only
   SESSION_COOKIE_SAMESITE=lax         # Cross-site requests
   SESSION_COOKIE_HTTPONLY=true        # No JavaScript access
   SESSION_COOKIE_DOMAIN=.yourdomain.com
   ```

3. **Token refresh not working**
   ```javascript
   // SDK should auto-refresh, verify setup:
   const client = new JanuaClient({
     baseUrl: 'https://api.janua.dev',
     autoRefresh: true,  // Must be true
     refreshThreshold: 300  // Refresh 5 min before expiry
   });
   ```

---

## JWT/Token Problems

### Issue: "Token expired" or "Token invalid"

**Symptoms:**
- 401 response with `TOKEN_EXPIRED` or `TOKEN_INVALID`
- API calls fail after period of inactivity

**Diagnostic Steps:**

```bash
# Decode token (without verification)
echo $ACCESS_TOKEN | cut -d'.' -f2 | base64 -d 2>/dev/null | jq

# Check expiry
python3 -c "
import jwt
import datetime
token = '$ACCESS_TOKEN'
payload = jwt.decode(token, options={'verify_signature': False})
exp = datetime.datetime.fromtimestamp(payload['exp'])
print(f'Expires: {exp}')
print(f'Now: {datetime.datetime.now()}')
"
```

**Solutions:**

1. **Implement token refresh**
   ```python
   # Python SDK
   from janua import JanuaClient

   client = JanuaClient(api_key="...")

   # Automatic refresh
   try:
       response = client.users.me()
   except AuthenticationError as e:
       if e.error_code == "TOKEN_EXPIRED":
           client.auth.refresh()  # Refresh tokens
           response = client.users.me()  # Retry
   ```

2. **Check clock synchronization**
   ```bash
   # Server time should match
   date
   ntpq -p  # Check NTP sync
   ```

3. **Verify signing keys match**
   ```bash
   # Compare public key hashes
   openssl rsa -pubin -in /path/to/public.pem -outform DER | sha256sum
   ```

### Issue: "Algorithm mismatch"

**Symptoms:**
- `TOKEN_INVALID` with algorithm errors
- Tokens from different environments fail

**Solution:**

```env
# Ensure consistent algorithm across services
JWT_ALGORITHM=RS256

# For RS256, both keys required
JWT_PRIVATE_KEY_PATH=/keys/private.pem
JWT_PUBLIC_KEY_PATH=/keys/public.pem
```

### Issue: Refresh token not working

**Symptoms:**
- `REFRESH_TOKEN_INVALID` or `REFRESH_TOKEN_EXPIRED`
- Cannot get new access token

**Causes:**

1. **Token already used** (single-use rotation enabled)
   ```env
   REFRESH_TOKEN_ROTATION=true  # Each refresh invalidates previous
   ```

2. **Token revoked** (user logout, password change)
   ```python
   # Check if token family is revoked
   from app.services.token_service import TokenService

   is_valid = await token_service.validate_refresh_token(token)
   ```

3. **Token expired**
   ```env
   REFRESH_TOKEN_EXPIRE_DAYS=7  # Default, adjust as needed
   ```

---

## Database Issues

### Issue: Connection refused / timeout

**Symptoms:**
- 500 errors on all requests
- "Connection refused" in logs
- Health check fails for database

**Diagnostic Steps:**

```bash
# Test PostgreSQL connection
psql "$DATABASE_URL" -c "SELECT 1"

# Check connection count
psql "$DATABASE_URL" -c "
SELECT count(*) as connections,
       max_conn.max_val as max_connections
FROM pg_stat_activity
CROSS JOIN (SELECT setting::int as max_val FROM pg_settings WHERE name='max_connections') max_conn
GROUP BY max_conn.max_val;
"
```

**Solutions:**

1. **Connection pool exhaustion**
   ```python
   # In app/config.py
   DATABASE_POOL_SIZE = 20        # Increase pool size
   DATABASE_POOL_OVERFLOW = 10    # Allow temporary overflow
   DATABASE_POOL_TIMEOUT = 30     # Wait for connection
   DATABASE_POOL_RECYCLE = 1800   # Recycle connections
   ```

2. **Network/firewall issues**
   ```bash
   # Test connectivity
   nc -zv $DB_HOST $DB_PORT

   # Check firewall rules
   iptables -L -n | grep $DB_PORT
   ```

3. **PostgreSQL not accepting connections**
   ```bash
   # Check pg_hba.conf for access rules
   cat /etc/postgresql/14/main/pg_hba.conf | grep -v "^#"
   ```

### Issue: Migration failures

**Symptoms:**
- `alembic upgrade head` fails
- Database schema out of sync

**Diagnostic Steps:**

```bash
# Check current revision
alembic current

# Show migration history
alembic history --verbose

# Check for pending migrations
alembic heads
```

**Solutions:**

1. **Conflicting migrations**
   ```bash
   # Merge heads if multiple
   alembic merge heads -m "merge_branches"
   alembic upgrade head
   ```

2. **Failed migration stuck**
   ```sql
   -- Check alembic version table
   SELECT * FROM alembic_version;

   -- If stuck, manually fix (DANGEROUS - backup first!)
   DELETE FROM alembic_version;
   INSERT INTO alembic_version VALUES ('known_good_revision');
   ```

3. **Permission issues**
   ```sql
   -- Grant necessary permissions
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO janua_user;
   GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO janua_user;
   ```

---

## Redis/Caching Issues

### Issue: Redis connection failures

**Symptoms:**
- Sessions not persisting
- Rate limiting not working
- Performance degradation (cache misses)

**Diagnostic Steps:**

```bash
# Test Redis connection
redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD ping

# Check Redis info
redis-cli INFO server
redis-cli INFO clients
redis-cli INFO memory
```

**Solutions:**

1. **Circuit breaker triggered**
   ```python
   # Janua has built-in circuit breaker for Redis
   # Check cache manager status
   from app.core.caching import cache_manager

   print(cache_manager.circuit_breaker.state)  # 'closed', 'open', 'half-open'
   ```

2. **Memory limit reached**
   ```bash
   # Check memory usage
   redis-cli INFO memory | grep used_memory_human

   # Clear expired keys
   redis-cli BGSAVE  # Snapshot first
   redis-cli DEBUG RELOAD  # Clear and reload
   ```

3. **Connection pool exhausted**
   ```env
   REDIS_MAX_CONNECTIONS=100
   REDIS_SOCKET_TIMEOUT=5
   ```

### Issue: Cache inconsistency

**Symptoms:**
- Stale data returned
- Updates not reflected immediately

**Solutions:**

1. **Clear specific cache**
   ```python
   from app.core.caching import cache_manager

   # Clear user cache
   await cache_manager.invalidate("user:*")

   # Clear organization cache
   await cache_manager.invalidate("org:*")

   # Clear all
   await cache_manager.clear_all()
   ```

2. **Verify TTL settings**
   ```python
   # Default TTLs in performance.py
   CACHE_TTL = {
       'user_profile': 300,      # 5 minutes
       'session_validation': 60,  # 1 minute
       'organization': 600,       # 10 minutes
       'permissions': 300,        # 5 minutes
       'settings': 1800,          # 30 minutes
   }
   ```

---

## SSO/SAML Problems

### Issue: SAML assertion validation failed

**Symptoms:**
- `SSO_AUTHENTICATION_ERROR`
- "Invalid SAML response" or "Assertion not valid"

**Diagnostic Steps:**

1. **Check SAML response**
   ```python
   # Enable SAML debugging
   import logging
   logging.getLogger('saml2').setLevel(logging.DEBUG)
   ```

2. **Validate certificates**
   ```bash
   # Check certificate expiry
   openssl x509 -in idp_certificate.pem -noout -dates

   # Verify certificate matches IdP metadata
   openssl x509 -in idp_certificate.pem -fingerprint -noout
   ```

**Common Issues:**

| Issue | Error Message | Solution |
|-------|---------------|----------|
| Clock skew | "NotBefore condition not met" | Sync server time with NTP |
| Wrong audience | "Invalid audience" | Verify SP Entity ID matches |
| Certificate mismatch | "Signature verification failed" | Update IdP certificate |
| Response timeout | "Response expired" | Check `NotOnOrAfter` condition |

### Issue: SSO redirect loop

**Symptoms:**
- Browser redirects infinitely
- Never reaches application

**Solutions:**

1. **Check RelayState**
   ```python
   # Ensure RelayState is preserved
   SSO_RELAY_STATE_SECRET = "your-secret-key"  # Must be set
   ```

2. **Verify callback URL**
   ```env
   SSO_CALLBACK_URL=https://your-app.com/api/v1/sso/callback
   # Must match exactly what's registered with IdP
   ```

3. **Check session cookie**
   ```env
   SESSION_COOKIE_SAMESITE=lax  # 'strict' may block redirects
   ```

### Issue: User attributes not mapping

**Symptoms:**
- User created but missing data
- Name/email not populated

**Solution:**

```python
# Configure attribute mapping in SSO provider settings
SSO_ATTRIBUTE_MAPPING = {
    "email": ["email", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"],
    "first_name": ["firstName", "givenName", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname"],
    "last_name": ["lastName", "surname", "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"],
}
```

---

## MFA Issues

### Issue: TOTP codes not working

**Symptoms:**
- Valid codes rejected
- "Invalid verification code" error

**Causes & Solutions:**

1. **Time sync issues**
   ```bash
   # Server time must be accurate
   timedatectl status

   # Enable NTP sync
   timedatectl set-ntp true
   ```

2. **Time window too strict**
   ```python
   # Default allows 1 period drift (30 seconds each way)
   TOTP_VALID_WINDOW = 1  # Increase to 2 for more tolerance
   ```

3. **Secret encoding**
   ```python
   # Verify secret is properly base32 encoded
   import pyotp
   totp = pyotp.TOTP(user.mfa_secret)
   print(f"Current code: {totp.now()}")
   ```

### Issue: MFA recovery codes not working

**Symptoms:**
- Recovery code rejected
- "Invalid recovery code" error

**Solutions:**

1. **Code already used**
   ```python
   # Recovery codes are single-use
   # Check if code was previously consumed
   from app.services.mfa_service import MFAService

   codes = await mfa_service.get_remaining_recovery_codes(user_id)
   print(f"Remaining codes: {len(codes)}")
   ```

2. **Regenerate recovery codes**
   ```python
   new_codes = await mfa_service.regenerate_recovery_codes(user_id)
   # Returns 10 new single-use codes
   ```

### Issue: SMS not delivered

**Symptoms:**
- SMS verification code never arrives
- "SMS delivery failed" error

**Causes:**

1. **Invalid phone format**
   ```python
   # Phone must be E.164 format
   # +1234567890 (correct)
   # 1234567890 (incorrect)
   import phonenumbers
   parsed = phonenumbers.parse(phone, "US")
   formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
   ```

2. **SMS provider issues**
   ```bash
   # Check Twilio/provider status
   curl https://status.twilio.com/api/v2/status.json
   ```

3. **Rate limiting by provider**
   ```env
   SMS_RATE_LIMIT_PER_PHONE=3   # Max SMS per phone per hour
   SMS_RATE_LIMIT_GLOBAL=100     # Max SMS per hour total
   ```

---

## WebAuthn/Passkeys Issues

### Issue: Registration fails

**Symptoms:**
- `WebAuthnError: The operation either timed out or was not allowed`
- Passkey not created

**Causes & Solutions:**

1. **Origin mismatch**
   ```env
   # Origin must match exactly
   WEBAUTHN_RP_ID=your-domain.com
   WEBAUTHN_RP_ORIGIN=https://your-domain.com
   # Do NOT include port unless necessary
   ```

2. **User verification required but unavailable**
   ```python
   # If device doesn't support user verification
   WEBAUTHN_USER_VERIFICATION = "preferred"  # Not "required"
   ```

3. **Authenticator not supported**
   ```javascript
   // Check browser support
   if (window.PublicKeyCredential) {
     console.log("WebAuthn supported");

     // Check platform authenticator
     const available = await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable();
     console.log(`Platform authenticator: ${available}`);
   }
   ```

### Issue: Authentication fails

**Symptoms:**
- "Passkey not found"
- "Credential not recognized"

**Solutions:**

1. **Multiple domains**
   ```env
   # RP ID must be same for registration and auth
   WEBAUTHN_RP_ID=yourdomain.com
   # Works for: auth.yourdomain.com, www.yourdomain.com
   # Does NOT work for: different-domain.com
   ```

2. **Credential deleted from authenticator**
   ```python
   # Remove orphaned credentials
   await webauthn_service.remove_credential(user_id, credential_id)

   # Re-register new passkey
   options = await webauthn_service.generate_registration_options(user_id)
   ```

3. **Counter mismatch (cloned authenticator)**
   ```python
   # If counter goes backwards, possible credential clone
   # Janua blocks this by default for security
   WEBAUTHN_STRICT_COUNTER = true  # Set to false only for debugging
   ```

---

## SDK Integration Issues

### Issue: "Network error" or connection timeout

**Symptoms:**
- SDK methods fail with network errors
- Requests never reach server

**Solutions:**

1. **CORS configuration**
   ```python
   # In FastAPI app
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://your-app.com"],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

2. **Base URL configuration**
   ```typescript
   // Correct
   const client = new JanuaClient({
     baseUrl: 'https://api.janua.dev',  // No trailing slash
   });

   // Incorrect
   const client = new JanuaClient({
     baseUrl: 'https://api.janua.dev/',  // Trailing slash causes issues
   });
   ```

3. **Proxy/firewall issues**
   ```bash
   # Test connectivity
   curl -v https://api.janua.dev/health
   ```

### Issue: TypeScript type errors

**Symptoms:**
- IDE shows type errors
- Build fails with type mismatches

**Common Fixes:**

1. **Event handler signatures**
   ```typescript
   // Wrong - old signature
   januaClient.on('signIn', (user: User) => {});

   // Correct - payload wrapper
   januaClient.on('auth:signedIn', ({ user }: { user: User }) => {});
   ```

2. **Token storage type**
   ```typescript
   // Add const assertion
   tokenStorage: {
     type: 'localStorage' as const,  // Required!
     key: 'janua_auth',
   }
   ```

3. **SDK version mismatch**
   ```bash
   # Update to latest
   npm update @janua/typescript-sdk @janua/react-sdk

   # Or specific version
   npm install @janua/typescript-sdk@1.2.0
   ```

### Issue: React hooks not working

**Symptoms:**
- `useAuth()` returns undefined
- Provider errors

**Solutions:**

1. **Provider not at root**
   ```tsx
   // Must wrap entire app
   function App() {
     return (
       <JanuaProvider config={config}>
         <Router>
           <YourApp />
         </Router>
       </JanuaProvider>
     );
   }
   ```

2. **Circular dependency**
   ```tsx
   // Don't use hooks in config file
   // Separate config from component logic
   ```

---

## Email Issues

### Issue: Emails not sending

**Symptoms:**
- Verification emails not received
- No errors in logs but email never arrives

**Diagnostic Steps:**

```bash
# Check SMTP connection
python3 -c "
import smtplib
server = smtplib.SMTP('$SMTP_HOST', $SMTP_PORT)
server.starttls()
server.login('$SMTP_USER', '$SMTP_PASSWORD')
print('SMTP connection successful')
server.quit()
"
```

**Solutions:**

1. **Check spam folder**
   - Many emails go to spam initially
   - Add SPF/DKIM/DMARC records

2. **SMTP configuration**
   ```env
   SMTP_HOST=smtp.sendgrid.net
   SMTP_PORT=587
   SMTP_USER=apikey
   SMTP_PASSWORD=your-sendgrid-api-key
   SMTP_FROM=noreply@yourdomain.com
   SMTP_TLS=true
   ```

3. **Email rate limiting**
   ```env
   EMAIL_RATE_LIMIT_PER_USER=5    # Per hour
   EMAIL_RATE_LIMIT_GLOBAL=1000   # Per hour total
   ```

### Issue: Email links expired or invalid

**Symptoms:**
- "Link expired" when clicking verification
- "Invalid token" errors

**Solutions:**

1. **Increase token expiry**
   ```env
   EMAIL_VERIFICATION_EXPIRE_HOURS=48  # Default: 24
   PASSWORD_RESET_EXPIRE_HOURS=2       # Default: 1
   ```

2. **Check base URL**
   ```env
   # Must match where links are clicked
   APP_BASE_URL=https://your-app.com
   ```

---

## Performance Problems

### Issue: Slow API responses

**Symptoms:**
- High latency (>500ms)
- Timeouts on requests

**Diagnostic Steps:**

```bash
# Enable request timing
curl -w "@-" -o /dev/null -s "https://api.janua.dev/api/v1/users/me" <<'EOF'
    time_namelookup:  %{time_namelookup}\n
       time_connect:  %{time_connect}\n
    time_appconnect:  %{time_appconnect}\n
   time_pretransfer:  %{time_pretransfer}\n
      time_redirect:  %{time_redirect}\n
 time_starttransfer:  %{time_starttransfer}\n
                    ----------\n
         time_total:  %{time_total}\n
EOF
```

**Solutions:**

1. **Enable caching**
   ```env
   CACHE_ENABLED=true
   CACHE_DEFAULT_TTL=300
   ```

2. **Optimize database queries**
   ```python
   # Check slow queries
   SQLALCHEMY_ECHO=true  # Logs all queries
   SLOW_QUERY_THRESHOLD=100  # Log queries >100ms
   ```

3. **Use connection pooling**
   ```env
   DATABASE_POOL_SIZE=20
   DATABASE_POOL_OVERFLOW=10
   ```

4. **Add database indexes**
   ```sql
   -- Check missing indexes
   SELECT * FROM pg_stat_user_indexes WHERE idx_scan = 0;

   -- Add common indexes
   CREATE INDEX idx_users_email ON users(email);
   CREATE INDEX idx_sessions_user_id ON sessions(user_id);
   ```

### Issue: High memory usage

**Symptoms:**
- OOM kills
- Container restarts

**Solutions:**

1. **Limit worker processes**
   ```bash
   # Uvicorn with controlled workers
   uvicorn app.main:app --workers 4 --limit-concurrency 100
   ```

2. **Optimize query patterns**
   ```python
   # Use pagination instead of loading all
   users = await session.query(User).limit(100).offset(page * 100)

   # Use streaming for large exports
   async for user in session.stream(select(User)):
       yield user
   ```

---

## Deployment Issues

### Issue: Container won't start

**Symptoms:**
- CrashLoopBackOff in Kubernetes
- Exit code 1

**Diagnostic Steps:**

```bash
# Check pod logs
kubectl logs pod/janua-api-xxx -n janua

# Check events
kubectl describe pod/janua-api-xxx -n janua

# Check resource limits
kubectl top pod -n janua
```

**Common Causes:**

1. **Missing environment variables**
   ```bash
   # Required variables
   DATABASE_URL
   REDIS_URL
   JWT_SECRET_KEY (or JWT_PRIVATE_KEY_PATH)
   ```

2. **Database not ready**
   ```yaml
   # Add init container
   initContainers:
   - name: wait-for-db
     image: busybox
     command: ['sh', '-c', 'until nc -z postgres 5432; do sleep 1; done']
   ```

3. **Resource limits too low**
   ```yaml
   resources:
     requests:
       memory: "256Mi"
       cpu: "100m"
     limits:
       memory: "512Mi"
       cpu: "500m"
   ```

### Issue: Cloudflare Tunnel not connecting

**Symptoms:**
- Site unreachable
- `cloudflared` pod errors

**Solutions:**

1. **Check tunnel credentials**
   ```bash
   # Verify secret exists
   kubectl get secret tunnel-credentials -n cloudflare-tunnel

   # Check tunnel status
   cloudflared tunnel info <tunnel-id>
   ```

2. **Verify ingress rules**
   ```yaml
   # In cloudflared config
   ingress:
     - hostname: api.janua.dev
       service: http://janua-api.janua.svc.cluster.local:4100
     - service: http_status:404
   ```

---

## Debugging Techniques

### Enable Debug Logging

```env
# Full debug output
DEBUG=true
LOG_LEVEL=DEBUG

# SQL query logging
SQLALCHEMY_ECHO=true

# Request/response logging
LOG_REQUEST_BODY=true
LOG_RESPONSE_BODY=true
```

### Structured Log Queries

```bash
# Search for errors
kubectl logs -n janua -l app=janua-api | grep '"level":"error"'

# Search by request ID
kubectl logs -n janua -l app=janua-api | grep "request_id.*abc123"

# Filter by user
kubectl logs -n janua -l app=janua-api | grep "user_id.*user-uuid"
```

### Database Debugging

```sql
-- Active connections
SELECT pid, usename, application_name, client_addr, state, query
FROM pg_stat_activity
WHERE datname = 'janua';

-- Lock issues
SELECT blocked.pid AS blocked_pid,
       blocked.query AS blocked_query,
       blocking.pid AS blocking_pid,
       blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking ON blocking.pid = ANY(pg_blocking_pids(blocked.pid));

-- Table sizes
SELECT relname AS table_name,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

### Redis Debugging

```bash
# Monitor commands in real-time
redis-cli MONITOR

# Check key count
redis-cli DBSIZE

# Find large keys
redis-cli --bigkeys

# Memory analysis
redis-cli MEMORY DOCTOR
```

### Network Debugging

```bash
# Test internal connectivity
kubectl exec -it pod/janua-api-xxx -n janua -- curl postgres:5432 -v

# DNS resolution
kubectl exec -it pod/janua-api-xxx -n janua -- nslookup postgres.janua.svc.cluster.local

# Trace route
kubectl exec -it pod/janua-api-xxx -n janua -- traceroute api.janua.dev
```

---

## Getting Help

### Collecting Diagnostic Information

When reporting issues, include:

```bash
# System info
uname -a
python --version
psql --version

# Janua version
curl https://api.janua.dev/health | jq .version

# Error logs (sanitized)
kubectl logs -n janua -l app=janua-api --tail=100 > janua-logs.txt

# Configuration (remove secrets!)
env | grep -E "^(JANUA|DATABASE|REDIS|JWT)" | sed 's/=.*/=REDACTED/'
```

### Support Channels

- **GitHub Issues**: [github.com/madfam-org/janua/issues](https://github.com/madfam-org/janua/issues)
- **Documentation**: [docs.janua.dev](https://docs.janua.dev)
- **Security Issues**: security@janua.dev

---

## Related Documentation

- [Security Checklist](./SECURITY_CHECKLIST.md)
- [Performance Tuning Guide](./PERFORMANCE_TUNING_GUIDE.md)
- [API Reference](../api/)
- [FAQ](../../apps/api/docs/FAQ.md)

---

*Last updated: January 2026*
*Janua v1.0.0*
