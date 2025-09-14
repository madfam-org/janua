#!/usr/bin/env python3
"""
Load Testing Framework for Plinto Platform
Phase 2: Performance Validation & Stress Testing

Comprehensive load testing suite to validate sub-100ms response times
and enterprise scalability under concurrent user loads.
"""

import asyncio
import aiohttp
import time
import statistics
import json
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import argparse
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import psutil
import random
import string

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'load_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Individual test result data"""
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    timestamp: datetime
    error: Optional[str] = None
    cache_hit: Optional[bool] = None

@dataclass
class LoadTestConfig:
    """Load test configuration"""
    base_url: str = "http://localhost:8000"
    concurrent_users: int = 100
    test_duration_seconds: int = 300  # 5 minutes
    ramp_up_seconds: int = 30
    ramp_down_seconds: int = 30
    target_percentile: float = 95.0
    target_response_time_ms: float = 100.0
    enable_auth_tests: bool = True
    enable_organization_tests: bool = True
    enable_health_tests: bool = True

class LoadTestRunner:
    """High-performance load testing engine"""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results: List[TestResult] = []
        self.session: Optional[aiohttp.ClientSession] = None
        self.auth_tokens: Dict[str, str] = {}  # user_id -> access_token
        self.test_users: List[Dict[str, str]] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
    async def setup_session(self):
        """Initialize HTTP session with optimizations"""
        timeout = aiohttp.ClientTimeout(total=30, connect=5, sock_read=10)
        connector = aiohttp.TCPConnector(
            limit=self.config.concurrent_users * 2,  # Connection pool
            limit_per_host=self.config.concurrent_users,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=60,
            enable_cleanup_closed=True
        )
        
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Plinto-LoadTest/1.0',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        )
        
        logger.info(f"HTTP session initialized with {self.config.concurrent_users} concurrent connections")
    
    async def cleanup_session(self):
        """Clean up HTTP session"""
        if self.session:
            await self.session.close()
    
    def generate_test_user(self) -> Dict[str, str]:
        """Generate test user credentials"""
        user_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return {
            'email': f'loadtest.{user_id}@plinto.test',
            'password': f'LoadTest123!{user_id}',
            'name': f'Load Test User {user_id}'
        }
    
    async def create_test_users(self, count: int) -> List[Dict[str, str]]:
        """Create test users for authentication testing"""
        logger.info(f"Creating {count} test users for load testing...")
        
        users = []
        for i in range(count):
            user = self.generate_test_user()
            
            # Create user via signup endpoint
            try:
                signup_data = {
                    'email': user['email'],
                    'password': user['password'],
                    'name': user['name']
                }
                
                async with self.session.post(
                    f"{self.config.base_url}/beta/signup",
                    json=signup_data
                ) as response:
                    if response.status == 200 or response.status == 201:
                        users.append(user)
                        if len(users) % 10 == 0:
                            logger.info(f"Created {len(users)}/{count} test users")
                    else:
                        logger.warning(f"Failed to create user {user['email']}: {response.status}")
                        
            except Exception as e:
                logger.warning(f"Error creating user {user['email']}: {e}")
        
        logger.info(f"Successfully created {len(users)} test users")
        return users
    
    async def authenticate_user(self, user: Dict[str, str]) -> Optional[str]:
        """Authenticate user and return access token"""
        try:
            signin_data = {
                'email': user['email'],
                'password': user['password']
            }
            
            async with self.session.post(
                f"{self.config.base_url}/beta/signin",
                json=signin_data
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('access_token')
                else:
                    logger.warning(f"Authentication failed for {user['email']}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.warning(f"Authentication error for {user['email']}: {e}")
            return None
    
    async def make_request(
        self, 
        method: str, 
        endpoint: str, 
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict] = None
    ) -> TestResult:
        """Make HTTP request and record performance metrics"""
        full_url = f"{self.config.base_url}{endpoint}"
        start_time = time.perf_counter()
        
        try:
            request_headers = headers or {}
            
            async with self.session.request(
                method=method,
                url=full_url,
                headers=request_headers,
                json=json_data
            ) as response:
                end_time = time.perf_counter()
                response_time_ms = (end_time - start_time) * 1000
                
                # Check for cache hit header
                cache_hit = response.headers.get('X-Cache-Status') == 'HIT'
                
                return TestResult(
                    endpoint=endpoint,
                    method=method,
                    status_code=response.status,
                    response_time_ms=response_time_ms,
                    timestamp=datetime.now(),
                    cache_hit=cache_hit
                )
                
        except Exception as e:
            end_time = time.perf_counter()
            response_time_ms = (end_time - start_time) * 1000
            
            return TestResult(
                endpoint=endpoint,
                method=method,
                status_code=0,
                response_time_ms=response_time_ms,
                timestamp=datetime.now(),
                error=str(e)
            )
    
    async def health_check_workload(self, user_id: str) -> List[TestResult]:
        """Health check and basic endpoint testing"""
        results = []
        
        endpoints = [
            ("GET", "/health"),
            ("GET", "/ready"),
            ("GET", "/"),
            ("GET", "/api/status")
        ]
        
        for method, endpoint in endpoints:
            result = await self.make_request(method, endpoint)
            results.append(result)
            
            # Small delay to simulate realistic usage
            await asyncio.sleep(random.uniform(0.1, 0.5))
        
        return results
    
    async def authentication_workload(self, user_id: str) -> List[TestResult]:
        """Authentication-focused load testing"""
        results = []
        
        if not self.test_users:
            logger.warning("No test users available for authentication workload")
            return results
        
        # Select a random test user
        user = random.choice(self.test_users)
        
        # Test signin
        signin_result = await self.make_request(
            "POST", 
            "/beta/signin",
            json_data={
                'email': user['email'],
                'password': user['password']
            }
        )
        results.append(signin_result)
        
        # If signin successful, get auth token for subsequent requests
        if signin_result.status_code == 200:
            token = await self.authenticate_user(user)
            if token:
                # Test authenticated endpoints
                auth_headers = {'Authorization': f'Bearer {token}'}
                
                # Test profile access
                profile_result = await self.make_request(
                    "GET",
                    "/api/v1/users/me",
                    headers=auth_headers
                )
                results.append(profile_result)
                
                # Test session validation (multiple rapid requests)
                for _ in range(3):
                    session_result = await self.make_request(
                        "GET",
                        "/api/v1/sessions/current",
                        headers=auth_headers
                    )
                    results.append(session_result)
                    await asyncio.sleep(0.1)
        
        return results
    
    async def organization_workload(self, user_id: str) -> List[TestResult]:
        """Organization and multi-tenant testing"""
        results = []
        
        # Test organization listing (cached endpoint)
        org_list_result = await self.make_request("GET", "/api/v1/organizations")
        results.append(org_list_result)
        
        # Test organization creation (if authenticated)
        if self.auth_tokens.get(user_id):
            auth_headers = {'Authorization': f'Bearer {self.auth_tokens[user_id]}'}
            
            org_create_result = await self.make_request(
                "POST",
                "/api/v1/organizations",
                headers=auth_headers,
                json_data={
                    'name': f'Load Test Org {user_id}',
                    'slug': f'loadtest-{user_id}-{int(time.time())}'
                }
            )
            results.append(org_create_result)
        
        return results
    
    async def user_simulation(self, user_id: str) -> List[TestResult]:
        """Simulate realistic user behavior"""
        all_results = []
        
        # Simulate user session with mixed workload
        workloads = []
        
        if self.config.enable_health_tests:
            workloads.append(self.health_check_workload)
        
        if self.config.enable_auth_tests:
            workloads.append(self.authentication_workload)
        
        if self.config.enable_organization_tests:
            workloads.append(self.organization_workload)
        
        # Execute random workloads
        for _ in range(random.randint(2, 5)):  # 2-5 operations per user
            workload = random.choice(workloads)
            results = await workload(user_id)
            all_results.extend(results)
            
            # Random think time between operations
            await asyncio.sleep(random.uniform(0.5, 2.0))
        
        return all_results
    
    async def ramp_up_users(self) -> List[asyncio.Task]:
        """Gradually ramp up concurrent users"""
        logger.info(f"Ramping up {self.config.concurrent_users} users over {self.config.ramp_up_seconds} seconds")
        
        tasks = []
        users_per_second = self.config.concurrent_users / self.config.ramp_up_seconds
        
        for i in range(self.config.concurrent_users):
            delay = i / users_per_second
            user_id = f"user_{i:04d}"
            
            # Schedule user simulation with delay
            task = asyncio.create_task(self._delayed_user_simulation(user_id, delay))
            tasks.append(task)
        
        return tasks
    
    async def _delayed_user_simulation(self, user_id: str, delay: float):
        """Execute user simulation with initial delay"""
        await asyncio.sleep(delay)
        return await self.user_simulation(user_id)
    
    def analyze_results(self) -> Dict[str, Any]:
        """Comprehensive performance analysis"""
        if not self.results:
            return {"error": "No results to analyze"}
        
        # Calculate timing metrics
        response_times = [r.response_time_ms for r in self.results if r.error is None]
        
        if not response_times:
            return {"error": "No successful requests to analyze"}
        
        # Overall statistics
        total_requests = len(self.results)
        successful_requests = len([r for r in self.results if r.status_code == 200])
        error_requests = total_requests - successful_requests
        
        # Response time analysis
        avg_response_time = statistics.mean(response_times)
        median_response_time = statistics.median(response_times)
        p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
        p99_response_time = statistics.quantiles(response_times, n=100)[98]  # 99th percentile
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        # Endpoint-specific analysis
        endpoint_stats = {}
        for result in self.results:
            key = f"{result.method} {result.endpoint}"
            if key not in endpoint_stats:
                endpoint_stats[key] = {
                    'count': 0,
                    'success_count': 0,
                    'response_times': []
                }
            
            stats = endpoint_stats[key]
            stats['count'] += 1
            if result.status_code == 200:
                stats['success_count'] += 1
            if result.error is None:
                stats['response_times'].append(result.response_time_ms)
        
        # Calculate endpoint metrics
        for key, stats in endpoint_stats.items():
            if stats['response_times']:
                stats['avg_response_time'] = statistics.mean(stats['response_times'])
                stats['p95_response_time'] = statistics.quantiles(stats['response_times'], n=20)[18] if len(stats['response_times']) > 20 else max(stats['response_times'])
                stats['success_rate'] = (stats['success_count'] / stats['count']) * 100
            else:
                stats['avg_response_time'] = 0
                stats['p95_response_time'] = 0
                stats['success_rate'] = 0
        
        # Cache performance (if available)
        cache_hits = len([r for r in self.results if r.cache_hit is True])
        cache_total = len([r for r in self.results if r.cache_hit is not None])
        cache_hit_rate = (cache_hits / cache_total * 100) if cache_total > 0 else 0
        
        # Test duration
        test_duration = (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else 0
        requests_per_second = total_requests / test_duration if test_duration > 0 else 0
        
        # Performance targets
        p95_target_met = p95_response_time <= self.config.target_response_time_ms
        avg_target_met = avg_response_time <= (self.config.target_response_time_ms * 0.7)  # 70% of target for average
        
        return {
            'test_summary': {
                'total_requests': total_requests,
                'successful_requests': successful_requests,
                'error_requests': error_requests,
                'success_rate_percent': (successful_requests / total_requests * 100),
                'test_duration_seconds': test_duration,
                'requests_per_second': requests_per_second,
                'concurrent_users': self.config.concurrent_users
            },
            'response_time_metrics': {
                'average_ms': round(avg_response_time, 2),
                'median_ms': round(median_response_time, 2),
                'p95_ms': round(p95_response_time, 2),
                'p99_ms': round(p99_response_time, 2),
                'min_ms': round(min_response_time, 2),
                'max_ms': round(max_response_time, 2)
            },
            'performance_targets': {
                'target_p95_ms': self.config.target_response_time_ms,
                'actual_p95_ms': round(p95_response_time, 2),
                'p95_target_met': p95_target_met,
                'target_avg_ms': self.config.target_response_time_ms * 0.7,
                'actual_avg_ms': round(avg_response_time, 2),
                'avg_target_met': avg_target_met,
                'overall_target_met': p95_target_met and avg_target_met
            },
            'cache_performance': {
                'cache_hit_rate_percent': round(cache_hit_rate, 2),
                'cache_hits': cache_hits,
                'cache_total_requests': cache_total
            },
            'endpoint_analysis': {
                key: {
                    'requests': stats['count'],
                    'success_rate_percent': round(stats['success_rate'], 2),
                    'avg_response_ms': round(stats['avg_response_time'], 2),
                    'p95_response_ms': round(stats['p95_response_time'], 2)
                }
                for key, stats in endpoint_stats.items()
            }
        }
    
    def generate_report(self, analysis: Dict[str, Any]) -> str:
        """Generate comprehensive load test report"""
        report = f"""
# Load Test Report
**Generated**: {datetime.now().isoformat()}
**Test Duration**: {analysis['test_summary']['test_duration_seconds']:.1f} seconds
**Concurrent Users**: {analysis['test_summary']['concurrent_users']}

## 📊 Test Summary
- **Total Requests**: {analysis['test_summary']['total_requests']:,}
- **Successful Requests**: {analysis['test_summary']['successful_requests']:,}
- **Error Requests**: {analysis['test_summary']['error_requests']:,}
- **Success Rate**: {analysis['test_summary']['success_rate_percent']:.1f}%
- **Requests per Second**: {analysis['test_summary']['requests_per_second']:.1f}

## ⚡ Response Time Analysis
- **Average**: {analysis['response_time_metrics']['average_ms']:.1f}ms
- **Median**: {analysis['response_time_metrics']['median_ms']:.1f}ms
- **95th Percentile**: {analysis['response_time_metrics']['p95_ms']:.1f}ms
- **99th Percentile**: {analysis['response_time_metrics']['p99_ms']:.1f}ms
- **Min**: {analysis['response_time_metrics']['min_ms']:.1f}ms
- **Max**: {analysis['response_time_metrics']['max_ms']:.1f}ms

## 🎯 Performance Targets
- **Target 95th Percentile**: {analysis['performance_targets']['target_p95_ms']:.0f}ms
- **Actual 95th Percentile**: {analysis['performance_targets']['actual_p95_ms']:.1f}ms
- **P95 Target Met**: {'✅ YES' if analysis['performance_targets']['p95_target_met'] else '❌ NO'}
- **Average Target Met**: {'✅ YES' if analysis['performance_targets']['avg_target_met'] else '❌ NO'}
- **Overall Target Met**: {'✅ YES' if analysis['performance_targets']['overall_target_met'] else '❌ NO'}

## 🔥 Cache Performance
- **Cache Hit Rate**: {analysis['cache_performance']['cache_hit_rate_percent']:.1f}%
- **Cache Hits**: {analysis['cache_performance']['cache_hits']:,}
- **Total Cached Requests**: {analysis['cache_performance']['cache_total_requests']:,}

## 📈 Endpoint Performance
"""
        
        for endpoint, stats in analysis['endpoint_analysis'].items():
            status = '✅' if stats['p95_response_ms'] <= self.config.target_response_time_ms else '⚠️'
            report += f"- {status} **{endpoint}**: {stats['avg_response_ms']:.1f}ms avg, {stats['p95_response_ms']:.1f}ms p95, {stats['success_rate_percent']:.1f}% success\n"
        
        return report
    
    async def run_load_test(self) -> Dict[str, Any]:
        """Execute complete load test suite"""
        logger.info("🚀 Starting Plinto Load Test Suite")
        logger.info(f"Configuration: {self.config.concurrent_users} users, {self.config.test_duration_seconds}s duration")
        
        try:
            # Setup
            await self.setup_session()
            
            # Create test users if authentication testing enabled
            if self.config.enable_auth_tests:
                self.test_users = await self.create_test_users(min(50, self.config.concurrent_users))
            
            # Start load test
            self.start_time = datetime.now()
            logger.info(f"Load test started at {self.start_time.isoformat()}")
            
            # Ramp up users
            tasks = await self.ramp_up_users()
            
            # Wait for test duration
            logger.info(f"Running load test for {self.config.test_duration_seconds} seconds...")
            
            # Collect results as they complete
            for completed_task in asyncio.as_completed(tasks):
                try:
                    user_results = await completed_task
                    self.results.extend(user_results)
                except Exception as e:
                    logger.error(f"User simulation failed: {e}")
            
            self.end_time = datetime.now()
            logger.info(f"Load test completed at {self.end_time.isoformat()}")
            
            # Analyze results
            analysis = self.analyze_results()
            
            # Generate and save report
            report = self.generate_report(analysis)
            
            # Save detailed results
            report_filename = f"load_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(report_filename, 'w') as f:
                f.write(report)
            
            # Save raw data
            data_filename = f"load_test_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(data_filename, 'w') as f:
                json.dump({
                    'config': asdict(self.config),
                    'analysis': analysis,
                    'results': [asdict(r) for r in self.results]
                }, f, indent=2, default=str)
            
            logger.info(f"📋 Load test report saved: {report_filename}")
            logger.info(f"📊 Raw data saved: {data_filename}")
            
            # Print summary
            logger.info("\n" + report)
            
            return analysis
            
        finally:
            await self.cleanup_session()

async def main():
    """Main load testing execution"""
    parser = argparse.ArgumentParser(description="Plinto Load Testing Framework")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL for testing")
    parser.add_argument("--users", type=int, default=100, help="Concurrent users")
    parser.add_argument("--duration", type=int, default=300, help="Test duration in seconds")
    parser.add_argument("--target-ms", type=float, default=100.0, help="Target response time in ms")
    parser.add_argument("--no-auth", action="store_true", help="Disable authentication tests")
    parser.add_argument("--no-org", action="store_true", help="Disable organization tests")
    
    args = parser.parse_args()
    
    config = LoadTestConfig(
        base_url=args.url,
        concurrent_users=args.users,
        test_duration_seconds=args.duration,
        target_response_time_ms=args.target_ms,
        enable_auth_tests=not args.no_auth,
        enable_organization_tests=not args.no_org
    )
    
    runner = LoadTestRunner(config)
    
    try:
        analysis = await runner.run_load_test()
        
        # Exit code based on performance targets
        if analysis['performance_targets']['overall_target_met']:
            logger.info("🎉 All performance targets met!")
            return 0
        else:
            logger.warning("⚠️ Some performance targets not met")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Load test interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Load test failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)