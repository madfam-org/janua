"""
Certificate Management Service for SSO

Handles X.509 certificates for SAML, certificate validation, storage, and rotation.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
from pathlib import Path
import os

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from ...exceptions import ValidationError


class CertificateManager:
    """Manages X.509 certificates for SSO"""

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize certificate manager

        Args:
            storage_path: Directory path for storing certificates
        """
        self.storage_path = storage_path or os.getenv("CERT_STORAGE_PATH", "/var/janua/certs")
        self._ensure_storage_directory()

    def _ensure_storage_directory(self):
        """Ensure certificate storage directory exists"""
        Path(self.storage_path).mkdir(parents=True, exist_ok=True)

    def validate_certificate(
        self, certificate_pem: str, check_expiry: bool = True, min_validity_days: int = 30
    ) -> Dict[str, Any]:
        """
        Validate X.509 certificate

        Args:
            certificate_pem: PEM-encoded certificate
            check_expiry: Whether to check certificate expiry
            min_validity_days: Minimum days until expiry

        Returns:
            Certificate information and validation status

        Raises:
            ValidationError: If certificate is invalid
        """
        try:
            # Parse certificate
            cert = self._parse_certificate(certificate_pem)

            # Extract information
            subject = cert.subject
            issuer = cert.issuer
            not_before = cert.not_valid_before_utc
            not_after = cert.not_valid_after_utc

            # Current time
            now = datetime.now(not_before.tzinfo)

            # Validation checks
            validation_result = {
                "valid": True,
                "subject": self._format_name(subject),
                "issuer": self._format_name(issuer),
                "serial_number": str(cert.serial_number),
                "not_before": not_before.isoformat(),
                "not_after": not_after.isoformat(),
                "is_ca": self._is_ca_certificate(cert),
                "key_usage": self._extract_key_usage(cert),
                "warnings": [],
            }

            # Check if certificate is not yet valid
            if now < not_before:
                validation_result["valid"] = False
                validation_result["warnings"].append(
                    f"Certificate not yet valid (valid from {not_before.isoformat()})"
                )

            # Check if certificate has expired
            if check_expiry and now > not_after:
                validation_result["valid"] = False
                validation_result["warnings"].append(
                    f"Certificate has expired (expired on {not_after.isoformat()})"
                )

            # Check minimum validity period
            if check_expiry:
                days_until_expiry = (not_after - now).days
                validation_result["days_until_expiry"] = days_until_expiry

                if days_until_expiry < min_validity_days:
                    validation_result["warnings"].append(
                        f"Certificate expires in {days_until_expiry} days (minimum: {min_validity_days})"
                    )

            # Verify signature algorithm
            sig_algorithm = cert.signature_algorithm_oid._name
            if sig_algorithm in ["sha1WithRSAEncryption", "sha1"]:
                validation_result["warnings"].append(
                    "Certificate uses SHA-1 (deprecated, use SHA-256 or higher)"
                )

            # Check key size
            public_key = cert.public_key()
            if hasattr(public_key, "key_size"):
                key_size = public_key.key_size
                validation_result["key_size"] = key_size

                if key_size < 2048:
                    validation_result["warnings"].append(
                        f"Key size {key_size} is too small (minimum: 2048 bits)"
                    )

            return validation_result

        except Exception as e:
            raise ValidationError(f"Invalid certificate: {str(e)}")

    def extract_public_key(self, certificate_pem: str) -> str:
        """
        Extract public key from certificate

        Args:
            certificate_pem: PEM-encoded certificate

        Returns:
            PEM-encoded public key
        """
        cert = self._parse_certificate(certificate_pem)
        public_key = cert.public_key()

        pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        return pem.decode("utf-8")

    def generate_self_signed_certificate(
        self,
        common_name: str,
        organization: Optional[str] = None,
        validity_days: int = 365,
        key_size: int = 2048,
    ) -> Tuple[str, str]:
        """
        Generate self-signed X.509 certificate

        Args:
            common_name: Common Name (CN) for the certificate
            organization: Organization (O) for the certificate
            validity_days: Certificate validity in days
            key_size: RSA key size in bits

        Returns:
            Tuple of (certificate_pem, private_key_pem)
        """
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=key_size, backend=default_backend()
        )

        # Build subject and issuer (same for self-signed)
        subject_attrs = [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
        if organization:
            subject_attrs.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization))

        subject = issuer = x509.Name(subject_attrs)

        # Build certificate
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow() + timedelta(days=validity_days))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=True,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .sign(private_key, hashes.SHA256(), backend=default_backend())
        )

        # Serialize certificate
        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")

        # Serialize private key
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        return cert_pem, key_pem

    def store_certificate(
        self, organization_id: str, certificate_pem: str, certificate_type: str = "idp"
    ) -> str:
        """
        Store certificate to filesystem

        Args:
            organization_id: Organization identifier
            certificate_pem: PEM-encoded certificate
            certificate_type: Type of certificate (idp, sp, signing, encryption)

        Returns:
            Path to stored certificate file
        """
        # Validate certificate first
        validation = self.validate_certificate(certificate_pem)
        if not validation["valid"]:
            raise ValidationError(f"Cannot store invalid certificate: {validation['warnings']}")

        # Create organization directory
        org_dir = Path(self.storage_path) / organization_id
        org_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{certificate_type}_{timestamp}.crt"
        cert_path = org_dir / filename

        # Write certificate
        with open(cert_path, "w") as f:
            f.write(certificate_pem)

        return str(cert_path)

    def load_certificate(
        self, organization_id: str, certificate_type: str = "idp"
    ) -> Optional[str]:
        """
        Load most recent certificate for organization

        Args:
            organization_id: Organization identifier
            certificate_type: Type of certificate to load

        Returns:
            PEM-encoded certificate or None if not found
        """
        org_dir = Path(self.storage_path) / organization_id
        if not org_dir.exists():
            return None

        # Find most recent certificate of the specified type
        certs = sorted(org_dir.glob(f"{certificate_type}_*.crt"), reverse=True)
        if not certs:
            return None

        # Read and return certificate
        with open(certs[0], "r") as f:
            return f.read()

    def convert_der_to_pem(self, der_bytes: bytes) -> str:
        """
        Convert DER-encoded certificate to PEM format

        Args:
            der_bytes: DER-encoded certificate bytes

        Returns:
            PEM-encoded certificate
        """
        cert = x509.load_der_x509_certificate(der_bytes, default_backend())
        return cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")

    def convert_pem_to_der(self, certificate_pem: str) -> bytes:
        """
        Convert PEM-encoded certificate to DER format

        Args:
            certificate_pem: PEM-encoded certificate

        Returns:
            DER-encoded certificate bytes
        """
        cert = self._parse_certificate(certificate_pem)
        return cert.public_bytes(serialization.Encoding.DER)

    def _parse_certificate(self, certificate_pem: str) -> x509.Certificate:
        """Parse PEM-encoded certificate"""
        try:
            # Clean up PEM string
            cert_pem = certificate_pem.strip()

            # Handle base64-only certificates (missing headers)
            if not cert_pem.startswith("-----BEGIN CERTIFICATE-----"):
                cert_pem = (
                    "-----BEGIN CERTIFICATE-----\n" + cert_pem + "\n-----END CERTIFICATE-----"
                )

            return x509.load_pem_x509_certificate(cert_pem.encode("utf-8"), default_backend())
        except Exception as e:
            raise ValidationError(f"Failed to parse certificate: {str(e)}")

    def _format_name(self, name: x509.Name) -> str:
        """Format X.509 name as string"""
        parts = []
        for attr in name:
            parts.append(f"{attr.oid._name}={attr.value}")
        return ", ".join(parts)

    def _is_ca_certificate(self, cert: x509.Certificate) -> bool:
        """Check if certificate is a CA certificate"""
        try:
            basic_constraints = cert.extensions.get_extension_for_oid(
                ExtensionOID.BASIC_CONSTRAINTS
            )
            return basic_constraints.value.ca
        except x509.ExtensionNotFound:
            return False

    def _extract_key_usage(self, cert: x509.Certificate) -> list[str]:
        """Extract key usage extensions from certificate"""
        try:
            key_usage = cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value

            usages = []
            if key_usage.digital_signature:
                usages.append("digital_signature")
            if key_usage.key_encipherment:
                usages.append("key_encipherment")
            if key_usage.data_encipherment:
                usages.append("data_encipherment")
            if key_usage.key_agreement:
                usages.append("key_agreement")
            if key_usage.key_cert_sign:
                usages.append("key_cert_sign")
            if key_usage.crl_sign:
                usages.append("crl_sign")

            return usages
        except x509.ExtensionNotFound:
            return []
