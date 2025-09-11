"""
User management module for the Plinto SDK
"""

from typing import Dict, List, Optional, Any
from io import BytesIO

from .http_client import HTTPClient
from .types import (
    User,
    UserUpdateRequest,
    UserListResponse,
    Session,
    SessionListResponse,
)
from .utils import build_query_params


class UsersModule:
    """User management operations"""
    
    def __init__(self, http_client: HTTPClient):
        self.http = http_client
    
    async def get_current_user(self) -> User:
        """
        Get current user's profile
        
        Returns:
            Current user data
        """
        response = await self.http.get("/api/v1/users/me")
        return User(**response.json())
    
    async def update_current_user(self, request: UserUpdateRequest) -> User:
        """
        Update current user's profile
        
        Args:
            request: User update request data
            
        Returns:
            Updated user data
        """
        response = await self.http.patch(
            "/api/v1/users/me",
            json_data=request.dict(exclude_unset=True)
        )
        return User(**response.json())
    
    async def upload_avatar(
        self,
        file_data: bytes,
        filename: str,
        content_type: str = "image/jpeg"
    ) -> Dict[str, str]:
        """
        Upload user avatar
        
        Args:
            file_data: Image file bytes
            filename: Original filename
            content_type: MIME type of the image
            
        Returns:
            Avatar URL
        """
        # Create file-like object
        file_obj = BytesIO(file_data)
        file_obj.name = filename
        
        files = {
            "file": (filename, file_obj, content_type)
        }
        
        response = await self.http.post(
            "/api/v1/users/me/avatar",
            files=files
        )
        return response.json()
    
    async def delete_avatar(self) -> Dict[str, str]:
        """
        Delete user avatar
        
        Returns:
            Success message
        """
        response = await self.http.delete("/api/v1/users/me/avatar")
        return response.json()
    
    async def get_user_by_id(self, user_id: str) -> User:
        """
        Get user by ID (admin only or same organization)
        
        Args:
            user_id: User ID to retrieve
            
        Returns:
            User data
        """
        response = await self.http.get(f"/api/v1/users/{user_id}")
        return User(**response.json())
    
    async def list_users(
        self,
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None
    ) -> UserListResponse:
        """
        List users (admin only or same organization)
        
        Args:
            page: Page number (1-based)
            per_page: Items per page (1-100)
            search: Search query for email, name, username
            status: Filter by user status
            
        Returns:
            Paginated list of users
        """
        params = build_query_params({
            "page": page,
            "per_page": per_page,
            "search": search,
            "status": status,
        })
        
        response = await self.http.get("/api/v1/users/", params=params)
        data = response.json()
        
        return UserListResponse(
            users=[User(**user) for user in data["users"]],
            meta={
                "page": data["page"],
                "per_page": data["per_page"],
                "total": data["total"],
                "total_pages": (data["total"] + data["per_page"] - 1) // data["per_page"]
            }
        )
    
    async def delete_current_user(self, password: str) -> Dict[str, str]:
        """
        Delete current user account
        
        Args:
            password: User password for verification
            
        Returns:
            Success message
        """
        response = await self.http.delete(
            "/api/v1/users/me",
            json_data={"password": password}
        )
        
        # Clear tokens after account deletion
        self.http.clear_tokens()
        
        return response.json()
    
    async def suspend_user(
        self,
        user_id: str,
        reason: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Suspend a user (admin only)
        
        Args:
            user_id: User ID to suspend
            reason: Reason for suspension
            
        Returns:
            Success message
        """
        json_data = {}
        if reason:
            json_data["reason"] = reason
        
        response = await self.http.post(
            f"/api/v1/users/{user_id}/suspend",
            json_data=json_data
        )
        return response.json()
    
    async def reactivate_user(self, user_id: str) -> Dict[str, str]:
        """
        Reactivate a suspended user (admin only)
        
        Args:
            user_id: User ID to reactivate
            
        Returns:
            Success message
        """
        response = await self.http.post(f"/api/v1/users/{user_id}/reactivate")
        return response.json()
    
    # Session Management
    async def list_sessions(self) -> SessionListResponse:
        """
        List all active sessions for current user
        
        Returns:
            List of user sessions
        """
        response = await self.http.get("/api/v1/sessions/")
        data = response.json()
        
        return SessionListResponse(
            sessions=[Session(**session) for session in data["sessions"]],
            meta={
                "page": 1,
                "per_page": data["total"],
                "total": data["total"],
                "total_pages": 1
            }
        )
    
    async def get_session(self, session_id: str) -> Session:
        """
        Get specific session details
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            Session data
        """
        response = await self.http.get(f"/api/v1/sessions/{session_id}")
        return Session(**response.json())
    
    async def revoke_session(self, session_id: str) -> Dict[str, str]:
        """
        Revoke a specific session
        
        Args:
            session_id: Session ID to revoke
            
        Returns:
            Success message
        """
        response = await self.http.delete(f"/api/v1/sessions/{session_id}")
        return response.json()
    
    async def revoke_all_sessions(self) -> Dict[str, Any]:
        """
        Revoke all sessions except current
        
        Returns:
            Number of sessions revoked
        """
        response = await self.http.delete("/api/v1/sessions/")
        return response.json()
    
    async def refresh_session(self, session_id: str) -> Dict[str, str]:
        """
        Refresh a session's expiration
        
        Args:
            session_id: Session ID to refresh
            
        Returns:
            Success message
        """
        response = await self.http.post(f"/api/v1/sessions/{session_id}/refresh")
        return response.json()
    
    async def get_recent_activity(self, limit: int = 10) -> Dict[str, Any]:
        """
        Get recent session activity
        
        Args:
            limit: Number of activities to return (1-50)
            
        Returns:
            Recent session activities
        """
        params = build_query_params({"limit": limit})
        response = await self.http.get("/api/v1/sessions/activity/recent", params=params)
        return response.json()
    
    async def get_security_alerts(self) -> Dict[str, Any]:
        """
        Get security alerts for sessions
        
        Returns:
            Security alerts and warnings
        """
        response = await self.http.get("/api/v1/sessions/security/alerts")
        return response.json()