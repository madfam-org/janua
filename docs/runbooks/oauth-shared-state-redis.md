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

## Health and readiness

- The readiness probe (`/api/v1/health/ready`) and `/ready` check Redis with a
  strict PING through **this process's own client**, the one requests use. They
  no longer open a fresh connection.
- Both report this pod's breaker as `redis_circuit`: `state`
  (`closed` / `open` / `half_open`), `last_failure_time`, `fallback_calls`,
  `strict_failures` and `client_initialized`. Hostnames, keys and error text are
  never included. `/api/v1/health/detailed` carries the same block under
  `checks.redis_circuit`. The full counters stay at `/api/v1/health/circuit-breaker`.
- **Readiness does not fail just because the breaker is open.** The replicas
  share one Redis, so a short blip opens every breaker at the same moment.
  Gating readiness on the breaker would remove every pod from the Service for
  the whole recovery window, which turns a blip into a sign-in outage. Readiness
  fails when this pod's own client cannot PING Redis. That covers a broken pod
  while Redis is fine, and it is what the probe already did for a Redis outage.
- A strict call that succeeds while the circuit is open moves the circuit to
  half-open. The readiness probe runs every 10 s, so a pod stops serving
  fallbacks within about one probe period after Redis answers again.

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

## Still on the fallback path (follow-ups)

These keys still use the breaker's fallback operations. Each needs its own
decision on fail-open versus fail-closed:

- `oauth:pre_login:<id>` **reads** in the hosted login and magic-link handlers.
  The write is strict. On a miss the readers rebuild the authorize URL from the
  client registration and lose `state` and PKCE.
- Refresh-token reuse detection: `blacklist:refresh:<jti>` uses `exists`. The
  fallback `0` means "not revoked", so detection fails open while Redis is
  unreachable.
- `JWTService` revocation and replay checks (`revoked:<jti>`, `blacklist:<jti>`,
  `revoked_user:<id>`, `used:refresh:<jti>`) fail open the same way. Its
  `jti:<type>:<jti>` registry fails the other way: a lost write when a token is
  minted makes that token unusable on every pod, and a fallback read rejects
  valid tokens.
- `user:valid:<id>` (`get_current_user`): a cached `valid` can outlive a
  deactivation by up to 5 minutes, and longer from the memory cache, which
  ignores TTLs.
- WebAuthn challenges (`passkeys.py`) and social-login `oauth_state:<state>`
  (`/oauth/{provider}`) are short-lived challenges. They have the same
  lost-write and stale-read shape as the consent CSRF token.
- The memory cache ignores TTLs for every key it holds.
