# Hosted error page, repeated presses, refresh grace, change of sign-in address: hotfix image (owner exception)

**Status (2026-11-20): authored, not built or pinned.** Production runs row 13
(`janua-api@sha256:2bbee189…`, janua#843). The full list of what production
runs is in [`../README.md`](../README.md).

## Why

The edge-case hardening that followed the 2026-11-19 sign-in incident
([`docs/ROADMAP.md`](../../../docs/ROADMAP.md#browser-facing-auth-flows-edge-case-hardening-from-the-2026-11-19-incident))
merged to `main` as nine pull requests after row 13's source (`75dd0eea`):

- janua#844: `POST /api/v1/internal/users/change-email`, an internal-key route
  that changes a person's sign-in address and keeps the user id;
- janua#845: a browser navigation refused on a hosted route (login, second
  factor, recovery, magic-link callback, authorize, consent, logout) gets `303`
  to the new GET page `/api/v1/auth/error` instead of the raw JSON envelope;
  API and `fetch` callers keep the envelope; one `auth.hosted_refusal` log line
  per refusal;
- janua#846, janua#847, janua#848, janua#850: `AuthService`, `app/main.py`,
  `routers/v1/auth.py` and `routers/v1/oauth_provider.py` split under the
  800-line limit, no behaviour change;
- janua#851: slowapi's 429 on a browser navigation of a hosted route gets the
  same page («Too many attempts»);
- janua#853: a repeated press on the hosted second-factor, consent or reset form
  lands where the first press went (the reset lands on the new GET page
  `/api/v1/auth/reset-password/done`);
- janua#852: two refreshes of one session at once no longer revoke the family;
  a repeat of the rotated-away token within 30 s, same session only, gets the
  pair the first refresh issued (`REFRESH_REUSE_GRACE_SECONDS`, default 30;
  0 restores strict single use).

`promote-to-prod.yml` is held until isolated staging is proven
(`scripts/staging/promotion_runtime_guard.py`), and promoting `main` would ship
more than these nine merges (see "What stays out"). Nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:2bbee189…`) and adds nine layers:

1. `apps/api/app/` at `SOURCE` (`ae191e86`, janua#852's merge, the last of the
   nine). The workflow refuses to build when the checkout's `apps/api/app`
   differs from `SOURCE`'s, so a later merge cannot travel.
2. Seven layers that put back the base image's own copy of each file in
   [`kept_files.txt`](kept_files.txt) (`COPY --from` the base digest).
3. `routers/v1/oauth_provider_shared.py` from
   [`oauth_provider_shared.py.shipped`](oauth_provider_shared.py.shipped).

Relative to production that is **40 files: 30 added, 10 modified**, listed in
[`shipped_files.txt`](shipped_files.txt), and exactly what the nine merges
change (`git diff --name-status 592d61b9 ae191e86 -- apps/api/app`). No file is
removed, no migration changes, no package or setting is added (the only new
environment variable, `REFRESH_REUSE_GRACE_SECONDS`, defaults to 30).

Production's copy of every file the nine merges touch is row 13's source's,
except three small differences `main` already carried that travel inside files
the merges modify:

- **Not shipped:** janua#801's `roles` filter in `_get_user_entitlements`
  (`entitlements["roles"] = organization_roles_for_roles_claim(...)` instead of
  the set of membership roles). It changes what the `roles` claim contains and
  is not part of this release. After janua#850 it lives in
  `routers/v1/oauth_provider_shared.py`, which ships from the folder's
  `.shipped` copy: `main`'s file with production's three lines back
  ([`oauth_provider_shared.diff`](oauth_provider_shared.diff), one hunk; the
  now-unused import stays). Rows 11 and 12 used the same device for
  `oauth_provider.py`.
- **Carried along, inert:** the reworded comment next to the CIMD client check
  (now in `routers/v1/oauth_provider_resource_tokens.py`); the support address
  in the OpenAPI description and contact block, the old product domain replaced
  by the MADFAM one (now in `main_openapi.py`); three `Exemption(...)` entries in
  `mcp/coverage.py` for the internal primary-organization routes production
  already serves (row 9), which only the MCP coverage test reads.

### What stays out

Seven files differ between production and `main` from before row 13, no row
ever shipped them, and none of the nine merges touches them. They keep
production's copies, byte for byte:

- `core/test_config.py`
- `routers/v1/webhooks_dhanam.py`
- `services/admin_notifications.py`
- `services/email_service.py`
- `services/enhanced_email_service.py`
- `services/resend_email_service.py`
- `sso/application/services/product_tiers.py`

No shipped file imports a name that exists only in `main`'s copy of these
(every `from app… import …` resolves in the composed tree exactly as on
`main`), and no shipped file imports a third-party module that production's
code does not already import.

**Effect:** discovery, the protected-resource client policy, every hosted page
the row 13 check renders and the JSON every API caller gets are unchanged. A
browser navigation refused on a hosted route lands on `/api/v1/auth/error`
(Spanish via `ui_locales` or `Accept-Language`, fixed copy, a reason code and
request id as reference, one button to the client's registered origin when the
request named a registered client). Three routes are added:
`GET /api/v1/auth/error`, `GET /api/v1/auth/reset-password/done`,
`POST /api/v1/internal/users/change-email`; no other route changes.

## How

1. Build: `gh workflow run hotfix-janua-api-edge-hardening.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code and migrations are their proven sources
     (every earlier hotfix's files, row 13's three at `DOUBLE_SUBMIT_SOURCE`);
   - the checkout's `apps/api/app` is `SOURCE`'s; the application commits
     between row 13's source and `SOURCE` are exactly the nine merges; `SOURCE`
     differs from production by exactly `shipped_files.txt` plus the seven
     kept files, which the nine merges never touched;
   - `oauth_provider_shared.py.shipped` differs from `SOURCE`'s file by exactly
     `oauth_provider_shared.diff`, and that hunk is production's own lines;
   - the new image adds nine layers, its `/app/app` is `SOURCE`'s tree with the
     seven kept files byte-equal to the base's and the shipped module equal to
     the folder's copy (any other file, in either direction, fails), and its
     migrations are the base's;
   - both images import; discovery and the client policy are identical; row
     13's check ([`../janua-api-login-double-submit/check_double_submit.py`](../janua-api-login-double-submit/check_double_submit.py),
     with its goldens) gives the same pages, copy and used-request answer in
     both and row 13's properties hold in both; this row's check
     ([`check_edge_hardening.py`](check_edge_hardening.py)) shows refused
     navigations (an `HTTPException`, a validation error, slowapi's 429) answer
     `303` to the error page on the hotfix and JSON on the base, the page
     renders without echoing the request, the refresh grace window is 30 s,
     API callers and navigations on other routes get identical JSON in both,
     and the route table is the base's plus exactly the three routes above.
   It writes nothing to staging, production or the repository.
2. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` and fills in the exception record
   below.
3. Check after Argo syncs:
   - the rollout is healthy and the running image ID is the pinned digest;
   - discovery and the JWKS are unchanged;
   - a normal sign-in through a client app's hosted password page lands in that
     app, and a double press still does;
   - `GET /api/v1/auth/error?reason=bad_request&status=400` answers the page;
     a JSON caller of a refused hosted route still gets the envelope;
   - a token refresh still rotates;
   - the MCP connector probes answer as before
     ([`../../../docs/runbooks/mcp-connector-post-promote.md`](../../../docs/runbooks/mcp-connector-post-promote.md)).
4. Undo: revert the pin PR.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-20 (in session): asked whether to run the Janua production release this weekend, answered «Yes, go ahead». Scope: this hotfix only (janua#844, #845, #846, #847, #848, #850, #851, #852, #853, without janua#801's `roles` filter), on top of the current production digest `sha256:2bbee189…` (janua#843); `promote-to-prod.yml` stays held |
| Built by | pending |
| Hotfix digest | pending |
| Replaces | `sha256:2bbee189303b669bb24302ed3437daa59ee2e0979436d79b3b02b887b1eeb361` (janua#843) |
| Delta | `apps/api/app` at `ae191e86` (40 files: 30 added, 10 modified, `shipped_files.txt`), seven files kept at production's copies (`kept_files.txt`), `routers/v1/oauth_provider_shared.py` from `oauth_provider_shared.py.shipped` (`oauth_provider_shared.diff`) |

## Remove

Delete this folder, `.github/workflows/hotfix-janua-api-edge-hardening.yml`
and `apps/api/tests/unit/core/test_hotfix_janua_api_edge_hardening.py` in
the first normal promotion after the hold lifts.
