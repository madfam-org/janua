"""Unit tests for rotation_monitor.

Pure, no network, no filesystem — just the classification logic over a
synthetic registry so we can assert each severity branch fires correctly.
"""

from __future__ import annotations

from datetime import date

from rotation_monitor import (
    BOOTSTRAP_SENTINEL,
    _classify,
    evaluate,
)

TODAY = date(2026, 4, 17)

POLICIES = {
    "quarterly": {"days": 90, "reminder_days": [14, 7, 3, 1]},
    "semi_annual": {"days": 180, "reminder_days": [30, 14, 7, 3, 1]},
    "annual": {"days": 365, "reminder_days": [30, 14, 7, 1]},
    "on_demand": {"days": None, "reminder_days": []},
}


def _secret(**overrides):
    base = {
        "id": "test-secret",
        "name": "TEST_SECRET",
        "policy": "quarterly",
        "last_rotated": "2025-10-01",
        "next_rotation": "2025-12-30",
    }
    base.update(overrides)
    return base


class TestOverdue:
    def test_overdue_secret_flagged(self) -> None:
        f = _classify(_secret(next_rotation="2026-01-01"), "janua", POLICIES, TODAY)
        assert f.severity == "overdue"
        assert f.days_past_due == (TODAY - date(2026, 1, 1)).days
        assert f.is_actionable

    def test_overdue_report_cites_original_date(self) -> None:
        f = _classify(
            _secret(next_rotation="2025-12-01"), "janua", POLICIES, TODAY
        )
        assert "2025-12-01" in f.reason


class TestReminder:
    def test_one_day_before_due_in_quarterly_policy_fires_reminder(self) -> None:
        one_day_out = TODAY.replace(day=TODAY.day + 1)
        f = _classify(
            _secret(
                policy="quarterly", next_rotation=one_day_out.isoformat()
            ),
            "janua",
            POLICIES,
            TODAY,
        )
        assert f.severity == "reminder"
        assert f.is_actionable

    def test_outside_reminder_window_stays_ok(self) -> None:
        # 45 days out, quarterly reminders are [14, 7, 3, 1] — not in set
        f = _classify(
            _secret(policy="quarterly", next_rotation="2026-06-01"),
            "janua",
            POLICIES,
            TODAY,
        )
        assert f.severity == "ok"
        assert not f.is_actionable

    def test_semi_annual_30_day_reminder_fires(self) -> None:
        target = date(2026, 5, 17)  # TODAY + 30 days
        f = _classify(
            _secret(policy="semi_annual", next_rotation=target.isoformat()),
            "janua",
            POLICIES,
            TODAY,
        )
        assert f.severity == "reminder"


class TestBootstrap:
    def test_bootstrap_sentinel_flagged_even_with_future_date(self) -> None:
        f = _classify(
            _secret(last_rotated=BOOTSTRAP_SENTINEL, next_rotation="2026-06-01"),
            "ecosystem",
            POLICIES,
            TODAY,
        )
        assert f.severity == "bootstrap"
        assert f.is_actionable

    def test_bootstrap_without_next_date_still_actionable(self) -> None:
        f = _classify(
            _secret(last_rotated=BOOTSTRAP_SENTINEL, next_rotation=None),
            "ecosystem",
            POLICIES,
            TODAY,
        )
        assert f.severity == "bootstrap"
        assert "baseline" in f.reason.lower()


class TestOnDemand:
    def test_on_demand_with_null_next_rotation_is_skipped(self) -> None:
        f = _classify(
            _secret(policy="on_demand", next_rotation=None, last_rotated="2025-01-01"),
            "janua",
            POLICIES,
            TODAY,
        )
        assert f.severity == "skipped"
        assert not f.is_actionable

    def test_on_demand_bootstrap_still_flagged(self) -> None:
        f = _classify(
            _secret(
                policy="on_demand",
                last_rotated=BOOTSTRAP_SENTINEL,
                next_rotation=None,
            ),
            "ecosystem",
            POLICIES,
            TODAY,
        )
        assert f.severity == "bootstrap"


class TestEvaluateOverRegistry:
    def test_mixed_registry(self) -> None:
        registry = {
            "rotation_policies": POLICIES,
            "secrets": {
                "janua": [
                    _secret(id="overdue-one", next_rotation="2025-01-01"),
                    _secret(id="ok-one", next_rotation="2027-01-01"),
                ],
                "ecosystem": [
                    _secret(
                        id="bootstrap-one",
                        last_rotated=BOOTSTRAP_SENTINEL,
                        next_rotation="2026-05-17",
                    ),
                ],
            },
        }
        findings = evaluate(registry, today=TODAY)
        by_id = {f.secret_id: f for f in findings}
        assert by_id["overdue-one"].severity == "overdue"
        assert by_id["ok-one"].severity == "ok"
        assert by_id["bootstrap-one"].severity == "bootstrap"

    def test_ignores_malformed_entries(self) -> None:
        registry = {
            "rotation_policies": POLICIES,
            "secrets": {
                "janua": [
                    _secret(id="good-one"),
                    "not-a-dict",
                    None,
                    42,
                ],
                "not-a-list": "oops",
            },
        }
        findings = evaluate(registry, today=TODAY)
        assert len(findings) == 1
        assert findings[0].secret_id == "good-one"


class TestUnparseableDates:
    def test_unparseable_next_rotation_is_skipped(self) -> None:
        f = _classify(
            _secret(next_rotation="not-a-date"),
            "janua",
            POLICIES,
            TODAY,
        )
        assert f.severity == "skipped"
        assert "unparseable" in f.reason

    def test_missing_next_rotation_for_scheduled_policy_skipped(self) -> None:
        f = _classify(
            _secret(policy="quarterly", next_rotation=None),
            "janua",
            POLICIES,
            TODAY,
        )
        assert f.severity == "skipped"
