# Janua commercial GA remediation plan

Status: active remediation plan
Last updated: 2026-05-25
Owner: Janua platform/product ops

This document is the current Janua GA truth surface. Older enterprise
roadmaps contain useful history but must not be treated as current supported
state unless the capability is proved by production code, hosted synthetics,
operator runbooks, and support commitments.

## GA definition

Janua is commercially GA only when a paying customer can depend on it for
production authentication without founder intervention. The minimum GA package
is hosted Janua for MADFAM and first external customers, with clearly scoped
auth capabilities, monitored uptime, security contacts, migration guidance,
and support boundaries.

## Current state

| Area | State | Gap |
| --- | --- | --- |
| Hosted runtime | `api.janua.dev/health` returns healthy and `auth.madfam.io` serves OIDC discovery. | Need recurring synthetic proof for OIDC, JWKS, token, session, and admin flows. |
| Enclii dependency | Enclii uses Janua SSO in production. | Need dependency SLO, incident escalation, and break-glass auth runbook. |
| Documentation | Docs contain both production-ready claims and enterprise roadmap claims. | Need shipped-vs-roadmap reconciliation before commercial outreach. |
| Enterprise features | SSO/OIDC and admin concepts are documented. | Need proof matrix for SAML, SCIM, RBAC, audit logs, compliance exports, and admin portal scope. |
| Migration | Auth0/cloud migration docs exist. | Need a tested migration dry-run with rollback and data export evidence. |
| Support/security | Security contact appears in docs. | Need public support path, response targets, vulnerability intake, and status integration. |

## ROI remediation order

| Priority | Workstream | Implementation | Exit gate |
| --- | --- | --- | --- |
| P0 | Truth reconciliation | Mark every public enterprise claim as `supported`, `beta`, `internal-only`, or `roadmap`. Update README, docs index, enterprise docs, and pricing/production-ready copy. | No public page claims an unsupported capability. |
| P0 | Hosted auth synthetics | `scripts/hosted-auth-synthetic.sh` and `.github/workflows/hosted-auth-synthetics.yml` probe health, OIDC discovery, JWKS, and optional client-credentials token exchange. Add a browser/user auth-code probe after the synthetic client and test user are provisioned. | Synthetic evidence runs on schedule and blocks release promotion on failure. |
| P0 | Enclii dependency hardening | Document Janua outage modes, Enclii impact, rollback/break-glass path, key rotation, and alert escalation. | Enclii incident runbook includes Janua dependency and tested fallback steps. |
| P0 | Security baseline | Prove password hashing posture, rate limiting, session cookie/security headers, CORS, token TTLs, key rotation, and audit logging for auth-sensitive endpoints. | Security checklist has current production evidence and zero critical open issues. |
| P1 | Admin portal minimum | Verify org, user, app/client, redirect URI, roles, audit events, and key management in the hosted admin flow. | An operator can onboard and support a customer tenant without DB access. |
| P1 | Enterprise scope | Define commercial packages for OIDC, SAML, RBAC, audit logs, exports, SCIM, custom domains, and support SLAs. | Sales/pricing copy only exposes packages with implementation evidence. |
| P1 | Migration proof | Run Auth0 or sample tenant import/export dry-run, including rollback and data integrity checks. | Migration guide links to a current proof artifact. |
| P1 | Observability and support | Add dashboard/status coverage for login success rate, token errors, latency, key rotation, and dependency failures. | Support can triage auth incidents from metrics/logs without raw DB access. |
| P2 | Compliance readiness | Build SOC2 evidence map, data retention/export/delete proof, and vendor/security packet. | Enterprise security review packet is shareable. |

## Commercial GA gates

| Gate | Requirement |
| --- | --- |
| Runtime | Public health, OIDC discovery, and JWKS endpoints pass scheduled synthetics for 30 days. |
| Auth correctness | Login, callback, token exchange, refresh/session, logout, and key rotation are tested against hosted Janua. |
| Tenant isolation | Org/user/app operations are covered by tests and admin smoke proof. |
| Claim hygiene | Docs and website separate shipped, beta, internal-only, and roadmap capabilities. |
| Security | No critical/high unactioned auth vulnerabilities; rate limits and audit logs are active. |
| Migration | At least one dry-run import/export has integrity and rollback evidence. |
| Support | Status page, support path, security disclosure path, and incident escalation are published. |

## Immediate implementation queue

1. Use `docs/enterprise/GA_CLAIM_MATRIX.md` as the current claim control and update public docs against it.
2. Provision `JANUA_SYNTHETIC_CLIENT_ID` and `JANUA_SYNTHETIC_CLIENT_SECRET`, then enable strict token mode for `.github/workflows/hosted-auth-synthetics.yml`.
3. Add Enclii dependency runbook covering Janua outage, key rotation, and rollback.
4. Reconcile enterprise docs so unsupported SAML/SCIM/compliance claims are roadmap-only.
5. Run a migration dry-run and file evidence before selling migration assistance.

## Non-blocking for scoped GA

| Capability | Why it is post-GA unless sold explicitly |
| --- | --- |
| SOC2 Type II | Requires observation window and auditor involvement. |
| Full SCIM automation | Enterprise valuable, but can be scoped as roadmap/beta until implemented and tested. |
| HIPAA/BAA | Legal/compliance commitment beyond current auth core. |
| Multi-region active-active | Availability upgrade, not required for initial scoped GA if SLA language is honest. |
| White-label enterprise portals | Commercial packaging option, not auth correctness prerequisite. |
