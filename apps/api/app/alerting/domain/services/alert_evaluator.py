"""
Alert Evaluator Domain Service
Core domain service for evaluating alert rules against metrics
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Protocol, Tuple

from ..models.rule import AlertRule
from ..models.alert import Alert, AlertMetrics, AlertStatus
import structlog
logger = structlog.get_logger()


@dataclass(frozen=True)
class EvaluationResult:
    """Result of alert rule evaluation"""
    rule_id: str
    metric_name: str
    current_value: float
    threshold_value: float
    comparison_operator: str
    should_trigger: bool
    consecutive_breaches: int
    evaluation_time: datetime = field(default_factory=datetime.now)
    context: Dict[str, any] = field(default_factory=dict)
    
    def is_breach(self) -> bool:
        """Check if this evaluation represents a threshold breach"""
        return self.should_trigger
    
    def breach_severity(self) -> str:
        """Get breach severity description"""
        if not self.should_trigger:
            return "no_breach"
        
        if self.consecutive_breaches >= 3:
            return "sustained_breach"
        elif self.consecutive_breaches >= 2:
            return "repeated_breach"
        else:
            return "initial_breach"


class MetricsProvider(Protocol):
    """Protocol for metric data providers"""
    
    async def get_metric_value(self, metric_name: str, window_seconds: int) -> Optional[float]:
        """Get current metric value for evaluation"""
        ...
    
    async def get_metric_context(self, metric_name: str, window_seconds: int) -> Dict[str, any]:
        """Get additional context for the metric"""
        ...


class RuleEvaluationHistory:
    """Manages evaluation history for rules"""
    
    def __init__(self):
        self._history: Dict[str, List[bool]] = {}
        self._timestamps: Dict[str, List[datetime]] = {}
    
    def record_evaluation(self, rule_id: str, result: bool) -> None:
        """Record evaluation result for rule"""
        if rule_id not in self._history:
            self._history[rule_id] = []
            self._timestamps[rule_id] = []
        
        self._history[rule_id].append(result)
        self._timestamps[rule_id].append(datetime.now())
        
        # Keep only recent history (last 50 evaluations)
        self._history[rule_id] = self._history[rule_id][-50:]
        self._timestamps[rule_id] = self._timestamps[rule_id][-50:]
    
    def get_consecutive_breaches(self, rule_id: str) -> int:
        """Get number of consecutive positive evaluations"""
        if rule_id not in self._history:
            return 0
        
        history = self._history[rule_id]
        consecutive = 0
        
        # Count from the end backwards
        for result in reversed(history):
            if result:
                consecutive += 1
            else:
                break
        
        return consecutive
    
    def get_breach_rate(self, rule_id: str, window_minutes: int = 60) -> float:
        """Get breach rate within time window"""
        if rule_id not in self._history:
            return 0.0
        
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        recent_results = [
            result for result, timestamp in zip(self._history[rule_id], self._timestamps[rule_id])
            if timestamp >= cutoff
        ]
        
        if not recent_results:
            return 0.0
        
        return sum(recent_results) / len(recent_results)
    
    def clear_history(self, rule_id: str) -> None:
        """Clear evaluation history for rule"""
        self._history.pop(rule_id, None)
        self._timestamps.pop(rule_id, None)
    
    def get_evaluation_stats(self, rule_id: str) -> Dict[str, any]:
        """Get evaluation statistics for rule"""
        if rule_id not in self._history:
            return {
                "total_evaluations": 0,
                "breach_count": 0,
                "breach_rate": 0.0,
                "consecutive_breaches": 0,
                "last_evaluation": None
            }
        
        history = self._history[rule_id]
        timestamps = self._timestamps[rule_id]
        
        return {
            "total_evaluations": len(history),
            "breach_count": sum(history),
            "breach_rate": sum(history) / len(history) if history else 0.0,
            "consecutive_breaches": self.get_consecutive_breaches(rule_id),
            "last_evaluation": timestamps[-1].isoformat() if timestamps else None,
            "recent_trend": history[-10:] if len(history) >= 10 else history
        }


class AlertEvaluatorService:
    """Domain service for evaluating alert rules"""
    
    def __init__(self, metrics_provider: MetricsProvider):
        self._metrics_provider = metrics_provider
        self._history = RuleEvaluationHistory()
        self._cooldown_tracker: Dict[str, datetime] = {}
    
    async def evaluate_rule(self, rule: AlertRule) -> EvaluationResult:
        """Evaluate a single alert rule"""
        if not rule.enabled:
            logger.debug(f"Rule {rule.rule_id} is disabled, skipping evaluation")
            return EvaluationResult(
                rule_id=rule.rule_id,
                metric_name=rule.condition.metric_name,
                current_value=0.0,
                threshold_value=rule.condition.threshold_value,
                comparison_operator=rule.condition.comparison_operator.value,
                should_trigger=False,
                consecutive_breaches=0
            )
        
        # Check if rule is in cooldown
        if self._is_in_cooldown(rule.rule_id, rule.cooldown_period_seconds):
            logger.debug(f"Rule {rule.rule_id} is in cooldown, skipping evaluation")
            return EvaluationResult(
                rule_id=rule.rule_id,
                metric_name=rule.condition.metric_name,
                current_value=0.0,
                threshold_value=rule.condition.threshold_value,
                comparison_operator=rule.condition.comparison_operator.value,
                should_trigger=False,
                consecutive_breaches=0,
                context={"reason": "cooldown_active"}
            )
        
        try:
            # Get current metric value
            current_value = await self._metrics_provider.get_metric_value(
                rule.condition.metric_name,
                rule.condition.evaluation_window_seconds
            )
            
            if current_value is None:
                logger.warning(f"No metric value available for {rule.condition.metric_name}")
                return EvaluationResult(
                    rule_id=rule.rule_id,
                    metric_name=rule.condition.metric_name,
                    current_value=0.0,
                    threshold_value=rule.condition.threshold_value,
                    comparison_operator=rule.condition.comparison_operator.value,
                    should_trigger=False,
                    consecutive_breaches=0,
                    context={"reason": "metric_unavailable"}
                )
            
            # Evaluate condition
            condition_met = rule.condition.evaluate(current_value)
            
            # Record evaluation in history
            self._history.record_evaluation(rule.rule_id, condition_met)
            
            # Get consecutive breaches
            consecutive_breaches = self._history.get_consecutive_breaches(rule.rule_id)
            
            # Determine if alert should trigger based on trigger count
            should_trigger = condition_met and consecutive_breaches >= rule.trigger_count
            
            # Get additional context
            context = await self._metrics_provider.get_metric_context(
                rule.condition.metric_name,
                rule.condition.evaluation_window_seconds
            )
            context.update({
                "evaluation_history": self._history.get_evaluation_stats(rule.rule_id),
                "trigger_count_required": rule.trigger_count,
                "cooldown_period_seconds": rule.cooldown_period_seconds
            })
            
            result = EvaluationResult(
                rule_id=rule.rule_id,
                metric_name=rule.condition.metric_name,
                current_value=current_value,
                threshold_value=rule.condition.threshold_value,
                comparison_operator=rule.condition.comparison_operator.value,
                should_trigger=should_trigger,
                consecutive_breaches=consecutive_breaches,
                context=context
            )
            
            # Set cooldown if alert should trigger
            if should_trigger:
                self._set_cooldown(rule.rule_id)
            
            logger.debug(
                f"Rule evaluation completed",
                rule_id=rule.rule_id,
                metric_name=rule.condition.metric_name,
                current_value=current_value,
                threshold=rule.condition.threshold_value,
                condition_met=condition_met,
                consecutive_breaches=consecutive_breaches,
                should_trigger=should_trigger
            )
            
            return result
            
        except Exception as e:
            logger.error(
                f"Failed to evaluate rule {rule.rule_id}",
                error=str(e),
                rule_id=rule.rule_id,
                metric_name=rule.condition.metric_name
            )
            return EvaluationResult(
                rule_id=rule.rule_id,
                metric_name=rule.condition.metric_name,
                current_value=0.0,
                threshold_value=rule.condition.threshold_value,
                comparison_operator=rule.condition.comparison_operator.value,
                should_trigger=False,
                consecutive_breaches=0,
                context={"reason": "evaluation_error", "error": str(e)}
            )
    
    async def evaluate_rules(self, rules: List[AlertRule]) -> List[EvaluationResult]:
        """Evaluate multiple alert rules"""
        results = []
        
        for rule in rules:
            try:
                result = await self.evaluate_rule(rule)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to evaluate rule {rule.rule_id}: {e}")
                # Add failed result
                results.append(EvaluationResult(
                    rule_id=rule.rule_id,
                    metric_name=rule.condition.metric_name if rule.condition else "unknown",
                    current_value=0.0,
                    threshold_value=0.0,
                    comparison_operator="unknown",
                    should_trigger=False,
                    consecutive_breaches=0,
                    context={"reason": "evaluation_exception", "error": str(e)}
                ))
        
        return results
    
    def create_alert_from_evaluation(self, rule: AlertRule, evaluation: EvaluationResult) -> Alert:
        """Create alert from evaluation result"""
        if not evaluation.should_trigger:
            raise ValueError("Cannot create alert from non-triggering evaluation")
        
        # Create alert metrics
        metrics = AlertMetrics(
            metric_name=evaluation.metric_name,
            current_value=evaluation.current_value,
            threshold_value=evaluation.threshold_value,
            comparison_operator=evaluation.comparison_operator,
            evaluation_window_seconds=rule.condition.evaluation_window_seconds
        )
        
        # Create alert
        alert = Alert(
            rule_id=rule.rule_id,
            severity=rule.severity,
            status=AlertStatus.TRIGGERED,
            title=rule.name,
            description=rule.description,
            metrics=metrics,
            context=evaluation.context
        )
        
        return alert
    
    def _is_in_cooldown(self, rule_id: str, cooldown_seconds: int) -> bool:
        """Check if rule is in cooldown period"""
        if rule_id not in self._cooldown_tracker:
            return False
        
        cooldown_end = self._cooldown_tracker[rule_id] + timedelta(seconds=cooldown_seconds)
        return datetime.now() < cooldown_end
    
    def _set_cooldown(self, rule_id: str) -> None:
        """Set cooldown for rule"""
        self._cooldown_tracker[rule_id] = datetime.now()
    
    def clear_cooldown(self, rule_id: str) -> None:
        """Clear cooldown for rule"""
        self._cooldown_tracker.pop(rule_id, None)
    
    def get_rule_statistics(self, rule_id: str) -> Dict[str, any]:
        """Get evaluation statistics for rule"""
        stats = self._history.get_evaluation_stats(rule_id)
        
        # Add cooldown information
        stats["in_cooldown"] = rule_id in self._cooldown_tracker
        if rule_id in self._cooldown_tracker:
            stats["cooldown_set_at"] = self._cooldown_tracker[rule_id].isoformat()
        
        return stats
    
    def reset_rule_history(self, rule_id: str) -> None:
        """Reset evaluation history for rule"""
        self._history.clear_history(rule_id)
        self.clear_cooldown(rule_id)
        logger.info(f"Reset evaluation history for rule {rule_id}")


class AlertEvaluationOrchestrator:
    """Orchestrates alert evaluation workflows"""
    
    def __init__(self, evaluator: AlertEvaluatorService):
        self._evaluator = evaluator
    
    async def evaluate_and_create_alerts(self, rules: List[AlertRule]) -> Tuple[List[Alert], List[EvaluationResult]]:
        """Evaluate rules and create alerts for triggering conditions"""
        evaluation_results = await self._evaluator.evaluate_rules(rules)
        
        alerts = []
        for rule, evaluation in zip(rules, evaluation_results):
            if evaluation.should_trigger:
                try:
                    alert = self._evaluator.create_alert_from_evaluation(rule, evaluation)
                    alerts.append(alert)
                    logger.info(
                        f"Created alert from rule evaluation",
                        alert_id=alert.alert_id,
                        rule_id=rule.rule_id,
                        severity=alert.severity.value
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to create alert from evaluation",
                        rule_id=rule.rule_id,
                        error=str(e)
                    )
        
        return alerts, evaluation_results
    
    async def evaluate_for_auto_resolution(self, active_alerts: List[Alert], rules: Dict[str, AlertRule]) -> List[Alert]:
        """Evaluate active alerts for potential auto-resolution"""
        alerts_to_resolve = []
        
        for alert in active_alerts:
            if not alert.is_active():
                continue
            
            rule = rules.get(alert.rule_id)
            if not rule:
                logger.warning(f"Rule {alert.rule_id} not found for alert {alert.alert_id}")
                continue
            
            try:
                evaluation = await self._evaluator.evaluate_rule(rule)
                
                # Check if condition is no longer met
                if not evaluation.should_trigger and evaluation.consecutive_breaches == 0:
                    alerts_to_resolve.append(alert)
                    logger.info(
                        f"Alert {alert.alert_id} marked for auto-resolution",
                        rule_id=rule.rule_id,
                        current_value=evaluation.current_value
                    )
                    
            except Exception as e:
                logger.error(
                    f"Failed to evaluate alert {alert.alert_id} for auto-resolution",
                    error=str(e)
                )
        
        return alerts_to_resolve
