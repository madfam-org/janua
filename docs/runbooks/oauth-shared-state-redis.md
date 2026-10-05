# OAuth shared state and the Redis circuit breaker

The authorization flow keeps short-lived security state in Redis. Every API
replica must see the same state, because the consent page is rendered by one pod
and the Allow/Deny form is posted to whichever pod the load balancer picks.

| Key | Written at | Read and consumed at | TTL |
|-----|-----------|----------------------|-----|
| `oauth:pre_login:<id>` | `GET /oauth/authorize` (no session yet) | hosted login form, magic link | 10 min |
| `oauth:csrf:<token>` | `GET /oauth/authorize` (consent screen) | `POST /oauth/consent`, `POST /oauth/authorize` | 10 min |
| `oauth:auth_request:<id>` | `GET /oauth/authorize` (consent screen) | `POST /oauth/consent` | 10 min |
| `oauth:code:<code>` | authorize / consent | `POST /oauth/token` | 10 min |
| `passkey_challenge:<user>` | `POST /passkeys/register/options` | `POST /passkeys/register/verify` | 5 min |
| `passkey_auth_challenge:<id>` | `POST /passkeys/authenticate/options` | `POST /passkeys/authenticate/verify` | 10 min |
| `oauth_state:<state>` | `POST /auth/oauth/authorize/{provider}`, `POST /auth/oauth/link/{provider}`, on-behalf link | `GET /auth/oauth/callback/{provider}`, `GET /auth/oauth/link/callback/{provider}` | 10 min |

The revocation list is also read on the security path. Its reads are strict.
Every reader goes through `app/services/token_revocation.py` (`is_revoked`),
which checks all the keys below that apply to the token:

| Key | Written by | Read by |
|-----|-----------|---------|
| `blacklist:<jti>` | `AuthService.revoke_sessions` (sign-out, password change, session-limit eviction, `DELETE /sessions*`, per-account sign-out, family revocation); refresh rotation; `POST /oauth/revoke` (strict) | `AuthService.verify_token` (`POST /auth/refresh`, `GET /auth/session`, sessions routes); `/oauth/token` `refresh_token` grant, `/oauth/introspect`, `/oauth/userinfo` |
| `blacklist:<type>:<jti>` | `JWTManager.blacklist_token` (devices, `refresh_token_pair`) | the same readers (both spellings are checked since 2026-10); `JWTManager.refresh_token_pair` (`blacklist:refresh:<jti>`, no mounted caller) |
| `revoked_family:<family>` | `AuthService.revoke_sessions` (every revoked session's refresh family); `revoke_token_family`; `POST /oauth/revoke` with a refresh token (strict) | refresh-token readers only: `POST /auth/refresh`, the `refresh_token` grant, `/oauth/introspect` |

Every entry expires on its own: a JTI with its token, a family after the
refresh-token lifetime (no token of a revoked family can be minted later).

## Failure mode (fixed 2026-10)

`get_redis()` returns a `ResilientRedisClient`. Its ordinary operations go
through a per-process circuit breaker. When Redis errors, or the circuit is
open, they do not raise: they return a fallback value, and reads may be served
from a per-process memory cache. That is fine for caches. It is wrong for the
keys above:

- A CSRF token or authorization request "written" while a pod's circuit was open
  was stored nowhere. The consent page still rendered. Pressing Allow then failed
  on every pod with `403 Invalid or expired CSRF token`.
- If the first PING failed when a process first used Redis, `init_redis` dropped
  the client for the life of that process. Every Redis call on that pod then
  fell back. The readiness probe and `/ready` opened their own connection, so
  they still reported Redis as healthy.
- `set` copied values into the memory cache and `delete` did not evict them. A
  pod whose circuit opened later could serve an authorization code or CSRF token
  that had already been consumed.

## Current behaviour

- **Strict operations.** The keys above are written, read and consumed with
  `strict_set`, `strict_get` and `strict_delete`. These calls try Redis whatever
  the circuit state. They never use the memory cache, and they raise
  `RedisUnavailableError` on failure.
- **Retryable 503.** `RedisUnavailableError` is answered with
  `503 Service Unavailable` and `Retry-After: 5`. Browsers get a short page
  ("Sign-in is temporarily unavailable"). API clients get the standard error
  envelope with code `TEMPORARILY_UNAVAILABLE`. `/authorize` never renders a
  consent form it could not honour. `/consent` answers 503, not 403, when Redis
  cannot be read, and nothing is consumed, so the same submit works once Redis
  answers.
- **When 403 still applies.** `/consent` answers 403 only when the token is
  missing, unknown, expired, issued to another user, or already consumed. A
  token is consumed by the first submit; a double-clicked Allow posts it twice.
  The consent form now submits once. The server logs `oauth.consent.csrf_rejected`
  with a `reason`.
- **Single use across pods.** Consumers check the count returned by `DEL`. Of two
  concurrent submits, or two redemptions of one code, exactly one succeeds.
- **No permanent degraded pod.** `init_redis` keeps the client even when the
  first PING fails. The redis-py pool reconnects on the next command. Connection
  attempts are bounded by `REDIS_CONNECTION_TIMEOUT` (milliseconds).
- `delete` evicts the pod-local copies of the keys it deletes.

## Revocation checks fail closed (2026-10)

Owner decision, 2026-10-04: "yes, make revocation checks fail closed".

Until then, the revocation list and refresh-token reuse detection were read with
the breaker's `get` and `exists`. While Redis was unreachable, or a replica's
breaker was open, those calls returned the fallback (`None` or `0`), which means
"not revoked". A logged-out, rotated-away or replayed token was accepted.

Now:

- `AuthService.verify_token` reads `blacklist:<jti>` with `strict_exists`.
  `JWTManager.refresh_token_pair` reads `blacklist:refresh:<jti>` the same way.
  When Redis cannot answer, they raise `RedisUnavailableError`, and the request
  gets `503` + `Retry-After`. They never answer "not revoked" without Redis.
- With Redis healthy, behaviour is unchanged. A token that is not revoked is
  accepted. A revoked one is refused (`401` on `/auth/refresh` and
  `/auth/session`). A reused refresh token is refused. If the reuse is detected
  in the database (no active session row has that JTI), the whole token family is
  revoked, as before.
- **Bookkeeping callers do not fail.** Sign-out (`/auth/signout`, `/auth/logout`),
  password change and the sessions routes (`GET /sessions`, `GET /sessions/{id}`,
  `DELETE /sessions`) use the token only to find "this" session. The request has
  already been authenticated by `get_current_user`. They call
  `AuthService.identify_token`. With Redis healthy that is `verify_token`. During
  an outage it falls back to the signature-checked claims, so sign-out still
  revokes the session row and clears cookies.
- **Revocation writes stay best-effort, and are no longer silent.** Logout,
  rotation and family revocation still write the list through the fallback,
  because those flows must finish and the session row in the database is
  updated too. A write Redis did not take is logged at error level as
  `Revocation-list write not acknowledged by Redis; token not blacklisted`.
- Passkey challenges and `oauth_state:*` use `strict_set`, `strict_get` and
  `strict_delete`, the same as the consent keys above. A challenge or state is
  consumed exactly once across replicas, using the count from `DEL`.

### What an operator sees during a Redis outage

| Request | Answer |
|---------|--------|
| `POST /api/v1/auth/refresh` | `503`, `Retry-After: 5`, `{"error": {"code": "TEMPORARILY_UNAVAILABLE", ...}}` |
| `GET /api/v1/auth/session` | `503`, same body |
| `/api/v1/passkeys/*/options` and `/verify` | `503`, same body |
| Social sign-in and link start, and their callbacks | `503`. Browsers (`Accept: text/html`) get the short "Sign-in is temporarily unavailable" page |
| OAuth consent, `/oauth/authorize`, `/oauth/token` (`authorization_code`) | `503` (since #694) |
| Sign-out, password change, sessions list, `DELETE /sessions*` | work. The session row is revoked in the database, and `POST /auth/refresh` checks the row, so the revocation holds once Redis is back |
| `POST /auth/password/reset`, `POST /auth/reset-password-form` | `503`, nothing applied: the password, the reset link and the sessions are unchanged, and the same link works once Redis answers (since 2026-10: a reset revokes every session strictly, see "Revocation that revokes") |
| `POST /oauth/revoke` | `503` when the token needs revoking (the revocation could not be stored); `200` for an unknown, invalid or another client's token |
| `POST /oauth/token` (`refresh_token` grant), `POST /oauth/introspect`, `GET /oauth/userinfo` | `503` (since 2026-10: they read the revocation list) |
| `GET /.well-known/jwks.json`, `GET /.well-known/openid-configuration` | `200`. They never touch Redis |
| Routes behind `get_current_user` (most of the API) | work. Signature check plus a database read; that dependency consults no revocation list |

Logs: `State store unavailable; answering 503` (with `path`) and
`Strict Redis operation failed` (with `error_type`). The `strict_failures`
counter in `redis_circuit` on `/ready` goes up.

Relying parties verify Janua access tokens locally against the JWKS. A Redis
outage does not change that path. Since 2026-10 the readiness probe no longer
fails because of Redis (see "Health and readiness" below), so both replicas stay
in the Service during a Redis outage: JWKS, discovery and every route in the
table above answer from Janua.

| Probe or health route | During a Redis outage |
|-----------------------|-----------------------|
| `GET /api/v1/health/ready` (the k8s `readinessProbe`) | `200`, `"status": "degraded"`, `"redis": "unhealthy"`, `"degraded": ["redis"]` (plus `"database"` if it is down too), `redis_circuit` with `strict_failures` rising |
| `GET /health` (the k8s `livenessProbe`), `GET /api/v1/health/live` | `200`, unchanged |
| `GET /api/v1/health/detailed` | `200`, overall `"status": "unhealthy"` and `checks.redis.status: "unhealthy"` (Redis stays a critical check there) |
| `GET /ready` (not probed) | `200`, `"status": "degraded"`, `"redis": false`, unchanged |

**Readiness going red no longer means "Redis is down".** Alert on the readiness
body instead (follow-up below).

### Recovery

Nothing needs to be cleared or replayed. Requests answered `503` changed nothing:
no token was rotated and no challenge or state was consumed. When Redis answers
again, the next strict call (or the next readiness probe) moves each replica's
breaker to half-open. Clients retry after `Retry-After`. Check
`redis_circuit.strict_failures` on `/ready`: it stops rising.

## Health and readiness

Owner decision, 2026-10-04: "yes, make readiness independent of Redis".

- **Readiness reports Redis but does not gate on it.** Before, a pod that could
  not PING Redis answered 503 on `/api/v1/health/ready`. Both replicas share one
  Redis, so a Redis-wide outage took every pod out of the Service after about
  30 s (period 10 s, failure threshold 3). JWKS and OIDC discovery, which never
  touch Redis, went down with them, and so did sign-in for every relying party.
  Now the probe answers 200 and reports the outage in its body: `redis`
  (`healthy` / `unhealthy` / `error`), `degraded` (the reported-only checks that
  are failing), `status` (`ready` or `degraded`) and `redis_circuit`. The list
  of reported-only checks is `READINESS_REPORTED_ONLY` in
  `app/routers/v1/health.py`; today it holds only `redis`.
- **Every other dependency gates exactly as before.** The registered checks are
  `database` (critical, reported only since the next section), `redis`
  (critical, reported only) and `encryption_key` (non-critical, never gated).
  The probe also answers 503 when the health checker never initialised, and for
  any critical check registered later that is not in `READINESS_REPORTED_ONLY`.
  Liveness (`/health`) is unchanged.
- The readiness probe (`/api/v1/health/ready`) and `/ready` check Redis with a
  strict PING through **this process's own client**, the one requests use. They
  no longer open a fresh connection.
- Both report this pod's breaker as `redis_circuit`: `state`
  (`closed` / `open` / `half_open`), `last_failure_time`, `fallback_calls`,
  `strict_failures` and `client_initialized`. Hostnames, keys and error text are
  never included. `/api/v1/health/detailed` carries the same block under
  `checks.redis_circuit`. The full counters stay at `/api/v1/health/circuit-breaker`.
- **Readiness does not fail because of the breaker or a failed PING.** The
  replicas share one Redis, so a short blip opens every breaker at the same
  moment, and a real outage fails every PING at the same moment. Gating on
  either removed every pod from the Service. A pod whose own client is broken
  while Redis is fine is no longer taken out either: it answers 503 on its
  Redis-backed routes and reports `redis: unhealthy`. Restart it if it does not
  recover.
- A strict call that succeeds while the circuit is open moves the circuit to
  half-open. The readiness probe runs every 10 s, so a pod stops serving
  fallbacks within about one probe period after Redis answers again.
- **Each check is bounded** (`READINESS_CHECK_TIMEOUT_SECONDS` in
  `app/main.py`, 2 s). The kubelet gives the probe 5 s and the checks run one
  after another. A dependency that hangs instead of refusing would otherwise
  outlast the probe, and a timed-out probe counts as failed, which would take
  the pod out of the Service despite "report, don't gate". A check that times
  out reports `unhealthy`.

## Database readiness: reported, not gated (2026-10)

Owner decision, 2026-10-04: "yes, go with all three recommendations" (J3-001).

Until then the `database` readiness check could not fail.
`get_database_health()` returns a dict (`{"healthy": false, ...}` during an
outage), and `HealthChecker` counted any non-empty result as healthy. So
readiness said `healthy` through every database outage, and `/health/detailed`
did too.

Now:

- `HealthChecker` counts a dict result as healthy only when its `healthy` is
  `true`. The registered check (`_check_database_health` in `app/main.py`)
  runs `SELECT 1` through the database manager, bounded like the Redis check.
- If the database was unreachable when the pod started, the check retries the
  connection on each probe and reports `healthy` once the database answers. It
  no longer reports `unhealthy` until the pod restarts.
- **Readiness reports the database and still answers 200.** The replicas
  share one database. Gating on it would empty the Service during a database
  outage and take JWKS, discovery and the health routes down with it, while
  the database-backed routes fail on their own anyway. `database` is in
  `READINESS_REPORTED_ONLY` with `redis`.
- The body carries `database: {"healthy": <bool>, "status": "healthy" |
  "unhealthy" | "error"}`. It never includes error text or hostnames.

### What an operator sees during a database outage

| Probe or route | During a database outage |
|----------------|--------------------------|
| `GET /api/v1/health/ready` (the k8s `readinessProbe`) | `200`, `"status": "degraded"`, `"database": {"healthy": false, "status": "unhealthy"}`, `"degraded": ["database"]` (`["database", "redis"]` if Redis is down too) |
| `GET /health` (the k8s `livenessProbe`), `GET /api/v1/health/live` | `200`, unchanged |
| `GET /api/v1/health/detailed` | `200`, overall `"status": "unhealthy"` and `checks.database.status: "unhealthy"` |
| `GET /ready` (not probed) | `200`, `"status": "degraded"`, unchanged |
| `GET /.well-known/jwks.json`, `GET /.well-known/openid-configuration` | `200`. They never touch the database |
| Database-backed routes (sign-in, refresh, password reset, sessions, OAuth token, admin...) | fail on their own, typically `503` with the error envelope code `DATABASE_ERROR` |

Both replicas stay in the Service, so relying parties keep verifying Janua
access tokens against the JWKS. Log line: `Database health check failed`
(with the error type only).

## Diagnosing a consent 403 or 503

1. Read `redis_circuit` on `/ready`. Each request lands on one pod, so read it a
   few times. `fallback_calls` or `strict_failures` going up means that pod
   is not reaching Redis.
2. Search the API logs for `oauth.consent.csrf_rejected` and its `reason`:
   `unknown_or_expired` (expired, double submit, or a token never issued),
   `consumed_concurrently` (two submits at once), `missing`. A user mismatch
   logs `CSRF token user mismatch`.
3. Search for `State store unavailable; answering 503` and
   `Strict Redis operation failed`.

## Follow-up: alerting on the readiness body

Not done in this change, and no monitoring configuration was touched. Because
readiness stays green during a Redis outage AND during a database outage, the
platform's alerting has to read the body, for both dependencies:

- alert when `GET /api/v1/health/ready` has a non-empty `"degraded"` on any
  replica for more than one or two probe periods. That covers both:
  - `"database": {"healthy": false, ...}` (`"degraded"` contains `"database"`);
  - `"redis"` other than `"healthy"` (`"degraded"` contains `"redis"`);
- alert when `redis_circuit.strict_failures` keeps rising, or `redis_circuit.state`
  stays `open`;
- keep alerting on a 503 from readiness: it now means a gating check failed
  (today, only a health checker that never initialised);
- a blackbox probe that only reads the HTTP status of readiness will no longer
  see either outage. Read the body, or probe a database-backed route.

## Still on the fallback path (follow-ups)

These keys still use the breaker's fallback operations. Each needs its own
decision:

- `oauth:pre_login:<id>` **reads** in the hosted login and magic-link handlers.
  The write is strict. On a miss the readers rebuild the authorize URL from the
  client registration and lose `state` and PKCE.
- Revocation-list **writes** (`blacklist:*`): best-effort, now logged when lost
  (above).
- `JWTService` (`app/services/jwt_service.py`) reads `revoked:<jti>`,
  `jti:<type>:<jti>`, `used:refresh:<jti>`, `blacklist:<jti>` and
  `revoked_user:<id>` through whatever client it is given. No mounted route calls
  its verification or refresh methods. Its `revoke_all_tokens` uses an
  asyncpg-style `db.fetch`. Left unchanged: delete it or rewire it, not both
  halves.
- `user:valid:<id>` (`get_current_user`) only short-circuits a cached
  **negative** answer. A cached `valid` is not trusted: the database is read on
  every request. A stale `invalid` from the memory cache can refuse a reactivated
  user during an outage (fails closed).
- RBAC caches in `app/services/rbac_service.py` (`permission` and role lookups,
  5 minutes in Redis) can be served from the per-process memory cache while the
  breaker is open, and that cache ignores TTLs. A revoked permission could be
  honoured from memory during an outage. Fix: on a miss or an outage, read the
  database rather than the fallback cache.
- Enterprise SSO OIDC state and nonce (`oidc_state:*` through `CacheService`)
  use a separate raw client that answers `None` or `False` on errors. There is no
  pod-memory replay, but a lost write still shows up later as an invalid state.
- The memory cache ignores TTLs for every key it holds.

Revocation gaps that are not about Redis availability. The first four were
fixed in 2026-10 (next section); the rest remain, recorded here so they are not
mistaken for fixed:

- Fixed: sign-out, password change and session-limit eviction did not stop
  `POST /auth/refresh` (key spelling and column mismatch).
- Fixed: `DELETE /sessions/{id}` and `DELETE /sessions` revoked nothing.
- Fixed: `POST /oauth/revoke` acknowledged without revoking anything.
- Fixed: password reset (`/auth/password/reset`, the hosted reset form) set
  the new password without revoking any session.
- `get_current_user` consults no revocation list, so a logged-out access token
  is accepted by most routes until it expires (owner ruling pending).
- The `refresh_token` grant on `POST /oauth/token` does not rotate-and-blacklist
  the presented token and has no reuse detection. A revoked family is refused.
- Access tokens minted by an OAuth grant carry no family, so revoking the
  grant's refresh token does not revoke them; they expire on their own
  (RFC 7009 makes this a SHOULD). Revoke one by presenting it.
- Bulk revocations in `admin.py`, `users.py` and `internal_users.py` set only
  `sessions.revoked` with an `UPDATE`. That now stops `/auth/refresh` (the row
  check), but those paths do not blacklist the sessions' access tokens.

## Revocation that revokes (2026-10)

Owner decision, 2026-10-04: "yes, go ahead with the follow-up Janua PR".

A Janua session is one `sessions` row. Its refresh tokens form one rotation
family: every refresh mints a new token with the same `family` claim and
moves the row's `refresh_token_jti` to it. Revoking a session therefore means
revoking that family.

`AuthService.revoke_sessions` is the one implementation every path uses. For
each row it:

1. sets every flag Janua reads: `revoked = True`, `is_active = False`,
   `revoked_at`, `revoked_reason`;
2. writes `revoked_family:<family>` and `blacklist:<refresh jti>` until the
   row's expiry;
3. writes `blacklist:<access jti>` for the access-token lifetime;
4. drops the row's fast-lookup entry from the Redis session store.

The Redis writes are best-effort (an error is logged when one is lost).
`POST /auth/refresh` also refuses any refresh token whose row is not live
(`revoked`, `is_active = False` or expired), so a revocation holds even when
its Redis write was lost, and even for paths that only update the row.

| Action | What is revoked | `revoked_reason` |
|--------|-----------------|------------------|
| `POST /auth/signout`, `POST /auth/logout` | this session's family; the presented access token's JTI until it expires | `user_logout` |
| `POST /auth/sessions/sign-out-one`, `sign-out-all`, OIDC `end_session` | each signed-out account's session (via `revoke_sso_session`) | `logout` |
| `DELETE /sessions` | every other session of the caller; the current one is kept | `user_revoked_all` |
| `POST /auth/password/change` | every OTHER session of the user, and their current access tokens; the session that changed the password stays signed in | `password_change` |
| `POST /auth/password/reset`, hosted `POST /auth/reset-password-form` | EVERY session of the user, and their current access tokens; none is kept (the person resetting may be signed in nowhere). Strict: see below | `password_reset` |
| Session limit (`MAX_SESSIONS_PER_IDENTITY`) at sign-in | the oldest sessions over the limit; that device must sign in again | `session_limit` |
| `DELETE /sessions/{id}` by its owner | that session | `user_revoked` |
| `DELETE /sessions/{id}` by a platform admin (`is_admin`) | that session, whoever owns it | `admin_revoked` |
| Refresh-token reuse detected | the whole family | `family_revoked_security` |

**Password reset is strict and revokes first** (owner decision 2026-10-04,
"yes, go with all three recommendations"). The reset writes the revocation
list with strict Redis writes BEFORE the new password is committed, then
commits the revoked rows, the new password and the used reset link in one
transaction. If Redis cannot take a write, the reset answers `503` +
`Retry-After` and rolls back: the password, the link and the rows are
unchanged, and the same link works once Redis answers. So no moment exists in
which the new password is set and an old session still refreshes. (The
opposite order would leave the new password set with the old sessions live
whenever the revocation then failed.) A failure after the Redis writes and
before the commit leaves the user signed out with the old password and an
unused link: safe and retryable. After the commit the reset sweeps once more,
best-effort, for a session a concurrent sign-in with the old password
committed meanwhile.

`DELETE /sessions/{id}` answers 404 to anyone who is neither the owner nor a
platform admin (the same answer as for a session that does not exist), and 400
for a session already revoked. A revoked session leaves `GET /sessions`, and
the account chooser and account switching stop offering it, because they
accept only live rows.

### `POST /oauth/revoke` (RFC 7009)

- The client authenticates as at the token endpoint (HTTP Basic or form
  fields). A confidential client must present its secret; a public client
  identifies itself with `client_id`. Otherwise `401 invalid_client`.
- `token_type_hint` (`access_token` or `refresh_token`) only sets which kind
  is tried first. It is optional, and a wrong hint still works.
- A refresh token revokes its family: the `refresh_token` grant answers
  `400 invalid_grant` for it and for every token the family mints later.
- An access token is blacklisted by its `jti` until it expires.
  `/oauth/introspect` reports it `{"active": false}` and `/oauth/userinfo`
  answers 401. Relying parties that verify tokens offline against the JWKS
  cannot see a revocation; they rely on the short access-token lifetime or on
  introspection.
- An unknown, invalid or expired token, a token issued to another client, and
  a Janua session token (which belongs to no client) change nothing and answer
  `200` (RFC 7009 §2.2).
- When Redis cannot store the revocation the answer is `503` + `Retry-After`,
  never a `200` for a revocation that did not happen.
