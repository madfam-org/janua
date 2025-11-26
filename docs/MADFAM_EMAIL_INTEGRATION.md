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
# Example: 6e33ae5c6f3032b0e1598d312372d2cfa5675bf510d16e49ce6d3e65989901dd

# Generate JANUA_WEBHOOK_SECRET (for webhook signature verification)
openssl rand -hex 32
# Example: c5c75003c6bf10e0f8a5e02a90e4b9bbe74d1318ee3d1b1a3ab049d6fa39d988
```

## Step 2: Configure Janua (Central Hub)

### Environment Variables

Add to Janua's `.env` or secrets management:

```env
# Email Provider
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Internal API (service-to-service)
INTERNAL_API_KEY=6e33ae5c6f3032b0e1598d312372d2cfa5675bf510d16e49ce6d3e65989901dd

# Webhook Secret (for billing webhooks to apps)
JANUA_WEBHOOK_SECRET=c5c75003c6bf10e0f8a5e02a90e4b9bbe74d1318ee3d1b1a3ab049d6fa39d988
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
  "templates_available": 15
}
```

## Step 3: Configure Consuming Apps

### Dhanam

```env
# .env
JANUA_API_URL=https://api.janua.dev
JANUA_INTERNAL_API_KEY=6e33ae5c6f3032b0e1598d312372d2cfa5675bf510d16e49ce6d3e65989901dd
JANUA_WEBHOOK_SECRET=c5c75003c6bf10e0f8a5e02a90e4b9bbe74d1318ee3d1b1a3ab049d6fa39d988
```

### Digifab-Quoting

```env
# .env
JANUA_API_URL=https://api.janua.dev
JANUA_INTERNAL_API_KEY=6e33ae5c6f3032b0e1598d312372d2cfa5675bf510d16e49ce6d3e65989901dd
JANUA_WEBHOOK_SECRET=c5c75003c6bf10e0f8a5e02a90e4b9bbe74d1318ee3d1b1a3ab049d6fa39d988
```

### Avala

```env
# .env
JANUA_API_URL=https://api.janua.dev
JANUA_INTERNAL_API_KEY=6e33ae5c6f3032b0e1598d312372d2cfa5675bf510d16e49ce6d3e65989901dd
JANUA_WEBHOOK_SECRET=c5c75003c6bf10e0f8a5e02a90e4b9bbe74d1318ee3d1b1a3ab049d6fa39d988
```

### Forj

```env
# .env
JANUA_API_URL=https://api.janua.dev
JANUA_INTERNAL_API_KEY=6e33ae5c6f3032b0e1598d312372d2cfa5675bf510d16e49ce6d3e65989901dd
```

### madfam-site

```env
# .env
JANUA_API_URL=https://api.janua.dev
JANUA_INTERNAL_API_KEY=6e33ae5c6f3032b0e1598d312372d2cfa5675bf510d16e49ce6d3e65989901dd
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

| App | Webhook URL | Events |
|-----|-------------|--------|
| Dhanam | `https://api.dhan.am/billing/webhook/janua` | subscription.*, payment.* |
| Digifab | `https://api.digifab.io/billing/webhook/janua` | subscription.*, payment.* |
| Avala | `https://api.avala.mx/billing/webhook/janua` | subscription.*, payment.* |

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
await januaEmailService.sendWelcomeEmail('user@example.com', 'John Doe');

// Send custom template
await januaEmailService.sendTemplateEmail({
  to: 'user@example.com',
  template: 'billing/payment-succeeded',
  variables: {
    amount: '29.99',
    currency: 'USD',
    invoice_number: 'INV-001',
  },
});
```

### Test Webhook Reception

```bash
# Simulate Janua webhook
curl -X POST https://api.dhan.am/billing/webhook/janua \
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

| Template ID | Description | Required Variables |
|-------------|-------------|-------------------|
| `auth/welcome` | New user welcome | `user_name`, `app_name` |
| `auth/password-reset` | Password reset | `reset_link`, `expires_in` |
| `auth/email-verification` | Email verification | `verification_link`, `expires_in` |
| `billing/invoice` | Invoice notification | `invoice_number`, `amount`, `currency`, `due_date` |
| `billing/payment-succeeded` | Payment confirmation | `amount`, `currency` |
| `billing/payment-failed` | Payment failure | `amount`, `currency`, `retry_date` |
| `transactional/quote-ready` | Quote ready (Digifab) | `quote_number`, `total_amount` |
| `transactional/certificate` | DC-3 certificate (Avala) | `certificate_name`, `recipient_name` |
| `transactional/budget-alert` | Budget alert (Dhanam) | `budget_name`, `percentage`, `spent`, `limit` |
| `invitation/team-invite` | Team invitation | `inviter_name`, `team_name`, `invite_url` |

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
