# GHCR Setup and Maintenance Guide

> [!IMPORTANT]
> MADFAM-ENCLII-FIRST-LEGACY-RAW v1: This document contains legacy raw infrastructure command examples.
> Routine production operations must use Enclii web, API, or CLI. Treat raw
> `kubectl`, `helm`, SSH, provider CLI/API, `docker exec`, and direct container
> access as platform bootstrap or documented break-glass only, and record any
> missing Enclii adapter gap.


> Guide for managing GitHub Container Registry (GHCR) authentication for Janua Kubernetes deployments.

## Overview

Janua uses GHCR (GitHub Container Registry) to store and distribute Docker images. Kubernetes clusters need proper authentication to pull these private images.

## Image Naming Convention

All Janua images follow this standard pattern:

```
ghcr.io/madfam-org/janua-{service}:{tag}

Services: api, dashboard, admin, docs, website
Tags: latest, main-{7char-sha}, v{semver}
```

### Examples
- `ghcr.io/madfam-org/janua-api:latest`
- `ghcr.io/madfam-org/janua-api:main-abc1234`
- `ghcr.io/madfam-org/janua-dashboard:latest`

## Creating a GitHub Personal Access Token (PAT)

### Step 1: Navigate to GitHub Settings

1. Go to [GitHub Settings > Developer settings > Personal access tokens > Fine-grained tokens](https://github.com/settings/tokens?type=beta)
2. Click "Generate new token"

### Step 2: Configure the Token

| Field | Value |
|-------|-------|
| **Token name** | `ghcr-janua-k8s-pull` |
| **Expiration** | 1 year (recommended for production) |
| **Repository access** | Only select repositories: `madfam-org/janua` |

### Step 3: Set Permissions

Under "Repository permissions":

| Permission | Access Level |
|------------|-------------|
| **Packages** | Read-only |

**Important**: Only grant `packages:read` - no other permissions are needed for image pulling.

### Step 4: Generate and Save

1. Click "Generate token"
2. **Copy the token immediately** - you cannot see it again
3. Store it securely (password manager, vault, etc.)

## Kubernetes Secret Setup

### Create the Secret

SSH to your Kubernetes node and run:

```bash
# Delete existing secret (if any)
sudo kubectl delete secret ghcr-credentials -n janua 2>/dev/null

# Create new secret
sudo kubectl create secret docker-registry ghcr-credentials \
  --namespace=janua \
  --docker-server=ghcr.io \
  --docker-username=madfam-org \
  --docker-password=<YOUR_PAT_TOKEN> \
  --docker-email=admin@madfam.io
```

### Verify the Secret

```bash
# Check secret exists
kubectl get secret ghcr-credentials -n janua

# Verify secret content (decoded)
kubectl get secret ghcr-credentials -n janua -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d | jq .
```

Expected output should show:
```json
{
  "auths": {
    "ghcr.io": {
      "username": "madfam-org",
      "password": "ghp_...",
      "email": "admin@madfam.io",
      "auth": "base64-encoded-credentials"
    }
  }
}
```

## Deployment Configuration

All K8s deployments must include `imagePullSecrets`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: janua-api
  namespace: janua
spec:
  template:
    spec:
      imagePullSecrets:
        - name: ghcr-credentials
      containers:
        - name: janua-api
          image: ghcr.io/madfam-org/janua-api:latest
          imagePullPolicy: Always
```

## Token Rotation Procedure

Tokens should be rotated annually (or immediately if compromised).

### Step 1: Create New Token

Follow the "Creating a GitHub PAT" steps above with a new token name like `ghcr-janua-k8s-pull-2026`.

### Step 2: Update Kubernetes Secret

```bash
# Delete old secret
sudo kubectl delete secret ghcr-credentials -n janua

# Create with new token
sudo kubectl create secret docker-registry ghcr-credentials \
  --namespace=janua \
  --docker-server=ghcr.io \
  --docker-username=madfam-org \
  --docker-password=<NEW_PAT_TOKEN> \
  --docker-email=admin@madfam.io
```

### Step 3: Force Pod Recreation (Optional)

If pods are having issues, restart deployments:

```bash
kubectl rollout restart deployment -n janua
```

### Step 4: Revoke Old Token

Once verified, revoke the old token in GitHub Settings.

## Troubleshooting

### ImagePullBackOff Errors

**Symptom**: Pods stuck in `ImagePullBackOff` status.

```bash
# Check pod events
kubectl describe pod <pod-name> -n janua | grep -A 10 Events

# Check image pull errors
kubectl get events -n janua | grep -i pull
```

**Common causes**:
1. **Expired PAT**: Create new token and update secret
2. **Wrong image name**: Verify image exists in GHCR
3. **Missing imagePullSecrets**: Check deployment YAML
4. **Wrong repository permissions**: Verify PAT has `packages:read`

### Verify Image Exists

```bash
# Check if image exists in GHCR
docker manifest inspect ghcr.io/madfam-org/janua-api:latest

# Or with authentication
echo $GHCR_TOKEN | docker login ghcr.io -u madfam-org --password-stdin
docker manifest inspect ghcr.io/madfam-org/janua-api:latest
```

### Debug Secret Issues

```bash
# Verify secret is correctly configured
kubectl get secret ghcr-credentials -n janua -o yaml

# Test pull manually (on node)
sudo docker login ghcr.io -u madfam-org -p <token>
sudo docker pull ghcr.io/madfam-org/janua-api:latest
```

### Check Deployment Has imagePullSecrets

```bash
kubectl get deployment janua-api -n janua -o jsonpath='{.spec.template.spec.imagePullSecrets}'
# Should output: [{"name":"ghcr-credentials"}]
```

## CI/CD Integration

The GitHub Actions workflow handles image publishing:

```yaml
# .github/workflows/docker-publish.yml
- name: Log in to GitHub Container Registry
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}  # Automatic in GitHub Actions
```

Deployment uses patch to preserve configuration:

```yaml
- name: Deploy to Kubernetes (patch-only)
  run: |
    kubectl patch deployment janua-api -n janua \
      --type='json' \
      -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/image", "value": "'$IMAGE'"}]'
```

## Security Best Practices

1. **Minimal permissions**: Only grant `packages:read` for pull tokens
2. **Token rotation**: Rotate annually or after any suspected compromise
3. **Separate tokens**: Use different tokens for CI (push) vs K8s (pull)
4. **Audit access**: Regularly review GitHub PAT usage
5. **Never commit tokens**: Always use secrets management

## Quick Reference

### Token Creation Checklist
- [ ] Fine-grained PAT (not classic)
- [ ] Repository: `madfam-org/janua`
- [ ] Permission: `packages:read` only
- [ ] Expiration: 1 year
- [ ] Stored securely

### K8s Secret Commands
```bash
# Create
kubectl create secret docker-registry ghcr-credentials \
  -n janua \
  --docker-server=ghcr.io \
  --docker-username=madfam-org \
  --docker-password=<TOKEN>

# Verify
kubectl get secret ghcr-credentials -n janua

# Delete
kubectl delete secret ghcr-credentials -n janua
```

### Verification Commands
```bash
# Check pods
kubectl get pods -n janua

# Check events
kubectl get events -n janua | grep -i pull

# Test image exists
docker manifest inspect ghcr.io/madfam-org/janua-api:latest
```

---

*Last updated: January 2025*
*Next rotation due: January 2026*
