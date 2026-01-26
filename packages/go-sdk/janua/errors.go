// Package janua provides error types for the Janua SDK
package janua

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"time"
)

// Error codes matching the Janua API
const (
	// Authentication errors
	ErrCodeAuthentication     = "AUTHENTICATION_ERROR"
	ErrCodeTokenError         = "TOKEN_ERROR"
	ErrCodeEmailNotVerified   = "EMAIL_NOT_VERIFIED"
	ErrCodeMFARequired        = "MFA_REQUIRED"
	ErrCodePasswordExpired    = "PASSWORD_EXPIRED"
	ErrCodeAccountLocked      = "ACCOUNT_LOCKED"
	ErrCodeSessionExpired     = "SESSION_EXPIRED"
	ErrCodeInvalidCredentials = "INVALID_CREDENTIALS" //nolint:gosec // G101: This is an error code constant, not a credential

	// Authorization errors
	ErrCodeAuthorization           = "AUTHORIZATION_ERROR"
	ErrCodeInsufficientPermissions = "INSUFFICIENT_PERMISSIONS"
	ErrCodeAccessDenied            = "ACCESS_DENIED"

	// Validation errors
	ErrCodeValidation = "VALIDATION_ERROR"

	// Resource errors
	ErrCodeNotFound = "NOT_FOUND_ERROR"
	ErrCodeConflict = "CONFLICT_ERROR"

	// Rate limiting
	ErrCodeRateLimit = "RATE_LIMIT_ERROR"

	// Server errors
	ErrCodeInternal           = "INTERNAL_ERROR"
	ErrCodeExternalService    = "EXTERNAL_SERVICE_ERROR"
	ErrCodeServiceUnavailable = "SERVICE_UNAVAILABLE"

	// SSO errors
	ErrCodeSSOAuthentication = "SSO_AUTHENTICATION_ERROR"
	ErrCodeSSOValidation     = "SSO_VALIDATION_ERROR"
	ErrCodeSSOConfiguration  = "SSO_CONFIGURATION_ERROR"
	ErrCodeSSOMetadata       = "SSO_METADATA_ERROR"
	ErrCodeSSOCertificate    = "SSO_CERTIFICATE_ERROR"
	ErrCodeSSOProvisioning   = "SSO_PROVISIONING_ERROR"
)

// JanuaError is the base error type for all Janua SDK errors
//
//nolint:revive // stutters: Renaming to Error would be a breaking API change
type JanuaError struct {
	// Code is the error code from the API
	Code string `json:"code"`
	// Message is a human-readable error message
	Message string `json:"message"`
	// StatusCode is the HTTP status code
	StatusCode int `json:"status_code"`
	// Details contains additional error information
	Details map[string]interface{} `json:"details,omitempty"`
	// RequestID is the request ID for debugging
	RequestID string `json:"request_id,omitempty"`
	// Cause is the underlying error if any
	Cause error `json:"-"`
}

// Error implements the error interface
func (e *JanuaError) Error() string {
	if e.RequestID != "" {
		return fmt.Sprintf("[%s] %s (request_id: %s)", e.Code, e.Message, e.RequestID)
	}
	return fmt.Sprintf("[%s] %s", e.Code, e.Message)
}

// Unwrap returns the underlying error
func (e *JanuaError) Unwrap() error {
	return e.Cause
}

// IsRetryable returns true if the error is retryable
func (e *JanuaError) IsRetryable() bool {
	switch e.StatusCode {
	case http.StatusTooManyRequests,
		http.StatusServiceUnavailable,
		http.StatusBadGateway,
		http.StatusGatewayTimeout:
		return true
	default:
		return false
	}
}

// AuthenticationError represents authentication failures
type AuthenticationError struct {
	JanuaError
}

// NewAuthenticationError creates a new authentication error
func NewAuthenticationError(message string, details map[string]interface{}) *AuthenticationError {
	return &AuthenticationError{
		JanuaError: JanuaError{
			Code:       ErrCodeAuthentication,
			Message:    message,
			StatusCode: http.StatusUnauthorized,
			Details:    details,
		},
	}
}

// TokenError represents token-related errors
type TokenError struct {
	JanuaError
}

// NewTokenError creates a new token error
func NewTokenError(message string, details map[string]interface{}) *TokenError {
	return &TokenError{
		JanuaError: JanuaError{
			Code:       ErrCodeTokenError,
			Message:    message,
			StatusCode: http.StatusUnauthorized,
			Details:    details,
		},
	}
}

// EmailNotVerifiedError indicates the user needs to verify their email
type EmailNotVerifiedError struct {
	JanuaError
}

// NewEmailNotVerifiedError creates a new email not verified error
func NewEmailNotVerifiedError(email string) *EmailNotVerifiedError {
	return &EmailNotVerifiedError{
		JanuaError: JanuaError{
			Code:       ErrCodeEmailNotVerified,
			Message:    "Email address not verified",
			StatusCode: http.StatusUnauthorized,
			Details:    map[string]interface{}{"email": email},
		},
	}
}

// MFARequiredError indicates MFA is required to complete authentication
type MFARequiredError struct {
	JanuaError
	// MFAToken is the temporary token to use for MFA verification
	MFAToken string
	// AvailableMethods lists the available MFA methods
	AvailableMethods []string
}

// NewMFARequiredError creates a new MFA required error
func NewMFARequiredError(mfaToken string, methods []string) *MFARequiredError {
	return &MFARequiredError{
		JanuaError: JanuaError{
			Code:       ErrCodeMFARequired,
			Message:    "Multi-factor authentication required",
			StatusCode: http.StatusUnauthorized,
			Details: map[string]interface{}{
				"mfa_token":         mfaToken,
				"available_methods": methods,
			},
		},
		MFAToken:         mfaToken,
		AvailableMethods: methods,
	}
}

// PasswordExpiredError indicates the user's password has expired
type PasswordExpiredError struct {
	JanuaError
	// ExpiredAt is when the password expired
	ExpiredAt *time.Time
}

// AccountLockedError indicates the account is locked
type AccountLockedError struct {
	JanuaError
	// LockedUntil is when the account will be unlocked
	LockedUntil *time.Time
	// Reason is the reason for the lock
	Reason string
}

// SessionExpiredError indicates the session has expired
type SessionExpiredError struct {
	JanuaError
	// ExpiredAt is when the session expired
	ExpiredAt *time.Time
}

// AuthorizationError represents authorization failures
type AuthorizationError struct {
	JanuaError
}

// NewAuthorizationError creates a new authorization error
func NewAuthorizationError(message string, details map[string]interface{}) *AuthorizationError {
	return &AuthorizationError{
		JanuaError: JanuaError{
			Code:       ErrCodeAuthorization,
			Message:    message,
			StatusCode: http.StatusForbidden,
			Details:    details,
		},
	}
}

// InsufficientPermissionsError indicates missing permissions
type InsufficientPermissionsError struct {
	JanuaError
	// RequiredPermissions lists the permissions needed
	RequiredPermissions []string
	// Resource is the resource being accessed
	Resource string
	// Action is the action being attempted
	Action string
}

// ValidationError represents validation failures
type ValidationError struct {
	JanuaError
	// FieldErrors contains per-field validation errors
	FieldErrors []FieldError
}

// FieldError represents a validation error for a specific field
type FieldError struct {
	Field   string `json:"field"`
	Message string `json:"message"`
	Type    string `json:"type,omitempty"`
}

// NewValidationError creates a new validation error
func NewValidationError(message string, fieldErrors []FieldError) *ValidationError {
	return &ValidationError{
		JanuaError: JanuaError{
			Code:       ErrCodeValidation,
			Message:    message,
			StatusCode: http.StatusUnprocessableEntity,
		},
		FieldErrors: fieldErrors,
	}
}

// NotFoundError indicates a resource was not found
type NotFoundError struct {
	JanuaError
	// Resource is the type of resource not found
	Resource string
	// ResourceID is the ID of the resource
	ResourceID string
}

// NewNotFoundError creates a new not found error
func NewNotFoundError(resource, resourceID string) *NotFoundError {
	return &NotFoundError{
		JanuaError: JanuaError{
			Code:       ErrCodeNotFound,
			Message:    fmt.Sprintf("%s not found", resource),
			StatusCode: http.StatusNotFound,
			Details: map[string]interface{}{
				"resource":    resource,
				"resource_id": resourceID,
			},
		},
		Resource:   resource,
		ResourceID: resourceID,
	}
}

// ConflictError indicates a resource conflict
type ConflictError struct {
	JanuaError
}

// NewConflictError creates a new conflict error
func NewConflictError(message string, details map[string]interface{}) *ConflictError {
	return &ConflictError{
		JanuaError: JanuaError{
			Code:       ErrCodeConflict,
			Message:    message,
			StatusCode: http.StatusConflict,
			Details:    details,
		},
	}
}

// RateLimitError indicates rate limiting
type RateLimitError struct {
	JanuaError
	// RetryAfter is when the client can retry
	RetryAfter time.Duration
	// Limit is the rate limit
	Limit int
	// Remaining is requests remaining
	Remaining int
	// ResetAt is when the rate limit resets
	ResetAt *time.Time
}

// NewRateLimitError creates a new rate limit error
func NewRateLimitError(retryAfter time.Duration) *RateLimitError {
	return &RateLimitError{
		JanuaError: JanuaError{
			Code:       ErrCodeRateLimit,
			Message:    "Rate limit exceeded",
			StatusCode: http.StatusTooManyRequests,
		},
		RetryAfter: retryAfter,
	}
}

// NetworkError represents network-level errors
type NetworkError struct {
	JanuaError
}

// NewNetworkError creates a new network error
func NewNetworkError(cause error) *NetworkError {
	return &NetworkError{
		JanuaError: JanuaError{
			Code:    "NETWORK_ERROR",
			Message: "Network error occurred",
			Cause:   cause,
		},
	}
}

// InternalError represents server-side errors
type InternalError struct {
	JanuaError
}

// NewInternalError creates a new internal error
func NewInternalError(requestID string) *InternalError {
	return &InternalError{
		JanuaError: JanuaError{
			Code:       ErrCodeInternal,
			Message:    "An internal error occurred",
			StatusCode: http.StatusInternalServerError,
			RequestID:  requestID,
		},
	}
}

// ParseAPIError parses an HTTP response into the appropriate error type
func ParseAPIError(resp *http.Response, body []byte) error {
	// Try to parse as structured API error
	var apiErr struct {
		Error struct {
			Code      string                 `json:"code"`
			Message   string                 `json:"message"`
			Details   map[string]interface{} `json:"details,omitempty"`
			RequestID string                 `json:"request_id,omitempty"`
		} `json:"error"`
	}

	base := JanuaError{
		StatusCode: resp.StatusCode,
		Code:       "UNKNOWN_ERROR",
		Message:    http.StatusText(resp.StatusCode),
	}

	// Try parsing as nested error format
	if err := parseJSON(body, &apiErr); err == nil && apiErr.Error.Code != "" {
		base.Code = apiErr.Error.Code
		base.Message = apiErr.Error.Message
		base.Details = apiErr.Error.Details
		base.RequestID = apiErr.Error.RequestID
	} else {
		// Try flat format
		var flatErr struct {
			Code    string                 `json:"code"`
			Message string                 `json:"message"`
			Details map[string]interface{} `json:"details,omitempty"`
		}
		if err := parseJSON(body, &flatErr); err == nil && flatErr.Code != "" {
			base.Code = flatErr.Code
			base.Message = flatErr.Message
			base.Details = flatErr.Details
		}
	}

	// Parse rate limit headers
	var rateLimitErr *RateLimitError
	if resp.StatusCode == http.StatusTooManyRequests {
		rateLimitErr = &RateLimitError{JanuaError: base}
		if retryAfter := resp.Header.Get("Retry-After"); retryAfter != "" {
			if seconds, err := strconv.Atoi(retryAfter); err == nil {
				rateLimitErr.RetryAfter = time.Duration(seconds) * time.Second
			}
		}
		if limit := resp.Header.Get("X-RateLimit-Limit"); limit != "" {
			if val, err := strconv.Atoi(limit); err == nil {
				rateLimitErr.Limit = val
			}
		}
		if remaining := resp.Header.Get("X-RateLimit-Remaining"); remaining != "" {
			if val, err := strconv.Atoi(remaining); err == nil {
				rateLimitErr.Remaining = val
			}
		}
		if reset := resp.Header.Get("X-RateLimit-Reset"); reset != "" {
			if ts, err := strconv.ParseInt(reset, 10, 64); err == nil {
				t := time.Unix(ts, 0)
				rateLimitErr.ResetAt = &t
			}
		}
		return rateLimitErr
	}

	// Map error code to specific error type
	switch base.Code {
	case ErrCodeAuthentication, ErrCodeInvalidCredentials:
		return &AuthenticationError{JanuaError: base}
	case ErrCodeTokenError:
		return &TokenError{JanuaError: base}
	case ErrCodeEmailNotVerified:
		return &EmailNotVerifiedError{JanuaError: base}
	case ErrCodeMFARequired:
		mfaErr := &MFARequiredError{JanuaError: base}
		if base.Details != nil {
			if token, ok := base.Details["mfa_token"].(string); ok {
				mfaErr.MFAToken = token
			}
			if methods, ok := base.Details["available_methods"].([]interface{}); ok {
				for _, m := range methods {
					if s, ok := m.(string); ok {
						mfaErr.AvailableMethods = append(mfaErr.AvailableMethods, s)
					}
				}
			}
		}
		return mfaErr
	case ErrCodePasswordExpired:
		return &PasswordExpiredError{JanuaError: base}
	case ErrCodeAccountLocked:
		lockedErr := &AccountLockedError{JanuaError: base}
		if base.Details != nil {
			if reason, ok := base.Details["reason"].(string); ok {
				lockedErr.Reason = reason
			}
		}
		return lockedErr
	case ErrCodeSessionExpired:
		return &SessionExpiredError{JanuaError: base}
	case ErrCodeAuthorization, ErrCodeAccessDenied:
		return &AuthorizationError{JanuaError: base}
	case ErrCodeInsufficientPermissions:
		permErr := &InsufficientPermissionsError{JanuaError: base}
		if base.Details != nil {
			if perms, ok := base.Details["required_permissions"].([]interface{}); ok {
				for _, p := range perms {
					if s, ok := p.(string); ok {
						permErr.RequiredPermissions = append(permErr.RequiredPermissions, s)
					}
				}
			}
			if resource, ok := base.Details["resource"].(string); ok {
				permErr.Resource = resource
			}
			if action, ok := base.Details["action"].(string); ok {
				permErr.Action = action
			}
		}
		return permErr
	case ErrCodeValidation:
		valErr := &ValidationError{JanuaError: base}
		if base.Details != nil {
			if errors, ok := base.Details["validation_errors"].([]interface{}); ok {
				for _, e := range errors {
					m, ok := e.(map[string]interface{})
					if !ok {
						continue
					}
					fe := FieldError{}
					if field, ok := m["field"].(string); ok {
						fe.Field = field
					}
					if msg, ok := m["message"].(string); ok {
						fe.Message = msg
					}
					if t, ok := m["type"].(string); ok {
						fe.Type = t
					}
					valErr.FieldErrors = append(valErr.FieldErrors, fe)
				}
			}
		}
		return valErr
	case ErrCodeNotFound:
		return &NotFoundError{JanuaError: base}
	case ErrCodeConflict:
		return &ConflictError{JanuaError: base}
	case ErrCodeRateLimit:
		return &RateLimitError{JanuaError: base}
	case ErrCodeInternal, ErrCodeServiceUnavailable:
		return &InternalError{JanuaError: base}
	default:
		return &base
	}
}

// Type assertion helpers

// IsAuthenticationError checks if the error is an authentication error
func IsAuthenticationError(err error) bool {
	_, ok := err.(*AuthenticationError)
	return ok
}

// IsTokenError checks if the error is a token error
func IsTokenError(err error) bool {
	_, ok := err.(*TokenError)
	return ok
}

// IsMFARequired checks if MFA is required
func IsMFARequired(err error) bool {
	_, ok := err.(*MFARequiredError)
	return ok
}

// IsEmailNotVerified checks if email verification is required
func IsEmailNotVerified(err error) bool {
	_, ok := err.(*EmailNotVerifiedError)
	return ok
}

// IsAuthorizationError checks if the error is an authorization error
func IsAuthorizationError(err error) bool {
	_, ok := err.(*AuthorizationError)
	return ok
}

// IsValidationError checks if the error is a validation error
func IsValidationError(err error) bool {
	_, ok := err.(*ValidationError)
	return ok
}

// IsNotFoundError checks if the error is a not found error
func IsNotFoundError(err error) bool {
	_, ok := err.(*NotFoundError)
	return ok
}

// IsRateLimitError checks if the error is a rate limit error
func IsRateLimitError(err error) bool {
	_, ok := err.(*RateLimitError)
	return ok
}

// IsNetworkError checks if the error is a network error
func IsNetworkError(err error) bool {
	_, ok := err.(*NetworkError)
	return ok
}

// IsRetryable checks if an error is retryable
func IsRetryable(err error) bool {
	if e, ok := err.(*JanuaError); ok {
		return e.IsRetryable()
	}
	if e, ok := err.(*RateLimitError); ok {
		return e.IsRetryable()
	}
	if _, ok := err.(*NetworkError); ok {
		return true
	}
	return false
}

// GetUserMessage returns a user-friendly error message
func GetUserMessage(err error) string {
	messages := map[string]string{
		ErrCodeAuthentication:          "Invalid email or password. Please try again.",
		ErrCodeTokenError:              "Your session is invalid. Please sign in again.",
		ErrCodeEmailNotVerified:        "Please verify your email address to continue.",
		ErrCodeMFARequired:             "Please complete two-factor authentication.",
		ErrCodePasswordExpired:         "Your password has expired. Please reset it.",
		ErrCodeAccountLocked:           "Your account is temporarily locked. Please try again later.",
		ErrCodeSessionExpired:          "Your session has expired. Please sign in again.",
		ErrCodeAuthorization:           "You don't have permission to perform this action.",
		ErrCodeInsufficientPermissions: "You need additional permissions for this action.",
		ErrCodeValidation:              "Please check your input and try again.",
		ErrCodeNotFound:                "The requested resource was not found.",
		ErrCodeConflict:                "This action conflicts with existing data.",
		ErrCodeRateLimit:               "Too many requests. Please wait a moment and try again.",
		ErrCodeInternal:                "An unexpected error occurred. Please try again later.",
		"NETWORK_ERROR":                "Unable to connect. Please check your internet connection.",
	}

	if e, ok := err.(*JanuaError); ok {
		if msg, exists := messages[e.Code]; exists {
			return msg
		}
		return e.Message
	}

	// Check specific error types
	switch e := err.(type) {
	case *AuthenticationError:
		return messages[ErrCodeAuthentication]
	case *MFARequiredError:
		return messages[ErrCodeMFARequired]
	case *RateLimitError:
		if e.RetryAfter > 0 {
			return fmt.Sprintf("Too many requests. Please try again in %s.", e.RetryAfter)
		}
		return messages[ErrCodeRateLimit]
	case *NetworkError:
		return messages["NETWORK_ERROR"]
	}

	return "An unexpected error occurred."
}

// parseJSON is a helper to parse JSON from bytes
func parseJSON(data []byte, v interface{}) error {
	if len(data) == 0 {
		return fmt.Errorf("empty response body")
	}
	// Note: Uses encoding/json imported in client.go
	// This function is defined here for error parsing but uses
	// json.Unmarshal from the standard library
	return json.Unmarshal(data, v)
}
