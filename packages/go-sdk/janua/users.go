package janua

import (
	"context"
	"fmt"
	"net/http"
)

// UsersService handles user management operations
type UsersService struct {
	client *Client
}

// GetCurrentUser gets the current authenticated user
func (s *UsersService) GetCurrentUser(ctx context.Context) (*User, error) {
	resp, err := s.client.request(ctx, http.MethodGet, "/api/v1/users/me", nil)
	if err != nil {
		return nil, err
	}

	var user User
	if err := decodeResponse(resp, &user); err != nil {
		return nil, err
	}

	return &user, nil
}

// GetUser gets a user by ID
func (s *UsersService) GetUser(ctx context.Context, userID string) (*User, error) {
	resp, err := s.client.request(ctx, http.MethodGet, fmt.Sprintf("/api/v1/users/%s", userID), nil)
	if err != nil {
		return nil, err
	}

	var user User
	if err := decodeResponse(resp, &user); err != nil {
		return nil, err
	}

	return &user, nil
}

// ListUsers lists all users
func (s *UsersService) ListUsers(ctx context.Context, opts *ListOptions) (*Paginated[User], error) {
	// Build query parameters
	path := "/api/v1/users"
	if opts != nil {
		// Add query parameters
		path = fmt.Sprintf("%s?page=%d&per_page=%d", path, opts.Page, opts.PerPage)
		if opts.Search != "" {
			path = fmt.Sprintf("%s&search=%s", path, opts.Search)
		}
		if opts.Sort != "" {
			path = fmt.Sprintf("%s&sort=%s&order=%s", path, opts.Sort, opts.Order)
		}
	}

	resp, err := s.client.request(ctx, http.MethodGet, path, nil)
	if err != nil {
		return nil, err
	}

	var result Paginated[User]
	if err := decodeResponse(resp, &result); err != nil {
		return nil, err
	}

	return &result, nil
}

// UpdateUserRequest represents a user update request
type UpdateUserRequest struct {
	FirstName string                 `json:"first_name,omitempty"`
	LastName  string                 `json:"last_name,omitempty"`
	Phone     string                 `json:"phone,omitempty"`
	Metadata  map[string]interface{} `json:"metadata,omitempty"`
}

// UpdateUser updates a user
func (s *UsersService) UpdateUser(ctx context.Context, userID string, req *UpdateUserRequest) (*User, error) {
	resp, err := s.client.request(ctx, http.MethodPut, fmt.Sprintf("/api/v1/users/%s", userID), req)
	if err != nil {
		return nil, err
	}

	var user User
	if err := decodeResponse(resp, &user); err != nil {
		return nil, err
	}

	return &user, nil
}

// UpdateCurrentUser updates the current user
func (s *UsersService) UpdateCurrentUser(ctx context.Context, req *UpdateUserRequest) (*User, error) {
	resp, err := s.client.request(ctx, http.MethodPut, "/api/v1/users/me", req)
	if err != nil {
		return nil, err
	}

	var user User
	if err := decodeResponse(resp, &user); err != nil {
		return nil, err
	}

	return &user, nil
}

// DeleteUser deletes a user
func (s *UsersService) DeleteUser(ctx context.Context, userID string) error {
	resp, err := s.client.request(ctx, http.MethodDelete, fmt.Sprintf("/api/v1/users/%s", userID), nil)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// BlockUser blocks a user
func (s *UsersService) BlockUser(ctx context.Context, userID string) error {
	resp, err := s.client.request(ctx, http.MethodPost, fmt.Sprintf("/api/v1/users/%s/block", userID), nil)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// UnblockUser unblocks a user
func (s *UsersService) UnblockUser(ctx context.Context, userID string) error {
	resp, err := s.client.request(ctx, http.MethodPost, fmt.Sprintf("/api/v1/users/%s/unblock", userID), nil)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// GetUserRoles gets a user's roles
func (s *UsersService) GetUserRoles(ctx context.Context, userID string) ([]Role, error) {
	resp, err := s.client.request(ctx, http.MethodGet, fmt.Sprintf("/api/v1/users/%s/roles", userID), nil)
	if err != nil {
		return nil, err
	}

	var roles []Role
	if err := decodeResponse(resp, &roles); err != nil {
		return nil, err
	}

	return roles, nil
}

// Role represents a user role
type Role struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Description string   `json:"description,omitempty"`
	Permissions []string `json:"permissions,omitempty"`
}

// AssignRole assigns a role to a user
func (s *UsersService) AssignRole(ctx context.Context, userID, roleID string) error {
	req := map[string]string{
		"role_id": roleID,
	}

	resp, err := s.client.request(ctx, http.MethodPost, fmt.Sprintf("/api/v1/users/%s/roles", userID), req)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// RemoveRole removes a role from a user
func (s *UsersService) RemoveRole(ctx context.Context, userID, roleID string) error {
	resp, err := s.client.request(ctx, http.MethodDelete, fmt.Sprintf("/api/v1/users/%s/roles/%s", userID, roleID), nil)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// GetUserOrganizations gets a user's organizations
func (s *UsersService) GetUserOrganizations(ctx context.Context, userID string) ([]Organization, error) {
	resp, err := s.client.request(ctx, http.MethodGet, fmt.Sprintf("/api/v1/users/%s/organizations", userID), nil)
	if err != nil {
		return nil, err
	}

	var orgs []Organization
	if err := decodeResponse(resp, &orgs); err != nil {
		return nil, err
	}

	return orgs, nil
}

// GetUserSessions gets a user's active sessions
func (s *UsersService) GetUserSessions(ctx context.Context, userID string) ([]Session, error) {
	resp, err := s.client.request(ctx, http.MethodGet, fmt.Sprintf("/api/v1/users/%s/sessions", userID), nil)
	if err != nil {
		return nil, err
	}

	var sessions []Session
	if err := decodeResponse(resp, &sessions); err != nil {
		return nil, err
	}

	return sessions, nil
}

// RevokeUserSession revokes a user's session
func (s *UsersService) RevokeUserSession(ctx context.Context, userID, sessionID string) error {
	resp, err := s.client.request(ctx, http.MethodDelete, fmt.Sprintf("/api/v1/users/%s/sessions/%s", userID, sessionID), nil)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// RevokeAllUserSessions revokes all of a user's sessions
func (s *UsersService) RevokeAllUserSessions(ctx context.Context, userID string) error {
	resp, err := s.client.request(ctx, http.MethodDelete, fmt.Sprintf("/api/v1/users/%s/sessions", userID), nil)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// SearchUsers searches for users
func (s *UsersService) SearchUsers(ctx context.Context, query string, opts *ListOptions) (*Paginated[User], error) {
	if opts == nil {
		opts = &ListOptions{}
	}
	opts.Search = query

	return s.ListUsers(ctx, opts)
}

// GetUserByEmail gets a user by email address
func (s *UsersService) GetUserByEmail(ctx context.Context, email string) (*User, error) {
	resp, err := s.client.request(ctx, http.MethodGet, fmt.Sprintf("/api/v1/users/email/%s", email), nil)
	if err != nil {
		return nil, err
	}

	var user User
	if err := decodeResponse(resp, &user); err != nil {
		return nil, err
	}

	return &user, nil
}

// BulkInviteRequest represents a bulk invite request
type BulkInviteRequest struct {
	Emails []string `json:"emails"`
	RoleID string   `json:"role_id,omitempty"`
	OrgID  string   `json:"org_id,omitempty"`
}

// BulkInviteUsers invites multiple users
func (s *UsersService) BulkInviteUsers(ctx context.Context, req *BulkInviteRequest) ([]User, error) {
	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/users/bulk-invite", req)
	if err != nil {
		return nil, err
	}

	var users []User
	if err := decodeResponse(resp, &users); err != nil {
		return nil, err
	}

	return users, nil
}
