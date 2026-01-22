#!/usr/bin/env python3
"""
Monitoring integration validation script
Checks that all monitoring endpoints are working correctly
"""

import asyncio
import aiohttp
import json
import sys
from typing import Dict, Any, List
from datetime import datetime


class MonitoringValidator:
    def __init__(self):
        self.base_urls = {
            "api": "http://localhost:8000",
            "dashboard": "http://localhost:3001",
            "admin": "http://localhost:3004",
        }
        self.results = []

    async def check_endpoint(
        self,
        session: aiohttp.ClientSession,
        service: str,
        endpoint: str,
        expected_content: str = None,
    ) -> Dict[str, Any]:
        """Check a single monitoring endpoint"""
        url = f"{self.base_urls[service]}{endpoint}"

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                content = await response.text()

                result = {
                    "service": service,
                    "endpoint": endpoint,
                    "url": url,
                    "status_code": response.status,
                    "response_time_ms": None,  # Would need timing
                    "content_type": response.headers.get("content-type", ""),
                    "success": response.status == 200,
                    "content_preview": content[:200] if len(content) > 200 else content,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                # Validate expected content if provided
                if expected_content and expected_content not in content:
                    result["success"] = False
                    result["error"] = f"Expected content '{expected_content}' not found"

                return result

        except Exception as e:
            return {
                "service": service,
                "endpoint": endpoint,
                "url": url,
                "status_code": None,
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def check_api_endpoints(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Check FastAPI monitoring endpoints"""
        endpoints = [
            ("/health", None),
            ("/ready", None),
            ("/api/v1/health", "healthy"),
            ("/api/v1/health/detailed", "status"),
            ("/metrics", "janua_"),
            ("/metrics/performance", None),
            ("/metrics/scalability", None),
        ]

        results = []
        for endpoint, expected in endpoints:
            result = await self.check_endpoint(session, "api", endpoint, expected)
            results.append(result)

        return results

    async def check_frontend_endpoints(
        self, session: aiohttp.ClientSession
    ) -> List[Dict[str, Any]]:
        """Check frontend monitoring endpoints"""
        results = []

        # Dashboard endpoints
        dashboard_endpoints = [("/api/metrics", "janua_dashboard_")]

        for endpoint, expected in dashboard_endpoints:
            result = await self.check_endpoint(session, "dashboard", endpoint, expected)
            results.append(result)

        # Admin endpoints
        admin_endpoints = [("/api/metrics", "janua_admin_")]

        for endpoint, expected in admin_endpoints:
            result = await self.check_endpoint(session, "admin", endpoint, expected)
            results.append(result)

        return results

    async def test_metrics_collection(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Test metrics collection by sending sample data"""
        results = []

        # Test dashboard metrics collection
        try:
            dashboard_metrics_url = f"{self.base_urls['dashboard']}/api/metrics"
            test_data = {"type": "pageView", "metadata": {"page": "/test", "test": True}}

            async with session.post(dashboard_metrics_url, json=test_data) as response:
                result = {
                    "service": "dashboard",
                    "endpoint": "/api/metrics",
                    "method": "POST",
                    "status_code": response.status,
                    "success": response.status == 200,
                    "test_type": "metrics_collection",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                results.append(result)

        except Exception as e:
            results.append(
                {
                    "service": "dashboard",
                    "endpoint": "/api/metrics",
                    "method": "POST",
                    "success": False,
                    "error": str(e),
                    "test_type": "metrics_collection",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        # Test admin metrics collection
        try:
            admin_metrics_url = f"{self.base_urls['admin']}/api/metrics"
            test_data = {"type": "adminAction", "metadata": {"action": "test", "test": True}}

            async with session.post(admin_metrics_url, json=test_data) as response:
                result = {
                    "service": "admin",
                    "endpoint": "/api/metrics",
                    "method": "POST",
                    "status_code": response.status,
                    "success": response.status == 200,
                    "test_type": "metrics_collection",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                results.append(result)

        except Exception as e:
            results.append(
                {
                    "service": "admin",
                    "endpoint": "/api/metrics",
                    "method": "POST",
                    "success": False,
                    "error": str(e),
                    "test_type": "metrics_collection",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        return results

    async def run_validation(self) -> Dict[str, Any]:
        """Run complete monitoring validation"""
        print("🔍 Starting monitoring integration validation...")

        async with aiohttp.ClientSession() as session:
            # Check all endpoints
            api_results = await self.check_api_endpoints(session)
            frontend_results = await self.check_frontend_endpoints(session)
            metrics_test_results = await self.test_metrics_collection(session)

            all_results = api_results + frontend_results + metrics_test_results

            # Calculate summary statistics
            total_checks = len(all_results)
            successful_checks = len([r for r in all_results if r.get("success", False)])
            failed_checks = total_checks - successful_checks

            success_rate = (successful_checks / total_checks * 100) if total_checks > 0 else 0

            summary = {
                "timestamp": datetime.utcnow().isoformat(),
                "total_checks": total_checks,
                "successful_checks": successful_checks,
                "failed_checks": failed_checks,
                "success_rate_percent": round(success_rate, 2),
                "services_tested": list(self.base_urls.keys()),
                "overall_status": "PASS" if success_rate >= 80 else "FAIL",
                "results": all_results,
            }

            return summary

    def print_results(self, summary: Dict[str, Any]):
        """Print validation results in a readable format"""
        print(f"\n📊 Monitoring Integration Validation Results")
        print(f"{'=' * 50}")
        print(f"Total Checks: {summary['total_checks']}")
        print(f"Successful: {summary['successful_checks']}")
        print(f"Failed: {summary['failed_checks']}")
        print(f"Success Rate: {summary['success_rate_percent']}%")
        print(f"Overall Status: {summary['overall_status']}")
        print(f"{'=' * 50}")

        # Group results by service
        services = {}
        for result in summary["results"]:
            service = result["service"]
            if service not in services:
                services[service] = []
            services[service].append(result)

        for service, results in services.items():
            print(f"\n🔧 {service.upper()} Service:")
            for result in results:
                status = "✅" if result.get("success", False) else "❌"
                endpoint = result.get("endpoint", "N/A")
                method = result.get("method", "GET")
                status_code = result.get("status_code", "N/A")

                print(f"  {status} {method} {endpoint} [{status_code}]")

                if not result.get("success", False) and "error" in result:
                    print(f"    Error: {result['error']}")

        print(f"\n📈 Integration Status:")
        if summary["overall_status"] == "PASS":
            print("✅ Monitoring integration is working correctly!")
            print("   - Prometheus metrics endpoints are responding")
            print("   - Health checks are configured")
            print("   - Frontend metrics collection is functional")
        else:
            print("❌ Monitoring integration has issues!")
            print("   Please check failed endpoints and ensure all services are running")

        print(f"\n📋 Next Steps:")
        print("   1. Start Prometheus to scrape metrics: docker-compose up prometheus")
        print("   2. Start Grafana for visualization: docker-compose up grafana")
        print("   3. Import dashboard configuration from monitoring/dashboard-config.yaml")
        print("   4. Configure alerts in deployment/monitoring/prometheus.yml")


async def main():
    """Main validation entry point"""
    validator = MonitoringValidator()

    try:
        summary = await validator.run_validation()
        validator.print_results(summary)

        # Save detailed results to file
        with open("monitoring-validation-results.json", "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\n💾 Detailed results saved to: monitoring-validation-results.json")

        # Exit with appropriate code
        sys.exit(0 if summary["overall_status"] == "PASS" else 1)

    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
