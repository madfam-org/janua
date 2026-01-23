# Enterprise Integration Guide

Comprehensive guide for integrating Janua with enterprise systems and third-party services.

## 🎯 Overview

This guide covers enterprise-grade integrations for organizations deploying Janua as their identity infrastructure. It includes SSO providers, SCIM 2.0 provisioning, enterprise directories, and third-party system integrations.

## 🏢 Enterprise SSO Integration

### Microsoft Azure AD / Entra ID

#### SAML 2.0 Configuration
```xml
<!-- Azure AD SAML Configuration -->
<EntityDescriptor entityID="https://api.janua.dev/sso/saml/metadata">
  <SPSSODescriptor
    AuthnRequestsSigned="true"
    protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">

    <KeyDescriptor use="signing">
      <ds:KeyInfo>
        <ds:X509Data>
          <ds:X509Certificate><!-- Certificate --></ds:X509Certificate>
        </ds:X509Data>
      </ds:KeyInfo>
    </KeyDescriptor>

    <AssertionConsumerService
      Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
      Location="https://api.janua.dev/sso/saml/acs"
      index="0" />
  </SPSSODescriptor>
</EntityDescriptor>
```

#### OIDC Configuration
```json
{
  "client_id": "your-azure-client-id",
  "client_secret": "your-azure-client-secret",
  "issuer": "https://login.microsoftonline.com/{tenant-id}/v2.0",
  "authorization_endpoint": "https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/authorize",
  "token_endpoint": "https://login.microsoftonline.com/{tenant-id}/oauth2/v2.0/token",
  "jwks_uri": "https://login.microsoftonline.com/{tenant-id}/discovery/v2.0/keys",
  "scopes": ["openid", "profile", "email"]
}
```

#### API Integration Example
```typescript
import { JanuaClient } from '@janua/typescript-sdk';

const janua = new JanuaClient({
  baseURL: 'https://api.janua.dev',
  apiKey: 'your-api-key'
});

// Configure Azure AD SSO
await janua.admin.sso.create({
  provider: 'azure_ad',
  oidc_issuer: 'https://login.microsoftonline.com/{tenant-id}/v2.0',
  oidc_client_id: 'your-client-id',
  oidc_client_secret: 'your-client-secret',
  jit_provisioning: true,
  default_role: 'member',
  attribute_mapping: {
    email: 'preferred_username',
    first_name: 'given_name',
    last_name: 'family_name',
    groups: 'groups'
  },
  allowed_domains: ['company.com']
});
```

### Okta Integration

#### SAML 2.0 Setup
```javascript
// Okta SAML Configuration
const oktaConfig = {
  provider: 'okta_saml',
  saml_sso_url: 'https://idp.example.com/app/company_janua_1/exk123456789/sso/saml',
  saml_entity_id: 'https://idp.example.com/app',
  saml_certificate: '-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----',
  attribute_mapping: {
    email: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name',
    first_name: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname',
    last_name: 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname',
    groups: 'http://schemas.microsoft.com/ws/2008/06/identity/claims/groups'
  }
};

await janua.admin.sso.create(oktaConfig);
```

### Google Workspace

#### OAuth 2.0 Configuration
```json
{
  "client_id": "123456789-abc123.apps.googleusercontent.com",
  "client_secret": "your-google-client-secret",
  "issuer": "https://accounts.google.com",
  "scopes": ["openid", "email", "profile"],
  "hosted_domain": "company.com"
}
```

## 👥 SCIM 2.0 User Provisioning

### Overview
SCIM (System for Cross-domain Identity Management) 2.0 enables automatic user provisioning from enterprise identity providers.

### Supported SCIM Operations
- **Create User**: Automatic user provisioning
- **Update User**: Profile synchronization
- **Delete User**: User deprovisioning
- **Create Group**: Group management
- **Update Group Membership**: Role assignments

### SCIM Endpoint Configuration
```http
Base URL: https://api.janua.dev/scim/v2
Authentication: Bearer {scim_token}
Content-Type: application/scim+json
```

### User Provisioning Example
```json
POST /scim/v2/Users
{
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
  "userName": "john.doe@company.com",
  "name": {
    "familyName": "Doe",
    "givenName": "John"
  },
  "emails": [{
    "primary": true,
    "value": "john.doe@company.com",
    "type": "work"
  }],
  "active": true,
  "groups": [
    {
      "value": "employees",
      "display": "Employees"
    }
  ]
}
```

### Group Management
```json
POST /scim/v2/Groups
{
  "schemas": ["urn:ietf:params:scim:schemas:core:2.0:Group"],
  "displayName": "Engineering Team",
  "members": [
    {
      "value": "user-id-123",
      "display": "John Doe"
    }
  ]
}
```

## 🗂️ Enterprise Directory Integration

### Active Directory / LDAP

#### Configuration
```yaml
ldap:
  host: ldap.company.com
  port: 636
  use_ssl: true
  bind_dn: "CN=janua-service,OU=Service Accounts,DC=company,DC=com"
  bind_password: "service-account-password"
  base_dn: "OU=Users,DC=company,DC=com"
  user_filter: "(&(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
  attributes:
    email: mail
    first_name: givenName
    last_name: sn
    username: sAMAccountName
    groups: memberOf
```

#### API Integration
```python
import asyncio
from janua import JanuaClient

async def sync_ldap_users():
    janua = JanuaClient(
        base_url="https://api.janua.dev",
        api_key="your-api-key"
    )

    # Configure LDAP connection
    await janua.admin.ldap.configure({
        "host": "ldap.company.com",
        "port": 636,
        "use_ssl": True,
        "bind_dn": "CN=janua-service,OU=Service Accounts,DC=company,DC=com",
        "bind_password": "service-account-password",
        "base_dn": "OU=Users,DC=company,DC=com"
    })

    # Sync users
    sync_result = await janua.admin.ldap.sync_users()
    print(f"Synced {sync_result['users_created']} users")
```

## 🔗 Third-Party System Integration

### Salesforce CRM

#### OAuth Configuration
```typescript
const salesforceConfig = {
  client_id: 'your-salesforce-connected-app-id',
  client_secret: 'your-salesforce-client-secret',
  redirect_uri: 'https://api.janua.dev/oauth/salesforce/callback',
  sandbox: false // Set to true for sandbox environments
};

// Configure Salesforce integration
await janua.admin.integrations.create({
  provider: 'salesforce',
  config: salesforceConfig,
  field_mapping: {
    'user.email': 'Email',
    'user.first_name': 'FirstName',
    'user.last_name': 'LastName',
    'organization.name': 'Account.Name'
  }
});
```

#### User Sync Example
```typescript
// Sync user data with Salesforce
await janua.admin.integrations.sync('salesforce', {
  direction: 'bidirectional',
  entities: ['users', 'organizations'],
  dry_run: false
});
```

### HubSpot Integration

```typescript
const hubspotConfig = {
  api_key: 'your-hubspot-api-key',
  portal_id: 'your-portal-id'
};

await janua.admin.integrations.create({
  provider: 'hubspot',
  config: hubspotConfig,
  webhooks: {
    contact_created: 'https://api.janua.dev/webhooks/hubspot/contact-created',
    contact_updated: 'https://api.janua.dev/webhooks/hubspot/contact-updated'
  }
});
```

### Slack Workspace Integration

```typescript
const slackConfig = {
  client_id: 'your-slack-app-client-id',
  client_secret: 'your-slack-app-client-secret',
  signing_secret: 'your-slack-signing-secret'
};

await janua.admin.integrations.create({
  provider: 'slack',
  config: slackConfig,
  scopes: ['users:read', 'users:read.email', 'team:read'],
  auto_provision: true
});
```

## 📊 Enterprise Analytics Integration

### Tableau

#### SAML SSO for Tableau
```xml
<!-- Tableau SAML Configuration -->
<EntityDescriptor entityID="tableau-server">
  <AssertionConsumerService
    Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
    Location="https://tableau.company.com/auth/saml/callback"
    index="0" />
</EntityDescriptor>
```

### Power BI

#### Azure AD Application Setup
```json
{
  "application_id": "power-bi-app-id",
  "tenant_id": "company-tenant-id",
  "scopes": [
    "https://analysis.windows.net/powerbi/api/Dataset.Read.All",
    "https://analysis.windows.net/powerbi/api/Report.Read.All"
  ]
}
```

## 🔐 Security & Compliance Integration

### CyberArk PAM Integration

```typescript
const cyberarkConfig = {
  base_url: 'https://cyberark.company.com',
  application_id: 'Janua_Identity_Platform',
  safe: 'Janua_Secrets',
  client_certificate: 'path/to/client.crt',
  client_key: 'path/to/client.key'
};

// Retrieve secrets from CyberArk
const secrets = await janua.admin.secrets.retrieve('cyberark', {
  object: 'Database_Password',
  safe: 'Janua_Secrets'
});
```

### Splunk SIEM Integration

```yaml
# Splunk Universal Forwarder Configuration
[monitor:///var/log/janua/audit.log]
index = security
sourcetype = janua_audit
host = janua-api

[monitor:///var/log/janua/auth.log]
index = security
sourcetype = janua_auth
host = janua-api
```

## 🚀 Deployment Automation

### Terraform Enterprise Integration

```hcl
# Configure Janua SSO for Terraform Enterprise
resource "janua_sso_configuration" "terraform_enterprise" {
  provider = "terraform_enterprise"

  saml_metadata_url = "https://terraform.company.com/saml/metadata"
  jit_provisioning  = true
  default_role      = "developer"

  attribute_mapping = {
    email      = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
    first_name = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname"
    last_name  = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"
    groups     = "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"
  }
}
```

### Jenkins CI/CD Integration

```groovy
// Jenkins Pipeline Integration
pipeline {
    agent any

    environment {
        JANUA_API_KEY = credentials('janua-api-key')
    }

    stages {
        stage('Authenticate') {
            steps {
                script {
                    def auth = sh(
                        script: "curl -H 'Authorization: Bearer ${JANUA_API_KEY}' https://api.janua.dev/auth/validate",
                        returnStdout: true
                    ).trim()

                    if (!auth.contains('"valid": true')) {
                        error('Authentication failed')
                    }
                }
            }
        }
    }
}
```

## 📱 Mobile Device Management

### Microsoft Intune Integration

```typescript
const intuneConfig = {
  tenant_id: 'company-tenant-id',
  client_id: 'intune-app-id',
  client_secret: 'intune-client-secret',
  compliance_policies: [
    'require_pin',
    'require_encryption',
    'block_jailbroken_devices'
  ]
};

await janua.admin.mdm.configure('intune', intuneConfig);
```

### VMware Workspace ONE

```json
{
  "server_url": "https://workspaceone.company.com",
  "api_key": "your-workspace-one-api-key",
  "username": "admin@company.com",
  "password": "admin-password",
  "tenant_code": "company"
}
```

## 🔄 Data Synchronization

### Real-time Sync Configuration

```typescript
// Configure real-time user synchronization
await janua.admin.sync.configure({
  providers: ['azure_ad', 'okta', 'salesforce'],
  frequency: 'real-time',
  conflict_resolution: 'source_priority',
  source_priority: ['azure_ad', 'okta', 'manual'],
  webhook_notifications: true
});
```

### Batch Sync Operations

```python
import asyncio
from janua import JanuaClient

async def daily_sync():
    janua = JanuaClient(api_key="your-api-key")

    # Sync users from all connected providers
    sync_results = await janua.admin.sync.run_batch({
        "providers": ["azure_ad", "okta", "ldap"],
        "entities": ["users", "groups"],
        "dry_run": False,
        "send_notification": True
    })

    print(f"Sync completed: {sync_results}")

# Schedule daily sync
if __name__ == "__main__":
    asyncio.run(daily_sync())
```

## 🎯 Custom Integration Development

### Webhook Development

```typescript
// Custom webhook handler
app.post('/webhooks/janua/user-created', async (req, res) => {
  const { user, organization, event_type } = req.body;

  // Verify webhook signature
  const signature = req.headers['x-janua-signature'];
  const isValid = janua.webhooks.verify(req.body, signature);

  if (!isValid) {
    return res.status(401).json({ error: 'Invalid signature' });
  }

  // Custom business logic
  switch (event_type) {
    case 'user.created':
      await provisionUserInCustomSystem(user);
      break;
    case 'user.updated':
      await updateUserInCustomSystem(user);
      break;
    case 'user.deleted':
      await deprovisionUserInCustomSystem(user);
      break;
  }

  res.status(200).json({ status: 'processed' });
});
```

### Custom SCIM Connector

```python
from janua.connectors import SCIMConnector

class CustomSystemConnector(SCIMConnector):
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        super().__init__()

    async def create_user(self, user_data):
        """Create user in custom system"""
        response = await self.http_client.post(
            f"{self.base_url}/api/users",
            json=user_data,
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.json()

    async def update_user(self, user_id, user_data):
        """Update user in custom system"""
        response = await self.http_client.patch(
            f"{self.base_url}/api/users/{user_id}",
            json=user_data,
            headers={"Authorization": f"Bearer {self.api_key}"}
        )
        return response.json()
```

## 📚 Integration Best Practices

### Security Considerations
- **Use secure credentials storage** (Azure Key Vault, AWS Secrets Manager)
- **Implement certificate pinning** for HTTPS connections
- **Validate all webhook signatures** to prevent spoofing
- **Use least privilege access** for service accounts
- **Enable audit logging** for all integration activities

### Performance Optimization
- **Implement caching** for frequently accessed data
- **Use async operations** for bulk synchronization
- **Implement rate limiting** to respect API limits
- **Use connection pooling** for database connections
- **Monitor integration performance** with metrics

### Error Handling
- **Implement retry logic** with exponential backoff
- **Log all integration errors** with context
- **Set up alerting** for integration failures
- **Provide fallback mechanisms** for critical operations
- **Document troubleshooting procedures**

## 📞 Support & Troubleshooting

### Common Integration Issues
1. **SSL Certificate Issues**: Verify certificate validity and trust chain
2. **Authentication Failures**: Check credentials and token expiration
3. **Rate Limiting**: Implement proper backoff strategies
4. **Data Mapping Errors**: Validate attribute mappings and data formats

### Getting Help
- **Documentation**: [https://docs.janua.dev/integrations](https://docs.janua.dev/integrations)
- **Support Portal**: [https://support.janua.dev](https://support.janua.dev)
- **Community Forum**: [https://community.janua.dev](https://community.janua.dev)
- **Enterprise Support**: [enterprise@janua.dev](mailto:enterprise@janua.dev)

---

*For custom integration development or enterprise support, contact our integration team at [integrations@janua.dev](mailto:integrations@janua.dev)*