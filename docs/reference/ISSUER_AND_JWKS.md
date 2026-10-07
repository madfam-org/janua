# Issuer, JWKS and audience: how to verify a Janua token

This page is the reference that services link to when they verify tokens
issued by Janua. It describes the code as it is on `main`; the source files
are named in each section.

## Issuer

Every Janua deployment has one issuer URL. Read it from the discovery
document, not from a hard-coded default:

```text
GET <issuer>/.well-known/openid-configuration   →   { "issuer": "<issuer>", "jwks_uri": "<issuer>/.well-known/jwks.json", … }
```

How Janua chooses it (`apps/api/app/main.py::openid_configuration`,
`apps/api/app/config.py::compute_jwt_issuer_from_custom_domain`):

1. If `JANUA_CUSTOM_DOMAIN` is set (a white-label deployment), the issuer is
   `https://<JANUA_CUSTOM_DOMAIN>`. Every endpoint in the discovery document
   uses that origin too.
2. Otherwise the issuer is `API_BASE_URL` (the default is `https://api.janua.dev`).

The `iss` claim in ID tokens, access tokens and service tokens equals that
issuer. One caveat without a custom domain: discovery and ID tokens use
`API_BASE_URL`, while access and service tokens use `JWT_ISSUER`. Both default
to `https://api.janua.dev`; a deployment that changes one must change the other. Verifiers must compare `iss` exactly; a trailing slash counts.
For the issuer of a specific hosted deployment, see that deployment's
discovery document (for example, [service-tokens.md](../service-tokens.md#endpoints)).

## JWKS

| Item | Value |
| --- | --- |
| URL | `<issuer>/.well-known/jwks.json` (also `jwks_uri` in discovery) |
| Key type | RSA, `use: sig`, `alg: RS256` |
| Keys published | exactly one: the current signing key |
| `kid` | the value of `JWT_KID` (default `janua-primary-key`) |

Source: `apps/api/app/core/jwt_manager.py::get_jwks`. Every RS256 token carries
the same `kid` in its JOSE header.

Production runs RS256 only: with `ENVIRONMENT=production` and no RSA PEM in
`JWT_PRIVATE_KEY`, the JWT manager raises at startup. The HS256 fallback exists for local
development and tests, and in that mode the JWKS is empty (`{"keys": []}`).
Verifiers must pin the algorithm list to `["RS256"]` and never accept `none`
or HS256.

## `kid` rotation

Rotation is a **hard cut**, not an overlap:

1. Generate a new RSA key pair (2048 bits or more).
2. Set `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY` and a **new** `JWT_KID`.
3. Restart the API. From then on, the JWKS publishes only the new key.

Consequences, as the code works today:

- Tokens signed with the old key fail verification as soon as a verifier
  refreshes its JWKS. Refresh tokens are signed with the same key, so users
  sign in again.
- A verifier that caches the JWKS must refetch it when a token arrives with a
  `kid` it does not know, and only then reject. `PyJWKClient` (Python) and
  `jwks-rsa` (Node) do this.
- Janua cannot publish the previous key next to the new one, so there is no
  window in which both verify. Plan rotations for a quiet hour.

Keep `JWT_KID` stable between restarts. Changing `JWT_KID` alone acts like a
rotation for any verifier that matches keys by `kid`: tokens already issued
carry the old `kid`, which the JWKS no longer lists, so they are rejected.

## Audience

| Token | `aud` | Issued by |
| --- | --- | --- |
| OIDC ID token | the OAuth `client_id` | `/api/v1/oauth/token` (authorization code), `_generate_id_token` in `apps/api/app/routers/v1/oauth_provider.py` |
| Access token for an OAuth client (authorization code, refresh) | the client's registered `audience`, else `JWT_AUDIENCE` | same router |
| Service token (`client_credentials`) | the client's registered `audience` (e.g. `<service>-api`) | same router; see [service-tokens.md](../service-tokens.md) |
| First-party session token (Janua's own sign-in) | `JWT_AUDIENCE` (default `janua.dev`) or, for a magic-link session, the audience of its redirect target | `apps/api/app/core/jwt_manager.py` |
| Protected-resource access token (RFC 8707 `resource`, e.g. an MCP server) | the resource URI exactly, e.g. `https://map.creatumundo.mx/api/mcp`; header `typ: at+jwt`, no `type` claim | `apps/api/app/services/resource_tokens.py`; see [PROTECTED_RESOURCES_AND_MCP_CLIENTS.md](./PROTECTED_RESOURCES_AND_MCP_CLIENTS.md) |

A resource server checks that `aud` equals **its own** registered audience,
exactly and case-sensitively. A relying party that only consumes the ID token
(a web app using Janua for sign-in) checks `aud == <its client_id>`.

## Claims every verifier checks

| Check | Rule |
| --- | --- |
| Signature | RS256, with the JWKS key whose `kid` matches the header |
| `iss` | equals the discovery `issuer` |
| `aud` | equals the verifier's audience (or `client_id` for ID tokens) |
| `exp` | in the future; a small leeway (30 s or less) for clock skew is fine |
| `sub` | the stable subject: a Janua user id, or `service-account:<client_id>` for service tokens |

Lifetimes today: ID tokens 1 hour, service tokens 1 hour, user access tokens
`JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 480 minutes), protected-resource
access tokens the resource's own lifetime (at most 15 minutes).

A protected-resource verifier also checks the JOSE header `typ` is `at+jwt`
(RFC 9068), so no other Janua token can be presented to it, and the `iss` is
the discovery issuer (`https://auth.madfam.io` in production).

## Example (Python, PyJWT)

```python
import jwt
from jwt import PyJWKClient

ISSUER = "<issuer>"                     # from discovery
jwks = PyJWKClient(f"{ISSUER}/.well-known/jwks.json")  # caches; refetches on unknown kid

def verify(token: str, audience: str) -> dict:
    key = jwks.get_signing_key_from_jwt(token).key
    return jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        issuer=ISSUER,
        audience=audience,
        leeway=30,
        options={"require": ["exp", "iss", "aud", "sub"]},
    )
```

## Related

- [Token validation in the integration guide](../guides/ECOSYSTEM_INTEGRATION.md#4-token-validation)
  and [JWKS caching](../guides/ECOSYSTEM_INTEGRATION.md#5-jwks-caching-best-practices)
- [Service tokens](../service-tokens.md): service clients, scopes and per-edge audiences
- [Machine-to-machine authentication](../guides/machine-to-machine-authentication-guide.md)
