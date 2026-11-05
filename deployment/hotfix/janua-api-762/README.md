# janua#762 hotfix image (one-off)

## Why

janua#762 stopped the discovery documents from advertising
`registration_endpoint: …/api/v1/oauth/register`, a route Janua has never had: it
answered 404. An MCP client that tries dynamic registration before CIMD fails
before sign-in starts.

The fix is merged, but a normal promotion cannot ship it. `promote-to-prod.yml`
is held until isolated staging is proven (`scripts/staging/promotion_runtime_guard.py`,
[`docs/runbooks/isolated-staging-activation.md`](../../../docs/runbooks/isolated-staging-activation.md)).
Promoting `main` would also ship #758, which that runbook says must not reach
production before the proof.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:7c907661…`, built from `b16869d7`) and copies in one file:
`apps/api/app/core/oauth_metadata.py`. No dependency is reinstalled, so the
framework versions are the ones production already runs.

Between `b16869d7` and `main`, the API application code differs in exactly two
files: this one and #758's `reserved_oauth_boundaries.py`. The hotfix takes only
the first.

## How

1. Build: `gh workflow run hotfix-janua-api-762.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code is exactly `b16869d7`;
   - the new image adds one layer and changes only `core/oauth_metadata.py`,
     byte-identical to the reviewed file;
   - its discovery document differs from the base only by the missing
     `registration_endpoint`.

   It prints the digest in the run summary. It writes nothing to staging,
   production or the repository.
2. Pin: a separate PR, reviewed and merged by the owner, changes only the
   `janua-api` digest in `k8s/overlays/production/kustomization.yaml`, and records
   the exception.
3. Check after Argo syncs:
   - both discovery documents have no `registration_endpoint`;
   - the CIMD `/api/v1/oauth/authorize` request still redirects to login;
   - the JWKS is unchanged;
   - the rollout is healthy.
4. Undo: revert the pin PR, or run `rollback-prod.yml` with a blank digest.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-05 (in session, after the promotion hold was explained) |
| Built by | [run 41954831187](https://github.com/madfam-org/janua/actions/runs/41954831187), from `main` at `f896df23`; all three proofs passed, then cosign-signed |
| Hotfix digest | `sha256:35c60b3935125a706941f724252f3a48409428d5ba55739b20cd428f37ba50f3` (tag `hotfix-762-f896df23…`) |
| Replaces | `sha256:7c9076615ad8345c88b8093e660a4484dd3ff6f0b9d43b11c28a9d85c5884676` (source `b16869d7`) |
| Delta | `app/core/oauth_metadata.py` only; the discovery documents lose `registration_endpoint` |
| Not shipped | #758 (`reserved_oauth_boundaries.py`) and everything else on `main` after `b16869d7` |
| Pinned by | the PR that sets the hotfix digest in `k8s/overlays/production/kustomization.yaml` |

An earlier run, 41952923922, failed its discovery check (fixed in #766). It
signed nothing, and its unsigned `hotfix-762-7518ff00…` tag is not used.

## Remove

Delete this folder and `.github/workflows/hotfix-janua-api-762.yml` in the
first normal promotion after isolated staging is proven. That promotion
replaces the hotfix digest with a staged one.
