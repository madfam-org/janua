# Janua Go SDK

[![Go Reference](https://pkg.go.dev/badge/github.com/madfam-org/janua/packages/go-sdk.svg)](https://pkg.go.dev/github.com/madfam-org/janua/packages/go-sdk)
[![Go Version](https://img.shields.io/badge/Go-1.21+-00ADD8.svg)](https://go.dev/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

Official Go SDK for the Janua Identity Platform. This SDK provides a complete, type-safe interface for user authentication, organization management, MFA, OAuth, passkeys, and administrative operations.

## Features

- **Complete Authentication** - Sign up, sign in, password reset, email verification
- **User Management** - Profile management, session handling, bulk operations
- **Organization Management** - Multi-tenancy with roles, members, and invitations
- **Multi-Factor Authentication** - TOTP setup, verification, and backup codes
- **OAuth Integration** - Google, GitHub, Microsoft, Discord, Twitter, and more
- **Passkey Support** - WebAuthn/FIDO2 passwordless authentication
- **Session Management** - List, revoke, and manage user sessions
- **Role-Based Access Control** - Custom roles with granular permissions
- **Type-Safe** - Full Go type safety with comprehensive struct definitions
- **Context Support** - All operations support `context.Context` for cancellation
- **Configurable HTTP Client** - Custom timeouts, retries, and transport options

## Installation

```bash
go get github.com/madfam-org/janua/packages/go-sdk
```

## Quick Start

### Basic Setup

```go
package main

import (
    "context"
    "log"
    "time"

    janua "github.com/madfam-org/janua/packages/go-sdk/janua"
)

func main() {
    // Create client with configuration
    client := janua.NewClient(janua.Config{
        BaseURL:    "https://api.janua.dev",
        APIKey:     "your-api-key",
        Timeout:    30 * time.Second,
    })

    ctx := context.Background()

    // Sign in a user
    auth, err := client.Auth.SignIn(ctx, &janua.SignInRequest{
        Email:    "user@example.com",
        Password: "securepassword123",
    })
    if err != nil {
        log.Fatal(err)
    }

    log.Printf("Signed in as: %s", auth.User.Email)
    log.Printf("Access token: %s", auth.Token.AccessToken)
}
```

### Authentication Flow

```go
package main

import (
    "context"
    "log"

    janua "github.com/madfam-org/janua/packages/go-sdk/janua"
)

func main() {
    client := janua.NewClient(janua.Config{
        BaseURL: "https://api.janua.dev",
    })

    ctx := context.Background()

    // 1. Sign up a new user
    signUpResp, err := client.Auth.SignUp(ctx, &janua.SignUpRequest{
        Email:     "newuser@example.com",
        Password:  "SecurePassword123!",
        FirstName: "John",
        LastName:  "Doe",
    })
    if err != nil {
        log.Fatal(err)
    }
    log.Printf("User created: %s", signUpResp.User.ID)

    // 2. Sign in
    signInResp, err := client.Auth.SignIn(ctx, &janua.SignInRequest{
        Email:    "newuser@example.com",
        Password: "SecurePassword123!",
    })
    if err != nil {
        log.Fatal(err)
    }

    // 3. Check if MFA is required
    if signInResp.MFA != nil {
        log.Printf("MFA required. Challenge ID: %s", signInResp.MFA.ChallengeID)
        log.Printf("Available methods: %v", signInResp.MFA.Methods)

        // Verify MFA code
        mfaResp, err := client.Auth.VerifyMFA(ctx, &janua.MFAVerifyRequest{
            ChallengeID: signInResp.MFA.ChallengeID,
            Code:        "123456", // From authenticator app
            Method:      "totp",
        })
        if err != nil {
            log.Fatal(err)
        }
        signInResp = mfaResp
    }

    // 4. Use the access token for authenticated requests
    log.Printf("Access token: %s", signInResp.Token.AccessToken)
    log.Printf("Refresh token: %s", signInResp.Token.RefreshToken)
}
```

## Configuration

The SDK supports various configuration options:

```go
import (
    "net/http"
    "time"

    janua "github.com/madfam-org/janua/packages/go-sdk/janua"
)

// Full configuration example
client := janua.NewClient(janua.Config{
    // Required
    BaseURL: "https://api.janua.dev",

    // Authentication (choose one)
    APIKey:      "your-api-key",           // For server-to-server
    AccessToken: "user-access-token",      // For authenticated user requests

    // Optional settings
    Timeout:    30 * time.Second,          // Request timeout (default: 30s)
    RetryCount: 3,                         // Number of retries (default: 3)
    RetryWait:  1 * time.Second,           // Wait between retries (default: 1s)

    // Custom HTTP client (optional)
    HTTPClient: &http.Client{
        Timeout: 60 * time.Second,
        Transport: &http.Transport{
            MaxIdleConns:        100,
            MaxIdleConnsPerHost: 10,
            IdleConnTimeout:     90 * time.Second,
        },
    },

    // Debug mode (optional)
    Debug: false,
})
```

### Environment-Based Configuration

```go
import (
    "os"

    janua "github.com/madfam-org/janua/packages/go-sdk/janua"
)

func NewClientFromEnv() *janua.Client {
    return janua.NewClient(janua.Config{
        BaseURL: os.Getenv("JANUA_API_URL"),
        APIKey:  os.Getenv("JANUA_API_KEY"),
    })
}
```

## API Reference

### Auth Service

The Auth service handles all authentication operations.

#### Sign Up

```go
resp, err := client.Auth.SignUp(ctx, &janua.SignUpRequest{
    Email:     "user@example.com",
    Password:  "SecurePassword123!",
    FirstName: "John",
    LastName:  "Doe",
    Phone:     "+1234567890",           // Optional
    Metadata: map[string]interface{}{   // Optional custom metadata
        "source": "mobile_app",
    },
})
```

#### Sign In

```go
// Email/password authentication
resp, err := client.Auth.SignIn(ctx, &janua.SignInRequest{
    Email:    "user@example.com",
    Password: "password123",
})

// Phone/OTP authentication
resp, err := client.Auth.SignIn(ctx, &janua.SignInRequest{
    Phone: "+1234567890",
    OTP:   "123456",
})
```

#### Sign Out

```go
err := client.Auth.SignOut(ctx, refreshToken)
```

#### Token Refresh

```go
newToken, err := client.Auth.RefreshToken(ctx, refreshToken)
if err != nil {
    log.Fatal("Token refresh failed:", err)
}
log.Printf("New access token: %s", newToken.AccessToken)
```

#### Email Verification

```go
// Verify email with token from email link
err := client.Auth.VerifyEmail(ctx, verificationToken)
```

#### Password Management

```go
// Request password reset (sends email)
err := client.Auth.RequestPasswordReset(ctx, "user@example.com")

// Reset password using token from email
err := client.Auth.ResetPassword(ctx, resetToken, "NewSecurePassword123!")

// Change password (authenticated user)
err := client.Auth.ChangePassword(ctx, "currentPassword", "newPassword")
```

#### Multi-Factor Authentication

```go
// Enable MFA
setup, err := client.Auth.EnableMFA(ctx, "totp")
if err != nil {
    log.Fatal(err)
}
log.Printf("Secret: %s", setup.Secret)
log.Printf("QR Code: %s", setup.QRCode)        // Base64 encoded QR code
log.Printf("Backup codes: %v", setup.BackupCodes)

// Verify MFA code during sign-in
resp, err := client.Auth.VerifyMFA(ctx, &janua.MFAVerifyRequest{
    ChallengeID: mfaChallenge.ChallengeID,
    Code:        "123456",
    Method:      "totp", // or "backup_code"
})

// Disable MFA
err := client.Auth.DisableMFA(ctx, "currentPassword")
```

#### OAuth Authentication

```go
// Get OAuth authorization URL
authURL, err := client.Auth.GetOAuthURL(ctx, &janua.OAuthRequest{
    Provider:    "google",
    RedirectURI: "https://myapp.com/auth/callback",
    State:       "random-state-string",
    Scopes:      []string{"email", "profile"},
})
// Redirect user to authURL

// Handle OAuth callback
resp, err := client.Auth.HandleOAuthCallback(ctx, code, state)
if err != nil {
    log.Fatal(err)
}
log.Printf("User authenticated: %s", resp.User.Email)
```

#### Passkey Authentication (WebAuthn/FIDO2)

```go
// Start passkey registration
options, err := client.Auth.StartPasskeyRegistration(ctx, &janua.PasskeyRegistrationRequest{
    DisplayName: "My Security Key",
})
// Use options with WebAuthn API in browser/app

// Complete passkey registration
credential, err := client.Auth.CompletePasskeyRegistration(ctx, credentialFromWebAuthn)

// Start passkey authentication
authOptions, err := client.Auth.StartPasskeyAuthentication(ctx)
// Use authOptions with WebAuthn API

// Complete passkey authentication
resp, err := client.Auth.CompletePasskeyAuthentication(ctx, assertionFromWebAuthn)
```

### Users Service

The Users service handles user management operations.

#### Get User Information

```go
// Get current authenticated user
user, err := client.Users.GetCurrentUser(ctx)

// Get user by ID
user, err := client.Users.GetUser(ctx, "user-id-123")

// Get user by email
user, err := client.Users.GetUserByEmail(ctx, "user@example.com")
```

#### List and Search Users

```go
// List users with pagination
users, err := client.Users.ListUsers(ctx, &janua.ListOptions{
    Page:    1,
    PerPage: 20,
    Sort:    "created_at",
    Order:   "desc",
})
log.Printf("Total users: %d", users.Total)
for _, user := range users.Items {
    log.Printf("User: %s (%s)", user.Email, user.ID)
}

// Search users
results, err := client.Users.SearchUsers(ctx, "john", &janua.ListOptions{
    Page:    1,
    PerPage: 10,
})
```

#### Update User

```go
// Update current user
user, err := client.Users.UpdateCurrentUser(ctx, &janua.UpdateUserRequest{
    FirstName: "Jane",
    LastName:  "Smith",
    Phone:     "+1987654321",
    Metadata: map[string]interface{}{
        "preferences": map[string]bool{
            "notifications": true,
        },
    },
})

// Update any user (admin)
user, err := client.Users.UpdateUser(ctx, "user-id", &janua.UpdateUserRequest{
    FirstName: "Updated",
})
```

#### User Administration

```go
// Block user
err := client.Users.BlockUser(ctx, "user-id")

// Unblock user
err := client.Users.UnblockUser(ctx, "user-id")

// Delete user
err := client.Users.DeleteUser(ctx, "user-id")

// Bulk invite users
users, err := client.Users.BulkInviteUsers(ctx, &janua.BulkInviteRequest{
    Emails: []string{"user1@example.com", "user2@example.com"},
    RoleID: "role-id",
    OrgID:  "org-id",
})
```

#### Role Management

```go
// Get user roles
roles, err := client.Users.GetUserRoles(ctx, "user-id")

// Assign role
err := client.Users.AssignRole(ctx, "user-id", "role-id")

// Remove role
err := client.Users.RemoveRole(ctx, "user-id", "role-id")
```

#### Session Management

```go
// Get user's organizations
orgs, err := client.Users.GetUserOrganizations(ctx, "user-id")

// Get active sessions
sessions, err := client.Users.GetUserSessions(ctx, "user-id")
for _, session := range sessions {
    log.Printf("Session: %s, IP: %s, Last Active: %s",
        session.ID, session.IPAddress, session.LastActiveAt)
}

// Revoke specific session
err := client.Users.RevokeUserSession(ctx, "user-id", "session-id")

// Revoke all sessions (force logout everywhere)
err := client.Users.RevokeAllUserSessions(ctx, "user-id")
```

### Organizations Service

The Organizations service handles multi-tenancy operations.

#### Organization Management

```go
// Create organization
org, err := client.Organizations.CreateOrganization(ctx, &janua.CreateOrganizationRequest{
    Name:        "Acme Corporation",
    Slug:        "acme-corp",              // Optional, auto-generated if not provided
    Description: "Enterprise software solutions",
    Logo:        "https://example.com/logo.png",
    Metadata: map[string]interface{}{
        "industry": "technology",
    },
    Settings: map[string]interface{}{
        "require_mfa": true,
    },
})

// Get organization by ID
org, err := client.Organizations.GetOrganization(ctx, "org-id")

// Get organization by slug
org, err := client.Organizations.GetOrganizationBySlug(ctx, "acme-corp")

// List organizations
orgs, err := client.Organizations.ListOrganizations(ctx, &janua.ListOptions{
    Page:    1,
    PerPage: 10,
    Search:  "acme",
})

// Update organization
org, err := client.Organizations.UpdateOrganization(ctx, "org-id", &janua.UpdateOrganizationRequest{
    Name:        "Acme Corp International",
    Description: "Updated description",
})

// Delete organization
err := client.Organizations.DeleteOrganization(ctx, "org-id")
```

#### Member Management

```go
// Get organization members
members, err := client.Organizations.GetOrganizationMembers(ctx, "org-id", &janua.ListOptions{
    Page:    1,
    PerPage: 50,
})
for _, member := range members.Items {
    log.Printf("Member: %s, Role: %s", member.User.Email, member.Role)
}

// Add member to organization
member, err := client.Organizations.AddOrganizationMember(ctx, "org-id", &janua.AddOrganizationMemberRequest{
    Email: "newmember@example.com",
    Role:  "member",
    Roles: []string{"developer", "viewer"},
})

// Update member role
member, err := client.Organizations.UpdateOrganizationMember(ctx, "org-id", "user-id", &janua.UpdateOrganizationMemberRequest{
    Role:  "admin",
    Roles: []string{"admin", "developer"},
})

// Remove member
err := client.Organizations.RemoveOrganizationMember(ctx, "org-id", "user-id")
```

#### Invitation Management

```go
// Create invitation
invite, err := client.Organizations.CreateOrganizationInvite(ctx, "org-id", &janua.CreateInviteRequest{
    Email: "invited@example.com",
    Role:  "member",
    Roles: []string{"developer"},
})
log.Printf("Invitation created: %s, Expires: %s", invite.ID, invite.ExpiresAt)

// List pending invitations
invites, err := client.Organizations.ListOrganizationInvites(ctx, "org-id")

// Revoke invitation
err := client.Organizations.RevokeOrganizationInvite(ctx, "org-id", "invite-id")

// Accept invitation (from invited user)
org, err := client.Organizations.AcceptOrganizationInvite(ctx, inviteToken)
```

#### Role Management

```go
// Get organization roles
roles, err := client.Organizations.GetOrganizationRoles(ctx, "org-id")
for _, role := range roles {
    log.Printf("Role: %s, Permissions: %v", role.Name, role.Permissions)
}

// Create custom role
role, err := client.Organizations.CreateOrganizationRole(ctx, "org-id", &janua.CreateOrganizationRoleRequest{
    Name:        "Project Manager",
    Description: "Can manage projects and team members",
    Permissions: []string{
        "projects:read",
        "projects:write",
        "members:read",
        "members:invite",
    },
})

// Update role
role, err := client.Organizations.UpdateOrganizationRole(ctx, "org-id", "role-id", &janua.CreateOrganizationRoleRequest{
    Name: "Senior Project Manager",
    Permissions: []string{
        "projects:read",
        "projects:write",
        "projects:delete",
        "members:read",
        "members:invite",
        "members:remove",
    },
})

// Delete role
err := client.Organizations.DeleteOrganizationRole(ctx, "org-id", "role-id")
```

## Error Handling

The SDK provides structured error responses with detailed information:

```go
import (
    "errors"
    "log"

    janua "github.com/madfam-org/janua/packages/go-sdk/janua"
)

resp, err := client.Auth.SignIn(ctx, &janua.SignInRequest{
    Email:    "user@example.com",
    Password: "wrongpassword",
})
if err != nil {
    // Check for specific API error
    var apiErr *janua.APIError
    if errors.As(err, &apiErr) {
        log.Printf("API Error [%s]: %s", apiErr.Code, apiErr.Message)
        log.Printf("Status: %d", apiErr.Status)
        log.Printf("Details: %v", apiErr.Details)

        // Handle specific error codes
        switch apiErr.Code {
        case "invalid_credentials":
            log.Println("Wrong email or password")
        case "user_not_found":
            log.Println("User does not exist")
        case "account_locked":
            log.Println("Account is locked, try again later")
        case "mfa_required":
            log.Println("MFA verification required")
        case "rate_limited":
            log.Println("Too many requests, slow down")
        default:
            log.Printf("Unknown error: %s", apiErr.Code)
        }
        return
    }

    // Handle network/other errors
    log.Printf("Request failed: %v", err)
}
```

### Common Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `invalid_credentials` | Wrong email or password | 401 |
| `user_not_found` | User does not exist | 404 |
| `email_not_verified` | Email verification required | 403 |
| `account_locked` | Account temporarily locked | 423 |
| `mfa_required` | MFA verification needed | 403 |
| `invalid_mfa_code` | Wrong MFA code | 400 |
| `token_expired` | Access token expired | 401 |
| `token_invalid` | Invalid token | 401 |
| `insufficient_permissions` | Missing required permissions | 403 |
| `resource_not_found` | Requested resource not found | 404 |
| `conflict` | Resource already exists | 409 |
| `rate_limited` | Too many requests | 429 |
| `validation_error` | Input validation failed | 400 |
| `server_error` | Internal server error | 500 |

## Data Types

### User

```go
type User struct {
    ID            string                 `json:"id"`
    Email         string                 `json:"email"`
    EmailVerified bool                   `json:"email_verified"`
    Phone         string                 `json:"phone,omitempty"`
    PhoneVerified bool                   `json:"phone_verified"`
    FirstName     string                 `json:"first_name,omitempty"`
    LastName      string                 `json:"last_name,omitempty"`
    AvatarURL     string                 `json:"avatar_url,omitempty"`
    Metadata      map[string]interface{} `json:"metadata,omitempty"`
    CreatedAt     string                 `json:"created_at"`
    UpdatedAt     string                 `json:"updated_at"`
    LastLoginAt   string                 `json:"last_login_at,omitempty"`
    IsBlocked     bool                   `json:"is_blocked"`
    MFAEnabled    bool                   `json:"mfa_enabled"`
}
```

### Token

```go
type Token struct {
    AccessToken  string `json:"access_token"`
    RefreshToken string `json:"refresh_token"`
    TokenType    string `json:"token_type"`
    ExpiresIn    int    `json:"expires_in"`
    ExpiresAt    string `json:"expires_at"`
}
```

### Organization

```go
type Organization struct {
    ID          string                 `json:"id"`
    Name        string                 `json:"name"`
    Slug        string                 `json:"slug"`
    Description string                 `json:"description,omitempty"`
    Logo        string                 `json:"logo,omitempty"`
    OwnerID     string                 `json:"owner_id"`
    Metadata    map[string]interface{} `json:"metadata,omitempty"`
    Settings    map[string]interface{} `json:"settings,omitempty"`
    MemberCount int                    `json:"member_count"`
    CreatedAt   string                 `json:"created_at"`
    UpdatedAt   string                 `json:"updated_at"`
}
```

### Session

```go
type Session struct {
    ID           string `json:"id"`
    UserID       string `json:"user_id"`
    IPAddress    string `json:"ip_address"`
    UserAgent    string `json:"user_agent"`
    DeviceType   string `json:"device_type,omitempty"`
    Location     string `json:"location,omitempty"`
    CreatedAt    string `json:"created_at"`
    LastActiveAt string `json:"last_active_at"`
    ExpiresAt    string `json:"expires_at"`
    IsCurrent    bool   `json:"is_current"`
}
```

### Pagination

```go
type Paginated[T any] struct {
    Items      []T `json:"items"`
    Total      int `json:"total"`
    Page       int `json:"page"`
    PerPage    int `json:"per_page"`
    TotalPages int `json:"total_pages"`
}

type ListOptions struct {
    Page    int    `json:"page"`
    PerPage int    `json:"per_page"`
    Search  string `json:"search,omitempty"`
    Sort    string `json:"sort,omitempty"`
    Order   string `json:"order,omitempty"` // "asc" or "desc"
}
```

## Examples

### HTTP Server Middleware

```go
package main

import (
    "context"
    "net/http"
    "strings"

    janua "github.com/madfam-org/janua/packages/go-sdk/janua"
)

type contextKey string

const userContextKey contextKey = "user"

func AuthMiddleware(client *janua.Client) func(http.Handler) http.Handler {
    return func(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
            // Extract token from Authorization header
            authHeader := r.Header.Get("Authorization")
            if authHeader == "" {
                http.Error(w, "Unauthorized", http.StatusUnauthorized)
                return
            }

            token := strings.TrimPrefix(authHeader, "Bearer ")

            // Create client with user's token
            userClient := janua.NewClient(janua.Config{
                BaseURL:     client.BaseURL,
                AccessToken: token,
            })

            // Validate token by fetching current user
            user, err := userClient.Users.GetCurrentUser(r.Context())
            if err != nil {
                http.Error(w, "Invalid token", http.StatusUnauthorized)
                return
            }

            // Add user to context
            ctx := context.WithValue(r.Context(), userContextKey, user)
            next.ServeHTTP(w, r.WithContext(ctx))
        })
    }
}

// Helper to get user from context
func GetUserFromContext(ctx context.Context) *janua.User {
    user, _ := ctx.Value(userContextKey).(*janua.User)
    return user
}
```

### Gin Framework Integration

```go
package main

import (
    "net/http"
    "strings"

    "github.com/gin-gonic/gin"
    janua "github.com/madfam-org/janua/packages/go-sdk/janua"
)

var januaClient *janua.Client

func init() {
    januaClient = janua.NewClient(janua.Config{
        BaseURL: "https://api.janua.dev",
        APIKey:  "your-api-key",
    })
}

func AuthRequired() gin.HandlerFunc {
    return func(c *gin.Context) {
        authHeader := c.GetHeader("Authorization")
        if authHeader == "" {
            c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "missing authorization header"})
            return
        }

        token := strings.TrimPrefix(authHeader, "Bearer ")

        userClient := janua.NewClient(janua.Config{
            BaseURL:     januaClient.BaseURL,
            AccessToken: token,
        })

        user, err := userClient.Users.GetCurrentUser(c.Request.Context())
        if err != nil {
            c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid token"})
            return
        }

        c.Set("user", user)
        c.Next()
    }
}

func main() {
    r := gin.Default()

    // Public routes
    r.POST("/auth/login", handleLogin)
    r.POST("/auth/signup", handleSignUp)

    // Protected routes
    protected := r.Group("/api")
    protected.Use(AuthRequired())
    {
        protected.GET("/me", func(c *gin.Context) {
            user := c.MustGet("user").(*janua.User)
            c.JSON(http.StatusOK, user)
        })
    }

    r.Run(":8080")
}

func handleLogin(c *gin.Context) {
    var req janua.SignInRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }

    resp, err := januaClient.Auth.SignIn(c.Request.Context(), &req)
    if err != nil {
        c.JSON(http.StatusUnauthorized, gin.H{"error": err.Error()})
        return
    }

    c.JSON(http.StatusOK, resp)
}

func handleSignUp(c *gin.Context) {
    var req janua.SignUpRequest
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }

    resp, err := januaClient.Auth.SignUp(c.Request.Context(), &req)
    if err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }

    c.JSON(http.StatusCreated, resp)
}
```

### gRPC Service Integration

```go
package main

import (
    "context"

    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/metadata"
    "google.golang.org/grpc/status"

    janua "github.com/madfam-org/janua/packages/go-sdk/janua"
)

var januaClient *janua.Client

func AuthUnaryInterceptor(
    ctx context.Context,
    req interface{},
    info *grpc.UnaryServerInfo,
    handler grpc.UnaryHandler,
) (interface{}, error) {
    // Skip auth for certain methods
    if info.FullMethod == "/auth.AuthService/Login" {
        return handler(ctx, req)
    }

    // Extract token from metadata
    md, ok := metadata.FromIncomingContext(ctx)
    if !ok {
        return nil, status.Error(codes.Unauthenticated, "missing metadata")
    }

    tokens := md.Get("authorization")
    if len(tokens) == 0 {
        return nil, status.Error(codes.Unauthenticated, "missing authorization token")
    }

    token := tokens[0]

    // Validate token
    userClient := janua.NewClient(janua.Config{
        BaseURL:     januaClient.BaseURL,
        AccessToken: token,
    })

    user, err := userClient.Users.GetCurrentUser(ctx)
    if err != nil {
        return nil, status.Error(codes.Unauthenticated, "invalid token")
    }

    // Add user to context
    ctx = context.WithValue(ctx, "user", user)

    return handler(ctx, req)
}
```

### Background Worker with Token Refresh

```go
package main

import (
    "context"
    "log"
    "sync"
    "time"

    janua "github.com/madfam-org/janua/packages/go-sdk/janua"
)

type AuthenticatedWorker struct {
    client       *janua.Client
    accessToken  string
    refreshToken string
    mu           sync.RWMutex
}

func NewAuthenticatedWorker(baseURL, email, password string) (*AuthenticatedWorker, error) {
    client := janua.NewClient(janua.Config{
        BaseURL: baseURL,
    })

    resp, err := client.Auth.SignIn(context.Background(), &janua.SignInRequest{
        Email:    email,
        Password: password,
    })
    if err != nil {
        return nil, err
    }

    worker := &AuthenticatedWorker{
        client:       client,
        accessToken:  resp.Token.AccessToken,
        refreshToken: resp.Token.RefreshToken,
    }

    // Start token refresh goroutine
    go worker.startTokenRefresh()

    return worker, nil
}

func (w *AuthenticatedWorker) startTokenRefresh() {
    ticker := time.NewTicker(14 * time.Minute) // Refresh before 15min expiry
    defer ticker.Stop()

    for range ticker.C {
        w.mu.Lock()
        newToken, err := w.client.Auth.RefreshToken(context.Background(), w.refreshToken)
        if err != nil {
            log.Printf("Failed to refresh token: %v", err)
            w.mu.Unlock()
            continue
        }

        w.accessToken = newToken.AccessToken
        w.refreshToken = newToken.RefreshToken
        w.mu.Unlock()

        log.Println("Token refreshed successfully")
    }
}

func (w *AuthenticatedWorker) GetClient() *janua.Client {
    w.mu.RLock()
    defer w.mu.RUnlock()

    return janua.NewClient(janua.Config{
        BaseURL:     w.client.BaseURL,
        AccessToken: w.accessToken,
    })
}

func (w *AuthenticatedWorker) DoWork(ctx context.Context) error {
    client := w.GetClient()

    // Use client for authenticated operations
    user, err := client.Users.GetCurrentUser(ctx)
    if err != nil {
        return err
    }

    log.Printf("Working as user: %s", user.Email)
    return nil
}
```

## Testing

### Mock Client for Unit Tests

```go
package myapp_test

import (
    "context"
    "testing"

    janua "github.com/madfam-org/janua/packages/go-sdk/janua"
)

// MockAuthService implements janua.AuthServiceInterface for testing
type MockAuthService struct {
    SignInFunc func(ctx context.Context, req *janua.SignInRequest) (*janua.AuthResponse, error)
}

func (m *MockAuthService) SignIn(ctx context.Context, req *janua.SignInRequest) (*janua.AuthResponse, error) {
    if m.SignInFunc != nil {
        return m.SignInFunc(ctx, req)
    }
    return &janua.AuthResponse{
        User: &janua.User{
            ID:    "test-user-id",
            Email: req.Email,
        },
        Token: &janua.Token{
            AccessToken:  "test-access-token",
            RefreshToken: "test-refresh-token",
        },
    }, nil
}

func TestMyService(t *testing.T) {
    mockAuth := &MockAuthService{
        SignInFunc: func(ctx context.Context, req *janua.SignInRequest) (*janua.AuthResponse, error) {
            if req.Email != "test@example.com" {
                return nil, &janua.APIError{Code: "invalid_credentials"}
            }
            return &janua.AuthResponse{
                User: &janua.User{ID: "123", Email: req.Email},
                Token: &janua.Token{AccessToken: "token"},
            }, nil
        },
    }

    // Use mockAuth in your tests
    _ = mockAuth
}
```

### Integration Tests

```go
package integration_test

import (
    "context"
    "os"
    "testing"

    janua "github.com/madfam-org/janua/packages/go-sdk/janua"
)

func TestIntegration(t *testing.T) {
    if os.Getenv("JANUA_API_URL") == "" {
        t.Skip("Skipping integration test: JANUA_API_URL not set")
    }

    client := janua.NewClient(janua.Config{
        BaseURL: os.Getenv("JANUA_API_URL"),
        APIKey:  os.Getenv("JANUA_API_KEY"),
    })

    ctx := context.Background()

    // Test user creation
    resp, err := client.Auth.SignUp(ctx, &janua.SignUpRequest{
        Email:    "integration-test@example.com",
        Password: "TestPassword123!",
    })
    if err != nil {
        t.Fatalf("SignUp failed: %v", err)
    }

    if resp.User.Email != "integration-test@example.com" {
        t.Errorf("Expected email integration-test@example.com, got %s", resp.User.Email)
    }

    // Cleanup
    _ = client.Users.DeleteUser(ctx, resp.User.ID)
}
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/madfam-org/janua.git
cd janua/packages/go-sdk

# Install dependencies
go mod download

# Run tests
go test ./...

# Run tests with coverage
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out

# Run linter
golangci-lint run
```

## License

This SDK is licensed under the AGPL-3.0 License. See [LICENSE](../../LICENSE) for details.

## Support

- **Documentation**: [https://docs.janua.dev](https://docs.janua.dev)
- **GitHub Issues**: [https://github.com/madfam-org/janua/issues](https://github.com/madfam-org/janua/issues)
- **Discord**: [https://discord.gg/janua](https://discord.gg/janua)
- **Email**: support@janua.dev

## Changelog

See the main [CHANGELOG.md](../../docs/CHANGELOG.md) for a list of changes and migration guides.
