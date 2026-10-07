# After promoting: protected resources and the MAP connector

For the owner, after `promote-to-prod.yml` ships the Janua API version that
added protected resources (RFC 8707), Client ID Metadata Documents and RFC 8414
metadata. Background: [Protected resources and MCP clients](../reference/PROTECTED_RESOURCES_AND_MCP_CLIENTS.md).
Merged is not live: confirm the running digest first
([production-gitops-reconcile.md](./production-gitops-reconcile.md)).

Every command below only reads, except where marked. None needs a credential.

## 1. Discovery

```bash
curl -s https://auth.madfam.io/.well-known/oauth-authorization-server | jq '{
  issuer, authorization_endpoint, token_endpoint,
  code_challenge_methods_supported, response_types_supported,
  client_id_metadata_document_supported,
  authorization_response_iss_parameter_supported,
  token_endpoint_auth_methods_supported,
  map_scopes: [.scopes_supported[] | select(startswith("map."))]
}'
```

Expected: `issuer` `https://auth.madfam.io`; endpoints under it;
`code_challenge_methods_supported` `["S256"]`; `response_types_supported`
`["code"]`; both flags `true`; `none` in the auth methods; `map_scopes`
`["map.ops:read", "map.cobro:read"]`. Before the promote this URL answered 404.

The OIDC document must be the same document:

```bash
diff <(curl -s https://auth.madfam.io/.well-known/openid-configuration | jq -S .) \
     <(curl -s https://auth.madfam.io/.well-known/oauth-authorization-server | jq -S .) \
  && echo identical
curl -s -o /dev/null -w '%{http_code} %{time_total}s\n' \
  https://auth.madfam.io/.well-known/oauth-authorization-server   # 200, well under 10 s
```

## 2. The authorization endpoint fetches Claude's document and refuses an unknown resource

```bash
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' \
  'https://auth.madfam.io/api/v1/oauth/authorize?response_type=code&client_id=https%3A%2F%2Fclaude.ai%2Foauth%2Fmcp-oauth-client-metadata&redirect_uri=https%3A%2F%2Fclaude.ai%2Fapi%2Fmcp%2Fauth_callback&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256&state=probe&resource=https%3A%2F%2Fexample.invalid%2Fmcp'
```

Expected: `302 https://claude.ai/api/mcp/auth_callback?error=invalid_target&…&state=probe&iss=https%3A%2F%2Fauth.madfam.io`.
That proves three things at once: the pod can reach `claude.ai` (egress), the
document validates, and `iss` is on the redirect. A `400` page whose text says
the client could not be verified means the fetch failed; read the API log for
`oauth.cimd.rejected` and its `reason`.

The same request with the MAP as resource (`resource=https%3A%2F%2Fmap.creatumundo.mx%2Fapi%2Fmcp`)
and no browser session answers `302` to `/api/v1/auth/login?…&login_method=magic_link`.
(This one stores a 20-minute sign-in record in Redis, like any sign-in attempt.)

## 3. Browser security headers and the token endpoint

```bash
curl -sI https://auth.madfam.io/.well-known/oauth-authorization-server \
  | grep -i '^content-security-policy' | tr ';' '\n' | grep form-action   # contains https://claude.ai

curl -s -X POST https://auth.madfam.io/api/v1/oauth/token \
  -d grant_type=refresh_token -d refresh_token=not-a-token \
  -d client_id=https://claude.ai/oauth/mcp-oauth-client-metadata \
  -d resource=https://map.creatumundo.mx/api/mcp
# {"error":"invalid_grant","error_description":"…"}  — the RFC 6749 shape Claude reads
```

If `form-action` lacks `https://claude.ai`, «Permitir» on the consent screen
does nothing in Chrome.

## 4. MCP Inspector

Once crea-map serves the MCP endpoint (`https://map.creatumundo.mx/api/mcp`):

```bash
npx @modelcontextprotocol/inspector
```

Connect to the URL with transport "Streamable HTTP" and open the OAuth
debugger ("Open Auth Settings" → guided flow). The metadata step must show the
MAP's protected-resource metadata (`authorization_servers` first entry
`https://auth.madfam.io`) and then Janua's metadata with
`client_id_metadata_document_supported: true`. The Inspector's own client is
**not** on the MAP's client policy (Claude and Claude Code only), so its
authorization step is refused: a `400` page «No se pudo autorizar la conexión»
(or a failed registration if it falls back to DCR). That refusal is the
expected result.

To run the full Inspector flow anyway, register a public client in Janua whose
only redirect URIs are the Inspector's loopback callbacks
(`http://localhost:6274/oauth/callback` and, for the guided debugger,
`http://localhost:6274/oauth/callback/debug`), and give its client ID to the
Inspector; a loopback-only client is inside the policy. That is an OAuth client
mutation: do it deliberately and delete the client afterwards.

## 5. End to end with Claude Code, then Claude

```bash
claude mcp add --transport http map-ctm https://map.creatumundo.mx/api/mcp
claude   # then /mcp → map-ctm → Authenticate
```

The browser opens `auth.madfam.io`: sign in (emailed link), then the Spanish
consent screen: «claude.ai quiere acceder al MAP de Crea Tu Mundo», the two
scopes, the 30-day line, and the loopback warning («una aplicación en esta
computadora»). «Permitir» returns to Claude Code, which lists the tools.

For the Director in Claude: Customize → Connectors → Add custom connector →
`https://map.creatumundo.mx/api/mcp`, OAuth client «Use Claude's published
identity». The consent screen shows «claude.ai» and no loopback warning.

## Logs to read

| Event | Meaning |
| --- | --- |
| `oauth.cimd.fetched` / `oauth.cimd.rejected` | Claude's document fetched (cached 5 min) / refused, with `reason` |
| `oauth.resource_authorize.refused` | an authorize request refused, with `error` and `reason` |
| `oauth.resource_consent.granted` / `.denied` | the person's answer |
| `oauth.resource_token.issued` | code exchange or refresh |
| `oauth.resource_refresh.reuse_detected` | a used refresh token came back; that connection's family is revoked |

If Claude says "Couldn't reach the MCP server" while the curls above work,
check the Cloudflare security events for `auth.madfam.io`: Claude calls from
`160.79.104.0/21`, and a WAF or bot challenge on that range breaks the flow.

## Rollback

`rollback-prod.yml`. Requests without `resource` behave as before, but the
discovery document changed for everyone: `code_challenge_methods_supported` is
`["S256"]` and `response_types_supported` / `response_modes_supported` list
only `code` / `query` (what `/authorize` always served), and every
authorization redirect now carries `iss`.
