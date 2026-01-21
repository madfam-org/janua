"""User management module for the Janua SDK."""

from typing import Optional, Dict, Any, List

from .http_client import HTTPClient
from .types import (
    User,
    UserProfile,
    UserPreferences,
    UserRole,
    ListResponse,
    JanuaConfig,
)


class UsersClient:
    """Client for user management operations."""
    
    def __init__(self, http: HTTPClient, config: JanuaConfig):
        """
        Initialize the users client.
        
        Args:
            http: HTTP client instance
            config: Janua configuration
        """
        self.http = http
        self.config = config
    
    def get(self, user_id: str) -> User:
        """
        Get a user by ID.
        
        Args:
            user_id: User ID (UUID string)
            
        Returns:
            User object
            
        Raises:
            NotFoundError: If user not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/users/{user_id}')
        data = response.json()
        return User(**data)
    
    def get_by_email(self, email: str) -> User:
        """
        Get a user by email address.
        
        Args:
            email: User's email address
            
        Returns:
            User object
            
        Raises:
            NotFoundError: If user not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get('/users/by-email', params={'email': email})
        data = response.json()
        return User(**data)
    
    def list(
        self,
        limit: int = 20,
        offset: int = 0,
        search: Optional[str] = None,
        organization_id: Optional[str] = None,
        email_verified: Optional[bool] = None,
        role: Optional[UserRole] = None,
        sort_by: str = 'created_at',
        sort_order: str = 'desc',
    ) -> ListResponse[User]:
        """
        List users with pagination and filtering.
        
        Args:
            limit: Number of users to return (max 100)
            offset: Number of users to skip
            search: Search query for name or email
            organization_id: Filter by organization
            email_verified: Filter by email verification status
            role: Filter by user role
            sort_by: Field to sort by
            sort_order: Sort order (asc or desc)
            
        Returns:
            ListResponse containing users and pagination info
            
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
        
        if search:
            params['search'] = search
        if organization_id:
            params['organization_id'] = organization_id
        if email_verified is not None:
            params['email_verified'] = email_verified
        if role:
            params['role'] = role.value
        
        response = self.http.get('/users', params=params)
        data = response.json()
        
        return ListResponse[User](
            items=[User(**item) for item in data['items']],
            total=data['total'],
            limit=data['limit'],
            offset=data['offset'],
        )
    
    def create(
        self,
        email: str,
        password: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        role: UserRole = UserRole.USER,
        email_verified: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> User:
        """
        Create a new user (admin only).
        
        Args:
            email: User's email address
            password: User's password (optional, can be set later)
            first_name: User's first name
            last_name: User's last name
            role: User's role
            email_verified: Whether email is pre-verified
            metadata: Additional user metadata
            
        Returns:
            Created User object
            
        Raises:
            ValidationError: If input validation fails
            AuthorizationError: If not authorized (admin only)
            JanuaError: If creation fails
        """
        payload = {
            'email': email,
            'role': role.value,
            'email_verified': email_verified,
            'metadata': metadata or {},
        }
        
        if password:
            payload['password'] = password
        if first_name:
            payload['first_name'] = first_name
        if last_name:
            payload['last_name'] = last_name
        
        response = self.http.post('/users', json=payload)
        data = response.json()
        return User(**data)
    
    def update(
        self,
        user_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone_number: Optional[str] = None,
        profile_image_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> User:
        """
        Update a user's information.
        
        Args:
            user_id: User ID
            first_name: New first name
            last_name: New last name
            phone_number: New phone number
            profile_image_url: New profile image URL
            metadata: Updated metadata
            
        Returns:
            Updated User object
            
        Raises:
            NotFoundError: If user not found
            ValidationError: If input validation fails
            AuthorizationError: If not authorized
            JanuaError: If update fails
        """
        payload = {}
        
        if first_name is not None:
            payload['first_name'] = first_name
        if last_name is not None:
            payload['last_name'] = last_name
        if phone_number is not None:
            payload['phone_number'] = phone_number
        if profile_image_url is not None:
            payload['profile_image_url'] = profile_image_url
        if metadata is not None:
            payload['metadata'] = metadata
        
        response = self.http.patch(f'/users/{user_id}', json=payload)
        data = response.json()
        return User(**data)
    
    def update_email(
        self,
        user_id: str,
        new_email: str,
        require_verification: bool = True,
    ) -> User:
        """
        Update a user's email address.
        
        Args:
            user_id: User ID
            new_email: New email address
            require_verification: Whether to require email verification
            
        Returns:
            Updated User object
            
        Raises:
            NotFoundError: If user not found
            ValidationError: If email is invalid or already taken
            AuthorizationError: If not authorized
            JanuaError: If update fails
        """
        response = self.http.post(
            f'/users/{user_id}/email',
            json={
                'email': new_email,
                'require_verification': require_verification,
            }
        )
        data = response.json()
        return User(**data)
    
    def update_role(
        self,
        user_id: str,
        role: UserRole,
    ) -> User:
        """
        Update a user's role (admin only).
        
        Args:
            user_id: User ID
            role: New role
            
        Returns:
            Updated User object
            
        Raises:
            NotFoundError: If user not found
            AuthorizationError: If not authorized (admin only)
            JanuaError: If update fails
        """
        response = self.http.post(
            f'/users/{user_id}/role',
            json={'role': role.value}
        )
        data = response.json()
        return User(**data)
    
    def delete(self, user_id: str) -> None:
        """
        Delete a user.
        
        Args:
            user_id: User ID
            
        Raises:
            NotFoundError: If user not found
            AuthorizationError: If not authorized
            JanuaError: If deletion fails
        """
        self.http.delete(f'/users/{user_id}')
    
    def suspend(
        self,
        user_id: str,
        reason: Optional[str] = None,
    ) -> User:
        """
        Suspend a user account.
        
        Args:
            user_id: User ID
            reason: Reason for suspension
            
        Returns:
            Updated User object
            
        Raises:
            NotFoundError: If user not found
            AuthorizationError: If not authorized
            JanuaError: If suspension fails
        """
        payload = {}
        if reason:
            payload['reason'] = reason
        
        response = self.http.post(f'/users/{user_id}/suspend', json=payload)
        data = response.json()
        return User(**data)
    
    def unsuspend(self, user_id: str) -> User:
        """
        Unsuspend a user account.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated User object
            
        Raises:
            NotFoundError: If user not found
            AuthorizationError: If not authorized
            JanuaError: If unsuspension fails
        """
        response = self.http.post(f'/users/{user_id}/unsuspend')
        data = response.json()
        return User(**data)
    
    def get_profile(self, user_id: str) -> UserProfile:
        """
        Get a user's profile.
        
        Args:
            user_id: User ID
            
        Returns:
            UserProfile object
            
        Raises:
            NotFoundError: If user not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/users/{user_id}/profile')
        data = response.json()
        return UserProfile(**data)
    
    def update_profile(
        self,
        user_id: str,
        bio: Optional[str] = None,
        location: Optional[str] = None,
        website: Optional[str] = None,
        company: Optional[str] = None,
        job_title: Optional[str] = None,
    ) -> UserProfile:
        """
        Update a user's profile.
        
        Args:
            user_id: User ID
            bio: User biography
            location: User location
            website: User website
            company: User's company
            job_title: User's job title
            
        Returns:
            Updated UserProfile object
            
        Raises:
            NotFoundError: If user not found
            ValidationError: If input validation fails
            AuthorizationError: If not authorized
            JanuaError: If update fails
        """
        payload = {}
        
        if bio is not None:
            payload['bio'] = bio
        if location is not None:
            payload['location'] = location
        if website is not None:
            payload['website'] = website
        if company is not None:
            payload['company'] = company
        if job_title is not None:
            payload['job_title'] = job_title
        
        response = self.http.patch(f'/users/{user_id}/profile', json=payload)
        data = response.json()
        return UserProfile(**data)
    
    def get_preferences(self, user_id: str) -> UserPreferences:
        """
        Get a user's preferences.
        
        Args:
            user_id: User ID
            
        Returns:
            UserPreferences object
            
        Raises:
            NotFoundError: If user not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        response = self.http.get(f'/users/{user_id}/preferences')
        data = response.json()
        return UserPreferences(**data)
    
    def update_preferences(
        self,
        user_id: str,
        language: Optional[str] = None,
        timezone: Optional[str] = None,
        date_format: Optional[str] = None,
        time_format: Optional[str] = None,
        email_notifications: Optional[bool] = None,
        sms_notifications: Optional[bool] = None,
        push_notifications: Optional[bool] = None,
    ) -> UserPreferences:
        """
        Update a user's preferences.
        
        Args:
            user_id: User ID
            language: Preferred language (e.g., 'en', 'es', 'fr')
            timezone: Preferred timezone (e.g., 'America/New_York')
            date_format: Date format preference
            time_format: Time format preference (12h or 24h)
            email_notifications: Enable email notifications
            sms_notifications: Enable SMS notifications
            push_notifications: Enable push notifications
            
        Returns:
            Updated UserPreferences object
            
        Raises:
            NotFoundError: If user not found
            ValidationError: If input validation fails
            AuthorizationError: If not authorized
            JanuaError: If update fails
        """
        payload = {}
        
        if language is not None:
            payload['language'] = language
        if timezone is not None:
            payload['timezone'] = timezone
        if date_format is not None:
            payload['date_format'] = date_format
        if time_format is not None:
            payload['time_format'] = time_format
        if email_notifications is not None:
            payload['email_notifications'] = email_notifications
        if sms_notifications is not None:
            payload['sms_notifications'] = sms_notifications
        if push_notifications is not None:
            payload['push_notifications'] = push_notifications
        
        response = self.http.patch(f'/users/{user_id}/preferences', json=payload)
        data = response.json()
        return UserPreferences(**data)
    
    def get_sessions(
        self,
        user_id: str,
        active_only: bool = False,
    ) -> List[Session]:
        """
        Get all sessions for a user.
        
        Args:
            user_id: User ID
            active_only: Only return active sessions
            
        Returns:
            List of Session objects
            
        Raises:
            NotFoundError: If user not found
            AuthorizationError: If not authorized
            JanuaError: If request fails
        """
        params = {}
        if active_only:
            params['active_only'] = True
        
        response = self.http.get(f'/users/{user_id}/sessions', params=params)
        data = response.json()
        
        from .types import Session
        return [Session(**item) for item in data['sessions']]