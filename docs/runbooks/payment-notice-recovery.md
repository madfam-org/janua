# Recoverable payment notices

`POST /api/v1/email/payment-notices` is an opt-in service boundary for the
single-recipient `map/pago-confirmado` template. It records provider acceptance,
not inbox delivery, a bank transfer, fiscal issuance, or family billing. Existing
internal-key mail routes retain their current behavior. This endpoint sends real
mail when enabled; local tests replace the provider and use synthetic data.

## Authority and request

Use a dedicated confidential, active Janua OAuth client bound to the native
organization, with audience `janua-email`, grant type `client_credentials`, and
native `allowed_scopes` grant `crea-map:payment-mail`. Provision through the
approved Enclii/operator custody path. Reuse the native OAuth scope grant/revoke
surface; do not add a parallel grant registry or share the platform internal key
with this caller. The body cannot select an organization, sender, template,
provider account, subject, or arbitrary HTML.

The RS256 access token must carry the exact audience/issuer, client identity,
`sub=service-account:<client_id>`, organization, machine token/actor types, and
scope. An issued/expiry pair is required with a maximum one-hour lifetime. The
current client record is read and locked again when claiming a dispatch; token
claims alone cannot preserve a revoked grant. Revocation cannot recall a
provider operation already authorized and in flight.

Body fields are `command_id` (stable UUID), `recipient` (one email), `year`
(2000–2100), `month` (1–12), and optional integer `sessions` (0–100000). The source
application persists this minimal intent atomically with its own notification.
It retries the exact command and body, including after timeouts. It must never
mint a replacement command to bypass an uncertain outcome.

Responses include command and receipt UUIDs and one of:

- `accepted`: nonempty provider `message_id`; exact replay returns the original
  receipt even if the sender credential or provider is currently unavailable.
- `pending`: no success claim; retry the same intent after `retry_after` (UTC).
- `review`: automated attempts are permanently stopped for this command;
  preserve the receipt and reconcile the provider evidence before any new send.

An altered command body returns 409. Unauthorized/revoked clients return 403,
including accepted replay. Missing transport, binding, template or credential
returns 503 before a new claim. Validation failures return 422.

## Retry boundaries

The receipt ledger stores tenant/client/command identity, digests, timestamps,
attempt leases, and provider receipt IDs. It does not store recipient or body.
The provider key is a stable opaque hash of organization, client and command;
all attempts use the same envelope and `X-Message-ID`.

Resend retains idempotency keys for [24 hours](https://resend.com/changelog/idempotency-keys).
Automatic retries stop at 23 hours from the first persisted attempt, leaving a
one-hour margin. The deadline is checked after waiting for the shared account
lock and immediately before provider I/O. This is a bounded deduplication
contract, not an indefinite exactly-once guarantee. Provider failures and invalid
receipts remain unknown, never accepted. Backoff starts at one minute, doubles
to a 15-minute cap, and stops after ten claimed attempts. A three-minute lease
allows recovery after a crashed worker. The caller owns scheduling; Janua does
not store enough message content to dispatch autonomously.

Template/envelope, sender binding, or credential fingerprint drift moves an
uncertain command into review. Credentials are HMAC-fingerprinted with the
application secret; rotating that secret also stops uncertain retries. The
explicitly configured platform account is supported, but an unavailable tenant
or alternate credential cannot fall back to that account. Check/reconcile open
commands before account, credential, template, or application-secret changes.
Accepted replay remains available subject to current caller authorization.

A stale worker cannot overwrite a newer attempt. A late acceptance is preserved
as an audit event with only intent/attempt/provider IDs. `review` is terminal;
this slice provides no button or endpoint that erases or resets the evidence.
An authorized operator must use the approved provider/Enclii evidence path to
resolve uncertainty. Delivery/bounce tracking and broader billing mail are
separate work and must not be inferred from an accepted receipt.

## Migration, rollout and rollback

Apply additive revision `017_payment_mail_dispatch` through approved Enclii
migration custody before enabling the endpoint. It creates the receipt ledger
and PostgreSQL triggers for tenant integrity, immutable identity, monotonic
attempts, terminal evidence, and deletion/truncation refusal. Applying after
`create_all` is supported. An empty migration can be reversed; a populated
ledger deliberately refuses downgrade. Application rollback preserves evidence.

Follow Janua's staging deployment and 30-minute soak/manual production-promotion
policy. Enable the source outbox only after the scoped Janua route, native client
grant, migration and exact sender credential have been verified. No historical
bulk-mail backfill is authorized by this rollout. A live canary requires a
named, controlled recipient and explicit send authorization. Do not put identity
records, tokens, keys, email bodies or real recipient details in public logs or
PRs. Production correctness remains unverified until that rollout and canary.

## Verification

Unit tests exercise real RS256 tokens, native grant revocation, body constraints,
the real template renderer, exact replay, unknown receipts, drift, deadlines,
and shared-account locking. PostgreSQL tests exercise actual Alembic upgrade,
empty downgrade/re-upgrade, duplicate first claims, concurrent leases, rollback,
late workers, lost receipt commits, tenant mismatch and database evidence guards.
The dedicated CI step runs against the disposable PostgreSQL service.

For local PostgreSQL proof set `LOCAL_DB=yes` and
`JANUA_MAIL_TEST_DATABASE_URL` to a loopback `postgresql+asyncpg` URL for a
dedicated database whose name ends in `_test`, then run:

```sh
pytest tests/unit/services/test_payment_mail_postgres.py --no-cov
```

Each test creates and drops only its randomly named fixture schema. Keep the URL
in the local environment; do not copy credentials into docs. Run the normal full
API suite too; this focused proof does not replace its coverage requirement.
