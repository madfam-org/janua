# Organization roles never read as application roles: hotfix image (owner exception)

## Why

Owner decision 2026-11-15: ship janua#801 and janua#802 now. Resource servers
authorize on `<app>:<role>` strings read from the token's `roles` claim, which
are meant to come only from audited application-role grants. The OIDC path
also published organization role strings under that key, and an
organization's own admins choose those strings. janua#801 and janua#802 stop
publishing an organization role of that shape and refuse it where roles are
written.

`promote-to-prod.yml` is held until isolated staging is proven
(`scripts/staging/promotion_runtime_guard.py`), and promoting `main` would ship
far more than this change. This folder follows the exception pattern of
[`../janua-api-org-bound-login/README.md`](../janua-api-org-bound-login/README.md).
Nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:f97bddd8…`, the org-bound-login hotfix pinned by janua#797)
and adds three layers, one file each, from `main`:

- `apps/api/app/services/org_claims_service.py`: `merge_app_roles_into_claims`,
  the helper both minting seams share, drops an organization role shaped like
  an application role from the legacy list and still writes `roles` when
  everything was dropped. Production's OIDC handler (not part of this hotfix)
  spreads that result over its own `roles` key, so the token is clean without
  touching the handler. The file also gains the helpers janua#801 added.
- `apps/api/app/services/role_service.py`: custom role create, rename and
  assign refuse a name of that shape.
- `apps/api/app/services/organization_member_service.py`: member add, role
  update and invitation refuse it too.

Between production's source (`b16869d7`) and `main`, these three files changed
only in janua#801 (`4bacd0b9`) and janua#802 (`508d1909`); the workflow
re-checks that.

Not in this hotfix: `routers/v1/oauth_provider.py` (it also changed in
janua#792, so `main`'s copy would ship more than this change; the shared merge
makes it unnecessary) and `core/reserved_oauth_boundaries.py` (the `eido-api`
reservation waits for a normal promotion; nothing trusts that audience yet).

**Before pinning:** anyone who relies on an organization role string of the
application-role shape needs the matching application-role grant, resolving on
a fresh token, or they lose that role when this ships. Application roles are
published only for a person with one unambiguous primary organization.

## How

1. Build: `gh workflow run hotfix-janua-api-org-role-shape.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code is `b16869d7` plus the reserved-boundaries
     files from `ee7668b8`, the ChatGPT files from `ae7a3f50` and the
     org-bound-login files from `6f3b9b1a` (what production runs);
   - the three copied files are production's plus janua#801 and janua#802 only;
   - the new image adds three layers and changes only the three files, each
     byte-identical to the reviewed source;
   - discovery and the protected-resource client policy are identical between
     the images (the policy dump is the ChatGPT hotfix's `dump_policy.py`);
   - in the new image a forged organization role never reaches the token, bare
     organization roles and real grants still do, and a role name of that shape
     is refused ([`check_roles.py`](check_roles.py)); and the base does not.
   It writes nothing to staging, production or the repository.
2. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` and fills in the exception record
   below.
3. Check after Argo syncs:
   - the rollout is healthy and the running image ID is the pinned digest;
   - discovery and the JWKS are unchanged;
   - a person holding an application-role grant still resolves it, and an
     organization role of that shape is no longer published;
   - the MCP connector probes still answer as before
     ([`../../../docs/runbooks/mcp-connector-post-promote.md`](../../../docs/runbooks/mcp-connector-post-promote.md)).
4. Undo: revert the pin PR.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-15 (in session): «Yes, ship hotfix» to «Ship the identity fix to production now as a hotfix image?» |
| Built by | [run 43763092668](https://github.com/madfam-org/janua/actions/runs/43763092668), dispatched from `main` (`0742d02a`) on 2026-11-15 |
| Hotfix digest | `sha256:99f354a940f6a9ada0f899653445ee75682c101b9aba8525b06a0627301b8c0d` (cosign-signed by that run) |
| Replaces | `sha256:f97bddd83a8091ed17c9c33d8ee36577406afefa902c35cd8e42c2f7dff8326e` (janua#797) |
| Delta | `app/services/org_claims_service.py`, `app/services/role_service.py` and `app/services/organization_member_service.py` from `main` (janua#801, janua#802) |

## Remove

Delete this folder, `.github/workflows/hotfix-janua-api-org-role-shape.yml` and
`apps/api/tests/unit/core/test_hotfix_janua_api_org_role_shape.py` in the first
normal promotion after the hold lifts.
