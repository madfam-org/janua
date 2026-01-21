from typing import Optional, Dict, Any, Literal
from .http_client import HttpClient
from .types import (
    SignUpRequest,
    SignInRequest,
    SignInResponse,
    SignUpResponse,
    AuthTokens,
    PasswordResetRequest,
    PasswordResetConfirm,
    VerifyEmailRequest,
    MagicLinkRequest,
    PasskeyRegistrationOptions,
)


class AuthClient:
    """Client for authentication operations"""
    
    def __init__(self, http: HttpClient):
        self.http = http
    
    async def sign_up(
        self,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SignUpResponse:
        """
        Sign up a new user
        
        Args:
            email: User's email address
            password: User's password
            first_name: User's first name
            last_name: User's last name
            username: Unique username
            metadata: Additional user metadata
        
        Returns:
            SignUpResponse with user, session, and tokens
        """
        request = SignUpRequest(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            username=username,
            metadata=metadata,
        )
        
        response = await self.http.post("/api/v1/auth/signup", json=request.model_dump(exclude_none=True))
        return SignUpResponse(**response)
    
    async def sign_in(
        self,
        email: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> SignInResponse:
        """
        Sign in a user
        
        Args:
            email: User's email address
            username: User's username (alternative to email)
            password: User's password
        
        Returns:
            SignInResponse with user, session, and tokens
        """
        if not email and not username:
            raise ValueError("Either email or username must be provided")
        
        if not password:
            raise ValueError("Password is required")
        
        request = SignInRequest(
            email=email,
            username=username,
            password=password,
        )
        
        response = await self.http.post("/api/v1/auth/signin", json=request.model_dump(exclude_none=True))
        return SignInResponse(**response)
    
    async def sign_out(self):
        """Sign out the current user"""
        await self.http.post("/api/v1/auth/signout")
    
    async def refresh_token(self, refresh_token: str) -> AuthTokens:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: The refresh token
        
        Returns:
            New auth tokens
        """
        response = await self.http.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        return AuthTokens(**response)
    
    async def request_password_reset(self, email: str):
        """
        Request a password reset email
        
        Args:
            email: User's email address
        """
        request = PasswordResetRequest(email=email)
        await self.http.post("/api/v1/auth/password/reset", json=request.model_dump())
    
    async def confirm_password_reset(self, token: str, new_password: str):
        """
        Confirm password reset with token
        
        Args:
            token: Password reset token
            new_password: New password
        """
        request = PasswordResetConfirm(token=token, new_password=new_password)
        await self.http.post("/api/v1/auth/password/confirm", json=request.model_dump())
    
    async def verify_email(self, token: str):
        """
        Verify email address with token
        
        Args:
            token: Email verification token
        """
        request = VerifyEmailRequest(token=token)
        await self.http.post("/api/v1/auth/email/verify", json=request.model_dump())
    
    async def send_magic_link(self, email: str, redirect_url: Optional[str] = None):
        """
        Send a magic link for passwordless authentication
        
        Args:
            email: User's email address
            redirect_url: URL to redirect after authentication
        """
        request = MagicLinkRequest(email=email, redirect_url=redirect_url)
        await self.http.post("/api/v1/auth/magic-link", json=request.model_dump(exclude_none=True))
    
    async def sign_in_with_magic_link(self, token: str) -> SignInResponse:
        """
        Sign in using a magic link token
        
        Args:
            token: Magic link token
        
        Returns:
            SignInResponse with user, session, and tokens
        """
        response = await self.http.post("/api/v1/auth/magic-link/verify", json={"token": token})
        return SignInResponse(**response)
    
    async def get_oauth_url(
        self,
        provider: Literal["google", "github", "microsoft", "apple", "discord", "twitter", "linkedin"],
        redirect_url: Optional[str] = None,
        scopes: Optional[list[str]] = None,
    ) -> Dict[str, str]:
        """
        Get OAuth authorization URL
        
        Args:
            provider: OAuth provider name
            redirect_url: URL to redirect after OAuth
            scopes: Additional OAuth scopes
        
        Returns:
            Dictionary with 'url' key containing the OAuth URL
        """
        params = {"provider": provider}
        if redirect_url:
            params["redirect_url"] = redirect_url
        if scopes:
            params["scopes"] = ",".join(scopes)
        
        return await self.http.get("/api/v1/auth/oauth/url", params=params)
    
    async def handle_oauth_callback(self, code: str, state: str) -> SignInResponse:
        """
        Handle OAuth callback
        
        Args:
            code: OAuth authorization code
            state: OAuth state parameter
        
        Returns:
            SignInResponse with user, session, and tokens
        """
        response = await self.http.post("/api/v1/auth/oauth/callback", json={"code": code, "state": state})
        return SignInResponse(**response)
    
    async def begin_passkey_registration(
        self,
        username: Optional[str] = None,
        display_name: Optional[str] = None,
        authenticator_attachment: Optional[Literal["platform", "cross-platform"]] = None,
    ) -> Dict[str, Any]:
        """
        Begin passkey registration process
        
        Args:
            username: Username for the passkey
            display_name: Display name for the passkey
            authenticator_attachment: Type of authenticator
        
        Returns:
            WebAuthn registration options
        """
        options = PasskeyRegistrationOptions(
            username=username,
            display_name=display_name,
            authenticator_attachment=authenticator_attachment,
        )
        
        return await self.http.post(
            "/api/v1/auth/passkeys/register/begin",
            json=options.model_dump(exclude_none=True)
        )
    
    async def complete_passkey_registration(self, credential: Dict[str, Any]):
        """
        Complete passkey registration
        
        Args:
            credential: WebAuthn credential from browser
        """
        await self.http.post("/api/v1/auth/passkeys/register/complete", json=credential)
    
    async def begin_passkey_authentication(self) -> Dict[str, Any]:
        """
        Begin passkey authentication process
        
        Returns:
            WebAuthn authentication options
        """
        return await self.http.post("/api/v1/auth/passkeys/authenticate/begin")
    
    async def complete_passkey_authentication(self, credential: Dict[str, Any]) -> SignInResponse:
        """
        Complete passkey authentication
        
        Args:
            credential: WebAuthn credential from browser
        
        Returns:
            SignInResponse with user, session, and tokens
        """
        response = await self.http.post("/api/v1/auth/passkeys/authenticate/complete", json=credential)
        return SignInResponse(**response)
    
    async def enable_mfa(self, type: Literal["totp", "sms"]) -> Dict[str, Optional[str]]:
        """
        Enable multi-factor authentication
        
        Args:
            type: MFA type (totp or sms)
        
        Returns:
            Dictionary with secret and/or QR code
        """
        return await self.http.post("/api/v1/auth/mfa/enable", json={"type": type})
    
    async def confirm_mfa(self, code: str):
        """
        Confirm MFA setup
        
        Args:
            code: MFA code from authenticator app
        """
        await self.http.post("/api/v1/auth/mfa/confirm", json={"code": code})
    
    async def disable_mfa(self, code: str):
        """
        Disable MFA
        
        Args:
            code: MFA code for verification
        """
        await self.http.post("/api/v1/auth/mfa/disable", json={"code": code})
    
    async def verify_mfa(self, code: str) -> AuthTokens:
        """
        Verify MFA code during login
        
        Args:
            code: MFA code from authenticator app
        
        Returns:
            Updated auth tokens
        """
        response = await self.http.post("/api/v1/auth/mfa/verify", json={"code": code})
        return AuthTokens(**response)