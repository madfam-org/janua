# Browser-Based Auth Audit: MADFAM Ecosystem

**Date**: 2026-03-05
**Auditor**: Automated (Claude Code + Playwright MCP)
**Branch**: `feature/cross-sdk-upgrade`
**Scope**: 12 surfaces across 8 domains
**Context**: Post zero-touch agnosticism changes (middleware consolidation, seed script expansion, CSP dynamic host)

---

## Executive Summary

Audited 12 auth-gated surfaces across the MADFAM ecosystem using real browser interaction. **8 of 12 surfaces are functional**, with 2 unreachable and 2 experiencing auth flow failures. Found **2 critical**, **4 high**, and **5 medium** severity issues. Most critical: tokens exposed in URL on Enclii OAuth callback, and missing security headers on Tezca/Forgesight.

---

## Per-Surface Results

### Legend
- ✅ Pass | ❌ Fail | ⚠️ Partial | ⏭️ Skip (N/A) | 🔴 Unreachable

| # | Surface | Unauth Redirect | Login Flow | Auth Access | Logout | Security Headers | Open Redirect | Overall |
|---|---------|----------------|------------|-------------|--------|-----------------|---------------|---------|
| 1 | Janua API | ⏭️ (API) | ✅ 200 + tokens | ✅ | ⏭️ | ✅ Full | ✅ Safe | ✅ |
| 2 | Janua Dashboard | ✅ → `/login` | ✅ Cookie set | ✅ | ✅ | ⚠️ Missing fonts CSP | ✅ Safe | ⚠️ |
| 3 | Janua Admin | ✅ → `/login` | ✅ Cookie set | ✅ | ⚠️ 500 on API | ⚠️ Inconsistent | ⏭️ | ⚠️ |
| 4 | Janua Docs | ⏭️ (Public) | ⏭️ | ⏭️ | ⏭️ | ✅ | ⏭️ | ✅ |
| 5 | Janua Website | ⏭️ (Public) | ⏭️ | ⏭️ | ⏭️ | ✅ | ⏭️ | ✅ |
| 6 | Dhanam App | ✅ → `/login` | ❌ API blocked | ❌ | ⏭️ | ✅ | ⏭️ | ❌ |
| 7 | Enclii Switchyard | ⚠️ Shell leaks | ✅ via Janua SSO | ✅ | ⏭️ | ⚠️ Dev artifacts | ⏭️ | ⚠️ |
| 8 | Pravara MES | 🔴 Unreachable | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 | 🔴 |
| 9 | Tezca | ⏭️ (Public) | ⏭️ | ⏭️ (`/cuenta` = 404) | ⏭️ | ❌ ALL MISSING | ⏭️ | ❌ |
| 10 | Forgesight Landing | ⏭️ (Public) | ⏭️ | ⏭️ | ⏭️ | ❌ ALL MISSING | ⏭️ | ❌ |
| 10b | Forgesight App | ✅ → `/sign-in` | ❌ CORS blocks auth | ❌ | ⏭️ | ⏭️ | ⏭️ | ❌ |
| 11 | Yantra4D Landing | ⏭️ (Public) | ⏭️ | ⏭️ | ⏭️ | ⚠️ Dev artifacts | ⏭️ | ⚠️ |
| 11b | Yantra4D App | ⏭️ (Public tool) | ⏭️ | ⏭️ | ⏭️ | ⏭️ | ⏭️ | ✅ |
| 12 | Dhanam Admin | ⏭️ (Deprecated) | ⏭️ | ⏭️ | ⏭️ | ⏭️ | ⏭️ | ⏭️ |

---

## Security Findings

### 🔴 CRITICAL

#### C-1: Tokens Exposed in URL — Enclii OAuth Callback

**Surface**: `app.enclii.dev`
**Severity**: CRITICAL
**OWASP**: A07:2021 – Identification and Authentication Failures

After completing Janua SSO login for Enclii, the callback URL contains the full `access_token`, `refresh_token`, AND `idp_token` as query parameters:

```
https://app.enclii.dev/auth/callback?access_token=eyJ...&refresh_token=eyJ...&idp_token=eyJ...
```

**Impact**: Tokens leak via:
- Browser history (persistent)
- Server access logs
- `Referer` headers on subsequent navigation
- Shared/bookmarked URLs
- Browser extensions with URL access

The `idp_token` contains a full Janua JWT with `is_admin: true`, user roles, tier info, and scopes — highly sensitive data in a URL.

**Recommendation**: Switch to authorization code flow. The callback should receive a one-time `code` parameter, which the backend exchanges for tokens server-side.

---

#### C-2: Missing ALL Security Headers — Tezca & Forgesight

**Surface**: `tezca.mx`, `forgesight.quest`
**Severity**: CRITICAL
**OWASP**: A05:2021 – Security Misconfiguration

Both surfaces return **zero** security headers:

| Header | tezca.mx | forgesight.quest |
|--------|----------|-----------------|
| `Strict-Transport-Security` | MISSING | MISSING |
| `X-Content-Type-Options` | MISSING | MISSING |
| `X-Frame-Options` | MISSING | MISSING |
| `Content-Security-Policy` | MISSING | MISSING |

**Impact**: Vulnerable to clickjacking, MIME-type sniffing, protocol downgrade, and XSS without CSP mitigation.

**Recommendation**: Add security headers via Next.js `next.config.js` headers config or middleware. Both are Next.js apps deployed on Cloudflare — headers should be set at the app layer since Cloudflare Tunnel doesn't add them automatically.

---

### 🟠 HIGH

#### H-1: Auth Flow Broken — Dhanam App

**Surface**: `app.dhan.am`
**Severity**: HIGH

Login submit triggers API call to `api.dhan.am/v1/auth/signin` which is blocked. Console shows CSP violation despite `connect-src` header including `https://api.dhan.am/v1`. Error: "An error occurred. Please try again."

**Impact**: Users cannot authenticate to Dhanam. The app is effectively non-functional.

**Root Cause**: Likely CORS misconfiguration on `api.dhan.am` (not returning `Access-Control-Allow-Origin` for `app.dhan.am`), or the API service itself is not responding correctly.

**Recommendation**: Verify CORS configuration on the Dhanam API. Check that `api.dhan.am` returns appropriate CORS headers for requests from `app.dhan.am`.

---

#### H-2: Auth Flow Broken — Forgesight App

**Surface**: `app.forgesight.quest`
**Severity**: HIGH

Login page loads but calls to `auth.madfam.io/api/v1/auth/me` fail repeatedly with CORS errors (8 consecutive failures visible in console): "Access to fetch at 'https://auth.madfam.io...' has been blocked by CORS policy."

**Impact**: Users cannot authenticate to Forgesight App.

**Recommendation**: Add `app.forgesight.quest` to the CORS `allowed_origins` list on the Janua API (`auth.madfam.io`).

---

#### H-3: Logout Endpoint Returns 500 — Janua API

**Surface**: `admin.janua.dev` → `api.janua.dev`
**Severity**: HIGH

When signing out from Janua Admin, the `POST /api/v1/auth/logout` endpoint returns HTTP 500. Client-side cookies are cleared correctly, but server-side session invalidation fails.

**Impact**: Server-side sessions may accumulate and never be properly invalidated, potentially allowing session reuse. The "21 Active Sessions" count observed in Admin dashboard may be inflated by un-invalidated sessions.

**Recommendation**: Debug the logout endpoint. Check for missing session in database or Redis connection issues.

---

#### H-4: Enclii Dashboard Shell Exposed Without Auth

**Surface**: `app.enclii.dev`
**Severity**: HIGH
**OWASP**: A01:2021 – Broken Access Control

Visiting `app.enclii.dev` without cookies renders the full dashboard shell: navigation bar (Dashboard, Projects, Services, Deployments, Observability, Templates, Databases), search, notifications, and footer. No data is populated, but the application structure is fully visible.

**Impact**: Reveals the full feature set and navigation structure to unauthenticated users, aiding reconnaissance. Client-side auth check happens too late — the SPA renders its chrome before redirecting.

**Recommendation**: Implement server-side auth check via Next.js middleware or route guards that prevent the shell from rendering. Return a redirect response before the SPA loads.

---

### 🟡 MEDIUM

#### M-1: Cookie `Secure` Flag Missing — Janua Admin

**Surface**: `admin.janua.dev`
**Severity**: MEDIUM

All three admin cookies lack the `Secure` flag:

| Cookie | HttpOnly | Secure | SameSite |
|--------|----------|--------|----------|
| `janua_token` | false | **false** | Strict |
| `janua_admin_email` | false | **false** | Strict |
| `janua_admin_roles` | false | **false** | Strict |

**Impact**: On an HTTPS site, cookies without `Secure` flag could theoretically be sent over downgraded HTTP connections. The `SameSite=Strict` mitigates some attack vectors.

**Recommendation**: Set `Secure: true` on all cookies when deployed on HTTPS.

---

#### M-2: CSP Blocks Swagger UI — Janua API `/docs`

**Surface**: `api.janua.dev/docs`
**Severity**: MEDIUM

The API's CSP (`default-src 'self'; script-src 'self'; ...`) blocks all resources needed by Swagger UI:
- `cdn.jsdelivr.net` (scripts, styles)
- `fastapi.tiangolo.com` (images)
- Inline scripts

The OpenAPI documentation page is completely non-functional in production.

**Recommendation**: Either add Swagger UI CDN origins to CSP for the `/docs` route, or bundle Swagger UI assets locally and serve from `'self'`.

---

#### M-3: Development Artifacts in Production CSP

**Surface**: `app.enclii.dev`, `4d.madfam.io`
**Severity**: MEDIUM

| Surface | CSP Directive | Dev Artifact |
|---------|--------------|-------------|
| Enclii | `connect-src` | `http://localhost:4200` |
| Yantra4D | `default-src` | `http://localhost:*` |
| Yantra4D | `frame-src` | `http://localhost:*` |
| Yantra4D | `connect-src` | `http://localhost:*`, `ws://localhost:*` |

**Impact**: Weakens CSP by allowing connections to local development servers. An attacker running a local server on a compromised machine could exfiltrate data via these allowed origins.

**Recommendation**: Use environment-based CSP configuration. Strip `localhost` entries in production builds.

---

#### M-4: HSTS `preload` Inconsistency

**Surface**: Cross-surface
**Severity**: MEDIUM

| Surface | HSTS Value |
|---------|-----------|
| api.janua.dev | `max-age=31536000; includeSubDomains; preload` ✅ |
| app.janua.dev | `max-age=31536000; includeSubDomains` (no `preload`) |
| admin.janua.dev | `max-age=31536000; includeSubDomains` (no `preload`) |
| docs.janua.dev | `max-age=31536000; includeSubDomains` (no `preload`) |
| app.enclii.dev | `max-age=31536000; includeSubDomains; preload` ✅ |
| app.dhan.am | `max-age=63072000; includeSubDomains; preload` ✅ |

**Recommendation**: Standardize HSTS across all surfaces. Add `preload` to all Janua subdomains and submit to the HSTS preload list.

---

#### M-5: CSP Font-Source Inconsistency — Janua Dashboard vs Admin

**Surface**: `app.janua.dev`, `admin.janua.dev`
**Severity**: MEDIUM

Dashboard CSP: `font-src 'self'` — blocks Google Fonts (console errors visible)
Admin CSP: `font-src 'self' data: https://fonts.gstatic.com` — allows Google Fonts ✅

Both apps appear to use Google Fonts but only Admin's CSP permits them.

**Recommendation**: Align CSP `font-src` directives. Either allow Google Fonts on both or bundle fonts locally for both.

---

## Service Availability

| Surface | Status |
|---------|--------|
| Pravara MES (`mes.madfam.io`) | 🔴 **Unreachable** — DNS resolution fails or service not running |
| Dhanam Admin (`admin.dhan.am`) | ⚠️ **Deprecated** — Shows deprecation notice, functionality moved to main app |

---

## Security Headers Matrix

| Surface | HSTS | XCTO | XFO | CSP | Referrer | Permissions |
|---------|------|------|-----|-----|----------|-------------|
| api.janua.dev | ✅ +preload | ✅ nosniff | ✅ DENY | ✅ | ✅ strict-origin | ✅ |
| app.janua.dev | ✅ | ✅ nosniff | ✅ DENY | ✅ | ✅ strict-origin | ✅ |
| admin.janua.dev | ✅ | ✅ nosniff | ✅ DENY | ✅ | ✅ strict-origin | ✅ |
| docs.janua.dev | ✅ | ✅ nosniff | ✅ DENY | ✅ | ✅ strict-origin | ✅ |
| janua.dev | ✅ | ✅ nosniff | ✅ DENY | ✅ | ✅ strict-origin | ✅ |
| app.dhan.am | ✅ +preload | ✅ nosniff | ✅ DENY | ✅ | ✅ strict-origin | ✅ |
| app.enclii.dev | ✅ +preload | ✅ nosniff | ✅ DENY | ⚠️ localhost | ✅ strict-origin | ❌ MISSING |
| tezca.mx | ❌ MISSING | ❌ MISSING | ❌ MISSING | ❌ MISSING | ❌ MISSING | ❌ MISSING |
| forgesight.quest | ❌ MISSING | ❌ MISSING | ❌ MISSING | ❌ MISSING | ❌ MISSING | ❌ MISSING |
| 4d.madfam.io | ❌ MISSING | ✅ nosniff | ⚠️ SAMEORIGIN | ⚠️ localhost | ❌ MISSING | ❌ MISSING |

---

## Cookie Security Matrix

| Surface | Cookie Name | HttpOnly | Secure | SameSite |
|---------|------------|----------|--------|----------|
| app.janua.dev | `janua_token` | ❌ | ❌ | — |
| admin.janua.dev | `janua_token` | ❌ | ❌ | Strict |
| admin.janua.dev | `janua_admin_email` | ❌ | ❌ | Strict |
| admin.janua.dev | `janua_admin_roles` | ❌ | ❌ | Strict |
| app.enclii.dev | `enclii_auth` | ❌ | ✅ | Lax |

**Note**: `janua_token` cookies are intentionally not `HttpOnly` to allow client-side SPA access for API calls. This is an accepted trade-off for SPA architecture but increases XSS impact.

---

## Recommendations Priority

### Immediate (before next deploy)
1. **C-1**: Switch Enclii to authorization code flow — tokens must not be in URLs
2. **H-3**: Fix `/api/v1/auth/logout` 500 error — sessions not being invalidated

### Short-term (this sprint)
3. **C-2**: Add security headers to Tezca and Forgesight via `next.config.js`
4. **H-1**: Debug Dhanam API CORS/connectivity issue
5. **H-2**: Add `app.forgesight.quest` to Janua API CORS allowed origins
6. **H-4**: Add server-side auth redirect to Enclii (Next.js middleware)
7. **M-2**: Fix CSP for Swagger UI on `/docs` endpoint (allow CDN or bundle locally)

### Medium-term (next sprint)
8. **M-1**: Set `Secure: true` on all admin cookies
9. **M-3**: Remove `localhost` entries from production CSP configs
10. **M-4**: Standardize HSTS with `preload` across all surfaces
11. **M-5**: Align CSP `font-src` between Dashboard and Admin

### Investigation needed
12. Pravara MES unreachable — check DNS and service deployment
13. Verify Dhanam Admin deprecation is intentional and old DNS can be removed

---

## Methodology

- **Tool**: Playwright MCP via Claude Code (Chromium browser automation)
- **Approach**: Real browser navigation, form interaction, cookie inspection, header analysis
- **Credentials**: Test admin account (not included in report)
- **Coverage**: All 12 planned surfaces visited; 10 accessible, 2 unreachable
- **Limitations**:
  - Single browser session (no cross-browser testing)
  - No automated scanner (manual probe-based)
  - Pravara MES could not be tested (unreachable)
  - Cross-app token reuse test not performed (would require manual cookie manipulation across domains, blocked by browser security)

---

*Report generated 2026-03-05 by automated audit pipeline*
