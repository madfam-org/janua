package janua

import (
	"context"
	"fmt"
	"net/http"
)

// WebhooksService handles webhook operations
type WebhooksService struct {
	client *Client
}

// Webhook represents a webhook configuration
type Webhook struct {
	ID        string   `json:"id"`
	URL       string   `json:"url"`
	Events    []string `json:"events"`
	Secret    string   `json:"secret,omitempty"`
	Active    bool     `json:"active"`
	CreatedAt string   `json:"created_at"`
	UpdatedAt string   `json:"updated_at"`
}

// WebhookCreateRequest represents a request to create a webhook
type WebhookCreateRequest struct {
	URL    string   `json:"url"`
	Events []string `json:"events"`
	Secret string   `json:"secret,omitempty"`
}

// WebhookUpdateRequest represents a request to update a webhook
type WebhookUpdateRequest struct {
	URL    string   `json:"url,omitempty"`
	Events []string `json:"events,omitempty"`
	Active *bool    `json:"active,omitempty"`
}

// List returns all webhooks
func (s *WebhooksService) List(ctx context.Context) (*Paginated[Webhook], error) {
	resp, err := s.client.request(ctx, http.MethodGet, "/api/v1/webhooks", nil)
	if err != nil {
		return nil, err
	}

	var result Paginated[Webhook]
	if err := decodeResponse(resp, &result); err != nil {
		return nil, err
	}
	return &result, nil
}

// Get returns a specific webhook by ID
func (s *WebhooksService) Get(ctx context.Context, webhookID string) (*Webhook, error) {
	path := fmt.Sprintf("/api/v1/webhooks/%s", webhookID)
	resp, err := s.client.request(ctx, http.MethodGet, path, nil)
	if err != nil {
		return nil, err
	}

	var webhook Webhook
	if err := decodeResponse(resp, &webhook); err != nil {
		return nil, err
	}
	return &webhook, nil
}

// Create creates a new webhook
func (s *WebhooksService) Create(ctx context.Context, req *WebhookCreateRequest) (*Webhook, error) {
	resp, err := s.client.request(ctx, http.MethodPost, "/api/v1/webhooks", req)
	if err != nil {
		return nil, err
	}

	var webhook Webhook
	if err := decodeResponse(resp, &webhook); err != nil {
		return nil, err
	}
	return &webhook, nil
}

// Update updates a webhook
func (s *WebhooksService) Update(ctx context.Context, webhookID string, req *WebhookUpdateRequest) (*Webhook, error) {
	path := fmt.Sprintf("/api/v1/webhooks/%s", webhookID)
	resp, err := s.client.request(ctx, http.MethodPatch, path, req)
	if err != nil {
		return nil, err
	}

	var webhook Webhook
	if err := decodeResponse(resp, &webhook); err != nil {
		return nil, err
	}
	return &webhook, nil
}

// Delete deletes a webhook
func (s *WebhooksService) Delete(ctx context.Context, webhookID string) error {
	path := fmt.Sprintf("/api/v1/webhooks/%s", webhookID)
	resp, err := s.client.request(ctx, http.MethodDelete, path, nil)
	if err != nil {
		return err
	}
	return decodeResponse(resp, nil)
}
