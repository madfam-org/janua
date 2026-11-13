# Org-bound login for platform members: hotfix image (owner exception)

## Why

Owner decision 2026-11-13: ship janua#795 now. An OAuth client bound to an
organization looked users up only in that organization's own identity pool, so
a platform-pool member of that same organization (the default shape for staff,
see `ProvisionUserRequest.identity_pool`) could not sign in on the client's
hosted login. They got in only by reusing a session opened elsewhere. janua#795
falls back to the platform pool for a user who holds an ACTIVE membership in the
client's organization, and nobody else.

`promote-to-prod.yml` is held until isolated staging is proven
(`scripts/staging/promotion_runtime_guard.py`), and promoting `main` would ship
far more than this change. This folder follows the exception pattern of
[`../janua-api-map-chatgpt/README.md`](../janua-api-map-chatgpt/README.md).
Nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:ae28948d…`, the ChatGPT-on-the-MAP hotfix pinned by janua#794)
and adds two layers, one file each, from `main`:

- `apps/api/app/auth/tenant_login_context.py`: `login_user` keeps the client's
  own pool first; when it has no match, it accepts a platform-pool user only if
  that user has an active membership in the client's organization
  (`_platform_member_by_email`). `user_in_client_pool` states the same rule.
- `apps/api/app/auth/hosted_security.py`: the MFA factor flow and the security
  page use `user_in_client_pool` instead of comparing `users.tenant_id` with the
  client's organization, so a platform member is not refused after a correct
  password.

Between production's source (`b16869d7`) and `main`, these two files changed
only in janua#795 (`6f3b9b1a`); the workflow re-checks that.

## How

1. Build: `gh workflow run hotfix-janua-api-org-bound-login.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code is `b16869d7` plus the reserved-boundaries
     files from `ee7668b8` plus the ChatGPT files from `ae7a3f50` (what
     production runs);
   - the two copied files changed only in janua#795 since `b16869d7`;
   - the new image adds two layers and changes only the two files, each
     byte-identical to the reviewed source;
   - discovery and the protected-resource client policy are identical between
     the images (the policy dump is the ChatGPT hotfix's `dump_policy.py`);
   - the new image has the platform-member fallback and still has the membership
     gate ([`check_login.py`](check_login.py)), and the base does not.
   It writes nothing to staging, production or the repository.
2. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` and fills in the exception record
   below.
3. Check after Argo syncs:
   - the rollout is healthy and the running image ID is the pinned digest;
   - discovery and the JWKS are unchanged;
   - the MCP connector probes still answer as before
     ([`../../../docs/runbooks/mcp-connector-post-promote.md`](../../../docs/runbooks/mcp-connector-post-promote.md)).
4. Undo: revert the pin PR.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-13 (in session): «Yes, merge #795» to «merge and promote janua#795» |
| Built by | pending |
| Hotfix digest | pending |
| Replaces | `sha256:ae28948d88cbd9dcb0ee3795ec881e9c8ddbb7e68103b0c83f937e3d003926e4` (janua#794) |
| Delta | `app/auth/tenant_login_context.py` and `app/auth/hosted_security.py` from `main` (janua#795) |

## Remove

Delete this folder, `.github/workflows/hotfix-janua-api-org-bound-login.yml` and
`apps/api/tests/unit/core/test_hotfix_janua_api_org_bound_login.py` in the first
normal promotion after the hold lifts.
