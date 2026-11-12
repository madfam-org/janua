"""Print the protected-resource client policies an image loads, and how it judges
three client documents, as one JSON line.

Run INSIDE an image, piped on stdin:

    docker run --rm -i --entrypoint python <env> IMAGE - < dump_policy.py

Importing ``app.core`` imports the whole application, so a clean run also proves
the image imports with the copied files. Only public values are printed: the
resources, scopes, client ids, hosts and redirect URIs already in the public
source, and accept/refuse verdicts on fixed documents. No network call is made
(``parse_document`` only validates bytes), and no configuration, secret or
database value is read.
"""

from __future__ import annotations

import json

#: OpenAI's document as published at https://chatgpt.com/oauth/client.json on
#: 2026-11-12 (it prefers private_key_jwt and supports none).
CHATGPT = "https://chatgpt.com/oauth/client.json"
CHATGPT_DOC = {
    "client_id": CHATGPT,
    "client_uri": "https://chatgpt.com/",
    "redirect_uris": ["https://chatgpt.com/connector_platform_oauth_redirect"],
    "token_endpoint_auth_method": "private_key_jwt",
    "token_endpoint_auth_methods_supported": ["none", "private_key_jwt"],
    "grant_types": [
        "authorization_code",
        "refresh_token",
        "urn:ietf:params:oauth:grant-type:jwt-bearer",
    ],
    "response_types": ["code"],
    "client_name": "ChatGPT",
    "token_endpoint_auth_signing_alg": "RS256",
    "jwks_uri": "https://chatgpt.com/oauth/jwks.json",
}
CLAUDE = "https://claude.ai/oauth/mcp-oauth-client-metadata"
CLAUDE_DOC = {
    "client_id": CLAUDE,
    "client_name": "Claude",
    "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"],
    "grant_types": ["authorization_code", "refresh_token"],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none",
}
#: A confidential-only client: must stay refused in every image.
CONFIDENTIAL_DOC = dict(
    CHATGPT_DOC,
    token_endpoint_auth_methods_supported=["private_key_jwt"],
)


def verdict(parse_document, document: dict, client_id: str, host: str) -> str:
    try:
        metadata = parse_document(json.dumps(document).encode(), client_id, host)
    except Exception as exc:  # ClientMetadataError, or anything the base raises
        return "refused:" + type(exc).__name__
    return "accepted:" + metadata.token_endpoint_auth_method


def snapshot() -> dict:
    from app.core import protected_resources as pr
    from app.services.client_id_metadata import parse_document

    resources = {}
    for uri, resource in sorted(pr.PROTECTED_RESOURCES.items()):
        policy = resource.client_policy
        resources[uri] = {
            "scopes": sorted(scope.name for scope in resource.scopes),
            "access_token_ttl_seconds": resource.access_token_ttl_seconds,
            "cimd_hosts": sorted(policy.cimd_hosts),
            "cimd_client_ids": sorted(policy.cimd_client_ids),
            "redirect_uris": sorted(policy.redirect_uris),
            "allow_loopback_redirects": policy.allow_loopback_redirects,
        }
    return {
        "resources": resources,
        "redirect_origins": pr.protected_resource_redirect_origins(),
        "documents": {
            "chatgpt": verdict(parse_document, CHATGPT_DOC, CHATGPT, "chatgpt.com"),
            "claude": verdict(parse_document, CLAUDE_DOC, CLAUDE, "claude.ai"),
            "confidential": verdict(
                parse_document, CONFIDENTIAL_DOC, CHATGPT, "chatgpt.com"
            ),
        },
    }


if __name__ == "__main__":
    print("POLICY=" + json.dumps(snapshot(), sort_keys=True))
