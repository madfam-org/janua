# What production runs: base promotion plus hotfix images

`promote-to-prod.yml` is held until isolated staging is proven
(`scripts/staging/promotion_runtime_guard.py`,
[`docs/runbooks/isolated-staging-activation.md`](../../docs/runbooks/isolated-staging-activation.md)).
Since 2026-11-11 every change that reached production did so as an
**owner-exception hotfix image**: the image production ran, plus only the
reviewed files of one change, proven by its workflow before signing. Each
folder here is one such image; its README holds the reason, the proof steps
and the exception record (who approved it, the build run, the digest it
replaced). This page is the index: read it to answer "what code is in
production?" without walking the chain record by record.

**Current production pin** (`k8s/overlays/production/kustomization.yaml`,
`janua-api`): `sha256:44c4310d742f4720efca7158872a88497fee6fd910996635109353ba7e098678`,
the public-silent-auth hotfix, live since 2026-11-18 20:37Z.

## The chain, oldest first

**Base.** The last normal promotion, 2026-11-03 (`4d0b8ef1`, "promote
8dc7029"): `janua-api@sha256:7c9076615ad8345c88b8093e660a4484dd3ff6f0b9d43b11c28a9d85c5884676`,
whose application code and migrations are the tree at `b16869d7` (janua#757).
Every hotfix workflow re-proves this (`BASE_SOURCE` in its `env`).

Each row starts from the image of the row above it. "Source" is the commit the
files are taken from (the workflow's `*_SOURCE`); "Files" are paths under
`apps/api/app/` unless marked.

| # | Folder | Change(s) | Source | Files | Digest | Pinned by |
|---|---|---|---|---|---|---|
| 1 | [`janua-api-reserved-boundaries`](janua-api-reserved-boundaries/README.md) | #758, #775, #781, #782, #788; #762's discovery fix | `ee7668b8` | `core/reserved_oauth_boundaries.py`, `core/oauth_metadata.py` | `sha256:b6e16fa5…` | #789 (2026-11-11) |
| 2 | [`janua-api-map-chatgpt`](janua-api-map-chatgpt/README.md) | #792 | `ae7a3f50` | `core/protected_resources.py`, `services/client_id_metadata.py` | `sha256:ae28948d…` | #794 (2026-11-12) |
| 3 | [`janua-api-org-bound-login`](janua-api-org-bound-login/README.md) | #795 | `6f3b9b1a` | `auth/tenant_login_context.py`, `auth/hosted_security.py` | `sha256:f97bddd8…` | #797 (2026-11-13) |
| 4 | [`janua-api-org-role-shape`](janua-api-org-role-shape/README.md) | #801, #802 | `0742d02a` | `services/org_claims_service.py`, `services/role_service.py`, `services/organization_member_service.py` | `sha256:99f354a9…` | #805 (2026-11-15) |
| 5 | [`janua-api-entitlement-source`](janua-api-entitlement-source/README.md) | #811 | `7c6150ff` | `models/__init__.py` | `sha256:cf723284…` | #812 (2026-11-15) |
| 6 | [`janua-api-reservations-2`](janua-api-reservations-2/README.md) | #798, #799, #800, #801, #806 | `393a95b2` | `core/reserved_oauth_boundaries.py`, `services/client_privacy_notices.py`, `auth/hosted_locale.py`, `routers/v1/auth.py`, `config.py` | `sha256:78efc789…` | #813 (2026-11-15) |
| 7 | [`janua-api-json-encoding`](janua-api-json-encoding/README.md) | #815 | `e9442f2f` | `models/types.py` | `sha256:9bac9212…` | #816 (2026-11-16) |
| 8 | [`janua-api-webhooks`](janua-api-webhooks/README.md) | #817 | `505683db` | `services/webhooks.py`, `routers/v1/webhooks.py` | `sha256:1b1e28de…` | #818 (2026-11-16) |
| 9 | [`janua-api-primary-organization`](janua-api-primary-organization/README.md) | #822 | `54fbf9bf` | `models/user_primary_organization.py`, `schemas/primary_organization.py`, `routers/v1/internal_primary_organization.py`, `services/org_claims_service.py`, `services/audit_logger.py`, `main.py` (the folder's copy), `alembic/versions/022_user_primary_organization.py` | `sha256:cd6e19df…` | #824 (2026-11-16) |
| 10 | [`janua-api-contain-roles-guest`](janua-api-contain-roles-guest/README.md) | #826 | `35a37b6f` | `core/reserved_oauth_boundaries.py`, `routers/v1/guest.py` | `sha256:507e76f5…` | #828 (2026-11-16) |
| 11 | [`janua-api-hosted-locale`](janua-api-hosted-locale/README.md) | #814, #820 | `dbacd843` | `auth/hosted_locale.py`, `routers/v1/auth.py`; `routers/v1/oauth_provider.py` from the folder's `oauth_provider.py.shipped` | `sha256:b9396f85…` | #831 (2026-11-17) |
| 12 | [`janua-api-public-silent-auth`](janua-api-public-silent-auth/README.md) | #833 | `85f3e832` | `routers/v1/oauth_provider.py` from the folder's `oauth_provider.py.shipped` | `sha256:44c4310d…` | #835 (2026-11-18) |

A later row overrides an earlier one for the same path (row 6, then row 10,
for `core/reserved_oauth_boundaries.py`; row 4, then row 9, for
`services/org_claims_service.py`; row 6, then row 11, for
`routers/v1/auth.py` and `auth/hosted_locale.py`). The exact replay, in this
order, is the step "Base image is BASE_SOURCE plus the earlier hotfix files" of
[`.github/workflows/hotfix-janua-api-public-silent-auth.yml`](../../.github/workflows/hotfix-janua-api-public-silent-auth.yml),
which `diff -r`s it against the running image before every build. The next
hotfix copies that step and adds its own row.

[`janua-api-762`](janua-api-762/README.md) was never pinned on its own (no
production pin between the base and row 1): its one file (`core/oauth_metadata.py`) shipped inside row 1.

**Database.** Migrations are not shipped by these images (promote runs no
alembic). Production records `022_user_primary_organization`, applied by hand
on 2026-11-16 (janua#825,
[`apps/api/alembic/PROD_ALEMBIC_STATE.json`](../../apps/api/alembic/PROD_ALEMBIC_STATE.json)).

**Not in production.** Everything merged to `main` that no row above lists,
including janua#792's comment and janua#801's `roles` claim filter in
`routers/v1/oauth_provider.py` (rows 11 and 12 ship production's own copy
of that file plus only their merge's hunks, not `main`'s).

## Remove

When the hold lifts, the first normal promotion ships `main` and supersedes
every row; delete each folder, its workflow and its guard test in that
promotion (each README's "Remove" section), and this index with them.
