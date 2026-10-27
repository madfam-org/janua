# Invite-only clients and product invitations

For operators. Since 2026-10-22 an OAuth client can admit only invited people (first user: the MADFAM CV beta).
Code: `apps/api/app/services/invite_only_clients.py`, `apps/api/app/routers/v1/internal_product_invites.py`.
Tests: `apps/api/tests/unit/routers/test_invite_only_clients.py`.

## What it does

An invite-only client names a **product**. A person may sign in to the client only while they hold an active
entitlement for that product: a `user_entitlements` row, or org inheritance (`services/entitlements_service.py`).
No new table: the invitation is an `ADMIN_GRANT` entitlement row.

| Where | Effect for a person without the entitlement |
|---|---|
| `GET /api/v1/oauth/authorize` | interactive: a 403 page in the request's `ui_locales` («Esta cuenta no tiene acceso a …», with «Usar otra cuenta» = the same request with `prompt=login`); `prompt=none`: `error=access_denied`, `error_description=invite_only` |
| `POST /api/v1/oauth/token`, `authorization_code` and `refresh_token` | `400 invalid_grant`. Every sign-in path ends here, so a revoked invitee loses the client at their next refresh |
| hosted sign-in link form, `POST /api/v1/auth/magic-link` | an unknown address is **not created**, and no link is minted or sent. The hosted form shows the same «if this address has been invited…» page for invited and unknown addresses |

Open clients (every client not listed) behave exactly as before.

## Turning it on for a client

`INVITE_ONLY_CLIENTS` on janua-api: comma-separated `client_id=product` pairs, for example
`<client_id>=cv`. It ships in the deployment manifest, so turning it on is a reviewed change plus a promote.
Fail closed: a listed client whose product is missing or malformed admits nobody. Empty (the default): no client
is invite-only.

Order: promote the code first, then the setting. Invite the first people right after the setting is live.
Until someone is invited, nobody (operators included) can sign in to that client.

## Inviting, resending, removing

These are internal endpoints (`X-Internal-API-Key`). The public edge refuses `/api/v1/internal/*`, so they are
called from inside the cluster. There is no Enclii adapter for this call yet (**adapter gap**, recorded here per
AGENTS.md). The exact operator command lives in the private ops repository's runbook, not in this public repo.

**Invite** (it is also the **resend**): `POST /api/v1/internal/product-invites`

```json
{"email": "<EMAIL>", "client_id": "<CLIENT_ID>", "locale": "es", "formality": "tu", "first_name": "<optional>"}
```

- Finds the person's identity (platform pool first, then any pool; ambiguous: 409) or creates a passwordless,
  `ACTIVE` one with `locale`. A suspended account is refused (409).
- Upserts the product entitlement (`tier` defaults to `beta`), with no expiry.
- Mints ONE single-use link valid for `PRODUCT_INVITE_LINK_TTL_HOURS` (default 72), and queues ONE mail. The mail
  names the client (`OAuthClient.name`) in the subject, heading and button, in `locale` (`es` or `en`) and,
  for Spanish, in `formality` (`tu` or `usted`, default `usted`). The sender is the platform system sender
  (R101 class `system`).
- The link lands on Janua's callback (the scanner-proof interstitial, Spanish when `locale` is `es`), which sets
  the Janua session and forwards to `GET /api/v1/auth/app-entry?client_id=…`. That route drops the `token`
  query and sends the browser to the client's front door (the origin of its first registered redirect URI).
  The product never receives a token in a URL. The person then presses the product's own sign-in button, and
  Janua reuses the session.
- Response: `user_id`, `user_created`, `product`, `tier`, `entitlement_granted` (false on a resend),
  `link_expires_at`, `email_queued`. Never the token, and never an address it was not sent.
- Calling it again mails a fresh link. Earlier links stay valid until they expire or are used.

**Remove**: `POST /api/v1/internal/product-invites/revoke` with `{"email": "<EMAIL>", "client_id": "<CLIENT_ID>"}`.
It cancels the entitlement (`expires_at = now`; the row and the audit trail stay) and spends the person's unused
invitation links for that client. Response: `changed` (false if already removed), `links_spent`. The identity is
untouched: suspend it with `POST /api/v1/internal/users/suspend` only if the person should lose every product.

Errors: `409` when the client is not invite-only (or listed without a product), `404` when the client is unknown
or inactive, `503` when email is off.

Audit: `entitlement.grant` / `entitlement.revoke` rows with the client, product, tier and actor. The rows never
include the address or the token.

## Privacy

Janua's request log records full URLs. The address travels only in POST bodies, never in a URL. The token reaches
the log only where Janua's existing callback contract appends it (`/magic-link/callback?token=`, and the
`?token=` the callback adds to its destination).
