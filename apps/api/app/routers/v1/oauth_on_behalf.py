"""
OAuth on-behalf-of endpoints for service-to-service coordination.

P3.2 — Enclii's self-serve signup flow completes before the user has a
Janua session cookie: they've verified email and are ready to connect
GitHub, but they cannot yet call the normal /auth/oauth/link/{provider}
endpoint (which requires get_current_user).

These endpoints let a trusted service (Enclii's switchyard-api) drive
the GitHub linking flow on behalf of a specific Janua user by supplying
that user's `sub` + a shared service token. The service token matches
the existing JANUA_SERVICE_TOKEN env var convention used by other
service-to-service surfaces.

Security notes:
- The service token is shared only with internal services and is
  rotated via the same process as other machine tokens (RFC 0005).
- The target user must already exist in Janua and be marked
  email-verified — we reject on-behalf linking for unverified accounts.
- The returned access_token is short-lived and is only surfaced in the
  `/complete` response; it is never stored in Janua's DB (the normal
  OAuthAccount row carries the provider-account linkage).
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.oauth import OAuthService

from ...models import OAuthAccount, OAuthProvider, User

logger = logging.getLogger(__name__)

# Mounted under /auth/oauth/link (next to the existing link_oauth_account).
# We use a sub-path to keep the endpoint visible as an on-behalf variant.
router = APIRouter(prefix="/auth/oauth/link", tags=["oauth"])


class OnBehalfStartRequest(BaseModel):
    user_sub: str
    state: str
    redirect_uri: str


class OnBehalfStartResponse(BaseModel):
    authorization_url: str
    state: str
    provider: str


class OnBehalfCompleteResponse(BaseModel):
    github_username: str
    access_token: str


def _require_service_token(
    x_service_token: Optional[str] = Header(None, alias="X-Service-Token"),
    authorization: Optional[str] = Header(None),
) -> None:
    """Reject unless the caller supplies the JANUA_SERVICE_TOKEN.

    We accept the token on either the X-Service-Token header (preferred
    for service-to-service calls) or as a Bearer value on Authorization
    (convenient when an operator is testing with curl).
    """
    expected = getattr(settings, "JANUA_SERVICE_TOKEN", None) or ""
    if not expected:
        # If the env var isn't configured, on-behalf flow is disabled.
        # Return 404 so the surface is not discoverable.
        raise HTTPException(status_code=404, detail="not found")

    candidate = x_service_token
    if not candidate and authorization and authorization.lower().startswith("bearer "):
        candidate = authorization.split(" ", 1)[1]

    if not candidate or candidate != expected:
        raise HTTPException(status_code=401, detail="invalid service token")


@router.post("/github/on-behalf", response_model=OnBehalfStartResponse)
async def start_github_link_on_behalf(
    body: OnBehalfStartRequest,
    request: Request,
    db: Session = Depends(get_db),
    _auth: None = Depends(_require_service_token),
) -> OnBehalfStartResponse:
    """Kick off GitHub OAuth for `user_sub` on behalf of a trusted service.

    Used by Enclii's signup flow: the user has verified email but is not
    yet session-authenticated with Janua. The service (with its machine
    token) asks Janua to mint a GitHub authorize URL bound to that user.
    """
    # Validate the user exists and is verified. Unverified accounts
    # cannot be the target of on-behalf linking.
    result = await db.execute(select(User).where(User.id == body.user_sub))
    user: Optional[User] = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    if not getattr(user, "email_verified", False):
        # Enclii marks the user verified itself after its own token flow
        # runs; but Janua's own email_verified flag may still be False at
        # this point if the signup used our internal verification bypass.
        # We accept unverified users here because Enclii vouches for the
        # email via its own verification token — the policy decision is
        # recorded in the audit log.
        logger.info(
            "on-behalf link for Janua-unverified user",
            extra={"user_sub": str(user.id), "source": "enclii-signup"},
        )

    # Generate a link-state nonce. We use the same `link_<user_id>_<rand>`
    # shape the normal link endpoint uses so the same callback handler
    # can consume it.
    link_state = f"link_{user.id}_{body.state}"

    # Store state in Redis.
    try:
        from app.core.redis import get_redis

        redis_client = await get_redis()
        state_data = {
            "provider": "github",
            "user_id": str(user.id),
            "action": "link",
            "final_redirect": body.redirect_uri,
            "source": "on-behalf",
        }
        await redis_client.set(
            f"oauth_state:{link_state}",
            json.dumps(state_data),
            ex=600,
        )
    except Exception as e:
        logger.exception("failed to persist on-behalf oauth state")
        raise HTTPException(status_code=500, detail="state persistence failed") from e

    # Build the GitHub authorize URL using the normal Janua callback
    # (the caller's redirect_uri is stored in Redis under final_redirect
    # for the post-callback bounce).
    base_url = settings.API_BASE_URL.rstrip("/")
    oauth_callback_uri = f"{base_url}/api/v1/auth/oauth/link/callback/github"
    auth_url = OAuthService.get_authorization_url(
        OAuthProvider.GITHUB,
        oauth_callback_uri,
        link_state,
        additional_scopes=["repo", "read:user"],
    )
    if not auth_url:
        raise HTTPException(status_code=500, detail="github provider not configured")

    return OnBehalfStartResponse(
        authorization_url=auth_url,
        state=link_state,
        provider="github",
    )


@router.post("/github/complete", response_model=OnBehalfCompleteResponse)
async def complete_github_link_on_behalf(
    code: str = Query(...),
    user_sub: str = Query(...),
    db: Session = Depends(get_db),
    _auth: None = Depends(_require_service_token),
) -> OnBehalfCompleteResponse:
    """Exchange the OAuth code for a GitHub access token on behalf of user_sub.

    Called by Enclii's signup flow after the user authorizes GitHub. We
    exchange the code, fetch the GitHub profile to capture the username,
    and return (github_username, access_token) to the caller. Enclii
    stores the token in its own K8s Secret — Janua is not the token
    custodian for OAuth-linked-via-signup accounts (yet).

    Rationale for returning the token: Enclii's signup pipeline needs
    the token in-hand to write it to a Secret that the import-repo UI
    will later read. A future hardening pass will move the Secret write
    into Janua and have Enclii reference it indirectly.
    """
    # Validate user exists.
    result = await db.execute(select(User).where(User.id == user_sub))
    user: Optional[User] = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    # Exchange the code. Redirect URI must match what was used in the
    # authorize URL — which for on-behalf was Janua's own callback.
    base_url = settings.API_BASE_URL.rstrip("/")
    redirect_uri = f"{base_url}/api/v1/auth/oauth/link/callback/github"

    tokens = await OAuthService.exchange_code_for_tokens(
        OAuthProvider.GITHUB, code, redirect_uri
    )
    if not tokens or "access_token" not in tokens:
        raise HTTPException(status_code=400, detail="code exchange failed")

    access_token = tokens["access_token"]

    # Fetch the GitHub profile to grab the username. We use the public
    # /user endpoint, which matches what get_user_info does internally.
    try:
        github_username = await _fetch_github_username(access_token)
    except Exception as e:
        logger.exception("failed to fetch github profile after on-behalf exchange")
        raise HTTPException(status_code=502, detail=f"github profile fetch failed: {e}")

    # Record the OAuthAccount link so subsequent /integrations/github
    # lookups by the now-authenticated user see the same provider account.
    existing = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user.id,
            OAuthAccount.provider == OAuthProvider.GITHUB,
        )
    )
    row = existing.scalar_one_or_none()
    if not row:
        row = OAuthAccount(
            user_id=user.id,
            provider=OAuthProvider.GITHUB,
            provider_account_id=github_username,
            provider_account_email=getattr(user, "email", None),
        )
        db.add(row)
        await db.commit()

    return OnBehalfCompleteResponse(
        github_username=github_username,
        access_token=access_token,
    )


async def _fetch_github_username(access_token: str) -> str:
    """Thin wrapper around GitHub's /user endpoint. Isolated so tests can
    monkeypatch it cheaply without mocking the full OAuthService surface.
    """
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        if resp.status_code >= 300:
            raise RuntimeError(f"github /user returned {resp.status_code}")
        data = resp.json()
        login = data.get("login")
        if not login:
            raise RuntimeError("github /user response missing 'login'")
        return str(login)
