#!/usr/bin/env python3
"""
Test Health Validation Script
Systematically checks and reports on test suite health
"""

import subprocess
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import time
from collections import defaultdict


class TestHealthValidator:
    """Validates test suite health and provides actionable feedback"""
    
    def __init__(self):
        self.results = defaultdict(dict)
        self.issues = []
        self.fixes_applied = []
        
    def run_validation(self) -> Dict:
        """Run complete validation suite"""
        print("🔍 Test Health Validation Starting...")
        print("=" * 50)
        
        # Step 1: Check dependencies
        self.check_dependencies()
        
        # Step 2: Validate test configuration
        self.validate_configuration()
        
        # Step 3: Run test suites
        self.run_test_suites()
        
        # Step 4: Analyze failures
        self.analyze_failures()
        
        # Step 5: Generate report
        return self.generate_report()
    
    def check_dependencies(self):
        """Check that all test dependencies are installed"""
        print("\n✅ Checking Dependencies...")
        
        required_packages = [
            "pytest",
            "pytest-asyncio", 
            "pytest-cov",
            "httpx",
            "sqlalchemy",
            "aiosqlite"
        ]
        
        for package in required_packages:
            try:
                result = subprocess.run(
                    ["pip", "show", package],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.results["dependencies"][package] = "✅ Installed"
                else:
                    self.results["dependencies"][package] = "❌ Missing"
                    self.issues.append(f"Missing package: {package}")
            except Exception as e:
                self.results["dependencies"][package] = f"❌ Error: {e}"
                
    def validate_configuration(self):
        """Validate test configuration files"""
        print("\n✅ Validating Configuration...")
        
        config_files = [
            "pytest.ini",
            "pyproject.toml",
            "tests/conftest.py"
        ]
        
        for config_file in config_files:
            path = Path(config_file)
            if path.exists():
                self.results["configuration"][config_file] = "✅ Present"
                
                # Check for async configuration
                if config_file == "pytest.ini":
                    content = path.read_text()
                    if "asyncio_mode" in content:
                        self.results["configuration"]["async_mode"] = "✅ Configured"
                    else:
                        self.results["configuration"]["async_mode"] = "⚠️ Not configured"
                        self.issues.append("pytest.ini missing asyncio_mode setting")
            else:
                self.results["configuration"][config_file] = "❌ Missing"
                self.issues.append(f"Missing config file: {config_file}")
                
    def run_test_suites(self):
        """Run different test suites and collect results"""
        print("\n✅ Running Test Suites...")
        
        test_commands = [
            ("Core Tests", ["python", "-m", "pytest", "tests/test_100_coverage.py", "-q", "--tb=no"]),
            ("Unit Tests", ["python", "-m", "pytest", "tests/unit", "-q", "--tb=no", "--maxfail=5"]),
            ("Integration Tests", ["python", "-m", "pytest", "tests/integration", "-q", "--tb=no", "--maxfail=5"])
        ]
        
        for suite_name, command in test_commands:
            print(f"  Running {suite_name}...")
            try:
                env = {
                    "ENVIRONMENT": "test",
                    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
                    "PYTHONPATH": str(Path.cwd())
                }
                
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    env={**subprocess.os.environ, **env},
                    timeout=30
                )
                
                # Parse output for pass/fail counts
                output = result.stdout + result.stderr
                if "passed" in output:
                    # Extract numbers like "42 passed, 5 failed"
                    import re
                    passed = re.search(r"(\d+) passed", output)
                    failed = re.search(r"(\d+) failed", output)
                    skipped = re.search(r"(\d+) skipped", output)
                    
                    passed_count = int(passed.group(1)) if passed else 0
                    failed_count = int(failed.group(1)) if failed else 0
                    skipped_count = int(skipped.group(1)) if skipped else 0
                    
                    self.results["test_suites"][suite_name] = {
                        "passed": passed_count,
                        "failed": failed_count,
                        "skipped": skipped_count,
                        "status": "✅ Pass" if failed_count == 0 else "❌ Fail"
                    }
                    
                    if failed_count > 0:
                        self.issues.append(f"{suite_name}: {failed_count} tests failing")
                else:
                    self.results["test_suites"][suite_name] = {
                        "status": "❌ Error",
                        "error": output[:200]
                    }
                    
            except subprocess.TimeoutExpired:
                self.results["test_suites"][suite_name] = {"status": "⚠️ Timeout"}
            except Exception as e:
                self.results["test_suites"][suite_name] = {"status": f"❌ Error: {e}"}
                
    def analyze_failures(self):
        """Analyze common failure patterns"""
        print("\n✅ Analyzing Failures...")
        
        common_issues = {
            "AsyncMock": "Replace Mock with AsyncMock for async operations",
            "pytest.mark.asyncio": "Add @pytest.mark.asyncio decorator",
            "coroutine was never awaited": "Ensure async functions are awaited",
            "event loop is closed": "Fix event loop configuration in conftest.py"
        }
        
        # Check recent test output for common issues
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "tests/unit", "-q", "--tb=short", "--maxfail=1"],
                capture_output=True,
                text=True,
                env={
                    "ENVIRONMENT": "test",
                    "DATABASE_URL": "sqlite+aiosqlite:///:memory:"
                },
                timeout=10
            )
            
            output = result.stdout + result.stderr
            
            for issue, fix in common_issues.items():
                if issue.lower() in output.lower():
                    self.results["common_issues"][issue] = f"⚠️ Found - Fix: {fix}"
                    self.issues.append(f"Common issue detected: {issue}")
                    
        except Exception:
            pass
            
    def generate_report(self) -> Dict:
        """Generate comprehensive health report"""
        print("\n" + "=" * 50)
        print("📊 TEST HEALTH REPORT")
        print("=" * 50)
        
        # Dependencies
        print("\n📦 Dependencies:")
        for package, status in self.results["dependencies"].items():
            print(f"  {package}: {status}")
            
        # Configuration
        print("\n⚙️ Configuration:")
        for file, status in self.results["configuration"].items():
            print(f"  {file}: {status}")
            
        # Test Suites
        print("\n🧪 Test Suites:")
        for suite, results in self.results["test_suites"].items():
            if isinstance(results, dict) and "passed" in results:
                print(f"  {suite}: {results['status']} (✅ {results['passed']} ❌ {results['failed']} ⏩ {results['skipped']})")
            else:
                print(f"  {suite}: {results.get('status', 'Unknown')}")
                
        # Issues Summary
        if self.issues:
            print("\n⚠️ Issues Found:")
            for issue in self.issues[:10]:  # Show top 10 issues
                print(f"  - {issue}")
                
        # Overall Health Score
        total_tests = sum(
            r.get("passed", 0) + r.get("failed", 0) 
            for r in self.results["test_suites"].values() 
            if isinstance(r, dict)
        )
        passed_tests = sum(
            r.get("passed", 0) 
            for r in self.results["test_suites"].values() 
            if isinstance(r, dict)
        )
        
        if total_tests > 0:
            health_score = (passed_tests / total_tests) * 100
        else:
            health_score = 0
            
        print(f"\n📈 Overall Health Score: {health_score:.1f}%")
        
        if health_score >= 90:
            print("✅ Test suite is healthy!")
        elif health_score >= 70:
            print("⚠️ Test suite needs attention")
        else:
            print("❌ Test suite requires immediate fixes")
            
        # Recommendations
        print("\n💡 Recommendations:")
        if health_score < 100:
            print("  1. Fix failing tests using async fixtures")
            print("  2. Add @pytest.mark.asyncio to async test functions")
            print("  3. Replace Mock with AsyncMock for async operations")
            print("  4. Ensure pytest-asyncio is installed and configured")
            print("  5. Run: ./scripts/fix-and-run-tests.sh")
            
        return {
            "health_score": health_score,
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "issues": self.issues,
            "results": dict(self.results)
        }


if __name__ == "__main__":
    validator = TestHealthValidator()
    report = validator.run_validation()
    
    # Exit with appropriate code
    if report["health_score"] >= 90:
        sys.exit(0)
    else:
        sys.exit(1)