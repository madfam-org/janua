"""
Alerting System - Refactored Interface
Public interface for the modular alerting system with helper functions.
"""

import uuid
from datetime import datetime
from typing import Dict, Optional, Any

from .core import AlertManager, AlertSeverity, Alert, AlertStatus

# Global alert manager instance
alert_manager = AlertManager()


# Helper functions
async def initialize_alerting():
    """Initialize the alerting system"""
    await alert_manager.initialize_redis()
    await alert_manager.start_monitoring()


async def trigger_manual_alert(
    title: str, description: str, severity: AlertSeverity, context: Optional[Dict[str, Any]] = None
) -> str:
    """Trigger a manual alert"""
    from .core.alert_types import AlertChannel

    alert = Alert(
        alert_id=str(uuid.uuid4()),
        rule_id="manual",
        severity=severity,
        status=AlertStatus.TRIGGERED,
        title=title,
        description=description,
        metric_value=0,
        threshold_value=0,
        triggered_at=datetime.now(),
        context=context or {},
    )

    # Send notifications to all configured channels
    for channel_type in [AlertChannel.EMAIL, AlertChannel.SLACK]:
        await alert_manager._send_notification(alert, channel_type)

    await alert_manager._store_alert(alert)
    alert_manager.active_alerts[alert.alert_id] = alert

    return alert.alert_id


async def get_alert_health() -> Dict[str, Any]:
    """Get alerting system health"""
    return {
        "status": "healthy"
        if alert_manager.evaluation_task and not alert_manager.evaluation_task.done()
        else "stopped",
        "active_alerts": len(alert_manager.active_alerts),
        "configured_rules": len(alert_manager.alert_rules),
        "configured_channels": len(alert_manager.notification_channels),
        "redis_connected": alert_manager.redis_client is not None,
    }
