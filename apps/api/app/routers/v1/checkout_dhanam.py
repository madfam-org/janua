"""
Dhanam Checkout Relay - federates checkout creation to Dhanam's billing API

Janua is identity-only (decision 2026-07-09, internal-devops
decisions/2026-07-09-avala-billing-gateway-alignment.md): checkout, PSP keys,
and the ledger belong to Dhanam. This endpoint is therefore a thin relay to
Dhanam's customer-federation API — the same pattern RouteCraft and Avala use:

1. User initiates an upgrade (Janua dashboard, or any MADFAM product that
   deep-links into Janua with a "{product}_{tier}" plan id).
2. Janua validates the organization + caller permissions.
3. Janua resolves/creates the Dhanam billing customer:
       POST {DHANAM_FEDERATION_URL}/v1/customers/resolve
       {"email": ..., "januaSub": ..., "name": ...} -> {"externalId", "created"}
4. Janua opens the checkout session:
       POST {DHANAM_FEDERATION_URL}/v1/customers/{externalId}/checkout
       {"planId": "janua_pro", "successUrl", "cancelUrl", "metadata"}
       -> {"checkoutUrl", "sessionId"}
   Both calls authenticate with `Authorization: Bearer {FEDERATION_API_TOKEN}`.
5. The client is redirected to Dhanam's ACTUAL hosted checkout URL (the PSP
   session URL) — not a synthetic Dhanam-frontend path.
6. After payment, Dhanam webhooks /api/v1/webhooks/dhanam/subscription and
   Janua updates organization.product_tiers[product] for JWT tier claims.

A local CheckoutSession row is kept as an audit record of the relay,
storing Dhanam's session/customer references.
"""

import json
import uuid as uuid_mod
from datetime import datetime
from typing import Optional
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models import CheckoutSession, Organization, OrganizationMember, User

# Re-use the ecosystem plan grammar from the webhooks module
from app.routers.v1.webhooks_dhanam import VALID_TIERS, parse_product_plan

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/checkout", tags=["billing"])

# Product slug for plans initiated from Janua's own dashboard. Bare tier ids
# ("pro") are qualified with this so Dhanam's PriceResolver resolves the
# janua/{tier} catalog entry instead of defaulting to the dhanam product.
JANUA_PRODUCT_SLUG = "janua"

# Billing period suffixes understood by both parse_product_plan() and Dhanam's
# PriceResolver.parseCatalogTier — preserved on the outbound catalog plan id.
BILLING_PERIOD_SUFFIXES = ("_monthly", "_annual", "_yearly")

# Per-request timeout for Dhanam federation calls (RouteCraft uses 8s).
DHANAM_FEDERATION_TIMEOUT_SECONDS = 10.0


class DhanamFederationError(Exception):
    """A Dhanam federation call failed (transport error or non-2xx response)."""

    def __init__(self, path: str, status_code: Optional[int], detail: str):
        self.path = path
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Dhanam federation {path} failed ({status_code}): {detail}")


class CreateCheckoutRequest(BaseModel):
    """Request to create a checkout session for Dhanam billing integration."""

    plan_id: str = Field(..., description="Plan ID (e.g., 'enclii_pro', 'pro' for janua/pro)")
    organization_id: UUID = Field(..., description="Janua organization ID to upgrade")
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if payment is cancelled")


class CheckoutSessionResponse(BaseModel):
    """Response with checkout session details."""

    checkout_url: str = Field(..., description="Dhanam-hosted checkout URL to redirect the user to")
    session_id: str = Field(..., description="Checkout session ID (Dhanam's session reference)")
    customer_id: Optional[str] = Field(
        None, description="Dhanam billing customer id (externalId) the checkout was created for"
    )
    provider: str = Field(
        ..., description="Billing gateway ('dhanam'; PSP selection happens in Dhanam)"
    )
    organization_id: str = Field(..., description="Organization ID being upgraded")
    plan_id: str = Field(..., description="Fully-qualified catalog plan ID sent to Dhanam")
    product: str = Field(..., description="Product being upgraded (janua, enclii, tezca, ...)")
    janua_tier: str = Field(..., description="Corresponding tier")


def _strip_billing_period(plan_id: str) -> tuple[str, str]:
    """Split a lowercased plan id into (core, billing-period suffix)."""
    normalized = plan_id.lower()
    for suffix in BILLING_PERIOD_SUFFIXES:
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)], suffix
    return normalized, ""


def build_catalog_plan_id(plan_id: str) -> tuple[str, Optional[str], str]:
    """Resolve (product, tier, dhanam_catalog_plan_id) for a checkout request.

    parse_product_plan() implements the ecosystem-wide plan grammar, but its
    bare-tier default (product="dhanam") is a webhook-side convention. A
    checkout reaching Janua's own API with an unqualified tier ("pro") was
    initiated from Janua's dashboard for the janua product, so bare tiers are
    qualified as "janua_{tier}" — the id Dhanam's PriceResolver parses back
    into (product="janua", tier). Billing-period suffixes are preserved so
    Dhanam still resolves the monthly/yearly interval.

    A bare legacy name ("scale", "enterprise", "sovereign") maps to another
    product's plan in the webhook grammar ("scale" -> dhanam/pro). From this
    checkout it would sell that product to a Janua buyer, so it resolves to no
    tier and the caller answers 400. Other products' plans must be qualified
    ("enclii_pro").
    """
    product, tier = parse_product_plan(plan_id)
    if tier is None:
        return product, None, ""
    core, suffix = _strip_billing_period(plan_id)
    if core in VALID_TIERS:
        product = JANUA_PRODUCT_SLUG
    elif "_" not in core and product != JANUA_PRODUCT_SLUG:
        return product, None, ""
    return product, tier, f"{product}_{tier}{suffix}"


def _federation_configured() -> bool:
    return bool(settings.DHANAM_FEDERATION_URL and settings.FEDERATION_API_TOKEN)


async def _dhanam_federation_post(path: str, payload: dict) -> dict:
    """POST to a Dhanam federation endpoint with the shared bearer token.

    Raises DhanamFederationError on transport failure, non-2xx status, or a
    non-JSON body. Request payloads are not logged (they carry identity data).
    """
    base_url = (settings.DHANAM_FEDERATION_URL or "").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=DHANAM_FEDERATION_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{base_url}{path}",
                json=payload,
                headers={"Authorization": f"Bearer {settings.FEDERATION_API_TOKEN}"},
            )
    except httpx.HTTPError as e:
        logger.error("Dhanam federation call failed", path=path, error=str(e))
        raise DhanamFederationError(path, None, str(e)) from e

    if response.status_code >= 400:
        logger.error(
            "Dhanam federation call rejected",
            path=path,
            status_code=response.status_code,
        )
        raise DhanamFederationError(path, response.status_code, response.text[:300])

    try:
        return response.json()
    except ValueError as e:
        logger.error("Dhanam federation returned non-JSON body", path=path)
        raise DhanamFederationError(path, response.status_code, "invalid JSON response") from e


def _map_resolve_error(error: DhanamFederationError) -> HTTPException:
    """Map a failed /v1/customers/resolve call to a client-facing error."""
    if error.status_code == status.HTTP_409_CONFLICT:
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This account's email is already linked to a different billing identity. "
                "Contact support to resolve the conflict."
            ),
        )
    if error.status_code == status.HTTP_403_FORBIDDEN:
        # Dhanam has FEDERATION_CUSTOMER_PROVISIONING_ENABLED off and no
        # existing customer matched — billing is not activated for this user.
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing customer provisioning is not enabled yet. Please try again later.",
        )
    return _map_transport_error(error)


def _map_transport_error(error: DhanamFederationError) -> HTTPException:
    """Map a transport failure / unexpected status to a client-facing error."""
    if error.status_code is None:
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing service is unreachable. Please try again later.",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Billing service rejected the checkout request. Please try again later.",
    )


@router.post("/dhanam", response_model=CheckoutSessionResponse)
async def create_dhanam_checkout(
    request_data: CreateCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a checkout session by relaying to Dhanam's federation API.

    This endpoint:
    1. Validates the plan, organization, and user permissions
    2. Resolves (or provisions) the Dhanam billing customer for the caller
    3. Creates the checkout session via Dhanam and returns Dhanam's actual
       hosted checkout URL
    4. Records a local CheckoutSession row for audit

    Fails closed with 503 when the federation relay is not configured
    (DHANAM_FEDERATION_URL / FEDERATION_API_TOKEN).
    """
    # Parse product and tier from plan_id; qualify bare tiers as janua/{tier}
    product, tier, catalog_plan_id = build_catalog_plan_id(request_data.plan_id)
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid plan_id: {request_data.plan_id}. Expected format: "
                f"'{{product}}_{{tier}}' where tier is one of {sorted(VALID_TIERS)}"
            ),
        )

    # Get the organization
    result = await db.execute(
        select(Organization).where(Organization.id == request_data.organization_id)
    )
    organization = result.scalar_one_or_none()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Organization not found: {request_data.organization_id}",
        )

    # Verify user has permission (must be owner or admin)
    is_owner = organization.owner_id == current_user.id

    if not is_owner:
        # Check if user is an admin member
        member_result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization.id,
                OrganizationMember.user_id == current_user.id,
                OrganizationMember.role.in_(["admin", "owner"]),
            )
        )
        member = member_result.scalar_one_or_none()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only organization owners and admins can initiate billing changes",
            )

    # Fail closed when the Dhanam relay is not configured — a synthetic
    # redirect would dead-end (Dhanam serves no /checkout/session/{id} route).
    if not _federation_configured():
        logger.error(
            "Dhanam federation relay not configured",
            missing_url=not settings.DHANAM_FEDERATION_URL,
            missing_token=not settings.FEDERATION_API_TOKEN,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured. Please contact support.",
        )

    # 1) Resolve — or provision — the Dhanam billing customer for the caller.
    #    Keyed on the Janua subject (JWT `sub` = user id) with email fallback.
    resolve_payload: dict = {
        "email": current_user.email,
        "januaSub": str(current_user.id),
    }
    if current_user.name:
        resolve_payload["name"] = current_user.name

    try:
        resolved = await _dhanam_federation_post("/v1/customers/resolve", resolve_payload)
    except DhanamFederationError as e:
        raise _map_resolve_error(e) from e

    external_id = resolved.get("externalId")
    if not external_id or not isinstance(external_id, str):
        logger.error("Dhanam resolve returned no externalId")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Billing service returned an invalid customer reference.",
        )

    # 2) Create the checkout session for the resolved customer. The metadata
    #    bag is threaded into the PSP session and flows back on Dhanam's
    #    webhooks, letting the org be credited (orgId is the key Dhanam's
    #    webhook processor reads; organization_id is Janua's webhook fallback).
    checkout_payload = {
        "planId": catalog_plan_id,
        "successUrl": request_data.success_url,
        "cancelUrl": request_data.cancel_url,
        "metadata": {
            "orgId": str(organization.id),
            "organization_id": str(organization.id),
            "organization_slug": organization.slug,
            "product": product,
            "janua_tier": tier,
        },
    }

    try:
        checkout = await _dhanam_federation_post(
            f"/v1/customers/{external_id}/checkout", checkout_payload
        )
    except DhanamFederationError as e:
        raise _map_transport_error(e) from e

    checkout_url = checkout.get("checkoutUrl")
    if not checkout_url or not isinstance(checkout_url, str):
        logger.error("Dhanam checkout returned no checkoutUrl")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Billing service did not return a checkout URL.",
        )

    # Dhanam may return an empty sessionId on some provider paths; keep a
    # local reference either way so the audit row has a unique key.
    dhanam_session_id = checkout.get("sessionId") or ""
    session_id = dhanam_session_id or f"checkout_{uuid_mod.uuid4().hex[:16]}"

    # 3) Record the relay for audit. Best-effort: the Dhanam session already
    #    exists, so a local persistence hiccup must not block the payment flow.
    try:
        checkout_session = CheckoutSession(
            session_id=session_id,
            organization_id=organization.id,
            user_id=current_user.id,
            price_id=catalog_plan_id,
            provider="dhanam",
            status="pending",
            session_metadata=json.dumps(
                {
                    "dhanam_customer_id": external_id,
                    "dhanam_session_id": dhanam_session_id,
                    "requested_plan_id": request_data.plan_id,
                    "product": product,
                    "janua_tier": tier,
                    "organization_slug": organization.slug,
                    "success_url": request_data.success_url,
                    "cancel_url": request_data.cancel_url,
                }
            ),
        )
        db.add(checkout_session)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(
            "Failed to persist checkout session audit row",
            session_id=session_id,
            organization_id=str(organization.id),
            error=str(e),
        )

    logger.info(
        "Created Dhanam federated checkout",
        session_id=session_id,
        organization_id=str(organization.id),
        organization_slug=organization.slug,
        requested_plan_id=request_data.plan_id,
        catalog_plan_id=catalog_plan_id,
        product=product,
        janua_tier=tier,
        dhanam_customer_created=bool(resolved.get("created")),
    )

    return CheckoutSessionResponse(
        checkout_url=checkout_url,
        session_id=session_id,
        customer_id=external_id,
        provider="dhanam",
        organization_id=str(organization.id),
        plan_id=catalog_plan_id,
        product=product,
        janua_tier=tier,
    )


@router.get("/session/{session_id}")
async def get_checkout_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get checkout session details.

    Allows Dhanam or other services to verify checkout session details.
    Only the user who created the session or org admins can access.
    """
    result = await db.execute(
        select(CheckoutSession).where(CheckoutSession.session_id == session_id)
    )
    checkout_session = result.scalar_one_or_none()

    if not checkout_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checkout session not found: {session_id}",
        )

    # Verify access (session owner or org admin)
    is_session_owner = checkout_session.user_id == current_user.id

    if not is_session_owner:
        # Check if user is org admin
        member_result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == checkout_session.organization_id,
                OrganizationMember.user_id == current_user.id,
                OrganizationMember.role.in_(["admin", "owner"]),
            )
        )
        member = member_result.scalar_one_or_none()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

    return {
        "session_id": checkout_session.session_id,
        "organization_id": str(checkout_session.organization_id),
        "price_id": checkout_session.price_id,
        "provider": checkout_session.provider,
        "status": checkout_session.status,
        "created_at": (
            checkout_session.created_at.isoformat() if checkout_session.created_at else None
        ),
    }


@router.post("/session/{session_id}/complete")
async def complete_checkout_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a checkout session as completed.

    Called by Dhanam after successful payment to update session status.
    The actual tier update happens via the webhook handler.

    Note: This endpoint should be protected by internal API key in production.
    """
    # In production, verify internal API key
    # For now, allow for testing

    result = await db.execute(
        select(CheckoutSession).where(CheckoutSession.session_id == session_id)
    )
    checkout_session = result.scalar_one_or_none()

    if not checkout_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Checkout session not found: {session_id}",
        )

    checkout_session.status = "completed"
    checkout_session.updated_at = datetime.utcnow()
    await db.commit()

    logger.info(
        "Checkout session completed",
        session_id=session_id,
        organization_id=str(checkout_session.organization_id),
    )

    return {"status": "completed", "session_id": session_id}
