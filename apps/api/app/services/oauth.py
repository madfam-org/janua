"""
OAuth service for handling third-party authentication
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.config import settings
from app.services.auth_service import AuthService

from ..models import OAuthAccount, OAuthProvider, User, UserStatus

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
            "client_secret_setting": "OAUTH_GOOGLE_CLIENT_SECRET",
        },
        OAuthProvider.GITHUB: {
            "auth_url": "https://github.com/login/oauth/authorize",
            "token_url": "https://github.com/login/oauth/access_token",
            "user_info_url": "https://api.github.com/user",
            "email_url": "https://api.github.com/user/emails",
            "scopes": ["user:email", "repo", "read:user"],
            "client_id_setting": "OAUTH_GITHUB_CLIENT_ID",
            "client_secret_setting": "OAUTH_GITHUB_CLIENT_SECRET",
        },
        OAuthProvider.MICROSOFT: {
            "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "user_info_url": "https://graph.microsoft.com/v1.0/me",
            "scopes": ["openid", "email", "profile"],
            "client_id_setting": "OAUTH_MICROSOFT_CLIENT_ID",
            "client_secret_setting": "OAUTH_MICROSOFT_CLIENT_SECRET",
        },
        OAuthProvider.APPLE: {
            "auth_url": "https://appleid.apple.com/auth/authorize",
            "token_url": "https://appleid.apple.com/auth/token",
            "scopes": ["name", "email"],
            "client_id_setting": "OAUTH_APPLE_CLIENT_ID",
            "client_secret_setting": None,  # Apple uses JWT-based client secret
            "response_mode": "form_post",
        },
        OAuthProvider.DISCORD: {
            "auth_url": "https://discord.com/api/oauth2/authorize",
            "token_url": "https://discord.com/api/oauth2/token",
            "user_info_url": "https://discord.com/api/users/@me",
            "scopes": ["identify", "email"],
            "client_id_setting": "OAUTH_DISCORD_CLIENT_ID",
            "client_secret_setting": "OAUTH_DISCORD_CLIENT_SECRET",
        },
        OAuthProvider.TWITTER: {
            "auth_url": "https://twitter.com/i/oauth2/authorize",
            "token_url": "https://api.twitter.com/2/oauth2/token",
            "user_info_url": "https://api.twitter.com/2/users/me",
            "scopes": ["users.read", "tweet.read"],
            "client_id_setting": "OAUTH_TWITTER_CLIENT_ID",
            "client_secret_setting": "OAUTH_TWITTER_CLIENT_SECRET",
            "pkce_required": True,
        },
        OAuthProvider.LINKEDIN: {
            "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
            "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
            "user_info_url": "https://api.linkedin.com/v2/userinfo",
            "scopes": ["openid", "profile", "email"],
            "client_id_setting": "OAUTH_LINKEDIN_CLIENT_ID",
            "client_secret_setting": "OAUTH_LINKEDIN_CLIENT_SECRET",
        },
        OAuthProvider.SLACK: {
            "auth_url": "https://slack.com/oauth/v2/authorize",
            "token_url": "https://slack.com/api/oauth.v2.access",
            "user_info_url": "https://slack.com/api/users.identity",
            "scopes": ["identity.basic", "identity.email", "identity.avatar"],
            "client_id_setting": "OAUTH_SLACK_CLIENT_ID",
            "client_secret_setting": "OAUTH_SLACK_CLIENT_SECRET",
        },
    }

    @classmethod
    def get_provider_config(cls, provider: OAuthProvider) -> Optional[Dict[str, Any]]:
        """Get configuration for an OAuth provider"""
        if provider not in cls.PROVIDERS:
            return None

        config = cls.PROVIDERS[provider].copy()

        # Get client credentials from settings
        client_id = getattr(settings, config["client_id_setting"], None)

        # Apple uses JWT-based client secret, handle specially
        if provider == OAuthProvider.APPLE:
            team_id = getattr(settings, "OAUTH_APPLE_TEAM_ID", None)
            key_id = getattr(settings, "OAUTH_APPLE_KEY_ID", None)
            private_key = getattr(settings, "OAUTH_APPLE_PRIVATE_KEY", None)

            if not client_id or not team_id or not key_id or not private_key:
                logger.warning(f"OAuth provider {provider.value} not configured")
                return None

            config["client_id"] = client_id
            config["team_id"] = team_id
            config["key_id"] = key_id
            config["private_key"] = private_key
            config["client_secret"] = cls._generate_apple_client_secret(
                client_id, team_id, key_id, private_key
            )
        else:
            client_secret = getattr(settings, config["client_secret_setting"], None)

            if not client_id or not client_secret:
                logger.warning(f"OAuth provider {provider.value} not configured")
                return None

            config["client_id"] = client_id
            config["client_secret"] = client_secret

        return config

    @classmethod
    def _generate_apple_client_secret(
        cls, client_id: str, team_id: str, key_id: str, private_key: str
    ) -> str:
        """Generate Apple client secret JWT"""
        from datetime import datetime, timedelta

        import jwt

        now = datetime.utcnow()
        payload = {
            "iss": team_id,
            "iat": now,
            "exp": now + timedelta(days=180),  # Max 6 months
            "aud": "https://appleid.apple.com",
            "sub": client_id,
        }

        headers = {"kid": key_id, "alg": "ES256"}

        return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)

    @classmethod
    def generate_state_token(cls) -> str:
        """Generate a secure state token for OAuth flow"""
        return secrets.token_urlsafe(32)

    @classmethod
    def _parse_scopes_from_tokens(cls, tokens: Dict[str, Any], provider: OAuthProvider) -> list:
        """Parse granted scopes from token response.

        GitHub returns scopes as comma-separated string in the token response.
        Other providers may return space-separated strings or lists.
        Falls back to configured scopes if provider doesn't return them.
        """
        granted_scopes = []

        if tokens.get("scope"):
            scope_str = tokens.get("scope", "")
            # GitHub uses comma-separated scopes
            if "," in scope_str:
                granted_scopes = [s.strip() for s in scope_str.split(",")]
            else:
                # Most providers use space-separated
                granted_scopes = scope_str.split()

        # Fallback to configured scopes if provider doesn't return them
        if not granted_scopes:
            config = cls.get_provider_config(provider)
            if config:
                granted_scopes = config.get("scopes", [])

        return granted_scopes

    @classmethod
    def get_authorization_url(
        cls,
        provider: OAuthProvider,
        redirect_uri: str,
        state: str,
        additional_scopes: Optional[list] = None,
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
            "scope": " ".join(scopes),
        }

        # Add provider-specific parameters
        if provider == OAuthProvider.GOOGLE:
            params["access_type"] = "offline"
            params["prompt"] = "consent"
        elif provider == OAuthProvider.MICROSOFT:
            params["response_mode"] = "query"
        elif provider == OAuthProvider.APPLE:
            params["response_mode"] = "form_post"
            params["response_type"] = "code id_token"
        elif provider == OAuthProvider.TWITTER:
            # Twitter requires PKCE
            import base64
            import hashlib

            code_verifier = secrets.token_urlsafe(32)
            code_challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
                .rstrip(b"=")
                .decode()
            )
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
            # Store code_verifier in state for later use
            params["state"] = f"{state}:{code_verifier}"
        elif provider == OAuthProvider.SLACK:
            # Slack uses different scope format
            params["user_scope"] = params.pop("scope")

        # Build authorization URL
        auth_url = f"{config['auth_url']}?{urlencode(params)}"
        return auth_url

    @classmethod
    async def exchange_code_for_tokens(
        cls, provider: OAuthProvider, code: str, redirect_uri: str
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
            "grant_type": "authorization_code",
        }

        headers = {"Accept": "application/json"}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(config["token_url"], data=data, headers=headers)

                if response.status_code != 200:
                    logger.error(f"Token exchange failed: {response.text}")
                    return None

                return response.json()
        except Exception as e:
            logger.error(f"Error exchanging OAuth code: {e}")
            return None

    @classmethod
    async def get_user_info(
        cls, provider: OAuthProvider, access_token: str
    ) -> Optional[Dict[str, Any]]:
        """Get user information from OAuth provider"""
        config = cls.get_provider_config(provider)
        if not config:
            return None

        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            async with httpx.AsyncClient() as client:
                # Get basic user info
                response = await client.get(config["user_info_url"], headers=headers)

                if response.status_code != 200:
                    logger.error(f"Failed to get user info: {response.text}")
                    return None

                user_info = response.json()

                # GitHub requires separate email endpoint
                if provider == OAuthProvider.GITHUB and "email_url" in config:
                    email_response = await client.get(config["email_url"], headers=headers)

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
        cls, provider: OAuthProvider, raw_info: Dict[str, Any]
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
            "raw_data": raw_info,
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

        elif provider == OAuthProvider.APPLE:
            normalized["provider_user_id"] = raw_info.get("sub")
            normalized["email"] = raw_info.get("email")
            normalized["email_verified"] = raw_info.get("email_verified", False)
            # Apple provides name only on first authorization
            if raw_info.get("name"):
                normalized["first_name"] = raw_info["name"].get("firstName")
                normalized["last_name"] = raw_info["name"].get("lastName")
                if normalized["first_name"] and normalized["last_name"]:
                    normalized["name"] = f"{normalized['first_name']} {normalized['last_name']}"

        elif provider == OAuthProvider.DISCORD:
            normalized["provider_user_id"] = raw_info.get("id")
            normalized["email"] = raw_info.get("email")
            normalized["email_verified"] = raw_info.get("verified", False)
            normalized["name"] = raw_info.get("global_name") or raw_info.get("username")
            avatar_hash = raw_info.get("avatar")
            if avatar_hash:
                normalized[
                    "profile_image_url"
                ] = f"https://cdn.discordapp.com/avatars/{raw_info.get('id')}/{avatar_hash}.png"
            # Discord doesn't provide first/last name
            if normalized["name"]:
                parts = normalized["name"].split(" ", 1)
                normalized["first_name"] = parts[0]
                if len(parts) > 1:
                    normalized["last_name"] = parts[1]

        elif provider == OAuthProvider.TWITTER:
            data = raw_info.get("data", raw_info)
            normalized["provider_user_id"] = data.get("id")
            normalized["name"] = data.get("name")
            normalized["profile_image_url"] = data.get("profile_image_url")
            # Twitter doesn't provide email by default
            normalized["email"] = data.get("email")
            normalized["email_verified"] = True if normalized["email"] else False
            # Parse name
            if normalized["name"]:
                parts = normalized["name"].split(" ", 1)
                normalized["first_name"] = parts[0]
                if len(parts) > 1:
                    normalized["last_name"] = parts[1]

        elif provider == OAuthProvider.LINKEDIN:
            normalized["provider_user_id"] = raw_info.get("sub")
            normalized["email"] = raw_info.get("email")
            normalized["email_verified"] = raw_info.get("email_verified", False)
            normalized["first_name"] = raw_info.get("given_name")
            normalized["last_name"] = raw_info.get("family_name")
            normalized["name"] = raw_info.get("name")
            normalized["profile_image_url"] = raw_info.get("picture")

        elif provider == OAuthProvider.SLACK:
            user = raw_info.get("user", raw_info)
            normalized["provider_user_id"] = user.get("id")
            normalized["email"] = user.get("email")
            normalized["email_verified"] = True  # Slack only returns verified emails
            normalized["name"] = user.get("name")
            normalized["profile_image_url"] = user.get("image_192") or user.get("image_72")
            # Parse name
            if normalized["name"]:
                parts = normalized["name"].split(" ", 1)
                normalized["first_name"] = parts[0]
                if len(parts) > 1:
                    normalized["last_name"] = parts[1]

        return normalized

    @classmethod
    def find_or_create_user(
        cls, db: Session, provider: OAuthProvider, user_info: Dict[str, Any], tokens: Dict[str, Any]
    ) -> Tuple[User, bool]:
        """Find existing user or create new one from OAuth info"""
        # Check if OAuth account exists
        oauth_account = (
            db.query(OAuthAccount)
            .filter(
                and_(
                    OAuthAccount.provider == provider,
                    OAuthAccount.provider_user_id == user_info["provider_user_id"],
                )
            )
            .first()
        )

        if oauth_account:
            # Existing OAuth account - update tokens
            oauth_account.access_token = tokens.get("access_token")
            oauth_account.refresh_token = tokens.get("refresh_token")
            if tokens.get("expires_in"):
                oauth_account.token_expires_at = datetime.utcnow() + timedelta(
                    seconds=tokens["expires_in"]
                )
            # Store provider data with scopes from token response
            granted_scopes = cls._parse_scopes_from_tokens(tokens, provider)
            oauth_account.provider_data = {
                "scopes": granted_scopes,
                "raw_user_info": user_info["raw_data"],
            }
            db.commit()

            return oauth_account.user, False

        # Check if user with email exists
        user = None
        if user_info.get("email"):
            user = (
                db.query(User)
                .filter(User.email == user_info["email"], User.status == UserStatus.ACTIVE)
                .first()
            )

        # Create new user if doesn't exist
        is_new_user = False
        if not user:
            user = User(
                email=user_info.get("email"),
                email_verified=user_info.get("email_verified", False),
                first_name=user_info.get("first_name"),
                last_name=user_info.get("last_name"),
                profile_image_url=user_info.get("profile_image_url"),
                status=UserStatus.ACTIVE,
            )
            db.add(user)
            db.flush()
            is_new_user = True

        # Parse scopes from token response
        granted_scopes = cls._parse_scopes_from_tokens(tokens, provider)

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
                if tokens.get("expires_in")
                else None
            ),
            provider_data={
                "scopes": granted_scopes,
                "raw_user_info": user_info["raw_data"],
            },
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
        cls, db: Session, provider: OAuthProvider, code: str, state: str, redirect_uri: str
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
        access_token, refresh_token, session = AuthService.create_user_session(db, user)

        return user, {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "is_new_user": is_new,
        }
