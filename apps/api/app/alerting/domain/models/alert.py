"""
Alert Domain Model - Aggregate Root
Represents the alert entity with its business rules and state transitions
"""

import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

import structlog

logger = structlog.get_logger()


class AlertSeverity(Enum):
    """Alert severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def priority_score(self) -> int:
        """Return numeric priority for sorting"""
        return {"low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]


class AlertStatus(Enum):
    """Alert status states"""

    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ESCALATED = "escalated"


@dataclass(frozen=True)
class AlertMetrics:
    """Value object for alert metrics"""

    metric_name: str
    current_value: float
    threshold_value: float
    comparison_operator: str
    evaluation_window_seconds: int

    def is_breached(self) -> bool:
        """Check if current value breaches threshold"""
        operators = {
            ">": lambda x, y: x > y,
            "<": lambda x, y: x < y,
            ">=": lambda x, y: x >= y,
            "<=": lambda x, y: x <= y,
            "==": lambda x, y: x == y,
            "!=": lambda x, y: x != y,
        }

        operator_func = operators.get(self.comparison_operator)
        if not operator_func:
            raise ValueError(f"Invalid comparison operator: {self.comparison_operator}")

        return operator_func(self.current_value, self.threshold_value)


@dataclass
class AlertEvent:
    """Domain event for alert state changes"""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    event_type: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    """Alert aggregate root - main domain entity"""

    # Identity
    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str = ""

    # Core properties
    severity: AlertSeverity = AlertSeverity.LOW
    status: AlertStatus = AlertStatus.TRIGGERED
    title: str = ""
    description: str = ""

    # Metrics and timing
    metrics: Optional[AlertMetrics] = None
    triggered_at: datetime = field(default_factory=datetime.now)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None

    # Actors
    acknowledged_by: Optional[str] = None
    resolved_by: Optional[str] = None

    # Context and history
    context: Dict[str, Any] = field(default_factory=dict)
    notifications_sent: List[str] = field(default_factory=list)

    # Events (for event sourcing)
    events: List[AlertEvent] = field(default_factory=list)

    def __post_init__(self):
        """Validate alert state after initialization"""
        if not self.title:
            raise ValueError("Alert title cannot be empty")
        if not self.rule_id:
            raise ValueError("Alert must be associated with a rule")

    def acknowledge(self, acknowledged_by: str) -> None:
        """Acknowledge the alert"""
        if self.status == AlertStatus.RESOLVED:
            raise ValueError("Cannot acknowledge resolved alert")

        if self.status == AlertStatus.ACKNOWLEDGED:
            logger.warning(f"Alert {self.alert_id} already acknowledged")
            return

        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now()
        self.acknowledged_by = acknowledged_by

        self._add_event("acknowledged", {"acknowledged_by": acknowledged_by})

        logger.info(f"Alert {self.alert_id} acknowledged by {acknowledged_by}")

    def resolve(self, resolved_by: Optional[str] = None) -> None:
        """Resolve the alert"""
        if self.status == AlertStatus.RESOLVED:
            logger.warning(f"Alert {self.alert_id} already resolved")
            return

        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now()
        if resolved_by:
            self.resolved_by = resolved_by

        self._add_event("resolved", {"resolved_by": resolved_by})

        logger.info(f"Alert {self.alert_id} resolved by {resolved_by or 'system'}")

    def suppress(self, reason: str) -> None:
        """Suppress the alert"""
        if self.status == AlertStatus.RESOLVED:
            raise ValueError("Cannot suppress resolved alert")

        self.status = AlertStatus.SUPPRESSED
        self.context["suppression_reason"] = reason

        self._add_event("suppressed", {"reason": reason})

        logger.info(f"Alert {self.alert_id} suppressed: {reason}")

    def escalate(self, escalation_reason: str) -> None:
        """Escalate the alert to higher severity"""
        if self.status == AlertStatus.RESOLVED:
            raise ValueError("Cannot escalate resolved alert")

        # Increase severity if possible
        if self.severity == AlertSeverity.LOW:
            self.severity = AlertSeverity.MEDIUM
        elif self.severity == AlertSeverity.MEDIUM:
            self.severity = AlertSeverity.HIGH
        elif self.severity == AlertSeverity.HIGH:
            self.severity = AlertSeverity.CRITICAL

        self.status = AlertStatus.ESCALATED
        self.escalated_at = datetime.now()
        self.context["escalation_reason"] = escalation_reason

        self._add_event(
            "escalated", {"new_severity": self.severity.value, "reason": escalation_reason}
        )

        logger.warning(
            f"Alert {self.alert_id} escalated to {self.severity.value}: {escalation_reason}"
        )

    def add_notification_sent(self, channel_info: str) -> None:
        """Record that a notification was sent"""
        if channel_info not in self.notifications_sent:
            self.notifications_sent.append(channel_info)
            self._add_event("notification_sent", {"channel": channel_info})

    def update_context(self, additional_context: Dict[str, Any]) -> None:
        """Add additional context to the alert"""
        self.context.update(additional_context)
        self._add_event("context_updated", {"added_context": additional_context})

    def is_active(self) -> bool:
        """Check if alert is in an active state"""
        return self.status in [
            AlertStatus.TRIGGERED,
            AlertStatus.ACKNOWLEDGED,
            AlertStatus.ESCALATED,
        ]

    def is_critical(self) -> bool:
        """Check if alert is critical severity"""
        return self.severity == AlertSeverity.CRITICAL

    def age_minutes(self) -> float:
        """Get age of alert in minutes"""
        return (datetime.now() - self.triggered_at).total_seconds() / 60

    def time_to_acknowledge_minutes(self) -> Optional[float]:
        """Get time taken to acknowledge in minutes"""
        if not self.acknowledged_at:
            return None
        return (self.acknowledged_at - self.triggered_at).total_seconds() / 60

    def time_to_resolve_minutes(self) -> Optional[float]:
        """Get time taken to resolve in minutes"""
        if not self.resolved_at:
            return None
        return (self.resolved_at - self.triggered_at).total_seconds() / 60

    def _add_event(self, event_type: str, metadata: Dict[str, Any]) -> None:
        """Add domain event to alert"""
        event = AlertEvent(alert_id=self.alert_id, event_type=event_type, metadata=metadata)
        self.events.append(event)

    def get_events(self) -> List[AlertEvent]:
        """Get all domain events for this alert"""
        return self.events.copy()

    def clear_events(self) -> None:
        """Clear domain events (typically after persistence)"""
        self.events.clear()


class AlertAggregate:
    """Alert aggregate for managing complex alert operations"""

    def __init__(self, alert: Alert):
        self._alert = alert

    @property
    def alert(self) -> Alert:
        """Get the underlying alert entity"""
        return self._alert

    def can_be_acknowledged(self) -> bool:
        """Check if alert can be acknowledged"""
        return self._alert.status in [AlertStatus.TRIGGERED, AlertStatus.ESCALATED]

    def can_be_resolved(self) -> bool:
        """Check if alert can be resolved"""
        return self._alert.status != AlertStatus.RESOLVED

    def can_be_escalated(self) -> bool:
        """Check if alert can be escalated"""
        return (
            self._alert.status in [AlertStatus.TRIGGERED, AlertStatus.ACKNOWLEDGED]
            and self._alert.severity != AlertSeverity.CRITICAL
        )

    def should_auto_resolve(self, metric_value: float) -> bool:
        """Check if alert should auto-resolve based on current metrics"""
        if not self._alert.metrics:
            return False

        # If metric is no longer breaching threshold, can auto-resolve
        return not self._alert.metrics.is_breached() and self._alert.is_active()

    def requires_escalation(self, max_age_minutes: int = 60) -> bool:
        """Check if alert requires escalation due to age"""
        if self._alert.status == AlertStatus.RESOLVED:
            return False

        # Critical alerts escalate faster
        if self._alert.severity == AlertSeverity.CRITICAL:
            max_age_minutes = max_age_minutes // 2

        return self._alert.age_minutes() > max_age_minutes

    def get_severity_color(self) -> str:
        """Get color representation for UI"""
        colors = {
            AlertSeverity.LOW: "#4CAF50",  # Green
            AlertSeverity.MEDIUM: "#FF9800",  # Orange
            AlertSeverity.HIGH: "#FF5722",  # Red
            AlertSeverity.CRITICAL: "#F44336",  # Dark Red
        }
        return colors[self._alert.severity]

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for serialization"""
        return {
            "alert_id": self._alert.alert_id,
            "rule_id": self._alert.rule_id,
            "severity": self._alert.severity.value,
            "status": self._alert.status.value,
            "title": self._alert.title,
            "description": self._alert.description,
            "metrics": {
                "metric_name": self._alert.metrics.metric_name,
                "current_value": self._alert.metrics.current_value,
                "threshold_value": self._alert.metrics.threshold_value,
                "comparison_operator": self._alert.metrics.comparison_operator,
                "evaluation_window_seconds": self._alert.metrics.evaluation_window_seconds,
            }
            if self._alert.metrics
            else None,
            "triggered_at": self._alert.triggered_at.isoformat(),
            "acknowledged_at": self._alert.acknowledged_at.isoformat()
            if self._alert.acknowledged_at
            else None,
            "resolved_at": self._alert.resolved_at.isoformat() if self._alert.resolved_at else None,
            "escalated_at": self._alert.escalated_at.isoformat()
            if self._alert.escalated_at
            else None,
            "acknowledged_by": self._alert.acknowledged_by,
            "resolved_by": self._alert.resolved_by,
            "context": self._alert.context,
            "notifications_sent": self._alert.notifications_sent,
            "age_minutes": self._alert.age_minutes(),
        }
