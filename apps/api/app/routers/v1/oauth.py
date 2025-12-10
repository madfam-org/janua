"""
OAuth authentication endpoints
"""

import logging
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
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

    for provider in OAuthProvider:
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
        redirect_to = validate_redirect_url(redirect_to)
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
        from app.core.database import get_redis

        redis_client = await get_redis()
        await redis_client.setex(
            f"oauth_state:{state}",
            600,  # 10 minutes
            provider,  # Store provider for additional validation
        )

        # Build redirect URI if not provided
        if not redirect_uri:
            # Use the API base URL + callback endpoint
            base_url = str(request.base_url).rstrip("/")
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
    except Exception as e:
        logger.error(f"OAuth authorization error: {e}")
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
        from app.core.database import get_redis

        redis_client = await get_redis()
        stored_provider = await redis_client.get(f"oauth_state:{state}")

        if not stored_provider:
            raise HTTPException(
                status_code=400, detail="Invalid or expired state token. Please try again."
            )

        # Verify provider matches
        if stored_provider.decode() != provider.lower():
            raise HTTPException(status_code=400, detail="State token provider mismatch")

        # Delete state token to prevent reuse
        await redis_client.delete(f"oauth_state:{state}")

        # Build redirect URI (must match the one used in authorize)
        base_url = str(request.base_url).rstrip("/")
        redirect_uri = f"{base_url}/api/v1/auth/oauth/callback/{provider}"

        # Handle OAuth callback
        result = await OAuthService.handle_oauth_callback(
            db, oauth_provider, code, state, redirect_uri
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
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail="OAuth callback processing failed")


@router.post("/link/{provider}")
async def link_oauth_account(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redirect_uri: Optional[str] = Query(None),
):
    """Link an OAuth account to existing user"""
    try:
        # Parse provider enum
        try:
            oauth_provider = OAuthProvider(provider.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

        # Check if provider is already linked
        result = await db.execute(
            select(OAuthAccount).where(
                OAuthAccount.user_id == current_user.id, OAuthAccount.provider == oauth_provider
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(status_code=400, detail=f"{provider} account is already linked")

        # Check if provider is configured
        config = OAuthService.get_provider_config(oauth_provider)
        if not config:
            raise HTTPException(status_code=400, detail=f"Provider {provider} is not configured")

        # Generate state token with link flag
        state = OAuthService.generate_state_token()

        # Store link intent in state (in production, use Redis)
        # For now, we'll encode it in the state token
        link_state = f"link_{current_user.id}_{state}"

        # Build redirect URI if not provided
        if not redirect_uri:
            base_url = str(request.base_url).rstrip("/")
            redirect_uri = f"{base_url}/api/v1/auth/oauth/callback/{provider}?link=true"

        # Get authorization URL
        auth_url = OAuthService.get_authorization_url(
            oauth_provider, redirect_uri, link_state, None
        )

        if not auth_url:
            raise HTTPException(status_code=500, detail="Failed to generate authorization URL")

        return {
            "authorization_url": auth_url,
            "state": link_state,
            "provider": provider,
            "action": "link",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth link error: {e}")
        raise HTTPException(status_code=500, detail="OAuth link initialization failed")


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
        db.delete(oauth_account)

        # Log activity
        activity = ActivityLog(
            user_id=current_user.id, action="oauth_unlinked", details={"provider": provider}
        )
        db.add(activity)

        await db.commit()

        return {"message": f"{provider} account unlinked successfully", "provider": provider}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth unlink error: {e}")
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
    for provider in OAuthProvider:
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
