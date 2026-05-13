# GitHub OAuth Client Secret Rotation

> [!IMPORTANT]
> MADFAM-ENCLII-FIRST-LEGACY-RAW v1: This document contains legacy raw infrastructure command examples.
> Routine production operations must use Enclii web, API, or CLI. Treat raw
> `kubectl`, `helm`, SSH, provider CLI/API, `docker exec`, and direct container
> access as platform bootstrap or documented break-glass only, and record any
> missing Enclii adapter gap.


## Overview

This runbook covers rotating the GitHub OAuth App client secret used for "Sign in with GitHub" functionality.

**Secret ID:** `janua-oauth-github-secret`
**Location:** `k8s/janua-secrets` → `GITHUB_CLIENT_SECRET`
**Policy:** Annual rotation
**Owner:** Security Team

## Prerequisites

- Access to GitHub organization settings with OAuth App management permissions
- `kubectl` access to the janua namespace
- Knowledge of the current OAuth App client ID

## Pre-Rotation Checklist

- [ ] Schedule rotation during low-traffic period
- [ ] Notify team of planned authentication changes
- [ ] Verify you have GitHub organization admin access
- [ ] Confirm OAuth App client ID matches production

## Rotation Steps

### Step 1: Generate New Secret in GitHub

1. Navigate to [GitHub Developer Settings](https://github.com/settings/developers) or Organization Settings → Developer Settings
2. Click on **OAuth Apps**
3. Select the Janua production OAuth App
4. In the "Client secrets" section, click **"Generate a new client secret"**
5. Copy the newly generated secret value immediately (it won't be shown again)
6. **DO NOT revoke the old secret yet**

### Step 2: Update Kubernetes Secret

```bash
# Set the new secret value
NEW_SECRET="PASTE_NEW_SECRET_HERE"

# Encode and update
kubectl patch secret janua-secrets -n janua --type='json' \
  -p="[{\"op\": \"replace\", \"path\": \"/data/github-client-secret\", \"value\":\"$(echo -n $NEW_SECRET | base64)\"}]"
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
kubectl logs -n janua -l app=janua-api --since=5m | grep -i "github\|oauth"

# Verify no authentication errors
kubectl logs -n janua -l app=janua-api --since=5m | grep -i "error" | head -10
```

**Manual Verification:**
1. Open an incognito browser window
2. Navigate to https://janua.io/login
3. Click "Sign in with GitHub"
4. Complete OAuth flow (authorize if prompted)
5. Verify successful login

### Step 5: Revoke Old Secret

After verifying the new secret works (wait at least 1 hour):

1. Return to GitHub OAuth App settings
2. Find the old client secret (older creation date)
3. Click **"Delete"** next to the old secret
4. Confirm deletion

### Step 6: Update Registry

Update `infra/secrets/SECRETS_REGISTRY.yaml`:

```yaml
- id: janua-oauth-github-secret
  last_rotated: "YYYY-MM-DD"  # Today's date
  next_rotation: "YYYY-MM-DD"  # +365 days
```

Commit and push the registry update.

## Rollback Procedure

If the new secret doesn't work:

1. The old secret is still active in GitHub (if not deleted)
2. Retrieve old secret from backup or password manager
3. Revert K8s secret:
   ```bash
   OLD_SECRET="..."
   kubectl patch secret janua-secrets -n janua --type='json' \
     -p="[{\"op\": \"replace\", \"path\": \"/data/github-client-secret\", \"value\":\"$(echo -n $OLD_SECRET | base64)\"}]"
   kubectl rollout restart deployment/janua-api -n janua
   ```
4. Investigate root cause before re-attempting

## Troubleshooting

### "Bad credentials" or "Invalid client secret"

- Verify the secret was copied correctly (no extra whitespace)
- Confirm you're editing the correct OAuth App
- Check the client ID matches what's configured in Janua

### OAuth flow shows "Application suspended"

- Check OAuth App status in GitHub settings
- Verify app hasn't been flagged for policy violations
- Contact GitHub support if needed

### "Redirect URI mismatch"

- Verify callback URLs are configured correctly in GitHub OAuth App settings
- Should include: `https://janua.io/api/auth/callback/github`

## GitHub OAuth App vs GitHub App

**Important:** This runbook is for **OAuth Apps**, not **GitHub Apps**. They have different authentication mechanisms:

- OAuth Apps: Used for user authentication ("Sign in with GitHub")
- GitHub Apps: Used for repository/organization integrations

Verify you're modifying the correct application type.

## Related Documents

- [SECRETS_REGISTRY.yaml](../../../infra/secrets/SECRETS_REGISTRY.yaml)
- [EMERGENCY_ROTATION.md](./EMERGENCY_ROTATION.md)
- [GHCR PAT Rotation](./ghcr-pat-rotation.md) - For container registry tokens
- [GitHub OAuth Documentation](https://docs.github.com/en/developers/apps/building-oauth-apps)

---

**Last Updated:** 2026-01-16
**Review Frequency:** Annual
