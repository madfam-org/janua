# Janua GA claim matrix

Status: active claim-control document
Last updated: 2026-05-25
Owner: Janua product/platform

Use this matrix before publishing sales copy, pricing pages, enterprise docs,
or migration commitments. A capability is commercial-GA supported only when it
has production code, hosted proof, operator runbook coverage, and support
ownership.

## Claim status values

| Status | Meaning |
| --- | --- |
| Supported | May be described as available for commercial GA when linked evidence remains current. |
| Beta | May be offered to selected customers with explicit limitations. |
| Internal-only | Available for MADFAM operations but not an external product commitment. |
| Roadmap | Must not be sold as available. |
| Needs proof | Code or docs may exist, but hosted evidence is missing. Treat as GA-blocking until proved. |

## GA-safe claims

| Capability | Claim status | Public wording | Evidence required before GA |
| --- | --- | --- | --- |
| Hosted auth health | Supported | Hosted Janua runtime exposes health endpoints. | Scheduled health synthetic evidence. |
| OIDC discovery | Supported | Janua exposes OpenID Connect discovery for configured issuers. | `.well-known/openid-configuration` synthetic. |
| JWKS | Supported | Janua exposes public signing keys for token verification. | JWKS synthetic with key-count evidence. |
| Enclii SSO dependency | Internal-only | Janua powers MADFAM/Enclii SSO. | Enclii dependency runbook and incident escalation. |
| Client-credentials token exchange | Needs proof | Available after synthetic client is provisioned and strict synthetic mode passes. | `hosted-auth-synthetics.yml` strict token proof. |
| User auth-code login | Needs proof | Browser login flow is supported only after hosted synthetic/user journey evidence is filed. | Auth-code synthetic or Playwright journey with non-secret test user. |
| Session refresh/logout | Needs proof | Supported after hosted session synthetic proof. | Refresh/logout synthetic evidence. |
| Admin org/user/app operations | Needs proof | Admin operations are supported after hosted admin smoke proof. | Tenant onboarding smoke without DB access. |
| RBAC | Needs proof | Role-based access is beta unless tenant isolation and role tests are current. | Test matrix and hosted admin proof. |
| Audit logs | Needs proof | Audit logs are beta unless retention/export proof exists. | Audit event query and retention runbook. |
| SAML SSO | Roadmap | Enterprise SAML is roadmap/beta only unless a customer-specific proof exists. | SAML IdP integration proof and support runbook. |
| SCIM provisioning | Roadmap | SCIM is roadmap only until implemented, tested, and monitored. | SCIM create/update/deactivate synthetic. |
| Compliance exports | Roadmap | Compliance exports are roadmap unless export/delete evidence exists. | Data export/delete proof and retention policy. |
| Auth0 migration | Beta | Migration assistance is available after dry-run proof for the customer scope. | Import/export dry-run with rollback and integrity evidence. |
| SOC2 Type II | Roadmap | SOC2 Type II readiness is a future compliance program, not a current certification. | Auditor scope and observation window. |
| HIPAA/BAA | Roadmap | HIPAA/BAA is not available unless legal/compliance explicitly approves. | Signed compliance packet and support procedures. |
| 99.99% SLA | Roadmap | Do not claim 99.99% SLA until uptime, support, and legal commitments exist. | 30-day evidence, support schedule, and approved SLA. |

## Publication rules

| Rule | Action |
| --- | --- |
| A page says "production ready" without scope | Replace with the exact supported scope and link this matrix. |
| A page lists SAML, SCIM, SOC2, HIPAA, or 99.99% SLA as available | Downgrade to roadmap unless evidence exists. |
| A feature has code but no hosted synthetic | Mark `Needs proof`, not `Supported`. |
| A feature is used only by MADFAM | Mark `Internal-only` unless external support is explicitly funded and staffed. |
| A customer asks for migration | Run a dry-run and file evidence before committing dates. |

## Evidence locations

| Evidence | Location |
| --- | --- |
| Hosted auth synthetics | `.github/workflows/hosted-auth-synthetics.yml` |
| Local synthetic script | `scripts/hosted-auth-synthetic.sh` |
| Commercial GA plan | `docs/internal/operations/COMMERCIAL_GA_REMEDIATION_PLAN.md` |
| Production readiness history | `docs/deployment/PRODUCTION_READINESS_REPORT.md` |
| Enterprise gap history | `docs/enterprise/IMPLEMENTATION_GAP_ANALYSIS.md` |

