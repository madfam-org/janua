"""
Alert Rule Domain Model - Entity
Represents alert rule configuration and evaluation logic
"""

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from datetime import timedelta

from .alert import AlertSeverity


class ComparisonOperator(Enum):
    """Supported comparison operators"""

    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    EQUAL = "=="
    NOT_EQUAL = "!="

    @classmethod
    def is_valid(cls, operator: str) -> bool:
        """Check if operator is valid"""
        return operator in [op.value for op in cls]


@dataclass(frozen=True)
class RuleCondition:
    """Value object representing a rule condition"""

    metric_name: str
    threshold_value: float
    comparison_operator: ComparisonOperator
    evaluation_window_seconds: int = 300  # 5 minutes default

    def __post_init__(self):
        """Validate condition parameters"""
        if not self.metric_name:
            raise ValueError("Metric name cannot be empty")
        if self.evaluation_window_seconds <= 0:
            raise ValueError("Evaluation window must be positive")
        if not isinstance(self.comparison_operator, ComparisonOperator):
            raise ValueError("Invalid comparison operator")

    def evaluate(self, current_value: float) -> bool:
        """Evaluate condition against current value"""
        operators = {
            ComparisonOperator.GREATER_THAN: lambda x, y: x > y,
            ComparisonOperator.LESS_THAN: lambda x, y: x < y,
            ComparisonOperator.GREATER_EQUAL: lambda x, y: x >= y,
            ComparisonOperator.LESS_EQUAL: lambda x, y: x <= y,
            ComparisonOperator.EQUAL: lambda x, y: x == y,
            ComparisonOperator.NOT_EQUAL: lambda x, y: x != y,
        }

        operator_func = operators[self.comparison_operator]
        return operator_func(current_value, self.threshold_value)

    def describe(self) -> str:
        """Get human-readable description"""
        return f"{self.metric_name} {self.comparison_operator.value} {self.threshold_value}"


@dataclass(frozen=True)
class AlertChannel:
    """Value object for alert channels"""

    channel_type: str
    enabled: bool = True

    def __post_init__(self):
        """Validate channel"""
        valid_types = {"email", "slack", "webhook", "discord", "sms"}
        if self.channel_type not in valid_types:
            raise ValueError(f"Invalid channel type. Must be one of: {valid_types}")


@dataclass
class AlertRule:
    """Alert rule entity - defines when and how alerts are triggered"""

    # Identity
    rule_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Basic properties
    name: str = ""
    description: str = ""
    severity: AlertSeverity = AlertSeverity.MEDIUM
    enabled: bool = True

    # Core evaluation logic
    condition: Optional[RuleCondition] = None
    trigger_count: int = 1  # consecutive evaluations needed
    cooldown_period_seconds: int = 300  # 5 minutes default

    # Notification configuration
    channels: Set[AlertChannel] = field(default_factory=set)

    # Advanced features
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Lifecycle
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: Optional[str] = None

    def __post_init__(self):
        """Validate rule after initialization"""
        if not self.name:
            raise ValueError("Rule name cannot be empty")
        if not self.condition:
            raise ValueError("Rule must have a condition")
        if self.trigger_count < 1:
            raise ValueError("Trigger count must be at least 1")
        if self.cooldown_period_seconds < 0:
            raise ValueError("Cooldown period cannot be negative")

    def add_channel(self, channel_type: str, enabled: bool = True) -> None:
        """Add notification channel"""
        channel = AlertChannel(channel_type=channel_type, enabled=enabled)
        self.channels.add(channel)

    def remove_channel(self, channel_type: str) -> None:
        """Remove notification channel"""
        self.channels = {ch for ch in self.channels if ch.channel_type != channel_type}

    def get_enabled_channels(self) -> List[str]:
        """Get list of enabled channel types"""
        return [ch.channel_type for ch in self.channels if ch.enabled]

    def add_tag(self, tag: str) -> None:
        """Add tag to rule"""
        if tag:
            self.tags.add(tag.lower())

    def remove_tag(self, tag: str) -> None:
        """Remove tag from rule"""
        self.tags.discard(tag.lower())

    def has_tag(self, tag: str) -> bool:
        """Check if rule has specific tag"""
        return tag.lower() in self.tags

    def enable(self) -> None:
        """Enable the rule"""
        self.enabled = True

    def disable(self) -> None:
        """Disable the rule"""
        self.enabled = False

    def update_condition(
        self,
        metric_name: str,
        threshold_value: float,
        comparison_operator: str,
        evaluation_window_seconds: int = 300,
    ) -> None:
        """Update rule condition"""
        if not ComparisonOperator.is_valid(comparison_operator):
            raise ValueError(f"Invalid comparison operator: {comparison_operator}")

        operator_enum = ComparisonOperator(comparison_operator)
        self.condition = RuleCondition(
            metric_name=metric_name,
            threshold_value=threshold_value,
            comparison_operator=operator_enum,
            evaluation_window_seconds=evaluation_window_seconds,
        )

    def update_severity(self, severity: AlertSeverity) -> None:
        """Update rule severity"""
        self.severity = severity

    def update_trigger_settings(self, trigger_count: int, cooldown_period_seconds: int) -> None:
        """Update trigger and cooldown settings"""
        if trigger_count < 1:
            raise ValueError("Trigger count must be at least 1")
        if cooldown_period_seconds < 0:
            raise ValueError("Cooldown period cannot be negative")

        self.trigger_count = trigger_count
        self.cooldown_period_seconds = cooldown_period_seconds

    def is_high_priority(self) -> bool:
        """Check if rule is high priority (HIGH or CRITICAL)"""
        return self.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]

    def get_cooldown_duration(self) -> timedelta:
        """Get cooldown duration as timedelta"""
        return timedelta(seconds=self.cooldown_period_seconds)

    def get_evaluation_window(self) -> timedelta:
        """Get evaluation window as timedelta"""
        if not self.condition:
            return timedelta(seconds=300)  # Default 5 minutes
        return timedelta(seconds=self.condition.evaluation_window_seconds)

    def matches_tags(self, required_tags: Set[str]) -> bool:
        """Check if rule matches all required tags"""
        return required_tags.issubset(self.tags)

    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary for serialization"""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "enabled": self.enabled,
            "condition": {
                "metric_name": self.condition.metric_name,
                "threshold_value": self.condition.threshold_value,
                "comparison_operator": self.condition.comparison_operator.value,
                "evaluation_window_seconds": self.condition.evaluation_window_seconds,
            }
            if self.condition
            else None,
            "trigger_count": self.trigger_count,
            "cooldown_period_seconds": self.cooldown_period_seconds,
            "channels": [
                {"channel_type": ch.channel_type, "enabled": ch.enabled} for ch in self.channels
            ],
            "tags": list(self.tags),
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlertRule":
        """Create rule from dictionary"""
        rule = cls(
            rule_id=data.get("rule_id", str(uuid.uuid4())),
            name=data["name"],
            description=data.get("description", ""),
            severity=AlertSeverity(data.get("severity", "medium")),
            enabled=data.get("enabled", True),
            trigger_count=data.get("trigger_count", 1),
            cooldown_period_seconds=data.get("cooldown_period_seconds", 300),
            tags=set(data.get("tags", [])),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            created_by=data.get("created_by"),
        )

        # Set condition if provided
        if "condition" in data and data["condition"]:
            cond_data = data["condition"]
            rule.condition = RuleCondition(
                metric_name=cond_data["metric_name"],
                threshold_value=cond_data["threshold_value"],
                comparison_operator=ComparisonOperator(cond_data["comparison_operator"]),
                evaluation_window_seconds=cond_data.get("evaluation_window_seconds", 300),
            )

        # Set channels if provided
        if "channels" in data:
            for ch_data in data["channels"]:
                rule.add_channel(
                    channel_type=ch_data["channel_type"], enabled=ch_data.get("enabled", True)
                )

        return rule


class RuleBuilder:
    """Builder pattern for creating alert rules"""

    def __init__(self):
        self._rule = AlertRule()

    def with_name(self, name: str) -> "RuleBuilder":
        """Set rule name"""
        self._rule.name = name
        return self

    def with_description(self, description: str) -> "RuleBuilder":
        """Set rule description"""
        self._rule.description = description
        return self

    def with_severity(self, severity: AlertSeverity) -> "RuleBuilder":
        """Set rule severity"""
        self._rule.severity = severity
        return self

    def with_condition(
        self,
        metric_name: str,
        threshold_value: float,
        comparison_operator: str,
        evaluation_window_seconds: int = 300,
    ) -> "RuleBuilder":
        """Set rule condition"""
        operator_enum = ComparisonOperator(comparison_operator)
        self._rule.condition = RuleCondition(
            metric_name=metric_name,
            threshold_value=threshold_value,
            comparison_operator=operator_enum,
            evaluation_window_seconds=evaluation_window_seconds,
        )
        return self

    def with_trigger_count(self, count: int) -> "RuleBuilder":
        """Set trigger count"""
        self._rule.trigger_count = count
        return self

    def with_cooldown(self, seconds: int) -> "RuleBuilder":
        """Set cooldown period"""
        self._rule.cooldown_period_seconds = seconds
        return self

    def with_channel(self, channel_type: str, enabled: bool = True) -> "RuleBuilder":
        """Add notification channel"""
        self._rule.add_channel(channel_type, enabled)
        return self

    def with_tag(self, tag: str) -> "RuleBuilder":
        """Add tag"""
        self._rule.add_tag(tag)
        return self

    def with_metadata(self, key: str, value: Any) -> "RuleBuilder":
        """Add metadata"""
        self._rule.metadata[key] = value
        return self

    def build(self) -> AlertRule:
        """Build the alert rule"""
        # Validate before returning
        if not self._rule.name:
            raise ValueError("Rule name is required")
        if not self._rule.condition:
            raise ValueError("Rule condition is required")

        return self._rule
