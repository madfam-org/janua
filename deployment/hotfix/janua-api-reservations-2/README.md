# Reservation registry, second refresh: hotfix image (owner exception)

## Why

Owner ruling 2026-11-15: reservations merged on `main` since the first
reserved-boundaries hotfix reach production through another hotfix image, not
by lifting the promotion hold.

A reservation makes registering or editing a client that carries a value a
platform-admin action. This module's own rule is that a sibling resource
server's machine scope or audience is reserved **and deployed** before any
client carrying it is provisioned. Three reservations are merged and not yet
in production:

- `tlacuilo` (audience) and `tlacuilo:extract` (scope), janua#800: tlacuilo's
  API takes any machine token carrying the pair, so its consumers' clients
  wait for this.
- `phynd-crm-pipeline:read` (scope), janua#799.
- `eido-api` (audience), janua#801.

`promote-to-prod.yml` is held until isolated staging is proven
(`scripts/staging/promotion_runtime_guard.py`), and promoting `main` would ship
far more than this file. This folder follows the exception pattern of
[`../janua-api-reserved-boundaries/README.md`](../janua-api-reserved-boundaries/README.md)
and [`../janua-api-org-bound-login/README.md`](../janua-api-org-bound-login/README.md).
Nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:cf723284…`, the entitlement-source hotfix of janua#811, which
replaced janua#805's organization-role-shape image)
and adds one layer with one file from `main`:

- `apps/api/app/core/reserved_oauth_boundaries.py`: the reservation registry.
  Against production's copy it only ADDS values to reservation sets (the four
  above) and one public name (`TLACUILO_SCOPES`). Nothing is removed, and no
  prefix, suffix, first-party name or tenant-bound list changes.

Between the registry production runs (`ee7668b8`) and `main`, this file
changed only in janua#799, janua#800 and janua#801; the workflow re-checks
that, and refuses any image whose registry is not strictly tighter than
production's ([`../janua-api-reserved-boundaries/compare_registry.py`](../janua-api-reserved-boundaries/compare_registry.py)).

## How

1. Build: `gh workflow run hotfix-janua-api-reservations-2.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code is `b16869d7` plus the reserved-boundaries
     files from `ee7668b8`, the ChatGPT files from `ae7a3f50`, the org-bound
     login files from `6f3b9b1a`, the organization-role-shape files from
     `0742d02a` and the model from `7c6150ff` (what production runs);
   - the copied file changed only in janua#799, #800 and #801 since `ee7668b8`;
   - the new image adds one layer and changes only that file, byte-identical to
     the reviewed source;
   - discovery and the protected-resource client policy are identical between
     the images;
   - the registry only tightens, and the additions are exactly the expected
     four values.
   It writes nothing to staging, production or the repository.
2. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` and fills in the exception record
   below.
3. Check after Argo syncs:
   - the rollout is healthy and the running image ID is the pinned digest;
   - discovery and the JWKS are unchanged;
   - the MCP connector probes still answer as before
     ([`../../../docs/runbooks/mcp-connector-post-promote.md`](../../../docs/runbooks/mcp-connector-post-promote.md));
   - `scripts/audit_reserved_oauth_clients.py` reports no existing client that
     carries a newly reserved value without being platform-registered.
4. Undo: revert the pin PR.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-15 (in session): the route (a fifth hotfix image, not lifting the hold). The build and the pin are each approved when ready |
| Built by | not built yet |
| Hotfix digest | not built yet |
| Replaces | `sha256:cf723284080b94d78419c8cd2a189e8ecffe9b5a24c79e7b60e60bd0fa528032` (janua#811's entitlement-source hotfix; rebased from janua#805's image when that was pinned) |
| Delta | `app/core/reserved_oauth_boundaries.py` from `main` (janua#799, #800, #801) |
