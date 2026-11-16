# Reservation registry and the sign-in privacy notice: hotfix image (owner exception)

## Why

Owner rulings 2026-11-15: reservations merged on `main` since the first
reserved-boundaries hotfix reach production through another hotfix image, not
by lifting the promotion hold (B5); and MADFAM CV's privacy notice is shown on
Janua's hosted sign-in page (A5, janua#806). One image carries both, so one
build and one pin ship both.

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

The sign-in notice (janua#806): `CLIENT_PRIVACY_NOTICES` is already set on the
Deployment for MADFAM CV's client; the running image ignores it. With this image a
listed client's hosted login shows one line linking its own notice; every other
page renders byte for byte as before.

`promote-to-prod.yml` is held until isolated staging is proven
(`scripts/staging/promotion_runtime_guard.py`), and promoting `main` would ship
far more than these files. This folder follows the exception pattern of
[`../janua-api-reserved-boundaries/README.md`](../janua-api-reserved-boundaries/README.md)
and [`../janua-api-org-bound-login/README.md`](../janua-api-org-bound-login/README.md).
Nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:cf723284…`, the entitlement-source hotfix of janua#811, which
replaced janua#805's organization-role-shape image)
and adds five layers, one file each, from `main`:

- `apps/api/app/core/reserved_oauth_boundaries.py`: the reservation registry.
  Against production's copy it only ADDS values to reservation sets (the four
  above) and one public name (`TLACUILO_SCOPES`). Nothing is removed, and no
  prefix, suffix, first-party name or tenant-bound list changes.
- `apps/api/app/services/client_privacy_notices.py` (new, janua#806): parses
  `CLIENT_PRIVACY_NOTICES`; a value that is not a plain https URL is dropped.
- `apps/api/app/auth/hosted_locale.py` and `apps/api/app/routers/v1/auth.py`
  (janua#806 only since production's source): the notice line, rendered only for
  a listed client.
- `apps/api/app/config.py` (janua#806 and janua#798 since production's source):
  the `CLIENT_PRIVACY_NOTICES` setting, and **janua#798**, which rides along: the
  support address named in emails is `EMAIL_SUPPORT_REPLY_TO` when set, instead
  of the sender address. Nothing else in the file differs.

Between the registry production runs (`ee7668b8`) and `main`, this file
changed only in janua#799, janua#800 and janua#801, and each of the other
files only in the pull requests named above; the workflow re-checks that, and refuses any image whose registry is not strictly tighter than
production's ([`../janua-api-reserved-boundaries/compare_registry.py`](../janua-api-reserved-boundaries/compare_registry.py)).

## How

1. Build: `gh workflow run hotfix-janua-api-reservations-2.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code is `b16869d7` plus the reserved-boundaries
     files from `ee7668b8`, the ChatGPT files from `ae7a3f50`, the org-bound
     login files from `6f3b9b1a`, the organization-role-shape files from
     `0742d02a` and the model from `7c6150ff` (what production runs);
   - the registry changed only in janua#799, #800 and #801 since `ee7668b8`, and
     the other four files only in janua#806 (and config.py in janua#798) since
     `b16869d7`;
   - the new image adds five layers and changes only those files, each
     byte-identical to the reviewed source;
   - discovery and the protected-resource client policy are identical between
     the images;
   - the hosted login renders the notice line for a listed client and is
     byte-identical for a client not listed;
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
| Delta | `app/core/reserved_oauth_boundaries.py` (janua#799, #800, #801); `app/services/client_privacy_notices.py`, `app/auth/hosted_locale.py`, `app/routers/v1/auth.py` (janua#806); `app/config.py` (janua#806, janua#798) |
