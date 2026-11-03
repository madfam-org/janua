# Browser-bound session continuation

`SESSION_BRIDGE_ENABLED` defaults to false. This opt-in protocol restores an
existing, live issuer session from an authenticated first-party application. It
creates no user, session, application membership or authentication evidence.
Normal target OAuth authorization and application admission remain
authoritative.

## Protocol

1. `GET /api/v1/oauth/session-bridge/start` accepts an ordinary silent
   authorization request plus `bridge_uri`. Both clients must be active
   confidential first-party clients. The source URI must identify exactly one
   registered client and must be HTTPS, with no query or fragment. The target
   callback is matched exactly; response type is code, PKCE is S256, and
   state/nonce are required. Only the documented authorization parameter set is
   retained. Scope is narrowed through the existing grant policy, and the source
   audience is bound in shared state.
2. Initialization writes a 120-second strict shared transaction and a fresh
   `__Host-janua-session-bridge` cookie: Secure, HttpOnly, Path=/, no Domain,
   SameSite=None. Only the initializer cookie hash is stored. The browser visits
   the registered source URI with an opaque transaction identifier; no access or
   refresh token enters a URL.
3. The source verifies its real active actor, independently of any preview
   identity, and calls `POST /prepare` with HTTP Basic client authentication and
   its access/refresh proof. The issuer rechecks client registration and current
   source audience. The response contains only an opaque one-use code, capped at
   30 seconds and at the original proof/session expiry.
4. The source returns a source-origin HTML form that posts the transaction/code
   to `POST /complete`. It never accepts a caller-provided code. Use no-store,
   no-referrer, frame-ancestors none, a fixed trusted form-action and a script
   nonce. No credentialed CORS read is involved. GET completion never
   establishes a session.
5. POST approval requires exactly one Origin header matching the registered source
   origin, the initializer cookie, matching transaction/code, current client,
   URI, scope, audience and live proof. It atomically consumes the original
   tuple, then stages only approved proof references in strict Redis. Failure
   after consumption loses this attempt and never restores the grant. POST
   **never sets an estate or authentication cookie**.
6. POST sets a new random `__Host-janua-session-bridge-final` cookie: Secure,
   HttpOnly, Path=/, no Domain, SameSite=Lax. Its hash keys the approved record;
   its TTL is at most 30 seconds and never exceeds the original proof expiry.
   A 303 redirects to the fixed query-free `GET /api/v1/oauth/session-bridge/finalize`.
7. That GET accepts only its private finalization cookie, never a public
   transaction or source code. It rechecks current client policy, proof and both
   current issuer identities before atomically consuming the approved record.
   Only then may it set the existing estate cookie and resume ordinary OAuth
   with the original state, nonce and PKCE. A conflict or revoked proof consumes
   the approval, clears only private bridge cookies and leaves existing auth
   cookies unchanged. Wrong/missing final cookies cannot consume another
   browser's approval. GET `/complete` remains unsupported.

The SameSite=None setting applies only to the initializer: a top-level
cross-site POST needs it. Existing issuer authentication cookies are explicitly
Lax and are absent on that POST, so an identity check there cannot authorize
replacement. The 303 safe GET evaluates the current Lax cookies, including an
account switch after POST approval. The new Lax cookie may be set during a
top-level POST; the safe current redirect hop qualifies for Lax delivery under
[the cookie specification](https://httpwg.org/http-extensions/draft-ietf-httpbis-rfc6265bis.html#name-strict-and-lax-enforcement).
These source rules still require native owned-stage browser navigation proof;
ASGI cookie injection does not demonstrate cross-site delivery. Existing auth
cookie attributes are unchanged. A foreign form cannot forge Origin; a forged
HTTP Origin lacks the initializer secret. No source code or finalization secret
is placed in a redirect URL.

## Source authority

- Signature, issuer, exact configured source audience, token type and expiry are
  checked with RS256. An audience taken from unverified token claims is not an
  acceptance policy.
- A direct credential must match the current access or refresh JTI in its exact
  live session. Supplied family/session references must agree. Legacy direct
  proof acquires no new assurance.
- An OIDC access token alone cannot restore a parent. Require the source-bound
  refresh grant, signed session reference, matching subject and session
  evidence, plus strict grant-JTI, grant-family and parent-family revocation
  reads. There is no stored-current OAuth rotation ledger here; do not claim
  otherwise. Historical grants without a revocable session reference require
  ordinary hosted confirmation.
- Current MFA policy and immutable session evidence are checked again before
  consumption. Only proof references and an evidence hash are stored, never
  bearer/refresh credentials.
- Both existing estate and hosted-access identities are compared. The hosted
  comparison is deliberately conservative: a signed/unrevoked subject that the
  downstream selector can still choose blocks replacement even if that legacy
  user's status/session is inactive. It never grants restoration authority. A
  conflict leaves existing authentication cookies unchanged.

A bound browser may cancel a transaction and return to the target's normal
sign-in state. Cancellation removes the transaction; an already-issued orphan
marker/code expires within its short TTL and cannot be used without that
transaction. Wrong browser, Origin or malformed input must not consume a valid
transaction. Redis unavailability fails closed.

## Qualification and rollout

The focused unit suite uses real RSA verification, isolated Redis doubles and
ASGI requests with synthetic roles/codes. Its HTTP tests substitute the live
database/session authority; they are not proof of native SQL isolation, real
browser cookie delivery, physical-device behavior or live SSO.

Before activation, qualify client registration, key custody, dependency
readiness, native session revocation, hosted OAuth/PKCE and cross-origin browser
POST → 303 → GET behavior, including withheld POST auth cookies and account
switches before finalization, in the owned isolated stage. Retain the required continuous
running-digest soak and manual promotion contract. Source and consumer
configurations remain disabled until their corresponding routes and
browser-bound target callback are live. No real email or production credential
entry is needed for automated tests.

Both normal login methods and already-established sessions must be covered.
Installed-app storage and out-of-scope navigation require a physical-device
acceptance pass; unrelated browser profiles cannot silently infer a source
identity. The source's refresh path must distinguish direct from OIDC refresh
grants and write its canonical cookies, without inventing a new session.

### Required native authority evidence

`tests/unit/auth/test_session_bridge_native.py` belongs to the existing
PostgreSQL partition. CI explicitly requires its test-service configuration and
asserts that all 27 cases executed successfully, with zero skipped cases, from
the PostgreSQL job's JUnit report. Missing configuration, services, collection or
execution fails the proof closed. Local opt-in requires `LOCAL_DB=yes`, the
existing loopback `MIGRATION_TEST_DATABASE_URL` targeting a dedicated `_test`
database, and `JANUA_SESSION_BRIDGE_TEST_REDIS_URL` for loopback Redis database 0.
`JANUA_SESSION_BRIDGE_NATIVE_REQUIRED=1` forbids a local configuration skip.

The fixture creates only its generated scratch schema with real User, Session,
Organization and OAuthClient ORM tables. It exercises actual AsyncSession reads,
committed row changes, stored MFA evidence/current JTI, real source JSONB URI
selection/current registered pair, and revocation through two independent Redis
connections. Every Redis key is tracked individually and deleted only by exact
owned key; no shared scan or flush is used. Synthetic RSA is generated locally;
verification, authority and session-policy functions are not mocked.

Source preparation or collection is not execution evidence. This ORM fixture
does not prove Alembic migrations, native HTTP middleware or browser cookie
navigation. Actual isolated-stage cross-site POST → 303 → GET and physical PWA
qualification remain separate before activation. No production configuration,
client registration, credentials or identities are required by this test.

The source lookup is shared by GET start and native qualification. Its bounded
SQL predicate supports native JSONB arrays and historical JSON-string ORM
serialization without changing global storage. Only extracted scalar text uses
an escaped quoted-URI prefilter; native arrays use JSONB containment. At most
three candidates are read, overflow/malformed values fail closed, and exact
URI membership in the decoded top-level list is mandatory. A unique source is
reloaded and must still satisfy current first-party/confidential/active policy.
No registry row or stored representation is rewritten.

The existing first-party name/reserved-scope and authorization-code eligibility
predicates also run before the candidate cap. Self-registered untrusted clients
sharing a URI cannot crowd out a legitimate platform source. The final current
Python policy remains authoritative; SQL candidate filtering grants nothing.
Native tests cover both physical storage forms, multiple URIs, duplicate source
refusal, untrusted crowding, malformed values and literal wildcard/substring
near misses. Source compilation or tests with substituted SQL are not native
execution evidence.

### Nonpublishing API image gate

PR verification builds the root `Dockerfile.api` with the actual repository
context after both API test partitions succeed. It loads a unique CI-only local
tag and never publishes, signs, pins or promotes it. The built image runs only
an isolated Python import/compile check with network disabled and synthetic
configuration. The production entrypoint, migrations and application lifespan
are not started. Ephemeral RSA keys stay in process memory and are not printed.

The gate compiles the seven changed API modules, imports the packaged real
application and checks all four bridge route methods, unsupported GET completion,
the unchanged disabled default and all four rate-limit entries. A successful
JavaScript build is not this evidence. Native PostgreSQL/Redis execution remains
an independent required result; image import is not browser or stage proof.
