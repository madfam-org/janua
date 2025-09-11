"""
Admin operations module for the Plinto SDK
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

from .http_client import HTTPClient
from .types import (
    AdminStatsResponse,
    SystemHealthResponse,
    User,
    Organization,
    UserStatus,
)
from .utils import build_query_params


class AdminModule:
    """Admin operations (requires admin privileges)"""
    
    def __init__(self, http_client: HTTPClient):
        self.http = http_client
    
    async def get_stats(self) -> AdminStatsResponse:
        """
        Get admin statistics
        
        Returns:
            System statistics
        """
        response = await self.http.get("/api/v1/admin/stats")
        return AdminStatsResponse(**response.json())
    
    async def get_system_health(self) -> SystemHealthResponse:
        """
        Get system health status
        
        Returns:
            System health information
        """
        response = await self.http.get("/api/v1/admin/health")
        return SystemHealthResponse(**response.json())
    
    async def list_all_users(
        self,
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None,
        status: Optional[UserStatus] = None,
        mfa_enabled: Optional[bool] = None,
        is_admin: Optional[bool] = None
    ) -> List[User]:
        """
        List all users (admin only)
        
        Args:
            page: Page number (1-based)
            per_page: Items per page (1-100)
            search: Search query for email, name, username
            status: Filter by user status
            mfa_enabled: Filter by MFA status
            is_admin: Filter by admin status
            
        Returns:
            List of users with admin details
        """
        params = build_query_params({
            "page": page,
            "per_page": per_page,
            "search": search,
            "status": status.value if status else None,
            "mfa_enabled": mfa_enabled,
            "is_admin": is_admin,
        })
        
        response = await self.http.get("/api/v1/admin/users", params=params)
        return [User(**user) for user in response.json()]
    
    async def update_user(
        self,
        user_id: str,
        status: Optional[UserStatus] = None,
        is_admin: Optional[bool] = None,
        email_verified: Optional[bool] = None
    ) -> Dict[str, str]:
        """
        Update user as admin
        
        Args:
            user_id: User ID to update
            status: New user status
            is_admin: Admin status
            email_verified: Email verification status
            
        Returns:
            Success message
        """
        json_data = {}
        if status is not None:
            json_data["status"] = status.value
        if is_admin is not None:
            json_data["is_admin"] = is_admin
        if email_verified is not None:
            json_data["email_verified"] = email_verified
        
        response = await self.http.patch(
            f"/api/v1/admin/users/{user_id}",
            json_data=json_data
        )
        return response.json()
    
    async def delete_user(
        self,
        user_id: str,
        permanent: bool = False
    ) -> Dict[str, str]:
        """
        Delete user as admin
        
        Args:
            user_id: User ID to delete
            permanent: Whether to permanently delete (hard delete)
            
        Returns:
            Success message
        """
        params = build_query_params({"permanent": permanent})
        
        response = await self.http.delete(
            f"/api/v1/admin/users/{user_id}",
            params=params
        )
        return response.json()
    
    async def list_all_organizations(
        self,
        page: int = 1,
        per_page: int = 20,
        search: Optional[str] = None,
        billing_plan: Optional[str] = None
    ) -> List[Organization]:
        """
        List all organizations (admin only)
        
        Args:
            page: Page number (1-based)
            per_page: Items per page (1-100)
            search: Search query for name, slug, owner email
            billing_plan: Filter by billing plan
            
        Returns:
            List of organizations with admin details
        """
        params = build_query_params({
            "page": page,
            "per_page": per_page,
            "search": search,
            "billing_plan": billing_plan,
        })
        
        response = await self.http.get("/api/v1/admin/organizations", params=params)
        return [Organization(**org) for org in response.json()]
    
    async def delete_organization(self, org_id: str) -> Dict[str, str]:
        """
        Delete organization as admin
        
        Args:
            org_id: Organization ID to delete
            
        Returns:
            Success message
        """
        response = await self.http.delete(f"/api/v1/admin/organizations/{org_id}")
        return response.json()
    
    async def get_activity_logs(
        self,
        page: int = 1,
        per_page: int = 50,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get activity logs (admin only)
        
        Args:
            page: Page number (1-based)
            per_page: Items per page (1-200)
            user_id: Filter by user ID
            action: Filter by action type
            start_date: Filter from date
            end_date: Filter to date
            
        Returns:
            List of activity logs
        """
        params = build_query_params({
            "page": page,
            "per_page": per_page,
            "user_id": user_id,
            "action": action,
            "start_date": start_date,
            "end_date": end_date,
        })
        
        response = await self.http.get("/api/v1/admin/activity-logs", params=params)
        return response.json()
    
    async def revoke_all_sessions(
        self,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Revoke all sessions (optionally for specific user)
        
        Args:
            user_id: User ID to revoke sessions for (if None, revokes all)
            
        Returns:
            Number of sessions revoked
        """
        json_data = {}
        if user_id:
            json_data["user_id"] = user_id
        
        response = await self.http.post(
            "/api/v1/admin/sessions/revoke-all",
            json_data=json_data
        )
        return response.json()
    
    async def toggle_maintenance_mode(
        self,
        enabled: bool,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Toggle maintenance mode
        
        Args:
            enabled: Whether to enable maintenance mode
            message: Maintenance message to display
            
        Returns:
            Maintenance mode status
        """
        json_data = {
            "enabled": enabled,
            "message": message
        }
        
        response = await self.http.post(
            "/api/v1/admin/maintenance-mode",
            json_data=json_data
        )
        return response.json()
    
    async def get_system_config(self) -> Dict[str, Any]:
        """
        Get system configuration (admin only)
        
        Returns:
            System configuration (non-sensitive)
        """
        response = await self.http.get("/api/v1/admin/config")
        return response.json()