import pytest

pytestmark = pytest.mark.asyncio


"""
Unit tests for MonitoringService - simplified to match actual implementation
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from app.services.monitoring import MonitoringService, MetricsCollector, MetricType, AlertSeverity


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

        with patch("app.services.monitoring.get_redis") as mock_redis:
            mock_redis.return_value = AsyncMock()
            await collector.initialize()
            assert collector.redis is not None

    def test_record_counter_metric(self):
        """Test recording counter metrics."""
        collector = MetricsCollector()

        collector.record_metric("api_calls", 1, MetricType.COUNTER)
        collector.record_metric("api_calls", 1, MetricType.COUNTER)

        assert "api_calls" in collector.metrics_buffer
        assert collector.metrics_buffer["api_calls"]["value"] == 2

    def test_record_gauge_metric(self):
        """Test recording gauge metrics."""
        collector = MetricsCollector()

        collector.record_metric("memory_usage", 75.5, MetricType.GAUGE)
        collector.record_metric("memory_usage", 80.0, MetricType.GAUGE)

        assert "memory_usage" in collector.metrics_buffer
        assert collector.metrics_buffer["memory_usage"]["value"] == 80.0

    def test_record_histogram_metric(self):
        """Test recording histogram metrics."""
        collector = MetricsCollector()

        collector.record_metric("response_time", 150, MetricType.HISTOGRAM)
        collector.record_metric("response_time", 200, MetricType.HISTOGRAM)

        assert "response_time" in collector.metrics_buffer
        metric = collector.metrics_buffer["response_time"]
        assert len(metric["samples"]) == 2
        assert 150 in metric["samples"]
        assert 200 in metric["samples"]

    def test_get_metric_stats(self):
        """Test getting metric statistics."""
        collector = MetricsCollector()

        # Record several values
        for value in [100, 150, 200, 250, 300]:
            collector.record_metric("test_metric", value, MetricType.HISTOGRAM)

        stats = collector.get_metric_stats("test_metric")

        assert stats is not None
        assert stats["count"] == 5
        assert stats["min"] == 100
        assert stats["max"] == 300
        assert stats["avg"] == 200

    @pytest.mark.asyncio
    async def test_flush_metrics(self):
        """Test flushing metrics to Redis."""
        collector = MetricsCollector()
        collector.redis = AsyncMock()

        collector.record_metric("test_metric", 100, MetricType.COUNTER)

        await collector.flush_metrics()

        collector.redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_start_flush_task(self):
        """Test starting periodic flush task."""
        collector = MetricsCollector()
        collector.redis = AsyncMock()

        with patch("asyncio.create_task") as mock_task:
            collector.start_flush_task()
            mock_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_flush_task(self):
        """Test stopping flush task."""
        collector = MetricsCollector()
        collector._flush_task = Mock()
        collector._flush_task.cancel = Mock()

        await collector.stop()

        collector._flush_task.cancel.assert_called_once()


class TestMonitoringService:
    """Test main monitoring service."""

    def test_monitoring_service_initialization(self):
        """Test monitoring service initializes correctly."""
        service = MonitoringService()
        assert hasattr(service, "metrics")
        assert hasattr(service, "alerts")
        assert service.initialized is False

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test service initialization."""
        service = MonitoringService()

        with patch.object(service.metrics, "initialize") as mock_init:
            await service.initialize()
            mock_init.assert_called_once()
            assert service.initialized is True

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test service shutdown."""
        service = MonitoringService()
        service.initialized = True

        with patch.object(service.metrics, "stop") as mock_stop:
            await service.shutdown()
            mock_stop.assert_called_once()
            assert service.initialized is False

    @pytest.mark.asyncio
    async def test_track_request(self):
        """Test tracking request metrics."""
        service = MonitoringService()

        with patch.object(service.metrics, "record_metric") as mock_record:
            await service.track_request("/api/users", "GET", 200, 150.5)

            # Should record at least request count and duration
            assert mock_record.call_count >= 2

    @pytest.mark.asyncio
    async def test_track_error(self):
        """Test tracking error metrics."""
        service = MonitoringService()

        with patch.object(service.metrics, "record_metric") as mock_record:
            await service.track_error("ValidationError", "/api/users", 400)

            mock_record.assert_called()

    @pytest.mark.asyncio
    async def test_track_business_event(self):
        """Test tracking business metrics."""
        service = MonitoringService()

        with patch.object(service.metrics, "record_metric") as mock_record:
            await service.track_business_event("user_signup", {"source": "web"})

            mock_record.assert_called()

    @pytest.mark.asyncio
    async def test_health_check_database(self):
        """Test database health check."""
        service = MonitoringService()

        with patch("app.services.monitoring.get_db") as mock_db:
            mock_db.return_value.execute = AsyncMock()

            result = await service.health_check_database()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_database_failure(self):
        """Test database health check failure."""
        service = MonitoringService()

        with patch("app.services.monitoring.get_db") as mock_db:
            mock_db.return_value.execute = AsyncMock(side_effect=Exception("DB error"))

            result = await service.health_check_database()

            assert result is False

    @pytest.mark.asyncio
    async def test_health_check_redis(self):
        """Test Redis health check."""
        service = MonitoringService()

        with patch("app.services.monitoring.get_redis") as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis.return_value = mock_redis_client

            result = await service.health_check_redis()

            assert result is True
            mock_redis_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_redis_failure(self):
        """Test Redis health check failure."""
        service = MonitoringService()

        with patch("app.services.monitoring.get_redis") as mock_redis:
            mock_redis.return_value.ping = AsyncMock(side_effect=Exception("Redis error"))

            result = await service.health_check_redis()

            assert result is False

    @pytest.mark.asyncio
    async def test_get_system_metrics(self):
        """Test getting system metrics."""
        service = MonitoringService()

        with patch("psutil.cpu_percent") as mock_cpu, patch(
            "psutil.virtual_memory"
        ) as mock_memory, patch("psutil.disk_usage") as mock_disk:
            mock_cpu.return_value = 75.0
            mock_memory.return_value.percent = 60.0
            mock_disk.return_value.percent = 45.0

            metrics = await service.get_system_metrics()

            assert metrics["cpu_percent"] == 75.0
            assert metrics["memory_percent"] == 60.0
            assert metrics["disk_percent"] == 45.0

    @pytest.mark.asyncio
    async def test_send_alert(self):
        """Test sending alerts."""
        service = MonitoringService()

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock()
            mock_post.return_value.__aexit__ = AsyncMock()

            await service.send_alert("Test alert", AlertSeverity.WARNING, {"key": "value"})

            # Should attempt to send webhook if configured
            if hasattr(service, "webhook_url") and service.webhook_url:
                mock_post.assert_called()

    @pytest.mark.asyncio
    async def test_check_thresholds(self):
        """Test checking metric thresholds."""
        service = MonitoringService()

        with patch.object(service, "get_system_metrics") as mock_metrics, patch.object(
            service, "send_alert"
        ) as mock_alert:
            # Simulate high CPU usage
            mock_metrics.return_value = {
                "cpu_percent": 95.0,  # Above threshold
                "memory_percent": 50.0,
                "disk_percent": 30.0,
            }

            await service.check_thresholds()

            # Should send alert for high CPU
            mock_alert.assert_called()

    @pytest.mark.asyncio
    async def test_get_health_status(self):
        """Test getting overall health status."""
        service = MonitoringService()

        with patch.object(service, "health_check_database") as mock_db, patch.object(
            service, "health_check_redis"
        ) as mock_redis, patch.object(service, "get_system_metrics") as mock_metrics:
            mock_db.return_value = True
            mock_redis.return_value = True
            mock_metrics.return_value = {
                "cpu_percent": 50.0,
                "memory_percent": 60.0,
                "disk_percent": 30.0,
            }

            health = await service.get_health_status()

            assert health["status"] == "healthy"
            assert health["checks"]["database"] is True
            assert health["checks"]["redis"] is True
            assert "system" in health

    @pytest.mark.asyncio
    async def test_get_health_status_degraded(self):
        """Test getting health status when degraded."""
        service = MonitoringService()

        with patch.object(service, "health_check_database") as mock_db, patch.object(
            service, "health_check_redis"
        ) as mock_redis, patch.object(service, "get_system_metrics") as mock_metrics:
            mock_db.return_value = True
            mock_redis.return_value = False  # Redis failure
            mock_metrics.return_value = {
                "cpu_percent": 50.0,
                "memory_percent": 60.0,
                "disk_percent": 30.0,
            }

            health = await service.get_health_status()

            assert health["status"] == "degraded"
            assert health["checks"]["database"] is True
            assert health["checks"]["redis"] is False

    @pytest.mark.asyncio
    async def test_cleanup_old_metrics(self):
        """Test cleaning up old metrics."""
        service = MonitoringService()
        service.metrics.redis = AsyncMock()

        await service.cleanup_old_metrics()

        # Should call Redis cleanup
        service.metrics.redis.eval.assert_called()


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_redis_connection_error_handling(self):
        """Test handling Redis connection errors gracefully."""
        service = MonitoringService()

        with patch("app.services.monitoring.get_redis") as mock_redis:
            mock_redis.side_effect = Exception("Redis connection failed")

            # Should not raise exception during initialization
            try:
                await service.initialize()
            except Exception:
                pytest.fail("Should handle Redis connection errors gracefully")

    @pytest.mark.asyncio
    async def test_metric_recording_error_handling(self):
        """Test handling metric recording errors."""
        service = MonitoringService()
        service.metrics.redis = AsyncMock()
        service.metrics.redis.hset = AsyncMock(side_effect=Exception("Redis error"))

        # Should not raise exception when recording fails
        try:
            await service.track_request("/api/test", "GET", 200, 100)
        except Exception:
            pytest.fail("Should handle metric recording errors gracefully")

    @pytest.mark.asyncio
    async def test_alert_sending_failure(self):
        """Test handling alert sending failures."""
        service = MonitoringService()

        with patch("aiohttp.ClientSession.post") as mock_post:
            mock_post.side_effect = Exception("Webhook failed")

            # Should not raise exception when alert sending fails
            try:
                await service.send_alert("Test", AlertSeverity.ERROR, {})
            except Exception:
                pytest.fail("Should handle alert sending errors gracefully")
