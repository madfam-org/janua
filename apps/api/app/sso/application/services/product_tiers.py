"""Pure helpers for resolving Janua product-tier JWT claims."""

import re
from typing import Mapping, Optional

#: Per-product tier order, LOWEST FIRST, used only to decide between an
#: organization tier and a user-scoped grant for the same product (see
#: `pick_product_tier`). Janua carries no product's tier ladder today — the
#: ladders live in Dhanam's catalog, priced by Tulana — so this is empty and
#: the org tier wins whenever both exist. Add a product here only with its
#: ladder taken from the catalog, e.g. `"karafiel": ("contador", "consultor",
#: "despacho", "firma")`.
PRODUCT_TIER_ORDERS: Mapping[str, tuple[str, ...]] = {}

# Legacy Janua subscription_tier -> foundry_tier mapping (backwards compat)
LEGACY_TIER_MAP = {
    "community": "community",
    "free": "community",
    "pro": "sovereign",
    "sovereign": "sovereign",
    "scale": "ecosystem",
    "enterprise": "ecosystem",
    "ecosystem": "ecosystem",
}


def map_subscription_to_foundry_tier(subscription_tier: str | None) -> str:
    """Map Janua subscription_tier to Foundry tier for JWT claims.

    Legacy mapping kept for backwards compatibility during transition:
    - community/free -> community
    - pro/sovereign -> sovereign
    - scale/enterprise/ecosystem -> ecosystem
    """
    if not subscription_tier:
        return "community"
    return LEGACY_TIER_MAP.get(subscription_tier.lower(), "community")


def pick_product_tier(
    product: str,
    org_tier: Optional[str],
    user_tier: Optional[str],
    orders: Optional[Mapping[str, tuple[str, ...]]] = None,
) -> Optional[str]:
    """The tier one product's `{product}_tier` claim states (G1-1 precedence).

    Two sources can entitle the same person to the same product: the primary
    organization's `product_tiers` and the person's own active
    `user_entitlements` grant (a Dhanam purchase made without an org, or an
    admin grant). The rule:

    1. Only one source has a tier → that tier.
    2. Both, and the product has a tier order in `PRODUCT_TIER_ORDERS` that
       contains both tiers → the HIGHER of the two.
    3. Both, and no usable order (no ladder for the product, or a tier not on
       it) → the ORG tier. Without a ladder "higher" is a guess; the org tier
       is the one an organization admin set and can see.
    """
    if not org_tier:
        return user_tier or None
    if not user_tier:
        return org_tier
    order = (PRODUCT_TIER_ORDERS if orders is None else orders).get(product.lower())
    if order:
        ladder = [tier.lower() for tier in order]
        org_rank = ladder.index(org_tier.lower()) if org_tier.lower() in ladder else None
        user_rank = ladder.index(user_tier.lower()) if user_tier.lower() in ladder else None
        if org_rank is not None and user_rank is not None:
            return user_tier if user_rank > org_rank else org_tier
    return org_tier


def merge_product_tiers(
    org_tiers: Mapping[str, str] | None,
    user_tiers: Mapping[str, str] | None,
    orders: Optional[Mapping[str, tuple[str, ...]]] = None,
) -> dict[str, str]:
    """Per-product tiers after `pick_product_tier`, for every product either source names."""
    org = {str(k): str(v) for k, v in (org_tiers or {}).items() if v}
    user = {str(k): str(v) for k, v in (user_tiers or {}).items() if v}
    merged: dict[str, str] = {}
    for product in sorted(set(org) | set(user)):
        tier = pick_product_tier(product, org.get(product), user.get(product), orders)
        if tier:
            merged[product] = tier
    return merged


def product_tier_claim_key(product: str) -> Optional[str]:
    """`{product}_tier` with the product slug made claim-safe (`pravara-mes` → `pravara_mes_tier`).

    Same normalisation as the client-credentials claims in oauth_provider.py.
    """
    key = re.sub(r"[^a-z0-9_]", "_", str(product).lower())
    return f"{key}_tier" if key else None


def product_tier_claims(tiers: Mapping[str, str] | None) -> dict[str, str]:
    """`{product}_tier` claims for a human token, one per product with a tier."""
    claims: dict[str, str] = {}
    for product, tier in sorted((tiers or {}).items()):
        key = product_tier_claim_key(product)
        if key and tier:
            claims[key] = tier
    return claims


def resolve_product_tiers(
    product_tiers: dict | None,
    subscription_tier: str | None,
    user_tiers: Mapping[str, str] | None = None,
) -> dict:
    """Resolve per-product tier claims from organization data.

    Returns a dict of JWT claim keys to tier values. Products without a tier
    are omitted (absent claim = community/self-hosted, not billed).

    Args:
        product_tiers: JSONB dict from Organization.product_tiers
        subscription_tier: Legacy string from Organization.subscription_tier
        user_tiers: the user's active per-user grants, merged with the org
            tiers by `pick_product_tier` (G1-1)
    """
    tiers = merge_product_tiers(product_tiers, user_tiers) if user_tiers else (product_tiers or {})

    # Build per-product claims
    claims = {}

    # foundry_tier: backwards-compatible Enclii claim
    enclii_tier = tiers.get("enclii")
    if enclii_tier:
        # Map new tier names to legacy foundry_tier values for Enclii compat
        foundry_map = {"essentials": "community", "pro": "sovereign", "madfam": "ecosystem"}
        claims["foundry_tier"] = foundry_map.get(enclii_tier, enclii_tier)
    else:
        # Fall back to legacy subscription_tier mapping
        claims["foundry_tier"] = map_subscription_to_foundry_tier(subscription_tier)

    # Per-product claims: iterate ALL products in product_tiers.
    # Any product stored in the JSONB gets a JWT claim; no hardcoded list.
    for product, tier in tiers.items():
        if product == "enclii":
            continue  # Handled above via foundry_tier backwards-compat
        if tier:
            claims[f"{product}_tier"] = tier

    return claims
