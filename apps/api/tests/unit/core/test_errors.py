"""
Comprehensive Error Handling Test Suite
Tests for API exceptions, error responses, and exception handlers
"""

import pytest
from unittest.mock import MagicMock
from fastapi import status
from fastapi.exceptions import RequestValidationError

from app.core.errors import (
    ErrorDetail,
    ErrorResponse,
    JanuaAPIException,
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
    ValidationError,
    RateLimitError,
    InternalServerError,
    ServiceUnavailableError,
    janua_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
    report_to_sentry,
)

pytestmark = pytest.mark.asyncio


class TestErrorDetailModel:
    """Test ErrorDetail Pydantic model."""

    def test_error_detail_with_all_fields(self):
        """Test ErrorDetail with all fields."""
        detail = ErrorDetail(
            field="email",
            message="Invalid email format",
            code="INVALID_EMAIL"
        )

        assert detail.field == "email"
        assert detail.message == "Invalid email format"
        assert detail.code == "INVALID_EMAIL"

    def test_error_detail_message_only(self):
        """Test ErrorDetail with only required field."""
        detail = ErrorDetail(message="Error occurred")

        assert detail.message == "Error occurred"
        assert detail.field is None
        assert detail.code is None

    def test_error_detail_serialization(self):
        """Test ErrorDetail serializes correctly."""
        detail = ErrorDetail(field="name", message="Required")
        data = detail.dict()

        assert "message" in data
        assert data["message"] == "Required"


class TestErrorResponseModel:
    """Test ErrorResponse Pydantic model."""

    def test_error_response_full(self):
        """Test ErrorResponse with all fields."""
        response = ErrorResponse(
            error="Bad Request",
            message="Invalid input",
            status_code=400,
            timestamp="2024-01-15T10:00:00",
            path="/api/users",
            request_id="req-123",
            details=[ErrorDetail(field="email", message="Invalid")],
            error_code="INVALID_INPUT"
        )

        assert response.error == "Bad Request"
        assert response.message == "Invalid input"
        assert response.status_code == 400
        assert len(response.details) == 1

    def test_error_response_required_only(self):
        """Test ErrorResponse with required fields only."""
        response = ErrorResponse(
            error="Error",
            message="Something went wrong",
            status_code=500,
            timestamp="2024-01-15T10:00:00"
        )

        assert response.error == "Error"
        assert response.path is None
        assert response.details is None


class TestJanuaAPIException:
    """Test base JanuaAPIException."""

    def test_exception_creation(self):
        """Test JanuaAPIException creation."""
        exc = JanuaAPIException(
            status_code=400,
            error="Bad Request",
            message="Invalid data",
            error_code="INVALID_DATA"
        )

        assert exc.status_code == 400
        assert exc.error == "Bad Request"
        assert exc.message == "Invalid data"
        assert exc.error_code == "INVALID_DATA"

    def test_exception_with_details(self):
        """Test JanuaAPIException with details."""
        details = [ErrorDetail(field="name", message="Required")]
        exc = JanuaAPIException(
            status_code=422,
            error="Validation Error",
            message="Validation failed",
            details=details
        )

        assert exc.details == details

    def test_exception_with_headers(self):
        """Test JanuaAPIException with custom headers."""
        exc = JanuaAPIException(
            status_code=429,
            error="Rate Limited",
            message="Too many requests",
            headers={"Retry-After": "60"}
        )

        assert exc.headers == {"Retry-After": "60"}

    def test_exception_inherits_from_httpexception(self):
        """Test JanuaAPIException inherits from HTTPException."""
        exc = JanuaAPIException(
            status_code=400,
            error="Error",
            message="Message"
        )

        # HTTPException properties
        assert exc.detail == "Message"


class TestBadRequestError:
    """Test BadRequestError exception."""

    def test_bad_request_default(self):
        """Test BadRequestError with default message."""
        exc = BadRequestError()

        assert exc.status_code == status.HTTP_400_BAD_REQUEST
        assert exc.error == "Bad Request"
        assert exc.message == "Bad request"

    def test_bad_request_custom_message(self):
        """Test BadRequestError with custom message."""
        exc = BadRequestError(message="Invalid JSON")

        assert exc.message == "Invalid JSON"


class TestUnauthorizedError:
    """Test UnauthorizedError exception."""

    def test_unauthorized_default(self):
        """Test UnauthorizedError with default message."""
        exc = UnauthorizedError()

        assert exc.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc.error == "Unauthorized"
        assert exc.message == "Authentication required"
        assert exc.error_code == "AUTH_REQUIRED"

    def test_unauthorized_custom_message(self):
        """Test UnauthorizedError with custom message."""
        exc = UnauthorizedError(message="Token expired")

        assert exc.message == "Token expired"


class TestForbiddenError:
    """Test ForbiddenError exception."""

    def test_forbidden_default(self):
        """Test ForbiddenError with default message."""
        exc = ForbiddenError()

        assert exc.status_code == status.HTTP_403_FORBIDDEN
        assert exc.error == "Forbidden"
        assert exc.message == "Access forbidden"
        assert exc.error_code == "ACCESS_DENIED"

    def test_forbidden_custom_message(self):
        """Test ForbiddenError with custom message."""
        exc = ForbiddenError(message="Admin access required")

        assert exc.message == "Admin access required"


class TestNotFoundError:
    """Test NotFoundError exception."""

    def test_not_found_default(self):
        """Test NotFoundError with default resource."""
        exc = NotFoundError()

        assert exc.status_code == status.HTTP_404_NOT_FOUND
        assert exc.error == "Not Found"
        assert exc.message == "Resource not found"
        assert exc.error_code == "RESOURCE_NOT_FOUND"

    def test_not_found_custom_resource(self):
        """Test NotFoundError with custom resource."""
        exc = NotFoundError(resource="User")

        assert exc.message == "User not found"


class TestConflictError:
    """Test ConflictError exception."""

    def test_conflict_default(self):
        """Test ConflictError with default message."""
        exc = ConflictError()

        assert exc.status_code == status.HTTP_409_CONFLICT
        assert exc.error == "Conflict"
        assert exc.message == "Resource conflict"
        assert exc.error_code == "RESOURCE_CONFLICT"

    def test_conflict_custom_message(self):
        """Test ConflictError with custom message."""
        exc = ConflictError(message="Email already exists")

        assert exc.message == "Email already exists"


class TestValidationError:
    """Test ValidationError exception."""

    def test_validation_default(self):
        """Test ValidationError with default message."""
        exc = ValidationError()

        assert exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert exc.error == "Validation Error"
        assert exc.message == "Validation failed"
        assert exc.error_code == "VALIDATION_FAILED"

    def test_validation_with_details(self):
        """Test ValidationError with field details."""
        details = [
            ErrorDetail(field="email", message="Invalid email"),
            ErrorDetail(field="password", message="Too short")
        ]
        exc = ValidationError(message="Input validation failed", details=details)

        assert exc.details == details
        assert len(exc.details) == 2


class TestRateLimitError:
    """Test RateLimitError exception."""

    def test_rate_limit_default(self):
        """Test RateLimitError with default message."""
        exc = RateLimitError()

        assert exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert exc.error == "Rate Limit Exceeded"
        assert exc.message == "Rate limit exceeded"
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"

    def test_rate_limit_with_retry_after(self):
        """Test RateLimitError with retry_after header."""
        exc = RateLimitError(retry_after=60)

        assert exc.headers == {"Retry-After": "60"}

    def test_rate_limit_without_retry_after(self):
        """Test RateLimitError without retry_after header."""
        exc = RateLimitError()

        assert exc.headers is None


class TestInternalServerError:
    """Test InternalServerError exception."""

    def test_internal_error_default(self):
        """Test InternalServerError with default message."""
        exc = InternalServerError()

        assert exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc.error == "Internal Server Error"
        assert exc.message == "An internal error occurred"
        assert exc.error_code == "INTERNAL_ERROR"


class TestServiceUnavailableError:
    """Test ServiceUnavailableError exception."""

    def test_service_unavailable_default(self):
        """Test ServiceUnavailableError with default message."""
        exc = ServiceUnavailableError()

        assert exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert exc.error == "Service Unavailable"
        assert exc.message == "Service temporarily unavailable"
        assert exc.error_code == "SERVICE_UNAVAILABLE"

    def test_service_unavailable_with_retry_after(self):
        """Test ServiceUnavailableError with retry_after header."""
        exc = ServiceUnavailableError(retry_after=300)

        assert exc.headers == {"Retry-After": "300"}


class TestJanuaExceptionHandler:
    """Test janua_exception_handler function."""

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock()
        request.url.path = "/api/v1/users"
        request.method = "POST"
        return request

    async def test_handler_returns_json_response(self, mock_request):
        """Test handler returns JSONResponse."""
        exc = BadRequestError(message="Invalid input")

        response = await janua_exception_handler(mock_request, exc)

        assert response.status_code == 400
        assert response.media_type == "application/json"

    async def test_handler_includes_error_details(self, mock_request):
        """Test handler includes error details in response."""
        exc = BadRequestError(message="Invalid input")

        response = await janua_exception_handler(mock_request, exc)
        content = response.body.decode()

        assert "Bad Request" in content
        assert "Invalid input" in content
        assert "/api/v1/users" in content

    async def test_handler_includes_request_id(self, mock_request):
        """Test handler generates and includes request_id."""
        exc = BadRequestError()

        response = await janua_exception_handler(mock_request, exc)
        content = response.body.decode()

        assert "request_id" in content

    async def test_handler_preserves_custom_headers(self, mock_request):
        """Test handler preserves custom headers from exception."""
        exc = RateLimitError(retry_after=60)

        response = await janua_exception_handler(mock_request, exc)

        assert response.headers.get("Retry-After") == "60"


class TestValidationExceptionHandler:
    """Test validation_exception_handler function."""

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock()
        request.url.path = "/api/v1/users"
        request.method = "POST"
        return request

    @pytest.fixture
    def mock_validation_error(self):
        """Create mock RequestValidationError."""
        error = MagicMock(spec=RequestValidationError)
        error.errors.return_value = [
            {
                "loc": ("body", "email"),
                "msg": "Invalid email address",
                "type": "value_error.email"
            }
        ]
        return error

    async def test_handler_returns_422(self, mock_request, mock_validation_error):
        """Test handler returns 422 status code."""
        response = await validation_exception_handler(mock_request, mock_validation_error)

        assert response.status_code == 422

    async def test_handler_parses_validation_errors(self, mock_request, mock_validation_error):
        """Test handler parses validation errors into details."""
        response = await validation_exception_handler(mock_request, mock_validation_error)
        content = response.body.decode()

        assert "body.email" in content
        assert "Invalid email address" in content


class TestGenericExceptionHandler:
    """Test generic_exception_handler function."""

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock()
        request.url.path = "/api/v1/users"
        request.method = "GET"
        request.app.state = MagicMock()
        request.app.state.debug = False
        return request

    async def test_handler_returns_500(self, mock_request):
        """Test handler returns 500 for unhandled exceptions."""
        exc = Exception("Something went wrong")

        response = await generic_exception_handler(mock_request, exc)

        assert response.status_code == 500

    async def test_handler_hides_details_in_production(self, mock_request):
        """Test handler hides exception details in production."""
        mock_request.app.state.debug = False
        exc = Exception("Internal database error")

        response = await generic_exception_handler(mock_request, exc)
        content = response.body.decode()

        assert "Internal database error" not in content
        assert "unexpected error" in content

    async def test_handler_shows_details_in_debug(self, mock_request):
        """Test handler shows exception details in debug mode."""
        mock_request.app.state.debug = True
        exc = ValueError("Invalid value")

        response = await generic_exception_handler(mock_request, exc)
        content = response.body.decode()

        assert "ValueError" in content
        assert "Invalid value" in content


class TestReportToSentry:
    """Test report_to_sentry function."""

    def test_report_without_sentry_installed(self):
        """Test report_to_sentry handles missing sentry_sdk gracefully."""
        error = Exception("Test error")

        # Should not raise even if sentry_sdk not installed
        report_to_sentry(error)

    def test_report_with_context(self):
        """Test report_to_sentry accepts context."""
        error = Exception("Test error")
        context = {"user_id": "123", "endpoint": "/api/test"}

        # Should not raise
        report_to_sentry(error, context=context)


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_all_exceptions_inherit_from_base(self):
        """Test all custom exceptions inherit from JanuaAPIException."""
        exceptions = [
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

        for exc_class in exceptions:
            assert issubclass(exc_class, JanuaAPIException)

    def test_all_exceptions_have_status_codes(self):
        """Test all exceptions have appropriate status codes."""
        expected_status = {
            BadRequestError: 400,
            UnauthorizedError: 401,
            ForbiddenError: 403,
            NotFoundError: 404,
            ConflictError: 409,
            ValidationError: 422,
            RateLimitError: 429,
            InternalServerError: 500,
            ServiceUnavailableError: 503,
        }

        for exc_class, expected_code in expected_status.items():
            exc = exc_class()
            assert exc.status_code == expected_code, f"{exc_class.__name__} has wrong status code"
