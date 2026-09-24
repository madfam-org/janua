# Janua Service Tokens (machine-to-machine auth)

Cross-service identity for the RFC 0024 §P4 consolidations:

| Flow | Service client | Scope | Token audience | Resource server |
|---|---|---|---|---|
| Zavlo → Karafiel CFDI bridge (§P4.2) | `zavlo-cfdi-emitter` | `cfdi:issue` | `karafiel-api` | Karafiel API |
| RouteCraft → Dhanam billing (§P4.3) | `routecraft-billing-relay` | `billing:events` | `dhanam-api` | Dhanam API |
| Nauta → Karafiel legal drafts (D3.5) | `nauta-legal-drafts` | `legal:draft`, `legal:client-profile` | `karafiel-api` | Karafiel API |
| Forj → Yantra4D catalog render | `forj-catalog-materializer` | `yantra4d:render` | `yantra4d-api` | Yantra4D render API |
| creator-census API → Janua token exchange (user present) | `creator-census` | `connections:delegate` | `janua-connections` | Janua connections API (see [Purpose-scoped provider consent](#purpose-scoped-provider-consent)) |
| creator-census re-verification job → Janua offline delegation (user absent) | `creator-census-reauth` | `connections:delegate` | `janua-connections` | Janua connections API |

Both migration plans (`zavlo/docs/karafiel-cfdi-migration-plan.md`,
`routecraft/docs/dhanam-payments-migration-plan.md`) are gated on this
decision. This document is the decision record + integration contract.

**Decision**: service-to-service calls authenticate with Janua-issued
OAuth 2.0 `client_credentials` tokens (RFC 6749 §4.4). One confidential
OAuth client per producer→consumer edge, scoped to exactly the capability
that edge needs. Resource servers verify tokens offline via Janua's JWKS
(RS256) or online via RFC 7662 introspection.

Janua's `client_credentials` support (token endpoint, per-client scope
allowlist, introspection, JWKS) **already exists** — see
[`docs/guides/machine-to-machine-authentication-guide.md`](./guides/machine-to-machine-authentication-guide.md)
for the general pattern. This page pins down the concrete service→service
clients (the RFC 0024 §P4 consolidations plus the Forj→Yantra4D catalog
render edge) and how each side integrates.

## Endpoints

Issuer (production): `https://auth.madfam.io`

| Purpose | Endpoint |
|---|---|
| Discovery | `GET /.well-known/openid-configuration` |
| JWKS (public keys) | `GET /.well-known/jwks.json` |
| Token | `POST /api/v1/oauth/token` |
| Introspection (RFC 7662) | `POST /api/v1/oauth/introspect` |
| Client registration (internal) | `POST /api/v1/oauth/clients/register` |

## Service clients

Provisioned by an operator with `apps/api/scripts/seed_service_clients.py`
(or zero-touch via `POST /api/v1/oauth/clients/register` +
`X-Internal-API-Key`).

**One client per consumer edge, keyed by `name`.** Registration identity is the
client **`name`** — the stable consumer-edge identifier declared in the
consumer's `janua.client.yaml` (or in `seed_service_clients.py`). Re-registering
the same name reconciles non-secret fields and returns 200 with **no** secret; a
new name creates a new client (201 + `client_secret`, shown once) **even when it
shares an `audience`**. Audience names the API being *called*, and several edges
legitimately call one API: `zavlo-cfdi-emitter` and `nauta-legal-drafts` both
target `karafiel-api`. Per ADR-006 each edge gets its own client scoped to
exactly what it calls. Internal-key registrations are recorded in `audit_logs`
(`oauth_client_registered_internal_created` / `..._updated`), attributed to the
`internal-api-key` principal and carrying no secret material.

Registration properties:

```jsonc
// zavlo-cfdi-emitter
{
  "name": "zavlo-cfdi-emitter",
  "audience": "karafiel-api",
  "allowed_scopes": ["cfdi:issue"],
  "grant_types": ["client_credentials"],
  "redirect_uris": [],
  "is_confidential": true
}

// routecraft-billing-relay
{
  "name": "routecraft-billing-relay",
  "audience": "dhanam-api",
  "allowed_scopes": ["billing:events"],
  "grant_types": ["client_credentials"],
  "redirect_uris": [],
  "is_confidential": true
}

// forj-catalog-materializer
{
  "name": "forj-catalog-materializer",
  "audience": "yantra4d-api",
  "allowed_scopes": ["yantra4d:render"],
  "grant_types": ["client_credentials"],
  "redirect_uris": [],
  "is_confidential": true
}
```

The `yantra4d:render` scope namespace is what makes Yantra4D emit a
`yantra4d_tier` claim high enough to clear its `pro`-tier GLB export gate
(`yantra4d/apps/api/middleware/auth.py`, `RENDER_SCOPE`). This is the same
render edge `fashion-cabinet/apps/api/body_render.py` already mints against
(`FC_YANTRA4D_CLIENT_ID/SECRET`) — forj's materializer is a second producer
on it, holding `FORJ_YANTRA4D_CLIENT_ID` / `FORJ_YANTRA4D_CLIENT_SECRET`.

The `client_secret` is shown **once** at provisioning. Store it in the
approved secret store (Enclii/Vault) and mount it into the calling
service's runtime environment. Placeholders only in code and docs —
never commit real `jnc_`/`jns_` values.

## How Zavlo / RouteCraft obtain tokens

`POST /api/v1/oauth/token` with `grant_type=client_credentials`. Client
authentication is `client_secret_basic` or `client_secret_post`.

```bash
curl -sS https://auth.madfam.io/api/v1/oauth/token \
  -u "$JANUA_CLIENT_ID:$JANUA_CLIENT_SECRET" \
  -d grant_type=client_credentials \
  -d scope="cfdi:issue"          # routecraft: scope="billing:events"
```

Response:

```json
{
  "access_token": "<RS256 JWT>",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": null,
  "scope": "cfdi:issue"
}
```

Rules for callers:

- Tokens live **1 hour** (`expires_in` matches the JWT `exp`). There is no
  refresh token — request a new token when the old one is near expiry.
  Cache the token in memory and re-request ~60s before expiry; do not
  request a fresh token per call (the token endpoint is rate-limited).
- Omitting `scope` grants **all** scopes on the client's allowlist; the
  seeded clients have exactly one scope, so both forms are equivalent.
- Requesting a scope outside the client's allowlist fails closed with
  `400 invalid_scope`.
- Send the token as `Authorization: Bearer <access_token>` on every
  Karafiel/Dhanam call.

TypeScript sketch for `zavlo-backend` (NestJS) / RouteCraft:

```ts
let cached: { token: string; exp: number } | null = null;

async function serviceToken(): Promise<string> {
  if (cached && cached.exp - 60_000 > Date.now()) return cached.token;
  const res = await fetch(`${JANUA_ISSUER}/api/v1/oauth/token`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Authorization:
        "Basic " +
        Buffer.from(`${CLIENT_ID}:${CLIENT_SECRET}`).toString("base64"),
    },
    body: new URLSearchParams({ grant_type: "client_credentials" }),
  });
  if (!res.ok) throw new Error(`janua token: ${res.status}`);
  const body = await res.json();
  cached = { token: body.access_token, exp: Date.now() + body.expires_in * 1000 };
  return cached.token;
}
```

## Token shape

Service tokens are RS256 JWTs (`kid` in the header, key published at
`/.well-known/jwks.json`) with these claims:

```jsonc
{
  "iss": "https://auth.madfam.io",
  "sub": "service-account:jnc_...",     // stable machine identity
  "aud": "karafiel-api",                // per-client audience
  "exp": 1780000000,                    // iat + 3600
  "iat": 1779996400,
  "jti": "...",
  "type": "access",
  "client_id": "jnc_...",
  "scope": "cfdi:issue",                // space-separated granted scopes
  "token_use": "client_credentials",
  "actor_type": "service_account",
  "roles": ["service_account"],
  "email": "zavlo-cfdi-emitter@service.auth.madfam.io"
}
```

## How Karafiel verifies (offline, JWKS)

Karafiel (FastAPI) verifies without calling Janua on the hot path:

1. Fetch + cache JWKS from `https://auth.madfam.io/.well-known/jwks.json`.
2. Verify signature (RS256), `iss == https://auth.madfam.io`,
   `aud == "karafiel-api"`, and `exp` (PyJWT does all four).
3. Enforce `token_use == "client_credentials"` and that the required
   scope is present in the `scope` claim.

```python
import jwt
from jwt import PyJWKClient

_jwks = PyJWKClient("https://auth.madfam.io/.well-known/jwks.json")

def verify_service_token(token: str, required_scope: str = "cfdi:issue") -> dict:
    key = _jwks.get_signing_key_from_jwt(token).key
    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        issuer="https://auth.madfam.io",
        audience="karafiel-api",
    )  # raises on bad signature / issuer / audience / expiry
    if claims.get("token_use") != "client_credentials":
        raise PermissionError("not a service token")
    if required_scope not in (claims.get("scope") or "").split():
        raise PermissionError(f"missing scope {required_scope}")
    return claims  # claims["sub"] / claims["client_id"] for audit rows
```

Karafiel's CFDI billing bridge guards `POST` envelope ingestion with
`required_scope="cfdi:issue"` and attributes the envelope to
`claims["client_id"]` alongside the existing `source: "zavlo.*"`
discriminator and idempotency key.

Scope map on the Karafiel side:

- `cfdi:issue` — Zavlo's CFDI envelope ingestion (above).
- `legal:draft` — creates and compiles service-agreement drafts and reads
  generated-document metadata.
- `legal:client-profile` — creates and updates the calling client's **own**
  legal-entity profile (`ClientProfile`) at `/api/v1/legal/clients`
  (`POST`/`PUT`/`PATCH`/`GET`; `DELETE` is refused). Karafiel PR #148.

`legal:draft` and `legal:client-profile` are **independent**: neither
implies the other, and Karafiel enforces each separately on its own routes.
A `legal:client-profile` token grants no access to drafts or generated
documents, and a `legal:draft` token cannot write a client profile.
`nauta-legal-drafts` is allowlisted for both because Nauta's
`engagement.provision` needs both capabilities; each token still carries
only the scopes that request asked for (omitting `scope` grants both).

## How Dhanam verifies (offline, JWKS)

Dhanam (NestJS) uses the same pattern via `passport-jwt` + `jwks-rsa`
(mirrors `zavlo-backend/src/modules/janua/janua-jwt.strategy.ts`):

```ts
import { passportJwtSecret } from "jwks-rsa";
import { ExtractJwt, Strategy } from "passport-jwt";

export class JanuaServiceJwtStrategy extends PassportStrategy(Strategy, "janua-service") {
  constructor() {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      algorithms: ["RS256"],
      issuer: "https://auth.madfam.io",
      audience: "dhanam-api",
      secretOrKeyProvider: passportJwtSecret({
        jwksUri: "https://auth.madfam.io/.well-known/jwks.json",
        cache: true,
        rateLimit: true,
      }),
    });
  }

  validate(claims: Record<string, unknown>) {
    if (claims.token_use !== "client_credentials") throw new UnauthorizedException();
    const scopes = String(claims.scope ?? "").split(" ");
    if (!scopes.includes("billing:events")) throw new ForbiddenException();
    return claims; // claims.sub === "service-account:jnc_..."
  }
}
```

Scope map on the Dhanam side:

- `billing:events` — RouteCraft's signed `payment.succeeded` /
  attribution emission to `POST /v1/billing/madfam-events` and the
  delegated `POST /v1/billing/checkout` call. The existing HMAC envelope
  signature (`t=<ts>,v1=<hex>`) stays as content integrity on the event
  body; the Bearer token is the caller *identity*.

## Alternative: introspection (RFC 7662)

Resource servers that prefer online checks (or need immediate-revocation
semantics) can call introspection instead of JWKS verification:

```bash
curl -sS https://auth.madfam.io/api/v1/oauth/introspect \
  -u "$RESOURCE_CLIENT_ID:$RESOURCE_CLIENT_SECRET" \
  -d token="$ACCESS_TOKEN"
# => {"active": true, "sub": "service-account:jnc_...",
#     "client_id": "jnc_...", "scope": "cfdi:issue", "exp": ..., "iat": ...}
```

Expired or otherwise invalid tokens return `{"active": false}`.
Introspection itself requires client authentication (the resource
server's own Janua client credentials).

## Rotation & operations

- Rotate secrets via Janua's OAuth client secret-rotation endpoint;
  `CLIENT_SECRET_ROTATION_ENABLED` gives a dual-secret grace window so
  callers roll without downtime.
- One client per edge: do not reuse `zavlo-cfdi-emitter` for anything but
  Zavlo→Karafiel, nor `routecraft-billing-relay` for anything but
  RouteCraft→Dhanam. New edges get new clients with their own scopes.
- Widening a client's `allowed_scopes` is an operator action on the Janua
  side (seed script re-run or admin API) and must be reflected here.

## Purpose-scoped provider consent

Some services need to act on a user's **own** third-party account. For
example, a service may read a creator's own YouTube channel data through the
official API. Janua brokers this without handing the service a long-lived
credential:
- the user consents to a named **purpose**;
- Janua keeps the provider tokens in its encrypted ConnectedAccount vault;
- the service asks Janua for a short-lived provider access token each time it
  needs one.

### Purpose registry

Purposes are an allowlist in code (`apps/api/app/core/consent_purposes.py`),
not runtime configuration. Widening who may borrow a user's provider token, or
what it can do, is a reviewed change. Each purpose pins:

| Field | Meaning |
|---|---|
| `provider` | The only provider the purpose applies to. |
| `additional_scopes` | Provider scopes requested on top of sign-in. Keep this to the minimum in use today. |
| `exchange_clients` | Service clients, by registration **name**, allowed to use the user-bound [token exchange](#3-user-present-token-exchange). |
| `offline_clients` | Service clients allowed to use [offline delegation](#4-user-absent-offline-delegation), for background re-verification only. |
| `allowed_subject_audiences` | Audiences that the user's own Janua access token may carry to be accepted as the exchange subject. |

The registry holds one purpose today:

| Purpose | Provider | Extra scopes | Exchange clients | Offline clients | Subject audiences |
|---|---|---|---|---|---|
| `creator-census.youtube` | `google` | `https://www.googleapis.com/auth/youtube.readonly` | `creator-census` | `creator-census-reauth` | `creator-census-api` |

Unknown purposes are refused everywhere. A client listed for one path is
refused on the other.

**Widening a purpose's scopes later.** Two steps:
1. Add the scope to the registry in a reviewed change.
2. Extend the provider's app verification to cover it (see below).

Existing grants then no longer cover the purpose, because every scope must be
held. The exchange answers `purpose_not_granted` until each user links again
with `?purpose=`. For Google, that re-link is an incremental consent that asks
only for the new scope.

Narrowing a purpose's scopes takes effect immediately.

### 1. The user grants the purpose

The user is signed in to Janua and starts a link for the purpose:

```http
POST /api/v1/auth/oauth/link/google?purpose=creator-census.youtube&redirect_uri=/settings/connections
Authorization: Bearer <user session token>
```

- The purpose must exist and belong to the provider in the path. Otherwise the
  call fails with `400 unknown_purpose` or `400 purpose_provider_mismatch`.
- The purpose's scopes are requested on top of the provider's sign-in scopes.
  For Google, Janua also sends:
  - `include_granted_scopes=true` (incremental authorization);
  - `access_type=offline` and `prompt=consent`, so that a refresh token is
    issued.
- If the provider is **already linked**, the purpose turns the link into a
  scope upgrade instead of failing with `400 already linked`. The upgrade must
  come back from the same provider account; otherwise it fails with
  `400 provider_account_mismatch`.
- On callback, Janua records the grant only if **every** purpose scope appears
  in the provider's token response. A partial grant (the user unticked a scope)
  records nothing and returns `purpose_scopes_not_granted`, as a `400` or as
  `?error=` on the redirect.
- The grant is stored on the user's ConnectedAccount for the provider, in the
  existing `oauth_scopes` and `account_metadata.purposes` JSON fields, so no
  schema change is needed. It is audited as `consent.purpose.granted`.

Without `purpose`, linking behaves exactly as before.

### 2. Service clients

Register one client per path (operator step). Both clients use the same
grant shape; only `name` differs.

```jsonc
{
  "name": "creator-census",          // and, separately, "creator-census-reauth"
  "audience": "janua-connections",
  "allowed_scopes": ["connections:delegate"],
  "grant_types": ["client_credentials"],
  "redirect_uris": [],
  "is_confidential": true
}
```

Mount each secret only where its path runs:
- the exchange client (`creator-census`) in the service's API;
- the offline client (`creator-census-reauth`) only in a job with no ingress.

Mint tokens with `grant_type=client_credentials`, as described above.

### 3. User present: token exchange

This is the default path. The service forwards the user's own Janua access
token (the *subject*), which it received on the user's request, together with
its own service token (the *actor*). The request is form-encoded, in
RFC 8693 shape:

```http
POST /api/v1/connections/token-exchange
Content-Type: application/x-www-form-urlencoded

grant_type=urn:ietf:params:oauth:grant-type:token-exchange
&subject_token=<the user's Janua access token, aud=creator-census-api>
&subject_token_type=urn:ietf:params:oauth:token-type:access_token
&actor_token=<service token, aud=janua-connections, scope=connections:delegate>
&actor_token_type=urn:ietf:params:oauth:token-type:access_token
&purpose=creator-census.youtube
&ttl_seconds=300
```

Janua then:
1. Verifies both tokens.
2. Picks the user's **active** connection that holds the purpose grant. No
   connection id is needed.
3. Refreshes the provider token if it is stale.
4. Returns `access_token` (the provider's), `issued_token_type`, `token_type`,
   `expires_in` and `expires_at` (never later than the provider token's own
   expiry), `scope`, `purpose`, `provider_type` and `connection_id`.

The call is audited as `tool.delegation.issued` with `path: exchange`, the
actor client and the subject user.

Why the user's token is required: a service that could present only its own
credential and a claimed user id could borrow the token of *every* consenting
user (a confused deputy). With the subject token, a compromised API can reach
only the users whose requests it is handling, and only while their access
tokens last.

### 4. User absent: offline delegation

This path is for background re-verification only. A refresh at Google is the
only real check that a user's authorization still stands; a check against
Janua's own records would report "granted" for a grant the user has already
revoked at Google.

```http
POST /api/v1/connections/{connection_id}/token
Authorization: Bearer <service token from an offline client>
X-Acting-User-Id: <the consenting user's Janua id>
Content-Type: application/json

{"purpose": "creator-census.youtube", "ttl_seconds": 300}
```

- It is open only to the purpose's `offline_clients`. Any other service client
  gets `403 user_binding_required`.
- `connection_id` comes from an earlier exchange response.
- The call is audited with `path: offline`.
- A `409 reauthorization_required` answer means Google no longer honours the
  grant. Treat it as the user's revocation until they consent again.

### Refusals

Every rule fails closed with a specific reason in `error.message`. **Path**
names where the reason applies: exchange, offline, or both.

| Status | Reason | Path | When |
|---|---|---|---|
| 400 | `unsupported_grant_type` / `unsupported_token_type` | exchange | The request is not an RFC 8693 access-token exchange. |
| 401 | `service_token_requires_rs256` | both | Janua is not signing with RS256. |
| 401 | `invalid_service_token` | both | The actor token is malformed, expired, for the wrong audience, or not a `client_credentials` token. |
| 403 | `service_token_missing_scope` | both | The actor token lacks `connections:delegate`. |
| 403 | `service_client_grant_unavailable` | both | The client is deactivated, or its registration no longer carries the audience, scope or grant. |
| 403 | `unknown_purpose` | both | The purpose is not in the registry. |
| 403 | `client_not_permitted` | exchange | The client is not in the purpose's `exchange_clients`. |
| 403 | `user_binding_required` | offline | The client is not in `offline_clients`. The legacy static token also gets this reason for any purpose-scoped or non-GitHub/Slack credential. |
| 401 | `invalid_subject_token` | exchange | The subject token has a bad signature, is expired, or is for an audience the purpose does not list. |
| 403 | `subject_must_be_user` | exchange | The subject is a service token. |
| 403 | `subject_user_unavailable` | exchange | The subject user is inactive or is a service principal. |
| 404 | `connection_not_found` | offline | No such connection. |
| 403 | `acting_user_mismatch` | offline | The connection does not belong to `X-Acting-User-Id`. |
| 403 | `purpose_provider_mismatch` | offline | The connection is for another provider. |
| 403 | `purpose_not_granted` | both | No active grant for the purpose: never granted, revoked, unlinked, or its scopes are no longer held. |
| 409 | `reauthorization_required` | both | The provider rejected the refresh token, there is none, or the refreshed grant no longer covers the purpose. The connection is marked `expired` until the user consents again. |
| 503 | `provider_refresh_unavailable` | both | The provider could not be reached to refresh. This is transient, and the consent is kept. |

**Freshness.** If the stored Google access token is expired or has less than
two minutes left, Janua refreshes it with the stored refresh token before
answering. Janua never returns a stale token.

### Revocation reaches the provider

Revocation is triggered by `DELETE /api/v1/connections/{id}` or by unlinking
Google (`DELETE /api/v1/auth/oauth/unlink/google`). Janua then:

1. **Revokes locally first, always.** The connection becomes `revoked` and
   every purpose on it ends (`consent.purpose.revoked`). Delegation is refused
   from then on, whatever happens next.
2. **Revokes at Google.** Janua calls `https://oauth2.googleapis.com/revoke`,
   preferring the refresh token, which ends the whole grant. Transient failures
   (network errors, HTTP 429, HTTP 5xx) are retried twice with backoff.
   `invalid_token` means the token was already revoked and counts as done.
3. **Audits every attempt** as `consent.provider.revoked`, with its outcome:
   - `revoked` or `already_invalid`: the vault copy of the tokens is wiped;
   - `failed`: the tokens are kept on the revoked, never-delegable row, and
     `account_metadata.provider_revocation` records the failure so that an
     operator can retry.

A Google failure never blocks or undoes Janua's own revocation. `DELETE`
returns the provider outcome in `provider_revocation`.

Revoking at Google ends Janua's whole Google grant for that user. Signing in
with Google still works afterwards, and asks for consent again. A service that
stores provider data should delete it once delegation starts answering
`purpose_not_granted`, or `409` without a later re-consent, according to its
own retention policy.

GitHub and Slack connections are revoked locally only; there is no
provider-side call for them.

### Legacy static service token

The shared `JANUA_SERVICE_TOKEN` (Coupler tool execute) works unchanged for
GitHub and Slack connections. It never reaches a registered purpose or any
other provider; those calls get `403 user_binding_required`.

### Google verification before production

Google classifies `https://www.googleapis.com/auth/youtube.readonly` as a
**sensitive** scope. The Google Cloud OAuth consent screen must pass Google's
OAuth app verification for this scope before the purpose is offered to users
outside the OAuth app's test-user list. Verification needs a privacy policy, a
justification for the scope, and a demo of the consent flow. Until the app is
verified, Google shows an "unverified app" warning and limits the app to test
users. Any later widening of the purpose (for example, adding YouTube Analytics)
must be added to the verification.
