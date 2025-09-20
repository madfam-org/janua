import pytest
pytestmark = pytest.mark.asyncio


"""
Comprehensive unit tests for MonitoringService
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

from app.services.monitoring import (
    MonitoringService,
    MetricsCollector,
    MetricType,
    AlertSeverity
)


class TestMetricsCollector:
    """Test metrics collection functionality."""

    def test_metrics_collector_initialization(self):
        """Test metrics collector initializes correctly."""
        collector = MetricsCollector()
        assert collector._metrics == {}
        assert hasattr(collector, '_redis_client')

    def test_record_metric_counter(self):
        """Test recording counter metrics."""
        collector = MetricsCollector()

        collector.record_metric("api_calls", 1, MetricType.COUNTER)
        collector.record_metric("api_calls", 1, MetricType.COUNTER)

        assert "api_calls" in collector._metrics
        assert collector._metrics["api_calls"]["value"] == 2

    def test_record_metric_gauge(self):
        """Test recording gauge metrics."""
        collector = MetricsCollector()

        collector.record_metric("memory_usage", 75.5, MetricType.GAUGE)
        collector.record_metric("memory_usage", 80.0, MetricType.GAUGE)

        assert "memory_usage" in collector._metrics
        assert collector._metrics["memory_usage"]["value"] == 80.0

    def test_record_metric_histogram(self):
        """Test recording histogram metrics."""
        collector = MetricsCollector()

        collector.record_metric("response_time", 150, MetricType.HISTOGRAM)
        collector.record_metric("response_time", 200, MetricType.HISTOGRAM)

        assert "response_time" in collector._metrics
        metric = collector._metrics["response_time"]
        assert len(metric["samples"]) == 2
        assert 150 in metric["samples"]
        assert 200 in metric["samples"]

    def test_get_metric_existing(self):
        """Test getting existing metric."""
        collector = MetricsCollector()
        collector.record_metric("test_metric", 42, MetricType.GAUGE)

        metric = collector.get_metric("test_metric")
        assert metric is not None
        assert metric["value"] == 42

    def test_get_metric_nonexistent(self):
        """Test getting nonexistent metric returns None."""
        collector = MetricsCollector()

        metric = collector.get_metric("nonexistent")
        assert metric is None

    @pytest.mark.asyncio
    async def test_export_to_redis(self):
        """Test exporting metrics to Redis."""
        collector = MetricsCollector()
        collector._redis_client = AsyncMock()

        collector.record_metric("test_metric", 100, MetricType.COUNTER)

        await collector.export_to_redis()

        collector._redis_client.hset.assert_called_once()


class TestHealthChecker:
    """Test health checking functionality."""

    def test_health_checker_initialization(self):
        """Test health checker initializes correctly."""
        metrics = Mock()
        checker = HealthChecker(metrics)
        assert checker.metrics == metrics
        assert checker._checks == {}

    def test_add_health_check(self):
        """Test adding health check."""
        metrics = Mock()
        checker = HealthChecker(metrics)

        check_func = Mock()
        checker.add_health_check("database", check_func)

        assert "database" in checker._checks
        assert checker._checks["database"] == check_func

    @pytest.mark.asyncio
    async def test_check_health_all_healthy(self):
        """Test health check when all services are healthy."""
        metrics = Mock()
        checker = HealthChecker(metrics)

        db_check = AsyncMock(return_value=True)
        redis_check = AsyncMock(return_value=True)

        checker.add_health_check("database", db_check)
        checker.add_health_check("redis", redis_check)

        health = await checker.check_health()

        assert health.status == HealthStatus.HEALTHY
        assert health.details["database"] is True
        assert health.details["redis"] is True

    @pytest.mark.asyncio
    async def test_check_health_some_unhealthy(self):
        """Test health check when some services are unhealthy."""
        metrics = Mock()
        checker = HealthChecker(metrics)

        db_check = AsyncMock(return_value=True)
        redis_check = AsyncMock(return_value=False)

        checker.add_health_check("database", db_check)
        checker.add_health_check("redis", redis_check)

        health = await checker.check_health()

        assert health.status == HealthStatus.DEGRADED
        assert health.details["database"] is True
        assert health.details["redis"] is False

    @pytest.mark.asyncio
    async def test_check_health_exception_handling(self):
        """Test health check handles exceptions."""
        metrics = Mock()
        checker = HealthChecker(metrics)

        failing_check = AsyncMock(side_effect=Exception("Connection failed"))
        checker.add_health_check("external_api", failing_check)

        health = await checker.check_health()

        assert health.status == HealthStatus.UNHEALTHY
        assert "external_api" in health.details
        assert health.details["external_api"] is False


class TestAlertManager:
    """Test alert management functionality."""

    def test_alert_manager_initialization(self):
        """Test alert manager initializes correctly."""
        metrics = Mock()
        manager = AlertManager(metrics)
        assert manager.metrics == metrics
        assert manager._alert_rules == []

    def test_add_alert_rule(self):
        """Test adding alert rule."""
        metrics = Mock()
        manager = AlertManager(metrics)

        rule_func = Mock()
        manager.add_alert_rule("high_cpu", rule_func, AlertSeverity.WARNING)

        assert len(manager._alert_rules) == 1
        rule = manager._alert_rules[0]
        assert rule["name"] == "high_cpu"
        assert rule["check"] == rule_func
        assert rule["severity"] == AlertSeverity.WARNING

    @pytest.mark.asyncio
    async def test_check_alerts_no_triggers(self):
        """Test checking alerts when none trigger."""
        metrics = Mock()
        manager = AlertManager(metrics)

        rule_func = AsyncMock(return_value=False)
        manager.add_alert_rule("test_rule", rule_func, AlertSeverity.INFO)

        alerts = await manager.check_alerts()

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_check_alerts_with_triggers(self):
        """Test checking alerts when some trigger."""
        metrics = Mock()
        manager = AlertManager(metrics)

        rule_func1 = AsyncMock(return_value=True)
        rule_func2 = AsyncMock(return_value=False)

        manager.add_alert_rule("critical_rule", rule_func1, AlertSeverity.CRITICAL)
        manager.add_alert_rule("info_rule", rule_func2, AlertSeverity.INFO)

        alerts = await manager.check_alerts()

        assert len(alerts) == 1
        assert alerts[0]["name"] == "critical_rule"
        assert alerts[0]["severity"] == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_send_alert(self):
        """Test sending alert."""
        metrics = Mock()
        manager = AlertManager(metrics)

        with patch('app.services.monitoring.AlertManager._send_webhook') as mock_webhook:
            mock_webhook.return_value = AsyncMock()

            await manager.send_alert("test_alert", AlertSeverity.WARNING, {"key": "value"})

            mock_webhook.assert_called_once()


class TestSystemMonitor:
    """Test system monitoring functionality."""

    def test_system_monitor_initialization(self):
        """Test system monitor initializes correctly."""
        metrics = Mock()
        monitor = SystemMonitor(metrics)
        assert monitor.metrics == metrics

    @patch('psutil.cpu_percent')
    def test_collect_cpu_metrics(self, mock_cpu):
        """Test collecting CPU metrics."""
        metrics = Mock()
        monitor = SystemMonitor(metrics)
        mock_cpu.return_value = 75.5

        monitor.collect_cpu_metrics()

        mock_cpu.assert_called_once()
        metrics.record_metric.assert_called_with("system.cpu_percent", 75.5, MetricType.GAUGE)

    @patch('psutil.virtual_memory')
    def test_collect_memory_metrics(self, mock_memory):
        """Test collecting memory metrics."""
        metrics = Mock()
        monitor = SystemMonitor(metrics)

        mock_memory.return_value.percent = 60.0
        mock_memory.return_value.used = 1073741824  # 1GB
        mock_memory.return_value.available = 2147483648  # 2GB

        monitor.collect_memory_metrics()

        assert metrics.record_metric.call_count == 3

    @patch('psutil.disk_usage')
    def test_collect_disk_metrics(self, mock_disk):
        """Test collecting disk metrics."""
        metrics = Mock()
        monitor = SystemMonitor(metrics)

        mock_disk.return_value.percent = 45.0
        mock_disk.return_value.used = 1073741824
        mock_disk.return_value.free = 2147483648

        monitor.collect_disk_metrics()

        assert metrics.record_metric.call_count == 3

    @pytest.mark.asyncio
    async def test_collect_all_metrics(self):
        """Test collecting all system metrics."""
        metrics = Mock()
        monitor = SystemMonitor(metrics)

        with patch.object(monitor, 'collect_cpu_metrics') as mock_cpu, \
             patch.object(monitor, 'collect_memory_metrics') as mock_memory, \
             patch.object(monitor, 'collect_disk_metrics') as mock_disk:

            await monitor.collect_all_metrics()

            mock_cpu.assert_called_once()
            mock_memory.assert_called_once()
            mock_disk.assert_called_once()


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

        with patch.object(service.metrics, 'initialize') as mock_metrics_init, \
             patch.object(service.health_checker, 'add_health_check') as mock_add_check:

            await service.initialize()

            mock_metrics_init.assert_called_once()
            assert mock_add_check.call_count >= 2  # At least database and redis checks
            assert service.initialized is True

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test service shutdown."""
        service = MonitoringService()
        service.initialized = True

        await service.shutdown()

        assert service.initialized is False

    @pytest.mark.asyncio
    async def test_record_request_metric(self):
        """Test recording request metrics."""
        service = MonitoringService()

        with patch.object(service.metrics, 'record_metric') as mock_record:
            await service.record_request_metric("/api/users", "GET", 200, 150.5)

            assert mock_record.call_count >= 2  # Request count and duration

    @pytest.mark.asyncio
    async def test_record_error_metric(self):
        """Test recording error metrics."""
        service = MonitoringService()

        with patch.object(service.metrics, 'record_metric') as mock_record:
            await service.record_error_metric("ValidationError", "/api/users", 400)

            mock_record.assert_called()

    @pytest.mark.asyncio
    async def test_record_business_metric(self):
        """Test recording business metrics."""
        service = MonitoringService()

        with patch.object(service.metrics, 'record_metric') as mock_record:
            await service.record_business_metric("user_signup", 1, {"source": "web"})

            mock_record.assert_called()

    @pytest.mark.asyncio
    async def test_get_health_status(self):
        """Test getting health status."""
        service = MonitoringService()

        with patch.object(service.health_checker, 'check_health') as mock_check:
            mock_check.return_value = Mock(status=HealthStatus.HEALTHY)

            health = await service.get_health_status()

            mock_check.assert_called_once()
            assert health.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_get_metrics_summary(self):
        """Test getting metrics summary."""
        service = MonitoringService()

        with patch.object(service.metrics, 'get_all_metrics') as mock_get:
            mock_get.return_value = {"api_calls": {"value": 100}}

            summary = await service.get_metrics_summary()

            mock_get.assert_called_once()
            assert "api_calls" in summary

    @pytest.mark.asyncio
    async def test_check_alerts(self):
        """Test checking alerts."""
        service = MonitoringService()

        with patch.object(service.alerting, 'check_alerts') as mock_check:
            mock_check.return_value = []

            alerts = await service.check_alerts()

            mock_check.assert_called_once()
            assert isinstance(alerts, list)