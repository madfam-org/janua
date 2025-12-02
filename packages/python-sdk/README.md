# Janua Python SDK

Official Python SDK for the Janua Authentication and User Management Platform.

## Features

- 🔐 **Complete Authentication** - Sign up, sign in, password reset, email verification
- 👤 **User Management** - Create, update, delete, and manage user profiles
- 🏢 **Organizations** - Multi-tenant support with roles and permissions
- 🔑 **Multi-Factor Authentication** - TOTP, SMS, and backup codes
- 🎫 **Session Management** - Create, refresh, and revoke sessions
- 🌐 **OAuth Integration** - Support for Google, GitHub, Microsoft, and more
- 🔏 **Passkeys/WebAuthn** - Passwordless authentication support
- 🪝 **Webhooks** - Real-time event notifications
- 🛡️ **Enterprise Ready** - SAML SSO, SCIM provisioning, audit logs

## Installation

```bash
pip install janua
```

For async support:
```bash
pip install janua[async]
```

## Quick Start

```python
from janua import JanuaClient

# Initialize the client
client = JanuaClient(api_key="your_api_key")

# Sign up a new user
user = client.auth.sign_up(
    email="user@example.com",
    password="SecurePassword123!",
    first_name="John",
    last_name="Doe"
)

# Sign in
result = client.auth.sign_in(
    email="user@example.com",
    password="SecurePassword123!"
)
user = result["user"]
session = result["session"]
tokens = result["tokens"]

# Get current user
current_user = client.auth.get_current_user()

# Update user profile
updated_user = client.users.update(
    user_id=user.id,
    first_name="Jane",
    last_name="Smith"
)
```

## Configuration

### Environment Variables

```bash
export JANUA_API_KEY="your_api_key"
export JANUA_BASE_URL="https://api.janua.dev"  # Optional
export JANUA_ENVIRONMENT="production"  # Optional
```

### Custom Configuration

```python
from janua import JanuaClient

client = JanuaClient(
    api_key="your_api_key",
    base_url="https://staging.api.janua.dev",
    timeout=30.0,
    max_retries=3,
    environment="staging",
    debug=True
)
```

## Authentication

### Email/Password Authentication

```python
# Sign up
user = client.auth.sign_up(
    email="user@example.com",
    password="SecurePassword123!",
    metadata={"source": "mobile_app"}
)

# Sign in with remember me
result = client.auth.sign_in(
    email="user@example.com",
    password="SecurePassword123!",
    remember_me=True
)

# Request password reset
client.auth.request_password_reset("user@example.com")

# Reset password with token
client.auth.reset_password(
    token="reset_token_from_email",
    new_password="NewSecurePassword123!"
)

# Change password (authenticated user)
client.auth.change_password(
    current_password="OldPassword123!",
    new_password="NewPassword123!"
)
```

### OAuth Authentication

```python
from janua.types import OAuthProvider

# Get OAuth authorization URL
auth_url = client.auth.get_oauth_url(
    provider=OAuthProvider.GOOGLE,
    redirect_uri="https://yourapp.com/callback",
    scopes=["email", "profile"]
)

# Handle OAuth callback
result = client.auth.handle_oauth_callback(
    provider=OAuthProvider.GOOGLE,
    code="authorization_code_from_callback"
)

# Link OAuth account to existing user
client.auth.link_oauth_account(
    provider=OAuthProvider.GITHUB,
    access_token="github_access_token"
)

# Unlink OAuth account
client.auth.unlink_oauth_account(OAuthProvider.GITHUB)
```

## User Management

```python
# Get user by ID
user = client.users.get(user_id)

# Get user by email
user = client.users.get_by_email("user@example.com")

# List users with pagination
users = client.users.list(
    limit=20,
    offset=0,
    search="john",
    email_verified=True
)

# Update user
user = client.users.update(
    user_id=user_id,
    first_name="Updated",
    last_name="Name",
    phone_number="+1234567890"
)

# Update user email
user = client.users.update_email(
    user_id=user_id,
    new_email="newemail@example.com",
    require_verification=True
)

# Suspend/unsuspend user
client.users.suspend(user_id, reason="Terms violation")
client.users.unsuspend(user_id)

# Delete user
client.users.delete(user_id)
```

## Organizations

```python
from janua.types import OrganizationRole

# Create organization
org = client.organizations.create(
    name="Acme Corp",
    slug="acme-corp",
    description="Leading technology company"
)

# List user's organizations
orgs = client.organizations.list(user_id=user_id)

# Add member to organization
member = client.organizations.add_member(
    organization_id=org.id,
    user_id=user_id,
    role=OrganizationRole.ADMIN
)

# Update member role
client.organizations.update_member_role(
    organization_id=org.id,
    user_id=user_id,
    role=OrganizationRole.OWNER
)

# Create organization invite
invite = client.organizations.create_invite(
    organization_id=org.id,
    email="newmember@example.com",
    role=OrganizationRole.MEMBER,
    message="Welcome to our organization!"
)

# Accept invite
client.organizations.accept_invite(invite_token)
```

## Multi-Factor Authentication

```python
from janua.types import MFAMethod

# Enable TOTP (authenticator app)
totp_setup = client.mfa.setup_totp()
# Show QR code to user: totp_setup.qr_code_url
# Verify setup with code from authenticator
client.mfa.verify_totp(code="123456")

# Enable SMS MFA
sms_setup = client.mfa.setup_sms(phone_number="+1234567890")
client.mfa.verify_sms(code="123456")

# Generate backup codes
backup = client.mfa.generate_backup_codes(count=10)
print(f"Backup codes: {backup.codes}")

# Create MFA challenge for authentication
challenge = client.mfa.create_challenge(method=MFAMethod.TOTP)
# User enters code
result = client.mfa.verify_challenge(
    challenge_id=challenge.id,
    code="123456"
)

# Trust device for 30 days
client.mfa.trust_device(
    device_name="John's iPhone",
    duration_days=30
)
```

## Passkeys (WebAuthn)

```python
# Begin passkey registration
challenge = client.passkeys.begin_registration(
    display_name="John's MacBook"
)

# Complete registration with credential from browser
passkey = client.passkeys.complete_registration(
    challenge_id=challenge.id,
    credential=webauthn_credential_response  # From browser
)

# Begin passkey authentication
challenge = client.passkeys.begin_authentication(
    email="user@example.com"
)

# Complete authentication
result = client.passkeys.complete_authentication(
    challenge_id=challenge.id,
    credential=webauthn_credential_response  # From browser
)

# List user's passkeys
passkeys = client.passkeys.list()

# Delete passkey
client.passkeys.delete(passkey_id)
```

## Session Management

```python
# Get current session
session = client.sessions.get_current()

# List all sessions
sessions = client.sessions.list(
    user_id=user_id,
    active_only=True
)

# Refresh session
refreshed = client.sessions.refresh(session_id)

# Revoke session
client.sessions.revoke(session_id)

# Revoke all other sessions
client.sessions.revoke_other()

# Get session device info
device = client.sessions.get_device(session_id)

# Mark device as trusted
client.sessions.update_device(
    session_id=session_id,
    name="Work Laptop",
    trusted=True
)
```

## Webhooks

```python
from janua.types import WebhookEventType

# Create webhook endpoint
endpoint = client.webhooks.create_endpoint(
    url="https://yourapp.com/webhooks",
    events=[
        WebhookEventType.USER_CREATED,
        WebhookEventType.USER_SIGNED_IN,
        WebhookEventType.USER_UPDATED
    ],
    description="Production webhook endpoint"
)

# List endpoints
endpoints = client.webhooks.list_endpoints()

# Update endpoint
endpoint = client.webhooks.update_endpoint(
    endpoint_id=endpoint.id,
    events=[WebhookEventType.USER_CREATED],
    enabled=False
)

# Rotate signing secret
endpoint = client.webhooks.rotate_secret(endpoint.id)

# Test webhook
delivery = client.webhooks.test_endpoint(endpoint.id)

# Validate webhook signature (in your webhook handler)
from janua.utils import validate_webhook_signature

def webhook_handler(request):
    payload = request.body
    signature = request.headers["X-Janua-Signature"]
    secret = endpoint.signing_secret
    
    if validate_webhook_signature(payload, signature, secret):
        # Process webhook
        pass
    else:
        # Invalid signature
        return 401
```

## Error Handling

```python
from janua.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    NotFoundError,
    RateLimitError
)

try:
    user = client.auth.sign_in(
        email="user@example.com",
        password="wrong_password"
    )
except AuthenticationError as e:
    print(f"Authentication failed: {e.message}")
except ValidationError as e:
    print(f"Invalid input: {e.message}")
    print(f"Details: {e.details}")
except RateLimitError as e:
    print(f"Rate limited: {e.message}")
    retry_after = e.details.get("retry_after")
    print(f"Retry after {retry_after} seconds")
except NotFoundError as e:
    print(f"Resource not found: {e.message}")
```

## Async Support

```python
import asyncio
from janua import AsyncJanuaClient

async def main():
    async with AsyncJanuaClient(api_key="your_api_key") as client:
        # All methods are async
        user = await client.auth.sign_up(
            email="user@example.com",
            password="SecurePassword123!"
        )
        
        result = await client.auth.sign_in(
            email="user@example.com",
            password="SecurePassword123!"
        )

asyncio.run(main())
```

## Testing

```python
import pytest
from unittest.mock import Mock
from janua import JanuaClient

@pytest.fixture
def mock_client():
    client = JanuaClient(api_key="test_key")
    client.http = Mock()
    return client

def test_sign_up(mock_client):
    mock_response = Mock()
    mock_response.json.return_value = {
        "user": {
            "id": "user_123",
            "email": "test@example.com",
            "role": "user",
            "status": "active"
        }
    }
    mock_client.http.post.return_value = mock_response
    
    user = mock_client.auth.sign_up(
        email="test@example.com",
        password="TestPassword123!"
    )
    
    assert user.email == "test@example.com"
    assert user.id == "user_123"
```

## Advanced Usage

### Custom Headers

```python
client = JanuaClient(
    api_key="your_api_key",
    custom_headers={
        "X-Custom-Header": "value",
        "X-Request-ID": "unique_id"
    }
)
```

### Retry Configuration

```python
client = JanuaClient(
    api_key="your_api_key",
    max_retries=5,  # Maximum retry attempts
    timeout=60.0     # Request timeout in seconds
)
```

### Debug Mode

```python
client = JanuaClient(api_key="your_api_key", debug=True)
# Or enable/disable dynamically
client.enable_debug()
client.disable_debug()
```

### Health Check

```python
# Check API health
health = client.health_check()
print(f"API Status: {health['status']}")

# Get API version
version = client.get_api_version()
print(f"API Version: {version}")
```

## License

MIT

## Support

- Documentation: https://docs.janua.dev/sdks/python
- GitHub Issues: https://github.com/madfam-io/python-sdk/issues
- Email: support@janua.dev

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## Security

For security issues, please email security@janua.dev instead of using the issue tracker.