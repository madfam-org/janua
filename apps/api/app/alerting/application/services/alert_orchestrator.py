"""
Alert Orchestrator Application Service
Coordinates alert lifecycle management and business workflows
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from ...domain.models.alert import Alert, AlertStatus, AlertAggregate
from ...domain.models.rule import AlertRule
from ...domain.services.alert_evaluator import AlertEvaluatorService, EvaluationResult
from .notification_dispatcher import NotificationDispatcher
import structlog
logger = structlog.get_logger()


@dataclass
class AlertLifecycleEvent:
    """Event representing alert lifecycle changes"""
    event_type: str  # created, acknowledged, resolved, escalated, auto_resolved
    alert_id: str
    rule_id: str
    timestamp: datetime
    metadata: Dict[str, any]


class AlertRepository:
    """Abstract repository for alert persistence"""
    
    async def save_alert(self, alert: Alert) -> None:
        """Save alert to storage"""
        raise NotImplementedError
    
    async def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID"""
        raise NotImplementedError
    
    async def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        raise NotImplementedError
    
    async def get_alerts_by_rule(self, rule_id: str) -> List[Alert]:
        """Get alerts for specific rule"""
        raise NotImplementedError
    
    async def update_alert_status(self, alert_id: str, status: AlertStatus, metadata: Dict[str, any] = None) -> bool:
        """Update alert status"""
        raise NotImplementedError


class RuleRepository:
    """Abstract repository for rule persistence"""
    
    async def get_enabled_rules(self) -> List[AlertRule]:
        """Get all enabled alert rules"""
        raise NotImplementedError
    
    async def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get rule by ID"""
        raise NotImplementedError
    
    async def save_rule(self, rule: AlertRule) -> None:
        """Save rule to storage"""
        raise NotImplementedError


class AlertOrchestrator:
    """Main application service for alert management"""
    
    def __init__(
        self,
        evaluator_service: AlertEvaluatorService,
        notification_dispatcher: NotificationDispatcher,
        alert_repository: AlertRepository,
        rule_repository: RuleRepository
    ):
        self._evaluator = evaluator_service
        self._notification_dispatcher = notification_dispatcher
        self._alert_repo = alert_repository
        self._rule_repo = rule_repository
        
        # Event tracking
        self._lifecycle_events: List[AlertLifecycleEvent] = []
        
        # State tracking
        self._active_alerts_cache: Dict[str, Alert] = {}
        self._rules_cache: Dict[str, AlertRule] = {}
        self._cache_updated_at: Optional[datetime] = None
        
        # Configuration
        self._auto_resolution_enabled = True
        self._escalation_enabled = True
        self._max_escalation_age_minutes = 60
    
    async def initialize(self) -> None:
        """Initialize the orchestrator"""
        await self._refresh_caches()
        logger.info("Alert orchestrator initialized")
    
    async def evaluate_and_process_alerts(self) -> Tuple[List[Alert], List[EvaluationResult]]:
        """Main workflow: evaluate rules and process resulting alerts"""
        try:
            # Refresh rules cache
            await self._refresh_rules_cache()
            
            # Get enabled rules
            rules = list(self._rules_cache.values())
            enabled_rules = [rule for rule in rules if rule.enabled]
            
            if not enabled_rules:
                logger.debug("No enabled rules found for evaluation")
                return [], []
            
            # Evaluate all rules
            evaluation_results = await self._evaluator.evaluate_rules(enabled_rules)
            
            # Process evaluations and create alerts
            new_alerts = []
            for rule, evaluation in zip(enabled_rules, evaluation_results):
                if evaluation.should_trigger:
                    # Check if alert already exists for this rule
                    existing_alert = await self._get_active_alert_for_rule(rule.rule_id)
                    if existing_alert:
                        logger.debug(
                            f"Active alert already exists for rule {rule.rule_id}, skipping creation",
                            existing_alert_id=existing_alert.alert_id
                        )
                        continue
                    
                    # Create new alert
                    alert = self._evaluator.create_alert_from_evaluation(rule, evaluation)
                    await self._create_alert(alert, rule)
                    new_alerts.append(alert)
            
            # Process auto-resolution if enabled
            if self._auto_resolution_enabled:
                await self._process_auto_resolution()
            
            # Process escalations if enabled
            if self._escalation_enabled:
                await self._process_escalations()
            
            return new_alerts, evaluation_results
            
        except Exception as e:
            logger.error(f"Failed to evaluate and process alerts: {e}")
            return [], []
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert"""
        try:
            alert = await self._get_alert_with_validation(alert_id)
            if not alert:
                return False
            
            aggregate = AlertAggregate(alert)
            if not aggregate.can_be_acknowledged():
                logger.warning(
                    f"Alert {alert_id} cannot be acknowledged in current status",
                    current_status=alert.status.value
                )
                return False
            
            # Acknowledge the alert
            alert.acknowledge(acknowledged_by)
            
            # Persist changes
            await self._alert_repo.save_alert(alert)
            self._active_alerts_cache[alert_id] = alert
            
            # Record lifecycle event
            await self._record_lifecycle_event(
                "acknowledged",
                alert_id,
                alert.rule_id,
                {"acknowledged_by": acknowledged_by}
            )
            
            logger.info(
                f"Alert acknowledged",
                alert_id=alert_id,
                acknowledged_by=acknowledged_by
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to acknowledge alert {alert_id}: {e}")
            return False
    
    async def resolve_alert(self, alert_id: str, resolved_by: Optional[str] = None, reason: Optional[str] = None) -> bool:
        """Resolve an alert"""
        try:
            alert = await self._get_alert_with_validation(alert_id)
            if not alert:
                return False
            
            aggregate = AlertAggregate(alert)
            if not aggregate.can_be_resolved():
                logger.warning(
                    f"Alert {alert_id} cannot be resolved in current status",
                    current_status=alert.status.value
                )
                return False
            
            # Resolve the alert
            alert.resolve(resolved_by)
            
            # Add resolution reason to context
            if reason:
                alert.update_context({"resolution_reason": reason})
            
            # Persist changes
            await self._alert_repo.save_alert(alert)
            
            # Remove from active cache
            self._active_alerts_cache.pop(alert_id, None)
            
            # Record lifecycle event
            await self._record_lifecycle_event(
                "resolved",
                alert_id,
                alert.rule_id,
                {
                    "resolved_by": resolved_by or "system",
                    "resolution_reason": reason
                }
            )
            
            logger.info(
                f"Alert resolved",
                alert_id=alert_id,
                resolved_by=resolved_by or "system",
                reason=reason
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to resolve alert {alert_id}: {e}")
            return False
    
    async def escalate_alert(self, alert_id: str, escalation_reason: str) -> bool:
        """Escalate an alert"""
        try:
            alert = await self._get_alert_with_validation(alert_id)
            if not alert:
                return False
            
            aggregate = AlertAggregate(alert)
            if not aggregate.can_be_escalated():
                logger.warning(
                    f"Alert {alert_id} cannot be escalated",
                    current_status=alert.status.value,
                    current_severity=alert.severity.value
                )
                return False
            
            # Store original severity for logging
            original_severity = alert.severity
            
            # Escalate the alert
            alert.escalate(escalation_reason)
            
            # Persist changes
            await self._alert_repo.save_alert(alert)
            self._active_alerts_cache[alert_id] = alert
            
            # Send escalation notifications
            rule = self._rules_cache.get(alert.rule_id)
            if rule:
                await self._notification_dispatcher.send_alert_notifications(alert, rule, notification_type="escalation")
            
            # Record lifecycle event
            await self._record_lifecycle_event(
                "escalated",
                alert_id,
                alert.rule_id,
                {
                    "original_severity": original_severity.value,
                    "new_severity": alert.severity.value,
                    "escalation_reason": escalation_reason
                }
            )
            
            logger.warning(
                f"Alert escalated",
                alert_id=alert_id,
                original_severity=original_severity.value,
                new_severity=alert.severity.value,
                reason=escalation_reason
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to escalate alert {alert_id}: {e}")
            return False
    
    async def get_alert_metrics(self, hours: int = 24) -> Dict[str, any]:
        """Get alert system metrics"""
        try:
            cutoff = datetime.now() - timedelta(hours=hours)
            
            # Get recent lifecycle events
            recent_events = [
                event for event in self._lifecycle_events
                if event.timestamp >= cutoff
            ]
            
            # Count events by type
            event_counts = {}
            for event in recent_events:
                event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
            
            # Get active alerts statistics
            active_alerts = list(self._active_alerts_cache.values())
            
            severity_distribution = {}
            status_distribution = {}
            for alert in active_alerts:
                severity_distribution[alert.severity.value] = severity_distribution.get(alert.severity.value, 0) + 1
                status_distribution[alert.status.value] = status_distribution.get(alert.status.value, 0) + 1
            
            # Calculate response times
            acknowledged_alerts = [a for a in active_alerts if a.acknowledged_at]
            _resolved_events = [e for e in recent_events if e.event_type == "resolved"]
            
            avg_acknowledgment_time = 0.0
            if acknowledged_alerts:
                ack_times = [a.time_to_acknowledge_minutes() for a in acknowledged_alerts if a.time_to_acknowledge_minutes()]
                avg_acknowledgment_time = sum(ack_times) / len(ack_times) if ack_times else 0.0
            
            return {
                "time_window_hours": hours,
                "active_alerts_count": len(active_alerts),
                "total_events": len(recent_events),
                "events_by_type": event_counts,
                "severity_distribution": severity_distribution,
                "status_distribution": status_distribution,
                "average_acknowledgment_time_minutes": avg_acknowledgment_time,
                "enabled_rules_count": len([r for r in self._rules_cache.values() if r.enabled]),
                "auto_resolution_enabled": self._auto_resolution_enabled,
                "escalation_enabled": self._escalation_enabled
            }
            
        except Exception as e:
            logger.error(f"Failed to get alert metrics: {e}")
            return {"error": "Failed to retrieve metrics"}
    
    async def _create_alert(self, alert: Alert, rule: AlertRule) -> None:
        """Create and process a new alert"""
        # Save alert
        await self._alert_repo.save_alert(alert)
        self._active_alerts_cache[alert.alert_id] = alert
        
        # Send notifications
        await self._notification_dispatcher.send_alert_notifications(alert, rule)
        
        # Record lifecycle event
        await self._record_lifecycle_event(
            "created",
            alert.alert_id,
            alert.rule_id,
            {
                "severity": alert.severity.value,
                "metric_name": alert.metrics.metric_name if alert.metrics else None,
                "current_value": alert.metrics.current_value if alert.metrics else None,
                "threshold_value": alert.metrics.threshold_value if alert.metrics else None
            }
        )
        
        logger.info(
            f"Created new alert",
            alert_id=alert.alert_id,
            rule_id=alert.rule_id,
            severity=alert.severity.value,
            title=alert.title
        )
    
    async def _process_auto_resolution(self) -> None:
        """Process auto-resolution for alerts"""
        try:
            active_alerts = list(self._active_alerts_cache.values())
            if not active_alerts:
                return
            
            # Filter alerts that can be auto-resolved
            resolvable_alerts = []
            for alert in active_alerts:
                rule = self._rules_cache.get(alert.rule_id)
                if not rule:
                    continue
                
                # Evaluate current conditions
                evaluation = await self._evaluator.evaluate_rule(rule)
                
                # Check if conditions are no longer met
                if not evaluation.should_trigger and evaluation.consecutive_breaches == 0:
                    # Additional check: ensure alert has been active for minimum time
                    if alert.age_minutes() >= 5:  # Minimum 5 minutes
                        resolvable_alerts.append(alert)
            
            # Auto-resolve alerts
            for alert in resolvable_alerts:
                await self.resolve_alert(
                    alert.alert_id,
                    resolved_by="system",
                    reason="auto_resolution_conditions_no_longer_met"
                )
            
            if resolvable_alerts:
                logger.info(f"Auto-resolved {len(resolvable_alerts)} alerts")
                
        except Exception as e:
            logger.error(f"Failed to process auto-resolution: {e}")
    
    async def _process_escalations(self) -> None:
        """Process alert escalations based on age and severity"""
        try:
            active_alerts = list(self._active_alerts_cache.values())
            if not active_alerts:
                return
            
            escalation_candidates = []
            for alert in active_alerts:
                aggregate = AlertAggregate(alert)
                
                # Check if alert requires escalation
                if aggregate.requires_escalation(self._max_escalation_age_minutes):
                    escalation_candidates.append(alert)
            
            # Process escalations
            for alert in escalation_candidates:
                await self.escalate_alert(
                    alert.alert_id,
                    f"Automatic escalation after {alert.age_minutes():.1f} minutes without resolution"
                )
            
            if escalation_candidates:
                logger.info(f"Auto-escalated {len(escalation_candidates)} alerts")
                
        except Exception as e:
            logger.error(f"Failed to process escalations: {e}")
    
    async def _get_alert_with_validation(self, alert_id: str) -> Optional[Alert]:
        """Get alert with validation"""
        # Try cache first
        alert = self._active_alerts_cache.get(alert_id)
        if alert:
            return alert
        
        # Try repository
        alert = await self._alert_repo.get_alert(alert_id)
        if alert and alert.is_active():
            self._active_alerts_cache[alert_id] = alert
        
        return alert
    
    async def _get_active_alert_for_rule(self, rule_id: str) -> Optional[Alert]:
        """Get active alert for specific rule"""
        # Check cache first
        for alert in self._active_alerts_cache.values():
            if alert.rule_id == rule_id and alert.is_active():
                return alert
        
        # Check repository
        alerts = await self._alert_repo.get_alerts_by_rule(rule_id)
        active_alerts = [a for a in alerts if a.is_active()]
        
        if active_alerts:
            # Update cache
            for alert in active_alerts:
                self._active_alerts_cache[alert.alert_id] = alert
            return active_alerts[0]  # Return the first active alert
        
        return None
    
    async def _refresh_caches(self) -> None:
        """Refresh internal caches"""
        await asyncio.gather(
            self._refresh_active_alerts_cache(),
            self._refresh_rules_cache()
        )
        self._cache_updated_at = datetime.now()
    
    async def _refresh_active_alerts_cache(self) -> None:
        """Refresh active alerts cache"""
        try:
            active_alerts = await self._alert_repo.get_active_alerts()
            self._active_alerts_cache = {alert.alert_id: alert for alert in active_alerts}
            logger.debug(f"Refreshed active alerts cache: {len(active_alerts)} alerts")
        except Exception as e:
            logger.error(f"Failed to refresh active alerts cache: {e}")
    
    async def _refresh_rules_cache(self) -> None:
        """Refresh rules cache"""
        try:
            rules = await self._rule_repo.get_enabled_rules()
            self._rules_cache = {rule.rule_id: rule for rule in rules}
            logger.debug(f"Refreshed rules cache: {len(rules)} rules")
        except Exception as e:
            logger.error(f"Failed to refresh rules cache: {e}")
    
    async def _record_lifecycle_event(self, event_type: str, alert_id: str, rule_id: str, metadata: Dict[str, any]) -> None:
        """Record alert lifecycle event"""
        event = AlertLifecycleEvent(
            event_type=event_type,
            alert_id=alert_id,
            rule_id=rule_id,
            timestamp=datetime.now(),
            metadata=metadata
        )
        
        self._lifecycle_events.append(event)
        
        # Keep only recent events (last 1000)
        if len(self._lifecycle_events) > 1000:
            self._lifecycle_events = self._lifecycle_events[-1000:]
        
        logger.debug(
            f"Recorded lifecycle event",
            event_type=event_type,
            alert_id=alert_id,
            rule_id=rule_id
        )
