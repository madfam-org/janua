package models

import (
	"fmt"
	"time"
)

// User represents a Janua user
type User struct {
	ID             string                 `json:"id"`
	Email          string                 `json:"email"`
	EmailVerified  bool                   `json:"email_verified"`
	Name           string                 `json:"name,omitempty"`
	Picture        string                 `json:"picture,omitempty"`
	Locale         string                 `json:"locale,omitempty"`
	OrganizationID string                 `json:"organization_id,omitempty"`
	Metadata       map[string]interface{} `json:"metadata,omitempty"`
	MFAEnabled     bool                   `json:"mfa_enabled"`
	CreatedAt      time.Time              `json:"created_at"`
	UpdatedAt      time.Time              `json:"updated_at"`
	LastSignInAt   *time.Time             `json:"last_sign_in_at,omitempty"`
	SignInCount    int                    `json:"sign_in_count"`
}

// Session represents an active user session
type Session struct {
	ID           string    `json:"id"`
	UserID       string    `json:"user_id"`
	IPAddress    string    `json:"ip_address"`
	UserAgent    string    `json:"user_agent"`
	Device       string    `json:"device,omitempty"`
	Location     string    `json:"location,omitempty"`
	LastActivity time.Time `json:"last_activity"`
	CreatedAt    time.Time `json:"created_at"`
	ExpiresAt    time.Time `json:"expires_at"`
}

// Organization represents a Janua organization
type Organization struct {
	ID        string                 `json:"id"`
	Name      string                 `json:"name"`
	Slug      string                 `json:"slug"`
	Domain    string                 `json:"domain,omitempty"`
	Logo      string                 `json:"logo,omitempty"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
	Settings  *OrganizationSettings  `json:"settings,omitempty"`
	CreatedAt time.Time              `json:"created_at"`
	UpdatedAt time.Time              `json:"updated_at"`
}

// OrganizationSettings contains organization-specific settings
type OrganizationSettings struct {
	RequireMFA            bool     `json:"require_mfa"`
	AllowedDomains        []string `json:"allowed_domains,omitempty"`
	SessionDuration       int      `json:"session_duration"` // in seconds
	PasswordPolicy        string   `json:"password_policy,omitempty"`
	AllowSignUp           bool     `json:"allow_sign_up"`
	AllowPasswordSignIn   bool     `json:"allow_password_sign_in"`
	AllowedOAuthProviders []string `json:"allowed_oauth_providers,omitempty"`
}

// AuthResponse represents the response from authentication endpoints
type AuthResponse struct {
	User         *User  `json:"user"`
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	ExpiresIn    int    `json:"expires_in"`
	TokenType    string `json:"token_type"`
}

// SignUpRequest represents a sign-up request
type SignUpRequest struct {
	Email          string                 `json:"email"`
	Password       string                 `json:"password"`
	Name           string                 `json:"name,omitempty"`
	OrganizationID string                 `json:"organization_id,omitempty"`
	Metadata       map[string]interface{} `json:"metadata,omitempty"`
}

// UserUpdate represents fields that can be updated on a user
type UserUpdate struct {
	Name     *string                 `json:"name,omitempty"`
	Picture  *string                 `json:"picture,omitempty"`
	Locale   *string                 `json:"locale,omitempty"`
	Metadata *map[string]interface{} `json:"metadata,omitempty"`
}

// MFASetup represents MFA setup information
type MFASetup struct {
	Secret        string   `json:"secret"`
	QRCode        string   `json:"qr_code"`
	RecoveryCodes []string `json:"recovery_codes"`
}

// APIError represents an API error response
type APIError struct {
	Code    string      `json:"code"`
	Message string      `json:"message"`
	Details interface{} `json:"details,omitempty"`
}

// Error implements the error interface for APIError
func (e *APIError) Error() string {
	return fmt.Sprintf("[%s] %s", e.Code, e.Message)
}

// OAuthProvider represents an OAuth provider configuration
type OAuthProvider struct {
	Provider    string   `json:"provider"`
	ClientID    string   `json:"client_id"`
	AuthURL     string   `json:"auth_url"`
	TokenURL    string   `json:"token_url"`
	RedirectURL string   `json:"redirect_url"`
	Scopes      []string `json:"scopes"`
}

// WebAuthnCredential represents a WebAuthn/Passkey credential
type WebAuthnCredential struct {
	ID             string     `json:"id"`
	UserID         string     `json:"user_id"`
	Name           string     `json:"name"`
	CredentialID   string     `json:"credential_id"`
	PublicKey      string     `json:"public_key"`
	SignCount      uint32     `json:"sign_count"`
	Transports     []string   `json:"transports,omitempty"`
	BackupEligible bool       `json:"backup_eligible"`
	BackupState    bool       `json:"backup_state"`
	CreatedAt      time.Time  `json:"created_at"`
	LastUsedAt     *time.Time `json:"last_used_at,omitempty"`
}

// AuditLog represents an audit log entry
type AuditLog struct {
	ID             string                 `json:"id"`
	OrganizationID string                 `json:"organization_id"`
	UserID         string                 `json:"user_id,omitempty"`
	Action         string                 `json:"action"`
	Resource       string                 `json:"resource"`
	ResourceID     string                 `json:"resource_id,omitempty"`
	IPAddress      string                 `json:"ip_address,omitempty"`
	UserAgent      string                 `json:"user_agent,omitempty"`
	Metadata       map[string]interface{} `json:"metadata,omitempty"`
	CreatedAt      time.Time              `json:"created_at"`
}
