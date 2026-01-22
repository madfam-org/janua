package janua

import (
	"context"
	"fmt"
	"net/http"
)

// OrganizationsService handles organization management operations
type OrganizationsService struct {
	client *Client
}

// CreateOrganizationRequest represents an organization creation request
type CreateOrganizationRequest struct {
	Name        string                 `json:"name"`
	Slug        string                 `json:"slug,omitempty"`
	Description string                 `json:"description,omitempty"`
	Logo        string                 `json:"logo,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	Settings    map[string]interface{} `json:"settings,omitempty"`
}

// CreateOrganization creates a new organization
func (s *OrganizationsService) CreateOrganization(ctx context.Context, req *CreateOrganizationRequest) (*Organization, error) {
	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/organizations", req)
	if err != nil {
		return nil, err
	}

	var org Organization
	if err := decodeResponse(resp, &org); err != nil {
		return nil, err
	}

	return &org, nil
}

// GetOrganization gets an organization by ID
func (s *OrganizationsService) GetOrganization(ctx context.Context, orgID string) (*Organization, error) {
	resp, err := s.client.request(ctx, http.MethodGet, fmt.Sprintf("/api/v1/organizations/%s", orgID), nil)
	if err != nil {
		return nil, err
	}

	var org Organization
	if err := decodeResponse(resp, &org); err != nil {
		return nil, err
	}

	return &org, nil
}

// GetOrganizationBySlug gets an organization by slug
func (s *OrganizationsService) GetOrganizationBySlug(ctx context.Context, slug string) (*Organization, error) {
	resp, err := s.client.request(ctx, http.MethodGet, fmt.Sprintf("/api/v1/organizations/slug/%s", slug), nil)
	if err != nil {
		return nil, err
	}

	var org Organization
	if err := decodeResponse(resp, &org); err != nil {
		return nil, err
	}

	return &org, nil
}

// ListOrganizations lists all organizations
func (s *OrganizationsService) ListOrganizations(ctx context.Context, opts *ListOptions) (*Paginated[Organization], error) {
	path := "/api/v1/organizations"
	if opts != nil {
		path = fmt.Sprintf("%s?page=%d&per_page=%d", path, opts.Page, opts.PerPage)
		if opts.Search != "" {
			path = fmt.Sprintf("%s&search=%s", path, opts.Search)
		}
	}

	resp, err := s.client.request(ctx, http.MethodGet, path, nil)
	if err != nil {
		return nil, err
	}

	var result Paginated[Organization]
	if err := decodeResponse(resp, &result); err != nil {
		return nil, err
	}

	return &result, nil
}

// UpdateOrganizationRequest represents an organization update request
type UpdateOrganizationRequest struct {
	Name        string                 `json:"name,omitempty"`
	Description string                 `json:"description,omitempty"`
	Logo        string                 `json:"logo,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
	Settings    map[string]interface{} `json:"settings,omitempty"`
}

// UpdateOrganization updates an organization
func (s *OrganizationsService) UpdateOrganization(ctx context.Context, orgID string, req *UpdateOrganizationRequest) (*Organization, error) {
	resp, err := s.client.request(ctx, http.MethodPut, fmt.Sprintf("/api/v1/organizations/%s", orgID), req)
	if err != nil {
		return nil, err
	}

	var org Organization
	if err := decodeResponse(resp, &org); err != nil {
		return nil, err
	}

	return &org, nil
}

// DeleteOrganization deletes an organization
func (s *OrganizationsService) DeleteOrganization(ctx context.Context, orgID string) error {
	resp, err := s.client.request(ctx, http.MethodDelete, fmt.Sprintf("/api/v1/organizations/%s", orgID), nil)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// OrganizationMember represents an organization member
type OrganizationMember struct {
	ID        string   `json:"id"`
	UserID    string   `json:"user_id"`
	User      *User    `json:"user,omitempty"`
	OrgID     string   `json:"org_id"`
	Role      string   `json:"role"`
	Roles     []string `json:"roles,omitempty"`
	JoinedAt  string   `json:"joined_at"`
	InvitedBy string   `json:"invited_by,omitempty"`
}

// GetOrganizationMembers gets organization members
func (s *OrganizationsService) GetOrganizationMembers(ctx context.Context, orgID string, opts *ListOptions) (*Paginated[OrganizationMember], error) {
	path := fmt.Sprintf("/api/v1/organizations/%s/members", orgID)
	if opts != nil {
		path = fmt.Sprintf("%s?page=%d&per_page=%d", path, opts.Page, opts.PerPage)
	}

	resp, err := s.client.request(ctx, http.MethodGet, path, nil)
	if err != nil {
		return nil, err
	}

	var result Paginated[OrganizationMember]
	if err := decodeResponse(resp, &result); err != nil {
		return nil, err
	}

	return &result, nil
}

// AddOrganizationMemberRequest represents a member addition request
type AddOrganizationMemberRequest struct {
	UserID string   `json:"user_id,omitempty"`
	Email  string   `json:"email,omitempty"`
	Role   string   `json:"role"`
	Roles  []string `json:"roles,omitempty"`
}

// AddOrganizationMember adds a member to an organization
func (s *OrganizationsService) AddOrganizationMember(ctx context.Context, orgID string, req *AddOrganizationMemberRequest) (*OrganizationMember, error) {
	resp, err := s.client.request(ctx, http.MethodPost, fmt.Sprintf("/api/v1/organizations/%s/members", orgID), req)
	if err != nil {
		return nil, err
	}

	var member OrganizationMember
	if err := decodeResponse(resp, &member); err != nil {
		return nil, err
	}

	return &member, nil
}

// UpdateOrganizationMemberRequest represents a member update request
type UpdateOrganizationMemberRequest struct {
	Role  string   `json:"role,omitempty"`
	Roles []string `json:"roles,omitempty"`
}

// UpdateOrganizationMember updates an organization member
func (s *OrganizationsService) UpdateOrganizationMember(ctx context.Context, orgID, userID string, req *UpdateOrganizationMemberRequest) (*OrganizationMember, error) {
	resp, err := s.client.request(ctx, http.MethodPut, fmt.Sprintf("/api/v1/organizations/%s/members/%s", orgID, userID), req)
	if err != nil {
		return nil, err
	}

	var member OrganizationMember
	if err := decodeResponse(resp, &member); err != nil {
		return nil, err
	}

	return &member, nil
}

// RemoveOrganizationMember removes a member from an organization
func (s *OrganizationsService) RemoveOrganizationMember(ctx context.Context, orgID, userID string) error {
	resp, err := s.client.request(ctx, http.MethodDelete, fmt.Sprintf("/api/v1/organizations/%s/members/%s", orgID, userID), nil)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// OrganizationInvite represents an organization invite
type OrganizationInvite struct {
	ID         string `json:"id"`
	OrgID      string `json:"org_id"`
	Email      string `json:"email"`
	Role       string `json:"role"`
	InvitedBy  string `json:"invited_by"`
	InvitedAt  string `json:"invited_at"`
	ExpiresAt  string `json:"expires_at"`
	AcceptedAt string `json:"accepted_at,omitempty"`
	Status     string `json:"status"`
}

// CreateInviteRequest represents an invite creation request
type CreateInviteRequest struct {
	Email string   `json:"email"`
	Role  string   `json:"role"`
	Roles []string `json:"roles,omitempty"`
}

// CreateOrganizationInvite creates an organization invite
func (s *OrganizationsService) CreateOrganizationInvite(ctx context.Context, orgID string, req *CreateInviteRequest) (*OrganizationInvite, error) {
	resp, err := s.client.request(ctx, http.MethodPost, fmt.Sprintf("/api/v1/organizations/%s/invites", orgID), req)
	if err != nil {
		return nil, err
	}

	var invite OrganizationInvite
	if err := decodeResponse(resp, &invite); err != nil {
		return nil, err
	}

	return &invite, nil
}

// ListOrganizationInvites lists organization invites
func (s *OrganizationsService) ListOrganizationInvites(ctx context.Context, orgID string) ([]OrganizationInvite, error) {
	resp, err := s.client.request(ctx, http.MethodGet, fmt.Sprintf("/api/v1/organizations/%s/invites", orgID), nil)
	if err != nil {
		return nil, err
	}

	var invites []OrganizationInvite
	if err := decodeResponse(resp, &invites); err != nil {
		return nil, err
	}

	return invites, nil
}

// RevokeOrganizationInvite revokes an organization invite
func (s *OrganizationsService) RevokeOrganizationInvite(ctx context.Context, orgID, inviteID string) error {
	resp, err := s.client.request(ctx, http.MethodDelete, fmt.Sprintf("/api/v1/organizations/%s/invites/%s", orgID, inviteID), nil)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}

// AcceptOrganizationInvite accepts an organization invite
func (s *OrganizationsService) AcceptOrganizationInvite(ctx context.Context, inviteToken string) (*Organization, error) {
	req := map[string]string{
		"token": inviteToken,
	}

	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/organizations/invites/accept", req)
	if err != nil {
		return nil, err
	}

	var org Organization
	if err := decodeResponse(resp, &org); err != nil {
		return nil, err
	}

	return &org, nil
}

// OrganizationRole represents an organization role
type OrganizationRole struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Description string   `json:"description,omitempty"`
	Permissions []string `json:"permissions"`
	IsDefault   bool     `json:"is_default"`
	IsSystem    bool     `json:"is_system"`
}

// GetOrganizationRoles gets organization roles
func (s *OrganizationsService) GetOrganizationRoles(ctx context.Context, orgID string) ([]OrganizationRole, error) {
	resp, err := s.client.request(ctx, http.MethodGet, fmt.Sprintf("/api/v1/organizations/%s/roles", orgID), nil)
	if err != nil {
		return nil, err
	}

	var roles []OrganizationRole
	if err := decodeResponse(resp, &roles); err != nil {
		return nil, err
	}

	return roles, nil
}

// CreateOrganizationRoleRequest represents a role creation request
type CreateOrganizationRoleRequest struct {
	Name        string   `json:"name"`
	Description string   `json:"description,omitempty"`
	Permissions []string `json:"permissions"`
}

// CreateOrganizationRole creates an organization role
func (s *OrganizationsService) CreateOrganizationRole(ctx context.Context, orgID string, req *CreateOrganizationRoleRequest) (*OrganizationRole, error) {
	resp, err := s.client.request(ctx, http.MethodPost, fmt.Sprintf("/api/v1/organizations/%s/roles", orgID), req)
	if err != nil {
		return nil, err
	}

	var role OrganizationRole
	if err := decodeResponse(resp, &role); err != nil {
		return nil, err
	}

	return &role, nil
}

// UpdateOrganizationRole updates an organization role
func (s *OrganizationsService) UpdateOrganizationRole(ctx context.Context, orgID, roleID string, req *CreateOrganizationRoleRequest) (*OrganizationRole, error) {
	resp, err := s.client.request(ctx, http.MethodPut, fmt.Sprintf("/api/v1/organizations/%s/roles/%s", orgID, roleID), req)
	if err != nil {
		return nil, err
	}

	var role OrganizationRole
	if err := decodeResponse(resp, &role); err != nil {
		return nil, err
	}

	return &role, nil
}

// DeleteOrganizationRole deletes an organization role
func (s *OrganizationsService) DeleteOrganizationRole(ctx context.Context, orgID, roleID string) error {
	resp, err := s.client.request(ctx, http.MethodDelete, fmt.Sprintf("/api/v1/organizations/%s/roles/%s", orgID, roleID), nil)
	if err != nil {
		return err
	}

	return decodeResponse(resp, nil)
}
