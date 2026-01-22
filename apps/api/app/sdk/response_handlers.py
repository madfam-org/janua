"""
Response handling utilities for SDK clients.

Provides consistent response processing, pagination handling,
and bulk operation result management across all platform SDKs.
"""

from typing import Any, Dict, List, Optional, TypeVar, Generic, AsyncIterator

from ..schemas.sdk_models import PaginationMetadata, BulkOperationResult, APIStatus
from .error_handling import create_error_from_response, APIError

T = TypeVar("T")


class ResponseHandler:
    """
    Handles API response processing and error detection.

    This class provides the common logic for processing API responses
    that will be implemented in each platform SDK.
    """

    @staticmethod
    def process_response(
        response_data: Dict[str, Any], status_code: int, headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Process an API response and handle errors.

        Args:
            response_data: Parsed response body
            status_code: HTTP status code
            headers: Response headers

        Returns:
            Processed response data

        Raises:
            APIError: If the response indicates an error
        """
        # Check for error responses
        if status_code >= 400:
            raise create_error_from_response(response_data, status_code)

        # Validate response structure
        if not isinstance(response_data, dict):
            raise APIError(
                message="Invalid response format",
                status_code=status_code,
                error_code="INVALID_RESPONSE_FORMAT",
            )

        # Check response status
        response_status = response_data.get("status", APIStatus.SUCCESS)
        if response_status == APIStatus.ERROR:
            raise create_error_from_response(response_data, status_code)

        return response_data

    @staticmethod
    def extract_data(response: Dict[str, Any]) -> Any:
        """
        Extract the data payload from a processed response.

        Args:
            response: Processed response dictionary

        Returns:
            Data payload or None if no data field
        """
        return response.get("data")

    @staticmethod
    def extract_pagination(response: Dict[str, Any]) -> Optional[PaginationMetadata]:
        """
        Extract pagination metadata from a response.

        Args:
            response: Processed response dictionary

        Returns:
            Pagination metadata or None if not paginated
        """
        pagination_data = response.get("pagination")
        if not pagination_data:
            return None

        return PaginationMetadata(**pagination_data)

    @staticmethod
    def is_success_response(response: Dict[str, Any]) -> bool:
        """Check if a response indicates success."""
        status = response.get("status", APIStatus.SUCCESS)
        return status == APIStatus.SUCCESS

    @staticmethod
    def get_request_id(response: Dict[str, Any]) -> Optional[str]:
        """Extract request ID from response for debugging."""
        return response.get("request_id")


class PaginationHandler(Generic[T]):
    """
    Handles paginated API responses with platform-appropriate iteration.

    Each platform SDK will implement this differently:
    - Python: async iterator protocol
    - TypeScript: AsyncIterable or Promise-based pagination
    - Go: channel-based iteration
    - Java: Stream or Iterator interface
    """

    def __init__(
        self, initial_response: Dict[str, Any], request_func, response_handler: ResponseHandler
    ):
        """
        Initialize pagination handler.

        Args:
            initial_response: First page response
            request_func: Function to make subsequent requests
            response_handler: Response handler instance
        """
        self.response_handler = response_handler
        self.request_func = request_func

        # Extract initial data
        self.current_data = response_handler.extract_data(initial_response)
        self.pagination = response_handler.extract_pagination(initial_response)
        self.current_page = self.pagination.page if self.pagination else 1

    @property
    def has_next_page(self) -> bool:
        """Check if there are more pages available."""
        return self.pagination and self.pagination.has_next

    @property
    def has_prev_page(self) -> bool:
        """Check if there are previous pages available."""
        return self.pagination and self.pagination.has_prev

    @property
    def total_items(self) -> int:
        """Get total number of items across all pages."""
        return self.pagination.total if self.pagination else len(self.current_data)

    @property
    def total_pages(self) -> int:
        """Get total number of pages."""
        return self.pagination.pages if self.pagination else 1

    async def next_page(self) -> Optional["PaginationHandler[T]"]:
        """
        Fetch the next page of results.

        Returns:
            New pagination handler for the next page, or None if no more pages
        """
        if not self.has_next_page:
            return None

        next_page_num = self.current_page + 1
        response = await self.request_func(page=next_page_num)
        processed_response = self.response_handler.process_response(
            response["data"], response["status_code"], response.get("headers")
        )

        return PaginationHandler(processed_response, self.request_func, self.response_handler)

    async def prev_page(self) -> Optional["PaginationHandler[T]"]:
        """
        Fetch the previous page of results.

        Returns:
            New pagination handler for the previous page, or None if no previous pages
        """
        if not self.has_prev_page:
            return None

        prev_page_num = self.current_page - 1
        response = await self.request_func(page=prev_page_num)
        processed_response = self.response_handler.process_response(
            response["data"], response["status_code"], response.get("headers")
        )

        return PaginationHandler(processed_response, self.request_func, self.response_handler)

    async def all_items(self, max_pages: Optional[int] = None) -> List[T]:
        """
        Collect all items from all pages.

        Args:
            max_pages: Maximum number of pages to fetch (safety limit)

        Returns:
            List of all items across pages

        Warning:
            Use with caution for large datasets. Consider using iterator instead.
        """
        all_items = self.current_data.copy()
        current_handler = self
        pages_fetched = 1

        while current_handler.has_next_page:
            if max_pages and pages_fetched >= max_pages:
                break

            current_handler = await current_handler.next_page()
            if current_handler:
                all_items.extend(current_handler.current_data)
                pages_fetched += 1
            else:
                break

        return all_items

    def __aiter__(self) -> AsyncIterator[T]:
        """Async iterator support for Python SDKs."""
        return self._async_iterator()

    async def _async_iterator(self) -> AsyncIterator[T]:
        """Implementation of async iteration over all pages."""
        current_handler = self

        # Yield items from current page
        for item in current_handler.current_data:
            yield item

        # Yield items from subsequent pages
        while current_handler.has_next_page:
            current_handler = await current_handler.next_page()
            if current_handler:
                for item in current_handler.current_data:
                    yield item
            else:
                break


class BulkOperationHandler:
    """
    Handles bulk operation responses with detailed success/failure tracking.

    Provides utilities for processing bulk operation results and
    handling partial successes/failures.
    """

    def __init__(self, response: Dict[str, Any], response_handler: ResponseHandler):
        """
        Initialize bulk operation handler.

        Args:
            response: Bulk operation response
            response_handler: Response handler instance
        """
        self.response_handler = response_handler
        self.response = response
        self.result = self._extract_bulk_result(response)

    def _extract_bulk_result(self, response: Dict[str, Any]) -> BulkOperationResult:
        """Extract bulk operation result from response."""
        result_data = response.get("result", {})
        return BulkOperationResult(**result_data)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        if self.result.total_requested == 0:
            return 0.0
        return (self.result.successful_count / self.result.total_requested) * 100

    @property
    def is_complete_success(self) -> bool:
        """Check if all operations succeeded."""
        return self.result.failed_count == 0

    @property
    def is_complete_failure(self) -> bool:
        """Check if all operations failed."""
        return self.result.successful_count == 0

    @property
    def is_partial_success(self) -> bool:
        """Check if some operations succeeded and some failed."""
        return 0 < self.result.successful_count < self.result.total_requested

    def get_successful_ids(self) -> List[str]:
        """Get list of successfully processed item IDs."""
        return self.result.successful_ids

    def get_failed_operations(self) -> List[Dict[str, Any]]:
        """Get list of failed operations with error details."""
        return [
            {
                "id": error.id,
                "index": error.index,
                "error_code": error.error_code,
                "message": error.message,
            }
            for error in self.result.failed_operations
        ]

    def get_errors_by_code(self, error_code: str) -> List[Dict[str, Any]]:
        """Get failed operations filtered by error code."""
        return [
            error for error in self.get_failed_operations() if error["error_code"] == error_code
        ]

    def has_error_code(self, error_code: str) -> bool:
        """Check if any operation failed with the specified error code."""
        return len(self.get_errors_by_code(error_code)) > 0

    def summary(self) -> Dict[str, Any]:
        """Get a summary of the bulk operation results."""
        return {
            "total_requested": self.result.total_requested,
            "successful": self.result.successful_count,
            "failed": self.result.failed_count,
            "success_rate": self.success_rate,
            "status": self._get_status_summary(),
            "error_codes": list(set(error["error_code"] for error in self.get_failed_operations())),
        }

    def _get_status_summary(self) -> str:
        """Get a human-readable status summary."""
        if self.is_complete_success:
            return "complete_success"
        elif self.is_complete_failure:
            return "complete_failure"
        elif self.is_partial_success:
            return "partial_success"
        else:
            return "unknown"


# Utility functions for SDK implementations
def create_response_handler() -> ResponseHandler:
    """Create a standard response handler."""
    return ResponseHandler()


def create_pagination_handler(
    response: Dict[str, Any], request_func, response_handler: Optional[ResponseHandler] = None
) -> PaginationHandler:
    """
    Create a pagination handler for a paginated response.

    Args:
        response: Initial paginated response
        request_func: Function to make subsequent page requests
        response_handler: Optional custom response handler

    Returns:
        Configured pagination handler
    """
    if response_handler is None:
        response_handler = create_response_handler()

    return PaginationHandler(response, request_func, response_handler)


def create_bulk_operation_handler(
    response: Dict[str, Any], response_handler: Optional[ResponseHandler] = None
) -> BulkOperationHandler:
    """
    Create a bulk operation handler for a bulk operation response.

    Args:
        response: Bulk operation response
        response_handler: Optional custom response handler

    Returns:
        Configured bulk operation handler
    """
    if response_handler is None:
        response_handler = create_response_handler()

    return BulkOperationHandler(response, response_handler)
