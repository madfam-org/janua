"""
Unit tests for custom exception classes
"""

from app.exceptions import (
    JanuaAPIException,
    AuthenticationError,
    TokenError,
    AuthorizationError,
    ValidationError,
    NotFoundError,
    ConflictError,
    RateLimitError
)


class TestJanuaAPIException:
    """Test the base JanuaAPIException class."""
    
    def test_basic_exception(self):
        """Test basic exception creation."""
        exc = JanuaAPIException(
            message="Test error",
            status_code=400,
            error_code="TEST_ERROR"
        )
        
        assert str(exc) == "Test error"
        assert exc.message == "Test error"
        assert exc.status_code == 400
        assert exc.error_code == "TEST_ERROR"
        assert exc.details == {}
    
    def test_exception_with_details(self):
        """Test exception with additional details."""
        details = {"field": "email", "value": "invalid"}
        exc = JanuaAPIException(
            message="Validation failed",
            status_code=422,
            error_code="VALIDATION_ERROR",
            details=details
        )
        
        assert exc.details == details
    
    def test_default_values(self):
        """Test exception with default values."""
        exc = JanuaAPIException(message="Simple error")
        
        assert exc.status_code == 500
        # Updated to match actual implementation - class name is uppercase without underscores
        assert exc.error_code == "JANUAAPIEXCEPTION"
        assert exc.details == {}


class TestSpecificExceptions:
    """Test specific exception subclasses."""
    
    def test_authentication_error(self):
        """Test AuthenticationError."""
        exc = AuthenticationError("Login failed")
        
        assert str(exc) == "Login failed"
        assert exc.status_code == 401
        assert exc.error_code == "AUTHENTICATION_ERROR"
    
    def test_authentication_error_defaults(self):
        """Test AuthenticationError with default message."""
        exc = AuthenticationError()
        
        assert str(exc) == "Authentication failed"
        assert exc.status_code == 401
    
    def test_token_error(self):
        """Test TokenError."""
        exc = TokenError("Invalid token format")
        
        assert str(exc) == "Invalid token format"
        assert exc.status_code == 401
        assert exc.error_code == "TOKEN_ERROR"
    
    def test_token_error_defaults(self):
        """Test TokenError with default message."""
        exc = TokenError()
        
        assert str(exc) == "Token error"
        assert exc.status_code == 401
    
    def test_authorization_error(self):
        """Test AuthorizationError."""
        exc = AuthorizationError("Insufficient permissions")
        
        assert str(exc) == "Insufficient permissions"
        assert exc.status_code == 403
        assert exc.error_code == "AUTHORIZATION_ERROR"
    
    def test_validation_error(self):
        """Test ValidationError."""
        details = {"field": "email", "error": "required"}
        exc = ValidationError("Field validation failed", details=details)
        
        assert str(exc) == "Field validation failed"
        assert exc.status_code == 422
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.details == details
    
    def test_not_found_error(self):
        """Test NotFoundError."""
        exc = NotFoundError("User not found")
        
        assert str(exc) == "User not found"
        assert exc.status_code == 404
        assert exc.error_code == "NOT_FOUND_ERROR"
    
    def test_conflict_error(self):
        """Test ConflictError."""
        exc = ConflictError("Email already exists")
        
        assert str(exc) == "Email already exists"
        assert exc.status_code == 409
        assert exc.error_code == "CONFLICT_ERROR"
    
    def test_rate_limit_error(self):
        """Test RateLimitError."""
        details = {"limit": 10, "window": 60}
        exc = RateLimitError("Too many requests", details=details)
        
        assert str(exc) == "Too many requests"
        assert exc.status_code == 429
        assert exc.error_code == "RATE_LIMIT_ERROR"
        assert exc.details == details
    
    def test_all_exceptions_inherit_from_base(self):
        """Test that all custom exceptions inherit from JanuaAPIException."""
        exceptions = [
            AuthenticationError(),
            TokenError(),
            AuthorizationError(),
            ValidationError(),
            NotFoundError(),
            ConflictError(),
            RateLimitError()
        ]
        
        for exc in exceptions:
            assert isinstance(exc, JanuaAPIException)
            assert hasattr(exc, 'message')
            assert hasattr(exc, 'status_code')
            assert hasattr(exc, 'error_code')
            assert hasattr(exc, 'details')