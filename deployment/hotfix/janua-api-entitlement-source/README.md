# Entitlement source mapping: hotfix image (owner exception)

## Why

No product entitlement can be written in production. Every write to
`user_entitlements` fails with

```
asyncpg.exceptions.UndefinedObjectError: type "entitlementsource" does not exist
```

because the model's `SQLEnum(EntitlementSource)` used SQLAlchemy's defaults (a
type named after the class, binding the member names), while production's
database has the type migration 007 created: `entitlement_source`, holding the
lowercase values (read-only check, 2026-11-15: three labels, the column of that
type, zero rows). Seen as a `503 DATABASE_ERROR` on
`POST /api/v1/internal/product-invites` when inviting the owner's own account to
the invite-only cv client; the same failure blocks admin grants and Dhanam
subscription grants. The fix is janua#811 (model only; the database is already
right, no migration).

`promote-to-prod.yml` is held until isolated staging is proven
(`scripts/staging/promotion_runtime_guard.py`), and promoting `main` would ship
far more than this file. This folder follows the exception pattern of
[`../janua-api-reservations-2/README.md`](../janua-api-reservations-2/README.md).
Nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:99f354a9…`, the organization-role-shape hotfix pinned by
janua#805) and adds one layer with one file from `main`:

- `apps/api/app/models/__init__.py`. Production's copy is byte-identical to the
  file at `BASE_SOURCE` (git blob `4cfee494…`, also checked in the running pod on
  2026-11-15); the only difference is the hunk in [`models.diff`](models.diff),
  the `source` column of `UserEntitlement`.

## How

1. Build: `gh workflow run hotfix-janua-api-entitlement-source.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code is `b16869d7` plus the files of the four
     earlier hotfixes from their sources (what production runs);
   - the model differs from production's copy by exactly `models.diff`;
   - the new image adds one layer and changes only that file, byte-identical to
     the reviewed source;
   - discovery and the protected-resource client policy are identical between
     the images;
   - the base maps the column to `entitlementsource` (the bug) and the new image
     to `entitlement_source` with the lowercase values, binding `'admin_grant'`.
   It writes nothing to staging, production or the repository.
2. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` and fills in the exception record
   below.
3. Check after Argo syncs:
   - the rollout is healthy and the running image ID is the pinned digest;
   - discovery and the JWKS are unchanged;
   - a product invitation for the cv client answers 200 with
     `entitlement_granted: true`, and that person can sign in to cv.
4. Undo: revert the pin PR.

The reservations-2 hotfix (merged, not built) and its sign-in-notice extension
(janua#809) also start from `99f354a9`. Whichever image is pinned first, the
other is rebased onto it before it is built, as janua#807 did.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-15 (in session): «make it so the login works». The merge, the build and the pin are each approved when ready |
| Built by | not built yet |
| Hotfix digest | not built yet |
| Replaces | `sha256:99f354a940f6a9ada0f899653445ee75682c101b9aba8525b06a0627301b8c0d` (janua#805) |
| Delta | `app/models/__init__.py` from `main` (janua#811: the hunk in `models.diff`) |
