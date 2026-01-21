from typing import Optional
from .http_client import HttpClient
from .auth import AuthClient
from .users import UserClient
from .organizations import OrganizationClient
from .types import User, Session


class JanuaClient:
    """
    Main client for interacting with the Janua API
    
    Example:
        ```python
        import asyncio
        from janua import JanuaClient
        
        async def main():
            client = JanuaClient(
                app_id="your-app-id",
                api_key="your-api-key"  # Optional for server-side usage
            )
            
            # Sign up a new user
            response = await client.auth.sign_up(
                email="user@example.com",
                password="secure-password",
                first_name="John",
                last_name="Doe"
            )
            
            print(f"User created: {response.user.email}")
            
            await client.close()
        
        asyncio.run(main())
        ```
    """
    
    def __init__(
        self,
        app_id: str,
        api_key: Optional[str] = None,
        api_url: str = "https://api.janua.dev",
        timeout: int = 30,
        debug: bool = False,
    ):
        """
        Initialize the Janua client
        
        Args:
            app_id: Your Janua application ID
            api_key: Your API key (optional, for server-side usage)
            api_url: The Janua API URL (defaults to production)
            timeout: Request timeout in seconds
            debug: Enable debug logging
        """
        if not app_id:
            raise ValueError("app_id is required")
        
        self.app_id = app_id
        self.api_key = api_key
        self.api_url = api_url
        self.debug = debug
        
        # Set up headers
        headers = {
            "X-App-Id": app_id,
            "Content-Type": "application/json",
        }
        
        if api_key:
            headers["X-API-Key"] = api_key
        
        # Initialize HTTP client
        self.http = HttpClient(
            base_url=api_url,
            headers=headers,
            timeout=timeout,
            debug=debug,
        )
        
        # Initialize sub-clients
        self.auth = AuthClient(self.http)
        self.users = UserClient(self.http)
        self.organizations = OrganizationClient(self.http)
        
        # Current user and session state
        self._current_user: Optional[User] = None
        self._current_session: Optional[Session] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def close(self):
        """Close the HTTP client connection"""
        await self.http.close()
    
    def get_user(self) -> Optional[User]:
        """Get the current authenticated user"""
        return self._current_user
    
    def get_session(self) -> Optional[Session]:
        """Get the current session"""
        return self._current_session
    
    def is_authenticated(self) -> bool:
        """Check if a user is currently authenticated"""
        return self._current_user is not None and self._current_session is not None
    
    async def sign_out(self):
        """Sign out the current user"""
        await self.auth.sign_out()
        self._current_user = None
        self._current_session = None
    
    async def update_session(self):
        """Update the current session and user information"""
        if not self.is_authenticated():
            raise ValueError("No active session to update")
        
        user = await self.users.get_current_user()
        # Note: In a real implementation, we'd also fetch session info
        self._current_user = user
    
    def set_auth_token(self, token: str):
        """
        Set the authentication token for requests
        
        Args:
            token: The JWT access token
        """
        self.http.set_header("Authorization", f"Bearer {token}")
    
    def clear_auth_token(self):
        """Clear the authentication token"""
        self.http.remove_header("Authorization")
    
    def _store_session(self, user: User, session: Session):
        """Store the current user and session"""
        self._current_user = user
        self._current_session = session