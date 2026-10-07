"""The consent screen for a third-party app asking to use a protected resource.

Spanish, because the people who see it (Crea Tu Mundo's team) read Spanish,
and shown on EVERY authorization for a protected resource: nothing is
remembered and no client is pre-consented, so a page that silently handed a
code to "Claude Code" on a loopback port could not be triggered by another
program on the same computer.

What the page names, and why:

- the RESOURCE (``display_name``), so the person knows whose data is at stake;
- the requesting APP by HOST: the host of the ``client_id`` URL for a Client
  ID Metadata Document, or the redirect host for a client registered in
  Janua. A self-asserted ``client_name`` is shown only as a secondary line,
  never alone (a document can claim any name);
- where the browser goes next; for a loopback redirect that is "una
  aplicación en esta computadora", with a warning: any local program can bind
  a port and present a real client's ``client_id`` (MCP authorization,
  "Localhost Redirect URI Risks");
- each scope in plain Spanish, and, when a refresh token is requested, that
  the app keeps access without asking again, and for how long at most.

Every value that reaches the HTML is escaped.
"""

from __future__ import annotations

import html
from typing import Optional, Sequence

from app.core.protected_resources import ProtectedResource


def _days(seconds: int) -> int:
    return max(1, round(seconds / 86400))


def render_resource_consent_page(
    *,
    resource: ProtectedResource,
    app_host: str,
    client_name: Optional[str],
    redirect_host: str,
    loopback: bool,
    scopes: Sequence[str],
    offline_access: bool,
    user_email: str,
    auth_request_id: str,
    csrf_token: str,
) -> str:
    esc = html.escape
    resource_name = esc(resource.display_name)
    app = esc(app_host)

    scope_items = ""
    for name in scopes:
        scope = resource.scope(name)
        description = scope.description if scope else name
        scope_items += (
            f'<li><span class="check" aria-hidden="true">&#10003;</span>{esc(description)}</li>\n'
        )
    if offline_access:
        days = _days(resource.refresh_token_max_lifetime_seconds)
        scope_items += (
            '<li><span class="check" aria-hidden="true">&#10003;</span>'
            "Mantener el acceso sin pedirte que vuelvas a iniciar sesión, "
            f"por hasta {days} días; después tendrás que volver a autorizarla.</li>\n"
        )

    asserted_name = ""
    if client_name and client_name.strip().lower() != app_host.lower():
        asserted_name = (
            f'<p class="asserted">Se identifica como «{esc(client_name.strip())}». '
            "Este nombre lo declara la propia aplicación.</p>"
        )

    if loopback:
        destination = "una aplicación en esta computadora"
        warning = (
            '<div class="warning" role="alert"><strong>Atención:</strong> la autorización se '
            f"entregará a una aplicación en esta computadora ({esc(redirect_host)}). "
            "Cualquier programa instalado en este equipo podría hacerse pasar por la "
            "aplicación que pide el acceso. Permítelo solo si tú acabas de iniciar esta "
            "conexión desde este equipo.</div>"
        )
    else:
        destination = esc(redirect_host)
        warning = ""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Autorizar acceso al {resource_name}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f4f1ec; color: #1f2933; min-height: 100vh;
            display: flex; align-items: center; justify-content: center; padding: 16px;
        }}
        main {{
            background: #ffffff; border-radius: 14px; width: 100%; max-width: 460px;
            padding: 32px 28px; box-shadow: 0 12px 40px rgba(31, 41, 51, 0.16);
        }}
        h1 {{ font-size: 21px; line-height: 1.3; margin-bottom: 10px; }}
        p.lead {{ font-size: 15px; line-height: 1.5; margin-bottom: 18px; }}
        dl {{ background: #f7f7f5; border-radius: 10px; padding: 14px 16px; margin-bottom: 16px; }}
        dt {{ font-size: 12px; color: #52606d; text-transform: uppercase; letter-spacing: .04em; }}
        dd {{ font-size: 16px; font-weight: 600; margin: 2px 0 10px; word-break: break-all; }}
        dd:last-child {{ margin-bottom: 0; }}
        p.asserted {{ font-size: 13px; color: #52606d; margin: -6px 0 16px; }}
        .warning {{
            background: #fff4e5; border: 1px solid #f0b357; border-radius: 10px;
            padding: 12px 14px; font-size: 14px; line-height: 1.45; margin-bottom: 16px;
        }}
        h2 {{ font-size: 15px; margin-bottom: 8px; }}
        ul {{ list-style: none; margin-bottom: 18px; }}
        li {{ font-size: 14px; line-height: 1.45; padding: 8px 0; border-bottom: 1px solid #eceae6; display: flex; gap: 10px; }}
        li:last-child {{ border-bottom: none; }}
        .check {{ color: #2f7d5b; font-weight: 700; }}
        p.account {{ font-size: 13px; color: #52606d; margin-bottom: 18px; text-align: center; }}
        .buttons {{ display: flex; gap: 12px; }}
        button {{
            flex: 1; padding: 13px; border-radius: 8px; font-size: 16px;
            font-weight: 600; cursor: pointer; border: none;
        }}
        .deny {{ background: #eceae6; color: #1f2933; }}
        .allow {{ background: #1f5f8b; color: #ffffff; }}
        p.footer {{ font-size: 11px; color: #7b8794; text-align: center; margin-top: 18px; }}
    </style>
</head>
<body>
    <main>
        <h1>{app} quiere acceder al {resource_name}</h1>
        <p class="lead">Revisa la solicitud antes de responder. Solo autoriza si tú iniciaste esta conexión.</p>
        <dl>
            <dt>Aplicación que solicita acceso</dt>
            <dd>{app}</dd>
            <dt>Después te regresará a</dt>
            <dd>{destination}</dd>
        </dl>
        {asserted_name}
        {warning}
        <h2>Si lo permites, {app} podrá:</h2>
        <ul>
{scope_items}        </ul>
        <p class="account">Sesión iniciada como <strong>{esc(user_email or "")}</strong></p>
        <form method="POST" action="/api/v1/oauth/consent"
              onsubmit="if (this.dataset.submitted) {{ return false; }} this.dataset.submitted = '1'; return true;">
            <input type="hidden" name="auth_request_id" value="{esc(auth_request_id)}">
            <input type="hidden" name="csrf_token" value="{esc(csrf_token)}">
            <div class="buttons">
                <button type="submit" name="action" value="deny" class="deny">Cancelar</button>
                <button type="submit" name="action" value="allow" class="allow">Permitir</button>
            </div>
        </form>
        <p class="footer">Janua · servicio de identidad de MADFAM</p>
    </main>
</body>
</html>
"""
