# MADFAM v0.1.0 Stability Sprint - SWE Agent Handoff

**Date**: December 9, 2025
**Sprint Goal**: Achieve full local and production stability for MADFAM ecosystem
**Handoff From**: Previous session (Phase 1 complete)
**Priority**: Continue remaining phases with evidence-based Playwright browser testing

---

## Current State Summary

### Completed (Phase 1)

| Task | Status | Evidence |
|------|--------|----------|
| Janua API container | ✅ Healthy | `docker ps` shows healthy, port 4100 |
| Janua Dashboard (4101) | ✅ Verified | Playwright screenshot: login form renders |
| Janua Docs (4103) | ✅ Verified | Playwright screenshot: full docs site |
| Enclii API (4200) | ✅ Verified | Health endpoint returns v0.1.0 |
| Docker images pushed | ✅ Complete | `ghcr.io/madfam-io/janua-api:v0.1.0`, `ghcr.io/madfam-io/enclii-api:v0.1.0` |

### Blocked (Known Issues)

| Task | Status | Blocker |
|------|--------|---------|
| Janua Admin (4102) | ⚠️ Build Error | `@janua/feature-flags` - npm.madfam.io not configured |
| Janua Website (4104) | ⚠️ Build Error | `@janua/typescript-sdk` - npm.madfam.io not configured |

### Infrastructure Running

```bash
# Currently running containers
docker ps
# NAMES            STATUS                   PORTS
# janua-api-test   Up (healthy)             0.0.0.0:4100->4100/tcp
# janua-postgres   Up 12 hours (healthy)    0.0.0.0:5432->5432/tcp
# janua-redis      Up 12 hours (healthy)    0.0.0.0:6379->6379/tcp
```

---

## Remaining Tasks

### Phase 2: npm.madfam.io Private Registry Setup

**Objective**: Unblock Admin (4102) and Website (4104) frontend apps

**Options** (choose one):
1. **Verdaccio** (self-hosted npm registry)
2. **GitHub Packages** (use existing ghcr.io auth)
3. **Temporary workaround**: Publish packages to npm public with @madfam scope

**Required packages to publish**:
- `@janua/feature-flags` (from `packages/feature-flags/`)
- `@janua/typescript-sdk` (from `packages/typescript-sdk/`)

**Verification after setup**:
```bash
# Test registry access
npm view @janua/feature-flags --registry=https://npm.madfam.io

# Install in apps
cd janua/apps/admin && pnpm install
cd janua/apps/website && pnpm install

# Playwright browser test
# Navigate to localhost:4102 - should render admin dashboard
# Navigate to localhost:4104 - should render marketing website
```

### Phase 3: Production K3s Deployment

**Production Server**: `foundry-core` (95.217.198.239) via `ssh.madfam.io`

**SSH Access**:
```bash
# Authenticate via Cloudflare Access
cloudflared access login ssh.madfam.io
ssh root@ssh.madfam.io
```

**Deployment Steps**:

1. **Pull latest images on server**:
```bash
ssh root@ssh.madfam.io
docker pull ghcr.io/madfam-io/janua-api:v0.1.0
docker pull ghcr.io/madfam-io/enclii-api:v0.1.0
```

2. **Apply K8s manifests**:
```bash
kubectl apply -f /path/to/janua-k8s-manifests/
kubectl apply -f /path/to/enclii-k8s-manifests/
```

3. **Verify deployment**:
```bash
kubectl get pods -n janua
kubectl get pods -n enclii
kubectl logs -n janua deployment/janua-api
```

### Phase 4: Production Health Verification (Playwright)

**Required Playwright browser tests for production**:

```javascript
// Test 1: Janua API Production
await page.goto('https://api.janua.dev/health');
// Expected: {"status":"healthy","version":"0.1.0"}
await page.screenshot({ path: 'prod-janua-api-health.png' });

// Test 2: Janua OIDC Configuration
await page.goto('https://api.janua.dev/.well-known/openid-configuration');
// Expected: Valid OIDC discovery document
await page.screenshot({ path: 'prod-janua-oidc-config.png' });

// Test 3: Janua Dashboard Production
await page.goto('https://app.janua.dev');
// Expected: Login page renders
await page.screenshot({ path: 'prod-janua-dashboard.png' });

// Test 4: Janua Docs Production
await page.goto('https://docs.janua.dev');
// Expected: Documentation site renders
await page.screenshot({ path: 'prod-janua-docs.png' });

// Test 5: Enclii API Production (when deployed)
await page.goto('https://api.enclii.dev/health');
// Expected: {"service":"switchyard-api","status":"healthy","version":"0.1.0"}
await page.screenshot({ path: 'prod-enclii-api-health.png' });
```

---

## Technical Context

### Port Allocation (PORT_ALLOCATION.md)

| Service | Port | Domain |
|---------|------|--------|
| Janua API | 4100 | api.janua.dev |
| Janua Dashboard | 4101 | app.janua.dev |
| Janua Admin | 4102 | admin.janua.dev |
| Janua Docs | 4103 | docs.janua.dev |
| Janua Website | 4104 | janua.dev |
| Enclii API | 4200 | api.enclii.dev |
| Enclii UI | 4201 | app.enclii.dev |

### Key Configuration Values

**Janua API Container (working command)**:
```bash
docker run -d --name janua-api-test \
  -p 4100:4100 \
  -e DATABASE_URL="postgresql://janua:janua_dev@host.docker.internal:5432/janua_db" \
  -e REDIS_URL="redis://host.docker.internal:6379/0" \
  -e JWT_SECRET_KEY="your-secret-key" \
  -e ADMIN_BOOTSTRAP_PASSWORD="YS9V9CK!qmR2s&" \
  -e ENABLE_BETA_ENDPOINTS="false" \
  -e EMAIL_PROVIDER="resend" \
  -e RESEND_API_KEY="re_placeholder" \
  ghcr.io/madfam-io/janua-api:v0.1.0
```

**Note for macOS**: Use `-p` port mapping (not `--network host`) and `host.docker.internal` for localhost services.

### Key Files

| File | Purpose |
|------|---------|
| `/janua/apps/api/claudedocs/v0.1.0-ecosystem-audit.md` | Full audit document with all findings |
| `/janua/CLAUDE.md` | Janua project documentation |
| `/enclii/CLAUDE.md` | Enclii project documentation |
| `/.playwright-mcp/*.png` | Captured screenshots from browser tests |

---

## Playwright MCP Usage

**Available Tools**:
- `mcp__playwright__browser_navigate` - Navigate to URL
- `mcp__playwright__browser_snapshot` - Get accessibility tree
- `mcp__playwright__browser_take_screenshot` - Capture screenshot
- `mcp__playwright__browser_click` - Click elements
- `mcp__playwright__browser_type` - Type text
- `mcp__playwright__browser_close` - Close browser

**Example Test Sequence**:
```
1. browser_navigate → URL
2. browser_snapshot → Verify page content
3. browser_take_screenshot → Capture evidence
4. Repeat for all endpoints
```

---

## Success Criteria

### Local Stability
- [ ] All 6 Janua apps running (API, Dashboard, Admin, Docs, Website, Demo)
- [ ] Enclii API running
- [ ] All health endpoints return 200
- [ ] Playwright screenshots captured for each app

### Production Stability
- [ ] K3s deployment successful
- [ ] Production health endpoints verified
- [ ] Cloudflare tunnels routing correctly
- [ ] Playwright production tests passing

---

## Agent Instructions

1. **Read first**:
   - `/janua/apps/api/claudedocs/v0.1.0-ecosystem-audit.md`
   - `/janua/CLAUDE.md`
   - `/enclii/CLAUDE.md`

2. **Check current state**:
   ```bash
   docker ps
   lsof -i :4100 -i :4101 -i :4102 -i :4103 -i :4104 -i :4200
   ```

3. **Execute phases sequentially**:
   - Phase 2: npm.madfam.io setup (or workaround)
   - Phase 3: K3s production deployment
   - Phase 4: Production Playwright verification

4. **Document everything**:
   - Update `v0.1.0-ecosystem-audit.md` with results
   - Save all Playwright screenshots
   - Note any blockers or issues

5. **Evidence requirements**:
   - Screenshot every endpoint tested
   - Log all health check responses
   - Document deployment commands used

---

*Generated: December 9, 2025 | MADFAM v0.1.0 Stability Sprint*
