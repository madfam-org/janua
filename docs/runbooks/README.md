# Janua runbooks

Operator guides for production GitOps, secrets rotation, and incident records.

## Production deploy

| Document | When to use |
|----------|-------------|
| [production-gitops-reconcile.md](./production-gitops-reconcile.md) | After promote, Argo OutOfSync, Kyverno blocks, GHCR pull failures |
| [../PP_3B_STAGING_PIPELINE.md](../PP_3B_STAGING_PIPELINE.md) | Full staging → prod pipeline (Pattern B) |

## Incidents

| Date | Document |
|------|----------|
| 2026-06-15 | [janua.dev website prod rollout](./incidents/2026-06-15-janua-website-prod-rollout.md) |

## Secrets

| Document | Scope |
|----------|-------|
| [secrets/ghcr-pat-rotation.md](./secrets/ghcr-pat-rotation.md) | `ghcr-credentials` pull secret |
| [secrets/DEPLOYMENT_GUIDE.md](./secrets/DEPLOYMENT_GUIDE.md) | General secret deployment |
| [secrets/EMERGENCY_ROTATION.md](./secrets/EMERGENCY_ROTATION.md) | Break-glass rotation |

**Enclii workflow (preferred for GHCR):** `madfam-org/enclii` → Actions → **Rotate GHCR credentials (namespace)**.
