"""billing/aviso-de-cobro: the monthly billing notice's list contract and derived slots.

Kept out of email.py, like email_cfdi.py, so the router stays template-agnostic.

The renderer is naive ``{{key}}`` substitution with flat ``{{#flag}}…{{/flag}}``
sections and no loops. So everything that repeats (the breakdown lines, the
payment details, the delivered-work tiles and checklist, the timeline, the
client's actions) is expanded here into rows, with every caller value
HTML-escaped, and every optional section is driven by a derived flag that is
set only when the section has something to show. An absent optional never
renders an empty heading or a placeholder.

The copy itself arrives from nauta already composed in the reader's register
(tú or usted). This module and the template only lay it out; the template's
own static words ("Periodo", "Desglose", "Total a pagar"…) are labels that do
not address the reader, so the template has a single register-neutral variant.
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Any, Dict, List, Mapping, Sequence, Tuple

TEMPLATE_ID = "billing/aviso-de-cobro"

#: Item shape of each list variable: (keys every item must carry, keys an item may carry).
#: A value is a string or a number; an empty string is allowed for an optional key.
LIST_ITEM_KEYS: Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = {
    "conceptos": (("concepto", "monto"), ("detalle",)),
    "pago_datos": (("etiqueta", "valor"), ()),
    "entregado_destacados": (("valor", "etiqueta"), ()),
    "entregado": (("titulo",), ("detalle",)),
    "viene": (("cuando", "que"), ()),
    "acciones": (("titulo",), ("detalle",)),
}

#: Links the notice may carry: https with a plain host, or a mailto address. No
#: character that could close an attribute or open a tag survives either form.
_HTTPS_URL = re.compile(r"^https://[A-Za-z0-9.-]+(?::[0-9]+)?(?:/[^\s\"'<>`]*)?$")
_MAILTO_URL = re.compile(r"^mailto:[^\s\"'<>`@]+@[A-Za-z0-9.-]+(?:\?[^\s\"'<>`]*)?$")

_FONT = "font-family:'Inter','Segoe UI','Helvetica Neue',Helvetica,Arial,sans-serif;"
_DISPLAY = "font-family:'Poppins','Segoe UI','Helvetica Neue',Helvetica,Arial,sans-serif;"
_MONO = "font-family:'Space Mono','SFMono-Regular',Menlo,Consolas,'Courier New',monospace;"

#: Tiles per row in «Lo que entregamos»; a phone stacks them (class mf-col).
_TILES_PER_ROW = 3


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float)) and not isinstance(value, bool)


def _present(value: Any) -> bool:
    """A scalar with visible content."""
    return _is_scalar(value) and str(value).strip() != ""


def _e(value: Any) -> str:
    return html_lib.escape(str(value), quote=True)


def _safe_url(value: Any) -> str:
    """The URL when it is a link the notice can vouch for, else ""."""
    if not isinstance(value, str):
        return ""
    url = value.strip()
    if _HTTPS_URL.match(url) or _MAILTO_URL.match(url):
        return url
    return ""


def list_variable_problems(
    variables: Mapping[str, Any],
    required: Sequence[str],
    item_keys: Mapping[str, Tuple[Tuple[str, ...], Tuple[str, ...]]] = LIST_ITEM_KEYS,
) -> List[str]:
    """Names of list variables (or `name[i].key` paths) that break the item contract.

    A REQUIRED list must be a non-empty list. An OPTIONAL list that is present
    must be a list (empty is allowed and means "no section"). Every item must
    be an object carrying its required keys as non-blank strings or numbers;
    its optional keys, when present, must be strings or numbers.
    """
    problems: List[str] = []
    for name, (item_required, item_optional) in item_keys.items():
        if name not in variables:
            continue  # absence of a required list is reported as "missing" upstream
        items = variables[name]
        if not isinstance(items, list) or (name in required and not items):
            problems.append(name)
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                problems.append(f"{name}[{index}]")
                continue
            for key in item_required:
                if not _present(item.get(key)):
                    problems.append(f"{name}[{index}].{key}")
            for key in item_optional:
                if key in item and item[key] is not None and not _is_scalar(item[key]):
                    problems.append(f"{name}[{index}].{key}")
    return problems


def _items(variables: Mapping[str, Any], name: str) -> List[Dict[str, Any]]:
    value = variables.get(name)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _optional_text(item: Mapping[str, Any], key: str) -> str:
    value = item.get(key)
    return str(value).strip() if _present(value) else ""


# --------------------------------------------------------------------------- #
# Row builders (HTML). Every interpolated value goes through _e().
# --------------------------------------------------------------------------- #
def _concepto_rows(items: List[Dict[str, Any]]) -> str:
    rows = []
    for item in items:
        detalle = _optional_text(item, "detalle")
        detalle_html = (
            f'<div style="{_FONT} font-size:13px; line-height:1.5; color:#5B5F77; '
            f'padding-top:2px;">{_e(detalle)}</div>'
            if detalle
            else ""
        )
        rows.append(
            '<tr><td style="padding:12px 12px 12px 0; border-bottom:1px solid #ECEAF4; '
            f'vertical-align:top; {_FONT} font-size:15px; line-height:1.5; color:#0A0E27;">'
            f"{_e(item['concepto'])}{detalle_html}</td>"
            '<td align="right" style="padding:12px 0; border-bottom:1px solid #ECEAF4; '
            f"vertical-align:top; white-space:nowrap; {_FONT} font-size:15px; "
            f'line-height:1.5; color:#0A0E27;">{_e(item["monto"])}</td></tr>'
        )
    return "".join(rows)


def _pago_rows(items: List[Dict[str, Any]]) -> str:
    return "".join(
        '<tr class="mf-row"><td class="mf-label" width="32%" style="padding:6px 12px 6px 0; '
        f'vertical-align:top; {_FONT} font-size:13px; line-height:1.5; color:#5B5F77;">'
        f"{_e(item['etiqueta'])}</td>"
        f'<td style="padding:6px 0; vertical-align:top; {_MONO} font-size:14px; '
        f'line-height:1.5; color:#0A0E27; word-break:break-all;">{_e(item["valor"])}</td></tr>'
        for item in items
    )


def _tile_row_sizes(count: int) -> List[int]:
    """Balanced rows of at most _TILES_PER_ROW tiles: 4 → [2, 2], 5 → [3, 2], 7 → [3, 2, 2]."""
    rows = -(-count // _TILES_PER_ROW)  # ceiling division
    base, extra = divmod(count, rows) if rows else (0, 0)
    return [base + (1 if index < extra else 0) for index in range(rows)]


def _destacado_rows(items: List[Dict[str, Any]]) -> str:
    """One fixed-layout table per row, so every tile in a row has the same width."""
    rows = []
    start = 0
    for size in _tile_row_sizes(len(items)):
        chunk = items[start : start + size]
        start += size
        width = f"{100 // size}%"
        cells = "".join(
            f'<td class="mf-col mf-tile" width="{width}" style="width:{width}; '
            'padding:0 4px 8px 4px; vertical-align:top;"><table role="presentation" '
            'width="100%" cellspacing="0" cellpadding="0" border="0" '
            'style="background-color:#F4F0FA; border-radius:10px;">'
            f'<tr><td style="padding:14px 14px 12px 14px;"><div style="{_DISPLAY} '
            'font-size:24px; font-weight:700; line-height:1.2; color:#9B59B6;">'
            f'{_e(item["valor"])}</div><div style="{_FONT} font-size:13px; line-height:1.4; '
            f'color:#5B5F77; padding-top:4px;">{_e(item["etiqueta"])}</div></td></tr>'
            "</table></td>"
            for item in chunk
        )
        rows.append(
            '<tr><td style="padding:0;"><table role="presentation" width="100%" '
            'cellspacing="0" cellpadding="0" border="0" style="table-layout:fixed;">'
            f"<tr>{cells}</tr></table></td></tr>"
        )
    return "".join(rows)


def _entregado_rows(items: List[Dict[str, Any]]) -> str:
    rows = []
    for item in items:
        detalle = _optional_text(item, "detalle")
        detalle_html = (
            f'<div style="{_FONT} font-size:14px; line-height:1.5; color:#5B5F77;">'
            f"{_e(detalle)}</div>"
            if detalle
            else ""
        )
        rows.append(
            '<tr><td width="30" style="padding:8px 10px 8px 0; vertical-align:top;">'
            '<div style="width:22px; height:22px; border-radius:11px; background-color:#6BCB77; '
            f"color:#0A0E27; text-align:center; {_FONT} font-size:13px; font-weight:700; "
            'line-height:22px;">&#10003;</div></td>'
            f'<td style="padding:8px 0; vertical-align:top;"><div style="{_FONT} '
            'font-size:15px; font-weight:600; line-height:1.5; color:#0A0E27;">'
            f"{_e(item['titulo'])}</div>{detalle_html}</td></tr>"
        )
    return "".join(rows)


def _viene_rows(items: List[Dict[str, Any]]) -> str:
    return "".join(
        '<tr class="mf-row"><td class="mf-label mf-when" width="130" style="padding:0 14px 16px 0; '
        f"vertical-align:top; {_FONT} font-size:12px; font-weight:700; letter-spacing:1px; "
        f'text-transform:uppercase; line-height:1.6; color:#9B59B6;">{_e(item["cuando"])}</td>'
        '<td style="padding:0 0 16px 16px; border-left:3px solid #FFD93D; vertical-align:top; '
        f'{_FONT} font-size:15px; line-height:1.55; color:#0A0E27;">{_e(item["que"])}</td></tr>'
        for item in items
    )


def _accion_rows(items: List[Dict[str, Any]]) -> str:
    rows = []
    for number, item in enumerate(items, start=1):
        detalle = _optional_text(item, "detalle")
        detalle_html = (
            f'<div style="{_FONT} font-size:14px; line-height:1.5; color:#5B5F77;">'
            f"{_e(detalle)}</div>"
            if detalle
            else ""
        )
        rows.append(
            '<tr><td width="34" style="padding:8px 12px 8px 0; vertical-align:top;">'
            '<div style="width:26px; height:26px; border-radius:13px; background-color:#9B59B6; '
            f"color:#FFFFFF; text-align:center; {_FONT} font-size:13px; font-weight:700; "
            f'line-height:26px;">{number}</div></td>'
            f'<td style="padding:8px 0; vertical-align:top;"><div style="{_FONT} '
            'font-size:15px; font-weight:600; line-height:1.5; color:#0A0E27;">'
            f"{_e(item['titulo'])}</div>{detalle_html}</td></tr>"
        )
    return "".join(rows)


# --------------------------------------------------------------------------- #
# Plain-text builders: raw values (the text part is never escaped).
# --------------------------------------------------------------------------- #
def _with_detail(main: str, item: Mapping[str, Any]) -> str:
    detalle = _optional_text(item, "detalle")
    return f"{main}\n  {detalle}" if detalle else main


def _text_lines(lines: List[str]) -> str:
    """Lines, each newline-terminated, so an empty list leaves no blank line."""
    return "".join(f"{line}\n" for line in lines)


def billing_notice_slots(variables: Mapping[str, Any]) -> Dict[str, str]:
    """Every derived slot billing/aviso-de-cobro's two bodies use. Always all keys.

    Flags are "1" or "" (the renderer keeps a ``{{#flag}}`` section only when
    its value is truthy). Each flag already includes its parent's condition,
    so the template's sections never need to nest.
    """
    conceptos = _items(variables, "conceptos")
    pago_datos = _items(variables, "pago_datos")
    destacados = _items(variables, "entregado_destacados")
    entregado = _items(variables, "entregado")
    viene = _items(variables, "viene")
    acciones = _items(variables, "acciones")

    cta_url = _safe_url(variables.get("cta_comprobante_url"))
    mostrar_cta = bool(cta_url) and _present(variables.get("cta_comprobante_etiqueta"))
    mostrar_entregado = _present(variables.get("entregado_titulo")) and bool(
        destacados or entregado
    )
    mostrar_viene = _present(variables.get("viene_titulo")) and bool(viene)
    mostrar_acciones = _present(variables.get("acciones_titulo")) and bool(acciones)
    acciones_url = _safe_url(variables.get("acciones_enlace_url"))
    mostrar_acciones_enlace = (
        mostrar_acciones
        and bool(acciones_url)
        and _present(variables.get("acciones_enlace_etiqueta"))
    )
    estado_url = _safe_url(variables.get("estado_cuenta_url"))
    mostrar_estado = bool(estado_url) and _present(variables.get("estado_cuenta_etiqueta"))

    def flag(condition: bool) -> str:
        return "1" if condition else ""

    return {
        # Flags.
        "mostrar_fecha_pago_nota": flag(_present(variables.get("fecha_pago_nota"))),
        "mostrar_cta_comprobante": flag(mostrar_cta),
        "mostrar_entregado": flag(mostrar_entregado),
        "mostrar_entregado_periodo": flag(
            mostrar_entregado and _present(variables.get("entregado_periodo"))
        ),
        "mostrar_entregado_destacados": flag(mostrar_entregado and bool(destacados)),
        "mostrar_entregado_lista": flag(mostrar_entregado and bool(entregado)),
        "mostrar_viene": flag(mostrar_viene),
        "mostrar_acciones": flag(mostrar_acciones),
        "mostrar_acciones_enlace": flag(mostrar_acciones_enlace),
        "mostrar_estado_cuenta": flag(mostrar_estado),
        # HTML rows (escaped) and attribute-safe links.
        "conceptos_filas": _concepto_rows(conceptos),
        "pago_datos_filas": _pago_rows(pago_datos),
        "entregado_destacados_filas": _destacado_rows(destacados) if mostrar_entregado else "",
        "entregado_filas": _entregado_rows(entregado) if mostrar_entregado else "",
        "viene_filas": _viene_rows(viene) if mostrar_viene else "",
        "acciones_filas": _accion_rows(acciones) if mostrar_acciones else "",
        "cta_comprobante_href": _e(cta_url) if mostrar_cta else "",
        "acciones_enlace_href": _e(acciones_url) if mostrar_acciones_enlace else "",
        "estado_cuenta_href": _e(estado_url) if mostrar_estado else "",
        # Plain-text equivalents (raw).
        "conceptos_texto": _text_lines(
            [_with_detail(f"- {i['concepto']}: {i['monto']}", i) for i in conceptos]
        ),
        "pago_datos_texto": _text_lines([f"{i['etiqueta']}: {i['valor']}" for i in pago_datos]),
        "entregado_destacados_texto": _text_lines(
            [f"- {i['valor']} {i['etiqueta']}" for i in destacados] if mostrar_entregado else []
        ),
        "entregado_texto": _text_lines(
            [_with_detail(f"[x] {i['titulo']}", i) for i in entregado] if mostrar_entregado else []
        ),
        "viene_texto": _text_lines(
            [f"- {i['cuando']}: {i['que']}" for i in viene] if mostrar_viene else []
        ),
        "acciones_texto": _text_lines(
            [_with_detail(f"{n}. {i['titulo']}", i) for n, i in enumerate(acciones, start=1)]
            if mostrar_acciones
            else []
        ),
        "cta_comprobante_enlace": cta_url if mostrar_cta else "",
        "acciones_enlace": acciones_url if mostrar_acciones_enlace else "",
        "estado_cuenta_enlace": estado_url if mostrar_estado else "",
    }
