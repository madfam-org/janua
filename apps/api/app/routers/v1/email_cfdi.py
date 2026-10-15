"""billing/cfdi's derived slots: the optional client-portal link.

Kept out of email.py so the router stays template-agnostic. The naive
``{{key}}`` renderer cannot hide an absent optional, so the whole row is
composed here and exposed to the template as always-present slots.
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Any

#: A client-portal URL the CFDI email may link: https, a plain host, no characters
#: that could close an attribute or open a tag.
_PORTAL_URL = re.compile(r"^https://[A-Za-z0-9.-]+(?::[0-9]+)?(?:/[^\s\"'<>`]*)?$")

_CFDI_PORTAL_ROW = (
    '<tr><td class="mf-pad" style="padding:16px 40px 0 40px; '
    "font-family:'Inter','Segoe UI','Helvetica Neue',Helvetica,Arial,sans-serif; "
    'font-size:15px; line-height:1.6; color:#2f302c;">'
    "{lead} "
    '<a href="{href}" target="_blank" style="color:#2c8136; font-weight:600; '
    'text-decoration:underline;">{label}</a></td></tr>'
)

#: The portal line in each register; it addresses the reader, so it has both.
_PORTAL_LEAD = {
    "usted": "Consulte y descargue todas sus facturas en su portal:",
    "tu": "Consulta y descarga todas tus facturas en tu portal:",
}


def cfdi_portal_slots(portal_url: Any, formality: Any = None) -> tuple[str, str]:
    """billing/cfdi's optional client-portal line as (html_row, text), or ("", "").

    The naive renderer cannot hide an absent optional, so the whole row is
    composed here and exposed as the always-present ``portal_bloque`` (HTML: a
    full table row, because the slot sits between the card's rows) and
    ``portal_texto`` (plain text). Only an https URL with a plain host survives;
    anything else renders nothing rather than a link the renderer cannot vouch
    for. `formality` "tu" words the line in tú; anything else, usted.
    """
    lead = _PORTAL_LEAD["tu" if formality == "tu" else "usted"]
    if not isinstance(portal_url, str):
        return "", ""
    url = portal_url.strip()
    if not _PORTAL_URL.match(url):
        return "", ""
    href = html_lib.escape(url, quote=True)
    label = html_lib.escape(url.removeprefix("https://"), quote=True)
    row = _CFDI_PORTAL_ROW.format(lead=lead, href=href, label=label)
    return row, f"{lead} {url}\n\n"
