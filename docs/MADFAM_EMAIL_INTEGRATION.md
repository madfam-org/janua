# MADFAM Centralized Email Integration

This document describes how to deploy and test the centralized Janua email service for all MADFAM applications.

## Send receipt contract (2026-09-22)

`POST /send` and `POST /send-template` return the same receipt:

| `delivery_status` | `success` | Meaning |
|---|---|---|
| `accepted` | `true` | Every requested recipient has a provider acceptance result and message ID. This is not an inbox-delivery receipt. |
| `simulated` | `false` | Email is disabled or using the development console. Nothing was transmitted. |
| `failed` | `false` | A recipient was rejected, the provider failed, or no acceptance receipt was returned. |

The `to` list must be nonempty. A partially accepted batch is `failed`; do not
blindly replay the whole batch because some recipients may already have been
accepted. The current response retains the final provider `message_id` for a
successful batch. Consumers requiring individual receipts should send one
recipient per request. A 2xx response alone is never evidence of acceptance.

This intentionally changes the old disabled/console success behavior. Rehearsal
clients must recognize `simulated` and must not stamp a real sent/delivered date.
Delivery and bounce reconciliation, durable retries and provider idempotency
remain separate work; this change does not establish exactly-once delivery.

Both Python Resend adapters use the shared account transport. Service construction
never changes the SDK's global credential. All platform and tenant sends select
an explicit account under the same lock and restore the prior SDK state even on
failure. Provider calls without an ID are rejected. Simulation and provider-error
logs omit recipient addresses, message contents and provider exception payloads.

Validation uses provider stubs and controlled concurrent threads; no real mail
is sent. Promote through the normal isolated staging/soak workflow. Verify real
provider acceptance only with an explicitly authorized test recipient.

## Quota refusals and per-account usage (2026-09-28)

A tenant on its own Resend account (today one vCTO client; see the bindings in `sender_binding.py`)
is bound by that account's plan: on the free plan, 100 messages per UTC calendar
day (reset at 00:00 UTC, not a rolling window) and 3,000 per month. Every To, CC
and BCC recipient counts, and inbound mail counts too
([Resend: account quotas](https://resend.com/docs/knowledge-base/account-quotas-and-limits)).
Over quota, Resend answers HTTP 429 `daily_quota_exceeded` or
`monthly_quota_exceeded` ([Resend: errors](https://resend.com/docs/api-reference/errors)).

- **Refusals keep their code.** `POST /send` and `POST /send-template` still
  return `success: false`, and add `error_code: "daily_quota_exceeded"` or
  `"monthly_quota_exceeded"` when that was the provider's reason (absent/null
  otherwise; `rate_limit_exceeded` is a per-second limit, not a quota). A caller
  can then queue the message for after the reset instead of reporting a bad
  address.
- **Usage per account.** `GET /api/v1/internal/email/usage?org_id=<uuid>&days=<1..31>`
  (same `X-Internal-API-Key`) returns `{cuenta, window: "utc_day", as_of, today,
  month, days: [{date, sent}]}` counted from the stored `email.sent` webhook events
  of the org's OWN account, whichever app sent them. 404 when the org sends on the
  shared platform account or its account's webhook is not configured. Counts only.
  Contract and limits: `app/routers/v1/internal_email_usage.py`,
  `app/services/email_usage.py`.

## Register and the monthly billing notice (2026-10-14)

**`formality` on `POST /send-template`.** Optional, `"tu"` or `"usted"` exactly
(anything else is `422`; `null` or absent means "not named"). It is the highest
tier of the register precedence, as on the magic link: the request, then the
recipient's stored `users.spanish_formality` (looked up per recipient by address;
an unknown, ambiguous or unreachable answer falls through and never blocks the
send), then the template's own voice, then `usted`. A template's voice is its
registry `default_formality` when it declares one (`billing/cfdi`: `usted`, MADFAM's
fiscal voice, so a `tú` product host does not change it) and otherwise the
requesting product's (`email_branding.default_formality_for`). The register only
changes templates that ship a `tú` file (`TEMPLATE_FILENAMES_TU`: today
`billing/cfdi`, subject «Tu CFDI …»); for every other template the caller's copy
already carries its register and the stored value is not looked up.
`POST /preview` takes the same field but never reads the stored register.

**`billing/aviso-de-cobro`.** The monthly billing notice nauta sends to a vCTO
client. Spanish, HTML + text, subject `{asunto}`, every value HTML-escaped, no
default sender (the platform sender applies). The copy arrives composed in the
reader's register; the template only lays it out, so it has one variant.

| Kind | Variables |
|---|---|
| Required | `asunto`, `preencabezado`, `marca`, `etiqueta`, `titulo`, `saludo`, `introduccion`, `total`, `moneda`, `total_nota`, `periodo`, `fecha_pago`, `factura_cuando`, `subtotal`, `iva_etiqueta`, `iva`, `total_linea`, `pago_titulo`, `pago_nota`, `factura_nota`, `cierre`, `firma_nombre`, `firma_cargo`, `pie`, `pie_nota` |
| Required lists (non-empty) | `conceptos[{concepto, monto, detalle?}]`, `pago_datos[{etiqueta, valor}]` |
| Optional | `fecha_pago_nota`, `cta_comprobante_etiqueta` + `cta_comprobante_url`, `entregado_titulo`, `entregado_periodo`, `viene_titulo`, `acciones_titulo`, `acciones_enlace_etiqueta` + `acciones_enlace_url`, `estado_cuenta_etiqueta` + `estado_cuenta_url` |
| Optional lists | `entregado_destacados[{valor, etiqueta}]`, `entregado[{titulo, detalle?}]`, `viene[{cuando, que}]`, `acciones[{titulo, detalle?}]` |

Item values are strings or numbers; `detalle` may be omitted. A list that breaks
its shape is `400 Invalid template variables: <path>` (e.g. `pago_datos[0].valor`).
A section renders only when it is complete: «entregado» needs `entregado_titulo`
and at least one of its two lists, «viene» and «acciones» need their title and
list, a link needs its label and an `https://` (or, for the receipt button,
`mailto:`) URL. Anything less drops the whole section, heading included. Rows
and section logic: `app/routers/v1/email_billing_notice.py`.

## BCC on template sends and the operator alert (2026-10-15)

**`bcc` on `POST /send-template`.** Optional list of addresses (`null`, absent
or `[]` mean none; an invalid address is a `422`). `/send-template` sends each
`to` address a message of its own, rendered in that recipient's register, so the
BCC does **not** ride on every message: it rides on the message to the **first**
address in `to` only. A BCC holder therefore receives exactly one copy, and it is
exactly the message that first recipient received (same register, same greeting).
The other recipients' messages never carry it. An address that is also in `to`
is dropped from the BCC (case-insensitive; it already gets its own message), and
a repeated address is kept once. Everything else (subject, sender, `reply_to`,
attachments, tags, the receipt) is unchanged. Every BCC address counts against
the sending Resend account's quota. Put the recipient whose copy the BCC holder
should see first in `to` (nauta: the client, with the advisor in `bcc`). `/send`
is unchanged: its `cc`/`bcc` still ride on every message.

**`ops/alert`.** A generic operator alert for MADFAM services (first caller:
nauta's worker, for its fiscal-edge probe: "unreadable", then "recovered").
Spanish, HTML + text, subject `{asunto}`, every value HTML-escaped, no default
sender (the platform sender applies, as for the other operator notices). It is
internal and addresses nobody, so it has one register-neutral variant: the
template's own words are labels with no tú/usted marker, and `formality` changes
nothing.

| Variable | Kind | Use |
|---|---|---|
| `asunto` | required | The subject line. |
| `titulo` | required | The heading (what happened, in one line). |
| `detalle` | required | Multi-line plain text. Each line is escaped and a newline becomes a line break in the HTML; the text part carries it as is. |
| `servicio` | required | Which service raised it, e.g. `Nauta · worker`. |
| `ocurrio` | required | When, as a human timestamp, e.g. `15 de octubre de 2026, 14:05 (CDMX)`. |
| `accion_url` | optional | An `https://` link (plain host). Anything else (http, `mailto:`, `javascript:`, quotes or brackets) is ignored. |
| `accion_texto` | optional | The button label. Defaults to «Abrir enlace» when only `accion_url` is given. Ignored without a usable `accion_url`. |

Without a usable `accion_url` the alert has no button in the HTML and no link
line in the text part. Derived slots: `app/routers/v1/email_ops_alert.py`.

```json
{
  "to": ["operaciones@example.com"],
  "template": "ops/alert",
  "variables": {
    "asunto": "[Nauta] El borde fiscal no se puede leer",
    "titulo": "El borde fiscal no se puede leer",
    "detalle": "GET https://fiscal.example.com/health -> 503\nÚltimo éxito: 15 de octubre de 2026, 12:00 (CDMX)",
    "servicio": "Nauta · worker",
    "ocurrio": "15 de octubre de 2026, 14:05 (CDMX)",
    "accion_url": "https://nauta.example.com/ops/fiscal",
    "accion_texto": "Abrir el panel fiscal"
  },
  "bcc": ["guardia@example.com"],
  "source_app": "nauta",
  "source_type": "notification"
}
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    JANUA EMAIL API                           │
│         /api/v1/internal/email/* (Resend)                    │
│                                                              │
│  Endpoints:                                                  │
│  - POST /send          (custom emails)                       │
│  - POST /send-template (template-based)                      │
│  - GET  /templates     (list available)                      │
│  - GET  /health        (service status)                      │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────┬───────┼───────┬───────────┐
        ▼           ▼       ▼       ▼           ▼
   Dhanam    Digifab-Quoting  Forj  Avala   madfam-site
   (NestJS)    (NestJS)      (TS)  (NestJS)   (Next.js)
```

## Prerequisites

1. **Resend Account**: Get an API key from [resend.com](https://resend.com)
2. **Domain Verification**: Verify sending domains in Resend dashboard
   - `madfam.io` (madfam-site)
   - `dhan.am` (Dhanam)
   - `digifab.io` (Digifab-Quoting)
   - `avala.mx` (Avala)
   - `forj.mx` (Forj)

## Step 1: Generate API Keys

Generate secure keys for production:

```bash
# Generate INTERNAL_API_KEY (share across all services)
openssl rand -hex 32
# Example: <GENERATED-openssl-rand-hex-32>

# Generate JANUA_WEBHOOK_SECRET (for webhook signature verification)
openssl rand -hex 32
# Example: <GENERATED-openssl-rand-hex-32>
```

## Step 2: Configure Janua (Central Hub)

### Environment Variables

Add to Janua's `.env` or secrets management:

```env
# Email Provider
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Internal API (service-to-service)
INTERNAL_API_KEY=<GENERATED-openssl-rand-hex-32>

# Webhook Secret (for billing webhooks to apps)
JANUA_WEBHOOK_SECRET=<GENERATED-openssl-rand-hex-32>
```

### Deploy Janua

```bash
cd janua
docker-compose -f deployment/production/docker-compose.production.yml up -d
```

### Verify Email Service

```bash
curl -X GET https://api.janua.dev/api/v1/internal/email/health \
  -H "X-Internal-API-Key: YOUR_INTERNAL_API_KEY"
```

Expected response:

```json
{
  "status": "healthy",
  "resend_configured": true,
  "internal_api_configured": true,
  "templates_available": 22
}
```

`templates_available` is computed live as `len(EMAIL_TEMPLATES)` (see
`apps/api/app/routers/v1/email.py`), so it tracks the registry — the number
above is the count as of this writing, not a fixed value.

## Step 3: Configure Consuming Apps

### Dhanam

```env
# .env
JANUA_API_URL=https://api.janua.dev
JANUA_INTERNAL_API_KEY=<GENERATED-openssl-rand-hex-32>
JANUA_WEBHOOK_SECRET=<GENERATED-openssl-rand-hex-32>
```

### Digifab-Quoting

```env
# .env
JANUA_API_URL=https://api.janua.dev
JANUA_INTERNAL_API_KEY=<GENERATED-openssl-rand-hex-32>
JANUA_WEBHOOK_SECRET=<GENERATED-openssl-rand-hex-32>
```

### Avala

```env
# .env
JANUA_API_URL=https://api.janua.dev
JANUA_INTERNAL_API_KEY=<GENERATED-openssl-rand-hex-32>
JANUA_WEBHOOK_SECRET=<GENERATED-openssl-rand-hex-32>
```

### Forj

```env
# .env
JANUA_API_URL=https://api.janua.dev
JANUA_INTERNAL_API_KEY=<GENERATED-openssl-rand-hex-32>
```

### madfam-site

```env
# .env
JANUA_API_URL=https://api.janua.dev
JANUA_INTERNAL_API_KEY=<GENERATED-openssl-rand-hex-32>
```

## Step 4: Run Database Migrations

Apply Prisma migrations to add Janua billing fields:

### Dhanam

```bash
cd dhanam/apps/api
npx prisma migrate deploy
# Or for development:
npx prisma db push
```

### Digifab-Quoting

```bash
cd digifab-quoting/apps/api
npx prisma migrate deploy
```

### Avala

```bash
cd avala/packages/db
npx prisma migrate deploy
```

## Step 5: Configure Webhook Endpoints

Register these webhook URLs in Janua's webhook management:

| App     | Webhook URL                                    | Events                    |
| ------- | ---------------------------------------------- | ------------------------- |
| Dhanam  | `https://api.example.com/billing/webhook`      | subscription._, payment._ |
| Digifab | `https://api.digifab.io/billing/webhook/janua` | subscription._, payment._ |
| Avala   | `https://api.avala.mx/billing/webhook/janua`   | subscription._, payment._ |

## Testing

### Test Email Sending

```bash
# Test custom email
curl -X POST https://api.janua.dev/api/v1/internal/email/send \
  -H "Content-Type: application/json" \
  -H "X-Internal-API-Key: YOUR_KEY" \
  -d '{
    "to": ["test@example.com"],
    "subject": "Test Email",
    "html": "<h1>Hello World</h1>",
    "source_app": "dhanam",
    "source_type": "test"
  }'

# Test template email
curl -X POST https://api.janua.dev/api/v1/internal/email/send-template \
  -H "Content-Type: application/json" \
  -H "X-Internal-API-Key: YOUR_KEY" \
  -d '{
    "to": ["test@example.com"],
    "template": "auth/welcome",
    "variables": {
      "user_name": "John",
      "app_name": "Dhanam",
      "login_url": "https://app.dhan.am",
      "support_email": "support@dhan.am"
    },
    "source_app": "dhanam",
    "source_type": "auth"
  }'
```

### Test from NestJS App (Dhanam/Digifab/Avala)

```typescript
// In your service or controller
const januaEmailService = this.moduleRef.get(JanuaEmailService);

// Send welcome email
await januaEmailService.sendWelcomeEmail("user@example.com", "John Doe");

// Send custom template
await januaEmailService.sendTemplateEmail({
  to: "user@example.com",
  template: "billing/payment-succeeded",
  variables: {
    amount: "29.99",
    currency: "USD",
    invoice_number: "INV-001",
  },
});
```

### Test Webhook Reception

```bash
# Simulate Janua webhook
curl -X POST https://api.example.com/billing/webhook \
  -H "Content-Type: application/json" \
  -H "X-Janua-Signature: YOUR_SIGNATURE" \
  -d '{
    "id": "evt_test_123",
    "type": "subscription.created",
    "timestamp": "2025-01-01T00:00:00Z",
    "data": {
      "customer_id": "cus_123",
      "subscription_id": "sub_123",
      "plan_id": "premium",
      "provider": "conekta"
    },
    "source_app": "janua"
  }'
```

## Available Templates

The registry is the source of truth. It lives in two paired dictionaries in
`apps/api/app/routers/v1/email.py` — `EMAIL_TEMPLATES` (id → description,
`required`/`optional` variables, `subject`, and any per-template default sender)
and `TEMPLATE_FILENAMES` (id → whitelisted HTML filename under
`apps/api/templates/emails/`). Every id appears in **both** dictionaries; the
`_get_safe_template_path()` whitelist check requires it. `GET /templates`
returns this same list at runtime, so a live service is always the definitive
answer — the table below is a snapshot for convenience.

The **Render** column reflects whether a dedicated HTML file exists for the id.
When it does not, `send-template` still succeeds: it falls back to
`generate_fallback_html()`, a generic frame built from the supplied variables
(see [Render mechanism](#render-mechanism) below). The **Sender** column shows
how the From line is chosen — see [Sender resolution](#sender-resolution).

| Template ID                          | Description                                                                     | Required Variables                                                                                          | Render    | Sender                          |
| ------------------------------------ | ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | --------- | ------------------------------- |
| `auth/welcome`                       | Welcome email for new users                                                     | `user_name`, `app_name`                                                                                     | dedicated | per org_id                      |
| `auth/password-reset`                | Password reset request                                                          | `reset_link`, `expires_in`                                                                                  | dedicated | per org_id                      |
| `auth/email-verification`            | Email address verification                                                      | `verification_link`, `expires_in`                                                                           | fallback  | per org_id                      |
| `auth/magic-link`                    | Passwordless login link                                                         | `magic_link`, `expires_in`                                                                                  | fallback  | per org_id                      |
| `billing/invoice`                    | Invoice notification                                                            | `invoice_number`, `amount`, `currency`, `due_date`                                                          | fallback  | per org_id                      |
| `billing/payment-succeeded`          | Payment confirmation                                                            | `amount`, `currency`                                                                                        | dedicated | per org_id                      |
| `billing/payment-failed`             | Payment failure notification                                                    | `amount`, `currency`, `retry_date`                                                                          | dedicated | per org_id                      |
| `billing/subscription-created`       | New subscription confirmation                                                   | `plan_name`, `amount`, `currency`, `billing_cycle`                                                          | fallback  | per org_id                      |
| `billing/subscription-cancelled`     | Subscription cancellation confirmation                                          | `plan_name`, `end_date`                                                                                     | fallback  | per org_id                      |
| `billing/cfdi`                       | CFDI (Mexican tax receipt) delivery — stamped XML + PDF attached                | `cliente_nombre`, `folio_fiscal`, `periodo`, `total`                                                        | dedicated | default `facturacion@madfam.io` |
| `transactional/quote-ready`          | Quote ready notification (Digifab)                                              | `quote_number`, `total_amount`                                                                              | dedicated | per org_id                      |
| `transactional/order-confirmation`   | Order confirmation (Digifab)                                                    | `order_number`, `total_amount`, `currency`                                                                  | fallback  | per org_id                      |
| `transactional/certificate`          | Certificate/DC-3 notification (Avala)                                           | `certificate_name`, `recipient_name`                                                                        | dedicated | per org_id                      |
| `transactional/enrollment`           | Course enrollment notification (Avala)                                          | `course_name`, `student_name`                                                                               | fallback  | per org_id                      |
| `transactional/budget-alert`         | Budget threshold alert (Dhanam)                                                 | `budget_name`, `percentage`, `spent`, `limit`                                                               | dedicated | per org_id                      |
| `invitation/team-invite`             | Team invitation                                                                 | `inviter_name`, `team_name`, `invite_url`                                                                   | dedicated | per org_id                      |
| `invitation/creator-invite`          | Creator platform invitation (Forj)                                              | `invite_url`                                                                                                | fallback  | per org_id                      |
| `onboarding/complete`                | Onboarding completion                                                           | `user_name`                                                                                                 | fallback  | per org_id                      |
| `transactional/agreement-accepted`   | Service agreement accepted — operator notification (Nauta)                      | `workspace_name`, `accepted_by`, `accepted_at`, `checksum`, `cockpit_url`                                   | dedicated | per org_id                      |
| `transactional/request-filed`        | Client priority filed — operator notification (Nauta)                          | `workspace_name`, `submitted_by`, `title`, `kind`, `severity`, `sla_line`, `filed_at`, `body_excerpt`, `cockpit_url` | dedicated | per org_id                      |
| `transactional/workspace-activated`  | Workspace activated — client notification (Nauta, register-composed)           | `heading`, `greeting`, `line_deposit`, `line_next`, `workspace_url`, `cta_label`, `line_support`, `workspace_host` | dedicated | per org_id                      |
| *(tenant payment notice, see below)* | Payment-confirmation notice to a member of a vCTO client's team (money-light)   | `periodo`                                                                                                   | dedicated | per org_id (tenant)             |
| `ops/alert`                          | Operator alert for MADFAM's team (internal, register-neutral, HTML + text)       | `asunto`, `titulo`, `detalle`, `servicio`, `ocurrio`                                                        | dedicated | per org_id (platform sender)    |

Some templates declare **optional** variables in addition to the required ones
above; consult `EMAIL_TEMPLATES` for the full contract of any id.

### Tenant payment-confirmation notice

Added in #630; its id is in `EMAIL_TEMPLATES` (and `GET /templates`). It tells
a member of a vCTO client's team that the period's work was
paid and thanks them. It is **deliberately money-light**: the contract is
`required: ["periodo"]`, `optional: ["sesiones"]` (a non-fiscal session *count*
only), and it carries **no** amount, currency, rate, bank/CLABE,
percentage, or other sensitive domain field — those live in HCM and the CFDI cockpit,
never in this notice. A guard test (the payment-confirmation test under
`apps/api/tests/unit/routers/`) renders the
template with an over-supplied variables dict and asserts none of those values
reach the body. The template declares **no** `default_from_email`, so its From
line resolves to the tenant via `org_id` (see [Sender resolution](#sender-resolution)).

### `billing/cfdi` (CFDI delivery)

Added in #629, together with attachment forwarding. This template delivers a
stamped Mexican tax receipt as **attachments** (XML + PDF). It declares a
per-template `default_from_email` of `facturacion@madfam.io` (a verified
`madfam.io` fiscal sender). Attachments passed on the request are forwarded to
Resend by both `/send` and `/send-template`; before #629 they were silently
dropped.

## Render mechanism

Two independent render paths exist in this repo — do not conflate them:

1. **The registry `send-template` route** (`apps/api/app/routers/v1/email.py`,
   `render_template()`) uses **naive `{{key}}` string substitution**: it reads
   the whitelisted HTML file and replaces each `{{key}}` occurrence with
   `str(value)` for every supplied variable. There are **no** Jinja
   conditionals, loops, filters, or auto-escaping on this path. A slot the
   caller does not supply is left as a literal `{{key}}` unless the template
   composes it another way — e.g. the tenant payment-confirmation notice derives an
   always-present `{{sesiones_detalle}}` slot from the optional `sesiones` count
   in `_derive_template_variables()`, precisely because the naive renderer
   cannot do singular/plural or hide an absent optional. If the HTML file is
   missing, this path falls back to `generate_fallback_html()`.

2. **The Jinja2 path** used **elsewhere** — `app/services/email_i18n.py` and
   `app/services/email/resend_service.py` (`FileSystemLoader`, autoescape) — is
   what renders the localized magic-link / auth mail via `email_service.py`. It
   is a different template set and a different mechanism. The registry route
   above does **not** use it.

When authoring a template for the registry route, write plain `{{key}}` slots
only; anything conditional must be composed in Python before substitution.

## Sender resolution

The From line is not taken at face value from the caller. It is chosen by
`app/services/email_sender.py` from tenant/host signals, and every send is
subject to a rule that a client display name never pairs with an address on
MADFAM's domain. The full policy — verified-domain gate, the per-tenant
`SenderBinding`, the vCTO gate, and the first tenant's live-on-its-own-account state — is
documented in [`EMAIL_SENDER_POLICY.md`](./EMAIL_SENDER_POLICY.md). In brief:

- A caller's explicit `from_email` / `from_name` is honoured **only** from a
  verified domain (and, for a client domain, only past the vCTO gate);
  otherwise it is discarded in favour of the tenant/host rule.
- A template may declare a `default_from_email` (e.g. `billing/cfdi` →
  `facturacion@madfam.io`); it applies only when the caller omits `from_email`.
- With neither an explicit sender nor a template default, the sender resolves
  from `org_id` (or the `redirect_url` host). The tenant payment-confirmation
  notice relies on this: `org_id` resolves to the tenant's own sender.

## Troubleshooting

### Email not sending

1. Check Janua health endpoint
2. Verify RESEND_API_KEY is set
3. Check domain is verified in Resend dashboard
4. Review Janua logs for errors

### Webhook signature mismatch

1. Ensure JANUA_WEBHOOK_SECRET matches in both Janua and consuming app
2. Verify raw body is being used for signature calculation
3. Check for middleware that might modify the request body

### Template not found

1. Verify template ID matches registry in `email.py`
2. Check HTML template file exists in `templates/emails/`
3. Fallback HTML will be generated if file is missing

## Monitoring

Track email delivery via:

- Resend dashboard for delivery metrics
- Janua logs with `source_app` and `source_type` tags
- Application-level logging of JanuaEmailService calls
