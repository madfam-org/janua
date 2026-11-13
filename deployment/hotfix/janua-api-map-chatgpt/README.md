# ChatGPT on the MAP resource: hotfix image (owner exception)

## Why

Owner decision 2026-11-12: ChatGPT may connect to the MAP de Crea Tu Mundo MCP
resource under the same terms as Claude (janua#792). The change is merged on
`main`, but a normal promotion cannot ship it: `promote-to-prod.yml` is held until
isolated staging is proven (`scripts/staging/promotion_runtime_guard.py`), and
promoting `main` would ship far more than this change.

This folder follows the exception pattern of
[`../janua-api-reserved-boundaries/README.md`](../janua-api-reserved-boundaries/README.md).
Nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:b6e16fa5…`, the reserved-boundaries hotfix pinned by janua#789)
and adds two layers, one file each, from `main`:

- `apps/api/app/core/protected_resources.py`: the MAP resource's client policy
  pins ChatGPT's stable Client ID Metadata Document
  `https://chatgpt.com/oauth/client.json` and its redirect
  `https://chatgpt.com/connector_platform_oauth_redirect`; CSP `form-action`
  follows from it;
- `apps/api/app/services/client_id_metadata.py`: a document that says **or
  supports** `token_endpoint_auth_method: none` qualifies (ChatGPT prefers
  `private_key_jwt`), recorded as `none`; every CIMD client stays public (PKCE,
  never a secret).

Between production's source and `main`, these two files differ by exactly this
change (checked 2026-11-12 with `git diff b16869d7 origin/main`). No dependency
is reinstalled.

## How

1. Merge janua#792 first: the image takes both files as they are on `main` when
   the workflow is dispatched.
2. Build: `gh workflow run hotfix-janua-api-map-chatgpt.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code is `b16869d7` plus the two
     reserved-boundaries files from `ee7668b8` (what production runs);
   - the new image adds two layers and changes only the two files, each
     byte-identical to the reviewed source;
   - both discovery documents are identical;
   - the client policies, as loaded by each image ([`dump_policy.py`](dump_policy.py)),
     differ only by ChatGPT on the MAP resource
     ([`compare_policy.py`](compare_policy.py)): ChatGPT's published document goes
     from refused to accepted as a public client, Claude's stays accepted, a
     confidential-only document stays refused, every other resource is unchanged.
   It writes nothing to staging, production or the repository.
3. Pin: a separate PR, reviewed and merged by the owner, changes only the
   `janua-api` digest in `k8s/overlays/production/kustomization.yaml` and fills in
   the exception record below.
4. Check after Argo syncs:
   - the rollout is healthy and the running image ID is the pinned digest;
   - discovery and the JWKS are unchanged;
   - `GET /api/v1/oauth/authorize?response_type=code&client_id=https%3A%2F%2Fchatgpt.com%2Foauth%2Fclient.json&redirect_uri=https%3A%2F%2Fchatgpt.com%2Fconnector_platform_oauth_redirect&code_challenge=x&code_challenge_method=S256&state=probe`
     (no `resource`) answers `302` to the ChatGPT redirect with
     `error=invalid_target` and `iss`: the pod fetched ChatGPT's document
     (egress and the host's bot protection) and accepted it. A refusal page
     instead means the fetch or the document failed; the log line is
     `oauth.cimd.rejected` with its `reason`;
   - the same probe with Claude's client id still answers as before
     ([`../../../docs/runbooks/mcp-connector-post-promote.md`](../../../docs/runbooks/mcp-connector-post-promote.md)).
5. Undo: revert the pin PR.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-12 (in session): «Add ChatGPT too» |
| Built by | [run 43345492945](https://github.com/madfam-org/janua/actions/runs/43345492945), dispatched by the owner from `main` (`ae7a3f50`) on 2026-11-12 |
| Hotfix digest | `sha256:ae28948d88cbd9dcb0ee3795ec881e9c8ddbb7e68103b0c83f937e3d003926e4` (cosign-signed by that run) |
| Replaces | `sha256:b6e16fa59433bb9f4bdc662c3a0e9d20fb55dca3f546d2b016f2346d41c80d72` (janua#789) |
| Delta | `app/core/protected_resources.py` and `app/services/client_id_metadata.py` from `main` (janua#792) |

## Remove

Delete this folder and `.github/workflows/hotfix-janua-api-map-chatgpt.yml` in
the first normal promotion after the hold lifts.
