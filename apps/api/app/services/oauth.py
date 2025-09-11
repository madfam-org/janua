"""
OAuth service for handling third-party authentication
"""

import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import secrets
import httpx
from urllib.parse import urlencode

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import User, OAuthAccount, OAuthProvider, UserStatus
from app.config import settings
from app.services.auth import AuthService

logger = logging.getLogger(__name__)


class OAuthService:
    """Service for handling OAuth authentication"""
    
    # OAuth provider configurations
    PROVIDERS = {
        OAuthProvider.GOOGLE: {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "user_info_url": "https://www.googleapis.com/oauth2/v1/userinfo",
            "scopes": ["openid", "email", "profile"],
            "client_id_setting": "OAUTH_GOOGLE_CLIENT_ID",
            "client_secret_setting": "OAUTH_GOOGLE_CLIENT_SECRET"
        },
        OAuthProvider.GITHUB: {
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "user_info_url": "https://api.github.com/user",
            "email_url": "https://api.github.com/user/emails",
            "scopes": ["user:email"],
            "client_id_setting": "OAUTH_GITHUB_CLIENT_ID",
            "client_secret_setting": "OAUTH_GITHUB_CLIENT_SECRET"
        },
        OAuthProvider.MICROSOFT: {
            "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "user_info_url": "https://graph.microsoft.com/v1.0/me",
            "scopes": ["openid", "email", "profile"],
            "client_id_setting": "OAUTH_MICROSOFT_CLIENT_ID",
            "client_secret_setting": "OAUTH_MICROSOFT_CLIENT_SECRET"
        }
    }
    
    @classmethod
    def get_provider_config(cls, provider: OAuthProvider) -> Optional[Dict[str, Any]]:
        """Get configuration for an OAuth provider"""
        if provider not in cls.PROVIDERS:
            return None
        
        config = cls.PROVIDERS[provider].copy()
        
        # Get client credentials from settings
        client_id = getattr(settings, config["client_id_setting"], None)
        client_secret = getattr(settings, config["client_secret_setting"], None)
        
        if not client_id or not client_secret:
            logger.warning(f"OAuth provider {provider.value} not configured")
            return None
        
        config["client_id"] = client_id
        config["client_secret"] = client_secret
        
        return config
    
    @classmethod
    def generate_state_token(cls) -> str:
        """Generate a secure state token for OAuth flow"""
        return secrets.token_urlsafe(32)
    
    @classmethod
    def get_authorization_url(
        cls,
        provider: OAuthProvider,
        redirect_uri: str,
        state: str,
        additional_scopes: Optional[list] = None
    ) -> Optional[str]:
        """Generate OAuth authorization URL"""
        config = cls.get_provider_config(provider)
        if not config:
            return None
        
        # Combine default and additional scopes
        scopes = config["scopes"].copy()
        if additional_scopes:
            scopes.extend(additional_scopes)
        
        # Build authorization parameters
        params = {
            "client_id": config["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": " ".join(scopes)
        }
        
        # Add provider-specific parameters
        if provider == OAuthProvider.GOOGLE:
            params["access_type"] = "offline"
            params["prompt"] = "consent"
        elif provider == OAuthProvider.MICROSOFT:
            params["response_mode"] = "query"
        
        # Build authorization URL
        auth_url = f"{config['auth_url']}?{urlencode(params)}"
        return auth_url
    
    @classmethod
    async def exchange_code_for_tokens(
        cls,
        provider: OAuthProvider,
        code: str,
        redirect_uri: str
    ) -> Optional[Dict[str, Any]]:
        """Exchange authorization code for access tokens"""
        config = cls.get_provider_config(provider)
        if not config:
            return None
        
        # Prepare token exchange request
        data = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        
        headers = {"Accept": "application/json"}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config["token_url"],
                    data=data,
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.error(f"Token exchange failed: {response.text}")
                    return None
                
                return response.json()
        except Exception as e:
            logger.error(f"Error exchanging OAuth code: {e}")
            return None
    
    @classmethod
    async def get_user_info(
        cls,
        provider: OAuthProvider,
        access_token: str
    ) -> Optional[Dict[str, Any]]:
        """Get user information from OAuth provider"""
        config = cls.get_provider_config(provider)
        if not config:
            return None
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            async with httpx.AsyncClient() as client:
                # Get basic user info
                response = await client.get(
                    config["user_info_url"],
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.error(f"Failed to get user info: {response.text}")
                    return None
                
                user_info = response.json()
                
                # GitHub requires separate email endpoint
                if provider == OAuthProvider.GITHUB and "email_url" in config:
                    email_response = await client.get(
                        config["email_url"],
                        headers=headers
                    )
                    
                    if email_response.status_code == 200:
                        emails = email_response.json()
                        # Get primary verified email
                        for email in emails:
                            if email.get("primary") and email.get("verified"):
                                user_info["email"] = email["email"]
                                break
                
                return cls.normalize_user_info(provider, user_info)
                
        except Exception as e:
            logger.error(f"Error getting OAuth user info: {e}")
            return None
    
    @classmethod
    def normalize_user_info(
        cls,
        provider: OAuthProvider,
        raw_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalize user info across different providers"""
        normalized = {
            "provider": provider.value,
            "provider_user_id": None,
            "email": None,
            "email_verified": False,
            "first_name": None,
            "last_name": None,
            "name": None,
            "profile_image_url": None,
            "raw_data": raw_info
        }
        
        if provider == OAuthProvider.GOOGLE:
            normalized["provider_user_id"] = raw_info.get("id")
            normalized["email"] = raw_info.get("email")
            normalized["email_verified"] = raw_info.get("verified_email", False)
            normalized["first_name"] = raw_info.get("given_name")
            normalized["last_name"] = raw_info.get("family_name")
            normalized["name"] = raw_info.get("name")
            normalized["profile_image_url"] = raw_info.get("picture")
            
        elif provider == OAuthProvider.GITHUB:
            normalized["provider_user_id"] = str(raw_info.get("id"))
            normalized["email"] = raw_info.get("email")
            normalized["email_verified"] = True  # GitHub only returns verified emails
            normalized["name"] = raw_info.get("name")
            normalized["profile_image_url"] = raw_info.get("avatar_url")
            # GitHub doesn't provide separate first/last name
            if normalized["name"]:
                parts = normalized["name"].split(" ", 1)
                normalized["first_name"] = parts[0]
                if len(parts) > 1:
                    normalized["last_name"] = parts[1]
                    
        elif provider == OAuthProvider.MICROSOFT:
            normalized["provider_user_id"] = raw_info.get("id")
            normalized["email"] = raw_info.get("mail") or raw_info.get("userPrincipalName")
            normalized["email_verified"] = True  # Microsoft only returns verified emails
            normalized["first_name"] = raw_info.get("givenName")
            normalized["last_name"] = raw_info.get("surname")
            normalized["name"] = raw_info.get("displayName")
            
        return normalized
    
    @classmethod
    def find_or_create_user(
        cls,
        db: Session,
        provider: OAuthProvider,
        user_info: Dict[str, Any],
        tokens: Dict[str, Any]
    ) -> Tuple[User, bool]:
        """Find existing user or create new one from OAuth info"""
        # Check if OAuth account exists
        oauth_account = db.query(OAuthAccount).filter(
            and_(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == user_info["provider_user_id"]
            )
        ).first()
        
        if oauth_account:
            # Existing OAuth account - update tokens
            oauth_account.access_token = tokens.get("access_token")
            oauth_account.refresh_token = tokens.get("refresh_token")
            if tokens.get("expires_in"):
                oauth_account.token_expires_at = datetime.utcnow() + timedelta(
                    seconds=tokens["expires_in"]
                )
            oauth_account.provider_data = user_info["raw_data"]
            db.commit()
            
            return oauth_account.user, False
        
        # Check if user with email exists
        user = None
        if user_info.get("email"):
            user = db.query(User).filter(
                User.email == user_info["email"],
                User.status == UserStatus.ACTIVE
            ).first()
        
        # Create new user if doesn't exist
        is_new_user = False
        if not user:
            user = User(
                email=user_info.get("email"),
                email_verified=user_info.get("email_verified", False),
                first_name=user_info.get("first_name"),
                last_name=user_info.get("last_name"),
                profile_image_url=user_info.get("profile_image_url"),
                status=UserStatus.ACTIVE
            )
            db.add(user)
            db.flush()
            is_new_user = True
        
        # Create OAuth account link
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=user_info["provider_user_id"],
            provider_email=user_info.get("email"),
            access_token=tokens.get("access_token"),
            refresh_token=tokens.get("refresh_token"),
            token_expires_at=(
                datetime.utcnow() + timedelta(seconds=tokens["expires_in"])
                if tokens.get("expires_in") else None
            ),
            provider_data=user_info["raw_data"]
        )
        db.add(oauth_account)
        
        # Update user profile if new info available
        if not user.first_name and user_info.get("first_name"):
            user.first_name = user_info["first_name"]
        if not user.last_name and user_info.get("last_name"):
            user.last_name = user_info["last_name"]
        if not user.profile_image_url and user_info.get("profile_image_url"):
            user.profile_image_url = user_info["profile_image_url"]
        
        # Mark email as verified if OAuth provider verified it
        if user_info.get("email_verified") and not user.email_verified:
            user.email_verified = True
            user.email_verified_at = datetime.utcnow()
        
        db.commit()
        
        return user, is_new_user
    
    @classmethod
    async def handle_oauth_callback(
        cls,
        db: Session,
        provider: OAuthProvider,
        code: str,
        state: str,
        redirect_uri: str
    ) -> Optional[Tuple[User, Dict[str, Any]]]:
        """Handle OAuth callback and create/update user"""
        # Exchange code for tokens
        tokens = await cls.exchange_code_for_tokens(provider, code, redirect_uri)
        if not tokens:
            logger.error("Failed to exchange OAuth code for tokens")
            return None
        
        # Get user info from provider
        user_info = await cls.get_user_info(provider, tokens["access_token"])
        if not user_info:
            logger.error("Failed to get OAuth user info")
            return None
        
        # Find or create user
        user, is_new = cls.find_or_create_user(db, provider, user_info, tokens)
        
        # Create session tokens
        access_token, refresh_token, session = AuthService.create_user_session(
            db, user
        )
        
        return user, {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "is_new_user": is_new
        }