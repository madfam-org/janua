"""
Unit tests for app.alerting.domain.models.alert

Pure domain model tests - no external dependencies.
Covers: AlertSeverity, AlertStatus, AlertMetrics, AlertEvent, Alert, AlertAggregate.
"""

import time
from datetime import datetime, timedelta

import pytest

from app.alerting.domain.models.alert import (
    Alert,
    AlertAggregate,
    AlertEvent,
    AlertMetrics,
    AlertSeverity,
    AlertStatus,
)


def _make_alert(**overrides) -> Alert:
    """Build a valid Alert with sensible defaults for tests."""
    defaults = {
        "rule_id": "rule-1",
        "title": "Disk almost full",
        "description": "Disk usage exceeds 90%",
        "severity": AlertSeverity.MEDIUM,
        "status": AlertStatus.TRIGGERED,
    }
    defaults.update(overrides)
    return Alert(**defaults)


class TestAlertSeverity:
    def test_priority_score_ordering(self):
        assert AlertSeverity.LOW.priority_score() == 1
        assert AlertSeverity.MEDIUM.priority_score() == 2
        assert AlertSeverity.HIGH.priority_score() == 3
        assert AlertSeverity.CRITICAL.priority_score() == 4

    def test_priority_score_strictly_increasing(self):
        ordered = [
            AlertSeverity.LOW,
            AlertSeverity.MEDIUM,
            AlertSeverity.HIGH,
            AlertSeverity.CRITICAL,
        ]
        scores = [s.priority_score() for s in ordered]
        assert scores == sorted(scores)
        assert len(set(scores)) == len(scores)


class TestAlertStatus:
    def test_status_values(self):
        assert AlertStatus.TRIGGERED.value == "triggered"
        assert AlertStatus.ACKNOWLEDGED.value == "acknowledged"
        assert AlertStatus.RESOLVED.value == "resolved"
        assert AlertStatus.SUPPRESSED.value == "suppressed"
        assert AlertStatus.ESCALATED.value == "escalated"


class TestAlertMetrics:
    @pytest.mark.parametrize(
        "operator,current,threshold,expected",
        [
            (">", 10.0, 5.0, True),
            (">", 5.0, 5.0, False),
            ("<", 1.0, 5.0, True),
            ("<", 5.0, 5.0, False),
            (">=", 5.0, 5.0, True),
            (">=", 4.9, 5.0, False),
            ("<=", 5.0, 5.0, True),
            ("<=", 5.1, 5.0, False),
            ("==", 5.0, 5.0, True),
            ("==", 5.1, 5.0, False),
            ("!=", 5.1, 5.0, True),
            ("!=", 5.0, 5.0, False),
        ],
    )
    def test_is_breached_for_each_operator(self, operator, current, threshold, expected):
        m = AlertMetrics(
            metric_name="cpu",
            current_value=current,
            threshold_value=threshold,
            comparison_operator=operator,
            evaluation_window_seconds=60,
        )
        assert m.is_breached() is expected

    def test_invalid_operator_raises(self):
        m = AlertMetrics(
            metric_name="cpu",
            current_value=10.0,
            threshold_value=5.0,
            comparison_operator="??",
            evaluation_window_seconds=60,
        )
        with pytest.raises(ValueError, match="Invalid comparison operator"):
            m.is_breached()

    def test_metrics_are_immutable(self):
        m = AlertMetrics(
            metric_name="cpu",
            current_value=10.0,
            threshold_value=5.0,
            comparison_operator=">",
            evaluation_window_seconds=60,
        )
        with pytest.raises(Exception):
            m.current_value = 99.0  # frozen dataclass


class TestAlertEvent:
    def test_default_factories(self):
        e = AlertEvent()
        assert e.event_id  # uuid generated
        assert isinstance(e.timestamp, datetime)
        assert e.metadata == {}

    def test_explicit_fields_preserved(self):
        e = AlertEvent(
            alert_id="alert-1",
            event_type="acknowledged",
            metadata={"by": "alice"},
        )
        assert e.alert_id == "alert-1"
        assert e.event_type == "acknowledged"
        assert e.metadata == {"by": "alice"}

    def test_event_ids_are_unique(self):
        ids = {AlertEvent().event_id for _ in range(50)}
        assert len(ids) == 50


class TestAlertConstruction:
    def test_requires_title(self):
        with pytest.raises(ValueError, match="title cannot be empty"):
            Alert(rule_id="r1", title="")

    def test_requires_rule_id(self):
        with pytest.raises(ValueError, match="associated with a rule"):
            Alert(rule_id="", title="hi")

    def test_default_alert_id_is_unique_uuid(self):
        a = _make_alert()
        b = _make_alert()
        assert a.alert_id != b.alert_id

    def test_defaults(self):
        a = _make_alert()
        assert a.status == AlertStatus.TRIGGERED
        assert a.acknowledged_at is None
        assert a.resolved_at is None
        assert a.notifications_sent == []
        assert a.events == []


class TestAlertAcknowledge:
    def test_acknowledge_transitions_state(self):
        a = _make_alert()
        a.acknowledge("alice")
        assert a.status == AlertStatus.ACKNOWLEDGED
        assert a.acknowledged_by == "alice"
        assert a.acknowledged_at is not None
        assert any(e.event_type == "acknowledged" for e in a.events)

    def test_acknowledge_resolved_alert_raises(self):
        a = _make_alert(status=AlertStatus.RESOLVED)
        with pytest.raises(ValueError, match="resolved alert"):
            a.acknowledge("alice")

    def test_acknowledge_already_acknowledged_is_idempotent(self):
        a = _make_alert()
        a.acknowledge("alice")
        events_before = len(a.events)
        a.acknowledge("bob")  # no-op, still acked by alice
        assert a.acknowledged_by == "alice"
        assert len(a.events) == events_before


class TestAlertResolve:
    def test_resolve_sets_state(self):
        a = _make_alert()
        a.resolve("bob")
        assert a.status == AlertStatus.RESOLVED
        assert a.resolved_by == "bob"
        assert a.resolved_at is not None

    def test_resolve_without_actor_uses_system(self):
        a = _make_alert()
        a.resolve()
        assert a.status == AlertStatus.RESOLVED
        assert a.resolved_by is None  # not overwritten

    def test_resolve_idempotent(self):
        a = _make_alert()
        a.resolve("bob")
        first_event_count = len(a.events)
        a.resolve("carol")
        # No new event added on second resolve
        assert len(a.events) == first_event_count


class TestAlertSuppress:
    def test_suppress_records_reason(self):
        a = _make_alert()
        a.suppress("maintenance window")
        assert a.status == AlertStatus.SUPPRESSED
        assert a.context["suppression_reason"] == "maintenance window"

    def test_cannot_suppress_resolved(self):
        a = _make_alert(status=AlertStatus.RESOLVED)
        with pytest.raises(ValueError, match="resolved"):
            a.suppress("nope")


class TestAlertEscalate:
    def test_escalate_low_to_medium(self):
        a = _make_alert(severity=AlertSeverity.LOW)
        a.escalate("no response in 30m")
        assert a.severity == AlertSeverity.MEDIUM
        assert a.status == AlertStatus.ESCALATED
        assert a.escalated_at is not None

    def test_escalate_medium_to_high(self):
        a = _make_alert(severity=AlertSeverity.MEDIUM)
        a.escalate("still no response")
        assert a.severity == AlertSeverity.HIGH

    def test_escalate_high_to_critical(self):
        a = _make_alert(severity=AlertSeverity.HIGH)
        a.escalate("page on-call")
        assert a.severity == AlertSeverity.CRITICAL

    def test_escalate_critical_stays_critical(self):
        a = _make_alert(severity=AlertSeverity.CRITICAL)
        a.escalate("already maxed")
        assert a.severity == AlertSeverity.CRITICAL
        # but event still recorded
        assert any(e.event_type == "escalated" for e in a.events)

    def test_cannot_escalate_resolved(self):
        a = _make_alert(status=AlertStatus.RESOLVED)
        with pytest.raises(ValueError, match="resolved"):
            a.escalate("nope")


class TestAlertNotificationsAndContext:
    def test_add_notification_sent_dedupes(self):
        a = _make_alert()
        a.add_notification_sent("email:ops")
        a.add_notification_sent("email:ops")  # dup
        a.add_notification_sent("slack:#alerts")
        assert a.notifications_sent == ["email:ops", "slack:#alerts"]
        # only two events for two unique sends
        sent_events = [e for e in a.events if e.event_type == "notification_sent"]
        assert len(sent_events) == 2

    def test_update_context_merges(self):
        a = _make_alert()
        a.update_context({"host": "web-1"})
        a.update_context({"region": "us-east"})
        assert a.context["host"] == "web-1"
        assert a.context["region"] == "us-east"


class TestAlertQueries:
    def test_is_active_for_each_status(self):
        active_states = {
            AlertStatus.TRIGGERED,
            AlertStatus.ACKNOWLEDGED,
            AlertStatus.ESCALATED,
        }
        for st in AlertStatus:
            a = _make_alert(status=st)
            assert a.is_active() is (st in active_states)

    def test_is_critical(self):
        assert _make_alert(severity=AlertSeverity.CRITICAL).is_critical() is True
        assert _make_alert(severity=AlertSeverity.HIGH).is_critical() is False

    def test_age_minutes_positive(self):
        a = _make_alert()
        a.triggered_at = datetime.now() - timedelta(minutes=5)
        assert a.age_minutes() >= 5.0

    def test_time_to_acknowledge_minutes(self):
        a = _make_alert()
        a.triggered_at = datetime.now() - timedelta(minutes=10)
        assert a.time_to_acknowledge_minutes() is None
        a.acknowledge("alice")
        ttak = a.time_to_acknowledge_minutes()
        assert ttak is not None
        assert ttak >= 10.0

    def test_time_to_resolve_minutes(self):
        a = _make_alert()
        a.triggered_at = datetime.now() - timedelta(minutes=10)
        assert a.time_to_resolve_minutes() is None
        a.resolve("bob")
        ttr = a.time_to_resolve_minutes()
        assert ttr is not None
        assert ttr >= 10.0


class TestAlertEventLog:
    def test_get_events_returns_copy(self):
        a = _make_alert()
        a.acknowledge("alice")
        events = a.get_events()
        events.clear()  # mutate copy
        assert len(a.events) == 1  # original untouched

    def test_clear_events(self):
        a = _make_alert()
        a.acknowledge("alice")
        a.resolve("alice")
        assert len(a.events) >= 2
        a.clear_events()
        assert a.events == []


class TestAlertAggregate:
    def test_alert_property_exposes_underlying(self):
        a = _make_alert()
        agg = AlertAggregate(a)
        assert agg.alert is a

    def test_can_be_acknowledged(self):
        assert AlertAggregate(_make_alert(status=AlertStatus.TRIGGERED)).can_be_acknowledged()
        assert AlertAggregate(_make_alert(status=AlertStatus.ESCALATED)).can_be_acknowledged()
        assert not AlertAggregate(_make_alert(status=AlertStatus.RESOLVED)).can_be_acknowledged()
        assert not AlertAggregate(_make_alert(status=AlertStatus.SUPPRESSED)).can_be_acknowledged()

    def test_can_be_resolved(self):
        for st in AlertStatus:
            agg = AlertAggregate(_make_alert(status=st))
            expected = st != AlertStatus.RESOLVED
            assert agg.can_be_resolved() is expected

    def test_can_be_escalated(self):
        # Triggered + non-critical: yes
        assert AlertAggregate(
            _make_alert(status=AlertStatus.TRIGGERED, severity=AlertSeverity.HIGH)
        ).can_be_escalated()
        # Critical: no
        assert not AlertAggregate(
            _make_alert(status=AlertStatus.TRIGGERED, severity=AlertSeverity.CRITICAL)
        ).can_be_escalated()
        # Resolved: no
        assert not AlertAggregate(
            _make_alert(status=AlertStatus.RESOLVED, severity=AlertSeverity.HIGH)
        ).can_be_escalated()

    def test_should_auto_resolve_no_metrics(self):
        a = _make_alert(metrics=None)
        assert AlertAggregate(a).should_auto_resolve(0.0) is False

    def test_should_auto_resolve_when_threshold_no_longer_breached(self):
        m = AlertMetrics(
            metric_name="cpu",
            current_value=5.0,  # not breached: 5 > 50 is False
            threshold_value=50.0,
            comparison_operator=">",
            evaluation_window_seconds=60,
        )
        a = _make_alert(metrics=m)
        assert AlertAggregate(a).should_auto_resolve(5.0) is True

    def test_should_not_auto_resolve_when_breached(self):
        m = AlertMetrics(
            metric_name="cpu",
            current_value=99.0,
            threshold_value=50.0,
            comparison_operator=">",
            evaluation_window_seconds=60,
        )
        a = _make_alert(metrics=m)
        assert AlertAggregate(a).should_auto_resolve(99.0) is False

    def test_requires_escalation_resolved_returns_false(self):
        a = _make_alert(status=AlertStatus.RESOLVED)
        assert AlertAggregate(a).requires_escalation(max_age_minutes=1) is False

    def test_requires_escalation_when_old(self):
        a = _make_alert()
        a.triggered_at = datetime.now() - timedelta(minutes=120)
        assert AlertAggregate(a).requires_escalation(max_age_minutes=60) is True

    def test_requires_escalation_critical_uses_half_window(self):
        a = _make_alert(severity=AlertSeverity.CRITICAL)
        a.triggered_at = datetime.now() - timedelta(minutes=35)
        # Critical halves max_age, so 60->30; 35 > 30 -> True
        assert AlertAggregate(a).requires_escalation(max_age_minutes=60) is True

    def test_severity_color(self):
        for sev in AlertSeverity:
            a = _make_alert(severity=sev)
            color = AlertAggregate(a).get_severity_color()
            assert color.startswith("#") and len(color) == 7

    def test_to_dict_with_metrics(self):
        m = AlertMetrics(
            metric_name="cpu",
            current_value=99.0,
            threshold_value=50.0,
            comparison_operator=">",
            evaluation_window_seconds=60,
        )
        a = _make_alert(metrics=m, severity=AlertSeverity.HIGH)
        d = AlertAggregate(a).to_dict()
        assert d["alert_id"] == a.alert_id
        assert d["severity"] == "high"
        assert d["metrics"]["metric_name"] == "cpu"
        assert d["metrics"]["current_value"] == 99.0
        assert d["acknowledged_at"] is None
        assert d["resolved_at"] is None
        assert "age_minutes" in d

    def test_to_dict_without_metrics_and_with_timestamps(self):
        a = _make_alert(metrics=None)
        a.acknowledge("alice")
        a.resolve("alice")
        d = AlertAggregate(a).to_dict()
        assert d["metrics"] is None
        assert d["acknowledged_at"] is not None
        assert d["resolved_at"] is not None
        assert d["acknowledged_by"] == "alice"
        assert d["resolved_by"] == "alice"
