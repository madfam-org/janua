import pytest

pytestmark = pytest.mark.asyncio


"""
Working unit tests for MonitoringService - matches actual implementation
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import time

from app.services.monitoring import (
    MonitoringService,
    MetricsCollector,
    HealthChecker,
    AlertManager,
    SystemMonitor,
    MetricType,
    AlertSeverity,
)


class TestMetricsCollector:
    """Test metrics collection functionality."""

    def test_metrics_collector_initialization(self):
        """Test metrics collector initializes correctly."""
        collector = MetricsCollector()
        assert collector.redis is None
        assert collector.metrics_buffer == {}
        assert collector.flush_interval == 10
        assert collector._flush_task is None

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test metrics collector initialization."""
        collector = MetricsCollector()

        with patch("app.services.monitoring.get_redis") as mock_get_redis, patch(
            "asyncio.create_task"
        ) as mock_create_task:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_task = AsyncMock()
            mock_create_task.return_value = mock_task

            await collector.initialize()

            assert collector.redis == mock_redis
            assert collector._flush_task == mock_task
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_increment_metric(self):
        """Test increment counter metric."""
        collector = MetricsCollector()

        with patch.object(collector, "_record_metric") as mock_record:
            await collector.increment("api_calls", 1, {"endpoint": "/users"})

            mock_record.assert_called_once_with(
                "api_calls", MetricType.COUNTER, 1, {"endpoint": "/users"}
            )

    @pytest.mark.asyncio
    async def test_gauge_metric(self):
        """Test gauge metric."""
        collector = MetricsCollector()

        with patch.object(collector, "_record_metric") as mock_record:
            await collector.gauge("cpu_usage", 75.5, {"host": "server1"})

            mock_record.assert_called_once_with(
                "cpu_usage", MetricType.GAUGE, 75.5, {"host": "server1"}
            )

    @pytest.mark.asyncio
    async def test_histogram_metric(self):
        """Test histogram metric."""
        collector = MetricsCollector()

        with patch.object(collector, "_record_metric") as mock_record:
            await collector.histogram("response_time", 150.0)

            mock_record.assert_called_once_with("response_time", MetricType.HISTOGRAM, 150.0, None)

    @pytest.mark.asyncio
    async def test_timing_metric(self):
        """Test timing metric."""
        collector = MetricsCollector()

        with patch.object(collector, "_record_metric") as mock_record:
            await collector.timing("api_request", 250.5)

            mock_record.assert_called_once_with(
                "api_request.duration", MetricType.HISTOGRAM, 250.5, None
            )

    @pytest.mark.asyncio
    async def test_record_metric_buffer(self):
        """Test metric recording to buffer."""
        collector = MetricsCollector()

        await collector._record_metric("test_metric", MetricType.COUNTER, 1.0, {"tag": "value"})

        assert len(collector.metrics_buffer) == 1
        key = list(collector.metrics_buffer.keys())[0]
        metric = collector.metrics_buffer[key]

        assert metric["name"] == "test_metric"
        assert metric["type"] == MetricType.COUNTER
        assert metric["tags"] == {"tag": "value"}
        assert metric["values"] == [1.0]
        assert "timestamp" in metric

    @pytest.mark.asyncio
    async def test_flush_metrics_redis(self):
        """Test flushing metrics to Redis."""
        collector = MetricsCollector()
        collector.redis = AsyncMock()

        # Add test metric to buffer
        collector.metrics_buffer["test:{}"] = {
            "name": "test_metric",
            "type": MetricType.COUNTER,
            "tags": {},
            "values": [1.0, 2.0],
            "timestamp": time.time(),
        }

        with patch.object(collector, "_send_to_monitoring_service") as mock_send:
            await collector._flush_metrics()

            # Verify Redis operations
            collector.redis.hincrby.assert_called_once_with("metrics:test_metric", "value", 3)
            collector.redis.expire.assert_called_once_with("metrics:test_metric", 86400)

            # Buffer should be cleared
            assert collector.metrics_buffer == {}


class TestHealthChecker:
    """Test health checking functionality."""

    def test_health_checker_initialization(self):
        """Test health checker initializes correctly."""
        metrics = Mock()
        checker = HealthChecker(metrics)

        assert checker.metrics == metrics
        assert checker.checks == {}
        assert checker.check_interval == 30
        assert checker._check_task is None

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test health checker initialization."""
        metrics = Mock()
        checker = HealthChecker(metrics)

        with patch("asyncio.create_task") as mock_create_task:
            mock_task = AsyncMock()
            mock_create_task.return_value = mock_task

            await checker.initialize()

            assert checker._check_task == mock_task
            mock_create_task.assert_called_once()

    def test_register_check(self):
        """Test registering health check."""
        metrics = Mock()
        checker = HealthChecker(metrics)

        check_func = AsyncMock()
        checker.register_check("database", check_func, critical=True)

        assert "database" in checker.checks
        assert checker.checks["database"]["func"] == check_func
        assert checker.checks["database"]["critical"] is True

    @pytest.mark.asyncio
    async def test_check_health_success(self):
        """Test successful health check."""
        metrics = AsyncMock()
        checker = HealthChecker(metrics)

        # Register test check
        check_func = AsyncMock(return_value=True)
        checker.register_check("test_service", check_func, critical=True)

        result = await checker.check_health()

        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert result["checks"]["test_service"]["status"] == "healthy"
        assert "duration_ms" in result["checks"]["test_service"]

    @pytest.mark.asyncio
    async def test_check_health_failure(self):
        """Test health check failure."""
        metrics = AsyncMock()
        checker = HealthChecker(metrics)

        # Register failing check
        check_func = AsyncMock(return_value=False)
        checker.register_check("test_service", check_func, critical=True)

        result = await checker.check_health()

        assert result["status"] == "unhealthy"
        assert result["checks"]["test_service"]["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_check_health_exception(self):
        """Test health check with exception."""
        metrics = AsyncMock()
        checker = HealthChecker(metrics)

        # Register check that raises exception
        check_func = AsyncMock(side_effect=Exception("Connection failed"))
        checker.register_check("test_service", check_func, critical=True)

        result = await checker.check_health()

        assert result["status"] == "unhealthy"
        assert result["checks"]["test_service"]["status"] == "error"
        assert "Connection failed" in result["checks"]["test_service"]["error"]


class TestAlertManager:
    """Test alert management functionality."""

    def test_alert_manager_initialization(self):
        """Test alert manager initializes correctly."""
        metrics = Mock()
        manager = AlertManager(metrics)

        assert manager.metrics == metrics
        assert manager.redis is None
        assert manager.alert_rules == []
        assert manager.alert_history == {}
        assert manager.check_interval == 60

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test alert manager initialization."""
        metrics = Mock()
        manager = AlertManager(metrics)

        with patch("app.services.monitoring.get_redis") as mock_get_redis, patch(
            "asyncio.create_task"
        ) as mock_create_task:
            mock_redis = AsyncMock()
            mock_get_redis.return_value = mock_redis
            mock_task = AsyncMock()
            mock_create_task.return_value = mock_task

            await manager.initialize()

            assert manager.redis == mock_redis
            assert manager._check_task == mock_task
            assert len(manager.alert_rules) > 0  # Rules loaded

    def test_evaluate_condition(self):
        """Test condition evaluation."""
        metrics = Mock()
        manager = AlertManager(metrics)

        # Test simple conditions
        assert manager._evaluate_condition("value > 10", 15) is True
        assert manager._evaluate_condition("value > 10", 5) is False
        assert manager._evaluate_condition("rate > 100", 150) is True

    @pytest.mark.asyncio
    async def test_get_metric_value_gauge(self):
        """Test getting gauge metric value."""
        metrics = Mock()
        manager = AlertManager(metrics)
        manager.redis = AsyncMock()

        manager.redis.hget.return_value = "75.5"

        value = await manager._get_metric_value("system.cpu_percent", 300)

        assert value == 75.5
        manager.redis.hget.assert_called_once_with("metrics:system.cpu_percent", "value")

    @pytest.mark.asyncio
    async def test_trigger_alert(self):
        """Test triggering an alert."""
        metrics = AsyncMock()
        manager = AlertManager(metrics)
        manager.redis = AsyncMock()

        rule = {
            "name": "test_alert",
            "severity": AlertSeverity.WARNING,
            "message": "Test alert: {value}",
        }

        with patch.object(manager, "_send_notifications") as mock_send:
            await manager._trigger_alert(rule, 42.0)

            # Verify alert stored in Redis
            manager.redis.lpush.assert_called_once()
            manager.redis.ltrim.assert_called_once_with("alerts:active", 0, 99)

            # Verify notification sent
            mock_send.assert_called_once()

            # Verify history updated
            assert "test_alert" in manager.alert_history


class TestSystemMonitor:
    """Test system monitoring functionality."""

    def test_system_monitor_initialization(self):
        """Test system monitor initializes correctly."""
        metrics = Mock()
        monitor = SystemMonitor(metrics)

        assert monitor.metrics == metrics
        assert monitor.collect_interval == 30
        assert monitor._collect_task is None

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test system monitor initialization."""
        metrics = Mock()
        monitor = SystemMonitor(metrics)

        with patch("asyncio.create_task") as mock_create_task:
            mock_task = AsyncMock()
            mock_create_task.return_value = mock_task

            await monitor.initialize()

            assert monitor._collect_task == mock_task
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_system_metrics(self):
        """Test collecting system metrics."""
        metrics = AsyncMock()
        monitor = SystemMonitor(metrics)

        with patch("psutil.cpu_percent") as mock_cpu, patch(
            "psutil.virtual_memory"
        ) as mock_memory, patch("psutil.disk_usage") as mock_disk, patch(
            "psutil.net_io_counters"
        ) as mock_net, patch(
            "psutil.Process"
        ) as mock_process:
            # Mock system values
            mock_cpu.return_value = 75.0
            mock_memory.return_value.percent = 60.0
            mock_memory.return_value.used = 1000000
            mock_memory.return_value.available = 2000000
            mock_disk.return_value.percent = 45.0
            mock_disk.return_value.free = 5000000000
            mock_net.return_value.bytes_sent = 1000
            mock_net.return_value.bytes_recv = 2000

            # Mock process
            mock_process_instance = AsyncMock()
            mock_process.return_value = mock_process_instance
            mock_process_instance.cpu_percent.return_value = 25.0
            mock_process_instance.memory_info.return_value.rss = 50000000
            mock_process_instance.num_threads.return_value = 10

            await monitor.collect_system_metrics()

            # Verify metrics were recorded
            assert metrics.gauge.call_count >= 8  # Multiple system metrics


class TestMonitoringService:
    """Test main monitoring service."""

    def test_monitoring_service_initialization(self):
        """Test monitoring service initializes correctly."""
        service = MonitoringService()

        assert isinstance(service.metrics, MetricsCollector)
        assert isinstance(service.health_checker, HealthChecker)
        assert isinstance(service.alerting, AlertManager)
        assert isinstance(service.system_monitor, SystemMonitor)
        assert service.initialized is False

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test service initialization."""
        service = MonitoringService()

        with patch.object(service.metrics, "initialize") as mock_metrics, patch.object(
            service.health_checker, "initialize"
        ) as mock_health, patch.object(service.alerting, "initialize") as mock_alerts, patch.object(
            service.system_monitor, "initialize"
        ) as mock_system:
            await service.initialize()

            mock_metrics.assert_called_once()
            mock_health.assert_called_once()
            mock_alerts.assert_called_once()
            mock_system.assert_called_once()
            assert service.initialized is True

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test service shutdown."""
        service = MonitoringService()
        service.initialized = True

        # Mock shutdown methods
        service.metrics.shutdown = AsyncMock()
        service.health_checker.shutdown = AsyncMock()
        service.alerting.shutdown = AsyncMock()
        service.system_monitor.shutdown = AsyncMock()

        await service.shutdown()

        service.system_monitor.shutdown.assert_called_once()
        service.alerting.shutdown.assert_called_once()
        service.health_checker.shutdown.assert_called_once()
        service.metrics.shutdown.assert_called_once()
        assert service.initialized is False

    @pytest.mark.asyncio
    async def test_record_metric_counter(self):
        """Test recording counter metric."""
        service = MonitoringService()
        service.metrics.counter = AsyncMock()

        await service.record_metric("api_calls", 1, MetricType.COUNTER, {"endpoint": "/users"})

        service.metrics.counter.assert_called_once_with("api_calls", 1, {"endpoint": "/users"})

    @pytest.mark.asyncio
    async def test_record_metric_gauge(self):
        """Test recording gauge metric."""
        service = MonitoringService()
        service.metrics.gauge = AsyncMock()

        await service.record_metric("cpu_usage", 75.5, MetricType.GAUGE)

        service.metrics.gauge.assert_called_once_with("cpu_usage", 75.5, None)

    @pytest.mark.asyncio
    async def test_get_health_status(self):
        """Test getting health status."""
        service = MonitoringService()
        service.health_checker.get_status = AsyncMock(return_value={"status": "healthy"})

        status = await service.get_health_status()

        assert status == {"status": "healthy"}
        service.health_checker.get_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_alert(self):
        """Test triggering alert."""
        service = MonitoringService()
        service.alerting.send_alert = AsyncMock()

        await service.trigger_alert(
            "Test Alert", "Test message", AlertSeverity.ERROR, {"key": "value"}
        )

        service.alerting.send_alert.assert_called_once_with(
            "Test Alert", "Test message", AlertSeverity.ERROR, {"key": "value"}
        )


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_metrics_flush_error_handling(self):
        """Test handling metric flush errors gracefully."""
        collector = MetricsCollector()
        collector.redis = AsyncMock()
        collector.redis.hincrby.side_effect = Exception("Redis error")

        # Add metric to buffer
        collector.metrics_buffer["test:{}"] = {
            "name": "test_metric",
            "type": MetricType.COUNTER,
            "tags": {},
            "values": [1.0],
            "timestamp": time.time(),
        }

        # Should not raise exception
        await collector._flush_metrics()

        # Metrics should be back in buffer for retry
        assert len(collector.metrics_buffer) > 0

    @pytest.mark.asyncio
    async def test_system_metrics_collection_error(self):
        """Test handling system metrics collection errors."""
        metrics = AsyncMock()
        monitor = SystemMonitor(metrics)

        with patch("psutil.cpu_percent", side_effect=Exception("System error")):
            # Should not raise exception
            await monitor.collect_system_metrics()

    @pytest.mark.asyncio
    async def test_alert_check_error_handling(self):
        """Test handling alert check errors."""
        metrics = Mock()
        manager = AlertManager(metrics)
        manager.redis = AsyncMock()

        # Mock failing metric retrieval
        manager._get_metric_value = AsyncMock(side_effect=Exception("Metric error"))

        # Should not raise exception
        await manager.check_alerts()
