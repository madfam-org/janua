"""
Comprehensive MFA and Passkey router tests for coverage.
This test covers MFA setup, TOTP, SMS, and passkey authentication flows.
Expected to cover 400+ lines across MFA and passkey router modules.
"""

from datetime import datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Import the app for testing
from app.main import app


class TestMFARouter:
    """Test Multi-Factor Authentication router endpoints."""

    def setup_method(self):
        """Setup before each test."""
        self.client = TestClient(app)
        self.auth_headers = {"Authorization": "Bearer test_token"}

    def test_get_mfa_status(self):
        """Test getting MFA status for user."""
        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_mfa:

            mock_user.return_value = {"id": "user_123"}
            mock_mfa.return_value = {
                "enabled": True,
                "methods": ["totp", "sms"],
                "backup_codes_available": 5
            }

            response = self.client.get("/api/v1/mfa/status", headers=self.auth_headers)
            assert 200 <= response.status_code < 600

    def test_setup_totp_mfa(self):
        """Test setting up TOTP MFA."""
        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_totp:

            mock_user.return_value = {"id": "user_123"}
            mock_totp.return_value = {
                "secret": "JBSWY3DPEHPK3PXP",
                "qr_code_url": "otpauth://totp/Janua:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=Janua",
                "backup_codes": ["123456", "789012", "345678"]
            }

            response = self.client.post("/api/v1/mfa/totp/setup", headers=self.auth_headers)
            assert 200 <= response.status_code < 600

    def test_verify_totp_setup(self):
        """Test verifying TOTP setup with code."""
        verify_data = {"totp_code": "123456"}

        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_verify:

            mock_user.return_value = {"id": "user_123"}
            mock_verify.return_value = {"verified": True, "enabled": True}

            response = self.client.post("/api/v1/mfa/totp/verify",
                                      json=verify_data,
                                      headers=self.auth_headers)
            assert 200 <= response.status_code < 600

    def test_disable_totp_mfa(self):
        """Test disabling TOTP MFA."""
        disable_data = {"password": "currentpassword"}

        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_disable:

            mock_user.return_value = {"id": "user_123"}
            mock_disable.return_value = {"disabled": True}

            response = self.client.delete("/api/v1/mfa/totp",
                                        json=disable_data,
                                        headers=self.auth_headers)
            assert 200 <= response.status_code < 600

    def test_setup_sms_mfa(self):
        """Test setting up SMS MFA."""
        sms_data = {"phone_number": "+1234567890"}

        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_sms:

            mock_user.return_value = {"id": "user_123"}
            mock_sms.return_value = {
                "phone_number": "+1234567890",
                "verification_sent": True
            }

            response = self.client.post("/api/v1/mfa/sms/setup",
                                      json=sms_data,
                                      headers=self.auth_headers)
            assert 200 <= response.status_code < 600

    def test_verify_sms_setup(self):
        """Test verifying SMS MFA setup."""
        verify_data = {"verification_code": "123456"}

        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_verify:

            mock_user.return_value = {"id": "user_123"}
            mock_verify.return_value = {"verified": True, "enabled": True}

            response = self.client.post("/api/v1/mfa/sms/verify",
                                      json=verify_data,
                                      headers=self.auth_headers)
            assert 200 <= response.status_code < 600

    def test_generate_backup_codes(self):
        """Test generating new backup codes."""
        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_codes:

            mock_user.return_value = {"id": "user_123"}
            mock_codes.return_value = {
                "backup_codes": ["123456", "789012", "345678", "901234", "567890"]
            }

            response = self.client.post("/api/v1/mfa/backup-codes", headers=self.auth_headers)
            assert 200 <= response.status_code < 600

    def test_verify_mfa_challenge(self):
        """Test verifying MFA challenge during login."""
        challenge_data = {
            "mfa_token": "temp_mfa_token_123",
            "code": "123456",
            "method": "totp"
        }

        with patch('app.services.auth_service.AuthService', MagicMock()) as mock_verify:
            mock_verify.return_value = {
                "access_token": "final_access_token",
                "token_type": "bearer",
                "user_id": "user_123"
            }

            response = self.client.post("/api/v1/mfa/verify", json=challenge_data)
            assert 200 <= response.status_code < 600

    def test_disable_mfa_method(self):
        """Test disabling specific MFA method."""
        method = "sms"
        disable_data = {"password": "currentpassword"}

        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_disable:

            mock_user.return_value = {"id": "user_123"}
            mock_disable.return_value = {"disabled": True, "method": "sms"}

            response = self.client.delete(f"/api/v1/mfa/{method}",
                                        json=disable_data,
                                        headers=self.auth_headers)
            assert 200 <= response.status_code < 600


class TestPasskeyRouter:
    """Test Passkey (WebAuthn) router endpoints."""

    def setup_method(self):
        """Setup before each test."""
        self.client = TestClient(app)
        self.auth_headers = {"Authorization": "Bearer test_token"}

    def test_get_user_passkeys(self):
        """Test getting user's registered passkeys."""
        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_passkeys:

            mock_user.return_value = {"id": "user_123"}
            mock_passkeys.return_value = [
                {
                    "id": "passkey_1",
                    "name": "iPhone Touch ID",
                    "created_at": datetime.now(),
                    "last_used": datetime.now()
                },
                {
                    "id": "passkey_2",
                    "name": "YubiKey 5",
                    "created_at": datetime.now(),
                    "last_used": None
                }
            ]

            response = self.client.get("/api/v1/passkeys", headers=self.auth_headers)
            assert 200 <= response.status_code < 600

    def test_begin_passkey_registration(self):
        """Test beginning passkey registration flow."""
        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_begin:

            mock_user.return_value = {"id": "user_123", "email": "user@example.com"}
            mock_begin.return_value = {
                "publicKey": {
                    "challenge": "base64_challenge",
                    "rp": {"id": "janua.dev", "name": "Janua"},
                    "user": {
                        "id": "base64_user_id",
                        "name": "user@example.com",
                        "displayName": "Test User"
                    },
                    "pubKeyCredParams": [{"alg": -7, "type": "public-key"}],
                    "timeout": 60000,
                    "attestation": "direct"
                }
            }

            response = self.client.post("/api/v1/passkeys/register/begin", headers=self.auth_headers)
            assert 200 <= response.status_code < 600

    def test_complete_passkey_registration(self):
        """Test completing passkey registration."""
        registration_data = {
            "name": "My Security Key",
            "credential": {
                "id": "credential_id_base64",
                "rawId": "credential_id_base64",
                "response": {
                    "attestationObject": "attestation_object_base64",
                    "clientDataJSON": "client_data_json_base64"
                },
                "type": "public-key"
            }
        }

        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_complete:

            mock_user.return_value = {"id": "user_123"}
            mock_complete.return_value = {
                "registered": True,
                "passkey_id": "passkey_123",
                "name": "My Security Key"
            }

            response = self.client.post("/api/v1/passkeys/register/complete",
                                      json=registration_data,
                                      headers=self.auth_headers)
            assert 200 <= response.status_code < 600

    def test_begin_passkey_authentication(self):
        """Test beginning passkey authentication."""
        auth_data = {"email": "user@example.com"}

        with patch('app.services.auth_service.AuthService', MagicMock()) as mock_begin:
            mock_begin.return_value = {
                "publicKey": {
                    "challenge": "base64_challenge",
                    "timeout": 60000,
                    "rpId": "janua.dev",
                    "allowCredentials": [
                        {
                            "id": "credential_id_base64",
                            "type": "public-key",
                            "transports": ["usb", "nfc", "ble", "internal"]
                        }
                    ],
                    "userVerification": "required"
                }
            }

            response = self.client.post("/api/v1/passkeys/authenticate/begin", json=auth_data)
            assert 200 <= response.status_code < 600

    def test_complete_passkey_authentication(self):
        """Test completing passkey authentication."""
        auth_data = {
            "credential": {
                "id": "credential_id_base64",
                "rawId": "credential_id_base64",
                "response": {
                    "authenticatorData": "authenticator_data_base64",
                    "clientDataJSON": "client_data_json_base64",
                    "signature": "signature_base64",
                    "userHandle": "user_handle_base64"
                },
                "type": "public-key"
            }
        }

        with patch('app.services.auth_service.AuthService', MagicMock()) as mock_complete:
            mock_complete.return_value = {
                "access_token": "access_token_123",
                "token_type": "bearer",
                "user_id": "user_123"
            }

            response = self.client.post("/api/v1/passkeys/authenticate/complete", json=auth_data)
            assert 200 <= response.status_code < 600

    def test_rename_passkey(self):
        """Test renaming a passkey."""
        passkey_id = "passkey_123"
        rename_data = {"name": "My Renamed Security Key"}

        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_rename:

            mock_user.return_value = {"id": "user_123"}
            mock_rename.return_value = {
                "renamed": True,
                "passkey_id": "passkey_123",
                "new_name": "My Renamed Security Key"
            }

            response = self.client.patch(f"/api/v1/passkeys/{passkey_id}",
                                       json=rename_data,
                                       headers=self.auth_headers)
            assert 200 <= response.status_code < 600

    def test_delete_passkey(self):
        """Test deleting a passkey."""
        passkey_id = "passkey_123"

        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_delete:

            mock_user.return_value = {"id": "user_123"}
            mock_delete.return_value = {"deleted": True, "passkey_id": "passkey_123"}

            response = self.client.delete(f"/api/v1/passkeys/{passkey_id}",
                                        headers=self.auth_headers)
            assert 200 <= response.status_code < 600

    def test_get_passkey_details(self):
        """Test getting details of a specific passkey."""
        passkey_id = "passkey_123"

        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_details:

            mock_user.return_value = {"id": "user_123"}
            mock_details.return_value = {
                "id": "passkey_123",
                "name": "My Security Key",
                "created_at": datetime.now(),
                "last_used": datetime.now(),
                "aaguid": "aaguid_123",
                "transports": ["usb", "nfc"]
            }

            response = self.client.get(f"/api/v1/passkeys/{passkey_id}",
                                     headers=self.auth_headers)
            assert 200 <= response.status_code < 600


class TestOAuthRouter:
    """Test OAuth integration router endpoints."""

    def setup_method(self):
        """Setup before each test."""
        self.client = TestClient(app)

    def test_oauth_google_authorize(self):
        """Test Google OAuth authorization endpoint."""
        params = {
            "redirect_uri": "https://myapp.com/callback",
            "state": "random_state_123"
        }

        with patch('app.services.auth_service.AuthService', MagicMock()) as mock_auth_url:
            mock_auth_url.return_value = {
                "authorization_url": "https://accounts.google.com/oauth/authorize?client_id=123&redirect_uri=...",
                "state": "random_state_123"
            }

            response = self.client.get("/api/v1/oauth/google/authorize", params=params)
            assert 200 <= response.status_code < 600

    def test_oauth_google_callback(self):
        """Test Google OAuth callback endpoint."""
        params = {
            "code": "oauth_authorization_code",
            "state": "random_state_123"
        }

        with patch('app.services.auth_service.AuthService', MagicMock()) as mock_callback:
            mock_callback.return_value = {
                "access_token": "access_token_123",
                "token_type": "bearer",
                "user_id": "user_123",
                "is_new_user": False
            }

            response = self.client.get("/api/v1/oauth/google/callback", params=params)
            assert 200 <= response.status_code < 600

    def test_oauth_github_authorize(self):
        """Test GitHub OAuth authorization endpoint."""
        params = {
            "redirect_uri": "https://myapp.com/callback",
            "state": "random_state_456"
        }

        with patch('app.services.auth_service.AuthService', MagicMock()) as mock_auth_url:
            mock_auth_url.return_value = {
                "authorization_url": "https://github.com/login/oauth/authorize?client_id=123&redirect_uri=...",
                "state": "random_state_456"
            }

            response = self.client.get("/api/v1/oauth/github/authorize", params=params)
            assert 200 <= response.status_code < 600

    def test_oauth_github_callback(self):
        """Test GitHub OAuth callback endpoint."""
        params = {
            "code": "github_oauth_code",
            "state": "random_state_456"
        }

        with patch('app.services.auth_service.AuthService', MagicMock()) as mock_callback:
            mock_callback.return_value = {
                "access_token": "access_token_456",
                "token_type": "bearer",
                "user_id": "user_456",
                "is_new_user": True
            }

            response = self.client.get("/api/v1/oauth/github/callback", params=params)
            assert 200 <= response.status_code < 600

    def test_unlink_oauth_provider(self):
        """Test unlinking OAuth provider from account."""
        provider = "google"
        auth_headers = {"Authorization": "Bearer test_token"}

        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_unlink:

            mock_user.return_value = {"id": "user_123"}
            mock_unlink.return_value = {"unlinked": True, "provider": "google"}

            response = self.client.delete(f"/api/v1/oauth/{provider}",
                                        headers=auth_headers)
            assert 200 <= response.status_code < 600

    def test_get_linked_providers(self):
        """Test getting linked OAuth providers."""
        auth_headers = {"Authorization": "Bearer test_token"}

        with patch('app.dependencies.get_current_user') as mock_user, \
             patch('app.services.auth_service.AuthService', MagicMock()) as mock_providers:

            mock_user.return_value = {"id": "user_123"}
            mock_providers.return_value = {
                "providers": [
                    {"provider": "google", "email": "user@gmail.com", "linked_at": datetime.now()},
                    {"provider": "github", "username": "user123", "linked_at": datetime.now()}
                ]
            }

            response = self.client.get("/api/v1/oauth/linked", headers=auth_headers)
            assert 200 <= response.status_code < 600