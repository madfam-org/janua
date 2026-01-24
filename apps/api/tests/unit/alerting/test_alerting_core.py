"""
Comprehensive tests for alerting core module
Tests alert types, models, and evaluator

Note: AlertManager tests are skipped because they require monitoring.apm
which has OpenTelemetry dependencies not installed in test environment.

Import Strategy:
The alerting package __init__.py imports AlertManager which imports monitoring.apm
which calls asyncio.create_task() at module level. To avoid this, we:
1. Mock the opentelemetry modules
2. Mock the monitoring.apm module with a fake apm_collector
3. Mock the alerting package __init__.py to prevent the chain
"""

import sys
from datetime import datetime
from unittest.mock import AsyncMock, Mock, MagicMock, patch

import pytest

# Mock the opentelemetry modules before importing alerting
mock_otel = MagicMock()
sys.modules["opentelemetry.exporter.jaeger"] = mock_otel
sys.modules["opentelemetry.exporter.jaeger.thrift"] = mock_otel
sys.modules["opentelemetry.exporter.prometheus"] = mock_otel
sys.modules["opentelemetry.sdk.metrics"] = mock_otel
sys.modules["opentelemetry.sdk.metrics.export"] = mock_otel
sys.modules["opentelemetry.metrics"] = mock_otel

# Mock the monitoring.apm module which has async init issues
mock_apm = MagicMock()
mock_apm.apm_collector = MagicMock()
sys.modules["app.monitoring.apm"] = mock_apm


class TestAlertSeverityEnum:
    """Test AlertSeverity enumeration."""

    def test_severity_values(self):
        """Test severity enum values."""
        from app.alerting.core.alert_types import AlertSeverity

        assert AlertSeverity.LOW.value == "low"
        assert AlertSeverity.MEDIUM.value == "medium"
        assert AlertSeverity.HIGH.value == "high"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_severity_comparison(self):
        """Test severity enums can be compared."""
        from app.alerting.core.alert_types import AlertSeverity

        assert AlertSeverity.LOW != AlertSeverity.HIGH
        assert AlertSeverity.CRITICAL == AlertSeverity.CRITICAL

    def test_severity_from_string(self):
        """Test creating severity from string value."""
        from app.alerting.core.alert_types import AlertSeverity

        assert AlertSeverity("low") == AlertSeverity.LOW
        assert AlertSeverity("critical") == AlertSeverity.CRITICAL


class TestAlertStatusEnum:
    """Test AlertStatus enumeration."""

    def test_status_values(self):
        """Test status enum values."""
        from app.alerting.core.alert_types import AlertStatus

        assert AlertStatus.TRIGGERED.value == "triggered"
        assert AlertStatus.ACKNOWLEDGED.value == "acknowledged"
        assert AlertStatus.RESOLVED.value == "resolved"
        assert AlertStatus.SUPPRESSED.value == "suppressed"


class TestAlertChannelEnum:
    """Test AlertChannel enumeration."""

    def test_channel_values(self):
        """Test channel enum values."""
        from app.alerting.core.alert_types import AlertChannel

        assert AlertChannel.EMAIL.value == "email"
        assert AlertChannel.SLACK.value == "slack"
        assert AlertChannel.WEBHOOK.value == "webhook"
        assert AlertChannel.SMS.value == "sms"
        assert AlertChannel.DISCORD.value == "discord"


class TestAlertRule:
    """Test AlertRule dataclass."""

    def test_alert_rule_creation(self):
        """Test creating an alert rule."""
        from app.alerting.core.alert_types import AlertSeverity
        from app.alerting.core.alert_models import AlertRule

        rule = AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            description="A test alert rule",
            severity=AlertSeverity.HIGH,
            metric_name="test_metric",
            threshold_value=100.0,
            comparison_operator=">",
            evaluation_window=300,
        )

        assert rule.rule_id == "test_rule"
        assert rule.name == "Test Rule"
        assert rule.severity == AlertSeverity.HIGH
        assert rule.threshold_value == 100.0
        assert rule.comparison_operator == ">"

    def test_alert_rule_defaults(self):
        """Test alert rule default values."""
        from app.alerting.core.alert_types import AlertSeverity
        from app.alerting.core.alert_models import AlertRule

        rule = AlertRule(
            rule_id="test",
            name="Test",
            description="Test",
            severity=AlertSeverity.LOW,
            metric_name="metric",
            threshold_value=0.0,
            comparison_operator="==",
            evaluation_window=60,
        )

        assert rule.trigger_count == 1
        assert rule.cooldown_period == 300
        assert rule.enabled is True
        assert rule.channels == []
        assert rule.conditions == {}
        assert rule.metadata == {}

    def test_alert_rule_with_channels(self):
        """Test alert rule with notification channels."""
        from app.alerting.core.alert_types import AlertSeverity, AlertChannel
        from app.alerting.core.alert_models import AlertRule

        rule = AlertRule(
            rule_id="multi_channel",
            name="Multi Channel Rule",
            description="Alert with multiple channels",
            severity=AlertSeverity.CRITICAL,
            metric_name="critical_metric",
            threshold_value=95.0,
            comparison_operator=">=",
            evaluation_window=120,
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.WEBHOOK],
        )

        assert len(rule.channels) == 3
        assert AlertChannel.EMAIL in rule.channels
        assert AlertChannel.SLACK in rule.channels


class TestAlert:
    """Test Alert dataclass."""

    def test_alert_creation(self):
        """Test creating an alert."""
        from app.alerting.core.alert_types import AlertSeverity, AlertStatus
        from app.alerting.core.alert_models import Alert

        now = datetime.utcnow()
        alert = Alert(
            alert_id="alert_001",
            rule_id="test_rule",
            severity=AlertSeverity.HIGH,
            status=AlertStatus.TRIGGERED,
            title="High CPU Usage",
            description="CPU usage exceeded 90%",
            metric_value=95.5,
            threshold_value=90.0,
            triggered_at=now,
        )

        assert alert.alert_id == "alert_001"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.TRIGGERED
        assert alert.metric_value == 95.5
        assert alert.triggered_at == now

    def test_alert_defaults(self):
        """Test alert default values."""
        from app.alerting.core.alert_types import AlertSeverity, AlertStatus
        from app.alerting.core.alert_models import Alert

        alert = Alert(
            alert_id="test",
            rule_id="rule",
            severity=AlertSeverity.LOW,
            status=AlertStatus.TRIGGERED,
            title="Test",
            description="Test",
            metric_value=0.0,
            threshold_value=0.0,
            triggered_at=datetime.utcnow(),
        )

        assert alert.acknowledged_at is None
        assert alert.resolved_at is None
        assert alert.acknowledged_by is None
        assert alert.context == {}
        assert alert.notifications_sent == []


class TestNotificationChannel:
    """Test NotificationChannel dataclass."""

    def test_channel_creation(self):
        """Test creating a notification channel."""
        from app.alerting.core.alert_types import AlertChannel
        from app.alerting.core.alert_models import NotificationChannel

        channel = NotificationChannel(
            channel_id="slack_001",
            channel_type=AlertChannel.SLACK,
            name="Engineering Alerts",
            config={"webhook_url": "https://hooks.slack.com/..."},
        )

        assert channel.channel_id == "slack_001"
        assert channel.channel_type == AlertChannel.SLACK
        assert channel.name == "Engineering Alerts"
        assert "webhook_url" in channel.config

    def test_channel_defaults(self):
        """Test notification channel defaults."""
        from app.alerting.core.alert_types import AlertChannel
        from app.alerting.core.alert_models import NotificationChannel

        channel = NotificationChannel(
            channel_id="test",
            channel_type=AlertChannel.EMAIL,
            name="Test",
            config={},
        )

        assert channel.enabled is True
        assert channel.rate_limit is None

    def test_channel_with_rate_limit(self):
        """Test notification channel with rate limit."""
        from app.alerting.core.alert_types import AlertChannel
        from app.alerting.core.alert_models import NotificationChannel

        channel = NotificationChannel(
            channel_id="rate_limited",
            channel_type=AlertChannel.EMAIL,
            name="Rate Limited Email",
            config={"recipients": ["ops@example.com"]},
            rate_limit=10,  # max 10 per hour
        )

        assert channel.rate_limit == 10


class TestAlertEvaluator:
    """Test AlertEvaluator class."""

    def _get_evaluator(self):
        """Create an evaluator instance."""
        from app.alerting.core.alert_evaluator import AlertEvaluator
        return AlertEvaluator()

    def _get_sample_rule(self):
        """Create a sample alert rule."""
        from app.alerting.core.alert_types import AlertSeverity
        from app.alerting.core.alert_models import AlertRule

        return AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test",
            severity=AlertSeverity.HIGH,
            metric_name="test_metric",
            threshold_value=100.0,
            comparison_operator=">",
            evaluation_window=300,
            trigger_count=1,
        )

    def test_evaluator_initialization(self):
        """Test evaluator initializes correctly."""
        evaluator = self._get_evaluator()
        assert evaluator.evaluation_history == {}

    def test_evaluate_greater_than_true(self):
        """Test greater than comparison - true case."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.comparison_operator = ">"
        rule.threshold_value = 100.0

        result = evaluator.evaluate_rule(rule, 150.0)
        assert result is True

    def test_evaluate_greater_than_false(self):
        """Test greater than comparison - false case."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.comparison_operator = ">"
        rule.threshold_value = 100.0

        result = evaluator.evaluate_rule(rule, 50.0)
        assert result is False

    def test_evaluate_less_than_true(self):
        """Test less than comparison - true case."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.comparison_operator = "<"
        rule.threshold_value = 100.0

        result = evaluator.evaluate_rule(rule, 50.0)
        assert result is True

    def test_evaluate_less_than_false(self):
        """Test less than comparison - false case."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.comparison_operator = "<"
        rule.threshold_value = 100.0

        result = evaluator.evaluate_rule(rule, 150.0)
        assert result is False

    def test_evaluate_greater_equal_true(self):
        """Test greater or equal comparison - true case."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.comparison_operator = ">="
        rule.threshold_value = 100.0

        # Exactly equal
        result = evaluator.evaluate_rule(rule, 100.0)
        assert result is True

    def test_evaluate_greater_equal_greater(self):
        """Test greater or equal comparison with greater value."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.comparison_operator = ">="
        rule.threshold_value = 100.0

        result = evaluator.evaluate_rule(rule, 150.0)
        assert result is True

    def test_evaluate_less_equal_true(self):
        """Test less or equal comparison - true case."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.comparison_operator = "<="
        rule.threshold_value = 100.0

        # Exactly equal
        result = evaluator.evaluate_rule(rule, 100.0)
        assert result is True

    def test_evaluate_less_equal_less(self):
        """Test less or equal comparison with less value."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.comparison_operator = "<="
        rule.threshold_value = 100.0

        result = evaluator.evaluate_rule(rule, 50.0)
        assert result is True

    def test_evaluate_equal_true(self):
        """Test equal comparison - true case."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.comparison_operator = "=="
        rule.threshold_value = 100.0

        result = evaluator.evaluate_rule(rule, 100.0)
        assert result is True

    def test_evaluate_equal_false(self):
        """Test equal comparison - false case."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.comparison_operator = "=="
        rule.threshold_value = 100.0

        result = evaluator.evaluate_rule(rule, 99.0)
        assert result is False

    def test_evaluate_not_equal_true(self):
        """Test not equal comparison - true case."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.comparison_operator = "!="
        rule.threshold_value = 100.0

        result = evaluator.evaluate_rule(rule, 99.0)
        assert result is True

    def test_evaluate_not_equal_false(self):
        """Test not equal comparison - false case."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.comparison_operator = "!="
        rule.threshold_value = 100.0

        result = evaluator.evaluate_rule(rule, 100.0)
        assert result is False

    def test_evaluate_unknown_operator(self):
        """Test unknown comparison operator returns false."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.comparison_operator = "???"

        result = evaluator.evaluate_rule(rule, 100.0)
        assert result is False

    def test_trigger_count_requirement(self):
        """Test trigger count requirement for alerts."""
        from app.alerting.core.alert_types import AlertSeverity
        from app.alerting.core.alert_models import AlertRule

        evaluator = self._get_evaluator()
        rule = AlertRule(
            rule_id="trigger_test",
            name="Trigger Test",
            description="Test",
            severity=AlertSeverity.HIGH,
            metric_name="test",
            threshold_value=100.0,
            comparison_operator=">",
            evaluation_window=300,
            trigger_count=3,  # Need 3 consecutive evaluations
        )

        # First evaluation - not enough history
        result = evaluator.evaluate_rule(rule, 150.0)
        assert result is False

        # Second evaluation - still not enough
        result = evaluator.evaluate_rule(rule, 150.0)
        assert result is False

        # Third evaluation - should trigger
        result = evaluator.evaluate_rule(rule, 150.0)
        assert result is True

    def test_trigger_count_reset_on_false(self):
        """Test that trigger count resets when condition is false."""
        from app.alerting.core.alert_types import AlertSeverity
        from app.alerting.core.alert_models import AlertRule

        evaluator = self._get_evaluator()
        rule = AlertRule(
            rule_id="reset_test",
            name="Reset Test",
            description="Test",
            severity=AlertSeverity.HIGH,
            metric_name="test",
            threshold_value=100.0,
            comparison_operator=">",
            evaluation_window=300,
            trigger_count=2,
        )

        # First true
        evaluator.evaluate_rule(rule, 150.0)
        # False - should reset
        evaluator.evaluate_rule(rule, 50.0)
        # True again - need another true to trigger
        result = evaluator.evaluate_rule(rule, 150.0)
        assert result is False

        # Second true - now should trigger
        result = evaluator.evaluate_rule(rule, 150.0)
        assert result is True

    def test_evaluation_history_maintained(self):
        """Test that evaluation history is maintained."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()

        evaluator.evaluate_rule(rule, 150.0)
        evaluator.evaluate_rule(rule, 50.0)
        evaluator.evaluate_rule(rule, 150.0)

        assert rule.rule_id in evaluator.evaluation_history
        assert len(evaluator.evaluation_history[rule.rule_id]) == 3

    def test_evaluation_history_limited(self):
        """Test that evaluation history doesn't grow unbounded."""
        evaluator = self._get_evaluator()
        rule = self._get_sample_rule()
        rule.trigger_count = 3

        # Add many evaluations
        for i in range(20):
            evaluator.evaluate_rule(rule, 150.0 if i % 2 == 0 else 50.0)

        # History should be limited to max(trigger_count, 10)
        assert len(evaluator.evaluation_history[rule.rule_id]) <= 10


class TestAlertManager:
    """Test AlertManager class - skipped due to dependencies."""

    @pytest.mark.skip(reason="AlertManager requires monitoring.apm with OpenTelemetry")
    def test_import_alert_manager(self):
        """Test that AlertManager can be imported."""
        from app.alerting.core.alert_manager import AlertManager

        assert AlertManager is not None

    @pytest.mark.skip(reason="AlertManager requires Redis - integration test")
    async def test_alert_manager_initialization(self):
        """Test AlertManager initializes correctly."""
        from app.alerting.core.alert_manager import AlertManager

        manager = AlertManager()
        assert manager.alert_rules is not None
        assert manager.active_alerts is not None

    @pytest.mark.skip(reason="AlertManager requires monitoring.apm with OpenTelemetry")
    def test_alert_manager_has_default_rules(self):
        """Test AlertManager loads default rules."""
        from app.alerting.core.alert_manager import AlertManager

        manager = AlertManager()

        # Should have default rules loaded
        assert len(manager.alert_rules) > 0
        assert "high_response_time" in manager.alert_rules
        assert "high_error_rate" in manager.alert_rules
        assert "low_disk_space" in manager.alert_rules
