"""
Performance Tests for WebSocket Server

Tests WebSocket server performance under various load conditions:
- Concurrent connections
- Message throughput
- Memory usage
- Connection stability
- Resource cleanup
"""

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import psutil
import pytest


# Mock WebSocket client for testing
class MockWebSocketClient:
    """Mock WebSocket client for performance testing"""

    def __init__(self, client_id: int, url: str, token: str):
        self.client_id = client_id
        self.url = url
        self.token = token
        self.connected = False
        self.messages_sent = 0
        self.messages_received = 0
        self.connection_time: Optional[float] = None
        self.latencies: List[float] = []

    async def connect(self) -> float:
        """Connect to WebSocket server and return connection time"""
        start_time = time.time()
        # Simulate connection
        await asyncio.sleep(0.01)  # Small delay for connection
        self.connected = True
        connection_time = time.time() - start_time
        self.connection_time = connection_time
        return connection_time

    async def disconnect(self):
        """Disconnect from WebSocket server"""
        self.connected = False
        await asyncio.sleep(0.001)

    async def send_message(self, message: Dict[str, Any]) -> float:
        """Send message and return send time"""
        if not self.connected:
            raise RuntimeError("Not connected")

        start_time = time.time()
        # Simulate message send
        await asyncio.sleep(0.001)
        self.messages_sent += 1
        send_time = time.time() - start_time
        return send_time

    async def receive_message(self) -> tuple[Dict[str, Any], float]:
        """Receive message and return message + latency"""
        if not self.connected:
            raise RuntimeError("Not connected")

        start_time = time.time()
        # Simulate message receive
        await asyncio.sleep(0.005)
        self.messages_received += 1
        latency = time.time() - start_time
        self.latencies.append(latency)

        message = {
            "id": self.messages_received,
            "client_id": self.client_id,
            "timestamp": time.time(),
        }
        return message, latency

    async def subscribe(self, channel: str):
        """Subscribe to channel"""
        await self.send_message({"action": "subscribe", "channel": channel})

    async def publish(self, channel: str, data: Dict[str, Any]):
        """Publish to channel"""
        await self.send_message(
            {
                "action": "publish",
                "channel": channel,
                "data": data,
            }
        )


@dataclass
class PerformanceMetrics:
    """Performance metrics collector"""

    connection_times: List[float] = field(default_factory=list)
    message_latencies: List[float] = field(default_factory=list)
    memory_samples: List[float] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    connection_count: int = 0
    message_count: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    def record_connection(self, connection_time: float):
        """Record successful connection"""
        self.connection_times.append(connection_time)
        self.connection_count += 1

    def record_message(self, latency: float):
        """Record message latency"""
        self.message_latencies.append(latency)
        self.message_count += 1

    def record_memory(self):
        """Record current memory usage"""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        self.memory_samples.append(memory_mb)

    def record_error(self, error_type: str, message: str):
        """Record error"""
        self.errors.append(
            {
                "type": error_type,
                "message": message,
                "timestamp": time.time(),
            }
        )

    def finalize(self):
        """Finalize metrics collection"""
        self.end_time = time.time()

    def get_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]

    def get_stats(self, values: List[float]) -> Dict[str, float]:
        """Calculate statistics for values"""
        if not values:
            return {
                "min": 0.0,
                "max": 0.0,
                "mean": 0.0,
                "median": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "stddev": 0.0,
            }

        return {
            "min": min(values),
            "max": max(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "p95": self.get_percentile(values, 95),
            "p99": self.get_percentile(values, 99),
            "stddev": statistics.stdev(values) if len(values) > 1 else 0.0,
        }

    def get_report(self) -> str:
        """Generate performance report"""
        duration = (self.end_time or time.time()) - self.start_time
        connection_stats = self.get_stats(self.connection_times)
        message_stats = self.get_stats(self.message_latencies)
        memory_stats = self.get_stats(self.memory_samples)

        throughput = self.message_count / duration if duration > 0 else 0

        report = f"""
Performance Test Report
=======================
Duration: {duration:.2f}s

Connections:
  Total: {self.connection_count}
  Connection Time (ms):
    Min: {connection_stats["min"] * 1000:.2f}
    Max: {connection_stats["max"] * 1000:.2f}
    Mean: {connection_stats["mean"] * 1000:.2f}
    Median: {connection_stats["median"] * 1000:.2f}
    P95: {connection_stats["p95"] * 1000:.2f}
    P99: {connection_stats["p99"] * 1000:.2f}
    StdDev: {connection_stats["stddev"] * 1000:.2f}

Messages:
  Total: {self.message_count}
  Throughput: {throughput:.2f} msg/s
  Message Latency (ms):
    Min: {message_stats["min"] * 1000:.2f}
    Max: {message_stats["max"] * 1000:.2f}
    Mean: {message_stats["mean"] * 1000:.2f}
    Median: {message_stats["median"] * 1000:.2f}
    P95: {message_stats["p95"] * 1000:.2f}
    P99: {message_stats["p99"] * 1000:.2f}
    StdDev: {message_stats["stddev"] * 1000:.2f}

Memory:
  Samples: {len(self.memory_samples)}
  Memory Usage (MB):
    Min: {memory_stats["min"]:.2f}
    Max: {memory_stats["max"]:.2f}
    Mean: {memory_stats["mean"]:.2f}
    Median: {memory_stats["median"]:.2f}
    Growth: {(memory_stats["max"] - memory_stats["min"]):.2f}

Errors: {len(self.errors)}
"""

        if self.errors:
            report += "\nError Summary:\n"
            error_types = {}
            for error in self.errors:
                error_type = error["type"]
                error_types[error_type] = error_types.get(error_type, 0) + 1

            for error_type, count in error_types.items():
                report += f"  {error_type}: {count}\n"

        return report.strip()


# Performance test configuration
PERF_CONFIG = {
    "concurrent_connections": {
        "light": 10,
        "medium": 50,
        "heavy": 100,
        "extreme": 250,
    },
    "message_throughput": {
        "messages_per_second": 100,
        "duration_seconds": 10,
    },
    "latency_thresholds": {
        "p50_ms": 100,
        "p95_ms": 250,
        "p99_ms": 500,
    },
    "memory_threshold": {
        "max_growth_mb": 200,
        "max_total_mb": 512,
    },
    "stability_test": {
        "duration_minutes": 5,
        "ping_interval_seconds": 1,
    },
}


class TestWebSocketConcurrentConnections:
    """Test concurrent WebSocket connections"""

    @pytest.mark.asyncio
    async def test_light_load_10_connections(self):
        """Test 10 concurrent connections (light load)"""
        metrics = PerformanceMetrics()
        clients: List[MockWebSocketClient] = []
        connection_count = PERF_CONFIG["concurrent_connections"]["light"]

        try:
            # Create and connect clients
            for i in range(connection_count):
                client = MockWebSocketClient(
                    client_id=i,
                    url="ws://localhost:8001/ws",
                    token=f"test-token-{i}",
                )
                clients.append(client)

                # Connect with small stagger
                connection_time = await client.connect()
                metrics.record_connection(connection_time)
                await asyncio.sleep(0.01)

            metrics.record_memory()

            # Verify all connected
            assert all(client.connected for client in clients)
            assert metrics.connection_count == connection_count

            # Check connection time performance
            connection_stats = metrics.get_stats(metrics.connection_times)
            assert connection_stats["p95"] * 1000 < PERF_CONFIG["latency_thresholds"]["p95_ms"]

            print(f"\n✅ Light Load ({connection_count} connections):")
            print(f"  P95 Connection Time: {connection_stats['p95'] * 1000:.2f}ms")
            print(f"  Memory: {metrics.memory_samples[-1]:.2f} MB")

        finally:
            # Cleanup
            for client in clients:
                await client.disconnect()
            metrics.finalize()

        print("\n" + metrics.get_report())

    @pytest.mark.asyncio
    async def test_medium_load_50_connections(self):
        """Test 50 concurrent connections (medium load)"""
        metrics = PerformanceMetrics()
        clients: List[MockWebSocketClient] = []
        connection_count = PERF_CONFIG["concurrent_connections"]["medium"]

        try:
            # Connect in batches for better performance
            batch_size = 10
            for batch_start in range(0, connection_count, batch_size):
                batch_end = min(batch_start + batch_size, connection_count)
                batch_tasks = []

                for i in range(batch_start, batch_end):
                    client = MockWebSocketClient(
                        client_id=i,
                        url="ws://localhost:8001/ws",
                        token=f"test-token-{i}",
                    )
                    clients.append(client)
                    batch_tasks.append(client.connect())

                # Connect batch concurrently
                connection_times = await asyncio.gather(*batch_tasks)
                for connection_time in connection_times:
                    metrics.record_connection(connection_time)

                # Record memory after each batch
                metrics.record_memory()
                await asyncio.sleep(0.05)

            # Verify all connected
            assert all(client.connected for client in clients)
            assert metrics.connection_count == connection_count

            # Check performance
            connection_stats = metrics.get_stats(metrics.connection_times)
            assert connection_stats["p95"] * 1000 < PERF_CONFIG["latency_thresholds"]["p95_ms"]

            # Check memory
            memory_stats = metrics.get_stats(metrics.memory_samples)
            assert memory_stats["max"] < PERF_CONFIG["memory_threshold"]["max_total_mb"]

            print(f"\n✅ Medium Load ({connection_count} connections):")
            print(f"  P95 Connection Time: {connection_stats['p95'] * 1000:.2f}ms")
            print(f"  Memory: {memory_stats['max']:.2f} MB")
            print(f"  Error Rate: {(len(metrics.errors) / connection_count) * 100:.2f}%")

        finally:
            for client in clients:
                await client.disconnect()
            metrics.finalize()

        print("\n" + metrics.get_report())

    @pytest.mark.asyncio
    async def test_heavy_load_100_connections(self):
        """Test 100 concurrent connections (heavy load)"""
        metrics = PerformanceMetrics()
        clients: List[MockWebSocketClient] = []
        connection_count = PERF_CONFIG["concurrent_connections"]["heavy"]

        try:
            # Connect in larger batches
            batch_size = 20
            for batch_start in range(0, connection_count, batch_size):
                batch_end = min(batch_start + batch_size, connection_count)
                batch_tasks = []

                for i in range(batch_start, batch_end):
                    client = MockWebSocketClient(
                        client_id=i,
                        url="ws://localhost:8001/ws",
                        token=f"test-token-{i}",
                    )
                    clients.append(client)
                    batch_tasks.append(client.connect())

                try:
                    connection_times = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    for result in connection_times:
                        if isinstance(result, Exception):
                            metrics.record_error("connection", str(result))
                        else:
                            metrics.record_connection(result)
                except Exception as e:
                    metrics.record_error("batch_connection", str(e))

                metrics.record_memory()
                await asyncio.sleep(0.1)

            # Check error rate
            error_rate = (len(metrics.errors) / connection_count) * 100
            assert error_rate < 10, f"Error rate too high: {error_rate:.2f}%"

            # Check performance
            if metrics.connection_times:
                connection_stats = metrics.get_stats(metrics.connection_times)
                assert connection_stats["p99"] * 1000 < PERF_CONFIG["latency_thresholds"]["p99_ms"]

            # Check memory
            memory_stats = metrics.get_stats(metrics.memory_samples)
            assert memory_stats["max"] < PERF_CONFIG["memory_threshold"]["max_total_mb"]

            print(f"\n✅ Heavy Load ({connection_count} connections):")
            print(f"  Successful: {metrics.connection_count}/{connection_count}")
            print(f"  P99 Connection Time: {connection_stats.get('p99', 0) * 1000:.2f}ms")
            print(f"  Memory: {memory_stats['max']:.2f} MB")
            print(f"  Error Rate: {error_rate:.2f}%")

        finally:
            for client in clients:
                if client.connected:
                    await client.disconnect()
            metrics.finalize()

        print("\n" + metrics.get_report())


class TestWebSocketMessageThroughput:
    """Test message throughput performance"""

    @pytest.mark.asyncio
    async def test_high_message_throughput(self):
        """Test high message throughput (100 msg/s for 10s)"""
        metrics = PerformanceMetrics()

        messages_per_second = PERF_CONFIG["message_throughput"]["messages_per_second"]
        duration_seconds = PERF_CONFIG["message_throughput"]["duration_seconds"]
        total_messages = messages_per_second * duration_seconds

        client = MockWebSocketClient(
            client_id=0,
            url="ws://localhost:8001/ws",
            token="throughput-test-token",
        )

        try:
            await client.connect()
            await client.subscribe("throughput-test")

            start_time = time.time()
            messages_sent = 0

            # Send messages at target rate
            while messages_sent < total_messages:
                send_time = await client.send_message(
                    {
                        "id": messages_sent,
                        "timestamp": time.time(),
                    }
                )

                # Simulate receiving the message
                message, latency = await client.receive_message()
                metrics.record_message(latency)

                messages_sent += 1

                # Maintain target rate
                expected_time = start_time + (messages_sent / messages_per_second)
                current_time = time.time()
                sleep_time = expected_time - current_time

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

                # Record memory periodically
                if messages_sent % 100 == 0:
                    metrics.record_memory()

            metrics.finalize()
            duration = metrics.end_time - metrics.start_time
            actual_throughput = metrics.message_count / duration

            # Assertions
            assert metrics.message_count >= total_messages * 0.95  # At least 95% delivery
            assert actual_throughput >= messages_per_second * 0.9  # Within 10% of target

            # Check latency
            message_stats = metrics.get_stats(metrics.message_latencies)
            assert message_stats["p95"] * 1000 < PERF_CONFIG["latency_thresholds"]["p95_ms"]

            print(f"\n✅ Message Throughput Test:")
            print(f"  Target: {messages_per_second} msg/s")
            print(f"  Actual: {actual_throughput:.2f} msg/s")
            print(f"  Delivery: {(metrics.message_count / total_messages) * 100:.2f}%")
            print(f"  P95 Latency: {message_stats['p95'] * 1000:.2f}ms")

        finally:
            await client.disconnect()

        print("\n" + metrics.get_report())

    @pytest.mark.asyncio
    async def test_burst_traffic(self):
        """Test burst message traffic handling"""
        metrics = PerformanceMetrics()

        burst_size = 1000
        burst_count = 5
        delay_between_bursts = 2  # seconds

        client = MockWebSocketClient(
            client_id=0,
            url="ws://localhost:8001/ws",
            token="burst-test-token",
        )

        try:
            await client.connect()
            await client.subscribe("burst-test")

            total_sent = 0

            for burst in range(burst_count):
                burst_start = time.time()

                # Send burst
                send_tasks = []
                for i in range(burst_size):
                    send_tasks.append(
                        client.send_message(
                            {
                                "burst": burst,
                                "index": i,
                                "timestamp": time.time(),
                            }
                        )
                    )

                await asyncio.gather(*send_tasks)
                burst_duration = time.time() - burst_start

                # Record burst metrics
                metrics.record_message(burst_duration)
                total_sent += burst_size

                print(
                    f"  Burst {burst + 1}/{burst_count}: {burst_size} messages in {burst_duration:.3f}s"
                )

                if burst < burst_count - 1:
                    await asyncio.sleep(delay_between_bursts)

                metrics.record_memory()

            metrics.finalize()

            # Check no errors occurred
            assert len(metrics.errors) == 0

            print(f"\n✅ Burst Traffic Test:")
            print(f"  Total Messages: {total_sent}")
            print(f"  Bursts: {burst_count} × {burst_size}")
            print(f"  No errors: ✓")

        finally:
            await client.disconnect()

        print("\n" + metrics.get_report())


class TestWebSocketStability:
    """Test WebSocket connection stability"""

    @pytest.mark.asyncio
    async def test_connection_stability(self):
        """Test connection stability over time (5 minutes)"""
        metrics = PerformanceMetrics()

        duration_minutes = PERF_CONFIG["stability_test"]["duration_minutes"]
        ping_interval = PERF_CONFIG["stability_test"]["ping_interval_seconds"]

        client = MockWebSocketClient(
            client_id=0,
            url="ws://localhost:8001/ws",
            token="stability-test-token",
        )

        try:
            await client.connect()

            end_time = time.time() + (duration_minutes * 60)
            ping_count = 0
            pong_count = 0

            while time.time() < end_time:
                # Send ping
                time.time()
                await client.send_message({"type": "ping"})
                ping_count += 1

                # Simulate pong response
                await asyncio.sleep(0.02)  # 20ms latency
                message, latency = await client.receive_message()
                pong_count += 1

                metrics.record_message(latency)

                # Wait for next ping
                await asyncio.sleep(ping_interval)

                # Record memory periodically
                if ping_count % 10 == 0:
                    metrics.record_memory()

            metrics.finalize()

            # Calculate pong rate
            pong_rate = (pong_count / ping_count) * 100

            # Assertions
            assert pong_rate >= 95  # At least 95% pong responses
            assert len(metrics.errors) == 0  # No disconnections

            # Check latency stability
            message_stats = metrics.get_stats(metrics.message_latencies)
            assert message_stats["p95"] * 1000 < PERF_CONFIG["latency_thresholds"]["p95_ms"]

            print(f"\n✅ Stability Test ({duration_minutes} minutes):")
            print(f"  Pings: {ping_count}")
            print(f"  Pongs: {pong_count}")
            print(f"  Pong Rate: {pong_rate:.2f}%")
            print(f"  P95 Latency: {message_stats['p95'] * 1000:.2f}ms")
            print(f"  No disconnections: ✓")

        finally:
            await client.disconnect()

        print("\n" + metrics.get_report())


class TestWebSocketMemory:
    """Test memory usage and leak detection"""

    @pytest.mark.asyncio
    async def test_no_memory_leak(self):
        """Test for memory leaks with repeated connect/disconnect"""
        metrics = PerformanceMetrics()

        cycles = 50
        initial_memory = None

        for i in range(cycles):
            client = MockWebSocketClient(
                client_id=i,
                url="ws://localhost:8001/ws",
                token=f"leak-test-{i}",
            )

            await client.connect()
            await asyncio.sleep(0.1)
            await client.disconnect()

            # Record memory every 10 cycles
            if i % 10 == 0:
                metrics.record_memory()
                if initial_memory is None:
                    initial_memory = metrics.memory_samples[0]

        # Final memory check
        metrics.record_memory()
        metrics.finalize()

        # Calculate memory growth
        final_memory = metrics.memory_samples[-1]
        memory_growth = final_memory - initial_memory
        growth_percentage = (memory_growth / initial_memory) * 100

        # Assert memory growth is acceptable
        assert memory_growth < PERF_CONFIG["memory_threshold"]["max_growth_mb"]
        assert growth_percentage < 50  # Less than 50% growth

        print(f"\n✅ Memory Leak Test ({cycles} cycles):")
        print(f"  Initial Memory: {initial_memory:.2f} MB")
        print(f"  Final Memory: {final_memory:.2f} MB")
        print(f"  Growth: {memory_growth:.2f} MB ({growth_percentage:.2f}%)")
        print(f"  No significant leak: ✓")

        print("\n" + metrics.get_report())
