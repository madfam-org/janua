# Consumer OAuth bootstrap (Janua CLI)

Template for MADFAM consumer repositories provisioning a Janua OAuth client in CI.

## Files

- `janua.client.yaml` — declarative client spec (committed)
- `.env.example` — documents runtime variables after provisioning

## Local / CI

```bash
# Install (after @janua/cli is published to npm.madfam.io)
npm install -g @janua/cli

# Plan (no writes)
janua provision plan -f janua.client.yaml \
  --api-url "${JANUA_API_URL:-https://auth.madfam.io}"

# Apply (idempotent register)
janua provision apply -f janua.client.yaml \
  --api-url "${JANUA_API_URL:-https://auth.madfam.io}" \
  --secrets-file .janua-client.env

# Verify manifest matches Janua
janua provision verify -f janua.client.yaml
```

Set `JANUA_INTERNAL_API_KEY` from Enclii/Vault (never commit).

## GitHub Actions

```yaml
- name: Provision Janua OAuth client
  run: npx @janua/cli@0.2.0 provision apply -f janua.client.yaml --quiet
  env:
    JANUA_API_URL: https://auth.madfam.io
    JANUA_INTERNAL_API_KEY: ${{ secrets.JANUA_INTERNAL_API_KEY }}
```

Store `JANUA_CLIENT_SECRET` in your secret manager when the step returns 201 (first run only).
