"""
Organizations Router Module
Refactored from single large file into focused sub-modules for better maintainability
"""

from fastapi import APIRouter
from .core import router as core_router

# from .members import router as members_router
# from .invitations import router as invitations_router
# from .roles import router as roles_router

# Main organizations router
router = APIRouter(prefix="/organizations", tags=["organizations"])

# Include all sub-routers
router.include_router(core_router)
# router.include_router(members_router, prefix="/{org_id}")
# router.include_router(invitations_router, prefix="/{org_id}/invitations")
# router.include_router(roles_router, prefix="/{org_id}/roles")

# Export schemas and dependencies for external use
from .schemas import (
    OrganizationCreateRequest,
    OrganizationUpdateRequest,
    OrganizationResponse,
    OrganizationDetailResponse,
)
from .dependencies import (
    check_organization_permission,
    check_organization_admin_permission,
    check_organization_member_permission,
)

__all__ = [
    "router",
    # Schemas
    "OrganizationCreateRequest",
    "OrganizationUpdateRequest",
    "OrganizationResponse",
    "OrganizationDetailResponse",
    # Dependencies
    "check_organization_permission",
    "check_organization_admin_permission",
    "check_organization_member_permission",
]
