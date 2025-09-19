"""
Production Stability Monitoring
Real-time monitoring and alerting for enterprise authentication platform
"""
import asyncio
import logging
import time
import psutil
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database import get_db
from app.config import settings


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ComponentStatus(Enum):
    """Component health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthMetric:
    """Health metric data structure."""
    name: str
    value: float
    unit: str
    status: ComponentStatus
    timestamp: datetime
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    additional_info: Optional[Dict[str, Any]] = None


@dataclass
class Alert:
    """Alert data structure."""
    id: str
    severity: AlertSeverity
    title: str
    description: str
    component: str
    metric_name: Optional[str]
    metric_value: Optional[float]
    threshold: Optional[float]
    timestamp: datetime
    resolved: bool = False
    resolution_time: Optional[datetime] = None


class StabilityMonitor:
    """Production stability monitoring system."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.metrics: Dict[str, HealthMetric] = {}
        self.alerts: List[Alert] = []
        self.alert_callbacks: List[Callable[[Alert], None]] = []
        self.monitoring_enabled = True
        self.check_interval = 30  # seconds

        # Health thresholds
        self.thresholds = {
            "cpu_usage": {"warning": 70.0, "critical": 90.0},
            "memory_usage": {"warning": 80.0, "critical": 95.0},
            "disk_usage": {"warning": 85.0, "critical": 95.0},
            "database_connections": {"warning": 80.0, "critical": 95.0},
            "response_time": {"warning": 1.0, "critical": 3.0},
            "error_rate": {"warning": 5.0, "critical": 10.0},
            "database_response_time": {"warning": 0.5, "critical": 2.0}
        }

    async def start_monitoring(self):
        """Start the monitoring loop."""
        self.logger.info("Starting production stability monitoring...")

        while self.monitoring_enabled:
            try:
                await self._collect_metrics()
                await self._evaluate_health()
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                self.logger.error(f"Monitoring error: {str(e)}")
                await asyncio.sleep(self.check_interval)

    async def stop_monitoring(self):
        """Stop the monitoring loop."""
        self.monitoring_enabled = False
        self.logger.info("Stopped production stability monitoring")

    async def _collect_metrics(self):
        """Collect system and application metrics."""
        current_time = datetime.utcnow()

        # System metrics
        await self._collect_system_metrics(current_time)

        # Database metrics
        await self._collect_database_metrics(current_time)

        # Application metrics
        await self._collect_application_metrics(current_time)

    async def _collect_system_metrics(self, timestamp: datetime):
        """Collect system-level metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.metrics["cpu_usage"] = HealthMetric(
                name="cpu_usage",
                value=cpu_percent,
                unit="percent",
                status=self._get_status("cpu_usage", cpu_percent),
                timestamp=timestamp,
                threshold_warning=self.thresholds["cpu_usage"]["warning"],
                threshold_critical=self.thresholds["cpu_usage"]["critical"]
            )

            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            self.metrics["memory_usage"] = HealthMetric(
                name="memory_usage",
                value=memory_percent,
                unit="percent",
                status=self._get_status("memory_usage", memory_percent),
                timestamp=timestamp,
                threshold_warning=self.thresholds["memory_usage"]["warning"],
                threshold_critical=self.thresholds["memory_usage"]["critical"],
                additional_info={
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used
                }
            )

            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            self.metrics["disk_usage"] = HealthMetric(
                name="disk_usage",
                value=disk_percent,
                unit="percent",
                status=self._get_status("disk_usage", disk_percent),
                timestamp=timestamp,
                threshold_warning=self.thresholds["disk_usage"]["warning"],
                threshold_critical=self.thresholds["disk_usage"]["critical"],
                additional_info={
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free
                }
            )

        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {str(e)}")

    async def _collect_database_metrics(self, timestamp: datetime):
        """Collect database metrics."""
        try:
            async for db in get_db():
                start_time = time.time()

                # Test database connectivity and response time
                try:
                    await db.execute(text("SELECT 1"))
                    db_response_time = time.time() - start_time

                    self.metrics["database_response_time"] = HealthMetric(
                        name="database_response_time",
                        value=db_response_time,
                        unit="seconds",
                        status=self._get_status("database_response_time", db_response_time),
                        timestamp=timestamp,
                        threshold_warning=self.thresholds["database_response_time"]["warning"],
                        threshold_critical=self.thresholds["database_response_time"]["critical"]
                    )

                    # Database connection pool info
                    engine = db.get_bind()
                    pool = engine.pool

                    if hasattr(pool, 'size') and hasattr(pool, 'checked_in'):
                        pool_usage = (pool.checked_in() / pool.size()) * 100 if pool.size() > 0 else 0

                        self.metrics["database_connections"] = HealthMetric(
                            name="database_connections",
                            value=pool_usage,
                            unit="percent",
                            status=self._get_status("database_connections", pool_usage),
                            timestamp=timestamp,
                            threshold_warning=self.thresholds["database_connections"]["warning"],
                            threshold_critical=self.thresholds["database_connections"]["critical"],
                            additional_info={
                                "pool_size": pool.size(),
                                "checked_in": pool.checked_in(),
                                "checked_out": pool.checked_out(),
                                "overflow": pool.overflow(),
                                "invalid": pool.invalid()
                            }
                        )

                except Exception as db_error:
                    self.metrics["database_response_time"] = HealthMetric(
                        name="database_response_time",
                        value=-1,
                        unit="seconds",
                        status=ComponentStatus.UNHEALTHY,
                        timestamp=timestamp,
                        additional_info={"error": str(db_error)}
                    )

                break  # Only need one connection for testing

        except Exception as e:
            self.logger.error(f"Error collecting database metrics: {str(e)}")

    async def _collect_application_metrics(self, timestamp: datetime):
        """Collect application-specific metrics."""
        try:
            # These would be collected from your application metrics
            # For now, we'll use placeholder values

            # Response time metric (would come from middleware)
            # This is a placeholder - integrate with your actual metrics
            response_time = 0.1  # seconds
            self.metrics["response_time"] = HealthMetric(
                name="response_time",
                value=response_time,
                unit="seconds",
                status=self._get_status("response_time", response_time),
                timestamp=timestamp,
                threshold_warning=self.thresholds["response_time"]["warning"],
                threshold_critical=self.thresholds["response_time"]["critical"]
            )

            # Error rate metric (would come from application logs)
            error_rate = 0.5  # percent
            self.metrics["error_rate"] = HealthMetric(
                name="error_rate",
                value=error_rate,
                unit="percent",
                status=self._get_status("error_rate", error_rate),
                timestamp=timestamp,
                threshold_warning=self.thresholds["error_rate"]["warning"],
                threshold_critical=self.thresholds["error_rate"]["critical"]
            )

        except Exception as e:
            self.logger.error(f"Error collecting application metrics: {str(e)}")

    def _get_status(self, metric_name: str, value: float) -> ComponentStatus:
        """Determine component status based on metric value and thresholds."""
        if metric_name not in self.thresholds:
            return ComponentStatus.UNKNOWN

        thresholds = self.thresholds[metric_name]

        if value >= thresholds["critical"]:
            return ComponentStatus.UNHEALTHY
        elif value >= thresholds["warning"]:
            return ComponentStatus.DEGRADED
        else:
            return ComponentStatus.HEALTHY

    async def _evaluate_health(self):
        """Evaluate overall health and generate alerts."""
        for metric_name, metric in self.metrics.items():
            if metric.status in [ComponentStatus.DEGRADED, ComponentStatus.UNHEALTHY]:
                await self._generate_alert(metric)

    async def _generate_alert(self, metric: HealthMetric):
        """Generate alert for unhealthy metrics."""
        alert_id = f"{metric.name}_{int(metric.timestamp.timestamp())}"

        # Check if we already have a recent alert for this metric
        recent_alerts = [
            a for a in self.alerts
            if a.metric_name == metric.name
            and not a.resolved
            and (datetime.utcnow() - a.timestamp) < timedelta(minutes=5)
        ]

        if recent_alerts:
            return  # Don't spam alerts

        severity = AlertSeverity.CRITICAL if metric.status == ComponentStatus.UNHEALTHY else AlertSeverity.WARNING
        threshold = metric.threshold_critical if metric.status == ComponentStatus.UNHEALTHY else metric.threshold_warning

        alert = Alert(
            id=alert_id,
            severity=severity,
            title=f"{metric.name.replace('_', ' ').title()} Alert",
            description=f"{metric.name} is {metric.value}{metric.unit} (threshold: {threshold}{metric.unit})",
            component=metric.name,
            metric_name=metric.name,
            metric_value=metric.value,
            threshold=threshold,
            timestamp=metric.timestamp
        )

        self.alerts.append(alert)
        await self._send_alert(alert)

    async def _send_alert(self, alert: Alert):
        """Send alert through configured channels."""
        self.logger.warning(f"ALERT [{alert.severity.value.upper()}]: {alert.title} - {alert.description}")

        # Call registered alert callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                self.logger.error(f"Error in alert callback: {str(e)}")

    def register_alert_callback(self, callback: Callable[[Alert], None]):
        """Register a callback for alerts."""
        self.alert_callbacks.append(callback)

    def get_current_health(self) -> Dict[str, Any]:
        """Get current health status."""
        overall_status = ComponentStatus.HEALTHY

        # Determine overall status
        for metric in self.metrics.values():
            if metric.status == ComponentStatus.UNHEALTHY:
                overall_status = ComponentStatus.UNHEALTHY
                break
            elif metric.status == ComponentStatus.DEGRADED and overall_status == ComponentStatus.HEALTHY:
                overall_status = ComponentStatus.DEGRADED

        return {
            "overall_status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {name: asdict(metric) for name, metric in self.metrics.items()},
            "active_alerts": len([a for a in self.alerts if not a.resolved]),
            "uptime": self._get_uptime()
        }

    def get_alerts(self, limit: int = 50, severity: Optional[AlertSeverity] = None) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        alerts = self.alerts

        if severity:
            alerts = [a for a in alerts if a.severity == severity]

        # Sort by timestamp (newest first) and limit
        alerts = sorted(alerts, key=lambda x: x.timestamp, reverse=True)[:limit]

        return [asdict(alert) for alert in alerts]

    def resolve_alert(self, alert_id: str):
        """Mark an alert as resolved."""
        for alert in self.alerts:
            if alert.id == alert_id and not alert.resolved:
                alert.resolved = True
                alert.resolution_time = datetime.utcnow()
                self.logger.info(f"Alert resolved: {alert.title}")
                break

    def _get_uptime(self) -> str:
        """Get system uptime."""
        try:
            uptime_seconds = time.time() - psutil.boot_time()
            uptime_delta = timedelta(seconds=uptime_seconds)
            return str(uptime_delta).split('.')[0]  # Remove microseconds
        except:
            return "unknown"

    def update_thresholds(self, metric_name: str, warning: float, critical: float):
        """Update alert thresholds for a metric."""
        if metric_name in self.thresholds:
            self.thresholds[metric_name]["warning"] = warning
            self.thresholds[metric_name]["critical"] = critical
            self.logger.info(f"Updated thresholds for {metric_name}: warning={warning}, critical={critical}")


# Global monitor instance
stability_monitor = StabilityMonitor()


# Alert integration functions
def slack_alert_callback(alert: Alert):
    """Send alert to Slack (placeholder implementation)."""
    # Implement Slack webhook integration
    pass


def email_alert_callback(alert: Alert):
    """Send alert via email (placeholder implementation)."""
    # Implement email alert integration
    pass


def pagerduty_alert_callback(alert: Alert):
    """Send alert to PagerDuty (placeholder implementation)."""
    # Implement PagerDuty integration
    pass


# Setup function
def setup_monitoring():
    """Setup monitoring with configured alert channels."""
    # Register alert callbacks based on configuration
    if hasattr(settings, 'SLACK_WEBHOOK_URL') and settings.SLACK_WEBHOOK_URL:
        stability_monitor.register_alert_callback(slack_alert_callback)

    if hasattr(settings, 'ALERT_EMAIL') and settings.ALERT_EMAIL:
        stability_monitor.register_alert_callback(email_alert_callback)

    if hasattr(settings, 'PAGERDUTY_INTEGRATION_KEY') and settings.PAGERDUTY_INTEGRATION_KEY:
        stability_monitor.register_alert_callback(pagerduty_alert_callback)