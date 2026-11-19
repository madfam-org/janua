# A repeated sign-in POST lands in the app, not on raw JSON: hotfix image (owner exception)

**Status (2026-11-19): pinned** by PIN_PR (`janua-api@sha256:2bbee189…`); live once Argo syncs. The full list of
what production runs is in [`../README.md`](../README.md).

## Why

Production sign-in incident, 2026-11-19 (janua#841, incident note
[`docs/runbooks/incidents/2026-11-19-hosted-login-double-submit.md`](../../../docs/runbooks/incidents/2026-11-19-hosted-login-double-submit.md)):
people signing in on the hosted password page saw a bare JSON page at
`/api/v1/auth/login-form` («La solicitud de acceso venció…»), and a refresh
posted the form again. It was a double submit: the first POST signed the person
in and consumed the pending request (`oauth:pre_login:<id>`), and the second
POST, 2–3 s later, reached `login_client_context` with the request gone, which
raised `HTTPException(400, …)`; the application rendered it as JSON.

janua#841:

- `app/auth/tenant_login_context.py`: `LoginRequestExpired`, a subclass of
  `HTTPException` with the same 400 and the same detail, so every other caller
  answers exactly as before and the hosted form can tell the case apart.
- `app/routers/v1/auth.py`: `login_form` reads the pending request once. When it
  is gone, the credentials are still checked against the registered, active
  client the form names (that client's identity pool, lockout, status,
  password) and a success goes (303) to that client's registered origin, which
  starts a fresh authorize the new session completes; a second factor, or an
  unknown or inactive client, issues nothing and goes (303) to the new GET page
  `/api/v1/auth/login-expired` (Spanish via `ui_locales`, `no-store`). Every
  hosted form carries `data-busy-label` and loads the same-origin script
  `GET /api/v1/auth/hosted-form.js`, which disables the button after the first
  press. The happy path and the non-OAuth path keep their 302.
- `app/auth/hosted_locale.py`: the copy for the page's button and the busy
  labels, English and Spanish.

`promote-to-prod.yml` is held until isolated staging is proven
(`scripts/staging/promotion_runtime_guard.py`), and promoting `main` would ship
far more than this change. This folder follows the exception pattern of
[`../janua-api-hosted-locale/README.md`](../janua-api-hosted-locale/README.md)
(three files copied from `main`) and
[`../janua-api-public-silent-auth/README.md`](../janua-api-public-silent-auth/README.md).
Nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:44c4310d…`, the public-silent-auth hotfix pinned by
janua#835) and adds three layers, one file each, all from `main`:

- `apps/api/app/auth/hosted_locale.py` ([`hosted_locale.diff`](hosted_locale.diff));
- `apps/api/app/auth/tenant_login_context.py` ([`tenant_login_context.diff`](tenant_login_context.diff));
- `apps/api/app/routers/v1/auth.py` ([`auth.diff`](auth.diff)).

Production's copy of each file is byte-identical to `main`'s before janua#841:
`hosted_locale.py` and `routers/v1/auth.py` are the hosted-locale hotfix's
(`HOSTED_SOURCE`), `tenant_login_context.py` the org-bound-login hotfix's
(`ORG_LOGIN_SOURCE`). So the files are `main`'s, with no `.shipped` copy, and
each differs from production's by exactly janua#841's hunks. The workflow
re-checks both: each shipped file against production's copy hunk by hunk, and
production's copies plus the merge's own diff against the shipped files, byte
for byte.

Everything the new code calls is already in production, unchanged:
`_recover_authorize_url_from_client`, `_recovery_page_html`, `page_locale`,
`hosted_copy` and `authorize_query` (the same files, or
`app/auth/authorize_resume.py`, untouched since `BASE_SOURCE`), and
`login_user`/`login_client_context` themselves.

**Effect:** a sign-in POST whose pending request is still there is decided
exactly as before (302 to the resumed authorize). A POST whose request is gone
(a double press, or an expired request) lands in the application after a
correct password, or on the GET «expired» page; never on the JSON body, and a
refresh does not post again. Hosted pages carry one extra `<script>` tag and
one `data-busy-label` attribute per form; with those two insertions removed
every page the check renders is byte for byte production's. The seven golden
renders are in [`pages/`](pages/) (the password, magic-link and privacy-notice
login pages in English and Spanish, and the second-factor page), rendered from
`main` before janua#841, whose three files are production's; the two password
pages are also byte for byte the goldens production's source rendered for
janua#808 (`apps/api/tests/unit/routers/fixtures/hosted_login_unlisted/`).
Without script the forms work as before.

## How

1. Build: `gh workflow run hotfix-janua-api-login-double-submit.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code and migrations are their proven sources
     (every earlier hotfix's files, the silent-auth `oauth_provider.py` at
     `SILENT_SOURCE`);
   - each changed file differs from production's copy by exactly the reviewed
     hunks, and production's copies plus the diff of merge `75dd0eea`
     (janua#841) are exactly the shipped files;
   - the new image adds three layers and changes only those three files, each
     byte-identical to its reviewed source;
   - discovery and the protected-resource client policy are identical between
     the images, and so are the copy production already had, the 400 every
     other caller answers and every other auth route; in both images every
     hosted page with janua#841's two insertions removed is byte for byte its
     golden in `pages/` (sent to the check on stdin and compared inside the
     image: code scanning reads the login page as credential data, so the
     pages are neither hashed nor printed);
   - in the new image the gone request raises its own type, the two GET routes
     are registered, the script is served, the login and second-factor pages
     load it and name their busy label, and the «expired» page and its URL have
     their shape ([`check_double_submit.py`](check_double_submit.py)); and the
     base does none of these.
   It writes nothing to staging, production or the repository.
2. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` and fills in the exception record
   below.
3. Check after Argo syncs:
   - the rollout is healthy and the running image ID is the pinned digest;
   - discovery and the JWKS are unchanged;
   - a normal sign-in through a client app's hosted password page lands in that
     app, and a deliberate double press (press, then press again or Enter at
     once) also lands in the app, never on JSON;
   - `GET /api/v1/auth/hosted-form.js` answers 200 with
     `application/javascript`;
   - the MCP connector probes answer as before
     ([`../../../docs/runbooks/mcp-connector-post-promote.md`](../../../docs/runbooks/mcp-connector-post-promote.md)).
4. Undo: revert the pin PR.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-19 (in session): asked for the fix and its hotfix after the production sign-in incident of that day (janua#841). Reason: production incident 2026-11-19. Pin OK given by the owner in session on 2026-11-19 («Promote the green fixes to production optimally and as soon as possible»); `promote-to-prod.yml` stays held. Scope: this hotfix only (janua#841), on top of the current production digest `sha256:44c4310d…` (janua#835) |
| Built by | [run 44625358092](https://github.com/madfam-org/janua/actions/runs/44625358092) from `main` `592d61b9` (janua#842); every proof step passed |
| Hotfix digest | `sha256:2bbee189303b669bb24302ed3437daa59ee2e0979436d79b3b02b887b1eeb361` |
| Replaces | `sha256:44c4310d742f4720efca7158872a88497fee6fd910996635109353ba7e098678` (janua#835) |
| Delta | `app/auth/hosted_locale.py`, `app/auth/tenant_login_context.py` and `app/routers/v1/auth.py` from `main`: production's copies plus janua#841 (`hosted_locale.diff`, `tenant_login_context.diff`, `auth.diff`) |

## Remove

Delete this folder, `.github/workflows/hotfix-janua-api-login-double-submit.yml`
and `apps/api/tests/unit/core/test_hotfix_janua_api_login_double_submit.py` in
the first normal promotion after the hold lifts.
