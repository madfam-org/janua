"""ops/alert: the operator alert's derived slots.

Kept out of email.py, like email_cfdi.py and email_billing_notice.py, so the
router stays template-agnostic.

The renderer is naive ``{{key}}`` substitution with flat ``{{#flag}}…{{/flag}}``
sections. Two parts of the alert cannot be plain substitution, so they are
composed here, HTML-escaped where they reach the HTML:

- ``detalle`` is multi-line plain text (a probe's findings, a stack of facts).
  The HTML gets ``detalle_html``: each line escaped, joined with ``<br>``, so a
  newline renders as a line break and never as markup. The text part uses the
  caller's ``detalle`` as is.
- The optional action link (``accion_url`` + ``accion_texto``) is shown only
  for an https URL with a plain host. Without a usable URL nothing is shown,
  label included; with a URL but no label, the neutral default label below is
  used. ``mostrar_accion`` drives the section in both bodies.

The template addresses nobody (internal operators), so it has one
register-neutral variant, and so does the default label.
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Any, Dict, Mapping

TEMPLATE_ID = "ops/alert"

#: The action button's label when the caller gives a URL but no `accion_texto`.
#: An infinitive: no tú/usted marker.
DEFAULT_ACTION_LABEL = "Abrir enlace"

#: An action link the alert may carry: https, a plain host, and no character
#: that could close an attribute or open a tag.
_HTTPS_URL = re.compile(r"^https://[A-Za-z0-9.-]+(?::[0-9]+)?(?:/[^\s\"'<>`]*)?$")


def _e(value: Any) -> str:
    return html_lib.escape(str(value), quote=True)


def _text(value: Any) -> str:
    """A scalar's visible text, or "" for None, blanks and non-scalars."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return ""
    return str(value).strip()


def _safe_url(value: Any) -> str:
    """The URL when it is an https link the alert can vouch for, else ""."""
    if not isinstance(value, str):
        return ""
    url = value.strip()
    return url if _HTTPS_URL.match(url) else ""


def detalle_html(detalle: Any) -> str:
    """`detalle` for the HTML body: every line escaped, newlines as ``<br>``.

    CRLF and lone CR count as newlines; leading and trailing blank lines are
    dropped so the box has no empty margin.
    """
    text = str(detalle).replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    return "<br>\n".join(_e(line) for line in text.split("\n"))


def ops_alert_slots(variables: Mapping[str, Any]) -> Dict[str, str]:
    """Every derived slot ops/alert's two bodies use. Always all keys.

    ``mostrar_accion`` is "1" or "" (the renderer keeps a ``{{#flag}}``
    section only when its value is truthy).
    """
    url = _safe_url(variables.get("accion_url"))
    label = (_text(variables.get("accion_texto")) or DEFAULT_ACTION_LABEL) if url else ""
    return {
        "detalle_html": detalle_html(variables.get("detalle", "")),
        "mostrar_accion": "1" if url else "",
        # HTML (escaped, attribute-safe).
        "accion_href": _e(url),
        "accion_etiqueta": _e(label),
        # Plain text (raw; the text part is never escaped).
        "accion_enlace": url,
        "accion_etiqueta_texto": label,
    }
