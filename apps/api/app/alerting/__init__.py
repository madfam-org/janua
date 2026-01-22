"""
Alerting Package
Modular alerting system with separated concerns for evaluation, notification, and management.
"""

from .core import (
    AlertSeverity,
    AlertStatus,
    AlertChannel,
    AlertRule,
    Alert,
    NotificationChannel,
    AlertEvaluator,
    NotificationSender,
    AlertManager,
)
from .alert_system_refactored import (
    alert_manager,
    initialize_alerting,
    trigger_manual_alert,
    get_alert_health,
)

__all__ = [
    "AlertSeverity",
    "AlertStatus",
    "AlertChannel",
    "AlertRule",
    "Alert",
    "NotificationChannel",
    "AlertEvaluator",
    "NotificationSender",
    "AlertManager",
    "alert_manager",
    "initialize_alerting",
    "trigger_manual_alert",
    "get_alert_health",
]
