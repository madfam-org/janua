# Webhooks on the async session: hotfix image (owner exception)

## Why

Janua has never delivered a webhook: production's `webhook_deliveries` held 0
rows on 2026-11-16, while its one endpoint (`crm.madfam.io`, `user.created`, the
CRM's sign-up feed) has been active since April. `app/services/webhooks.py` failed
four ways, each caught and logged as «Error triggering webhook event»:

- it used the sync `Session` API (`db.query`, bare `db.commit()`) on the
  `AsyncSession` the app passes (sign-up, and the webhooks API);
- it matched subscriptions with `events.contains([...])`, which compiles to
  `LIKE` on Janua's Text-based JSON type and PostgreSQL rejects for JSONB;
- it read `settings.API_VERSION`, which Janua's settings do not have;
- it built `WebhookDelivery(attempt=…)` and wrote `status_code`, `delivered_at`
  and `error`, none of which exist on the model (`status`, `attempts`,
  `last_attempt`, `response_status`, `error_message` do).

The webhooks API's delivery schema used the same wrong names. The fix is
janua#817. `promote-to-prod.yml` is held, so this follows the exception pattern of
[`../janua-api-json-encoding/README.md`](../janua-api-json-encoding/README.md).
Nothing here runs on merge.

## What

[`Dockerfile`](Dockerfile) starts from the exact image production runs
(`janua-api@sha256:9bac9212…`, the JSON-encoding hotfix pinned by janua#816) and
adds two layers, one file each, from `main`:

- `apps/api/app/services/webhooks.py` (the hunk in [`service.diff`](service.diff));
- `apps/api/app/routers/v1/webhooks.py` (the hunk in [`router.diff`](router.diff)).

Production's copies are byte-identical to the files at `BASE_SOURCE` (checked in
the running pod on 2026-11-16).

## How

1. Build: `gh workflow run hotfix-janua-api-webhooks.yml --repo madfam-org/janua --ref main -f reason="..."`.
   The workflow refuses any ref but `main`. Before it signs anything, it proves:
   - the base image's application code is `b16869d7` plus the files of the seven
     earlier hotfixes from their sources (what production runs);
   - each file differs from production's copy by exactly its reviewed hunk;
   - the new image adds two layers and changes only those files, byte-identical
     to the reviewed sources;
   - discovery and the protected-resource client policy are identical;
   - the base matches synchronously with `db.query` (the bug) and the new image on
     the async session, with the model's delivery fields in the API schema.
   It writes nothing to staging, production or the repository.
2. Pin: a separate PR changes only the `janua-api` digest in
   `k8s/overlays/production/kustomization.yaml` and fills in the exception record.
3. Check after Argo syncs: rollout healthy on the pinned digest; discovery and
   JWKS unchanged; the next sign-up records a `webhook_deliveries` row for the CRM
   endpoint (status, attempts, response status).
4. Undo: revert the pin PR.

## Exception record

| | |
|---|---|
| Approved by | Owner, 2026-11-16 (in session): «Fix webhooks». The merge, the build and the pin are each approved when ready |
| Built by | not built yet |
| Hotfix digest | not built yet |
| Replaces | `sha256:9bac921211d652922f61571e9d1129da19df49725067bfabbd0e67b224910c2c` (janua#816) |
| Delta | `app/services/webhooks.py` and `app/routers/v1/webhooks.py` from `main` (janua#817: `service.diff`, `router.diff`) |
