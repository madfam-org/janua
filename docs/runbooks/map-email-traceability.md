# MAP email traceability

This is audit metadata, never a queue or permission to send. MAP's outgoing-click
hold remains in force. Magic-link login is its sole automatic-mail exception.
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
- `message_kind`: `magic_login`, `payment`, or the internal mail classification.
- `trigger_kind`: `map_login_request`, `payment_command`, or `internal_api`.
- `command_id`: native payment command UUID, where applicable.

Optional metadata is omitted for legacy/unmatched events. Accepted provider mail
and delivered mail remain different facts; delivery is proved by a verified
`delivered` event with the same provider message ID. Historical timestamp matches
are not retroactively upgraded to exact proof.

The new audit contains no address, message body, subject, redirect URL, login token
or provider credential. Existing MagicLink storage remains the identity authority;
diagnostics on audited paths use audit UUIDs and bounded error classes only.
Validation uses synthetic fixtures, SQLite and denied outbound networking.
