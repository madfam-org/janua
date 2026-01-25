"""
Comprehensive API Error Handling Middleware
Standardized error responses with monitoring integration
"""

import time
import traceback
import uuid
from typing import Any, Dict, Optional

import structlog
from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Import unified exception system
from app.core.exceptions import JanuaAPIException

logger = structlog.get_logger()


class APIException(Exception):
    """Base API exception with structured error handling"""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(APIException):
    """Authentication-related errors"""

    def __init__(self, message: str = "Authentication failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_FAILED",
            details=details,
        )


class AuthorizationError(APIException):
    """Authorization-related errors"""

    def __init__(self, message: str = "Access denied", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="ACCESS_DENIED",
            details=details,
        )


class ValidationError(APIException):
    """Validation-related errors"""

    def __init__(self, message: str = "Validation failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            details=details,
        )


class BusinessLogicError(APIException):
    """Business logic errors"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="BUSINESS_LOGIC_ERROR",
            details=details,
        )


class DatabaseError(APIException):
    """Database-related errors"""

    def __init__(self, message: str = "Database operation failed", details: Optional[Dict] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="DATABASE_ERROR",
            details=details,
        )


class ExternalServiceError(APIException):
    """External service errors"""

    def __init__(
        self, message: str = "External service unavailable", details: Optional[Dict] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="EXTERNAL_SERVICE_ERROR",
            details=details,
        )


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Comprehensive error handling middleware with monitoring"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Generate or retrieve request ID for tracing (UUID for distributed tracing)
        request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

        # Add request context
        logger_context = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "client_ip": self._get_client_ip(request),
        }

        try:
            response = await call_next(request)

            # Log successful requests
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "Request completed",
                **logger_context,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            return response

        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000

            # Create error response
            error_response = await self._create_error_response(exc, request_id)

            # Log error with context
            logger.error(
                "Request failed",
                **logger_context,
                error_type=type(exc).__name__,
                error_message=str(exc),
                status_code=error_response.status_code,
                duration_ms=round(duration_ms, 2),
                traceback=traceback.format_exc() if error_response.status_code >= 500 else None,
            )

            return error_response

    async def _create_error_response(self, exc: Exception, request_id: int) -> JSONResponse:
        """Create standardized error response"""

        # Handle unified Janua exceptions (from app.core.exceptions)
        if isinstance(exc, JanuaAPIException):
            error_data = {
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": request_id,
                    "timestamp": time.time(),
                }
            }
            return JSONResponse(status_code=exc.status_code, content=error_data)

        # Handle legacy APIException (from this file) for backward compatibility
        elif isinstance(exc, APIException):
            # Custom API exceptions
            error_data = {
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                    "request_id": request_id,
                    "timestamp": time.time(),
                }
            }
            return JSONResponse(status_code=exc.status_code, content=error_data)

        elif isinstance(exc, HTTPException):
            # FastAPI HTTP exceptions
            error_data = {
                "error": {
                    "code": "HTTP_ERROR",
                    "message": exc.detail,
                    "request_id": request_id,
                    "timestamp": time.time(),
                }
            }
            return JSONResponse(status_code=exc.status_code, content=error_data)

        elif isinstance(exc, RequestValidationError):
            # Pydantic validation errors
            validation_errors = []
            for error in exc.errors():
                validation_errors.append(
                    {
                        "field": ".".join(str(loc) for loc in error["loc"]),
                        "message": error["msg"],
                        "type": error["type"],
                    }
                )

            error_data = {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": {"validation_errors": validation_errors},
                    "request_id": request_id,
                    "timestamp": time.time(),
                }
            }
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_data
            )

        elif isinstance(exc, SQLAlchemyError):
            # Database errors
            error_data = {
                "error": {
                    "code": "DATABASE_ERROR",
                    "message": "Database operation failed",
                    "request_id": request_id,
                    "timestamp": time.time(),
                }
            }
            return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=error_data)

        else:
            # Unexpected errors
            error_data = {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "request_id": request_id,
                    "timestamp": time.time(),
                }
            }
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=error_data
            )

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP with proxy support"""
        # Check for forwarded headers (common with load balancers)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct connection
        return request.client.host if request.client else "unknown"


# Helper function to get request ID
def _get_request_id(request: Request) -> str:
    """Get or generate a request ID for tracing"""
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


# Custom exception handlers for FastAPI
async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
    """Handler for custom API exceptions"""
    error_data = {
        "error": {
            "code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "request_id": _get_request_id(request),
            "timestamp": time.time(),
        }
    }
    return JSONResponse(status_code=exc.status_code, content=error_data)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handler for validation errors"""
    validation_errors = []
    for error in exc.errors():
        validation_errors.append(
            {
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
        )

    error_data = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {"validation_errors": validation_errors},
            "request_id": _get_request_id(request),
            "timestamp": time.time(),
        }
    }
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_data)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handler for HTTP exceptions"""
    error_data = {
        "error": {
            "code": "HTTP_ERROR",
            "message": exc.detail,
            "request_id": _get_request_id(request),
            "timestamp": time.time(),
        }
    }
    return JSONResponse(status_code=exc.status_code, content=error_data)


async def janua_exception_handler(request: Request, exc: JanuaAPIException) -> JSONResponse:
    """Handler for unified Janua exceptions"""
    request_id = _get_request_id(request)
    error_data = {
        "error": {
            "code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "request_id": request_id,
            "timestamp": time.time(),
        }
    }

    # Log the exception with context
    logger.error(
        "Janua exception occurred",
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        status_code=exc.status_code,
        request_id=request_id,
        path=str(request.url),
    )

    return JSONResponse(status_code=exc.status_code, content=error_data)
