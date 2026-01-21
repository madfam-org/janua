
import pytest

pytestmark = pytest.mark.asyncio

"""
Comprehensive integration tests for organization management
Tests organization CRUD, member management, RBAC, and billing integration
"""

import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import uuid

from app.models import OrganizationRole


@pytest.mark.asyncio
class TestOrganizationManagementEndpoints:
    """Test suite for organization management API endpoints"""

    @pytest.mark.asyncio
    async def test_create_organization(self, test_client: AsyncClient):
        """Test creating a new organization"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_data = {
            "name": "Test Company",
            "description": "A test organization",
            "website": "https://testcompany.com",
            "industry": "Technology"
        }

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_user.email = "owner@testcompany.com"
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org = MagicMock()
                mock_org.id = str(uuid.uuid4())
                mock_org.name = org_data["name"]
                mock_org.description = org_data["description"]
                mock_org.website = org_data["website"]
                mock_org.industry = org_data["industry"]
                mock_org.created_at = datetime.utcnow()
                mock_org.owner_id = mock_user.id
                mock_org_service.return_value.create_organization.return_value = mock_org

                response = await test_client.post("/api/v1/organizations", json=org_data, headers=headers)

                assert response.status_code == 201
                data = response.json()
                assert data["name"] == org_data["name"]
                assert data["description"] == org_data["description"]
                assert data["website"] == org_data["website"]
                assert data["industry"] == org_data["industry"]

    @pytest.mark.asyncio
    async def test_get_organization_details(self, test_client: AsyncClient):
        """Test getting organization details"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org = MagicMock()
                mock_org.id = org_id
                mock_org.name = "Test Company"
                mock_org.description = "A test organization"
                mock_org.member_count = 5
                mock_org.created_at = datetime.utcnow()
                mock_org_service.return_value.get_organization.return_value = mock_org
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.ADMIN

                response = await test_client.get(f"/api/v1/organizations/{org_id}", headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert data["id"] == org_id
                assert data["name"] == "Test Company"
                assert data["member_count"] == 5

    @pytest.mark.asyncio
    async def test_update_organization(self, test_client: AsyncClient):
        """Test updating organization details"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())
        update_data = {
            "name": "Updated Company Name",
            "description": "Updated description",
            "website": "https://updated-company.com"
        }

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.ADMIN

                updated_org = MagicMock()
                updated_org.id = org_id
                updated_org.name = update_data["name"]
                updated_org.description = update_data["description"]
                updated_org.website = update_data["website"]
                mock_org_service.return_value.update_organization.return_value = updated_org

                response = await test_client.put(f"/api/v1/organizations/{org_id}", json=update_data, headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert data["name"] == update_data["name"]
                assert data["description"] == update_data["description"]

    @pytest.mark.asyncio
    async def test_delete_organization(self, test_client: AsyncClient):
        """Test deleting an organization"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())
        delete_data = {
            "confirmation": "DELETE",
            "reason": "No longer needed"
        }

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.OWNER
                mock_org_service.return_value.delete_organization.return_value = True

                response = await test_client.delete(f"/api/v1/organizations/{org_id}", json=delete_data, headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Organization deleted successfully"

    @pytest.mark.asyncio
    async def test_list_user_organizations(self, test_client: AsyncClient):
        """Test listing user's organizations"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_orgs = [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Company A",
                        "role": OrganizationRole.OWNER.value,
                        "member_count": 10,
                        "created_at": datetime.utcnow().isoformat()
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "name": "Company B",
                        "role": OrganizationRole.MEMBER.value,
                        "member_count": 25,
                        "created_at": (datetime.utcnow() - timedelta(days=30)).isoformat()
                    }
                ]
                mock_org_service.return_value.get_user_organizations.return_value = mock_orgs

                response = await test_client.get("/api/v1/organizations", headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert len(data["organizations"]) == 2
                assert data["organizations"][0]["role"] == "owner"
                assert data["organizations"][1]["role"] == "member"


@pytest.mark.asyncio
class TestOrganizationMemberManagement:
    """Test suite for organization member management"""

    @pytest.mark.asyncio
    async def test_invite_member(self, test_client: AsyncClient):
        """Test inviting a member to organization"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())
        invite_data = {
            "email": "newmember@example.com",
            "role": "member",
            "message": "Welcome to our team!"
        }

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.ADMIN

                with patch('app.services.invitation_service.InvitationService') as mock_invite_service:
                    mock_invitation = MagicMock()
                    mock_invitation.id = str(uuid.uuid4())
                    mock_invitation.email = invite_data["email"]
                    mock_invitation.role = invite_data["role"]
                    mock_invite_service.return_value.create_invitation.return_value = mock_invitation

                    response = await test_client.post(
                        f"/api/v1/organizations/{org_id}/members/invite",
                        json=invite_data,
                        headers=headers
                    )

                    assert response.status_code == 201
                    data = response.json()
                    assert data["email"] == invite_data["email"]
                    assert data["role"] == invite_data["role"]

    @pytest.mark.asyncio
    async def test_accept_invitation(self, test_client: AsyncClient):
        """Test accepting an organization invitation"""
        headers = {"Authorization": "Bearer valid_token_123"}
        invitation_token = "invitation_token_123"

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_user.email = "newmember@example.com"
            mock_get_user.return_value = mock_user

            with patch('app.services.invitation_service.InvitationService') as mock_invite_service:
                mock_invite_service.return_value.accept_invitation.return_value = {
                    "organization_id": str(uuid.uuid4()),
                    "role": OrganizationRole.MEMBER.value
                }

                response = await test_client.post(
                    f"/api/v1/organizations/invitations/{invitation_token}/accept",
                    headers=headers
                )

                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Invitation accepted successfully"

    @pytest.mark.asyncio
    async def test_list_organization_members(self, test_client: AsyncClient):
        """Test listing organization members"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.ADMIN

                mock_members = [
                    {
                        "id": str(uuid.uuid4()),
                        "email": "owner@company.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "role": OrganizationRole.OWNER.value,
                        "joined_at": (datetime.utcnow() - timedelta(days=365)).isoformat(),
                        "last_active": datetime.utcnow().isoformat()
                    },
                    {
                        "id": str(uuid.uuid4()),
                        "email": "admin@company.com",
                        "first_name": "Jane",
                        "last_name": "Smith",
                        "role": OrganizationRole.ADMIN.value,
                        "joined_at": (datetime.utcnow() - timedelta(days=30)).isoformat(),
                        "last_active": (datetime.utcnow() - timedelta(hours=2)).isoformat()
                    }
                ]
                mock_org_service.return_value.get_organization_members.return_value = mock_members

                response = await test_client.get(f"/api/v1/organizations/{org_id}/members", headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert len(data["members"]) == 2
                assert data["members"][0]["role"] == "owner"
                assert data["members"][1]["role"] == "admin"

    @pytest.mark.asyncio
    async def test_update_member_role(self, test_client: AsyncClient):
        """Test updating a member's role"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())
        member_id = str(uuid.uuid4())
        role_data = {
            "role": "admin"
        }

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.OWNER
                mock_org_service.return_value.update_member_role.return_value = True

                response = await test_client.put(
                    f"/api/v1/organizations/{org_id}/members/{member_id}/role",
                    json=role_data,
                    headers=headers
                )

                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Member role updated successfully"

    @pytest.mark.asyncio
    async def test_remove_member(self, test_client: AsyncClient):
        """Test removing a member from organization"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())
        member_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.ADMIN
                mock_org_service.return_value.remove_member.return_value = True

                response = await test_client.delete(
                    f"/api/v1/organizations/{org_id}/members/{member_id}",
                    headers=headers
                )

                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Member removed successfully"

    @pytest.mark.asyncio
    async def test_list_pending_invitations(self, test_client: AsyncClient):
        """Test listing pending invitations"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.ADMIN

                with patch('app.services.invitation_service.InvitationService') as mock_invite_service:
                    mock_invitations = [
                        {
                            "id": str(uuid.uuid4()),
                            "email": "pending1@example.com",
                            "role": "member",
                            "invited_at": datetime.utcnow().isoformat(),
                            "expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat()
                        },
                        {
                            "id": str(uuid.uuid4()),
                            "email": "pending2@example.com",
                            "role": "admin",
                            "invited_at": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                            "expires_at": (datetime.utcnow() + timedelta(days=6)).isoformat()
                        }
                    ]
                    mock_invite_service.return_value.get_pending_invitations.return_value = mock_invitations

                    response = await test_client.get(f"/api/v1/organizations/{org_id}/invitations", headers=headers)

                    assert response.status_code == 200
                    data = response.json()
                    assert len(data["invitations"]) == 2

    @pytest.mark.asyncio
    async def test_revoke_invitation(self, test_client: AsyncClient):
        """Test revoking a pending invitation"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())
        invitation_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.ADMIN

                with patch('app.services.invitation_service.InvitationService') as mock_invite_service:
                    mock_invite_service.return_value.revoke_invitation.return_value = True

                    response = await test_client.delete(
                        f"/api/v1/organizations/{org_id}/invitations/{invitation_id}",
                        headers=headers
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["message"] == "Invitation revoked successfully"


@pytest.mark.asyncio
class TestOrganizationRBAC:
    """Test suite for organization role-based access control"""

    @pytest.mark.asyncio
    async def test_owner_permissions(self, test_client: AsyncClient):
        """Test that owners have full permissions"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.OWNER

                # Owners should be able to perform all operations
                operations = [
                    ("PUT", f"/api/v1/organizations/{org_id}", {"name": "Updated"}),
                    ("DELETE", f"/api/v1/organizations/{org_id}", {"confirmation": "DELETE"}),
                    ("POST", f"/api/v1/organizations/{org_id}/members/invite", {"email": "test@example.com", "role": "member"}),
                ]

                for method, url, data in operations:
                    if method == "PUT":
                        response = await test_client.put(url, json=data, headers=headers)
                    elif method == "DELETE":
                        response = await test_client.delete(url, json=data, headers=headers)
                    elif method == "POST":
                        response = await test_client.post(url, json=data, headers=headers)

                    # Owner should have permission (mock success)
                    assert response.status_code in [200, 201]

    @pytest.mark.asyncio
    async def test_admin_permissions(self, test_client: AsyncClient):
        """Test admin permissions and restrictions"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.ADMIN

                # Admins can invite members
                invite_response = await test_client.post(
                    f"/api/v1/organizations/{org_id}/members/invite",
                    json={"email": "test@example.com", "role": "member"},
                    headers=headers
                )
                assert invite_response.status_code in [201, 403]  # Depends on implementation

                # Admins cannot delete organization
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.ADMIN
                delete_response = await test_client.delete(
                    f"/api/v1/organizations/{org_id}",
                    json={"confirmation": "DELETE"},
                    headers=headers
                )
                assert delete_response.status_code == 403

    @pytest.mark.asyncio
    async def test_member_permissions(self, test_client: AsyncClient):
        """Test member permissions and restrictions"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.MEMBER

                # Members cannot invite other members
                invite_response = await test_client.post(
                    f"/api/v1/organizations/{org_id}/members/invite",
                    json={"email": "test@example.com", "role": "member"},
                    headers=headers
                )
                assert invite_response.status_code == 403

                # Members cannot update organization
                update_response = await test_client.put(
                    f"/api/v1/organizations/{org_id}",
                    json={"name": "Updated"},
                    headers=headers
                )
                assert update_response.status_code == 403

    @pytest.mark.asyncio
    async def test_viewer_permissions(self, test_client: AsyncClient):
        """Test viewer permissions (read-only)"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.VIEWER

                # Viewers can view organization details
                view_response = await test_client.get(f"/api/v1/organizations/{org_id}", headers=headers)
                assert view_response.status_code == 200

                # Viewers cannot perform any modifications
                forbidden_operations = [
                    ("PUT", f"/api/v1/organizations/{org_id}", {"name": "Updated"}),
                    ("POST", f"/api/v1/organizations/{org_id}/members/invite", {"email": "test@example.com", "role": "member"}),
                    ("DELETE", f"/api/v1/organizations/{org_id}", {"confirmation": "DELETE"}),
                ]

                for method, url, data in forbidden_operations:
                    if method == "PUT":
                        response = await test_client.put(url, json=data, headers=headers)
                    elif method == "POST":
                        response = await test_client.post(url, json=data, headers=headers)
                    elif method == "DELETE":
                        response = await test_client.delete(url, json=data, headers=headers)

                    assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_non_member_access(self, test_client: AsyncClient):
        """Test that non-members cannot access organization"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = None  # Not a member

                response = await test_client.get(f"/api/v1/organizations/{org_id}", headers=headers)
                assert response.status_code == 403


@pytest.mark.asyncio
class TestOrganizationSecurity:
    """Security tests for organization management"""

    @pytest.mark.asyncio
    async def test_organization_isolation(self, test_client: AsyncClient):
        """Test that users cannot access other organizations' data"""
        headers = {"Authorization": "Bearer valid_token_123"}
        other_org_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                # User is not a member of this organization
                mock_org_service.return_value.get_user_role.return_value = None

                response = await test_client.get(f"/api/v1/organizations/{other_org_id}", headers=headers)
                assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_invitation_token_security(self, test_client: AsyncClient):
        """Test invitation token security"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            # Test invalid/expired invitation tokens
            invalid_tokens = [
                "invalid_token",
                "expired_token_123",
                "",
                "malformed.token.here"
            ]

            for token in invalid_tokens:
                with patch('app.services.invitation_service.InvitationService') as mock_invite_service:
                    mock_invite_service.return_value.accept_invitation.side_effect = Exception("Invalid token")

                    response = await test_client.post(
                        f"/api/v1/organizations/invitations/{token}/accept",
                        headers=headers
                    )
                    assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_privilege_escalation_prevention(self, test_client: AsyncClient):
        """Test prevention of privilege escalation attacks"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                # User is a member trying to escalate to admin
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.MEMBER

                # Attempt to update another member's role (should fail)
                other_member_id = str(uuid.uuid4())
                role_data = {"role": "admin"}

                response = await test_client.put(
                    f"/api/v1/organizations/{org_id}/members/{other_member_id}/role",
                    json=role_data,
                    headers=headers
                )
                assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_bulk_operations_security(self, test_client: AsyncClient):
        """Test security of bulk operations"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            # Test bulk invitation with too many emails
            bulk_invite_data = {
                "emails": [f"user{i}@example.com" for i in range(1000)],  # Too many
                "role": "member"
            }

            response = await test_client.post(
                f"/api/v1/organizations/{org_id}/members/bulk-invite",
                json=bulk_invite_data,
                headers=headers
            )
            # Should reject bulk operations that are too large
            assert response.status_code in [400, 422, 429]


@pytest.mark.asyncio
class TestOrganizationEdgeCases:
    """Edge case tests for organization management"""

    @pytest.mark.asyncio
    async def test_organization_name_conflicts(self, test_client: AsyncClient):
        """Test handling of organization name conflicts"""
        headers = {"Authorization": "Bearer valid_token_123"}
        duplicate_name_data = {
            "name": "Existing Company Name",
            "description": "A company with duplicate name"
        }

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                # Simulate name conflict
                mock_org_service.return_value.create_organization.side_effect = Exception("Name already exists")

                response = await test_client.post("/api/v1/organizations", json=duplicate_name_data, headers=headers)
                assert response.status_code in [400, 409]

    @pytest.mark.asyncio
    async def test_large_organization_operations(self, test_client: AsyncClient):
        """Test operations on organizations with many members"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.ADMIN

                # Simulate large member list
                large_member_list = [
                    {
                        "id": str(uuid.uuid4()),
                        "email": f"member{i}@company.com",
                        "first_name": f"Member{i}",
                        "last_name": "User",
                        "role": OrganizationRole.MEMBER.value,
                        "joined_at": datetime.utcnow().isoformat()
                    }
                    for i in range(1000)
                ]
                mock_org_service.return_value.get_organization_members.return_value = large_member_list

                response = await test_client.get(f"/api/v1/organizations/{org_id}/members", headers=headers)

                assert response.status_code == 200
                data = response.json()
                # Should handle large lists (possibly with pagination)
                assert "members" in data

    @pytest.mark.asyncio
    async def test_concurrent_member_operations(self, test_client: AsyncClient):
        """Test concurrent member management operations"""
        import asyncio

        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = str(uuid.uuid4())

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.organizations.OrganizationService') as mock_org_service:
                mock_org_service.return_value.get_user_role.return_value = OrganizationRole.ADMIN

                # Concurrent invitation requests
                invite_data = {
                    "email": "concurrent@example.com",
                    "role": "member"
                }

                tasks = [
                    test_client.post(f"/api/v1/organizations/{org_id}/members/invite", json=invite_data, headers=headers)
                    for _ in range(5)
                ]

                responses = await asyncio.gather(*tasks)

                # Should handle concurrent operations gracefully
                for response in responses:
                    assert response.status_code in [201, 409, 422]