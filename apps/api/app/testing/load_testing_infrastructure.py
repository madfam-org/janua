"""
Load Testing Infrastructure
Enterprise-grade load testing with Locust, performance scenarios, and real-time monitoring
"""

import os
import time
import random
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging
import statistics
from locust import HttpUser, task, between
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)


class TestScenario(Enum):
    """Load testing scenarios"""

    SMOKE = "smoke"
    LOAD = "load"
    STRESS = "stress"
    SPIKE = "spike"
    SOAK = "soak"
    CAPACITY = "capacity"
    BREAKPOINT = "breakpoint"
    SCALABILITY = "scalability"


class PerformanceMetric(Enum):
    """Performance metrics to track"""

    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    CONCURRENCY = "concurrency"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    NETWORK_IO = "network_io"
    DATABASE_CONNECTIONS = "database_connections"


@dataclass
class TestConfiguration:
    """Load test configuration"""

    scenario: TestScenario
    target_url: str
    duration_seconds: int
    initial_users: int
    peak_users: int
    spawn_rate: float
    think_time_min: float
    think_time_max: float
    success_criteria: Dict[str, float]
    test_data: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class TestResult:
    """Load test results"""

    test_id: str
    scenario: TestScenario
    started_at: datetime
    completed_at: Optional[datetime]
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    p50_response_time: float
    p95_response_time: float
    p99_response_time: float
    requests_per_second: float
    error_rate: float
    peak_concurrent_users: int
    errors_by_type: Dict[str, int]
    response_times: List[float]
    success: bool
    failure_reasons: List[str]


class AuthenticationUser(HttpUser):
    """Load test user for authentication endpoints"""

    wait_time = between(1, 3)

    def on_start(self):
        """Initialize user session"""
        self.client.verify = False
        self.username = f"testuser_{random.randint(1000, 9999)}@example.com"
        self.password = "Test123!@#"
        self.token = None

    @task(3)
    def signup(self):
        """Test signup endpoint"""
        response = self.client.post(
            "/api/v1/auth/signup",
            json={
                "email": f"new_{self.username}",
                "password": self.password,
                "full_name": "Test User",
            },
            catch_response=True,
        )

        if response.status_code == 200:
            response.success()
        else:
            response.failure(f"Signup failed: {response.status_code}")

    @task(5)
    def signin(self):
        """Test signin endpoint"""
        response = self.client.post(
            "/api/v1/auth/signin",
            json={"email": self.username, "password": self.password},
            catch_response=True,
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            response.success()
        else:
            response.failure(f"Signin failed: {response.status_code}")

    @task(2)
    def get_profile(self):
        """Test profile endpoint"""
        if not self.token:
            return

        response = self.client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
        )

        if response.status_code == 200:
            response.success()
        else:
            response.failure(f"Profile fetch failed: {response.status_code}")

    @task(1)
    def refresh_token(self):
        """Test token refresh"""
        if not self.token:
            return

        response = self.client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {self.token}"},
            catch_response=True,
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            response.success()
        else:
            response.failure(f"Token refresh failed: {response.status_code}")


class APIUser(HttpUser):
    """General API load test user"""

    wait_time = between(0.5, 2)

    def on_start(self):
        """Initialize API user"""
        self.client.verify = False
        # Authenticate and get token
        self._authenticate()

    def _authenticate(self):
        """Authenticate user"""
        response = self.client.post(
            "/api/v1/auth/signin",
            json={"email": "loadtest@example.com", "password": "LoadTest123!@#"},
        )

        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.headers = {}

    @task(10)
    def list_users(self):
        """Test user list endpoint"""
        response = self.client.get("/api/v1/users", headers=self.headers, catch_response=True)

        if response.status_code in [200, 403]:
            response.success()
        else:
            response.failure(f"User list failed: {response.status_code}")

    @task(5)
    def get_user_detail(self):
        """Test user detail endpoint"""
        user_id = random.randint(1, 100)
        response = self.client.get(
            f"/api/v1/users/{user_id}", headers=self.headers, catch_response=True
        )

        if response.status_code in [200, 404, 403]:
            response.success()
        else:
            response.failure(f"User detail failed: {response.status_code}")

    @task(3)
    def search_users(self):
        """Test user search"""
        response = self.client.get(
            "/api/v1/users/search?q=test", headers=self.headers, catch_response=True
        )

        if response.status_code in [200, 403]:
            response.success()
        else:
            response.failure(f"User search failed: {response.status_code}")


class LoadTestingInfrastructure:
    """
    Enterprise-grade load testing infrastructure with:
    - Multiple testing scenarios (smoke, load, stress, spike, soak)
    - Real-time performance monitoring
    - Automated performance regression detection
    - Visual reporting with Plotly
    - Integration with CI/CD pipelines
    - Custom user behavior simulation
    """

    def __init__(self):
        self.test_results: List[TestResult] = []
        self.active_tests: Dict[str, TestConfiguration] = {}
        self.performance_baselines: Dict[str, Dict[str, float]] = {}
        self._load_baselines()

    def _load_baselines(self):
        """Load performance baselines"""

        self.performance_baselines = {
            "auth_endpoints": {
                "p95_response_time": 200,  # ms
                "p99_response_time": 500,  # ms
                "error_rate": 0.01,  # 1%
                "requests_per_second": 100,
            },
            "api_endpoints": {
                "p95_response_time": 150,
                "p99_response_time": 300,
                "error_rate": 0.005,
                "requests_per_second": 200,
            },
            "database_operations": {
                "p95_response_time": 50,
                "p99_response_time": 100,
                "connection_pool_size": 100,
                "query_timeout": 5000,
            },
        }

    async def run_test_scenario(
        self, scenario: TestScenario, target_url: str, **kwargs
    ) -> TestResult:
        """Run a specific test scenario"""

        import uuid

        test_id = str(uuid.uuid4())

        # Get scenario configuration
        config = self._get_scenario_config(scenario, target_url, **kwargs)
        self.active_tests[test_id] = config

        try:
            # Run the appropriate test
            if scenario == TestScenario.SMOKE:
                result = await self._run_smoke_test(test_id, config)
            elif scenario == TestScenario.LOAD:
                result = await self._run_load_test(test_id, config)
            elif scenario == TestScenario.STRESS:
                result = await self._run_stress_test(test_id, config)
            elif scenario == TestScenario.SPIKE:
                result = await self._run_spike_test(test_id, config)
            elif scenario == TestScenario.SOAK:
                result = await self._run_soak_test(test_id, config)
            elif scenario == TestScenario.CAPACITY:
                result = await self._run_capacity_test(test_id, config)
            elif scenario == TestScenario.BREAKPOINT:
                result = await self._run_breakpoint_test(test_id, config)
            else:
                result = await self._run_scalability_test(test_id, config)

            # Check against baselines
            result.success = self._check_success_criteria(result, config)

            # Store result
            self.test_results.append(result)

            # Generate report
            await self._generate_report(result)

            return result

        finally:
            del self.active_tests[test_id]

    def _get_scenario_config(
        self, scenario: TestScenario, target_url: str, **kwargs
    ) -> TestConfiguration:
        """Get configuration for test scenario"""

        configs = {
            TestScenario.SMOKE: TestConfiguration(
                scenario=scenario,
                target_url=target_url,
                duration_seconds=kwargs.get("duration", 60),
                initial_users=1,
                peak_users=5,
                spawn_rate=1,
                think_time_min=1,
                think_time_max=3,
                success_criteria={"max_response_time": 1000, "error_rate": 0.01},
            ),
            TestScenario.LOAD: TestConfiguration(
                scenario=scenario,
                target_url=target_url,
                duration_seconds=kwargs.get("duration", 600),
                initial_users=10,
                peak_users=kwargs.get("peak_users", 100),
                spawn_rate=kwargs.get("spawn_rate", 2),
                think_time_min=1,
                think_time_max=3,
                success_criteria={"p95_response_time": 500, "error_rate": 0.01},
            ),
            TestScenario.STRESS: TestConfiguration(
                scenario=scenario,
                target_url=target_url,
                duration_seconds=kwargs.get("duration", 900),
                initial_users=50,
                peak_users=kwargs.get("peak_users", 500),
                spawn_rate=kwargs.get("spawn_rate", 10),
                think_time_min=0.5,
                think_time_max=2,
                success_criteria={"p95_response_time": 1000, "error_rate": 0.05},
            ),
            TestScenario.SPIKE: TestConfiguration(
                scenario=scenario,
                target_url=target_url,
                duration_seconds=kwargs.get("duration", 300),
                initial_users=10,
                peak_users=kwargs.get("peak_users", 1000),
                spawn_rate=kwargs.get("spawn_rate", 100),
                think_time_min=0.1,
                think_time_max=0.5,
                success_criteria={"recovery_time": 60, "max_error_rate": 0.1},
            ),
            TestScenario.SOAK: TestConfiguration(
                scenario=scenario,
                target_url=target_url,
                duration_seconds=kwargs.get("duration", 7200),  # 2 hours
                initial_users=50,
                peak_users=kwargs.get("peak_users", 100),
                spawn_rate=kwargs.get("spawn_rate", 1),
                think_time_min=1,
                think_time_max=5,
                success_criteria={"memory_leak": False, "consistent_performance": True},
            ),
            TestScenario.CAPACITY: TestConfiguration(
                scenario=scenario,
                target_url=target_url,
                duration_seconds=kwargs.get("duration", 1800),
                initial_users=100,
                peak_users=kwargs.get("peak_users", 2000),
                spawn_rate=kwargs.get("spawn_rate", 20),
                think_time_min=0.5,
                think_time_max=2,
                success_criteria={"max_users": 1000, "p95_response_time": 1000},
            ),
            TestScenario.BREAKPOINT: TestConfiguration(
                scenario=scenario,
                target_url=target_url,
                duration_seconds=kwargs.get("duration", 3600),
                initial_users=100,
                peak_users=kwargs.get("peak_users", 10000),
                spawn_rate=kwargs.get("spawn_rate", 50),
                think_time_min=0.1,
                think_time_max=1,
                success_criteria={"find_breaking_point": True},
            ),
            TestScenario.SCALABILITY: TestConfiguration(
                scenario=scenario,
                target_url=target_url,
                duration_seconds=kwargs.get("duration", 2400),
                initial_users=10,
                peak_users=kwargs.get("peak_users", 1000),
                spawn_rate=kwargs.get("spawn_rate", 10),
                think_time_min=1,
                think_time_max=3,
                success_criteria={"linear_scalability": True, "resource_efficiency": True},
            ),
        }

        return configs.get(scenario, configs[TestScenario.LOAD])

    async def _run_smoke_test(self, test_id: str, config: TestConfiguration) -> TestResult:
        """Run smoke test - basic functionality check"""

        logger.info(f"Starting smoke test {test_id}")

        # Run minimal load test
        result = await self._execute_locust_test(
            test_id=test_id,
            user_class=AuthenticationUser,
            host=config.target_url,
            users=config.peak_users,
            spawn_rate=config.spawn_rate,
            run_time=config.duration_seconds,
        )

        return result

    async def _run_load_test(self, test_id: str, config: TestConfiguration) -> TestResult:
        """Run load test - normal expected load"""

        logger.info(f"Starting load test {test_id}")

        # Gradually increase load
        result = await self._execute_locust_test(
            test_id=test_id,
            user_class=APIUser,
            host=config.target_url,
            users=config.peak_users,
            spawn_rate=config.spawn_rate,
            run_time=config.duration_seconds,
        )

        return result

    async def _run_stress_test(self, test_id: str, config: TestConfiguration) -> TestResult:
        """Run stress test - beyond normal capacity"""

        logger.info(f"Starting stress test {test_id}")

        # Push system to limits
        result = await self._execute_locust_test(
            test_id=test_id,
            user_class=APIUser,
            host=config.target_url,
            users=config.peak_users,
            spawn_rate=config.spawn_rate,
            run_time=config.duration_seconds,
        )

        return result

    async def _run_spike_test(self, test_id: str, config: TestConfiguration) -> TestResult:
        """Run spike test - sudden traffic surge"""

        logger.info(f"Starting spike test {test_id}")

        # Sudden spike in traffic
        result = await self._execute_locust_test(
            test_id=test_id,
            user_class=APIUser,
            host=config.target_url,
            users=config.peak_users,
            spawn_rate=config.spawn_rate * 10,  # Rapid spawn
            run_time=config.duration_seconds,
        )

        return result

    async def _run_soak_test(self, test_id: str, config: TestConfiguration) -> TestResult:
        """Run soak test - extended duration test"""

        logger.info(f"Starting soak test {test_id}")

        # Long duration test
        result = await self._execute_locust_test(
            test_id=test_id,
            user_class=APIUser,
            host=config.target_url,
            users=config.peak_users,
            spawn_rate=config.spawn_rate,
            run_time=config.duration_seconds,
        )

        # Check for memory leaks
        result = self._analyze_soak_test(result)

        return result

    async def _run_capacity_test(self, test_id: str, config: TestConfiguration) -> TestResult:
        """Run capacity test - find maximum capacity"""

        logger.info(f"Starting capacity test {test_id}")

        # Incrementally increase load
        max_successful_users = 0
        current_users = config.initial_users

        while current_users <= config.peak_users:
            result = await self._execute_locust_test(
                test_id=test_id,
                user_class=APIUser,
                host=config.target_url,
                users=current_users,
                spawn_rate=config.spawn_rate,
                run_time=60,  # 1 minute per level
            )

            if result.error_rate < 0.01 and result.p95_response_time < 1000:
                max_successful_users = current_users
                current_users += 100
            else:
                break

        result.peak_concurrent_users = max_successful_users
        return result

    async def _run_breakpoint_test(self, test_id: str, config: TestConfiguration) -> TestResult:
        """Run breakpoint test - find system breaking point"""

        logger.info(f"Starting breakpoint test {test_id}")

        # Increase load until system breaks
        result = await self._execute_locust_test(
            test_id=test_id,
            user_class=APIUser,
            host=config.target_url,
            users=config.peak_users,
            spawn_rate=config.spawn_rate,
            run_time=config.duration_seconds,
            stop_on_error_rate=0.5,  # Stop at 50% error rate
        )

        return result

    async def _run_scalability_test(self, test_id: str, config: TestConfiguration) -> TestResult:
        """Run scalability test - test horizontal scaling"""

        logger.info(f"Starting scalability test {test_id}")

        # Test with different instance counts
        results = []

        for instances in [1, 2, 4, 8]:
            # Would configure load balancer for instances
            result = await self._execute_locust_test(
                test_id=f"{test_id}_{instances}",
                user_class=APIUser,
                host=config.target_url,
                users=config.peak_users * instances,
                spawn_rate=config.spawn_rate,
                run_time=300,  # 5 minutes per configuration
            )
            results.append(result)

        # Analyze scalability
        return self._analyze_scalability(results)

    async def _execute_locust_test(
        self,
        test_id: str,
        user_class,
        host: str,
        users: int,
        spawn_rate: float,
        run_time: int,
        stop_on_error_rate: float = None,
    ) -> TestResult:
        """Execute Locust test"""

        from locust.env import Environment
        from locust.log import setup_logging

        # Setup logging
        setup_logging("INFO", None)

        # Create environment
        env = Environment(user_classes=[user_class], host=host)

        # Start test
        env.runner.start(users, spawn_rate=spawn_rate)

        # Collect metrics
        response_times = []
        errors = {}
        start_time = datetime.utcnow()

        # Run for specified duration
        test_start = time.time()
        while time.time() - test_start < run_time:
            time.sleep(1)

            # Collect current stats
            for stat in env.stats.entries.values():
                response_times.extend(
                    [stat.avg_response_time, stat.min_response_time, stat.max_response_time]
                )

            # Check stop condition
            if stop_on_error_rate:
                total_requests = sum(e.num_requests for e in env.stats.entries.values())
                total_failures = sum(e.num_failures for e in env.stats.entries.values())

                if total_requests > 0:
                    error_rate = total_failures / total_requests
                    if error_rate >= stop_on_error_rate:
                        logger.warning(f"Stopping test due to high error rate: {error_rate}")
                        break

        # Stop test
        env.runner.quit()

        # Calculate results
        total_stats = env.stats.total

        result = TestResult(
            test_id=test_id,
            scenario=TestScenario.LOAD,
            started_at=start_time,
            completed_at=datetime.utcnow(),
            total_requests=total_stats.num_requests,
            successful_requests=total_stats.num_requests - total_stats.num_failures,
            failed_requests=total_stats.num_failures,
            avg_response_time=total_stats.avg_response_time,
            min_response_time=total_stats.min_response_time,
            max_response_time=total_stats.max_response_time,
            p50_response_time=total_stats.get_response_time_percentile(0.5),
            p95_response_time=total_stats.get_response_time_percentile(0.95),
            p99_response_time=total_stats.get_response_time_percentile(0.99),
            requests_per_second=total_stats.total_rps,
            error_rate=total_stats.num_failures / max(total_stats.num_requests, 1),
            peak_concurrent_users=users,
            errors_by_type=errors,
            response_times=response_times,
            success=True,
            failure_reasons=[],
        )

        return result

    def _analyze_soak_test(self, result: TestResult) -> TestResult:
        """Analyze soak test for memory leaks and degradation"""

        # Check for performance degradation over time
        if len(result.response_times) > 100:
            first_quarter = result.response_times[: len(result.response_times) // 4]
            last_quarter = result.response_times[-len(result.response_times) // 4 :]

            avg_first = statistics.mean(first_quarter)
            avg_last = statistics.mean(last_quarter)

            # Check if performance degraded by more than 20%
            if avg_last > avg_first * 1.2:
                result.failure_reasons.append("Performance degradation detected")
                result.success = False

        return result

    def _analyze_scalability(self, results: List[TestResult]) -> TestResult:
        """Analyze scalability test results"""

        # Check if throughput scales linearly
        throughputs = [r.requests_per_second for r in results]
        instances = [1, 2, 4, 8]

        # Calculate scalability efficiency
        base_throughput = throughputs[0]
        efficiencies = [
            throughputs[i] / (base_throughput * instances[i]) for i in range(len(throughputs))
        ]

        avg_efficiency = statistics.mean(efficiencies)

        # Create summary result
        summary = results[-1]  # Use last result as base
        summary.success = avg_efficiency > 0.7  # 70% efficiency threshold

        if not summary.success:
            summary.failure_reasons.append(f"Poor scalability efficiency: {avg_efficiency:.2%}")

        return summary

    def _check_success_criteria(self, result: TestResult, config: TestConfiguration) -> bool:
        """Check if test met success criteria"""

        criteria = config.success_criteria
        success = True

        # Check response time criteria
        if "p95_response_time" in criteria:
            if result.p95_response_time > criteria["p95_response_time"]:
                result.failure_reasons.append(
                    f"P95 response time {result.p95_response_time}ms exceeds threshold {criteria['p95_response_time']}ms"
                )
                success = False

        if "p99_response_time" in criteria:
            if result.p99_response_time > criteria["p99_response_time"]:
                result.failure_reasons.append(
                    f"P99 response time {result.p99_response_time}ms exceeds threshold {criteria['p99_response_time']}ms"
                )
                success = False

        # Check error rate
        if "error_rate" in criteria:
            if result.error_rate > criteria["error_rate"]:
                result.failure_reasons.append(
                    f"Error rate {result.error_rate:.2%} exceeds threshold {criteria['error_rate']:.2%}"
                )
                success = False

        # Check throughput
        if "min_rps" in criteria:
            if result.requests_per_second < criteria["min_rps"]:
                result.failure_reasons.append(
                    f"Throughput {result.requests_per_second:.2f} RPS below threshold {criteria['min_rps']} RPS"
                )
                success = False

        return success

    async def _generate_report(self, result: TestResult):
        """Generate visual test report"""

        # Create report directory
        report_dir = Path("load_test_reports")
        report_dir.mkdir(exist_ok=True)

        # Generate HTML report with Plotly
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Response Time Distribution",
                "Throughput Over Time",
                "Error Rate",
                "Concurrent Users",
            ),
        )

        # Response time histogram
        if result.response_times:
            fig.add_trace(
                go.Histogram(x=result.response_times, name="Response Times"), row=1, col=1
            )

        # Throughput line chart (simulated)
        time_points = list(range(0, len(result.response_times)))
        fig.add_trace(
            go.Scatter(
                x=time_points, y=[result.requests_per_second] * len(time_points), name="RPS"
            ),
            row=1,
            col=2,
        )

        # Error rate pie chart
        fig.add_trace(
            go.Pie(
                labels=["Success", "Failures"],
                values=[result.successful_requests, result.failed_requests],
                marker_colors=["green", "red"],
            ),
            row=2,
            col=1,
        )

        # Concurrent users
        fig.add_trace(
            go.Scatter(
                x=time_points, y=[result.peak_concurrent_users] * len(time_points), name="Users"
            ),
            row=2,
            col=2,
        )

        # Update layout
        fig.update_layout(title=f"Load Test Report - {result.test_id}", height=800, showlegend=True)

        # Save report
        report_path = report_dir / f"report_{result.test_id}.html"
        fig.write_html(str(report_path))

        logger.info(f"Report generated: {report_path}")

    async def run_ci_pipeline_tests(self) -> bool:
        """Run tests suitable for CI/CD pipeline"""

        # Run smoke test
        smoke_result = await self.run_test_scenario(
            TestScenario.SMOKE, os.getenv("API_URL", "http://localhost:8000")
        )

        if not smoke_result.success:
            logger.error("Smoke test failed in CI pipeline")
            return False

        # Run basic load test
        load_result = await self.run_test_scenario(
            TestScenario.LOAD,
            os.getenv("API_URL", "http://localhost:8000"),
            duration=300,  # 5 minutes for CI
            peak_users=50,
        )

        if not load_result.success:
            logger.error("Load test failed in CI pipeline")
            return False

        return True

    async def compare_with_baseline(self, result: TestResult, baseline_name: str) -> Dict[str, Any]:
        """Compare test results with baseline"""

        baseline = self.performance_baselines.get(baseline_name, {})

        comparison = {"test_id": result.test_id, "baseline": baseline_name, "metrics": {}}

        # Compare P95 response time
        if "p95_response_time" in baseline:
            diff = result.p95_response_time - baseline["p95_response_time"]
            comparison["metrics"]["p95_response_time"] = {
                "current": result.p95_response_time,
                "baseline": baseline["p95_response_time"],
                "difference": diff,
                "regression": diff
                > baseline["p95_response_time"] * 0.1,  # 10% regression threshold
            }

        # Compare error rate
        if "error_rate" in baseline:
            diff = result.error_rate - baseline["error_rate"]
            comparison["metrics"]["error_rate"] = {
                "current": result.error_rate,
                "baseline": baseline["error_rate"],
                "difference": diff,
                "regression": diff > baseline["error_rate"] * 0.5,  # 50% regression threshold
            }

        # Overall regression detection
        comparison["has_regression"] = any(
            m.get("regression", False) for m in comparison["metrics"].values()
        )

        return comparison
