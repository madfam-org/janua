"""Client grant types and scopes, the data API scope and service-client claims.

Split out of `app/routers/v1/oauth_provider.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_oauth_provider_shared.get_redis`), so one
patch target reaches every caller.
"""

import re
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.device_clients import DEVICE_ONLY_SCOPES, is_device_client_id
from app.models import OAuthClient, Organization
from app.routers.v1 import oauth_provider_shared as _oauth_provider_shared
from app.services.org_claims_service import ORG_ROLES_CLAIM

#: What a client with no stored ``grant_types`` / ``allowed_scopes`` may use.
DEFAULT_CLIENT_GRANT_TYPES = ("authorization_code", "refresh_token")


DEFAULT_CLIENT_SCOPES = ("openid", "profile", "email")


def _client_grant_types(client: OAuthClient) -> set:
    """The grant types the token endpoint honours for ``client``.

    The stored value is taken as-is (``set(value)``), falling back to the
    defaults when it is empty. Only a JSON array of names names a grant.
    `scripts/audit_client_credentials_tier_claims.py` carries a copy; its
    tests fail if the two drift.
    """
    return set(client.grant_types or DEFAULT_CLIENT_GRANT_TYPES)


def _client_allowed_scopes(client: OAuthClient) -> set:
    """The scopes a token grant may request for ``client`` (same rules as above).

    A device-only scope (`core/device_clients.DEVICE_ONLY_SCOPES`) counts only
    for a client of kind ``device``: whatever an ordinary client's row holds,
    no grant gives it one.
    """
    allowed = set(client.allowed_scopes or DEFAULT_CLIENT_SCOPES)
    if not is_device_client_id(getattr(client, "client_id", None)):
        allowed -= DEVICE_ONLY_SCOPES
    return allowed


def _parse_requested_scopes(scope: Optional[str], client: OAuthClient) -> str:
    """Return validated space-separated scopes for token grants."""
    allowed = _client_allowed_scopes(client)
    requested = set((scope or "").split())
    if not requested:
        requested = set(allowed)

    if not requested.issubset(allowed):
        denied = sorted(requested - allowed)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid_scope: {', '.join(denied)}",
        )

    return " ".join(sorted(requested))


#: Standard OIDC identity scopes an END-USER grant may always carry, whatever
#: the client's stored ``allowed_scopes``. They confer nothing beyond the
#: person's own identity — the ID token already carries ``email``/``name`` and a
#: refresh token is issued without ``offline_access`` — so honouring them keeps
#: every existing sign-in working even for a client whose stored list omits
#: one (``offline_access`` is not in ``DEFAULT_CLIENT_SCOPES``). Not used by the
#: client_credentials grant.
USER_GRANT_IDENTITY_SCOPES = frozenset({"openid", "profile", "email", "offline_access"})


def _narrow_to_allowed_scopes(scope: Optional[str], client: OAuthClient) -> tuple[str, list[str]]:
    """Narrow an END-USER grant's scope to what ``client`` may hold.

    The authorization-code and refresh grants carry a scope a person approved
    for a client. That scope may never contain anything outside the client's
    ``allowed_scopes`` (``_client_allowed_scopes``, the client_credentials
    allowlist) plus ``USER_GRANT_IDENTITY_SCOPES``. RFC 6749 §3.3 lets the authorization server
    "fully or partially ignore the scope requested"; the token response's
    ``scope`` field then tells the client what was actually granted.

    Returns ``(granted, dropped)``:

    * ``granted`` is the input UNCHANGED (byte for byte) when every requested
      scope is allowed — so a client that only asks for what it is registered
      for sees exactly the token it saw before. Otherwise it is the allowed
      subset, space-joined in request order with duplicates removed. An empty
      request stays empty (nothing to narrow, nothing to widen).
    * ``dropped`` lists the refused scopes (sorted, de-duplicated) for logging.

    Callers decide what an empty result means for their grant (see
    ``_require_grantable_scope``). The client_credentials grant keeps using
    ``_parse_requested_scopes``, which rejects instead of narrowing.
    """
    requested = (scope or "").split()
    allowed = _client_allowed_scopes(client) | USER_GRANT_IDENTITY_SCOPES
    dropped = sorted({s for s in requested if s not in allowed})
    if not dropped:
        return scope or "", []
    kept: list[str] = []
    for s in requested:
        if s in allowed and s not in kept:
            kept.append(s)
    return " ".join(kept), dropped


def _require_grantable_scope(scope: Optional[str], client: OAuthClient, *, grant: str) -> str:
    """``_narrow_to_allowed_scopes`` plus the one case narrowing cannot answer.

    A NON-EMPTY request of which nothing is allowed has no partial grant to
    fall back to, so it is refused with ``invalid_scope`` (``ValueError``; the
    caller maps it to a redirect or a 400 as its endpoint requires). Dropped
    scopes are logged, never silently discarded.
    """
    granted, dropped = _narrow_to_allowed_scopes(scope, client)
    if dropped:
        _oauth_provider_shared.logger.warning(
            "oauth.scope_not_allowed_for_client",
            grant=grant,
            client_id=client.client_id,
            dropped_scopes=dropped,
            granted_scope=granted,
        )
    if (scope or "").split() and not granted:
        raise ValueError(f"invalid_scope: {', '.join(dropped)}")
    return granted


# The scope a relying party requests to receive a PostgREST-shaped token — the
# BaaS/data-API seam (enclii managed-Postgres addons). Opt-in per client: it only
# takes effect when the client has it in `allowed_scopes` AND requests it, so
# every existing token is byte-for-byte unchanged. See `_data_api_claims`.
DATA_API_SCOPE = "data-api"


# The single scalar Postgres role PostgREST maps to `SET LOCAL ROLE` for an
# authenticated end-user. Deliberately the conventional Supabase/PostgREST value
# so a tenant's existing PostgREST/RLS setup and `@supabase/*` clients work as-is.
DATA_API_ROLE = "authenticated"


def _data_api_claims(scope: str, client: OAuthClient, org_claims: dict) -> dict:
    """Extra claims that make a token consumable by an enclii data-API (PostgREST).

    Returns `{}` unless the granted scope includes ``data-api`` (which requires
    the client to have that scope allowed) — so this is a NO-OP for every token
    that does not opt in, and no existing MADFAM/ecosystem token changes shape.

    When opted in, two claims are added:
      * ``role`` — the SCALAR PostgREST needs for ``SET LOCAL ROLE`` (Janua's
        other tokens carry ``roles`` as an ARRAY of app-RBAC roles, which
        PostgREST cannot use). Set to ``authenticated``.
      * ``tenant_id`` — bound to the CLIENT's organization when it has one
        (`OAuthClient.organization_id`), so a data-API addon registered for a
        tenant always scopes to that tenant's rows under RLS, regardless of how
        many orgs the end-user belongs to. Falls back to the ambiguity-resolved
        ``tenant_id`` from `org_claims` when the client is not org-bound.
    """
    if DATA_API_SCOPE not in set(scope.split()):
        return {}
    claims: dict = {"role": DATA_API_ROLE}
    if client.organization_id is not None:
        claims["tenant_id"] = str(client.organization_id)
    elif org_claims.get("tenant_id"):
        claims["tenant_id"] = org_claims["tenant_id"]
    return claims


def _service_account_email(client: OAuthClient) -> str:
    """Derive a stable non-human email claim for machine clients."""
    slug = re.sub(r"[^a-z0-9-]+", "-", (client.name or "").lower()).strip("-")
    slug = slug or "service-account"
    return f"{slug}@service.auth.madfam.io"


#: Shape of a namespaced application role, `"<app>:<role>"` — the vocabulary
#: symbiosis-hcm reads (`hcm:hr`, `hcm:admin`, `hcm:employee`) and the same
#: shape `models/app_role.format_app_role` produces for a human's grant. Janua
#: validates SHAPE, never MEANING: it holds no table of valid apps and no
#: vocabulary of role names, exactly as it holds none for capability-link
#: scopes. A new HCM role must not require a janua deploy.
APP_ROLE_SCOPE_PATTERN = re.compile(r"^[a-z][a-z0-9-]*:[a-z][a-z0-9_-]*$")


#: Organization-MEMBERSHIP roles. These describe authority over the janua
#: ACCOUNT (inviting a colleague, rotating a secret, paying the invoice) and
#: must never authorize anything inside a product. They ride under the
#: namespaced `madfam_org_roles` claim and are refused here even if an operator
#: writes one into `allowed_scopes` — symbiosis-hcm's `HR_ROLES` set contains
#: the literal string `"admin"`, so an org role reaching a bare `roles` claim is
#: precisely the payroll leak the namespace exists to prevent.
ORG_MEMBERSHIP_ROLE_SCOPES = frozenset({"owner", "admin", "member"})


def _service_client_app_roles(client: OAuthClient, granted_scopes: set[str]) -> list[str]:
    """Namespaced application roles a machine token may carry, from its grant.

    THE GRANT FOR A SERVICE CLIENT IS ITS ``allowed_scopes``. A person's
    application roles come from `organization_member_app_roles` (migration 016),
    keyed by a membership row; a service client has no membership, so the
    operator-controlled column that already says what this client may ask for is
    the grant record. Nothing here is derived, defaulted, or inferred: a role
    reaches a service token because an operator put that exact string in
    `allowed_scopes` AND the client requested it.

    Four conditions, all required:

    1. **The client is org-bound** (`organization_id` is set). A service without
       a tenant must not carry tenant authority — its token has no `org_id` to
       scope the role to, so an `hcm:hr` on it would be authority over *every*
       tenant HCM happens to ask about. Fail-closed: no org, no app roles.
    2. **The scope was REQUESTED.** Least privilege survives: a client allowed
       `hcm:hr` that asks only for `openid` gets a token that cannot read
       payroll. (`_parse_requested_scopes` has already refused anything outside
       `allowed_scopes`, and defaults an empty request to the full allowed set.)
    3. **The scope is allowed** on the client. Belt-and-braces with (2): this
       function never reads a string the operator did not grant, even if a
       future caller reaches it with an unvalidated scope list.
    4. **The scope has the namespaced app-role SHAPE** and is not an
       organization-membership role nor a bare/`*:admin` legacy alias. The
       legacy aliases keep their existing underscore treatment in the caller
       (`hcm:admin` → `hcm_admin`) so no live consumer changes shape.

    Emitted VERBATIM, colon kept, because the resource server matches the exact
    string it publishes. Deduplicated and sorted so a token's role list is
    stable across mints — a claim that reorders between refreshes is a diff that
    means nothing and that someone will eventually try to debug.
    """
    if not client.organization_id:
        return []

    allowed = set(client.allowed_scopes or [])
    roles = set()
    for requested_scope in granted_scopes:
        if requested_scope not in allowed:
            continue
        if requested_scope in ORG_MEMBERSHIP_ROLE_SCOPES:
            continue
        if requested_scope.endswith(":admin"):
            # Legacy alias territory. The caller already emits the underscore
            # form (`hcm_admin`) for these and has done for every existing
            # consumer; minting the colon form here as well would quietly widen
            # what an established `*:admin` scope authorizes.
            continue
        if not APP_ROLE_SCOPE_PATTERN.match(requested_scope):
            continue
        roles.add(requested_scope)

    return sorted(roles)


async def _get_client_credentials_claims(
    client: OAuthClient,
    scope: str,
    db: AsyncSession,
) -> dict:
    """Build downstream-compatible claims for a machine OAuth client."""
    requested_scopes = set(scope.split())
    scoped_products = {
        requested_scope.split(":", 1)[0]
        for requested_scope in requested_scopes
        if ":" in requested_scope
    }
    roles = ["service_account"]
    if "admin" in requested_scopes:
        roles.append("admin")
    for requested_scope in requested_scopes:
        if requested_scope.endswith(":admin"):
            roles.append(requested_scope.replace(":", "_"))

    # Namespaced application roles from the client's grant (`allowed_scopes`).
    # ADDITIVE: every string above is still emitted, so no existing consumer
    # sees a claim change shape. See `_service_client_app_roles` for why the
    # grant is `allowed_scopes` and why a client with no `organization_id`
    # receives none of these.
    app_roles = _service_client_app_roles(client, requested_scopes)
    roles.extend(app_roles)

    claims = {
        "client_id": client.client_id,
        "scope": scope,
        "token_use": "client_credentials",
        "actor_type": "service_account",
        "roles": sorted(set(roles)),
        "is_admin": "admin" in requested_scopes,
        "tier": "community",
        "sub_status": "active",
        # NAMESPACED organization roles, consistent with session and OIDC
        # tokens. A machine principal holds no organization MEMBERSHIP, so the
        # only truthful thing to say about its account authority is what it is:
        # a service account. Application roles go ONLY in `roles`; putting one
        # here would tell a consumer that the janua account granted it, which
        # is exactly the conflation `madfam_org_roles` was namespaced to stop
        # (see `services/org_claims_service.py`, «Why madfam_org_roles and not
        # roles»).
        ORG_ROLES_CLAIM: ["service_account"],
    }

    # Product tier claims (`<product>_tier`) state an entitlement, and
    # downstream tier gates authorize on them. Two sources:
    #
    # - a client registered by a platform admin is MADFAM's own service
    #   account: each product it holds a namespaced scope for gets the
    #   `madfam` tier, so it can reach that product's gated operations
    #   without a human session;
    # - every client bound to an organization gets that organization's
    #   `product_tiers` (applied below, and they win over the above).
    #
    # Any other client gets no tier claim for a product its organization is
    # not entitled to. Consumers read an absent claim as their lowest
    # authenticated tier.
    if scoped_products and await _oauth_provider_shared.client_registered_by_platform_admin(
        db, client
    ):
        for product in scoped_products:
            claim_key = re.sub(r"[^a-z0-9_]", "_", str(product).lower())
            if claim_key:
                claims[f"{claim_key}_tier"] = "madfam"

    if client.organization_id:
        org_result = await db.execute(
            select(Organization).where(Organization.id == client.organization_id)
        )
        org = org_result.scalar_one_or_none()
        if org:
            org_id = str(org.id)
            claims.update(
                {
                    "org_id": org_id,
                    "tenant_id": org_id,
                    "org_slug": org.slug,
                    "tier": org.subscription_tier or "community",
                    "product_tiers": org.product_tiers or {},
                }
            )
            for product, product_tier in (org.product_tiers or {}).items():
                claim_key = re.sub(r"[^a-z0-9_]", "_", str(product).lower())
                if claim_key:
                    claims[f"{claim_key}_tier"] = product_tier

    return claims
