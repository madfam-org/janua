"""
Comprehensive tests for app.core.errors module
"""

from fastapi import status
from app.core.errors import (
    JanuaAPIException,
    ErrorDetail,
    ErrorResponse,
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
    ValidationError,
    RateLimitError,
    InternalServerError,
    ServiceUnavailableError,
)


class TestErrorDetail:
    """Test ErrorDetail model"""

    def test_error_detail_creation(self):
        """Test basic ErrorDetail creation"""
        detail = ErrorDetail(message="Test error")
        assert detail.message == "Test error"
        assert detail.field is None
        assert detail.code is None

    def test_error_detail_with_field_and_code(self):
        """Test ErrorDetail with field and code"""
        detail = ErrorDetail(field="email", message="Invalid email format", code="INVALID_EMAIL")
        assert detail.field == "email"
        assert detail.message == "Invalid email format"
        assert detail.code == "INVALID_EMAIL"


class TestErrorResponse:
    """Test ErrorResponse model"""

    def test_error_response_creation(self):
        """Test basic ErrorResponse creation"""
        response = ErrorResponse(
            error="Test Error",
            message="This is a test",
            status_code=400,
            timestamp="2023-01-01T00:00:00Z",
        )
        assert response.error == "Test Error"
        assert response.message == "This is a test"
        assert response.status_code == 400
        assert response.timestamp == "2023-01-01T00:00:00Z"

    def test_error_response_with_details(self):
        """Test ErrorResponse with details"""
        details = [ErrorDetail(field="email", message="Required")]
        response = ErrorResponse(
            error="Validation Error",
            message="Validation failed",
            status_code=422,
            timestamp="2023-01-01T00:00:00Z",
            details=details,
        )
        assert len(response.details) == 1
        assert response.details[0].field == "email"


class TestJanuaAPIException:
    """Test JanuaAPIException base class"""

    def test_janua_api_exception_creation(self):
        """Test basic JanuaAPIException creation"""
        exc = JanuaAPIException(status_code=400, error="Test Error", message="Test message")
        assert exc.status_code == 400
        assert exc.error == "Test Error"
        assert exc.message == "Test message"
        assert exc.detail == "Test message"

    def test_janua_api_exception_with_details(self):
        """Test JanuaAPIException with error details"""
        details = [ErrorDetail(field="email", message="Required")]
        exc = JanuaAPIException(
            status_code=422,
            error="Validation Error",
            message="Validation failed",
            error_code="VALIDATION_001",
            details=details,
        )
        assert exc.error_code == "VALIDATION_001"
        assert len(exc.details) == 1

    def test_janua_api_exception_inheritance(self):
        """Test JanuaAPIException inherits from HTTPException"""
        from fastapi import HTTPException

        exc = JanuaAPIException(status_code=400, error="Test", message="Test")
        assert isinstance(exc, HTTPException)


class TestBadRequestError:
    """Test BadRequestError class"""

    def test_bad_request_error_default(self):
        """Test BadRequestError with default message"""
        error = BadRequestError()
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.error == "Bad Request"
        assert error.message == "Bad request"

    def test_bad_request_error_custom_message(self):
        """Test BadRequestError with custom message"""
        error = BadRequestError("Invalid input format")
        assert error.status_code == status.HTTP_400_BAD_REQUEST
        assert error.error == "Bad Request"
        assert error.message == "Invalid input format"


class TestUnauthorizedError:
    """Test UnauthorizedError class"""

    def test_unauthorized_error_default(self):
        """Test UnauthorizedError with default message"""
        error = UnauthorizedError()
        assert error.status_code == status.HTTP_401_UNAUTHORIZED
        assert error.error == "Unauthorized"
        assert error.message == "Authentication required"
        assert error.error_code == "AUTH_REQUIRED"

    def test_unauthorized_error_custom_message(self):
        """Test UnauthorizedError with custom message"""
        error = UnauthorizedError("Invalid credentials")
        assert error.status_code == status.HTTP_401_UNAUTHORIZED
        assert error.message == "Invalid credentials"


class TestForbiddenError:
    """Test ForbiddenError class"""

    def test_forbidden_error_default(self):
        """Test ForbiddenError with default message"""
        error = ForbiddenError()
        assert error.status_code == status.HTTP_403_FORBIDDEN
        assert error.error == "Forbidden"
        assert error.message == "Access forbidden"
        assert error.error_code == "ACCESS_DENIED"

    def test_forbidden_error_custom_message(self):
        """Test ForbiddenError with custom message"""
        error = ForbiddenError("Insufficient permissions")
        assert error.status_code == status.HTTP_403_FORBIDDEN
        assert error.message == "Insufficient permissions"


class TestNotFoundError:
    """Test NotFoundError class"""

    def test_not_found_error_default(self):
        """Test NotFoundError with default resource"""
        error = NotFoundError()
        assert error.status_code == status.HTTP_404_NOT_FOUND
        assert error.error == "Not Found"
        assert error.message == "Resource not found"
        assert error.error_code == "RESOURCE_NOT_FOUND"

    def test_not_found_error_custom_resource(self):
        """Test NotFoundError with custom resource"""
        error = NotFoundError(resource="User")
        assert error.status_code == status.HTTP_404_NOT_FOUND
        assert error.message == "User not found"


class TestConflictError:
    """Test ConflictError class"""

    def test_conflict_error_default(self):
        """Test ConflictError with default message"""
        error = ConflictError()
        assert error.status_code == status.HTTP_409_CONFLICT
        assert error.error == "Conflict"
        assert error.message == "Resource conflict"
        assert error.error_code == "RESOURCE_CONFLICT"

    def test_conflict_error_custom_message(self):
        """Test ConflictError with custom message"""
        error = ConflictError("Email already exists")
        assert error.status_code == status.HTTP_409_CONFLICT
        assert error.message == "Email already exists"


class TestValidationError:
    """Test ValidationError class"""

    def test_validation_error_default(self):
        """Test ValidationError with default message"""
        error = ValidationError()
        assert error.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert error.error == "Validation Error"
        assert error.message == "Validation failed"
        assert error.error_code == "VALIDATION_FAILED"

    def test_validation_error_with_details(self):
        """Test ValidationError with field details"""
        details = [
            ErrorDetail(field="email", message="Invalid format"),
            ErrorDetail(field="password", message="Too short"),
        ]
        error = ValidationError("Multiple validation errors", details=details)
        assert error.message == "Multiple validation errors"
        assert len(error.details) == 2
        assert error.details[0].field == "email"


class TestRateLimitError:
    """Test RateLimitError class"""

    def test_rate_limit_error_default(self):
        """Test RateLimitError with default message"""
        error = RateLimitError()
        assert error.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert error.error == "Rate Limit Exceeded"
        assert error.message == "Rate limit exceeded"
        assert error.error_code == "RATE_LIMIT_EXCEEDED"

    def test_rate_limit_error_with_retry_after(self):
        """Test RateLimitError with retry after header"""
        error = RateLimitError("Too many requests", retry_after=60)
        assert error.message == "Too many requests"
        assert error.headers == {"Retry-After": "60"}

    def test_rate_limit_error_no_retry_after(self):
        """Test RateLimitError without retry after"""
        error = RateLimitError()
        assert error.headers is None


class TestInternalServerError:
    """Test InternalServerError class"""

    def test_internal_server_error_default(self):
        """Test InternalServerError with default message"""
        error = InternalServerError()
        assert error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert error.error == "Internal Server Error"
        assert error.message == "An internal error occurred"
        assert error.error_code == "INTERNAL_ERROR"

    def test_internal_server_error_custom_message(self):
        """Test InternalServerError with custom message"""
        error = InternalServerError("Database connection failed")
        assert error.message == "Database connection failed"


class TestServiceUnavailableError:
    """Test ServiceUnavailableError class"""

    def test_service_unavailable_error_default(self):
        """Test ServiceUnavailableError with default message"""
        error = ServiceUnavailableError()
        assert error.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert error.error == "Service Unavailable"
        assert error.message == "Service temporarily unavailable"
        assert error.error_code == "SERVICE_UNAVAILABLE"

    def test_service_unavailable_error_with_retry_after(self):
        """Test ServiceUnavailableError with retry after header"""
        error = ServiceUnavailableError("Maintenance mode", retry_after=3600)
        assert error.message == "Maintenance mode"
        assert error.headers == {"Retry-After": "3600"}


class TestErrorHierarchy:
    """Test error class inheritance and relationships"""

    def test_all_errors_inherit_from_janua_api_exception(self):
        """Test that all error classes inherit from JanuaAPIException"""
        error_classes = [
            BadRequestError,
            UnauthorizedError,
            ForbiddenError,
            NotFoundError,
            ConflictError,
            ValidationError,
            RateLimitError,
            InternalServerError,
            ServiceUnavailableError,
        ]

        for error_class in error_classes:
            error_instance = error_class()
            assert isinstance(error_instance, JanuaAPIException)

    def test_all_errors_inherit_from_http_exception(self):
        """Test that all error classes inherit from HTTPException"""
        from fastapi import HTTPException

        error_classes = [
            BadRequestError,
            UnauthorizedError,
            ForbiddenError,
            NotFoundError,
            ConflictError,
            ValidationError,
            RateLimitError,
            InternalServerError,
            ServiceUnavailableError,
        ]

        for error_class in error_classes:
            error_instance = error_class()
            assert isinstance(error_instance, HTTPException)

    def test_status_codes_are_correct(self):
        """Test that error classes have correct HTTP status codes"""
        status_mapping = {
            BadRequestError: status.HTTP_400_BAD_REQUEST,
            UnauthorizedError: status.HTTP_401_UNAUTHORIZED,
            ForbiddenError: status.HTTP_403_FORBIDDEN,
            NotFoundError: status.HTTP_404_NOT_FOUND,
            ConflictError: status.HTTP_409_CONFLICT,
            ValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
            RateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,
            InternalServerError: status.HTTP_500_INTERNAL_SERVER_ERROR,
            ServiceUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
        }

        for error_class, expected_status in status_mapping.items():
            error_instance = error_class()
            assert error_instance.status_code == expected_status


class TestErrorEdgeCases:
    """Test edge cases and error scenarios"""

    def test_error_with_none_values(self):
        """Test error creation with None values"""
        error = JanuaAPIException(
            status_code=400, error="Test", message="Test", error_code=None, details=None
        )
        assert error.error_code is None
        assert error.details is None

    def test_error_with_empty_details(self):
        """Test error creation with empty details list"""
        error = ValidationError(details=[])
        assert error.details == []

    def test_error_chaining_compatibility(self):
        """Test that errors work with exception chaining"""
        original_error = ValueError("Original error")
        try:
            raise original_error
        except ValueError as e:
            chained_error = InternalServerError("Wrapped error")
            chained_error.__cause__ = e
            assert chained_error.__cause__ is original_error

    def test_error_string_representation(self):
        """Test error string representation"""
        error = BadRequestError("Test message")
        error_str = str(error)
        assert "Test message" in error_str
