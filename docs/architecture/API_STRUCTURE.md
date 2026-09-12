# Janua API Structure

## Current Architecture

The Janua platform uses a **monorepo structure** with clear separation between frontend applications and the backend API:

### Directory Structure
```
janua/
├── apps/
│   ├── api/          # ← Python FastAPI backend  → ghcr.io/madfam-org/janua-api
│   ├── admin/        # Next.js admin panel       → ghcr.io/madfam-org/janua-admin
│   ├── dashboard/    # Next.js user dashboard    → ghcr.io/madfam-org/janua-dashboard
│   ├── docs/         # Documentation site        → ghcr.io/madfam-org/janua-docs
│   ├── website/      # Marketing website         → ghcr.io/madfam-org/janua-website
│   └── edge-verify/  # Edge token verification (not a published image)
├── packages/         # Shared SDKs and libraries
│   ├── typescript-sdk/
│   ├── react-sdk/
│   ├── python-sdk/
│   ├── go-sdk/
│   └── ...           # Other SDKs
├── Dockerfile.api    # ← the image build for apps/api (build context is the REPO ROOT)
├── Dockerfile.admin  # one per published app, all at the repo root
├── k8s/              # kustomize base + overlays (staging, production)
└── deployment/       # Helm chart, compose files, local/dev infrastructure
```

## API Location

**The API is located at `/apps/api/`** - this is the single source of truth for the backend API.

### Why This Structure?

1. **Clear Separation**: Python backend in `/apps/api/`, TypeScript/JavaScript frontends in other `/apps/*` folders
2. **Independent Deployment**: each app builds its own image and carries its own digest in the kustomize overlays, so one can ship without the others
3. **One build context**: the image is built from the **repo root** `Dockerfile.api`, not from `/apps/api/`. It needs the root for the monorepo's shared files, and it copies `apps/api/requirements.txt` and `apps/api/` in explicitly. `apps/api/Dockerfile` still exists for local use and is referenced by **no** workflow — do not edit it expecting production to change.

## API Technology Stack

- **Framework**: FastAPI (Python)
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Cache**: Redis
- **Authentication**: JWT with refresh tokens
- **Rate Limiting**: Redis-backed token bucket algorithm
- **Deployment**: container image on GHCR, pinned by digest, reconciled by ArgoCD onto MADFAM's k3s (see [Deployment](#deployment))

## Important Files

### Configuration
- `/apps/api/requirements.txt` - Python dependencies
- `/apps/api/.env.example` - Environment variables template
- `/Dockerfile.api` - the image CI actually builds
- `/k8s/overlays/staging/kustomization.yaml` - staging image digests (written by CI)
- `/k8s/overlays/production/kustomization.yaml` - production image digests (written by promote only)
- `/apps/api/alembic/PROD_ALEMBIC_STATE.json` - the ledger of production's schema revision

### Application Code
- `/apps/api/app/main.py` - FastAPI application entry point
- `/apps/api/app/config.py` - Application configuration
- `/apps/api/app/routers/` - API endpoints
- `/apps/api/app/models/` - Database models
- `/apps/api/app/services/` - Business logic
- `/apps/api/app/middleware/` - Middleware (auth, rate limiting, etc.)

## Deployment

There is no PaaS. The API runs as a container on **MADFAM's own k3s cluster**,
and every step between a merge and a running pod is a git commit.

```
merge to main
   │
   ├─▶ .github/workflows/docker-publish.yml  ("Docker Publish")
   │     builds Dockerfile.api (context: repo root)
   │     pushes ghcr.io/madfam-org/janua-api  :main and :<sha>
   │     signs it keyless with cosign (unsigned ⇒ hard failure; Kyverno will not admit it)
   │
   ├─▶ same workflow, job "Commit Digests to Staging Kustomization"
   │     kustomize edit set image …janua-api@sha256:…
   │     commits to k8s/overlays/staging/kustomization.yaml — AUTOMATIC, no gate
   │
   │   ArgoCD application janua-staging  →  namespace janua-staging
   │
   └─▶ .github/workflows/promote-to-prod.yml  ("Promote staging -> prod")
         workflow_dispatch ONLY — a human runs it and states a reason
         writes the SAME digest into k8s/overlays/production/kustomization.yaml

       ArgoCD application janua-services (namespace argocd)  →  namespace janua
```

**Promotion is a pointer update.** It does not rebuild; it copies the digest
that has been running in staging into the production overlay. Janua is RFC 0001
**Pattern B (manual promote gate)** because it is the ecosystem's auth floor —
every other MADFAM service depends on its JWTs — so auto-promote is gated off by
the repo variable `AUTO_PROMOTE_ENABLED`.

Two gates run before the promote writes anything:

- **`migrations-guard`** — compares the repo's alembic head against
  `apps/api/alembic/PROD_ALEMBIC_STATE.json`. It cannot query the database (it
  runs on a GitHub-hosted runner with no route to prod), so it converts a silent
  assumption into a loud question: unrecorded revisions stop the promote unless
  the operator ticks `migrations_acknowledged`.
- **Soak** — the digest must have been in the staging overlay for at least
  `MIN_SOAK_MINUTES` (default **30**). `break_glass_without_soak` bypasses it and
  is recorded in the audit log.

**Promote runs no migrations. That is the design.** A migration reaches
production only when an operator applies it, from inside the `janua-api` pod,
and then stamps and records it:

```bash
# read-only verification first
kubectl -n janua exec deploy/janua-api -- python scripts/alembic_converge.py --check
```

See [`docs/runbooks/ALEMBIC_CONVERGENCE.md`](/docs/runbooks/ALEMBIC_CONVERGENCE.md).
`PROD_ALEMBIC_STATE.json` is a **ledger, not a source of truth** — the database is
the truth; that file records the last time a human read it — and it must be
refreshed in the same PR as the migration.

Rollback is [`rollback-prod.yml`](/.github/workflows/rollback-prod.yml),
`workflow_dispatch` only, sharing the `prod-promote` concurrency group.
Reconciling a promote that git accepted but the cluster did not adopt is
[`docs/runbooks/production-gitops-reconcile.md`](/docs/runbooks/production-gitops-reconcile.md)
— note the Argo application is named **`janua-services`**, not `janua`.

The operator-facing walkthrough of the whole pipeline is
[`docs/PP_3B_STAGING_PIPELINE.md`](/docs/PP_3B_STAGING_PIPELINE.md).

## Development

To run the API locally:

```bash
cd apps/api
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 4100
```

Or with Docker:

```bash
cd apps/api
docker-compose up
```

The container listens on `$PORT`, default **4100**.

## Why Not in Nx Workspace?

While the frontend apps use Nx workspace tooling, the Python API is kept separate because:

1. **Different ecosystem**: Python vs JavaScript/TypeScript
2. **Different build tools**: pip vs npm/pnpm
3. **Independence**: API can be developed and released independently — it has its own image, its own digest in the overlays, and its own schema lifecycle

Every app in the monorepo, Python and Next.js alike, ships the same way: an
image on GHCR, a digest in a kustomize overlay, ArgoCD on MADFAM's k3s. Nothing
here is deployed to a third-party PaaS.

This structure provides the best of both worlds - a unified monorepo for code organization while maintaining ecosystem-appropriate tooling for each component.
