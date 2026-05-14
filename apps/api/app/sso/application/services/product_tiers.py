"""Pure helpers for resolving Janua product-tier JWT claims."""

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


def resolve_product_tiers(product_tiers: dict | None, subscription_tier: str | None) -> dict:
    """Resolve per-product tier claims from organization data.

    Returns a dict of JWT claim keys to tier values. Products without a tier
    are omitted (absent claim = community/self-hosted, not billed).

    Args:
        product_tiers: JSONB dict from Organization.product_tiers
        subscription_tier: Legacy string from Organization.subscription_tier
    """
    tiers = product_tiers or {}

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
