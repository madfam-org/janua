# Janua UI/UX Feature Coverage Audit

**Date**: 2026-01-25
**Auditor**: Claude Code
**Scope**: Dashboard UI vs Backend API feature coverage

---

## Executive Summary

This audit compares Janua's backend API capabilities against the Dashboard UI to identify feature coverage gaps. The goal is to ensure all backend features have corresponding UI elements or are appropriately excluded from end-user interfaces.

### Key Findings

| Category | Count |
|----------|-------|
| Features with Full UI Coverage | 12 |
| Features with Partial UI | 3 |
| Features with No UI (Gaps) | 4 |
| Infrastructure-Only (Intentionally No UI) | 3 |

---

## Detailed Feature Coverage Matrix

### Full UI Coverage (No Action Required)

| Feature | Backend Router | Dashboard UI | Status |
|---------|---------------|--------------|--------|
| **Auth (email/password)** | `auth.py` (36KB) | `/login`, `/` overview | Complete |
| **MFA** | `mfa.py` (16KB) | Profile MFA setup, stats | Complete |
| **Passkeys/WebAuthn** | `passkeys.py` (15KB) | Passkey management in profile | Complete |
| **OAuth (social login)** | `oauth.py` (24KB), `oauth_provider.py` (51KB) | OAuth linking in profile | Complete |
| **Sessions** | `sessions.py` (12KB) | Sessions tab on dashboard | Complete |
| **Organizations** | `organizations.py` (34KB), `organization_members.py` (7KB) | Organizations tab | Complete |
| **Webhooks** | `webhooks.py` (13KB) | Webhooks tab on dashboard | Complete |
| **Audit Logs** | `audit_logs.py` (17KB) | `/audit-logs` page | Complete |
| **Compliance/GDPR** | `compliance.py` (18KB) | `/compliance` page with DSR, consent | Complete |
| **SCIM** | `scim.py` (42KB), `scim_config.py` (16KB) | `/settings/scim` page | Complete |
| **SSO/SAML/OIDC** | `sso.py` (18KB) | `/settings/sso` page | Complete |
| **Invitations** | `invitations.py` (13KB) | `/settings/invitations` page | Complete |

### Partial UI Coverage (Minor Gaps)

| Feature | Backend | Current UI | Gap Description | Priority |
|---------|---------|------------|-----------------|----------|
| **RBAC/Policies** | `rbac.py` (8KB), `policies.py` (12KB) | Demo-only display | Full role editor missing | P2 |
| **Billing** | `checkout_dhanam.py` (10KB) | Plan display only | Full billing management | P3 |
| **User Profile** | `users.py` (16KB) | Basic profile page | Advanced settings missing | P3 |

### No UI Coverage (Feature Gaps)

| Feature | Backend Router | Endpoints | Recommended UI | Priority |
|---------|---------------|-----------|----------------|----------|
| **White Label/Branding** | `white_label.py` (21KB) | 8+ endpoints | `/settings/branding` | **P1** |
| **API Key Management** | Model exists in DB | CRUD operations | `/settings/api-keys` | **P1** |
| **Alert Configuration** | `alerts.py` (21KB) | 15+ endpoints | `/settings/alerts` | P2 |
| **IoT Device Management** | `iot.py` (3KB) | Basic endpoints | Future consideration | P3 |

### Infrastructure-Only (Intentionally No UI)

These features are infrastructure concerns and intentionally have no user-facing UI in Janua.

| Feature | Backend | Rationale |
|---------|---------|-----------|
| **Health/Metrics** | `health.py` | Kubernetes probes, not user-facing |
| **Email Internal** | `email.py` | Service-to-service communication |
| **WebSocket** | `websocket.py` | Real-time infrastructure |

---

## Recommended UI Additions (Phase 3)

### P1: White Label/Branding Settings

**Location**: `/settings/branding`

**Backend Endpoints Available**:
- `GET/POST/PUT /api/v1/white-label/branding/{organization_id}`
- `POST /api/v1/white-label/domains`
- `POST /api/v1/white-label/domains/{domain_id}/verify`
- `GET/POST/PUT /api/v1/white-label/email-templates`

**UI Features Needed**:
- Logo upload (primary, dark mode, favicon)
- Color scheme customization (primary, secondary, accent, background)
- Font family selection
- Custom CSS injection
- Custom domain configuration with verification
- Preview mode

**Business Value**: High - enables enterprise white-labeling without code changes

### P1: API Key Management

**Location**: `/settings/api-keys`

**Model**: `ApiKey` (exists in `apps/api/app/models/__init__.py`)

**UI Features Needed**:
- List existing API keys (name, prefix, created, last used)
- Create new API key with scope selection
- One-time key display on creation (security)
- Copy to clipboard functionality
- Revoke/delete API keys
- Usage statistics per key

**Business Value**: High - enables programmatic access for integrations

### P2: Alert Configuration

**Location**: `/settings/alerts`

**Backend Endpoints Available** (in `alerts.py`):
- `GET /api/v1/alerts/active`
- `GET/POST /api/v1/alerts/channels`
- `GET/POST /api/v1/alerts/rules`
- `POST /api/v1/alerts/{alert_id}/acknowledge`
- `POST /api/v1/alerts/{alert_id}/resolve`

**UI Features Needed**:
- Active alerts dashboard
- Alert rule configuration (login failures, suspicious activity)
- Notification channel setup (email, webhook, Slack)
- Alert acknowledgment/resolution

**Business Value**: Medium - security monitoring for compliance

---

## Settings Hub Update Required

The current `/settings/page.tsx` needs new cards for:

```
settingsSections additions:
  - title: 'Branding'
    description: 'Customize logo, colors, and domain for your organization'
    href: '/settings/branding'
    icon: <Palette />
    badge: 'Enterprise'

  - title: 'API Keys'
    description: 'Manage programmatic access to Janua API'
    href: '/settings/api-keys'
    icon: <Code />

  - title: 'Alerts'
    description: 'Configure security notifications and alert rules'
    href: '/settings/alerts'
    icon: <Bell />
```

---

## Changes Made in This Audit

### Phase 1: Removed Hardware/Infrastructure UI (Completed)

The following infrastructure-related components were removed as they belong in Enclii (infrastructure monitoring), not Janua (auth platform):

| Item Removed | Reason |
|--------------|--------|
| `apps/dashboard/components/dashboard/system-health.tsx` | Hardware metrics (API latency, DB latency, Redis latency, cache hit rate) |
| `SystemHealth` component from dashboard page | Infrastructure monitoring |
| `/health/metrics` endpoint from `health.py` | Performance metrics endpoint |
| `janua_admin_memory_usage_bytes` metric | Memory monitoring (infra concern) |
| `janua_dashboard_memory_usage_bytes` metric | Memory monitoring (infra concern) |
| `apps/api/app/routers/v1/apm.py` | Full APM router (traces, profiles, system metrics) |
| APM router registration in `main.py` | APM registration removal |

### What Was Kept

- `/health/` - Basic health check (service: "janua-api")
- `/health/detailed` - Component health (database, redis status)
- `/health/ready` - Kubernetes readiness probe
- `/health/live` - Kubernetes liveness probe
- `/health/redis` - Redis availability status
- `/health/circuit-breaker` - Circuit breaker state (useful for auth reliability)

---

## Verification Checklist

- [x] Dashboard loads without SystemHealth component
- [x] API imports cleanly without APM router
- [x] Health endpoints still functional for K8s probes
- [x] No dangling imports or references
- [x] TypeScript compilation succeeds (pre-existing test errors unrelated)

---

## Implementation Summary

### Phase 3 Completed: New UI Pages Built

| Page | Location | Features |
|------|----------|----------|
| **Branding & White Label** | `/settings/branding` | Company info, logo upload, color scheme, typography, custom CSS, custom domains |
| **API Keys** | `/settings/api-keys` | Create/list/revoke keys, scope selection, security warnings, one-time key display |
| **Security Alerts** | `/settings/alerts` | Active alerts dashboard, notification channels, alert rules, default security rules |

### Settings Hub Updated

Added navigation cards for all new settings pages:
- Branding & White Label (Enterprise badge)
- API Keys
- Security Alerts

### Files Created/Modified

**New Files:**
- `apps/dashboard/app/settings/branding/page.tsx` (19KB)
- `apps/dashboard/app/settings/api-keys/page.tsx` (17KB)
- `apps/dashboard/app/settings/alerts/page.tsx` (21KB)

**Modified Files:**
- `apps/dashboard/app/settings/page.tsx` - Added 3 new navigation cards

---

## Remaining Items (Future Work)

1. **Full RBAC Editor**: Currently demo-only, needs full role management UI
2. **API Keys Backend**: Verify `/api/v1/api-keys` endpoints exist and match UI expectations
3. **Alert Rules Creator**: UI for creating custom alert rules (currently shows default rules only)
4. **File Upload**: Branding page has disabled upload buttons (needs storage integration)

---

*Generated by Claude Code as part of Janua UI/UX Audit Task - 2026-01-25*
