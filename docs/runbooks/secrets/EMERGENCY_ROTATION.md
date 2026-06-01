# Emergency Secret Rotation Runbook

> [!IMPORTANT]
> MADFAM-ENCLII-FIRST-LEGACY-RAW v1: This document contains legacy raw infrastructure command examples.
> Routine production operations must use Enclii web, API, or CLI. Treat raw
> `kubectl`, `helm`, SSH, provider CLI/API, `docker exec`, and direct container
> access as platform bootstrap or documented break-glass only, and record any
> missing Enclii adapter gap.


## Overview

This runbook covers emergency procedures for rotating secrets when a security incident is suspected or confirmed. Use these procedures when:

- A secret may have been compromised
- An employee with secret access has departed
- A security incident requires immediate credential rotation
- Abnormal activity is detected in logs or monitoring

## Severity Levels

| Level | Description | Secrets Affected | Response Time |
|-------|-------------|------------------|---------------|
| **CRITICAL** | Active breach, confirmed compromise | JWT keys, DB passwords, payment keys | **Immediate** (< 15 min) |
| **HIGH** | Suspected compromise, departed employee | OAuth secrets, registry creds, API keys | **4 hours** |
| **MEDIUM** | Precautionary rotation, policy compliance | Monitoring tokens, non-prod secrets | **24 hours** |

## Emergency Response Team

| Role | Responsibility | Contact Method |
|------|----------------|----------------|
| Security Lead | Incident command, decision authority | Slack: #security-oncall |
| Infrastructure Lead | Execution of rotation scripts | Slack: #infra-oncall |
| Development Lead | Application-level verification | Slack: #dev-oncall |

## Pre-Rotation Checklist

Before rotating any secret in an emergency:

- [ ] Document the incident in the security incident log
- [ ] Identify all affected systems and dependencies
- [ ] Notify on-call personnel via appropriate channels
- [ ] Prepare rollback plan if rotation fails
- [ ] Ensure you have cluster access and necessary permissions

## CRITICAL Severity: Immediate Actions

### 1. JWT Key Compromise

**Signs of Compromise:**
- Unauthorized access with valid JWT tokens
- Unusual token generation patterns
- Tokens appearing from unexpected sources

**Immediate Actions:**

```bash
# 1. Rotate JWT keys immediately (no dry-run in emergency)
./scripts/secrets/rotate-jwt-keys.sh --project janua

# 2. Monitor authentication logs
kubectl logs -n janua -l app=janua-api --since=5m | grep -i "auth\|jwt\|token"

# 3. Force token refresh for all sessions (if application supports)
kubectl exec -n janua deploy/janua-api -- npm run invalidate-sessions

# 4. After 24h grace period, cleanup old keys
./scripts/secrets/rotate-jwt-keys.sh --project janua --cleanup
```

**Verification:**
```bash
# Check API is responding
curl -s https://api.janua.io/health | jq .

# Verify new tokens are being issued
kubectl logs -n janua -l app=janua-api --since=2m | grep "token issued"
```

### 2. Database Password Compromise

**Signs of Compromise:**
- Unauthorized database queries in logs
- Unexpected data access patterns
- Database connection from unknown IPs

**Immediate Actions:**

```bash
# 1. Rotate database password
./scripts/secrets/rotate-db-password.sh --project janua

# 2. Check for active suspicious connections
kubectl exec -n janua janua-postgres-0 -- psql -U postgres -c \
  "SELECT pid, usename, client_addr, state, query FROM pg_stat_activity;"

# 3. Terminate suspicious connections if needed
kubectl exec -n janua janua-postgres-0 -- psql -U postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE client_addr = 'SUSPICIOUS_IP';"

# 4. Review connection logs
kubectl logs -n janua janua-postgres-0 --since=1h | grep -i "connection\|auth"
```

### 3. Payment Key Compromise (Stripe)

**Signs of Compromise:**
- Unauthorized transactions
- API calls from unknown IPs in Stripe dashboard
- Webhook signature validation failures

**Immediate Actions:**

1. **Revoke in Stripe Dashboard immediately:**
   - Go to https://dashboard.stripe.com/apikeys
   - Roll the compromised key (creates new key instantly)
   - Note the new key value

2. **Update Kubernetes secret:**
   ```bash
   # Encode new key
   NEW_KEY="DUMMY_STRIPE_LIVE_KEY_DO_NOT_USE"
   ENCODED=$(echo -n "$NEW_KEY" | base64)

   # Update secret
   kubectl patch secret janua-secrets -n janua --type='json' \
     -p="[{\"op\": \"replace\", \"path\": \"/data/stripe-secret-key\", \"value\":\"$ENCODED\"}]"

   # Restart API
   kubectl rollout restart deployment/janua-api -n janua
   ```

3. **Update webhook secret if needed:**
   - Regenerate in Stripe Dashboard → Webhooks
   - Update `stripe-webhook-secret` in K8s

4. **Review recent transactions:**
   - Check Stripe Dashboard for unauthorized activity
   - Review webhook delivery logs

## HIGH Severity: 4-Hour Response

### Employee Departure Rotation

When an employee with secret access departs:

```bash
# 1. Identify secrets the employee had access to
# Review access logs and permission records

# 2. Rotate affected secrets based on access level
./scripts/secrets/rotate-db-password.sh --project janua  # If DB access
./scripts/secrets/rotate-jwt-keys.sh --project janua     # If signing key access

# 3. Rotate OAuth secrets if they had provider access
# Follow OAuth rotation runbooks for each provider

# 4. Update GHCR credentials if they had GitHub access
./scripts/secrets/rotate-ghcr-credentials.sh --project janua
```

### OAuth Secret Rotation

For each OAuth provider the employee had access to:

1. Rotate in provider's developer console
2. Update Kubernetes secret
3. Verify login flow works
4. Update SECRETS_REGISTRY.yaml

See individual OAuth runbooks for provider-specific steps.

## Emergency Scripts

### Rotate All Critical Secrets

**Script:** `scripts/secrets/emergency-rotate-all.sh`

```bash
#!/bin/bash
# Emergency rotation of all critical secrets
# USE WITH CAUTION - this will cause service disruption

set -euo pipefail

PROJECT="${1:-janua}"
CONFIRM="${2:-}"

if [[ "$CONFIRM" != "--confirm" ]]; then
    echo "This will rotate ALL critical secrets for $PROJECT"
    echo "Services will experience disruption during rotation"
    echo ""
    echo "Run with --confirm to proceed:"
    echo "  $0 $PROJECT --confirm"
    exit 1
fi

echo "Starting emergency rotation for $PROJECT..."

# Rotate JWT keys
echo "=== Rotating JWT keys ==="
./scripts/secrets/rotate-jwt-keys.sh --project "$PROJECT"

# Rotate database password
echo "=== Rotating database password ==="
./scripts/secrets/rotate-db-password.sh --project "$PROJECT"

# Note: Payment keys and OAuth secrets require manual rotation
echo ""
echo "=== Manual Actions Required ==="
echo "1. Rotate Stripe keys in dashboard.stripe.com"
echo "2. Rotate OAuth secrets in each provider's console"
echo "3. Update SECRETS_REGISTRY.yaml with new rotation dates"
echo ""
echo "Emergency rotation complete. Verify all services are operational."
```

### Single Secret Emergency Rotation

```bash
# Rotate a specific secret by ID
./scripts/secrets/rotate-secret.sh --id janua-jwt-private-key --emergency

# The --emergency flag:
# - Skips confirmation prompts
# - Logs to security incident log
# - Sends immediate notifications
```

## Post-Rotation Verification

### Service Health Checks

```bash
# Check all deployments are ready
kubectl get deployments -n janua

# Verify API health
curl -s https://api.janua.io/health | jq .

# Check for authentication errors in last 5 minutes
kubectl logs -n janua -l app=janua-api --since=5m | grep -i "error\|fail" | head -20

# Verify database connectivity
kubectl exec -n janua deploy/janua-api -- npm run db:check
```

### Authentication Flow Verification

```bash
# Test OAuth flows (manual)
# 1. Clear browser cookies
# 2. Attempt login with each OAuth provider
# 3. Verify token refresh works
# 4. Test API access with new token
```

### Monitoring Checks

- [ ] Check Grafana dashboards for error spikes
- [ ] Review Sentry for new error types
- [ ] Verify metrics are being collected
- [ ] Check alert status in PagerDuty/OpsGenie

## Documentation Requirements

After emergency rotation, document:

1. **Incident Report**
   - What triggered the emergency
   - Timeline of actions taken
   - Secrets rotated
   - Services affected
   - Duration of any downtime

2. **Registry Update**
   - Update SECRETS_REGISTRY.yaml
   - Set accurate last_rotated dates
   - Calculate new next_rotation dates

3. **Lessons Learned**
   - What could prevent recurrence
   - Process improvements identified
   - Automation opportunities

## Recovery from Failed Rotation

If rotation fails mid-process:

### Database Password Recovery

```bash
# If K8s secret updated but DB not:
# Get the old password from K8s backup or password manager
OLD_PASS="..."

# Revert K8s secret
kubectl patch secret janua-secrets -n janua --type='json' \
  -p="[{\"op\": \"replace\", \"path\": \"/data/database-password\", \"value\":\"$(echo -n $OLD_PASS | base64)\"}]"

# Restart pods
kubectl rollout restart deployment/janua-api -n janua
```

### JWT Key Recovery

```bash
# If -old keys exist, they're still valid
# Check current state:
kubectl get secret janua-secrets -n janua -o jsonpath='{.data}' | jq 'keys'

# If new keys are problematic, swap back to old:
# (Requires manual extraction and re-encoding of old keys)
```

## Emergency Contacts

| Service | Contact | SLA |
|---------|---------|-----|
| Stripe Support | https://support.stripe.com | 24/7 for critical |
| Google OAuth | https://console.cloud.google.com/support | Business hours |
| GitHub Support | https://support.github.com | 24/7 for Enterprise |
| Cloudflare | https://support.cloudflare.com | 24/7 |

## Related Documents

- [SECRETS_REGISTRY.yaml](../../../infra/secrets/SECRETS_REGISTRY.yaml) - Central secrets inventory
- [JWT Key Rotation](./jwt-key-rotation.md) - Standard JWT rotation procedure
- [Database Password Rotation](./db-password-rotation.md) - Standard DB rotation procedure
- [OAuth Rotation Runbooks](./oauth-*.md) - Provider-specific OAuth procedures

---

**Last Updated:** 2026-01-16
**Review Frequency:** Quarterly
**Owner:** Security Team
