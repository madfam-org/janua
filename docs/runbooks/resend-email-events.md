# Resend email events (delivered / opened / clicked / bounced)

Janua receives Resend's signed webhooks, stores a minimized row per event, and
serves them per sending app. A sending app (by its own `source_app`) joins them to the
messages it sent through `POST /api/v1/internal/email/send` by `email_id`,
which is the `message_id` Janua returned on send.

## Endpoints

| Route | Auth | Purpose |
|---|---|---|
| `POST /api/v1/email/webhooks/resend/{cuenta}` | Svix signature (per Resend account) | Receiver. `cuenta` = `platform` or a tenant account's slug (`WEBHOOK_SECRET_SETTINGS` in `app/services/email_events.py`). |
| `GET /api/v1/internal/email/events?source_app=&after=&limit=` | `X-Internal-API-Key` | Per-app feed, cursor-paginated. |
| `POST /api/v1/internal/email/preview` | `X-Internal-API-Key` | Render-only preview of a send. Never sends. |
| `GET /api/v1/internal/email/preview/templates` | `X-Internal-API-Key` | Previewable templates with their required variables. |
| `GET /e/o/{token}.gif` | none (public, tracking host) | First-party open pixel. Always the same GIF. |
| `GET /e/c/{token}/{index}` | none (public, tracking host) | First-party click: 302 to the stored target, else the tenant's site. |

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
   `secret/janua#resend_webhook_secret_<cuenta>`, where `<cuenta>` is the tenant
   account's slug (and, only if the platform account
   also gets a webhook, `#resend_webhook_secret_platform`). THEN add the mapping
   to the enclii-managed ExternalSecret
   (`enclii: infra/k8s/base/external-secrets/vault-secrets/janua-secrets.yaml`),
   because that ExternalSecret is all-or-nothing and fails to sync if a property
   is missing:
   ```yaml
       - secretKey: resend-webhook-secret-<cuenta>
         remoteRef:
           key: secret/janua
           property: resend_webhook_secret_<cuenta>
   ```
   The janua-api Deployment already reads `resend-webhook-secret-<cuenta>` /
   `resend-webhook-secret-platform` as optional env vars. Until they exist the
   receiver answers 404 for that account and stores nothing.
   Write it, check its shape and restart janua-api as in
   [`secrets/resend-webhook-secret-rotation.md`](secrets/resend-webhook-secret-rotation.md)
   (hidden prompt into `vault kv patch`, never `vault kv put`).
3. **Resend (the tenant's account)**: Webhooks, add endpoint
   `https://auth.madfam.io/api/v1/email/webhooks/resend/<cuenta>` with events
   `email.sent`, `email.delivered`, `email.delivery_delayed`, `email.bounced`,
   `email.complained`, `email.opened`, `email.clicked`, `email.suppressed`.
   Order note: the secret only exists after the endpoint is created, so the
   first deliveries get 404 and Resend retries them until the secret reaches
   the pod.
4. **Tracking**: ~~enable open/click tracking on the tenant's sending domain in Resend~~
   **SUPERSEDED 2026-09-25** by «First-party measurement» below. Resend
   tracking stays OFF and `EMAIL_TRACKED_SENDER_DOMAINS` stays EMPTY, so the
   branded sign-in email keeps its HTML. (The mechanism is kept: if Resend
   tracking were ever enabled on a domain, roll that env var out FIRST, then
   flip tracking in Resend, so sign-in links are never rewritten.)
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

## First-party measurement (opens and clicks measured by Janua, not Resend)

Owner decision 2026-09-25: login mail stays branded and is never measured;
money mail (a tenant portal's monthly billing notice) is measured. Resend's tracking is
per-domain, and turning it on for the tenant's sending domain would push every token email
from that domain to text-only. So **Resend open/click tracking stays OFF and
`EMAIL_TRACKED_SENDER_DOMAINS` stays empty**; Janua measures the messages a
caller opts in, on a tracking host on the tenant's own domain.

**Who is measured.** A message sent through `POST /api/v1/internal/email/send`
with `"track_engagement": true`, and only when ALL hold; otherwise it is sent
unmodified and `email.engagement_not_instrumented` logs the reason:

- not token mail: `contains_token_link` is false AND no link in the HTML has a
  credential-looking parameter (the same detector as above);
- it still has an HTML part;
- its sender binding has a tracking host (the setting its `tracking_host_setting`
  names; the platform binding has none) on the domain of the From actually used
  (a tenant message that fell back to `hola@madfam.io` is not measured).

Sign-in, reset, verification and invitation mail never set the flag, and would
be refused by the rules above if they did. Templates (`/send-template`) and the
preview are never instrumented.

**What changes in the message.** HTML part only; the text part is byte-identical.
Each http(s) link (not `mailto:`/`tel:`, not already on the tracking host)
becomes `{host}/e/c/{token}/{i}`, and a 1x1 pixel `{host}/e/o/{token}.gif` goes
before `</body>`. One 256-bit token per message and recipient; only its SHA-256
is stored (`email_tracking_links`), with the original targets, the Resend
account and tags, and the Resend `email_id` bound right after the send.

**What the endpoints do.** Public, no auth, no cookies, not in OpenAPI. The pixel
is always the same GIF with `Cache-Control: no-store`. A click is a 302 to the
target stored for (token, index), never to anything in the request; an unknown
token, a bad index or a database error is a 302 to the tenant's site
(the binding's `default_site` on a tenant's tracking host, `https://madfam.io` elsewhere),
chosen by the Host header alone, so the answer reveals nothing. Unknown tokens
write nothing.

**What is stored per event.** A row in `email_events` with `source='first_party'`,
`email.opened` / `email.clicked`, the time, `source_app`/`org_id`, and for a
click the target reduced to `scheme://host/path` (same minimization as webhook
clicks). No IP, no user agent. A coarse `possible_prefetch` flag is computed in
memory (Apple Mail Privacy Protection, link scanners, HEAD requests, hits within
15 s of the send). Deduped: one open per message and one click per link, plus
separately the first hit that looked automatic, so a prefetch cannot hide the
person's own open. They reach the per-app feed with the webhook events, same
shape, plus `"source": "first_party"` (and `"possible_prefetch": true` when set).

### Owner steps (in order)

1. **Apply the SQL**: `docs/ops/sql/019_email_first_party_engagement.sql` in the
   data/postgres pod (`psql -U postgres -d janua -v ON_ERROR_STOP=1 -f ...`). It
   refuses unless production is at `018_email_events`. Keep the post-commit
   verification output for step 5.
2. **Route the tracking host to janua-api** through Enclii: a DNS record and a
   tunnel route for `<tracking-host>` (a name on the tenant's own domain) to the
   janua-api service, like `auth.madfam.io`. Only `/e/o/*` and `/e/c/*` are
   served there: `TrackingHostScopeMiddleware` answers 404 to every other path
   on a tracking host (and refuses websockets), so trusting the host does not
   expose sign-in, reset or OIDC discovery under the tenant's domain. The host must reach janua with its own `Host`
   header: janua-api trusts it (TrustedHostMiddleware) because it is derived
   from the binding's tracking-host setting at startup.
3. **Set the binding's tracking-host setting** (the env var its
   `tracking_host_setting` names in `sender_binding.py`) to
   `https://<tracking-host>` on janua-api
   (https origin only: no path, no port). Unset or invalid = the tenant's mail is never
   instrumented.
4. **Promote** (`promote-to-prod`, with `migrations_acknowledged=true`: the
   promote guard reads the ledger, which still says 018 until step 5).
   Then check: `curl -sI https://<tracking-host>/e/o/x.gif` answers
   `200 image/gif` with `no-store`; `curl -sI https://<tracking-host>/e/c/x/0`
   answers `302` to the tenant's site.
5. **Ledger PR**: after reading the database with `alembic_converge.py --check`,
   record `019_email_first_party_engagement` in
   `apps/api/alembic/PROD_ALEMBIC_STATE.json` (see ALEMBIC_CONVERGENCE.md),
   pasting the step-1 verification output.

Only after these may a sending app set `track_engagement: true`. Before
this ships, the field is silently ignored (pydantic drops unknown fields), so an
early flag measures nothing rather than failing the send.
