"""Passkeys (WebAuthn) module for the Janua SDK."""

from typing import Optional, Dict, Any

from .http_client import HTTPClient
from .types import (
    Passkey,
    PasskeyChallenge,
    ListResponse,
    JanuaConfig,
)
from .exceptions import (
    ValidationError,
)


class PasskeysClient:
    """Client for passkeys (WebAuthn) operations."""
    
    def __init__(self, http: HTTPClient, config: JanuaConfig):
        """
        Initialize the passkeys client.
        
        Args:
            http: HTTP client instance
            config: Janua configuration
        """
        self.http = http
        self.config = config
    
    def list(
        self,
        user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ListResponse[Passkey]:
        """
        List passkeys for a user.
        
        Args:
            user_id: User ID (defaults to current user)
            limit: Number of passkeys to return (max 100)
            offset: Number of passkeys to skip
            
        Returns:
            ListResponse containing passkeys and pagination info
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        params = {
            'limit': min(limit, 100),
            'offset': offset,
        }
        
        if user_id:
            response = self.http.get(
                f'/passkeys/users/{user_id}',
                params=params
            )
        else:
            response = self.http.get('/passkeys', params=params)
        
        data = response.json()
        
        return ListResponse[Passkey](
            items=[Passkey(**item) for item in data['items']],
            total=data['total'],
            limit=data['limit'],
            offset=data['offset'],
        )
    
    def get(self, passkey_id: str) -> Passkey:
        """
        Get a passkey by ID.
        
        Args:
            passkey_id: Passkey ID
            
        Returns:
            Passkey object
            
        Raises:
            NotFoundError: If passkey not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/passkeys/{passkey_id}')
        data = response.json()
        return Passkey(**data)
    
    def delete(self, passkey_id: str) -> None:
        """
        Delete a passkey.
        
        Args:
            passkey_id: Passkey ID
            
        Raises:
            NotFoundError: If passkey not found
            AuthorizationError: If not authorized
            JanuaError: If deletion fails
        """
        self.http.delete(f'/passkeys/{passkey_id}')
    
    def update(
        self,
        passkey_id: str,
        name: Optional[str] = None,
    ) -> Passkey:
        """
        Update a passkey.
        
        Args:
            passkey_id: Passkey ID
            name: New display name for the passkey
            
        Returns:
            Updated Passkey object
            
        Raises:
            NotFoundError: If passkey not found
            AuthorizationError: If not authorized
            JanuaError: If update fails
        """
        payload = {}
        if name is not None:
            payload['name'] = name
        
        response = self.http.patch(f'/passkeys/{passkey_id}', json=payload)
        data = response.json()
        return Passkey(**data)
    
    # Registration flow
    
    def begin_registration(
        self,
        user_id: Optional[str] = None,
        display_name: Optional[str] = None,
        authenticator_selection: Optional[Dict[str, Any]] = None,
    ) -> PasskeyChallenge:
        """
        Begin passkey registration process.
        
        Args:
            user_id: User ID (defaults to current user)
            display_name: Display name for the credential
            authenticator_selection: WebAuthn authenticator selection criteria
            
        Returns:
            PasskeyChallenge object with registration options
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If registration fails
        """
        payload = {}
        if display_name:
            payload['display_name'] = display_name
        if authenticator_selection:
            payload['authenticator_selection'] = authenticator_selection
        
        if user_id:
            response = self.http.post(
                f'/passkeys/users/{user_id}/register/begin',
                json=payload
            )
        else:
            response = self.http.post('/passkeys/register/begin', json=payload)
        
        data = response.json()
        return PasskeyChallenge(**data)
    
    def complete_registration(
        self,
        challenge_id: str,
        credential: Dict[str, Any],
        name: Optional[str] = None,
    ) -> Passkey:
        """
        Complete passkey registration process.
        
        Args:
            challenge_id: Challenge ID from begin_registration
            credential: WebAuthn credential response from client
            name: Optional name for the passkey
            
        Returns:
            Created Passkey object
            
        Raises:
            NotFoundError: If challenge not found
            ValidationError: If credential is invalid
            AuthorizationError: If not authorized
            JanuaError: If registration fails
        """
        payload = {
            'credential': credential,
        }
        if name:
            payload['name'] = name
        
        response = self.http.post(
            f'/passkeys/register/complete/{challenge_id}',
            json=payload
        )
        data = response.json()
        return Passkey(**data)
    
    # Authentication flow
    
    def begin_authentication(
        self,
        email: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> PasskeyChallenge:
        """
        Begin passkey authentication process.
        
        Args:
            email: User email for authentication
            user_id: User ID for authentication
            
        Returns:
            PasskeyChallenge object with authentication options
            
        Raises:
            ValidationError: If neither email nor user_id provided
            JanuaError: If authentication fails
        """
        payload = {}
        if email:
            payload['email'] = email
        if user_id:
            payload['user_id'] = user_id
        
        if not email and not user_id:
            raise ValidationError("Either email or user_id must be provided")
        
        response = self.http.post('/passkeys/authenticate/begin', json=payload)
        data = response.json()
        return PasskeyChallenge(**data)
    
    def complete_authentication(
        self,
        challenge_id: str,
        credential: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Complete passkey authentication process.
        
        Args:
            challenge_id: Challenge ID from begin_authentication
            credential: WebAuthn credential response from client
            
        Returns:
            Authentication result with user, session, and tokens
            
        Raises:
            NotFoundError: If challenge not found
            AuthenticationError: If authentication fails
            ValidationError: If credential is invalid
            JanuaError: If authentication fails
        """
        response = self.http.post(
            f'/passkeys/authenticate/complete/{challenge_id}',
            json={'credential': credential}
        )
        data = response.json()
        
        from .types import User, Session, AuthTokens
        
        return {
            'user': User(**data['user']),
            'session': Session(**data['session']),
            'tokens': AuthTokens(**data['tokens']),
        }
    
    # Device management
    
    def get_device_info(self, passkey_id: str) -> Dict[str, Any]:
        """
        Get device information for a passkey.
        
        Args:
            passkey_id: Passkey ID
            
        Returns:
            Device information dictionary
            
        Raises:
            NotFoundError: If passkey not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/passkeys/{passkey_id}/device')
        return response.json()
    
    def verify_device(
        self,
        passkey_id: str,
        challenge: Optional[str] = None,
    ) -> bool:
        """
        Verify a passkey device is still accessible.
        
        Args:
            passkey_id: Passkey ID
            challenge: Optional challenge for verification
            
        Returns:
            True if device is accessible
            
        Raises:
            NotFoundError: If passkey not found
            AuthorizationError: If not authorized
            JanuaError: If verification fails
        """
        payload = {}
        if challenge:
            payload['challenge'] = challenge
        
        response = self.http.post(
            f'/passkeys/{passkey_id}/verify',
            json=payload
        )
        data = response.json()
        return data.get('verified', False)
    
    # Bulk operations
    
    def delete_all(
        self,
        user_id: Optional[str] = None,
        verification_code: Optional[str] = None,
    ) -> int:
        """
        Delete all passkeys for a user.
        
        Args:
            user_id: User ID (defaults to current user)
            verification_code: MFA code for verification
            
        Returns:
            Number of passkeys deleted
            
        Raises:
            AuthenticationError: If verification fails
            AuthorizationError: If not authorized
            JanuaError: If deletion fails
        """
        payload = {}
        if verification_code:
            payload['verification_code'] = verification_code
        
        if user_id:
            response = self.http.delete(
                f'/passkeys/users/{user_id}/all',
                json=payload
            )
        else:
            response = self.http.delete('/passkeys/all', json=payload)
        
        data = response.json()
        return data.get('deleted_count', 0)
    
    def get_statistics(
        self,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get passkey usage statistics.
        
        Args:
            user_id: User ID (defaults to current user)
            
        Returns:
            Statistics dictionary
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        if user_id:
            response = self.http.get(f'/passkeys/users/{user_id}/stats')
        else:
            response = self.http.get('/passkeys/stats')
        
        return response.json()
    
    # Platform-specific helpers
    
    def get_platform_options(self) -> Dict[str, Any]:
        """
        Get platform-specific WebAuthn options.
        
        Returns:
            Platform configuration options
            
        Raises:
            JanuaError: If request fails
        """
        response = self.http.get('/passkeys/platform-options')
        return response.json()
    
    def is_supported(self, user_agent: Optional[str] = None) -> bool:
        """
        Check if passkeys are supported for a user agent.
        
        Args:
            user_agent: User agent string to check
            
        Returns:
            True if passkeys are supported
            
        Raises:
            JanuaError: If check fails
        """
        params = {}
        if user_agent:
            params['user_agent'] = user_agent
        
        response = self.http.get('/passkeys/supported', params=params)
        data = response.json()
        return data.get('supported', False)