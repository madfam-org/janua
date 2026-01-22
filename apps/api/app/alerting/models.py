"""
Alert System Data Models
Pure data structures and enums for the alerting system
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


class AlertSeverity(Enum):
    """Alert severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status states"""

    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertChannel(Enum):
    """Alert delivery channels"""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"
    DISCORD = "discord"


@dataclass
class AlertRule:
    """Alert rule configuration"""

    rule_id: str
    name: str
    description: str
    severity: AlertSeverity
    metric_name: str
    threshold_value: float
    comparison_operator: str  # >, <, >=, <=, ==, !=
    evaluation_window: int  # seconds
    trigger_count: int = 1  # consecutive evaluations to trigger
    cooldown_period: int = 300  # seconds between alerts
    enabled: bool = True
    channels: List[AlertChannel] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Alert:
    """Alert instance"""

    alert_id: str
    rule_id: str
    severity: AlertSeverity
    status: AlertStatus
    title: str
    description: str
    metric_value: float
    threshold_value: float
    triggered_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    notifications_sent: List[str] = field(default_factory=list)


@dataclass
class NotificationChannel:
    """Notification channel configuration"""

    channel_id: str
    channel_type: AlertChannel
    name: str
    config: Dict[str, Any]
    enabled: bool = True
    rate_limit: Optional[int] = None  # max notifications per hour


@dataclass
class EvaluationResult:
    """Result of alert rule evaluation"""

    rule_id: str
    metric_value: float
    threshold_value: float
    should_trigger: bool
    evaluation_time: datetime
    consecutive_triggers: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
