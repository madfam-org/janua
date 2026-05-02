"""
Unit tests for app.alerting.evaluation.evaluator.AlertEvaluator.

Pure logic - evaluates AlertRule against metric values, with trigger-count
windowing semantics.
"""

import pytest

from app.alerting.evaluation.evaluator import AlertEvaluator
from app.alerting.models import AlertRule, AlertSeverity


def _rule(
    operator: str = ">",
    threshold: float = 50.0,
    trigger_count: int = 1,
    rule_id: str = "rule-1",
) -> AlertRule:
    return AlertRule(
        rule_id=rule_id,
        name="test rule",
        description="",
        severity=AlertSeverity.MEDIUM,
        metric_name="cpu",
        threshold_value=threshold,
        comparison_operator=operator,
        evaluation_window=60,
        trigger_count=trigger_count,
    )


class TestEvaluateRuleOperators:
    @pytest.mark.parametrize(
        "operator,current,threshold,expected",
        [
            (">", 60.0, 50.0, True),
            (">", 50.0, 50.0, False),
            ("<", 40.0, 50.0, True),
            ("<", 50.0, 50.0, False),
            (">=", 50.0, 50.0, True),
            (">=", 49.0, 50.0, False),
            ("<=", 50.0, 50.0, True),
            ("<=", 51.0, 50.0, False),
            ("==", 50.0, 50.0, True),
            ("==", 51.0, 50.0, False),
            ("!=", 51.0, 50.0, True),
            ("!=", 50.0, 50.0, False),
        ],
    )
    def test_evaluate_with_default_trigger_count(
        self, operator, current, threshold, expected
    ):
        ev = AlertEvaluator()
        r = _rule(operator=operator, threshold=threshold)
        assert ev.evaluate_rule(r, current) is expected

    def test_unknown_operator_returns_false_and_warns(self):
        ev = AlertEvaluator()
        r = _rule(operator="??")
        assert ev.evaluate_rule(r, 100.0) is False
        # No history recorded for unknown operator
        assert "rule-1" not in ev.evaluation_history


class TestTriggerCountWindowing:
    def test_single_breach_with_trigger_count_3_returns_false(self):
        ev = AlertEvaluator()
        r = _rule(operator=">", threshold=50, trigger_count=3)
        assert ev.evaluate_rule(r, 60.0) is False  # 1/3 breaches

    def test_three_consecutive_breaches_with_trigger_count_3_returns_true(self):
        ev = AlertEvaluator()
        r = _rule(operator=">", threshold=50, trigger_count=3)
        assert ev.evaluate_rule(r, 60.0) is False
        assert ev.evaluate_rule(r, 70.0) is False
        assert ev.evaluate_rule(r, 80.0) is True

    def test_breach_then_recovery_resets_streak(self):
        ev = AlertEvaluator()
        r = _rule(operator=">", threshold=50, trigger_count=3)
        ev.evaluate_rule(r, 60.0)  # breach
        ev.evaluate_rule(r, 70.0)  # breach
        ev.evaluate_rule(r, 30.0)  # recovery - resets
        # Need 3 consecutive again
        assert ev.evaluate_rule(r, 60.0) is False
        assert ev.evaluate_rule(r, 60.0) is False
        assert ev.evaluate_rule(r, 60.0) is True

    def test_history_is_capped(self):
        ev = AlertEvaluator()
        r = _rule(operator=">", threshold=50, trigger_count=2)
        # max_history = max(2, 10) = 10
        for _ in range(20):
            ev.evaluate_rule(r, 60.0)
        assert len(ev.evaluation_history[r.rule_id]) == 10


class TestEvaluateRuleDetailed:
    def test_detailed_includes_consecutive_count(self):
        ev = AlertEvaluator()
        r = _rule(operator=">", threshold=50, trigger_count=2)
        ev.evaluate_rule(r, 60.0)
        result = ev.evaluate_rule_detailed(r, 70.0)
        assert result.rule_id == "rule-1"
        assert result.metric_value == 70.0
        assert result.threshold_value == 50.0
        assert result.consecutive_triggers == 2
        assert result.should_trigger is True
        assert result.context["operator"] == ">"
        assert result.context["trigger_count_required"] == 2

    def test_detailed_no_history(self):
        ev = AlertEvaluator()
        r = _rule(operator=">", threshold=50)
        result = ev.evaluate_rule_detailed(r, 30.0)  # not breached
        # 1 evaluation in history; consecutive count from end = 0 (latest is False)
        assert result.consecutive_triggers == 0
        assert result.should_trigger is False

    def test_detailed_consecutive_stops_at_first_false(self):
        ev = AlertEvaluator()
        r = _rule(operator=">", threshold=50, trigger_count=1)
        ev.evaluate_rule(r, 60.0)  # T
        ev.evaluate_rule(r, 30.0)  # F
        ev.evaluate_rule(r, 60.0)  # T
        ev.evaluate_rule(r, 60.0)  # T
        result = ev.evaluate_rule_detailed(r, 60.0)  # T
        # Last 3 are T,T,T; before that F. consecutive_triggers stops at the F
        assert result.consecutive_triggers == 3


class TestEvaluationHistoryManagement:
    def test_reset_specific_rule(self):
        ev = AlertEvaluator()
        r1 = _rule(rule_id="r1")
        r2 = _rule(rule_id="r2")
        ev.evaluate_rule(r1, 60.0)
        ev.evaluate_rule(r2, 60.0)
        ev.reset_evaluation_history("r1")
        assert "r1" not in ev.evaluation_history
        assert "r2" in ev.evaluation_history

    def test_reset_all(self):
        ev = AlertEvaluator()
        ev.evaluate_rule(_rule(rule_id="r1"), 60.0)
        ev.evaluate_rule(_rule(rule_id="r2"), 60.0)
        ev.reset_evaluation_history()
        assert ev.evaluation_history == {}

    def test_reset_unknown_rule_is_safe(self):
        ev = AlertEvaluator()
        ev.reset_evaluation_history("does-not-exist")  # must not raise


class TestEvaluationStats:
    def test_stats_empty_for_unknown_rule(self):
        ev = AlertEvaluator()
        stats = ev.get_evaluation_stats("missing")
        assert stats == {
            "total_evaluations": 0,
            "positive_evaluations": 0,
            "success_rate": 0.0,
        }

    def test_stats_after_evaluations(self):
        ev = AlertEvaluator()
        r = _rule(operator=">", threshold=50)
        ev.evaluate_rule(r, 60.0)  # T
        ev.evaluate_rule(r, 30.0)  # F
        ev.evaluate_rule(r, 60.0)  # T
        stats = ev.get_evaluation_stats("rule-1")
        assert stats["total_evaluations"] == 3
        assert stats["positive_evaluations"] == 2
        assert stats["success_rate"] == pytest.approx(2 / 3)
        assert stats["recent_trend"] == [True, False, True]

    def test_stats_recent_trend_capped_at_5(self):
        ev = AlertEvaluator()
        r = _rule(operator=">", threshold=50)
        for _ in range(8):
            ev.evaluate_rule(r, 60.0)
        stats = ev.get_evaluation_stats("rule-1")
        assert len(stats["recent_trend"]) == 5
