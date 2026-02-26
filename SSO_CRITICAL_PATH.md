# SSO Critical Path — MADFAM Platform Verification

**Created**: 2026-02-26
**Status**: In progress — 3 of 7 fixes merged, 4 remaining
**Branch**: `fix/sso-verification-failures` (merged to `main`)

---

## Summary

Browser-based verification of Janua SSO login across all MADFAM platforms revealed 7 issues. Fixes 1-3 are merged into `madfam-org/janua` main. Fixes 4-7 require action in other repos or production ops.

| # | Fix | Status | Owner Repo |
|---|-----|--------|------------|
| 1 | Register missing OAuth clients (seed script) | Merged — **needs prod seed run** | `janua` |
| 2 | Cookie domain for cross-subdomain SSO | Merged — **needs `COOKIE_DOMAIN` env var** | `janua` |
| 3 | Add missing storage config attributes | Merged | `janua` |
| 4 | Dhanam CORS | **TODO** | `dhanam` |
| 5 | Yantra4D AuthButton env vars | **TODO** | `yantra4d` |
| 6 | Dashboard social buttons deployment | **TODO** (deploy only) | `janua` |
| 7 | Tezca auth UI | **Deferred** | `tezca` |

---

## Merged Fixes (Janua repo)

### Fix 1: Register Missing OAuth Clients

**Commit**: `97a0d2b1` (in merge `9482dfc2`)
**Files**: `apps/api/scripts/seed_ecosystem_clients.py`

The seed script now includes pre-assigned `client_id` values for Dispatch, Switchyard, and Dhanam that match what those apps already have deployed. Redirect URIs are corrected to match actual production callback paths.

**Required production action**:

```bash
# 1. Port-forward to production Postgres
kubectl port-forward svc/janua-postgres -n janua 5432:5432

# 2. Run seed script
cd apps/api
DATABASE_URL=postgresql://<user>:<pass>@localhost:5432/janua \
  python scripts/seed_ecosystem_clients.py

# 3. SAVE the printed client_secret values immediately — they cannot be retrieved later

# 4. Update K8s secrets for each consumer app:
#    - enclii-dispatch: set JANUA_CLIENT_SECRET in enclii namespace
#    - dhanam-web: set JANUA_CLIENT_SECRET in dhanam namespace
#    - enclii-switchyard: already has its secret; verify it matches
```

### Fix 2: Cookie Domain for Cross-Subdomain SSO

**Files**: `apps/api/app/routers/v1/auth.py`

Added `settings.COOKIE_DOMAIN` to `set_cookie()` calls in the `/signin` form-login endpoint. Without this, cookies are scoped to `api.janua.dev` and can't be read by `app.janua.dev` or `admin.janua.dev`.

**Required production action**: Verify `COOKIE_DOMAIN=.janua.dev` is set in the janua-api K8s deployment env. It's already in `.env.example` but must be present in production.

### Fix 3: Storage Config Attributes

**Files**: `apps/api/app/config.py`

Added `STORAGE_ENABLED`, `STORAGE_BUCKET_NAME`, `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY` to the Settings class. These are referenced by the admin health endpoint (`admin.py:238`) and previously caused `AttributeError` on the System Health page.

**No production action required** — defaults to disabled.

---

## Remaining Fixes

### Fix 4: Dhanam CORS

**Repo**: `madfam-org/dhanam`
**Impact**: Unblocks Dhanam email/password login (independent of SSO)
**Effort**: Config change only — no code change needed

**Problem**: The `CORS_ORIGINS` env var in the Dhanam production K8s deployment doesn't include `https://app.dhan.am`. The Dhanam API (`apps/api/src/main.ts`, lines 93-99) rejects preflight requests from the frontend.

**Fix**:

```bash
# Option A: Edit K8s configmap/secret directly
kubectl edit configmap dhanam-api-config -n dhanam
# Add https://app.dhan.am to CORS_ORIGINS

# Option B: Update the deployment env
kubectl set env deployment/dhanam-api -n dhanam \
  CORS_ORIGINS="https://app.dhan.am,https://dhan.am,http://localhost:3000"
```

**Verify**: `curl -I -X OPTIONS https://api.dhan.am/... -H "Origin: https://app.dhan.am"` should return `Access-Control-Allow-Origin: https://app.dhan.am`.

---

### Fix 5: Yantra4D AuthButton Crash

**Repo**: `madfam-org/yantra4d`
**Impact**: Fixes "Iniciar sesion" button crash on 4d-app.madfam.io
**Effort**: Config change only — no code change needed

**Root cause**: `VITE_JANUA_BASE_URL` GitHub Actions secret is empty/missing. The build produces an image where `AuthProvider.jsx` falls back to `AuthBypassProvider`, whose `signInWithOAuth` is a no-op that crashes in minified code.

**Fix**:

1. Go to `github.com/madfam-org/yantra4d` > Settings > Secrets and variables > Actions
2. Set repository secrets:
   - `JANUA_BASE_URL` = `https://auth.madfam.io`
   - `JANUA_CLIENT_ID` = the client_id from the seed script for `yantra4d-studio`
3. Re-trigger the deploy workflow to rebuild the Docker image with correct env vars

**Verify**: Visit `https://4d-app.madfam.io`, click "Iniciar sesion" — should redirect to Janua login instead of crashing.

---

### Fix 6: Dashboard Social Buttons Deployment

**Repo**: `madfam-org/janua` (deploy only)
**Impact**: Social login buttons (Google, GitHub, etc.) appear on dashboard login page
**Effort**: Zero code changes — just trigger a deploy

**Root cause**: Commit `8ae92134` added social provider buttons to the dashboard, but the production image predates this commit. The current deployed digest (`f6743bbe`) was built before the social login code was merged.

**Fix**:

```bash
# Trigger a new build + deploy for janua-dashboard
# Either push a tag, or manually trigger the docker-publish workflow:
gh workflow run docker-publish.yml -f service=janua-dashboard
```

**Verify**: Visit `https://app.janua.dev/login` — Google/GitHub/Microsoft buttons should appear below the email/password form.

---

### Fix 7: Tezca Auth UI (Deferred)

**Repo**: `madfam-org/tezca`
**Impact**: Optional — Tezca is a public legal research site that works without auth
**Effort**: Small frontend change when needed

**Current state**: The `@janua/nextjs` SDK is integrated in `apps/web` and K8s secrets reference `WEB_JANUA_PUBLISHABLE_KEY`, but no sign-in button exists in the navbar. This appears intentional for the current public-access MVP.

**Fix when ready**: Add a `<SignInButton />` or equivalent to the Tezca navbar component. Only needed when Tezca requires user accounts (e.g., saved searches, bookmarks, premium content).

---

## Verification Checklist

After completing all fixes, re-run browser verification for each platform:

- [ ] **Janua Dashboard** (app.janua.dev) — email/pass login + social buttons visible
- [ ] **Janua Admin** (admin.janua.dev) — navigate from Dashboard without "Access Denied"
- [ ] **Enclii Switchyard** (app.enclii.dev) — OIDC login via Janua
- [ ] **Enclii Dispatch** (admin.enclii.dev) — OIDC login via Janua (after seed + secret deploy)
- [ ] **Dhanam** (app.dhan.am) — SSO login via Janua (after CORS fix + seed)
- [ ] **Yantra4D Studio** (4d-app.madfam.io) — "Iniciar sesion" redirects to Janua (after env fix)
- [ ] **Tezca** (tezca.mx) — N/A until auth UI is added

---

## Dependency Graph

```
Fix 1 (seed script) ──┬──> Fix 4 (Dhanam CORS) ──> Dhanam SSO works
                       │
                       ├──> Enclii Dispatch SSO works (after K8s secret update)
                       │
                       └──> Fix 5 (Yantra4D env) ──> Yantra4D auth works

Fix 2 (cookie domain) ──> Janua Admin cross-subdomain SSO works

Fix 3 (storage config) ──> Admin health endpoint stops crashing

Fix 6 (dashboard deploy) ──> Social buttons visible (independent)

Fix 7 (Tezca UI) ──> Deferred (independent)
```

Fix 1 is the critical bottleneck — it must be run before Dispatch, Dhanam, or Yantra4D can complete SSO.
