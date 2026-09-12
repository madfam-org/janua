# ADR-001: Authentication Flow Design

**Status**: Accepted
**Date**: 2024-01-25
**Deciders**: Janua Core Team
**Categories**: Security, Architecture

## Context

Janua needs a secure, scalable authentication system that supports:
- Email/password authentication
- OAuth/social login (Google, GitHub, Microsoft, etc.)
- Magic links (passwordless)
- Passkeys (WebAuthn/FIDO2)
- Multi-factor authentication (TOTP, SMS)
- Session management across devices
- Enterprise SSO (SAML, OIDC)

The system must balance security with user experience and support both web and mobile clients.

## Decision

We implement a **token-based authentication system** with the following characteristics:

### 1. Token Strategy: RS256 JWT with Refresh Tokens

**Access Tokens:**
- Algorithm: RS256 (RSA with SHA-256)
- Lifetime: 15 minutes
- Claims: `sub` (user_id), `org` (organization_id), `roles`, `jti` (token ID)
- Storage: Memory only (client-side)

**Refresh Tokens:**
- Algorithm: RS256
- Lifetime: 7 days (configurable)
- Stored in: Database (hashed) + httpOnly cookie
- Rotation: Required on each use (token family tracking)

```
┌──────────────────────────────────────────────────────────────────┐
│                    Authentication Flow                            │
└──────────────────────────────────────────────────────────────────┘

    ┌────────┐                    ┌────────┐                ┌─────────┐
    │ Client │                    │  API   │                │ Database│
    └───┬────┘                    └───┬────┘                └────┬────┘
        │                             │                          │
        │ POST /auth/signin           │                          │
        │ {email, password}           │                          │
        │────────────────────────────►│                          │
        │                             │ Verify credentials       │
        │                             │─────────────────────────►│
        │                             │◄─────────────────────────│
        │                             │                          │
        │                             │ Check MFA status         │
        │                             │─────────────────────────►│
        │                             │◄─────────────────────────│
        │                             │                          │
        │  [If MFA enabled]           │                          │
        │◄────────────────────────────│ 200: MFA_REQUIRED        │
        │  {mfa_challenge_id}         │                          │
        │                             │                          │
        │ POST /auth/mfa/verify       │                          │
        │ {challenge_id, code}        │                          │
        │────────────────────────────►│                          │
        │                             │ Verify TOTP              │
        │                             │                          │
        │  200: Tokens                │ Create session           │
        │◄────────────────────────────│─────────────────────────►│
        │  {access_token,             │                          │
        │   refresh_token}            │                          │
        │                             │                          │
```

### 2. Session Management

Sessions are tracked in the database for:
- Multi-device awareness
- Remote session revocation
- Security anomaly detection
- Compliance audit trails

**Session Record:**
```json
{
  "id": "sess_abc123",
  "user_id": "usr_xyz789",
  "access_token_jti": "jti_def456",
  "refresh_token_family": "fam_ghi012",
  "device_fingerprint": "fp_hash",
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "is_active": true,
  "expires_at": "2024-02-01T00:00:00Z"
}
```

### 3. Token Family Rotation

To detect refresh token theft, we implement token family tracking:

```
Initial Login:
  family_id = generate_uuid()
  refresh_token = sign({family: family_id, seq: 0})

On Refresh:
  IF token.family != session.family THEN reject
  IF token.seq < session.last_seq THEN
    # Token reuse detected - potential theft
    revoke_entire_family(token.family)
    alert_user()
  ELSE
    new_token = sign({family: token.family, seq: token.seq + 1})
    update_session(last_seq: token.seq + 1)
```

### 4. MFA Implementation

**Supported Methods:**
1. TOTP (Authenticator apps) - Primary
2. SMS OTP - Secondary
3. Backup codes - Recovery

**MFA Challenge Flow:**
1. User provides credentials
2. If MFA enabled, return `MFA_REQUIRED` with challenge ID
3. Client prompts for MFA code
4. User submits code with challenge ID
5. On success, issue tokens

### 5. OAuth Flow

Standard Authorization Code flow with PKCE for public clients:

```
1. Client → /oauth/{provider}/authorize?redirect_uri=...&state=...&code_challenge=...
2. API redirects to provider's authorization endpoint
3. User authenticates with provider
4. Provider redirects to /oauth/{provider}/callback?code=...&state=...
5. API exchanges code for provider tokens
6. API creates/links user account
7. API issues Janua tokens
8. API redirects to client's redirect_uri with tokens
```

### 6. Passkey (WebAuthn) Flow

**Registration:**
1. Client requests registration options
2. API returns WebAuthn registration challenge
3. Browser creates credential with authenticator
4. Client sends attestation to API
5. API verifies and stores public key

**Authentication:**
1. Client requests authentication options
2. API returns WebAuthn authentication challenge
3. Authenticator signs challenge
4. Client sends assertion to API
5. API verifies signature, issues tokens

## Alternatives Considered

### Alternative 1: Opaque Tokens (Rejected)

**Pros:**
- Revocable instantly
- Smaller token size

**Cons:**
- Requires database lookup on every request
- Higher latency
- Single point of failure

**Decision:** JWT with short expiry provides good balance of statelessness and security.

### Alternative 2: HS256 Algorithm (Rejected)

**Pros:**
- Simpler key management
- Faster signing

**Cons:**
- Shared secret between services
- Key rotation more complex
- Cannot provide public key for verification

**Decision:** RS256 allows services to verify tokens without knowing the signing key.

### Alternative 3: Session-only (No Tokens) (Rejected)

**Pros:**
- Simpler mental model
- Instant revocation

**Cons:**
- Requires sticky sessions or session store
- Doesn't scale horizontally well
- Poor mobile/API support

**Decision:** Token-based better supports our multi-client, microservices architecture.

## Consequences

### Positive

1. **Horizontal Scalability**: Stateless token validation allows any API instance to handle requests
2. **Cross-Service Auth**: Other services can verify tokens with public key
3. **Mobile Support**: Tokens work well for mobile apps without cookie limitations
4. **Security**: Short-lived access tokens limit exposure; refresh token rotation detects theft
5. **Flexibility**: Supports multiple auth methods (password, OAuth, passkey, MFA)

### Negative

1. **Token Revocation Delay**: Access tokens valid until expiry (mitigated by 15-minute lifetime)
2. **Complexity**: Token management more complex than simple sessions
3. **Storage**: Refresh tokens require database storage

### Mitigations

1. **Revocation**: Critical operations check token JTI against revocation list in Redis
2. **Complexity**: SDKs abstract token management from application developers
3. **Storage**: Session cleanup job removes expired records

## Security Considerations

1. **Access Token Storage**: Memory only, never localStorage
2. **Refresh Token**: httpOnly cookie with Secure and SameSite=Strict
3. **Token Signing Key**: Rotated quarterly with 2-week overlap
4. **Brute Force Protection**: Rate limiting on auth endpoints
5. **Session Anomaly Detection**: Alert on unusual login patterns

## Email lookup pools (the 013 drift, and its resolution)

**Status: RESOLVED 2026-09-06 — the code and the schema now agree. Read before
touching any email lookup, because what the agreement means has changed.**

Since janua#583 («per-tenant email uniqueness», BaaS Phase 1) the application
treats `users.email` as unique PER POOL: once per tenant, plus once in the
untenanted (staff / platform) pool. `app/services/user_lookup.py` is the single
primitive for that, and every call site must declare which pool it means.

**The database agreed late.** For three days it did not: migration
`013_per_tenant_email_uniqueness` had been written but not applied in
production, prod's `alembic_version` was `011`, and `users.email` still carried
the GLOBAL unique index `ix_users_email` from `000_init`. That drift is what
broke magic link on 2026-09-03 (below).

It was closed on **2026-09-06**: 013 and 014 were applied with the `postgres`
role (`users`, `oauth_clients` and `alembic_version` are owned by `enclii`; the
app role `janua` cannot `CREATE INDEX`), the database was stamped to
`016_org_member_app_roles`, and `scripts/alembic_converge.py --check` reported
0 divergences from the `janua-api` pod. The ledger of that reading is
[`apps/api/alembic/PROD_ALEMBIC_STATE.json`](/apps/api/alembic/PROD_ALEMBIC_STATE.json)
— the database is the truth, that file records the last time a human read it.

So `ix_users_email` is **gone** in production and the two partial unique indexes
(`uq_users_tenant_email` WHERE `tenant_id IS NOT NULL`, `uq_users_email_global`
WHERE `tenant_id IS NULL`) are **live**. One address may now legitimately hold a
row in the platform pool and a row in each of N tenant pools.

### What that drift cost (2026-09-03)

`POST /api/v1/auth/magic-link` looked users up in the untenanted pool only. The
internal provisioning API writes users **with** a `tenant_id` (CTM staff,
provisioned by crea-map, which sends `tenant_id` in its provision body), so the
lookup missed them; the handler's "not found → create" branch then ran and its
INSERT collided with the still-global `ix_users_email`:

```
POST /api/v1/auth/magic-link → IntegrityError → 503
```

The requesting product showed «revisa tu correo» and no link was ever sent.
21 users were affected (example: request_id `47ef96c7-1b29-4048-910e-3e6335a3771f`,
2026-09-03T15:51:54Z). The operator's stopgap moved those 21 rows to the
untenanted pool (`tenant_id = NULL`, recorded in `ops_untenant_2026_09_03`),
which unblocks those users but not anyone provisioned with a `tenant_id` after
that.

### The bridge

`resolve_user_by_email_across_pools()` in `user_lookup.py` is the documented
bridge for **bare-email entry points only** — those that have no tenant context
to declare (magic link, password reset, internal lifecycle by address). Before
013 landed this resolution was **exact**, because at most one row could hold the
address. **It is not exact any more.** It is a resolution:

- it takes a `preferred_tenant_id` — the organization of the OAuth client that
  owns the request's redirect host — consulted first, and that preference is now
  load-bearing rather than anticipatory;
- with several matches and no preference it **raises**
  `AmbiguousEmailAcrossPools` rather than returning an arbitrary row; the
  handler answers **400** (**409** on the internal provisioning surface), never
  a silent cross-tenant login.

**That refusal is a reachable production branch as of 2026-09-06.** It was
unreachable while the address stayed globally unique. Nothing in the database
prevents the collision now, so it must be observable rather than merely
correct: every site that turns the exception into a response emits
`auth.ambiguous_email_across_pools` (`app/services/user_lookup.py`), and the
alert plus its triage steps live in
[the incident playbook](/docs/internal/operations/INCIDENT_RESPONSE_PLAYBOOK.md#januaambiguousemailacrosspools).

Every caller that *does* know its tenant (OAuth end-user flows, SCIM, SSO,
admin, provisioning) must keep using pool-scoped `get_user_by_email()`.

### Entry points audited 2026-09-03

| Entry point | Pool | Why |
| --- | --- | --- |
| `POST /auth/magic-link` | untenanted, then across-pools bridge | Has a create branch; the bug above |
| `_dispatch_password_reset` | untenanted, then across-pools bridge | Same silent miss; no create branch, enumeration-safe |
| `POST /auth/signin` | untenanted only | No create branch; authenticates by password hash, which provisioning never sets |
| hosted `login-form` | untenanted only | Same reasoning as `/signin` |

### Follow-ups for the owner (not decided here)

1. ~~**Apply migration 013 in production, or retire it.**~~ **DONE 2026-09-06**
   — applied and stamped by the operator, prod converged at
   `016_org_member_app_roles`; ledger refreshed in
   [`PROD_ALEMBIC_STATE.json`](/apps/api/alembic/PROD_ALEMBIC_STATE.json). Note
   the deploy pipeline **promotes images and runs no alembic**, which is why
   this was a deliberate operator action and why the next one will be too.
2. ~~**Should org STAFF carry `users.tenant_id` at all?**~~ **DECIDED by the
   owner 2026-09-03 17:00Z: no.** Under Phase-1 semantics `tenant_id` marks an
   *end-user pool*; organization staff belong in the untenanted (platform) pool
   with their org membership expressed by `organization_members`. The internal
   provisioning API now separates the two concerns — `organization_id` names the
   organization, `identity_pool` (default `"platform"`) selects the pool — and
   STAFF no longer get a `users.tenant_id`. Implemented in this PR's second
   commit; see the internal-users section of the
   [endpoints reference](/apps/api/docs/api/endpoints-reference.md#identity-pool-vs-organization).
3. **Reconcile the `ops_untenant_2026_09_03` stopgap** with whichever of the
   above is chosen.

## Related Documentation

- [Rate Limiting](/docs/api/RATE_LIMITING.md)
- [Security Guidelines](/docs/security/SECURITY.md)
- [Database Schema](./DATABASE_SCHEMA.md)
- [Multi-tenancy ADR](./ADR-003_MULTITENANCY.md)
