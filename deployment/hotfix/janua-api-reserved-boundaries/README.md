# Reserved OAuth boundaries hotfix image (owner exception)

## Why

Janua's OAuth reservation registry
([`apps/api/app/core/reserved_oauth_boundaries.py`](../../../apps/api/app/core/reserved_oauth_boundaries.py))
decides which audiences and scopes only a platform admin may put on a client. Its
own docstring says a sibling's new machine scope is reserved **and deployed**
before any client carrying it is provisioned. Several reservations are merged on
`main` but not running: the one-colon Dhanam writer scope, the Dhanam cost-events
writer scope, the PhyndCRM machine audience and read scope, and (once merged) the
COGS MCP read scopes and Nauta read scopes. The machine edges that use them wait
on this.

A normal promotion cannot ship them. `promote-to-prod.yml` is held until isolated
staging is proven (`scripts/staging/promotion_runtime_guard.py`,
[`docs/runbooks/isolated-staging-activation.md`](../../../docs/runbooks/isolated-staging-activation.md)).
Promoting `main` would also ship the hashed dependency lock rebuild, a much wider
change than these reservations.

This folder follows the janua#762 exception pattern
([`../janua-api-762/README.md`](../janua-api-762/README.md)). It is only for the
owner to use if the owner chooses the exception route; nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:7c907661…`, built from `b16869d7`) and adds one layer with two
files from `main`:

- `apps/api/app/core/reserved_oauth_boundaries.py`, the registry;
- `apps/api/app/core/oauth_metadata.py`, the janua#762 discovery fix, so this
  image also covers the janua#762 exception and replaces its pin.

No dependency is reinstalled, so the framework versions are the ones production
already runs. Between `b16869d7` and `main`, the API image's application code
differs in exactly these two files plus `app/core/test_config.py` (a test helper).

The registry only adds values to sets. A value added to a reserved set makes
registering or editing a client that carries it a platform-admin action. Token
issuance and resource-server checks do not read these sets, so no existing token
or client stops working; an organization admin can no longer edit a client of
theirs that holds a newly reserved value.

## How

1. If the COGS scopes should ship too, merge their reservation PR first. The
   image takes the registry as it is on `main` when the workflow is dispatched.
2. Build: `gh workflow run hotfix-janua-api-reserved-boundaries.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code is exactly `b16869d7`;
   - the new image adds one layer and changes only the two files, each
     byte-identical to the reviewed source;
   - its discovery document differs from the base only by the missing
     `registration_endpoint`;
   - its registry, as loaded by the image ([`dump_registry.py`](dump_registry.py)),
     is strictly tighter than the base's ([`compare_registry.py`](compare_registry.py)):
     no reserved value lost, no other value changed, no public name removed,
     predicates consistent with the sets.

   The run summary prints the digest and the added scopes and audiences. It
   writes nothing to staging, production or the repository.
3. Before pinning, run the read-only audit
   `apps/api/scripts/audit_reserved_oauth_clients.py` (it is self-contained and
   can be piped into a production pod). Any `review` row holding a newly reserved
   value belongs to a client an organization admin can no longer edit.
4. Pin: a separate PR, reviewed and merged by the owner, changes only the
   `janua-api` digest in `k8s/overlays/production/kustomization.yaml`, and records
   the exception. It supersedes the janua#762 pin PR if that one is still open.
5. Check after Argo syncs:
   - the rollout is healthy and the running image ID is the pinned digest;
   - both discovery documents have no `registration_endpoint`;
   - the JWKS is unchanged;
   - registering a client with a newly reserved scope as a non-admin answers 403
     (use a throwaway organization, never a real client).
6. Undo: revert the pin PR.

## Remove

Delete this folder, `.github/workflows/hotfix-janua-api-reserved-boundaries.yml`
and its test in the first normal promotion after isolated staging is proven.
That promotion replaces the hotfix digest with a staged one.
