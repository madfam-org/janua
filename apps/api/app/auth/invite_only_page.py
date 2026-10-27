"""The page ``/oauth/authorize`` shows a signed-in person an invite-only client refuses.

Interactive requests only; ``prompt=none`` gets ``error=access_denied`` on the
client's redirect URI instead. The page says what happened in the request's
language (``ui_locales``), never which accounts ARE invited, and offers the one
useful next step: the same authorize request with ``prompt=login``, so a person
holding a second, invited account can switch to it.
"""

from __future__ import annotations

import html
from typing import Optional

from fastapi.responses import HTMLResponse

from app.auth.hosted_locale import hosted_copy, html_lang


def render_invite_only_refusal(
    *,
    app_name: str,
    locale: str,
    other_account_url: Optional[str],
) -> HTMLResponse:
    copy = hosted_copy(locale)
    switch = (
        f'<p class="switch"><a href="{html.escape(other_account_url)}">'
        f"{copy['invite_only_other_account']}</a></p>"
        if other_account_url
        else ""
    )
    page = f"""<!DOCTYPE html>
<html lang="{html_lang(locale)}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex, nofollow">
    <title>{copy['invite_only_title']}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 40px;
            width: 100%;
            max-width: 420px;
        }}
        h1 {{ color: #333; font-size: 22px; margin-bottom: 16px; }}
        p {{ color: #444; font-size: 15px; line-height: 1.5; margin-bottom: 12px; }}
        .switch a {{ color: #667eea; text-decoration: none; }}
        .switch a:hover {{ text-decoration: underline; }}
        .footer {{ text-align: center; margin-top: 24px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{copy['invite_only_heading']} <strong>{html.escape(app_name)}</strong></h1>
        <p>{copy['invite_only_body']}</p>
        {switch}
        <div class="footer">{copy['footer']}</div>
    </div>
</body>
</html>
"""
    return HTMLResponse(
        content=page,
        status_code=403,
        headers={"cache-control": "no-store", "x-robots-tag": "noindex, nofollow"},
    )
