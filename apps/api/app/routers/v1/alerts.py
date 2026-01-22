"""
Alerting System API Routes
Endpoints for managing alerts, rules, and notification channels
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
import structlog

from app.alerting.alert_system import (
    alert_manager,
    get_alert_health,
    trigger_manual_alert,
    AlertSeverity,
    AlertChannel,
    AlertRule,
    NotificationChannel,
)
from app.core.auth import get_current_admin_user
from app.core.models import User

logger = structlog.get_logger()

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# Pydantic models for API
class AlertRuleCreate(BaseModel):
    name: str = Field(..., description="Rule name")
    description: str = Field(..., description="Rule description")
    severity: AlertSeverity = Field(..., description="Alert severity")
    metric_name: str = Field(..., description="Metric to monitor")
    threshold_value: float = Field(..., description="Threshold value")
    comparison_operator: str = Field(
        ..., regex="^(>|<|>=|<=|==|!=)$", description="Comparison operator"
    )
    evaluation_window: int = Field(300, ge=60, le=3600, description="Evaluation window in seconds")
    trigger_count: int = Field(1, ge=1, le=10, description="Consecutive evaluations to trigger")
    cooldown_period: int = Field(300, ge=60, le=3600, description="Cooldown period in seconds")
    channels: List[AlertChannel] = Field(default_factory=list, description="Notification channels")
    enabled: bool = Field(True, description="Whether rule is enabled")


class AlertRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[AlertSeverity] = None
    threshold_value: Optional[float] = None
    comparison_operator: Optional[str] = Field(None, regex="^(>|<|>=|<=|==|!=)$")
    evaluation_window: Optional[int] = Field(None, ge=60, le=3600)
    trigger_count: Optional[int] = Field(None, ge=1, le=10)
    cooldown_period: Optional[int] = Field(None, ge=60, le=3600)
    channels: Optional[List[AlertChannel]] = None
    enabled: Optional[bool] = None


class NotificationChannelCreate(BaseModel):
    name: str = Field(..., description="Channel name")
    channel_type: AlertChannel = Field(..., description="Channel type")
    config: Dict[str, Any] = Field(..., description="Channel configuration")
    enabled: bool = Field(True, description="Whether channel is enabled")
    rate_limit: Optional[int] = Field(None, ge=1, le=100, description="Max notifications per hour")


class NotificationChannelUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    rate_limit: Optional[int] = Field(None, ge=1, le=100)


class ManualAlertCreate(BaseModel):
    title: str = Field(..., description="Alert title")
    description: str = Field(..., description="Alert description")
    severity: AlertSeverity = Field(..., description="Alert severity")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


@router.get("/health")
async def alerting_health_check():
    """Get alerting system health status"""
    try:
        health = await get_alert_health()
        return health
    except Exception as e:
        logger.error("Failed to get alerting health", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to get alerting health")


@router.get("/statistics")
async def get_alert_statistics(
    hours: int = Query(24, ge=1, le=168, description="Hours to analyze"),
    current_user: User = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Get alert statistics for the specified time period"""
    try:
        stats = await alert_manager.get_alert_statistics(hours)
        return stats
    except Exception as e:
        logger.error("Failed to get alert statistics", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve alert statistics")


@router.get("/active")
async def get_active_alerts(
    current_user: User = Depends(get_current_admin_user),
) -> List[Dict[str, Any]]:
    """Get all active alerts"""
    try:
        active_alerts = []
        for alert in alert_manager.active_alerts.values():
            active_alerts.append(
                {
                    "alert_id": alert.alert_id,
                    "rule_id": alert.rule_id,
                    "severity": alert.severity.value,
                    "status": alert.status.value,
                    "title": alert.title,
                    "description": alert.description,
                    "metric_value": alert.metric_value,
                    "threshold_value": alert.threshold_value,
                    "triggered_at": alert.triggered_at.isoformat(),
                    "acknowledged_at": alert.acknowledged_at.isoformat()
                    if alert.acknowledged_at
                    else None,
                    "acknowledged_by": alert.acknowledged_by,
                    "context": alert.context,
                    "notifications_sent": alert.notifications_sent,
                }
            )

        return sorted(active_alerts, key=lambda x: x["triggered_at"], reverse=True)

    except Exception as e:
        logger.error("Failed to get active alerts", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve active alerts")


@router.post("/manual")
async def create_manual_alert(
    alert_data: ManualAlertCreate, current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Create a manual alert"""
    try:
        alert_id = await trigger_manual_alert(
            title=alert_data.title,
            description=alert_data.description,
            severity=alert_data.severity,
            context=alert_data.context,
        )

        logger.info(
            "Manual alert created",
            alert_id=alert_id,
            created_by=current_user.id,
            severity=alert_data.severity.value,
        )

        return {"alert_id": alert_id, "message": "Manual alert created successfully"}

    except Exception as e:
        logger.error("Failed to create manual alert", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create manual alert")


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str, current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Acknowledge an alert"""
    try:
        success = await alert_manager.acknowledge_alert(alert_id, current_user.id)

        if not success:
            raise HTTPException(status_code=404, detail="Alert not found or already acknowledged")

        return {"message": "Alert acknowledged successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to acknowledge alert", alert_id=alert_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to acknowledge alert")


@router.post("/{alert_id}/resolve")
async def resolve_alert(
    alert_id: str, current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Resolve an alert"""
    try:
        success = await alert_manager.resolve_alert(alert_id)

        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")

        return {"message": "Alert resolved successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to resolve alert", alert_id=alert_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to resolve alert")


@router.get("/rules")
async def get_alert_rules(
    current_user: User = Depends(get_current_admin_user),
) -> List[Dict[str, Any]]:
    """Get all alert rules"""
    try:
        rules = []
        for rule in alert_manager.alert_rules.values():
            rules.append(
                {
                    "rule_id": rule.rule_id,
                    "name": rule.name,
                    "description": rule.description,
                    "severity": rule.severity.value,
                    "metric_name": rule.metric_name,
                    "threshold_value": rule.threshold_value,
                    "comparison_operator": rule.comparison_operator,
                    "evaluation_window": rule.evaluation_window,
                    "trigger_count": rule.trigger_count,
                    "cooldown_period": rule.cooldown_period,
                    "enabled": rule.enabled,
                    "channels": [ch.value for ch in rule.channels],
                    "conditions": rule.conditions,
                    "metadata": rule.metadata,
                }
            )

        return rules

    except Exception as e:
        logger.error("Failed to get alert rules", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve alert rules")


@router.post("/rules")
async def create_alert_rule(
    rule_data: AlertRuleCreate, current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Create a new alert rule"""
    try:
        import uuid

        rule_id = str(uuid.uuid4())
        rule = AlertRule(
            rule_id=rule_id,
            name=rule_data.name,
            description=rule_data.description,
            severity=rule_data.severity,
            metric_name=rule_data.metric_name,
            threshold_value=rule_data.threshold_value,
            comparison_operator=rule_data.comparison_operator,
            evaluation_window=rule_data.evaluation_window,
            trigger_count=rule_data.trigger_count,
            cooldown_period=rule_data.cooldown_period,
            enabled=rule_data.enabled,
            channels=rule_data.channels,
        )

        alert_manager.alert_rules[rule_id] = rule

        # Persist to Redis if available
        if alert_manager.redis_client:
            rule_data_dict = {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "severity": rule.severity.value,
                "metric_name": rule.metric_name,
                "threshold_value": rule.threshold_value,
                "comparison_operator": rule.comparison_operator,
                "evaluation_window": rule.evaluation_window,
                "trigger_count": rule.trigger_count,
                "cooldown_period": rule.cooldown_period,
                "enabled": str(rule.enabled).lower(),
                "channels": json.dumps([ch.value for ch in rule.channels]),
                "conditions": json.dumps(rule.conditions),
                "metadata": json.dumps(rule.metadata),
            }

            await alert_manager.redis_client.hset(f"alert:rule:{rule_id}", mapping=rule_data_dict)
            await alert_manager.redis_client.sadd("alert:rules", rule_id)

        logger.info(
            "Alert rule created",
            rule_id=rule_id,
            created_by=current_user.id,
            rule_name=rule_data.name,
        )

        return {"rule_id": rule_id, "message": "Alert rule created successfully"}

    except Exception as e:
        logger.error("Failed to create alert rule", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create alert rule")


@router.put("/rules/{rule_id}")
async def update_alert_rule(
    rule_id: str,
    rule_updates: AlertRuleUpdate,
    current_user: User = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Update an alert rule"""
    try:
        if rule_id not in alert_manager.alert_rules:
            raise HTTPException(status_code=404, detail="Alert rule not found")

        rule = alert_manager.alert_rules[rule_id]

        # Update fields
        update_data = rule_updates.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(rule, field, value)

        # Persist changes to Redis if available
        if alert_manager.redis_client:
            rule_data_dict = {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "description": rule.description,
                "severity": rule.severity.value,
                "metric_name": rule.metric_name,
                "threshold_value": rule.threshold_value,
                "comparison_operator": rule.comparison_operator,
                "evaluation_window": rule.evaluation_window,
                "trigger_count": rule.trigger_count,
                "cooldown_period": rule.cooldown_period,
                "enabled": str(rule.enabled).lower(),
                "channels": json.dumps([ch.value for ch in rule.channels]),
                "conditions": json.dumps(rule.conditions),
                "metadata": json.dumps(rule.metadata),
            }

            await alert_manager.redis_client.hset(f"alert:rule:{rule_id}", mapping=rule_data_dict)

        logger.info(
            "Alert rule updated",
            rule_id=rule_id,
            updated_by=current_user.id,
            updates=list(update_data.keys()),
        )

        return {"message": "Alert rule updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update alert rule", rule_id=rule_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update alert rule")


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: str, current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Delete an alert rule"""
    try:
        if rule_id not in alert_manager.alert_rules:
            raise HTTPException(status_code=404, detail="Alert rule not found")

        del alert_manager.alert_rules[rule_id]

        # Remove from Redis if available
        if alert_manager.redis_client:
            await alert_manager.redis_client.delete(f"alert:rule:{rule_id}")
            await alert_manager.redis_client.srem("alert:rules", rule_id)

        logger.info("Alert rule deleted", rule_id=rule_id, deleted_by=current_user.id)

        return {"message": "Alert rule deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete alert rule", rule_id=rule_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete alert rule")


@router.get("/channels")
async def get_notification_channels(
    current_user: User = Depends(get_current_admin_user),
) -> List[Dict[str, Any]]:
    """Get all notification channels"""
    try:
        channels = []
        for channel in alert_manager.notification_channels.values():
            # Mask sensitive config data
            safe_config = {
                k: "[MASKED]"
                if k.lower() in ["password", "token", "secret", "key", "webhook_url"]
                else v
                for k, v in channel.config.items()
            }

            channels.append(
                {
                    "channel_id": channel.channel_id,
                    "channel_type": channel.channel_type.value,
                    "name": channel.name,
                    "config": safe_config,
                    "enabled": channel.enabled,
                    "rate_limit": channel.rate_limit,
                }
            )

        return channels

    except Exception as e:
        logger.error("Failed to get notification channels", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve notification channels")


@router.post("/channels")
async def create_notification_channel(
    channel_data: NotificationChannelCreate, current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Create a new notification channel"""
    try:
        import uuid

        channel_id = str(uuid.uuid4())
        channel = NotificationChannel(
            channel_id=channel_id,
            channel_type=channel_data.channel_type,
            name=channel_data.name,
            config=channel_data.config,
            enabled=channel_data.enabled,
            rate_limit=channel_data.rate_limit,
        )

        alert_manager.notification_channels[channel_id] = channel

        # Persist to Redis if available
        if alert_manager.redis_client:
            import json

            channel_data_dict = {
                "channel_id": channel.channel_id,
                "channel_type": channel.channel_type.value,
                "name": channel.name,
                "config": json.dumps(channel.config),
                "enabled": str(channel.enabled).lower(),
                "rate_limit": str(channel.rate_limit) if channel.rate_limit else "",
            }

            await alert_manager.redis_client.hset(
                f"alert:channel:{channel_id}", mapping=channel_data_dict
            )
            await alert_manager.redis_client.sadd("alert:channels", channel_id)

        logger.info(
            "Notification channel created",
            channel_id=channel_id,
            created_by=current_user.id,
            channel_type=channel_data.channel_type.value,
        )

        return {"channel_id": channel_id, "message": "Notification channel created successfully"}

    except Exception as e:
        logger.error("Failed to create notification channel", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create notification channel")


@router.put("/channels/{channel_id}")
async def update_notification_channel(
    channel_id: str,
    channel_updates: NotificationChannelUpdate,
    current_user: User = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Update a notification channel"""
    try:
        if channel_id not in alert_manager.notification_channels:
            raise HTTPException(status_code=404, detail="Notification channel not found")

        channel = alert_manager.notification_channels[channel_id]

        # Update fields
        update_data = channel_updates.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(channel, field, value)

        # Persist changes to Redis if available
        if alert_manager.redis_client:
            import json

            channel_data_dict = {
                "channel_id": channel.channel_id,
                "channel_type": channel.channel_type.value,
                "name": channel.name,
                "config": json.dumps(channel.config),
                "enabled": str(channel.enabled).lower(),
                "rate_limit": str(channel.rate_limit) if channel.rate_limit else "",
            }

            await alert_manager.redis_client.hset(
                f"alert:channel:{channel_id}", mapping=channel_data_dict
            )

        logger.info(
            "Notification channel updated",
            channel_id=channel_id,
            updated_by=current_user.id,
            updates=list(update_data.keys()),
        )

        return {"message": "Notification channel updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update notification channel", channel_id=channel_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to update notification channel")


@router.delete("/channels/{channel_id}")
async def delete_notification_channel(
    channel_id: str, current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Delete a notification channel"""
    try:
        if channel_id not in alert_manager.notification_channels:
            raise HTTPException(status_code=404, detail="Notification channel not found")

        del alert_manager.notification_channels[channel_id]

        # Remove from Redis if available
        if alert_manager.redis_client:
            await alert_manager.redis_client.delete(f"alert:channel:{channel_id}")
            await alert_manager.redis_client.srem("alert:channels", channel_id)

        logger.info(
            "Notification channel deleted", channel_id=channel_id, deleted_by=current_user.id
        )

        return {"message": "Notification channel deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete notification channel", channel_id=channel_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to delete notification channel")


@router.post("/test/{channel_id}")
async def test_notification_channel(
    channel_id: str, current_user: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Test a notification channel"""
    try:
        if channel_id not in alert_manager.notification_channels:
            raise HTTPException(status_code=404, detail="Notification channel not found")

        # Create test alert
        test_alert = await trigger_manual_alert(
            title="Test Alert",
            description="This is a test alert to verify notification channel configuration",
            severity=AlertSeverity.LOW,
            context={"test": True, "triggered_by": current_user.id, "channel_id": channel_id},
        )

        return {"message": "Test alert sent successfully", "test_alert_id": test_alert}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to test notification channel", channel_id=channel_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to test notification channel")
