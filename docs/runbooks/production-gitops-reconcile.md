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

5. **Public smoke** — from a workstation (ARC may not reach public janua.dev):

   ```bash
   css=$(curl -fsSL https://janua.dev/ | grep -oE '/_next/static/chunks/[^"]+\.css' | head -1)
   curl -fsSL "https://janua.dev${css}" | grep -qF '.flex{'
   curl -fsSI https://janua.dev/legal/privacy | grep -q '200'
   curl -fsSL https://janua.dev/ | grep -qF 'Edge-Fast Identity Platform'
   ```

Full pipeline context: [PP_3B_STAGING_PIPELINE.md](../PP_3B_STAGING_PIPELINE.md).

---

## Break-glass: `sync-prod-gitops.yml`

When Enclii ops sync is insufficient (stuck Argo operation, Kyverno block already
patched in git, GHCR pull failure):

1. GitHub Actions → **Sync prod GitOps overlay** (`workflow_dispatch`)
2. Inputs: `confirm=sync-now`, `component=janua-website` (or blank for website default)

The workflow (`.github/workflows/sync-prod-gitops.yml`):

- Refuses any dispatch ref but `main`, and any `component` other than
  `janua-api`, `janua-admin`, `janua-dashboard`, `janua-docs` or `janua-website`,
  before it touches the cluster
- Checks out `main`'s tip, so it applies exactly what Argo CD would reconcile.
  It cannot change what production runs; that goes through `promote-to-prod.yml`
  or `rollback-prod.yml` first
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

**Retired 2026-11:** `force-fix-deployment.yml` and `unified-recovery.yml`, both
from the January 2026 Switchyard incidents, are gone. They replaced `janua-api`
with an image tag that was never promoted, outside GitOps, and scaled Enclii's
`switchyard-api`. Use this workflow or Enclii ops sync instead.

### Production kubeconfig secret (owner decision)

Only three workflows may hold `KUBECONFIG_PRODUCTION`: this one,
`drift-check.yml` and `diagnose-cluster.yml`. The last two only read. The jobs
that read the secret all declare `environment: production-cluster`:
- `sync` in `sync-prod-gitops.yml`;
- `check-drift` in `drift-check.yml`;
- `diagnose` in `diagnose-cluster.yml`.

`apps/api/tests/unit/core/test_cluster_credential_workflows.py` enforces both.

Until the secret moves into that environment, those jobs still read the
**repository** copy. GitHub gives repository secrets to a run on any branch, and
that run uses the branch's copy of the workflow. So the `main`-only check above
stops a mistaken dispatch, not someone with write access. Finishing the move is a
repository-settings change for the owner:

1. Limit the environment to `main`. If a job has already run in it, GitHub has
   created the environment without rules; this adds them.

   ```bash
   gh api -X PUT repos/madfam-org/janua/environments/production-cluster --input - <<'EOF'
   {"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}
   EOF
   gh api -X POST repos/madfam-org/janua/environments/production-cluster/deployment-branch-policies -f name=main -f type=branch
   ```

2. Store the base64-encoded kubeconfig in the environment. Pass the value on
   stdin, with
   `gh secret set KUBECONFIG_PRODUCTION --env production-cluster -R madfam-org/janua`,
   then confirm it with
   `gh secret list --env production-cluster -R madfam-org/janua`.
3. Only then delete the repository copy:
   `gh secret delete KUBECONFIG_PRODUCTION -R madfam-org/janua`.

Steps 1 and 2 may happen before or after the jobs gain the `environment:` line:
until step 3, a job falls back to the repository copy.

Do **not** add required reviewers to this environment while `drift-check` runs
in it on its six-hourly schedule. Every scheduled run would then wait for an
approval. If you want a second approver on break-glass applies, give `sync` its
own environment first.

Also worth confirming in the cluster: the ARC runner pods' own service account
should have no write access to the `janua` namespace. Otherwise a workflow on
ARC would not need this secret at all.

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

**Removing the exception (owner decision).** While the exception is in place the
cluster does not check that a Janua image was built and signed by CI. Deleting the
file without the prerequisites below breaks every Argo sync of `janua-services`,
so remove it only when all of these hold:

1. **Kyverno can read the images.** The policy reads registry credentials from a
   `ghcr-credentials` secret in Kyverno's own namespace. Either that secret holds
   a token with `read:packages` for `madfam-org/janua-*`, or the packages are
   public and Kyverno reads them anonymously (no stale token in that secret).
   Which of these is true can only be confirmed in the cluster; nothing in Git
   declares that secret.
2. **Every image it would admit is signed.** That means each digest production
   runs, and each digest a rollback could restore, needs a keyless cosign
   signature from GitHub Actions.
3. **Staged removal.** Drop one workload name from the exception first (lowest
   blast radius: `janua-website*`), sync, and confirm admission. Then do the rest.

Status 2026-11-04, read from the public registry (not from the cluster):
- All five packages answer anonymous manifest reads.
- The five digests production runs verify with `cosign verify` against the GitHub Actions issuer, signed by `docker-publish.yml` on `main`.
- 104 of the 105 digests in the production overlay's history on `main` are still pullable, each with a signature. One old api digest is gone from GHCR.

Status 2026-11-05, read in the cluster (no changes made):
- The `janua` namespace is opted in to signature checks.
- Kyverno has its own `ghcr-credentials` secret.
- Server-side dry runs of pods using each of the five running images were never
  refused by `verify-image-signatures`.
- A control dry run with a digest that does not exist *was* refused by it, which
  proves the check runs on dry runs.

Items 1 and 2 hold, so removal is under way, one name at a time:

| Stage | Workload name dropped | Status |
| --- | --- | --- |
| 1 | `janua-website*` | this change |
| 2 | `janua-docs*` | after stage 1 admits cleanly |
| 3 | `janua-dashboard*`, `janua-admin*` | after stage 2 |
| 4 | `janua-api*`, then delete the file | last: highest blast radius |

**Check after each stage syncs.** Replace `janua-website` with the stage's
workload. The script refuses to answer until Argo has synced the shorter
exception.

```bash
ssh ssh.madfam.io 'bash -s' <<'EOF'
w=janua-website
k() { sudo -n kubectl "$@"; }
names=$(k -n janua get policyexception janua-gitops-rollout-signature -o jsonpath='{.spec.match.any[0].resources.names}')
case "$names" in *"$w"*) echo "NOT SYNCED: the exception still lists $w; sync janua-services and rerun"; exit 1;; esac
img=$(k -n janua get deploy "$w" -o jsonpath='{.spec.template.spec.containers[0].image}')
out=$(k -n janua run "$w-verify" --restart=Never --dry-run=server -o name --image="$img" 2>&1)
if echo "$out" | grep -q verify-image-signatures; then echo "SIGNATURE-FAIL: revert this stage"; else echo "OK: $w is signature-checked and its image passes"; fi
echo "$out" | tail -3
EOF
```

A bare test pod may also be refused by `drop-all-capabilities`. That is expected
and does not affect the signature verdict.

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

**Symptoms:** `drift-check.yml`, `sync-prod-gitops.yml` on a GitHub-hosted runner (`ubuntu-24.04`) log
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
| `.github/workflows/sync-prod-gitops.yml` | Break-glass apply of `main`'s overlay + GHCR refresh |
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
