# Enterprise SSO/SAML Setup Guide

> **Complete guide to configuring SAML 2.0 Single Sign-On for enterprise identity providers**

## Overview

Janua API provides enterprise-grade SSO/SAML 2.0 integration that works with all major identity providers including Okta, Azure AD, Google Workspace, AWS SSO, PingIdentity, and OneLogin. This guide covers complete setup and configuration.

## 🏢 SSO Features

### SAML 2.0 Support
- **Full SAML 2.0 compliance** with IDP and SP-initiated flows
- **Metadata exchange** for automated configuration
- **Attribute mapping** for user profile synchronization
- **JIT (Just-In-Time) provisioning** for automatic user creation
- **Single Logout (SLO)** support for security
- **Digital signatures** and encryption support

### OIDC Support
- **OpenID Connect 1.0** compliant implementation
- **Discovery endpoint** for automatic configuration
- **PKCE support** for enhanced security
- **Multiple scopes** (openid, profile, email, groups)
- **Refresh token** handling

### Enterprise Features
- **Multi-provider support** per organization
- **Domain-based routing** to appropriate IDPs
- **Role mapping** from SAML assertions
- **Custom attribute mapping** for user profiles
- **Audit logging** for compliance
- **Failover** to local authentication

## 🚀 Quick Start

### 1. Create SSO Configuration

```bash
curl -X POST "https://api.janua.dev/api/v1/sso/configurations" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "organization_id": "org_123",
    "provider": "SAML",
    "saml_metadata_url": "https://idp.example.com/app/abc123def456/sso/saml/metadata",
    "jit_provisioning": true,
    "default_role": "member",
    "attribute_mapping": {
      "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",`
      "first_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",`
      "last_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"
    },
    "allowed_domains": ["yourcompany.com"]
  }'
```

### 2. Get Janua SAML Metadata

```bash
curl "https://api.janua.dev/api/v1/sso/metadata/org_123"
```

### 3. Test SSO Configuration

```bash
curl -X POST "https://api.janua.dev/api/v1/sso/test" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "organization_id": "org_123",
    "test_user_email": "test@yourcompany.com"
  }'
```

## 🔧 Identity Provider Setup

### Okta Setup

#### 1. Create SAML Application in Okta
1. Go to **Admin Console** → **Applications** → **Create App Integration**
2. Select **SAML 2.0**
3. Application name: "Janua Authentication"

#### 2. Configure SAML Settings
```yaml
Single Sign-On URL: https://api.janua.dev/api/v1/sso/saml/acs
Audience URI (SP Entity ID): https://api.janua.dev/sp/metadata/org_123
Default RelayState: (leave blank)
Name ID format: EmailAddress
Application username: Email
```

#### 3. Attribute Statements
```yaml
email: user.email
first_name: user.firstName
last_name: user.lastName
groups: user.groups (optional)
```

#### 4. Get Okta Metadata
```
https://idp.example.com/app/abc123def456/sso/saml/metadata
```

### Azure AD Setup

#### 1. Create Enterprise Application
1. Go to **Azure AD** → **Enterprise Applications** → **New application**
2. Select **Create your own application**
3. Name: "Janua Authentication"
4. Choose **Integrate any other application**

#### 2. Configure Single Sign-On
```yaml
Identifier (Entity ID): https://api.janua.dev/sp/metadata/org_123
Reply URL (Assertion Consumer Service URL): https://api.janua.dev/api/v1/sso/saml/acs
Sign on URL: https://yourapp.janua.dev/auth/sso
Logout URL: https://api.janua.dev/api/v1/sso/saml/slo
```

#### 3. User Attributes & Claims
```yaml
`http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress: user.mail`
`http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname: user.givenname`
`http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname: user.surname`
`http://schemas.microsoft.com/ws/2008/06/identity/claims/groups: user.groups`
```

#### 4. Download Metadata
Go to **Single sign-on** → **SAML Signing Certificate** → Download **Federation Metadata XML**

### Google Workspace Setup

#### 1. Create SAML App
1. Go to **Google Admin Console** → **Apps** → **Web and mobile apps**
2. Click **Add App** → **Add custom SAML app**
3. App name: "Janua Authentication"

#### 2. Configure SAML Details
```yaml
ACS URL: https://api.janua.dev/api/v1/sso/saml/acs
Entity ID: https://api.janua.dev/sp/metadata/org_123
Start URL: https://yourapp.janua.dev/auth/sso
Name ID: Basic Information > Primary email
Name ID format: EMAIL
```

#### 3. Attribute Mapping
```yaml
email: Basic Information > Primary email
first_name: Basic Information > First name
last_name: Basic Information > Last name
```

#### 4. Get Google Metadata
Download from **Google IDP metadata** link in the SAML app details.

## 💻 Implementation Examples

### Frontend SSO Integration

```javascript
class SSOIntegration {
  constructor(apiClient) {
    this.api = apiClient;
  }

  // Initiate SSO flow
  async initiateSSO(organizationId, email = null) {
    try {
      const response = await this.api.post('/api/v1/sso/initiate', {
        organization_id: organizationId,
        email: email, // Optional: for domain-based routing
        relay_state: window.location.href // Where to redirect after SSO
      });

      // Redirect to identity provider
      window.location.href = response.data.redirect_url;
    } catch (error) {
      throw new Error(`SSO initiation failed: ${error.response?.data?.detail}`);
    }
  }

  // Handle SSO callback
  async handleSSOCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    const error = urlParams.get('error');

    if (error) {
      throw new Error(`SSO authentication failed: ${error}`);
    }

    if (token) {
      // Store authentication tokens
      localStorage.setItem('access_token', token);

      // Get user profile
      const user = await this.api.get('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${token}` }
      });

      return user.data;
    }

    throw new Error('No authentication token received');
  }

  // Check if SSO is available for domain
  async checkSSOAvailability(email) {
    try {
      const domain = email.split('@')[1];
      const response = await this.api.get(`/api/v1/sso/discovery/${domain}`);
      return response.data.available;
    } catch (error) {
      return false;
    }
  }
}
```

### React SSO Component

```jsx
import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

const SSOAuthentication = ({ organizationId }) => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const ssoIntegration = new SSOIntegration(apiClient);

  // Handle SSO callback on page load
  useEffect(() => {
    const token = searchParams.get('token');
    const error = searchParams.get('error');

    if (token || error) {
      handleSSOCallback();
    }
  }, [searchParams]);

  const handleSSOCallback = async () => {
    setLoading(true);
    try {
      const user = await ssoIntegration.handleSSOCallback();
      navigate('/dashboard');
    } catch (error) {
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSSOLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await ssoIntegration.initiateSSO(organizationId, email);
    } catch (error) {
      setError(error.message);
      setLoading(false);
    }
  };

  const checkSSO = async (email) => {
    if (email.includes('@')) {
      const available = await ssoIntegration.checkSSOAvailability(email);
      return available;
    }
    return false;
  };

  return (
    <div className="sso-authentication">
      <h2>🏢 Enterprise Sign In</h2>

      <form onSubmit={handleSSOLogin}>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Enter your work email"
          required
          disabled={loading}
        />

        <button type="submit" disabled={loading}>
          {loading ? 'Redirecting...' : 'Sign In with SSO'}
        </button>

        {error && <div className="error">{error}</div>}
      </form>

      <div className="alternative-auth">
        <p>Or <a href="/auth/signin">sign in with password</a></p>
      </div>
    </div>
  );
};
```

### Vue.js SSO Component

```vue
<template>
  <div class="sso-authentication">
    <h2>🏢 Enterprise Sign In</h2>

    <form @submit.prevent="handleSSOLogin">
      <input
        v-model="email"
        type="email"
        placeholder="Enter your work email"
        required
        :disabled="loading"
      />

      <button type="submit" :disabled="loading">
        {{ loading ? 'Redirecting...' : 'Sign In with SSO' }}
      </button>

      <div v-if="error" class="error">{{ error }}</div>
    </form>

    <div class="alternative-auth">
      <p>Or <a href="/auth/signin">sign in with password</a></p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const props = defineProps({
  organizationId: String
});

const email = ref('');
const loading = ref(false);
const error = ref('');
const route = useRoute();
const router = useRouter();

const ssoIntegration = new SSOIntegration(apiClient);

onMounted(() => {
  const token = route.query.token;
  const ssoError = route.query.error;

  if (token || ssoError) {
    handleSSOCallback();
  }
});

const handleSSOCallback = async () => {
  loading.value = true;
  try {
    await ssoIntegration.handleSSOCallback();
    router.push('/dashboard');
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
};

const handleSSOLogin = async () => {
  loading.value = true;
  error.value = '';

  try {
    await ssoIntegration.initiateSSO(props.organizationId, email.value);
  } catch (err) {
    error.value = err.message;
    loading.value = false;
  }
};
</script>
```

## 🔧 Backend SSO Configuration

### Custom Attribute Mapping

```python
from app.services.sso_service import SSOService

class CustomSSOHandler:
    def __init__(self):
        self.sso_service = SSOService()

    async def create_advanced_sso_config(
        self,
        organization_id: str,
        provider_config: dict
    ):
        """Create SSO configuration with advanced attribute mapping"""

        # Advanced attribute mapping
        attribute_mapping = {
            # Standard attributes
            "email": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",`
            "first_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",`
            "last_name": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname",`

            # Custom attributes
            "employee_id": "https://example.com/claims/employeeid",
            "department": "https://example.com/claims/department",
            "manager_email": "https://example.com/claims/manager",
            "cost_center": "https://example.com/claims/costcenter",

            # Role mapping
            "groups": "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups",`
            "roles": "https://example.com/claims/roles"
        }

        # Role mapping rules
        role_mapping = {
            "Admin": "owner",
            "IT-Admin": "admin",
            "Manager": "admin",
            "Employee": "member",
            "Contractor": "viewer"
        }

        config = {
            "organization_id": organization_id,
            "provider": "SAML",
            "saml_metadata_url": provider_config["metadata_url"],
            "jit_provisioning": True,
            "default_role": "member",
            "attribute_mapping": attribute_mapping,
            "role_mapping": role_mapping,
            "allowed_domains": provider_config["allowed_domains"],

            # Advanced settings
            "require_signed_assertion": True,
            "require_encrypted_assertion": False,
            "sign_auth_request": True,
            "name_id_format": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"
        }

        return await self.sso_service.create_configuration(config)
```

### Custom User Provisioning

```python
from app.models import User, Organization
from app.services.rbac_service import RBACService

class SSOUserProvisioner:
    def __init__(self):
        self.rbac_service = RBACService()

    async def provision_user_from_saml(
        self,
        saml_attributes: dict,
        organization: Organization,
        db: AsyncSession
    ):
        """Custom user provisioning from SAML attributes"""

        # Extract user info
        email = saml_attributes.get("email")
        first_name = saml_attributes.get("first_name", "")
        last_name = saml_attributes.get("last_name", "")
        employee_id = saml_attributes.get("employee_id")
        department = saml_attributes.get("department")
        groups = saml_attributes.get("groups", [])

        # Check if user exists
        user = await self.get_user_by_email(email, db)

        if not user:
            # Create new user
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                email_verified=True,  # SSO implies email verification
                sso_provider="SAML",
                employee_id=employee_id,
                department=department,
                created_via_sso=True
            )
            db.add(user)
            await db.flush()

        # Update user attributes
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        user.department = department or user.department
        user.last_sso_login = datetime.utcnow()

        # Handle role assignment based on groups
        await self.assign_roles_from_groups(
            user, organization, groups, db
        )

        await db.commit()
        return user

    async def assign_roles_from_groups(
        self,
        user: User,
        organization: Organization,
        groups: list,
        db: AsyncSession
    ):
        """Assign roles based on SAML group membership"""

        # Group to role mapping
        group_role_mapping = {
            "Janua-Admins": "owner",
            "IT-Admins": "admin",
            "Managers": "admin",
            "Employees": "member",
            "Contractors": "viewer"
        }

        # Determine highest role from groups
        assigned_role = "member"  # default

        for group in groups:
            if group in group_role_mapping:
                role = group_role_mapping[group]
                if self.is_higher_role(role, assigned_role):
                    assigned_role = role

        # Assign role in organization
        await self.rbac_service.assign_user_role(
            user.id, organization.id, assigned_role, db
        )

    def is_higher_role(self, role1: str, role2: str) -> bool:
        """Check if role1 is higher than role2"""
        role_hierarchy = ["viewer", "member", "admin", "owner"]
        return role_hierarchy.index(role1) > role_hierarchy.index(role2)
```

## 🛡️ Security Best Practices

### SAML Security Configuration

```python
from app.core.saml_security import SAMLSecurityConfig

class SecureSAMLSetup:
    def __init__(self):
        self.security_config = SAMLSecurityConfig()

    def get_production_security_settings(self):
        """Production-ready SAML security settings"""
        return {
            # Signature requirements
            "authnRequestsSigned": True,
            "wantAssertionsSigned": True,
            "wantAssertionsEncrypted": False,  # Enable if supported by IDP

            # Validation settings
            "wantNameId": True,
            "wantNameIdEncrypted": False,
            "requestedAuthnContext": ["urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport"],

            # Timing
            "clockSkew": 300,  # 5 minutes tolerance
            "lifetimeMaxDuration": 3600,  # 1 hour max session

            # Certificate validation
            "certificateValidation": True,
            "allowSelfSignedCertificates": False,

            # Replay protection
            "replayAttackProtection": True,
            "messageIdTimeout": 3600,

            # URL validation
            "destinationValidation": True,
            "audienceValidation": True
        }

    async def rotate_sp_certificate(self, organization_id: str):
        """Rotate service provider certificate for security"""

        # Generate new certificate pair
        new_cert, new_private_key = self.security_config.generate_certificate_pair()

        # Update configuration
        await self.update_sp_certificate(
            organization_id, new_cert, new_private_key
        )

        # Notify administrators
        await self.notify_certificate_rotation(organization_id)
```

### SSO Audit Logging

```python
from app.models import AuditLog
import json

class SSOAuditLogger:
    async def log_sso_event(
        self,
        event_type: str,
        user_id: str = None,
        organization_id: str = None,
        details: dict = None,
        ip_address: str = None,
        user_agent: str = None,
        db: AsyncSession = None
    ):
        """Log SSO events for compliance and security"""

        audit_entry = AuditLog(
            event_type=f"sso_{event_type}",
            user_id=user_id,
            organization_id=organization_id,
            resource_type="sso_authentication",
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=datetime.utcnow()
        )

        db.add(audit_entry)
        await db.commit()

    # Usage examples
    async def log_sso_login_success(self, user, request, db):
        await self.log_sso_event(
            "login_success",
            user_id=user.id,
            organization_id=user.current_organization_id,
            details={
                "provider": "SAML",
                "email": user.email,
                "login_method": "sso"
            },
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            db=db
        )

    async def log_sso_configuration_change(self, admin_user, org_id, changes, db):
        await self.log_sso_event(
            "configuration_updated",
            user_id=admin_user.id,
            organization_id=org_id,
            details={
                "changes": changes,
                "admin_email": admin_user.email
            },
            db=db
        )
```

## 📊 Testing & Validation

### SSO Configuration Testing

```python
class SSOTestSuite:
    def __init__(self, sso_service):
        self.sso_service = sso_service

    async def test_sso_configuration(self, organization_id: str):
        """Comprehensive SSO configuration testing"""

        test_results = {
            "metadata_validation": False,
            "certificate_validation": False,
            "endpoint_accessibility": False,
            "attribute_mapping": False,
            "test_authentication": False
        }

        try:
            # Test 1: Validate metadata
            config = await self.sso_service.get_configuration(organization_id)
            metadata_valid = await self.validate_metadata(config)
            test_results["metadata_validation"] = metadata_valid

            # Test 2: Validate certificates
            cert_valid = await self.validate_certificates(config)
            test_results["certificate_validation"] = cert_valid

            # Test 3: Test endpoint accessibility
            endpoints_accessible = await self.test_endpoints(config)
            test_results["endpoint_accessibility"] = endpoints_accessible

            # Test 4: Test attribute mapping
            mapping_valid = await self.test_attribute_mapping(config)
            test_results["attribute_mapping"] = mapping_valid

            # Test 5: End-to-end authentication test
            auth_test_passed = await self.test_authentication_flow(config)
            test_results["test_authentication"] = auth_test_passed

        except Exception as e:
            logger.error(f"SSO testing failed: {e}")

        return test_results

    async def validate_metadata(self, config):
        """Validate IDP metadata"""
        try:
            if config.saml_metadata_url:
                # Fetch and parse metadata
                metadata = await self.fetch_metadata(config.saml_metadata_url)
                return self.parse_saml_metadata(metadata)
            return True
        except Exception:
            return False

    async def test_authentication_flow(self, config):
        """Test complete authentication flow"""
        try:
            # Create test SAML request
            auth_request = await self.create_test_auth_request(config)

            # This would typically require IDP cooperation
            # In practice, this is often a manual test
            return True
        except Exception:
            return False
```

### Frontend SSO Testing

```javascript
// SSO Testing Utilities
class SSOTester {
  constructor(apiClient) {
    this.api = apiClient;
  }

  async testSSOConfiguration(organizationId) {
    try {
      const response = await this.api.post('/api/v1/sso/test', {
        organization_id: organizationId,
        test_type: 'configuration'
      });

      return response.data;
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || error.message
      };
    }
  }

  async validateSSODomain(email) {
    const domain = email.split('@')[1];

    try {
      const response = await this.api.get(`/api/v1/sso/discovery/${domain}`);
      return response.data;
    } catch (error) {
      return { available: false };
    }
  }

  // Test SSO flow without full authentication
  async testSSOFlow(organizationId) {
    try {
      // Initiate test flow
      const response = await this.api.post('/api/v1/sso/test-flow', {
        organization_id: organizationId,
        dry_run: true
      });

      return {
        success: true,
        redirect_url: response.data.redirect_url,
        test_mode: true
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || error.message
      };
    }
  }
}

// Usage in testing
const ssoTester = new SSOTester(apiClient);

// Test configuration
const configTest = await ssoTester.testSSOConfiguration('org_123');
console.log('Configuration test:', configTest);

// Test domain discovery
const domainTest = await ssoTester.validateSSODomain('user@company.com');
console.log('Domain test:', domainTest);

// Test flow
const flowTest = await ssoTester.testSSOFlow('org_123');
console.log('Flow test:', flowTest);
```

## 🔍 Troubleshooting

### Common SAML Issues

**Issue: "Invalid SAML Response"**
```python
def debug_saml_response():
    """Debug SAML response issues"""

    # Check common issues
    checks = {
        "clock_skew": "Check time synchronization between SP and IDP",
        "audience_mismatch": "Verify Entity ID matches configuration",
        "signature_validation": "Check certificate configuration",
        "attribute_mapping": "Verify attribute names match assertions",
        "assertion_expiry": "Check assertion timestamps and validity"
    }

    # Log detailed SAML response for debugging
    logger.debug(f"SAML Response validation checks: {checks}")

    return checks
```

**Issue: "User not found after SSO"**
```python
def debug_user_provisioning():
    """Debug JIT provisioning issues"""

    debug_steps = [
        "1. Check if JIT provisioning is enabled",
        "2. Verify email attribute is present in SAML assertion",
        "3. Check domain restrictions in SSO configuration",
        "4. Verify user creation permissions",
        "5. Check for email conflicts with existing users"
    ]

    return debug_steps
```

**Issue: "SSO redirect loop"**
```python
def debug_redirect_loop():
    """Debug SSO redirect loop issues"""

    solutions = {
        "check_relay_state": "Ensure RelayState is properly configured",
        "verify_acs_url": "Check ACS URL matches IDP configuration",
        "session_handling": "Verify session cookie configuration",
        "domain_mismatch": "Check domain configuration in both SP and IDP"
    }

    return solutions
```

## 📚 Advanced Configuration

### Multi-Provider Setup

```python
class MultiProviderSSOManager:
    async def setup_multiple_providers(self, organization_id: str):
        """Setup multiple SSO providers for one organization"""

        providers = [
            {
                "provider": "SAML",
                "name": "Okta",
                "saml_metadata_url": "https://idp.example.com/app/abc/sso/saml/metadata",
                "priority": 1,
                "domains": ["company.com", "subsidiary.com"]
            },
            {
                "provider": "OIDC",
                "name": "Azure AD",
                "oidc_issuer": "https://login.example.com/tenant/v2.0",
                "oidc_client_id": "client-id",
                "priority": 2,
                "domains": ["partner.com"]
            }
        ]

        for provider_config in providers:
            await self.create_sso_configuration(
                organization_id, provider_config
            )

    async def route_user_to_provider(self, email: str, organization_id: str):
        """Route user to appropriate SSO provider based on domain"""

        domain = email.split('@')[1]

        # Find provider for domain
        provider = await self.find_provider_for_domain(domain, organization_id)

        if provider:
            return await self.initiate_sso_with_provider(provider, email)
        else:
            # Fallback to default provider or local auth
            return await self.fallback_authentication(email)
```

## 📖 API Reference

### Complete SSO Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sso/configurations` | Create SSO configuration |
| GET | `/sso/configurations/{org_id}` | Get SSO configuration |
| PUT | `/sso/configurations/{org_id}` | Update SSO configuration |
| DELETE | `/sso/configurations/{org_id}` | Delete SSO configuration |
| POST | `/sso/initiate` | Initiate SSO authentication |
| POST | `/sso/saml/acs` | SAML assertion consumer service |
| POST | `/sso/saml/slo` | SAML single logout |
| GET | `/sso/metadata/{org_id}` | Get SP metadata |
| POST | `/sso/test` | Test SSO configuration |
| GET | `/sso/discovery/{domain}` | SSO provider discovery |

For complete API documentation, see:
- [Enterprise API Reference](../api/enterprise.md)
- [Authentication Flows](../api/authentication.md#sso-integration)

## 🎯 Next Steps

1. **Advanced Role Mapping**: Implement complex role hierarchies
2. **SCIM Integration**: Connect SSO with user provisioning
3. **Risk-Based Authentication**: Add adaptive security
4. **Mobile SSO**: Implement mobile-friendly SSO flows
5. **Federation**: Setup cross-organization SSO

---

**🏢 [Enterprise RBAC Guide](enterprise-rbac-setup-guide.md)** • **👨‍💼 [SCIM Documentation](../api/scim.md)** • **🔐 [Security Best Practices](../security/README.md)**