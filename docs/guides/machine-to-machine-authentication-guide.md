# Machine-to-Machine Authentication Guide

Janua supports confidential OAuth clients for service-to-service MADFAM ecosystem
operations. Use this pattern for automated probes, Selva platform agents, and
Codex-assisted verification runs. Do not share human superadmin passwords with
automation.

## Recommended identity

Create one Janua OAuth client per operational capability. For ecosystem-wide
truth probes, use a client like `madfam-ecosystem-probe` with:

- `grant_types`: `["client_credentials"]`
- `is_confidential`: `true`
- `allowed_scopes`: only the required scopes, for example `openid`,
  `yantra4d:quote`, `cotiza:quote`, `forgesight:read`, and optionally `admin`
  when a run must exercise admin-only routes
- `organization_id`: the MADFAM platform organization
- `audience`: the downstream API audience that will validate the token

The issued access token is short-lived and has no refresh token.

## Token claims

`client_credentials` tokens include downstream-compatible claims:

- `sub`: `service-account:<client_id>`
- `email`: deterministic non-human service email
- `client_id`: Janua OAuth client id
- `token_use`: `client_credentials`
- `actor_type`: `service_account`
- `roles`: includes `service_account`; includes `admin` only when the client is
  allowed to request the `admin` scope and actually requests it
- `org_id` and `tenant_id`: populated from the client organization
- `tier`: organization subscription tier
- `<product>_tier`: product-specific org tiers such as `yantra4d_tier`

If Janua cannot resolve the client organization, explicitly granted product
scopes such as `yantra4d:quote` still emit `<product>_tier: "madfam"` for that
product. This keeps platform-owned machine probes usable during organization
directory degradation while preserving least privilege through the client scope
allowlist.

This lets Yantra4D, Cotiza, ForgeSight, Enclii, and Selva validate one Janua
token shape without custom per-service credentials.

## Provisioning policy

Provision the client through Enclii or Selva tools that call Janua's managed API:

```bash
POST /api/v1/oauth/clients/register
X-Internal-API-Key: <stored in Enclii/Vault>
```

Store the returned `client_secret` immediately in Enclii/Vault. Janua returns
the secret only once. Authorized Selva agents should receive access through the
secret store or an Enclii-issued runtime mount, not by copying the secret into
source code, chats, shell history, or Kubernetes manifests.

## Token request

```bash
curl -sS https://auth.madfam.io/api/v1/oauth/token \
  -u "$JANUA_CLIENT_ID:$JANUA_CLIENT_SECRET" \
  -d grant_type=client_credentials \
  -d scope="openid yantra4d:quote cotiza:quote forgesight:read"
```

If the client asks for a scope that was not granted on the OAuth client, Janua
returns `invalid_scope`.

## Rotation

Rotate client secrets through Janua's OAuth client secret-rotation endpoint and
roll the new value through Enclii/Vault. Do not create a new human admin account
for automated runs unless there is a specific browser-only test that cannot be
represented by a service account.
