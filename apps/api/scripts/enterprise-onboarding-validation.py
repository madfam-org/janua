#!/usr/bin/env python3
"""
Enterprise Customer Onboarding Validation
Validates readiness for enterprise customer onboarding process
"""
import asyncio
import json
import requests
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


class EnterpriseOnboardingValidator:
    """Validates enterprise customer onboarding readiness."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "onboarding_readiness": False,
            "readiness_score": 0,
            "categories": {},
            "blockers": [],
            "missing_features": [],
            "documentation_gaps": [],
            "recommendations": []
        }

    async def validate_onboarding_readiness(self) -> Dict[str, Any]:
        """Validate enterprise onboarding readiness."""
        print("🏢 Starting Enterprise Onboarding Readiness Validation...")
        print("=" * 60)

        await self.validate_sdk_ecosystem()
        await self.validate_documentation_completeness()
        await self.validate_enterprise_features()
        await self.validate_security_requirements()
        await self.validate_deployment_options()
        await self.validate_integration_capabilities()
        await self.validate_support_infrastructure()
        await self.validate_compliance_readiness()

        self._calculate_readiness()
        return self.results

    async def validate_sdk_ecosystem(self):
        """Validate SDK ecosystem completeness."""
        print("🛠️  Validating SDK Ecosystem...")

        category = {
            "name": "SDK Ecosystem",
            "score": 0,
            "items": [],
            "required_for_enterprise": True
        }

        # Check for SDK packages
        sdk_packages = [
            ("packages/typescript-sdk", "TypeScript/JavaScript SDK"),
            ("packages/python-sdk", "Python SDK"),
            ("packages/react-sdk", "React SDK"),
            ("packages/vue-sdk", "Vue SDK"),
            ("packages/nextjs-sdk", "Next.js SDK"),
            ("packages/react-native-sdk", "React Native SDK"),
            ("packages/go-sdk", "Go SDK"),
            ("packages/flutter-sdk", "Flutter SDK")
        ]

        available_sdks = 0
        for sdk_path, sdk_name in sdk_packages:
            if Path(sdk_path).exists():
                available_sdks += 1
                category["items"].append({
                    "name": sdk_name,
                    "status": "AVAILABLE",
                    "path": sdk_path
                })

                # Check for README
                readme_path = Path(sdk_path) / "README.md"
                if readme_path.exists():
                    category["items"].append({
                        "name": f"{sdk_name} Documentation",
                        "status": "AVAILABLE",
                        "path": str(readme_path)
                    })
                else:
                    self.results["documentation_gaps"].append(f"Missing README for {sdk_name}")

            else:
                category["items"].append({
                    "name": sdk_name,
                    "status": "MISSING",
                    "path": sdk_path
                })

        category["score"] = (available_sdks / len(sdk_packages)) * 100

        if category["score"] < 70:
            self.results["blockers"].append(
                f"Insufficient SDK coverage ({available_sdks}/{len(sdk_packages)}). Need at least 70% for enterprise."
            )

        self.results["categories"]["sdk_ecosystem"] = category

    async def validate_documentation_completeness(self):
        """Validate documentation completeness for enterprise customers."""
        print("📚 Validating Documentation Completeness...")

        category = {
            "name": "Documentation",
            "score": 0,
            "items": [],
            "required_for_enterprise": True
        }

        # Enterprise documentation requirements
        required_docs = [
            ("README.md", "Project Overview"),
            ("DEVELOPMENT.md", "Development Guide"),
            ("API_REFERENCE.md", "API Reference"),
            ("SECURITY.md", "Security Documentation"),
            ("docs/enterprise-deployment.md", "Enterprise Deployment Guide"),
            ("docs/enterprise-features.md", "Enterprise Features Guide"),
            ("docs/security-configuration.md", "Security Configuration"),
            ("docs/compliance.md", "Compliance Guide"),
            ("docs/integration-examples.md", "Integration Examples"),
            ("docs/troubleshooting.md", "Troubleshooting Guide")
        ]

        available_docs = 0
        for doc_path, doc_name in required_docs:
            if Path(doc_path).exists():
                available_docs += 1
                category["items"].append({
                    "name": doc_name,
                    "status": "AVAILABLE",
                    "path": doc_path
                })

                # Check document quality (basic check for length)
                try:
                    content = Path(doc_path).read_text()
                    if len(content) < 500:  # Very short document
                        self.results["documentation_gaps"].append(
                            f"{doc_name} appears incomplete (< 500 characters)"
                        )
                except Exception:
                    pass

            else:
                category["items"].append({
                    "name": doc_name,
                    "status": "MISSING",
                    "path": doc_path
                })
                self.results["documentation_gaps"].append(f"Missing: {doc_name}")

        category["score"] = (available_docs / len(required_docs)) * 100

        if category["score"] < 60:
            self.results["blockers"].append(
                "Documentation insufficient for enterprise customers. Need comprehensive guides."
            )

        self.results["categories"]["documentation"] = category

    async def validate_enterprise_features(self):
        """Validate enterprise feature availability."""
        print("🏢 Validating Enterprise Features...")

        category = {
            "name": "Enterprise Features",
            "score": 0,
            "items": [],
            "required_for_enterprise": True
        }

        # Test enterprise feature endpoints
        enterprise_features = [
            ("/api/v1/sso/providers", "SSO Providers"),
            ("/api/v1/sso/saml/configure", "SAML SSO"),
            ("/api/v1/sso/oidc/configure", "OIDC SSO"),
            ("/api/v1/rbac/roles", "Role-Based Access Control"),
            ("/api/v1/audit-logs", "Audit Logging"),
            ("/api/v1/organizations", "Multi-tenant Organizations"),
            ("/api/v1/compliance/gdpr", "GDPR Compliance"),
            ("/api/v1/webhooks", "Webhook Management"),
            ("/api/v1/admin", "Admin Console"),
            ("/api/v1/policies", "Security Policies")
        ]

        available_features = 0
        for endpoint, feature_name in enterprise_features:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code < 500:  # Endpoint exists
                    available_features += 1
                    category["items"].append({
                        "name": feature_name,
                        "status": "AVAILABLE",
                        "endpoint": endpoint,
                        "response_code": response.status_code
                    })
                else:
                    category["items"].append({
                        "name": feature_name,
                        "status": "ERROR",
                        "endpoint": endpoint,
                        "response_code": response.status_code
                    })
                    self.results["missing_features"].append(feature_name)

            except requests.exceptions.RequestException:
                category["items"].append({
                    "name": feature_name,
                    "status": "UNAVAILABLE",
                    "endpoint": endpoint
                })
                self.results["missing_features"].append(feature_name)

        category["score"] = (available_features / len(enterprise_features)) * 100

        if category["score"] < 80:
            self.results["blockers"].append(
                f"Missing critical enterprise features. Need {len(enterprise_features) - available_features} more features."
            )

        self.results["categories"]["enterprise_features"] = category

    async def validate_security_requirements(self):
        """Validate security requirements for enterprise."""
        print("🔐 Validating Security Requirements...")

        category = {
            "name": "Security Requirements",
            "score": 0,
            "items": [],
            "required_for_enterprise": True
        }

        security_checks = [
            ("HTTPS Enforcement", self._check_https),
            ("Security Headers", self._check_security_headers),
            ("Authentication Security", self._check_auth_security),
            ("Rate Limiting", self._check_rate_limiting),
            ("Input Validation", self._check_input_validation)
        ]

        passed_checks = 0
        for check_name, check_func in security_checks:
            try:
                result = await check_func()
                if result["passed"]:
                    passed_checks += 1
                    category["items"].append({
                        "name": check_name,
                        "status": "PASS",
                        "details": result.get("details", "")
                    })
                else:
                    category["items"].append({
                        "name": check_name,
                        "status": "FAIL",
                        "details": result.get("details", "")
                    })

            except Exception as e:
                category["items"].append({
                    "name": check_name,
                    "status": "ERROR",
                    "details": str(e)
                })

        category["score"] = (passed_checks / len(security_checks)) * 100

        if category["score"] < 90:
            self.results["blockers"].append(
                "Security requirements not met for enterprise deployment."
            )

        self.results["categories"]["security"] = category

    async def _check_https(self) -> Dict[str, Any]:
        """Check HTTPS enforcement."""
        if self.base_url.startswith("https://"):
            return {"passed": True, "details": "Using HTTPS"}
        else:
            return {"passed": False, "details": "Not using HTTPS - required for enterprise"}

    async def _check_security_headers(self) -> Dict[str, Any]:
        """Check security headers."""
        try:
            response = requests.get(f"{self.base_url}/api/v1/health", timeout=5)
            headers = response.headers

            required_headers = [
                "X-Content-Type-Options",
                "X-Frame-Options",
                "X-XSS-Protection"
            ]

            missing_headers = [h for h in required_headers if h not in headers]

            if not missing_headers:
                return {"passed": True, "details": "All security headers present"}
            else:
                return {
                    "passed": False,
                    "details": f"Missing headers: {', '.join(missing_headers)}"
                }

        except Exception:
            return {"passed": False, "details": "Could not check security headers"}

    async def _check_auth_security(self) -> Dict[str, Any]:
        """Check authentication security."""
        # Test weak password rejection
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/signup",
                json={
                    "email": "test_weak@example.com",
                    "password": "123456",
                    "first_name": "Test",
                    "last_name": "User"
                },
                timeout=5
            )

            if response.status_code == 400:  # Weak password rejected
                return {"passed": True, "details": "Password policy enforced"}
            else:
                return {"passed": False, "details": "Weak passwords accepted"}

        except Exception:
            return {"passed": False, "details": "Could not test authentication"}

    async def _check_rate_limiting(self) -> Dict[str, Any]:
        """Check rate limiting."""
        # Make multiple requests to test rate limiting
        try:
            for i in range(20):
                response = requests.post(
                    f"{self.base_url}/api/v1/auth/signin",
                    json={"email": "test@example.com", "password": "wrong"},
                    timeout=2
                )

                if response.status_code == 429:  # Rate limited
                    return {"passed": True, "details": "Rate limiting active"}

            return {"passed": False, "details": "No rate limiting detected"}

        except Exception:
            return {"passed": False, "details": "Could not test rate limiting"}

    async def _check_input_validation(self) -> Dict[str, Any]:
        """Check input validation."""
        # Test basic SQL injection protection
        try:
            response = requests.post(
                f"{self.base_url}/api/v1/auth/signin",
                json={
                    "email": "'; DROP TABLE users; --",
                    "password": "password"
                },
                timeout=5
            )

            # Should not cause server error
            if response.status_code != 500:
                return {"passed": True, "details": "Input validation working"}
            else:
                return {"passed": False, "details": "Possible SQL injection vulnerability"}

        except Exception:
            return {"passed": False, "details": "Could not test input validation"}

    async def validate_deployment_options(self):
        """Validate deployment options for enterprise."""
        print("🚀 Validating Deployment Options...")

        category = {
            "name": "Deployment Options",
            "score": 0,
            "items": [],
            "required_for_enterprise": False
        }

        deployment_options = [
            ("Dockerfile", "Docker containerization"),
            ("docker-compose.yml", "Docker Compose"),
            ("kubernetes", "Kubernetes manifests"),
            ("railway.json", "Railway deployment"),
            ("requirements.txt", "Python dependencies"),
            ("package.json", "Node.js dependencies")
        ]

        available_options = 0
        for file_path, option_name in deployment_options:
            if Path(file_path).exists() or Path(f"deployment/{file_path}").exists():
                available_options += 1
                category["items"].append({
                    "name": option_name,
                    "status": "AVAILABLE"
                })
            else:
                category["items"].append({
                    "name": option_name,
                    "status": "MISSING"
                })

        category["score"] = (available_options / len(deployment_options)) * 100

        if category["score"] < 50:
            self.results["recommendations"].append(
                "Add more deployment options for enterprise flexibility"
            )

        self.results["categories"]["deployment"] = category

    async def validate_integration_capabilities(self):
        """Validate integration capabilities."""
        print("🔗 Validating Integration Capabilities...")

        category = {
            "name": "Integration Capabilities",
            "score": 0,
            "items": [],
            "required_for_enterprise": True
        }

        # Check webhook capabilities
        try:
            response = requests.get(f"{self.base_url}/api/v1/webhooks", timeout=5)
            if response.status_code < 500:
                category["items"].append({
                    "name": "Webhook Support",
                    "status": "AVAILABLE"
                })
                category["score"] += 25
        except Exception:
            category["items"].append({
                "name": "Webhook Support",
                "status": "UNAVAILABLE"
            })

        # Check API versioning
        try:
            response = requests.get(f"{self.base_url}/api/v1/health", timeout=5)
            if response.status_code == 200:
                category["items"].append({
                    "name": "API Versioning",
                    "status": "AVAILABLE"
                })
                category["score"] += 25
        except Exception:
            pass

        # Check GraphQL support
        try:
            response = requests.post(f"{self.base_url}/api/v1/graphql", timeout=5)
            if response.status_code < 500:
                category["items"].append({
                    "name": "GraphQL Support",
                    "status": "AVAILABLE"
                })
                category["score"] += 25
        except Exception:
            category["items"].append({
                "name": "GraphQL Support",
                "status": "UNAVAILABLE"
            })

        # Check SCIM provisioning
        try:
            response = requests.get(f"{self.base_url}/api/v1/scim/users", timeout=5)
            if response.status_code < 500:
                category["items"].append({
                    "name": "SCIM Provisioning",
                    "status": "AVAILABLE"
                })
                category["score"] += 25
        except Exception:
            category["items"].append({
                "name": "SCIM Provisioning",
                "status": "UNAVAILABLE"
            })

        if category["score"] < 75:
            self.results["missing_features"].append("Integration capabilities insufficient")

        self.results["categories"]["integration"] = category

    async def validate_support_infrastructure(self):
        """Validate support infrastructure readiness."""
        print("🛟 Validating Support Infrastructure...")

        category = {
            "name": "Support Infrastructure",
            "score": 0,
            "items": [],
            "required_for_enterprise": True
        }

        # Check monitoring capabilities
        try:
            response = requests.get(f"{self.base_url}/api/v1/health", timeout=5)
            if response.status_code == 200:
                category["items"].append({
                    "name": "Health Monitoring",
                    "status": "AVAILABLE"
                })
                category["score"] += 20

                # Check health details
                data = response.json()
                if isinstance(data, dict) and len(data) > 2:
                    category["score"] += 10

        except Exception:
            category["items"].append({
                "name": "Health Monitoring",
                "status": "UNAVAILABLE"
            })

        # Check metrics endpoint
        try:
            response = requests.get(f"{self.base_url}/api/v1/metrics", timeout=5)
            if response.status_code == 200:
                category["items"].append({
                    "name": "Metrics Endpoint",
                    "status": "AVAILABLE"
                })
                category["score"] += 20
        except Exception:
            category["items"].append({
                "name": "Metrics Endpoint",
                "status": "UNAVAILABLE"
            })

        # Check error tracking setup
        if Path("sentry.properties").exists() or "SENTRY_DSN" in str(Path(".")):
            category["items"].append({
                "name": "Error Tracking",
                "status": "CONFIGURED"
            })
            category["score"] += 20
        else:
            category["items"].append({
                "name": "Error Tracking",
                "status": "NOT_CONFIGURED"
            })

        # Check logging configuration
        if Path("logging.conf").exists() or Path("logs").exists():
            category["items"].append({
                "name": "Structured Logging",
                "status": "CONFIGURED"
            })
            category["score"] += 15
        else:
            category["items"].append({
                "name": "Structured Logging",
                "status": "NOT_CONFIGURED"
            })

        # Check documentation for support
        support_docs = ["docs/troubleshooting.md", "docs/support.md", "SUPPORT.md"]
        support_doc_exists = any(Path(doc).exists() for doc in support_docs)

        if support_doc_exists:
            category["items"].append({
                "name": "Support Documentation",
                "status": "AVAILABLE"
            })
            category["score"] += 15
        else:
            category["items"].append({
                "name": "Support Documentation",
                "status": "MISSING"
            })

        if category["score"] < 70:
            self.results["blockers"].append(
                "Support infrastructure insufficient for enterprise customers"
            )

        self.results["categories"]["support"] = category

    async def validate_compliance_readiness(self):
        """Validate compliance readiness."""
        print("📋 Validating Compliance Readiness...")

        category = {
            "name": "Compliance Readiness",
            "score": 0,
            "items": [],
            "required_for_enterprise": True
        }

        # Check GDPR endpoints
        gdpr_endpoints = [
            "/api/v1/compliance/gdpr",
            "/api/v1/compliance/export-data",
            "/api/v1/compliance/delete-data"
        ]

        gdpr_score = 0
        for endpoint in gdpr_endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                if response.status_code < 500:
                    gdpr_score += 1
            except Exception:
                pass

        if gdpr_score >= 2:
            category["items"].append({
                "name": "GDPR Compliance",
                "status": "IMPLEMENTED"
            })
            category["score"] += 30
        else:
            category["items"].append({
                "name": "GDPR Compliance",
                "status": "NOT_IMPLEMENTED"
            })

        # Check audit logging
        try:
            response = requests.get(f"{self.base_url}/api/v1/audit-logs", timeout=5)
            if response.status_code < 500:
                category["items"].append({
                    "name": "Audit Logging",
                    "status": "IMPLEMENTED"
                })
                category["score"] += 35
        except Exception:
            category["items"].append({
                "name": "Audit Logging",
                "status": "NOT_IMPLEMENTED"
            })

        # Check data retention policies
        try:
            response = requests.get(f"{self.base_url}/api/v1/compliance/data-retention", timeout=5)
            if response.status_code < 500:
                category["items"].append({
                    "name": "Data Retention Policies",
                    "status": "IMPLEMENTED"
                })
                category["score"] += 35
        except Exception:
            category["items"].append({
                "name": "Data Retention Policies",
                "status": "NOT_IMPLEMENTED"
            })

        if category["score"] < 60:
            self.results["blockers"].append(
                "Compliance features insufficient for enterprise requirements"
            )

        self.results["categories"]["compliance"] = category

    def _calculate_readiness(self):
        """Calculate overall onboarding readiness."""
        required_categories = [
            cat for cat in self.results["categories"].values()
            if cat.get("required_for_enterprise", False)
        ]

        if not required_categories:
            self.results["readiness_score"] = 0
            return

        total_score = sum(cat["score"] for cat in required_categories)
        avg_score = total_score / len(required_categories)

        self.results["readiness_score"] = avg_score

        # Enterprise readiness requires 75% overall and no critical blockers
        self.results["onboarding_readiness"] = (
            avg_score >= 75 and len(self.results["blockers"]) == 0
        )

        # Add recommendations based on gaps
        if not self.results["onboarding_readiness"]:
            if avg_score < 75:
                self.results["recommendations"].append(
                    f"Increase overall readiness score from {avg_score:.1f}% to 75%+"
                )

            if self.results["blockers"]:
                self.results["recommendations"].append(
                    "Resolve all critical blockers before enterprise onboarding"
                )

    def print_summary(self):
        """Print onboarding readiness summary."""
        print("\n" + "=" * 60)
        print("🏢 ENTERPRISE ONBOARDING READINESS RESULTS")
        print("=" * 60)

        # Overall status
        status_emoji = "✅" if self.results["onboarding_readiness"] else "❌"
        print(f"\n{status_emoji} Onboarding Ready: {'YES' if self.results['onboarding_readiness'] else 'NO'}")
        print(f"📊 Readiness Score: {self.results['readiness_score']:.1f}%")

        # Category breakdown
        print(f"\n📊 Category Scores:")
        for category_name, category_data in self.results["categories"].items():
            score = category_data["score"]
            required = "🔴 REQUIRED" if category_data.get("required_for_enterprise") else "🟡 OPTIONAL"
            print(f"  {category_data['name']}: {score:.1f}% {required}")

        # Blockers
        if self.results["blockers"]:
            print(f"\n🚨 Critical Blockers ({len(self.results['blockers'])}):")
            for blocker in self.results["blockers"]:
                print(f"  • {blocker}")

        # Missing features
        if self.results["missing_features"]:
            print(f"\n❌ Missing Features ({len(self.results['missing_features'])}):")
            for feature in self.results["missing_features"]:
                print(f"  • {feature}")

        # Documentation gaps
        if self.results["documentation_gaps"]:
            print(f"\n📚 Documentation Gaps ({len(self.results['documentation_gaps'])}):")
            for gap in self.results["documentation_gaps"]:
                print(f"  • {gap}")

        # Recommendations
        if self.results["recommendations"]:
            print(f"\n💡 Recommendations ({len(self.results['recommendations'])}):")
            for rec in self.results["recommendations"]:
                print(f"  • {rec}")

        print(f"\n⏰ Validation completed at: {self.results['timestamp']}")


async def main():
    """Main validation entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Enterprise Onboarding Readiness Validation")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--output", help="Output file for results (JSON)")

    args = parser.parse_args()

    validator = EnterpriseOnboardingValidator(args.url)

    try:
        results = await validator.validate_onboarding_readiness()
        validator.print_summary()

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"\n📄 Results saved to: {args.output}")

        # Exit with error if not ready for onboarding
        sys.exit(0 if results["onboarding_readiness"] else 1)

    except KeyboardInterrupt:
        print("\n\n❌ Validation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Validation failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    import sys
    asyncio.run(main())