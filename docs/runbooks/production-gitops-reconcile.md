# Production GitOps reconcile (Janua)

> **Audience:** Operators, SRE, release engineers  
> **Pattern:** RFC 0001 Pattern B — manual promote gate  
> **Enclii-first:** Routine prod reconciliation uses Enclii web/API/CLI. Raw `kubectl` from GitHub-hosted runners is break-glass only.

This runbook describes how production digests in git become running pods on the
cluster, what commonly blocks rollout, and how to recover without guessing.

---

## Architecture summary

| Layer | Source of truth | Reconciler |
|-------|-----------------|------------|
| Container images | `ghcr.io/madfam-org/janua-*` (cosign-signed on `main`) | CI `docker-publish.yml` |
| Staging digests | `k8s/overlays/staging/kustomization.yaml` | `docker-publish.yml` (auto on `main`) |
| Production digests | `k8s/overlays/production/kustomization.yaml` | `promote-to-prod.yml` (manual) |
| Cluster state | Argo CD Application **`janua-services`** | Argo CD in `argocd` namespace |

**Important:** The Argo CD Application is named `janua-services`, not `janua`.
Manifest path: `k8s/overlays/production`. Target namespace: `janua`.

Policy record: root `enclii.yaml` → `promotion.pattern: manual`,
`min_soak_minutes: 30`.

---

## Happy-path promote (operator)

1. **Build + staging soak** — merge to `main`; `docker-publish.yml` updates
   `k8s/overlays/staging/` digests. Wait ≥30 minutes (or repo `MIN_SOAK_MINUTES`).
2. **Promote** — GitHub Actions → **Promote staging → prod**
   (`promote-to-prod.yml`). Use `break_glass_without_soak=true` only for
   verified emergencies.
3. **Reconcile cluster** — git ahead of cluster is normal until Argo syncs:

   ```bash
   enclii ops apps diff janua-services -n argocd --json
   enclii ops apps sync janua-services -n argocd --apply \
     --reason "Reconcile prod after promote-to-prod digest write"
   ```

4. **Verify rollout** — per service:

   ```bash
   enclii ops pods diagnose janua-website -n janua --json
   curl -fsSI https://janua.dev/health
   ```

5. **Public smoke** — landing CSS utilities present, marketing shell on subpages:

   ```bash
   css=$(curl -fsSL "https://janua.dev${css}" | rg -q '\.flex\{' || curl -fsSL "https://janua.dev${css}" | grep -q '\.flex{')
   curl -fsSI https://janua.dev/pricing | rg -q '200'
   curl -fsSI https://janua.dev/legal/privacy | rg -q '200'
   # SSR title + font tokens (hero headline is client-rendered)
   curl -fsSL https://janua.dev/ | grep -q 'Edge-Fast Identity Platform'
   ```

Full pipeline context: [PP_3B_STAGING_PIPELINE.md](../PP_3B_STAGING_PIPELINE.md).

---

## Break-glass: `sync-prod-gitops.yml`

When Enclii ops sync is insufficient (stuck Argo operation, Kyverno block already
patched in git, GHCR pull failure):

1. GitHub Actions → **Sync prod GitOps overlay** (`workflow_dispatch`)
2. Inputs: `confirm=sync-now`, `component=janua-website` (or blank for website default)

The workflow (`.github/workflows/sync-prod-gitops.yml`):

- Runs on **`madfam-runners-blue`** when `ARC_BOOTSTRAP_COMPLETE=true`
- Repoints `KUBECONFIG_PRODUCTION` to the **in-cluster API** on ARC
  (`KUBERNETES_SERVICE_HOST`) — external kube-apiserver URLs in the secret are
  not reachable from GitHub-hosted runners
- Refreshes `janua/ghcr-credentials` from `dhanam/ghcr-credentials` (best-effort)
- Clears stuck Argo operations on `janua-services`
- Applies `kustomize build k8s/overlays/production`
- Waits for deployment rollout + HTTP smoke

**Limitation:** Copying GHCR credentials from `dhanam` may not grant access to
all `madfam-org/janua-*` packages. Prefer the Enclii rotate workflow below when
pulls fail with `403 Forbidden`.

---

## Common blockers

### 1. Argo CD OutOfSync / stuck sync operation

**Symptoms:** `enclii ops apps diff janua-services` shows `OutOfSync`; sync
returns `409 already_running`.

**Recovery:**

```bash
# After stuck operation clears (or via break-glass workflow patch):
enclii ops apps sync janua-services -n argocd --apply --reason "..."
```

If sync loops on Kyverno or image pull, fix those first (below).

### 2. Kyverno `verify-image-signatures`

**Symptoms:** Argo sync error on `janua-website` (or other deployments):

```text
verify-image-signatures / autogen-check-signature: failed to verify image ...
GET https://ghcr.io/token?... DENIED: denied
```

**Cause:** Cluster policy requires cosign verification; Kyverno cannot pull
private GHCR manifests to verify signatures.

**Mitigation (shipped 2026-06-15):** Scoped PolicyException in
`k8s/overlays/production/kyverno-policy-exception.yaml` (Dhanam-aligned pattern).
Does **not** disable cluster-wide verification — only Janua workload names in
`janua` namespace.

**Long-term:** Public GHCR packages or Kyverno registry credentials aligned with
`madfam-bot` `read:packages` across all janua images.

### 3. Stale `janua/ghcr-credentials`

**Symptoms:** New pod `ImagePullBackOff` / `ErrImagePull` with
`403 Forbidden` on `ghcr.io/token`; old pod continues serving stale image.

**Recovery (Enclii — preferred):**

```bash
# madfam-org/enclii → Actions → Rotate GHCR credentials (namespace)
# namespace=janua
# reason="Unblock janua image pull after promote"
```

Workflow: `enclii/.github/workflows/rotate-ghcr-namespace.yml` (uses
`GHCR_PAT` + in-cluster kubeconfig on ARC).

**Manual reference:** [ghcr-pat-rotation.md](./secrets/ghcr-pat-rotation.md)

### 4. GitHub Actions cannot reach cluster API

**Symptoms:** `drift-check.yml`, `sync-prod-gitops.yml` on `ubuntu-latest` log
`Cluster API unreachable`; `KUBECONFIG_PRODUCTION` points at dead external IP.

**Rule:** Production reconcile from CI must use **ARC runners** with in-cluster
API repointing (see `enclii` `gitops-argo-sync.yml` pattern). Do not rely on
external kube-apiserver URLs from GitHub-hosted runners.

**Enclii adapter gap:** Document when GH Actions kubectl is intentionally
unavailable; use `enclii ops apps sync` from an authenticated operator session.

---

## Files and workflows reference

| Artifact | Purpose |
|----------|---------|
| `k8s/overlays/production/kustomization.yaml` | Prod digest pins (promote-only) |
| `k8s/overlays/production/kyverno-policy-exception.yaml` | GitOps rollout unblock for cosign gate |
| `.github/workflows/promote-to-prod.yml` | Manual promote (Pattern B) |
| `.github/workflows/sync-prod-gitops.yml` | Break-glass apply + GHCR refresh |
| `.github/workflows/docker-publish.yml` | Build/sign → staging digests only |
| `infra/argocd/config.json` | Argo app metadata (`janua-services`) |
| `enclii/.github/workflows/rotate-ghcr-namespace.yml` | Namespace GHCR secret refresh |

---

## Verification checklist (post-reconcile)

- [ ] `enclii ops apps diff janua-services -n argocd` — target deployment `Synced`
- [ ] `enclii ops pods diagnose <deployment> -n janua` — single Ready pod on expected digest
- [ ] Public URL health (`https://janua.dev/health`, `https://api.janua.dev/health`)
- [ ] For website: Tailwind utilities in CSS; `(marketing)` layout on `/pricing`
- [ ] For website: `/legal/privacy` returns 200 (post Phase 2 UX)
- [ ] Footer links match current `apps/website/components/footer.tsx` (no dead 404s)

---

## Related documents

- [PP_3B_STAGING_PIPELINE.md](../PP_3B_STAGING_PIPELINE.md) — full 3-tier pipeline
- [Incident: 2026-06-15 website prod rollout](./incidents/2026-06-15-janua-website-prod-rollout.md)
- [ghcr-pat-rotation.md](./secrets/ghcr-pat-rotation.md)
- [AGENTS.md](../../AGENTS.md) — Enclii-first doctrine

**Last updated:** 2026-06-15
