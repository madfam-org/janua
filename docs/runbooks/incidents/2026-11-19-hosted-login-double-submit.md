# Incident: hosted sign-in answered a double submit with raw JSON (2026-11-19)

> **Status:** Fix in review (janua#841); production fix ships as a hotfix image
> (`deployment/hotfix/README.md`) once merged and approved.
> **Severity:** P2 (sign-in worked on a later attempt; no data exposure, no outage)
> **Window observed:** 2026-11-19 18:05–18:07 UTC in production logs; the pattern
> is older than that window.
> **Operator runbook:** [oauth-shared-state-redis.md](../oauth-shared-state-redis.md#a-sign-in-that-lands-on-request-expired)

---

## Summary

Staff of a client product signing in with email and password on the hosted
login page (`POST /api/v1/auth/login-form`) sometimes landed on a bare JSON body:

```json
{"error": {"code": "HTTP_ERROR", "message": "La solicitud de acceso venció. Vuelve al MAP para iniciar.", ...}}
```

Refreshing asked to resubmit the form and showed the same body. After several
tries the person got in. It was reported as a Janua outage; it was not one.
Health, readiness, discovery and JWKS answered 200, both API pods had no
restarts, and there were no 5xx responses in the six hours before.

## Root cause

A double submit.

1. The first `POST /login-form` read `oauth:pre_login:<id>` (`redis_hit`),
   hashed the password (about 1.3 s), created a session, **deleted** the
   pending-request key and answered 302 to `/oauth/authorize`.
2. Before the browser followed that 302, the person pressed the button again (or
   Enter). The browser cancelled the first navigation and sent a second POST with
   the same `auth_request_id`, 2–3 s after the first. The logs show no GET of the
   first 302 in between.
3. The second POST found the key gone (`redis_miss`), logged
   `redis_miss_oauth_recovered`, and then called
   `app/auth/tenant_login_context.py: login_client_context`, which read the key
   strictly and raised `HTTPException(400, "La solicitud de acceso venció…")`.
   The API's exception handler rendered it as the JSON error envelope.
4. A refresh re-POSTed the same form and got the same answer.

`login_form` had a branch that promised an HTML "session expired" page for a
missing request, but the strict read in `login_client_context` raised before it
was reached. The button stayed live during the password hash, so nothing stopped
the second press.

The first reading of these log lines, during the outage check, took them for
harmless resubmits after a successful sign-in. They were the failure.

## Fix (janua#841)

- `login_client_context` raises `LoginRequestExpired` (a subclass of the same
  400) for a missing pending request; every other caller behaves as before.
- `login_form` reads the pending request once. When it is gone:
  - credentials are still checked against the registered, active client the form
    names (its identity pool, lockout, account status, password, failed-attempt
    counting). On success the browser gets a new session and a **303** to that
    client's registered origin, which starts a fresh authorize request that the
    session completes. The person lands in the product.
  - when a second factor is required, or no registered client can restart the
    flow, nothing is checked or issued, and the browser gets a 303 to
    **GET `/api/v1/auth/login-expired`**: a page (Spanish with `ui_locales=es`,
    `Cache-Control: no-store`) with one button to the client's registered origin.
    A refresh there is a GET.
- Every hosted form (password, magic link, MFA, forgot and reset password) loads
  the same-origin script `GET /api/v1/auth/hosted-form.js`, which disables the
  button after the first submit and announces the busy label («Entrando…») in a
  `role="status"` region. It re-enables on a back/forward-cache restore or after
  20 s. Without script the forms behave as before, and the server side above
  still holds.

Tests: `apps/api/tests/unit/routers/test_login_form_request_gone.py`.

## What the person should do until the fix is live

Type the password and press «Entrar» once; it takes a second or two. If the
"request expired" message appears, do not refresh: open the product again from
its address and sign in.

## Follow-ups

The general hardening of browser-facing auth flows against this class of edge
case (back/refresh, two tabs, a page left open past the 10-minute pre-login TTL,
Redis loss, magic links opened on another device or prefetched by scanners) is
tracked as a dated section in [ROADMAP.md](../../ROADMAP.md).
