"""Organization claims service — the SSOT for org/tenant/role token claims.

Computes the organization-membership claims that org-scoped resource servers
(symbiosis-hcm, and any future tenant-partitioned API) need in order to
authorize a caller at all. Every token-minting seam in janua — the OIDC
authorization-code grant, the OIDC refresh grant, `AuthService.create_session`
(magic link, password login, MFA completion, passkey) and
`AuthService.refresh_tokens` — resolves these claims *here*, not locally.

This module exists because the resolver used to live inline in
``routers/v1/oauth_provider.py``, which made it structurally unreachable from
the session path: a magic-link token carried no ``org_id`` at all, so
symbiosis-hcm answered 403 to every CTM team member who arrived through the
MAP's «Mi espacio (RH)» link. Two hand-maintained copies of a claim resolver
drift, and a drifted authorization claim fails either closed (someone stops
working) or open (someone gains a tenant) — so there is exactly one copy, and
the OIDC router imports it.

Claim contract
--------------

``orgs``
    Every ACTIVE membership as ``{id, slug, role}``. Omitted entirely when the
    user has none.

``org_id`` / ``tenant_id`` / ``org_slug``
    Emitted ONLY when unambiguous — exactly one active membership, or, among
    several, the one this rule picks, in this order:

    1. ``user.tenant_id`` names one of them (unchanged);
    2. else ``user.primary_organization_id`` names one of them — an
       organization an OPERATOR chose through the internal API
       (``routers/v1/internal_primary_organization.py``, migration 022).

    A primary organization the user holds no ACTIVE membership in resolves to
    nothing: the pointer is checked against the same active-membership rows as
    everything else here, so a removed or suspended membership cannot be
    revived by it. Ambiguity emits ``orgs`` alone; consumers must not guess a
    tenant. This is deliberate: guessing a primary org for a multi-org user is
    how one tenant's operator reads another tenant's payroll. The explicit
    primary organization is not a guess — it is a recorded operator decision,
    on the audit trail, that a person can be asked about.

    ``tenant_id`` is NOT how an operator sets a primary organization: it is the
    email-uniqueness pool the identity lives in (see
    ``routers/v1/internal_users.py``), and pointing it at an organization for
    staff once made magic link and password reset unable to find them.

``madfam_org_roles``
    The user's organization roles (``owner`` / ``admin`` / ``member``) for the
    resolved primary org, under a namespace that says *which* authority issued
    them. **This is not, and must never be read as, an application role.**

``roles`` (application roles)
    ``"<app>:<role>"`` strings such as ``hcm:hr``, granted explicitly per
    organization member (``organization_member_app_roles``, migration 016).
    Emitted ONLY for the resolved primary org's own membership, and omitted
    entirely when there are no live grants. See the next section.

Application roles, and why they are the other half of the namespacing fix
-------------------------------------------------------------------------

Namespacing ``madfam_org_roles`` was right and it left a hole. symbiosis-hcm
authorizes on application roles read from ``roles`` — ``hcm:hr``, ``hcm:admin``,
``employee`` (``symbiosis-hcm/apps/api/core/permissions.py``) — and nothing in
janua emitted a single ``hcm:*`` string. So CTM's Dirección could hold a valid
membership, receive a token with a correct ``org_id``, and still be refused
every HR feature: membership answered *which tenant*, and nothing answered
*which product authority*.

The claim is populated from EXPLICIT GRANTS ONLY. There is no derivation from
``member.role``, no default set, and no mapping table that turns an org
``admin`` into an ``hcm:admin``. Any such rule would rebuild, by the back door,
precisely the org-role-to-payroll bridge the namespacing exists to prevent — an
account admin would gain HR authority as a side effect of being an account
admin. If someone is to read payroll, an operator granted it, and there is a row
saying who and when.

Three scoping rules the resolver holds:

* **Only the resolved primary org's membership contributes.** Grants are keyed
  by ``organization_member_id``, so the query starts from ONE membership row and
  structurally cannot reach another org's grants. A multi-org user with no
  unambiguous primary org (no ``tenant_id`` match and no operator-set primary
  organization they are an active member of) gets ``orgs`` and no ``roles``,
  for the same reason they get no ``org_id``.
* **Nothing is implicit for service accounts.** A service principal receives
  application roles on exactly the same terms as a person: those explicitly
  granted to its membership, and no others.
* **Revocation reaches a live session at refresh.** The query filters
  ``revoked_at IS NULL`` and every mint path re-resolves, so a revoked grant
  stops feeding the claim on the next rotation — the same property the
  ``status == "active"`` membership filter gives.

HOW THE CLAIM IS MERGED, and why the resolver does not return a ``roles`` key
itself. The OIDC path ALREADY emits a ``roles`` claim of its own — organization
roles, for clients that have read it for years, and it contains the bare string
``"admin"`` (``oauth_provider._get_user_entitlements``). In that handler
``**org_claims`` is spread AFTER ``"roles": entitlements["roles"]``, so a
``roles`` key coming out of this resolver would silently CLOBBER the legacy
claim — breaking existing consumers through nothing but dict ordering.

So the resolver returns application roles under the private key
``APP_ROLES_KEY``, and each minting seam merges them into ``roles`` explicitly:

* Session tokens (magic link, password, MFA, passkey) stamp application roles
  as ``roles`` and nothing else. A session token still carries NO organization
  role under that key — the invariant test in
  ``tests/unit/services/test_org_claims_service.py`` is unchanged and still
  passes, because what lands there is ``hcm:hr``, never ``admin``.
* The OIDC path UNIONS them onto the legacy list, so existing clients keep
  every string they read today and gain the namespaced application roles.

``merge_app_roles_into_claims`` below is that merge, written once so the two
seams cannot drift. Callers never see ``APP_ROLES_KEY`` in a token: the merge
pops it.

Why ``madfam_org_roles`` and not ``roles``
-----------------------------------------

The legacy ``roles`` claim (OIDC only) carries organization-membership roles —
``owner``/``admin``/``member`` — but its name promises nothing about the
namespace those strings live in. symbiosis-hcm read it as its HR role list, and
its ``HR_ROLES`` set contains the literal string ``"admin"``. So the moment
``org_id`` reached an HCM-bound token, every janua org *account* admin would
have become an HR admin over payroll and labour files. Sealing the org claim
without namespacing the role claim converts today's honest 403 into a payroll
leak.

Session tokens therefore stamp the namespaced ``madfam_org_roles`` and
**deliberately do NOT stamp a bare ``roles``**. A resource server that wants
org roles asks for them by their real name; a resource server that wants
application roles must source them from its own authority (HCM does exactly
this — see ``symbiosis-hcm/apps/api/core/permissions.py``). The OIDC path keeps
emitting ``roles`` unchanged for existing clients — this module adds the
namespaced claim alongside it, it does not remove anything.

Resolution never raises: a failure emits no org claims at all (fail-closed —
downstream org-scoped services reject, and never mis-scope).
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, OrganizationMember, User
from app.models.app_role import APP_ROLE_SEPARATOR, OrganizationMemberAppRole, format_app_role

logger = structlog.get_logger()

#: Namespaced claim key for organization-membership roles. Namespaced on
#: purpose: see the module docstring. Do not rename without a coordinated
#: change in every consumer — the name IS the contract about the authority.
ORG_ROLES_CLAIM = "madfam_org_roles"

#: The claim key application roles ultimately ride under. This is the name
#: symbiosis-hcm reads (`core/permissions.py`) and it is NOT ours to choose.
APP_ROLES_CLAIM = "roles"

#: PRIVATE transport key. `get_user_org_claims` returns resolved application
#: roles under this name, never under `roles` — the OIDC handler spreads the
#: claims dict AFTER its own `"roles": entitlements["roles"]`, so a `roles` key
#: here would clobber the legacy organization-role claim by dict ordering
#: alone. `merge_app_roles_into_claims` pops it, so it never reaches a token.
APP_ROLES_KEY = "_app_roles"


async def get_user_org_claims(user: User, db: AsyncSession) -> dict[str, Any]:
    """Resolve organization claims for a human token.

    Returns a dict ready to merge into a JWT payload. Empty when the user has
    no active membership, or when resolution fails.

    Memberships with status other than ``active`` (pending/inactive/removed)
    never contribute — a removed member must not keep tenant access through a
    long-lived refresh chain.
    """
    try:
        result = await db.execute(
            select(OrganizationMember, Organization)
            .join(
                Organization,
                Organization.id == OrganizationMember.organization_id,
            )
            .where(
                OrganizationMember.user_id == user.id,
                OrganizationMember.status == "active",
            )
        )
        rows = result.all()
    except Exception as e:
        logger.warning(
            "Failed to fetch org claims, omitting from token",
            user_id=str(user.id),
            error=str(e),
        )
        try:
            await db.rollback()
        except Exception:  # pragma: no cover - defensive; rollback may itself fail
            pass
        return {}

    if not rows:
        return {}

    claims: dict[str, Any] = {
        "orgs": [
            {"id": str(org.id), "slug": org.slug, "role": member.role or "member"}
            for member, org in rows
        ]
    }

    primary_member = None
    primary = None
    if len(rows) == 1:
        primary_member, primary = rows[0]
    else:
        # Among several ACTIVE memberships, the first explicit pointer that
        # names one of them wins: the identity pool (`tenant_id`, unchanged),
        # then the operator-set primary organization. Both are matched against
        # `rows`, which holds active memberships only, so a pointer to an
        # organization the user is not an active member of matches nothing and
        # the user stays ambiguous — fail closed, exactly as before.
        for pointer in (
            getattr(user, "tenant_id", None),
            _explicit_primary_organization_id(user),
        ):
            if not pointer:
                continue
            pointer = str(pointer)
            for member, org in rows:
                if str(org.id) == pointer:
                    primary_member, primary = member, org
                    break
            if primary is not None:
                break

    if primary is not None:
        claims.update(
            {
                "org_id": str(primary.id),
                "tenant_id": str(primary.id),
                "org_slug": primary.slug,
                # Namespaced. NOT `roles`. See module docstring: HCM's HR_ROLES
                # contains "admin", so an org-account admin landing in a bare
                # `roles` claim would read as an HR admin over payroll.
                ORG_ROLES_CLAIM: [(primary_member.role if primary_member else None) or "member"],
            }
        )

        # Application roles ride ONLY with an unambiguous primary org. Without
        # one there is no single membership to read grants from, and picking
        # any of several would hand one tenant's HR authority to a session the
        # user opened for another.
        if primary_member is not None:
            app_roles = await _get_member_app_roles(primary_member, db)
            if app_roles:
                claims[APP_ROLES_KEY] = app_roles

    return claims


def _explicit_primary_organization_id(user: Any) -> Any:
    """The operator-set primary organization on the user row, or ``None``.

    Read from the user object every minting seam already loaded, like
    ``tenant_id`` — no extra query. Any failure to read it (an object without
    the attribute, an expired instance that cannot lazy-load in an async
    session) is ``None``: no pointer, so a multi-org user stays ambiguous, which
    is today's behaviour, never a guessed organization and never a failed login.
    """
    try:
        return getattr(user, "primary_organization_id", None)
    except Exception as e:  # pragma: no cover - defensive; attribute load failure
        logger.warning(
            "Failed to read primary organization, treating as unset",
            user_id=str(getattr(user, "id", None)),
            error=str(e),
        )
        return None


async def _get_member_app_roles(member: Any, db: AsyncSession) -> list[str]:
    """Live application-role grants for ONE membership, as ``"<app>:<role>"``.

    Keyed by ``organization_member_id``, so this cannot reach another
    organization's grants even if asked to — the cross-org leak is prevented by
    the shape of the query, not by a filter someone could drop.

    Degrades to ``[]`` on any read failure, matching the fail-closed rule the
    rest of this module holds: an unreachable grants table (a database that has
    not yet had migration 016 applied by hand, per the deploy note) yields a
    token with no application roles — today's behaviour exactly — never a token
    with guessed ones, and never a failed login.
    """
    member_id = getattr(member, "id", None)
    if member_id is None:
        return []

    try:
        result = await db.execute(
            select(OrganizationMemberAppRole)
            .where(
                OrganizationMemberAppRole.organization_member_id == member_id,
                # Retired grants stop contributing on the very next mint, which
                # is what makes a revocation reach a live session at refresh.
                OrganizationMemberAppRole.revoked_at.is_(None),
            )
            .order_by(
                OrganizationMemberAppRole.app,
                OrganizationMemberAppRole.role,
            )
        )
        grants = result.scalars().all()
    except Exception as e:
        logger.warning(
            "Failed to fetch application roles, omitting from token",
            member_id=str(member_id),
            error=str(e),
        )
        try:
            await db.rollback()
        except Exception:  # pragma: no cover - defensive; rollback may itself fail
            pass
        return []

    # Deduplicated and sorted so the claim is stable across mints: a token whose
    # role list reorders between refreshes is a diff that means nothing and that
    # someone will eventually try to debug.
    return sorted({format_app_role(g.app, g.role) for g in grants if g.app and g.role})


def merge_app_roles_into_claims(
    claims: dict[str, Any],
    *,
    existing_roles: list[str] | None = None,
) -> dict[str, Any]:
    """Fold resolved application roles into the public ``roles`` claim.

    Written once and used by BOTH minting seams so they cannot drift about what
    ``roles`` means:

    * Session tokens pass no ``existing_roles``: what lands under ``roles`` is
      application roles alone. A session token still carries no ORGANIZATION
      role under that key — the strings are ``hcm:hr``, never ``admin`` — so
      the invariant that motivated the ``madfam_org_roles`` namespace holds
      unchanged.
    * The OIDC path passes its legacy organization-role list, and the result is
      the UNION: every bare organization role existing clients read today, plus
      the namespaced application roles. The one thing removed from the legacy
      list is an organization role SHAPED like an application role, which was
      never a grant (see `is_application_role_shaped`).

    Always pops the private transport key, so ``APP_ROLES_KEY`` can never reach
    a token. Returns a NEW dict; the input is not mutated.
    """
    merged = dict(claims)
    app_roles = merged.pop(APP_ROLES_KEY, None) or []

    if not app_roles and not existing_roles:
        # Nothing to say. Emit no `roles` key at all rather than an empty list,
        # so a user with no grants gets a token shaped exactly as before.
        return merged

    # The legacy list is ORGANIZATION roles, which organizations name themselves.
    # One shaped like an application role is dropped HERE as well as where the
    # OIDC handler builds the list (`organization_roles_for_roles_claim`): this
    # helper is the one place both minting seams agree on what `roles` means,
    # so the rule "a string with the separator comes only from a grant" holds
    # for every caller, including one that hands in an unfiltered list.
    # `roles` is still written when everything was dropped: the OIDC handler
    # spreads this dict over its own `"roles"` key, and an absent key would let
    # the unfiltered list through.
    combined = [role for role in (existing_roles or []) if not is_application_role_shaped(role)]
    for role in app_roles:
        if role not in combined:
            combined.append(role)

    merged[APP_ROLES_CLAIM] = combined
    return merged


def is_application_role_shaped(role: str | None) -> bool:
    """True when an ORGANIZATION role string could be read as an application role.

    A resource server reads ``roles`` and authorizes on ``<app>:<role>``
    (``hcm:hr``, ``hcm:admin``). It cannot
    tell where a string came from, so the separator is what makes a string an
    application role, exactly as it is for the grant routes
    (`schemas/app_role.py`: "authority fabricated by punctuation").
    """
    return bool(role) and APP_ROLE_SEPARATOR in str(role)


def organization_roles_for_roles_claim(
    membership_roles: Any, *, user_id: Any = None
) -> list[str]:
    """The organization role strings the OIDC path may put under ``roles``.

    Organization roles are named by an organization's own admins: the custom
    role routes accept any name, and a member's role is a free string. The
    OIDC path publishes those strings under ``roles`` NEXT TO real
    application-role grants (`merge_app_roles_into_claims`). So an admin of
    any organization could name a role ``hcm:admin``, assign it to
    themselves, sign in through a client, and present a token no resource
    server can tell from one carrying an audited grant.

    The rule that closes it: **a string containing the separator reaches
    ``roles`` only from a live `OrganizationMemberAppRole` grant.** An
    organization role string shaped like one is never published. Bare strings
    (``owner``, ``admin``, ``member``, ``employee``, a custom ``Support``) are
    published as before; nothing else about the legacy claim changes.

    Dropped strings are logged, by name and without the user's other claims,
    because the person holding one loses an authority they may have relied on:
    the remedy is an application-role grant (`routers/v1/internal_app_roles.py`).
    """
    published: set[str] = set()
    for role in membership_roles:
        if not role:
            continue
        if is_application_role_shaped(role):
            logger.warning(
                "Organization role shaped like an application role was not published "
                "under `roles`; grant the application role instead",
                user_id=str(user_id) if user_id is not None else None,
                organization_role=str(role),
            )
            continue
        published.add(role)
    return list(published)


async def get_user_org_claims_safe(user: User, db: AsyncSession) -> dict[str, Any]:
    """`get_user_org_claims` that can never raise, for the session-mint path.

    Org claims enrich a session; they must never be able to block a login.
    ``get_user_org_claims`` already degrades its own DB reads, and this guard
    covers anything unexpected above them — matching how the entitlement claim
    is resolved in ``AuthService.create_session``.
    """
    try:
        return await get_user_org_claims(user, db)
    except Exception:  # pragma: no cover - defensive; never fail login on this
        logger.warning(
            "Failed to resolve org claims for session token; stamping none",
            user_id=str(user.id),
        )
        return {}


__all__ = [
    "APP_ROLES_CLAIM",
    "APP_ROLES_KEY",
    "ORG_ROLES_CLAIM",
    "get_user_org_claims",
    "get_user_org_claims_safe",
    "is_application_role_shaped",
    "merge_app_roles_into_claims",
    "organization_roles_for_roles_claim",
]
