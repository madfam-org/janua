"""
Notification Domain Models - Value Objects and Strategy Interfaces
Represents notification requests and channel configurations
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Protocol
from datetime import datetime
from enum import Enum

from .alert import Alert


class NotificationStatus(Enum):
    """Notification delivery status"""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"
    RATE_LIMITED = "rate_limited"


class NotificationPriority(Enum):
    """Notification priority levels"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass(frozen=True)
class NotificationTemplate:
    """Value object for notification templates"""

    template_id: str
    channel_type: str
    subject_template: str
    body_template: str
    variables: List[str] = field(default_factory=list)

    def render_subject(self, context: Dict[str, Any]) -> str:
        """Render subject template with context"""
        try:
            return self.subject_template.format(**context)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")

    def render_body(self, context: Dict[str, Any]) -> str:
        """Render body template with context"""
        try:
            return self.body_template.format(**context)
        except KeyError as e:
            raise ValueError(f"Missing template variable: {e}")


@dataclass(frozen=True)
class NotificationChannel:
    """Value object representing a notification channel configuration"""

    channel_id: str
    channel_type: str  # email, slack, webhook, discord, sms
    name: str
    config: Dict[str, Any]
    enabled: bool = True
    rate_limit_per_hour: Optional[int] = None
    priority_filter: Optional[NotificationPriority] = None

    def __post_init__(self):
        """Validate channel configuration"""
        valid_types = {"email", "slack", "webhook", "discord", "sms"}
        if self.channel_type not in valid_types:
            raise ValueError(f"Invalid channel type. Must be one of: {valid_types}")

        if not self.name:
            raise ValueError("Channel name cannot be empty")

        if not self.config:
            raise ValueError("Channel config cannot be empty")

        # Validate required config keys per channel type
        required_keys = self._get_required_config_keys()
        missing_keys = required_keys - set(self.config.keys())
        if missing_keys:
            raise ValueError(
                f"Missing required config keys for {self.channel_type}: {missing_keys}"
            )

    def _get_required_config_keys(self) -> set:
        """Get required configuration keys for channel type"""
        requirements = {
            "email": {"smtp_server", "username", "password", "to_addresses"},
            "slack": {"webhook_url"},
            "webhook": {"webhook_url"},
            "discord": {"webhook_url"},
            "sms": {"api_key", "service_provider", "phone_numbers"},
        }
        return requirements.get(self.channel_type, set())

    def supports_priority(self, priority: NotificationPriority) -> bool:
        """Check if channel supports the given priority level"""
        if not self.priority_filter:
            return True

        priority_levels = {
            NotificationPriority.LOW: 1,
            NotificationPriority.NORMAL: 2,
            NotificationPriority.HIGH: 3,
            NotificationPriority.URGENT: 4,
        }

        return priority_levels[priority] >= priority_levels[self.priority_filter]

    def is_rate_limited(self, sent_count_last_hour: int) -> bool:
        """Check if channel is rate limited"""
        if not self.rate_limit_per_hour:
            return False
        return sent_count_last_hour >= self.rate_limit_per_hour


@dataclass
class NotificationRequest:
    """Request to send a notification - aggregate root for notification domain"""

    # Identity
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Core data
    alert: Alert = None
    channel: NotificationChannel = None
    priority: NotificationPriority = NotificationPriority.NORMAL

    # Content
    subject: str = ""
    message: str = ""
    template: Optional[NotificationTemplate] = None
    context: Dict[str, Any] = field(default_factory=dict)

    # Delivery tracking
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3

    # Metadata
    error_message: Optional[str] = None
    delivery_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate notification request"""
        if not self.alert:
            raise ValueError("Alert is required for notification request")
        if not self.channel:
            raise ValueError("Channel is required for notification request")
        if not self.channel.enabled:
            raise ValueError("Cannot create request for disabled channel")

    def prepare_content(self) -> None:
        """Prepare notification content using template or defaults"""
        if self.template:
            # Use template to generate content
            template_context = self._build_template_context()
            self.subject = self.template.render_subject(template_context)
            self.message = self.template.render_body(template_context)
        else:
            # Use default content generation
            self.subject = self._generate_default_subject()
            self.message = self._generate_default_message()

    def mark_sent(self, delivery_metadata: Optional[Dict[str, Any]] = None) -> None:
        """Mark notification as sent"""
        self.status = NotificationStatus.SENT
        self.sent_at = datetime.now()
        if delivery_metadata:
            self.delivery_metadata.update(delivery_metadata)

    def mark_failed(self, error_message: str) -> None:
        """Mark notification as failed"""
        self.status = NotificationStatus.FAILED
        self.failed_at = datetime.now()
        self.error_message = error_message

    def mark_rate_limited(self) -> None:
        """Mark notification as rate limited"""
        self.status = NotificationStatus.RATE_LIMITED

    def can_retry(self) -> bool:
        """Check if notification can be retried"""
        return self.status == NotificationStatus.FAILED and self.retry_count < self.max_retries

    def increment_retry(self) -> None:
        """Increment retry count and update status"""
        if not self.can_retry():
            raise ValueError("Cannot retry notification")

        self.retry_count += 1
        self.status = NotificationStatus.RETRYING

    def is_urgent(self) -> bool:
        """Check if notification is urgent"""
        return (
            self.priority == NotificationPriority.URGENT or self.alert.severity.name == "CRITICAL"
        )

    def get_age_minutes(self) -> float:
        """Get age of notification request in minutes"""
        return (datetime.now() - self.created_at).total_seconds() / 60

    def _build_template_context(self) -> Dict[str, Any]:
        """Build context for template rendering"""
        base_context = {
            "alert_id": self.alert.alert_id,
            "rule_id": self.alert.rule_id,
            "severity": self.alert.severity.value,
            "status": self.alert.status.value,
            "title": self.alert.title,
            "description": self.alert.description,
            "triggered_at": self.alert.triggered_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "channel_name": self.channel.name,
        }

        # Add metrics if available
        if self.alert.metrics:
            base_context.update(
                {
                    "metric_name": self.alert.metrics.metric_name,
                    "current_value": self.alert.metrics.current_value,
                    "threshold_value": self.alert.metrics.threshold_value,
                    "comparison_operator": self.alert.metrics.comparison_operator,
                }
            )

        # Add custom context
        base_context.update(self.context)
        base_context.update(self.alert.context)

        return base_context

    def _generate_default_subject(self) -> str:
        """Generate default subject line"""
        return f"[{self.alert.severity.value.upper()}] {self.alert.title}"

    def _generate_default_message(self) -> str:
        """Generate default message content"""
        lines = [
            f"Alert: {self.alert.title}",
            f"Severity: {self.alert.severity.value.upper()}",
            f"Description: {self.alert.description}",
            f"Triggered: {self.alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Alert ID: {self.alert.alert_id}",
        ]

        if self.alert.metrics:
            lines.extend(
                [
                    f"Metric: {self.alert.metrics.metric_name}",
                    f"Current Value: {self.alert.metrics.current_value}",
                    f"Threshold: {self.alert.metrics.threshold_value}",
                ]
            )

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "request_id": self.request_id,
            "alert_id": self.alert.alert_id,
            "channel_id": self.channel.channel_id,
            "priority": self.priority.value,
            "subject": self.subject,
            "message": self.message,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error_message": self.error_message,
            "delivery_metadata": self.delivery_metadata,
            "context": self.context,
        }


class NotificationStrategy(Protocol):
    """Protocol for notification delivery strategies"""

    async def send(self, request: NotificationRequest) -> bool:
        """Send notification using this strategy"""
        ...  # noqa: B018 - Protocol method stub, implementation in concrete classes

    async def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate channel configuration for this strategy"""
        ...  # noqa: B018 - Protocol method stub, implementation in concrete classes

    def get_channel_type(self) -> str:
        """Get supported channel type"""
        ...  # noqa: B018 - Protocol method stub, implementation in concrete classes


class AbstractNotificationStrategy(ABC):
    """Abstract base class for notification strategies"""

    @abstractmethod
    async def send(self, request: NotificationRequest) -> bool:
        """Send notification using this strategy"""

    @abstractmethod
    async def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate channel configuration for this strategy"""

    @abstractmethod
    def get_channel_type(self) -> str:
        """Get supported channel type"""

    def _log_attempt(self, request: NotificationRequest, action: str) -> None:
        """Log notification attempt"""
        from app.logging import logger

        logger.info(
            f"Notification {action}",
            request_id=request.request_id,
            channel_id=request.channel.channel_id,
            channel_type=request.channel.channel_type,
            alert_id=request.alert.alert_id,
        )

    def _log_error(self, request: NotificationRequest, error: str) -> None:
        """Log notification error"""
        from app.logging import logger

        logger.error(
            "Notification failed",
            request_id=request.request_id,
            channel_id=request.channel.channel_id,
            channel_type=request.channel.channel_type,
            alert_id=request.alert.alert_id,
            error=error,
        )
