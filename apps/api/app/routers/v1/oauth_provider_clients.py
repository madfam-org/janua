"""Client policy at /authorize: silent sign-in, first-party pre-consent, public-client rules, the account chooser and OAuth error redirects.

Split out of `app/routers/v1/oauth_provider.py` (2026-11-19, the 800-line
pre-commit limit); code moved verbatim. Names tests patch live in one module
and other modules call them through it (e.g. `_oauth_provider_shared.get_redis`), so one
patch target reaches every caller.
"""

import html
import re
from typing import Any, Optional

from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.hosted_locale import DEFAULT_HOSTED_LOCALE, hosted_copy, html_lang
from app.core.reserved_oauth_boundaries import SILENT_AUTH_SCOPE, is_first_party_name
from app.models import OAuthClient
from app.routers.v1 import oauth_provider_shared as _oauth_provider_shared
from app.routers.v1.oauth_provider_scopes import _narrow_to_allowed_scopes
from app.routers.v1.oauth_provider_shared import _build_safe_callback_url, _session_started_at


def _is_silent_auth_allowed(client: OAuthClient) -> bool:
    """`prompt=none` is restricted to first-party clients to prevent surprise
    issuance to third-party apps.

    A client is first-party when it is BOTH `is_active=True` AND `is_confidential=True`
    (i.e. has a registered server-side secret) AND its name does not begin
    with the operator-marker prefix used for tenant-self-service registrations.
    Operators wanting silent-auth for a specific tenant client can opt-in by
    setting `OAuthClient.allowed_scopes` to include `madfam:silent_auth`.

    The implementation is intentionally conservative: silent-auth bypasses
    the visible consent screen, so we err on the side of "no, show the
    interactive flow" when a client has not been explicitly trusted.

    PUBLIC clients are never trusted here. A public client the operator marked
    with `madfam:silent_auth` is decided per request in `authorize_get`
    (`_is_marked_public_client`, `_public_first_party_refusal`).
    """
    if not client.is_active:
        return False
    if not getattr(client, "is_confidential", False):
        return False
    allowed_scopes = list(client.allowed_scopes or [])
    if SILENT_AUTH_SCOPE in allowed_scopes:
        return True
    # Default-allow for known first-party MADFAM client_ids. The Selva office
    # client is the primary consumer of silent-auth in Phase 1.
    return is_first_party_name(client.name)


def _is_first_party_preconsented(client: OAuthClient) -> bool:
    """First-party clients do not need a visible consent screen (B6).

    Consent exists so a person can refuse a THIRD party access to their Janua
    account. `selva-office*`, `madfam-*`, and any client an operator has
    explicitly marked with `madfam:silent_auth` are surfaces of MADFAM itself:
    asking someone to authorize MADFAM to MADFAM communicates nothing and, on
    the silent path, is not even askable — `prompt=none` cannot render a
    screen, so a missing consent row turns into `consent_required` and the
    silent hop fails for a client that was never going to be refused.

    Deliberately the SAME predicate as `_is_silent_auth_allowed`, not a looser
    one: exactly the clients trusted to skip the consent UI silently are the
    clients treated as pre-consented, so widening one can never quietly widen
    the other. A third-party client is unaffected and still sees the screen.
    """
    return _is_silent_auth_allowed(client)


#: An S256 ``code_challenge`` is BASE64URL(SHA-256(verifier)) without padding:
#: exactly 43 characters of the base64url alphabet (RFC 7636 §4.2).
_S256_CHALLENGE_SHAPE = re.compile(r"^[A-Za-z0-9_-]{43}$")


def _is_marked_public_client(client: OAuthClient) -> bool:
    """An active PUBLIC client carrying the operator marker ``madfam:silent_auth``.

    Only the marker counts. The first-party NAME prefixes (`selva-office*`,
    `madfam-*`) never make a public client first-party: a client without a
    secret is trusted only when an operator marked it explicitly. Whether the
    marker is honoured for a given request is `_public_first_party_refusal`.
    """
    return bool(
        client.is_active
        and not getattr(client, "is_confidential", False)
        and SILENT_AUTH_SCOPE in (client.allowed_scopes or [])
    )


def _public_first_party_refusal(
    client: OAuthClient,
    *,
    redirect_uri: str,
    requested_scope: Optional[str],
    code_challenge: Optional[str],
    code_challenge_method: Optional[str],
) -> Optional[tuple[str, str]]:
    """Why a marked public client's request may NOT skip sign-in or consent.

    ``None`` when every request condition holds; otherwise the OIDC error and
    a short description for the redirect. The conditions (owner decision
    2026-11-18), each of which binds a code to the registered app:

    - PKCE S256, stated explicitly (``code_challenge_method=S256``; an omitted
      method is not accepted here although the token endpoint defaults it) and
      a challenge of the S256 shape;
    - ``redirect_uri`` EXACTLY equal to a registered string — no query,
      trailing-slash or loopback-port leniency of `_validate_redirect_uri`;
    - every requested scope within the client's registered scopes (nothing was
      narrowed away by `_narrow_to_allowed_scopes`).

    Reserved scopes (product roles and the other registry values) are handled
    at the consent step, where the person's own consent row is read. The
    person's session, invite-only, email verification and MFA gates run for
    this client exactly as for every other one.
    """
    if code_challenge_method != "S256" or not _S256_CHALLENGE_SHAPE.match(code_challenge or ""):
        return "interaction_required", "pkce_s256_required"
    if redirect_uri not in (client.redirect_uris or []):
        return "interaction_required", "redirect_uri_not_exact"
    _, dropped = _narrow_to_allowed_scopes(requested_scope, client)
    if dropped:
        return "consent_required", "scope_not_registered"
    return None


async def _resolve_held_accounts(held_sids: list[str], db: AsyncSession) -> list[tuple[str, Any]]:
    """Resolve each held `sid` to `(sid, user)`: live sessions only, one per person.

    A `sid` whose row is revoked, expired, or whose user is not active is
    silently omitted — the chooser only ever offers accounts a switch could
    actually front.

    One entry per USER: every sign-in appends a new `sid`, so a person who signed
    in five times holds five live sessions and was listed five times. The entry
    kept is that user's newest live session (by `created_at`; on a tie or an
    undatable row, the later position in `janua_sessions`, which is
    most-recent-last). The list keeps the held order of the sessions kept.
    The held set itself is not pruned here; see `append_sid` for why.
    """
    best: dict[str, tuple[int, str, Any, Any]] = {}
    for position, sid in enumerate(held_sids):
        user, session = await _oauth_provider_shared.resolve_session_by_id(sid, db)
        if user is None or session is None:
            continue
        key = str(getattr(user, "id", sid))
        current = best.get(key)
        if current is None:
            best[key] = (position, sid, user, session)
            continue
        new_started = _session_started_at(session)
        old_started = _session_started_at(current[3])
        if new_started is not None and old_started is not None and new_started < old_started:
            continue  # the one already kept is newer
        best[key] = (position, sid, user, session)
    kept = sorted(best.values(), key=lambda entry: entry[0])
    return [(sid, user) for _, sid, user, _ in kept]


def _account_chooser_html(
    accounts: list[tuple[str, Any]],
    *,
    authorize_next: str,
    add_account_url: str,
    client_name: str,
    locale: str = DEFAULT_HOSTED_LOCALE,
) -> str:
    """Render the `prompt=select_account` chooser over the held estate accounts.

    Each account is a form that POSTs its `sid` to `/api/v1/auth/switch-session/form`
    (the form-encoded twin of the JSON `/switch-session`, which answers a plain
    HTML form with 422) with `next` set to the rebuilt authorize URL, so choosing an account re-points
    `janua_sso` and lands back at `/authorize` for that account. "Use another
    account" is a normal interactive login. All user-controlled text is HTML
    escaped (XSS), and only the opaque `sid` and the pre-validated `next` travel
    in the forms — no token, no email in a query string.

    ``locale`` is a page locale from ``page_locale`` (``"en"`` or ``"es"``),
    never the raw ``ui_locales``: it only picks a row of ``HOSTED_COPY`` and the
    ``<html lang>`` constant. English (the default) is the page every client
    rendered before the chooser spoke Spanish, byte for byte.
    """
    copy = hosted_copy(locale)
    escaped_client = html.escape(client_name or copy["chooser_app_fallback"])
    escaped_next = html.escape(authorize_next)
    escaped_add = html.escape(add_account_url)

    rows = ""
    for sid, user in accounts:
        label = (
            getattr(user, "email", None)
            or getattr(user, "username", None)
            or copy["chooser_account_fallback"]
        )
        display = html.escape(str(label))
        escaped_sid = html.escape(str(sid))
        rows += f"""
        <form method="post" action="/api/v1/auth/switch-session/form" class="account">
            <input type="hidden" name="sid" value="{escaped_sid}">
            <input type="hidden" name="next" value="{escaped_next}">
            <button type="submit" class="account-btn">
                <span class="account-avatar">{display[:1].upper()}</span>
                <span class="account-email">{display}</span>
            </button>
        </form>
        """

    return f"""
<!DOCTYPE html>
<html lang="{html_lang(locale)}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{copy["chooser_title"]}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; display: flex; align-items: center;
            justify-content: center; padding: 20px;
        }}
        .chooser {{
            background: white; border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px; width: 100%; max-width: 420px;
        }}
        h1 {{ font-size: 22px; color: #333; margin-bottom: 6px; text-align: center; }}
        p.sub {{ color: #666; font-size: 14px; margin-bottom: 24px; text-align: center; }}
        .account {{ margin-bottom: 10px; }}
        .account-btn {{
            width: 100%; display: flex; align-items: center; gap: 12px;
            padding: 12px 14px; border: 1px solid #e2e2e2; border-radius: 10px;
            background: #fafafa; cursor: pointer; font-size: 15px; color: #222;
        }}
        .account-btn:hover {{ background: #f0f0ff; border-color: #764ba2; }}
        .account-avatar {{
            width: 34px; height: 34px; border-radius: 50%;
            background: #764ba2; color: white; display: flex;
            align-items: center; justify-content: center; font-weight: 600;
        }}
        .add {{
            display: block; margin-top: 18px; text-align: center;
            color: #764ba2; text-decoration: none; font-size: 14px;
        }}
        .add:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="chooser">
        <h1>{copy["chooser_heading"]}</h1>
        <p class="sub">{copy["chooser_continue_to"].format(app=escaped_client)}</p>
        {rows}
        <a class="add" href="{escaped_add}">{copy["chooser_other_account"]}</a>
    </div>
</body>
</html>
"""


def _redirect_with_oauth_error(
    redirect_uri: str,
    error: str,
    error_description: str,
    state: Optional[str],
    *,
    client_validated: bool,
) -> RedirectResponse:
    """Build an OAuth-spec-compliant error redirect (`error`, `error_description`,
    optional `state`).

    This is the standard "tell the client we couldn't authenticate silently"
    path for `prompt=none` failures (`error=login_required`,
    `error=consent_required`, etc.). The redirect_uri MUST be already
    validated against the OAuth client's registered URIs before calling this.
    """
    params: dict[str, str] = {
        "error": error,
        "error_description": error_description,
    }
    if state:
        params["state"] = state
    return RedirectResponse(
        url=_build_safe_callback_url(redirect_uri, params, client_validated=client_validated),
        status_code=302,
    )
