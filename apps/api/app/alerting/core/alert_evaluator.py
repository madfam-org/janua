"""
Alert Evaluator
Evaluates metrics against alert rules to determine if alerts should trigger.
"""

import structlog
from typing import Dict, List

from .alert_models import AlertRule

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
