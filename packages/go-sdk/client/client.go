package client

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"time"

	"github.com/madfam-org/janua/packages/go-sdk/auth"
	"github.com/madfam-org/janua/packages/go-sdk/models"
)

// Client represents the Janua API client
type Client struct {
	baseURL    string
	apiKey     string
	httpClient *http.Client
	auth       *auth.Manager
}

// Config holds the client configuration
type Config struct {
	BaseURL    string
	APIKey     string
	HTTPClient *http.Client
	Timeout    time.Duration
}

// New creates a new Janua client
func New(config Config) *Client {
	if config.BaseURL == "" {
		config.BaseURL = "https://api.janua.dev"
	}

	if config.HTTPClient == nil {
		timeout := config.Timeout
		if timeout == 0 {
			timeout = 30 * time.Second
		}
		config.HTTPClient = &http.Client{
			Timeout: timeout,
		}
	}

	return &Client{
		baseURL:    config.BaseURL,
		apiKey:     config.APIKey,
		httpClient: config.HTTPClient,
		auth:       auth.NewManager(config.APIKey),
	}
}

// SignIn authenticates a user with email and password
func (c *Client) SignIn(ctx context.Context, email, password string) (*models.AuthResponse, error) {
	payload := map[string]string{
		"email":    email,
		"password": password,
	}

	var response models.AuthResponse
	err := c.post(ctx, "/auth/signin", payload, &response)
	if err != nil {
		return nil, err
	}

	// Store the tokens in the auth manager
	c.auth.SetTokens(response.AccessToken, response.RefreshToken)
	
	return &response, nil
}

// SignUp creates a new user account
func (c *Client) SignUp(ctx context.Context, req *models.SignUpRequest) (*models.AuthResponse, error) {
	var response models.AuthResponse
	err := c.post(ctx, "/auth/signup", req, &response)
	if err != nil {
		return nil, err
	}

	c.auth.SetTokens(response.AccessToken, response.RefreshToken)
	
	return &response, nil
}

// SignOut logs out the current user
func (c *Client) SignOut(ctx context.Context) error {
	err := c.post(ctx, "/auth/signout", nil, nil)
	if err != nil {
		return err
	}

	c.auth.ClearTokens()
	return nil
}

// GetUser retrieves the current user's information
func (c *Client) GetUser(ctx context.Context) (*models.User, error) {
	var user models.User
	err := c.get(ctx, "/users/me", &user)
	return &user, err
}

// UpdateUser updates the current user's information
func (c *Client) UpdateUser(ctx context.Context, updates *models.UserUpdate) (*models.User, error) {
	var user models.User
	err := c.patch(ctx, "/users/me", updates, &user)
	return &user, err
}

// ListSessions retrieves all active sessions for the current user
func (c *Client) ListSessions(ctx context.Context) ([]*models.Session, error) {
	var response struct {
		Sessions []*models.Session `json:"sessions"`
	}
	err := c.get(ctx, "/sessions", &response)
	return response.Sessions, err
}

// RevokeSession revokes a specific session
func (c *Client) RevokeSession(ctx context.Context, sessionID string) error {
	return c.delete(ctx, fmt.Sprintf("/sessions/%s", sessionID))
}

// EnableMFA enables multi-factor authentication
func (c *Client) EnableMFA(ctx context.Context) (*models.MFASetup, error) {
	var setup models.MFASetup
	err := c.post(ctx, "/mfa/enable", nil, &setup)
	return &setup, err
}

// VerifyMFA verifies an MFA code
func (c *Client) VerifyMFA(ctx context.Context, code string) error {
	payload := map[string]string{"code": code}
	return c.post(ctx, "/mfa/verify", payload, nil)
}

// DisableMFA disables multi-factor authentication
func (c *Client) DisableMFA(ctx context.Context, code string) error {
	payload := map[string]string{"code": code}
	return c.post(ctx, "/mfa/disable", payload, nil)
}

// HTTP helper methods

func (c *Client) get(ctx context.Context, path string, result interface{}) error {
	return c.request(ctx, "GET", path, nil, result)
}

func (c *Client) post(ctx context.Context, path string, body interface{}, result interface{}) error {
	return c.request(ctx, "POST", path, body, result)
}

func (c *Client) patch(ctx context.Context, path string, body interface{}, result interface{}) error {
	return c.request(ctx, "PATCH", path, body, result)
}

func (c *Client) delete(ctx context.Context, path string) error {
	return c.request(ctx, "DELETE", path, nil, nil)
}

func (c *Client) request(ctx context.Context, method, path string, body interface{}, result interface{}) error {
	u, err := url.Parse(c.baseURL)
	if err != nil {
		return err
	}
	u.Path = "/api/v1" + path

	var bodyReader io.Reader
	if body != nil {
		jsonBody, err := json.Marshal(body)
		if err != nil {
			return err
		}
		bodyReader = bytes.NewReader(jsonBody)
	}

	req, err := http.NewRequestWithContext(ctx, method, u.String(), bodyReader)
	if err != nil {
		return err
	}

	// Set headers
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")
	
	// Add API key if available
	if c.apiKey != "" {
		req.Header.Set("X-API-Key", c.apiKey)
	}

	// Add authorization token if available
	if token := c.auth.GetAccessToken(); token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	// Check for errors
	if resp.StatusCode >= 400 {
		var apiErr models.APIError
		if err := json.NewDecoder(resp.Body).Decode(&apiErr); err != nil {
			return fmt.Errorf("API error: %s", resp.Status)
		}
		return &apiErr
	}

	// Decode response if result is provided
	if result != nil {
		return json.NewDecoder(resp.Body).Decode(result)
	}

	return nil
}