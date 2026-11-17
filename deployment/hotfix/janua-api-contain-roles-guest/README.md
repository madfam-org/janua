# Product role scopes and guest audience: hotfix image (owner exception)

## Why

Owner decision 2026-11-17: ship janua#826 to production now. It reserves product
role scopes, so only a platform admin registers or edits a client that carries
one (`RESERVED_SCOPE_NAMESPACES`; the tenant-bound `hcm:hr` and `selva:infer`
stay registrable), and gives guest tokens their own audience (`janua-guest`)
instead of the platform default.

`promote-to-prod.yml` is held until isolated staging is proven
(`scripts/staging/promotion_runtime_guard.py`), and promoting `main` would ship
far more than this change. This folder follows the exception pattern of
[`../janua-api-primary-organization/README.md`](../janua-api-primary-organization/README.md).
Nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:cd6e19df…`, the primary-organization hotfix pinned by
janua#824) and adds two layers, one file each, from `main`:

- `apps/api/app/core/reserved_oauth_boundaries.py`: product role scopes are
  reserved, the guest audience is defined ([`reserved.diff`](reserved.diff)).
- `apps/api/app/routers/v1/guest.py`: guest tokens carry `GUEST_AUDIENCE`
  ([`guest.diff`](guest.diff)).

Production's copy of each file is its source's (`RES2_SOURCE` for the registry,
`BASE_SOURCE` for the guest router), and `main` differs from it by exactly the
reviewed hunk; the workflow re-checks both.

**Effect:** only client registration and edits consult the registry, so the
production clients that already carry product role scopes keep minting tokens
as before. Selva Office recognises guest tokens by `type` and `roles`, not by
audience, so its guests keep working.

## How

1. Build: `gh workflow run hotfix-janua-api-contain-roles-guest.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code and migrations are their proven sources
     (every earlier hotfix's files, the primary-organization files at
     `PRIMARY_SOURCE`);
   - each changed file differs from production's copy by exactly the reviewed
     hunk;
   - the new image adds two layers and changes only those two files, each
     byte-identical to `main`;
   - discovery and the protected-resource client policy are identical between
     the images;
   - in the new image product role scopes are reserved and guest tokens carry
     their own reserved audience, while tenant-bound scopes, look-alikes and the
     guest grant behave as before ([`check_contain.py`](check_contain.py)); and
     the base does not.
   It writes nothing to staging, production or the repository.
2. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` and fills in the exception record
   below.
3. Check after Argo syncs: the rollout is healthy and the running image ID is
   the pinned digest; discovery and the JWKS are unchanged; in the running pod a
   product role scope is reserved and a guest token carries `janua-guest`; the
   MCP connector probes answer as before
   ([`../../../docs/runbooks/mcp-connector-post-promote.md`](../../../docs/runbooks/mcp-connector-post-promote.md)).
4. Undo: revert the pin PR.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-17 (in session): «Yes, contain now» to «Contain these now with an identity-service hotfix plus Tulana and Nauta patches?». Scope: this hotfix only (janua#826), on top of the current production digest `sha256:cd6e19df…` (janua#824) |
| Built by | pending: filled in by the pin PR |
| Hotfix digest | pending: filled in by the pin PR |
| Replaces | `sha256:cd6e19df31f412fe3530c7481af8de1c4263b7ae0830795ab9d392737a0da9f5` (janua#824) |
| Delta | `app/core/reserved_oauth_boundaries.py` and `app/routers/v1/guest.py` from `main` (janua#826: `reserved.diff`, `guest.diff`) |

## Remove

Delete this folder, `.github/workflows/hotfix-janua-api-contain-roles-guest.yml`
and `apps/api/tests/unit/core/test_hotfix_janua_api_contain_roles_guest.py` in
the first normal promotion after the hold lifts.
