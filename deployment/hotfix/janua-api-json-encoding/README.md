# JSON encoded once: hotfix image (owner exception)

## Why

Janua's JSON column type (`app/models/types.py`) `json.dumps`-ed every value and
the PostgreSQL JSONB driver encoded it again, so every ORM write was stored as a
JSON **string**. A read-only count on 2026-11-16 found 3,154 such values in 13
production columns (activity and audit logs, OAuth clients, sessions, consents,
user metadata, organization settings). The ORM decodes both shapes, but SQL-level
JSON queries never match those rows:

- webhook endpoint matching (`events @> [event]`): an endpoint created through the
  ORM would never receive events;
- compliance queries on audit metadata (`@>`, `->>`, paths): empty or short.

The fix is janua#815 (the type plus `scripts/normalize_jsonb_strings.py`).
`promote-to-prod.yml` is held until isolated staging is proven
(`scripts/staging/promotion_runtime_guard.py`), and promoting `main` would ship far
more than this file. This folder follows the exception pattern of
[`../janua-api-entitlement-source/README.md`](../janua-api-entitlement-source/README.md).
Nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:78efc789…`, the reservations-2 hotfix pinned by janua#813) and
adds one layer with one file from `main`:

- `apps/api/app/models/types.py`. Production's copy is byte-identical to the file
  at `BASE_SOURCE` (git blob `598a9d5b…`, also checked in the running pod on
  2026-11-16); the only difference is the hunk in [`types.diff`](types.diff).

## How

1. Build: `gh workflow run hotfix-janua-api-json-encoding.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code is `b16869d7` plus the files of the six
     earlier hotfixes from their sources (what production runs);
   - the JSON type differs from production's copy by exactly `types.diff`;
   - the new image adds one layer and changes only that file, byte-identical to
     the reviewed source;
   - discovery and the protected-resource client policy are identical;
   - the base binds a JSON string for PostgreSQL (the bug) and the new image binds
     the value as is, while still reading legacy strings and plain strings.
   It writes nothing to staging, production or the repository.
2. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` and fills in the exception record.
3. After Argo syncs and the rollout is healthy (running image ID = the pinned
   digest; discovery and JWKS unchanged), the operator unwraps the stored strings,
   dry run first:

   ```bash
   kubectl -n janua exec -i deploy/janua-api -c janua-api -- python - < apps/api/scripts/normalize_jsonb_strings.py
   kubectl -n janua exec -i deploy/janua-api -c janua-api -- python - --apply < apps/api/scripts/normalize_jsonb_strings.py
   ```

   It prints table/column names and counts, never values, and exits non-zero if
   anything is left. Running it before the image is live would let old pods
   re-encode new writes behind it.
4. Undo: revert the pin PR. Unwrapped rows need no undo: the old type reads real
   objects too.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-16 (in session): «Fix it here» (the systemic JSON fix). The merge, the build, the pin and the data cleanup are each approved when ready |
| Built by | not built yet |
| Hotfix digest | not built yet |
| Replaces | `sha256:78efc78925192d99f2116dbed27afcd46b9db96d27bcb7c029aaca73d681f858` (janua#813) |
| Delta | `app/models/types.py` from `main` (janua#815: the hunk in `types.diff`) |
