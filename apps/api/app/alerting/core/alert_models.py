"""
Alert Data Models
Data structures for alert rules, alerts, and notification channels.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

from .alert_types import AlertSeverity, AlertStatus, AlertChannel


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
