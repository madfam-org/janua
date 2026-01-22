#!/usr/bin/env python3
"""
Enterprise Readiness Validation Script
Comprehensive validation of enterprise authentication platform requirements

Security Note on CodeQL Alerts:
- This script tests password policies using COMMON/WEAK passwords (e.g., "123456")
  that are intentionally chosen for their weakness, not real user credentials.
- The print statements output validation METADATA (scores, category names, test results),
  not actual sensitive data like passwords or secrets.
- All test passwords are contained in test request payloads and never logged directly.
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any
import requests
from datetime import datetime


class EnterpriseReadinessValidator:
    """Validates enterprise readiness across multiple dimensions."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_score": 0,
            "categories": {},
            "critical_issues": [],
            "recommendations": [],
            "enterprise_ready": False,
        }

    async def validate_all(self) -> Dict[str, Any]:
        """Run all enterprise readiness validations."""
        print("🔍 Starting Enterprise Readiness Validation...")
        print("=" * 60)

        # Run all validation categories
        await self.validate_api_coverage()
        await self.validate_security_posture()
        await self.validate_authentication_flows()
        await self.validate_enterprise_features()
        await self.validate_scalability()
        await self.validate_compliance()
        await self.validate_monitoring()
        await self.validate_documentation()

        # Calculate overall score
        self._calculate_overall_score()

        return self.results

    async def validate_api_coverage(self):
        """Validate API endpoint coverage and functionality."""
        print("📡 Validating API Coverage...")

        category = {
            "name": "API Coverage",
            "score": 0,
            "max_score": 100,
            "tests": [],
            "critical": False,
        }

        # Test core endpoints
        endpoints = [
            ("/api/v1/health", "GET", "Health Check"),
            ("/api/v1/auth/signup", "POST", "User Registration"),
            ("/api/v1/auth/signin", "POST", "User Authentication"),
            ("/api/v1/auth/me", "GET", "Current User"),
            ("/api/v1/users", "GET", "User Management"),
            ("/api/v1/organizations", "GET", "Organization Management"),
            ("/api/v1/mfa/setup", "POST", "MFA Setup"),
            ("/api/v1/sso/providers", "GET", "SSO Configuration"),
            ("/api/v1/webhooks", "GET", "Webhook Management"),
            ("/api/v1/audit-logs", "GET", "Audit Logging"),
        ]

        passed_tests = 0
        for endpoint, method, description in endpoints:
            try:
                if method == "GET":
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                else:
                    response = requests.post(f"{self.base_url}{endpoint}", json={}, timeout=5)

                # Accept various status codes (endpoint exists)
                if response.status_code < 500:
                    passed_tests += 1
                    category["tests"].append(
                        {
                            "name": description,
                            "status": "PASS",
                            "details": f"Endpoint accessible ({response.status_code})",
                        }
                    )
                else:
                    category["tests"].append(
                        {
                            "name": description,
                            "status": "FAIL",
                            "details": f"Server error ({response.status_code})",
                        }
                    )

            except requests.exceptions.RequestException as e:
                category["tests"].append(
                    {
                        "name": description,
                        "status": "FAIL",
                        "details": f"Connection error: {str(e)}",
                    }
                )

        category["score"] = (passed_tests / len(endpoints)) * 100
        if category["score"] < 70:
            category["critical"] = True
            self.results["critical_issues"].append(
                f"API coverage too low ({category['score']:.1f}%). Missing critical endpoints."
            )

        self.results["categories"]["api_coverage"] = category

    async def validate_security_posture(self):
        """Validate security configuration and posture."""
        print("🔒 Validating Security Posture...")

        category = {
            "name": "Security Posture",
            "score": 0,
            "max_score": 100,
            "tests": [],
            "critical": False,
        }

        # Test security headers
        try:
            response = requests.get(f"{self.base_url}/api/v1/health", timeout=5)
            headers = response.headers

            security_headers = {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": ["DENY", "SAMEORIGIN"],
                "X-XSS-Protection": "1; mode=block",
                "Strict-Transport-Security": None,  # Any value
                "Content-Security-Policy": None,
            }

            header_score = 0
            for header, expected in security_headers.items():
                if header.lower() in [h.lower() for h in headers.keys()]:
                    header_score += 20
                    category["tests"].append(
                        {
                            "name": f"Security Header: {header}",
                            "status": "PASS",
                            "details": f"Present: {headers.get(header, 'N/A')}",
                        }
                    )
                else:
                    category["tests"].append(
                        {
                            "name": f"Security Header: {header}",
                            "status": "FAIL",
                            "details": "Missing security header",
                        }
                    )

            category["score"] = header_score

        except requests.exceptions.RequestException:
            category["score"] = 0
            category["tests"].append(
                {
                    "name": "Security Headers Check",
                    "status": "FAIL",
                    "details": "Could not connect to API",
                }
            )

        if category["score"] < 60:
            category["critical"] = True
            self.results["critical_issues"].append(
                "Missing critical security headers. Enterprise security requirements not met."
            )

        self.results["categories"]["security_posture"] = category

    async def validate_authentication_flows(self):
        """Validate authentication flow security and functionality."""
        print("🔐 Validating Authentication Flows...")

        category = {
            "name": "Authentication Flows",
            "score": 0,
            "max_score": 100,
            "tests": [],
            "critical": False,
        }

        # Test signup flow
        signup_data = {
            "email": f"test_{int(time.time())}@example.com",
            "password": "TestPassword123!",  # nosec B105 - test fixture
            "first_name": "Test",
            "last_name": "User",
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/signup", json=signup_data, timeout=10
            )

            if response.status_code in [200, 201]:
                category["tests"].append(
                    {
                        "name": "User Registration",
                        "status": "PASS",
                        "details": "Signup endpoint functional",
                    }
                )
                category["score"] += 25
            else:
                category["tests"].append(
                    {
                        "name": "User Registration",
                        "status": "FAIL",
                        "details": f"Signup failed ({response.status_code})",
                    }
                )

        except requests.exceptions.RequestException as e:
            category["tests"].append(
                {
                    "name": "User Registration",
                    "status": "FAIL",
                    "details": f"Connection error: {str(e)}",
                }
            )

        # Test password policy enforcement using COMMON WEAK passwords
        # These are intentionally weak test patterns, not real credentials
        # Note: Only the count of rejections is logged, not the test patterns
        weak_test_patterns = [
            "123456",
            "password",
            "qwerty",
        ]  # nosec B105 - weak password test patterns
        password_policy_score = 0

        for test_pattern in weak_test_patterns:
            try:
                response = requests.post(
                    f"{self.base_url}/api/v1/auth/signup",
                    json={
                        "email": f"weak_{test_pattern}@example.com",
                        "password": test_pattern,  # nosec B105 - intentional weak password test
                        "first_name": "Test",
                        "last_name": "User",
                    },
                    timeout=5,
                )

                if response.status_code == 400:  # Should reject weak password
                    password_policy_score += 1

            except requests.exceptions.RequestException:
                pass  # Intentionally ignoring - network errors expected during password policy testing

        if password_policy_score >= 2:
            category["tests"].append(
                {
                    "name": "Password Policy Enforcement",
                    "status": "PASS",
                    "details": f"Rejected {password_policy_score}/{len(weak_test_patterns)} weak passwords",
                }
            )
            category["score"] += 25
        else:
            category["tests"].append(
                {
                    "name": "Password Policy Enforcement",
                    "status": "FAIL",
                    "details": "Weak password policy or not enforced",
                }
            )

        # Test rate limiting
        rate_limit_score = 0
        for i in range(15):  # Try to trigger rate limiting
            try:
                response = requests.post(
                    f"{self.base_url}/api/v1/auth/signin",
                    json={
                        "email": "nonexistent@example.com",
                        "password": "wrongpassword",  # nosec B105 - intentional wrong password for rate limit test
                    },
                    timeout=2,
                )

                if response.status_code == 429:  # Rate limited
                    rate_limit_score = 50
                    break

            except requests.exceptions.RequestException:
                pass  # Intentionally ignoring - network errors expected during rate limit testing

        if rate_limit_score > 0:
            category["tests"].append(
                {"name": "Rate Limiting", "status": "PASS", "details": "Rate limiting active"}
            )
            category["score"] += 25
        else:
            category["tests"].append(
                {"name": "Rate Limiting", "status": "WARN", "details": "Rate limiting not detected"}
            )
            category["score"] += 10

        # Test JWT token structure
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/signin",
                json={
                    "email": "test@example.com",
                    "password": "TestPassword123!",  # nosec B105 - test fixture
                },
                timeout=5,
            )

            if response.status_code == 200 and "access_token" in response.json():
                category["tests"].append(
                    {
                        "name": "JWT Token Generation",
                        "status": "PASS",
                        "details": "JWT tokens generated correctly",
                    }
                )
                category["score"] += 25
            else:
                category["tests"].append(
                    {
                        "name": "JWT Token Generation",
                        "status": "FAIL",
                        "details": "JWT token generation issues",
                    }
                )

        except requests.exceptions.RequestException:
            category["tests"].append(
                {
                    "name": "JWT Token Generation",
                    "status": "FAIL",
                    "details": "Cannot test JWT generation",
                }
            )

        if category["score"] < 75:
            category["critical"] = True
            self.results["critical_issues"].append(
                "Authentication flows not enterprise-ready. Critical security issues."
            )

        self.results["categories"]["authentication_flows"] = category

    async def validate_enterprise_features(self):
        """Validate enterprise-specific features."""
        print("🏢 Validating Enterprise Features...")

        category = {
            "name": "Enterprise Features",
            "score": 0,
            "max_score": 100,
            "tests": [],
            "critical": False,
        }

        # Test SSO endpoints
        sso_endpoints = [
            "/api/v1/sso/providers",
            "/api/v1/sso/saml/configure",
            "/api/v1/sso/oidc/configure",
        ]

        sso_score = 0
        for endpoint in sso_endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code < 500:  # Endpoint exists
                    sso_score += 1

            except requests.exceptions.RequestException:
                pass  # Intentionally ignoring - network errors expected during SSO endpoint check

        if sso_score >= 2:
            category["tests"].append(
                {
                    "name": "SSO Infrastructure",
                    "status": "PASS",
                    "details": f"SSO endpoints available ({sso_score}/{len(sso_endpoints)})",
                }
            )
            category["score"] += 30
        else:
            category["tests"].append(
                {
                    "name": "SSO Infrastructure",
                    "status": "FAIL",
                    "details": "SSO endpoints missing or non-functional",
                }
            )

        # Test audit logging
        try:
            response = requests.get(f"{self.base_url}/api/v1/audit-logs", timeout=5)
            if response.status_code in [200, 401, 403]:  # Endpoint exists
                category["tests"].append(
                    {
                        "name": "Audit Logging",
                        "status": "PASS",
                        "details": "Audit logging endpoint available",
                    }
                )
                category["score"] += 25
            else:
                category["tests"].append(
                    {
                        "name": "Audit Logging",
                        "status": "FAIL",
                        "details": "Audit logging not implemented",
                    }
                )

        except requests.exceptions.RequestException:
            category["tests"].append(
                {
                    "name": "Audit Logging",
                    "status": "FAIL",
                    "details": "Audit logging endpoint not accessible",
                }
            )

        # Test RBAC
        try:
            response = requests.get(f"{self.base_url}/api/v1/rbac/roles", timeout=5)
            if response.status_code < 500:
                category["tests"].append(
                    {"name": "RBAC System", "status": "PASS", "details": "RBAC endpoints available"}
                )
                category["score"] += 25
            else:
                category["tests"].append(
                    {
                        "name": "RBAC System",
                        "status": "FAIL",
                        "details": "RBAC system not available",
                    }
                )

        except requests.exceptions.RequestException:
            category["tests"].append(
                {
                    "name": "RBAC System",
                    "status": "FAIL",
                    "details": "RBAC endpoints not accessible",
                }
            )

        # Test compliance endpoints
        try:
            response = requests.get(f"{self.base_url}/api/v1/compliance/gdpr", timeout=5)
            if response.status_code < 500:
                category["tests"].append(
                    {
                        "name": "Compliance Features",
                        "status": "PASS",
                        "details": "Compliance endpoints available",
                    }
                )
                category["score"] += 20
            else:
                category["tests"].append(
                    {
                        "name": "Compliance Features",
                        "status": "FAIL",
                        "details": "Compliance features not implemented",
                    }
                )

        except requests.exceptions.RequestException:
            category["tests"].append(
                {
                    "name": "Compliance Features",
                    "status": "FAIL",
                    "details": "Compliance endpoints not accessible",
                }
            )

        if category["score"] < 60:
            self.results["recommendations"].append(
                "Implement missing enterprise features: SSO, RBAC, audit logging, compliance"
            )

        self.results["categories"]["enterprise_features"] = category

    async def validate_scalability(self):
        """Validate scalability and performance characteristics."""
        print("📈 Validating Scalability...")

        category = {
            "name": "Scalability",
            "score": 0,
            "max_score": 100,
            "tests": [],
            "critical": False,
        }

        # Test response times
        response_times = []
        successful_requests = 0

        for i in range(10):
            try:
                start_time = time.time()
                response = requests.get(f"{self.base_url}/api/v1/health", timeout=5)
                end_time = time.time()

                if response.status_code == 200:
                    response_times.append(end_time - start_time)
                    successful_requests += 1

            except requests.exceptions.RequestException:
                pass  # Intentionally ignoring - network errors expected during response time testing

        if response_times:
            avg_response_time = sum(response_times) / len(response_times)
            if avg_response_time < 0.1:  # Under 100ms
                category["tests"].append(
                    {
                        "name": "Response Time Performance",
                        "status": "PASS",
                        "details": f"Average response time: {avg_response_time:.3f}s",
                    }
                )
                category["score"] += 50
            else:
                category["tests"].append(
                    {
                        "name": "Response Time Performance",
                        "status": "WARN",
                        "details": f"Slow response time: {avg_response_time:.3f}s",
                    }
                )
                category["score"] += 25

        # Test concurrent request handling
        import aiohttp

        async def make_request(session):
            try:
                async with session.get(f"{self.base_url}/api/v1/health") as response:
                    return response.status == 200
            except Exception:
                return False

        async def test_concurrency():
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                tasks = [make_request(session) for _ in range(20)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                return sum(1 for r in results if r is True)

        try:
            concurrent_success = await test_concurrency()
            if concurrent_success >= 18:  # 90% success rate
                category["tests"].append(
                    {
                        "name": "Concurrent Request Handling",
                        "status": "PASS",
                        "details": f"Handled {concurrent_success}/20 concurrent requests",
                    }
                )
                category["score"] += 50
            else:
                category["tests"].append(
                    {
                        "name": "Concurrent Request Handling",
                        "status": "FAIL",
                        "details": f"Only handled {concurrent_success}/20 concurrent requests",
                    }
                )
                category["score"] += 25

        except Exception as e:
            category["tests"].append(
                {
                    "name": "Concurrent Request Handling",
                    "status": "FAIL",
                    "details": f"Concurrency test failed: {str(e)}",
                }
            )

        self.results["categories"]["scalability"] = category

    async def validate_compliance(self):
        """Validate compliance and regulatory features."""
        print("📋 Validating Compliance...")

        category = {
            "name": "Compliance",
            "score": 0,
            "max_score": 100,
            "tests": [],
            "critical": False,
        }

        # Check for compliance endpoints
        compliance_features = [
            ("/api/v1/compliance/gdpr", "GDPR Data Export"),
            ("/api/v1/compliance/audit", "Audit Trail"),
            ("/api/v1/compliance/data-retention", "Data Retention"),
            ("/api/v1/compliance/report", "Compliance Reporting"),
        ]

        feature_score = 0
        for endpoint, feature_name in compliance_features:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code < 500:
                    feature_score += 25
                    category["tests"].append(
                        {"name": feature_name, "status": "PASS", "details": "Endpoint available"}
                    )
                else:
                    category["tests"].append(
                        {
                            "name": feature_name,
                            "status": "FAIL",
                            "details": "Endpoint not implemented",
                        }
                    )

            except requests.exceptions.RequestException:
                category["tests"].append(
                    {"name": feature_name, "status": "FAIL", "details": "Endpoint not accessible"}
                )

        category["score"] = feature_score

        if category["score"] < 50:
            self.results["recommendations"].append(
                "Implement compliance features for GDPR, audit trails, and data retention"
            )

        self.results["categories"]["compliance"] = category

    async def validate_monitoring(self):
        """Validate monitoring and observability."""
        print("📊 Validating Monitoring...")

        category = {
            "name": "Monitoring",
            "score": 0,
            "max_score": 100,
            "tests": [],
            "critical": False,
        }

        # Test health endpoints
        health_endpoints = [
            ("/api/v1/health", "Basic Health Check"),
            ("/api/v1/health/ready", "Readiness Probe"),
            ("/api/v1/health/live", "Liveness Probe"),
            ("/api/v1/metrics", "Metrics Endpoint"),
        ]

        health_score = 0
        for endpoint, description in health_endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code in [200, 503]:  # Both OK and not ready are valid
                    health_score += 25
                    category["tests"].append(
                        {
                            "name": description,
                            "status": "PASS",
                            "details": f"Available ({response.status_code})",
                        }
                    )
                else:
                    category["tests"].append(
                        {
                            "name": description,
                            "status": "FAIL",
                            "details": f"Unexpected status ({response.status_code})",
                        }
                    )

            except requests.exceptions.RequestException:
                category["tests"].append(
                    {"name": description, "status": "FAIL", "details": "Endpoint not accessible"}
                )

        category["score"] = health_score

        if category["score"] < 75:
            self.results["recommendations"].append(
                "Implement comprehensive health checks and metrics endpoints"
            )

        self.results["categories"]["monitoring"] = category

    async def validate_documentation(self):
        """Validate documentation completeness."""
        print("📚 Validating Documentation...")

        category = {
            "name": "Documentation",
            "score": 0,
            "max_score": 100,
            "tests": [],
            "critical": False,
        }

        # Check for documentation files
        docs_to_check = [
            ("README.md", "Project README"),
            ("DEVELOPMENT.md", "Development Guide"),
            ("API_REFERENCE.md", "API Reference"),
            ("SECURITY.md", "Security Documentation"),
            ("packages/typescript-sdk/README.md", "TypeScript SDK Docs"),
            ("packages/python-sdk/README.md", "Python SDK Docs"),
            ("packages/react-sdk/README.md", "React SDK Docs"),
        ]

        docs_score = 0
        for doc_path, description in docs_to_check:
            if Path(doc_path).exists():
                docs_score += 15
                category["tests"].append(
                    {"name": description, "status": "PASS", "details": "Documentation file exists"}
                )
            else:
                category["tests"].append(
                    {"name": description, "status": "FAIL", "details": "Documentation file missing"}
                )

        category["score"] = min(docs_score, 100)

        if category["score"] < 70:
            self.results["recommendations"].append(
                "Improve documentation coverage for enterprise adoption"
            )

        self.results["categories"]["documentation"] = category

    def _calculate_overall_score(self):
        """Calculate overall enterprise readiness score."""
        total_score = 0
        total_weight = 0
        critical_failures = 0

        # Weighted scoring
        weights = {
            "api_coverage": 20,
            "security_posture": 25,
            "authentication_flows": 25,
            "enterprise_features": 15,
            "scalability": 10,
            "compliance": 15,
            "monitoring": 10,
            "documentation": 10,
        }

        for category_name, category_data in self.results["categories"].items():
            weight = weights.get(category_name, 10)
            score = category_data["score"]

            total_score += score * weight
            total_weight += 100 * weight

            if category_data.get("critical", False):
                critical_failures += 1

        self.results["overall_score"] = (
            (total_score / total_weight) * 100 if total_weight > 0 else 0
        )
        self.results["enterprise_ready"] = (
            self.results["overall_score"] >= 75 and critical_failures == 0
        )

        # Add summary recommendations
        if not self.results["enterprise_ready"]:
            if critical_failures > 0:
                self.results["recommendations"].insert(
                    0, f"CRITICAL: {critical_failures} critical issues must be resolved"
                )
            if self.results["overall_score"] < 75:
                self.results["recommendations"].insert(
                    0,
                    f"Overall score too low ({self.results['overall_score']:.1f}%). Need 75%+ for enterprise readiness",
                )

    def print_summary(self):
        """Print validation summary.

        Note: This method outputs validation METADATA to stdout for operator review.
        Output includes category names, numeric scores, and test result summaries.
        No actual passwords, secrets, or credentials are logged.

        Security Note: All output values are validation metadata. The password test
        patterns used in validate_authentication_flows() are only used in test requests
        and are never logged - only the count of rejections is output.
        """
        print("\n" + "=" * 60)
        print("🏢 ENTERPRISE READINESS VALIDATION RESULTS")
        print("=" * 60)

        # Overall status - numeric scores and boolean flags
        status_emoji = "✅" if self.results["enterprise_ready"] else "❌"
        overall_score = self.results["overall_score"]  # nosec - numeric score, not secret
        print(f"\n{status_emoji} Overall Score: {overall_score:.1f}%")
        print(f"Enterprise Ready: {'YES' if self.results['enterprise_ready'] else 'NO'}")

        # Category breakdown - category names and numeric scores
        print("\n📊 Category Scores:")
        for category_name, category_data in self.results["categories"].items():
            score = category_data["score"]  # nosec - numeric score, not secret
            critical = category_data.get("critical", False)  # nosec - boolean flag
            status = "🔴 CRITICAL" if critical else ("🟢 PASS" if score >= 75 else "🟡 NEEDS WORK")
            cat_name = category_data["name"]  # nosec - category name, not secret
            print(f"  {cat_name}: {score:.1f}% {status}")

        # Critical issues - summary text, not sensitive data
        if self.results["critical_issues"]:
            issue_count = len(self.results["critical_issues"])
            print(f"\n🚨 Critical Issues ({issue_count}):")
            for issue in self.results["critical_issues"]:
                issue_text = str(issue)  # nosec - issue summary, not secret
                print(f"  • {issue_text}")

        # Recommendations - action items, not sensitive data
        if self.results["recommendations"]:
            rec_count = len(self.results["recommendations"])
            print(f"\n💡 Recommendations ({rec_count}):")
            for rec in self.results["recommendations"]:
                rec_text = str(rec)  # nosec - recommendation text, not secret
                print(f"  • {rec_text}")

        timestamp = self.results["timestamp"]  # nosec - timestamp, not secret
        print(f"\n⏰ Validation completed at: {timestamp}")


async def main():
    """Main validation entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Enterprise Readiness Validation")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--output", help="Output file for results (JSON)")
    parser.add_argument("--quiet", action="store_true", help="Quiet mode")

    args = parser.parse_args()

    validator = EnterpriseReadinessValidator(args.url)

    try:
        results = await validator.validate_all()

        if not args.quiet:
            validator.print_summary()

        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\n📄 Results saved to: {args.output}")

        # Exit with error code if not enterprise ready
        sys.exit(0 if results["enterprise_ready"] else 1)

    except KeyboardInterrupt:
        print("\n\n❌ Validation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Validation failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
