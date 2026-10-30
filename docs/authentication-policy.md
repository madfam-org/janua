# Organization authentication policy

Implementation status: source prepared; no deployment, migration, permission
grant, or live policy activation is implied. Product release holds remain
independent.

## Passwords and magic links

The issuer owns passwords, recovery, TOTP enrollment and backup codes. A relying
party starts its existing authorization-code flow with PKCE S256 and state; it
may add `login_method=password` and `ui_locales=es`. Magic-link entry remains
available. Password creation uses the same contextual recovery flow as password
reset, without registering a second identity or changing organization membership.

Hosted primary-factor, recovery and MFA continuations resolve the identity pool
from a validated registered-client transaction. A matching email in a different
organization is never a fallback. Continuations bind the browser, user,
organization, client and return destination. Setup displays the actual signed-in
account and renders backup codes once. Recovery emails keep the selected locale.

Voluntary MFA enrollment is enforced across both entry methods, including when
the organization policy is optional. This supersedes the legacy
`MFA_ENFORCE_ON_LOGIN` bypass for enrolled users. Required organizations enroll
members who have no factor before issuing a session. JSON sign-in without an
enrolled factor cannot bypass a required policy; use the hosted enrollment flow.

TOTP time steps and challenges have atomic, shared replay protection. Backup
codes are hashed and consumed once. Removing a factor requires the current
password plus a TOTP or unused backup code, is refused under any required
membership policy, and strictly revokes existing sessions in the factor-change
transaction. Password reset also revokes existing sessions; it does not clear MFA.

## Technical-direction MFA floor

The product's real staff lifecycle synchronizes the reserved live grant
`crea-map:mfa-required` for active Dirección Tecnológica members. It confers no
administrative authority. Generic app administrators cannot grant or revoke it;
neither browser input, email domains, organization ownership nor token roles
are accepted as the live source. Grants are scoped to active memberships and
revocation history is retained in the existing app-role table; no new migration
is required for this requirement marker.

The shared issuer requirement check combines voluntary enrollment, the live
product-owned floor and the existing organization policy. Thus an optional team
policy never exempts technical-direction staff. Password and both magic-link
entry paths, SSO authorization, code exchange and refresh use that same check.
An unenrolled required member completes cookie-bound TOTP enrollment before a
session is created; an enrolled member must pass TOTP or a one-use backup code.
Factor disablement consults mandatory policy separately from voluntary enrollment
so optional staff may still remove their own factor safely.

MAP additionally checks signed session evidence against the real current staff
role on each identity resolution, before any view-as/act-as transformation. Weak
old sessions and failed initial synchronization cannot become a technical actor.
Production activation still requires the coordinated MAP/Janua deployment and
trusted roster reconciliation. This source change performs neither, issues no
emails and changes no billing release hold. Existing strong offline JWTs retain
their normal validity window; it does not add per-request remote introspection.

## Policy API

`GET /api/v1/organizations/{organization_id}/authentication-policy` requires a
strictly verified bearer and active membership. A missing row returns
`mfa_mode=optional`, `version=0` without writing. Database failures propagate;
they never silently turn enforcement off.

`PUT` accepts only `mfa_mode` (`optional` or `required`), `expected_version`
(nonnegative integer) and a nonblank bounded `reason`. The caller must be a live,
active human member with the explicit `crea-map:security-policy-admin` grant.
Organization ownership, platform administration, ordinary app administration,
internal keys and token role claims alone do not authorize a policy change.
Generic app-role delegation cannot grant or revoke this reserved role. Its
trusted provisioning lifecycle remains a separate operator/product concern.

Every change, including lowering enforcement, needs primary and MFA proof from
the caller's live session within five minutes. Enabling required MFA additionally
requires a currently enrolled factor. Invalid authentication returns 401;
insufficient authority 403; stale policy versions 409; missing recent proof or
enrollment 428. After 428, reauthenticate and review the policy again before
explicitly resubmitting. Never automatically replay a policy change.

Policy and append-only change history commit together with version comparison.
Actor, membership and grant locks serialize policy changes against revocation
and factor disablement. A concurrent save produces one winner and a conflict,
never two journal entries for the same version.

## Session proof and activation boundary

Authentication evidence (`amr`, `auth_time`, `mfa_time`, `sid`) is persisted on the
session and carried through code exchange and refresh. It must match a live,
unrevoked session. Refresh preserves original proof times; it cannot make an old
login recent or manufacture MFA. Policy is rechecked at authorization, consent,
code exchange and refresh, including protected-resource OAuth. Silent access
that needs interaction returns an OAuth interaction error.

Enforcement begins at the next issuer authorization or refresh. Already-issued
JWTs validated offline by a relying party remain valid until their expiration.
An immediate cutover requires a separately reviewed session-expiry strategy;
changing policy alone must not be represented as instant revocation.

## Schema and rollout

Migration `020_org_authentication_policy` adds policy/history tables and session
proof columns. Existing sessions receive an empty method list and null proof
times, without invented assurance. Upgrade is additive and reentrant. Source
rollback retains the schema and history; downgrade refuses while any policy is
required. The companion reviewed SQL is
[`ops/sql/020_organization_authentication_policy.sql`](ops/sql/020_organization_authentication_policy.sql).
It checks the expected ledger revision, bounds lock waits, and grants the
runtime only SELECT/INSERT on history. This file is not execution authorization;
use the approved Enclii migration adapter and keep release held if unavailable.

Acceptance order:

1. Review both issuer and relying-party source with product flags off.
2. In an isolated synthetic organization/client, apply the additive schema and
   test password creation/reset, magic links, TOTP setup, one-use backup codes,
   repeat submissions, disabled identities and rejected redirects. Do not send
   external mail or use clinical/production identities for testing.
3. Exercise optional → required → optional, stale-version conflicts, recent-MFA
   rejection, failure recovery and concurrent policy/role/factor operations.
   Confirm legacy weak sessions cannot refresh after required activation.
4. Verify the product's actual authority reconciliation and demotion/deactivation
   retirement; clones and simulation must have no production authority.
5. Obtain the product owner's activation window and agree on staff support for
   losing both authenticator and backup codes before live rollout. Initial
   organization policy remains optional until an authorized human changes it.

Focused API regressions use SQLite, real signed credentials and a Redis protocol
test double. PostgreSQL migration/CAS tests use an explicit isolated
`MIGRATION_TEST_DATABASE_URL`; CI's existing `database` selection runs them in
its PostgreSQL service. These checks do not replace hosted acceptance.
