# MAP email traceability

This is audit metadata, never a queue or permission to send. MAP's outgoing-click
hold remains in force. Magic-link login and user-initiated password recovery are the auth exceptions.
Do not send real emails or hosted-auth synthetics to validate this change.

Apply reviewed operator SQL `docs/ops/sql/021_map_email_traceability.sql` after
`020_org_authentication_policy`, before promoting the new API image. Production
promotion never runs Alembic; verify the actual schema/revision before updating
`PROD_ALEMBIC_STATE.json`. This source change does not advance that ledger. It adds
`email_send_audits`, nullable verified-event fields and payment-attempt metadata.
Existing records are not backfilled. Source rollback retains audit evidence.
A missing or unwritable audit store blocks MAP provider I/O.

## Exact joins

For a MAP magic-login request, Janua validates the destination, resolves its
active registered OAuth client and CTM organization, and creates a server UUID.
Caller `source_app`, request IDs and actor headers do not establish provenance.
The neutral 2xx auth response always has `X-Janua-Mail-Correlation-ID`, including
unknown/invite-only addresses; its presence does not prove issuance or delivery.
The response body is unchanged.

The request intent is durable before account lookup, so an audit outage cannot
produce different responses based on account existence. An unknown/invite-only
request becomes `not_issued`. For an actual send, the intent is linked to the
exact `magic_links.id` before scheduling. A request without that link cannot
enter the provider transport. Provider acceptance records its exact message ID;
`sending` without an acceptance receipt becomes `unknown`, never success.

MAP internal send/template calls may forward `X-MAP-Mail-Audit-ID` (a UUID).
Janua creates an intent for each actual message and retains that upstream ID.
The header is diagnostic metadata, not service identity, human identity or an
outgoing-click authorization. These calls are labelled
`authenticated_internal_claim`; only the MAP audit proves the actual human click.
For `source_app=crea-map`, raw/template send endpoints reject a missing or
malformed `X-MAP-Mail-Audit-ID` before creating an intent or calling a provider.
Native MAP payment mail also requires the UUID before every new provider attempt,
including a due retry of a legacy pending command. Accepted receipt and backoff
reads that do not contact the provider remain readable without the header. The
first valid attempt ID is retained; later clicks never rewrite a prior receipt.
This is a mandatory audit join, not proof of human permission: MAP must still
verify the real outgoing click and durably record its actor/action before sending.
Magic login has server-derived canonical provenance and is unaffected.
Other source applications keep their current transport behavior.

Native payment mail retains its existing authenticated, organization-bound
`payment_mail_dispatches` intent and receipt. It records the first valid upstream
MAP audit UUID and tags the immutable payment command UUID. The changing UUID of
a later click is not added to the provider payload under an existing idempotency
key. Accepted replay continues to use its recorded provider receipt. A pending
legacy envelope whose new tag changes the hash stays in review; never replay it
automatically.

Provider webhook signatures are verified as before. Reserved correlation tags
are only exposed after matching a durable intent's source, organization and
provider ID; an unknown/mismatched tag does not create an audit relationship.
Verified sent/delivered events can reconcile a lost post-send receipt against an
already attempted intent. No audit row causes a retry.

## Additive event-feed fields

`GET /api/v1/internal/email/events?source_app=crea-map` retains its existing
`email_id`, event type, timestamps and cursor. Where a durable join is verified,
it adds:

- `mail_audit_id`: Janua intent UUID; for native payment mail, its receipt UUID.
- `map_audit_id`: valid upstream MAP attempt UUID, when supplied.
- `message_kind`: `magic_login`, `password_recovery`, `payment`, or the internal mail classification.
- `trigger_kind`: `map_login_request`, `map_password_recovery_request`, `payment_command`, or `internal_api`.
- `command_id`: native payment command UUID, where applicable.

Optional metadata is omitted for legacy/unmatched events. Accepted provider mail
and delivered mail remain different facts; delivery is proved by a verified
`delivered` event with the same provider message ID. Historical timestamp matches
are not retroactively upgraded to exact proof.

The new audit contains no address, message body, subject, redirect URL, login token
or provider credential. Existing MagicLink storage remains the identity authority;
diagnostics on audited paths use audit UUIDs and bounded error classes only.
Validation uses synthetic fixtures, SQLite and denied outbound networking.

## User-initiated password recovery

Password recovery is allowed for MAP alongside magic login. Use the registered
native client and a validated return origin, for example the hosted path
`/api/v1/auth/forgot-password?client_id=<native-client>&return_url=<encoded-MAP-origin-and-/api/auth/login>&ui_locales=es`.
The native registration must be active; the return origin must be HTTPS and match
a registered redirect origin. A live `auth_request_id` can bind the exact OAuth
transaction instead. Wrong or expired context fails closed, never falls back to
a generic identity pool. Form, retry and reset completion preserve that context.

Janua commits a neutral intent before identity lookup and links the exact private
`password_resets.id` before scheduling the task. Unknown/inactive/ambiguous users
produce `not_issued`; account absence cannot be inferred from the neutral 2xx
`X-Janua-Mail-Correlation-ID` or unchanged response body. The message is classified
`password_recovery` / `map_password_recovery_request` /
`registered_map_recovery`, then joins the exact provider receipt and verified
webhook events like magic login. A missing/unwritable audit fails before provider
I/O. Neither password-reset IDs nor tokens appear in the audit DTO or logs.

Public recovery creates its own canonical Janua intent. It needs neither a MAP
logged-in actor nor the business-send `X-MAP-Mail-Audit-ID`. A password-reset
transport with a MAP destination and no live audited issuance still fails closed.
Welcome, account creation, email verification and scheduler mail are not auth
exceptions and cannot inherit this context. Generic Janua/other-product recovery
is unchanged; shared CTM organization membership alone is never MAP provenance.

## Read metadata without SQL

`GET /api/v1/internal/email/audit` uses the existing internal-key authentication.
Supply `org_id` (UUID), `source_app`, `from` and `to` (aware UTC timestamps), an
optional `folio` UUID and `limit` (1–200). The positive window is at most seven
days and selects `requested_at`, with an exclusive upper bound. A folio matches
the canonical audit UUID, upstream MAP attempt UUID or native payment command.
The response echoes the validated organization/application binding.

`summary.total`, `provider_accepted`, `verified_sent` and `verified_delivered`
cover every recorded intent in that bounded scope, even when `records` is
limited. `has_more` says when to narrow the window or look up an exact folio.
Provider acceptance and verified delivery remain separate facts. Sent/delivery
proof is observed through `observed_through`, including later delivery of a
request in the selected window. `window_applies_to=requested_at` labels this
request-based scope.

Separately, `provider_events_in_window` selects verified provider `occurred_at`
inside the same UTC window. Its `verified_sent` and `verified_delivered` count
distinct provider message IDs with an exact recorded intent join, including
intents requested before `from`. `events_for_older_intents` counts matching
sent/delivered event rows for those older intents; it is an event count, not an
additional message count. The organization, source and optional folio filters
apply to both scopes. An older request delivered inside the window increases the
provider delivery count without increasing `summary.total` or adding a request
record. No timestamp proximity is used to establish message identity.

`coverage=recorded_intents_only_no_backfill` and
`history_complete=false` are always explicit: an empty page never proves zero
historical mail. Unknown/rejected records without a recorded completion time
return null `resolved_at`.

The endpoint returns an allowlisted metadata DTO, never a recipient, subject,
body, login token, redirect URL or MagicLink capability. PostgreSQL queries use a
read-only repeatable snapshot and a five-second statement timeout. A database,
key or unavailable endpoint is an error, never an invented empty audit.

Production and training login provenance uses the active native registration's
exact MAP redirect host. A platform-pool registration may have no organization;
that does not invent a tenant identity pool. The mail organization is resolved
from Janua's server-owned sender binding after the destination is verified.
