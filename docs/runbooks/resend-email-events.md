# Resend email events (delivered / opened / clicked / bounced)

Janua receives Resend's signed webhooks, stores a minimized row per event, and
serves them per sending app. MAP (`source_app=crea-map`) joins them to the
messages it sent through `POST /api/v1/internal/email/send` by `email_id`,
which is the `message_id` Janua returned on send.

## Endpoints

| Route | Auth | Purpose |
|---|---|---|
| `POST /api/v1/email/webhooks/resend/{cuenta}` | Svix signature (per Resend account) | Receiver. `cuenta` = `ctm` or `platform`. |
| `GET /api/v1/internal/email/events?source_app=&after=&limit=` | `X-Internal-API-Key` | Per-app feed, cursor-paginated. |
| `POST /api/v1/internal/email/preview` | `X-Internal-API-Key` | Render-only preview of a send. Never sends. |
| `GET /api/v1/internal/email/preview/templates` | `X-Internal-API-Key` | Previewable templates with their required variables. |

The feed contract is documented in `apps/api/app/routers/v1/internal_email_events.py`,
the preview contract in `apps/api/app/routers/v1/email_preview.py`.

## What is stored (and what is not)

Stored: provider, account, Svix delivery id (unique), Resend `email_id`, event
type, when it happened, the `source_app` / `org_id` tags Janua put on the send,
bounce/suppression type and subtype, and for clicks the link reduced to
`scheme://host/path` (long opaque path segments become `{redacted}`).

Never stored: recipient or sender address, subject, body, IP address, user
agent, bounce diagnostic text, the query string or fragment of a clicked link.

## Owner steps (in order)

1. **Apply the SQL**: `docs/ops/sql/018_email_events.sql` in the data/postgres
   pod (`psql -U postgres -d janua -v ON_ERROR_STOP=1 -f ...`). Paste the
   post-commit verification queries at the bottom of the file into the ledger PR.
2. **Secrets.** Generate nothing by hand: Resend shows the signing secret
   (`whsec_...`) when the webhook is created in step 3. Write it to Vault
   `secret/janua#resend_webhook_secret_ctm` (and, only if the platform account
   also gets a webhook, `#resend_webhook_secret_platform`). THEN add the mapping
   to the enclii-managed ExternalSecret
   (`enclii: infra/k8s/base/external-secrets/vault-secrets/janua-secrets.yaml`),
   because that ExternalSecret is all-or-nothing and fails to sync if a property
   is missing:
   ```yaml
       - secretKey: resend-webhook-secret-ctm
         remoteRef:
           key: secret/janua
           property: resend_webhook_secret_ctm
   ```
   The janua-api Deployment already reads `resend-webhook-secret-ctm` /
   `resend-webhook-secret-platform` as optional env vars. Until they exist the
   receiver answers 404 for that account and stores nothing.
3. **Resend (CTM account)**: Webhooks, add endpoint
   `https://auth.madfam.io/api/v1/email/webhooks/resend/ctm` with events
   `email.sent`, `email.delivered`, `email.delivery_delayed`, `email.bounced`,
   `email.complained`, `email.opened`, `email.clicked`, `email.suppressed`.
   Order note: the secret only exists after the endpoint is created, so the
   first deliveries get 404 and Resend retries them until the secret reaches
   the pod.
4. **Tracking**: enable open/click tracking on `creatumundo.mx` in Resend (it
   is a per-domain setting and needs its tracking subdomain verified), then set
   `EMAIL_TRACKED_SENDER_DOMAINS=creatumundo.mx` on janua-api. From then on,
   any token-bearing message from that domain goes out text-only. Set the env
   var no later than enabling tracking; setting it earlier only costs HTML on
   token mail, never correctness.
5. **Ledger PR**: after reading the database, record `018_email_events` in
   `apps/api/alembic/PROD_ALEMBIC_STATE.json` (see ALEMBIC_CONVERGENCE.md).
6. **Promote.**

## Token links are never tracked

When the From domain is in `EMAIL_TRACKED_SENDER_DOMAINS`, these go out
text-only (no HTML part, so no rewritten links and no pixel):

- Janua's own auth mail (`EmailService`): magic link, password reset, email
  verification (method and background task), organization invitation.
- `ResendEmailService`: verification, password reset, invitation, data-export
  download link, MFA recovery codes.
- `/internal/email/send-template`: `auth/magic-link`, `auth/password-reset`,
  `auth/email-verification`, `invitation/team-invite`, `invitation/creator-invite`.
- `/internal/email/send`: when the caller sets `contains_token_link: true`, or
  when any link in the HTML has a credential-looking query/fragment parameter
  (`token`, `code`, `signature`, ...).

Opens are not reported for text-only messages; that is the trade.
