"""MAP auth cannot turn self-service requests into non-magic outgoing mail.

No caller header, feature toggle, or claimed role releases this hold. Explicit
business sends use MAP's separate outgoing-click/internal-service boundary.
"""

import json

from app.services.email_send_audit import is_map_destination


def map_auth_mail_held(*, template: str | None, redirect_url=None, org_id=None) -> bool:
    return template != "magic_link" and is_map_destination(redirect_url)


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
