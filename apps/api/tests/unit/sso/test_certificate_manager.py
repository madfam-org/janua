"""
Comprehensive Certificate Manager Test Suite
Tests X.509 certificate validation, generation, storage, and conversion.
"""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


class TestCertificateValidation:
    """Test certificate validation functionality"""

    @pytest.fixture
    def certificate_manager(self):
        """Create certificate manager with temp storage"""
        from app.sso.domain.services.certificate_manager import CertificateManager

        with tempfile.TemporaryDirectory() as tmpdir:
            yield CertificateManager(storage_path=tmpdir)

    @pytest.fixture
    def valid_certificate(self, certificate_manager):
        """Generate a valid test certificate"""
        cert_pem, _ = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com",
            organization="Test Org",
            validity_days=365,
        )
        return cert_pem

    @pytest.fixture
    def expired_certificate(self, certificate_manager):
        """Generate an expired certificate using mocked time"""
        # We can't easily generate an expired cert, so we'll mock validation
        # For real testing, we'd need a pre-generated expired certificate
        # This fixture shows the pattern
        return None  # Placeholder

    def test_validate_valid_certificate(self, certificate_manager, valid_certificate):
        """Should validate a valid certificate"""
        result = certificate_manager.validate_certificate(valid_certificate)

        assert result["valid"] is True
        assert "subject" in result
        assert "issuer" in result
        assert "not_before" in result
        assert "not_after" in result
        assert len(result["warnings"]) == 0

    def test_validate_certificate_with_warnings(
        self, certificate_manager, valid_certificate
    ):
        """Should return warnings for certificates with short validity"""
        result = certificate_manager.validate_certificate(
            valid_certificate, min_validity_days=400  # More than our 365-day cert
        )

        assert result["valid"] is True
        assert any("expires" in w for w in result["warnings"])

    def test_validate_invalid_certificate_string(self, certificate_manager):
        """Should raise error for invalid certificate data"""
        from app.sso.exceptions import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            certificate_manager.validate_certificate("not a certificate")

        assert "Invalid certificate" in str(exc_info.value)

    def test_validate_without_expiry_check(
        self, certificate_manager, valid_certificate
    ):
        """Should skip expiry check when disabled"""
        result = certificate_manager.validate_certificate(
            valid_certificate, check_expiry=False
        )

        assert result["valid"] is True
        assert "days_until_expiry" not in result

    def test_validate_extracts_key_size(self, certificate_manager, valid_certificate):
        """Should extract key size from certificate"""
        result = certificate_manager.validate_certificate(valid_certificate)

        assert "key_size" in result
        assert result["key_size"] >= 2048

    def test_validate_extracts_serial_number(
        self, certificate_manager, valid_certificate
    ):
        """Should extract serial number from certificate"""
        result = certificate_manager.validate_certificate(valid_certificate)

        assert "serial_number" in result
        assert len(result["serial_number"]) > 0


class TestCertificateGeneration:
    """Test self-signed certificate generation"""

    @pytest.fixture
    def certificate_manager(self):
        from app.sso.domain.services.certificate_manager import CertificateManager

        with tempfile.TemporaryDirectory() as tmpdir:
            yield CertificateManager(storage_path=tmpdir)

    def test_generate_certificate_returns_tuple(self, certificate_manager):
        """Should return tuple of certificate and private key"""
        cert_pem, key_pem = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com"
        )

        assert cert_pem.startswith("-----BEGIN CERTIFICATE-----")
        assert key_pem.startswith("-----BEGIN RSA PRIVATE KEY-----")

    def test_generate_certificate_with_organization(self, certificate_manager):
        """Should include organization in certificate"""
        cert_pem, _ = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com",
            organization="Test Organization",
        )

        result = certificate_manager.validate_certificate(cert_pem)
        assert "Test Organization" in result["subject"]

    def test_generate_certificate_validity(self, certificate_manager):
        """Should respect validity_days parameter"""
        cert_pem, _ = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com",
            validity_days=30,
        )

        result = certificate_manager.validate_certificate(cert_pem)
        assert result["days_until_expiry"] <= 30
        assert result["days_until_expiry"] >= 29

    def test_generate_certificate_key_size(self, certificate_manager):
        """Should respect key_size parameter"""
        cert_pem, _ = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com",
            key_size=4096,
        )

        result = certificate_manager.validate_certificate(cert_pem)
        assert result["key_size"] == 4096

    def test_generate_certificate_is_not_ca(self, certificate_manager):
        """Generated certificate should not be a CA"""
        cert_pem, _ = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com"
        )

        result = certificate_manager.validate_certificate(cert_pem)
        assert result["is_ca"] is False

    def test_generate_certificate_has_key_usage(self, certificate_manager):
        """Generated certificate should have proper key usage"""
        cert_pem, _ = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com"
        )

        result = certificate_manager.validate_certificate(cert_pem)
        assert "digital_signature" in result["key_usage"]
        assert "key_encipherment" in result["key_usage"]


class TestPublicKeyExtraction:
    """Test public key extraction from certificates"""

    @pytest.fixture
    def certificate_manager(self):
        from app.sso.domain.services.certificate_manager import CertificateManager

        with tempfile.TemporaryDirectory() as tmpdir:
            yield CertificateManager(storage_path=tmpdir)

    def test_extract_public_key(self, certificate_manager):
        """Should extract public key from certificate"""
        cert_pem, _ = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com"
        )

        public_key = certificate_manager.extract_public_key(cert_pem)

        assert public_key.startswith("-----BEGIN PUBLIC KEY-----")
        assert "-----END PUBLIC KEY-----" in public_key


class TestCertificateStorage:
    """Test certificate storage and retrieval"""

    @pytest.fixture
    def certificate_manager(self):
        from app.sso.domain.services.certificate_manager import CertificateManager

        with tempfile.TemporaryDirectory() as tmpdir:
            yield CertificateManager(storage_path=tmpdir)

    @pytest.fixture
    def valid_certificate(self, certificate_manager):
        cert_pem, _ = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com"
        )
        return cert_pem

    def test_store_certificate(self, certificate_manager, valid_certificate):
        """Should store certificate to filesystem"""
        path = certificate_manager.store_certificate(
            organization_id="org_123",
            certificate_pem=valid_certificate,
            certificate_type="idp",
        )

        assert os.path.exists(path)
        assert "org_123" in path
        assert "idp_" in path
        assert path.endswith(".crt")

    def test_load_certificate(self, certificate_manager, valid_certificate):
        """Should load most recent certificate"""
        certificate_manager.store_certificate(
            organization_id="org_456",
            certificate_pem=valid_certificate,
            certificate_type="sp",
        )

        loaded = certificate_manager.load_certificate(
            organization_id="org_456",
            certificate_type="sp",
        )

        assert loaded is not None
        assert loaded.strip() == valid_certificate.strip()

    def test_load_nonexistent_certificate(self, certificate_manager):
        """Should return None for nonexistent certificate"""
        loaded = certificate_manager.load_certificate(
            organization_id="nonexistent",
            certificate_type="idp",
        )

        assert loaded is None

    def test_store_invalid_certificate_fails(self, certificate_manager):
        """Should not store invalid certificate"""
        from app.sso.exceptions import ValidationError

        with pytest.raises(ValidationError):
            certificate_manager.store_certificate(
                organization_id="org_789",
                certificate_pem="invalid certificate",
                certificate_type="idp",
            )


class TestCertificateConversion:
    """Test certificate format conversion"""

    @pytest.fixture
    def certificate_manager(self):
        from app.sso.domain.services.certificate_manager import CertificateManager

        with tempfile.TemporaryDirectory() as tmpdir:
            yield CertificateManager(storage_path=tmpdir)

    @pytest.fixture
    def valid_certificate(self, certificate_manager):
        cert_pem, _ = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com"
        )
        return cert_pem

    def test_convert_pem_to_der(self, certificate_manager, valid_certificate):
        """Should convert PEM to DER format"""
        der_bytes = certificate_manager.convert_pem_to_der(valid_certificate)

        assert isinstance(der_bytes, bytes)
        assert len(der_bytes) > 0
        # DER format doesn't have the PEM headers
        assert b"-----BEGIN" not in der_bytes

    def test_convert_der_to_pem(self, certificate_manager, valid_certificate):
        """Should convert DER back to PEM format"""
        der_bytes = certificate_manager.convert_pem_to_der(valid_certificate)
        pem_converted = certificate_manager.convert_der_to_pem(der_bytes)

        assert pem_converted.startswith("-----BEGIN CERTIFICATE-----")
        # The certificates should be equivalent
        result_original = certificate_manager.validate_certificate(valid_certificate)
        result_converted = certificate_manager.validate_certificate(pem_converted)
        assert result_original["serial_number"] == result_converted["serial_number"]

    def test_roundtrip_conversion(self, certificate_manager, valid_certificate):
        """Should preserve certificate through PEM->DER->PEM conversion"""
        der_bytes = certificate_manager.convert_pem_to_der(valid_certificate)
        pem_converted = certificate_manager.convert_der_to_pem(der_bytes)

        original = certificate_manager.validate_certificate(valid_certificate)
        converted = certificate_manager.validate_certificate(pem_converted)

        assert original["serial_number"] == converted["serial_number"]
        assert original["subject"] == converted["subject"]


class TestCertificateParsing:
    """Test certificate parsing edge cases"""

    @pytest.fixture
    def certificate_manager(self):
        from app.sso.domain.services.certificate_manager import CertificateManager

        with tempfile.TemporaryDirectory() as tmpdir:
            yield CertificateManager(storage_path=tmpdir)

    def test_parse_certificate_without_headers(self, certificate_manager):
        """Should handle certificate without PEM headers"""
        cert_pem, _ = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com"
        )

        # Remove headers
        base64_only = cert_pem.replace("-----BEGIN CERTIFICATE-----", "")
        base64_only = base64_only.replace("-----END CERTIFICATE-----", "")
        base64_only = base64_only.strip()

        # Should still validate
        result = certificate_manager.validate_certificate(base64_only)
        assert result["valid"] is True

    def test_parse_certificate_with_whitespace(self, certificate_manager):
        """Should handle certificate with extra whitespace"""
        cert_pem, _ = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com"
        )

        # Add extra whitespace
        with_whitespace = "\n\n  " + cert_pem + "\n\n  "

        result = certificate_manager.validate_certificate(with_whitespace)
        assert result["valid"] is True


class TestStorageDirectory:
    """Test storage directory management"""

    def test_creates_storage_directory(self):
        """Should create storage directory if it doesn't exist"""
        from app.sso.domain.services.certificate_manager import CertificateManager

        with tempfile.TemporaryDirectory() as tmpdir:
            new_path = os.path.join(tmpdir, "new_subdir", "certs")

            # Directory shouldn't exist yet
            assert not os.path.exists(new_path)

            CertificateManager(storage_path=new_path)

            # Now it should exist
            assert os.path.exists(new_path)

    def test_uses_env_variable_default(self):
        """Should use CERT_STORAGE_PATH env variable"""
        from app.sso.domain.services.certificate_manager import CertificateManager

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"CERT_STORAGE_PATH": tmpdir}):
                manager = CertificateManager(storage_path=None)
                assert manager.storage_path == tmpdir


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def certificate_manager(self):
        from app.sso.domain.services.certificate_manager import CertificateManager

        with tempfile.TemporaryDirectory() as tmpdir:
            yield CertificateManager(storage_path=tmpdir)

    def test_small_key_size_warning(self, certificate_manager):
        """Should warn about small key sizes"""
        # Generate with 1024-bit key (too small)
        cert_pem, _ = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com",
            key_size=1024,  # Insecure
        )

        result = certificate_manager.validate_certificate(cert_pem)

        assert any("too small" in w for w in result["warnings"])

    def test_validate_certificate_info_extraction(self, certificate_manager):
        """Should extract all expected information"""
        cert_pem, _ = certificate_manager.generate_self_signed_certificate(
            common_name="test.example.com",
            organization="Test Org",
        )

        result = certificate_manager.validate_certificate(cert_pem)

        expected_fields = [
            "valid",
            "subject",
            "issuer",
            "serial_number",
            "not_before",
            "not_after",
            "is_ca",
            "key_usage",
            "key_size",
            "days_until_expiry",
            "warnings",
        ]

        for field in expected_fields:
            assert field in result, f"Missing field: {field}"
