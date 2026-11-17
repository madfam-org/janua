# Issuer, JWKS and audience: how to verify a Janua token

This page is the reference that services link to when they verify tokens
issued by Janua. It describes the code as it is on `main`; the source files
are named in each section. Paths are relative to `apps/api/app/`.

Related:

- [Service tokens](../service-tokens.md): `client_credentials` clients, their
  claims, scopes and per-edge audiences.
- [Claims de organización y service principals](../architecture/CLAIMS_DE_ORGANIZACION_Y_SERVICE_PRINCIPALS.md)
  (Spanish): organization, role and tier claims on session and OIDC tokens.
- [Protected resources and MCP clients](./PROTECTED_RESOURCES_AND_MCP_CLIENTS.md):
  RFC 9068 tokens for a protected resource such as an MCP server.

## Issuer

Every Janua deployment has one issuer URL. Read it from the discovery
document, not from a hard-coded default:

```text
GET <issuer>/.well-known/openid-configuration   →   { "issuer": "<issuer>", "jwks_uri": "<issuer>/.well-known/jwks.json", … }
```

Two settings produce the `iss` claim:

| Source | Used by | How it is set |
| --- | --- | --- |
| `JWT_ISSUER` | session, OAuth/OIDC access and refresh, `client_credentials`, guest and SSO-cookie tokens | `config.py`: default `https://api.janua.dev`; `compute_jwt_issuer_from_custom_domain` replaces the default with `https://<JANUA_CUSTOM_DOMAIN>` when `JANUA_CUSTOM_DOMAIN` is set |
| `https://<JANUA_CUSTOM_DOMAIN>`, else `API_BASE_URL` | the discovery document, OIDC ID tokens, protected-resource tokens | `core/oauth_metadata.py::oauth_issuer`, `routers/v1/oauth_provider.py::_generate_id_token` |

Production sets `JANUA_CUSTOM_DOMAIN=auth.madfam.io` and leaves `JWT_ISSUER`
at its default (`k8s/base/deployments/janua-api.yaml`), so both resolve to
`https://auth.madfam.io`. Staging sets `JANUA_CUSTOM_DOMAIN`, `API_BASE_URL`
and `JWT_ISSUER` to the same origin (`k8s/overlays/staging/api.yaml`). A
deployment that sets `JWT_ISSUER` explicitly must keep it equal to the
discovery issuer. Verifiers compare `iss` exactly; a trailing slash counts.

## JWKS

| Item | Value |
| --- | --- |
| URL | `<issuer>/.well-known/jwks.json` (also `jwks_uri` in discovery) |
| Key type | RSA, `use: sig`, `alg: RS256` |
| Keys published | exactly one: the current signing key |
| `kid` | the value of `JWT_KID` (default `janua-primary-key`) |

Source: `core/jwt_manager.py::get_jwks`.

Production runs RS256 only: with `ENVIRONMENT=production` and no RSA PEM in
`JWT_PRIVATE_KEY`, the JWT manager raises at startup. The HS256 fallback exists
for local development and tests, and in that mode the JWKS is empty
(`{"keys": []}`).

### Which tokens carry `kid`

Every RS256 token is signed with the one published key, but not every token
names it in its JOSE header:

| Minted by | Tokens | JOSE header |
| --- | --- | --- |
| `services/auth_service.py::AuthService.create_access_token` / `create_refresh_token` (plain `jwt.encode`, no headers) | first-party session access and refresh tokens: password, magic link, MFA completion and passkey sign-in (`AuthService.create_session`) and their refresh (`AuthService.refresh_tokens`) | `alg: RS256`, **no `kid`** |
| `core/jwt_manager.py` (`create_access_token`, `create_refresh_token`, `encode_token`) | OAuth/OIDC access and refresh tokens, OIDC ID tokens, `client_credentials` tokens, guest tokens, the SSO cookies (`auth/sso_cookie.py`, `auth/sessions_cookie.py`), protected-resource access and refresh tokens (`services/resource_tokens.py`), SAML sign-in tokens (`routers/v1/sso.py`) | `alg: RS256`, `kid: <JWT_KID>`; protected-resource access tokens also `typ: at+jwt` |
| `auth/mfa_enforcement.py::mint_mfa_challenge_token` | MFA challenge tokens | `alg: HS256`; no JWKS key verifies them |

### Selecting the key

A verifier that only looks keys up by `kid` rejects every first-party session
token. Select the key like this:

1. Pin the algorithm list to `["RS256"]` in code. Never take the algorithm from
   the token header, and never accept `none` or HS256.
2. When the header has a `kid`, use the JWKS key with that `kid`.
3. When the header has no `kid`, try each RS256 `sig` key in the JWKS until one
   verifies the signature.
4. Cache the JWKS with a TTL (one hour is reasonable). When no cached key
   verifies (an unknown `kid`, or no key verifies a token without one), refetch
   the JWKS and try again, at most once per minute. Reject the token if it
   still does not verify.

## `kid` rotation

Rotation is a **hard cut**, not an overlap:

1. Generate a new RSA key pair (2048 bits or more).
2. Set `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY` and a **new** `JWT_KID`.
3. Restart the API. From then on, the JWKS publishes only the new key.

Consequences, as the code works today:

- Tokens signed with the old key fail verification as soon as a verifier
  refreshes its JWKS. Refresh tokens are signed with the same key, so users
  sign in again.
- A verifier that caches the JWKS refetches it on a miss, as described in
  [Selecting the key](#selecting-the-key), and only then rejects.
- Janua cannot publish the previous key next to the new one, so there is no
  window in which both verify. Plan rotations for a quiet hour.

Keep `JWT_KID` stable between restarts. Changing `JWT_KID` alone acts like a
rotation for tokens that carry a `kid`: tokens already issued name the old
`kid`, which the JWKS no longer lists, so a verifier that matches by `kid`
rejects them.

## Token kinds: the `type` claim

Several kinds of token share the issuer and the signing key. A resource server
requires **`type == "access"`** and refuses everything else:

| `type` | Token | Minted in |
| --- | --- | --- |
| `access` | first-party session access token, OAuth/OIDC user access token, `client_credentials` token | `services/auth_service.py`, `core/jwt_manager.py` |
| `refresh` | session and OAuth refresh tokens | `services/auth_service.py`, `core/jwt_manager.py` |
| `resource_refresh` | protected-resource refresh token | `services/resource_tokens.py` |
| `guest_access` | guest token | `routers/v1/guest.py` |
| `sso_session` | `janua_sso` cookie | `auth/sso_cookie.py` |
| `sso_session_set` | held-sessions cookie | `auth/sessions_cookie.py` |
| `mfa_challenge` | MFA challenge token (HS256, so it also fails the RS256 pin) | `auth/mfa_enforcement.py` |
| none | OIDC ID token (`aud` = the `client_id`) | `routers/v1/oauth_provider.py::_generate_id_token` |
| none | protected-resource access token (RFC 9068, header `typ: at+jwt`) | `services/resource_tokens.py` |

Protected-resource access tokens are for the MCP resource flow only; their
verifier checks `typ: at+jwt` instead of `type` (see
[PROTECTED_RESOURCES_AND_MCP_CLIENTS.md](./PROTECTED_RESOURCES_AND_MCP_CLIENTS.md)).
A relying party that consumes ID tokens for sign-in checks
`aud == <its client_id>` and does not use them as access tokens.

### Telling access tokens apart

| Kind | Claims that identify it |
| --- | --- |
| First-party session access | no `client_id`; carries `tid`, `family` and `sid`; header has no `kid` |
| OAuth/OIDC user access | `client_id` and `scope`; `sub` is a Janua user id (it may also carry `sid`) |
| `client_credentials` | `token_use: "client_credentials"`, `actor_type: "service_account"`, `sub: "service-account:<client_id>"`, plus `client_id` and `scope` |

SAML sign-in access tokens (`routers/v1/sso.py`) carry a `kid` and no
`client_id`, `tid`, `family` or `sid`.

## Audience

| Token | `aud` | Issued by |
| --- | --- | --- |
| OIDC ID token | the OAuth `client_id` | `routers/v1/oauth_provider.py::_generate_id_token` |
| OAuth user access and refresh tokens (authorization code, refresh) | the client's `audience`, else `JWT_AUDIENCE` | `routers/v1/oauth_provider.py` |
| `client_credentials` token | the client's `audience`, else `JWT_AUDIENCE` | `routers/v1/oauth_provider.py::_handle_client_credentials_grant`; see [service-tokens.md](../service-tokens.md) |
| First-party session access token | `JWT_AUDIENCE`, or for a magic-link session the audience of its redirect target | `services/auth_service.py::AuthService.create_access_token` |
| First-party session refresh token | `JWT_AUDIENCE` | `services/auth_service.py::AuthService.create_refresh_token` |
| Guest token | `janua-guest` | `routers/v1/guest.py`, `core/reserved_oauth_boundaries.py::GUEST_AUDIENCE` |
| SSO cookies | `JWT_AUDIENCE` | `auth/sso_cookie.py`, `auth/sessions_cookie.py` |
| Protected-resource access token (RFC 8707 `resource`) | the resource URI exactly | `services/resource_tokens.py`; see [PROTECTED_RESOURCES_AND_MCP_CLIENTS.md](./PROTECTED_RESOURCES_AND_MCP_CLIENTS.md) |

A resource server checks that `aud` equals **its own** audience, exactly and
case-sensitively.

**The platform default.** `JWT_AUDIENCE` defaults to `janua.dev` (`config.py`);
production keeps the default and staging sets `janua-staging`. First-party
session tokens carry it, and so does every token of a client that has no
audience of its own. It cannot be reserved for that reason
(`core/reserved_oauth_boundaries.py::SHARED_DEFAULT_AUDIENCES`). A resource
server that accepts it accepts tokens from all of those sources, so it also
decides on `type` and on the claims in
[Telling access tokens apart](#telling-access-tokens-apart).

**A client's own audience.** `OAuthClient.audience` is not unique
(`models/__init__.py`): any number of clients can carry the same value.
Registering or editing a client with a reserved audience is a platform-admin
action (`services/oauth_client_authority.py`); the reserved values are listed
in `core/reserved_oauth_boundaries.py` (every `janua-*` audience, the ecosystem
service audiences and the consent-purpose subject audiences). An audience is
therefore trustworthy as "issued to a client a platform admin registered" only
when it is reserved there. For an audience that is not reserved, also check
`client_id` against the clients you expect.

## Claims every verifier checks

| Check | Rule |
| --- | --- |
| Algorithm | `RS256`, from a fixed allow-list in code |
| Signature | the JWKS key chosen as in [Selecting the key](#selecting-the-key) |
| `type` | equals `access` |
| `iss` | equals the discovery `issuer` |
| `aud` | equals the verifier's own audience |
| `exp` | in the future; a small leeway (30 s or less) for clock skew is fine |
| `sub` | the stable subject: a Janua user id, or `service-account:<client_id>` for `client_credentials` tokens |

Lifetimes today: ID tokens 1 hour, `client_credentials` tokens 1 hour
(`SERVICE_TOKEN_TTL_SECONDS`), session and OAuth user access tokens
`JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 480 minutes), protected-resource
access tokens the resource's own lifetime (at most 15 minutes).

## Example (Python, PyJWT)

```python
import threading
import time

import jwt
import requests

ISSUER = "<issuer>"  # the `issuer` from discovery
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
ALGORITHMS = ["RS256"]  # fixed in code; never read from the token header
JWKS_TTL_SECONDS = 3600
MIN_REFETCH_SECONDS = 60


class JanuaKeys:
    """The JWKS's RS256 signing keys, cached with a TTL."""

    def __init__(self) -> None:
        self._keys: list[tuple[str | None, object]] = []
        self._fetched_at = float("-inf")
        self._lock = threading.Lock()

    def _fetch(self) -> None:
        document = requests.get(JWKS_URL, timeout=5).json()
        self._keys = [
            (jwk.get("kid"), jwt.PyJWK(jwk, algorithm="RS256").key)
            for jwk in document.get("keys", [])
            if jwk.get("kty") == "RSA"
            and jwk.get("use", "sig") == "sig"
            and jwk.get("alg", "RS256") == "RS256"
        ]
        self._fetched_at = time.monotonic()

    def candidates(self, kid: str | None, *, refetch: bool = False) -> list:
        with self._lock:
            age = time.monotonic() - self._fetched_at
            if age > JWKS_TTL_SECONDS or (refetch and age > MIN_REFETCH_SECONDS):
                self._fetch()
            keys = self._keys
        if kid is not None:
            return [key for key_id, key in keys if key_id == kid]
        return [key for _, key in keys]  # session tokens carry no `kid`


_keys = JanuaKeys()


def verify_access_token(token: str, audience: str) -> dict:
    kid = jwt.get_unverified_header(token).get("kid")
    for refetch in (False, True):  # one refetch on a miss, rate-limited above
        for key in _keys.candidates(kid, refetch=refetch):
            try:
                claims = jwt.decode(
                    token,
                    key,
                    algorithms=ALGORITHMS,
                    issuer=ISSUER,
                    audience=audience,
                    leeway=30,
                    options={"require": ["exp", "iss", "aud", "sub"]},
                )
            except jwt.InvalidSignatureError:
                continue
            if claims.get("type") != "access":
                raise jwt.InvalidTokenError("not an access token")
            return claims
    raise jwt.InvalidSignatureError("no Janua signing key verifies this token")
```

The Janua SDK verification helpers predate this page; see the notes in
`packages/jwt-utils/README.md`, `packages/python-sdk/README.md` and
`packages/go-sdk/README.md` before using them in a resource server.

## Related

- [Token validation in the integration guide](../guides/ECOSYSTEM_INTEGRATION.md#4-token-validation)
  and [JWKS caching](../guides/ECOSYSTEM_INTEGRATION.md#5-jwks-caching-best-practices)
- [Service tokens](../service-tokens.md): service clients, scopes and per-edge audiences
- [Claims de organización y service principals](../architecture/CLAIMS_DE_ORGANIZACION_Y_SERVICE_PRINCIPALS.md):
  organization, role and tier claims
- [Machine-to-machine authentication](../guides/machine-to-machine-authentication-guide.md)
