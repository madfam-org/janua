"""
OIDC Discovery Service

Implements OpenID Connect Discovery 1.0 specification for automatic
provider configuration from discovery endpoints.

Reference: https://openid.net/specs/openid-connect-discovery-1_0.html

SECURITY NOTE: This service makes HTTP requests to external OIDC providers.
All URLs are validated against SSRF attacks before any requests are made.
See _validate_hostname_ssrf() for the SSRF protection implementation.
"""

import ipaddress
import socket
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import httpx
from datetime import datetime, timedelta


class OIDCDiscoveryService:
    """
    OpenID Connect Discovery service.

    Fetches and parses provider configuration from well-known endpoints.
    Caches discovery documents for performance.

    SECURITY: All external URLs are validated against SSRF attacks before
    HTTP requests are made. This includes blocking:
    - Localhost and loopback addresses
    - Private network ranges (10.x.x.x, 172.16-31.x.x, 192.168.x.x)
    - Link-local addresses (169.254.x.x)
    - Cloud metadata endpoints (169.254.169.254)
    """

    # Standard OIDC discovery path
    DISCOVERY_PATH = "/.well-known/openid-configuration"

    # Cache TTL for discovery documents (1 hour)
    DISCOVERY_CACHE_TTL = 3600

    # SECURITY: Blocked hostname patterns for SSRF protection
    _BLOCKED_HOSTNAMES = frozenset(["localhost", "127.0.0.1", "::1", "0.0.0.0"])

    # SECURITY: Cloud metadata endpoint IPs to block
    _CLOUD_METADATA_IPS = frozenset(["169.254.169.254", "169.254.170.2"])

    def __init__(self, cache_service=None):
        """
        Initialize discovery service.

        Args:
            cache_service: Optional cache service for discovery document caching
        """
        self.cache_service = cache_service
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    async def discover_configuration(
        self, issuer: str, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Discover OIDC provider configuration from issuer.

        Args:
            issuer: OIDC issuer URL (e.g., https://accounts.google.com)
            force_refresh: Force refresh even if cached

        Returns:
            OIDC provider configuration dictionary with:
            - issuer: The issuer URL
            - authorization_endpoint: OAuth 2.0 authorization endpoint
            - token_endpoint: OAuth 2.0 token endpoint
            - userinfo_endpoint: OIDC userinfo endpoint
            - jwks_uri: JSON Web Key Set document location
            - response_types_supported: Supported response types
            - subject_types_supported: Supported subject types
            - id_token_signing_alg_values_supported: Supported signing algorithms
            - scopes_supported: Supported OAuth 2.0 scopes
            - claims_supported: Supported claims
            - ... (additional optional fields)

        Raises:
            ValueError: If issuer is invalid or discovery fails

        SECURITY: Issuer URL is validated against SSRF before any HTTP request.
        """
        # SECURITY: Validate issuer URL before any network operations
        self._validate_issuer(issuer)

        # Check cache first
        if not force_refresh:
            cached = await self._get_cached_config(issuer)
            if cached:
                return cached

        # Fetch discovery document (URL already validated via _validate_issuer)
        discovery_url = self._build_discovery_url(issuer)
        config = await self._fetch_discovery_document(discovery_url)

        # Validate configuration
        self._validate_configuration(config)

        # Cache configuration
        await self._cache_configuration(issuer, config)

        return config

    async def discover_from_url(
        self, discovery_url: str, force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Discover OIDC configuration from explicit discovery URL.

        Args:
            discovery_url: Full discovery URL (e.g., https://example.com/.well-known/openid-configuration)
            force_refresh: Force refresh even if cached

        Returns:
            OIDC provider configuration dictionary

        Raises:
            ValueError: If discovery URL is invalid or fetch fails

        SECURITY: Discovery URL is validated against SSRF before any HTTP request.
        """
        # Extract issuer from URL for caching
        parsed = urlparse(discovery_url)
        issuer = f"{parsed.scheme}://{parsed.netloc}"

        # SECURITY: Validate the discovery URL before making request
        self._validate_discovery_url(discovery_url)

        # Check cache
        if not force_refresh:
            cached = await self._get_cached_config(issuer)
            if cached:
                return cached

        # Fetch discovery document (URL already validated above)
        config = await self._fetch_discovery_document(discovery_url)

        # Validate configuration
        self._validate_configuration(config)

        # Cache configuration
        await self._cache_configuration(issuer, config)

        return config

    def extract_provider_config(
        self,
        discovery_config: Dict[str, Any],
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Extract provider configuration suitable for OIDC protocol.

        Args:
            discovery_config: Full discovery document
            client_id: OAuth 2.0 client ID
            client_secret: OAuth 2.0 client secret
            redirect_uri: OAuth 2.0 redirect URI
            scopes: Optional list of scopes (default: openid, profile, email)

        Returns:
            Configuration dictionary for OIDCProtocol
        """
        return {
            # Required fields
            "issuer": discovery_config["issuer"],
            "client_id": client_id,
            "client_secret": client_secret,
            "authorization_endpoint": discovery_config["authorization_endpoint"],
            "token_endpoint": discovery_config["token_endpoint"],
            "redirect_uri": redirect_uri,
            # Optional fields
            "userinfo_endpoint": discovery_config.get("userinfo_endpoint"),
            "jwks_uri": discovery_config.get("jwks_uri"),
            "revocation_endpoint": discovery_config.get("revocation_endpoint"),
            "end_session_endpoint": discovery_config.get("end_session_endpoint"),
            # Scopes
            "scopes": scopes or ["openid", "profile", "email"],
            # Supported features
            "response_types_supported": discovery_config.get("response_types_supported", []),
            "subject_types_supported": discovery_config.get("subject_types_supported", []),
            "id_token_signing_alg_values_supported": discovery_config.get(
                "id_token_signing_alg_values_supported", ["RS256"]
            ),
            "scopes_supported": discovery_config.get("scopes_supported", []),
            "claims_supported": discovery_config.get("claims_supported", []),
        }

    def _validate_issuer(self, issuer: str) -> None:
        """
        Validate issuer URL format.

        SECURITY: Includes SSRF protection to prevent requests to internal networks.
        This MUST be called before any HTTP request using the issuer URL.
        """
        if not issuer:
            raise ValueError("Issuer is required")

        if not issuer.startswith(("http://", "https://")):
            raise ValueError("Issuer must be a valid HTTPS URL")

        parsed = urlparse(issuer)
        if not parsed.netloc:
            raise ValueError("Invalid issuer URL")

        # SECURITY: SSRF protection - block internal network access
        self._validate_hostname_ssrf(parsed.hostname)

        # Production should use HTTPS
        if issuer.startswith("http://"):
            import warnings

            warnings.warn(
                "Using HTTP for OIDC discovery in production is insecure. Use HTTPS.", UserWarning
            )

    def _validate_discovery_url(self, url: str) -> None:
        """
        Validate discovery URL for SSRF protection.

        SECURITY: Prevents Server-Side Request Forgery attacks.
        This MUST be called before any HTTP request using the URL.
        """
        if not url:
            raise ValueError("Discovery URL is required")

        if not url.startswith(("http://", "https://")):
            raise ValueError("Discovery URL must be a valid HTTP(S) URL")

        parsed = urlparse(url)
        if not parsed.netloc:
            raise ValueError("Invalid discovery URL")

        # SECURITY: SSRF protection - block internal network access
        self._validate_hostname_ssrf(parsed.hostname)

        # Production should use HTTPS
        if url.startswith("http://"):
            import warnings

            warnings.warn(
                "Using HTTP for OIDC discovery in production is insecure. Use HTTPS.", UserWarning
            )

    def _validate_hostname_ssrf(self, hostname: Optional[str]) -> None:
        """
        Validate hostname against SSRF attacks.

        SECURITY: Blocks requests to internal networks, localhost, and cloud metadata endpoints.

        This is the core SSRF protection mechanism. It validates:
        1. Hostname is not in blocked list (localhost, 127.0.0.1, etc.)
        2. Resolved IP addresses are not in private/internal ranges
        3. Cloud metadata endpoints (169.254.169.254) are blocked

        Raises:
            ValueError: If hostname resolves to a blocked address
        """
        if not hostname:
            raise ValueError("Invalid URL: missing hostname")

        # Block localhost variants
        if hostname.lower() in self._BLOCKED_HOSTNAMES:
            raise ValueError("SSRF protection: localhost URLs are not allowed")

        # Resolve hostname and check for private IPs
        try:
            ip_addresses = socket.getaddrinfo(hostname, None)
            for family, _, _, _, sockaddr in ip_addresses:
                ip_str = sockaddr[0]
                ip_obj = ipaddress.ip_address(ip_str)

                # Block private, loopback, link-local, and reserved ranges
                if (
                    ip_obj.is_private
                    or ip_obj.is_loopback
                    or ip_obj.is_link_local
                    or ip_obj.is_reserved
                ):
                    raise ValueError(
                        "SSRF protection: URLs resolving to internal networks are not allowed"
                    )

                # Specifically block cloud metadata endpoints
                if ip_str in self._CLOUD_METADATA_IPS:
                    raise ValueError("SSRF protection: cloud metadata endpoints are not allowed")
        except socket.gaierror:
            # DNS resolution failed - this is acceptable for validation
            # The actual HTTP request will fail if the hostname doesn't resolve
            pass
        except ValueError as e:
            if "SSRF protection" in str(e):
                raise
            # Other ValueError from ip_address parsing - continue validation

    def _build_discovery_url(self, issuer: str) -> str:
        """Build discovery URL from issuer."""
        # Remove trailing slash
        issuer = issuer.rstrip("/")

        # Add discovery path
        return f"{issuer}{self.DISCOVERY_PATH}"

    async def _fetch_discovery_document(self, url: str) -> Dict[str, Any]:
        """
        Fetch discovery document from URL.

        SECURITY: This method MUST only be called after URL validation via
        _validate_discovery_url() or _validate_issuer() to prevent SSRF attacks.
        The URL is re-validated here as defense-in-depth.

        Args:
            url: The discovery URL to fetch (must be pre-validated)

        Returns:
            Parsed JSON configuration dictionary

        Raises:
            ValueError: If fetch fails or document is invalid
        """
        # SECURITY: Defense-in-depth - re-validate URL before making request
        # This ensures SSRF protection even if caller forgets to validate
        parsed = urlparse(url)
        if parsed.hostname:
            self._validate_hostname_ssrf(parsed.hostname)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # SECURITY: URL has been validated against SSRF via _validate_hostname_ssrf()
                # which blocks localhost, private networks, and cloud metadata endpoints.
                # This request is safe because:
                # 1. _validate_issuer() or _validate_discovery_url() was called by the caller
                # 2. Defense-in-depth: _validate_hostname_ssrf() is called again above
                response = await client.get(  # noqa: S113 - SSRF protection applied above
                    url,
                    headers={"Accept": "application/json"},
                    follow_redirects=False,  # SECURITY: Don't follow redirects to prevent SSRF bypass
                )

                if response.status_code != 200:
                    raise ValueError(
                        f"Discovery endpoint returned {response.status_code}: {response.text}"
                    )

                config = response.json()

                if not isinstance(config, dict):
                    raise ValueError("Discovery document must be a JSON object")

                return config

        except httpx.HTTPError as e:
            raise ValueError(f"Failed to fetch discovery document: {str(e)}")
        except ValueError:
            # Re-raise ValueError as-is (includes our custom errors)
            raise
        except Exception as e:
            raise ValueError(f"Error parsing discovery document: {str(e)}")

    def _validate_configuration(self, config: Dict[str, Any]) -> None:
        """
        Validate OIDC configuration has required fields.

        Per OpenID Connect Discovery 1.0 specification, required fields are:
        - issuer
        - authorization_endpoint
        - token_endpoint
        - jwks_uri
        - response_types_supported
        - subject_types_supported
        - id_token_signing_alg_values_supported
        """
        required_fields = [
            "issuer",
            "authorization_endpoint",
            "token_endpoint",
            "jwks_uri",
            "response_types_supported",
            "subject_types_supported",
            "id_token_signing_alg_values_supported",
        ]

        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            raise ValueError(
                f"Discovery document missing required fields: {', '.join(missing_fields)}"
            )

        # Validate endpoint URLs
        for endpoint_field in ["authorization_endpoint", "token_endpoint", "jwks_uri"]:
            endpoint = config.get(endpoint_field)
            if endpoint and not endpoint.startswith(("http://", "https://")):
                raise ValueError(f"Invalid URL for {endpoint_field}: {endpoint}")

    async def _get_cached_config(self, issuer: str) -> Optional[Dict[str, Any]]:
        """Get cached configuration if available and not expired."""
        cache_key = f"oidc_discovery:{issuer}"

        # Try cache service first
        if self.cache_service:
            try:
                cached = await self.cache_service.get(cache_key)
                if cached:
                    return cached
            except Exception:
                pass  # Cache service failure falls through to memory cache

        # Try memory cache
        if issuer in self._memory_cache:
            cached_data = self._memory_cache[issuer]
            expires_at = cached_data.get("_expires_at")

            if expires_at and datetime.fromisoformat(expires_at) > datetime.utcnow():
                # Remove cache metadata before returning
                config = {k: v for k, v in cached_data.items() if not k.startswith("_")}
                return config
            else:
                # Expired, remove from cache
                del self._memory_cache[issuer]

        return None

    async def _cache_configuration(self, issuer: str, config: Dict[str, Any]) -> None:
        """Cache discovery configuration."""
        cache_key = f"oidc_discovery:{issuer}"
        expires_at = datetime.utcnow() + timedelta(seconds=self.DISCOVERY_CACHE_TTL)

        # Add expiration to config
        cached_config = {**config, "_expires_at": expires_at.isoformat()}

        # Store in cache service
        if self.cache_service:
            try:
                await self.cache_service.set(
                    cache_key,
                    config,  # Don't cache expiration metadata in external cache
                    ttl=self.DISCOVERY_CACHE_TTL,
                )
            except Exception:
                pass  # Cache service failure falls back to memory cache

        # Always store in memory cache as fallback
        self._memory_cache[issuer] = cached_config

    async def clear_cache(self, issuer: Optional[str] = None) -> None:
        """
        Clear discovery cache.

        Args:
            issuer: Optional issuer to clear. If None, clears all cached configs.
        """
        if issuer:
            # Clear specific issuer
            cache_key = f"oidc_discovery:{issuer}"

            if self.cache_service:
                try:
                    await self.cache_service.delete(cache_key)
                except Exception:
                    pass  # Cache service delete failure is non-critical

            if issuer in self._memory_cache:
                del self._memory_cache[issuer]
        else:
            # Clear all
            if self.cache_service:
                # Can't easily clear all from cache service
                # This would require tracking all keys
                pass

            self._memory_cache.clear()
