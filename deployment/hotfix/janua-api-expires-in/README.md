# OAuth `expires_in` matches the access token's real expiry: hotfix image (owner exception)

**Status (2026-11-23): not built, not pinned.** Production runs row 15
(`janua-api@sha256:0b8b5cfd…`, janua#859). The full list of what production
runs is in [`../README.md`](../README.md).

## Why

The authorization-code exchange and the refresh grant answered a literal
`expires_in=3600`, while the access token they mint carries
`exp = iat + JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (480 minutes). A client that
trusts the announcement stops using a token with seven valid hours left. The
Enclii CLI does, so whenever its refresh was refused the owner had to run
`enclii login` again after one hour, and crea-sim's fleet reconciler stopped
with it. crea-sim ADR-0012 (§1, ruling 2) asks for that manual step to go away
by fixing the session, not with a long-lived API token.

janua#860 computes `expires_in` from the `exp` the mint returns, on both
grants. It merged to `main` on 2026-11-24 (UTC) as `2dc62eeb`.
`promote-to-prod.yml` is held, so it reaches production as this row.

**Who it affects in production:** every OAuth client of the code and refresh
grants reads 28800 instead of 3600. Clients that schedule their refresh from
`expires_in` refresh about every 8 hours instead of every hour, so claims that
are re-read at refresh (roles, entitlements, organization) reach them later.
Access is not widened: resource servers already accepted each token for its
full 8 hours. The token, its lifetime, the refresh token and every check on
the refresh path are unchanged. `client_credentials` is not touched.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs (row 15)
and adds one layer: `apps/api/app/routers/v1/oauth_provider_grants.py` at
`SOURCE` (`2dc62eeb`, janua#860's merge; `apps/api/app` on `main` is still
exactly that tree). Against production's copy (the same file at `ae191e86`,
`PREVIOUS`) it differs by janua#860 alone: 18 lines added, 4 removed, the
`_access_token_expires_in` helper and its two uses.

Nothing else changes: no other file, package, migration or setting.

## Proof (the workflow, before signing)

1. The Dockerfile is the `FROM` and the one `COPY`, nothing else.
2. `apps/api/app` on `main` is `SOURCE`; the module is `SOURCE`'s; between
   `PREVIOUS` and `SOURCE` only this module changed under `apps/api/app`, by
   18 added and 4 removed lines, the two literals replaced by the helper.
3. The base is signed by row 15's workflow on `main` and carries `PREVIOUS`'s
   copy of the module.
4. The built image has one added layer and differs from the base by that one
   file; migrations unchanged.
5. Both images import the whole application; discovery is identical;
   [`check_expires_in.py`](check_expires_in.py) finds the literal 3600 in both
   grants on the base and none on the hotfix, where a freshly minted token's
   announced lifetime equals its own `exp`.

## Steps

1. Build: `gh workflow run hotfix-janua-api-expires-in.yml --repo madfam-org/janua --ref main -f reason="..."`.
2. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` to the digest the run's
   "Sign image with cosign" step prints, and fills in this record. After it
   rolls: the pods run the pinned digest, discovery and readiness answer, and a
   sign-in still works.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-23 (in session): asked whether to promote the new image, answered «Yes, promote it»; told the promote workflow is held and offered this row instead, answered «Yes, prepare row 16». Scope: janua#860's one file, on top of production's row 15 |
| Built by | not built yet |
| Replaces | `sha256:0b8b5cfd91e95a82ab4508c083e34edc364338a61df8b2af19a76babda521989` (janua#859) |
| Delta | `apps/api/app/routers/v1/oauth_provider_grants.py` at `2dc62eeb` |

## Remove

Delete this folder, `.github/workflows/hotfix-janua-api-expires-in.yml` and
`apps/api/tests/unit/core/test_hotfix_janua_api_expires_in.py` in the first
normal promotion after the hold lifts.
