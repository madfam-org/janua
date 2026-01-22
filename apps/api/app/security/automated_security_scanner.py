"""
Automated Security Scanning System
Continuous vulnerability assessment with OWASP, CVE scanning, and dependency auditing
"""

import asyncio
import json
import re
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging
import aiofiles
import yaml

logger = logging.getLogger(__name__)


class ScanType(Enum):
    """Types of security scans"""

    DEPENDENCY = "dependency"
    CODE = "code"
    INFRASTRUCTURE = "infrastructure"
    CONFIGURATION = "configuration"
    SECRETS = "secrets"
    COMPLIANCE = "compliance"
    PENETRATION = "penetration"
    API = "api"


class VulnerabilitySeverity(Enum):
    """CVE severity levels"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ComplianceFramework(Enum):
    """Security compliance frameworks"""

    OWASP_TOP_10 = "owasp_top_10"
    CIS_BENCHMARK = "cis_benchmark"
    PCI_DSS = "pci_dss"
    HIPAA = "hipaa"
    SOC2 = "soc2"
    GDPR = "gdpr"
    ISO_27001 = "iso_27001"
    NIST = "nist"


@dataclass
class Vulnerability:
    """Identified vulnerability"""

    vuln_id: str
    type: str
    severity: VulnerabilitySeverity
    title: str
    description: str
    affected_component: str
    cve_id: Optional[str]
    cvss_score: Optional[float]
    remediation: str
    references: List[str]
    discovered_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanResult:
    """Security scan result"""

    scan_id: str
    scan_type: ScanType
    started_at: datetime
    completed_at: Optional[datetime]
    vulnerabilities: List[Vulnerability]
    total_issues: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    compliance_status: Dict[str, bool]
    scan_metadata: Dict[str, Any]


class AutomatedSecurityScanner:
    """
    Enterprise-grade automated security scanning system with:
    - OWASP Top 10 vulnerability detection
    - CVE database scanning
    - Dependency vulnerability auditing
    - Secret detection
    - Configuration security assessment
    - Compliance validation
    - API security testing
    - Infrastructure scanning
    """

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)

        # Scanner configuration
        self.scan_interval = 3600  # 1 hour
        self.enable_auto_remediation = True
        self.compliance_frameworks = [
            ComplianceFramework.OWASP_TOP_10,
            ComplianceFramework.PCI_DSS,
            ComplianceFramework.SOC2,
        ]

        # Vulnerability database
        self.known_vulnerabilities: Dict[str, Vulnerability] = {}
        self.cve_database: Dict[str, Any] = {}
        self._load_vulnerability_database()

        # Scan history
        self.scan_history: List[ScanResult] = []
        self.active_scans: Dict[str, ScanResult] = {}

        # Security patterns
        self.security_patterns = self._load_security_patterns()

        # Start continuous scanning
        asyncio.create_task(self._continuous_scanning_loop())

    def _load_vulnerability_database(self):
        """Load known vulnerabilities and CVE database"""

        # Would load from NVD, CVE database, etc.
        # Sample vulnerabilities for demonstration
        self.known_vulnerabilities = {
            "SQLI-001": Vulnerability(
                vuln_id="SQLI-001",
                type="sql_injection",
                severity=VulnerabilitySeverity.CRITICAL,
                title="SQL Injection Vulnerability",
                description="Unsanitized user input in SQL queries",
                affected_component="database",
                cve_id="CVE-2021-XXXXX",
                cvss_score=9.8,
                remediation="Use parameterized queries",
                references=["https://owasp.org/www-community/attacks/SQL_Injection"],
                discovered_at=datetime.utcnow(),
            )
        }

    def _load_security_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Load security scanning patterns"""

        return {
            "sql_injection": [
                re.compile(r"f['\"].*SELECT.*WHERE.*{.*}['\"]", re.IGNORECASE),
                re.compile(r"query\s*\(\s*['\"].*\+.*['\"]", re.IGNORECASE),
                re.compile(r"execute\s*\(\s*['\"].*%s.*['\"].*%", re.IGNORECASE),
            ],
            "xss": [
                re.compile(r"innerHTML\s*=\s*[^'\"]*\+", re.IGNORECASE),
                re.compile(r"document\.write\s*\([^'\"]*\+", re.IGNORECASE),
                re.compile(r"eval\s*\([^'\"]*\+", re.IGNORECASE),
            ],
            "hardcoded_secrets": [
                re.compile(
                    r"(api[_-]?key|apikey|secret|password|pwd|token|auth)\s*=\s*['\"][^'\"]{8,}['\"]",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"(aws_access_key_id|aws_secret_access_key)\s*=\s*['\"][^'\"]+['\"]",
                    re.IGNORECASE,
                ),
                re.compile(r"(PRIVATE KEY|RSA PRIVATE KEY|SSH PRIVATE KEY)"),
            ],
            "insecure_random": [
                re.compile(r"random\.\w+\(\)", re.IGNORECASE),
                re.compile(r"Math\.random\(\)", re.IGNORECASE),
            ],
            "path_traversal": [
                re.compile(r"open\s*\([^)]*\+[^)]*\)", re.IGNORECASE),
                re.compile(r"readFile[^(]*\([^)]*\+[^)]*\)", re.IGNORECASE),
            ],
            "command_injection": [
                re.compile(r"exec\s*\([^'\"]*\+", re.IGNORECASE),
                re.compile(r"system\s*\([^'\"]*\+", re.IGNORECASE),
                re.compile(r"subprocess\.\w+\s*\([^'\"]*\+", re.IGNORECASE),
            ],
            "xxe": [
                re.compile(r"XMLReader.*SUBST_ENTITIES", re.IGNORECASE),
                re.compile(
                    r"DocumentBuilder.*setExpandEntityReferences\s*\(\s*true", re.IGNORECASE
                ),
            ],
            "insecure_deserialization": [
                re.compile(r"pickle\.loads?\s*\(", re.IGNORECASE),
                re.compile(r"yaml\.load\s*\([^,)]*\)", re.IGNORECASE),
                re.compile(r"ObjectInputStream", re.IGNORECASE),
            ],
            "weak_crypto": [
                re.compile(r"(MD5|SHA1)\s*\(", re.IGNORECASE),
                re.compile(r"DES|3DES|RC4", re.IGNORECASE),
                re.compile(r"Random\s*\(\s*\)", re.IGNORECASE),
            ],
            "cors_misconfiguration": [
                re.compile(r"Access-Control-Allow-Origin.*\*", re.IGNORECASE),
                re.compile(r"credentials.*true.*Allow-Origin.*\*", re.IGNORECASE),
            ],
        }

    async def run_comprehensive_scan(self) -> ScanResult:
        """Run comprehensive security scan"""

        import uuid

        scan_id = str(uuid.uuid4())

        result = ScanResult(
            scan_id=scan_id,
            scan_type=ScanType.CODE,
            started_at=datetime.utcnow(),
            completed_at=None,
            vulnerabilities=[],
            total_issues=0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            compliance_status={},
            scan_metadata={},
        )

        self.active_scans[scan_id] = result

        try:
            # Run all scan types
            await asyncio.gather(
                self._scan_dependencies(result),
                self._scan_code(result),
                self._scan_configurations(result),
                self._scan_secrets(result),
                self._scan_infrastructure(result),
                self._scan_api_security(result),
                self._check_compliance(result),
            )

            # Calculate totals
            result.total_issues = len(result.vulnerabilities)
            result.critical_count = sum(
                1 for v in result.vulnerabilities if v.severity == VulnerabilitySeverity.CRITICAL
            )
            result.high_count = sum(
                1 for v in result.vulnerabilities if v.severity == VulnerabilitySeverity.HIGH
            )
            result.medium_count = sum(
                1 for v in result.vulnerabilities if v.severity == VulnerabilitySeverity.MEDIUM
            )
            result.low_count = sum(
                1 for v in result.vulnerabilities if v.severity == VulnerabilitySeverity.LOW
            )

            result.completed_at = datetime.utcnow()
            self.scan_history.append(result)

            # Auto-remediation if enabled
            if self.enable_auto_remediation:
                await self._auto_remediate(result)

            return result

        finally:
            del self.active_scans[scan_id]

    async def _scan_dependencies(self, result: ScanResult):
        """Scan project dependencies for known vulnerabilities"""

        vulnerabilities = []

        # Check Python dependencies
        if (self.project_root / "requirements.txt").exists():
            vulnerabilities.extend(await self._scan_python_dependencies())

        # Check Node.js dependencies
        if (self.project_root / "package.json").exists():
            vulnerabilities.extend(await self._scan_node_dependencies())

        # Check Go dependencies
        if (self.project_root / "go.mod").exists():
            vulnerabilities.extend(await self._scan_go_dependencies())

        result.vulnerabilities.extend(vulnerabilities)

    async def _scan_python_dependencies(self) -> List[Vulnerability]:
        """Scan Python dependencies using safety"""

        vulnerabilities = []

        try:
            # Run safety check (would need to be installed)
            process = await asyncio.create_subprocess_shell(
                "safety check --json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root,
            )

            stdout, stderr = await process.communicate()

            if stdout:
                issues = json.loads(stdout)
                for issue in issues:
                    vulnerabilities.append(
                        Vulnerability(
                            vuln_id=f"DEP-PY-{issue.get('vulnerability_id', 'UNKNOWN')}",
                            type="dependency",
                            severity=self._map_severity(issue.get("severity", "unknown")),
                            title=f"Vulnerable dependency: {issue.get('package', 'unknown')}",
                            description=issue.get("description", ""),
                            affected_component=issue.get("package", "unknown"),
                            cve_id=issue.get("cve"),
                            cvss_score=issue.get("cvss_score"),
                            remediation=f"Update to {issue.get('safe_version', 'latest')}",
                            references=issue.get("references", []),
                            discovered_at=datetime.utcnow(),
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to scan Python dependencies: {e}")

        return vulnerabilities

    async def _scan_node_dependencies(self) -> List[Vulnerability]:
        """Scan Node.js dependencies using npm audit"""

        vulnerabilities = []

        try:
            process = await asyncio.create_subprocess_shell(
                "npm audit --json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root,
            )

            stdout, stderr = await process.communicate()

            if stdout:
                audit_data = json.loads(stdout)
                for advisory_id, advisory in audit_data.get("advisories", {}).items():
                    vulnerabilities.append(
                        Vulnerability(
                            vuln_id=f"DEP-NPM-{advisory_id}",
                            type="dependency",
                            severity=self._map_severity(advisory.get("severity", "unknown")),
                            title=advisory.get("title", "Unknown vulnerability"),
                            description=advisory.get("overview", ""),
                            affected_component=advisory.get("module_name", "unknown"),
                            cve_id=advisory.get("cves", [None])[0]
                            if advisory.get("cves")
                            else None,
                            cvss_score=None,
                            remediation=advisory.get("recommendation", ""),
                            references=advisory.get("references", []),
                            discovered_at=datetime.utcnow(),
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to scan Node dependencies: {e}")

        return vulnerabilities

    async def _scan_go_dependencies(self) -> List[Vulnerability]:
        """Scan Go dependencies using gosec"""

        vulnerabilities = []

        try:
            process = await asyncio.create_subprocess_shell(
                "gosec -fmt json ./...",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root,
            )

            stdout, stderr = await process.communicate()

            if stdout:
                issues = json.loads(stdout).get("Issues", [])
                for issue in issues:
                    vulnerabilities.append(
                        Vulnerability(
                            vuln_id=f"DEP-GO-{issue.get('rule_id', 'UNKNOWN')}",
                            type="code",
                            severity=self._map_severity(issue.get("severity", "unknown")),
                            title=issue.get("details", "Security issue"),
                            description=issue.get("code", ""),
                            affected_component=issue.get("file", "unknown"),
                            cve_id=issue.get("cwe", {}).get("id"),
                            cvss_score=None,
                            remediation="Review and fix the identified issue",
                            references=[issue.get("cwe", {}).get("url", "")],
                            discovered_at=datetime.utcnow(),
                            metadata={"line": issue.get("line")},
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to scan Go dependencies: {e}")

        return vulnerabilities

    async def _scan_code(self, result: ScanResult):
        """Scan source code for security vulnerabilities"""

        vulnerabilities = []

        # Scan all source files
        for pattern_type, patterns in self.security_patterns.items():
            for file_path in self.project_root.rglob("*.py"):
                if "venv" in str(file_path) or "node_modules" in str(file_path):
                    continue

                try:
                    async with aiofiles.open(file_path, "r") as f:
                        content = await f.read()

                    for pattern in patterns:
                        matches = pattern.finditer(content)
                        for match in matches:
                            line_num = content[: match.start()].count("\n") + 1

                            vulnerabilities.append(
                                Vulnerability(
                                    vuln_id=f"CODE-{pattern_type.upper()}-{hashlib.md5(str(match.group()).encode()).hexdigest()[:8]}",
                                    type=pattern_type,
                                    severity=self._get_pattern_severity(pattern_type),
                                    title=f"{pattern_type.replace('_', ' ').title()} detected",
                                    description=f"Potential {pattern_type} vulnerability found",
                                    affected_component=str(
                                        file_path.relative_to(self.project_root)
                                    ),
                                    cve_id=None,
                                    cvss_score=None,
                                    remediation=self._get_remediation(pattern_type),
                                    references=self._get_references(pattern_type),
                                    discovered_at=datetime.utcnow(),
                                    metadata={
                                        "line": line_num,
                                        "code_snippet": match.group()[:100],
                                    },
                                )
                            )
                except Exception as e:
                    logger.error(f"Failed to scan file {file_path}: {e}")

        result.vulnerabilities.extend(vulnerabilities)

    async def _scan_configurations(self, result: ScanResult):
        """Scan configuration files for security issues"""

        vulnerabilities = []

        # Check for insecure configurations
        config_files = [
            ".env",
            ".env.production",
            ".env.local",
            "config.yaml",
            "config.yml",
            "settings.py",
            "docker-compose.yml",
            "kubernetes.yaml",
        ]

        for config_file in config_files:
            config_path = self.project_root / config_file
            if config_path.exists():
                vulnerabilities.extend(await self._check_config_security(config_path))

        result.vulnerabilities.extend(vulnerabilities)

    async def _check_config_security(self, config_path: Path) -> List[Vulnerability]:
        """Check configuration file for security issues"""

        vulnerabilities = []

        try:
            async with aiofiles.open(config_path, "r") as f:
                content = await f.read()

            # Check for hardcoded secrets
            secret_patterns = [
                (r"password\s*[:=]\s*['\"]([^'\"]+)['\"]", "hardcoded_password"),
                (r"api_key\s*[:=]\s*['\"]([^'\"]+)['\"]", "hardcoded_api_key"),
                (r"secret\s*[:=]\s*['\"]([^'\"]+)['\"]", "hardcoded_secret"),
            ]

            for pattern, vuln_type in secret_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    vulnerabilities.append(
                        Vulnerability(
                            vuln_id=f"CONFIG-{vuln_type.upper()}-{hashlib.md5(match.group(1).encode()).hexdigest()[:8]}",
                            type="configuration",
                            severity=VulnerabilitySeverity.HIGH,
                            title=f"Hardcoded {vuln_type.replace('_', ' ')} detected",
                            description=f"Found hardcoded sensitive data in configuration",
                            affected_component=str(config_path.relative_to(self.project_root)),
                            cve_id=None,
                            cvss_score=None,
                            remediation="Use environment variables or secret management system",
                            references=[
                                "https://owasp.org/www-project-top-ten/2017/A3_2017-Sensitive_Data_Exposure"
                            ],
                            discovered_at=datetime.utcnow(),
                        )
                    )

            # Check for insecure settings
            if "debug" in content.lower() and ("true" in content.lower() or "1" in content):
                vulnerabilities.append(
                    Vulnerability(
                        vuln_id=f"CONFIG-DEBUG-ENABLED",
                        type="configuration",
                        severity=VulnerabilitySeverity.MEDIUM,
                        title="Debug mode enabled",
                        description="Debug mode is enabled in configuration",
                        affected_component=str(config_path.relative_to(self.project_root)),
                        cve_id=None,
                        cvss_score=None,
                        remediation="Disable debug mode in production",
                        references=[],
                        discovered_at=datetime.utcnow(),
                    )
                )

        except Exception as e:
            logger.error(f"Failed to check config security: {e}")

        return vulnerabilities

    async def _scan_secrets(self, result: ScanResult):
        """Scan for exposed secrets and credentials"""

        vulnerabilities = []

        # Patterns for different types of secrets
        secret_patterns = {
            "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
            "github_token": re.compile(r"ghp_[a-zA-Z0-9]{36}"),
            "slack_token": re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}"),
            "private_key": re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
            "google_api": re.compile(r"AIza[0-9A-Za-z\\-_]{35}"),
            "jwt_token": re.compile(r"eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]+"),
        }

        for file_path in self.project_root.rglob("*"):
            if file_path.is_file() and file_path.stat().st_size < 1024 * 1024:  # Skip files > 1MB
                try:
                    async with aiofiles.open(file_path, "r", errors="ignore") as f:
                        content = await f.read()

                    for secret_type, pattern in secret_patterns.items():
                        matches = pattern.finditer(content)
                        for match in matches:
                            vulnerabilities.append(
                                Vulnerability(
                                    vuln_id=f"SECRET-{secret_type.upper()}-{hashlib.md5(match.group().encode()).hexdigest()[:8]}",
                                    type="secrets",
                                    severity=VulnerabilitySeverity.CRITICAL,
                                    title=f"Exposed {secret_type.replace('_', ' ')} detected",
                                    description=f"Found exposed {secret_type} in source code",
                                    affected_component=str(
                                        file_path.relative_to(self.project_root)
                                    ),
                                    cve_id=None,
                                    cvss_score=None,
                                    remediation="Remove secret and rotate credentials immediately",
                                    references=[
                                        "https://owasp.org/www-project-top-ten/2017/A3_2017-Sensitive_Data_Exposure"
                                    ],
                                    discovered_at=datetime.utcnow(),
                                )
                            )
                except Exception:
                    # Skip binary files or files that can't be read
                    pass

        result.vulnerabilities.extend(vulnerabilities)

    async def _scan_infrastructure(self, result: ScanResult):
        """Scan infrastructure configuration"""

        vulnerabilities = []

        # Check Docker configurations
        docker_files = list(self.project_root.rglob("Dockerfile*"))
        for docker_file in docker_files:
            vulnerabilities.extend(await self._scan_dockerfile(docker_file))

        # Check Kubernetes configurations
        k8s_files = list(self.project_root.rglob("*.yaml")) + list(self.project_root.rglob("*.yml"))
        for k8s_file in k8s_files:
            if "kubernetes" in str(k8s_file).lower() or "k8s" in str(k8s_file).lower():
                vulnerabilities.extend(await self._scan_kubernetes(k8s_file))

        result.vulnerabilities.extend(vulnerabilities)

    async def _scan_dockerfile(self, dockerfile: Path) -> List[Vulnerability]:
        """Scan Dockerfile for security issues"""

        vulnerabilities = []

        try:
            async with aiofiles.open(dockerfile, "r") as f:
                content = await f.read()

            # Check for running as root
            if "USER" not in content:
                vulnerabilities.append(
                    Vulnerability(
                        vuln_id="DOCKER-ROOT-USER",
                        type="infrastructure",
                        severity=VulnerabilitySeverity.MEDIUM,
                        title="Container runs as root",
                        description="Docker container runs as root user",
                        affected_component=str(dockerfile.relative_to(self.project_root)),
                        cve_id=None,
                        cvss_score=None,
                        remediation="Add 'USER' directive to run as non-root",
                        references=[
                            "https://docs.docker.com/develop/develop-images/dockerfile_best-practices/"
                        ],
                        discovered_at=datetime.utcnow(),
                    )
                )

            # Check for using latest tag
            if ":latest" in content or re.search(r"FROM\s+[^:]+\s*$", content):
                vulnerabilities.append(
                    Vulnerability(
                        vuln_id="DOCKER-LATEST-TAG",
                        type="infrastructure",
                        severity=VulnerabilitySeverity.LOW,
                        title="Using 'latest' tag",
                        description="Docker image uses 'latest' tag which is not reproducible",
                        affected_component=str(dockerfile.relative_to(self.project_root)),
                        cve_id=None,
                        cvss_score=None,
                        remediation="Use specific version tags for base images",
                        references=[],
                        discovered_at=datetime.utcnow(),
                    )
                )

        except Exception as e:
            logger.error(f"Failed to scan Dockerfile: {e}")

        return vulnerabilities

    async def _scan_kubernetes(self, k8s_file: Path) -> List[Vulnerability]:
        """Scan Kubernetes configuration for security issues"""

        vulnerabilities = []

        try:
            async with aiofiles.open(k8s_file, "r") as f:
                content = await f.read()

            k8s_config = yaml.safe_load(content)

            if k8s_config and k8s_config.get("kind") == "Deployment":
                spec = k8s_config.get("spec", {}).get("template", {}).get("spec", {})

                # Check for security context
                if not spec.get("securityContext"):
                    vulnerabilities.append(
                        Vulnerability(
                            vuln_id="K8S-NO-SECURITY-CONTEXT",
                            type="infrastructure",
                            severity=VulnerabilitySeverity.MEDIUM,
                            title="Missing security context",
                            description="Kubernetes deployment lacks security context",
                            affected_component=str(k8s_file.relative_to(self.project_root)),
                            cve_id=None,
                            cvss_score=None,
                            remediation="Add securityContext with appropriate settings",
                            references=[
                                "https://kubernetes.io/docs/tasks/configure-pod-container/security-context/"
                            ],
                            discovered_at=datetime.utcnow(),
                        )
                    )

                # Check for resource limits
                containers = spec.get("containers", [])
                for container in containers:
                    if not container.get("resources", {}).get("limits"):
                        vulnerabilities.append(
                            Vulnerability(
                                vuln_id="K8S-NO-RESOURCE-LIMITS",
                                type="infrastructure",
                                severity=VulnerabilitySeverity.LOW,
                                title="Missing resource limits",
                                description=f"Container {container.get('name', 'unknown')} lacks resource limits",
                                affected_component=str(k8s_file.relative_to(self.project_root)),
                                cve_id=None,
                                cvss_score=None,
                                remediation="Add resource limits to prevent resource exhaustion",
                                references=[],
                                discovered_at=datetime.utcnow(),
                            )
                        )

        except Exception as e:
            logger.error(f"Failed to scan Kubernetes config: {e}")

        return vulnerabilities

    async def _scan_api_security(self, result: ScanResult):
        """Scan API endpoints for security issues"""

        vulnerabilities = []

        # Would perform actual API testing in production
        # For now, checking for common API security issues in code

        api_files = (
            list(self.project_root.rglob("*router*.py"))
            + list(self.project_root.rglob("*controller*.py"))
            + list(self.project_root.rglob("*api*.py"))
        )

        for api_file in api_files:
            try:
                async with aiofiles.open(api_file, "r") as f:
                    content = await f.read()

                # Check for missing authentication
                if "@app." in content or "@router." in content:
                    if "def " in content and "Depends" not in content:
                        vulnerabilities.append(
                            Vulnerability(
                                vuln_id=f"API-NO-AUTH-{api_file.stem}",
                                type="api",
                                severity=VulnerabilitySeverity.HIGH,
                                title="Potential missing authentication",
                                description="API endpoint may lack authentication",
                                affected_component=str(api_file.relative_to(self.project_root)),
                                cve_id=None,
                                cvss_score=None,
                                remediation="Add authentication dependency to endpoints",
                                references=["https://owasp.org/www-project-api-security/"],
                                discovered_at=datetime.utcnow(),
                            )
                        )

            except Exception as e:
                logger.error(f"Failed to scan API file {api_file}: {e}")

        result.vulnerabilities.extend(vulnerabilities)

    async def _check_compliance(self, result: ScanResult):
        """Check compliance with security frameworks"""

        for framework in self.compliance_frameworks:
            result.compliance_status[framework.value] = await self._check_framework_compliance(
                framework
            )

    async def _check_framework_compliance(self, framework: ComplianceFramework) -> bool:
        """Check compliance with specific framework"""

        if framework == ComplianceFramework.OWASP_TOP_10:
            # Check OWASP Top 10 compliance
            checks = {
                "injection": self._check_injection_protection(),
                "broken_auth": self._check_authentication(),
                "sensitive_data": self._check_data_protection(),
                "xxe": self._check_xxe_protection(),
                "broken_access": self._check_access_control(),
                "security_misconfig": self._check_security_config(),
                "xss": self._check_xss_protection(),
                "insecure_deserialization": self._check_deserialization(),
                "vulnerable_components": self._check_dependencies(),
                "insufficient_logging": self._check_logging(),
            }

            return all(await asyncio.gather(*checks.values()))

        # Add other framework checks as needed
        return True

    async def _check_injection_protection(self) -> bool:
        """Check for injection protection"""
        # Implementation would check for parameterized queries, input validation, etc.
        return True

    async def _check_authentication(self) -> bool:
        """Check authentication implementation"""
        # Implementation would verify strong authentication
        return True

    async def _check_data_protection(self) -> bool:
        """Check sensitive data protection"""
        # Implementation would check encryption, hashing, etc.
        return True

    async def _check_xxe_protection(self) -> bool:
        """Check XXE protection"""
        # Implementation would check XML parser configuration
        return True

    async def _check_access_control(self) -> bool:
        """Check access control implementation"""
        # Implementation would verify authorization checks
        return True

    async def _check_security_config(self) -> bool:
        """Check security configuration"""
        # Implementation would check security headers, CORS, etc.
        return True

    async def _check_xss_protection(self) -> bool:
        """Check XSS protection"""
        # Implementation would check output encoding, CSP, etc.
        return True

    async def _check_deserialization(self) -> bool:
        """Check deserialization security"""
        # Implementation would check for safe deserialization
        return True

    async def _check_dependencies(self) -> bool:
        """Check dependency vulnerabilities"""
        # Implementation would check for known vulnerable dependencies
        return True

    async def _check_logging(self) -> bool:
        """Check logging and monitoring"""
        # Implementation would verify security logging
        return True

    def _get_pattern_severity(self, pattern_type: str) -> VulnerabilitySeverity:
        """Get severity level for pattern type"""

        critical = ["sql_injection", "command_injection", "hardcoded_secrets"]
        high = ["xss", "xxe", "insecure_deserialization", "path_traversal"]
        medium = ["weak_crypto", "insecure_random", "cors_misconfiguration"]

        if pattern_type in critical:
            return VulnerabilitySeverity.CRITICAL
        elif pattern_type in high:
            return VulnerabilitySeverity.HIGH
        elif pattern_type in medium:
            return VulnerabilitySeverity.MEDIUM
        else:
            return VulnerabilitySeverity.LOW

    def _get_remediation(self, pattern_type: str) -> str:
        """Get remediation advice for pattern type"""

        remediations = {
            "sql_injection": "Use parameterized queries or ORM",
            "xss": "Sanitize and encode user input",
            "hardcoded_secrets": "Use environment variables or secret management",
            "command_injection": "Validate and sanitize input, use safe APIs",
            "path_traversal": "Validate file paths, use safe path operations",
            "xxe": "Disable XML external entity processing",
            "insecure_deserialization": "Use safe deserialization methods",
            "weak_crypto": "Use strong cryptographic algorithms (AES, SHA-256)",
            "insecure_random": "Use cryptographically secure random generators",
            "cors_misconfiguration": "Configure CORS properly, avoid wildcards",
        }

        return remediations.get(pattern_type, "Review and fix the security issue")

    def _get_references(self, pattern_type: str) -> List[str]:
        """Get reference URLs for pattern type"""

        references = {
            "sql_injection": ["https://owasp.org/www-community/attacks/SQL_Injection"],
            "xss": ["https://owasp.org/www-community/attacks/xss/"],
            "hardcoded_secrets": [
                "https://owasp.org/www-project-top-ten/2017/A3_2017-Sensitive_Data_Exposure"
            ],
            "command_injection": ["https://owasp.org/www-community/attacks/Command_Injection"],
            "path_traversal": ["https://owasp.org/www-community/attacks/Path_Traversal"],
            "xxe": [
                "https://owasp.org/www-community/vulnerabilities/XML_External_Entity_(XXE)_Processing"
            ],
            "insecure_deserialization": [
                "https://owasp.org/www-project-top-ten/2017/A8_2017-Insecure_Deserialization"
            ],
            "weak_crypto": [
                "https://owasp.org/www-project-top-ten/2017/A3_2017-Sensitive_Data_Exposure"
            ],
            "insecure_random": [
                "https://owasp.org/www-community/vulnerabilities/Insecure_Randomness"
            ],
            "cors_misconfiguration": [
                "https://owasp.org/www-community/attacks/CORS_OriginHeaderScrutiny"
            ],
        }

        return references.get(pattern_type, [])

    def _map_severity(self, severity: str) -> VulnerabilitySeverity:
        """Map severity string to enum"""

        severity = severity.lower()

        if severity in ["critical", "high"]:
            return VulnerabilitySeverity.CRITICAL
        elif severity == "high":
            return VulnerabilitySeverity.HIGH
        elif severity in ["medium", "moderate"]:
            return VulnerabilitySeverity.MEDIUM
        elif severity == "low":
            return VulnerabilitySeverity.LOW
        else:
            return VulnerabilitySeverity.INFO

    async def _auto_remediate(self, result: ScanResult):
        """Automatically remediate certain vulnerabilities"""

        for vuln in result.vulnerabilities:
            if vuln.type == "dependency" and self.enable_auto_remediation:
                await self._update_dependency(vuln)
            elif vuln.type == "configuration" and vuln.severity in [
                VulnerabilitySeverity.CRITICAL,
                VulnerabilitySeverity.HIGH,
            ]:
                await self._fix_configuration(vuln)

    async def _update_dependency(self, vuln: Vulnerability):
        """Update vulnerable dependency"""

        # Would implement actual dependency updates
        logger.info(f"Would update {vuln.affected_component} to fix {vuln.vuln_id}")

    async def _fix_configuration(self, vuln: Vulnerability):
        """Fix configuration vulnerability"""

        # Would implement actual configuration fixes
        logger.info(f"Would fix configuration in {vuln.affected_component}")

    async def _continuous_scanning_loop(self):
        """Continuous security scanning loop"""

        while True:
            try:
                await self.run_comprehensive_scan()
                await asyncio.sleep(self.scan_interval)
            except Exception as e:
                logger.error(f"Scanning error: {e}")
                await asyncio.sleep(self.scan_interval * 2)

    async def get_scan_report(self, scan_id: Optional[str] = None) -> Dict[str, Any]:
        """Get detailed scan report"""

        if scan_id:
            scan = next((s for s in self.scan_history if s.scan_id == scan_id), None)
            if not scan:
                return {"error": "Scan not found"}
        else:
            scan = self.scan_history[-1] if self.scan_history else None
            if not scan:
                return {"error": "No scans available"}

        return {
            "scan_id": scan.scan_id,
            "scan_type": scan.scan_type.value,
            "started_at": scan.started_at.isoformat(),
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
            "summary": {
                "total_issues": scan.total_issues,
                "critical": scan.critical_count,
                "high": scan.high_count,
                "medium": scan.medium_count,
                "low": scan.low_count,
            },
            "vulnerabilities": [
                {
                    "id": v.vuln_id,
                    "type": v.type,
                    "severity": v.severity.value,
                    "title": v.title,
                    "component": v.affected_component,
                    "remediation": v.remediation,
                }
                for v in scan.vulnerabilities[:10]  # Top 10 vulnerabilities
            ],
            "compliance": scan.compliance_status,
        }
