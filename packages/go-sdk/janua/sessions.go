package janua

import (
	"context"
	"fmt"
	"net/http"
)

// SessionsService handles session operations
type SessionsService struct {
	client *Client
}

// List returns all sessions for the current user
func (s *SessionsService) List(ctx context.Context) (*Paginated[Session], error) {
	resp, err := s.client.request(ctx, http.MethodGet, "/api/v1/sessions", nil)
	if err != nil {
		return nil, err
	}

	var result Paginated[Session]
	if err := decodeResponse(resp, &result); err != nil {
		return nil, err
	}
	return &result, nil
}

// Get returns a specific session by ID
func (s *SessionsService) Get(ctx context.Context, sessionID string) (*Session, error) {
	path := fmt.Sprintf("/api/v1/sessions/%s", sessionID)
	resp, err := s.client.request(ctx, http.MethodGet, path, nil)
	if err != nil {
		return nil, err
	}

	var session Session
	if err := decodeResponse(resp, &session); err != nil {
		return nil, err
	}
	return &session, nil
}

// Revoke revokes a specific session
func (s *SessionsService) Revoke(ctx context.Context, sessionID string) error {
	path := fmt.Sprintf("/api/v1/sessions/%s", sessionID)
	resp, err := s.client.request(ctx, http.MethodDelete, path, nil)
	if err != nil {
		return err
	}
	return decodeResponse(resp, nil)
}

// RevokeAll revokes all sessions for the current user
func (s *SessionsService) RevokeAll(ctx context.Context) error {
	resp, err := s.client.request(ctx, http.MethodDelete, "/api/v1/sessions", nil)
	if err != nil {
		return err
	}
	return decodeResponse(resp, nil)
}
