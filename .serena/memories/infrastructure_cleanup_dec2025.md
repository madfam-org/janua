# Infrastructure Cleanup - December 2025

## Summary
Completely removed all references to 3rd party DevOps services (Railway, Vercel) from the codebase. Janua now exclusively uses self-hosted infrastructure on Hetzner bare metal via MADFAM's Enclii DevOps solution.

## Changes Made

### Files Removed
- `apps/api/railway.json`
- `apps/website/vercel.json`
- `config/vercel.json`
- `config/railway.json`
- `docs/deployment/VERCEL_SETUP.md`
- `docs/internal/operations/RAILWAY_DEPLOYMENT.md`
- `.github/workflows/website-deploy.yml` (Vercel-based)
- `apps/dashboard/.github/workflows/deploy.yml` (Vercel-based)

### Files Updated
1. **`.github/workflows/deploy.yml`** - Replaced Vercel workflow with Docker/Enclii-based CI/CD
   - Builds Docker images for api, dashboard, website, docs
   - Pushes to GitHub Container Registry (ghcr.io)
   - Deploys via Enclii webhook
   
2. **`.env.example`** - Removed Railway/Vercel references, added MADFAM-specific config

3. **`.env.production.example`** - Complete rewrite for Hetzner/Enclii infrastructure
   - Added `INTERNAL_API_URL=http://janua-api:8000` (critical for container-to-container comms)
   - Self-hosted PostgreSQL and Redis
   - Cloudflare services integration
   - R2 storage configuration

4. **`deployment/production/docker-compose.production.yml`** - Added INTERNAL_API_URL to dashboard service

5. **`docs/deployment/DEPLOYMENT.md`** - Complete rewrite for Hetzner/Enclii deployment
   - Architecture overview with Cloudflare Tunnel
   - MADFAM port allocation (4100-4199 block)
   - Container-to-container communication explanation
   - CI/CD pipeline documentation
   - Troubleshooting section (including login 500 fix)

6. **`docs/DEPLOYMENT.md`** - Replaced Railway/Render sections with Hetzner/Enclii

7. **`apps/api/docs/project-docs/DEPLOYMENT.md`** - Updated architecture diagram to remove Railway

## Critical Configuration

### INTERNAL_API_URL
The `INTERNAL_API_URL` environment variable is critical for production:
- Next.js dashboard API routes proxy to FastAPI backend
- In Docker containers, `localhost` doesn't work - containers are isolated
- Must use Docker network hostname: `http://janua-api:8000`

```yaml
janua-dashboard:
  environment:
    - INTERNAL_API_URL=http://janua-api:8000  # Runtime, internal
    - NEXT_PUBLIC_API_URL=https://api.janua.dev  # Build-time, external
```

### Port Allocation (MADFAM Standard)
| Service | Port | Domain |
|---------|------|--------|
| API | 4100 | api.janua.dev |
| Dashboard | 4101 | app.janua.dev |
| Admin | 4102 | admin.janua.dev |
| Docs | 4103 | docs.janua.dev |
| Website | 4104 | janua.dev |

## Issue Fixed
- **Login 500 Error**: Missing `INTERNAL_API_URL` caused dashboard to try `localhost:8000` inside container
- **Solution**: Added `INTERNAL_API_URL=http://janua-api:8000` to docker-compose.production.yml

## Infrastructure Stack
- **Server**: Hetzner bare metal
- **Containers**: Docker Compose
- **Ingress**: Cloudflare Tunnel (zero-trust)
- **Registry**: GitHub Container Registry (ghcr.io)
- **CI/CD**: GitHub Actions → Enclii webhook
- **Storage**: Cloudflare R2
- **CDN/WAF**: Cloudflare

## Additional Files Updated (Session 2)
- `scripts/production-readiness-check.sh` - Updated to check for Docker/Enclii configs instead of Railway/Vercel
- `apps/api/scripts/deploy.sh` - Replaced Vercel webhook with Docker/Enclii deployment
- `apps/api/scripts/deploy-vercel.sh` - **DELETED**
- `apps/website/deploy.sh` - Replaced Vercel with Docker/Enclii deployment