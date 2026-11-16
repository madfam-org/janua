# Operator-set primary organization: hotfix image (owner exception)

## Why

Owner decision 2026-11-16: ship janua#822 to production now. The claims
resolver emits `org_id`, `madfam_org_roles` and application roles (`roles`)
only for an unambiguous primary membership. A staff account with several
active organization memberships and no `tenant_id` match therefore gets `orgs`
and nothing else, and can never pass a resource server that gates on an
application role, however many grants it holds. janua#822 adds an explicit
primary organization that an operator sets through the internal API
(`/api/v1/internal/primary-organization`). The resolver honours it only while
the person holds an ACTIVE membership there, and `tenant_id` still wins.

`promote-to-prod.yml` is held until isolated staging is proven
(`scripts/staging/promotion_runtime_guard.py`), and promoting `main` would ship
far more than this change. This folder follows the exception pattern of
[`../janua-api-webhooks/README.md`](../janua-api-webhooks/README.md). Nothing
here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:1b1e28de…`, the webhooks hotfix pinned by janua#818) and
adds seven layers, one file each:

| File in the image | Source | Production's copy |
|---|---|---|
| `app/models/user_primary_organization.py` | `main` | none (new) |
| `app/schemas/primary_organization.py` | `main` | none (new) |
| `app/routers/v1/internal_primary_organization.py` | `main` | none (new) |
| `alembic/versions/022_user_primary_organization.py` | `main` | none (new) |
| `app/services/org_claims_service.py` | `main` | `ROLE_SHAPE_SOURCE`'s; differs by exactly [`claims.diff`](claims.diff) |
| `app/services/audit_logger.py` | `main` | `BASE_SOURCE`'s; differs by exactly [`audit.diff`](audit.diff) |
| `app/main.py` | [`main.py`](main.py) in this folder | `BASE_SOURCE`'s; differs by exactly [`main.diff`](main.diff) |

`main.py` is the one file not copied from `main`. Between production's source
(`b16869d7`) and `main`, `app/main.py` also changed in janua#798 (the OpenAPI
support contact), which production does not run. So this folder carries
production's own `main.py` with only the router registration added
(`main.diff`, the block janua#822 added on `main`, verbatim). The workflow and
the guard test both prove that.

What the image does NOT touch: `app/models/__init__.py` and the `User` model.
The choice lives in its own table, `user_primary_organizations`. The resolver
reads that table only for a person with several active memberships and no
`tenant_id` match, in a SAVEPOINT that answers "no primary" on any failure,
a missing table included.

## Deploy order and the migration

The order does not matter for availability:

- this image on a database without migration 022 mints exactly today's
  tokens (the read degrades; logins never fail on it);
- migration 022 on a database whose image predates it is never read.

The feature works only once both are in. Until then the internal endpoints
answer a 5xx (503).

The migration is the reviewed operator SQL
[`docs/ops/sql/022_user_primary_organization.sql`](../../../docs/ops/sql/022_user_primary_organization.sql),
applied by hand like 017–021:

- it runs in one transaction as `enclii`, with a 5 s lock timeout;
- it refuses unless `alembic_version` is 021 or 022, and is safe to re-run;
- it creates the table, gives the app role SELECT, INSERT and UPDATE (no
  DELETE), and moves `alembic_version` to 022.

The readback queries are at the end of that file.

## How

1. Build: `gh workflow run hotfix-janua-api-primary-organization.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code and migrations are `b16869d7` plus the
     files of the eight earlier hotfixes from their sources (what production
     runs);
   - `org_claims_service.py`, `audit_logger.py` and `main.py` differ from
     production's copies by exactly `claims.diff`, `audit.diff` and
     `main.diff`. `main.diff` removes nothing, and its block is verbatim on
     `main`. The four new files do not exist in production;
   - the new image adds seven layers and changes or adds only those seven
     files, each byte-identical to its reviewed source;
   - discovery and the protected-resource client policy are identical between
     the images;
   - [`check_primary_org.py`](check_primary_org.py) passes. In the new image, a
     person with two active memberships and a primary organization gets that
     organization's `org_id` and application role, and the three routes are
     registered. A primary organization they are not a member of resolves to
     nothing, and `tenant_id` wins without reading the table. A failed read
     (no table) gives no org claims and no error, a single membership never
     reads the table, and the `User` model is untouched. In the base image,
     the app role and the routes are absent.

   It writes nothing to staging, production or the repository.
2. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` and fills in the exception record.
3. Migration (before or after the pin, see above): apply the operator SQL in
   the database pod and run its readback queries. Then a reviewed PR moves
   `apps/api/alembic/PROD_ALEMBIC_STATE.json` to `022_user_primary_organization`
   with that output.
4. Check after Argo syncs and the SQL:
   - the rollout is healthy and the running image ID is the pinned digest;
   - discovery and the JWKS are unchanged;
   - `GET /api/v1/internal/primary-organization/{user_id}` answers 200 for a
     known person;
   - after `POST …/set` for a staff account with several memberships, the read
     reports `token_org_id` and the expected `token_app_roles`, and a fresh
     session or OIDC token carries them;
   - people with one membership or a matching `tenant_id` see unchanged tokens.
5. Undo: revert the pin PR. The table can stay; nothing older reads it.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-16, in chat: «You have my GO for the hotfix». Scope: this primary-organization hotfix only (janua#822), on top of the current production digest `sha256:1b1e28de…` (janua#818). The merge of this folder, the build dispatch and the pin PR remain separate steps the owner's coordinator takes after review |
| Built by | (filled in by the pin PR: run link and `main` commit) |
| Hotfix digest | (filled in by the pin PR) |
| Replaces | `sha256:1b1e28de2e16d9672c5d536675f29a5784e556b5e0a14badfe2a999e7346c499` (janua#818) |
| Delta | `app/models/user_primary_organization.py`, `app/schemas/primary_organization.py`, `app/routers/v1/internal_primary_organization.py`, `alembic/versions/022_user_primary_organization.py` (new), `app/services/org_claims_service.py` and `app/services/audit_logger.py` from `main`, and production's `app/main.py` plus the registration (janua#822: `claims.diff`, `audit.diff`, `main.diff`) |

## Remove

Delete this folder, `.github/workflows/hotfix-janua-api-primary-organization.yml`
and `apps/api/tests/unit/core/test_hotfix_janua_api_primary_organization.py` in
the first normal promotion after the hold lifts.
