# Cross-Repository Audit Report - December 2025

## Audit Date: 2025-12-06
## Auditor: Claude Code

---

## 1. DRIFT ANALYSIS

### 1.1 Git Commit Drift (LOCAL vs PRODUCTION)

| Repo | Local HEAD | Production HEAD | Status |
|------|------------|-----------------|--------|
| **janua** | `b657a88` (Fix alembic async) | `77bbd5b` (OAuth2 Client API) | 🔴 **DRIFTED** |
| **enclii** | `c8ef8c5` (Janua service specs) | `25bfd87` (UI CORS support) | 🔴 **DRIFTED** |
| **solarpunk-foundry** | N/A | Not deployed | ✅ OK |

### 1.2 Docker Image Drift

Production images all use `localhost:5000/*:latest` tags:
- janua-api: Rebuilt 26 minutes ago
- janua-admin/dashboard/docs/website: Built 24 hours ago  
- switchyard-api/ui: Built 24 hours ago
- enclii-landing: Built ~1 hour ago

**Issue**: Images are tagged `latest` without version/commit SHA tracking.

### 1.3 K8s Deployment Status

**janua namespace** (5 deployments, all healthy):
- janua-api: 1/1 Running (13m old)
- janua-admin: 1/1 Running (23h)
- janua-dashboard: 1/1 Running (23h)
- janua-docs: 1/1 Running (23h)
- janua-website: 1/1 Running (23h)

**enclii namespace** (3 deployments, all healthy):
- enclii-landing: 1/1 Running (77m)
- switchyard-api: 1/1 Running (23h)
- switchyard-ui: 1/1 Running (23h)

**monitoring namespace** (exists but content not verified)

---

## 2. INFRASTRUCTURE STATUS

### 2.1 Server Health
- **OS**: Ubuntu 24.04 LTS
- **ZFS Pool**: `rpool` - ONLINE, no errors, mirror configuration
- **Disk Usage**: ~1% on all ZFS datasets (plenty of headroom)
- **Datasets**: postgres, builds, registry, assets - all properly configured

### 2.2 Services Running
- **k3s**: Active (lightweight kubernetes)
- **Docker**: Active  
- **Cloudflare Tunnels**: 3 tunnels active
  - `cloudflared-janua` → janua-prod
  - `cloudflared-enclii` → enclii-prod
  - `cloudflared` → foundry-prod

### 2.3 Network/Security
- UFW status not actively configured (empty rules)
- All traffic routes through Cloudflare Tunnel (zero-trust)

---

## 3. DOCUMENTATION GAPS

### 3.1 Documentation Volume by Repo

| Repo | Markdown Files | Key Areas |
|------|----------------|-----------|
| **janua** | 383 files | API, SDKs, architecture, deployment |
| **enclii** | 94 files | Audits, architecture, production guides |
| **solarpunk-foundry** | 49 files | Port allocation, dogfooding, ecosystem |

### 3.2 Missing Documentation

**Critical Gaps:**
1. **Production Runbooks**
   - No incident response procedures
   - No disaster recovery documentation
   - No backup verification procedures

2. **Deployment Documentation**
   - No CI/CD pipeline docs for current k8s deployments
   - No image versioning/tagging strategy documented
   - No rollback procedures for k8s deployments

3. **Cross-Repo Integration**
   - Janua ↔ Enclii OIDC integration not documented in either repo
   - No single source of truth for production URLs/domains
   - No service dependency map

4. **Operations**
   - No monitoring/alerting configuration docs
   - No on-call procedures
   - No SLA definitions

### 3.3 Inconsistencies Found

1. **Port Documentation**: INFRASTRUCTURE.md shows 4300-4399 for Dhanam, 4400-4499 for Avala, but PORT_ALLOCATION.md in solarpunk-foundry shows different assignments
2. **Canonical Paths**: Fixed today - consolidated to `/opt/solarpunk/`
3. **Authentication Mode**: Enclii docs mention "Janua integration ready" but no actual integration exists yet

---

## 4. FIXES APPLIED

### 4.1 Directory Structure (Fixed)
- Removed orphaned `/opt/janua/` directory
- Consolidated canonical path to `/opt/solarpunk/{janua,enclii}`
- Updated docker-compose.prod.yml volume mounts
- Created Serena memory `production_directory_structure_canonical`

### 4.2 Documentation Updated
- Updated `deployment/enclii/DEPLOYMENT.md` with correct paths

---

## 5. RECOMMENDED ACTIONS

### 5.1 Immediate (High Priority)

1. **Sync Local Repos to Production**
   ```bash
   # On production server
   cd /opt/solarpunk/janua && git pull origin main
   cd /opt/solarpunk/enclii && git pull origin main
   ```

2. **Implement Image Versioning**
   - Tag images with git SHA: `janua-api:abc123`
   - Add commit SHA to k8s deployment annotations

3. **Create Production Runbooks**
   - Incident response playbook
   - Backup/restore procedures
   - Rollback procedures

### 5.2 Medium Priority

1. **Complete Janua ↔ Enclii OIDC Integration**
   - Deploy OAuth Provider endpoints (created but not deployed)
   - Configure Enclii to use Janua as OIDC provider

2. **Consolidate Port Documentation**
   - Single source of truth in solarpunk-foundry
   - Remove duplicated port definitions

3. **Add Monitoring/Alerting**
   - Configure Prometheus alerts
   - Setup PagerDuty/Slack notifications

### 5.3 Low Priority

1. **Documentation Cleanup**
   - Archive old/stale docs
   - Standardize doc structure across repos
   - Add last-updated timestamps

2. **Create Service Dependency Map**
   - Visual diagram of service relationships
   - Document API contracts between services

---

## 6. SUMMARY

| Area | Status | Action Required |
|------|--------|-----------------|
| Git Drift | 🔴 DRIFTED | Sync repos to prod |
| Infrastructure | ✅ HEALTHY | None |
| Directory Structure | ✅ FIXED | None |
| Documentation | 🟡 GAPS | Create runbooks |
| Image Versioning | 🔴 MISSING | Implement tagging |
| OIDC Integration | 🟡 PARTIAL | Deploy endpoints |

**Overall Health**: 🟡 **NEEDS ATTENTION**
- Infrastructure is stable
- Code drift needs sync
- Documentation gaps need filling
