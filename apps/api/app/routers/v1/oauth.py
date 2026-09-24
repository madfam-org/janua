"""
OAuth authentication endpoints
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode as _urlencode
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.consent_purposes import get_purpose
from app.core.locale import locale_from_request
from app.database import get_db
from app.dependencies import get_current_user
from app.services.connected_account_service import ConnectedAccountService
from app.services.oauth import OAuthService

from ...models import ActivityLog, OAuthAccount, OAuthProvider, Passkey, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/oauth", tags=["oauth"])


def validate_redirect_url(url: Optional[str]) -> Optional[str]:
    """
    Validate that a redirect URL is safe and allowed.

    Args:
        url: The URL to validate

    Returns:
        The validated URL

    Raises:
        HTTPException: If the URL is invalid or not allowed
    """
    if not url:
        return url

    try:
        parsed = urlparse(url)

        # Get allowed origins from settings
        allowed_origins = settings.cors_origins_list

        # Allow relative URLs (no scheme or netloc)
        if not parsed.scheme and not parsed.netloc:
            return url

        # For absolute URLs, check against allowed origins
        if parsed.netloc:
            # Construct origin from parsed URL
            origin = f"{parsed.scheme}://{parsed.netloc}"

            # Check if origin is in allowed list
            if origin not in allowed_origins and not any(
                allowed in origin for allowed in allowed_origins
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Redirect URL domain not allowed. Must be one of: {', '.join(allowed_origins)}",
                )

        return url

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid redirect URL: {str(e)}")


def _append_query(url: str, **params: str) -> str:
    """Append query parameters to an already-validated redirect URL."""
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{_urlencode(params)}"


class OAuthInitRequest(BaseModel):
    """OAuth initialization request"""

    provider: OAuthProvider
    redirect_uri: Optional[str] = None
    scopes: Optional[list[str]] = None
    redirect_to: Optional[str] = None  # Where to redirect after OAuth completes


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request"""

    code: str
    state: str
    provider: OAuthProvider


class OAuthProvidersResponse(BaseModel):
    """Available OAuth providers response"""

    providers: list[dict]


@router.get("/providers", response_model=OAuthProvidersResponse)
async def get_oauth_providers():
    """Get list of available OAuth providers"""
    providers = []

    for provider in list(OAuthProvider):
        config = OAuthService.get_provider_config(provider)
        if config:
            providers.append(
                {"provider": provider.value, "name": provider.value.capitalize(), "enabled": True}
            )

    return OAuthProvidersResponse(providers=providers)


@router.post("/authorize/{provider}")
async def oauth_authorize(
    provider: str,
    request: Request,
    redirect_uri: Optional[str] = Query(None),
    redirect_to: Optional[str] = Query(None),
    scopes: Optional[str] = Query(None),
):
    """Initialize OAuth flow for a provider"""
    try:
        # Validate redirect URLs to prevent open redirect vulnerabilities
        # redirect_to is validated (and stored in state for post-auth redirect)
        validate_redirect_url(redirect_to)
        redirect_uri = validate_redirect_url(redirect_uri)

        # Parse provider enum
        try:
            oauth_provider = OAuthProvider(provider.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

        # Check if provider is configured
        config = OAuthService.get_provider_config(oauth_provider)
        if not config:
            raise HTTPException(status_code=400, detail=f"Provider {provider} is not configured")

        # Generate state token
        state = OAuthService.generate_state_token()

        # Store state in Redis with 10-minute expiry for validation
        from app.core.redis import get_redis

        redis_client = await get_redis()
        state_stored = await redis_client.set(
            f"oauth_state:{state}",
            provider,  # Store provider for additional validation
            ex=600,  # 10 minutes
        )

        # Validate Redis state storage succeeded (critical for OAuth security)
        if not state_stored:
            logger.error("Failed to store OAuth state in Redis - service unavailable")
            raise HTTPException(
                status_code=503,
                detail="Authentication service temporarily unavailable. Please try again.",
            )

        # Build redirect URI if not provided
        if not redirect_uri:
            # Use the API base URL + callback endpoint
            base_url = settings.API_BASE_URL.rstrip("/")
            redirect_uri = f"{base_url}/api/v1/auth/oauth/callback/{provider}"

        # Parse additional scopes if provided
        additional_scopes = scopes.split(",") if scopes else None

        # Get authorization URL
        auth_url = OAuthService.get_authorization_url(
            oauth_provider, redirect_uri, state, additional_scopes
        )

        if not auth_url:
            raise HTTPException(status_code=500, detail="Failed to generate authorization URL")

        return {"authorization_url": auth_url, "state": state, "provider": provider}

    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError, RuntimeError) as e:
        logger.warning(
            "OAuth authorization error",
            extra={
                "error_type": type(e).__name__,
                "error": str(e),
                "provider": provider,
            },
        )
        raise HTTPException(status_code=400, detail=f"OAuth initialization failed: {str(e)}")
    except Exception:
        logger.exception("Unexpected error in OAuth authorization", extra={"provider": provider})
        raise HTTPException(status_code=500, detail="OAuth initialization failed")


@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    code: str = Query(...),
    state: str = Query(...),
):
    """Handle OAuth callback from provider"""
    try:
        # Parse provider enum
        try:
            oauth_provider = OAuthProvider(provider.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

        # Validate state token from Redis
        from app.core.redis import get_redis

        redis_client = await get_redis()
        stored_provider = await redis_client.get(f"oauth_state:{state}")

        if not stored_provider:
            raise HTTPException(
                status_code=400, detail="Invalid or expired state token. Please try again."
            )

        # Verify provider matches
        # ResilientRedisClient returns strings directly (already decoded)
        if stored_provider != provider.lower():
            raise HTTPException(status_code=400, detail="State token provider mismatch")

        # Delete state token to prevent reuse
        await redis_client.delete(f"oauth_state:{state}")

        # Build redirect URI (must match the one used in authorize)
        base_url = settings.API_BASE_URL.rstrip("/")
        redirect_uri = f"{base_url}/api/v1/auth/oauth/callback/{provider}"

        # Handle OAuth callback
        result = await OAuthService.handle_oauth_callback(
            db,
            oauth_provider,
            code,
            state,
            redirect_uri,
            locale=locale_from_request(request),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        if not result:
            raise HTTPException(status_code=401, detail="OAuth authentication failed")

        user, auth_data = result

        # Set cookies for web applications
        if settings.FRONTEND_URL:
            # Build cookie kwargs with optional domain for cross-subdomain SSO
            cookie_kwargs = {
                "max_age": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "secure": settings.SECURE_COOKIES,
                "httponly": True,
                "samesite": "lax",
            }
            if settings.COOKIE_DOMAIN:
                cookie_kwargs["domain"] = settings.COOKIE_DOMAIN

            refresh_cookie_kwargs = {
                "max_age": settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
                "secure": settings.SECURE_COOKIES,
                "httponly": True,
                "samesite": "lax",
            }
            if settings.COOKIE_DOMAIN:
                refresh_cookie_kwargs["domain"] = settings.COOKIE_DOMAIN

            # Set secure HTTP-only cookies
            response.set_cookie(
                key="access_token",
                value=auth_data["access_token"],
                **cookie_kwargs,
            )

            response.set_cookie(
                key="refresh_token",
                value=auth_data["refresh_token"],
                **refresh_cookie_kwargs,
            )

            # Redirect to frontend
            redirect_url = f"{settings.FRONTEND_URL}/dashboard"
            if auth_data.get("is_new_user"):
                redirect_url = f"{settings.FRONTEND_URL}/welcome"

            return {
                "status": "success",
                "redirect_url": redirect_url,
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "profile_image_url": user.profile_image_url,
                },
                "is_new_user": auth_data.get("is_new_user", False),
            }
        else:
            # Return tokens for API/SDK usage
            return {
                "access_token": auth_data["access_token"],
                "refresh_token": auth_data["refresh_token"],
                "token_type": "bearer",
                "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "profile_image_url": user.profile_image_url,
                },
                "is_new_user": auth_data.get("is_new_user", False),
            }

    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError) as e:
        logger.warning(
            "OAuth callback error",
            extra={
                "error_type": type(e).__name__,
                "error": str(e),
                "provider": provider,
            },
        )
        raise HTTPException(status_code=400, detail=f"OAuth callback failed: {str(e)}")
    except Exception:
        logger.exception("Unexpected error in OAuth callback", extra={"provider": provider})
        raise HTTPException(status_code=500, detail="OAuth callback processing failed")


@router.post("/link/{provider}")
async def link_oauth_account(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redirect_uri: Optional[str] = Query(None),
    purpose: Optional[str] = Query(
        None,
        description=(
            "Registered consent purpose (e.g. `creator-census.youtube`). Requests "
            "the purpose's extra provider scopes and records the grant on callback."
        ),
    ),
):
    """Link an OAuth account to existing user.

    The redirect_uri parameter is where the user will be redirected AFTER
    the OAuth flow completes (i.e., after Janua processes the callback).
    Janua always uses its own callback URL when talking to OAuth providers.

    With `purpose`, the link doubles as purpose-scoped consent: the purpose
    must be registered for this provider, its scopes are requested on top of
    the sign-in scopes (Google: incremental authorization), and an already
    linked provider is re-authorized as a scope upgrade instead of refused.
    Without `purpose`, behaviour is unchanged.
    """
    try:
        # Validate redirect_uri if provided (prevents open redirect)
        final_redirect = validate_redirect_url(redirect_uri)

        # Parse provider enum
        try:
            oauth_provider = OAuthProvider(provider.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

        consent_purpose = None
        if purpose is not None:
            consent_purpose = get_purpose(purpose)
            if consent_purpose is None:
                raise HTTPException(status_code=400, detail="unknown_purpose")
            if consent_purpose.provider != oauth_provider.value:
                raise HTTPException(status_code=400, detail="purpose_provider_mismatch")

        # Check if provider is already linked
        result = await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.user_id == current_user.id, OAuthAccount.provider == oauth_provider
            )
        )
        existing = result.scalar_one_or_none()

        if existing and consent_purpose is None:
            raise HTTPException(status_code=400, detail=f"{provider} account is already linked")

        # Check if provider is configured
        config = OAuthService.get_provider_config(oauth_provider)
        if not config:
            raise HTTPException(status_code=400, detail=f"Provider {provider} is not configured")

        # Generate state token with link flag
        state = OAuthService.generate_state_token()
        link_state = f"link_{current_user.id}_{state}"

        # Store link state in Redis with metadata (final redirect, user, etc.)
        from app.core.redis import get_redis

        redis_client = await get_redis()
        state_data = {
            "provider": provider.lower(),
            "user_id": str(current_user.id),
            "action": "link",
            "final_redirect": final_redirect,  # Where to redirect after OAuth completes
        }
        if consent_purpose is not None:
            state_data["purpose"] = consent_purpose.id
            state_data["upgrade"] = existing is not None
        await redis_client.set(
            f"oauth_state:{link_state}",
            json.dumps(state_data),
            ex=600,  # 10 minutes
        )

        # ALWAYS use Janua's callback URL for OAuth providers
        # The provider (GitHub, etc.) will redirect back to Janua,
        # then Janua will redirect to the final_redirect
        base_url = settings.API_BASE_URL.rstrip("/")
        oauth_callback_uri = f"{base_url}/api/v1/auth/oauth/link/callback/{provider}"

        # Get authorization URL using Janua's callback
        auth_url = OAuthService.get_authorization_url(
            oauth_provider,
            oauth_callback_uri,
            link_state,
            list(consent_purpose.additional_scopes) if consent_purpose else None,
            include_granted_scopes=consent_purpose is not None,
        )

        if not auth_url:
            raise HTTPException(status_code=500, detail="Failed to generate authorization URL")

        response_body = {
            "authorization_url": auth_url,
            "state": link_state,
            "provider": provider,
            "action": "link",
        }
        if consent_purpose is not None:
            response_body["purpose"] = consent_purpose.id
            response_body["scope_upgrade"] = existing is not None
        return response_body

    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError) as e:
        logger.warning(
            "OAuth link error",
            extra={
                "error_type": type(e).__name__,
                "error": str(e),
                "provider": provider,
            },
        )
        raise HTTPException(status_code=400, detail=f"OAuth link failed: {str(e)}")
    except Exception:
        logger.exception("Unexpected error in OAuth link", extra={"provider": provider})
        raise HTTPException(status_code=500, detail="OAuth link initialization failed")


@router.get("/link/callback/{provider}")
async def link_oauth_callback(
    provider: str,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    code: str = Query(...),
    state: str = Query(...),
):
    """Handle OAuth callback for account linking.

    This endpoint receives the callback from OAuth providers (GitHub, etc.)
    after the user authorizes the app. It then:
    1. Exchanges the code for tokens
    2. Links the OAuth account to the user
    3. Redirects to the final destination (the original client page)
    """
    from urllib.parse import urlencode

    from starlette.responses import RedirectResponse

    try:
        # Parse provider enum
        try:
            oauth_provider = OAuthProvider(provider.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

        # Retrieve and validate state from Redis
        from app.core.redis import get_redis

        redis_client = await get_redis()
        stored_state_data = await redis_client.get(f"oauth_state:{state}")

        if not stored_state_data:
            raise HTTPException(
                status_code=400, detail="Invalid or expired state token. Please try again."
            )

        # Parse state data
        # ResilientRedisClient returns strings directly (already decoded)
        state_data = json.loads(stored_state_data)

        # Verify it's a link action
        if state_data.get("action") != "link":
            raise HTTPException(status_code=400, detail="Invalid state: not a link action")

        # Verify provider matches
        if state_data.get("provider") != provider.lower():
            raise HTTPException(status_code=400, detail="State token provider mismatch")

        # Get user ID from state
        user_id = state_data.get("user_id")
        final_redirect = state_data.get("final_redirect")

        # Delete state token to prevent reuse
        await redis_client.delete(f"oauth_state:{state}")

        # Build the callback URI that was used (must match for token exchange)
        base_url = settings.API_BASE_URL.rstrip("/")
        oauth_callback_uri = f"{base_url}/api/v1/auth/oauth/link/callback/{provider}"

        # Exchange code for tokens
        tokens = await OAuthService.exchange_code_for_tokens(
            oauth_provider, code, oauth_callback_uri
        )

        if not tokens:
            raise HTTPException(status_code=401, detail="Failed to exchange OAuth code for tokens")

        # Get user info from provider
        user_info = await OAuthService.get_user_info(oauth_provider, tokens["access_token"])

        if not user_info:
            raise HTTPException(
                status_code=401, detail="Failed to get user info from OAuth provider"
            )

        # Get the user from database

        result = await db.execute(select(User).where(User.id == UUID(user_id)))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if this OAuth account is already linked to another user.
        # `get_user_info` returns the NORMALIZED shape, whose id key is
        # `provider_user_id`; the raw `id`/`sub` keys are kept only as a
        # fallback. Reading only `id`/`sub` stored the literal "None" for every
        # link, which made every second linker collide with the first.
        raw_provider_user_id = (
            user_info.get("provider_user_id") or user_info.get("id") or user_info.get("sub")
        )
        if not raw_provider_user_id:
            raise HTTPException(
                status_code=401, detail="Failed to get user info from OAuth provider"
            )
        provider_user_id = str(raw_provider_user_id)
        existing_result = await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == oauth_provider,
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )
        existing_account = existing_result.scalars().first()

        if existing_account:
            if str(existing_account.user_id) != user_id:
                error_msg = f"This {provider} account is already linked to another user"
                if final_redirect:
                    return RedirectResponse(
                        url=f"{final_redirect}?error={urlencode({'error': error_msg})}",
                        status_code=302,
                    )
                raise HTTPException(status_code=400, detail=error_msg)

        # Purpose-scoped consent (set by POST /link/{provider}?purpose=...)
        purpose_id = state_data.get("purpose")
        consent_purpose = get_purpose(purpose_id) if purpose_id else None
        if purpose_id and (
            consent_purpose is None or consent_purpose.provider != oauth_provider.value
        ):
            raise HTTPException(status_code=400, detail="unknown_purpose")

        # Granted scopes as the provider reported them in the token response
        granted_scopes = OAuthService._parse_scopes_from_tokens(tokens, oauth_provider)

        if consent_purpose is not None:
            missing = [s for s in consent_purpose.additional_scopes if s not in granted_scopes]
            if missing:
                # The user unticked a requested scope on the provider's
                # consent screen. Record nothing: a partial grant is not a grant.
                logger.warning(
                    "Purpose consent incomplete",
                    extra={
                        "provider": provider,
                        "purpose": consent_purpose.id,
                        "missing_scopes": missing,
                    },
                )
                if final_redirect:
                    return RedirectResponse(
                        url=_append_query(final_redirect, error="purpose_scopes_not_granted"),
                        status_code=302,
                    )
                raise HTTPException(status_code=400, detail="purpose_scopes_not_granted")

        provider_data = {
            "scopes": granted_scopes,
            "raw_user_info": user_info,
        }
        token_expires_at = (
            datetime.utcnow() + timedelta(seconds=int(tokens["expires_in"]))
            if tokens.get("expires_in")
            else None
        )

        user_link = None
        if consent_purpose is not None:
            link_result = await db.execute(
                select(OAuthAccount).where(
                    OAuthAccount.user_id == UUID(user_id),
                    OAuthAccount.provider == oauth_provider,
                )
            )
            user_link = link_result.scalars().first()

        if user_link is not None:
            # Scope upgrade of an existing link. It must be the SAME provider
            # account; rows written before the provider_user_id fix hold the
            # literal "None" and are repaired here.
            if user_link.provider_user_id not in (provider_user_id, "None", None, ""):
                error_code = "provider_account_mismatch"
                if final_redirect:
                    return RedirectResponse(
                        url=_append_query(final_redirect, error=error_code),
                        status_code=302,
                    )
                raise HTTPException(status_code=400, detail=error_code)
            user_link.provider_user_id = provider_user_id
            user_link.provider_email = user_info.get("email") or user_link.provider_email
            user_link.access_token = tokens["access_token"]
            if tokens.get("refresh_token"):
                user_link.refresh_token = tokens["refresh_token"]
            user_link.token_expires_at = token_expires_at
            user_link.provider_data = provider_data
            oauth_account = user_link
        else:
            # Create OAuth account link
            oauth_account = OAuthAccount(
                user_id=UUID(user_id),
                provider=oauth_provider,
                provider_user_id=provider_user_id,
                provider_email=user_info.get("email"),
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token"),
                token_expires_at=token_expires_at,
                provider_data=provider_data,
            )
            db.add(oauth_account)

            # Log activity
            activity = ActivityLog(
                user_id=UUID(user_id),
                action="oauth_linked",
                activity_metadata={"provider": provider, "provider_email": user_info.get("email")},
            )
            db.add(activity)

        if consent_purpose is not None:
            connection = await ConnectedAccountService(db).record_purpose_grant(
                user_id=UUID(user_id),
                oauth_account=oauth_account,
                purpose=consent_purpose,
                granted_scopes=granted_scopes,
            )
            db.add(
                ActivityLog(
                    user_id=UUID(user_id),
                    action="consent.purpose.granted",
                    resource_type="connected_account",
                    resource_id=str(connection.id),
                    activity_metadata={
                        "purpose": consent_purpose.id,
                        "provider": consent_purpose.provider,
                        "scopes": list(consent_purpose.additional_scopes),
                        "scope_upgrade": user_link is not None,
                    },
                )
            )

        await db.commit()

        # SECURITY: Use parameterized logging to prevent log injection
        logger.info(
            "Successfully linked OAuth account", extra={"provider": provider, "user_id": user_id}
        )

        # Redirect to final destination or return success
        if final_redirect:
            return RedirectResponse(url=final_redirect, status_code=302)

        return {
            "status": "success",
            "message": f"{provider} account linked successfully",
            "provider": provider,
            "provider_email": user_info.get("email"),
        }

    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
        logger.warning(
            "OAuth link callback error",
            extra={
                "error_type": type(e).__name__,
                "error": str(e),
                "provider": provider,
            },
        )
        raise HTTPException(status_code=400, detail=f"OAuth link callback failed: {str(e)}")
    except Exception:
        logger.exception("Unexpected error in OAuth link callback", extra={"provider": provider})
        raise HTTPException(status_code=500, detail="OAuth link callback processing failed")


@router.delete("/unlink/{provider}")
async def unlink_oauth_account(
    provider: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Unlink an OAuth account from user"""
    try:
        # Parse provider enum
        try:
            oauth_provider = OAuthProvider(provider.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

        # Find OAuth account
        result = await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.user_id == current_user.id, OAuthAccount.provider == oauth_provider
            )
        )
        oauth_account = result.scalar_one_or_none()

        if not oauth_account:
            raise HTTPException(status_code=404, detail=f"{provider} account is not linked")

        # Check if user has other auth methods
        has_password = current_user.password_hash is not None
        count_result = await db.execute(
            select(func.count()).select_from(
                select(OAuthAccount)
                .where(
                    OAuthAccount.user_id == current_user.id, OAuthAccount.provider != oauth_provider
                )
                .subquery()
            )
        )
        other_oauth = count_result.scalar()

        if not has_password and other_oauth == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot unlink the only authentication method. Please set a password first.",
            )

        # Delete OAuth account
        await db.delete(oauth_account)

        # Unlinking a provider ends every delegated connection and purpose
        # consent built on it; nothing may keep borrowing its token.
        ended_purposes = await ConnectedAccountService(db).revoke_for_provider(
            current_user.id, oauth_provider.value
        )
        for purpose_id in ended_purposes:
            db.add(
                ActivityLog(
                    user_id=current_user.id,
                    action="consent.purpose.revoked",
                    resource_type="connected_account",
                    activity_metadata={"purpose": purpose_id, "reason": "provider_unlinked"},
                )
            )

        # Log activity
        activity = ActivityLog(
            user_id=current_user.id,
            action="oauth_unlinked",
            activity_metadata={"provider": provider},
        )
        db.add(activity)

        await db.commit()

        return {"message": f"{provider} account unlinked successfully", "provider": provider}

    except HTTPException:
        raise
    except (ValueError, KeyError, TypeError) as e:
        logger.warning(
            "OAuth unlink error",
            extra={
                "error_type": type(e).__name__,
                "error": str(e),
                "provider": provider,
            },
        )
        raise HTTPException(status_code=400, detail=f"OAuth unlink failed: {str(e)}")
    except Exception:
        logger.exception("Unexpected error in OAuth unlink", extra={"provider": provider})
        raise HTTPException(status_code=500, detail="Failed to unlink OAuth account")


@router.get("/accounts")
async def get_linked_accounts(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Get all linked OAuth accounts for current user"""
    # Get all linked OAuth accounts
    result = await db.execute(select(OAuthAccount).where(OAuthAccount.user_id == current_user.id))
    oauth_accounts = result.scalars().all()

    # Get available providers
    all_providers = []
    for provider in list(OAuthProvider):
        config = OAuthService.get_provider_config(provider)
        if config:
            linked_account = next((acc for acc in oauth_accounts if acc.provider == provider), None)

            provider_info = {
                "provider": provider.value,
                "name": provider.value.capitalize(),
                "linked": linked_account is not None,
                "enabled": True,
            }

            if linked_account:
                provider_info.update(
                    {
                        "provider_email": linked_account.provider_email,
                        "linked_at": linked_account.created_at,
                        "last_updated": linked_account.updated_at,
                    }
                )

            all_providers.append(provider_info)

    # Get other auth methods status
    passkeys_result = await db.execute(
        select(func.count()).select_from(
            select(Passkey).where(Passkey.user_id == current_user.id).subquery()
        )
    )
    passkeys_count = passkeys_result.scalar()

    auth_methods = {
        "password": current_user.password_hash is not None,
        "mfa_enabled": current_user.mfa_enabled,
        "passkeys_count": passkeys_count,
    }

    return {
        "oauth_accounts": all_providers,
        "auth_methods": auth_methods,
        "total_linked": len([p for p in all_providers if p["linked"]]),
    }
