# Silent sign-in for marked public first-party clients: hotfix image (owner exception)

## Why

Owner decision 2026-11-18: ship janua#833 to production now. A first-party
browser app that is a **public** client (PKCE, no secret) may use `prompt=none`
and skip the consent screen when an operator marked it with
`madfam:silent_auth`, and only when:

- the row was registered by a platform admin
  (`oauth_client_authority.client_registered_by_platform_admin`);
- the request states PKCE S256 explicitly, with a challenge of the S256 shape;
- its `redirect_uri` is exactly one of the registered strings;
- every requested scope is registered for the client;
- any reserved scope it asks for (a product role scope, the marker itself) is
  one the person already granted this client on the consent screen.

Otherwise the caller gets `login_required`, `consent_required` or
`interaction_required` at the validated `redirect_uri` (or, interactively, the
ordinary consent screen). Unmarked public clients and every confidential client
behave exactly as before. No migration; no client is marked by this change. See
[`../../../docs/architecture/SILENT_SSO_SESSION.md`](../../../docs/architecture/SILENT_SSO_SESSION.md)
(B8).

`promote-to-prod.yml` is held until isolated staging is proven
(`scripts/staging/promotion_runtime_guard.py`), and promoting `main` would ship
far more than this change. This folder follows the exception pattern of
[`../janua-api-hosted-locale/README.md`](../janua-api-hosted-locale/README.md).
Nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:b9396f85…`, the hosted-locale hotfix pinned by janua#831)
and adds one layer, one file:

- [`oauth_provider.py.shipped`](oauth_provider.py.shipped) in this folder,
  copied in as `app/routers/v1/oauth_provider.py`: production's own copy (the
  hosted-locale hotfix's `oauth_provider.py.shipped` at `HOSTED_SOURCE`) plus
  only the janua#833 hunks ([`oauth_provider.diff`](oauth_provider.diff)).
  `main`'s copy is not shipped: it also carries janua#792 (a comment) and
  janua#801 (the `roles` claim filter), which production does not run. It does
  not end in `.py` so code scanning does not re-report, on a second path, the
  alerts it already tracks on `apps/api/app/routers/v1/oauth_provider.py`.

janua#833 changes no other application file. Everything the new code calls is
already in production, unchanged: `is_reserved_scope` and `SILENT_AUTH_SCOPE`
(`core/reserved_oauth_boundaries.py`, the contain-roles-guest copy, identical to
`main`'s), `client_registered_by_platform_admin`
(`services/oauth_client_authority.py`) and `ConsentService.has_consent`
(`services/consent_service.py`), both unchanged since `BASE_SOURCE`. The
workflow re-checks that the shipped file differs from production's by exactly
the reviewed hunks, and that replaying the merge's own diff onto production's
copy gives exactly the shipped file.

**Effect:** none while no public client carries the marker (step 2 below
checks that before the pin). For every client that
does not carry the marker, and for every confidential client, `prompt=none` and
the consent skip are decided exactly as before (the workflow compares
`_is_silent_auth_allowed` and `_is_first_party_preconsented` over a matrix of
client shapes between the images; discovery and the protected-resource client
policy are compared too). A public client carrying the marker on a row a
platform admin registered: silent sign-in and no consent screen under the
conditions above. The same marker on a row anyone else registered: refused
with `interaction_required`, as today.

## How

1. Build: `gh workflow run hotfix-janua-api-public-silent-auth.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code and migrations are their proven sources
     (every earlier hotfix's files, the hosted-locale files at `HOSTED_SOURCE`);
   - the shipped file differs from production's copy by exactly the reviewed
     hunks, and production's copy plus the diff of merge `878e8428`
     (janua#833) is exactly the shipped file;
   - the new image adds one layer and changes only that file, byte-identical to
     its reviewed source;
   - discovery, the protected-resource client policy and the first-party
     predicates every client already goes through are identical between the
     images;
   - in the new image a marked public client is recognised (only one carrying
     the marker, never by name), its request conditions and the
     platform-admin registration rule are enforced, and reserved scopes still
     need the person's consent ([`check_silent_auth.py`](check_silent_auth.py));
     and the base does none of these.
   It writes nothing to staging, production or the repository.
2. Before pinning, confirm read-only that no public client already carries the
   marker (no repository declaration does; production's rows cannot be read from
   here). The new behaviour applies from the first request to any such row a
   platform admin registered, so the answer must be empty, or each row listed
   must be one the owner wants marked:
   `SELECT client_id, name, created_by FROM oauth_clients WHERE is_confidential = false AND allowed_scopes ? 'madfam:silent_auth';`
3. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` and fills in the exception record
   below.
4. Check after Argo syncs: the rollout is healthy and the running image ID is
   the pinned digest; discovery and the JWKS are unchanged; a `prompt=none`
   request from an existing confidential first-party client (the client portal,
   nauta) still returns a code with a held session; the MCP connector probes
   answer as before
   ([`../../../docs/runbooks/mcp-connector-post-promote.md`](../../../docs/runbooks/mcp-connector-post-promote.md)).
5. Mark a client (separate operator step, only when an app needs it): follow
   [SILENT_SSO_SESSION.md → How an operator marks a client](../../../docs/architecture/SILENT_SSO_SESSION.md#b8--marked-public-first-party-clients-2026-11-18).
6. Undo: revert the pin PR (and unmark any client marked in step 5 by removing
   the scope; on the previous image the marker on a public client does nothing).

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-18 (in session): «Go ahead with A and C» (ship janua#833 to production by hotfix); `promote-to-prod.yml` stays held. Scope: this hotfix only (janua#833), on top of the current production digest `sha256:b9396f85…` (janua#831) |
| Built by | [run 44388593537](https://github.com/madfam-org/janua/actions/runs/44388593537) from `main` `85f3e832` (janua#834); every proof step passed |
| Hotfix digest | `sha256:44c4310d742f4720efca7158872a88497fee6fd910996635109353ba7e098678` (cosign-signed by that run) |
| Replaces | `sha256:b9396f85e85e6f233cac090a032026f12540881848122e6ddfd68600a3dcae1a` (janua#831) |
| Delta | production's `app/routers/v1/oauth_provider.py` plus janua#833 (`oauth_provider.diff`) |

## Remove

Delete this folder, `.github/workflows/hotfix-janua-api-public-silent-auth.yml`
and `apps/api/tests/unit/core/test_hotfix_janua_api_public_silent_auth.py` in
the first normal promotion after the hold lifts.
