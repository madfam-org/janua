# Janua runbooks

Operator guides for production GitOps, secrets rotation, and incident records.

## Production deploy

| Document | When to use |
|----------|-------------|
| [production-gitops-reconcile.md](./production-gitops-reconcile.md) | After promote, Argo OutOfSync, Kyverno blocks, GHCR pull failures |
| [ALEMBIC_CONVERGENCE.md](./ALEMBIC_CONVERGENCE.md) (ES) | Before promoting with unapplied migrations; after applying a migration by hand |
| [../PP_3B_STAGING_PIPELINE.md](../PP_3B_STAGING_PIPELINE.md) | Full staging → prod pipeline (Pattern B) |

## Compliance

| Document | When to use |
|----------|-------------|
| [data-subject-request-access-audit.md](./data-subject-request-access-audit.md) | Who may read a data-subject request export; read-only audit of who processed existing requests |

## Email

- [Recoverable payment notices](payment-notice-recovery.md): scoped service tokens, bounded provider retries, and immutable acceptance receipts.
- [Resend email events](resend-email-events.md): signed webhook receiver, per-app events feed, render-only preview, the never-track-token-links rule, and first-party open/click measurement on per-tenant tracking hosts.

| Document | When to use |
|----------|-------------|
| [resend-domain-onboarding.md](./resend-domain-onboarding.md) | Adding a client sending domain to Resend (Phase 2 of `../EMAIL_SENDER_POLICY.md`) |

## Incidents

| Date | Document |
|------|----------|
| 2026-06-15 | [janua.dev website prod rollout](./incidents/2026-06-15-janua-website-prod-rollout.md) |

## Secrets

| Document | Scope |
|----------|-------|
| [secrets/ghcr-pat-rotation.md](./secrets/ghcr-pat-rotation.md) | `ghcr-credentials` pull secret |
| [secrets/resend-webhook-secret-rotation.md](./secrets/resend-webhook-secret-rotation.md) | Resend webhook signing secret per account (`RESEND_WEBHOOK_SECRET_CTM`) |
| [secrets/DEPLOYMENT_GUIDE.md](./secrets/DEPLOYMENT_GUIDE.md) | General secret deployment |
| [secrets/EMERGENCY_ROTATION.md](./secrets/EMERGENCY_ROTATION.md) | Break-glass rotation |

**Enclii workflow (preferred for GHCR):** `madfam-org/enclii` → Actions → **Rotate GHCR credentials (namespace)**.
