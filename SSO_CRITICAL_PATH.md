# SSO Critical Path — MADFAM Platform Verification

> [!IMPORTANT]
> MADFAM-ENCLII-FIRST-LEGACY-RAW v1: This document contains legacy raw infrastructure command examples.
> Routine production operations must use Enclii web, API, or CLI. Treat raw
> `kubectl`, `helm`, SSH, provider CLI/API, `docker exec`, and direct container
> access as platform bootstrap or documented break-glass only, and record any
> missing Enclii adapter gap.


**Created**: 2026-02-26
**Status**: In progress — 4 of 8 fixes merged (Fix 8 admin login also promoted to
prod), 4 remaining. The "Sign in with Janua" OIDC rewire (Fix 8 follow-up) is
implemented in PR #447 — needs the 3-step go-live sequence below (seed → env
vars → merge).
**Branch**: `fix/sso-verification-failures` (merged to `main`);
`claude/janua-sso-oidc-rewire` (PR #447 — the OIDC rewire)

---

## Summary

Browser-based verification of Janua SSO login across all MADFAM platforms revealed 7 issues. Fixes 1-3 are merged into `madfam-org/janua` main. Fixes 4-7 require action in other repos or production ops. Fix 8 (admin.janua.dev login) was found and fixed separately on 2026-07-08 — merged and promoted to production.

| # | Fix | Status | Owner Repo |
|---|-----|--------|------------|
| 1 | Register missing OAuth clients (seed script) | Merged — **needs prod seed run** | `janua` |
| 2 | Cookie domain for cross-subdomain SSO | Merged — **needs `COOKIE_DOMAIN` env var** | `janua` |
| 3 | Add missing storage config attributes | Merged | `janua` |
| 4 | Dhanam CORS | **TODO** | `dhanam` |
| 5 | Yantra4D AuthButton env vars | **TODO** | `yantra4d` |
| 6 | Dashboard social buttons deployment | **TODO** (deploy only) | `janua` |
| 7 | Tezca auth UI | **Deferred** | `tezca` |
| 8 | Admin login — broken `enableJanuaSSO` → email/password | **Merged + Promoted** | `janua` |
| 8b | "Sign in with Janua" OIDC rewire + env-var wiring (Fix 8 follow-up) | Implemented in **PR #447** — needs seed + env vars + merge | `janua` |

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

### Fix 8: Admin Login — Broken `enableJanuaSSO` Replaced with Email/Password

**Commit**: `d4ae513` (PR #445, merged to `main`)
**Promoted to prod**: `51ac8b6` (`deploy(prod): promote`) — prod overlay `janua-admin` pin `sha256:8568baa4…`; `admin.janua.dev` is live on the fixed build.
**Files**: `apps/admin/app/login/page.tsx`

**Problem**: `admin.janua.dev/login` was configured SSO-only (`showEmailPassword={false}`, `socialProviders={{}}`, `enableJanuaSSO={true}`). Its only control was a "Sign in with Janua" button that called `januaClient.auth.initiateOAuth('janua')`, which posts to the **social**-OAuth endpoint `POST /api/v1/auth/oauth/authorize/janua`. But `janua` is not a valid social provider — the `OAuthProvider` enum is `google/github/microsoft/apple/discord/twitter/linkedin/slack` — so the API returned `400 "Invalid provider: janua"`. Admin login was impossible.

**Fix**: Dropped `enableJanuaSSO` and set `showEmailPassword=true`. Admin operators now authenticate directly against Janua via email/password (`januaClient.auth.signIn`), matching the working `apps/dashboard` pattern. The `@janua.dev` / `@madfam.io` domain + `admin`/`superadmin` role gate (`lib/auth.tsx` + middleware) is unchanged.

**No further production action required** — merged and already promoted.

> [!WARNING]
> **TODO — open follow-up in `@janua/ui` (NOT yet fixed):** The underlying defect lives in the shared UI package. Both `enableJanuaSSO` (`packages/ui/src/components/auth/sign-in.tsx`) and `JanuaSSOLoginButton` (`packages/ui/src/components/auth/janua-sso-button.tsx`) push `'janua'` onto the **social**-OAuth path (`initiateOAuth('janua')`) instead of Janua's **OIDC provider** authorize endpoint (`GET /api/v1/oauth/authorize?client_id=…&response_type=code`). A real "Sign in with Janua" button for other ecosystem apps must use the OIDC flow with a registered `client_id` (ties into **Fix 1** above). **Any app still rendering that button has the same broken login.** The admin fix side-steps this by using email/password rather than repairing the button.
>
> Also worth noting (orthogonal): `GET /api/v1/auth/oauth/providers` returns `[]` in prod because the social-provider env vars are unset.

---

## "Sign in with Janua" OIDC rewire (Fix 8 follow-up — PR #447)

**Repo**: `madfam-org/janua` · **Branch**: `claude/janua-sso-oidc-rewire` (draft PR #447)

### What #447 changes (already implemented)

The old "Sign in with Janua" button routed `janua` through the **social** OAuth
path (`initiateOAuth('janua')`), which the API rejects with `400 "Invalid
provider: janua"`. #447 rewires the button to Janua's **OIDC provider** flow:

- **SDK** (`@janua/typescript-sdk`): adds `initiateJanuaSSO` /
  `getJanuaAuthorizeUrl` / `handleJanuaSSOCallback` driving
  `GET /api/v1/oauth/authorize` + PKCE (S256).
- **UI** (`@janua/ui`): `SignIn` and `JanuaSSOLoginButton` now use the OIDC flow
  and **fail loud** — the button is not rendered and an error is logged when no
  `client_id` is available (instead of silently hitting the invalid social path).
- **Env-var wiring (zero per-app code)**: `januaClientId` defaults to
  `process.env.NEXT_PUBLIC_JANUA_CLIENT_ID` and `januaRedirectUri` to
  `process.env.NEXT_PUBLIC_JANUA_REDIRECT_URI` (falling back to
  `${origin}/auth/callback`). Threaded through `@janua/nextjs-sdk` `SignInForm`
  and the `madfamAuthConfig` preset (`packages/ui/src/config/madfam-preset.ts`).
  An explicit prop still overrides the env var. **Result: any ecosystem app gets
  a working button by setting one public env var — no code change.**

> `client_id` is a **public, PKCE-protected identifier** (OIDC), safe to commit,
> print, and put in `NEXT_PUBLIC_*`. It is **NOT a secret** — these are public
> clients with no `client_secret` (PKCE replaces it). Never confuse this with the
> confidential `jnc_*` clients + `client_secret`s from Fix 1.

### OIDC client seed (one operator command)

**File**: `apps/api/scripts/seed_oidc_clients.py` (idempotent upsert on `client_id`).

Registers each consuming app as a **first-party PUBLIC OIDC client** (public /
PKCE-required, `grant_types = authorization_code + refresh_token`, scopes
`openid profile email`, `redirect_uris` = the app's real `/auth/callback`):

| `client_id` (public) | App | Redirect URI |
|----------------------|-----|--------------|
| `dhanam-web` | Dhanam web | `https://app.dhan.am/auth/callback` |
| `enclii-switchyard` | Enclii Switchyard | `https://app.enclii.dev/auth/callback` |
| `enclii-dispatch` | Enclii Dispatch | `https://admin.enclii.dev/auth/callback` |
| `yantra4d-web` | Yantra4D studio | `https://app.yantra4d.com/auth/callback` (host resolved 2026-07-08: `app.yantra4d.com` is live; `4d-app.madfam.io` / `studio.yantra4d.com` do not resolve) |
| `tezca-web` | Tezca web | `https://tezca.mx/auth/callback` |
| `dashboard` | Janua dashboard | `https://app.janua.dev/auth/callback` |

Each entry also registers a localhost dev callback. The script prints the
`client_id → app → redirect_uri` map at the end (all public). It is **not** run
automatically — a prod DB write is an operator action.

### Operator go-live sequence (NO broken-button gap)

Run in this exact order so the button is functional the moment #447 merges:

**1. Seed the public OIDC clients against prod** (registers the `client_id`s above):

```bash
# Port-forward to production Postgres (break-glass; prefer Enclii DB access)
kubectl port-forward svc/janua-postgres -n janua 5432:5432

cd apps/api
DATABASE_URL=postgresql://<user>:<pass>@localhost:5432/janua \
  python scripts/seed_oidc_clients.py
# Idempotent — safe to re-run. Prints the client_id → app → redirect_uri map.
# No client_secret is printed: these are PUBLIC (PKCE) clients.
```

**2. Set `NEXT_PUBLIC_JANUA_CLIENT_ID` for each app (via Enclii)** to its
`client_id` from the table above (e.g. Dhanam → `dhanam-web`). Optionally set
`NEXT_PUBLIC_JANUA_REDIRECT_URI` if an app's callback differs from
`${origin}/auth/callback`. These are **public** build-time env vars — no secret
store required. This is the entire per-app change (no code).

**3. Merge PR #447.** Once the SDK/UI ship with steps 1–2 already in place, the
button works for every app on first load — no gap.

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
# Push a change under apps/dashboard/**, or dispatch the workflow.
# docker-publish.yml has no `service` input: a dispatch rebuilds all five services.
gh workflow run docker-publish.yml
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
