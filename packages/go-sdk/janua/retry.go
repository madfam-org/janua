// Package janua provides retry functionality for the Janua SDK
package janua

import (
	"context"
	"math"
	"math/rand"
	"net/http"
	"time"
)

// RetryConfig configures retry behavior
type RetryConfig struct {
	// MaxAttempts is the maximum number of retry attempts (including initial request)
	MaxAttempts int
	// BaseDelay is the initial delay between retries
	BaseDelay time.Duration
	// MaxDelay is the maximum delay between retries
	MaxDelay time.Duration
	// ExponentialBase is the base for exponential backoff (default: 2.0)
	ExponentialBase float64
	// Jitter adds randomness to delay to prevent thundering herd
	Jitter bool
	// RetryIf is a function that determines if an error should trigger a retry
	RetryIf func(error) bool
	// RetryStatusCodes is a list of HTTP status codes that should trigger a retry
	RetryStatusCodes []int
	// OnRetry is called before each retry with the attempt number and error
	OnRetry func(attempt int, err error, delay time.Duration)
}

// DefaultRetryConfig returns sensible retry defaults
func DefaultRetryConfig() *RetryConfig {
	return &RetryConfig{
		MaxAttempts:     3,
		BaseDelay:       1 * time.Second,
		MaxDelay:        30 * time.Second,
		ExponentialBase: 2.0,
		Jitter:          true,
		RetryStatusCodes: []int{
			http.StatusTooManyRequests,     // 429
			http.StatusInternalServerError, // 500
			http.StatusBadGateway,          // 502
			http.StatusServiceUnavailable,  // 503
			http.StatusGatewayTimeout,      // 504
		},
		RetryIf: DefaultRetryIf,
	}
}

// NoRetryConfig returns a config that disables retries
func NoRetryConfig() *RetryConfig {
	return &RetryConfig{
		MaxAttempts: 1,
	}
}

// DefaultRetryIf is the default retry decision function
func DefaultRetryIf(err error) bool {
	// Always retry network errors
	if IsNetworkError(err) {
		return true
	}

	// Check if it's a Janua error with IsRetryable
	if IsRetryable(err) {
		return true
	}

	// Check rate limit errors (always retryable)
	if IsRateLimitError(err) {
		return true
	}

	return false
}

// Retryer provides retry functionality for HTTP requests
type Retryer struct {
	config *RetryConfig
}

// NewRetryer creates a new Retryer with the given config
func NewRetryer(config *RetryConfig) *Retryer {
	if config == nil {
		config = DefaultRetryConfig()
	}
	if config.ExponentialBase == 0 {
		config.ExponentialBase = 2.0
	}
	if config.RetryIf == nil {
		config.RetryIf = DefaultRetryIf
	}
	return &Retryer{config: config}
}

// DoFunc represents a function that performs an operation and returns an error
type DoFunc func() error

// DoFuncWithResult represents a function that performs an operation and returns a result
type DoFuncWithResult[T any] func() (T, error)

// Do executes the function with retry logic
func (r *Retryer) Do(ctx context.Context, fn DoFunc) error {
	var lastErr error

	for attempt := 1; attempt <= r.config.MaxAttempts; attempt++ {
		// Check context before each attempt
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		err := fn()
		if err == nil {
			return nil
		}

		lastErr = err

		// Don't retry on last attempt
		if attempt >= r.config.MaxAttempts {
			break
		}

		// Check if we should retry
		if !r.shouldRetry(err) {
			return err
		}

		// Calculate delay
		delay := r.calculateDelay(attempt, err)

		// Call OnRetry callback if set
		if r.config.OnRetry != nil {
			r.config.OnRetry(attempt, err, delay)
		}

		// Wait with context awareness
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(delay):
			// Continue to next attempt
		}
	}

	return lastErr
}

// DoWithResult executes the function with retry logic and returns the result
func DoWithResult[T any](ctx context.Context, r *Retryer, fn DoFuncWithResult[T]) (T, error) {
	var lastErr error
	var zero T

	for attempt := 1; attempt <= r.config.MaxAttempts; attempt++ {
		// Check context before each attempt
		select {
		case <-ctx.Done():
			return zero, ctx.Err()
		default:
		}

		result, err := fn()
		if err == nil {
			return result, nil
		}

		lastErr = err

		// Don't retry on last attempt
		if attempt >= r.config.MaxAttempts {
			break
		}

		// Check if we should retry
		if !r.shouldRetry(err) {
			return zero, err
		}

		// Calculate delay
		delay := r.calculateDelay(attempt, err)

		// Call OnRetry callback if set
		if r.config.OnRetry != nil {
			r.config.OnRetry(attempt, err, delay)
		}

		// Wait with context awareness
		select {
		case <-ctx.Done():
			return zero, ctx.Err()
		case <-time.After(delay):
			// Continue to next attempt
		}
	}

	return zero, lastErr
}

// shouldRetry determines if an error should trigger a retry
func (r *Retryer) shouldRetry(err error) bool {
	if r.config.RetryIf != nil {
		return r.config.RetryIf(err)
	}
	return false
}

// calculateDelay calculates the delay before the next retry
func (r *Retryer) calculateDelay(attempt int, err error) time.Duration {
	// Check for rate limit error with RetryAfter
	if rlErr, ok := err.(*RateLimitError); ok && rlErr.RetryAfter > 0 {
		return rlErr.RetryAfter
	}

	// Calculate exponential backoff
	multiplier := math.Pow(r.config.ExponentialBase, float64(attempt-1))
	delay := time.Duration(float64(r.config.BaseDelay) * multiplier)

	// Apply max delay cap
	if delay > r.config.MaxDelay {
		delay = r.config.MaxDelay
	}

	// Apply jitter if enabled
	if r.config.Jitter {
		// Add random jitter of ±25%
		jitterRange := float64(delay) * 0.25
		jitter := (rand.Float64()*2 - 1) * jitterRange //nolint:gosec // G404: Jitter doesn't need cryptographic randomness
		delay = time.Duration(float64(delay) + jitter)
	}

	return delay
}

// WithRetry is a convenience function for simple retry operations
func WithRetry[T any](ctx context.Context, config *RetryConfig, fn DoFuncWithResult[T]) (T, error) {
	retryer := NewRetryer(config)
	return DoWithResult(ctx, retryer, fn)
}

// WithDefaultRetry is a convenience function using default retry config
func WithDefaultRetry[T any](ctx context.Context, fn DoFuncWithResult[T]) (T, error) {
	return WithRetry(ctx, DefaultRetryConfig(), fn)
}

// RetryableClient wraps an HTTP client with retry functionality
type RetryableClient struct {
	client  *http.Client
	retryer *Retryer
}

// NewRetryableClient creates a new HTTP client with retry functionality
func NewRetryableClient(client *http.Client, config *RetryConfig) *RetryableClient {
	if client == nil {
		client = http.DefaultClient
	}
	return &RetryableClient{
		client:  client,
		retryer: NewRetryer(config),
	}
}

// Do performs an HTTP request with retry logic
func (rc *RetryableClient) Do(req *http.Request) (*http.Response, error) {
	var resp *http.Response
	var lastErr error

	err := rc.retryer.Do(req.Context(), func() error {
		var err error
		resp, err = rc.client.Do(req)
		if err != nil {
			lastErr = NewNetworkError(err)
			return lastErr
		}

		// Check if status code should trigger retry
		for _, code := range rc.retryer.config.RetryStatusCodes {
			if resp.StatusCode == code {
				// Close body before retry
				resp.Body.Close()
				lastErr = &JanuaError{
					Code:       "HTTP_ERROR",
					Message:    http.StatusText(resp.StatusCode),
					StatusCode: resp.StatusCode,
				}
				return lastErr
			}
		}

		return nil
	})

	if err != nil {
		return nil, err
	}

	return resp, lastErr
}

// CircuitBreaker provides circuit breaker functionality
type CircuitBreaker struct {
	// State tracking
	failures    int
	successes   int
	lastFailure time.Time
	state       CircuitState

	// Configuration
	failureThreshold int
	successThreshold int
	timeout          time.Duration
	halfOpenMaxCalls int
	halfOpenCalls    int
}

// CircuitState represents the state of the circuit breaker
type CircuitState int

const (
	CircuitClosed CircuitState = iota
	CircuitOpen
	CircuitHalfOpen
)

// CircuitBreakerConfig configures the circuit breaker
type CircuitBreakerConfig struct {
	// FailureThreshold is the number of failures before opening the circuit
	FailureThreshold int
	// SuccessThreshold is the number of successes needed to close the circuit
	SuccessThreshold int
	// Timeout is how long the circuit stays open before half-opening
	Timeout time.Duration
	// HalfOpenMaxCalls is the max concurrent calls in half-open state
	HalfOpenMaxCalls int
}

// DefaultCircuitBreakerConfig returns sensible defaults
func DefaultCircuitBreakerConfig() *CircuitBreakerConfig {
	return &CircuitBreakerConfig{
		FailureThreshold: 5,
		SuccessThreshold: 3,
		Timeout:          30 * time.Second,
		HalfOpenMaxCalls: 1,
	}
}

// NewCircuitBreaker creates a new circuit breaker
func NewCircuitBreaker(config *CircuitBreakerConfig) *CircuitBreaker {
	if config == nil {
		config = DefaultCircuitBreakerConfig()
	}
	return &CircuitBreaker{
		state:            CircuitClosed,
		failureThreshold: config.FailureThreshold,
		successThreshold: config.SuccessThreshold,
		timeout:          config.Timeout,
		halfOpenMaxCalls: config.HalfOpenMaxCalls,
	}
}

// ErrCircuitOpen is returned when the circuit is open
var ErrCircuitOpen = &JanuaError{
	Code:    "CIRCUIT_OPEN",
	Message: "Circuit breaker is open",
}

// Execute runs a function through the circuit breaker
func (cb *CircuitBreaker) Execute(fn func() error) error {
	if !cb.allowRequest() {
		return ErrCircuitOpen
	}

	err := fn()

	cb.recordResult(err)

	return err
}

// allowRequest checks if a request should be allowed
func (cb *CircuitBreaker) allowRequest() bool {
	switch cb.state {
	case CircuitClosed:
		return true
	case CircuitOpen:
		// Check if timeout has passed
		if time.Since(cb.lastFailure) > cb.timeout {
			cb.state = CircuitHalfOpen
			cb.halfOpenCalls = 0
			return true
		}
		return false
	case CircuitHalfOpen:
		if cb.halfOpenCalls < cb.halfOpenMaxCalls {
			cb.halfOpenCalls++
			return true
		}
		return false
	default:
		return false
	}
}

// recordResult records the result of a request
func (cb *CircuitBreaker) recordResult(err error) {
	if err != nil {
		cb.failures++
		cb.successes = 0
		cb.lastFailure = time.Now()

		if cb.failures >= cb.failureThreshold {
			cb.state = CircuitOpen
		}
	} else {
		cb.successes++
		cb.failures = 0

		if cb.state == CircuitHalfOpen && cb.successes >= cb.successThreshold {
			cb.state = CircuitClosed
		}
	}
}

// State returns the current circuit state
func (cb *CircuitBreaker) State() CircuitState {
	return cb.state
}

// String returns a string representation of the circuit state
func (s CircuitState) String() string {
	switch s {
	case CircuitClosed:
		return "closed"
	case CircuitOpen:
		return "open"
	case CircuitHalfOpen:
		return "half-open"
	default:
		return "unknown"
	}
}
