"""Janua's authorization-server metadata, in one place.

Served twice with the same content:

- ``/.well-known/openid-configuration`` (OpenID Connect Discovery 1.0), and
- ``/.well-known/oauth-authorization-server`` (RFC 8414), which MCP clients
  such as Claude try first.

``issuer`` is also what goes in the ``iss`` parameter of every authorization
response (RFC 9207) and in the ``iss`` claim of tokens minted for protected
resources, so all three come from :func:`oauth_issuer`.
"""

from __future__ import annotations

import os
from typing import Any

from app.config import settings
from app.core.protected_resources import all_resource_scopes


def oauth_issuer() -> str:
    """The issuer identifier, exactly as the discovery documents publish it.

    ``JANUA_CUSTOM_DOMAIN`` (a white-label deployment such as auth.madfam.io)
    wins; otherwise ``API_BASE_URL``. The OIDC spec requires the issuer to
    match the domain serving the endpoints, so every endpoint below uses it.
    """
    custom_domain = os.getenv("JANUA_CUSTOM_DOMAIN")
    if custom_domain:
        return f"https://{custom_domain}".rstrip("/")
    return settings.API_BASE_URL.rstrip("/")


#: Scopes Janua itself defines, before the protected-resource scopes.
CORE_SCOPES = (
    "openid",
    "profile",
    "email",
    "offline_access",
    # Service-to-service (client_credentials) scopes — see docs/service-tokens.md
    "cfdi:issue",
    "billing:events",
    "legal:draft",
    "legal:client-profile",
    "connections:delegate",
    "white-label:branding",
)


def authorization_server_metadata() -> dict[str, Any]:
    """The metadata document (OIDC Discovery and RFC 8414 share it)."""
    base_url = oauth_issuer()
    scopes = list(CORE_SCOPES)
    for scope in all_resource_scopes():
        if scope not in scopes:
            scopes.append(scope)

    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/api/v1/oauth/authorize",
        "token_endpoint": f"{base_url}/api/v1/oauth/token",
        "userinfo_endpoint": f"{base_url}/api/v1/oauth/userinfo",
        "jwks_uri": f"{base_url}/.well-known/jwks.json",
        "introspection_endpoint": f"{base_url}/api/v1/oauth/introspect",
        "revocation_endpoint": f"{base_url}/api/v1/oauth/revoke",
        "end_session_endpoint": f"{base_url}/logout",
        "registration_endpoint": f"{base_url}/api/v1/oauth/register",
        # The authorization endpoint has only ever answered response_type=code
        # in the query (anything else is a 400); the implicit and hybrid types
        # and the fragment / form_post modes listed until 2026-10 were never
        # served.
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token", "client_credentials"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": scopes,
        # `none` = public clients (PKCE, no secret). Claude's Client ID Metadata
        # Document client authenticates this way; together with the flag
        # below it is what makes Claude choose CIMD.
        "token_endpoint_auth_methods_supported": [
            "client_secret_basic",
            "client_secret_post",
            "none",
        ],
        "claims_supported": [
            "sub",
            "iss",
            "aud",
            "exp",
            "iat",
            "auth_time",
            "nonce",
            "email",
            "email_verified",
            "name",
            "given_name",
            "family_name",
            "picture",
            "updated_at",
        ],
        # S256 only: `plain` was listed until 2026-10 but /authorize has always
        # refused it (OAuth 2.1).
        "code_challenge_methods_supported": ["S256"],
        # RFC 9207: every authorization response carries `iss`.
        "authorization_response_iss_parameter_supported": True,
        # draft-ietf-oauth-client-id-metadata-document: an https client_id is a
        # URL Janua fetches the client's metadata from (allowlisted hosts only,
        # see app/core/protected_resources.py).
        "client_id_metadata_document_supported": True,
        "service_documentation": "https://docs.janua.dev",
    }
