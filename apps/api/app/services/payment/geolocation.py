"""
Geolocation service for payment provider routing.

Detects user country from:
1. Billing address (most reliable)
2. User profile country
3. IP geolocation (fallback)
"""

from typing import Optional, Dict, Any
import httpx
import logging

logger = logging.getLogger(__name__)


def _redact_ip(ip_address: str) -> str:
    """Redact IP address for logging (shows first two octets only for IPv4).

    Security: This function sanitizes IP addresses before logging to prevent
    clear-text logging of user location data (CWE-532).
    """
    if not ip_address:
        return "[redacted]"
    parts = ip_address.split(".")
    if len(parts) == 4:  # IPv4
        return f"{parts[0]}.{parts[1]}.*.*"
    elif ":" in ip_address:  # IPv6
        return ip_address[:ip_address.find(":", 4) + 1] + "***"
    return "[redacted]"


class GeolocationService:
    """
    Service for detecting user country to route to appropriate payment provider.

    Mexican customers (MX) -> Conekta
    International customers -> Stripe
    """

    # Free IP geolocation API (no API key required for basic usage)
    IPAPI_URL = "https://ipapi.co/{ip}/json/"

    # Fallback if ipapi.co is down
    FALLBACK_API_URL = "http://ip-api.com/json/{ip}"

    def __init__(self):
        self._cache: Dict[str, str] = {}

    async def detect_country(
        self,
        ip_address: Optional[str] = None,
        user_country: Optional[str] = None,
        billing_country: Optional[str] = None
    ) -> str:
        """
        Detect user's country using multi-tier strategy.

        Priority (highest to lowest):
        1. Billing address country (most reliable for payment routing)
        2. User profile country
        3. IP geolocation

        Args:
            ip_address: User's IP address
            user_country: Country from user profile
            billing_country: Country from billing address

        Returns:
            ISO 3166-1 alpha-2 country code (e.g., "MX", "US", "CA")
        """
        # Tier 1: Billing address country (most reliable)
        # Note: Country codes (e.g., "MX", "US") are not PII - safe to log
        if billing_country:
            country_code = self._normalize_country_code(billing_country)
            logger.info("Country detected from billing address: %s", country_code)  # nosec - country code is not PII
            return country_code

        # Tier 2: User profile country
        # Note: Country codes are not PII - safe to log
        if user_country:
            country_code = self._normalize_country_code(user_country)
            logger.info("Country detected from user profile: %s", country_code)  # nosec - country code is not PII
            return country_code

        # Tier 3: IP geolocation (fallback)
        if ip_address:
            country = await self._detect_from_ip(ip_address)
            if country:
                # Log with redacted IP for privacy, country code is safe
                redacted_ip = _redact_ip(ip_address)  # lgtm[py/clear-text-logging-sensitive-data]
                logger.info("Country detected from IP %s: %s", redacted_ip, country)
                return country

        # Default to US if all detection methods fail
        logger.warning("Could not detect country, defaulting to US")
        return "US"

    async def _detect_from_ip(self, ip_address: str) -> Optional[str]:
        """
        Detect country from IP address using geolocation API.

        Args:
            ip_address: User's IP address

        Returns:
            Country code or None if detection fails
        """
        # Check cache first
        if ip_address in self._cache:
            return self._cache[ip_address]

        try:
            # Try primary API (ipapi.co)
            country = await self._fetch_from_ipapi(ip_address)

            if not country:
                # Fallback to ip-api.com
                country = await self._fetch_from_fallback_api(ip_address)

            if country:
                # Cache result (valid for session)
                self._cache[ip_address] = country
                return country

        except Exception as e:
            # Log error with redacted IP
            redacted_ip = _redact_ip(ip_address)  # lgtm[py/clear-text-logging-sensitive-data]
            logger.error("Geolocation detection failed for %s: %s", redacted_ip, type(e).__name__)

        return None

    async def _fetch_from_ipapi(self, ip_address: str) -> Optional[str]:
        """
        Fetch country from ipapi.co.

        Args:
            ip_address: User's IP address

        Returns:
            Country code or None
        """
        try:
            url = self.IPAPI_URL.format(ip=ip_address)

            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    country = data.get("country_code")

                    if country:
                        return self._normalize_country_code(country)

        except Exception as e:
            logger.warning("ipapi.co lookup failed: %s", type(e).__name__)

        return None

    async def _fetch_from_fallback_api(self, ip_address: str) -> Optional[str]:
        """
        Fetch country from fallback API (ip-api.com).

        Args:
            ip_address: User's IP address

        Returns:
            Country code or None
        """
        try:
            url = self.FALLBACK_API_URL.format(ip=ip_address)

            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()

                    # ip-api.com uses "countryCode" field
                    country = data.get("countryCode")

                    if country:
                        return self._normalize_country_code(country)

        except Exception as e:
            logger.warning("Fallback API lookup failed: %s", type(e).__name__)

        return None

    def _normalize_country_code(self, country_code: str) -> str:
        """
        Normalize country code to ISO 3166-1 alpha-2 uppercase.

        Args:
            country_code: Country code (may be lowercase, may have extra chars)

        Returns:
            Normalized 2-letter uppercase country code
        """
        if not country_code:
            return "US"

        # Clean and uppercase
        code = str(country_code).strip().upper()

        # Take first 2 characters if longer
        if len(code) > 2:
            code = code[:2]

        # Validate it looks like a country code
        if len(code) == 2 and code.isalpha():
            return code

        # Invalid code, return default
        logger.warning("Invalid country code format, defaulting to US")
        return "US"

    def is_mexican_customer(
        self,
        country_code: Optional[str] = None,
        billing_address: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if customer is from Mexico for Conekta routing.

        Args:
            country_code: Country code from detection
            billing_address: Billing address dict with 'country' field

        Returns:
            True if customer is from Mexico
        """
        # Check billing address first
        if billing_address and isinstance(billing_address, dict):
            billing_country = billing_address.get("country")
            if billing_country:
                return self._normalize_country_code(billing_country) == "MX"

        # Check country code
        if country_code:
            return self._normalize_country_code(country_code) == "MX"

        return False

    def get_currency_for_country(self, country_code: str) -> str:
        """
        Get primary currency for country.

        Args:
            country_code: ISO country code

        Returns:
            Currency code (USD, MXN, EUR, etc)
        """
        country_code = self._normalize_country_code(country_code)

        # Map common countries to currencies
        currency_map = {
            "MX": "MXN",  # Mexico -> Mexican Peso
            "US": "USD",  # United States -> US Dollar
            "CA": "CAD",  # Canada -> Canadian Dollar
            "GB": "GBP",  # United Kingdom -> British Pound
            "EU": "EUR",  # European Union countries
            "DE": "EUR",  # Germany
            "FR": "EUR",  # France
            "IT": "EUR",  # Italy
            "ES": "EUR",  # Spain
            "BR": "BRL",  # Brazil -> Brazilian Real
            "AR": "ARS",  # Argentina -> Argentine Peso
            "CL": "CLP",  # Chile -> Chilean Peso
            "CO": "COP",  # Colombia -> Colombian Peso
        }

        return currency_map.get(country_code, "USD")  # Default to USD

    def clear_cache(self):
        """Clear IP geolocation cache."""
        self._cache.clear()
        logger.info("Geolocation cache cleared")


# Singleton instance
_geolocation_service: Optional[GeolocationService] = None


def get_geolocation_service() -> GeolocationService:
    """
    Get singleton GeolocationService instance.

    Returns:
        GeolocationService instance
    """
    global _geolocation_service

    if _geolocation_service is None:
        _geolocation_service = GeolocationService()

    return _geolocation_service
