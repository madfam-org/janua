"""
Organization management module for the Plinto SDK
"""

from typing import Dict, List, Optional, Any

from .http_client import HTTPClient
from .types import (
    Organization,
    OrganizationCreateRequest,
    OrganizationUpdateRequest,
    OrganizationMember,
    OrganizationInviteRequest,
    OrganizationInvitation,
    OrganizationRole,
)
from .utils import build_query_params


class OrganizationsModule:
    """Organization management operations"""
    
    def __init__(self, http_client: HTTPClient):
        self.http = http_client
    
    async def create_organization(
        self,
        request: OrganizationCreateRequest
    ) -> Organization:
        """
        Create a new organization
        
        Args:
            request: Organization creation request data
            
        Returns:
            Created organization
        """
        response = await self.http.post(
            "/api/v1/organizations/",
            json_data=request.dict()
        )
        return Organization(**response.json())
    
    async def list_organizations(self) -> List[Organization]:
        """
        List user's organizations
        
        Returns:
            List of organizations user belongs to
        """
        response = await self.http.get("/api/v1/organizations/")
        return [Organization(**org) for org in response.json()]
    
    async def get_organization(self, org_id: str) -> Organization:
        """
        Get organization details
        
        Args:
            org_id: Organization ID
            
        Returns:
            Organization data
        """
        response = await self.http.get(f"/api/v1/organizations/{org_id}")
        return Organization(**response.json())
    
    async def update_organization(
        self,
        org_id: str,
        request: OrganizationUpdateRequest
    ) -> Organization:
        """
        Update organization details
        
        Args:
            org_id: Organization ID
            request: Organization update request data
            
        Returns:
            Updated organization
        """
        response = await self.http.patch(
            f"/api/v1/organizations/{org_id}",
            json_data=request.dict(exclude_unset=True)
        )
        return Organization(**response.json())
    
    async def delete_organization(self, org_id: str) -> Dict[str, str]:
        """
        Delete an organization (owner only)
        
        Args:
            org_id: Organization ID
            
        Returns:
            Success message
        """
        response = await self.http.delete(f"/api/v1/organizations/{org_id}")
        return response.json()
    
    # Member Management
    async def list_members(self, org_id: str) -> List[OrganizationMember]:
        """
        List organization members
        
        Args:
            org_id: Organization ID
            
        Returns:
            List of organization members
        """
        response = await self.http.get(f"/api/v1/organizations/{org_id}/members")
        return [OrganizationMember(**member) for member in response.json()]
    
    async def update_member_role(
        self,
        org_id: str,
        user_id: str,
        role: OrganizationRole
    ) -> Dict[str, str]:
        """
        Update member role
        
        Args:
            org_id: Organization ID
            user_id: User ID
            role: New role
            
        Returns:
            Success message
        """
        response = await self.http.put(
            f"/api/v1/organizations/{org_id}/members/{user_id}/role",
            json_data={"role": role.value}
        )
        return response.json()
    
    async def remove_member(
        self,
        org_id: str,
        user_id: str
    ) -> Dict[str, str]:
        """
        Remove member from organization
        
        Args:
            org_id: Organization ID
            user_id: User ID to remove
            
        Returns:
            Success message
        """
        response = await self.http.delete(
            f"/api/v1/organizations/{org_id}/members/{user_id}"
        )
        return response.json()
    
    # Invitation Management
    async def invite_member(
        self,
        org_id: str,
        request: OrganizationInviteRequest
    ) -> Dict[str, Any]:
        """
        Invite a new member to organization
        
        Args:
            org_id: Organization ID
            request: Invitation request data
            
        Returns:
            Invitation details
        """
        response = await self.http.post(
            f"/api/v1/organizations/{org_id}/invite",
            json_data=request.dict()
        )
        return response.json()
    
    async def accept_invitation(self, token: str) -> Dict[str, Any]:
        """
        Accept an organization invitation
        
        Args:
            token: Invitation token
            
        Returns:
            Organization details after joining
        """
        response = await self.http.post(
            f"/api/v1/organizations/invitations/{token}/accept"
        )
        return response.json()
    
    async def list_invitations(
        self,
        org_id: str,
        status: Optional[str] = None
    ) -> List[OrganizationInvitation]:
        """
        List organization invitations
        
        Args:
            org_id: Organization ID
            status: Filter by status (pending, accepted, expired)
            
        Returns:
            List of invitations
        """
        params = build_query_params({"status": status})
        
        response = await self.http.get(
            f"/api/v1/organizations/{org_id}/invitations",
            params=params
        )
        return [OrganizationInvitation(**inv) for inv in response.json()]
    
    async def revoke_invitation(
        self,
        org_id: str,
        invitation_id: str
    ) -> Dict[str, str]:
        """
        Revoke an invitation
        
        Args:
            org_id: Organization ID
            invitation_id: Invitation ID
            
        Returns:
            Success message
        """
        response = await self.http.delete(
            f"/api/v1/organizations/{org_id}/invitations/{invitation_id}"
        )
        return response.json()
    
    # Custom Roles Management
    async def create_custom_role(
        self,
        org_id: str,
        name: str,
        description: Optional[str] = None,
        permissions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a custom role for organization
        
        Args:
            org_id: Organization ID
            name: Role name
            description: Role description
            permissions: List of permissions
            
        Returns:
            Created role data
        """
        json_data = {
            "name": name,
            "description": description,
            "permissions": permissions or []
        }
        
        response = await self.http.post(
            f"/api/v1/organizations/{org_id}/roles",
            json_data=json_data
        )
        return response.json()
    
    async def list_custom_roles(self, org_id: str) -> List[Dict[str, Any]]:
        """
        List organization's custom roles
        
        Args:
            org_id: Organization ID
            
        Returns:
            List of roles (built-in and custom)
        """
        response = await self.http.get(f"/api/v1/organizations/{org_id}/roles")
        return response.json()
    
    async def delete_custom_role(
        self,
        org_id: str,
        role_id: str
    ) -> Dict[str, str]:
        """
        Delete a custom role
        
        Args:
            org_id: Organization ID
            role_id: Role ID
            
        Returns:
            Success message
        """
        response = await self.http.delete(
            f"/api/v1/organizations/{org_id}/roles/{role_id}"
        )
        return response.json()
    
    async def transfer_ownership(
        self,
        org_id: str,
        new_owner_id: str
    ) -> Dict[str, str]:
        """
        Transfer organization ownership
        
        Args:
            org_id: Organization ID
            new_owner_id: New owner user ID
            
        Returns:
            Success message
        """
        response = await self.http.post(
            f"/api/v1/organizations/{org_id}/transfer-ownership",
            json_data={"new_owner_id": new_owner_id}
        )
        return response.json()