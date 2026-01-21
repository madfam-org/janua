"""
Comprehensive error logging utilities

Provides utilities for structured error logging with context,
ensuring no silent error handlers and consistent error tracking.
"""

import traceback
from typing import Any, Optional, Callable
from functools import wraps
import structlog

logger = structlog.get_logger()


def log_error(
    message: str,
    error: Optional[Exception] = None,
    level: str = "error",
    **context
) -> None:
    """
    Log an error with structured context.

    Args:
        message: Human-readable error message
        error: Optional exception object
        level: Log level (error, warning, info)
        **context: Additional context fields

    Example:
        try:
            await redis.get("key")
        except Exception as e:
            log_error(
                "Redis operation failed",
                error=e,
                operation="get",
                key="user:123"
            )
    """
    log_data = {
        "message": message,
        **context
    }

    if error:
        log_data["error_type"] = type(error).__name__
        log_data["error_message"] = str(error)

        # Add traceback for errors (not warnings)
        if level == "error":
            log_data["traceback"] = traceback.format_exc()

    # Log at appropriate level
    log_func = getattr(logger, level, logger.error)
    log_func(**log_data)


def log_exception(
    context_message: str,
    **context
) -> Callable:
    """
    Decorator to log exceptions in a function.

    Automatically logs exceptions with context and re-raises them.

    Args:
        context_message: Message describing what operation failed
        **context: Additional context to include in logs

    Example:
        @log_exception("Failed to fetch user", resource="user")
        async def get_user(user_id: str):
            return await db.query(User).get(user_id)

        # On exception, logs:
        # {
        #   "message": "Failed to fetch user",
        #   "resource": "user",
        #   "error_type": "DatabaseError",
        #   "error_message": "Connection timeout",
        #   "traceback": "..."
        # }
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                log_error(
                    context_message,
                    error=e,
                    function=func.__name__,
                    **context
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_error(
                    context_message,
                    error=e,
                    function=func.__name__,
                    **context
                )
                raise

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def safe_execute(
    operation: Callable,
    fallback: Any = None,
    error_message: str = "Operation failed",
    log_level: str = "warning",
    **context
) -> Any:
    """
    Execute an operation safely with automatic error logging and fallback.

    Args:
        operation: Function to execute
        fallback: Value to return on error (default: None)
        error_message: Message to log on error
        log_level: Log level for errors (default: warning)
        **context: Additional context for logging

    Returns:
        Result of operation or fallback value

    Example:
        # Safe Redis operation
        user_data = await safe_execute(
            lambda: redis.get(f"user:{user_id}"),
            fallback={},
            error_message="Failed to fetch user from cache",
            user_id=user_id
        )

        # Safe email send
        sent = await safe_execute(
            lambda: email_service.send_email(email),
            fallback=False,
            error_message="Failed to send email",
            email=email
        )
    """
    try:
        import asyncio
        if asyncio.iscoroutinefunction(operation):
            result = asyncio.create_task(operation())
        else:
            result = operation()
        return result
    except Exception as e:
        log_error(
            error_message,
            error=e,
            level=log_level,
            **context
        )
        return fallback


# ============================================================================
# Context Managers for Error Logging
# ============================================================================


class LoggedOperation:
    """
    Context manager for logging operation success/failure.

    Automatically logs when entering and exiting a block,
    including success/failure status and duration.

    Example:
        async with LoggedOperation("user_creation", user_id=user_id):
            user = await create_user(user_id, data)
            await send_welcome_email(user)

        # Logs on enter:
        # {"operation": "user_creation", "status": "started", "user_id": "123"}

        # Logs on success:
        # {"operation": "user_creation", "status": "completed", "duration_ms": 123}

        # Logs on error:
        # {"operation": "user_creation", "status": "failed", "error": "...", "duration_ms": 45}
    """

    def __init__(self, operation: str, **context):
        self.operation = operation
        self.context = context
        self.start_time = None

    async def __aenter__(self):
        import time
        self.start_time = time.time()

        logger.info(
            f"{self.operation} started",
            operation=self.operation,
            status="started",
            **self.context
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        import time
        duration_ms = (time.time() - self.start_time) * 1000

        if exc_type is None:
            # Success
            logger.info(
                f"{self.operation} completed",
                operation=self.operation,
                status="completed",
                duration_ms=round(duration_ms, 2),
                **self.context
            )
        else:
            # Failure
            log_error(
                f"{self.operation} failed",
                error=exc_val,
                operation=self.operation,
                status="failed",
                duration_ms=round(duration_ms, 2),
                **self.context
            )

        # Don't suppress the exception
        return False


# ============================================================================
# Patterns for Fixing Silent Error Handlers
# ============================================================================

"""
ANTI-PATTERN 1: Silent Exception with pass
-------------------------------------------
❌ BAD:
try:
    await redis.get("key")
except Exception:
    pass  # Silent failure!

✅ GOOD:
try:
    await redis.get("key")
except Exception as e:
    log_error(
        "Failed to get value from cache",
        error=e,
        key="user:123",
        level="warning"  # Use warning for non-critical failures
    )
    # Return fallback or continue with degraded functionality


ANTI-PATTERN 2: Silent Exception with return
---------------------------------------------
❌ BAD:
try:
    user = await get_user(user_id)
except Exception:
    return None  # What went wrong? We'll never know!

✅ GOOD:
try:
    user = await get_user(user_id)
except Exception as e:
    log_error(
        "Failed to fetch user",
        error=e,
        user_id=user_id
    )
    return None


ANTI-PATTERN 3: Generic Exception Catch
----------------------------------------
❌ BAD:
try:
    result = await complex_operation()
except Exception:
    # No logging, no context
    return fallback_value

✅ GOOD:
try:
    result = await complex_operation()
except Exception as e:
    log_error(
        "Complex operation failed",
        error=e,
        operation="complex_operation",
        level="error"
    )
    return fallback_value


PATTERN 1: Use safe_execute for non-critical operations
--------------------------------------------------------
# Cache lookup (non-critical - system works without cache)
user_data = await safe_execute(
    lambda: redis.get(f"user:{user_id}"),
    fallback=None,
    error_message="Cache lookup failed",
    level="warning",  # Not an error, just degraded performance
    user_id=user_id
)

if user_data is None:
    # Fetch from database
    user_data = await get_user_from_db(user_id)


PATTERN 2: Use log_exception decorator for critical operations
---------------------------------------------------------------
@log_exception("User creation failed", critical=True)
async def create_user(user_data: dict) -> User:
    user = User(**user_data)
    await db.add(user)
    await db.commit()
    return user

# Exception is logged with full context and re-raised


PATTERN 3: Use LoggedOperation for multi-step processes
--------------------------------------------------------
async def onboard_new_user(user_id: str):
    async with LoggedOperation("user_onboarding", user_id=user_id):
        # All steps are automatically logged
        user = await create_user_account(user_id)
        await send_welcome_email(user)
        await setup_default_permissions(user)
        await trigger_analytics_event("user_created", user_id)

    # Automatically logs:
    # - Start of operation
    # - Success with duration
    # - Failure with error details and duration


PATTERN 4: Specific exception handling with logging
----------------------------------------------------
async def update_user_email(user_id: str, new_email: str):
    try:
        user = await get_user(user_id)

        if not user:
            log_error(
                "User not found for email update",
                user_id=user_id,
                level="warning"
            )
            raise HTTPException(404, "User not found")

        user.email = new_email
        await db.commit()

        # Invalidate caches
        await cache_manager.invalidate(f"user:{user_id}")

        return user

    except HTTPException:
        # Re-raise HTTP exceptions (already handled)
        raise

    except Exception as e:
        await db.rollback()

        log_error(
            "Failed to update user email",
            error=e,
            user_id=user_id,
            new_email=new_email,
            level="error"
        )

        raise HTTPException(500, "Email update failed")


PATTERN 5: External service calls with retry logging
-----------------------------------------------------
async def send_email_with_retry(email: str, content: str):
    max_retries = 3

    for attempt in range(max_retries):
        try:
            await email_service.send(email, content)

            logger.info(
                "Email sent successfully",
                email=email,
                attempt=attempt + 1
            )
            return True

        except Exception as e:
            log_error(
                f"Email send failed (attempt {attempt + 1}/{max_retries})",
                error=e,
                email=email,
                attempt=attempt + 1,
                level="warning" if attempt < max_retries - 1 else "error"
            )

            if attempt == max_retries - 1:
                # Final attempt failed
                return False

            # Wait before retry
            import asyncio
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

    return False
"""


# ============================================================================
# Monitoring Integration
# ============================================================================


class ErrorMetrics:
    """
    Track error metrics for monitoring/alerting.

    Can be integrated with Prometheus, Grafana, or other monitoring systems.
    """

    def __init__(self):
        self.error_counts = {}
        self.error_rates = {}

    def record_error(
        self,
        error_type: str,
        operation: str,
        **context
    ):
        """Record an error occurrence"""
        key = f"{operation}:{error_type}"

        if key not in self.error_counts:
            self.error_counts[key] = 0

        self.error_counts[key] += 1

        logger.info(
            "Error metric recorded",
            error_type=error_type,
            operation=operation,
            count=self.error_counts[key],
            **context
        )

    def get_error_count(self, operation: str, error_type: str) -> int:
        """Get error count for specific operation and type"""
        key = f"{operation}:{error_type}"
        return self.error_counts.get(key, 0)


# Global error metrics instance
error_metrics = ErrorMetrics()
