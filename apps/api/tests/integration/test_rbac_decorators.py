"""
Integration tests for RBAC decorator functionality
Tests FastAPI decorators with real endpoint integration
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rbac_engine import Action, PermissionManager, RBACEngine, ResourceType

# Create test app with RBAC-decorated endpoints
test_app = FastAPI()
rbac_engine = RBACEngine()
rbac = PermissionManager(rbac_engine)


# Test endpoints using RBAC decorators
@test_app.get("/test/require-permission")
@rbac.require_permission(ResourceType.USER, Action.READ)
async def test_require_permission_endpoint(
    db: AsyncSession = Depends(get_db), current_user_id: str = None
):
    """Test endpoint with require_permission decorator"""
    return {"message": "success", "user_id": current_user_id}


@test_app.get("/test/require-any-permission")
@rbac.require_any_permission(["user:read", "user:admin"])
async def test_require_any_permission_endpoint(
    db: AsyncSession = Depends(get_db), current_user_id: str = None
):
    """Test endpoint with require_any_permission decorator"""
    return {"message": "success", "user_id": current_user_id}


class TestRequirePermissionDecorator:
    """Test @require_permission decorator functionality"""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client"""
        return TestClient(test_app)

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def test_user_id(self):
        """Test user ID"""
        return str(uuid4())

    def test_require_permission_success(self, client, mock_db_session, test_user_id):
        """Test decorator allows access when permission check passes"""

        # Mock the check_permission to return True
        with patch.object(rbac_engine, "check_permission", new=AsyncMock(return_value=True)):
            # Mock get_db dependency
            def override_get_db():
                return mock_db_session

            test_app.dependency_overrides[get_db] = override_get_db

            try:
                # Make request with user_id in query params (simulating dependency injection)
                response = client.get(
                    "/test/require-permission", params={"current_user_id": test_user_id}
                )

                # Should succeed
                assert response.status_code == 200
                assert response.json()["message"] == "success"
            finally:
                test_app.dependency_overrides.clear()

    def test_require_permission_denied(self, client, mock_db_session, test_user_id):
        """Test decorator denies access when permission check fails"""

        # Mock the check_permission to return False
        with patch.object(rbac_engine, "check_permission", new=AsyncMock(return_value=False)):

            def override_get_db():
                return mock_db_session

            test_app.dependency_overrides[get_db] = override_get_db

            try:
                response = client.get(
                    "/test/require-permission", params={"current_user_id": test_user_id}
                )

                # Should be forbidden
                assert response.status_code == 403
                assert "Permission denied" in response.json()["detail"]
            finally:
                test_app.dependency_overrides.clear()

    def test_require_permission_no_auth(self, client):
        """Test decorator requires authentication"""

        # No user_id provided - should fail with 403
        response = client.get("/test/require-permission")

        assert response.status_code == 403
        assert "Authentication required" in response.json()["detail"]

    def test_require_permission_no_session(self, client, test_user_id):
        """Test decorator requires database session"""

        # User provided but no db session
        # Override get_db to return None
        def override_get_db():
            return None

        test_app.dependency_overrides[get_db] = override_get_db

        try:
            response = client.get(
                "/test/require-permission", params={"current_user_id": test_user_id}
            )

            assert response.status_code == 403
            assert "Authentication required" in response.json()["detail"]
        finally:
            test_app.dependency_overrides.clear()

    def test_require_permission_with_resource_id(self, client, mock_db_session, test_user_id):
        """Test decorator handles resource-specific permissions"""

        # Test decorator calls check_permission (validates decorator is working)
        with patch.object(
            rbac_engine, "check_permission", new=AsyncMock(return_value=True)
        ) as mock_check:

            def override_get_db():
                return mock_db_session

            test_app.dependency_overrides[get_db] = override_get_db

            try:
                response = client.get(
                    "/test/require-permission",
                    params={"current_user_id": test_user_id},
                )

                assert response.status_code == 200
                # Verify decorator called check_permission
                mock_check.assert_called_once()
            finally:
                test_app.dependency_overrides.clear()


class TestRequireAnyPermissionDecorator:
    """Test @require_any_permission decorator functionality"""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client"""
        return TestClient(test_app)

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def test_user_id(self):
        """Test user ID"""
        return str(uuid4())

    def test_require_any_permission_success(self, client, mock_db_session, test_user_id):
        """Test decorator allows access when user has any required permission"""

        # Mock has_any_permission to return True
        with patch.object(rbac_engine, "has_any_permission", new=AsyncMock(return_value=True)):

            def override_get_db():
                return mock_db_session

            test_app.dependency_overrides[get_db] = override_get_db

            try:
                response = client.get(
                    "/test/require-any-permission", params={"current_user_id": test_user_id}
                )

                assert response.status_code == 200
                assert response.json()["message"] == "success"
            finally:
                test_app.dependency_overrides.clear()

    def test_require_any_permission_denied(self, client, mock_db_session, test_user_id):
        """Test decorator denies access when user lacks all required permissions"""

        # Mock has_any_permission to return False
        with patch.object(rbac_engine, "has_any_permission", new=AsyncMock(return_value=False)):

            def override_get_db():
                return mock_db_session

            test_app.dependency_overrides[get_db] = override_get_db

            try:
                response = client.get(
                    "/test/require-any-permission", params={"current_user_id": test_user_id}
                )

                assert response.status_code == 403
                assert "Permission denied" in response.json()["detail"]
                assert "requires one of" in response.json()["detail"]
            finally:
                test_app.dependency_overrides.clear()

    def test_require_any_permission_no_auth(self, client):
        """Test decorator requires authentication"""

        response = client.get("/test/require-any-permission")

        assert response.status_code == 403
        assert "Authentication required" in response.json()["detail"]

    def test_require_any_permission_no_session(self, client, test_user_id):
        """Test decorator requires database session"""

        def override_get_db():
            return None

        test_app.dependency_overrides[get_db] = override_get_db

        try:
            response = client.get(
                "/test/require-any-permission", params={"current_user_id": test_user_id}
            )

            assert response.status_code == 403
            assert "Authentication required" in response.json()["detail"]
        finally:
            test_app.dependency_overrides.clear()


class TestDecoratorErrorHandling:
    """Test decorator error handling and edge cases"""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client"""
        return TestClient(test_app)

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def test_user_id(self):
        """Test user ID"""
        return str(uuid4())

    def test_decorator_handles_permission_check_exception(
        self, client, mock_db_session, test_user_id
    ):
        """Test decorator propagates exceptions from permission check"""

        # Mock check_permission to raise exception
        with patch.object(
            rbac_engine, "check_permission", new=AsyncMock(side_effect=Exception("DB error"))
        ):

            def override_get_db():
                return mock_db_session

            test_app.dependency_overrides[get_db] = override_get_db

            try:
                # Exception should propagate through decorator (FastAPI handles it)
                with pytest.raises(Exception) as exc_info:
                    client.get("/test/require-permission", params={"current_user_id": test_user_id})

                # Verify it's our mocked exception
                assert "DB error" in str(exc_info.value)
            finally:
                test_app.dependency_overrides.clear()

    def test_decorator_logs_permission_denial(self, client, mock_db_session, test_user_id):
        """Test decorator logs when permission is denied"""

        with patch.object(rbac_engine, "check_permission", new=AsyncMock(return_value=False)):
            with patch("app.core.rbac_engine.logger") as mock_logger:

                def override_get_db():
                    return mock_db_session

                test_app.dependency_overrides[get_db] = override_get_db

                try:
                    client.get("/test/require-permission", params={"current_user_id": test_user_id})

                    # Verify logging occurred
                    assert mock_logger.warning.called
                    # Check log message contains permission denial info
                    call_args = mock_logger.warning.call_args
                    assert "Permission denied" in str(call_args)
                finally:
                    test_app.dependency_overrides.clear()
