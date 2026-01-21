"""Session management module for the Janua SDK."""

from typing import Optional, Dict, Any

from .http_client import HTTPClient
from .types import (
    Session,
    SessionDevice,
    SessionActivity,
    ListResponse,
    JanuaConfig,
)


class SessionsClient:
    """Client for session management operations."""
    
    def __init__(self, http: HTTPClient, config: JanuaConfig):
        """
        Initialize the sessions client.
        
        Args:
            http: HTTP client instance
            config: Janua configuration
        """
        self.http = http
        self.config = config
    
    def get(self, session_id: str) -> Session:
        """
        Get a session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session object
            
        Raises:
            NotFoundError: If session not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/sessions/{session_id}')
        data = response.json()
        return Session(**data)
    
    def get_current(self) -> Session:
        """
        Get the current active session.
        
        Returns:
            Current Session object
            
        Raises:
            AuthorizationError: If not authenticated
            JanuaError: If request fails
        """
        response = self.http.get('/sessions/current')
        data = response.json()
        return Session(**data)
    
    def list(
        self,
        user_id: Optional[str] = None,
        active_only: bool = False,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = 'created_at',
        sort_order: str = 'desc',
    ) -> ListResponse[Session]:
        """
        List sessions with pagination and filtering.
        
        Args:
            user_id: Filter by user ID
            active_only: Only return active sessions
            limit: Number of sessions to return (max 100)
            offset: Number of sessions to skip
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)
            
        Returns:
            ListResponse containing sessions and pagination info
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        params = {
            'limit': min(limit, 100),
            'offset': offset,
            'sort_by': sort_by,
            'sort_order': sort_order,
        }
        
        if user_id:
            params['user_id'] = user_id
        if active_only:
            params['active_only'] = True
        
        response = self.http.get('/sessions', params=params)
        data = response.json()
        
        return ListResponse[Session](
            items=[Session(**item) for item in data['items']],
            total=data['total'],
            limit=data['limit'],
            offset=data['offset'],
        )
    
    def refresh(self, session_id: str) -> Session:
        """
        Refresh a session to extend its expiration.
        
        Args:
            session_id: Session ID to refresh
            
        Returns:
            Updated Session object
            
        Raises:
            NotFoundError: If session not found
            AuthorizationError: If not authorized
            JanuaError: If refresh fails
        """
        response = self.http.post(f'/sessions/{session_id}/refresh')
        data = response.json()
        return Session(**data)
    
    def revoke(self, session_id: str) -> None:
        """
        Revoke a session.
        
        Args:
            session_id: Session ID to revoke
            
        Raises:
            NotFoundError: If session not found
            AuthorizationError: If not authorized
            JanuaError: If revocation fails
        """
        self.http.delete(f'/sessions/{session_id}')
    
    def revoke_all(self, user_id: str) -> int:
        """
        Revoke all sessions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of sessions revoked
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If revocation fails
        """
        response = self.http.delete(f'/sessions/user/{user_id}')
        data = response.json()
        return data.get('revoked_count', 0)
    
    def revoke_other(self) -> int:
        """
        Revoke all other sessions for the current user.
        
        Returns:
            Number of sessions revoked
            
        Raises:
            AuthorizationError: If not authenticated
            JanuaError: If revocation fails
        """
        response = self.http.delete('/sessions/other')
        data = response.json()
        return data.get('revoked_count', 0)
    
    def get_device(self, session_id: str) -> SessionDevice:
        """
        Get device information for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            SessionDevice object
            
        Raises:
            NotFoundError: If session not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/sessions/{session_id}/device')
        data = response.json()
        return SessionDevice(**data)
    
    def update_device(
        self,
        session_id: str,
        name: Optional[str] = None,
        trusted: Optional[bool] = None,
    ) -> SessionDevice:
        """
        Update device information for a session.
        
        Args:
            session_id: Session ID
            name: Custom device name
            trusted: Mark device as trusted
            
        Returns:
            Updated SessionDevice object
            
        Raises:
            NotFoundError: If session not found
            AuthorizationError: If not authorized
            JanuaError: If update fails
        """
        payload = {}
        
        if name is not None:
            payload['name'] = name
        if trusted is not None:
            payload['trusted'] = trusted
        
        response = self.http.patch(
            f'/sessions/{session_id}/device',
            json=payload
        )
        data = response.json()
        return SessionDevice(**data)
    
    def get_activity(
        self,
        session_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> ListResponse[SessionActivity]:
        """
        Get activity log for a session.
        
        Args:
            session_id: Session ID
            limit: Number of activities to return (max 100)
            offset: Number of activities to skip
            
        Returns:
            ListResponse containing activities and pagination info
            
        Raises:
            NotFoundError: If session not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        params = {
            'limit': min(limit, 100),
            'offset': offset,
        }
        
        response = self.http.get(
            f'/sessions/{session_id}/activity',
            params=params
        )
        data = response.json()
        
        return ListResponse[SessionActivity](
            items=[SessionActivity(**item) for item in data['items']],
            total=data['total'],
            limit=data['limit'],
            offset=data['offset'],
        )
    
    def validate_token(self, token: str) -> Session:
        """
        Validate a session token.
        
        Args:
            token: Session token to validate
            
        Returns:
            Session object if valid
            
        Raises:
            AuthorizationError: If token is invalid
            JanuaError: If validation fails
        """
        response = self.http.post(
            '/sessions/validate',
            json={'token': token}
        )
        data = response.json()
        return Session(**data)
    
    def extend(
        self,
        session_id: str,
        duration: int,
    ) -> Session:
        """
        Extend a session's expiration time.
        
        Args:
            session_id: Session ID
            duration: Additional duration in seconds
            
        Returns:
            Updated Session object
            
        Raises:
            NotFoundError: If session not found
            AuthorizationError: If not authorized
            JanuaError: If extension fails
        """
        response = self.http.post(
            f'/sessions/{session_id}/extend',
            json={'duration': duration}
        )
        data = response.json()
        return Session(**data)
    
    def update_metadata(
        self,
        session_id: str,
        metadata: Dict[str, Any],
    ) -> Session:
        """
        Update session metadata.
        
        Args:
            session_id: Session ID
            metadata: Metadata to update
            
        Returns:
            Updated Session object
            
        Raises:
            NotFoundError: If session not found
            AuthorizationError: If not authorized
            JanuaError: If update fails
        """
        response = self.http.patch(
            f'/sessions/{session_id}/metadata',
            json={'metadata': metadata}
        )
        data = response.json()
        return Session(**data)
    
    def get_active_count(self, user_id: str) -> int:
        """
        Get count of active sessions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of active sessions
            
        Raises:
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/sessions/user/{user_id}/count')
        data = response.json()
        return data.get('active_count', 0)
    
    def cleanup_expired(self) -> int:
        """
        Clean up expired sessions (admin only).
        
        Returns:
            Number of sessions cleaned up
            
        Raises:
            AuthorizationError: If not authorized (admin only)
            JanuaError: If cleanup fails
        """
        response = self.http.post('/sessions/cleanup')
        data = response.json()
        return data.get('cleaned_count', 0)