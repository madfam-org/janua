// Package janua provides a Go SDK for the Janua authentication platform
package janua

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
)

const (
	DefaultBaseURL = "https://janua.dev"
	DefaultTimeout = 30 * time.Second
	Version        = "1.0.0"
)

// Client is the main Janua SDK client
type Client struct {
	baseURL    string
	httpClient *http.Client
	apiKey     string
	tenantID   string
	
	// Services
	Auth          *AuthService
	Users         *UsersService
	Organizations *OrganizationsService
	Sessions      *SessionsService
	Webhooks      *WebhooksService
}

// Config holds the configuration for the Janua client
type Config struct {
	BaseURL  string
	APIKey   string
	TenantID string
	Timeout  time.Duration
}

// NewClient creates a new Janua client
func NewClient(config *Config) *Client {
	if config.BaseURL == "" {
		config.BaseURL = DefaultBaseURL
	}
	if config.Timeout == 0 {
		config.Timeout = DefaultTimeout
	}

	httpClient := &http.Client{
		Timeout: config.Timeout,
	}

	c := &Client{
		baseURL:    config.BaseURL,
		httpClient: httpClient,
		apiKey:     config.APIKey,
		tenantID:   config.TenantID,
	}

	// Initialize services
	c.Auth = &AuthService{client: c}
	c.Users = &UsersService{client: c}
	c.Organizations = &OrganizationsService{client: c}
	c.Sessions = &SessionsService{client: c}
	c.Webhooks = &WebhooksService{client: c}

	return c
}

// request performs an HTTP request
func (c *Client) request(ctx context.Context, method, path string, body interface{}) (*http.Response, error) {
	u, err := url.Parse(c.baseURL)
	if err != nil {
		return nil, err
	}
	u.Path = path

	var bodyReader io.Reader
	if body != nil {
		jsonBody, err := json.Marshal(body)
		if err != nil {
			return nil, err
		}
		bodyReader = bytes.NewBuffer(jsonBody)
	}

	req, err := http.NewRequestWithContext(ctx, method, u.String(), bodyReader)
	if err != nil {
		return nil, err
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", fmt.Sprintf("janua-go/%s", Version))

	if c.apiKey != "" {
		req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.apiKey))
	}
	if c.tenantID != "" {
		req.Header.Set("X-Tenant-ID", c.tenantID)
	}

	return c.httpClient.Do(req)
}

// decodeResponse decodes the JSON response
func decodeResponse(resp *http.Response, v interface{}) error {
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		var apiErr APIError
		if err := json.NewDecoder(resp.Body).Decode(&apiErr); err != nil {
			return fmt.Errorf("API error: %s", resp.Status)
		}
		return &apiErr
	}

	if v != nil {
		return json.NewDecoder(resp.Body).Decode(v)
	}
	return nil
}

// APIError represents an error from the Janua API
type APIError struct {
	Code    string                 `json:"code"`
	Message string                 `json:"message"`
	Details map[string]interface{} `json:"details,omitempty"`
}

func (e *APIError) Error() string {
	return fmt.Sprintf("%s: %s", e.Code, e.Message)
}

// User represents a Janua user
type User struct {
	ID            string                 `json:"id"`
	Email         string                 `json:"email"`
	FirstName     string                 `json:"first_name,omitempty"`
	LastName      string                 `json:"last_name,omitempty"`
	EmailVerified bool                   `json:"email_verified"`
	Phone         string                 `json:"phone,omitempty"`
	PhoneVerified bool                   `json:"phone_verified"`
	Metadata      map[string]interface{} `json:"metadata,omitempty"`
	CreatedAt     time.Time              `json:"created_at"`
	UpdatedAt     time.Time              `json:"updated_at"`
}

// Organization represents a Janua organization
type Organization struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Slug        string                 `json:"slug"`
	Description string                 `json:"description,omitempty"`
	Logo        string                 `json:"logo,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	Settings    map[string]interface{} `json:"settings,omitempty"`
	CreatedAt   time.Time              `json:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at"`
}

// Session represents a user session
type Session struct {
	ID           string    `json:"id"`
	UserID       string    `json:"user_id"`
	TenantID     string    `json:"tenant_id"`
	DeviceInfo   DeviceInfo `json:"device_info"`
	IP           string    `json:"ip"`
	UserAgent    string    `json:"user_agent"`
	LastActivity time.Time `json:"last_activity"`
	ExpiresAt    time.Time `json:"expires_at"`
	CreatedAt    time.Time `json:"created_at"`
}

// DeviceInfo contains device information for a session
type DeviceInfo struct {
	Type     string `json:"type"`
	Browser  string `json:"browser"`
	OS       string `json:"os"`
	Location string `json:"location,omitempty"`
}

// Token represents authentication tokens
type Token struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	TokenType    string `json:"token_type"`
	ExpiresIn    int    `json:"expires_in"`
}

// Claims represents JWT claims
type Claims struct {
	jwt.RegisteredClaims
	UserID   string                 `json:"uid"`
	TenantID string                 `json:"tid"`
	Email    string                 `json:"email"`
	Roles    []string               `json:"roles,omitempty"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// VerifyToken verifies a JWT token
func VerifyToken(tokenString string, publicKey string) (*Claims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &Claims{}, func(token *jwt.Token) (interface{}, error) {
		// Verify the signing method
		if _, ok := token.Method.(*jwt.SigningMethodRSA); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}

		// Parse the public key
		key, err := jwt.ParseRSAPublicKeyFromPEM([]byte(publicKey))
		if err != nil {
			return nil, err
		}
		return key, nil
	})

	if err != nil {
		return nil, err
	}

	if claims, ok := token.Claims.(*Claims); ok && token.Valid {
		return claims, nil
	}

	return nil, fmt.Errorf("invalid token")
}

// Paginated represents a paginated response
type Paginated[T any] struct {
	Data       []T `json:"data"`
	Total      int `json:"total"`
	Page       int `json:"page"`
	PerPage    int `json:"per_page"`
	TotalPages int `json:"total_pages"`
}

// ListOptions represents options for list operations
type ListOptions struct {
	Page    int    `url:"page,omitempty"`
	PerPage int    `url:"per_page,omitempty"`
	Sort    string `url:"sort,omitempty"`
	Order   string `url:"order,omitempty"`
	Search  string `url:"search,omitempty"`
}

// WebhookEvent represents a webhook event
type WebhookEvent struct {
	ID        string                 `json:"id"`
	Type      string                 `json:"type"`
	Data      map[string]interface{} `json:"data"`
	Timestamp time.Time              `json:"timestamp"`
	Signature string                 `json:"signature"`
}

// VerifyWebhookSignature verifies a webhook signature
func VerifyWebhookSignature(payload []byte, signature string, secret string) bool {
	// Implementation would verify HMAC signature
	// This is a placeholder
	return true
}

// GenerateState generates a random state for OAuth flows
func GenerateState() string {
	return uuid.New().String()
}

// GenerateCodeVerifier generates a PKCE code verifier
func GenerateCodeVerifier() string {
	// Generate random 32-byte string
	return uuid.New().String() + uuid.New().String()
}

// GenerateCodeChallenge generates a PKCE code challenge from a verifier
func GenerateCodeChallenge(verifier string) string {
	// This would implement S256 challenge generation
	// Placeholder for now
	return verifier
}