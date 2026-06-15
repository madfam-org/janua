# Incident: janua.dev website prod rollout (2026-06-15)

> **Status:** Resolved  
> **Severity:** P1 (public marketing site visually broken)  
> **Duration:** ~7 days git-correct / cluster-stale (promote merged ~2026-06-15; prod live ~2026-06-15 19:36 UTC)  
> **Operator runbook:** [production-gitops-reconcile.md](../production-gitops-reconcile.md)

---

## Summary

The Tailwind v4 / marketing-shell fix ([#419](https://github.com/madfam-org/janua/pull/419))
merged to `main` and was promoted to `k8s/overlays/production/kustomization.yaml`,
but **janua.dev continued serving a pre-fix image** until GHCR pull credentials
were refreshed and the deployment rolled.

Git was the source of truth; the cluster never successfully adopted the new
`janua-website` digest through three stacked infrastructure gates.

---

## User-visible impact

- **janua.dev** rendered unstyled (Tailwind utilities not compiled)
- Broken CTAs, stacked layout, no grid on `/pricing`
- Old footer links (Playground, Education, Press Kit) still visible
- `/pricing` missing shared nav/footer from `(marketing)` layout

---

## Root cause (three layers)

### Layer 1 — Application (#419)

`apps/website/styles/globals.css` used Tailwind **v3** directives
(`@tailwind base/components/utilities`) with **Tailwind v4** PostCSS
(`@tailwindcss/postcss`). Utility classes never compiled.

**Fix (merged):** Migrate to `@config` + `@import "tailwindcss"`; add
`(marketing)` route group with shared `Navigation` + `Footer`; fix anchor
targets, banner/theme spacing, footer dead links, PostHog CSP.

### Layer 2 — GitOps / Kyverno

Argo CD Application **`janua-services`** remained `OutOfSync` on
`janua-website`. Sync attempts failed:

```text
verify-image-signatures / autogen-check-signature:
  failed to verify image ghcr.io/madfam-org/janua-website@sha256:1af203d...
  GET https://ghcr.io/token?scope=repository%3Amadfam-org%2Fjanua-website%3Apull
  DENIED: denied
```

Kyverno could not pull the private GHCR manifest to verify cosign signatures.

**Fix (merged `dbc23614`):** `k8s/overlays/production/kyverno-policy-exception.yaml`
— scoped PolicyException (same pattern as Dhanam `dhanam-gitops-rollout-signature`).

### Layer 3 — Image pull credentials

After PolicyException landed, a new pod was scheduled but **`janua/ghcr-credentials`
was stale**. Pull failed with `403 Forbidden`. The May 2026 pod
(`sha256:57498543…`) kept serving traffic.

Copying `ghcr-credentials` from `dhanam` was insufficient (token lacked
`janua-website` package scope).

**Fix (ops):** Enclii workflow `rotate-ghcr-namespace.yml` on `madfam-org/enclii`
refreshed `janua/ghcr-credentials` with `madfam-bot` + `GHCR_PAT`, then
`kubectl rollout restart deployment/janua-website`.

---

## Secondary friction

| Issue | Detail |
|-------|--------|
| Wrong Argo app name in docs/runbooks | App is `janua-services`, not `janua` |
| `KUBECONFIG_PRODUCTION` unreachable from GH-hosted runners | External apiserver IP connection refused; ARC + in-cluster API repoint required |
| `promote-to-prod` soak gate | First promote blocked until `break_glass_without_soak` (#420) |
| Promote checkout auth | Fixed #421 — use `GITHUB_TOKEN` not expired bot PAT |
| Stuck Argo automated retry | Blocked manual `enclii ops apps sync` until operation cleared |

---

## Changes merged

### janua (`madfam-org/janua`)

| PR / commit | Description |
|-------------|-------------|
| [#419](https://github.com/madfam-org/janua/pull/419) | Website Tailwind v4 + marketing shell |
| [#420](https://github.com/madfam-org/janua/pull/420) | `break_glass_without_soak` on promote workflow |
| [#421](https://github.com/madfam-org/janua/pull/421) | Promote checkout token fix + prod digest seed |
| [#422](https://github.com/madfam-org/janua/pull/422) | `sync-prod-gitops.yml` break-glass workflow |
| `dbc23614` | Kyverno PolicyException for prod overlay |
| `071bef4a` … `336e6eaf` | Harden `sync-prod-gitops` (ARC, kubeconfig, GHCR copy) |

### enclii (`madfam-org/enclii`)

| Commit | Description |
|--------|-------------|
| `04e3296e` | `rotate-ghcr-namespace.yml` workflow_dispatch |

---

## Resolution timeline (2026-06-15 UTC)

1. **~18:32** — Docker Publish succeeded for #419; staging digest updated
2. **~19:14** — Prod kustomization had website digest `sha256:1af203d…`; Argo sync failed on Kyverno
3. **~19:22** — PolicyException merged; `enclii ops apps sync janua-services` submitted
4. **~19:25–19:34** — `sync-prod-gitops` iterations; ARC kubeconfig repoint fixed cluster connectivity
5. **~19:35** — Enclii **Rotate GHCR credentials** for `janua` namespace
6. **~19:36** — New pod healthy; janua.dev serving styled site with updated nav/footer

---

## Verification (post-fix)

- Home: styled hero, nav dropdowns, ecosystem banner, gradient CTAs
- `/pricing`: shared nav + footer; pricing grid layout
- Footer: **Live demo** (not Playground); no Education / Press Kit / Cookie Policy 404s
- CSS bundle includes `.flex{`, `.grid{` utilities

---

## Follow-up actions

| Priority | Action | Owner |
|----------|--------|-------|
| P1 | Add `GHCR_PAT` or `MADFAM_BOT_PAT` to janua repo; use `madfam-bot` in `docker-publish.yml` GHCR login | DevOps |
| P2 | Add `prod-post-promote.yml` (mirror Dhanam) — Enclii lifecycle callback + best-effort Argo refresh | Platform |
| P2 | Rotate or retire stale external `KUBECONFIG_PRODUCTION` secret; document ARC-only path | Platform |
| P3 | Kyverno long-term: public GHCR packages or registry creds for verify-image-signatures | Security |
| P3 | Phase 2 UX: typography beyond Inter, gradient cleanup, legal pages | Product |

---

## Lessons learned

1. **Git-correct ≠ live** — Always verify running pod digest vs
   `k8s/overlays/production/kustomization.yaml`.
2. **Check Argo app name** — `janua-services` in `argocd` namespace.
3. **Promote is necessary but not sufficient** — Pattern B requires explicit
   reconcile + rollout proof.
4. **GHCR pull secrets are part of deploy** — Digest promote without valid
   `ghcr-credentials` leaves old pods serving indefinitely with no obvious Argo error.
5. **Enclii-first** — `enclii ops apps sync` and namespace GHCR rotate workflows
   work; GitHub-hosted kubectl does not.

---

**Documented:** 2026-06-15
