"""
Unit tests for app.core.logger.

Covers CustomJsonFormatter field injection, setup_logging configuration,
get_logger / get_context_logger factories, and LoggerAdapter context merging.
"""

import json
import logging

import pytest

from app.core.logger import (
    CustomJsonFormatter,
    LoggerAdapter,
    get_context_logger,
    get_logger,
    setup_logging,
)


# ---------------------------------------------------------------------------
# CustomJsonFormatter.add_fields
# ---------------------------------------------------------------------------


def _make_record(**extra) -> logging.LogRecord:
    """Build a LogRecord with optional extra attributes."""
    record = logging.LogRecord(
        name="my.module",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    for k, v in extra.items():
        setattr(record, k, v)
    return record


class TestCustomJsonFormatter:
    def test_emits_valid_json_with_required_fields(self):
        fmt = CustomJsonFormatter("%(message)s")
        record = _make_record()
        out = fmt.format(record)
        data = json.loads(out)
        assert "timestamp" in data
        assert data["timestamp"].endswith("Z")
        assert data["level"] == "INFO"
        assert "module" in data
        assert "function" in data
        assert data["message"] == "hello world"

    def test_includes_user_id_when_set(self):
        fmt = CustomJsonFormatter("%(message)s")
        record = _make_record(user_id="user-42")
        data = json.loads(fmt.format(record))
        assert data["user_id"] == "user-42"

    def test_includes_organization_id_when_set(self):
        fmt = CustomJsonFormatter("%(message)s")
        record = _make_record(organization_id="org-7")
        data = json.loads(fmt.format(record))
        assert data["organization_id"] == "org-7"

    def test_includes_request_id_when_set(self):
        fmt = CustomJsonFormatter("%(message)s")
        record = _make_record(request_id="req-9")
        data = json.loads(fmt.format(record))
        assert data["request_id"] == "req-9"

    def test_omits_optional_context_when_unset(self):
        fmt = CustomJsonFormatter("%(message)s")
        record = _make_record()
        data = json.loads(fmt.format(record))
        for key in ("user_id", "organization_id", "request_id"):
            assert key not in data

    def test_level_field_for_warning(self):
        fmt = CustomJsonFormatter("%(message)s")
        record = logging.LogRecord(
            name="m",
            level=logging.WARNING,
            pathname=__file__,
            lineno=1,
            msg="warn",
            args=(),
            exc_info=None,
        )
        data = json.loads(fmt.format(record))
        assert data["level"] == "WARNING"


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------


@pytest.fixture
def restore_root_logger():
    """Snapshot/restore root logger state across tests."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    yield
    root.handlers.clear()
    for h in saved_handlers:
        root.addHandler(h)
    root.setLevel(saved_level)


class TestSetupLogging:
    def test_setup_logging_sets_level(self, restore_root_logger):
        setup_logging(level="DEBUG", json_output=True)
        assert logging.getLogger().level == logging.DEBUG

    def test_setup_logging_replaces_handlers(self, restore_root_logger):
        # Add a sentinel handler that should be removed
        root = logging.getLogger()
        sentinel = logging.NullHandler()
        root.addHandler(sentinel)
        setup_logging(level="INFO", json_output=True)
        assert sentinel not in root.handlers
        assert len(root.handlers) == 1

    def test_setup_logging_json_uses_custom_formatter(self, restore_root_logger):
        setup_logging(level="INFO", json_output=True)
        handler = logging.getLogger().handlers[0]
        assert isinstance(handler.formatter, CustomJsonFormatter)

    def test_setup_logging_text_uses_standard_formatter(self, restore_root_logger):
        setup_logging(level="INFO", json_output=False)
        handler = logging.getLogger().handlers[0]
        assert handler.formatter is not None
        assert not isinstance(handler.formatter, CustomJsonFormatter)

    def test_setup_logging_lower_case_level(self, restore_root_logger):
        # The function uppercases the level string
        setup_logging(level="warning", json_output=False)
        assert logging.getLogger().level == logging.WARNING


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------


class TestGetLogger:
    def test_get_logger_returns_logger_with_name(self):
        log = get_logger("test.module.x")
        assert isinstance(log, logging.Logger)
        assert log.name == "test.module.x"

    def test_get_logger_returns_same_instance_for_same_name(self):
        a = get_logger("dup.name")
        b = get_logger("dup.name")
        assert a is b


# ---------------------------------------------------------------------------
# LoggerAdapter / get_context_logger
# ---------------------------------------------------------------------------


class TestLoggerAdapter:
    def test_process_merges_extra_context(self):
        underlying = get_logger("test.adapter")
        adapter = LoggerAdapter(underlying, {"user_id": "u1"})
        msg, kwargs = adapter.process("hello", {})
        assert msg == "hello"
        assert kwargs["extra"]["user_id"] == "u1"

    def test_process_preserves_existing_extra(self):
        adapter = LoggerAdapter(get_logger("t.a"), {"user_id": "u1"})
        _, kwargs = adapter.process("m", {"extra": {"request_id": "r1"}})
        assert kwargs["extra"]["user_id"] == "u1"
        assert kwargs["extra"]["request_id"] == "r1"


class TestGetContextLogger:
    def test_returns_logger_adapter(self):
        log = get_context_logger("ctx.module")
        assert isinstance(log, LoggerAdapter)

    def test_includes_only_provided_context(self):
        log = get_context_logger("ctx.module", user_id="u1")
        assert log.extra == {"user_id": "u1"}

    def test_includes_all_context_when_provided(self):
        log = get_context_logger(
            "ctx.module",
            user_id="u1",
            organization_id="org-7",
            request_id="r1",
        )
        assert log.extra == {
            "user_id": "u1",
            "organization_id": "org-7",
            "request_id": "r1",
        }

    def test_empty_context_when_no_kwargs(self):
        log = get_context_logger("ctx.empty")
        assert log.extra == {}

    def test_falsy_values_are_dropped(self):
        # The implementation only adds context when value is truthy
        log = get_context_logger(
            "ctx.falsy",
            user_id="",
            organization_id=None,
            request_id="",
        )
        assert log.extra == {}
