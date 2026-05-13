# Stripe API Key & Webhook Secret Rotation

> [!IMPORTANT]
> MADFAM-ENCLII-FIRST-LEGACY-RAW v1: This document contains legacy raw infrastructure command examples.
> Routine production operations must use Enclii web, API, or CLI. Treat raw
> `kubectl`, `helm`, SSH, provider CLI/API, `docker exec`, and direct container
> access as platform bootstrap or documented break-glass only, and record any
> missing Enclii adapter gap.


## Overview

This runbook covers rotating Stripe API keys and webhook secrets used for payment processing.

**Secrets:**
| Secret ID | Key | Location |
|-----------|-----|----------|
| `janua-stripe-secret-key` | `STRIPE_SECRET_KEY` | `k8s/janua-secrets` |
| `janua-stripe-webhook-secret` | `STRIPE_WEBHOOK_SECRET` | `k8s/janua-secrets` |
| `janua-stripe-publishable-key` | `STRIPE_PUBLISHABLE_KEY` | `k8s/janua-configmap` |

**Policy:** Annual rotation
**Owner:** Security Team
**Risk Level:** CRITICAL - Payment processing

## Prerequisites

- Access to Stripe Dashboard with API key management permissions
- `kubectl` access to the janua namespace
- Understanding of Stripe's key rolling mechanism

## Pre-Rotation Checklist

- [ ] **Schedule during low-traffic period** (critical for payment systems)
- [ ] Notify finance and support teams
- [ ] Verify current payment flows are working
- [ ] Have Stripe support contact ready
- [ ] Prepare rollback plan

## Part 1: Rotate API Secret Key

### Step 1: Roll Key in Stripe Dashboard

Stripe supports rolling keys with a grace period:

1. Navigate to [Stripe Dashboard - API Keys](https://dashboard.stripe.com/apikeys)
2. Ensure you're in **Live mode** (toggle in top-left)
3. Find the "Secret key" row
4. Click **"Roll key..."**
5. Set expiration for old key: **24 hours** (recommended)
6. Click **"Roll API key"**
7. Copy the new secret key (starts with `sk_live_`)

### Step 2: Update Kubernetes Secret

```bash
# Set the new secret key
NEW_KEY="sk_live_PASTE_NEW_KEY_HERE"

# Encode and update
kubectl patch secret janua-secrets -n janua --type='json' \
  -p="[{\"op\": \"replace\", \"path\": \"/data/stripe-secret-key\", \"value\":\"$(echo -n $NEW_KEY | base64)\"}]"
```

### Step 3: Rolling Restart

```bash
# Restart API and billing services
kubectl rollout restart deployment/janua-api -n janua
kubectl rollout restart deployment/janua-billing -n janua 2>/dev/null || true

# Wait for rollout
kubectl rollout status deployment/janua-api -n janua --timeout=180s
```

### Step 4: Verification

```bash
# Check for Stripe API errors
kubectl logs -n janua -l app=janua-api --since=5m | grep -i "stripe"

# Check for payment errors
kubectl logs -n janua -l app=janua-api --since=5m | grep -i "payment\|charge\|subscription"
```

**Critical Verification:**
1. Test a small transaction in production (if possible) or verify recent transactions succeed
2. Check Stripe Dashboard → Developers → Logs for successful API calls
3. Verify subscription renewals are processing

### Step 5: Monitor Grace Period

The old key remains valid for 24 hours. Monitor:
- Stripe Dashboard → Developers → Logs for calls using old key
- Any third-party integrations using the old key

After 24 hours, the old key automatically expires.

## Part 2: Rotate Webhook Secret

### Step 1: Create New Webhook Endpoint (or Regenerate Secret)

**Option A: Regenerate existing webhook secret**

1. Go to [Stripe Dashboard - Webhooks](https://dashboard.stripe.com/webhooks)
2. Click on the production webhook endpoint
3. Click **"Reveal"** next to the signing secret, note it for rollback
4. Click **"Roll secret..."**
5. Copy the new signing secret (starts with `whsec_`)

**Option B: Create new endpoint (cleaner but more disruptive)**

1. Create new webhook endpoint with same URL
2. Configure same events
3. Use new signing secret
4. After verification, delete old endpoint

### Step 2: Update Kubernetes Secret

```bash
# Set the new webhook secret
NEW_WEBHOOK="whsec_PASTE_NEW_SECRET_HERE"

# Encode and update
kubectl patch secret janua-secrets -n janua --type='json' \
  -p="[{\"op\": \"replace\", \"path\": \"/data/stripe-webhook-secret\", \"value\":\"$(echo -n $NEW_WEBHOOK | base64)\"}]"

# Restart to pick up new secret
kubectl rollout restart deployment/janua-api -n janua
```

### Step 3: Verify Webhook Delivery

1. Go to Stripe Dashboard → Developers → Webhooks
2. Click on the endpoint
3. Check "Recent deliveries" for successful 200 responses
4. Look for any signature verification failures

```bash
# Check for webhook signature errors
kubectl logs -n janua -l app=janua-api --since=10m | grep -i "webhook\|signature"
```

## Part 3: Rotate Publishable Key (Optional)

The publishable key is public and doesn't need frequent rotation, but if needed:

### Step 1: Roll Key in Stripe Dashboard

1. Go to API Keys page
2. Roll the publishable key (same process as secret key)

### Step 2: Update ConfigMap

```bash
NEW_PK="pk_live_PASTE_NEW_KEY_HERE"

kubectl patch configmap janua-config -n janua --type='json' \
  -p="[{\"op\": \"replace\", \"path\": \"/data/stripe-publishable-key\", \"value\":\"$NEW_PK\"}]"
```

### Step 3: Redeploy Frontend

```bash
# Frontend services need rebuild with new key
kubectl rollout restart deployment/janua-dashboard -n janua
kubectl rollout restart deployment/janua-website -n janua
```

## Update Registry

Update `infra/secrets/SECRETS_REGISTRY.yaml`:

```yaml
- id: janua-stripe-secret-key
  last_rotated: "YYYY-MM-DD"
  next_rotation: "YYYY-MM-DD"  # +365 days

- id: janua-stripe-webhook-secret
  last_rotated: "YYYY-MM-DD"
  next_rotation: "YYYY-MM-DD"  # +365 days
```

## Rollback Procedure

### API Key Rollback

During the 24-hour grace period:
1. Old key is still valid
2. Retrieve old key from secure backup
3. Revert K8s secret and restart

After grace period expires:
1. Contact Stripe support for emergency key recovery
2. Or roll the new key again to get fresh credentials

### Webhook Secret Rollback

1. Retrieve old webhook secret from backup
2. Revert K8s secret:
   ```bash
   OLD_WEBHOOK="whsec_..."
   kubectl patch secret janua-secrets -n janua --type='json' \
     -p="[{\"op\": \"replace\", \"path\": \"/data/stripe-webhook-secret\", \"value\":\"$(echo -n $OLD_WEBHOOK | base64)\"}]"
   kubectl rollout restart deployment/janua-api -n janua
   ```

## Troubleshooting

### "Invalid API key" errors

- Verify key was copied correctly
- Check you're using live key, not test key
- Ensure no extra whitespace

### Webhook signature verification failures

- Common after webhook secret rotation
- Verify new secret is deployed
- Check webhook endpoint URL is correct
- Ensure no caching of old secret

### Payments failing

1. Check Stripe Dashboard for error details
2. Verify API key permissions (should be full access for backend)
3. Check for rate limiting
4. Contact Stripe support if persistent

### Subscriptions not renewing

- Check webhook delivery logs in Stripe
- Verify `invoice.paid` and `invoice.payment_failed` events are configured
- Review subscription status in Stripe Dashboard

## Security Considerations

- **Never log** Stripe secret keys
- **Never commit** keys to version control
- Use **restricted keys** if possible for limited-scope operations
- Enable **two-factor authentication** on Stripe account
- Set up **Stripe Radar** for fraud detection

## Emergency Contacts

- Stripe Support: https://support.stripe.com (24/7 for critical payment issues)
- Stripe Status: https://status.stripe.com

## Related Documents

- [SECRETS_REGISTRY.yaml](../../../infra/secrets/SECRETS_REGISTRY.yaml)
- [EMERGENCY_ROTATION.md](./EMERGENCY_ROTATION.md)
- [Stripe API Key Rolling](https://stripe.com/docs/keys#rolling-keys)
- [Stripe Webhook Signatures](https://stripe.com/docs/webhooks/signatures)

---

**Last Updated:** 2026-01-16
**Review Frequency:** Annual
**CRITICAL:** Schedule during low-traffic periods only
