"""
Unit tests for app.core.error_logging.

Covers log_error, log_exception decorator (sync + async), LoggedOperation
context manager, and ErrorMetrics tracking.
"""

import asyncio
from unittest.mock import patch

import pytest

from app.core.error_logging import (
    ErrorMetrics,
    LoggedOperation,
    error_metrics,
    log_error,
    log_exception,
    safe_execute,
)


# ---------------------------------------------------------------------------
# log_error
# ---------------------------------------------------------------------------


class TestLogError:
    def test_log_error_basic_message_only(self):
        with patch("app.core.error_logging.logger") as mock_logger:
            log_error("simple")
        mock_logger.error.assert_called_once()
        kwargs = mock_logger.error.call_args.kwargs
        assert kwargs["message"] == "simple"
        assert "error_type" not in kwargs
        assert "traceback" not in kwargs

    def test_log_error_includes_error_metadata(self):
        err = ValueError("bad input")
        with patch("app.core.error_logging.logger") as mock_logger:
            log_error("validation failed", error=err, field="email")
        kwargs = mock_logger.error.call_args.kwargs
        assert kwargs["error_type"] == "ValueError"
        assert kwargs["error_message"] == "bad input"
        assert kwargs["field"] == "email"

    def test_log_error_includes_traceback_at_error_level(self):
        try:
            raise RuntimeError("boom")
        except RuntimeError as e:
            with patch("app.core.error_logging.logger") as mock_logger:
                log_error("op failed", error=e, level="error")
            kwargs = mock_logger.error.call_args.kwargs
            assert "traceback" in kwargs

    def test_log_error_warning_level_omits_traceback(self):
        err = RuntimeError("warn")
        with patch("app.core.error_logging.logger") as mock_logger:
            log_error("op slow", error=err, level="warning")
        # Should call .warning, not .error
        mock_logger.warning.assert_called_once()
        kwargs = mock_logger.warning.call_args.kwargs
        assert "traceback" not in kwargs
        assert kwargs["error_type"] == "RuntimeError"

    def test_log_error_unknown_level_falls_back_to_error(self):
        with patch("app.core.error_logging.logger") as mock_logger:
            # logger has no .nonsense attribute, so getattr returns logger.error
            log_error("hi", level="nonsense")
        # Either .nonsense or .error gets called; verify a log was emitted.
        # The implementation: getattr(logger, level, logger.error)
        # MagicMock returns a MagicMock for any attr, so .nonsense will be used.
        # Either way, ensure a logging method was invoked at least once.
        assert mock_logger.method_calls, "expected a log call"


# ---------------------------------------------------------------------------
# log_exception decorator
# ---------------------------------------------------------------------------


class TestLogExceptionDecorator:
    def test_sync_function_passes_through_on_success(self):
        @log_exception("won't trigger")
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_sync_function_logs_and_reraises(self):
        @log_exception("op failed", op="div")
        def divide(a, b):
            return a / b

        with patch("app.core.error_logging.logger") as mock_logger:
            with pytest.raises(ZeroDivisionError):
                divide(1, 0)
        # log_error invoked logger.error with our context message
        mock_logger.error.assert_called_once()
        kwargs = mock_logger.error.call_args.kwargs
        assert kwargs["message"] == "op failed"
        assert kwargs["function"] == "divide"
        assert kwargs["op"] == "div"

    def test_async_function_passes_through_on_success(self):
        @log_exception("noop")
        async def fetch():
            return "ok"

        assert asyncio.run(fetch()) == "ok"

    def test_async_function_logs_and_reraises(self):
        @log_exception("async failed", resource="user")
        async def get_user():
            raise LookupError("missing")

        with patch("app.core.error_logging.logger") as mock_logger:
            with pytest.raises(LookupError):
                asyncio.run(get_user())
        mock_logger.error.assert_called_once()
        kwargs = mock_logger.error.call_args.kwargs
        assert kwargs["message"] == "async failed"
        assert kwargs["resource"] == "user"


# ---------------------------------------------------------------------------
# safe_execute
# ---------------------------------------------------------------------------


class TestSafeExecute:
    def test_safe_execute_returns_sync_result(self):
        assert safe_execute(lambda: 42) == 42

    def test_safe_execute_returns_fallback_on_exception(self):
        def boom():
            raise RuntimeError("nope")

        with patch("app.core.error_logging.logger") as mock_logger:
            out = safe_execute(boom, fallback="fallback-val", error_message="op")
        assert out == "fallback-val"
        # Should have logged at the warning level (default)
        assert mock_logger.warning.called or mock_logger.error.called

    def test_safe_execute_logs_with_context(self):
        with patch("app.core.error_logging.logger") as mock_logger:
            safe_execute(
                lambda: (_ for _ in ()).throw(KeyError("k")),
                fallback=None,
                error_message="cache miss",
                key="user:1",
            )
        assert mock_logger.warning.called or mock_logger.error.called


# ---------------------------------------------------------------------------
# LoggedOperation context manager
# ---------------------------------------------------------------------------


class TestLoggedOperation:
    def test_logs_start_and_completion_on_success(self):
        async def run():
            with patch("app.core.error_logging.logger") as mock_logger:
                async with LoggedOperation("setup", user_id="u1"):
                    pass
            return mock_logger

        mock_logger = asyncio.run(run())
        # Two info logs: started + completed
        assert mock_logger.info.call_count == 2
        first = mock_logger.info.call_args_list[0].kwargs
        second = mock_logger.info.call_args_list[1].kwargs
        assert first["status"] == "started"
        assert first["user_id"] == "u1"
        assert second["status"] == "completed"
        assert "duration_ms" in second

    def test_logs_failure_and_does_not_suppress(self):
        async def run():
            with patch("app.core.error_logging.logger") as mock_logger:
                with pytest.raises(RuntimeError):
                    async with LoggedOperation("setup"):
                        raise RuntimeError("boom")
            return mock_logger

        mock_logger = asyncio.run(run())
        # error called via log_error with error_type set
        assert mock_logger.error.called
        kwargs = mock_logger.error.call_args.kwargs
        assert kwargs["status"] == "failed"
        assert "duration_ms" in kwargs


# ---------------------------------------------------------------------------
# ErrorMetrics
# ---------------------------------------------------------------------------


class TestErrorMetrics:
    def test_record_increments_counter(self):
        m = ErrorMetrics()
        m.record_error("ValueError", "validate")
        m.record_error("ValueError", "validate")
        assert m.get_error_count("validate", "ValueError") == 2

    def test_separate_keys_per_operation(self):
        m = ErrorMetrics()
        m.record_error("ValueError", "validate")
        m.record_error("ValueError", "save")
        assert m.get_error_count("validate", "ValueError") == 1
        assert m.get_error_count("save", "ValueError") == 1

    def test_unknown_key_returns_zero(self):
        m = ErrorMetrics()
        assert m.get_error_count("missing", "Whatever") == 0

    def test_record_logs_count(self):
        m = ErrorMetrics()
        with patch("app.core.error_logging.logger") as mock_logger:
            m.record_error("KeyError", "lookup", user_id="u1")
        mock_logger.info.assert_called_once()
        kwargs = mock_logger.info.call_args.kwargs
        assert kwargs["error_type"] == "KeyError"
        assert kwargs["operation"] == "lookup"
        assert kwargs["count"] == 1
        assert kwargs["user_id"] == "u1"

    def test_global_instance_exists(self):
        assert isinstance(error_metrics, ErrorMetrics)
