# Hosted locale on the chooser, second factor and switch refusal: hotfix image (owner exception)

## Why

Owner decision 2026-11-17: ship janua#814 and janua#820 to production now. Both
make hosted pages follow the `ui_locales` rule of `app/auth/hosted_locale.py`
(English by default, byte for byte; Spanish when the relying application asks
for it; only the normalized constant `es` ever travels):

- janua#814: the `prompt=select_account` account chooser speaks Spanish when
  `ui_locales` asks for it, and the resumed `/authorize` it posts (`next`)
  keeps `ui_locales=es`.
- janua#820: the second-factor branch of `GET /oauth/authorize` stores and
  forwards only the normalized constant (it stored the raw value and sent
  `ui_locales or "es"` to the login page), and the page
  `POST /auth/switch-session/form` answers when it refuses a chooser click
  speaks the chooser's language.

`promote-to-prod.yml` is held until isolated staging is proven
(`scripts/staging/promotion_runtime_guard.py`), and promoting `main` would ship
far more than these changes. This folder follows the exception pattern of
[`../janua-api-contain-roles-guest/README.md`](../janua-api-contain-roles-guest/README.md).
Nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:507e76f5…`, the contain-roles-guest hotfix pinned by
janua#828) and adds three layers, one file each:

- `apps/api/app/auth/hosted_locale.py` from `main`: the `chooser_*` and
  `switch_refused_*` copy, English and Spanish
  ([`hosted_locale.diff`](hosted_locale.diff); janua#814 and janua#820).
- `apps/api/app/routers/v1/auth.py` from `main`: the refusal page reads the
  locale from `next` and renders its copy ([`auth.diff`](auth.diff); janua#820).
- [`oauth_provider.py`](oauth_provider.py) in this folder: production's own
  `apps/api/app/routers/v1/oauth_provider.py` plus only the janua#814 and
  janua#820 hunks ([`oauth_provider.diff`](oauth_provider.diff)). `main`'s copy
  is not shipped: it also carries janua#792 (a comment) and janua#801 (the
  `roles` claim filter), which production does not run.

Production's copy of each file is its source's (`RES2_SOURCE` for
`hosted_locale.py` and `auth.py`, `BASE_SOURCE` for `oauth_provider.py`). The
workflow re-checks that each shipped file differs from it by exactly the
reviewed hunk, and that replaying the two merges' own diffs onto production's
copies gives exactly the three shipped files.

**Effect:** pages that asked for no language are unchanged, byte for byte (the
workflow compares the English chooser and refusal pages between the images).
With `ui_locales=es` the chooser, the pages after it and the refusal page speak
Spanish. One visible change for requests that ask for no language: a signed-in
person who needs a second factor now lands on the English login page instead of
the Spanish one, like every other hosted page (janua#820). Requests that send
`ui_locales=es` still get Spanish.

## How

1. Build: `gh workflow run hotfix-janua-api-hosted-locale.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code and migrations are their proven sources
     (every earlier hotfix's files, the contain files at `CONTAIN_SOURCE`);
   - each changed file differs from production's copy by exactly the reviewed
     hunk, and production's copies plus the diffs of merges `1e02b325`
     (janua#814) and `1f41e10d` (janua#820) are exactly the shipped files;
   - the new image adds three layers and changes only those three files, each
     byte-identical to its reviewed source;
   - discovery, the protected-resource client policy and the English chooser
     and refusal pages are identical between the images;
   - in the new image the chooser and the refusal page speak Spanish when asked,
     the chooser's resumed `/authorize` carries the constant, and the
     second-factor branch forwards only the constant
     ([`check_locale.py`](check_locale.py)); and the base does none of these.
   It writes nothing to staging, production or the repository.
2. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` and fills in the exception record
   below.
3. Check after Argo syncs: the rollout is healthy and the running image ID is
   the pinned digest; discovery and the JWKS are unchanged; an
   `/oauth/authorize?prompt=select_account&ui_locales=es` with a held session
   shows «Elige una cuenta»; the MCP connector probes answer as before
   ([`../../../docs/runbooks/mcp-connector-post-promote.md`](../../../docs/runbooks/mcp-connector-post-promote.md)).
4. Undo: revert the pin PR.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-17 (in session): ship the two language fixes to production now; `promote-to-prod.yml` stays held. Scope: this hotfix only (janua#814 and janua#820), on top of the current production digest `sha256:507e76f5…` (janua#828) |
| Built by | pending: filled in by the pin PR |
| Hotfix digest | pending: filled in by the pin PR |
| Replaces | `sha256:507e76f567c0847a124515f3e2d3b76d698a2c9f4dc9aae9fdf6d099cf966eec` (janua#828) |
| Delta | `app/auth/hosted_locale.py` and `app/routers/v1/auth.py` from `main`, production's `app/routers/v1/oauth_provider.py` plus the two merges (janua#814 and janua#820: `hosted_locale.diff`, `auth.diff`, `oauth_provider.diff`) |

## Remove

Delete this folder, `.github/workflows/hotfix-janua-api-hosted-locale.yml`
and `apps/api/tests/unit/core/test_hotfix_janua_api_hosted_locale.py` in
the first normal promotion after the hold lifts.
