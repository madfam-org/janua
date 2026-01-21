"""Tests for the authentication module."""

import pytest
from unittest.mock import Mock
from uuid import uuid4

from janua.auth import AuthClient
from janua.types import (
    User,
    Session,
    AuthTokens,
    OAuthProvider,
)


class TestAuthClient:
    """Test the AuthClient class."""
    
    @pytest.fixture
    def mock_http(self):
        """Create a mock HTTP client."""
        return Mock()
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        config = Mock()
        config.api_key = "test_api_key"
        config.base_url = "https://api.janua.dev"
        return config
    
    @pytest.fixture
    def auth_client(self, mock_http, mock_config):
        """Create an AuthClient instance with mocks."""
        return AuthClient(mock_http, mock_config)
    
    def test_sign_up_success(self, auth_client, mock_http):
        """Test successful user sign up."""
        user_id = str(uuid4())
        mock_response = Mock()
        mock_response.json.return_value = {
            "user": {
                "id": user_id,
                "email": "test@example.com",
                "email_verified": False,
                "first_name": "Test",
                "last_name": "User",
                "role": "user",
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        }
        mock_http.post.return_value = mock_response
        
        user = auth_client.sign_up(
            email="test@example.com",
            password="SecurePassword123!",
            first_name="Test",
            last_name="User",
        )
        
        assert isinstance(user, User)
        assert user.email == "test@example.com"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.email_verified is False
        
        mock_http.post.assert_called_once()
        call_args = mock_http.post.call_args
        assert call_args[0][0] == "/auth/signup"
        assert call_args[1]["json"]["email"] == "test@example.com"
        assert call_args[1]["json"]["password"] == "SecurePassword123!"
    
    def test_sign_up_with_metadata(self, auth_client, mock_http):
        """Test sign up with metadata."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "user": {
                "id": str(uuid4()),
                "email": "test@example.com",
                "email_verified": False,
                "role": "user",
                "status": "active",
                "metadata": {"source": "mobile"},
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        }
        mock_http.post.return_value = mock_response
        
        user = auth_client.sign_up(
            email="test@example.com",
            password="SecurePassword123!",
            metadata={"source": "mobile"},
        )
        
        assert user.metadata == {"source": "mobile"}
    
    def test_sign_in_success(self, auth_client, mock_http):
        """Test successful user sign in."""
        user_id = str(uuid4())
        session_id = str(uuid4())
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "user": {
                "id": user_id,
                "email": "test@example.com",
                "email_verified": True,
                "role": "user",
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
            "session": {
                "id": session_id,
                "user_id": user_id,
                "expires_at": "2024-01-02T00:00:00Z",
                "created_at": "2024-01-01T00:00:00Z",
            },
            "tokens": {
                "access_token": "access_token_value",
                "refresh_token": "refresh_token_value",
                "token_type": "Bearer",
                "expires_in": 3600,
            }
        }
        mock_http.post.return_value = mock_response
        
        result = auth_client.sign_in(
            email="test@example.com",
            password="SecurePassword123!",
        )
        
        assert "user" in result
        assert "session" in result
        assert "tokens" in result
        assert isinstance(result["user"], User)
        assert isinstance(result["session"], Session)
        assert isinstance(result["tokens"], AuthTokens)
        assert result["user"].email == "test@example.com"
        assert result["tokens"].access_token == "access_token_value"
    
    def test_sign_in_with_remember_me(self, auth_client, mock_http):
        """Test sign in with remember me option."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "user": {"id": str(uuid4()), "email": "test@example.com", "role": "user", "status": "active", "created_at": "2024-01-01T00:00:00Z", "updated_at": "2024-01-01T00:00:00Z"},
            "session": {"id": str(uuid4()), "user_id": str(uuid4()), "expires_at": "2024-01-02T00:00:00Z", "created_at": "2024-01-01T00:00:00Z"},
            "tokens": {"access_token": "token", "refresh_token": "refresh", "token_type": "Bearer", "expires_in": 3600}
        }
        mock_http.post.return_value = mock_response
        
        auth_client.sign_in(
            email="test@example.com",
            password="password",
            remember_me=True,
            session_duration=86400,
        )
        
        call_args = mock_http.post.call_args
        assert call_args[1]["json"]["remember_me"] is True
        assert call_args[1]["json"]["session_duration"] == 86400
    
    def test_sign_out(self, auth_client, mock_http):
        """Test sign out."""
        auth_client.sign_out()
        
        mock_http.post.assert_called_once_with(
            "/auth/signout",
            json={}
        )
    
    def test_sign_out_specific_session(self, auth_client, mock_http):
        """Test sign out specific session."""
        session_id = str(uuid4())
        auth_client.sign_out(session_id=session_id)
        
        mock_http.post.assert_called_once_with(
            "/auth/signout",
            json={"session_id": session_id}
        )
    
    def test_sign_out_all(self, auth_client, mock_http):
        """Test sign out all sessions."""
        user_id = str(uuid4())
        auth_client.sign_out_all(user_id=user_id)
        
        mock_http.post.assert_called_once_with(f"/auth/signout-all/{user_id}")
    
    def test_get_current_user(self, auth_client, mock_http):
        """Test get current user."""
        user_id = str(uuid4())
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": user_id,
            "email": "current@example.com",
            "email_verified": True,
            "role": "user",
            "status": "active",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_http.get.return_value = mock_response
        
        user = auth_client.get_current_user()
        
        assert isinstance(user, User)
        assert user.email == "current@example.com"
        mock_http.get.assert_called_once_with("/auth/me")
    
    def test_refresh_token(self, auth_client, mock_http):
        """Test refresh token."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        mock_http.post.return_value = mock_response
        
        tokens = auth_client.refresh_token("old_refresh_token")
        
        assert isinstance(tokens, AuthTokens)
        assert tokens.access_token == "new_access_token"
        assert tokens.refresh_token == "new_refresh_token"
        
        mock_http.post.assert_called_once_with(
            "/auth/refresh",
            json={"refresh_token": "old_refresh_token"}
        )
    
    def test_request_password_reset(self, auth_client, mock_http):
        """Test request password reset."""
        auth_client.request_password_reset("user@example.com")
        
        mock_http.post.assert_called_once()
        call_args = mock_http.post.call_args
        assert call_args[0][0] == "/auth/password/reset"
        assert call_args[1]["json"]["email"] == "user@example.com"
    
    def test_reset_password(self, auth_client, mock_http):
        """Test reset password."""
        auth_client.reset_password(
            token="reset_token",
            new_password="NewSecurePassword123!"
        )
        
        mock_http.post.assert_called_once_with(
            "/auth/password/confirm",
            json={
                "token": "reset_token",
                "password": "NewSecurePassword123!"
            }
        )
    
    def test_change_password(self, auth_client, mock_http):
        """Test change password."""
        auth_client.change_password(
            current_password="OldPassword123!",
            new_password="NewPassword123!"
        )
        
        mock_http.post.assert_called_once_with(
            "/auth/password/change",
            json={
                "current_password": "OldPassword123!",
                "new_password": "NewPassword123!"
            }
        )
    
    def test_request_email_verification(self, auth_client, mock_http):
        """Test request email verification."""
        auth_client.request_email_verification("user@example.com")
        
        mock_http.post.assert_called_once()
        call_args = mock_http.post.call_args
        assert call_args[0][0] == "/auth/email/verify"
        assert call_args[1]["json"]["email"] == "user@example.com"
    
    def test_verify_email(self, auth_client, mock_http):
        """Test verify email."""
        user_id = str(uuid4())
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": user_id,
            "email": "verified@example.com",
            "email_verified": True,
            "role": "user",
            "status": "active",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_http.post.return_value = mock_response
        
        user = auth_client.verify_email("verification_token")
        
        assert isinstance(user, User)
        assert user.email_verified is True
        
        mock_http.post.assert_called_once_with(
            "/auth/email/confirm",
            json={"token": "verification_token"}
        )
    
    def test_get_oauth_url(self, auth_client, mock_http):
        """Test get OAuth URL."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "url": "https://provider.com/oauth/authorize?client_id=123"
        }
        mock_http.get.return_value = mock_response
        
        url = auth_client.get_oauth_url(
            provider=OAuthProvider.GOOGLE,
            redirect_uri="https://app.example.com/callback",
            state="random_state",
            scopes=["email", "profile"]
        )
        
        assert url == "https://provider.com/oauth/authorize?client_id=123"
        
        mock_http.get.assert_called_once()
        call_args = mock_http.get.call_args
        assert call_args[0][0] == "/auth/oauth/url"
        assert call_args[1]["params"]["provider"] == "google"
        assert call_args[1]["params"]["redirect_uri"] == "https://app.example.com/callback"
        assert call_args[1]["params"]["state"] == "random_state"
        assert call_args[1]["params"]["scopes"] == "email,profile"
    
    def test_handle_oauth_callback(self, auth_client, mock_http):
        """Test handle OAuth callback."""
        user_id = str(uuid4())
        session_id = str(uuid4())
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "user": {
                "id": user_id,
                "email": "oauth@example.com",
                "email_verified": True,
                "role": "user",
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
            "session": {
                "id": session_id,
                "user_id": user_id,
                "expires_at": "2024-01-02T00:00:00Z",
                "created_at": "2024-01-01T00:00:00Z",
            },
            "tokens": {
                "access_token": "oauth_access_token",
                "refresh_token": "oauth_refresh_token",
                "token_type": "Bearer",
                "expires_in": 3600,
            }
        }
        mock_http.post.return_value = mock_response
        
        result = auth_client.handle_oauth_callback(
            provider=OAuthProvider.GITHUB,
            code="auth_code",
            state="state_value"
        )
        
        assert "user" in result
        assert "session" in result
        assert "tokens" in result
        assert result["user"].email == "oauth@example.com"
        
        mock_http.post.assert_called_once_with(
            "/auth/oauth/callback",
            json={
                "provider": "github",
                "code": "auth_code",
                "state": "state_value"
            }
        )
    
    def test_link_oauth_account(self, auth_client, mock_http):
        """Test link OAuth account."""
        user_id = str(uuid4())
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": user_id,
            "email": "user@example.com",
            "email_verified": True,
            "role": "user",
            "status": "active",
            "oauth_providers": ["google"],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_http.post.return_value = mock_response
        
        user = auth_client.link_oauth_account(
            provider=OAuthProvider.GOOGLE,
            access_token="google_access_token"
        )
        
        assert isinstance(user, User)
        assert "google" in user.oauth_providers
        
        mock_http.post.assert_called_once_with(
            "/auth/oauth/link",
            json={
                "provider": "google",
                "access_token": "google_access_token"
            }
        )
    
    def test_unlink_oauth_account(self, auth_client, mock_http):
        """Test unlink OAuth account."""
        user_id = str(uuid4())
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": user_id,
            "email": "user@example.com",
            "email_verified": True,
            "role": "user",
            "status": "active",
            "oauth_providers": [],
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        mock_http.delete.return_value = mock_response
        
        user = auth_client.unlink_oauth_account(OAuthProvider.GOOGLE)
        
        assert isinstance(user, User)
        assert len(user.oauth_providers) == 0
        
        mock_http.delete.assert_called_once_with("/auth/oauth/link/google")
    
    def test_check_session(self, auth_client, mock_http):
        """Test check session."""
        session_id = str(uuid4())
        user_id = str(uuid4())
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": session_id,
            "user_id": user_id,
            "expires_at": "2024-01-02T00:00:00Z",
            "created_at": "2024-01-01T00:00:00Z",
        }
        mock_http.get.return_value = mock_response
        
        session = auth_client.check_session(session_id)
        
        assert isinstance(session, Session)
        assert str(session.id) == session_id
        
        mock_http.get.assert_called_once_with(f"/auth/sessions/{session_id}")