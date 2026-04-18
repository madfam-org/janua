# PP.3 — Janua staging audit vs RFC 0001

> Last Updated: 2026-04-17
> RFC: [internal-devops/rfcs/0001-dev-staging-prod-pipeline.md](https://github.com/madfam-org/internal-devops/blob/main/rfcs/0001-dev-staging-prod-pipeline.md)
> Runbook: [internal-devops/runbooks/staging-bootstrap.md](https://github.com/madfam-org/internal-devops/blob/main/runbooks/staging-bootstrap.md)
> Reference impl: [karafiel PP.1 — `infra/k8s/overlays/staging/`](https://github.com/madfam-org/karafiel/tree/main/infra/k8s/overlays/staging)
> Precedent: [dhanam PP.2 — `docs/PP_2_STAGING_AUDIT.md`](https://github.com/madfam-org/dhanam/blob/main/docs/PP_2_STAGING_AUDIT.md) (PR #295)
> Scope: audit only — this PR ships the document + a CLAUDE.md cross-reference. Structural and promotion-workflow convergence is **deferred** to PP.3b / PP.3c.

## TL;DR

Janua has **no staging environment today**. The current pipeline is `push to main → CI builds 5 images → CI commits digests into the base kustomization → ArgoCD reconciles directly into prod`. This is the single-tier shape RFC 0001 exists to replace, and for an auth service it is the riskiest shape in the ecosystem (a bad digest == every downstream service's login is broken).

Compliance against RFC 0001: **~15%**. Of 17 audited rows, 2 are aligned, 13 are diverged (in scope for PP.3b / PP.3c), and 2 are deferred (nightly masked DB refresh, secrets cutover). The divergence list is broader than Dhanam's because Janua never had a staging overlay at all — not even a duplicated one.

The four shapes that most differ from RFC 0001:

1. **No staging anything.** No `janua-staging` namespace, no `overlays/staging/`, no staging ArgoCD Application, no `staging-*.janua.dev` subdomain. Staging has to be built from scratch, not refactored from an existing duplicate.
2. **ArgoCD watches `k8s/base/deployments/`**, not an overlay. Current `k8s/overlays/prod/` has `newTag: main` (mutable) and is orphaned — it is not what's deployed. The canonical "prod manifests" today are the base itself, with digests edited into `k8s/base/deployments/kustomization.yaml` by CI. That inverts the RFC layout (`base/` should be env-agnostic; overlays should hold the images).
3. **No promote / rollback workflows.** `.github/workflows/docker-publish.yml` writes prod digests directly on every push to `main`. Rollback is a manual `git revert` plus a re-run. RTO is "however long it takes to rebuild and re-deploy," which is nowhere near RFC 0001's <5 min target.
4. **Janua-specific: there is no "staging Janua tenant" option.** Every other service in the ecosystem uses Janua as the staging auth provider; Janua cannot. Staging Janua must be a **separate self-contained tenant with its own JWT signing keys, its own OAuth client registry, and its own issuer URL**. This is flagged in a dedicated section below.

None of these are blockers for PP.3 (this audit). They are the work items for PP.3b (structural) and PP.3c (promote + rollback + staging Janua tenant wiring).

## Current state vs RFC 0001 — row-by-row

| # | Area | RFC 0001 expects | Janua today | Status | Resolution |
|---|---|---|---|---|---|
| 1 | **Layout: env-agnostic base** | `infra/k8s/base/` holds manifests with no env-specific values | `k8s/base/` at repo root holds manifests **with digests baked in** (via `kustomize edit set image` on base kustomization) | Diverged (fundamental) | PP.3b: strip `images:` out of `k8s/base/deployments/kustomization.yaml`. Move `images:` block into `overlays/prod/kustomization.yaml` and the (new) `overlays/staging/kustomization.yaml`. Update `docker-publish.yml` to write to `overlays/<tier>/`. |
| 2 | **Layout: infra/k8s location** | `infra/k8s/{base,overlays/{staging,production}}` | `k8s/{base,overlays/{dev,prod}}` at repo root; `infra/k8s/production/` only holds the rotation-monitor CronJob | Intentional deviation | Keep `k8s/` at root for now (relocating would churn 20+ downstream references). Document in CLAUDE.md. Follow RFC's `overlays/{staging,production}` naming though — rename `prod` → `production` (cosmetic, PP.3b). |
| 3 | **Staging overlay exists** | `overlays/staging/kustomization.yaml` | Does not exist. Only `overlays/dev/` (local Minikube / KIND) and `overlays/prod/` (orphaned — not in ArgoCD path) | Diverged | PP.3b: create `overlays/staging/kustomization.yaml` referencing `../../base` with staging patches (replicas=1, HPA min=1 max=2, staging env vars, staging ingress, staging image digests). |
| 4 | **Orphaned prod overlay** | `overlays/production/` is the canonical manifest set ArgoCD watches | `k8s/overlays/prod/kustomization.yaml` has `newTag: main` (mutable) and is **not** referenced by any ArgoCD App. ArgoCD watches `k8s/base/deployments/` instead. | Diverged | PP.3b: migrate ArgoCD App source path from `k8s/base/deployments` → `k8s/overlays/production`. Move the digests currently in `base/` into `overlays/production/`. Delete the `newTag: main` mutable tags. Coordinated with ArgoCD App reconfiguration (ops action). |
| 5 | **All 5 apps in staging** | Every deployable app has staging coverage (api, admin, dashboard, docs, website) | All 5 apps exist in `k8s/base/deployments/`, but staging has zero coverage since the overlay doesn't exist. | Diverged | PP.3b: staging overlay patches all 5. Dashboard + admin are the most important to soak (they hit real customers). Website + docs are low-risk but cheap to include. |
| 6 | **Image pinning (prod)** | Digest patched into `overlays/production/kustomization.yaml` by CI (or by promote workflow) | Digest patched into **`k8s/base/deployments/kustomization.yaml`** by `docker-publish.yml` on every push to main | Diverged | PP.3b: move `kustomize edit set image` target in `docker-publish.yml` from `k8s/base/deployments/` to `k8s/overlays/staging/` (only). Prod digest only lands via `promote-to-prod.yml` (PP.3c). |
| 7 | **Image pinning (staging)** | Digest patched into `overlays/staging/` by `build-and-deploy-staging.yml` | N/A — no staging exists | Diverged | PP.3b: add the staging digest-write step to `docker-publish.yml` (or split into a new `build-and-deploy-staging.yml` following Karafiel's pattern). |
| 8 | **Promote workflow** | `promote-to-prod.yml` (`workflow_dispatch`) accepts staging digest, validates soak + smoke, writes to `overlays/production/` | Does not exist. Prod digests land on every push to main. | Diverged | PP.3c (separate PR): add `promote-to-prod.yml`. Janua is **Pattern B — manual gate** per RFC 0001 § Promotion mechanics (auth = critical). |
| 9 | **Rollback workflow** | `rollback-prod.yml` takes target digest, RTO <5 min | Does not exist. Rollback = `git revert` + wait for re-build. | Diverged | PP.3c: add `rollback-prod.yml` with target-digest input. Target RTO <5 min. Per-service default documented in `.enclii.yml` `promotion:` key. |
| 10 | **Soak period before promote** | ≥30 min in staging, staging smoke pass required, validated by promote workflow | N/A — no staging, no promotion | Deferred → PP.3c | |
| 11 | **ArgoCD staging Application** | `janua-staging` App watches `overlays/staging/` | Does not exist. `infra/argocd/config.json` registers only the prod App (and points it at `k8s/base/deployments` — see row 4) | Diverged | PP.3b (infra action): register `janua-staging` ArgoCD Application. Operator checklist in `internal-devops/runbooks/staging-bootstrap.md` §2. |
| 12 | **Staging namespace** | `janua-staging` (per RFC § Secrets table) | Does not exist. Only `janua` (prod). | Diverged | PP.3b (ops action): `kubectl create namespace janua-staging`. |
| 13 | **Staging subdomain / ingress** | `staging-api.janua.dev`, `staging-app.janua.dev`, `staging-auth.madfam.io` | Does not exist. Cloudflare tunnel routes only prod domains (see `enclii/infra/k8s/production/cloudflared-unified.yaml`). | Diverged | PP.3b (ops + Cloudflare): add tunnel routes + DNS for 5 staging subdomains. Staging ingress patch in `overlays/staging/`. |
| 14 | **Staging smoke test** | Post-deploy curl against `staging-<domain>/health` with retry | None — `docker-publish.yml` does not smoke-test. Prod `/health` is the only health signal today. | Diverged | PP.3b: add curl-retry smoke step against `https://staging-api.janua.dev/health` (6 × 20s, Karafiel template). |
| 15 | **Replica counts (staging)** | 1 per deploy, HPA min=1 max=2 | N/A | Diverged | PP.3b: staging overlay sets `replicas: 1` + HPA patch disabling / capping autoscaling. |
| 16 | **Replica counts (prod)** | 2-N per deploy, HPA tuned | `hpa-janua-api.yaml` at `k8s/base/`, currently applies everywhere | Aligned-ish | Keep; after PP.3b base/overlay split, HPA stays in base and is disabled-by-patch in staging overlay. |
| 17 | **Staging secrets template** | Separate `janua-staging-secrets` secret covering every env var prod uses, plus **a distinct JWT signing keypair** | N/A — no staging | Diverged, Janua-specific | PP.3b: secrets template covers `JWT_PRIVATE_KEY_PATH` + `JWT_PUBLIC_KEY_PATH` pointing at a **staging-only RSA-2048 keypair**. Must never reuse prod keys (see "Janua-specific staging constraints" below). |
| 18 | **External service sandbox** | Stripe test, Resend test, Google/GitHub OAuth staging apps | N/A. Prod OAuth client IDs (Google, GitHub, Microsoft) live in `janua-secrets` today. | Diverged | PP.3b: register staging OAuth clients with each upstream provider (Google/GitHub/Microsoft) using `https://staging-auth.madfam.io/callback` redirect URIs. Populate `janua-staging-secrets` with those client IDs + secrets. |
| 19 | **DB: nightly masked restore** | Nightly prod→staging PII-masked DB refresh, 03:00 UTC | Not implemented | Deferred (RFC 0001 open question — masking tool TBD) | Out of scope for PP.3b. Sensitive for Janua: user table contains PII that must never leak to staging unmasked. |
| 20 | **Promotion pattern declaration** | `.enclii.yml` `promotion:` key | Absent from `enclii.yaml` | Diverged → PP.3c | Add `promotion: { pattern: manual, min_soak_minutes: 30, require_smoke_pass: true }`. |
| 21 | **Decommission bypass path** | After 14 days stable, direct-to-prod digest commits removed (RFC Phase 4) | N/A — current pipeline IS the bypass | Diverged → PP.3c + post-soak | Trim `docker-publish.yml`'s direct-to-prod digest commit after PP.3c lands and staging is proven stable. |

## Summary

| Classification | Count | Rows |
|---|---|---|
| Aligned | 2 | 2 (intentional deviation on k8s/ location), 16 (prod HPAs) |
| Diverged — PP.3b scope (structural) | 10 | 1, 3, 4, 5, 6, 7, 11, 12, 13, 14, 15, 17, 18 |
| Diverged — PP.3c scope (promote/rollback/bypass-removal) | 4 | 8, 9, 10, 20, 21 |
| Deferred (out of Phase 1 scope) | 1 | 19 (nightly masked DB) |

**Compliance: ~15%** — Janua has the least staging coverage of the three audited services (Karafiel PP.1 was already piloted; Dhanam PP.2 had a working-if-divergent staging; Janua has none). Both follow-up PRs are required.

## Janua-specific staging constraints (flag for ops)

Janua is itself the auth service. Every **other** service uses Janua for staging OIDC. Janua cannot. This imposes three requirements that don't apply to any other service's staging rollout:

### 1. Separate staging Janua tenant — no "read-only from prod" workaround

Per RFC 0001's § Secrets table: `Janua client secret | Dev: dev-bypass | Staging: janua-staging-sso | Production: janua-prod-sso`. For consumer services, "staging" means "point at Janua's staging tenant." For Janua itself, **there is no staging tenant to point at unless we build one.**

Staging Janua must be a fully separate instance:
- Its own PostgreSQL database (`janua_staging`), never a replica of prod
- Its own OAuth client registry (staging downstream services register against it, not against prod)
- Its own issuer URL: recommended `https://staging-auth.madfam.io` or `https://auth-staging.janua.dev` (Cloudflare tunnel + DNS, ops action)
- Its own admin bootstrap password (via `ADMIN_BOOTSTRAP_PASSWORD` on first startup)

**A "staging reads production in read-only mode" workaround is explicitly rejected** because:
- Janua issues JWTs; a staging instance reading prod users would issue tokens valid against prod services
- The OAuth client registry is write-heavy (every new staging service adds a client); read-only makes staging unusable
- Audit log bleed-through — staging admin actions would appear in prod audit records

### 2. Staging JWT signing key MUST be a distinct RSA-2048 keypair

`JWT_ALGORITHM=RS256` today in prod (per CLAUDE.md § Environment Variables). Staging must:
- Have its own `keys/private.pem` / `keys/public.pem` generated specifically for staging (`openssl genrsa -out private.pem 2048`)
- Mount those keys from `janua-staging-secrets`, never from `janua-secrets`
- Publish its public key at `https://staging-auth.madfam.io/.well-known/jwks.json`, separate from prod's JWKS endpoint

If the staging key ever matches the prod key, a compromised staging env becomes a prod token issuer. This is a **hard requirement**, not a best practice. The staging-bootstrap runbook §3 needs a Janua-specific addendum to spell this out.

### 3. Field encryption key (`FIELD_ENCRYPTION_KEY`) must also be distinct

Per CLAUDE.md: `FIELD_ENCRYPTION_KEY` is required in production for SOC 2 CF-01. Staging must have its own Fernet key so that if staging is ever seeded with real production-shape data (via the deferred row 19 masked-restore), the at-rest encryption is not shared across environments.

Generate with: `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`

### Staging-secrets-template addendum for Janua

When `janua-staging-secrets` is first created (PP.3b operator checklist), it must include:

| Secret key | How to generate | Notes |
|---|---|---|
| `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` | `openssl genrsa -out private.pem 2048` + `openssl rsa -in private.pem -pubout -out public.pem` | Never reuse prod keypair |
| `JWT_SECRET_KEY` | `openssl rand -base64 48` | HS256 fallback; distinct from prod |
| `FIELD_ENCRYPTION_KEY` | `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'` | Distinct from prod Fernet key |
| `ADMIN_BOOTSTRAP_PASSWORD` | `openssl rand -base64 24` | Bootstraps `admin@madfam.io` in staging DB |
| `DATABASE_URL` | Points at `janua_staging` DB, distinct role | Never a prod replica |
| `GOOGLE_CLIENT_ID` / `SECRET`, `GITHUB_CLIENT_ID` / `SECRET`, `MICROSOFT_CLIENT_ID` / `SECRET` | Register staging apps with each provider | Redirect URIs: `https://staging-auth.madfam.io/oauth/<provider>/callback` |
| `RESEND_API_KEY` | Scoped staging key, verified test sending domain | `@staging.janua.dev` or similar |
| `ALLOWED_ADMIN_DOMAINS` | `@janua.dev,@madfam.io` | Same as prod is fine |

This addendum should land in `infra/secrets/SECRETS_REGISTRY.yaml` under a new `janua-staging` entry when PP.3b opens the structural PR.

## What PP.3 (this PR) ships

Per user instructions ("audit + CLAUDE.md update only, under 300 LOC, no convergence bundling"):

1. **This audit document** (`docs/PP_3_STAGING_AUDIT.md`).
2. **CLAUDE.md update** — a "Deployment Pipeline (dev → staging → prod)" section cross-referencing RFC 0001, the runbook, and this audit doc, following the format Dhanam PP.2 landed.
3. **No YAML, workflow, or secret changes.** Structural convergence is scoped to follow-up PRs:
   - **PP.3b — Structural** (est. ~250 LOC yaml + ~40 LOC workflow). Create `overlays/staging/`, move digests out of `base/` into `overlays/{staging,production}/`, migrate ArgoCD App path, add staging smoke, add staging OAuth client registration, populate `janua-staging-secrets` template. Rename `overlays/prod/` → `overlays/production/`.
   - **PP.3c — Promote + rollback + bypass removal** (est. ~250 LOC net). Add `promote-to-prod.yml`, `rollback-prod.yml`. Add `promotion:` key to `.enclii.yml`. Trim `docker-publish.yml`'s direct-to-prod commit once staging is proven stable (Phase 4 per RFC).

Split rationale matches PP.2 precedent: keep every diff reviewable and reversible; never change prod deploy behavior and staging deploy behavior in the same PR.

## Cross-references

- RFC 0001 — `internal-devops/rfcs/0001-dev-staging-prod-pipeline.md`
- Runbook — `internal-devops/runbooks/staging-bootstrap.md`
- Reference impl — `karafiel/infra/k8s/overlays/staging/kustomization.yaml` (PP.1)
- PP.2 precedent — `dhanam/docs/PP_2_STAGING_AUDIT.md` (PR #295)
- Secrets registry — `infra/secrets/SECRETS_REGISTRY.yaml` (PP.3b will add `janua-staging` entry)
- Tunnel routing — `enclii/infra/k8s/production/cloudflared-unified.yaml` (PP.3b will add `staging-*` routes)
- This PR — `feat/pp-3-janua-staging-audit`
- Follow-up PRs — PP.3b (structural convergence), PP.3c (promote/rollback + bypass removal)
