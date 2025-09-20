
pytestmark = pytest.mark.asyncio

"""
Comprehensive integration tests for user management endpoints
Tests CRUD operations, user profiles, settings, and permissions
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime, timedelta
import uuid

from app.models import User, UserStatus, OrganizationRole
from app.services.auth_service import AuthService


@pytest.mark.asyncio
class TestUserManagementEndpoints:
    """Test suite for user management API endpoints"""

    @pytest.mark.asyncio
    async def test_get_user_profile(self, test_client: AsyncClient):
        """Test getting user profile"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_user.email = "user@example.com"
            mock_user.first_name = "John"
            mock_user.last_name = "Doe"
            mock_user.username = "johndoe"
            mock_user.email_verified = True
            mock_user.status = UserStatus.ACTIVE
            mock_user.created_at = datetime.utcnow()
            mock_user.updated_at = datetime.utcnow()
            mock_user.profile_picture_url = None
            mock_user.bio = None
            mock_user.timezone = "UTC"
            mock_user.language = "en"
            mock_get_user.return_value = mock_user

            response = await test_client.get("/api/v1/users/profile", headers=headers)

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == "user@example.com"
            assert data["first_name"] == "John"
            assert data["last_name"] == "Doe"
            assert data["username"] == "johndoe"

    @pytest.mark.asyncio
    async def test_update_user_profile(self, test_client: AsyncClient):
        """Test updating user profile"""
        headers = {"Authorization": "Bearer valid_token_123"}
        update_data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "bio": "Updated bio",
            "timezone": "America/New_York"
        }

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.UserService') as mock_user_service:
                updated_user = MagicMock()
                updated_user.id = mock_user.id
                updated_user.first_name = update_data["first_name"]
                updated_user.last_name = update_data["last_name"]
                updated_user.bio = update_data["bio"]
                updated_user.timezone = update_data["timezone"]
                mock_user_service.return_value.update_user_profile.return_value = updated_user

                response = await test_client.put("/api/v1/users/profile", json=update_data, headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert data["first_name"] == "Jane"
                assert data["last_name"] == "Smith"
                assert data["bio"] == "Updated bio"

    @pytest.mark.asyncio
    async def test_change_password(self, test_client: AsyncClient):
        """Test changing user password"""
        headers = {"Authorization": "Bearer valid_token_123"}
        password_data = {
            "current_password": "OldPassword123!",
            "new_password": "NewPassword123!"
        }

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.AuthService') as mock_auth_service:
                mock_auth_service.return_value.change_password.return_value = True

                response = await test_client.post("/api/v1/users/change-password", json=password_data, headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Password changed successfully"

    @pytest.mark.asyncio
    async def test_change_password_invalid_current(self, test_client: AsyncClient):
        """Test changing password with invalid current password"""
        headers = {"Authorization": "Bearer valid_token_123"}
        password_data = {
            "current_password": "WrongPassword",
            "new_password": "NewPassword123!"
        }

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.AuthService') as mock_auth_service:
                mock_auth_service.return_value.change_password.return_value = False

                response = await test_client.post("/api/v1/users/change-password", json=password_data, headers=headers)

                assert response.status_code == 400
                data = response.json()
                assert "Invalid current password" in data["detail"]

    @pytest.mark.asyncio
    async def test_upload_profile_picture(self, test_client: AsyncClient):
        """Test uploading profile picture"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.StorageService') as mock_storage:
                mock_storage.return_value.upload_file.return_value = "https://storage.example.com/profile.jpg"

                # Mock file upload
                files = {"file": ("profile.jpg", b"fake image data", "image/jpeg")}
                response = await test_client.post("/api/v1/users/profile-picture", files=files, headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert "profile_picture_url" in data
                assert data["profile_picture_url"] == "https://storage.example.com/profile.jpg"

    @pytest.mark.asyncio
    async def test_delete_user_account(self, test_client: AsyncClient):
        """Test deleting user account"""
        headers = {"Authorization": "Bearer valid_token_123"}
        delete_data = {
            "password": "UserPassword123!",
            "confirmation": "DELETE"
        }

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.UserService') as mock_user_service:
                mock_user_service.return_value.delete_user_account.return_value = True

                response = await test_client.delete("/api/v1/users/account", json=delete_data, headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Account deleted successfully"

    @pytest.mark.asyncio
    async def test_get_user_sessions(self, test_client: AsyncClient):
        """Test getting user active sessions"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.SessionService') as mock_session_service:
                mock_sessions = [
                    {
                        "id": "session_1",
                        "device_info": "Chrome on Windows",
                        "ip_address": "192.168.1.1",
                        "last_activity": datetime.utcnow().isoformat(),
                        "is_current": True
                    },
                    {
                        "id": "session_2",
                        "device_info": "Mobile Safari",
                        "ip_address": "192.168.1.2",
                        "last_activity": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
                        "is_current": False
                    }
                ]
                mock_session_service.return_value.get_user_sessions.return_value = mock_sessions

                response = await test_client.get("/api/v1/users/sessions", headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert len(data["sessions"]) == 2
                assert data["sessions"][0]["is_current"] == True

    @pytest.mark.asyncio
    async def test_revoke_session(self, test_client: AsyncClient):
        """Test revoking a specific session"""
        headers = {"Authorization": "Bearer valid_token_123"}
        session_id = "session_to_revoke"

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.SessionService') as mock_session_service:
                mock_session_service.return_value.revoke_session.return_value = True

                response = await test_client.delete(f"/api/v1/users/sessions/{session_id}", headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Session revoked successfully"

    @pytest.mark.asyncio
    async def test_get_user_activity_log(self, test_client: AsyncClient):
        """Test getting user activity log"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.ActivityService') as mock_activity_service:
                mock_activities = [
                    {
                        "id": "activity_1",
                        "action": "login",
                        "timestamp": datetime.utcnow().isoformat(),
                        "ip_address": "192.168.1.1",
                        "user_agent": "Chrome/91.0"
                    },
                    {
                        "id": "activity_2",
                        "action": "profile_update",
                        "timestamp": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
                        "ip_address": "192.168.1.1",
                        "user_agent": "Chrome/91.0"
                    }
                ]
                mock_activity_service.return_value.get_user_activities.return_value = mock_activities

                response = await test_client.get("/api/v1/users/activity", headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert len(data["activities"]) == 2
                assert data["activities"][0]["action"] == "login"

    @pytest.mark.asyncio
    async def test_update_user_preferences(self, test_client: AsyncClient):
        """Test updating user preferences"""
        headers = {"Authorization": "Bearer valid_token_123"}
        preferences_data = {
            "email_notifications": True,
            "push_notifications": False,
            "marketing_emails": False,
            "two_factor_enabled": True,
            "language": "es",
            "timezone": "Europe/Madrid"
        }

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.UserService') as mock_user_service:
                mock_user_service.return_value.update_user_preferences.return_value = preferences_data

                response = await test_client.put("/api/v1/users/preferences", json=preferences_data, headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert data["email_notifications"] == True
                assert data["two_factor_enabled"] == True
                assert data["language"] == "es"

    @pytest.mark.asyncio
    async def test_get_user_organizations(self, test_client: AsyncClient):
        """Test getting user's organizations"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.OrganizationService') as mock_org_service:
                mock_organizations = [
                    {
                        "id": "org_1",
                        "name": "Company A",
                        "role": OrganizationRole.ADMIN.value,
                        "joined_at": datetime.utcnow().isoformat()
                    },
                    {
                        "id": "org_2",
                        "name": "Company B",
                        "role": OrganizationRole.MEMBER.value,
                        "joined_at": (datetime.utcnow() - timedelta(days=30)).isoformat()
                    }
                ]
                mock_org_service.return_value.get_user_organizations.return_value = mock_organizations

                response = await test_client.get("/api/v1/users/organizations", headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert len(data["organizations"]) == 2
                assert data["organizations"][0]["role"] == "admin"

    @pytest.mark.asyncio
    async def test_leave_organization(self, test_client: AsyncClient):
        """Test leaving an organization"""
        headers = {"Authorization": "Bearer valid_token_123"}
        org_id = "org_to_leave"

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.OrganizationService') as mock_org_service:
                mock_org_service.return_value.leave_organization.return_value = True

                response = await test_client.delete(f"/api/v1/users/organizations/{org_id}", headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Left organization successfully"


@pytest.mark.asyncio
class TestUserManagementSecurity:
    """Security tests for user management endpoints"""

    @pytest.mark.asyncio
    async def test_unauthorized_profile_access(self, test_client: AsyncClient):
        """Test accessing profile without authentication"""
        response = await test_client.get("/api/v1/users/profile")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_profile_update_validation(self, test_client: AsyncClient):
        """Test profile update with invalid data"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            invalid_data_sets = [
                {"first_name": "a" * 1000},  # Too long
                {"email": "invalid-email"},  # Invalid email
                {"timezone": "Invalid/Timezone"},  # Invalid timezone
                {"language": "invalid_lang_code"},  # Invalid language
            ]

            for invalid_data in invalid_data_sets:
                response = await test_client.put("/api/v1/users/profile", json=invalid_data, headers=headers)
                assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_password_change_security(self, test_client: AsyncClient):
        """Test password change security requirements"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            weak_passwords = [
                "123456",
                "password",
                "qwerty",
                "abc123",
                "password123"
            ]

            for weak_password in weak_passwords:
                password_data = {
                    "current_password": "CurrentPassword123!",
                    "new_password": weak_password
                }

                response = await test_client.post("/api/v1/users/change-password", json=password_data, headers=headers)
                # Should reject weak passwords
                assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_file_upload_security(self, test_client: AsyncClient):
        """Test file upload security measures"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            # Test various malicious file types
            malicious_files = [
                ("malware.exe", b"MZ\x90\x00", "application/x-executable"),
                ("script.php", b"<?php system($_GET['cmd']); ?>", "application/x-php"),
                ("test.html", b"<script>alert('xss')</script>", "text/html"),
                ("large_file.jpg", b"x" * 10000000, "image/jpeg"),  # Very large file
            ]

            for filename, content, content_type in malicious_files:
                files = {"file": (filename, content, content_type)}
                response = await test_client.post("/api/v1/users/profile-picture", files=files, headers=headers)
                # Should reject malicious files
                assert response.status_code in [400, 413, 422]

    @pytest.mark.asyncio
    async def test_session_isolation(self, test_client: AsyncClient):
        """Test that users can only access their own sessions"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.SessionService') as mock_session_service:
                # Attempt to revoke another user's session
                other_user_session = "other_user_session_id"
                mock_session_service.return_value.revoke_session.return_value = False

                response = await test_client.delete(f"/api/v1/users/sessions/{other_user_session}", headers=headers)
                # Should not be able to revoke other user's session
                assert response.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_account_deletion_security(self, test_client: AsyncClient):
        """Test account deletion security measures"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            # Test deletion without proper confirmation
            insufficient_data_sets = [
                {},  # No data
                {"password": "UserPassword123!"},  # Missing confirmation
                {"confirmation": "DELETE"},  # Missing password
                {"password": "wrong_password", "confirmation": "DELETE"},  # Wrong password
                {"password": "UserPassword123!", "confirmation": "WRONG"},  # Wrong confirmation
            ]

            for insufficient_data in insufficient_data_sets:
                response = await test_client.delete("/api/v1/users/account", json=insufficient_data, headers=headers)
                assert response.status_code in [400, 401, 422]


@pytest.mark.asyncio
class TestUserManagementEdgeCases:
    """Edge case tests for user management"""

    @pytest.mark.asyncio
    async def test_concurrent_profile_updates(self, test_client: AsyncClient):
        """Test concurrent profile updates"""
        import asyncio

        headers = {"Authorization": "Bearer valid_token_123"}
        update_data = {"first_name": "Updated Name"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.UserService') as mock_user_service:
                mock_user_service.return_value.update_user_profile.return_value = mock_user

                # Make concurrent profile update requests
                tasks = [
                    test_client.put("/api/v1/users/profile", json=update_data, headers=headers)
                    for _ in range(5)
                ]

                responses = await asyncio.gather(*tasks)

                # All requests should either succeed or fail gracefully
                for response in responses:
                    assert response.status_code in [200, 409, 422]

    @pytest.mark.asyncio
    async def test_unicode_profile_data(self, test_client: AsyncClient):
        """Test profile updates with unicode characters"""
        headers = {"Authorization": "Bearer valid_token_123"}
        unicode_data = {
            "first_name": "José",
            "last_name": "González",
            "bio": "こんにちは世界 🌍 Ñoño",
        }

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.UserService') as mock_user_service:
                updated_user = MagicMock()
                updated_user.first_name = unicode_data["first_name"]
                updated_user.last_name = unicode_data["last_name"]
                updated_user.bio = unicode_data["bio"]
                mock_user_service.return_value.update_user_profile.return_value = updated_user

                response = await test_client.put("/api/v1/users/profile", json=unicode_data, headers=headers)

                assert response.status_code == 200
                data = response.json()
                assert data["first_name"] == "José"
                assert data["bio"] == "こんにちは世界 🌍 Ñoño"

    @pytest.mark.asyncio
    async def test_empty_and_null_values(self, test_client: AsyncClient):
        """Test handling of empty and null values in profile updates"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            test_cases = [
                {"first_name": ""},  # Empty string
                {"first_name": None},  # Null value
                {"bio": "   "},  # Whitespace only
                {"first_name": "Valid", "last_name": ""},  # Mixed valid/empty
            ]

            for test_data in test_cases:
                response = await test_client.put("/api/v1/users/profile", json=test_data, headers=headers)
                # Should handle gracefully - either accept, reject, or sanitize
                assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_timezone_edge_cases(self, test_client: AsyncClient):
        """Test timezone handling edge cases"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            timezone_cases = [
                "UTC",
                "America/New_York",
                "Europe/London",
                "Asia/Tokyo",
                "Pacific/Auckland",
                "Invalid/Timezone",  # Should be rejected
                "",  # Empty
                None,  # Null
            ]

            for timezone in timezone_cases:
                update_data = {"timezone": timezone}
                response = await test_client.put("/api/v1/users/profile", json=update_data, headers=headers)

                if timezone in ["Invalid/Timezone", "", None]:
                    assert response.status_code in [400, 422]
                else:
                    # Valid timezones should be accepted or handled gracefully
                    assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_large_session_list(self, test_client: AsyncClient):
        """Test handling of users with many active sessions"""
        headers = {"Authorization": "Bearer valid_token_123"}

        with patch('app.dependencies.get_current_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.id = str(uuid.uuid4())
            mock_get_user.return_value = mock_user

            with patch('app.routers.v1.users.SessionService') as mock_session_service:
                # Simulate many active sessions
                large_session_list = [
                    {
                        "id": f"session_{i}",
                        "device_info": f"Device {i}",
                        "ip_address": f"192.168.1.{i % 255}",
                        "last_activity": datetime.utcnow().isoformat(),
                        "is_current": i == 0
                    }
                    for i in range(100)
                ]
                mock_session_service.return_value.get_user_sessions.return_value = large_session_list

                response = await test_client.get("/api/v1/users/sessions", headers=headers)

                assert response.status_code == 200
                data = response.json()
                # Should handle large lists gracefully (possibly with pagination)
                assert "sessions" in data
                assert len(data["sessions"]) <= 100  # Should return all or paginate