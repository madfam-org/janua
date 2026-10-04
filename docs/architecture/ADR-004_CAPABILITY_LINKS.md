# ADR-004: Capability Links as a Janua Primitive

**Status**: Proposed (groundwork merged behind the internal API; no app migrated)
**Date**: 2026-08-31
**Deciders**: MADFAM ecosystem / Janua
**Categories**: Architecture, Identity, Authorization, Security

---

## Context

### The problem: the same token, hand-rolled four times

A recurring shape has appeared independently across the MADFAM ecosystem:

> Give **one specific person** — who may have no account — a **link** that grants
> **a named set of powers** over **one specific thing**, for **a bounded time**,
> and let an operator **take it back**.

A client's customer completing an intake form. A guest subscribing to a calendar. A
counterparty opening a data room. Each app built its own table, its own token
generator, its own expiry check, and its own revocation semantics. A survey of
the four existing implementations (2026-08-31) found that **they do not agree on
the security properties**, and the disagreements are not deliberate:

| | client portal intake link | kalya `FeedToken` | kalya `Booking.manageToken` | janua `guest_invites` |
|---|---|---|---|---|
| Hashed at rest | SHA-256 | SHA-256 | **No — plaintext** | **No — plaintext** |
| Entropy | 256 bit | 256 bit | 192 bit | 256 bit |
| TTL | 30 d (mandatory) | **None** | None | **Nullable = never** |
| Single-use | No (by design) | No | No | No (`max_uses=0` = ∞) |
| Revocation | `revocada_en` | `revoked_at` | **None** | `revoked` bool, no timestamp |
| Scope | one subject (as PK) | subject *or* host | one booking | **org only, no subject** |
| Failure message | Generic | Generic | Generic 404 | **Granular + public probe** |

Two of the four store live credentials in plaintext. Two can mint links that
never expire. One has no revocation at all. Every new app that needs this shape
today starts this table over and re-decides all seven columns, and the evidence
is that the decisions come out differently each time.

### What is genuinely good in the prior art, and stays

This ADR is **not** a criticism of the client portal. Its intake link gets the
security core right — hash at rest, shown once, mandatory TTL, soft revocation,
and a genuinely generic refusal chosen precisely because distinguishing
"expired" from "never existed" is an enumeration oracle over sensitive personal
records. kalya's `FeedToken` independently reached the same conclusions and adds
a tenant column and a label. **Those two implementations are the design input
for this ADR, not the thing it replaces.**

### Prior art, honestly assessed

**1. A vCTO client portal — its app-local intake-link table** (in the client's
own repo). SHA-256 at rest, 256-bit token, 30-day TTL,
multi-use *by design* (a long multi-part form with document uploads —
single-use would force manual re-issuance on every attempt), soft
revoke, uniformly generic public refusal.

*Tradeoffs, stated plainly:* `usuario_id` is the **primary key**, so exactly one
live link can exist per subject, ever — no separate revocable links for two
recipients. Re-minting is an upsert that **clears `revocada_en`**, so re-issuing a
link erases the record that a previous one was revoked; there is no history of
prior links at all. No use counter, no `last_used_at`.

*Verdict:* **the client portal's app-local table is fine and stays.** It is in production,
it is correct on the properties that matter most, and its 30-day multi-use
policy is a domain-workflow decision janua has no business overriding. This
ADR does not migrate it.

**2. kalya — two primitives that disagree with each other.** `FeedToken`
(`prisma/schema.prisma:522`) is the strongest prior art: separate table,
`tenant_id`, nullable `subject_id`/`host_id`, SHA-256, soft revoke,
`last_used_at`, and an explicit written argument for a bare hash over a KDF.
Its one gap is **no `expires_at` at all** — correct for a polled calendar
subscription, but it means an unrevoked leak is permanent.
`Booking.manageToken` in the *same codebase* is the counterexample: 192-bit,
**stored plaintext**, no TTL, no revocation. Its mitigations are real (token in
the POST body, `no-referrer`, cancel link uses a URL *fragment*) but they are
transport hygiene compensating for an at-rest weakness.

**3. nauta — the notable negative result.** Nauta has **no** bearer-token portal
link and **no** NDA signing link. `WorkspaceInvitation`
(`packages/db/prisma/schema.prisma:774`) has **no token column**: the credential
is a *Janua-verified email address*, and `redeemInvitation` takes
`emailVerified` as a required argument specifically so a future caller "has to
lie to skip it." NDA acceptance is an *evidence* table, not a link. The closest
token is a **stateless HMAC** upload intent (15-minute expiry, domain-separated
key, `timingSafeEqual`) which by construction has no table and therefore **no
revocation** and is replayable inside its window — a tradeoff its own code
states.

*Tradeoff to name:* nauta's identity-bound model has no bearer leak surface at
all, because nothing bearer-shaped travels. But it **requires the recipient to
have a Janua account.** That constraint is exactly what a capability link
exists to relax. Where an app *can* use nauta's model, it should — an
identity-bound invitation is strictly stronger than any bearer token.

**4. janua's own `guest_invites` — the near-miss that must be reconciled.**
This is the most important finding, because janua already has an adjacent table
(`app/models/__init__.py:690`, migration `004`). It is **not** the same
primitive and cannot be quietly reused:

- The **plaintext token is the stored column**, is the lookup key, and is
  **returned in every admin list response** alongside a full invite URL.
- `expires_at` is **nullable, defaulting to NULL = never expires**.
- `max_uses = 0` means **unlimited**, and is the default.
- Revocation is a bare boolean with **no timestamp** — "when was this closed?"
  is unanswerable.
- It has **no subject column**. Its only narrowing is a nullable `room_id`
  varchar. It grants a guest-role JWT scoped to an *organization*.
- `GET /validate/{token}` is **public and unauthenticated** and returns the
  organization's name, with granular messages distinguishing invalid from
  expired from exhausted — an enumeration and org-disclosure oracle.

> **Separately flagged, not addressed by this ADR:** the survey found that
> `guest_invites.py`'s create/list/revoke endpoints depend only on
> `get_current_user`. The module docstring claims `require_admin()` is enforced,
> but `require_admin` is not imported or used, and no check ties `current_user`
> to the `org_id` in the path. If that reading is correct it is a cross-tenant
> authorization defect independent of this work and **should be triaged on its
> own merits, not bundled into this change.**

### Why janua, and why now

Three of the four implementations live in apps that already delegate identity to
janua. The fourth is janua's own. When the *next* app needs this shape, the
choices are: hand-roll a fifth table and re-decide the seven columns, or call a
primitive that has already decided them once, correctly, with tests.

The value janua adds is **not** storage. It is that the security properties stop
being a per-app judgement call: hash-at-rest, mandatory bounded TTL, soft
revocation with a timestamp, uniform refusal, and an audit trail become
non-optional because they are the only behaviour the API offers.

---

## Decision

Janua gains a **capability link** primitive behind the internal service API.

A capability link is a **tenant-scoped, subject-opaque, scoped, expiring bearer
grant** with four operations: **create**, **resolve**, **revoke**, **rotate**.

### The three properties that define it

**1. The plaintext token is stored nowhere.** Janua persists only
`sha256(token)`. The plaintext is returned exactly once — in the create and
rotate response bodies — and janua cannot reproduce it. A dump of
`capability_links` yields no usable credential. A lost token is *rotated*, never
recovered.

**2. The subject and scopes are opaque.** `subject_type`, `subject_id` and every
scope string are free strings that janua stores, indexes, and hands back
verbatim. Janua **never parses them**, never joins on them, and holds no table
describing them. `"usuario"` / `"booking"` / `"engagement"` are meaningless to
janua and must stay that way — that opacity is the only reason one primitive can
serve a client portal's roster, a booking, and a data room without janua learning three
domain models.

**3. Rows are never deleted.** Revoke and rotate set `revoked_at`; the row
survives. There is no delete endpoint and must not be one — the same reasoning
that keeps a purge out of `internal_users.py`. Destroying the row destroys the
evidence that access was granted, to whom, and over what. This is where the
design **departs from the client portal**, whose re-mint clears the revocation record.

### Why a bare SHA-256 and not bcrypt/argon2

The token is 256 bits of `secrets.token_urlsafe(32)`, not a human-chosen
password. There is no dictionary to attack, so a slow KDF's work factor buys
nothing against this input while taxing every resolve. An unsalted hash is also
**deterministic**, which is what lets resolve find the row with one indexed
lookup instead of scanning every row. This matches what the client portal and kalya's
`FeedToken` independently concluded, and is standard practice for API keys.

---

## API contract

All endpoints are internal-only, under `/api/v1/internal/capability-links`, and
carry `X-Internal-API-Key` via the **same `verify_internal_api_key` dependency**
as `internal_users.py`. This is not a new or weaker trust boundary — it is the
trust janua already extends to sibling apps.

The dependency is a deliberately **swappable seam**: it is declared once per
route and no handler body depends on the shared key, so the ratified move to
janua-issued service tokens is a dependency swap, not a rewrite.

### Shared auth failures (every endpoint)

| Condition | Status |
|---|---|
| `X-Internal-API-Key` header absent | `422` |
| Header present, wrong value | `401` |
| `settings.INTERNAL_API_KEY` unset server-side | `503` |

Auth is evaluated **before** any token lookup, so an unauthenticated caller
cannot use this surface to probe whether a token exists.

### `POST /api/v1/internal/capability-links` → `201`

```jsonc
{
  "tenant_id": "uuid",          // REQUIRED, never defaulted
  "subject_type": "usuario",     // opaque, 1..64
  "subject_id": "usuario-123",   // opaque, 1..255
  "scopes": ["expediente:read"], // opaque strings, 1..32 items, no dupes/blanks
  "ttl_seconds": 2592000,        // 60 .. 7776000 (90 d)
  "use_mode": "multi_use",       // "single_use" | "multi_use"
  "metadata": {}                 // caller context; NEVER secret material
}
```

Response — **the only shape that ever carries the plaintext**:

```jsonc
{
  "id": "uuid", "tenant_id": "uuid",
  "subject_type": "usuario", "subject_id": "usuario-123",
  "scopes": ["expediente:read"], "use_mode": "multi_use",
  "token": "<plaintext, shown once, never again>",
  "expires_at": "...", "created_at": "..."
}
```

**Deliberately NOT idempotent**, unlike `internal_users.provision`. Two identical
calls mint two independent links with different tokens, because collapsing them
would mean either returning a token janua no longer holds (impossible) or
re-issuing one grant to two recipients who could then never be revoked apart.

`tenant_id` is **required and never defaulted**, for the same reason as on the
internal user schemas: it selects the isolation boundary, and a defaulted value
would let a caller that forgot the field mint a grant in the wrong organization —
a cross-tenant authority bug that reads as success.

`422` on: empty/duplicate/blank scopes, TTL outside `[60s, 90d]`, missing
`tenant_id`.

### `POST /api/v1/internal/capability-links/resolve` → `200`

```jsonc
{ "token": "<plaintext>", "tenant_id": "uuid" }  // tenant_id OPTIONAL
```

Returns `{id, tenant_id, subject_type, subject_id, scopes, use_mode,
expires_at, use_count, metadata}` — and **no token**.

`tenant_id`, when supplied, is an **additional constraint and never a
relaxation**: a resolve naming a tenant must match the link's tenant, so an app
serving one tenant cannot be tricked into honouring another tenant's token.
Callers that omit it must check the returned `tenant_id` themselves.

**POST, not GET, deliberately.** The token is the request body. A GET would put
live credential material in the URL, where it lands in access logs, proxy logs,
referrers, and browser history — the exact leak path this design exists to close.
(kalya's booking flow reaches the same conclusion by different means, putting its
token in a URL *fragment*.)

**Every failure is one identical `404`:**

```json
{"error": {"code": "HTTP_ERROR", "message": "Invalid or expired capability link", ...}}
```

Unknown token, expired, revoked, single-use already spent, and tenant mismatch
all return the same status, code, and message. The server log distinguishes them;
the client cannot. This is the client portal's discipline, generalized — and it is the
direct opposite of `guest_invites`' granular public messages.

**Use counting burns only on success.** A refused resolve never advances
`use_count`, so a holder of a revoked or expired token cannot pre-spend a
single-use grant they are not entitled to use.

### `POST /api/v1/internal/capability-links/{id}/revoke` → `200`

Body `{tenant_id, reason?}`. Idempotent: always `200` when the link exists in the
caller's tenant, with `changed` reporting whether *this* call revoked it. `404`
when there is no such link **in that tenant** — which is also the answer for a
link that exists in another tenant, so revoke cannot probe for foreign link ids.

The tenant predicate is in the SQL `WHERE`, not an `if` after the fetch: a
post-fetch check is one early return away from being skipped, and the consequence
is cross-tenant revocation of another org's grant.

### `POST /api/v1/internal/capability-links/{id}/rotate` → `201`

Body `{tenant_id, ttl_seconds?}`. Mints a **new row** with the same subject,
scopes and use mode; revokes the old row with reason `rotated` and sets
`replaced_by_id` to the successor — both **in one transaction**, so there is no
window where both tokens are live and none where neither is.

Omitted `ttl_seconds` inherits the original link's **full original lifetime
measured from now**, not its remaining time — otherwise rotating a
nearly-expired link would produce a replacement dead on arrival, which is the
very case rotation exists to serve.

**Rotating a revoked or expired link is `409`, not a silent re-issue.** Rotation
must never resurrect authority an operator already withdrew; that would make
revocation something a caller can undo. Mint a new link instead — the deliberate
act belongs in the caller's code.

---

## Storage schema

`capability_links` (migration `014_capability_links`, additive, re-entrant):

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `tenant_id` | uuid NOT NULL, indexed | **No FK** — janua has no `tenants` table; `users.tenant_id` is itself a bare indexed UUID |
| `subject_type` | varchar(64) NOT NULL | Opaque |
| `subject_id` | varchar(255) NOT NULL | Opaque |
| `scopes` | jsonb NOT NULL `'[]'` | Array. **Not** a delimited string |
| `token_hash` | varchar(64) NOT NULL | SHA-256 hex. **The plaintext is never stored** |
| `use_mode` | varchar(16) NOT NULL `'multi_use'` | |
| `expires_at` | timestamp **NOT NULL** | Mandatory — no immortal links |
| `use_count` | int NOT NULL `0` | |
| `last_used_at` | timestamp NULL | |
| `revoked_at` | timestamp NULL | Retire, never erase |
| `revoked_reason` | varchar(64) NULL | `revoked` vs `rotated` |
| `replaced_by_id` | uuid NULL | Rotation chain of custody |
| `link_metadata` | jsonb NOT NULL `'{}'` | Never secret material |
| `created_at` / `created_by` | timestamp / varchar(64) | |

Indexes: `uq_capability_links_token_hash` (UNIQUE — resolve's single lookup rides
it), `ix_capability_links_tenant_id`, `ix_capability_links_tenant_subject`
`(tenant_id, subject_type, subject_id)`.

Two schema choices worth defending explicitly:

- **`expires_at` is NOT NULL.** Both `guest_invites` and kalya's `FeedToken`
  allow a link that never expires; every leak of one is permanent. Requiring a
  bounded lifetime — with a 90-day ceiling — makes an unbounded grant
  unrepresentable rather than merely discouraged.
- **`scopes` is JSONB, not a delimited string.** A scope containing the delimiter
  would split into two, and here that would *fabricate authority* rather than
  lose it — the failure direction that matters.

---

## Threat model

**Enumeration.** Tokens are 256-bit CSPRNG output; guessing is not a live threat.
The realistic vector is using *responses* to confirm that a guessed or
half-remembered token once existed. Mitigation: every resolve failure returns an
identical `(status, code, message)`; auth is checked before lookup; revoke and
rotate answer `404` for foreign-tenant ids exactly as for absent ones; there is no
public validate endpoint. A regression test asserts all five failure modes are
byte-identical modulo the per-request envelope fields.

**Timing.** Resolve does one indexed hash lookup plus an `hmac.compare_digest`.
The not-found path performs a same-length dummy comparison. Honestly: the DB
lookup, not the comparison, dominates any timing signal, so this is **hardening,
not a proof of constant time.** The real defence is the 256-bit token and the
identical refusal; the constant-time comparison is defence in depth.

**Token leakage in transcripts and logs.** The single largest practical risk,
and the reason for several rules above. The plaintext appears in exactly two
response bodies and **nowhere else**: not in a log line (structured logs carry
`link_id`), not in an audit `details` blob (a token written to the audit trail
would outlive the link and defeat hash-at-rest entirely), not in an error
message, and never in a URL. Links travel in email and chat; treat every issued
link as potentially forwarded — the client portal documents recipients forwarding theirs
over WhatsApp.

**Rotation guidance.** Rotate on any suspicion of forwarding or leak, on
recipient change, and routinely for long-lived grants. Rotation is the *only*
recovery path for a lost token, since janua cannot reproduce it. Prefer the
shortest workable TTL over a long TTL plus vigilance.

**Compromise of the internal API key.** This surface is exactly as strong as
`X-Internal-API-Key` — a shared secret held by every sibling app. A holder can
mint a grant over any subject in any tenant. This is a **known, accepted, and
pre-existing** property of janua's internal API, not one introduced here; it is
the same trust `internal_users.py` already relies on, and the ratified move to
per-service tokens fixes it for this router at the same time as the others.

**A capability link is a bearer credential.** Anyone holding the string has the
scopes until it expires or is revoked. That is inherent to the shape, which is
why TTL is mandatory, revocation is immediate, and the audit trail is not
optional. Where the recipient *can* have an identity, nauta's identity-bound
invitation model is strictly stronger and should be preferred.

---

## Migration path — explicitly OPTIONAL

**No app is required to migrate. Ever.** This is groundwork, not a mandate.

- **The client portal keeps its intake link.** It is in production, correct on the
  properties that matter, and its 30-day multi-use policy is a domain decision.
  Nothing in this ADR asks it to change. If it *ever* adopts the primitive, the
  motivation would be gaining multiple concurrent links per subject and a
  revocation history its current PK-per-subject upsert cannot express — not
  security, which it already has.
- **kalya's `FeedToken` should probably stay too**: no TTL is genuinely correct
  for a polled calendar subscription, and the primitive's mandatory TTL would be
  a regression for that use case. `Booking.manageToken` is the better candidate —
  it would gain hash-at-rest and revocation, both of which it lacks.
- **nauta needs nothing.** Its identity-bound model is stronger. The primitive is
  only relevant if it ever needs to reach someone with no Janua account.
- **`guest_invites` is NOT migrated, deprecated, or altered by this change.** It
  is a different primitive (org-scoped, no subject). Silently duplicating it
  would be the wrong outcome, but so would bundling its remediation into this
  ADR. Its plaintext storage, nullable expiry, and the authorization gap flagged
  above are **separate work items** to be triaged on their own merits.

The intended first consumers are **new** surfaces that would otherwise hand-roll
a fifth table. Migration of an existing implementation should happen only when
that app has an independent reason to want it.

---

## Non-goals

- **Not a session system.** Resolving a capability link does not create a janua
  session, does not mint a JWT, and does not sign anyone in. It answers "what
  does this string authorize?" and stops. (`guest_invites` *does* mint a guest
  JWT — another reason the two are different primitives.)
- **Not OAuth, and not an OAuth scope system.** No authorization code, no
  refresh, no consent, no client registration. Scope strings here are opaque
  app-defined labels with no relationship to OAuth scopes.
- **No janua knowledge of subject semantics.** Janua will not gain a subject
  registry, subject validation, per-`subject_type` behaviour, or scope
  vocabularies. The first feature request to "just validate that the subject
  exists" must be refused: it would require janua to hold every app's domain
  model, and it is the exact coupling this design is built to avoid.
- **Not a replacement for identity.** Where the recipient can have an account,
  use identity. This primitive exists for the case where they cannot.
- **Not a permission engine.** Janua stores and returns scopes; the calling app
  decides what they permit. Janua never evaluates them.
- **No delete.** Grants are retired, never erased.

---

## Consequences

**Positive.** One correct implementation with tests replaces a per-app judgement
call on seven security properties. Hash-at-rest, bounded TTL, generic refusal,
soft revocation and audit become non-optional because they are the only
behaviour on offer. Rotation-with-history exists, which no prior implementation
has. New apps stop starting the table over.

**Negative, stated honestly.**

- It **centralizes bearer-credential storage in the identity service**, making
  janua's blast radius larger. The hash-at-rest design is what keeps a database
  compromise from yielding usable credentials, and it is load-bearing.
- It is **only as strong as `X-Internal-API-Key`** until service tokens land.
- **Mandatory TTL is a real constraint**, not a free win: it would be a
  regression for kalya's `FeedToken` use case, which is part of why no migration
  is forced.
- It adds a **table janua must operate** — retention and archival of expired and
  revoked rows are unspecified here and will need a policy before volume grows.

**Deploy note (operator step).** `promote` runs **no migrations** in this
ecosystem. `014_capability_links` must be applied deliberately against each
target database before the endpoints are exercised there. Until it is, the
handlers raise on a missing relation — loudly, which is the intended failure.
Nothing else regresses, since no existing code path touches the table.

---

## Appendix: `users.email` uniqueness and per-tenant end-user auth

*Analysis only. No code in this change touches any of it.*

### The current state is better than the brief for this work assumed

The premise that "`users.email` uniqueness blocks per-tenant end-user auth"
**was already substantially addressed** by migration
`013_per_tenant_email_uniqueness` (in `main`). It replaced the global unique
index with **two partial unique indexes**:

- `uq_users_tenant_email` — `UNIQUE (tenant_id, email) WHERE tenant_id IS NOT NULL`
- `uq_users_email_global` — `UNIQUE (email) WHERE tenant_id IS NULL`

Two partial indexes rather than one composite, because a single
`UNIQUE(tenant_id, email)` would **silently regress the staff pool**: Postgres
treats NULLs as distinct in a unique index, so two untenanted rows with the same
email would both be permitted, losing today's guarantee. And `tenant_id NOT NULL`
was rejected because staff legitimately belong to no tenant.

`app/services/user_lookup.py` is the matching app-layer primitive: every email
lookup must declare its pool, and there is deliberately no "search every pool"
helper.

**So the schema-level blocker is gone.** The same person's email *can* already
exist once in each of two tenant orgs. What remains is narrower and entirely in
the auth flows.

### What actually still blocks it: the flows resolve email in one pool

The gap is that the entry points hardcode the untenanted pool. `auth.py:2257`:

```python
user = await get_user_by_email(db, magic_link_data.email, tenant_id=None, active_only=True)
```

`POST /auth/magic-link` takes a bare email with no tenant context, resolves it in
the `tenant_id IS NULL` pool, and **creates a user there if absent**. So a person
who exists in two tenant orgs cannot sign in as either — a bare-email magic link
resolves to (or creates) a *third*, untenanted identity. `MagicLink` itself has
no tenant column; it carries `user_id` and `email`, so the tenant is only ever
implied by which user row was resolved.

**The remaining work is therefore flow-level, not schema-level:** give the
magic-link request a tenant context and thread it through the lookup, the
create branch, and the callback.

### Options

**A. Tenant-scoped magic link (recommended).** Keep the two partial indexes.
Add an optional tenant discriminator to the magic-link request — derived from the
requesting OAuth client's organization or the redirect host, both of which
`_session_audience_for_redirect` already resolves — and pass it to
`get_user_by_email`. Omitted, behaviour is unchanged (`tenant_id=None`), so the
staff/platform flow is untouched.

*Blast radius:* moderate but contained. `send_magic_link`, its create branch,
and `magic_link_callback` (which resolves by `magic_link.user_id`, so it already
follows correctly once the right user is chosen). *Ambiguity to resolve:* a bare
email with no tenant context that exists in several tenants — the honest answer
is to keep resolving it in the untenanted pool rather than guessing, and require
tenanted callers to supply the context.

**B. Separate end-user table.** Cleanest conceptual separation of staff from
end-users, and it retires the awkward "one `users` table with no discriminator"
that 013's docstring calls out. But it is a very large change: sessions, MFA,
passkeys, OAuth, SCIM, audit, and every SDK assume one user table. **Not
recommended now** — the cost is disproportionate given 013 already delivered the
isolation, though it may be the right destination if per-tenant end-user auth
becomes a primary product.

**C. Alias strategy** (e.g. `tenant+alice@example.com`). **Not recommended.** It
encodes tenancy in a user-visible identifier, breaks as soon as a person belongs
to two tenants, corrupts the address for actual mail delivery, and pushes
parsing into every call site. It trades a schema problem for a data-integrity one.

### Recommendation

**Option A.** The expensive half — the schema — is already done and shipped.
What remains is threading tenant context through the magic-link flow, which is
additive, defaults to today's behaviour, and needs no backfill.

Two things to settle before implementing, neither of which is in scope here:

1. **Case sensitivity.** Both indexes are case-*sensitive*, matching the
   `ix_users_email` they replaced. But `internal_users.py` lowercases on write
   for its own idempotency. Two write paths currently disagree about whether
   `Foo@bar.com` and `foo@bar.com` are one person. Per-tenant end-user auth will
   surface this; 013 deliberately deferred it as needing normalization of
   existing rows and every write path.
2. **Whether `magic_links` needs its own `tenant_id`.** Today the tenant is
   implied by the resolved user. An explicit column would make the callback's
   pool unambiguous and auditable, at the cost of one more migration.

---

## References

- `apps/api/alembic/versions/013_per_tenant_email_uniqueness.py` — the two partial indexes
- `apps/api/app/services/user_lookup.py` — pool-scoped lookup primitive
- `apps/api/app/routers/v1/internal_users.py` — internal-API style precedent
- `apps/api/app/routers/v1/auth.py:2235` — `send_magic_link`, the `tenant_id=None` pin
- `apps/api/app/models/__init__.py:690` — `GuestInvite`, the near-miss primitive
- ADR-003 — Multi-Tenancy Strategy
