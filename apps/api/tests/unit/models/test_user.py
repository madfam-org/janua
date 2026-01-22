"""
Tests for User model
"""

from app.models.user import User


class TestUserModel:
    """Test User model"""

    def test_user_creation(self):
        """Test user can be created"""
        user = User(email="test@example.com", name="Test User")
        assert user.email == "test@example.com"
        assert user.name == "Test User"
