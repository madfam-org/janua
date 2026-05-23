# @janua/cli

> Provision OAuth clients for MADFAM consumer apps and administer Janua

**Version:** 0.2.0 | **Status:** Production (provisioning), Development (admin UX)

## Consumer repos (CI bootstrap)

1. Add `janua.client.yaml` (see `examples/consumer-bootstrap/`).
2. Store `JANUA_INTERNAL_API_KEY` in Enclii/Vault or CI secrets.
3. Run:

```bash
janua provision plan -f janua.client.yaml
janua provision apply -f janua.client.yaml
janua provision verify -f janua.client.yaml
```

Uses `POST /api/v1/oauth/clients/register` (idempotent by client name or pinned `spec.client_id`).

Full pipeline and ops guide: [docs/PP_3B_STAGING_PIPELINE.md](../../docs/PP_3B_STAGING_PIPELINE.md).

## Install

```bash
npm config set @janua:registry https://npm.madfam.io
npm install -g @janua/cli
```

Publish: tag `cli-v0.2.0` on the Janua repository (see `.github/workflows/publish-sdks.yml`).

## Commands

### Provisioning (internal API key)

| Command | Description |
|---------|-------------|
| `janua provision apply` | Register clients from manifest |
| `janua provision plan` | Detect create vs drift |
| `janua provision verify` | Fail if remote drifts from manifest |
| `janua provision export-env` | Print shell exports |

### Administration (Bearer token)

```bash
janua admin auth login
janua admin clients list
janua admin users list
```

Legacy top-level aliases (`janua auth login`, `janua apps list`) remain for compatibility.

## Manifest

```yaml
apiVersion: janua.dev/v1
kind: OAuthClient
metadata:
  name: my-service-web
spec:
  audience: my-service-api
  client_id: jnc_optionalPinnedId012345678   # optional — auto-generated if omitted
  redirect_uris:
    - https://app.example.com/api/auth/callback
  allowed_scopes: [openid, profile, email]
  grant_types: [authorization_code, refresh_token]
  is_confidential: true
```

Multi-client file: `kind: OAuthClientList` with `clients: [...]`.

## Environment

| Variable | Use |
|----------|-----|
| `JANUA_INTERNAL_API_KEY` | Provision commands |
| `JANUA_API_URL` | API base (default production) |
| `JANUA_TOKEN` | Admin Bearer override |

## Development

```bash
cd packages/cli
pnpm install
pnpm test
pnpm build
node dist/index.js provision plan -f ../../examples/consumer-bootstrap/janua.client.yaml
```
