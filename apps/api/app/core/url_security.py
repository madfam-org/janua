"""
URL Security Utilities for Janua

This module provides URL validation functions to prevent open redirect vulnerabilities
(CWE-601) and other URL-based attacks.

SECURITY: All redirect URLs must be validated before use to prevent attackers from
redirecting users to malicious sites after authentication.
"""

import fnmatch
from urllib.parse import urlparse
from typing import Optional

import structlog

from app.config import settings

logger = structlog.get_logger()

# Default allowed redirect hosts for the Janua ecosystem
# These are the base domains that are always safe to redirect to
DEFAULT_ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "::1",
    "janua.dev",
    "*.janua.dev",
    "madfam.io",
    "*.madfam.io",
]


def _parse_allowed_hosts_from_cors() -> list[str]:
    """
    Extract allowed hosts from CORS origins configuration.

    This provides defense-in-depth by only allowing redirects to origins
    that are already trusted for CORS.
    """
    hosts = []
    try:
        for origin in settings.cors_origins_list:
            parsed = urlparse(origin)
            if parsed.netloc:
                hosts.append(parsed.netloc)
    except Exception as e:
        logger.warning("Failed to parse CORS origins for redirect validation", error=str(e))
    return hosts


def get_allowed_redirect_hosts() -> list[str]:
    """
    Get the complete list of allowed redirect hosts.

    Combines:
    1. Default Janua ecosystem hosts
    2. Hosts extracted from CORS origins
    3. Custom domain if configured

    Returns:
        List of allowed host patterns (supports wildcards like *.example.com)
    """
    hosts = list(DEFAULT_ALLOWED_HOSTS)

    # Add hosts from CORS configuration
    cors_hosts = _parse_allowed_hosts_from_cors()
    hosts.extend(cors_hosts)

    # Add custom domain if configured
    if settings.JANUA_CUSTOM_DOMAIN:
        hosts.append(settings.JANUA_CUSTOM_DOMAIN)
        # Also add wildcard for subdomains
        hosts.append(f"*.{settings.JANUA_CUSTOM_DOMAIN}")

    # Add DOMAIN setting if it's not localhost
    if settings.DOMAIN and settings.DOMAIN not in ("localhost", "127.0.0.1"):
        hosts.append(settings.DOMAIN)
        hosts.append(f"*.{settings.DOMAIN}")

    # Deduplicate while preserving order
    seen = set()
    unique_hosts = []
    for host in hosts:
        if host not in seen:
            seen.add(host)
            unique_hosts.append(host)

    return unique_hosts


def _host_matches_pattern(host: str, pattern: str) -> bool:
    """
    Check if a host matches a pattern, supporting wildcards.

    Args:
        host: The host to check (e.g., "app.janua.dev")
        pattern: The pattern to match against (e.g., "*.janua.dev")

    Returns:
        True if the host matches the pattern
    """
    # Normalize both to lowercase
    host = host.lower()
    pattern = pattern.lower()

    # Remove port from host if present
    if ":" in host:
        host = host.split(":")[0]

    # Direct match
    if host == pattern:
        return True

    # Wildcard match (e.g., *.janua.dev matches app.janua.dev)
    if pattern.startswith("*."):
        # Pattern like *.janua.dev should match:
        # - app.janua.dev (subdomain)
        # - janua.dev (base domain)
        base_domain = pattern[2:]  # Remove "*."
        if host == base_domain:
            return True
        if host.endswith(f".{base_domain}"):
            return True

    # Use fnmatch for more complex patterns
    return fnmatch.fnmatch(host, pattern)


def is_safe_redirect_url(
    url: str,
    allowed_hosts: Optional[list[str]] = None,
    allow_relative: bool = True,
) -> bool:
    """
    Validate that a URL is safe to redirect to.

    SECURITY: This function prevents open redirect attacks (CWE-601) by:
    1. Allowing relative URLs (path-only) by default
    2. Blocking javascript: and data: URLs
    3. Only allowing absolute URLs to pre-approved hosts

    Args:
        url: The URL to validate
        allowed_hosts: List of allowed host patterns (defaults to Janua ecosystem hosts)
        allow_relative: Whether to allow relative (path-only) URLs

    Returns:
        True if the URL is safe to redirect to, False otherwise
    """
    if not url:
        return False

    # Strip whitespace
    url = url.strip()

    # Block empty URLs
    if not url:
        return False

    # SECURITY: Block javascript: and data: URLs
    url_lower = url.lower()
    if url_lower.startswith(("javascript:", "data:", "vbscript:", "file:")):
        logger.warning(
            "Blocked dangerous URL scheme in redirect",
            url_prefix=url[:20],
        )
        return False

    # SECURITY: Block URLs that could be parsed as absolute URLs to external sites
    # This catches cases like //evil.com/path (protocol-relative URLs)
    if url.startswith("//"):
        # Parse and validate the host
        parsed = urlparse(f"https:{url}")
        if not parsed.netloc:
            return False
        # Fall through to host validation
        url = f"https:{url}"

    # Parse the URL
    parsed = urlparse(url)

    # Allow relative URLs (no scheme and no netloc)
    if not parsed.scheme and not parsed.netloc:
        if allow_relative:
            # SECURITY: Ensure the path doesn't start with // (could become protocol-relative)
            if parsed.path.startswith("//"):
                return False
            # SECURITY: Block backslash tricks that could be parsed differently by browsers
            if "\\" in url:
                return False
            return True
        return False

    # For absolute URLs, validate the host
    if not parsed.netloc:
        return False

    # Get allowed hosts
    if allowed_hosts is None:
        allowed_hosts = get_allowed_redirect_hosts()

    # Check if host matches any allowed pattern
    host = parsed.netloc.lower()

    for pattern in allowed_hosts:
        if _host_matches_pattern(host, pattern):
            return True

    logger.warning(
        "Blocked redirect to unauthorized host",
        host=host,
        url_prefix=url[:50],
    )
    return False


def validate_redirect_url(
    url: str,
    default_url: str = "/",
    allowed_hosts: Optional[list[str]] = None,
) -> str:
    """
    Validate and return a safe redirect URL.

    This is the primary function to use when handling redirect URLs from user input.

    SECURITY: If the URL is not safe, returns the default_url instead of raising
    an exception. This prevents information leakage about what URLs are blocked.

    Args:
        url: The URL to validate
        default_url: URL to return if validation fails (default: "/")
        allowed_hosts: Optional list of allowed host patterns

    Returns:
        The original URL if safe, or default_url if not

    Example:
        redirect_url = validate_redirect_url(request.query_params.get("next", "/"))
        return RedirectResponse(url=redirect_url)
    """
    if is_safe_redirect_url(url, allowed_hosts=allowed_hosts):
        return url

    logger.info(
        "Redirect URL validation failed, using default",
        attempted_url_prefix=url[:50] if url else None,
        default_url=default_url,
    )
    return default_url


def validate_oauth_redirect_uri(
    redirect_uri: str,
    registered_uris: list[str],
) -> bool:
    """
    Validate an OAuth redirect URI against registered URIs.

    This is a stricter validation for OAuth flows where the redirect URI
    must exactly match a pre-registered value.

    SECURITY: OAuth redirect URIs require exact matching (or careful prefix matching)
    to prevent authorization code/token theft.

    Args:
        redirect_uri: The redirect URI from the OAuth request
        registered_uris: List of URIs registered for the OAuth client

    Returns:
        True if the redirect_uri matches a registered URI
    """
    if not redirect_uri or not registered_uris:
        return False

    # Parse and normalize the requested URI
    parsed = urlparse(redirect_uri)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"

    for registered in registered_uris:
        registered_parsed = urlparse(registered)
        registered_normalized = (
            f"{registered_parsed.scheme}://{registered_parsed.netloc}"
            f"{registered_parsed.path.rstrip('/')}"
        )
        if normalized == registered_normalized:
            return True

    return False
