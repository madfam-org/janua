"""
SAML Metadata Manager

Handles SAML metadata generation and parsing for SP and IdP metadata exchange.
Supports both SP-initiated and IdP-initiated flows with certificate embedding.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom

# Use defusedxml for secure XML parsing to prevent XML bomb attacks
import defusedxml.ElementTree as DefusedET

from app.sso.domain.services.certificate_manager import CertificateManager


class MetadataManager:
    """
    SAML metadata generation and parsing service.

    Handles:
    - SP metadata generation with certificate embedding
    - IdP metadata parsing and validation
    - Endpoint discovery from metadata
    - Certificate extraction from metadata
    """

    # SAML metadata XML namespaces
    NAMESPACES = {
        'md': 'urn:oasis:names:tc:SAML:2.0:metadata',
        'ds': 'http://www.w3.org/2000/09/xmldsig#',
        'saml': 'urn:oasis:names:tc:SAML:2.0:assertion',
    }

    def __init__(self, certificate_manager: Optional[CertificateManager] = None):
        """
        Initialize metadata manager.

        Args:
            certificate_manager: Certificate manager for certificate operations
        """
        self.certificate_manager = certificate_manager or CertificateManager()

    def generate_sp_metadata(
        self,
        entity_id: str,
        acs_url: str,
        sls_url: Optional[str] = None,
        organization_name: Optional[str] = None,
        contact_email: Optional[str] = None,
        certificate_pem: Optional[str] = None,
        want_assertions_signed: bool = True,
        authn_requests_signed: bool = True,
        validity_hours: int = 24 * 365  # 1 year default
    ) -> str:
        """
        Generate SP metadata XML.

        Args:
            entity_id: Unique identifier for SP (usually base URL)
            acs_url: Assertion Consumer Service URL
            sls_url: Single Logout Service URL (optional)
            organization_name: Organization name for metadata
            contact_email: Technical contact email
            certificate_pem: X.509 certificate for signing/encryption
            want_assertions_signed: Require signed assertions
            authn_requests_signed: Sign authentication requests
            validity_hours: Metadata validity period

        Returns:
            SAML metadata XML string
        """
        # Create root element
        root = ET.Element('md:EntityDescriptor', {
            'xmlns:md': self.NAMESPACES['md'],
            'xmlns:ds': self.NAMESPACES['ds'],
            'entityID': entity_id,
            'validUntil': (datetime.utcnow() + timedelta(hours=validity_hours)).isoformat() + 'Z'
        })

        # Create SPSSODescriptor
        sp_sso = ET.SubElement(root, 'md:SPSSODescriptor', {
            'AuthnRequestsSigned': str(authn_requests_signed).lower(),
            'WantAssertionsSigned': str(want_assertions_signed).lower(),
            'protocolSupportEnumeration': 'urn:oasis:names:tc:SAML:2.0:protocol'
        })

        # Add certificate if provided
        if certificate_pem:
            self._add_key_descriptor(sp_sso, certificate_pem, use='signing')
            self._add_key_descriptor(sp_sso, certificate_pem, use='encryption')

        # Add Single Logout Service if URL provided
        if sls_url:
            ET.SubElement(sp_sso, 'md:SingleLogoutService', {
                'Binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect',
                'Location': sls_url
            })

        # Add NameID formats
        for name_id_format in [
            'urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress',
            'urn:oasis:names:tc:SAML:2.0:nameid-format:persistent',
            'urn:oasis:names:tc:SAML:2.0:nameid-format:transient'
        ]:
            name_id = ET.SubElement(sp_sso, 'md:NameIDFormat')
            name_id.text = name_id_format

        # Add Assertion Consumer Service
        ET.SubElement(sp_sso, 'md:AssertionConsumerService', {
            'Binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST',
            'Location': acs_url,
            'index': '0',
            'isDefault': 'true'
        })

        # Add organization information if provided
        if organization_name:
            org = ET.SubElement(root, 'md:Organization')
            org_name = ET.SubElement(org, 'md:OrganizationName')
            org_name.set('{http://www.w3.org/XML/1998/namespace}lang', 'en')
            org_name.text = organization_name

            org_display = ET.SubElement(org, 'md:OrganizationDisplayName')
            org_display.set('{http://www.w3.org/XML/1998/namespace}lang', 'en')
            org_display.text = organization_name

            org_url = ET.SubElement(org, 'md:OrganizationURL')
            org_url.set('{http://www.w3.org/XML/1998/namespace}lang', 'en')
            org_url.text = entity_id

        # Add contact information if provided
        if contact_email:
            contact = ET.SubElement(root, 'md:ContactPerson', {
                'contactType': 'technical'
            })
            email = ET.SubElement(contact, 'md:EmailAddress')
            email.text = f'mailto:{contact_email}'

        # Convert to formatted XML string
        return self._prettify_xml(root)

    def parse_idp_metadata(self, metadata_xml: str) -> Dict[str, Any]:
        """
        Parse IdP metadata XML.

        Args:
            metadata_xml: SAML metadata XML string

        Returns:
            Parsed metadata dictionary with:
            - entity_id: IdP entity ID
            - sso_url: Single Sign-On service URL
            - slo_url: Single Logout service URL (if available)
            - certificates: List of X.509 certificates
            - name_id_formats: Supported NameID formats

        Raises:
            ValueError: If metadata is invalid
        """
        try:
            # Parse XML using defusedxml to prevent XML bomb attacks
            root = DefusedET.fromstring(metadata_xml)

            # Extract entity ID
            entity_id = root.get('entityID')
            if not entity_id:
                raise ValueError("Missing entityID in metadata")

            # Find IDPSSODescriptor
            idp_sso = root.find('.//md:IDPSSODescriptor', self.NAMESPACES)
            if idp_sso is None:
                raise ValueError("No IDPSSODescriptor found in metadata")

            # Extract SSO URL
            sso_service = idp_sso.find(
                './/md:SingleSignOnService[@Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"]',
                self.NAMESPACES
            )
            if sso_service is None:
                # Try HTTP-POST binding as fallback
                sso_service = idp_sso.find(
                    './/md:SingleSignOnService[@Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"]',
                    self.NAMESPACES
                )

            if sso_service is None:
                raise ValueError("No SingleSignOnService found in metadata")

            sso_url = sso_service.get('Location')
            if not sso_url:
                raise ValueError("Missing Location in SingleSignOnService")

            # Extract SLO URL (optional)
            slo_url = None
            slo_service = idp_sso.find(
                './/md:SingleLogoutService[@Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"]',
                self.NAMESPACES
            )
            if slo_service is not None:
                slo_url = slo_service.get('Location')

            # Extract certificates
            certificates = []
            key_descriptors = idp_sso.findall('.//md:KeyDescriptor', self.NAMESPACES)
            for key_desc in key_descriptors:
                cert_elem = key_desc.find('.//ds:X509Certificate', self.NAMESPACES)
                if cert_elem is not None and cert_elem.text:
                    # Clean and format certificate
                    cert_data = cert_elem.text.strip().replace('\n', '').replace(' ', '')
                    cert_pem = self._format_certificate_pem(cert_data)

                    # Validate certificate
                    validation = self.certificate_manager.validate_certificate(
                        cert_pem,
                        check_expiry=True
                    )

                    certificates.append({
                        'pem': cert_pem,
                        'use': key_desc.get('use', 'signing'),
                        'validation': validation
                    })

            # Extract NameID formats
            name_id_formats = []
            for name_id_elem in idp_sso.findall('.//md:NameIDFormat', self.NAMESPACES):
                if name_id_elem.text:
                    name_id_formats.append(name_id_elem.text.strip())

            return {
                'entity_id': entity_id,
                'sso_url': sso_url,
                'slo_url': slo_url,
                'certificates': certificates,
                'name_id_formats': name_id_formats,
                'valid': True
            }

        except DefusedET.ParseError as e:
            raise ValueError(f"Invalid XML: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to parse metadata: {str(e)}")

    def validate_metadata(
        self,
        metadata_xml: str,
        metadata_type: str = 'idp'
    ) -> Dict[str, Any]:
        """
        Validate SAML metadata.

        Args:
            metadata_xml: SAML metadata XML string
            metadata_type: Type of metadata ('idp' or 'sp')

        Returns:
            Validation result with warnings and errors
        """
        result = {
            'valid': True,
            'warnings': [],
            'errors': []
        }

        try:
            # Parse XML using defusedxml to prevent XML bomb attacks
            root = DefusedET.fromstring(metadata_xml)

            # Check entity ID
            entity_id = root.get('entityID')
            if not entity_id:
                result['errors'].append("Missing entityID")
                result['valid'] = False
            elif not entity_id.startswith('http'):
                result['warnings'].append("entityID should be a URL")

            # Check validUntil
            valid_until = root.get('validUntil')
            if valid_until:
                try:
                    expiry = datetime.fromisoformat(valid_until.replace('Z', '+00:00'))
                    if expiry < datetime.utcnow():
                        result['errors'].append("Metadata has expired")
                        result['valid'] = False
                    elif (expiry - datetime.utcnow()).days < 30:
                        result['warnings'].append("Metadata expires in less than 30 days")
                except ValueError:
                    result['warnings'].append("Invalid validUntil format")

            # Type-specific validation
            if metadata_type == 'idp':
                parsed = self.parse_idp_metadata(metadata_xml)

                # Check for certificates
                if not parsed.get('certificates'):
                    result['warnings'].append("No certificates found in metadata")
                else:
                    # Check certificate validity
                    for cert in parsed['certificates']:
                        if not cert['validation']['valid']:
                            result['errors'].append(f"Invalid certificate: {cert['validation'].get('error')}")
                            result['valid'] = False
                        elif cert['validation'].get('warnings'):
                            result['warnings'].extend(cert['validation']['warnings'])

        except ValueError as e:
            result['errors'].append(str(e))
            result['valid'] = False
        except Exception as e:
            result['errors'].append(f"Validation error: {str(e)}")
            result['valid'] = False

        return result

    def _add_key_descriptor(
        self,
        parent: ET.Element,
        certificate_pem: str,
        use: str = 'signing'
    ) -> None:
        """Add KeyDescriptor element with certificate."""
        key_desc = ET.SubElement(parent, 'md:KeyDescriptor', {'use': use})
        key_info = ET.SubElement(key_desc, 'ds:KeyInfo')
        x509_data = ET.SubElement(key_info, 'ds:X509Data')
        x509_cert = ET.SubElement(x509_data, 'ds:X509Certificate')

        # Extract certificate data (remove headers and newlines)
        cert_data = certificate_pem.replace('-----BEGIN CERTIFICATE-----', '')
        cert_data = cert_data.replace('-----END CERTIFICATE-----', '')
        cert_data = cert_data.strip().replace('\n', '')

        x509_cert.text = cert_data

    def _format_certificate_pem(self, cert_data: str) -> str:
        """Format certificate data as PEM."""
        # Remove any whitespace
        cert_data = cert_data.strip().replace('\n', '').replace(' ', '')

        # Add PEM headers
        pem = '-----BEGIN CERTIFICATE-----\n'

        # Split into 64-character lines
        for i in range(0, len(cert_data), 64):
            pem += cert_data[i:i+64] + '\n'

        pem += '-----END CERTIFICATE-----\n'

        return pem

    def _prettify_xml(self, elem: ET.Element) -> str:
        """Convert XML element to formatted string."""
        rough_string = ET.tostring(elem, encoding='unicode')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent='  ', encoding='utf-8').decode('utf-8')
