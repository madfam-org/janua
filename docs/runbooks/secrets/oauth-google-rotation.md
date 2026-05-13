# Google OAuth Client Secret Rotation

> [!IMPORTANT]
> MADFAM-ENCLII-FIRST-LEGACY-RAW v1: This document contains legacy raw infrastructure command examples.
> Routine production operations must use Enclii web, API, or CLI. Treat raw
> `kubectl`, `helm`, SSH, provider CLI/API, `docker exec`, and direct container
> access as platform bootstrap or documented break-glass only, and record any
> missing Enclii adapter gap.


## Overview

This runbook covers rotating the Google OAuth 2.0 client secret used for "Sign in with Google" functionality.

**Secret ID:** `janua-oauth-google-secret`
**Location:** `k8s/janua-secrets` → `GOOGLE_CLIENT_SECRET`
**Policy:** Annual rotation
**Owner:** Security Team

## Prerequisites

- Access to Google Cloud Console with OAuth client management permissions
- `kubectl` access to the janua namespace
- Knowledge of the current OAuth client ID

## Pre-Rotation Checklist

- [ ] Schedule rotation during low-traffic period
- [ ] Notify team of planned authentication changes
- [ ] Verify you have Google Cloud Console access
- [ ] Confirm OAuth client ID matches production

## Rotation Steps

### Step 1: Generate New Secret in Google Cloud Console

1. Navigate to [Google Cloud Console - Credentials](https://console.cloud.google.com/apis/credentials)
2. Select the correct project (Janua Production)
3. Find the OAuth 2.0 Client ID for web application
4. Click on the client name to open details
5. In the "Client secrets" section, click **"ADD SECRET"**
6. Copy the newly generated secret value
7. **DO NOT delete the old secret yet**

### Step 2: Update Kubernetes Secret

```bash
# Set the new secret value
NEW_SECRET="PASTE_NEW_SECRET_HERE"

# Encode and update
kubectl patch secret janua-secrets -n janua --type='json' \
  -p="[{\"op\": \"replace\", \"path\": \"/data/google-client-secret\", \"value\":\"$(echo -n $NEW_SECRET | base64)\"}]"
```

### Step 3: Rolling Restart

```bash
# Restart API to pick up new secret
kubectl rollout restart deployment/janua-api -n janua

# Wait for rollout
kubectl rollout status deployment/janua-api -n janua --timeout=180s
```

### Step 4: Verification

```bash
# Check API logs for OAuth errors
kubectl logs -n janua -l app=janua-api --since=5m | grep -i "google\|oauth"

# Verify no authentication errors
kubectl logs -n janua -l app=janua-api --since=5m | grep -i "error" | head -10
```

**Manual Verification:**
1. Open an incognito browser window
2. Navigate to https://janua.io/login
3. Click "Sign in with Google"
4. Complete OAuth flow
5. Verify successful login

### Step 5: Remove Old Secret from Google Console

After verifying the new secret works (wait at least 1 hour):

1. Return to Google Cloud Console - Credentials
2. Open the OAuth client details
3. Find the old secret (older creation date)
4. Click the trash icon to delete it
5. Confirm deletion

### Step 6: Update Registry

Update `infra/secrets/SECRETS_REGISTRY.yaml`:

```yaml
- id: janua-oauth-google-secret
  last_rotated: "YYYY-MM-DD"  # Today's date
  next_rotation: "YYYY-MM-DD"  # +365 days
```

Commit and push the registry update.

## Rollback Procedure

If the new secret doesn't work:

1. The old secret is still active in Google Console
2. Retrieve old secret from backup or password manager
3. Revert K8s secret:
   ```bash
   OLD_SECRET="..."
   kubectl patch secret janua-secrets -n janua --type='json' \
     -p="[{\"op\": \"replace\", \"path\": \"/data/google-client-secret\", \"value\":\"$(echo -n $OLD_SECRET | base64)\"}]"
   kubectl rollout restart deployment/janua-api -n janua
   ```
4. Delete the problematic new secret from Google Console
5. Investigate root cause before re-attempting

## Troubleshooting

### "Invalid client secret" errors

- Verify the secret was copied correctly (no extra whitespace)
- Confirm you're editing the correct OAuth client
- Check the client ID matches what's configured in Janua

### OAuth flow redirects to error page

- Verify redirect URIs are still configured correctly
- Check consent screen settings haven't changed
- Review API enabled status (Google+ API, People API)

### Token refresh failures

- May indicate client secret mismatch
- Check if old refresh tokens are using old secret
- Users may need to re-authenticate

## Related Documents

- [SECRETS_REGISTRY.yaml](../../../infra/secrets/SECRETS_REGISTRY.yaml)
- [EMERGENCY_ROTATION.md](./EMERGENCY_ROTATION.md)
- [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2)

---

**Last Updated:** 2026-01-16
**Review Frequency:** Annual
