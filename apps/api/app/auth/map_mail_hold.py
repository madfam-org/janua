"""MAP permits traced magic login and user-initiated password recovery.

Caller headers never establish auth provenance. Recovery requires a live
server-derived audit scope; business sends use MAP's separate outgoing-click
and internal-service boundary. Welcome/provisioning are not auth exceptions.
"""

import json

from app.services.email_send_audit import current_audit, is_map_destination


def map_auth_mail_held(*, template: str | None, redirect_url=None, org_id=None) -> bool:
    if not is_map_destination(redirect_url) or template == "magic_link":
        return False
    audit = current_audit()
    if template == "password_reset" and audit is not None:
        return not (
            audit.source_app == "crea-map" and audit.message_kind == "password_recovery"
            and audit.provenance == "registered_map_recovery"
        )
    return True


def is_map_login_client(client) -> bool:
    if client is None or getattr(client, "is_active", False) is not True:
        return False
    uris = getattr(client, "redirect_uris", None) or []
    if isinstance(uris, str):
        try:
            uris = json.loads(uris)
        except (TypeError, ValueError):
            return False
    return isinstance(uris, list) and any(
        isinstance(uri, str) and is_map_destination(uri) for uri in uris
    )
