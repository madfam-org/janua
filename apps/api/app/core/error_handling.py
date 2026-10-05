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
from fastapi.responses import HTMLResponse, JSONResponse, Response
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


# Seconds a client should wait before retrying when the shared state store is
# unavailable. Short: the breaker probes Redis again well within this window.
STATE_STORE_RETRY_AFTER_SECONDS = 5

STATE_STORE_UNAVAILABLE_MESSAGE = (
    "Sign-in is temporarily unavailable. Please try again in a few seconds."
)

_STATE_STORE_UNAVAILABLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Temporarily unavailable - Janua</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #f5f5f7; color: #333; display: flex; align-items: center;
               justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }
        .box { background: white; border-radius: 12px; padding: 32px; max-width: 420px;
               box-shadow: 0 8px 30px rgba(0,0,0,0.12); }
        h1 { font-size: 20px; margin: 0 0 12px; }
        p { font-size: 14px; line-height: 1.5; color: #555; margin: 0 0 8px; }
    </style>
</head>
<body>
    <div class="box">
        <h1>Sign-in is temporarily unavailable</h1>
        <p>Nothing was changed. Please wait a few seconds, then go back and try again.</p>
    </div>
</body>
</html>
"""


async def redis_unavailable_handler(request: Request, exc: Exception) -> Response:
    """Answer 503 + Retry-After when a strict Redis operation could not run.

    Raised (as `RedisUnavailableError`) only by the strict operations of
    `ResilientRedisClient`, which guard security state every replica must share
    (OAuth consent CSRF tokens, stored authorization requests, authorization
    codes). Browsers get a short human page, API clients the standard error
    envelope. Never a 403: the request may be perfectly valid; the store is not.
    """
    request_id = _get_request_id(request)
    logger.error(
        "State store unavailable; answering 503",
        path=request.url.path,
        method=request.method,
        request_id=request_id,
        error_type=type(exc).__name__,
    )
    headers = {
        "Retry-After": str(STATE_STORE_RETRY_AFTER_SECONDS),
        "Cache-Control": "no-store",
    }
    if "text/html" in request.headers.get("accept", ""):
        return HTMLResponse(
            content=_STATE_STORE_UNAVAILABLE_HTML,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers=headers,
        )
    error_data = {
        "error": {
            "code": "TEMPORARILY_UNAVAILABLE",
            "message": STATE_STORE_UNAVAILABLE_MESSAGE,
            "request_id": request_id,
            "timestamp": time.time(),
        }
    }
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=error_data, headers=headers
    )
