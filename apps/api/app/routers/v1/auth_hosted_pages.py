"""HTML of the hosted sign-in pages (login page, password and sign-in-link forms, second-factor challenge).

Split out of `app/routers/v1/auth.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_auth_shared.get_redis`), so one
patch target reaches every caller.
"""

from typing import Optional
from urllib.parse import urlencode

from app.auth.hosted_locale import (
    DEFAULT_HOSTED_LOCALE,
    UI_LOCALES_PARAM,
    hosted_copy,
    ui_locales_query,
)
from app.auth.hosted_locale import html_lang as hosted_html_lang
from app.auth.login_method import LOGIN_METHOD_MAGIC_LINK
from app.routers.v1.auth_shared import (
    HOSTED_FORM_SCRIPT_TAG,
    _busy_label_attr,
    _oauth_context_hidden_fields_html,
)


def _render_mfa_challenge_page(
    *,
    mfa_token: str,
    app_name: str,
    auth_request_id: Optional[str],
    client_id: Optional[str],
    client_name: Optional[str],
    next_url: Optional[str],
    error_message: Optional[str] = None,
    status_code: int = 200,
):
    """Render the hosted second-factor screen for the OAuth browser-login flow.

    This replaces the previous dead-end interstitial (a static "you need a second
    factor" message with no way to enter a code — auth's P1 #3). It POSTs the code
    plus the short-lived `mfa_token` to `/api/v1/auth/login-form/mfa`, which
    verifies the factor, sets the session cookies, and resumes the OAuth redirect.

    The OAuth context (`auth_request_id`/`client_id`/`client_name`/`next`) is
    carried as hidden fields so the verify step can rebuild the same authorize
    URL — the `oauth:pre_login:<auth_request_id>` Redis key is NOT consumed on the
    MFA branch (login_form only deletes it after a session is actually created),
    so it is still available when the second factor completes.
    """
    import html

    from fastapi.responses import HTMLResponse

    safe_app_name = html.escape(app_name or "Application")
    hidden_fields = _oauth_context_hidden_fields_html(
        auth_request_id=auth_request_id,
        client_id=client_id,
        client_name=client_name,
        next_url=next_url,
    )
    error_html = f'<div class="error">{html.escape(error_message)}</div>' if error_message else ""

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Two-factor authentication - Janua</title>{HOSTED_FORM_SCRIPT_TAG}
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
        .login-container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            width: 100%;
            max-width: 400px;
        }}
        .logo {{ text-align: center; margin-bottom: 24px; }}
        .logo h1 {{ font-size: 28px; color: #333; margin-bottom: 8px; }}
        .logo p {{ color: #666; font-size: 14px; }}
        .app-info {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .app-info span {{ color: #666; font-size: 13px; }}
        .app-info strong {{ color: #333; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 6px; color: #333; font-weight: 500; font-size: 14px; }}
        input[type="text"] {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 20px;
            letter-spacing: 4px;
            text-align: center;
        }}
        input:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
        }}
        .hint {{ color: #666; font-size: 13px; text-align: center; margin-top: 12px; }}
        .error {{
            background: #fee;
            color: #c00;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .footer {{ text-align: center; margin-top: 24px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>&#128274; Janua</h1>
            <p>Two-factor authentication</p>
        </div>

        <div class="app-info">
            <span>Signing in to <strong>{safe_app_name}</strong></span>
        </div>

        {error_html}

        <form method="POST" action="/api/v1/auth/login-form/mfa"{_busy_label_attr(hosted_copy(DEFAULT_HOSTED_LOCALE)["busy_verifying"])}>
            <input type="hidden" name="mfa_token" value="{html.escape(mfa_token)}">
            {hidden_fields}
            <div class="form-group">
                <label for="code">Verification code</label>
                <input type="text" id="code" name="code" inputmode="text"
                       autocomplete="one-time-code" placeholder="123456"
                       required autofocus>
            </div>
            <button type="submit">Verify</button>
            <div class="hint">Enter the 6-digit code from your authenticator app, or a backup code.</div>
        </form>

        <div class="footer">Powered by Janua &bull; Secure Authentication</div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html_content, status_code=status_code)


def _password_form_html(hidden_fields: str, locale: str = DEFAULT_HOSTED_LOCALE) -> str:
    """The historical email + password form (in the page's language)."""
    c = hosted_copy(locale)
    return f"""<form id="loginForm" method="POST" action="/api/v1/auth/login-form"{_busy_label_attr(c["busy_signing_in"])}>
            {hidden_fields}
            <div class="form-group">
                <label for="email">{c["email_label"]}</label>
                <input type="email" id="email" name="email" required autocomplete="email" autofocus>
            </div>
            <div class="form-group">
                <label for="password">{c["password_label"]}</label>
                <input type="password" id="password" name="password" required autocomplete="current-password">
                <div class="aux-link"><a href="/api/v1/auth/forgot-password{ui_locales_query(locale)}">{c["forgot_password"]}</a></div>
            </div>
            <button type="submit" id="submitBtn">{c["sign_in_button"]}</button>
        </form>"""


def _magic_link_form_html(hidden_fields: str, locale: str = DEFAULT_HOSTED_LOCALE) -> str:
    """Email-only form: Janua mails a sign-in link, no password involved."""
    c = hosted_copy(locale)
    return f"""<form id="magicLinkForm" method="POST" action="/api/v1/auth/login-form/magic-link"{_busy_label_attr(c["busy_sending"])}>
            {hidden_fields}
            <div class="form-group">
                <label for="email">{c["email_label"]}</label>
                <input type="email" id="email" name="email" required autocomplete="email" autofocus>
            </div>
            <p class="hint">{c["magic_hint"]}</p>
            <button type="submit" id="submitBtn">{c["magic_button"]}</button>
        </form>"""


def _login_page_switch_url(
    *,
    method: str,
    auth_request_id: Optional[str],
    client_id: Optional[str],
    client_name: Optional[str],
    next_url: Optional[str],
    ui_locale: Optional[str] = None,
) -> str:
    """The same login page, other method first, OAuth context preserved."""
    params: dict[str, str] = {"login_method": method}
    if auth_request_id:
        params["auth_request_id"] = auth_request_id
    elif next_url:
        params["next"] = next_url
    if client_id:
        params["client_id"] = client_id
    if client_name:
        params["client_name"] = client_name
    if ui_locale and ui_locale != DEFAULT_HOSTED_LOCALE:
        params[UI_LOCALES_PARAM] = ui_locale
    return f"/api/v1/auth/login?{urlencode(params)}"


def _hosted_login_page_html(
    *,
    app_name: str,
    hidden_fields: str,
    method: str,
    switch_url: Optional[str],
    error_message: Optional[str] = None,
    locale: str = DEFAULT_HOSTED_LOCALE,
    privacy_notice_url: Optional[str] = None,
) -> str:
    """The hosted login page with ONE method first and the other one click away.

    `method` is already resolved (app/auth/login_method.py); `switch_url` is
    the link to the same page with the other method, or None when magic
    links cannot be offered on this deployment (then only the password form
    exists, exactly as before 2026-09-17). `app_name` and `error_message` are
    plain text and escaped here; `hidden_fields` is already HTML.
    `privacy_notice_url` (app/services/client_privacy_notices.py, already
    validated https) adds one line linking the client's own privacy notice;
    None renders the page exactly as before.
    """
    import html as _html

    c = hosted_copy(locale)
    if method == LOGIN_METHOD_MAGIC_LINK:
        form_html = _magic_link_form_html(hidden_fields, locale)
        switch_label = c["switch_to_password"]
    else:
        form_html = _password_form_html(hidden_fields, locale)
        switch_label = c["switch_to_magic"]
    switch_html = (
        f'<div class="switch"><a href="{_html.escape(switch_url)}">{switch_label}</a></div>'
        if switch_url
        else ""
    )
    error_html = (
        f'<div class="error" id="error" style="display:block">{_html.escape(error_message)}</div>'
        if error_message
        else '<div class="error" id="error"></div>'
    )
    notice_html = (
        '<p class="privacy-notice">'
        + c["privacy_notice_line"].format(
            app=f"<strong>{_html.escape(app_name)}</strong>",
            notice=(
                f'<a href="{_html.escape(privacy_notice_url, quote=True)}" target="_blank" rel="noopener noreferrer">'
                f'{c["privacy_notice_link"]}</a>'
            ),
        )
        + "</p>"
        if privacy_notice_url
        else ""
    )
    notice_style = (
        """
        .privacy-notice {
            margin-top: 18px;
            color: #444;
            font-size: 13px;
            line-height: 1.45;
        }
        .privacy-notice a { color: #4c51bf; }"""
        if privacy_notice_url
        else ""
    )
    return f"""
<!DOCTYPE html>
<html lang="{hosted_html_lang(locale)}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{c["sign_in_title"]}</title>{HOSTED_FORM_SCRIPT_TAG}
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
        .login-container {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            width: 100%;
            max-width: 400px;
        }}
        .logo {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .logo h1 {{
            font-size: 28px;
            color: #333;
            margin-bottom: 8px;
        }}
        .logo p {{
            color: #666;
            font-size: 14px;
        }}
        .app-info {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 12px 16px;
            margin-bottom: 24px;
            text-align: center;
        }}
        .app-info span {{
            color: #666;
            font-size: 13px;
        }}
        .app-info strong {{
            color: #333;
        }}
        .form-group {{
            margin-bottom: 20px;
        }}
        label {{
            display: block;
            margin-bottom: 6px;
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }}
        input[type="email"], input[type="password"] {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5eb;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}
        input:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}
        button {{
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }}
        button:disabled {{
            opacity: 0.7;
            cursor: not-allowed;
            transform: none;
        }}
        .error {{
            background: #fee;
            color: #c00;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            display: none;
        }}
        .aux-link {{
            text-align: right;
            margin-top: 6px;
        }}
        .aux-link a {{
            color: #667eea;
            font-size: 13px;
            text-decoration: none;
        }}
        .aux-link a:hover {{
            text-decoration: underline;
        }}
        .hint {{
            color: #666;
            font-size: 13px;
            margin: -8px 0 16px;
        }}
        .switch {{
            text-align: center;
            margin-top: 18px;
        }}
        .switch a {{
            color: #667eea;
            font-size: 14px;
            text-decoration: none;
        }}
        .switch a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            text-align: center;
            margin-top: 24px;
            color: #666;
            font-size: 12px;
        }}{notice_style}
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>&#128274; Janua</h1>
            <p>{c["tagline"]}</p>
        </div>

        <div class="app-info">
            <span>{c["signing_in_to"]} <strong>{_html.escape(app_name)}</strong></span>
        </div>

        {error_html}

        {form_html}
        {switch_html}{notice_html}

        <div class="footer">
            {c["footer"]}
        </div>
    </div>
</body>
</html>
"""
