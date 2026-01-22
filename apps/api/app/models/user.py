"""
User models - backward compatibility module
"""

# Re-export user-related models from the main models module for backward compatibility
from . import User, Session, UserStatus, Organization, OrganizationMember

__all__ = ["User", "Session", "UserStatus", "Organization", "OrganizationMember", "Tenant"]

# Aliases for backward compatibility
Tenant = Organization  # Tenant is an alias for Organization