"""
Alert Rule Evaluation Engine
Handles evaluation of metrics against alert rules and trigger logic
"""

import structlog
from typing import Dict, List
from datetime import datetime

from ..models import AlertRule, EvaluationResult

logger = structlog.get_logger()


class AlertEvaluator:
    """Evaluates metrics against alert rules"""

    def __init__(self):
        self.evaluation_history: Dict[str, List[bool]] = {}

    def evaluate_rule(self, rule: AlertRule, current_value: float) -> bool:
        """Evaluate a single rule against current metric value"""
        threshold = rule.threshold_value
        operator = rule.comparison_operator

        # Perform comparison
        if operator == ">":
            result = current_value > threshold
        elif operator == "<":
            result = current_value < threshold
        elif operator == ">=":
            result = current_value >= threshold
        elif operator == "<=":
            result = current_value <= threshold
        elif operator == "==":
            result = current_value == threshold
        elif operator == "!=":
            result = current_value != threshold
        else:
            logger.warning("Unknown comparison operator", operator=operator, rule_id=rule.rule_id)
            return False

        # Track evaluation history for trigger count logic
        if rule.rule_id not in self.evaluation_history:
            self.evaluation_history[rule.rule_id] = []

        self.evaluation_history[rule.rule_id].append(result)

        # Keep only recent evaluations
        max_history = max(rule.trigger_count, 10)
        self.evaluation_history[rule.rule_id] = self.evaluation_history[rule.rule_id][-max_history:]

        # Check if we have enough consecutive positive evaluations
        recent_evaluations = self.evaluation_history[rule.rule_id][-rule.trigger_count :]

        if len(recent_evaluations) >= rule.trigger_count:
            return all(recent_evaluations)

        return False

    def evaluate_rule_detailed(self, rule: AlertRule, current_value: float) -> EvaluationResult:
        """Evaluate rule and return detailed result"""
        should_trigger = self.evaluate_rule(rule, current_value)

        # Get consecutive trigger count
        consecutive_triggers = 0
        if rule.rule_id in self.evaluation_history:
            recent_history = self.evaluation_history[rule.rule_id]
            for result in reversed(recent_history):
                if result:
                    consecutive_triggers += 1
                else:
                    break

        return EvaluationResult(
            rule_id=rule.rule_id,
            metric_value=current_value,
            threshold_value=rule.threshold_value,
            should_trigger=should_trigger,
            evaluation_time=datetime.now(),
            consecutive_triggers=consecutive_triggers,
            context={
                "operator": rule.comparison_operator,
                "trigger_count_required": rule.trigger_count,
                "evaluation_history_length": len(self.evaluation_history.get(rule.rule_id, [])),
            },
        )

    def reset_evaluation_history(self, rule_id: str = None):
        """Reset evaluation history for a specific rule or all rules"""
        if rule_id:
            self.evaluation_history.pop(rule_id, None)
        else:
            self.evaluation_history.clear()

    def get_evaluation_stats(self, rule_id: str) -> Dict:
        """Get evaluation statistics for a rule"""
        history = self.evaluation_history.get(rule_id, [])
        if not history:
            return {"total_evaluations": 0, "positive_evaluations": 0, "success_rate": 0.0}

        positive_count = sum(history)
        return {
            "total_evaluations": len(history),
            "positive_evaluations": positive_count,
            "success_rate": positive_count / len(history),
            "recent_trend": history[-5:] if len(history) >= 5 else history,
        }
