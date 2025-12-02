# Janua Go SDK

Official Go SDK for the Janua Identity Platform.

## Installation

```bash
go get github.com/madfam-io/go-sdk
```

## Quick Start

```go
package main

import (
    "context"
    "log"
    
    janua "github.com/madfam-io/go-sdk/client"
)

func main() {
    // Initialize client
    client := janua.New(janua.Config{
        BaseURL: "https://api.janua.dev",
        APIKey:  "your-api-key",
    })
    
    ctx := context.Background()
    
    // Sign in
    auth, err := client.SignIn(ctx, "user@example.com", "password")
    if err != nil {
        log.Fatal(err)
    }
    
    // Get user information
    user, err := client.GetUser(ctx)
    if err != nil {
        log.Fatal(err)
    }
    
    log.Printf("Signed in as: %s", user.Email)
}
```

## Features

- 🔐 **Authentication**: Sign in, sign up, sign out
- 👤 **User Management**: Get and update user profiles
- 🔑 **Session Management**: List and revoke sessions
- 🛡️ **MFA Support**: Enable, verify, and disable MFA
- 🏢 **Organizations**: Multi-tenancy support
- 🔄 **Token Management**: Automatic token refresh
- ⚡ **WebAuthn/Passkeys**: Passwordless authentication
- 📝 **Audit Logs**: Track security events

## API Reference

### Client Initialization

```go
client := janua.New(janua.Config{
    BaseURL:    "https://api.janua.dev",  // Optional, defaults to production
    APIKey:     "your-api-key",            // Required for API access
    HTTPClient: customHTTPClient,          // Optional custom HTTP client
    Timeout:    30 * time.Second,          // Optional request timeout
})
```

### Authentication

#### Sign Up
```go
resp, err := client.SignUp(ctx, &models.SignUpRequest{
    Email:    "user@example.com",
    Password: "SecurePassword123!",
    Name:     "John Doe",
})
```

#### Sign In
```go
resp, err := client.SignIn(ctx, "user@example.com", "password")
```

#### Sign Out
```go
err := client.SignOut(ctx)
```

### User Management

#### Get Current User
```go
user, err := client.GetUser(ctx)
```

#### Update User
```go
name := "New Name"
user, err := client.UpdateUser(ctx, &models.UserUpdate{
    Name: &name,
})
```

### Session Management

#### List Sessions
```go
sessions, err := client.ListSessions(ctx)
```

#### Revoke Session
```go
err := client.RevokeSession(ctx, sessionID)
```

### Multi-Factor Authentication

#### Enable MFA
```go
setup, err := client.EnableMFA(ctx)
// setup.QRCode contains the QR code for authenticator apps
// setup.RecoveryCodes contains backup recovery codes
```

#### Verify MFA Code
```go
err := client.VerifyMFA(ctx, "123456")
```

#### Disable MFA
```go
err := client.DisableMFA(ctx, "123456")
```

## Error Handling

The SDK provides structured error responses:

```go
auth, err := client.SignIn(ctx, email, password)
if err != nil {
    if apiErr, ok := err.(*models.APIError); ok {
        // Handle API error
        log.Printf("API Error [%s]: %s", apiErr.Code, apiErr.Message)
    } else {
        // Handle other errors
        log.Printf("Error: %v", err)
    }
}
```

## Examples

See the [examples](./examples) directory for complete working examples:

- [Basic Authentication](./examples/basic/main.go)
- [MFA Setup](./examples/mfa/main.go)
- [Session Management](./examples/sessions/main.go)
- [Organization Management](./examples/organizations/main.go)

## Contributing

We welcome contributions! Please see our [Contributing Guide](../../CONTRIBUTING.md) for details.

## License

This SDK is licensed under the AGPL-3.0 License. See [LICENSE](../../LICENSE) for details.