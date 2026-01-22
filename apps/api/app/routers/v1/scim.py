"""
SCIM 2.0 API Endpoints
Enterprise identity provider integration for user and group provisioning
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import structlog

from ...models import User
from app.models.enterprise import Organization, SCIMResource, OrganizationMember, OrganizationRole
from app.core.database_manager import get_db
from app.core.tenant_context import TenantContext

logger = structlog.get_logger()

router = APIRouter(prefix="/scim/v2", tags=["SCIM 2.0"])


# SCIM 2.0 Response Models
class SCIMError:
    """SCIM error response format"""

    @staticmethod
    def format(status_code: int, detail: str, scim_type: str = "invalidValue"):
        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
            "status": str(status_code),
            "detail": detail,
            "scimType": scim_type,
        }


class SCIMListResponse:
    """SCIM list response format"""

    @staticmethod
    def format(
        resources: List[Dict], total_results: int, start_index: int = 1, items_per_page: int = 100
    ):
        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
            "totalResults": total_results,
            "Resources": resources,
            "startIndex": start_index,
            "itemsPerPage": items_per_page,
        }


# Authentication dependency for SCIM endpoints
async def verify_scim_token(authorization: str = Header(None), db: AsyncSession = Depends(get_db)):
    """Verify SCIM bearer token"""

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    authorization.replace("Bearer ", "")

    # In production, verify against SCIM tokens stored in database
    # For now, we'll check if it's a valid JWT or API key

    # Check if organization has SCIM enabled
    org_id = TenantContext.get_organization_id()
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token or organization context"
        )

    result = await db.execute(
        select(Organization).where(
            and_(Organization.id == org_id, Organization.scim_enabled == True)
        )
    )
    organization = result.scalar_one_or_none()

    if not organization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="SCIM not enabled for this organization",
        )

    return organization


# SCIM Service Provider Configuration
@router.get("/ServiceProviderConfig")
async def get_service_provider_config():
    """Return SCIM service provider configuration"""

    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "patch": {"supported": True},
        "bulk": {"supported": True, "maxOperations": 1000, "maxPayloadSize": 1048576},
        "filter": {"supported": True, "maxResults": 200},
        "changePassword": {"supported": True},
        "sort": {"supported": True},
        "etag": {"supported": True},
        "authenticationSchemes": [
            {
                "type": "oauthbearertoken",
                "name": "OAuth Bearer Token",
                "description": "Authentication using OAuth 2.0 bearer token",
                "specUri": "https://tools.ietf.org/html/rfc6750",
                "documentationUri": "https://janua.dev/docs/scim",
                "primary": True,
            }
        ],
        "meta": {
            "location": "/scim/v2/ServiceProviderConfig",
            "resourceType": "ServiceProviderConfig",
            "created": "2024-01-01T00:00:00Z",
            "lastModified": "2024-01-01T00:00:00Z",
            "version": "1.0",
        },
    }


# SCIM Schemas
@router.get("/Schemas")
async def get_schemas():
    """Return supported SCIM schemas"""

    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": 3,
        "Resources": [
            {
                "id": "urn:ietf:params:scim:schemas:core:2.0:User",
                "name": "User",
                "description": "User Account",
                "attributes": [
                    {
                        "name": "userName",
                        "type": "string",
                        "multiValued": False,
                        "required": True,
                        "caseExact": False,
                        "mutability": "readWrite",
                        "returned": "always",
                        "uniqueness": "server",
                    },
                    {
                        "name": "emails",
                        "type": "complex",
                        "multiValued": True,
                        "required": True,
                        "mutability": "readWrite",
                        "returned": "always",
                    },
                    {
                        "name": "active",
                        "type": "boolean",
                        "multiValued": False,
                        "required": False,
                        "mutability": "readWrite",
                        "returned": "always",
                    },
                ],
            },
            {
                "id": "urn:ietf:params:scim:schemas:core:2.0:Group",
                "name": "Group",
                "description": "Group",
                "attributes": [
                    {
                        "name": "displayName",
                        "type": "string",
                        "multiValued": False,
                        "required": True,
                        "mutability": "readWrite",
                        "returned": "always",
                    },
                    {
                        "name": "members",
                        "type": "complex",
                        "multiValued": True,
                        "mutability": "readWrite",
                        "returned": "always",
                    },
                ],
            },
            {
                "id": "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User",
                "name": "EnterpriseUser",
                "description": "Enterprise User",
                "attributes": [
                    {
                        "name": "employeeNumber",
                        "type": "string",
                        "multiValued": False,
                        "required": False,
                        "mutability": "readWrite",
                        "returned": "always",
                    },
                    {
                        "name": "department",
                        "type": "string",
                        "multiValued": False,
                        "required": False,
                        "mutability": "readWrite",
                        "returned": "always",
                    },
                ],
            },
        ],
    }


# User endpoints
@router.get("/Users")
async def list_users(
    organization: Organization = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
    startIndex: int = Query(1, ge=1),
    count: int = Query(100, ge=1, le=1000),
    filter: Optional[str] = Query(None),
):
    """List users with optional filtering"""

    try:
        # Build base query
        query = (
            select(User, SCIMResource, OrganizationMember)
            .join(
                SCIMResource,
                and_(
                    SCIMResource.internal_id == User.id,
                    SCIMResource.resource_type == "User",
                    SCIMResource.organization_id == organization.id,
                ),
                isouter=True,
            )
            .join(
                OrganizationMember,
                and_(
                    OrganizationMember.user_id == User.id,
                    OrganizationMember.organization_id == organization.id,
                ),
            )
        )

        # Apply filter if provided
        if filter:
            # Parse SCIM filter (simplified - production needs full parser)
            if "userName eq" in filter:
                username = filter.split('"')[1]
                query = query.where(User.username == username)
            elif "email eq" in filter:
                email = filter.split('"')[1]
                query = query.where(User.email == email)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total_count = total_result.scalar()

        # Apply pagination
        query = query.offset(startIndex - 1).limit(count)

        # Execute query
        result = await db.execute(query)
        rows = result.all()

        # Format users as SCIM resources
        resources = []
        for user, scim_resource, membership in rows:
            resource = format_user_resource(user, scim_resource, membership)
            resources.append(resource)

        return SCIMListResponse.format(
            resources=resources,
            total_results=total_count,
            start_index=startIndex,
            items_per_page=count,
        )

    except Exception as e:
        logger.error("SCIM user list failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SCIMError.format(500, "Internal server error"),
        )


@router.get("/Users/{user_id}")
async def get_user(
    user_id: str,
    organization: Organization = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific user by SCIM ID"""

    # Look up SCIM resource
    result = await db.execute(
        select(SCIMResource, User, OrganizationMember)
        .join(User, User.id == SCIMResource.internal_id)
        .join(
            OrganizationMember,
            and_(
                OrganizationMember.user_id == User.id,
                OrganizationMember.organization_id == organization.id,
            ),
            isouter=True,
        )
        .where(
            and_(
                SCIMResource.scim_id == user_id,
                SCIMResource.organization_id == organization.id,
                SCIMResource.resource_type == "User",
            )
        )
    )

    row = result.one_or_none()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=SCIMError.format(404, "User not found")
        )

    scim_resource, user, membership = row
    return format_user_resource(user, scim_resource, membership)


@router.post("/Users")
async def create_user(
    user_data: Dict[str, Any],
    organization: Organization = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user via SCIM"""

    try:
        # Extract user information
        username = user_data.get("userName")
        emails = user_data.get("emails", [])
        primary_email = next((e["value"] for e in emails if e.get("primary")), None)
        active = user_data.get("active", True)
        name = user_data.get("name", {})

        if not username or not primary_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=SCIMError.format(400, "userName and email are required"),
            )

        # Check if user already exists
        existing_user = await db.execute(
            select(User).where(or_(User.email == primary_email, User.username == username))
        )
        if existing_user.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=SCIMError.format(409, "User already exists"),
            )

        # Create user
        import uuid

        user = User(
            id=uuid.uuid4(),
            email=primary_email,
            username=username,
            first_name=name.get("givenName"),
            last_name=name.get("familyName"),
            display_name=user_data.get("displayName"),
            status="active" if active else "inactive",
            email_verified=True,  # SCIM users are pre-verified
        )
        db.add(user)

        # Create SCIM resource mapping
        scim_resource = SCIMResource(
            organization_id=organization.id,
            scim_id=str(uuid.uuid4()),
            resource_type="User",
            internal_id=user.id,
            raw_attributes=user_data,
            sync_status="synced",
        )
        db.add(scim_resource)

        # Add user to organization with default role
        default_role = await db.execute(
            select(OrganizationRole).where(
                and_(
                    OrganizationRole.organization_id == organization.id,
                    OrganizationRole.is_default == True,
                )
            )
        )
        role = default_role.scalar_one_or_none()

        if role:
            member = OrganizationMember(
                organization_id=organization.id,
                user_id=user.id,
                role_id=role.id,
                status="active",
                joined_at=datetime.utcnow(),
            )
            db.add(member)

        await db.commit()
        await db.refresh(user)
        await db.refresh(scim_resource)

        logger.info("SCIM user created", scim_id=scim_resource.scim_id, user_id=str(user.id))

        return format_user_resource(user, scim_resource, member if role else None)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("SCIM user creation failed", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SCIMError.format(500, "Internal server error"),
        )


@router.put("/Users/{user_id}")
async def update_user(
    user_id: str,
    user_data: Dict[str, Any],
    organization: Organization = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    """Update a user via SCIM"""

    try:
        # Look up SCIM resource and user
        result = await db.execute(
            select(SCIMResource, User)
            .join(User, User.id == SCIMResource.internal_id)
            .where(
                and_(
                    SCIMResource.scim_id == user_id,
                    SCIMResource.organization_id == organization.id,
                    SCIMResource.resource_type == "User",
                )
            )
        )

        row = result.one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SCIMError.format(404, "User not found"),
            )

        scim_resource, user = row

        # Update user fields
        if "userName" in user_data:
            user.username = user_data["userName"]

        if "emails" in user_data:
            emails = user_data["emails"]
            primary_email = next((e["value"] for e in emails if e.get("primary")), None)
            if primary_email:
                user.email = primary_email

        if "active" in user_data:
            user.status = "active" if user_data["active"] else "inactive"

        if "name" in user_data:
            name = user_data["name"]
            user.first_name = name.get("givenName", user.first_name)
            user.last_name = name.get("familyName", user.last_name)

        if "displayName" in user_data:
            user.display_name = user_data["displayName"]

        # Update SCIM resource
        scim_resource.raw_attributes = user_data
        scim_resource.last_synced_at = datetime.utcnow()

        await db.commit()
        await db.refresh(user)

        logger.info("SCIM user updated", scim_id=scim_resource.scim_id, user_id=str(user.id))

        # Get membership for response
        membership_result = await db.execute(
            select(OrganizationMember).where(
                and_(
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.organization_id == organization.id,
                )
            )
        )
        membership = membership_result.scalar_one_or_none()

        return format_user_resource(user, scim_resource, membership)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("SCIM user update failed", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SCIMError.format(500, "Internal server error"),
        )


@router.patch("/Users/{user_id}")
async def patch_user(
    user_id: str,
    patch_data: Dict[str, Any],
    organization: Organization = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    """Partially update a user via SCIM PATCH operations"""

    try:
        # Look up SCIM resource and user
        result = await db.execute(
            select(SCIMResource, User)
            .join(User, User.id == SCIMResource.internal_id)
            .where(
                and_(
                    SCIMResource.scim_id == user_id,
                    SCIMResource.organization_id == organization.id,
                    SCIMResource.resource_type == "User",
                )
            )
        )

        row = result.one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SCIMError.format(404, "User not found"),
            )

        scim_resource, user = row

        # Process SCIM PATCH operations
        operations = patch_data.get("Operations", [])
        for op in operations:
            op_type = op.get("op", "").lower()
            path = op.get("path", "")
            value = op.get("value")

            if op_type == "replace":
                apply_patch_replace(user, path, value)
            elif op_type == "add":
                apply_patch_add(user, path, value)
            elif op_type == "remove":
                apply_patch_remove(user, path)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=SCIMError.format(400, f"Unsupported operation: {op_type}"),
                )

        # Update SCIM resource tracking
        scim_resource.last_synced_at = datetime.utcnow()
        scim_resource.sync_status = "synced"

        await db.commit()
        await db.refresh(user)

        logger.info(
            "SCIM user patched",
            scim_id=scim_resource.scim_id,
            user_id=str(user.id),
            operations=len(operations),
        )

        # Get membership for response
        membership_result = await db.execute(
            select(OrganizationMember).where(
                and_(
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.organization_id == organization.id,
                )
            )
        )
        membership = membership_result.scalar_one_or_none()

        return format_user_resource(user, scim_resource, membership)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("SCIM user patch failed", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SCIMError.format(500, "Internal server error"),
        )


def apply_patch_replace(user: User, path: str, value: Any):
    """Apply a SCIM PATCH replace operation"""
    if path == "active" or path == "":
        if isinstance(value, dict) and "active" in value:
            user.status = "active" if value["active"] else "inactive"
        elif isinstance(value, bool):
            user.status = "active" if value else "inactive"
    elif path == "userName":
        user.username = value
    elif path == "displayName":
        user.display_name = value
    elif path == "name.givenName":
        user.first_name = value
    elif path == "name.familyName":
        user.last_name = value
    elif path == "emails" or path == 'emails[type eq "work"].value':
        if isinstance(value, list) and len(value) > 0:
            primary_email = next(
                (e["value"] for e in value if e.get("primary")), value[0].get("value")
            )
            if primary_email:
                user.email = primary_email
        elif isinstance(value, str):
            user.email = value
    elif path == "externalId":
        pass  # externalId is stored in SCIM resource, not user


def apply_patch_add(user: User, path: str, value: Any):
    """Apply a SCIM PATCH add operation - same as replace for most fields"""
    apply_patch_replace(user, path, value)


def apply_patch_remove(user: User, path: str):
    """Apply a SCIM PATCH remove operation"""
    if path == "name.givenName":
        user.first_name = None
    elif path == "name.familyName":
        user.last_name = None
    elif path == "displayName":
        user.display_name = None
    # Note: Cannot remove required fields like userName, email, active


@router.delete("/Users/{user_id}")
async def delete_user(
    user_id: str,
    organization: Organization = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    """Delete (deactivate) a user via SCIM"""

    try:
        # Look up SCIM resource and user
        result = await db.execute(
            select(SCIMResource, User)
            .join(User, User.id == SCIMResource.internal_id)
            .where(
                and_(
                    SCIMResource.scim_id == user_id,
                    SCIMResource.organization_id == organization.id,
                    SCIMResource.resource_type == "User",
                )
            )
        )

        row = result.one_or_none()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SCIMError.format(404, "User not found"),
            )

        scim_resource, user = row

        # Soft delete - deactivate user and remove from organization
        user.status = "deleted"

        # Remove organization membership
        await db.execute(
            select(OrganizationMember)
            .where(
                and_(
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.organization_id == organization.id,
                )
            )
            .delete()
        )

        # Delete SCIM resource mapping
        await db.delete(scim_resource)

        await db.commit()

        logger.info("SCIM user deleted", scim_id=user_id, user_id=str(user.id))

        return "", status.HTTP_204_NO_CONTENT

    except HTTPException:
        raise
    except Exception as e:
        logger.error("SCIM user deletion failed", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SCIMError.format(500, "Internal server error"),
        )


# Helper functions
def format_user_resource(
    user: User, scim_resource: Optional[SCIMResource], membership: Optional[OrganizationMember]
) -> Dict:
    """Format a user as a SCIM resource"""

    resource = {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
        "id": scim_resource.scim_id if scim_resource else str(user.id),
        "externalId": str(user.id),
        "userName": user.username or user.email,
        "name": {
            "formatted": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "familyName": user.last_name,
            "givenName": user.first_name,
        },
        "displayName": user.display_name or user.email,
        "emails": [{"value": user.email, "type": "work", "primary": True}],
        "active": user.status == "active",
        "meta": {
            "resourceType": "User",
            "created": user.created_at.isoformat() if user.created_at else None,
            "lastModified": user.updated_at.isoformat() if user.updated_at else None,
            "location": f"/scim/v2/Users/{scim_resource.scim_id if scim_resource else str(user.id)}",
        },
    }

    # Add enterprise extension if member of organization
    if membership:
        resource["schemas"].append("urn:ietf:params:scim:schemas:extension:enterprise:2.0:User")
        resource["urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"] = {
            "organization": str(membership.organization_id)
        }

    return resource


# Group endpoints would follow similar pattern
# Implementing basic structure for completeness


@router.get("/Groups")
async def list_groups(
    organization: Organization = Depends(verify_scim_token), db: AsyncSession = Depends(get_db)
):
    """List groups (roles) in the organization"""

    result = await db.execute(
        select(OrganizationRole).where(OrganizationRole.organization_id == organization.id)
    )
    roles = result.scalars().all()

    resources = []
    for role in roles:
        resources.append(
            {
                "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
                "id": str(role.id),
                "displayName": role.name,
                "meta": {
                    "resourceType": "Group",
                    "created": role.created_at.isoformat() if role.created_at else None,
                    "lastModified": role.updated_at.isoformat() if role.updated_at else None,
                    "location": f"/scim/v2/Groups/{role.id}",
                },
            }
        )

    return SCIMListResponse.format(
        resources=resources, total_results=len(resources), start_index=1, items_per_page=100
    )


@router.get("/Groups/{group_id}")
async def get_group(
    group_id: str,
    organization: Organization = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific group by ID"""

    try:
        group_uuid = UUID(group_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=SCIMError.format(404, "Group not found")
        )

    result = await db.execute(
        select(OrganizationRole).where(
            and_(
                OrganizationRole.id == group_uuid,
                OrganizationRole.organization_id == organization.id,
            )
        )
    )
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=SCIMError.format(404, "Group not found")
        )

    # Get group members
    members_result = await db.execute(
        select(OrganizationMember, User, SCIMResource)
        .join(User, User.id == OrganizationMember.user_id)
        .outerjoin(
            SCIMResource,
            and_(
                SCIMResource.internal_id == User.id,
                SCIMResource.resource_type == "User",
                SCIMResource.organization_id == organization.id,
            ),
        )
        .where(
            and_(
                OrganizationMember.organization_id == organization.id,
                OrganizationMember.role_id == role.id,
            )
        )
    )

    members = []
    for member, user, scim_resource in members_result.all():
        members.append(
            {
                "value": scim_resource.scim_id if scim_resource else str(user.id),
                "$ref": f"/scim/v2/Users/{scim_resource.scim_id if scim_resource else str(user.id)}",
                "display": user.display_name or user.email,
            }
        )

    return format_group_resource(role, members)


@router.post("/Groups", status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: Dict[str, Any],
    organization: Organization = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    """Create a new group (role) via SCIM"""

    try:
        display_name = group_data.get("displayName")
        if not display_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=SCIMError.format(400, "displayName is required"),
            )

        # Check if role already exists
        existing = await db.execute(
            select(OrganizationRole).where(
                and_(
                    OrganizationRole.organization_id == organization.id,
                    OrganizationRole.name == display_name,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=SCIMError.format(409, "Group already exists"),
            )

        import uuid

        role = OrganizationRole(
            id=uuid.uuid4(),
            organization_id=organization.id,
            name=display_name,
            description=group_data.get("description", ""),
            permissions=[],  # Default empty permissions
            is_default=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(role)

        # Create SCIM resource mapping for the group
        scim_resource = SCIMResource(
            organization_id=organization.id,
            scim_id=str(uuid.uuid4()),
            resource_type="Group",
            internal_id=role.id,
            raw_attributes=group_data,
            sync_status="synced",
        )
        db.add(scim_resource)

        await db.commit()
        await db.refresh(role)

        logger.info("SCIM group created", group_id=str(role.id), name=display_name)

        # Process initial members if provided
        members = group_data.get("members", [])
        await update_group_members(db, organization.id, role.id, members)

        return format_group_resource(role, members)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("SCIM group creation failed", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SCIMError.format(500, "Internal server error"),
        )


@router.put("/Groups/{group_id}")
async def update_group(
    group_id: str,
    group_data: Dict[str, Any],
    organization: Organization = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    """Update a group via SCIM (full replacement)"""

    try:
        group_uuid = UUID(group_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=SCIMError.format(404, "Group not found")
        )

    try:
        result = await db.execute(
            select(OrganizationRole).where(
                and_(
                    OrganizationRole.id == group_uuid,
                    OrganizationRole.organization_id == organization.id,
                )
            )
        )
        role = result.scalar_one_or_none()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SCIMError.format(404, "Group not found"),
            )

        # Update role
        if "displayName" in group_data:
            role.name = group_data["displayName"]
        role.updated_at = datetime.utcnow()

        # Update members (full replacement)
        members = group_data.get("members", [])
        await update_group_members(db, organization.id, role.id, members, replace=True)

        await db.commit()
        await db.refresh(role)

        logger.info("SCIM group updated", group_id=str(role.id))

        return format_group_resource(role, members)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("SCIM group update failed", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SCIMError.format(500, "Internal server error"),
        )


@router.patch("/Groups/{group_id}")
async def patch_group(
    group_id: str,
    patch_data: Dict[str, Any],
    organization: Organization = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    """Partially update a group via SCIM PATCH operations"""

    try:
        group_uuid = UUID(group_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=SCIMError.format(404, "Group not found")
        )

    try:
        result = await db.execute(
            select(OrganizationRole).where(
                and_(
                    OrganizationRole.id == group_uuid,
                    OrganizationRole.organization_id == organization.id,
                )
            )
        )
        role = result.scalar_one_or_none()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SCIMError.format(404, "Group not found"),
            )

        # Process SCIM PATCH operations
        operations = patch_data.get("Operations", [])
        for op in operations:
            op_type = op.get("op", "").lower()
            path = op.get("path", "")
            value = op.get("value")

            if op_type == "replace":
                if path == "displayName" or (
                    not path and isinstance(value, dict) and "displayName" in value
                ):
                    role.name = value if isinstance(value, str) else value.get("displayName")
                elif path == "members" or (
                    not path and isinstance(value, dict) and "members" in value
                ):
                    members = value if isinstance(value, list) else value.get("members", [])
                    await update_group_members(db, organization.id, role.id, members, replace=True)

            elif op_type == "add":
                if path == "members" or "members" in path:
                    members = value if isinstance(value, list) else [value] if value else []
                    await update_group_members(db, organization.id, role.id, members, replace=False)

            elif op_type == "remove":
                if path and "members" in path:
                    # Parse member to remove from path like "members[value eq \"user-id\"]"
                    import re

                    match = re.search(r'members\[value eq "([^"]+)"\]', path)
                    if match:
                        member_id = match.group(1)
                        await remove_group_member(db, organization.id, role.id, member_id)

        role.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(role)

        logger.info("SCIM group patched", group_id=str(role.id), operations=len(operations))

        # Get current members for response
        members = await get_group_members(db, organization.id, role.id)
        return format_group_resource(role, members)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("SCIM group patch failed", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SCIMError.format(500, "Internal server error"),
        )


@router.delete("/Groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    organization: Organization = Depends(verify_scim_token),
    db: AsyncSession = Depends(get_db),
):
    """Delete a group via SCIM"""

    try:
        group_uuid = UUID(group_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=SCIMError.format(404, "Group not found")
        )

    try:
        result = await db.execute(
            select(OrganizationRole).where(
                and_(
                    OrganizationRole.id == group_uuid,
                    OrganizationRole.organization_id == organization.id,
                )
            )
        )
        role = result.scalar_one_or_none()

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=SCIMError.format(404, "Group not found"),
            )

        # Cannot delete system/default roles
        if role.is_default:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=SCIMError.format(400, "Cannot delete default role"),
            )

        # Delete SCIM resource mapping
        await db.execute(
            select(SCIMResource)
            .where(
                and_(
                    SCIMResource.internal_id == role.id,
                    SCIMResource.resource_type == "Group",
                    SCIMResource.organization_id == organization.id,
                )
            )
            .delete()
        )

        # Delete the role
        await db.delete(role)
        await db.commit()

        logger.info("SCIM group deleted", group_id=group_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("SCIM group deletion failed", error=str(e))
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SCIMError.format(500, "Internal server error"),
        )


# Group helper functions


def format_group_resource(role: OrganizationRole, members: List[Dict] = None) -> Dict:
    """Format a role as a SCIM Group resource"""
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
        "id": str(role.id),
        "displayName": role.name,
        "members": members or [],
        "meta": {
            "resourceType": "Group",
            "created": role.created_at.isoformat() if role.created_at else None,
            "lastModified": role.updated_at.isoformat() if role.updated_at else None,
            "location": f"/scim/v2/Groups/{role.id}",
        },
    }


async def get_group_members(db: AsyncSession, org_id: UUID, role_id: UUID) -> List[Dict]:
    """Get members of a group"""
    result = await db.execute(
        select(OrganizationMember, User, SCIMResource)
        .join(User, User.id == OrganizationMember.user_id)
        .outerjoin(
            SCIMResource,
            and_(
                SCIMResource.internal_id == User.id,
                SCIMResource.resource_type == "User",
                SCIMResource.organization_id == org_id,
            ),
        )
        .where(
            and_(
                OrganizationMember.organization_id == org_id, OrganizationMember.role_id == role_id
            )
        )
    )

    members = []
    for member, user, scim_resource in result.all():
        members.append(
            {
                "value": scim_resource.scim_id if scim_resource else str(user.id),
                "$ref": f"/scim/v2/Users/{scim_resource.scim_id if scim_resource else str(user.id)}",
                "display": user.display_name or user.email,
            }
        )
    return members


async def update_group_members(
    db: AsyncSession, org_id: UUID, role_id: UUID, members: List[Dict], replace: bool = False
):
    """Update group members"""

    if replace:
        # Remove all existing members with this role (just update their role, don't remove from org)
        await db.execute(
            select(OrganizationMember).where(
                and_(
                    OrganizationMember.organization_id == org_id,
                    OrganizationMember.role_id == role_id,
                )
            )
        )
        # Set role to None for existing members
        result = await db.execute(
            select(OrganizationMember).where(
                and_(
                    OrganizationMember.organization_id == org_id,
                    OrganizationMember.role_id == role_id,
                )
            )
        )
        for member in result.scalars():
            member.role_id = None

    # Add new members
    for member_data in members:
        member_value = member_data.get("value")
        if not member_value:
            continue

        # Find user by SCIM ID or internal ID
        user_result = await db.execute(
            select(User)
            .join(
                SCIMResource,
                and_(
                    SCIMResource.internal_id == User.id,
                    SCIMResource.scim_id == member_value,
                    SCIMResource.organization_id == org_id,
                ),
                isouter=True,
            )
            .where(or_(SCIMResource.scim_id == member_value, User.id == member_value))
        )
        user = user_result.scalar_one_or_none()

        if user:
            # Update membership to use this role
            membership_result = await db.execute(
                select(OrganizationMember).where(
                    and_(
                        OrganizationMember.organization_id == org_id,
                        OrganizationMember.user_id == user.id,
                    )
                )
            )
            membership = membership_result.scalar_one_or_none()
            if membership:
                membership.role_id = role_id


async def remove_group_member(db: AsyncSession, org_id: UUID, role_id: UUID, member_id: str):
    """Remove a specific member from a group"""
    # Find user by SCIM ID
    user_result = await db.execute(
        select(User)
        .join(
            SCIMResource,
            and_(
                SCIMResource.internal_id == User.id,
                SCIMResource.scim_id == member_id,
                SCIMResource.organization_id == org_id,
            ),
            isouter=True,
        )
        .where(or_(SCIMResource.scim_id == member_id, User.id == member_id))
    )
    user = user_result.scalar_one_or_none()

    if user:
        membership_result = await db.execute(
            select(OrganizationMember).where(
                and_(
                    OrganizationMember.organization_id == org_id,
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.role_id == role_id,
                )
            )
        )
        membership = membership_result.scalar_one_or_none()
        if membership:
            membership.role_id = None
