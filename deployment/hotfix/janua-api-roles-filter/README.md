# OIDC `roles` claim without organization strings shaped like application roles: hotfix image (owner exception)

**Status (2026-11-21): authored, not built or pinned.** Production runs row 14
(`janua-api@sha256:046d4686…`, janua#857). The full list of what production
runs is in [`../README.md`](../README.md).

## Why

janua#801 closed a gap in the `roles` claim: an organization admin can name a
member's role freely, so a membership role such as `nauta:platform-admin` would
reach `roles` next to real application-role grants, and no resource server can
tell the two apart. Since janua#801, a string containing the separator reaches
`roles` only from a live application-role grant
(`services/org_claims_service.py: organization_roles_for_roles_claim`).

Row 4 shipped that rule in the claims service (2026-11-15). The OIDC handler's
own copy in `_get_user_entitlements` never shipped: rows 11 and 12 shipped
production's copy of `routers/v1/oauth_provider.py`, and row 14 shipped the
split module `routers/v1/oauth_provider_shared.py` with production's lines on
purpose (its `oauth_provider_shared.diff`), because the owner had approved the
nine edge-hardening merges, not this change. This row ships that one hunk.

**Who it affects in production (read-only query, 2026-11-21, owner OK):** of 46
memberships, one has a role containing `:`. It is an owner account's
`nauta:platform-admin` in the ecosystem organization, and that same membership
holds a live `nauta:platform-admin` application-role grant, so its `roles`
claim keeps the string. No organization defines a custom role containing `:`.
Nobody loses access.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs (row 14)
and adds one layer: `apps/api/app/routers/v1/oauth_provider_shared.py` at
`SOURCE` (`ae191e86`, row 14's source; `apps/api/app` on `main` is still
exactly that tree). Against production's copy it differs by row 14's reviewed
hunk, reversed: `entitlements["roles"] = organization_roles_for_roles_claim(...)`
instead of collecting every active membership role.

Nothing else changes: no other file, package, migration or setting.

## Proof (the workflow, before signing)

1. The Dockerfile is the `FROM` and the one `COPY`, nothing else.
2. `apps/api/app` on `main` is `SOURCE`; the module is `SOURCE`'s; against row
   14's `.shipped` copy it differs by exactly row 14's `oauth_provider_shared.diff`.
3. The base is signed by row 14's workflow on `main` and carries row 14's copy
   of the module.
4. The built image has one added layer and differs from the base by that one
   file; migrations unchanged.
5. Both images import the whole application; discovery is identical;
   `_get_user_entitlements` uses `organization_roles_for_roles_claim` in the
   hotfix and not in the base.

## Steps

1. Build: `gh workflow run hotfix-janua-api-roles-filter.yml --repo madfam-org/janua --ref main -f reason="..."`.
2. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` to the digest the run's
   "Sign image with cosign" step prints, and fills in this record. After it
   rolls: the pods run the pinned digest, discovery and readiness answer, and a
   sign-in still works.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-21 (in session): after the read-only query was proposed, answered «you have my OK for the roles actionable». Scope: this one hunk, on top of production's row 14 |
| Built by | pending |
| Hotfix digest | pending |
| Replaces | `sha256:046d4686480e0eb73b6a5e8e1674b15936840eafcbc36fa1c5ee17ae702b0b2e` (janua#857) |
| Delta | `apps/api/app/routers/v1/oauth_provider_shared.py` at `ae191e86` |

## Remove

Delete this folder, `.github/workflows/hotfix-janua-api-roles-filter.yml` and
`apps/api/tests/unit/core/test_hotfix_janua_api_roles_filter.py` in the first
normal promotion after the hold lifts.
