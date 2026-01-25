package janua

import (
	"context"
	"fmt"
	"net/http"
)

// AuthService handles authentication operations
type AuthService struct {
	client *Client
}

// SignUpRequest represents a sign-up request
type SignUpRequest struct {
	Email     string                 `json:"email"`
	Password  string                 `json:"password"`
	FirstName string                 `json:"first_name,omitempty"`
	LastName  string                 `json:"last_name,omitempty"`
	Phone     string                 `json:"phone,omitempty"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

// SignInRequest represents a sign-in request
type SignInRequest struct {
	Email    string `json:"email,omitempty"`
	Phone    string `json:"phone,omitempty"`
	Password string `json:"password,omitempty"`
	OTP      string `json:"otp,omitempty"`
}

// AuthResponse represents an authentication response
type AuthResponse struct {
	User  *User         `json:"user"`
	Token *Token        `json:"token"`
	MFA   *MFAChallenge `json:"mfa,omitempty"`
}

// MFAChallenge represents an MFA challenge
type MFAChallenge struct {
	ChallengeID string   `json:"challenge_id"`
	Methods     []string `json:"methods"`
}

// SignUp creates a new user account
func (s *AuthService) SignUp(ctx context.Context, req *SignUpRequest) (*AuthResponse, error) {
	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/signup", req)
	if err != nil {
		return nil, err
	}

	var authResp AuthResponse
	if err := decodeResponse(resp, &authResp); err != nil {
		return nil, err
	}

	// Auto-store tokens
	if authResp.Token != nil {
		s.client.SetTokens(authResp.Token)
	}

	return &authResp, nil
}

// SignIn authenticates a user
func (s *AuthService) SignIn(ctx context.Context, req *SignInRequest) (*AuthResponse, error) {
	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/signin", req)
	if err != nil {
		return nil, err
	}

	var authResp AuthResponse
	if err := decodeResponse(resp, &authResp); err != nil {
		return nil, err
	}

	// Auto-store tokens
	if authResp.Token != nil {
		s.client.SetTokens(authResp.Token)
	}

	return &authResp, nil
}

// SignOut signs out the current user
func (s *AuthService) SignOut(ctx context.Context, refreshToken string) error {
	req := map[string]string{
		"refresh_token": refreshToken,
	}

	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/signout", req)
	if err != nil {
		return err
	}

	// Clear stored tokens
	s.client.ClearTokens()

	return decodeResponse(resp, nil)
}

// RefreshToken refreshes an access token
func (s *AuthService) RefreshToken(ctx context.Context, refreshToken string) (*Token, error) {
	req := map[string]string{
		"refresh_token": refreshToken,
	}

	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/refresh", req)
	if err != nil {
		return nil, err
	}

	var token Token
	if err := decodeResponse(resp, &token); err != nil {
		return nil, err
	}

	// Auto-store new tokens
	s.client.SetTokens(&token)

	return &token, nil
}

// VerifyEmail verifies an email address
func (s *AuthService) VerifyEmail(ctx context.Context, token string) error {
	req := map[string]string{
		"token": token,
	}

	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/verify-email", req)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// RequestPasswordReset requests a password reset
func (s *AuthService) RequestPasswordReset(ctx context.Context, email string) error {
	req := map[string]string{
		"email": email,
	}

	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/password/reset", req)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// ResetPassword resets a password using a token
func (s *AuthService) ResetPassword(ctx context.Context, token, newPassword string) error {
	req := map[string]string{
		"token":    token,
		"password": newPassword,
	}

	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/password/confirm", req)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// ChangePassword changes the current user's password
func (s *AuthService) ChangePassword(ctx context.Context, currentPassword, newPassword string) error {
	req := map[string]string{
		"current_password": currentPassword,
		"new_password":     newPassword,
	}

	resp, err := s.client.request(ctx, http.MethodPut, "/api/v1/auth/password/change", req)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// MFAVerifyRequest represents an MFA verification request
type MFAVerifyRequest struct {
	ChallengeID string `json:"challenge_id"`
	Code        string `json:"code"`
	Method      string `json:"method"`
}

// VerifyMFA verifies an MFA code
func (s *AuthService) VerifyMFA(ctx context.Context, req *MFAVerifyRequest) (*AuthResponse, error) {
	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/mfa/verify", req)
	if err != nil {
		return nil, err
	}

	var authResp AuthResponse
	if err := decodeResponse(resp, &authResp); err != nil {
		return nil, err
	}

	return &authResp, nil
}

// EnableMFA enables MFA for the current user
func (s *AuthService) EnableMFA(ctx context.Context, method string) (*MFASetupResponse, error) {
	req := map[string]string{
		"method": method,
	}

	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/mfa/enable", req)
	if err != nil {
		return nil, err
	}

	var setupResp MFASetupResponse
	if err := decodeResponse(resp, &setupResp); err != nil {
		return nil, err
	}

	return &setupResp, nil
}

// MFASetupResponse represents MFA setup information
type MFASetupResponse struct {
	Secret      string   `json:"secret"`
	QRCode      string   `json:"qr_code"`
	BackupCodes []string `json:"backup_codes"`
}

// DisableMFA disables MFA for the current user
func (s *AuthService) DisableMFA(ctx context.Context, password string) error {
	req := map[string]string{
		"password": password,
	}

	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/mfa/disable", req)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// OAuthRequest represents an OAuth authorization request
type OAuthRequest struct {
	Provider    string   `json:"provider"`
	RedirectURI string   `json:"redirect_uri"`
	State       string   `json:"state,omitempty"`
	Scopes      []string `json:"scopes,omitempty"`
}

// GetOAuthURL gets the OAuth authorization URL
func (s *AuthService) GetOAuthURL(ctx context.Context, req *OAuthRequest) (string, error) {
	resp, err := s.client.request(ctx, http.MethodGet, fmt.Sprintf("/api/v1/auth/oauth/%s/authorize", req.Provider), nil)
	if err != nil {
		return "", err
	}

	var result struct {
		URL string `json:"authorization_url"`
	}
	if err := decodeResponse(resp, &result); err != nil {
		return "", err
	}

	return result.URL, nil
}

// HandleOAuthCallback handles the OAuth callback
func (s *AuthService) HandleOAuthCallback(ctx context.Context, code, state string) (*AuthResponse, error) {
	req := map[string]string{
		"code":  code,
		"state": state,
	}

	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/oauth/callback", req)
	if err != nil {
		return nil, err
	}

	var authResp AuthResponse
	if err := decodeResponse(resp, &authResp); err != nil {
		return nil, err
	}

	// Auto-store tokens
	if authResp.Token != nil {
		s.client.SetTokens(authResp.Token)
	}

	return &authResp, nil
}

// PasskeyRegistrationRequest represents a passkey registration request
type PasskeyRegistrationRequest struct {
	UserID      string `json:"user_id,omitempty"`
	DisplayName string `json:"display_name,omitempty"`
}

// PasskeyCredential represents a passkey credential
type PasskeyCredential struct {
	ID          string `json:"id"`
	PublicKey   string `json:"public_key"`
	UserID      string `json:"user_id"`
	DisplayName string `json:"display_name"`
	CreatedAt   string `json:"created_at"`
}

// StartPasskeyRegistration starts the passkey registration process
func (s *AuthService) StartPasskeyRegistration(ctx context.Context, req *PasskeyRegistrationRequest) (map[string]interface{}, error) {
	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/passkeys/register/start", req)
	if err != nil {
		return nil, err
	}

	var options map[string]interface{}
	if err := decodeResponse(resp, &options); err != nil {
		return nil, err
	}

	return options, nil
}

// CompletePasskeyRegistration completes the passkey registration
func (s *AuthService) CompletePasskeyRegistration(ctx context.Context, credential map[string]interface{}) (*PasskeyCredential, error) {
	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/passkeys/register/complete", credential)
	if err != nil {
		return nil, err
	}

	var cred PasskeyCredential
	if err := decodeResponse(resp, &cred); err != nil {
		return nil, err
	}

	return &cred, nil
}

// StartPasskeyAuthentication starts the passkey authentication process
func (s *AuthService) StartPasskeyAuthentication(ctx context.Context) (map[string]interface{}, error) {
	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/passkeys/authenticate/start", nil)
	if err != nil {
		return nil, err
	}

	var options map[string]interface{}
	if err := decodeResponse(resp, &options); err != nil {
		return nil, err
	}

	return options, nil
}

// CompletePasskeyAuthentication completes the passkey authentication
func (s *AuthService) CompletePasskeyAuthentication(ctx context.Context, assertion map[string]interface{}) (*AuthResponse, error) {
	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/auth/passkeys/authenticate/complete", assertion)
	if err != nil {
		return nil, err
	}

	var authResp AuthResponse
	if err := decodeResponse(resp, &authResp); err != nil {
		return nil, err
	}

	// Auto-store tokens
	if authResp.Token != nil {
		s.client.SetTokens(authResp.Token)
	}

	return &authResp, nil
}
