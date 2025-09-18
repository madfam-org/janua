# Plinto — SOFTWARE\_SPEC.md

**Company:** Plinto (plinto.dev) by **Aureo Labs** (aureolabs.dev), a **MADFAM** company (madfam.io)
**Doc status:** Draft v1.1 (Updated for single-domain + Vercel/Railway/Cloudflare)
**Owners:** Platform Eng @ Aureo Labs
**Audience:** Engineering, Security, Product, GTM
**Review cadence:** Monthly until GA

---

## 0) Executive Summary

**Plinto** is the **secure substrate** for identity: a unifying layer that verifies users at the edge, centralizes policy, and remains under customer control. We will operate **entirely on the single domain `plinto.dev`** during this stage, and our infra stack is **Vercel + Railway + Cloudflare (R2 + CDN/WAF + Turnstile)**.

**What we are building:**

* **Plinto Core** — identity, sessions, orgs/tenants, roles, policy evaluation, audit, webhooks.
* **Plinto Edge** — low-latency verification at the edge (Vercel/Cloudflare), JWKS distribution.
* **Plinto Admin** — dashboard for users/orgs/roles, audits, incidents, billing hooks.
* **Plinto SDKs** — first-class developer kits (Next.js/React/Node, later Vue, Go, Python).
* **Plinto Enterprise** — SSO (SAML/OIDC), SCIM, residency, advanced audit, SLAs.

**North Star:**

> *Edge-fast, privacy-first, enterprise-ready identity that you can actually own.*

---

## 1) Goals, Non‑Goals, Success Criteria

### 1.1 Goals

1. Unify MADFAM product auth behind one adapter and platform, **served from plinto.dev**.
2. Deliver **passkeys/WebAuthn**, email/password, social logins, sessions, org/team RBAC, webhooks.
3. Provide **edge verification** (p95 < 50ms) with global JWKS cache and per-tenant keys.
4. Ship **enterprise features**: SAML/OIDC SSO, SCIM, audit trails, data residency controls.
5. Achieve **SLOs**: 99.95% uptime; p95 token issuance < 120ms; verify < 50ms at edge.

### 1.2 Non‑Goals (v1)

* No passwordless SMS; email + WebAuthn suffice for v1.
* No on-prem installer at GA; focus on managed multi-region SaaS first.
* No separate marketing domain (e.g., .io/.one). **Everything lives on `plinto.dev`.**

### 1.3 Success metrics

* ≥ 92% signup→verify conversion (consumer) / ≥ 80% (B2B with SSO).
* Passkey adoption ≥ 25% by day-30 per tenant.
* 0 critical auth incidents across 2 consecutive quarters pre-GA.
* Time-to-implement (Next.js) ≤ 90 minutes from empty repo.

---

## 2) System Overview & Architecture

### 2.1 Component map

* **Auth API (Plinto Core)** — FastAPI service (Python) with optional **SuperTokens** core for sessions/email-password & **OPA** for policy; Redis for sessions/ratelimits; Postgres for identity data; Celery/RQ workers for webhooks/email.
* **Edge adapters (Plinto Edge)** — Vercel Middleware + Cloudflare Workers libraries for token verification using cached JWKS.
* **Admin UI (Plinto Admin)** — Next.js app (Vercel) with RBAC-gated ops and audit explorer.
* **SDKs (Plinto SDKs)** — `@plinto/nextjs`, `@plinto/react-sdk`, `@plinto/edge`, `@plinto/node`, `@plinto/core`.
* **Enterprise connectors** — SAML/OIDC providers, SCIM server.
* **Observability** — OpenTelemetry traces, metrics, structured logs; dashboards & alerts.

### 2.2 Deployment topology (v1)

* **Railway** — Plinto Core services (API at `/api`), **Postgres** (primary), **Redis** (caches/ratelimits), background workers.
* **Vercel** — Hosts the **single Next.js site** on `https://plinto.dev` (marketing/docs/admin UI), plus **Edge Middleware** for our own properties and reference apps.
* **Cloudflare** — Fronts `plinto.dev` for WAF/CDN; **R2** for audit/exports; **Turnstile** on risky flows; caches **JWKS** globally.
* **Email** — SES or SendGrid with warmed IPs; domain: `mail.plinto.dev` (DNS managed via Cloudflare).

```
Browser/Client → Cloudflare (WAF/CDN/Turnstile) → Vercel (Next.js: /, /docs, /admin) → Railway (Core API mounted at /api)
                                          ↘ Edge verify (Vercel/Cloudflare) ← JWKS cached at Cloudflare from /.well-known
```

### 2.3 Single-domain routing plan

* **Public site/docs**: `https://plinto.dev/` and `https://plinto.dev/docs` (Next.js on Vercel).
* **Admin**: `https://plinto.dev/admin` (Next.js pages gated by RBAC).
* **API**: `https://plinto.dev/api/v1/...` (proxied via Vercel to Railway Core).
* **Discovery**: `https://plinto.dev/.well-known/jwks.json` and `/openid-configuration` (Cloudflare-cached).

### 2.4 Protocols & standards

* **WebAuthn / FIDO2** (passkeys), **OIDC** and **OAuth 2.1**, **SAML 2.0** (enterprise), **SCIM 2.0**, **JWT (JWS/JWE)**, **PKCE**, **CORS**, **mTLS** (optional for service-to-service), **JWK/JWKS**.

### 2.5 Tenancy & regions

* **Logical multi-tenancy** in v1 with strong isolation (tenant\_id everywhere).
* **Per-tenant signing keys** with region pinning (US/EU); future option: per-tenant DB.

---

## 3) Security, Privacy, Compliance

### 3.1 Key management & token strategy

* **KMS-backed** key material (per region).
* **Rotations**: scheduled 90d + emergency rollover; dual-pubkey (`kid`) overlap; automated JWKS purge at CDN.
* **Tokens**: short-lived access (≤15m), refresh rotation & reuse detection; JTI blacklist in Redis; optional **DPoP** for APIs.

### 3.2 Threat model (STRIDE highlights) & mitigations

* **Spoofing**: WebAuthn, email-link signed with exp & nonce, IP/device signals, **Turnstile** on signup/reset.
* **Tampering**: JWS + `aud/iss/nbf/exp` checks, deterministic claim sets, schema validation.
* **Repudiation**: append-only **audit\_events** with request\_id, hash chain per user; signed webhook deliveries.
* **Information disclosure**: consented scopes; PII minimization; at-rest encryption; field-level encryption for secrets.
* **DoS**: per-tenant & per-IP ratelimits; circuit breakers; queue backpressure; **Cloudflare WAF**.
* **Elevation of privilege**: least-privilege admin roles; OPA policies; 4-eyes on role mutation.

### 3.3 Privacy & compliance

* **GDPR**, **LFPDPPP (MX)**, **CCPA** readiness: DSR endpoints (export/delete), data maps, DPAs/SCCs, consent receipts; retention policy for audits.
* **Data residency**: choose region at tenant creation; audit/docs reflect region.

---

## 4) Data Model (v1)

> Storage: **Postgres** (OLTP) + **R2** (long-retention audit/export). Caching: **Redis**.

### 4.1 Core tables (simplified)

| Table         | Key fields                                                                    | Notes                                                  |
| ------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------ |
| tenants       | tenant\_id (UUID), slug, region, plan                                         | Region pinning, quotas.                                |
| users         | user\_id, tenant\_id, email (unique per tenant), name, status                 | Email normalized/lc; status: active/suspended/deleted. |
| credentials   | cred\_id, user\_id, type (password, webauthn), hash/public\_key, created\_at  | Argon2id/bcrypt; WebAuthn public keys.                 |
| passkeys      | passkey\_id, user\_id, aaguid, cred\_id, counter, device\_label               | WebAuthn-specific.                                     |
| orgs          | org\_id, tenant\_id, name, slug, owner\_user\_id                              | Multi-tenant organizations.                            |
| memberships   | id, org\_id, user\_id, role\_id, created\_at                                  | Index `(org_id,user_id)` unique.                       |
| roles         | role\_id, tenant\_id, name, description                                       | Predefined + custom.                                   |
| policies      | policy\_id, tenant\_id, kind (RBAC/ABAC), version, rules (JSON)               | OPA/Cedar-compatible JSON.                             |
| sessions      | session\_id, user\_id, device\_id, refresh\_jti, ip, user\_agent, expires\_at | For rotation & revoke.                                 |
| jwk\_keys     | kid, tenant\_id (nullable for global), alg, public\_jwk, status               | `status`: active, next, retired.                       |
| audit\_events | event\_id, tenant\_id, user\_id, type, ip, ua, metadata (JSON), ts            | Append-only; streamed to R2.                           |
| webhooks      | hook\_id, tenant\_id, url, secret, events\[], active                          | Signed with HMAC; retries + DLQ.                       |

### 4.2 Indices & constraints (must)

* `UNIQUE(email, tenant_id)` on `users`.
* `UNIQUE(org_id, user_id)` on `memberships`.
* `CHECK` role invariants: exactly one `owner` per org.
* Row Level Security (RLS) where feasible for admin scopes.

---

## 5) API Surface (v1)

**Base URL:** `https://plinto.dev/api`
**Auth:** Bearer tokens (JWT) for app→API; HttpOnly cookies (SameSite=None; Secure) for browser sessions.
**Versioning:** `/api/v1/...`
**Idempotency:** `Idempotency-Key` header on mutating endpoints.

### 5.1 Identity & session endpoints

* `POST /api/v1/auth/signup` — email+password or email+passkey bootstrap.
* `POST /api/v1/auth/signin` — password or WebAuthn assertion; issues session/refresh.
* `POST /api/v1/auth/signout` — revokes session; rotates tokens.
* `POST /api/v1/auth/passkeys/register` — begin/finish ceremonies.
* `POST /api/v1/auth/password/reset` — request + complete with signed token.
* `GET /api/v1/sessions/verify` — token introspection (also library local verify).

### 5.2 Orgs & roles

* `POST /api/v1/orgs` | `GET /api/v1/orgs/:id` | `GET /api/v1/orgs`
* `POST /api/v1/orgs/:id/members` | `DELETE /api/v1/orgs/:id/members/:userId`
* `PUT /api/v1/orgs/:id/role` — change owner (two-admin confirmation).
* `GET /api/v1/roles` | `POST /api/v1/roles` | `PUT /api/v1/roles/:id`

### 5.3 Policy (via OPA adapter)

* `POST /api/v1/policy/evaluate` — subject/action/resource; returns `allow:boolean`, reasons\[].
* `POST /api/v1/policy` — upsert policy bundle; dry-run mode supported.

### 5.4 Webhooks & events

* `POST /api/v1/webhooks` — register; events: `user.created`, `login.success`, `mfa.enabled`, `token.revoked`, `org.invited`, etc.
* Delivery: HMAC `X-Plinto-Signature`, retries with backoff; **DLQ** exposed via Admin.

### 5.5 Discovery & federation

* `GET /.well-known/jwks.json` — rotated keys (per-tenant kid support).
* `GET /.well-known/openid-configuration` — OIDC metadata.
* SSO endpoints for SAML/OIDC (Enterprise).

### 5.6 Error model

```json
{
  "error": {
    "code": "invalid_credentials",
    "message": "Email or password incorrect",
    "request_id": "req_abc123",
    "hint": "Check WebAuthn timer"
  }
}
```

---

## 6) Edge Verification Contract (Plinto Edge)

* **Libraries:** `@plinto/edge` for Vercel/Cloudflare.
* **Inputs:** `Authorization: Bearer <JWT>` or HttpOnly cookies `plinto_session`.
* **Behavior:**

  1. Load JWKS from `https://plinto.dev/.well-known/jwks.json` (CDN cached; ETag).
  2. Verify signature + `iss/aud/exp/nbf`; check `jti` reuse.
  3. Hydrate `request.auth = { userId, orgId, tenantId, claims }`.
  4. Optional **OPA-check** for route-level policy.
* **Performance:** Target p95 < 50ms at edge for hot cache.

---

## 7) SDKs (Developer Experience)

### 7.1 Packages & APIs

* `@plinto/nextjs` — AuthProvider, middleware, server helpers (Route Handlers).
* `@plinto/react-sdk` — UI widgets: `<SignIn/>`, `<SignUp/>`, `<UserButton/>`, `<OrgSwitcher/>`, `<PasskeyPrompt/>`.
* `@plinto/edge` — `verify(request, {audience}) -> Claims`.
* `@plinto/node` — `createToken`, `verifyToken`, `rotateKeys` (admin).
* `@plinto/core` — types, errors, codecs.

### 7.2 Copy‑paste starts

* **Next.js (App Router)**: 3 files (middleware.ts, auth.ts, layout.tsx).
* **CLI**: `npx create-plinto-app` scaffolds env, pages, API routes, and example policies.

---

## 8) Admin (Ops & Compliance) — `/admin`

* **User & Org Management** — search, suspend/reactivate, role changes (with 2PA).
* **Audit Explorer** — filter by actor, IP, event type; export to CSV/JSON (R2-backed).
* **Webhooks Console** — deliveries, retry, DLQ purges.
* **Security** — key status/rotation, session invalidation, IP allow/block lists.
* **Compliance** — DSR queue (export/delete), consent ledger, region change workflow.

---

## 9) Observability & SLOs

* **Metrics** (per tenant & global): `auth_success_rate`, `issuance_latency_ms`, `verify_latency_ms`, `token_reuse_rate`, `signup_conversion`, `email_bounce_rate`, `ratelimit_hits`, `errors_by_code`.
* **Tracing**: OpenTelemetry, propagate `request_id` to webhooks.
* **Logging**: JSON logs with PII redaction; 30d hot retention; long-term in **R2**.
* **SLOs**: Uptime 99.95%; RPO ≤ 5m; RTO ≤ 30m; page within 5m for P0.

---

## 10) Rate Limiting & Abuse

* **Per-IP and per-tenant** token buckets in Redis.
* **Turnstile** on signup/reset and anomalous login.
* **Anomaly signals**: velocity, IP reputation, device mismatch → step-up (WebAuthn/email link).

---

## 11) Email & Deliverability

* SPF/DKIM/DMARC aligned for `plinto.dev`; warmed IPs; dedicated bounce/complaint handling.
* Templates localized (EN/ES), with strict link expiry (≤15m), single-use nonces.

---

## 12) Migration Strategy (from Clerk/others)

* **Parallel run** with feature flag (`PLINTO_ENABLED`).
* **Dual sessions**: accept both cookies for 2 weeks; new logins mint Plinto tokens + legacy cookie for rollback.
* **Passwords**: assume **forced reset**; friction-minimized UX.
* **Socials**: re-consent flows; account linking by verified email + proof.
* **Data**: import users/orgs via admin loader; preserve external IDs in `external_ref` fields.

---

## 13) Runbooks (must-have before GA)

* **Key rotation** — generate next, publish, flip `kid`, purge CDN, retire old after TTL; rollback path documented.
* **Incident response** — triage matrix, comms templates, status page updates; for credential stuffing, enable global CAP; for compromise, rotate secrets + invalidate sessions by scope.
* **DDoS/abuse** — WAF rulesets; fail-closed paths; emergency ratelimit overrides.
* **Email outage** — switch provider; degrade to passkeys-only + admin recovery flow.

---

## 14) Performance & Load Targets

* **Auth issue p95** < 120ms @ 2k RPS; **verify p95** < 50ms (edge hot).
* **Cold start**: API under 500ms after scale-to-zero (if enabled).
* **DB**: p95 queries < 20ms for critical paths; Redis ops < 5ms.

---

## 15) Testing & Quality

* **Unit** (≥85% coverage on Core), **Contract tests** for SDKs, **Chaos** (kill Redis/API) with graceful degradation, **Load** (k6) to 2x expected peak, **Security** (SAST/DAST), third‑party **pen‑test** before GA.

---

## 16) Packaging & Releases

* **Semver** for SDKs; API uses additive changes in v1 with deprecations.
* **Release train** bi-weekly; change logs; migration notes; canary tenants.

---

## 17) Pricing/Packaging Signals (GTM input)

* **Community**: Core + Edge, single region, basic audit; fair-use limits.
* **Pro**: multi-region, webhooks, custom roles, higher limits.
* **Enterprise**: SSO/SCIM, residency, dedicated support, SLA.
* Clear **“Own your data & keys”** narrative; comparison pages vs incumbents.

---

## 18) Timeline & Gates

* **Gate 0 (2 weeks):** passkeys + email, sessions, JWKS rotation demo; edge verify on Vercel.
* **Gate 1 (MVP, month 2):** replace auth in Forge Sight; SLO met in shadow; no P0 for 2 weeks.
* **Gate 2 (Parity, month 4):** socials, orgs/RBAC, webhooks, audit v1; pen-test fixes closed.
* **Gate 3 (Enterprise, month 6):** SAML/OIDC, SCIM, residency, status page; 90d clean ops.
* **Gate 4 (GA, month 7+):** docs, support runbooks, billing, SLAs.

---

## 19) Risks & Mitigations

* **SSO complexity** → use proven libs, extensive IdP matrix tests; enterprise pilot first.
* **Deliverability** → warm IPs, Turnstile, step-up challenges, signed links.
* **Scope creep** → feature gates; Ports & Adapters; strict ADRs.
* **Ops load** → maximize managed services (Railway/Vercel/Cloudflare), automate runbooks; grow SRE as usage scales.

---

## 20) Open Questions

* Cedar vs OPA for long-term policy language?
* Bring-your-own-KMS at tenant level (Enterprise)?
* Graph-based authorization ("Telar") in v2—how exposed?

---

## Appendix A — Example Types (TS)

```ts
export type Claims = {
  sub: string; // userId
  tid: string; // tenantId
  oid?: string; // orgId
  roles?: string[];
  iat: number; exp: number; nbf?: number; jti: string; aud: string; iss: string;
};
```

## Appendix B — Required ENV (Core)

```
PLINTO_ENV=prod
DATABASE_URL=postgres://...
REDIS_URL=redis://...
EMAIL_PROVIDER=ses|sendgrid
TURNSTILE_SECRET=...
KMS_KEY_ARN=...
JWT_AUDIENCE=plinto.dev
JWT_ISSUER=https://plinto.dev
COOKIE_DOMAIN=plinto.dev
```

## Appendix C — Domain & Paths (single-domain)

* **Host:** `plinto.dev` (only).
* **Paths:** `/` (site), `/docs` (docs), `/admin` (admin UI), `/api/v1/...` (API), `/.well-known/*` (JWKS/OIDC), `/status` (status page optional).
* **CDN:** Cloudflare in front of entire domain; JWKS heavily cached with purge on key rotation.
* **Storage:** Cloudflare **R2** for audit logs & exports.
