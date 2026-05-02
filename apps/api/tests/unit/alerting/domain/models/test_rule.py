"""
Unit tests for app.alerting.domain.models.rule

Pure tests for AlertRule, RuleCondition, AlertChannel, ComparisonOperator.

NOTE: AlertRule.from_dict and the RuleBuilder class are NOT covered here:
both call AlertRule(...) without a condition (and from_dict also defers
adding the condition until after construction), but AlertRule.__post_init__
requires a non-None condition. As written today, both code paths raise
ValueError("Rule must have a condition") on import-time use, so they cannot
be exercised without modifying production code (out of scope for this
coverage backfill).
"""

from datetime import timedelta

import pytest

from app.alerting.domain.models.alert import AlertSeverity
from app.alerting.domain.models.rule import (
    AlertChannel,
    AlertRule,
    ComparisonOperator,
    RuleCondition,
)


def _condition(**overrides) -> RuleCondition:
    defaults = {
        "metric_name": "cpu_pct",
        "threshold_value": 90.0,
        "comparison_operator": ComparisonOperator.GREATER_THAN,
        "evaluation_window_seconds": 300,
    }
    defaults.update(overrides)
    return RuleCondition(**defaults)


class TestComparisonOperator:
    def test_values(self):
        assert ComparisonOperator.GREATER_THAN.value == ">"
        assert ComparisonOperator.LESS_THAN.value == "<"
        assert ComparisonOperator.GREATER_EQUAL.value == ">="
        assert ComparisonOperator.LESS_EQUAL.value == "<="
        assert ComparisonOperator.EQUAL.value == "=="
        assert ComparisonOperator.NOT_EQUAL.value == "!="

    @pytest.mark.parametrize("op", [">", "<", ">=", "<=", "==", "!="])
    def test_is_valid_true(self, op):
        assert ComparisonOperator.is_valid(op) is True

    @pytest.mark.parametrize("op", ["", "??", "approximately", ">>"])
    def test_is_valid_false(self, op):
        assert ComparisonOperator.is_valid(op) is False


class TestRuleCondition:
    def test_empty_metric_name_raises(self):
        with pytest.raises(ValueError, match="Metric name cannot be empty"):
            RuleCondition(
                metric_name="",
                threshold_value=10.0,
                comparison_operator=ComparisonOperator.GREATER_THAN,
            )

    @pytest.mark.parametrize("window", [0, -1, -100])
    def test_non_positive_window_raises(self, window):
        with pytest.raises(ValueError, match="must be positive"):
            RuleCondition(
                metric_name="x",
                threshold_value=1.0,
                comparison_operator=ComparisonOperator.GREATER_THAN,
                evaluation_window_seconds=window,
            )

    def test_invalid_operator_type_raises(self):
        with pytest.raises(ValueError, match="Invalid comparison operator"):
            RuleCondition(
                metric_name="x",
                threshold_value=1.0,
                comparison_operator=">",  # str not enum
            )

    @pytest.mark.parametrize(
        "op,current,threshold,expected",
        [
            (ComparisonOperator.GREATER_THAN, 10.0, 5.0, True),
            (ComparisonOperator.GREATER_THAN, 5.0, 5.0, False),
            (ComparisonOperator.LESS_THAN, 1.0, 5.0, True),
            (ComparisonOperator.LESS_THAN, 5.0, 5.0, False),
            (ComparisonOperator.GREATER_EQUAL, 5.0, 5.0, True),
            (ComparisonOperator.GREATER_EQUAL, 4.9, 5.0, False),
            (ComparisonOperator.LESS_EQUAL, 5.0, 5.0, True),
            (ComparisonOperator.LESS_EQUAL, 5.1, 5.0, False),
            (ComparisonOperator.EQUAL, 5.0, 5.0, True),
            (ComparisonOperator.EQUAL, 5.1, 5.0, False),
            (ComparisonOperator.NOT_EQUAL, 5.1, 5.0, True),
            (ComparisonOperator.NOT_EQUAL, 5.0, 5.0, False),
        ],
    )
    def test_evaluate(self, op, current, threshold, expected):
        c = RuleCondition(
            metric_name="m", threshold_value=threshold, comparison_operator=op
        )
        assert c.evaluate(current) is expected

    def test_describe_format(self):
        c = _condition(threshold_value=80.0)
        assert c.describe() == "cpu_pct > 80.0"

    def test_is_frozen(self):
        c = _condition()
        with pytest.raises(Exception):
            c.metric_name = "other"


class TestAlertChannel:
    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Invalid channel type"):
            AlertChannel(channel_type="wat")

    @pytest.mark.parametrize(
        "ch_type", ["email", "slack", "webhook", "discord", "sms"]
    )
    def test_valid_types(self, ch_type):
        ch = AlertChannel(channel_type=ch_type)
        assert ch.channel_type == ch_type

    def test_default_enabled(self):
        ch = AlertChannel(channel_type="email")
        assert ch.enabled is True

    def test_explicit_disabled(self):
        ch = AlertChannel(channel_type="email", enabled=False)
        assert ch.enabled is False


class TestAlertRuleConstruction:
    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name cannot be empty"):
            AlertRule(name="", condition=_condition())

    def test_missing_condition_raises(self):
        with pytest.raises(ValueError, match="must have a condition"):
            AlertRule(name="my rule", condition=None)

    def test_zero_trigger_count_raises(self):
        with pytest.raises(ValueError, match="Trigger count must be at least 1"):
            AlertRule(name="r", condition=_condition(), trigger_count=0)

    def test_negative_cooldown_raises(self):
        with pytest.raises(ValueError, match="Cooldown period cannot be negative"):
            AlertRule(name="r", condition=_condition(), cooldown_period_seconds=-1)

    def test_default_rule_id_unique(self):
        a = AlertRule(name="r", condition=_condition())
        b = AlertRule(name="r", condition=_condition())
        assert a.rule_id != b.rule_id


class TestAlertRuleChannels:
    def test_add_remove_channel(self):
        r = AlertRule(name="r", condition=_condition())
        r.add_channel("email")
        r.add_channel("slack")
        assert {ch.channel_type for ch in r.channels} == {"email", "slack"}
        r.remove_channel("email")
        assert {ch.channel_type for ch in r.channels} == {"slack"}

    def test_get_enabled_channels(self):
        r = AlertRule(name="r", condition=_condition())
        r.add_channel("email", enabled=True)
        r.add_channel("slack", enabled=False)
        enabled = r.get_enabled_channels()
        assert "email" in enabled
        assert "slack" not in enabled


class TestAlertRuleTags:
    def test_add_tag_lowercases(self):
        r = AlertRule(name="r", condition=_condition())
        r.add_tag("Production")
        r.add_tag("DataBase")
        assert "production" in r.tags
        assert "database" in r.tags

    def test_add_empty_tag_ignored(self):
        r = AlertRule(name="r", condition=_condition())
        r.add_tag("")
        assert r.tags == set()

    def test_remove_tag(self):
        r = AlertRule(name="r", condition=_condition())
        r.add_tag("prod")
        r.remove_tag("PROD")  # case-insensitive
        assert "prod" not in r.tags

    def test_has_tag(self):
        r = AlertRule(name="r", condition=_condition())
        r.add_tag("prod")
        assert r.has_tag("PROD") is True
        assert r.has_tag("dev") is False

    def test_matches_tags_subset(self):
        r = AlertRule(name="r", condition=_condition())
        r.add_tag("prod")
        r.add_tag("payments")
        assert r.matches_tags({"prod"}) is True
        assert r.matches_tags({"prod", "payments"}) is True
        assert r.matches_tags({"prod", "missing"}) is False


class TestAlertRuleStateTransitions:
    def test_enable_disable(self):
        r = AlertRule(name="r", condition=_condition(), enabled=False)
        assert r.enabled is False
        r.enable()
        assert r.enabled is True
        r.disable()
        assert r.enabled is False

    def test_update_severity(self):
        r = AlertRule(name="r", condition=_condition())
        r.update_severity(AlertSeverity.CRITICAL)
        assert r.severity == AlertSeverity.CRITICAL

    def test_update_condition_valid(self):
        r = AlertRule(name="r", condition=_condition())
        r.update_condition(
            metric_name="memory",
            threshold_value=80.0,
            comparison_operator=">=",
            evaluation_window_seconds=60,
        )
        assert r.condition.metric_name == "memory"
        assert r.condition.threshold_value == 80.0
        assert r.condition.comparison_operator == ComparisonOperator.GREATER_EQUAL
        assert r.condition.evaluation_window_seconds == 60

    def test_update_condition_invalid_operator_raises(self):
        r = AlertRule(name="r", condition=_condition())
        with pytest.raises(ValueError, match="Invalid comparison operator"):
            r.update_condition("x", 1.0, "??")

    def test_update_trigger_settings_valid(self):
        r = AlertRule(name="r", condition=_condition())
        r.update_trigger_settings(trigger_count=3, cooldown_period_seconds=600)
        assert r.trigger_count == 3
        assert r.cooldown_period_seconds == 600

    def test_update_trigger_settings_zero_count_raises(self):
        r = AlertRule(name="r", condition=_condition())
        with pytest.raises(ValueError, match="Trigger count must be at least 1"):
            r.update_trigger_settings(0, 60)

    def test_update_trigger_settings_negative_cooldown_raises(self):
        r = AlertRule(name="r", condition=_condition())
        with pytest.raises(ValueError, match="Cooldown period cannot be negative"):
            r.update_trigger_settings(1, -10)


class TestAlertRuleQueries:
    def test_is_high_priority(self):
        for sev in (AlertSeverity.HIGH, AlertSeverity.CRITICAL):
            r = AlertRule(name="r", condition=_condition(), severity=sev)
            assert r.is_high_priority() is True
        for sev in (AlertSeverity.LOW, AlertSeverity.MEDIUM):
            r = AlertRule(name="r", condition=_condition(), severity=sev)
            assert r.is_high_priority() is False

    def test_get_cooldown_duration(self):
        r = AlertRule(name="r", condition=_condition(), cooldown_period_seconds=120)
        assert r.get_cooldown_duration() == timedelta(seconds=120)

    def test_get_evaluation_window(self):
        r = AlertRule(
            name="r", condition=_condition(evaluation_window_seconds=600)
        )
        assert r.get_evaluation_window() == timedelta(seconds=600)


class TestAlertRuleSerialization:
    def test_to_dict_roundtrip_minimal(self):
        r = AlertRule(name="r", condition=_condition(), severity=AlertSeverity.HIGH)
        r.add_channel("email")
        r.add_tag("prod")
        r.metadata = {"owner": "ops"}
        d = r.to_dict()
        assert d["name"] == "r"
        assert d["severity"] == "high"
        assert d["condition"]["metric_name"] == "cpu_pct"
        assert d["condition"]["comparison_operator"] == ">"
        assert d["channels"] == [{"channel_type": "email", "enabled": True}]
        assert "prod" in d["tags"]
        assert d["metadata"] == {"owner": "ops"}

    def test_to_dict_no_condition_path_unreachable(self):
        # AlertRule.__post_init__ rejects None condition, so the
        # `if self.condition` branch in to_dict cannot be exercised on a
        # validly-constructed instance. Documented for completeness.
        with pytest.raises(ValueError):
            AlertRule(name="r", condition=None).to_dict()
