"""
Unit tests for app.alerting.domain.models.notification

Pure value-object / aggregate tests for notification domain.
"""

from datetime import datetime, timedelta

import pytest

from app.alerting.domain.models.alert import Alert, AlertSeverity
from app.alerting.domain.models.notification import (
    NotificationChannel,
    NotificationPriority,
    NotificationRequest,
    NotificationStatus,
    NotificationTemplate,
)


def _alert(**overrides) -> Alert:
    defaults = {
        "rule_id": "rule-1",
        "title": "CPU spike",
        "description": "CPU > 90%",
        "severity": AlertSeverity.HIGH,
    }
    defaults.update(overrides)
    return Alert(**defaults)


def _slack_channel(**overrides) -> NotificationChannel:
    defaults = {
        "channel_id": "ch-1",
        "channel_type": "slack",
        "name": "Ops Slack",
        "config": {"webhook_url": "https://hooks.slack.example/abc"},
    }
    defaults.update(overrides)
    return NotificationChannel(**defaults)


class TestNotificationStatus:
    def test_values(self):
        assert NotificationStatus.PENDING.value == "pending"
        assert NotificationStatus.SENT.value == "sent"
        assert NotificationStatus.FAILED.value == "failed"
        assert NotificationStatus.RETRYING.value == "retrying"
        assert NotificationStatus.RATE_LIMITED.value == "rate_limited"


class TestNotificationPriority:
    def test_values(self):
        assert {p.value for p in NotificationPriority} == {
            "low",
            "normal",
            "high",
            "urgent",
        }


class TestNotificationTemplate:
    def test_render_subject_and_body(self):
        t = NotificationTemplate(
            template_id="t1",
            channel_type="email",
            subject_template="Alert: {title}",
            body_template="{title} on {host}",
        )
        assert t.render_subject({"title": "X"}) == "Alert: X"
        assert t.render_body({"title": "X", "host": "h1"}) == "X on h1"

    def test_render_subject_missing_var_raises(self):
        t = NotificationTemplate(
            template_id="t1",
            channel_type="email",
            subject_template="Alert: {title}",
            body_template="-",
        )
        with pytest.raises(ValueError, match="Missing template variable"):
            t.render_subject({"wrong": "X"})

    def test_render_body_missing_var_raises(self):
        t = NotificationTemplate(
            template_id="t1",
            channel_type="email",
            subject_template="-",
            body_template="Hello {name}",
        )
        with pytest.raises(ValueError, match="Missing template variable"):
            t.render_body({})

    def test_template_is_frozen(self):
        t = NotificationTemplate(
            template_id="t1",
            channel_type="email",
            subject_template="-",
            body_template="-",
        )
        with pytest.raises(Exception):
            t.template_id = "t2"


class TestNotificationChannelValidation:
    def test_invalid_channel_type_raises(self):
        with pytest.raises(ValueError, match="Invalid channel type"):
            NotificationChannel(
                channel_id="x",
                channel_type="carrier-pigeon",
                name="x",
                config={"foo": "bar"},
            )

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="name cannot be empty"):
            NotificationChannel(
                channel_id="x",
                channel_type="slack",
                name="",
                config={"webhook_url": "u"},
            )

    def test_empty_config_raises(self):
        with pytest.raises(ValueError, match="config cannot be empty"):
            NotificationChannel(
                channel_id="x",
                channel_type="slack",
                name="x",
                config={},
            )

    @pytest.mark.parametrize(
        "ch_type,bad_config",
        [
            ("email", {"smtp_server": "s"}),  # missing username/password/to_addresses
            ("slack", {"not_webhook": "x"}),
            ("webhook", {"x": "y"}),
            ("discord", {"x": "y"}),
            ("sms", {"api_key": "k"}),
        ],
    )
    def test_missing_required_keys_raises(self, ch_type, bad_config):
        with pytest.raises(ValueError, match="Missing required config keys"):
            NotificationChannel(
                channel_id="x", channel_type=ch_type, name="x", config=bad_config
            )

    def test_email_full_config_ok(self):
        ch = NotificationChannel(
            channel_id="e1",
            channel_type="email",
            name="ops email",
            config={
                "smtp_server": "smtp.example.com",
                "username": "u",
                "password": "p",
                "to_addresses": ["ops@example.com"],
            },
        )
        assert ch.channel_type == "email"


class TestNotificationChannelBehavior:
    def test_supports_priority_no_filter_allows_all(self):
        ch = _slack_channel()
        for p in NotificationPriority:
            assert ch.supports_priority(p) is True

    def test_supports_priority_with_filter(self):
        ch = _slack_channel(priority_filter=NotificationPriority.HIGH)
        assert ch.supports_priority(NotificationPriority.LOW) is False
        assert ch.supports_priority(NotificationPriority.NORMAL) is False
        assert ch.supports_priority(NotificationPriority.HIGH) is True
        assert ch.supports_priority(NotificationPriority.URGENT) is True

    def test_is_rate_limited_no_limit(self):
        ch = _slack_channel()
        assert ch.is_rate_limited(99999) is False

    def test_is_rate_limited_under_limit(self):
        ch = _slack_channel(rate_limit_per_hour=10)
        assert ch.is_rate_limited(5) is False

    def test_is_rate_limited_at_limit(self):
        ch = _slack_channel(rate_limit_per_hour=10)
        assert ch.is_rate_limited(10) is True

    def test_is_rate_limited_over_limit(self):
        ch = _slack_channel(rate_limit_per_hour=10)
        assert ch.is_rate_limited(11) is True


class TestNotificationRequestValidation:
    def test_requires_alert(self):
        with pytest.raises(ValueError, match="Alert is required"):
            NotificationRequest(alert=None, channel=_slack_channel())

    def test_requires_channel(self):
        with pytest.raises(ValueError, match="Channel is required"):
            NotificationRequest(alert=_alert(), channel=None)

    def test_disabled_channel_rejected(self):
        ch = _slack_channel(enabled=False)
        with pytest.raises(ValueError, match="disabled channel"):
            NotificationRequest(alert=_alert(), channel=ch)


class TestNotificationRequestContent:
    def test_prepare_content_default(self):
        req = NotificationRequest(alert=_alert(), channel=_slack_channel())
        req.prepare_content()
        assert req.subject == "[HIGH] CPU spike"
        assert "CPU spike" in req.message
        assert "HIGH" in req.message
        assert "Triggered" in req.message

    def test_prepare_content_with_template(self):
        tpl = NotificationTemplate(
            template_id="t1",
            channel_type="slack",
            subject_template="{severity}:{title}",
            body_template="alert {alert_id}",
        )
        a = _alert()
        req = NotificationRequest(alert=a, channel=_slack_channel(), template=tpl)
        req.prepare_content()
        assert req.subject == f"high:CPU spike"
        assert req.message == f"alert {a.alert_id}"

    def test_prepare_content_includes_metrics(self):
        from app.alerting.domain.models.alert import AlertMetrics

        a = _alert()
        a.metrics = AlertMetrics(
            metric_name="cpu",
            current_value=92.5,
            threshold_value=90.0,
            comparison_operator=">",
            evaluation_window_seconds=60,
        )
        req = NotificationRequest(alert=a, channel=_slack_channel())
        req.prepare_content()
        assert "cpu" in req.message
        assert "92.5" in req.message
        assert "90.0" in req.message


class TestNotificationRequestLifecycle:
    def test_mark_sent(self):
        req = NotificationRequest(alert=_alert(), channel=_slack_channel())
        req.mark_sent({"provider_id": "abc"})
        assert req.status == NotificationStatus.SENT
        assert req.sent_at is not None
        assert req.delivery_metadata["provider_id"] == "abc"

    def test_mark_sent_without_metadata(self):
        req = NotificationRequest(alert=_alert(), channel=_slack_channel())
        req.mark_sent()
        assert req.status == NotificationStatus.SENT
        assert req.delivery_metadata == {}

    def test_mark_failed(self):
        req = NotificationRequest(alert=_alert(), channel=_slack_channel())
        req.mark_failed("connection refused")
        assert req.status == NotificationStatus.FAILED
        assert req.failed_at is not None
        assert req.error_message == "connection refused"

    def test_mark_rate_limited(self):
        req = NotificationRequest(alert=_alert(), channel=_slack_channel())
        req.mark_rate_limited()
        assert req.status == NotificationStatus.RATE_LIMITED

    def test_can_retry_only_after_failure(self):
        req = NotificationRequest(alert=_alert(), channel=_slack_channel())
        assert req.can_retry() is False  # pending
        req.mark_failed("err")
        assert req.can_retry() is True

    def test_can_retry_max_exhausted(self):
        req = NotificationRequest(
            alert=_alert(), channel=_slack_channel(), max_retries=1
        )
        req.mark_failed("err")
        req.increment_retry()
        # status now retrying; mark failed again to be eligible-ish
        req.mark_failed("err2")
        assert req.can_retry() is False

    def test_increment_retry_when_not_eligible_raises(self):
        req = NotificationRequest(alert=_alert(), channel=_slack_channel())
        with pytest.raises(ValueError, match="Cannot retry"):
            req.increment_retry()

    def test_increment_retry_updates_status(self):
        req = NotificationRequest(alert=_alert(), channel=_slack_channel())
        req.mark_failed("err")
        req.increment_retry()
        assert req.retry_count == 1
        assert req.status == NotificationStatus.RETRYING


class TestNotificationRequestQueries:
    def test_is_urgent_via_priority(self):
        req = NotificationRequest(
            alert=_alert(severity=AlertSeverity.LOW),
            channel=_slack_channel(),
            priority=NotificationPriority.URGENT,
        )
        assert req.is_urgent() is True

    def test_is_urgent_via_alert_severity(self):
        req = NotificationRequest(
            alert=_alert(severity=AlertSeverity.CRITICAL),
            channel=_slack_channel(),
            priority=NotificationPriority.NORMAL,
        )
        assert req.is_urgent() is True

    def test_is_not_urgent(self):
        req = NotificationRequest(
            alert=_alert(severity=AlertSeverity.MEDIUM),
            channel=_slack_channel(),
            priority=NotificationPriority.NORMAL,
        )
        assert req.is_urgent() is False

    def test_age_minutes_positive(self):
        req = NotificationRequest(alert=_alert(), channel=_slack_channel())
        req.created_at = datetime.now() - timedelta(minutes=2)
        assert req.get_age_minutes() >= 2.0


class TestNotificationRequestSerialization:
    def test_to_dict_minimal(self):
        a = _alert()
        ch = _slack_channel()
        req = NotificationRequest(alert=a, channel=ch)
        d = req.to_dict()
        assert d["alert_id"] == a.alert_id
        assert d["channel_id"] == ch.channel_id
        assert d["status"] == "pending"
        assert d["sent_at"] is None
        assert d["failed_at"] is None
        assert d["retry_count"] == 0

    def test_to_dict_after_send(self):
        req = NotificationRequest(alert=_alert(), channel=_slack_channel())
        req.mark_sent({"provider_id": "p1"})
        d = req.to_dict()
        assert d["status"] == "sent"
        assert d["sent_at"] is not None
        assert d["delivery_metadata"] == {"provider_id": "p1"}

    def test_to_dict_after_failure(self):
        req = NotificationRequest(alert=_alert(), channel=_slack_channel())
        req.mark_failed("boom")
        d = req.to_dict()
        assert d["status"] == "failed"
        assert d["failed_at"] is not None
        assert d["error_message"] == "boom"
