# MADFAM Centralized Email Integration

This document describes how to deploy and test the centralized Janua email service for all MADFAM applications.

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
| `map/pago-confirmado`                | MAP — payment-confirmation notice to a Crea Tu Mundo integrante (money-light)   | `periodo`                                                                                                   | dedicated | per org_id (CTM)                |

Some templates declare **optional** variables in addition to the required ones
above; consult `EMAIL_TEMPLATES` for the full contract of any id.

### `map/pago-confirmado` (MAP integrante payment confirmation)

Added in #630. It tells a Crea Tu Mundo colaboradora that the period's work was
paid and thanks her. It is **deliberately money-light**: the contract is
`required: ["periodo"]`, `optional: ["sesiones"]` (a non-fiscal session *count*
only), and it carries **no** amount, currency, rate, bank/CLABE,
beca/percentage, or clinical field — those live in HCM and the CFDI cockpit,
never in this notice. A guard test
(`apps/api/tests/unit/routers/test_email_map_pago_confirmado.py`) renders the
template with an over-supplied variables dict and asserts none of those values
reach the body. The template declares **no** `default_from_email`, so its From
line resolves to CTM via `org_id` (see [Sender resolution](#sender-resolution)).

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
   composes it another way — e.g. `map/pago-confirmado` derives an
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
`SenderBinding`, the vCTO gate, and the CTM live-on-its-own-account state — is
documented in [`EMAIL_SENDER_POLICY.md`](./EMAIL_SENDER_POLICY.md). In brief:

- A caller's explicit `from_email` / `from_name` is honoured **only** from a
  verified domain (and, for a client domain, only past the vCTO gate);
  otherwise it is discarded in favour of the tenant/host rule.
- A template may declare a `default_from_email` (e.g. `billing/cfdi` →
  `facturacion@madfam.io`); it applies only when the caller omits `from_email`.
- With neither an explicit sender nor a template default, the sender resolves
  from `org_id` (or the `redirect_url` host). `map/pago-confirmado` relies on
  this: `org_id` resolves to Crea Tu Mundo `<hola@creatumundo.mx>`.

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
