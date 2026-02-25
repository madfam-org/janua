# Janua Provider Operations Runbook

**Audience**: Platform operators managing Janua as an identity provider
**Last Updated**: 2026-02-24
**Applies to**: Janua API v1, MADFAM ecosystem deployments

---

## Overview

This runbook covers day-to-day operations for running Janua as the central OAuth2/OIDC identity provider for the MADFAM ecosystem. It assumes you have admin access to the Janua API and familiarity with the deployment infrastructure described in the main project CLAUDE.md.

Key operational areas covered:

- Bootstrapping OAuth clients for ecosystem apps
- CORS origin management (automatic and manual)
- OAuth client lifecycle management
- JWKS and client secret key rotation
- Rate limit configuration and monitoring
- Per-client audience claim enforcement
- Troubleshooting common integration issues

**Production endpoints**:

| Endpoint | URL |
|----------|-----|
| API | `https://api.janua.dev` |
| OIDC Discovery | `https://api.janua.dev/.well-known/openid-configuration` |
| JWKS | `https://api.janua.dev/.well-known/jwks.json` |
| Dashboard | `https://app.janua.dev` |
| Admin | `https://admin.janua.dev` |

---

## Ecosystem Bootstrap

The `scripts/seed_ecosystem_clients.py` script registers known MADFAM ecosystem applications as OAuth clients in a single operation. This is an operator tool for initial setup or environment provisioning. It is not the consumer onboarding path -- individual apps should not run this script themselves.

### Running the seed script

```bash
cd /path/to/janua/scripts
python seed_ecosystem_clients.py
```

To register a single app:

```bash
python seed_ecosystem_clients.py --app stratum-tcg
```

The script creates OAuth clients with pre-configured values for each ecosystem app (audience, redirect URIs, allowed scopes). Client credentials are printed to stdout on creation. Store them securely -- the `client_secret` is not retrievable after this point.

### When to run

- After a fresh deployment or database migration
- When adding a new app to the ecosystem
- When re-provisioning a staging or development environment

### Manual client registration

If you need to register a client outside the seed script, use the API directly:

```bash
curl -X POST https://api.janua.dev/api/v1/oauth/clients \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-new-app",
    "redirect_uris": ["https://my-app.dev/api/auth/callback"],
    "audience": "my-app-api",
    "allowed_scopes": ["openid", "profile", "email"],
    "grant_types": ["authorization_code", "refresh_token"],
    "is_confidential": true
  }'
```

The response includes the `client_id` and `client_secret`. Save the secret immediately.

---

## CORS Auto-Provisioning

Janua automatically derives allowed CORS origins from the `redirect_uris` registered on active OAuth clients. No admin intervention is required when a consumer registers a new client with valid redirect URIs.

### How it works

1. The `DynamicCORSMiddleware` loads CORS origins from three sources:
   - Static configuration (`CORS_ORIGINS` environment variable)
   - Database (`allowed_cors_origins` table)
   - OAuth client `redirect_uris` (origins extracted automatically)

2. For each active OAuth client, the middleware parses the scheme and host from every registered `redirect_uri` and adds the resulting origin to the allowed set. For example, `https://tezca.dev/api/auth/callback` produces the allowed origin `https://tezca.dev`.

3. The combined origin set is cached in memory with a **60-second TTL**. After a client is created or updated, the new origin will be recognized within 60 seconds without restarting the API.

### Verifying CORS status

Check the current cache status from the admin API or application logs. The middleware logs the number of origins loaded from each source at debug level.

### Forcing a cache refresh

If you need origins to take effect immediately (for example, during incident response), restart the API pod:

```bash
kubectl rollout restart deployment/janua-api -n janua
```

This clears the in-memory CORS cache. Under normal operations, waiting for the 60-second TTL expiration is sufficient.

### Wildcard origins

The middleware supports wildcard patterns such as `*.janua.dev` in the static configuration. These are evaluated on every request alongside the cached origin set.

---

## OAuth Client Management

### Listing all clients (admin)

The admin endpoint returns all OAuth clients in the system regardless of ownership:

```bash
curl https://api.janua.dev/api/v1/oauth/clients/admin/all \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

Supports pagination:

```bash
curl "https://api.janua.dev/api/v1/oauth/clients/admin/all?page=1&per_page=50" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

### Viewing a specific client

```bash
curl https://api.janua.dev/api/v1/oauth/clients/{client_db_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

The `client_secret` is never returned after creation. The response includes `redirect_uris`, `allowed_scopes`, `grant_types`, `is_active`, `last_used_at`, and the `organization_id` if scoped to an organization.

### Updating a client

```bash
curl -X PATCH https://api.janua.dev/api/v1/oauth/clients/{client_db_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "redirect_uris": [
      "https://my-app.dev/api/auth/callback",
      "https://staging.my-app.dev/api/auth/callback"
    ]
  }'
```

### Deactivating a client

To disable a client without deleting it:

```bash
curl -X PATCH https://api.janua.dev/api/v1/oauth/clients/{client_db_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

Deactivated clients cannot obtain new tokens. Existing tokens remain valid until they expire.

### Deleting a client

```bash
curl -X DELETE https://api.janua.dev/api/v1/oauth/clients/{client_db_id} \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

This immediately invalidates all tokens issued to the client.

### Dashboard UI

OAuth clients can also be managed through the Dashboard at `https://app.janua.dev/settings/oauth-clients`. The UI provides the same operations as the API with a visual interface for non-technical operators.

---

## Key Rotation

### JWKS key rotation

Janua signs tokens using RS256 with RSA-2048 keys. The public keys are served at `/.well-known/jwks.json`. Consumer apps fetch this endpoint and cache it locally, refreshing when they encounter an unknown `kid` (key ID) in a token header.

**Rotation procedure**:

1. Generate a new RSA-2048 key pair.
2. Add the new private key to the API configuration and deploy. Both old and new keys should be available during the transition.
3. The JWKS endpoint will serve both keys. Consumers that cache JWKS will pick up the new key on their next refresh cycle.
4. Wait for all outstanding access tokens signed with the old key to expire (default: 15 minutes for access tokens, 7 days for refresh tokens).
5. Remove the old private key from the API configuration and deploy again.

**JWKS cache considerations**: Consumer apps typically cache the JWKS response. If a consumer uses a strict TTL cache (rather than refreshing on unknown `kid`), they may reject tokens signed with the new key until their cache expires. Coordinate with consumer app teams before rotating keys to ensure their JWKS client supports `kid`-based refresh.

Verify the current JWKS:

```bash
curl https://api.janua.dev/.well-known/jwks.json | jq '.keys[] | {kid, kty, alg}'
```

### Client secret rotation

Client secrets can be rotated with a graceful grace period. During the grace period, both old and new secrets are accepted, allowing zero-downtime credential updates.

**Rotate a client secret**:

```bash
curl -X POST https://api.janua.dev/api/v1/oauth/clients/{client_db_id}/rotate \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"grace_period_hours": 24}'
```

The response includes the new `client_secret` (save it immediately), `rotated_at` timestamp, and `old_secrets_expire_at`.

If no `grace_period_hours` is specified, the default from `CLIENT_SECRET_ROTATION_GRACE_HOURS` in the server configuration is used.

**Check secret status**:

```bash
curl https://api.janua.dev/api/v1/oauth/clients/{client_db_id}/secrets \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

This shows all active secrets, their creation dates, expiration times, last usage, and whether rotation is recommended based on secret age.

**Revoke a specific old secret** (before grace period expires):

```bash
curl -X POST https://api.janua.dev/api/v1/oauth/clients/{client_db_id}/secrets/revoke \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"secret_id": "uuid-of-secret-to-revoke"}'
```

**Emergency: revoke all old secrets immediately**:

```bash
curl -X POST https://api.janua.dev/api/v1/oauth/clients/{client_db_id}/secrets/revoke-all-old \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

This invalidates all secrets except the current primary. Use only when old secrets may be compromised, as it will break consumer apps still using the previous secret.

---

## Rate Limits

Janua applies rate limits at multiple levels: per-IP, per-endpoint, and per-tenant. Limits are enforced using a sliding window algorithm backed by Redis.

### OAuth endpoint limits

The following default limits apply to OAuth-specific endpoints:

| Endpoint | Limit | Window | Key |
|----------|-------|--------|-----|
| `POST /api/v1/oauth/token` | 10 requests | 5 minutes | Per client IP |
| `GET /api/v1/oauth/authorize` | 20 requests | 5 minutes | Per client IP |
| `POST /api/v1/oauth/consent` | 10 requests | 5 minutes | Per client IP |
| `POST /api/v1/oauth/callback` | 20 requests | 5 minutes | Per client IP |
| `POST /api/v1/oauth/revoke` | 10 requests | 5 minutes | Per client IP |

General OAuth prefix endpoints that do not match a specific rule default to 20 requests per minute per IP.

### Tenant tier multipliers

Rate limits scale based on the organization's subscription tier:

| Tier | Multiplier | Effective token endpoint limit |
|------|------------|-------------------------------|
| Community / Free | 1.0x | 10 per 5 min |
| Pro | 2.0x | 20 per 5 min |
| Scale | 5.0x | 50 per 5 min |
| Enterprise | 10.0x | 100 per 5 min |

Tier information is resolved from the organization's `subscription_tier` or `billing_plan` field and cached in Redis for 5 minutes.

### Rate limit response headers

Every API response includes rate limit headers:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1708790400
```

When a limit is exceeded, the API returns HTTP 429 with a `Retry-After` header indicating when the client can retry.

### Auto-banning

Clients that exceed rate limits more than 10 times within an hour are automatically banned for 1 hour. Monitor for bans in the API logs:

```bash
kubectl logs -n janua -l app=janua-api | grep "banned"
```

### Exemptions

IPs listed in the `RATE_LIMIT_WHITELIST` environment variable are effectively unlimited. Internal network IPs (10.x.x.x, 192.168.x.x) receive 2x the default limit.

Health check and JWKS endpoints (`/health`, `/ready`, `/.well-known/jwks.json`) are exempt from rate limiting.

---

## Per-Client Audience Claims

Each OAuth client can be assigned a unique `aud` (audience) claim. When a token is issued for a specific client, the `aud` claim is set to that client's registered audience value. This ensures that tokens issued for app A are rejected by app B when app B validates the `aud` claim against its own expected audience string.

### How audience is resolved

At token issuance time (in the `POST /oauth/token` endpoint), the audience is resolved as:

```
client.audience || settings.JWT_AUDIENCE
```

If the client has an `audience` field set, that value is used. Otherwise, the global `JWT_AUDIENCE` from the server configuration is used as a fallback.

### Setting the audience

The audience is set during client registration and included in the `OAuthClientCreate` schema:

```bash
curl -X POST https://api.janua.dev/api/v1/oauth/clients \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "stratum-tcg",
    "audience": "stratum-tcg-api",
    "redirect_uris": ["https://stratum-tcg.dev/api/auth/callback"],
    "allowed_scopes": ["openid", "profile", "email"]
  }'
```

### Audience values for ecosystem apps

The seed script pre-configures these audience values:

| App | Audience |
|-----|----------|
| Stratum-TCG | `stratum-tcg-api` |
| Dhanam | `dhanam-api` |
| Enclii | `enclii-api` |
| Yantra4D | `yantra4d-api` |
| Tezca | `tezca-api` |

### Consumer responsibility

Every consumer app must validate the `aud` claim when verifying JWTs. The expected audience string must match exactly (case-sensitive) what was registered for that client. Tokens with a mismatched `aud` must be rejected.

Example validation (Python):

```python
import jwt

payload = jwt.decode(
    token,
    public_key,
    algorithms=["RS256"],
    issuer="https://api.janua.dev",
    audience="stratum-tcg-api",  # must match registered audience
)
```

---

## Monitoring and Troubleshooting

### CORS errors

**Symptom**: Browser console shows `Access-Control-Allow-Origin` errors when a consumer app calls Janua endpoints.

**Diagnosis**:

1. Verify the client's `redirect_uris` are registered correctly:

   ```bash
   curl https://api.janua.dev/api/v1/oauth/clients/{client_db_id} \
     -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.redirect_uris'
   ```

2. Confirm the origin derived from the redirect URI matches what the browser sends. For example, if the redirect URI is `https://my-app.dev/callback`, the origin must be `https://my-app.dev` (no path, no trailing slash).

3. If the client was just created or updated, wait up to 60 seconds for the CORS cache to refresh.

4. Check that the origin is not blocked by a more specific rule in the static `CORS_ORIGINS` configuration.

**Resolution**: Update the client's `redirect_uris` to include a URI whose origin matches the browser's request origin.

### Audience mismatch

**Symptom**: Token validation fails with "audience invalid" or "invalid aud claim" even though the user authenticated successfully.

**Diagnosis**:

1. Decode the access token to inspect the `aud` claim:

   ```bash
   echo $TOKEN | cut -d'.' -f2 | base64 -d 2>/dev/null | jq '.aud'
   ```

2. Compare the token's `aud` value against what the consumer app expects.

3. Check the client's registered audience:

   ```bash
   curl https://api.janua.dev/api/v1/oauth/clients/{client_db_id} \
     -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.audience'
   ```

**Resolution**: Ensure the consumer app's token validation configuration uses the exact same audience string that was registered for its OAuth client. These are case-sensitive.

### Key rotation issues

**Symptom**: Consumer apps reject valid tokens after a JWKS key rotation, reporting "invalid signature" or "unknown kid".

**Diagnosis**:

1. Check the current JWKS keys:

   ```bash
   curl https://api.janua.dev/.well-known/jwks.json | jq '.keys[] | .kid'
   ```

2. Decode the rejected token's header to find the `kid`:

   ```bash
   echo $TOKEN | cut -d'.' -f1 | base64 -d 2>/dev/null | jq '.kid'
   ```

3. Verify the token's `kid` exists in the JWKS response.

**Resolution**: If the consumer app uses a strict TTL cache for JWKS, it may not have fetched the new key yet. Ask the consumer to clear their JWKS cache or wait for their cache TTL to expire. Best practice is for consumers to implement `kid`-based JWKS refresh: when an unknown `kid` is encountered, re-fetch the JWKS before rejecting the token.

### Rate limit exceeded

**Symptom**: Consumer app receives HTTP 429 responses.

**Diagnosis**:

1. Check the `X-RateLimit-Remaining` and `Retry-After` response headers.
2. Identify the client and endpoint from the API logs:

   ```bash
   kubectl logs -n janua -l app=janua-api | grep "Rate limit exceeded"
   ```

3. Check if the client's organization tier entitles them to higher limits.

**Resolution**: If the client legitimately needs higher throughput, upgrade their organization's subscription tier. For temporary relief during migrations or load tests, add the client's IP to `RATE_LIMIT_WHITELIST`.

### Client secret not working after rotation

**Symptom**: Consumer app receives `invalid_client` errors after a secret rotation.

**Diagnosis**:

1. Check the secret status to verify the grace period has not expired:

   ```bash
   curl https://api.janua.dev/api/v1/oauth/clients/{client_db_id}/secrets \
     -H "Authorization: Bearer $ADMIN_TOKEN" | jq
   ```

2. Verify the consumer app is using the new secret, not the old one.

**Resolution**: If the grace period has expired and the consumer is still using the old secret, perform another rotation with a longer grace period and coordinate the credential update with the consumer team.
