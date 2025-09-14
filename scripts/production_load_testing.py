#!/usr/bin/env python3
"""
Production Load Testing Suite for Plinto Platform
Phase 3: End-to-end Production Validation

Comprehensive production-ready load testing covering:
- Real-world traffic patterns
- Enterprise-scale concurrent users
- Multi-region simulation
- Performance regression detection
- SLA compliance validation
- Capacity planning metrics
"""

import asyncio
import aiohttp
import time
import statistics
import json
import logging
import sys
import random
import string
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import argparse
from dataclasses import dataclass, asdict
import secrets
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
import psutil
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'production_load_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class LoadTestConfig:
    """Production load test configuration"""
    base_url: str = "https://api.plinto.dev"
    max_concurrent_users: int = 500
    test_duration_minutes: int = 30
    ramp_up_minutes: int = 5
    ramp_down_minutes: int = 5
    target_percentile: float = 95.0
    target_response_time_ms: float = 100.0
    sla_success_rate: float = 99.5
    enterprise_scenarios: bool = True
    multi_region_simulation: bool = True
    capacity_testing: bool = True

@dataclass
class TestScenario:
    """Individual test scenario definition"""
    name: str
    weight: float  # Probability of selection
    user_type: str
    operations: List[Dict[str, Any]]
    think_time_range: Tuple[float, float]  # Min, max think time in seconds

@dataclass
class PerformanceMetric:
    """Performance measurement data"""
    timestamp: datetime
    endpoint: str
    method: str
    response_time_ms: float
    status_code: int
    user_type: str
    scenario: str
    region: str
    success: bool
    error_message: Optional[str] = None
    cache_hit: Optional[bool] = None
    
class ProductionLoadTestRunner:
    """Enterprise-grade production load testing engine"""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.metrics: List[PerformanceMetric] = []
        self.active_sessions = {}  # user_id -> session_data
        self.test_users: List[Dict[str, str]] = []
        self.scenarios: List[TestScenario] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.concurrent_executor = ThreadPoolExecutor(max_workers=config.max_concurrent_users)
        
    def setup_test_scenarios(self):
        """Configure realistic production test scenarios"""
        self.scenarios = [
            TestScenario(
                name="New User Registration",
                weight=0.05,  # 5% of traffic
                user_type="new_user",
                operations=[
                    {"action": "signup", "endpoint": "/beta/signup"},
                    {"action": "email_verification", "endpoint": "/api/v1/auth/verify-email"},
                    {"action": "profile_setup", "endpoint": "/api/v1/users/me"}
                ],
                think_time_range=(2.0, 10.0)
            ),
            TestScenario(
                name="Returning User Login",
                weight=0.15,  # 15% of traffic
                user_type="returning_user",
                operations=[
                    {"action": "signin", "endpoint": "/beta/signin"},
                    {"action": "dashboard_access", "endpoint": "/api/v1/users/me"},
                    {"action": "session_check", "endpoint": "/api/v1/sessions/current"}
                ],
                think_time_range=(1.0, 5.0)
            ),
            TestScenario(
                name="Active User Session",
                weight=0.40,  # 40% of traffic
                user_type="active_user",
                operations=[
                    {"action": "profile_view", "endpoint": "/api/v1/users/me"},
                    {"action": "organization_list", "endpoint": "/api/v1/organizations"},
                    {"action": "settings_update", "endpoint": "/api/v1/users/me"},
                    {"action": "activity_check", "endpoint": "/api/v1/users/activity"}
                ],
                think_time_range=(5.0, 30.0)
            ),
            TestScenario(
                name="Enterprise Admin Workflow",
                weight=0.20,  # 20% of traffic
                user_type="enterprise_admin",
                operations=[
                    {"action": "organization_dashboard", "endpoint": "/api/v1/organizations"},
                    {"action": "user_management", "endpoint": "/api/v1/organizations/members"},
                    {"action": "scim_sync", "endpoint": "/api/v1/scim/users"},
                    {"action": "audit_logs", "endpoint": "/api/v1/organizations/audit"},
                    {"action": "webhook_config", "endpoint": "/api/v1/webhooks"}
                ],
                think_time_range=(10.0, 60.0)
            ),
            TestScenario(
                name="API Integration Usage",
                weight=0.15,  # 15% of traffic
                user_type="api_consumer",
                operations=[
                    {"action": "token_refresh", "endpoint": "/api/v1/auth/refresh"},
                    {"action": "user_lookup", "endpoint": "/api/v1/users/me"},
                    {"action": "batch_operations", "endpoint": "/api/v1/users"},
                    {"action": "webhook_delivery", "endpoint": "/api/v1/webhooks/test"}
                ],
                think_time_range=(0.5, 2.0)
            ),
            TestScenario(
                name="Health Check Monitoring",
                weight=0.05,  # 5% of traffic
                user_type="monitoring_system",
                operations=[
                    {"action": "health_check", "endpoint": "/health"},
                    {"action": "readiness_check", "endpoint": "/ready"},
                    {"action": "metrics_collection", "endpoint": "/metrics/performance"}
                ],
                think_time_range=(0.1, 1.0)
            )
        ]
        
        logger.info(f"📋 Configured {len(self.scenarios)} production test scenarios")
        for scenario in self.scenarios:
            logger.info(f"   • {scenario.name}: {scenario.weight*100:.1f}% weight, {len(scenario.operations)} operations")

    async def create_test_user_pool(self, count: int) -> List[Dict[str, str]]:
        """Create a pool of test users for realistic testing"""
        logger.info(f"👥 Creating {count} test users for production load testing...")
        
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            
            for i in range(count):
                user_data = {
                    'email': f'loadtest.prod.{secrets.token_hex(6)}@plinto.test',
                    'password': f'ProdTest123!{secrets.token_hex(4)}',
                    'name': f'Production Test User {i+1:04d}'
                }
                task = self.create_single_test_user(session, user_data)
                tasks.append(task)
                
                # Batch creation to avoid overwhelming the server
                if len(tasks) >= 20 or i == count - 1:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    successful_users = [r for r in results if isinstance(r, dict)]
                    self.test_users.extend(successful_users)
                    tasks = []
                    
                    if len(self.test_users) % 50 == 0:
                        logger.info(f"   Created {len(self.test_users)}/{count} test users")
                    
                    # Brief delay between batches
                    await asyncio.sleep(0.5)
        
        logger.info(f"✅ Successfully created {len(self.test_users)} production test users")
        return self.test_users

    async def create_single_test_user(self, session: aiohttp.ClientSession, user_data: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Create a single test user"""
        try:
            async with session.post(
                f"{self.config.base_url}/beta/signup",
                json=user_data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status in [200, 201]:
                    return user_data
                else:
                    logger.debug(f"Failed to create user {user_data['email']}: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.debug(f"Error creating user {user_data['email']}: {e}")
            return None

    def select_scenario(self) -> TestScenario:
        """Select a test scenario based on weighted probabilities"""
        weights = [scenario.weight for scenario in self.scenarios]
        return random.choices(self.scenarios, weights=weights)[0]

    async def execute_scenario_operation(
        self, 
        session: aiohttp.ClientSession, 
        operation: Dict[str, Any], 
        user_data: Dict[str, str],
        scenario_name: str,
        region: str
    ) -> PerformanceMetric:
        """Execute a single operation within a scenario"""
        start_time = time.perf_counter()
        endpoint = operation['endpoint']
        method = operation.get('method', 'GET')
        action = operation['action']
        
        try:
            # Prepare request based on action type
            headers = {}
            json_data = None
            
            # Add authentication if user is logged in
            if user_data.get('access_token'):
                headers['Authorization'] = f"Bearer {user_data['access_token']}"
            
            # Prepare request data based on action
            if action == 'signup':
                method = 'POST'
                json_data = {
                    'email': user_data['email'],
                    'password': user_data['password'],
                    'name': user_data['name']
                }
            elif action == 'signin':
                method = 'POST'
                json_data = {
                    'email': user_data['email'],
                    'password': user_data['password']
                }
            elif action in ['settings_update', 'profile_setup']:
                method = 'PATCH'
                json_data = {
                    'name': f"Updated {user_data['name']} {random.randint(1, 1000)}"
                }
            elif action == 'webhook_test':
                method = 'POST'
                json_data = {
                    'url': 'https://webhook.site/unique-id',
                    'events': ['user.created', 'user.updated']
                }
            
            # Execute request with regional simulation
            headers['X-Region'] = region  # Simulate multi-region requests
            
            async with session.request(
                method=method,
                url=f"{self.config.base_url}{endpoint}",
                headers=headers,
                json=json_data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                end_time = time.perf_counter()
                response_time_ms = (end_time - start_time) * 1000
                
                # Check for cache hit header
                cache_hit = response.headers.get('X-Cache-Status') == 'HIT'
                success = response.status < 400
                
                # Handle successful signin - store token
                if action == 'signin' and response.status == 200:
                    response_data = await response.json()
                    user_data['access_token'] = response_data.get('access_token', '')
                
                return PerformanceMetric(
                    timestamp=datetime.now(),
                    endpoint=endpoint,
                    method=method,
                    response_time_ms=response_time_ms,
                    status_code=response.status,
                    user_type=scenario_name,
                    scenario=action,
                    region=region,
                    success=success,
                    cache_hit=cache_hit
                )
        
        except Exception as e:
            end_time = time.perf_counter()
            response_time_ms = (end_time - start_time) * 1000
            
            return PerformanceMetric(
                timestamp=datetime.now(),
                endpoint=endpoint,
                method=method,
                response_time_ms=response_time_ms,
                status_code=0,
                user_type=scenario_name,
                scenario=action,
                region=region,
                success=False,
                error_message=str(e)
            )

    async def simulate_user_session(self, user_id: str, duration_minutes: float) -> List[PerformanceMetric]:
        """Simulate a realistic user session for the specified duration"""
        session_metrics = []
        user_data = random.choice(self.test_users).copy() if self.test_users else {
            'email': f'temp.user.{user_id}@test.com',
            'password': 'TempPassword123!',
            'name': f'Temp User {user_id}'
        }
        
        # Simulate multi-region requests
        regions = ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1']
        region = random.choice(regions) if self.config.multi_region_simulation else 'us-east-1'
        
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': f'Plinto-LoadTest-{user_id}'}
        ) as session:
            
            session_start = time.time()
            session_end = session_start + (duration_minutes * 60)
            
            while time.time() < session_end:
                # Select scenario based on weights
                scenario = self.select_scenario()
                
                # Execute scenario operations
                for operation in scenario.operations:
                    if time.time() >= session_end:
                        break
                    
                    metric = await self.execute_scenario_operation(
                        session, operation, user_data, scenario.name, region
                    )
                    session_metrics.append(metric)
                    
                    # Think time between operations
                    think_time = random.uniform(*scenario.think_time_range)
                    await asyncio.sleep(min(think_time, session_end - time.time()))
                
                # Brief pause between scenarios
                if time.time() < session_end:
                    await asyncio.sleep(random.uniform(1.0, 5.0))
        
        logger.debug(f"User {user_id} session completed: {len(session_metrics)} operations")
        return session_metrics

    async def execute_load_test_phase(self, phase_name: str, concurrent_users: int, duration_minutes: float):
        """Execute a phase of the load test with specified parameters"""
        logger.info(f"🚀 Starting {phase_name}: {concurrent_users} users for {duration_minutes:.1f} minutes")
        
        # Create user simulation tasks
        tasks = []
        for i in range(concurrent_users):
            user_id = f"{phase_name.lower().replace(' ', '_')}_{i:04d}"
            task = asyncio.create_task(self.simulate_user_session(user_id, duration_minutes))
            tasks.append(task)
        
        # Execute all user sessions concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect metrics from all sessions
        phase_metrics = []
        for result in results:
            if isinstance(result, list):
                phase_metrics.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"User session failed in {phase_name}: {result}")
        
        logger.info(f"✅ {phase_name} completed: {len(phase_metrics)} operations recorded")
        return phase_metrics

    async def run_capacity_testing(self) -> List[PerformanceMetric]:
        """Run capacity testing with gradual user increase"""
        logger.info("📈 Starting Capacity Testing Phase...")
        
        capacity_metrics = []
        user_increments = [50, 100, 200, 300, 400, 500]
        
        for user_count in user_increments:
            if user_count > self.config.max_concurrent_users:
                break
            
            logger.info(f"🔢 Capacity Test: {user_count} concurrent users")
            
            # Short burst test for each user count level
            metrics = await self.execute_load_test_phase(
                f"Capacity {user_count}",
                user_count,
                2.0  # 2 minutes per capacity level
            )
            
            capacity_metrics.extend(metrics)
            
            # Analyze response times at this capacity level
            if metrics:
                response_times = [m.response_time_ms for m in metrics if m.success]
                if response_times:
                    avg_response_time = statistics.mean(response_times)
                    p95_response_time = statistics.quantiles(response_times, n=20)[18] if len(response_times) > 20 else max(response_times)
                    
                    logger.info(f"   📊 At {user_count} users: {avg_response_time:.1f}ms avg, {p95_response_time:.1f}ms p95")
                    
                    # Stop capacity testing if performance degrades significantly
                    if p95_response_time > self.config.target_response_time_ms * 3:  # 3x target threshold
                        logger.warning(f"⚠️ Performance degradation detected at {user_count} users")
                        break
            
            # Brief cooldown between capacity levels
            await asyncio.sleep(30)
        
        return capacity_metrics

    async def run_production_load_test(self) -> Dict[str, Any]:
        """Execute comprehensive production load test"""
        logger.info("🏭 Starting Production Load Testing Suite")
        logger.info("=" * 60)
        logger.info(f"Configuration:")
        logger.info(f"  • Target URL: {self.config.base_url}")
        logger.info(f"  • Max Concurrent Users: {self.config.max_concurrent_users}")
        logger.info(f"  • Test Duration: {self.config.test_duration_minutes} minutes")
        logger.info(f"  • SLA Target: {self.config.target_response_time_ms}ms (95th percentile)")
        logger.info(f"  • Success Rate Target: {self.config.sla_success_rate}%")
        logger.info("=" * 60)
        
        self.start_time = datetime.now()
        
        try:
            # Phase 1: Setup
            self.setup_test_scenarios()
            await self.create_test_user_pool(min(100, self.config.max_concurrent_users))
            
            # Phase 2: Ramp-up
            logger.info(f"\n📈 Phase 2: Ramp-up ({self.config.ramp_up_minutes} minutes)")
            ramp_up_users = int(self.config.max_concurrent_users * 0.3)  # 30% of max users
            ramp_up_metrics = await self.execute_load_test_phase(
                "Ramp Up", ramp_up_users, self.config.ramp_up_minutes
            )
            self.metrics.extend(ramp_up_metrics)
            
            # Phase 3: Steady State Load Testing
            logger.info(f"\n🔄 Phase 3: Steady State ({self.config.test_duration_minutes} minutes)")
            steady_state_metrics = await self.execute_load_test_phase(
                "Steady State", self.config.max_concurrent_users, self.config.test_duration_minutes
            )
            self.metrics.extend(steady_state_metrics)
            
            # Phase 4: Capacity Testing (if enabled)
            if self.config.capacity_testing:
                capacity_metrics = await self.run_capacity_testing()
                self.metrics.extend(capacity_metrics)
            
            # Phase 5: Ramp-down
            logger.info(f"\n📉 Phase 5: Ramp-down ({self.config.ramp_down_minutes} minutes)")
            ramp_down_users = int(self.config.max_concurrent_users * 0.2)  # 20% of max users
            ramp_down_metrics = await self.execute_load_test_phase(
                "Ramp Down", ramp_down_users, self.config.ramp_down_minutes
            )
            self.metrics.extend(ramp_down_metrics)
            
            self.end_time = datetime.now()
            
            # Generate comprehensive analysis
            analysis = self.analyze_production_results()
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Production load test failed: {e}")
            raise
        finally:
            self.concurrent_executor.shutdown(wait=True)

    def analyze_production_results(self) -> Dict[str, Any]:
        """Comprehensive analysis of production load test results"""
        logger.info("📊 Analyzing Production Load Test Results...")
        
        if not self.metrics:
            return {"error": "No metrics collected"}
        
        # Basic statistics
        total_requests = len(self.metrics)
        successful_requests = len([m for m in self.metrics if m.success])
        failed_requests = total_requests - successful_requests
        success_rate = (successful_requests / total_requests) * 100
        
        # Response time analysis
        successful_metrics = [m for m in self.metrics if m.success]
        response_times = [m.response_time_ms for m in successful_metrics]
        
        if not response_times:
            return {"error": "No successful requests for analysis"}
        
        # Performance statistics
        avg_response_time = statistics.mean(response_times)
        median_response_time = statistics.median(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        # Percentile calculations
        response_times_sorted = sorted(response_times)
        p50 = statistics.median(response_times_sorted)
        p90 = np.percentile(response_times_sorted, 90)
        p95 = np.percentile(response_times_sorted, 95)
        p99 = np.percentile(response_times_sorted, 99)
        
        # SLA compliance
        sla_compliant_requests = len([rt for rt in response_times if rt <= self.config.target_response_time_ms])
        sla_compliance_rate = (sla_compliant_requests / len(response_times)) * 100
        
        success_rate_sla_met = success_rate >= self.config.sla_success_rate
        response_time_sla_met = p95 <= self.config.target_response_time_ms
        overall_sla_met = success_rate_sla_met and response_time_sla_met
        
        # Scenario analysis
        scenario_stats = {}
        for scenario in self.scenarios:
            scenario_metrics = [m for m in self.metrics if m.user_type == scenario.name]
            if scenario_metrics:
                scenario_response_times = [m.response_time_ms for m in scenario_metrics if m.success]
                if scenario_response_times:
                    scenario_stats[scenario.name] = {
                        'requests': len(scenario_metrics),
                        'success_rate': len([m for m in scenario_metrics if m.success]) / len(scenario_metrics) * 100,
                        'avg_response_time': statistics.mean(scenario_response_times),
                        'p95_response_time': np.percentile(scenario_response_times, 95),
                        'target_weight': scenario.weight * 100
                    }
        
        # Endpoint analysis
        endpoint_stats = {}
        for metric in self.metrics:
            key = f"{metric.method} {metric.endpoint}"
            if key not in endpoint_stats:
                endpoint_stats[key] = []
            endpoint_stats[key].append(metric)
        
        endpoint_analysis = {}
        for endpoint, metrics in endpoint_stats.items():
            successful = [m for m in metrics if m.success]
            if successful:
                response_times = [m.response_time_ms for m in successful]
                endpoint_analysis[endpoint] = {
                    'requests': len(metrics),
                    'success_rate': len(successful) / len(metrics) * 100,
                    'avg_response_time': statistics.mean(response_times),
                    'p95_response_time': np.percentile(response_times, 95) if len(response_times) > 1 else response_times[0],
                    'cache_hit_rate': len([m for m in successful if m.cache_hit]) / len(successful) * 100 if successful else 0
                }
        
        # Regional analysis (if multi-region enabled)
        region_stats = {}
        if self.config.multi_region_simulation:
            for region in ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1']:
                region_metrics = [m for m in self.metrics if m.region == region and m.success]
                if region_metrics:
                    region_response_times = [m.response_time_ms for m in region_metrics]
                    region_stats[region] = {
                        'requests': len(region_metrics),
                        'avg_response_time': statistics.mean(region_response_times),
                        'p95_response_time': np.percentile(region_response_times, 95)
                    }
        
        # Test duration and throughput
        test_duration = (self.end_time - self.start_time).total_seconds()
        requests_per_second = total_requests / test_duration if test_duration > 0 else 0
        
        # Generate comprehensive report
        return {
            'test_summary': {
                'total_requests': total_requests,
                'successful_requests': successful_requests,
                'failed_requests': failed_requests,
                'success_rate_percent': round(success_rate, 2),
                'test_duration_seconds': round(test_duration, 1),
                'requests_per_second': round(requests_per_second, 2),
                'max_concurrent_users': self.config.max_concurrent_users,
                'test_start': self.start_time.isoformat(),
                'test_end': self.end_time.isoformat()
            },
            'performance_metrics': {
                'average_ms': round(avg_response_time, 2),
                'median_ms': round(median_response_time, 2),
                'min_ms': round(min_response_time, 2),
                'max_ms': round(max_response_time, 2),
                'p50_ms': round(p50, 2),
                'p90_ms': round(p90, 2),
                'p95_ms': round(p95, 2),
                'p99_ms': round(p99, 2)
            },
            'sla_compliance': {
                'target_response_time_ms': self.config.target_response_time_ms,
                'target_success_rate_percent': self.config.sla_success_rate,
                'actual_p95_response_time_ms': round(p95, 2),
                'actual_success_rate_percent': round(success_rate, 2),
                'response_time_sla_met': response_time_sla_met,
                'success_rate_sla_met': success_rate_sla_met,
                'overall_sla_met': overall_sla_met,
                'sla_compliance_rate_percent': round(sla_compliance_rate, 2)
            },
            'scenario_analysis': scenario_stats,
            'endpoint_analysis': endpoint_analysis,
            'regional_analysis': region_stats if region_stats else None,
            'capacity_insights': {
                'max_tested_users': self.config.max_concurrent_users,
                'performance_stable': overall_sla_met,
                'recommended_capacity': self.config.max_concurrent_users if overall_sla_met else int(self.config.max_concurrent_users * 0.8)
            }
        }

    def generate_production_report(self, analysis: Dict[str, Any]) -> str:
        """Generate comprehensive production load test report"""
        sla_status = "✅ PASSED" if analysis['sla_compliance']['overall_sla_met'] else "❌ FAILED"
        
        report = f"""
# Production Load Test Report
**Generated**: {datetime.now().isoformat()}
**Test Duration**: {analysis['test_summary']['test_duration_seconds']:.1f} seconds
**Max Concurrent Users**: {analysis['test_summary']['max_concurrent_users']}
**Overall SLA Status**: {sla_status}

## 📊 Executive Summary
- **Total Requests**: {analysis['test_summary']['total_requests']:,}
- **Success Rate**: {analysis['test_summary']['success_rate_percent']:.2f}%
- **Requests per Second**: {analysis['test_summary']['requests_per_second']:.1f}
- **Average Response Time**: {analysis['performance_metrics']['average_ms']:.1f}ms
- **95th Percentile**: {analysis['performance_metrics']['p95_ms']:.1f}ms

## 🎯 SLA Compliance
- **Response Time Target**: {analysis['sla_compliance']['target_response_time_ms']:.0f}ms (95th percentile)
- **Actual 95th Percentile**: {analysis['sla_compliance']['actual_p95_response_time_ms']:.1f}ms
- **Response Time SLA**: {'✅ MET' if analysis['sla_compliance']['response_time_sla_met'] else '❌ NOT MET'}

- **Success Rate Target**: {analysis['sla_compliance']['target_success_rate_percent']:.1f}%
- **Actual Success Rate**: {analysis['sla_compliance']['actual_success_rate_percent']:.2f}%
- **Success Rate SLA**: {'✅ MET' if analysis['sla_compliance']['success_rate_sla_met'] else '❌ NOT MET'}

## 📈 Performance Breakdown
- **Average**: {analysis['performance_metrics']['average_ms']:.1f}ms
- **Median**: {analysis['performance_metrics']['median_ms']:.1f}ms
- **90th Percentile**: {analysis['performance_metrics']['p90_ms']:.1f}ms
- **95th Percentile**: {analysis['performance_metrics']['p95_ms']:.1f}ms
- **99th Percentile**: {analysis['performance_metrics']['p99_ms']:.1f}ms
- **Min**: {analysis['performance_metrics']['min_ms']:.1f}ms
- **Max**: {analysis['performance_metrics']['max_ms']:.1f}ms

## 🎭 Scenario Performance
"""
        
        for scenario_name, stats in analysis['scenario_analysis'].items():
            status = '✅' if stats['p95_response_time'] <= self.config.target_response_time_ms else '⚠️'
            report += f"- {status} **{scenario_name}**: {stats['avg_response_time']:.1f}ms avg, {stats['p95_response_time']:.1f}ms p95, {stats['success_rate']:.1f}% success\n"
        
        report += "\n## 📍 Endpoint Analysis\n"
        for endpoint, stats in sorted(analysis['endpoint_analysis'].items(), key=lambda x: x[1]['p95_response_time']):
            status = '✅' if stats['p95_response_time'] <= self.config.target_response_time_ms else '⚠️'
            cache_info = f", {stats['cache_hit_rate']:.1f}% cached" if stats['cache_hit_rate'] > 0 else ""
            report += f"- {status} **{endpoint}**: {stats['avg_response_time']:.1f}ms avg, {stats['p95_response_time']:.1f}ms p95{cache_info}\n"
        
        if analysis.get('regional_analysis'):
            report += "\n## 🌍 Regional Performance\n"
            for region, stats in analysis['regional_analysis'].items():
                report += f"- **{region}**: {stats['avg_response_time']:.1f}ms avg, {stats['p95_response_time']:.1f}ms p95\n"
        
        report += f"\n## 🚀 Capacity Recommendations\n"
        report += f"- **Max Tested Concurrent Users**: {analysis['capacity_insights']['max_tested_users']}\n"
        report += f"- **Performance Stability**: {'✅ Stable' if analysis['capacity_insights']['performance_stable'] else '⚠️ Degraded'}\n"
        report += f"- **Recommended Capacity**: {analysis['capacity_insights']['recommended_capacity']} concurrent users\n"
        
        return report

async def main():
    """Main production load testing execution"""
    parser = argparse.ArgumentParser(description="Plinto Production Load Testing Suite")
    parser.add_argument("--url", default="https://api.plinto.dev", help="Base URL for testing")
    parser.add_argument("--users", type=int, default=500, help="Max concurrent users")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in minutes")
    parser.add_argument("--target-ms", type=float, default=100.0, help="Target response time in ms")
    parser.add_argument("--sla-success", type=float, default=99.5, help="SLA success rate threshold")
    parser.add_argument("--no-capacity", action="store_true", help="Skip capacity testing")
    parser.add_argument("--no-multiregion", action="store_true", help="Skip multi-region simulation")
    
    args = parser.parse_args()
    
    config = LoadTestConfig(
        base_url=args.url,
        max_concurrent_users=args.users,
        test_duration_minutes=args.duration,
        target_response_time_ms=args.target_ms,
        sla_success_rate=args.sla_success,
        capacity_testing=not args.no_capacity,
        multi_region_simulation=not args.no_multiregion
    )
    
    runner = ProductionLoadTestRunner(config)
    
    try:
        analysis = await runner.run_production_load_test()
        
        # Generate and save report
        report = runner.generate_production_report(analysis)
        
        # Save detailed results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_filename = f"production_load_test_report_{timestamp}.md"
        data_filename = f"production_load_test_data_{timestamp}.json"
        
        with open(report_filename, 'w') as f:
            f.write(report)
        
        with open(data_filename, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        logger.info(f"\n📋 Production load test report saved: {report_filename}")
        logger.info(f"📊 Raw data saved: {data_filename}")
        
        # Print summary
        logger.info("\n" + report)
        
        # Exit code based on SLA compliance
        if analysis['sla_compliance']['overall_sla_met']:
            logger.info("🎉 All production SLAs met!")
            return 0
        else:
            logger.warning("⚠️ Some production SLAs not met")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Production load test interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Production load test failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)