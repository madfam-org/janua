"""Organization management module for the Janua SDK."""

from typing import Optional, Dict, Any, List

from .http_client import HTTPClient
from .types import (
    Organization,
    OrganizationMember,
    OrganizationRole,
    OrganizationInvite,
    OrganizationSettings,
    ListResponse,
    JanuaConfig,
)


class OrganizationsClient:
    """Client for organization management operations."""
    
    def __init__(self, http: HTTPClient, config: JanuaConfig):
        """
        Initialize the organizations client.
        
        Args:
            http: HTTP client instance
            config: Janua configuration
        """
        self.http = http
        self.config = config
    
    def get(self, organization_id: str) -> Organization:
        """
        Get an organization by ID.
        
        Args:
            organization_id: Organization ID
            
        Returns:
            Organization object
            
        Raises:
            NotFoundError: If organization not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/organizations/{organization_id}')
        data = response.json()
        return Organization(**data)
    
    def get_by_slug(self, slug: str) -> Organization:
        """
        Get an organization by slug.
        
        Args:
            slug: Organization slug
            
        Returns:
            Organization object
            
        Raises:
            NotFoundError: If organization not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/organizations/by-slug/{slug}')
        data = response.json()
        return Organization(**data)
    
    def list(
        self,
        user_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        search: Optional[str] = None,
        sort_by: str = 'created_at',
        sort_order: str = 'desc',
    ) -> ListResponse[Organization]:
        """
        List organizations with pagination and filtering.
        
        Args:
            user_id: Filter by user membership
            limit: Number of organizations to return (max 100)
            offset: Number of organizations to skip
            search: Search query for name
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)
            
        Returns:
            ListResponse containing organizations and pagination info
            
        Raises:
            ValidationError: If parameters are invalid
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
        if search:
            params['search'] = search
        
        response = self.http.get('/organizations', params=params)
        data = response.json()
        
        return ListResponse[Organization](
            items=[Organization(**item) for item in data['items']],
            total=data['total'],
            limit=data['limit'],
            offset=data['offset'],
        )
    
    def create(
        self,
        name: str,
        slug: Optional[str] = None,
        description: Optional[str] = None,
        logo_url: Optional[str] = None,
        website: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Organization:
        """
        Create a new organization.
        
        Args:
            name: Organization name
            slug: Organization slug (auto-generated if not provided)
            description: Organization description
            logo_url: Organization logo URL
            website: Organization website
            metadata: Additional metadata
            
        Returns:
            Created Organization object
            
        Raises:
            ValidationError: If input validation fails
            AuthorizationError: If not authorized
            JanuaError: If creation fails
        """
        payload = {
            'name': name,
            'metadata': metadata or {},
        }
        
        if slug:
            payload['slug'] = slug
        if description:
            payload['description'] = description
        if logo_url:
            payload['logo_url'] = logo_url
        if website:
            payload['website'] = website
        
        response = self.http.post('/organizations', json=payload)
        data = response.json()
        return Organization(**data)
    
    def update(
        self,
        organization_id: str,
        name: Optional[str] = None,
        slug: Optional[str] = None,
        description: Optional[str] = None,
        logo_url: Optional[str] = None,
        website: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Organization:
        """
        Update an organization.
        
        Args:
            organization_id: Organization ID
            name: New organization name
            slug: New organization slug
            description: New description
            logo_url: New logo URL
            website: New website
            metadata: Updated metadata
            
        Returns:
            Updated Organization object
            
        Raises:
            NotFoundError: If organization not found
            ValidationError: If input validation fails
            AuthorizationError: If not authorized
            JanuaError: If update fails
        """
        payload = {}
        
        if name is not None:
            payload['name'] = name
        if slug is not None:
            payload['slug'] = slug
        if description is not None:
            payload['description'] = description
        if logo_url is not None:
            payload['logo_url'] = logo_url
        if website is not None:
            payload['website'] = website
        if metadata is not None:
            payload['metadata'] = metadata
        
        response = self.http.patch(f'/organizations/{organization_id}', json=payload)
        data = response.json()
        return Organization(**data)
    
    def delete(self, organization_id: str) -> None:
        """
        Delete an organization.
        
        Args:
            organization_id: Organization ID
            
        Raises:
            NotFoundError: If organization not found
            AuthorizationError: If not authorized (must be owner)
            JanuaError: If deletion fails
        """
        self.http.delete(f'/organizations/{organization_id}')
    
    # Member management
    
    def list_members(
        self,
        organization_id: str,
        limit: int = 20,
        offset: int = 0,
        role: Optional[OrganizationRole] = None,
    ) -> ListResponse[OrganizationMember]:
        """
        List organization members.
        
        Args:
            organization_id: Organization ID
            limit: Number of members to return (max 100)
            offset: Number of members to skip
            role: Filter by role
            
        Returns:
            ListResponse containing members and pagination info
            
        Raises:
            NotFoundError: If organization not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        params = {
            'limit': min(limit, 100),
            'offset': offset,
        }
        
        if role:
            params['role'] = role.value
        
        response = self.http.get(
            f'/organizations/{organization_id}/members',
            params=params
        )
        data = response.json()
        
        return ListResponse[OrganizationMember](
            items=[OrganizationMember(**item) for item in data['items']],
            total=data['total'],
            limit=data['limit'],
            offset=data['offset'],
        )
    
    def get_member(
        self,
        organization_id: str,
        user_id: str,
    ) -> OrganizationMember:
        """
        Get a specific organization member.
        
        Args:
            organization_id: Organization ID
            user_id: User ID
            
        Returns:
            OrganizationMember object
            
        Raises:
            NotFoundError: If organization or member not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(
            f'/organizations/{organization_id}/members/{user_id}'
        )
        data = response.json()
        return OrganizationMember(**data)
    
    def add_member(
        self,
        organization_id: str,
        user_id: str,
        role: OrganizationRole = OrganizationRole.MEMBER,
    ) -> OrganizationMember:
        """
        Add a member to an organization.
        
        Args:
            organization_id: Organization ID
            user_id: User ID to add
            role: Member's role in the organization
            
        Returns:
            Created OrganizationMember object
            
        Raises:
            NotFoundError: If organization or user not found
            ValidationError: If user is already a member
            AuthorizationError: If not authorized
            JanuaError: If addition fails
        """
        response = self.http.post(
            f'/organizations/{organization_id}/members',
            json={
                'user_id': user_id,
                'role': role.value,
            }
        )
        data = response.json()
        return OrganizationMember(**data)
    
    def update_member_role(
        self,
        organization_id: str,
        user_id: str,
        role: OrganizationRole,
    ) -> OrganizationMember:
        """
        Update a member's role in an organization.
        
        Args:
            organization_id: Organization ID
            user_id: User ID
            role: New role
            
        Returns:
            Updated OrganizationMember object
            
        Raises:
            NotFoundError: If organization or member not found
            AuthorizationError: If not authorized
            JanuaError: If update fails
        """
        response = self.http.patch(
            f'/organizations/{organization_id}/members/{user_id}',
            json={'role': role.value}
        )
        data = response.json()
        return OrganizationMember(**data)
    
    def remove_member(
        self,
        organization_id: str,
        user_id: str,
    ) -> None:
        """
        Remove a member from an organization.
        
        Args:
            organization_id: Organization ID
            user_id: User ID to remove
            
        Raises:
            NotFoundError: If organization or member not found
            AuthorizationError: If not authorized
            ValidationError: If trying to remove the last owner
            JanuaError: If removal fails
        """
        self.http.delete(f'/organizations/{organization_id}/members/{user_id}')
    
    # Invite management
    
    def list_invites(
        self,
        organization_id: str,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> ListResponse[OrganizationInvite]:
        """
        List organization invites.
        
        Args:
            organization_id: Organization ID
            status: Filter by invite status (pending, accepted, expired)
            limit: Number of invites to return (max 100)
            offset: Number of invites to skip
            
        Returns:
            ListResponse containing invites and pagination info
            
        Raises:
            NotFoundError: If organization not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        params = {
            'limit': min(limit, 100),
            'offset': offset,
        }
        
        if status:
            params['status'] = status
        
        response = self.http.get(
            f'/organizations/{organization_id}/invites',
            params=params
        )
        data = response.json()
        
        return ListResponse[OrganizationInvite](
            items=[OrganizationInvite(**item) for item in data['items']],
            total=data['total'],
            limit=data['limit'],
            offset=data['offset'],
        )
    
    def create_invite(
        self,
        organization_id: str,
        email: str,
        role: OrganizationRole = OrganizationRole.MEMBER,
        message: Optional[str] = None,
        expires_in_days: int = 7,
    ) -> OrganizationInvite:
        """
        Create an organization invite.
        
        Args:
            organization_id: Organization ID
            email: Email address to invite
            role: Role to assign when accepted
            message: Optional invitation message
            expires_in_days: Days until invite expires
            
        Returns:
            Created OrganizationInvite object
            
        Raises:
            NotFoundError: If organization not found
            ValidationError: If email is invalid or already a member
            AuthorizationError: If not authorized
            JanuaError: If creation fails
        """
        payload = {
            'email': email,
            'role': role.value,
            'expires_in_days': expires_in_days,
        }
        
        if message:
            payload['message'] = message
        
        response = self.http.post(
            f'/organizations/{organization_id}/invites',
            json=payload
        )
        data = response.json()
        return OrganizationInvite(**data)
    
    def cancel_invite(
        self,
        organization_id: str,
        invite_id: str,
    ) -> None:
        """
        Cancel an organization invite.
        
        Args:
            organization_id: Organization ID
            invite_id: Invite ID
            
        Raises:
            NotFoundError: If organization or invite not found
            AuthorizationError: If not authorized
            JanuaError: If cancellation fails
        """
        self.http.delete(f'/organizations/{organization_id}/invites/{invite_id}')
    
    def accept_invite(
        self,
        invite_token: str,
    ) -> Organization:
        """
        Accept an organization invite.
        
        Args:
            invite_token: Invite token from invitation email
            
        Returns:
            Organization that was joined
            
        Raises:
            NotFoundError: If invite not found
            ValidationError: If invite is expired or already used
            JanuaError: If acceptance fails
        """
        response = self.http.post(
            '/organizations/invites/accept',
            json={'token': invite_token}
        )
        data = response.json()
        return Organization(**data)
    
    # Settings management
    
    def get_settings(
        self,
        organization_id: str,
    ) -> OrganizationSettings:
        """
        Get organization settings.
        
        Args:
            organization_id: Organization ID
            
        Returns:
            OrganizationSettings object
            
        Raises:
            NotFoundError: If organization not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/organizations/{organization_id}/settings')
        data = response.json()
        return OrganizationSettings(**data)
    
    def update_settings(
        self,
        organization_id: str,
        require_mfa: Optional[bool] = None,
        allowed_email_domains: Optional[List[str]] = None,
        session_duration: Optional[int] = None,
        password_policy: Optional[Dict[str, Any]] = None,
    ) -> OrganizationSettings:
        """
        Update organization settings.
        
        Args:
            organization_id: Organization ID
            require_mfa: Require MFA for all members
            allowed_email_domains: Allowed email domains for members
            session_duration: Default session duration in seconds
            password_policy: Password policy settings
            
        Returns:
            Updated OrganizationSettings object
            
        Raises:
            NotFoundError: If organization not found
            ValidationError: If settings are invalid
            AuthorizationError: If not authorized (admin/owner only)
            JanuaError: If update fails
        """
        payload = {}
        
        if require_mfa is not None:
            payload['require_mfa'] = require_mfa
        if allowed_email_domains is not None:
            payload['allowed_email_domains'] = allowed_email_domains
        if session_duration is not None:
            payload['session_duration'] = session_duration
        if password_policy is not None:
            payload['password_policy'] = password_policy
        
        response = self.http.patch(
            f'/organizations/{organization_id}/settings',
            json=payload
        )
        data = response.json()
        return OrganizationSettings(**data)