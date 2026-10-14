"""An unparseable IP must be logged and scored as not suspicious, not raise.

`_is_suspicious_ip_range` logs invalid input through a stdlib logger. It used to
pass structlog-style keyword fields, which stdlib `Logger._log()` rejects with
TypeError, so the "log and return False" handler raised instead. Real logger,
not patched.
"""

from __future__ import annotations

import logging

from app.security.threat_detection import AdvancedThreatDetectionSystem

LOGGER_NAME = "app.security.threat_detection"


def _detector() -> AdvancedThreatDetectionSystem:
    # __init__ starts background asyncio tasks and loads ML models; the method
    # under test touches neither, so skip it.
    return object.__new__(AdvancedThreatDetectionSystem)


def test_invalid_ip_is_logged_with_fields_in_extra_and_not_suspicious(caplog):
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    assert _detector()._is_suspicious_ip_range("not-an-ip") is False

    (record,) = [
        r
        for r in caplog.records
        if r.getMessage() == "Invalid IP address format in threat detection"
    ]
    assert record.ip == "not-an-ip"
    assert record.error_type == "ValueError"


def test_private_range_is_still_suspicious():
    assert _detector()._is_suspicious_ip_range("10.0.0.7") is True
