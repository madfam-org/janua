# GHCR (GitHub Container Registry) PAT Rotation

> [!IMPORTANT]
> MADFAM-ENCLII-FIRST-LEGACY-RAW v1: This document contains legacy raw infrastructure command examples.
> Routine production operations must use Enclii web, API, or CLI. Treat raw
> `kubectl`, `helm`, SSH, provider CLI/API, `docker exec`, and direct container
> access as platform bootstrap or documented break-glass only, and record any
> missing Enclii adapter gap.


## Overview

This runbook covers rotating the GitHub Personal Access Token used to pull container images from GitHub Container Registry (ghcr.io).

**Secrets:**
| Secret ID | Project | Location |
|-----------|---------|----------|
| `janua-ghcr-credentials` | Janua | `k8s/imagepullsecret` |
| `enclii-ghcr-credentials` | Enclii | `k8s/imagepullsecret` |

**Policy:** Annual rotation
**Owner:** DevOps Team
**Note:** Cross-project - same PAT may be used for both projects

## Prerequisites

- GitHub account with access to the container packages
- Permission to create Fine-grained Personal Access Tokens
- `kubectl` access to both janua and enclii namespaces

## Pre-Rotation Checklist

- [ ] Coordinate with both Janua and Enclii teams
- [ ] Schedule during non-deployment window
- [ ] Verify current image pull is working
- [ ] Document which repositories the token needs access to

## Token Requirements

The PAT needs the following permissions:
- **Repository access:** All repositories (or specific ones containing packages)
- **Permissions:**
  - `read:packages` - Required for pulling images

For Fine-grained PAT (recommended):
- Resource owner: Your organization
- Repository access: Select repositories with container packages
- Permissions: Packages → Read-only

## Rotation Steps

### Step 1: Generate New Fine-grained PAT

1. Go to [GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens](https://github.com/settings/tokens?type=beta)
2. Click **"Generate new token"**
3. Configure:
   - **Token name:** `ghcr-pull-janua-enclii-YYYY` (include year for tracking)
   - **Expiration:** 1 year (or custom)
   - **Resource owner:** Select your organization
   - **Repository access:** "Only select repositories" → choose repos with packages
   - **Permissions:**
     - Packages: Read-only
4. Click **"Generate token"**
5. **Copy the token immediately** (won't be shown again)

### Step 2: Test Token Locally (Optional but Recommended)

```bash
# Test authentication
echo "TOKEN_HERE" | docker login ghcr.io -u USERNAME --password-stdin

# Test pull
docker pull ghcr.io/your-org/janua-api:latest
```

### Step 3: Update Janua Kubernetes Secret

```bash
# Set credentials
GITHUB_USER="your-github-username"
GITHUB_TOKEN="ghp_xxxxxxxxxxxx"

# Create docker config JSON
DOCKER_CONFIG=$(echo -n "${GITHUB_USER}:${GITHUB_TOKEN}" | base64)
AUTH_JSON="{\"auths\":{\"ghcr.io\":{\"auth\":\"${DOCKER_CONFIG}\"}}}"

# Update secret
kubectl create secret docker-registry ghcr-credentials \
  --docker-server=ghcr.io \
  --docker-username="${GITHUB_USER}" \
  --docker-password="${GITHUB_TOKEN}" \
  -n janua \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Step 4: Verify Janua Deployments

```bash
# Trigger a rollout to test image pull
kubectl rollout restart deployment/janua-api -n janua

# Watch for ImagePullBackOff errors
kubectl get pods -n janua -w

# Check events for pull errors
kubectl get events -n janua --sort-by='.lastTimestamp' | grep -i "pull\|image"
```

### Step 5: Update Enclii Kubernetes Secret

```bash
# Same process for Enclii namespace
kubectl create secret docker-registry ghcr-credentials \
  --docker-server=ghcr.io \
  --docker-username="${GITHUB_USER}" \
  --docker-password="${GITHUB_TOKEN}" \
  -n enclii \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Step 6: Verify Enclii Deployments

```bash
kubectl rollout restart deployment/enclii-api -n enclii
kubectl get pods -n enclii -w
kubectl get events -n enclii --sort-by='.lastTimestamp' | grep -i "pull\|image"
```

### Step 7: Revoke Old Token

After both projects are verified working:

1. Go to GitHub → Settings → Developer settings → Personal access tokens
2. Find the old token (check creation date)
3. Click **"Delete"**
4. Confirm deletion

### Step 8: Update Registry

Update `infra/secrets/SECRETS_REGISTRY.yaml`:

```yaml
- id: janua-ghcr-credentials
  last_rotated: "YYYY-MM-DD"
  next_rotation: "YYYY-MM-DD"  # +365 days

- id: enclii-ghcr-credentials
  last_rotated: "YYYY-MM-DD"
  next_rotation: "YYYY-MM-DD"  # +365 days
```

## Automated Script

**File:** `scripts/secrets/rotate-ghcr-credentials.sh`

```bash
#!/bin/bash
set -euo pipefail

# Usage: ./rotate-ghcr-credentials.sh --user USERNAME --token TOKEN [--namespace janua|enclii|all]

GITHUB_USER=""
GITHUB_TOKEN=""
NAMESPACE="all"

while [[ $# -gt 0 ]]; do
    case $1 in
        --user) GITHUB_USER="$2"; shift 2 ;;
        --token) GITHUB_TOKEN="$2"; shift 2 ;;
        --namespace) NAMESPACE="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$GITHUB_USER" || -z "$GITHUB_TOKEN" ]]; then
    echo "Usage: $0 --user USERNAME --token TOKEN [--namespace janua|enclii|all]"
    exit 1
fi

update_secret() {
    local ns=$1
    echo "Updating ghcr-credentials in namespace: $ns"

    kubectl create secret docker-registry ghcr-credentials \
        --docker-server=ghcr.io \
        --docker-username="${GITHUB_USER}" \
        --docker-password="${GITHUB_TOKEN}" \
        -n "$ns" \
        --dry-run=client -o yaml | kubectl apply -f -

    echo "Secret updated in $ns"
}

if [[ "$NAMESPACE" == "all" ]]; then
    update_secret "janua"
    update_secret "enclii"
else
    update_secret "$NAMESPACE"
fi

echo "Done. Remember to verify deployments and update SECRETS_REGISTRY.yaml"
```

## Rollback Procedure

If new token doesn't work:

1. Old token should still be valid (don't delete until verified)
2. Retrieve old token from password manager or backup
3. Re-apply old credentials:
   ```bash
   kubectl create secret docker-registry ghcr-credentials \
     --docker-server=ghcr.io \
     --docker-username="OLD_USER" \
     --docker-password="OLD_TOKEN" \
     -n janua --dry-run=client -o yaml | kubectl apply -f -
   ```

## Troubleshooting

### ImagePullBackOff Errors

```bash
# Check pod events
kubectl describe pod POD_NAME -n janua | grep -A 10 Events

# Common causes:
# - Token doesn't have read:packages permission
# - Token expired
# - Wrong username
# - Repository not accessible to token
```

### "unauthorized: authentication required"

- Verify token has `read:packages` permission
- For Fine-grained PAT, ensure correct repositories are selected
- Check if organization requires SSO authentication

### Pods stuck in ImagePullBackOff

```bash
# Force recreate pods
kubectl delete pods -n janua -l app=janua-api
# Deployment will recreate them with fresh image pull
```

## Fine-grained vs Classic PAT

| Feature | Fine-grained | Classic |
|---------|--------------|---------|
| Granular permissions | ✅ Yes | ❌ Limited |
| Repository scoping | ✅ Yes | ❌ All or nothing |
| Expiration required | ✅ Yes (max 1 year) | ❌ Optional |
| Recommended | ✅ Yes | ❌ Legacy |

**Always prefer Fine-grained PATs** for better security.

## Related Documents

- [SECRETS_REGISTRY.yaml](../../../infra/secrets/SECRETS_REGISTRY.yaml)
- [EMERGENCY_ROTATION.md](./EMERGENCY_ROTATION.md)
- [GitHub PAT Documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)

---

**Last Updated:** 2026-01-16
**Review Frequency:** Annual
**Cross-Project:** Coordinate Janua + Enclii rotation together
