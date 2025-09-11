"""
Authentication module for the Plinto SDK
"""

from typing import Dict, List, Optional, Any

from .http_client import HTTPClient
from .types import (
    SignUpRequest,
    SignInRequest,
    SignInResponse,
    TokenResponse,
    RefreshTokenRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    MagicLinkRequest,
    User,
    MFAStatusResponse,
    MFAEnableRequest,
    MFAEnableResponse,
    MFAVerifyRequest,
    MFADisableRequest,
    PasskeyResponse,
    PasskeyRegisterRequest,
    PasskeyUpdateRequest,
    OAuthProviderInfo,
    OAuthProvider,
)


class AuthModule:
    """Authentication operations"""
    
    def __init__(self, http_client: HTTPClient):
        self.http = http_client
    
    async def sign_up(self, request: SignUpRequest) -> SignInResponse:
        """
        Create a new user account
        
        Args:
            request: Sign up request data
            
        Returns:
            Sign in response with user and tokens
        """
        response = await self.http.post(
            "/api/v1/auth/signup",
            json_data=request.dict()
        )
        return SignInResponse(**response.json())
    
    async def sign_in(self, request: SignInRequest) -> SignInResponse:
        """
        Authenticate user and get tokens
        
        Args:
            request: Sign in request data
            
        Returns:
            Sign in response with user and tokens
        """
        response = await self.http.post(
            "/api/v1/auth/signin",
            json_data=request.dict()
        )
        data = response.json()
        
        # Store tokens in HTTP client
        tokens = data["tokens"]
        self.http.set_tokens(
            tokens["access_token"],
            tokens["refresh_token"],
            tokens["expires_in"]
        )
        
        return SignInResponse(**data)
    
    async def sign_out(self) -> Dict[str, str]:
        """
        Sign out current session
        
        Returns:
            Success message
        """
        response = await self.http.post("/api/v1/auth/signout")
        
        # Clear tokens from HTTP client
        self.http.clear_tokens()
        
        return response.json()
    
    async def refresh_token(self, refresh_token: Optional[str] = None) -> TokenResponse:
        """
        Refresh access token
        
        Args:
            refresh_token: Refresh token (if not provided, uses stored token)
            
        Returns:
            New token response
        """
        if not refresh_token:
            refresh_token = self.http.token_storage.get_refresh_token()
            if not refresh_token:
                raise ValueError("No refresh token available")
        
        request = RefreshTokenRequest(refresh_token=refresh_token)
        response = await self.http.post(
            "/api/v1/auth/refresh",
            json_data=request.dict()
        )
        
        data = response.json()
        tokens = TokenResponse(**data)
        
        # Update stored tokens
        self.http.set_tokens(
            tokens.access_token,
            tokens.refresh_token,
            tokens.expires_in
        )
        
        return tokens
    
    async def get_current_user(self) -> User:
        """
        Get current authenticated user
        
        Returns:
            Current user data
        """
        response = await self.http.get("/api/v1/auth/me")
        return User(**response.json())
    
    async def forgot_password(self, request: ForgotPasswordRequest) -> Dict[str, str]:
        """
        Request password reset email
        
        Args:
            request: Forgot password request
            
        Returns:
            Success message
        """
        response = await self.http.post(
            "/api/v1/auth/password/forgot",
            json_data=request.dict()
        )
        return response.json()
    
    async def reset_password(self, request: ResetPasswordRequest) -> Dict[str, str]:
        """
        Reset password with token
        
        Args:
            request: Reset password request
            
        Returns:
            Success message
        """
        response = await self.http.post(
            "/api/v1/auth/password/reset",
            json_data=request.dict()
        )
        return response.json()
    
    async def change_password(self, request: ChangePasswordRequest) -> Dict[str, str]:
        """
        Change password for authenticated user
        
        Args:
            request: Change password request
            
        Returns:
            Success message
        """
        response = await self.http.post(
            "/api/v1/auth/password/change",
            json_data=request.dict()
        )
        return response.json()
    
    async def verify_email(self, token: str) -> Dict[str, str]:
        """
        Verify email with token
        
        Args:
            token: Email verification token
            
        Returns:
            Success message
        """
        response = await self.http.post(
            "/api/v1/auth/email/verify",
            json_data={"token": token}
        )
        return response.json()
    
    async def resend_verification_email(self) -> Dict[str, str]:
        """
        Resend email verification
        
        Returns:
            Success message
        """
        response = await self.http.post("/api/v1/auth/email/resend-verification")
        return response.json()
    
    async def send_magic_link(self, request: MagicLinkRequest) -> Dict[str, str]:
        """
        Send magic link for passwordless sign-in
        
        Args:
            request: Magic link request
            
        Returns:
            Success message
        """
        response = await self.http.post(
            "/api/v1/auth/magic-link",
            json_data=request.dict()
        )
        return response.json()
    
    async def verify_magic_link(self, token: str) -> SignInResponse:
        """
        Sign in with magic link token
        
        Args:
            token: Magic link token
            
        Returns:
            Sign in response
        """
        response = await self.http.post(
            "/api/v1/auth/magic-link/verify",
            json_data={"token": token}
        )
        data = response.json()
        
        # Store tokens
        tokens = data["tokens"]
        self.http.set_tokens(
            tokens["access_token"],
            tokens["refresh_token"],
            tokens["expires_in"]
        )
        
        return SignInResponse(**data)
    
    # MFA Methods
    async def get_mfa_status(self) -> MFAStatusResponse:
        """
        Get MFA status for current user
        
        Returns:
            MFA status information
        """
        response = await self.http.get("/api/v1/mfa/status")
        return MFAStatusResponse(**response.json())
    
    async def enable_mfa(self, request: MFAEnableRequest) -> MFAEnableResponse:
        """
        Enable MFA for current user
        
        Args:
            request: MFA enable request with password
            
        Returns:
            MFA setup information including QR code
        """
        response = await self.http.post(
            "/api/v1/mfa/enable",
            json_data=request.dict()
        )
        return MFAEnableResponse(**response.json())
    
    async def verify_mfa(self, request: MFAVerifyRequest) -> Dict[str, str]:
        """
        Verify MFA setup with TOTP code
        
        Args:
            request: MFA verification request
            
        Returns:
            Success message
        """
        response = await self.http.post(
            "/api/v1/mfa/verify",
            json_data=request.dict()
        )
        return response.json()
    
    async def disable_mfa(self, request: MFADisableRequest) -> Dict[str, str]:
        """
        Disable MFA for current user
        
        Args:
            request: MFA disable request
            
        Returns:
            Success message
        """
        response = await self.http.post(
            "/api/v1/mfa/disable",
            json_data=request.dict()
        )
        return response.json()
    
    async def regenerate_backup_codes(self, password: str) -> Dict[str, Any]:
        """
        Regenerate MFA backup codes
        
        Args:
            password: User password for verification
            
        Returns:
            New backup codes
        """
        response = await self.http.post(
            "/api/v1/mfa/regenerate-backup-codes",
            json_data={"password": password}
        )
        return response.json()
    
    async def validate_mfa_code(self, code: str) -> Dict[str, Any]:
        """
        Validate an MFA code
        
        Args:
            code: TOTP or backup code
            
        Returns:
            Validation result
        """
        response = await self.http.post(
            "/api/v1/mfa/validate-code",
            json_data={"code": code}
        )
        return response.json()
    
    # Passkey Methods
    async def get_passkey_registration_options(
        self,
        authenticator_attachment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get WebAuthn registration options for passkey
        
        Args:
            authenticator_attachment: "platform" or "cross-platform"
            
        Returns:
            WebAuthn registration options
        """
        json_data = {}
        if authenticator_attachment:
            json_data["authenticator_attachment"] = authenticator_attachment
        
        response = await self.http.post(
            "/api/v1/passkeys/register/options",
            json_data=json_data
        )
        return response.json()
    
    async def verify_passkey_registration(
        self,
        request: PasskeyRegisterRequest
    ) -> Dict[str, Any]:
        """
        Verify passkey registration
        
        Args:
            request: Passkey registration data
            
        Returns:
            Registration result
        """
        response = await self.http.post(
            "/api/v1/passkeys/register/verify",
            json_data=request.dict()
        )
        return response.json()
    
    async def get_passkey_auth_options(
        self,
        email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get WebAuthn authentication options
        
        Args:
            email: Email for passwordless login
            
        Returns:
            WebAuthn authentication options
        """
        json_data = {}
        if email:
            json_data["email"] = email
        
        response = await self.http.post(
            "/api/v1/passkeys/authenticate/options",
            json_data=json_data
        )
        return response.json()
    
    async def verify_passkey_authentication(
        self,
        credential: Dict[str, Any],
        challenge: str,
        email: Optional[str] = None
    ) -> SignInResponse:
        """
        Verify passkey authentication
        
        Args:
            credential: WebAuthn credential
            challenge: Authentication challenge
            email: Email for passwordless login
            
        Returns:
            Authentication result with tokens
        """
        json_data = {
            "credential": credential,
            "challenge": challenge
        }
        if email:
            json_data["email"] = email
        
        response = await self.http.post(
            "/api/v1/passkeys/authenticate/verify",
            json_data=json_data
        )
        data = response.json()
        
        # Store tokens if authentication successful
        if "access_token" in data:
            self.http.set_tokens(
                data["access_token"],
                data["refresh_token"],
                data["expires_in"]
            )
        
        return SignInResponse(**data)
    
    async def list_passkeys(self) -> List[PasskeyResponse]:
        """
        List user's passkeys
        
        Returns:
            List of passkeys
        """
        response = await self.http.get("/api/v1/passkeys/")
        return [PasskeyResponse(**item) for item in response.json()]
    
    async def update_passkey(
        self,
        passkey_id: str,
        request: PasskeyUpdateRequest
    ) -> PasskeyResponse:
        """
        Update passkey name
        
        Args:
            passkey_id: Passkey ID
            request: Update request
            
        Returns:
            Updated passkey
        """
        response = await self.http.patch(
            f"/api/v1/passkeys/{passkey_id}",
            json_data=request.dict()
        )
        return PasskeyResponse(**response.json())
    
    async def delete_passkey(self, passkey_id: str, password: str) -> Dict[str, str]:
        """
        Delete a passkey
        
        Args:
            passkey_id: Passkey ID
            password: User password for verification
            
        Returns:
            Success message
        """
        response = await self.http.delete(
            f"/api/v1/passkeys/{passkey_id}",
            json_data={"password": password}
        )
        return response.json()
    
    # OAuth Methods
    async def get_oauth_providers(self) -> List[OAuthProviderInfo]:
        """
        Get available OAuth providers
        
        Returns:
            List of OAuth provider information
        """
        response = await self.http.get("/api/v1/auth/oauth/providers")
        data = response.json()
        return [
            OAuthProviderInfo(**provider) for provider in data["providers"]
        ]
    
    async def get_oauth_authorization_url(
        self,
        provider: OAuthProvider,
        redirect_uri: Optional[str] = None,
        redirect_to: Optional[str] = None,
        scopes: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Get OAuth authorization URL
        
        Args:
            provider: OAuth provider
            redirect_uri: Redirect URI after OAuth
            redirect_to: Where to redirect after OAuth completes
            scopes: Additional OAuth scopes
            
        Returns:
            Authorization URL and state
        """
        params = {}
        if redirect_uri:
            params["redirect_uri"] = redirect_uri
        if redirect_to:
            params["redirect_to"] = redirect_to
        if scopes:
            params["scopes"] = ",".join(scopes)
        
        response = await self.http.post(
            f"/api/v1/auth/oauth/authorize/{provider.value}",
            params=params
        )
        return response.json()
    
    async def link_oauth_account(
        self,
        provider: OAuthProvider,
        redirect_uri: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Link OAuth account to current user
        
        Args:
            provider: OAuth provider
            redirect_uri: Redirect URI after linking
            
        Returns:
            Authorization URL for linking
        """
        params = {}
        if redirect_uri:
            params["redirect_uri"] = redirect_uri
        
        response = await self.http.post(
            f"/api/v1/auth/oauth/link/{provider.value}",
            params=params
        )
        return response.json()
    
    async def unlink_oauth_account(self, provider: OAuthProvider) -> Dict[str, str]:
        """
        Unlink OAuth account from user
        
        Args:
            provider: OAuth provider to unlink
            
        Returns:
            Success message
        """
        response = await self.http.delete(
            f"/api/v1/auth/oauth/unlink/{provider.value}"
        )
        return response.json()
    
    async def get_linked_accounts(self) -> Dict[str, Any]:
        """
        Get all linked OAuth accounts
        
        Returns:
            OAuth accounts and auth methods status
        """
        response = await self.http.get("/api/v1/auth/oauth/accounts")
        return response.json()