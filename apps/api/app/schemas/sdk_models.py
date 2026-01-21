"""
SDK-optimized response models and patterns for consistent API consumption.

This module provides standardized response patterns specifically designed
for SDK generation and consumption across multiple platforms.
"""

from typing import Any, Dict, Generic, List, Optional, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

# Type variables for generic responses
T = TypeVar('T')
DataT = TypeVar('DataT')


class APIStatus(str, Enum):
    """Standard API response status codes"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


class SDKBaseResponse(BaseModel):
    """
    Base response model for all SDK-consumable endpoints.

    Provides consistent structure that translates well to all SDK platforms:
    - TypeScript/JavaScript
    - Python
    - Go
    - Java
    - Swift (iOS)
    - Kotlin (Android)
    """
    status: APIStatus = APIStatus.SUCCESS
    message: str = "Operation completed successfully"
    request_id: Optional[str] = Field(None, description="Unique request identifier for debugging")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp in UTC")


class SDKDataResponse(SDKBaseResponse, Generic[DataT]):
    """
    Generic data response for single item returns.

    Example usage:
    - user: SDKDataResponse[UserResponse]
    - organization: SDKDataResponse[OrganizationResponse]
    """
    data: DataT = Field(..., description="Response data payload")


class SDKListResponse(SDKBaseResponse, Generic[DataT]):
    """
    Standardized list/collection response with consistent pagination.

    Works across all platforms with predictable field names and types.
    """
    data: List[DataT] = Field(..., description="List of items")
    pagination: "PaginationMetadata" = Field(..., description="Pagination information")


class PaginationMetadata(BaseModel):
    """
    Consistent pagination metadata for all list endpoints.

    SDK-friendly with clear field names and types.
    """
    total: int = Field(..., description="Total number of items across all pages", ge=0)
    page: int = Field(..., description="Current page number (1-based)", ge=1)
    per_page: int = Field(..., description="Items per page", ge=1, le=100)
    pages: int = Field(..., description="Total number of pages", ge=1)
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")
    next_page: Optional[int] = Field(None, description="Next page number if available")
    prev_page: Optional[int] = Field(None, description="Previous page number if available")


class SDKSuccessResponse(SDKBaseResponse):
    """
    Simple success response for operations that don't return data.

    Used for DELETE operations, bulk operations, etc.
    """
    operation: str = Field(..., description="Operation that was performed")
    affected_count: Optional[int] = Field(None, description="Number of items affected")


class SDKErrorResponse(SDKBaseResponse):
    """
    Standardized error response structure for consistent SDK error handling.
    """
    status: APIStatus = APIStatus.ERROR
    error_code: str = Field(..., description="Machine-readable error code")
    error_type: str = Field(..., description="Error category for SDK error handling")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    user_message: Optional[str] = Field(None, description="User-friendly error message")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retrying")


class ValidationErrorDetail(BaseModel):
    """Individual validation error for field-level error reporting."""
    field: str = Field(..., description="Field name that failed validation")
    message: str = Field(..., description="Validation error message")
    code: str = Field(..., description="Validation error code")
    value: Optional[Any] = Field(None, description="Value that failed validation")


class SDKValidationErrorResponse(SDKErrorResponse):
    """
    Specialized validation error response with field-level details.
    """
    error_code: str = "VALIDATION_ERROR"
    error_type: str = "validation"
    validation_errors: List[ValidationErrorDetail] = Field(..., description="Field-specific validation errors")


class BulkOperationResult(BaseModel):
    """
    Result structure for bulk operations.

    Provides clear success/failure tracking for batch operations.
    """
    total_requested: int = Field(..., description="Total number of operations requested")
    successful_count: int = Field(..., description="Number of successful operations")
    failed_count: int = Field(..., description="Number of failed operations")
    successful_ids: List[str] = Field(default_factory=list, description="IDs of successful operations")
    failed_operations: List["BulkOperationError"] = Field(default_factory=list, description="Failed operations with errors")


class BulkOperationError(BaseModel):
    """Individual bulk operation error."""
    id: Optional[str] = Field(None, description="Item ID that failed")
    index: int = Field(..., description="Index in the request array")
    error_code: str = Field(..., description="Error code for this operation")
    message: str = Field(..., description="Error message for this operation")


class SDKBulkResponse(SDKBaseResponse):
    """Response for bulk operations with detailed success/failure tracking."""
    operation: str = Field(..., description="Bulk operation performed")
    result: BulkOperationResult = Field(..., description="Bulk operation results")


class RateLimitInfo(BaseModel):
    """
    Rate limiting information for SDK consumption.

    Allows SDKs to implement intelligent retry logic.
    """
    limit: int = Field(..., description="Request limit per window")
    remaining: int = Field(..., description="Remaining requests in current window")
    reset_time: datetime = Field(..., description="When the rate limit window resets")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retrying")


class SDKHealthResponse(BaseModel):
    """
    API health check response for SDK monitoring.
    """
    status: str = Field(..., description="Overall API health status")
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Environment (production, staging, etc.)")
    uptime: float = Field(..., description="API uptime in seconds")
    services: Dict[str, str] = Field(..., description="Individual service health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class FileUploadResponse(SDKBaseResponse):
    """
    Standardized file upload response.

    Replaces inconsistent file upload responses across the API.
    """
    file: "UploadedFileInfo" = Field(..., description="Uploaded file information")


class UploadedFileInfo(BaseModel):
    """Information about an uploaded file."""
    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    url: str = Field(..., description="Public URL to access the file")
    secure_url: Optional[str] = Field(None, description="Secure/authenticated URL if different")
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the file was uploaded")


class WebhookEventResponse(SDKBaseResponse):
    """
    Webhook event response structure.

    Provides consistent webhook handling for SDK consumers.
    """
    event_type: str = Field(..., description="Type of webhook event")
    event_id: str = Field(..., description="Unique event identifier")
    webhook_id: str = Field(..., description="Webhook configuration ID")
    delivery_id: str = Field(..., description="Unique delivery attempt ID")
    signature: str = Field(..., description="Webhook signature for verification")
    payload: Dict[str, Any] = Field(..., description="Event payload data")


# Forward reference resolution
PaginationMetadata.model_rebuild()
SDKListResponse.model_rebuild()
BulkOperationResult.model_rebuild()


# SDK Response Type Aliases for common patterns
class UserSDKResponse(SDKDataResponse["UserResponse"]):
    """User-specific SDK response"""


class OrganizationSDKResponse(SDKDataResponse["OrganizationResponse"]):
    """Organization-specific SDK response"""


class SessionSDKResponse(SDKDataResponse["SessionResponse"]):
    """Session-specific SDK response"""


# Export commonly used types for SDK generation
__all__ = [
    # Base response classes
    "SDKBaseResponse",
    "SDKDataResponse",
    "SDKListResponse",
    "SDKSuccessResponse",
    "SDKErrorResponse",
    "SDKValidationErrorResponse",
    "SDKBulkResponse",
    "SDKHealthResponse",

    # Utility classes
    "PaginationMetadata",
    "BulkOperationResult",
    "BulkOperationError",
    "ValidationErrorDetail",
    "RateLimitInfo",
    "FileUploadResponse",
    "UploadedFileInfo",
    "WebhookEventResponse",

    # Enums
    "APIStatus",

    # Type aliases
    "UserSDKResponse",
    "OrganizationSDKResponse",
    "SessionSDKResponse",
]