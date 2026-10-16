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
    An explicit ``organization_id`` must name an active membership. Without
    selection, emitted only when unambiguous — exactly one active membership,
    or ``user.tenant_id`` names one of them. Ambiguity emits ``orgs`` alone;
    consumers must not guess a tenant. This is deliberate: guessing a primary
    org for a multi-org user is how one tenant's operator reads another
    tenant's payroll.

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
  unambiguous primary org gets ``orgs`` and no ``roles``, for the same reason
  they get no ``org_id``.
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

Without explicit selection, a failure emits no org claims (the existing
fail-closed contract). An explicit selection instead raises
``InvalidOrganizationSelection`` on invalid or unverifiable membership: a
caller must refuse that grant, never fall back to a different organization.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, OrganizationMember, User
from app.models.app_role import OrganizationMemberAppRole, format_app_role

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


class InvalidOrganizationSelection(ValueError):
    """An explicit organization must never degrade to another membership."""


async def get_user_org_claims(
    user: User, db: AsyncSession, *, organization_id: str | None = None
) -> dict[str, Any]:
    """Resolve organization claims for a human token.

    Returns a dict ready to merge into a JWT payload. Empty when the user has
    no active membership, or when resolution fails, unless ``organization_id``
    was explicitly selected. Selection requires that active membership and
    raises on failure; it never changes ``user.tenant_id`` or any membership.

    Memberships with status other than ``active`` (pending/inactive/removed)
    never contribute — a removed member must not keep tenant access through a
    long-lived refresh chain.
    """
    if organization_id is not None:
        try:
            organization_id = str(UUID(organization_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidOrganizationSelection("Invalid organization selection") from exc
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
        if organization_id is not None:
            raise InvalidOrganizationSelection("Organization membership could not be verified") from e
        return {}

    if not rows:
        if organization_id is not None:
            raise InvalidOrganizationSelection("No active membership in the selected organization")
        return {}

    claims: dict[str, Any] = {
        "orgs": [
            {"id": str(org.id), "slug": org.slug, "role": member.role or "member"}
            for member, org in rows
        ]
    }

    primary_member = None
    primary = None
    if organization_id is not None:
        for member, org in rows:
            if str(org.id) == organization_id and member.status == "active":
                primary_member, primary = member, org
                break
        if primary is None:
            raise InvalidOrganizationSelection("No active membership in the selected organization")
    elif len(rows) == 1:
        primary_member, primary = rows[0]
    else:
        tenant_id = getattr(user, "tenant_id", None)
        if tenant_id:
            tenant_id = str(tenant_id)
            for member, org in rows:
                if str(org.id) == tenant_id:
                    primary_member, primary = member, org
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
        # one (selected or automatically resolved) there is no single membership to read grants from, and picking
        # any of several would hand one tenant's HR authority to a session the
        # user opened for another.
        if primary_member is not None:
            app_roles = await _get_member_app_roles(primary_member, db)
            if app_roles:
                claims[APP_ROLES_KEY] = app_roles

    return claims


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
      the UNION: every string existing clients read today, plus the namespaced
      application roles. Nothing is removed from an established claim.

    Always pops the private transport key, so ``APP_ROLES_KEY`` can never reach
    a token. Returns a NEW dict; the input is not mutated.
    """
    merged = dict(claims)
    app_roles = merged.pop(APP_ROLES_KEY, None) or []

    if not app_roles and not existing_roles:
        # Nothing to say. Emit no `roles` key at all rather than an empty list,
        # so a user with no grants gets a token shaped exactly as before.
        return merged

    combined = list(existing_roles or [])
    for role in app_roles:
        if role not in combined:
            combined.append(role)

    merged[APP_ROLES_CLAIM] = combined
    return merged


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
    "merge_app_roles_into_claims",
]
