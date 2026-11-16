"""Render the hosted login page inside an image and print what the notice proof needs.

Run INSIDE an image, piped on stdin:

    docker run --rm -i --entrypoint python <env> IMAGE - < check_signin_notice.py

Prints one line ``SIGNIN=<json>`` with the page rendered for a client that is NOT
listed (es and en; public HTML, compared byte for byte between images), and, when the
image has the per-client notice, whether a listed client's page carries the line. Nothing is read from a database, the network
or a secret; the client id and URL are fixtures.
"""

from __future__ import annotations

import inspect
import json

from app.routers.v1 import auth

COMMON = {"app_name": "MADFAM CV", "hidden_fields": "", "method": "password", "switch_url": None}


out = {
    "unlisted": {loc: auth._hosted_login_page_html(**COMMON, locale=loc) for loc in ("es", "en")},
    "has_notice": "privacy_notice_url" in inspect.signature(auth._hosted_login_page_html).parameters,
}
if out["has_notice"]:
    page = auth._hosted_login_page_html(**COMMON, locale="es", privacy_notice_url="https://cv.example/privacidad")
    out["listed_line"] = (
        "Al continuar, <strong>MADFAM CV</strong> tratará tus datos como explica su" in page
        and 'href="https://cv.example/privacidad"' in page
    )
    from app.services.client_privacy_notices import parse_client_privacy_notices

    out["rejects_http"] = parse_client_privacy_notices("c=http://cv.example/p") == {}
print("SIGNIN=" + json.dumps(out, sort_keys=True))
