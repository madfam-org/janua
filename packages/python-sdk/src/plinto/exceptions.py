class PlintoAPIError(Exception):
    """Base exception for Plinto API errors"""
    
    def __init__(
        self, 
        message: str, 
        code: str = "UNKNOWN_ERROR", 
        status_code: int = None, 
        details: dict = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class AuthenticationError(PlintoAPIError):
    """Raised when authentication fails"""
    
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, code="AUTHENTICATION_ERROR", status_code=401, **kwargs)


class ValidationError(PlintoAPIError):
    """Raised when request validation fails"""
    
    def __init__(self, message: str = "Validation failed", **kwargs):
        super().__init__(message, code="VALIDATION_ERROR", status_code=400, **kwargs)


class NotFoundError(PlintoAPIError):
    """Raised when a resource is not found"""
    
    def __init__(self, message: str = "Resource not found", **kwargs):
        super().__init__(message, code="NOT_FOUND", status_code=404, **kwargs)


class RateLimitError(PlintoAPIError):
    """Raised when rate limit is exceeded"""
    
    def __init__(self, message: str = "Rate limit exceeded", **kwargs):
        super().__init__(message, code="RATE_LIMIT_EXCEEDED", status_code=429, **kwargs)


class PermissionError(PlintoAPIError):
    """Raised when permission is denied"""
    
    def __init__(self, message: str = "Permission denied", **kwargs):
        super().__init__(message, code="PERMISSION_DENIED", status_code=403, **kwargs)


class ConflictError(PlintoAPIError):
    """Raised when there's a conflict with the current state"""
    
    def __init__(self, message: str = "Conflict with current state", **kwargs):
        super().__init__(message, code="CONFLICT", status_code=409, **kwargs)


class ServerError(PlintoAPIError):
    """Raised when the server encounters an error"""
    
    def __init__(self, message: str = "Internal server error", **kwargs):
        super().__init__(message, code="SERVER_ERROR", status_code=500, **kwargs)