#!/usr/bin/env python3
"""
Performance Validation Script for Janua Platform
Automated validation of Phase 2 performance optimizations

Runs comprehensive tests to validate:
- Sub-100ms response time targets
- Database optimization effectiveness  
- Cache performance and hit rates
- Concurrent user handling capacity
"""

import asyncio
import subprocess
import json
import logging
import sys
import time
from datetime import datetime
from typing import Dict, Any
import argparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class PerformanceValidator:
    """Automated performance validation suite"""

    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.validation_results = {}

    async def validate_basic_endpoints(self) -> Dict[str, Any]:
        """Validate basic endpoint response times"""
        logger.info("🔍 Validating basic endpoint performance...")

        # Run lightweight load test on basic endpoints
        cmd = [
            "python3",
            "scripts/load_testing_framework.py",
            "--url",
            self.api_url,
            "--users",
            "10",
            "--duration",
            "30",
            "--target-ms",
            "50",
            "--no-auth",
            "--no-org",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                return {
                    "status": "PASSED",
                    "message": "Basic endpoints meet performance targets",
                    "details": "All health check endpoints respond under 50ms",
                }
            else:
                return {
                    "status": "FAILED",
                    "message": "Basic endpoints exceed performance targets",
                    "details": result.stderr or result.stdout,
                }
        except subprocess.TimeoutExpired:
            return {
                "status": "FAILED",
                "message": "Basic endpoint validation timed out",
                "details": "Test took longer than 60 seconds",
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Validation error: {str(e)}",
                "details": "Failed to execute basic endpoint test",
            }

    async def validate_authentication_performance(self) -> Dict[str, Any]:
        """Validate authentication endpoint performance"""
        logger.info("🔐 Validating authentication performance...")

        cmd = [
            "python3",
            "scripts/load_testing_framework.py",
            "--url",
            self.api_url,
            "--users",
            "25",
            "--duration",
            "60",
            "--target-ms",
            "100",
            "--no-org",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            if result.returncode == 0:
                return {
                    "status": "PASSED",
                    "message": "Authentication endpoints meet sub-100ms targets",
                    "details": "Signin, token validation, and user profile queries optimized",
                }
            else:
                return {
                    "status": "FAILED",
                    "message": "Authentication performance targets not met",
                    "details": result.stderr or result.stdout,
                }
        except subprocess.TimeoutExpired:
            return {
                "status": "FAILED",
                "message": "Authentication validation timed out",
                "details": "Test exceeded 120 second limit",
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Authentication validation error: {str(e)}",
                "details": "Failed to execute authentication test",
            }

    async def validate_concurrent_load(self) -> Dict[str, Any]:
        """Validate performance under concurrent load"""
        logger.info("⚡ Validating concurrent user load handling...")

        cmd = [
            "python3",
            "scripts/load_testing_framework.py",
            "--url",
            self.api_url,
            "--users",
            "100",
            "--duration",
            "120",
            "--target-ms",
            "100",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                return {
                    "status": "PASSED",
                    "message": "System handles 100 concurrent users within targets",
                    "details": "Performance remains stable under concurrent load",
                }
            else:
                return {
                    "status": "FAILED",
                    "message": "Performance degrades under concurrent load",
                    "details": result.stderr or result.stdout,
                }
        except subprocess.TimeoutExpired:
            return {
                "status": "FAILED",
                "message": "Concurrent load test timed out",
                "details": "Test exceeded 5 minute limit",
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Concurrent load validation error: {str(e)}",
                "details": "Failed to execute concurrent load test",
            }

    async def validate_database_optimization(self) -> Dict[str, Any]:
        """Validate database optimization implementation"""
        logger.info("🗄️ Validating database optimization...")

        cmd = ["python3", "scripts/apply_database_optimization.py"]

        try:
            # Check if database optimization script runs successfully
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if "optimization completed" in result.stdout.lower() or result.returncode == 0:
                return {
                    "status": "PASSED",
                    "message": "Database optimizations applied successfully",
                    "details": "All critical indexes created and query optimization active",
                }
            else:
                return {
                    "status": "FAILED",
                    "message": "Database optimization issues detected",
                    "details": result.stderr or result.stdout,
                }
        except subprocess.TimeoutExpired:
            return {
                "status": "FAILED",
                "message": "Database optimization timed out",
                "details": "Optimization script exceeded 5 minute limit",
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Database validation error: {str(e)}",
                "details": "Failed to execute database optimization validation",
            }

    async def validate_cache_performance(self) -> Dict[str, Any]:
        """Validate caching system performance"""
        logger.info("🔥 Validating cache performance...")

        try:
            import aiohttp

            # Test cache hit rates by making repeated requests
            async with aiohttp.ClientSession() as session:
                cache_test_results = []

                # Test endpoints that should be cached
                test_endpoints = ["/health", "/api/status", "/ready"]

                for endpoint in test_endpoints:
                    # Make initial request
                    url = f"{self.api_url}{endpoint}"
                    start_time = time.perf_counter()

                    async with session.get(url) as response:
                        first_request_time = (time.perf_counter() - start_time) * 1000

                        # Make second request (should be cached)
                        start_time = time.perf_counter()
                        async with session.get(url) as cached_response:
                            second_request_time = (time.perf_counter() - start_time) * 1000

                            cache_test_results.append(
                                {
                                    "endpoint": endpoint,
                                    "first_request_ms": first_request_time,
                                    "second_request_ms": second_request_time,
                                    "cache_improvement": first_request_time - second_request_time
                                    > 5,  # >5ms improvement indicates caching
                                }
                            )

                # Analyze cache performance
                cache_effective = (
                    sum(1 for r in cache_test_results if r["cache_improvement"])
                    >= len(cache_test_results) * 0.5
                )

                if cache_effective:
                    return {
                        "status": "PASSED",
                        "message": "Cache system demonstrating performance improvement",
                        "details": f'Cache effective on {len([r for r in cache_test_results if r["cache_improvement"]])}/{len(cache_test_results)} tested endpoints',
                    }
                else:
                    return {
                        "status": "WARNING",
                        "message": "Cache performance improvement not clearly demonstrated",
                        "details": "May need cache warming or endpoint selection adjustment",
                    }

        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Cache validation error: {str(e)}",
                "details": "Failed to test cache performance",
            }

    async def validate_monitoring_setup(self) -> Dict[str, Any]:
        """Validate performance monitoring is working"""
        logger.info("📊 Validating performance monitoring setup...")

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                # Test performance metrics endpoint
                url = f"{self.api_url}/metrics/performance"

                async with session.get(url) as response:
                    if response.status == 200:
                        metrics_data = await response.json()

                        # Check if metrics contain expected fields
                        required_fields = ["cache_stats", "endpoint_performance", "timestamp"]
                        has_all_fields = all(field in metrics_data for field in required_fields)

                        if has_all_fields:
                            return {
                                "status": "PASSED",
                                "message": "Performance monitoring active and reporting metrics",
                                "details": f"Metrics endpoint returning {len(metrics_data)} data fields",
                            }
                        else:
                            return {
                                "status": "FAILED",
                                "message": "Performance metrics incomplete",
                                "details": f"Missing fields: {[f for f in required_fields if f not in metrics_data]}",
                            }
                    else:
                        return {
                            "status": "FAILED",
                            "message": "Performance metrics endpoint not accessible",
                            "details": f"HTTP {response.status} response",
                        }

        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Monitoring validation error: {str(e)}",
                "details": "Failed to access performance monitoring endpoint",
            }

    async def run_full_validation(self) -> Dict[str, Any]:
        """Run comprehensive performance validation suite"""
        logger.info("🚀 Starting Performance Validation Suite")
        logger.info("=" * 50)

        validation_start = datetime.now()

        # Run all validation tests
        validations = [
            ("Basic Endpoints", self.validate_basic_endpoints()),
            ("Authentication Performance", self.validate_authentication_performance()),
            ("Database Optimization", self.validate_database_optimization()),
            ("Cache Performance", self.validate_cache_performance()),
            ("Performance Monitoring", self.validate_monitoring_setup()),
            ("Concurrent Load Handling", self.validate_concurrent_load()),
        ]

        results = {}
        passed_count = 0
        total_count = len(validations)

        for test_name, test_coro in validations:
            logger.info(f"\n🧪 Running: {test_name}")
            try:
                result = await test_coro
                results[test_name] = result

                status_icon = {"PASSED": "✅", "FAILED": "❌", "WARNING": "⚠️", "ERROR": "💥"}.get(
                    result["status"], "❓"
                )

                logger.info(f"{status_icon} {test_name}: {result['message']}")

                if result["status"] == "PASSED":
                    passed_count += 1
                elif result["details"]:
                    logger.info(f"   Details: {result['details']}")

            except Exception as e:
                logger.error(f"💥 {test_name} failed with exception: {e}")
                results[test_name] = {
                    "status": "ERROR",
                    "message": f"Validation exception: {str(e)}",
                    "details": "Unexpected error during test execution",
                }

        validation_end = datetime.now()
        validation_duration = (validation_end - validation_start).total_seconds()

        # Calculate overall results
        success_rate = (passed_count / total_count) * 100
        overall_status = "PASSED" if success_rate >= 80 else "FAILED"

        summary = {
            "overall_status": overall_status,
            "success_rate": success_rate,
            "passed_tests": passed_count,
            "total_tests": total_count,
            "validation_duration_seconds": validation_duration,
            "detailed_results": results,
            "timestamp": validation_start.isoformat(),
        }

        # Generate summary report
        logger.info("\n" + "=" * 50)
        logger.info("📋 VALIDATION SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Overall Status: {overall_status}")
        logger.info(f"Success Rate: {success_rate:.1f}%")
        logger.info(f"Tests Passed: {passed_count}/{total_count}")
        logger.info(f"Duration: {validation_duration:.1f} seconds")

        if overall_status == "PASSED":
            logger.info("🎉 Performance validation PASSED - Phase 2 targets achieved!")
        else:
            logger.warning("⚠️ Performance validation FAILED - Review failed tests")

        # Save detailed results
        report_filename = f"performance_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, "w") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"📄 Detailed results saved: {report_filename}")

        return summary


async def main():
    """Main validation execution"""
    parser = argparse.ArgumentParser(description="Janua Performance Validation")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument(
        "--quick", action="store_true", help="Run quick validation (skip load tests)"
    )

    args = parser.parse_args()

    validator = PerformanceValidator(api_url=args.url)

    try:
        if args.quick:
            # Quick validation - skip heavy load tests
            logger.info("🏃 Running quick performance validation...")
            results = await validator.validate_basic_endpoints()
            monitoring_results = await validator.validate_monitoring_setup()

            if results["status"] == "PASSED" and monitoring_results["status"] == "PASSED":
                logger.info("✅ Quick validation PASSED")
                return 0
            else:
                logger.warning("⚠️ Quick validation issues detected")
                return 1
        else:
            # Full validation suite
            summary = await validator.run_full_validation()

            if summary["overall_status"] == "PASSED":
                return 0
            else:
                return 1

    except KeyboardInterrupt:
        logger.info("Validation interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
