package auth

import (
	"encoding/base64"
	"encoding/json"
	"strings"
	"sync"
	"time"
)

// Manager handles authentication tokens and JWT validation
type Manager struct {
	mu           sync.RWMutex
	apiKey       string
	accessToken  string
	refreshToken string
	expiresAt    time.Time
}

// NewManager creates a new auth manager
func NewManager(apiKey string) *Manager {
	return &Manager{
		apiKey: apiKey,
	}
}

// SetTokens sets the access and refresh tokens
func (m *Manager) SetTokens(accessToken, refreshToken string) {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.accessToken = accessToken
	m.refreshToken = refreshToken

	// Parse expiration from JWT
	if exp := extractExpiration(accessToken); exp != nil {
		m.expiresAt = *exp
	}
}

// GetAccessToken returns the current access token
func (m *Manager) GetAccessToken() string {
	m.mu.RLock()
	defer m.mu.RUnlock()

	// Check if token is expired
	if !m.expiresAt.IsZero() && time.Now().After(m.expiresAt) {
		return ""
	}

	return m.accessToken
}

// GetRefreshToken returns the current refresh token
func (m *Manager) GetRefreshToken() string {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.refreshToken
}

// ClearTokens clears all stored tokens
func (m *Manager) ClearTokens() {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.accessToken = ""
	m.refreshToken = ""
	m.expiresAt = time.Time{}
}

// IsAuthenticated checks if the user is currently authenticated
func (m *Manager) IsAuthenticated() bool {
	return m.GetAccessToken() != ""
}

// NeedsRefresh checks if the access token needs to be refreshed
func (m *Manager) NeedsRefresh() bool {
	m.mu.RLock()
	defer m.mu.RUnlock()

	if m.accessToken == "" || m.expiresAt.IsZero() {
		return false
	}

	// Refresh if token expires in less than 5 minutes
	return time.Until(m.expiresAt) < 5*time.Minute
}

// extractExpiration extracts the expiration time from a JWT token
func extractExpiration(token string) *time.Time {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil
	}

	// Decode the payload
	payload, err := base64.RawURLEncoding.DecodeString(parts[1])
	if err != nil {
		return nil
	}

	var claims map[string]interface{}
	if err := json.Unmarshal(payload, &claims); err != nil {
		return nil
	}

	// Extract exp claim
	if exp, ok := claims["exp"].(float64); ok {
		t := time.Unix(int64(exp), 0)
		return &t
	}

	return nil
}
