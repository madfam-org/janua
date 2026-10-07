# Protected resources and MCP clients

Janua can mint access tokens for a **protected resource**: an API, today one
MCP server, that a third-party client names in the RFC 8707 `resource`
parameter. The token's `aud` is that resource's URI, its scopes are the
resource's own, and it lives at most 15 minutes. This is how the center's
Director connects the MAP of Crea Tu Mundo to Claude (claude.ai, Desktop,
mobile) and how Claude Code connects to it.

A request **without** `resource`, from a registered (`jnc_…`) client, behaves
exactly as before. The only change every client sees is the `iss` parameter on
authorization responses (RFC 9207).

Code: `apps/api/app/core/protected_resources.py` (registry and policy),
`apps/api/app/services/client_id_metadata.py` (CIMD),
`apps/api/app/services/resource_tokens.py` (tokens),
`apps/api/app/routers/v1/oauth_provider.py` (the endpoints, section
"Protected resources"), `apps/api/app/auth/resource_consent_page.py` (consent).
Tests: `apps/api/tests/unit/routers/test_oauth_protected_resources.py`,
`tests/unit/services/test_client_id_metadata.py`,
`tests/unit/core/test_protected_resources.py`.

## The registry

The list is code, reviewed in a PR, never runtime configuration: adding a
resource, a scope, a CIMD host or a redirect URI widens who can get a token for
whose data. Anything not listed is refused with `invalid_target`.

| Field | MAP de Crea Tu Mundo |
| --- | --- |
| `resource` (= token `aud`, byte for byte) | `https://map.creatumundo.mx/api/mcp` |
| `display_name` (consent screen) | «MAP de Crea Tu Mundo» |
| scopes | `map.ops:read` «Consultar la operación del MAP, sin nombres ni datos clínicos»; `map.cobro:read` «Consultar la cobranza del MAP por clave de familia» |
| access token lifetime | 15 minutes (the registry refuses more) |
| refresh token | rotates on every use; ends after 7 days unused or 30 days after consent, whichever is first |
| CIMD hosts | `claude.ai` |
| CIMD client_ids (pinned) | `https://claude.ai/oauth/mcp-oauth-client-metadata` (claude.ai, Desktop, mobile, Cowork); `https://claude.ai/oauth/claude-code-client-metadata` (Claude Code) |
| exact redirect URIs | `https://claude.ai/api/mcp/auth_callback` |
| loopback redirects | allowed (`127.0.0.1`, `[::1]`, `localhost`, any port) |
| first login method offered | emailed link (`magic_link`) |

### Registering a new resource

1. Add a `ProtectedResource` to `_REGISTRY` in
   `apps/api/app/core/protected_resources.py`:
   - `resource`: the canonical URI (lowercase scheme and host, no default port,
     no trailing slash, no fragment). It must equal the `resource` field of the
     MCP server's protected-resource metadata (RFC 9728), because Claude sends
     exactly that value.
   - `display_name` and every scope `description`: plain Spanish for the
     person who reads the consent screen.
   - scopes: namespaced `area.thing:verb` names; never `offline_access`.
   - `client_policy`: the CIMD hosts, the exact CIMD client_id URLs Janua may
     fetch (each on one of those hosts), the exact https callback URIs, and
     whether loopback redirects are allowed.
   - `access_token_ttl_seconds` at most 900; the module refuses to import
     otherwise (`check_registry`).
2. Add the entry's expectations to `tests/unit/core/test_protected_resources.py`.
3. Nothing else to wire: discovery lists the new scopes, and the CSP
   `form-action` directive picks up new callback origins from the registry
   (without it the browser silently blocks the redirect after «Permitir»).
4. Merge, promote (manual, `promote-to-prod.yml`), then run
   [the post-promote checks](../runbooks/mcp-connector-post-promote.md).

## What Claude needs, and what Janua answers

Claude's connector client is stricter than the MCP specification in a few
places (https://claude.com/docs/connectors/building/authentication):

| Claude does / needs | Janua |
| --- | --- |
| Reads RFC 8414 metadata at `/.well-known/oauth-authorization-server` first, then OIDC discovery | Both paths serve the same document |
| Uses a Client ID Metadata Document only when the metadata has `client_id_metadata_document_supported: true` **and** `none` in `token_endpoint_auth_methods_supported`; otherwise falls back to DCR | Both advertised |
| Hosted apps identify as `https://claude.ai/oauth/mcp-oauth-client-metadata`, redirect `https://claude.ai/api/mcp/auth_callback` | Fetched (allowlisted host), exact match |
| Claude Code identifies as `https://claude.ai/oauth/claude-code-client-metadata`, redirects to `http://localhost:<port>/callback` or `http://127.0.0.1:<port>/callback` | Loopback matched with the port ignored |
| PKCE S256 on every authorization request; checks `code_challenge_methods_supported` | `["S256"]`; `plain` and missing PKCE are refused |
| Sends `resource` on authorization and token requests | Required for CIMD clients; must name a registered resource |
| Appends `offline_access` when the metadata lists it | Issues a refresh token only then |
| Token requests are `application/x-www-form-urlencoded` | Read as form fields |
| Refresh: needs RFC 6749 `invalid_grant` for a dead refresh token, and the new refresh token in the same response | Yes, both |
| 10 s for discovery, registration and token; 30 s for refresh | No outbound call on the token endpoint; the only outbound call (CIMD fetch, cached 5 minutes) happens at `/authorize` and is capped at 5 s |
| Calls from `160.79.104.0/21` | `auth.madfam.io` must not challenge that range (Cloudflare WAF / bot rules) |

The resource side (the MCP server) must answer an unauthenticated call with
`401` and `WWW-Authenticate: Bearer resource_metadata="…"`, and serve
protected-resource metadata whose `authorization_servers` lists
`https://auth.madfam.io` first and whose `resource` is the registered URI.

## Tokens

**Access token** (RFC 9068 JWT, RS256, verify with `https://auth.madfam.io/.well-known/jwks.json`):

| Part | Value |
| --- | --- |
| header `typ` | `at+jwt` |
| `iss` | `https://auth.madfam.io` (the discovery issuer) |
| `aud` | the resource URI exactly |
| `sub` | the person's Janua user id: the same `sub` as their ID token and as their MAP session token, i.e. what crea-map stores in `Member.januaSubject` |
| `client_id` | the CIMD URL (`https://claude.ai/oauth/…`) or the registered `jnc_…` id |
| `scope` | the granted resource scopes, space-separated (never `offline_access`) |
| `iat`, `exp`, `jti` | `exp - iat` = the resource's lifetime (900 s for the MAP) |

It deliberately has no Janua `type` claim, no email, roles or organization
claims. Every Janua verifier of its own session tokens requires
`type == "access"`, so a resource token is never a Janua session. A MAP session
token (`aud` `crea-map`, `type` `access`) is not a resource token either: the
resource must check `typ`, `iss`, `aud` and `exp`. In Python:

```python
header = jwt.get_unverified_header(token)
assert header.get("typ", "").lower() in ("at+jwt", "application/at+jwt")
claims = jwt.decode(
    token,
    PyJWKClient("https://auth.madfam.io/.well-known/jwks.json").get_signing_key_from_jwt(token).key,
    algorithms=["RS256"],
    issuer="https://auth.madfam.io",
    audience="https://map.creatumundo.mx/api/mcp",
    options={"require": ["exp", "iat", "iss", "aud", "sub", "jti"]},
)
```

With `jose` (Node): `jwtVerify(token, createRemoteJWKSet(jwksUrl), { issuer,
audience, algorithms: ["RS256"], typ: "at+jwt" })`. Find the member by `sub`
only; mailbox equality must not establish identity.

**Refresh token**: read only by Janua. Single use: the first redemption wins;
presenting an already-used one is treated as theft and revokes the whole
family (that connection must be authorized again), and the answer is
`invalid_grant`. A refresh may narrow the scope (`scope=` a subset) but never
widen it; the rotated refresh token keeps the original grant.

**Revocation**: `POST /api/v1/oauth/revoke` with `token` and `client_id` (a
CIMD client sends no secret). A refresh token revokes its family. Access tokens
are verified offline and expire within 15 minutes, so revoking one has no
effect. Introspection answers `{"active": false}` for resource tokens: the
resource verifies them offline against the JWKS.

## Clients

- **Client ID Metadata Documents** (draft-ietf-oauth-client-id-metadata-document):
  an `https` client_id is fetched only when it is one of the resource's
  pinned client_id URLs, on its host allowlist; the URL fetched is the
  registry's string, never the request's (a new Claude client URL needs a
  registry change). The URL must be `https`, default port, no user info, query or
  fragment, a real path without dot segments, a host name (not an IP). Every
  address the host resolves to must be public; the connection goes to the
  checked address (TLS still verified against the host name); no redirects;
  `200`, JSON, at most 10 KB, within 5 s overall. The document must name
  itself (`client_id` equal to the URL), be a public client
  (`token_endpoint_auth_method: none`), list `redirect_uris`, and carry no
  secret. Valid documents are cached per process for their `max-age` (at most
  an hour, 64 entries); failures are never cached.
- **Registered clients** (`jnc_…`, created through the admin API; this is
  also what Claude's "use your own OAuth client" option uses): allowed when
  every registered redirect URI is inside the resource's policy
  (`https://claude.ai/api/mcp/auth_callback` or loopback), and the request uses
  one of them. A confidential client authenticates at the token endpoint as
  usual. Prefer the CIMD path: Janua's CORS layer trusts the origin of every
  registered redirect URI, with credentials, so a registered loopback client
  also opens the API to that local origin.
- **Dynamic Client Registration**: Janua has no RFC 7591 endpoint. Discovery
  has long advertised `registration_endpoint`
  (`/api/v1/oauth/register`), which answers 404; Claude does not use it
  because CIMD is advertised. Whether to implement it or stop advertising it
  is an open owner decision (AGENTS.md backlog).

## Consent

A resource-bound request always shows the consent screen, in Spanish, and
nothing is remembered: no client is pre-consented, so a program on the same
computer cannot obtain a code silently by posing as Claude Code. The page names
the resource, the app by host (the CIMD URL's host, or the redirect host for a
registered client; the self-declared name only as a secondary line), where the
browser goes next, each scope in plain words, the refresh-token lifetime when
one is requested, and the signed-in account. When the redirect is a loopback
address it says the authorization goes to «una aplicación en esta computadora»
and warns that any local program could pose as the app.

## Errors

At `/authorize`, problems with the client or its redirect URI render a `400`
page and never redirect (RFC 6749 §4.1.2.1): unknown or refused client, CIMD
fetch or validation failure, unregistered redirect URI. After that, errors go
back to the redirect URI with `error`, `error_description`, `state` and `iss`:

| `error` | When |
| --- | --- |
| `invalid_target` | `resource` missing (CIMD client), malformed, unknown, or more than one |
| `unsupported_response_type` | anything but `code` |
| `unauthorized_client` | the client or redirect URI is outside the resource's policy |
| `invalid_request` | no `code_challenge`, method not `S256`, malformed challenge |
| `invalid_scope` | no requested scope belongs to the resource |
| `login_required` / `consent_required` | `prompt=none` (consent is always interactive) |
| `access_denied` | the person pressed «Cancelar» |

The token endpoint answers RFC 6749 §5.2 JSON (`{"error", "error_description"}`,
`Cache-Control: no-store`) on this path: `invalid_client` (401),
`invalid_grant` (bad, expired, reused, revoked or foreign code or refresh
token; inactive account), `invalid_target` (a `resource` different from the
grant's, or a default-flow code), `invalid_scope` (a refresh that adds scopes),
`invalid_request`, `unauthorized_client`. Redis unavailable is `503` with
`Retry-After`, never `invalid_grant`.

## Known limits

- One resource per request (RFC 8707 allows several).
- `http://[::1]` redirects match, but CSP `form-action` cannot list an IPv6
  literal, so a browser may block the redirect after the consent POST. Claude
  Code uses `localhost` and `127.0.0.1`.
- `sub` is whichever Janua account the person signs in with at
  `auth.madfam.io`. If one email exists in more than one user pool, the hosted
  login may pick a different account than the one the MAP knows, and the MAP
  will not recognize the token.
- The access token carries no email, so a MAP member who has never signed in
  to the MAP (provisional `pending:` subject) is not recognized until they do.
- A connection is not tied to a Janua session: signing out, "sign out
  everywhere" or a password change does not end it. It ends when the client
  revokes it (removing the connector), when the account stops being active, or
  at the latest 30 days after consent. There is no operator switch for one
  connection yet; suspending the account ends all of them at the next refresh
  (access tokens already issued run out within 15 minutes).
- Consent grants are logged (`oauth.resource_consent.granted`,
  `oauth.resource_token.issued`) but not written to `audit_logs`: the audit
  event type is a database enum and a new value needs a migration.
