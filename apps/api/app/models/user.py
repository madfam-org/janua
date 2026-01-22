"""
User models - backward compatibility module
"""

# Import all user-related models from the main models module
# Note: These are re-exported for backward compatibility
from . import (
    User,
    Session,
    UserStatus,
    Organization,
    OrganizationMember,
)

# Aliases for backward compatibility
Tenant = Organization  # Tenant is an alias for Organization