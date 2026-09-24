# Janua Service Tokens (machine-to-machine auth)

Cross-service identity for the RFC 0024 §P4 consolidations:

| Flow | Service client | Scope | Token audience | Resource server |
|---|---|---|---|---|
| Zavlo → Karafiel CFDI bridge (§P4.2) | `zavlo-cfdi-emitter` | `cfdi:issue` | `karafiel-api` | Karafiel API |
| RouteCraft → Dhanam billing (§P4.3) | `routecraft-billing-relay` | `billing:events` | `dhanam-api` | Dhanam API |
| Nauta → Karafiel legal drafts (D3.5) | `nauta-legal-drafts` | `legal:draft`, `legal:client-profile` | `karafiel-api` | Karafiel API |
| Forj → Yantra4D catalog render | `forj-catalog-materializer` | `yantra4d:render` | `yantra4d-api` | Yantra4D render API |
| creator-census → Janua delegated provider token | `creator-census` | `connections:delegate` | `janua-connections` | Janua connections API (see [Purpose-scoped provider consent](#purpose-scoped-provider-consent)) |

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

Some services need to act on a user's **own** third-party account — for
example, reading a creator's own YouTube channel statistics and analytics
through the official API. Janua brokers this without handing the service a
long-lived credential: the user consents to a named **purpose**, Janua keeps
the provider tokens in its encrypted ConnectedAccount vault, and the service
asks Janua for a short-lived provider access token each time it needs one.

### Purpose registry

Purposes are an allowlist in code (`apps/api/app/core/consent_purposes.py`),
not runtime configuration: widening who may borrow a user's provider token is
a reviewed change. Each purpose pins one provider, the extra provider scopes it
requests, and the Janua service clients (by registration **name**) allowed to
receive delegated tokens for it. Unknown purposes are refused everywhere.

| Purpose | Provider | Extra scopes | Allowed service clients |
|---|---|---|---|
| `creator-census.youtube` | `google` | `https://www.googleapis.com/auth/youtube.readonly`, `https://www.googleapis.com/auth/yt-analytics.readonly` | `creator-census` |

### 1. The user grants the purpose

The user, signed in to Janua, starts a link for the purpose:

```http
POST /api/v1/auth/oauth/link/google?purpose=creator-census.youtube&redirect_uri=/settings/connections
Authorization: Bearer <user session token>
```

- The purpose must exist and belong to the provider in the path, otherwise
  `400 unknown_purpose` / `400 purpose_provider_mismatch`.
- The purpose's scopes are requested on top of the provider's sign-in scopes.
  For Google, Janua also sends `include_granted_scopes=true` (incremental
  authorization), `access_type=offline` and `prompt=consent`, so a refresh
  token is issued.
- If the provider is **already linked**, the purpose turns the link into a
  scope upgrade instead of `400 already linked`. The upgrade must come back
  from the same provider account (`400 provider_account_mismatch` otherwise).
- On callback, Janua records the grant only if **every** purpose scope appears
  in the provider's token response. A partial grant (the user unticked a
  scope) records nothing and returns `purpose_scopes_not_granted` (as a
  `400`, or as `?error=` on the redirect).
- The grant is stored on the user's ConnectedAccount for the provider (the
  existing `oauth_scopes` and `account_metadata.purposes` JSON fields; no
  schema change) and audited as `consent.purpose.granted`.

Without `purpose`, linking behaves exactly as before.

### 2. The service obtains a service token

Register the service's client once (operator step), with exactly this grant:

```jsonc
{
  "name": "creator-census",
  "audience": "janua-connections",
  "allowed_scopes": ["connections:delegate"],
  "grant_types": ["client_credentials"],
  "redirect_uris": [],
  "is_confidential": true
}
```

Then mint tokens with `grant_type=client_credentials` as described above.

### 3. The service requests a delegated provider token

```http
POST /api/v1/connections/{connection_id}/token
Authorization: Bearer <service token, aud=janua-connections, scope=connections:delegate>
X-Acting-User-Id: <the consenting user's Janua id>
Content-Type: application/json

{"purpose": "creator-census.youtube", "ttl_seconds": 300}
```

Response: `access_token` (the provider's), `expires_at` (never later than the
provider token's own expiry), `purpose`, `provider_type`, `scopes`. The call is
audited as `tool.delegation.issued` with the purpose and the service client.
The service must not persist the provider token beyond `expires_at`.

Every rule fails closed with a specific reason (`error.message`):

| Status | Reason | When |
|---|---|---|
| 401 | `service_token_requires_rs256` | Janua is not signing with RS256 |
| 401 | `invalid_service_token` | bad signature/issuer/expiry, wrong audience, or not a `client_credentials` token |
| 403 | `service_token_missing_scope` | token lacks `connections:delegate` |
| 403 | `service_client_grant_unavailable` | client deactivated, or its registration no longer carries the audience/scope/grant |
| 403 | `unknown_purpose` | purpose not in the registry |
| 403 | `service_client_not_allowed_for_purpose` | client not in the purpose's allowlist |
| 404 | `connection_not_found` | no such connection |
| 403 | `acting_user_mismatch` | connection does not belong to `X-Acting-User-Id` |
| 403 | `connection_revoked` | the user revoked the connection (or unlinked the provider) |
| 403 | `purpose_provider_mismatch` | connection is for another provider |
| 403 | `purpose_not_granted` | the user never granted this purpose on this connection, or its scopes are no longer held |
| 409 | `reauthorization_required` | the provider rejected the refresh token, there is none, or the refreshed grant no longer covers the purpose; the connection is marked `expired` until the user re-consents |
| 503 | `provider_refresh_unavailable` | the provider could not be reached to refresh; transient, the consent is kept |

**Freshness.** If the stored Google access token is expired or within two
minutes of expiry, Janua refreshes it with the stored refresh token before
answering. Janua never returns a stale token.

**Revocation.** `DELETE /api/v1/connections/{id}` (or unlinking the provider)
revokes the connection and ends every purpose granted on it
(`consent.purpose.revoked`); later delegation for it is refused. A user who
wants the purpose back links again with `?purpose=`.

### Legacy static service token

The shared `JANUA_SERVICE_TOKEN` (Coupler tool execute) keeps working unchanged
for GitHub and Slack connections. It cannot request a registered purpose
(`403 purpose_requires_service_token`) and cannot receive tokens for any other
provider (`403 provider_requires_service_token`); those are reachable only
with a service token as above.

### Google verification before production

Google classifies the YouTube read scopes (`youtube.readonly`,
`yt-analytics.readonly`) as **sensitive**. Before this purpose is offered to
users outside the OAuth app's test-user list, the Google Cloud OAuth consent
screen must pass Google's OAuth app verification for those scopes (privacy
policy, scope justification, and a demo of the consent flow). Until then,
Google shows an "unverified app" warning and limits the app to test users.

