"""
Production monitoring and alerting system
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import psutil
import aiohttp

from app.core.config import settings
from app.core.logging import logger
from app.core.redis import get_redis


class MetricType(str, Enum):
    """Types of metrics to track"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricsCollector:
    """
    Collects and aggregates application metrics
    """
    
    def __init__(self):
        self.redis = None
        self.metrics_buffer = {}
        self.flush_interval = 10  # seconds
        self._flush_task = None
    
    async def initialize(self):
        """Initialize metrics collector"""
        self.redis = await get_redis()
        self._flush_task = asyncio.create_task(self._periodic_flush())
    
    async def increment(
        self,
        metric_name: str,
        value: float = 1,
        tags: Optional[Dict[str, str]] = None
    ):
        """Increment a counter metric"""
        await self._record_metric(
            metric_name,
            MetricType.COUNTER,
            value,
            tags
        )
    
    async def gauge(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """Set a gauge metric"""
        await self._record_metric(
            metric_name,
            MetricType.GAUGE,
            value,
            tags
        )
    
    async def histogram(
        self,
        metric_name: str,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """Record a histogram metric"""
        await self._record_metric(
            metric_name,
            MetricType.HISTOGRAM,
            value,
            tags
        )
    
    async def timing(
        self,
        metric_name: str,
        duration_ms: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """Record a timing metric"""
        await self._record_metric(
            f"{metric_name}.duration",
            MetricType.HISTOGRAM,
            duration_ms,
            tags
        )
    
    async def _record_metric(
        self,
        name: str,
        metric_type: MetricType,
        value: float,
        tags: Optional[Dict[str, str]] = None
    ):
        """Record a metric to buffer"""
        
        key = f"{name}:{json.dumps(tags or {}, sort_keys=True)}"
        
        if key not in self.metrics_buffer:
            self.metrics_buffer[key] = {
                "name": name,
                "type": metric_type,
                "tags": tags or {},
                "values": [],
                "timestamp": time.time()
            }
        
        self.metrics_buffer[key]["values"].append(value)
        
        # Flush if buffer is too large
        if len(self.metrics_buffer) > 1000:
            await self._flush_metrics()
    
    async def _flush_metrics(self):
        """Flush metrics to Redis and monitoring service"""
        
        if not self.metrics_buffer:
            return
        
        metrics_to_flush = self.metrics_buffer.copy()
        self.metrics_buffer.clear()
        
        try:
            # Store in Redis for real-time dashboards
            for key, metric in metrics_to_flush.items():
                redis_key = f"metrics:{metric['name']}"
                
                # Aggregate values based on metric type
                if metric["type"] == MetricType.COUNTER:
                    total = sum(metric["values"])
                    await self.redis.hincrby(redis_key, "value", int(total))
                
                elif metric["type"] == MetricType.GAUGE:
                    latest = metric["values"][-1]
                    await self.redis.hset(redis_key, "value", latest)
                
                elif metric["type"] == MetricType.HISTOGRAM:
                    # Store histogram data
                    histogram_key = f"{redis_key}:histogram"
                    for value in metric["values"]:
                        await self.redis.zadd(
                            histogram_key,
                            {str(time.time()): value}
                        )
                    # Keep only last hour of data
                    cutoff = time.time() - 3600
                    await self.redis.zremrangebyscore(
                        histogram_key, 0, cutoff
                    )
                
                # Set expiry
                await self.redis.expire(redis_key, 86400)  # 24 hours
            
            # Send to external monitoring service if configured
            if settings.MONITORING_ENDPOINT:
                await self._send_to_monitoring_service(metrics_to_flush)
            
        except Exception as e:
            logger.error(f"Failed to flush metrics: {e}")
            # Re-add to buffer for retry
            self.metrics_buffer.update(metrics_to_flush)
    
    async def _send_to_monitoring_service(
        self,
        metrics: Dict[str, Any]
    ):
        """Send metrics to external monitoring service"""
        
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "environment": settings.ENVIRONMENT,
            "service": "plinto-api",
            "metrics": list(metrics.values())
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    settings.MONITORING_ENDPOINT,
                    json=payload,
                    headers={"Authorization": f"Bearer {settings.MONITORING_API_KEY}"},
                    timeout=5
                ) as response:
                    if response.status != 200:
                        logger.warning(
                            f"Failed to send metrics: {response.status}"
                        )
            except asyncio.TimeoutError:
                logger.warning("Timeout sending metrics to monitoring service")
    
    async def _periodic_flush(self):
        """Periodically flush metrics"""
        while True:
            await asyncio.sleep(self.flush_interval)
            await self._flush_metrics()


class HealthChecker:
    """
    System health checking and monitoring
    """
    
    def __init__(self, metrics: MetricsCollector):
        self.metrics = metrics
        self.checks = {}
        self.check_interval = 30  # seconds
        self._check_task = None
    
    async def initialize(self):
        """Initialize health checker"""
        self._check_task = asyncio.create_task(self._periodic_check())
    
    def register_check(
        self,
        name: str,
        check_func,
        critical: bool = False
    ):
        """Register a health check"""
        self.checks[name] = {
            "func": check_func,
            "critical": critical,
            "last_result": None,
            "last_check": None
        }
    
    async def check_health(self) -> Dict[str, Any]:
        """Run all health checks"""
        
        results = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        for name, check in self.checks.items():
            try:
                start_time = time.time()
                result = await check["func"]()
                duration = (time.time() - start_time) * 1000
                
                results["checks"][name] = {
                    "status": "healthy" if result else "unhealthy",
                    "duration_ms": duration,
                    "critical": check["critical"]
                }
                
                # Record metric
                await self.metrics.gauge(
                    f"health.{name}",
                    1 if result else 0,
                    {"critical": str(check["critical"])}
                )
                
                # Update overall status
                if not result and check["critical"]:
                    results["status"] = "unhealthy"
                
                # Update check info
                check["last_result"] = result
                check["last_check"] = time.time()
                
            except Exception as e:
                logger.error(f"Health check {name} failed: {e}")
                results["checks"][name] = {
                    "status": "error",
                    "error": str(e),
                    "critical": check["critical"]
                }
                
                if check["critical"]:
                    results["status"] = "unhealthy"
        
        return results
    
    async def _periodic_check(self):
        """Run health checks periodically"""
        while True:
            await asyncio.sleep(self.check_interval)
            await self.check_health()


class AlertManager:
    """
    Manages alerts and notifications
    """
    
    def __init__(self, metrics: MetricsCollector):
        self.metrics = metrics
        self.redis = None
        self.alert_rules = []
        self.alert_history = {}
        self.check_interval = 60  # seconds
        self._check_task = None
    
    async def initialize(self):
        """Initialize alert manager"""
        self.redis = await get_redis()
        self._load_alert_rules()
        self._check_task = asyncio.create_task(self._periodic_check())
    
    def _load_alert_rules(self):
        """Load alert rules"""
        self.alert_rules = [
            {
                "name": "high_error_rate",
                "metric": "api.errors",
                "condition": "rate > 10",
                "window": 300,  # 5 minutes
                "severity": AlertSeverity.ERROR,
                "message": "High error rate detected: {value} errors/min"
            },
            {
                "name": "high_response_time",
                "metric": "api.response_time",
                "condition": "p95 > 1000",
                "window": 300,
                "severity": AlertSeverity.WARNING,
                "message": "High response time: {value}ms (p95)"
            },
            {
                "name": "low_disk_space",
                "metric": "system.disk_free",
                "condition": "value < 1073741824",  # 1GB
                "window": 60,
                "severity": AlertSeverity.CRITICAL,
                "message": "Low disk space: {value} bytes remaining"
            },
            {
                "name": "high_memory_usage",
                "metric": "system.memory_percent",
                "condition": "value > 90",
                "window": 300,
                "severity": AlertSeverity.WARNING,
                "message": "High memory usage: {value}%"
            },
            {
                "name": "database_connection_failure",
                "metric": "database.connections",
                "condition": "value == 0",
                "window": 60,
                "severity": AlertSeverity.CRITICAL,
                "message": "Database connection failure"
            },
            {
                "name": "rate_limit_violations",
                "metric": "rate_limit.violations",
                "condition": "rate > 100",
                "window": 300,
                "severity": AlertSeverity.WARNING,
                "message": "High rate limit violations: {value}/min"
            }
        ]
    
    async def check_alerts(self):
        """Check all alert rules"""
        
        for rule in self.alert_rules:
            try:
                # Get metric value
                value = await self._get_metric_value(
                    rule["metric"],
                    rule["window"]
                )
                
                # Evaluate condition
                if self._evaluate_condition(rule["condition"], value):
                    await self._trigger_alert(rule, value)
                else:
                    await self._clear_alert(rule)
                    
            except Exception as e:
                logger.error(f"Failed to check alert {rule['name']}: {e}")
    
    async def _get_metric_value(
        self,
        metric_name: str,
        window: int
    ) -> float:
        """Get metric value from Redis"""
        
        redis_key = f"metrics:{metric_name}"
        
        # Get value based on metric type
        if "rate" in metric_name:
            # Calculate rate
            count = await self.redis.get(f"{redis_key}:count") or 0
            return float(count) / (window / 60)  # per minute
        
        elif "p95" in metric_name or "p99" in metric_name:
            # Get percentile from histogram
            histogram_key = f"{redis_key}:histogram"
            values = await self.redis.zrange(histogram_key, 0, -1)
            if values:
                percentile = 95 if "p95" in metric_name else 99
                index = int(len(values) * (percentile / 100))
                return float(values[index])
            return 0
        
        else:
            # Get gauge value
            value = await self.redis.hget(redis_key, "value")
            return float(value) if value else 0
    
    def _evaluate_condition(
        self,
        condition: str,
        value: float
    ) -> bool:
        """Evaluate alert condition"""
        
        # Simple evaluation (in production, use a proper expression evaluator)
        try:
            # Replace 'value' with actual value
            condition = condition.replace("value", str(value))
            condition = condition.replace("rate", str(value))
            condition = condition.replace("p95", str(value))
            condition = condition.replace("p99", str(value))
            
            # Evaluate
            return eval(condition)
        except:
            return False
    
    async def _trigger_alert(
        self,
        rule: Dict[str, Any],
        value: float
    ):
        """Trigger an alert"""
        
        alert_id = f"{rule['name']}:{int(time.time())}"
        
        # Check if already alerted recently
        if rule["name"] in self.alert_history:
            last_alert = self.alert_history[rule["name"]]
            if time.time() - last_alert < 300:  # 5 min cooldown
                return
        
        # Create alert
        alert = {
            "id": alert_id,
            "name": rule["name"],
            "severity": rule["severity"],
            "message": rule["message"].format(value=value),
            "value": value,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Store in Redis
        await self.redis.lpush("alerts:active", json.dumps(alert))
        await self.redis.ltrim("alerts:active", 0, 99)  # Keep last 100
        
        # Record metric
        await self.metrics.increment(
            "alerts.triggered",
            tags={"severity": rule["severity"], "rule": rule["name"]}
        )
        
        # Send notifications
        await self._send_notifications(alert)
        
        # Update history
        self.alert_history[rule["name"]] = time.time()
        
        logger.warning(f"Alert triggered: {alert['message']}")
    
    async def _clear_alert(self, rule: Dict[str, Any]):
        """Clear an alert if it was active"""
        
        # Remove from history after cooldown
        if rule["name"] in self.alert_history:
            if time.time() - self.alert_history[rule["name"]] > 600:
                del self.alert_history[rule["name"]]
    
    async def _send_notifications(self, alert: Dict[str, Any]):
        """Send alert notifications"""
        
        # Send to webhook if configured
        if settings.ALERT_WEBHOOK_URL:
            async with aiohttp.ClientSession() as session:
                try:
                    payload = {
                        "text": f"🚨 *{alert['severity'].upper()}*: {alert['message']}",
                        "alert": alert
                    }
                    
                    await session.post(
                        settings.ALERT_WEBHOOK_URL,
                        json=payload,
                        timeout=5
                    )
                except Exception as e:
                    logger.error(f"Failed to send alert notification: {e}")
        
        # Send email for critical alerts
        if alert["severity"] == AlertSeverity.CRITICAL:
            # TODO: Implement email notification
            pass
    
    async def _periodic_check(self):
        """Check alerts periodically"""
        while True:
            await asyncio.sleep(self.check_interval)
            await self.check_alerts()


class SystemMonitor:
    """
    Monitor system resources
    """
    
    def __init__(self, metrics: MetricsCollector):
        self.metrics = metrics
        self.collect_interval = 30  # seconds
        self._collect_task = None
    
    async def initialize(self):
        """Initialize system monitor"""
        self._collect_task = asyncio.create_task(self._periodic_collect())
    
    async def collect_system_metrics(self):
        """Collect system metrics"""
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            await self.metrics.gauge("system.cpu_percent", cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            await self.metrics.gauge("system.memory_percent", memory.percent)
            await self.metrics.gauge("system.memory_used", memory.used)
            await self.metrics.gauge("system.memory_available", memory.available)
            
            # Disk usage
            disk = psutil.disk_usage("/")
            await self.metrics.gauge("system.disk_percent", disk.percent)
            await self.metrics.gauge("system.disk_free", disk.free)
            
            # Network I/O
            net_io = psutil.net_io_counters()
            await self.metrics.gauge("system.network_bytes_sent", net_io.bytes_sent)
            await self.metrics.gauge("system.network_bytes_recv", net_io.bytes_recv)
            
            # Process info
            process = psutil.Process()
            await self.metrics.gauge("process.cpu_percent", process.cpu_percent())
            await self.metrics.gauge("process.memory_rss", process.memory_info().rss)
            await self.metrics.gauge("process.num_threads", process.num_threads())
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
    
    async def _periodic_collect(self):
        """Collect metrics periodically"""
        while True:
            await asyncio.sleep(self.collect_interval)
            await self.collect_system_metrics()