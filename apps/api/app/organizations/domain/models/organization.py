"""
Organization domain model (Aggregate Root)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID, uuid4


@dataclass
class Organization:
    """Organization aggregate root containing business logic and invariants"""

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    slug: str = ""
    description: Optional[str] = None
    logo_url: Optional[str] = None
    owner_id: UUID = field(default_factory=uuid4)
    settings: Dict = field(default_factory=dict)
    org_metadata: Dict = field(default_factory=dict)
    billing_email: Optional[str] = None
    billing_plan: str = "free"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate organization state after creation"""
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        """Ensure organization business rules are maintained"""
        if not self.name or len(self.name.strip()) == 0:
            raise ValueError("Organization name cannot be empty")

        if len(self.name) > 200:
            raise ValueError("Organization name cannot exceed 200 characters")

        if not self.slug or len(self.slug.strip()) == 0:
            raise ValueError("Organization slug cannot be empty")

        if len(self.slug) > 100:
            raise ValueError("Organization slug cannot exceed 100 characters")

        if not self._is_valid_slug(self.slug):
            raise ValueError(
                "Organization slug must contain only lowercase letters, numbers, and hyphens"
            )

        if self.description and len(self.description) > 1000:
            raise ValueError("Organization description cannot exceed 1000 characters")

        if self.logo_url and len(self.logo_url) > 500:
            raise ValueError("Logo URL cannot exceed 500 characters")

    def _is_valid_slug(self, slug: str) -> bool:
        """Validate slug format"""
        import re

        return bool(re.match(r"^[a-z0-9-]+$", slug))

    def update_name(self, name: str) -> None:
        """Update organization name with validation"""
        if not name or len(name.strip()) == 0:
            raise ValueError("Organization name cannot be empty")

        if len(name) > 200:
            raise ValueError("Organization name cannot exceed 200 characters")

        self.name = name.strip()
        self.updated_at = datetime.utcnow()

    def update_description(self, description: Optional[str]) -> None:
        """Update organization description with validation"""
        if description and len(description) > 1000:
            raise ValueError("Organization description cannot exceed 1000 characters")

        self.description = description
        self.updated_at = datetime.utcnow()

    def update_logo_url(self, logo_url: Optional[str]) -> None:
        """Update organization logo URL with validation"""
        if logo_url and len(logo_url) > 500:
            raise ValueError("Logo URL cannot exceed 500 characters")

        self.logo_url = logo_url
        self.updated_at = datetime.utcnow()

    def update_billing_email(self, billing_email: Optional[str]) -> None:
        """Update billing email with validation"""
        if billing_email:
            # Basic email validation
            import re

            email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_pattern, billing_email):
                raise ValueError("Invalid email format")

        self.billing_email = billing_email
        self.updated_at = datetime.utcnow()

    def update_settings(self, settings: Dict) -> None:
        """Update organization settings"""
        if not isinstance(settings, dict):
            raise ValueError("Settings must be a dictionary")

        self.settings = settings
        self.updated_at = datetime.utcnow()

    def transfer_ownership(self, new_owner_id: UUID) -> None:
        """Transfer organization ownership"""
        if not new_owner_id:
            raise ValueError("New owner ID cannot be empty")

        self.owner_id = new_owner_id
        self.updated_at = datetime.utcnow()

    def is_owner(self, user_id: UUID) -> bool:
        """Check if user is the organization owner"""
        return self.owner_id == user_id

    def can_be_deleted_by(self, user_id: UUID) -> bool:
        """Check if organization can be deleted by the given user"""
        return self.is_owner(user_id)

    def to_dict(self) -> Dict:
        """Convert to dictionary representation"""
        return {
            "id": str(self.id),
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "logo_url": self.logo_url,
            "owner_id": str(self.owner_id),
            "settings": self.settings,
            "org_metadata": self.org_metadata,
            "billing_email": self.billing_email,
            "billing_plan": self.billing_plan,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
