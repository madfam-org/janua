"""Authentication module for the Janua SDK."""

from typing import Optional, Dict, Any

from .http_client import HTTPClient
from .types import (
    User,
    Session,
    AuthTokens,
    SignInRequest,
    SignUpRequest,
    PasswordResetRequest,
    EmailVerificationRequest,
    OAuthProvider,
    JanuaConfig,
)


class AuthClient:
    """Client for authentication operations."""
    
    def __init__(self, http: HTTPClient, config: JanuaConfig):
        """
        Initialize the auth client.
        
        Args:
            http: HTTP client instance
            config: Janua configuration
        """
        self.http = http
        self.config = config
    
    def sign_up(
        self,
        email: str,
        password: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        auto_verify: bool = False,
    ) -> User:
        """
        Sign up a new user.
        
        Args:
            email: User's email address
            password: User's password (must meet security requirements)
            first_name: User's first name
            last_name: User's last name
            metadata: Additional user metadata
            auto_verify: Automatically verify email (for testing)
            
        Returns:
            Created User object
            
        Raises:
            ValidationError: If input validation fails
            JanuaError: If sign up fails
        """
        payload = SignUpRequest(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            metadata=metadata or {},
        ).model_dump(exclude_none=True)
        
        if auto_verify:
            payload['auto_verify'] = True
        
        response = self.http.post('/auth/signup', json=payload)
        data = response.json()
        return User(**data['user'])
    
    def sign_in(
        self,
        email: str,
        password: str,
        remember_me: bool = False,
        session_duration: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Sign in a user with email and password.
        
        Args:
            email: User's email address
            password: User's password
            remember_me: Create a long-lived session
            session_duration: Custom session duration in seconds
            
        Returns:
            Dictionary containing user, session, and tokens
            
        Raises:
            AuthenticationError: If credentials are invalid
            JanuaError: If sign in fails
        """
        payload = SignInRequest(
            email=email,
            password=password,
        ).model_dump()
        
        if remember_me:
            payload['remember_me'] = remember_me
        if session_duration:
            payload['session_duration'] = session_duration
        
        response = self.http.post('/auth/signin', json=payload)
        data = response.json()
        
        return {
            'user': User(**data['user']),
            'session': Session(**data['session']),
            'tokens': AuthTokens(**data['tokens']),
        }
    
    def sign_out(self, session_id: Optional[str] = None) -> None:
        """
        Sign out the current user or a specific session.
        
        Args:
            session_id: Optional specific session to sign out
            
        Raises:
            JanuaError: If sign out fails
        """
        payload = {}
        if session_id:
            payload['session_id'] = session_id
        
        self.http.post('/auth/signout', json=payload)
    
    def sign_out_all(self, user_id: str) -> None:
        """
        Sign out all sessions for a user.
        
        Args:
            user_id: ID of the user to sign out
            
        Raises:
            JanuaError: If sign out fails
        """
        self.http.post(f'/auth/signout-all/{user_id}')
    
    def get_current_user(self) -> User:
        """
        Get the currently authenticated user.
        
        Returns:
            Current User object
            
        Raises:
            AuthenticationError: If not authenticated
            JanuaError: If request fails
        """
        response = self.http.get('/auth/me')
        data = response.json()
        return User(**data)
    
    def refresh_token(self, refresh_token: str) -> AuthTokens:
        """
        Refresh authentication tokens.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            New AuthTokens object
            
        Raises:
            AuthenticationError: If refresh token is invalid
            JanuaError: If refresh fails
        """
        response = self.http.post(
            '/auth/refresh',
            json={'refresh_token': refresh_token}
        )
        data = response.json()
        return AuthTokens(**data)
    
    def request_password_reset(self, email: str) -> None:
        """
        Request a password reset for a user.
        
        Args:
            email: User's email address
            
        Raises:
            JanuaError: If request fails
        """
        payload = PasswordResetRequest(email=email).model_dump()
        self.http.post('/auth/password/reset', json=payload)
    
    def reset_password(
        self,
        token: str,
        new_password: str,
    ) -> None:
        """
        Reset a user's password using a reset token.
        
        Args:
            token: Password reset token
            new_password: New password
            
        Raises:
            ValidationError: If new password doesn't meet requirements
            AuthenticationError: If token is invalid
            JanuaError: If reset fails
        """
        self.http.post(
            '/auth/password/confirm',
            json={
                'token': token,
                'password': new_password,
            }
        )
    
    def change_password(
        self,
        current_password: str,
        new_password: str,
    ) -> None:
        """
        Change the current user's password.
        
        Args:
            current_password: Current password
            new_password: New password
            
        Raises:
            ValidationError: If new password doesn't meet requirements
            AuthenticationError: If current password is incorrect
            JanuaError: If change fails
        """
        self.http.post(
            '/auth/password/change',
            json={
                'current_password': current_password,
                'new_password': new_password,
            }
        )
    
    def request_email_verification(self, email: str) -> None:
        """
        Request email verification for a user.
        
        Args:
            email: User's email address
            
        Raises:
            JanuaError: If request fails
        """
        payload = EmailVerificationRequest(email=email).model_dump()
        self.http.post('/auth/email/verify', json=payload)
    
    def verify_email(self, token: str) -> User:
        """
        Verify a user's email address.
        
        Args:
            token: Email verification token
            
        Returns:
            Updated User object
            
        Raises:
            AuthenticationError: If token is invalid
            JanuaError: If verification fails
        """
        response = self.http.post(
            '/auth/email/confirm',
            json={'token': token}
        )
        data = response.json()
        return User(**data)
    
    def get_oauth_url(
        self,
        provider: OAuthProvider,
        redirect_uri: Optional[str] = None,
        state: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ) -> str:
        """
        Get OAuth authorization URL for a provider.
        
        Args:
            provider: OAuth provider
            redirect_uri: OAuth redirect URI
            state: OAuth state parameter
            scopes: Additional OAuth scopes
            
        Returns:
            OAuth authorization URL
            
        Raises:
            ValidationError: If provider is not supported
            JanuaError: If request fails
        """
        params = {
            'provider': provider.value,
        }
        if redirect_uri:
            params['redirect_uri'] = redirect_uri
        if state:
            params['state'] = state
        if scopes:
            params['scopes'] = ','.join(scopes)
        
        response = self.http.get('/auth/oauth/url', params=params)
        data = response.json()
        return data['url']
    
    def handle_oauth_callback(
        self,
        provider: OAuthProvider,
        code: str,
        state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle OAuth callback and authenticate user.
        
        Args:
            provider: OAuth provider
            code: OAuth authorization code
            state: OAuth state parameter
            
        Returns:
            Dictionary containing user, session, and tokens
            
        Raises:
            AuthenticationError: If OAuth authentication fails
            JanuaError: If callback handling fails
        """
        payload = {
            'provider': provider.value,
            'code': code,
        }
        if state:
            payload['state'] = state
        
        response = self.http.post('/auth/oauth/callback', json=payload)
        data = response.json()
        
        return {
            'user': User(**data['user']),
            'session': Session(**data['session']),
            'tokens': AuthTokens(**data['tokens']),
        }
    
    def link_oauth_account(
        self,
        provider: OAuthProvider,
        access_token: str,
    ) -> User:
        """
        Link an OAuth account to the current user.
        
        Args:
            provider: OAuth provider
            access_token: OAuth access token
            
        Returns:
            Updated User object
            
        Raises:
            AuthenticationError: If not authenticated
            ValidationError: If account already linked
            JanuaError: If linking fails
        """
        response = self.http.post(
            '/auth/oauth/link',
            json={
                'provider': provider.value,
                'access_token': access_token,
            }
        )
        data = response.json()
        return User(**data)
    
    def unlink_oauth_account(
        self,
        provider: OAuthProvider,
    ) -> User:
        """
        Unlink an OAuth account from the current user.
        
        Args:
            provider: OAuth provider to unlink
            
        Returns:
            Updated User object
            
        Raises:
            AuthenticationError: If not authenticated
            ValidationError: If account not linked
            JanuaError: If unlinking fails
        """
        response = self.http.delete(f'/auth/oauth/link/{provider.value}')
        data = response.json()
        return User(**data)
    
    def check_session(self, session_id: str) -> Session:
        """
        Check if a session is valid.
        
        Args:
            session_id: Session ID to check
            
        Returns:
            Session object if valid
            
        Raises:
            AuthenticationError: If session is invalid
            JanuaError: If check fails
        """
        response = self.http.get(f'/auth/sessions/{session_id}')
        data = response.json()
        return Session(**data)