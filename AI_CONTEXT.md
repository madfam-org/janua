# AI_CONTEXT.md - Janua Identity Provider

## Architecture
- **Stack**: FastAPI (Python 3.11+) + Next.js 15.1.6 + PostgreSQL + Redis
- **Pattern**: Hexagonal architecture, edge-native event-driven
- **Auth**: RS256 JWT, OAuth 2.0/OIDC, SAML, WebAuthn/Passkeys

## God Files (Critical Paths)
| Purpose | Path |
|---------|------|
| API Entry | `apps/api/app/main.py` |
| Config | `apps/api/app/config.py` |
| Auth Service | `apps/api/app/services/auth_service.py` |
| JWT Service | `apps/api/app/services/jwt_service.py` |
| OAuth Service | `apps/api/app/services/oauth_service.py` |
| K8s Manifests | `k8s/base/deployments/` |
| Enclii Config | `.enclii.yml` |
| CI/CD | `.github/workflows/` |

## Port Allocation
- 4100: API (api.janua.dev / auth.madfam.io)
- 4101: Dashboard (app.janua.dev)
- 4102: Admin (admin.janua.dev)
- 4103: Docs (docs.janua.dev)
- 4104: Website (janua.dev)

## The Tripod
- **Consumes**: Enclii for deployment orchestration
- **Publishes**: @janua/* SDKs to npm.madfam.io
- **Does NOT use**: @madfam/ui (uses internal @janua/ui)
- **Provides**: Authentication for Enclii and all tenant apps

## Agent Directives
1. ALWAYS run `pytest` before committing Python changes
2. ALWAYS run `pnpm typecheck` before committing TypeScript
3. USE conventional commits (feat:, fix:, docs:, chore:)
4. READ this file at session start
5. **The "Proof of Life" Standard:** No deployment, refactor, or fix is considered "Complete" until you have successfully `curl`ed the public endpoint (e.g., `https://api.janua.dev/health`) and received a `200 OK` (or `401 Unauthorized` for protected routes).
   - **Principle:** "Kubernetes Applied" is NOT "Done." "Endpoint Reachable" is "Done."
   - **Failure Protocol:** If the curl fails (502/503/Connection Refused), you MUST diagnose the logs immediately. Do not report success.

## Secret Management Protocols (Safe-Patch Mode)
**High-Value Targets**: You are PERMITTED to edit `.env` and `.env.local` files, but MUST adhere to:

1. **Backup First**: Before ANY modification to a secret file:
   ```bash
   cp .env .env.bak  # Create immediate restore point
   ```

2. **Patch, Don't Purge**: NEVER overwrite with `> .env` (deletes existing keys). ALWAYS use:
   ```bash
   sed -i '' 's/OLD_VALUE/NEW_VALUE/' .env  # Modify specific key
   echo "NEW_KEY=value" >> .env             # Append new key
   ```

3. **Placeholder Ban**: FORBIDDEN from writing values containing:
   - `your_key_here`
   - `placeholder`
   - `example`
   - `xxx` or `TODO`
   into active config files (`.env`, `.env.local`)

## Testing Commands
```bash
# Python API tests
cd apps/api && pytest

# TypeScript validation
pnpm typecheck
pnpm lint

# Full validation
pnpm build
```

## Local Development
```bash
# Start shared infrastructure
~/labspace/madfam start

# Or start Janua only
docker compose -f deployment/docker-compose.yml up -d
```
