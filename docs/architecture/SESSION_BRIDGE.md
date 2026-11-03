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
5. Completion requires exactly one Origin header matching the registered source
   origin, the initializer cookie, matching transaction/code, current
   client/URI/scope/audience policy, live proof authority and no conflicting
   existing issuer identity. The complete validated Redis tuple is atomically
   consumed before setting the existing estate cookie. A 303 resumes the
   original ordinary OAuth authorization with its original state, nonce and
   PKCE.

The SameSite=None setting applies only to the short-lived initializer: a
top-level cross-site POST needs it. The estate cookie keeps its existing
attributes. A foreign browser form cannot forge Origin; a forged HTTP Origin
alone lacks the initiating browser secret. Browser binding without this
source-origin POST check would not reject a captured-transaction/code injection.

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
POST behavior in the owned isolated stage. Retain the required continuous
running-digest soak and manual promotion contract. Source and consumer
configurations remain disabled until their corresponding routes and
browser-bound target callback are live. No real email or production credential
entry is needed for automated tests.

Both normal login methods and already-established sessions must be covered.
Installed-app storage and out-of-scope navigation require a physical-device
acceptance pass; unrelated browser profiles cannot silently infer a source
identity. The source's refresh path must distinguish direct from OIDC refresh
grants and write its canonical cookies, without inventing a new session.
