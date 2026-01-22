"""
Standardized API Error Handling System
"""
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from datetime import datetime
import traceback
import uuid
import structlog

logger = structlog.get_logger()


class ErrorDetail(BaseModel):
    """Detailed error information"""

    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standardized error response format"""

    error: str
    message: str
    status_code: int
    timestamp: str
    path: Optional[str] = None
    request_id: Optional[str] = None
    details: Optional[List[ErrorDetail]] = None
    error_code: Optional[str] = None


class JanuaAPIException(HTTPException):
    """Base exception for all Janua API errors"""

    def __init__(
        self,
        status_code: int,
        error: str,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[List[ErrorDetail]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.error = error
        self.message = message
        self.error_code = error_code
        self.details = details


# Predefined API Exceptions
class BadRequestError(JanuaAPIException):
    """400 Bad Request"""

    def __init__(self, message: str = "Bad request", **kwargs):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST, error="Bad Request", message=message, **kwargs
        )


class UnauthorizedError(JanuaAPIException):
    """401 Unauthorized"""

    def __init__(self, message: str = "Authentication required", **kwargs):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error="Unauthorized",
            message=message,
            error_code="AUTH_REQUIRED",
            **kwargs,
        )


class ForbiddenError(JanuaAPIException):
    """403 Forbidden"""

    def __init__(self, message: str = "Access forbidden", **kwargs):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error="Forbidden",
            message=message,
            error_code="ACCESS_DENIED",
            **kwargs,
        )


class NotFoundError(JanuaAPIException):
    """404 Not Found"""

    def __init__(self, resource: str = "Resource", **kwargs):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error="Not Found",
            message=f"{resource} not found",
            error_code="RESOURCE_NOT_FOUND",
            **kwargs,
        )


class ConflictError(JanuaAPIException):
    """409 Conflict"""

    def __init__(self, message: str = "Resource conflict", **kwargs):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error="Conflict",
            message=message,
            error_code="RESOURCE_CONFLICT",
            **kwargs,
        )


class ValidationError(JanuaAPIException):
    """422 Validation Error"""

    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[List[ErrorDetail]] = None,
        **kwargs,
    ):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error="Validation Error",
            message=message,
            error_code="VALIDATION_FAILED",
            details=details,
            **kwargs,
        )


class RateLimitError(JanuaAPIException):
    """429 Too Many Requests"""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: Optional[int] = None, **kwargs
    ):
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error="Rate Limit Exceeded",
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            headers=headers,
            **kwargs,
        )


class InternalServerError(JanuaAPIException):
    """500 Internal Server Error"""

    def __init__(self, message: str = "An internal error occurred", **kwargs):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="Internal Server Error",
            message=message,
            error_code="INTERNAL_ERROR",
            **kwargs,
        )


class ServiceUnavailableError(JanuaAPIException):
    """503 Service Unavailable"""

    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error="Service Unavailable",
            message=message,
            error_code="SERVICE_UNAVAILABLE",
            headers=headers,
            **kwargs,
        )


# Error Handlers
async def janua_exception_handler(request: Request, exc: JanuaAPIException) -> JSONResponse:
    """Handler for JanuaAPIException"""
    request_id = str(uuid.uuid4())

    # Log the error
    logger.error(
        "API error occurred",
        error=exc.error,
        message=exc.message,
        status_code=exc.status_code,
        error_code=exc.error_code,
        path=request.url.path,
        method=request.method,
        request_id=request_id,
    )

    # Create error response
    error_response = ErrorResponse(
        error=exc.error,
        message=exc.message,
        status_code=exc.status_code,
        timestamp=datetime.utcnow().isoformat(),
        path=request.url.path,
        request_id=request_id,
        details=exc.details,
        error_code=exc.error_code,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.dict(exclude_none=True),
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handler for validation errors"""
    request_id = str(uuid.uuid4())

    # Parse validation errors
    details = []
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error["loc"])
        details.append(ErrorDetail(field=field_path, message=error["msg"], code=error["type"]))

    # Log the validation error
    logger.warning(
        "Validation error",
        path=request.url.path,
        method=request.method,
        errors=exc.errors(),
        request_id=request_id,
    )

    # Create error response
    error_response = ErrorResponse(
        error="Validation Error",
        message="Request validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        timestamp=datetime.utcnow().isoformat(),
        path=request.url.path,
        request_id=request_id,
        details=details,
        error_code="VALIDATION_FAILED",
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.dict(exclude_none=True),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unexpected exceptions"""
    request_id = str(uuid.uuid4())

    # Log the full exception
    logger.exception(
        "Unhandled exception occurred",
        path=request.url.path,
        method=request.method,
        request_id=request_id,
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        traceback=traceback.format_exc(),
    )

    # Create generic error response (don't expose internal details in production)
    message = "An unexpected error occurred"
    if hasattr(request.app.state, "debug") and request.app.state.debug:
        message = f"{type(exc).__name__}: {str(exc)}"

    error_response = ErrorResponse(
        error="Internal Server Error",
        message=message,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        timestamp=datetime.utcnow().isoformat(),
        path=request.url.path,
        request_id=request_id,
        error_code="INTERNAL_ERROR",
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.dict(exclude_none=True),
    )


# Error tracking integration
def report_to_sentry(error: Exception, context: Dict[str, Any] = None):
    """Report error to Sentry if configured"""
    try:
        import sentry_sdk

        if sentry_sdk.Hub.current.client:
            with sentry_sdk.push_scope() as scope:
                if context:
                    for key, value in context.items():
                        scope.set_extra(key, value)
                sentry_sdk.capture_exception(error)
    except ImportError:
        pass  # Sentry not installed
    except Exception as e:
        logger.error("Failed to report to Sentry", error=str(e))
