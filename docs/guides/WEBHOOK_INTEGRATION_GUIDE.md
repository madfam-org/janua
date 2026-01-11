# Webhook Integration Guide

Receive real-time notifications about authentication events in your application.

## Overview

Janua webhooks allow your application to receive HTTP callbacks when important events occur, such as:
- User registration and verification
- Login and logout events
- Password changes and resets
- MFA enrollment and verification
- Organization membership changes
- Session management events

---

## Quick Start

### 1. Create a Webhook Endpoint

First, create an endpoint in your application to receive webhook events:

```python
# Python/FastAPI
from fastapi import FastAPI, Request, HTTPException
import hmac
import hashlib

app = FastAPI()

WEBHOOK_SECRET = "whsec_your_webhook_secret"

@app.post("/webhooks/janua")
async def handle_janua_webhook(request: Request):
    # Get the raw body
    body = await request.body()

    # Verify signature
    signature = request.headers.get("X-Janua-Signature")
    if not verify_signature(body, signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse event
    event = await request.json()

    # Handle event
    if event["type"] == "user.created":
        user = event["data"]["user"]
        print(f"New user registered: {user['email']}")
    elif event["type"] == "user.login":
        print(f"User logged in: {event['data']['user']['email']}")

    return {"received": True}

def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

```javascript
// Node.js/Express
const express = require('express');
const crypto = require('crypto');

const app = express();
const WEBHOOK_SECRET = 'whsec_your_webhook_secret';

app.post('/webhooks/janua', express.raw({type: 'application/json'}), (req, res) => {
  const signature = req.headers['x-janua-signature'];

  // Verify signature
  const expectedSig = 'sha256=' + crypto
    .createHmac('sha256', WEBHOOK_SECRET)
    .update(req.body)
    .digest('hex');

  if (!crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expectedSig))) {
    return res.status(401).send('Invalid signature');
  }

  const event = JSON.parse(req.body);

  // Handle event
  switch (event.type) {
    case 'user.created':
      console.log(`New user: ${event.data.user.email}`);
      break;
    case 'user.login':
      console.log(`Login: ${event.data.user.email}`);
      break;
  }

  res.json({ received: true });
});
```

### 2. Register Your Webhook in Janua

```bash
curl -X POST https://api.janua.dev/api/v1/webhooks \
  -H "Authorization: Bearer $JANUA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-app.com/webhooks/janua",
    "events": ["user.created", "user.login", "user.logout"],
    "description": "Production webhook"
  }'
```

**Response:**
```json
{
  "id": "wh_abc123",
  "url": "https://your-app.com/webhooks/janua",
  "events": ["user.created", "user.login", "user.logout"],
  "secret": "whsec_abc123xyz...",
  "status": "active",
  "created_at": "2025-01-11T10:00:00Z"
}
```

**Important:** Save the `secret` - it's only shown once!

---

## API Reference

### Create Webhook Endpoint

```http
POST /api/v1/webhooks
Authorization: Bearer <token>
Content-Type: application/json

{
  "url": "https://your-app.com/webhooks",
  "events": ["user.created", "user.login"],
  "description": "Optional description",
  "metadata": {
    "environment": "production"
  }
}
```

### List Webhooks

```http
GET /api/v1/webhooks
Authorization: Bearer <token>
```

**Response:**
```json
{
  "webhooks": [
    {
      "id": "wh_abc123",
      "url": "https://your-app.com/webhooks",
      "events": ["user.created", "user.login"],
      "status": "active",
      "created_at": "2025-01-11T10:00:00Z",
      "last_delivery": {
        "status": "success",
        "timestamp": "2025-01-11T12:30:00Z"
      }
    }
  ]
}
```

### Get Webhook Details

```http
GET /api/v1/webhooks/{webhook_id}
Authorization: Bearer <token>
```

### Update Webhook

```http
PATCH /api/v1/webhooks/{webhook_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "url": "https://new-url.com/webhooks",
  "events": ["user.created", "user.login", "user.mfa.enabled"],
  "status": "active"
}
```

### Delete Webhook

```http
DELETE /api/v1/webhooks/{webhook_id}
Authorization: Bearer <token>
```

### Regenerate Secret

```http
POST /api/v1/webhooks/{webhook_id}/regenerate-secret
Authorization: Bearer <token>
```

**Response:**
```json
{
  "id": "wh_abc123",
  "secret": "whsec_new_secret_xyz..."
}
```

### Test Webhook

Send a test event to verify your endpoint:

```http
POST /api/v1/webhooks/{webhook_id}/test
Authorization: Bearer <token>
```

### View Delivery History

```http
GET /api/v1/webhooks/{webhook_id}/deliveries
Authorization: Bearer <token>
```

**Response:**
```json
{
  "deliveries": [
    {
      "id": "del_xyz789",
      "event_type": "user.created",
      "status": "success",
      "response_code": 200,
      "response_time_ms": 145,
      "timestamp": "2025-01-11T12:30:00Z"
    },
    {
      "id": "del_xyz790",
      "event_type": "user.login",
      "status": "failed",
      "response_code": 500,
      "error": "Connection timeout",
      "timestamp": "2025-01-11T12:35:00Z",
      "next_retry": "2025-01-11T12:40:00Z"
    }
  ]
}
```

---

## Event Types

### Authentication Events

| Event | Description | Payload |
|-------|-------------|---------|
| `user.created` | New user registered | User object |
| `user.updated` | User profile updated | User object, changed fields |
| `user.deleted` | User account deleted | User ID |
| `user.login` | Successful login | User, session, device info |
| `user.logout` | User logged out | User, session ID |
| `user.login.failed` | Failed login attempt | Email, reason, IP |

### Email Verification

| Event | Description | Payload |
|-------|-------------|---------|
| `user.email.verification_sent` | Verification email sent | User, email |
| `user.email.verified` | Email verified | User |
| `user.email.changed` | Email address changed | User, old email, new email |

### Password Events

| Event | Description | Payload |
|-------|-------------|---------|
| `user.password.reset_requested` | Reset requested | User email |
| `user.password.reset` | Password reset completed | User |
| `user.password.changed` | Password changed | User |

### Multi-Factor Authentication

| Event | Description | Payload |
|-------|-------------|---------|
| `user.mfa.enabled` | MFA enabled | User, method (totp/sms) |
| `user.mfa.disabled` | MFA disabled | User |
| `user.mfa.verified` | MFA verification successful | User, method |
| `user.mfa.failed` | MFA verification failed | User, attempts |

### Passkeys / WebAuthn

| Event | Description | Payload |
|-------|-------------|---------|
| `user.passkey.registered` | Passkey registered | User, passkey info |
| `user.passkey.deleted` | Passkey removed | User, passkey ID |
| `user.passkey.used` | Passkey used for auth | User, passkey info |

### Session Events

| Event | Description | Payload |
|-------|-------------|---------|
| `session.created` | New session started | Session, user, device |
| `session.revoked` | Session terminated | Session ID, user |
| `session.expired` | Session expired | Session ID, user |

### Organization Events

| Event | Description | Payload |
|-------|-------------|---------|
| `organization.created` | Org created | Organization |
| `organization.updated` | Org settings changed | Organization, changes |
| `organization.deleted` | Org deleted | Organization ID |
| `organization.member.added` | Member joined | Organization, user, role |
| `organization.member.removed` | Member left | Organization, user |
| `organization.member.role_changed` | Role updated | Organization, user, old/new role |
| `organization.invitation.sent` | Invite sent | Organization, email, inviter |
| `organization.invitation.accepted` | Invite accepted | Organization, user |

### OAuth Events

| Event | Description | Payload |
|-------|-------------|---------|
| `oauth.linked` | OAuth provider linked | User, provider |
| `oauth.unlinked` | OAuth provider unlinked | User, provider |
| `oauth.client.created` | OAuth app created | Client info |
| `oauth.client.deleted` | OAuth app deleted | Client ID |

### Security Events

| Event | Description | Payload |
|-------|-------------|---------|
| `security.account.locked` | Account locked | User, reason |
| `security.account.unlocked` | Account unlocked | User |
| `security.suspicious_activity` | Suspicious activity detected | User, activity details |
| `device.new` | Login from new device | User, device info |
| `device.trusted` | Device marked trusted | User, device |

---

## Event Payload Structure

All webhook events follow this structure:

```json
{
  "id": "evt_abc123xyz",
  "type": "user.created",
  "api_version": "2025-01-01",
  "created_at": "2025-01-11T10:30:00Z",
  "data": {
    "user": {
      "id": "usr_abc123",
      "email": "user@example.com",
      "name": "John Doe",
      "created_at": "2025-01-11T10:30:00Z"
    }
  },
  "metadata": {
    "ip_address": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "request_id": "req_xyz789"
  }
}
```

### Event Object Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique event identifier |
| `type` | string | Event type (e.g., `user.created`) |
| `api_version` | string | API version for payload format |
| `created_at` | string | ISO 8601 timestamp |
| `data` | object | Event-specific data |
| `metadata` | object | Request context (IP, user agent, etc.) |

---

## Signature Verification

All webhook requests include a signature for verification.

### Headers

| Header | Description |
|--------|-------------|
| `X-Janua-Signature` | HMAC-SHA256 signature |
| `X-Janua-Timestamp` | Unix timestamp of request |
| `X-Janua-Event-ID` | Unique event ID |
| `X-Janua-Event-Type` | Event type |

### Verification Process

1. Extract the signature from `X-Janua-Signature`
2. Get the raw request body (before JSON parsing)
3. Compute HMAC-SHA256 of body using your webhook secret
4. Compare computed signature with header value

### Python Example

```python
import hmac
import hashlib
import time

def verify_webhook(payload: bytes, signature: str, timestamp: str, secret: str) -> bool:
    # Check timestamp to prevent replay attacks (5 minute window)
    current_time = int(time.time())
    request_time = int(timestamp)
    if abs(current_time - request_time) > 300:
        return False

    # Compute expected signature
    signed_payload = f"{timestamp}.{payload.decode()}"
    expected = hmac.new(
        secret.encode(),
        signed_payload.encode(),
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### Node.js Example

```javascript
const crypto = require('crypto');

function verifyWebhook(payload, signature, timestamp, secret) {
  // Check timestamp (5 minute window)
  const currentTime = Math.floor(Date.now() / 1000);
  if (Math.abs(currentTime - parseInt(timestamp)) > 300) {
    return false;
  }

  // Compute expected signature
  const signedPayload = `${timestamp}.${payload}`;
  const expected = 'sha256=' + crypto
    .createHmac('sha256', secret)
    .update(signedPayload)
    .digest('hex');

  // Constant-time comparison
  return crypto.timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expected)
  );
}
```

---

## Retry Policy

When webhook delivery fails, Janua automatically retries:

| Attempt | Delay | Total Time |
|---------|-------|------------|
| 1 | Immediate | 0 |
| 2 | 1 minute | 1 min |
| 3 | 5 minutes | 6 min |
| 4 | 30 minutes | 36 min |
| 5 | 2 hours | 2h 36min |
| 6 | 8 hours | 10h 36min |
| 7 | 24 hours | 34h 36min |

### Retry Conditions

- **Retry**: HTTP 5xx errors, network timeouts, connection refused
- **No Retry**: HTTP 2xx (success), HTTP 4xx (client error)

### Handling Retries

Your endpoint should be idempotent. Use the `X-Janua-Event-ID` header to detect duplicate deliveries:

```python
processed_events = set()  # Use Redis in production

@app.post("/webhooks/janua")
async def handle_webhook(request: Request):
    event_id = request.headers.get("X-Janua-Event-ID")

    if event_id in processed_events:
        return {"received": True, "duplicate": True}

    # Process event...

    processed_events.add(event_id)
    return {"received": True}
```

---

## Best Practices

### 1. Return Quickly

Respond within 5 seconds to avoid timeouts. Process events asynchronously:

```python
from fastapi import BackgroundTasks

@app.post("/webhooks/janua")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    event = await request.json()

    # Queue for background processing
    background_tasks.add_task(process_event, event)

    # Return immediately
    return {"received": True}

async def process_event(event: dict):
    # Handle event asynchronously
    if event["type"] == "user.created":
        await send_welcome_email(event["data"]["user"])
```

### 2. Verify Signatures

Always verify webhook signatures before processing:

```python
if not verify_signature(body, signature, secret):
    raise HTTPException(status_code=401, detail="Invalid signature")
```

### 3. Handle Idempotency

Store processed event IDs to prevent duplicate handling:

```python
# Redis-based deduplication
async def is_duplicate(event_id: str) -> bool:
    return await redis.setnx(f"webhook:{event_id}", "1", ex=86400) == 0
```

### 4. Log Everything

Log all webhook events for debugging:

```python
import structlog

logger = structlog.get_logger()

@app.post("/webhooks/janua")
async def handle_webhook(request: Request):
    event = await request.json()

    logger.info(
        "webhook_received",
        event_id=event["id"],
        event_type=event["type"],
        user_id=event["data"].get("user", {}).get("id")
    )
```

### 5. Use HTTPS

Always use HTTPS endpoints in production. Janua will not deliver webhooks to HTTP URLs in production environments.

### 6. Set Up Monitoring

Monitor webhook health:
- Track delivery success rate
- Alert on repeated failures
- Monitor endpoint response times

---

## SDK Examples

### TypeScript SDK

```typescript
import { JanuaClient } from '@janua/typescript-sdk';

const janua = new JanuaClient({
  apiKey: process.env.JANUA_API_KEY,
});

// Create webhook
const webhook = await janua.webhooks.create({
  url: 'https://your-app.com/webhooks',
  events: ['user.created', 'user.login'],
});

console.log('Webhook secret:', webhook.secret);

// List webhooks
const webhooks = await janua.webhooks.list();

// Delete webhook
await janua.webhooks.delete(webhook.id);
```

### Python SDK

```python
from janua import JanuaClient

janua = JanuaClient(api_key="your_api_key")

# Create webhook
webhook = janua.webhooks.create(
    url="https://your-app.com/webhooks",
    events=["user.created", "user.login"]
)

print(f"Webhook secret: {webhook.secret}")

# List webhooks
webhooks = janua.webhooks.list()

# Delete webhook
janua.webhooks.delete(webhook.id)
```

---

## Troubleshooting

### Webhook Not Receiving Events

1. **Check endpoint URL**: Ensure it's publicly accessible
2. **Check firewall**: Allow requests from Janua IPs
3. **Verify HTTPS**: Production requires HTTPS
4. **Check event subscription**: Verify events are subscribed

### Signature Verification Fails

1. **Check secret**: Ensure you're using the correct webhook secret
2. **Raw body**: Verify you're using the raw request body (not parsed JSON)
3. **Encoding**: Ensure UTF-8 encoding
4. **Timestamp**: Check for clock skew

### Duplicate Events

1. **Implement idempotency**: Store and check event IDs
2. **Retry logic**: Your endpoint may have returned an error

### High Latency

1. **Async processing**: Return quickly, process in background
2. **Queue events**: Use message queue for heavy processing

---

## IP Allowlist

Janua sends webhooks from these IP ranges:

**Production:**
- `104.21.0.0/16` (Cloudflare)
- `172.67.0.0/16` (Cloudflare)

For dynamic IPs, verify using signature verification instead of IP allowlisting.

---

## See Also

- [API Reference](../api/API_REFERENCE.md)
- [Authentication Guide](./SSO_INTEGRATION_GUIDE.md)
- [Security Best Practices](../security/SECURITY.md)
