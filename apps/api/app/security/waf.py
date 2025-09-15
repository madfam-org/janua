"""
Web Application Firewall (WAF) Implementation
Provides comprehensive protection against common web attacks
"""

import re
import json
import hashlib
import ipaddress
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()


@dataclass
class WAFRule:
    """WAF rule definition"""
    id: str
    name: str
    pattern: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    action: str    # BLOCK, LOG, RATE_LIMIT
    enabled: bool = True
    description: str = ""


@dataclass
class AttackSignature:
    """Attack signature for detection"""
    name: str
    patterns: List[str]
    severity: str
    category: str  # SQL_INJECTION, XSS, LFI, RFI, etc.


class WAFEngine:
    """Core WAF engine for request analysis and threat detection"""

    def __init__(self):
        self.rules: Dict[str, WAFRule] = {}
        self.signatures: Dict[str, AttackSignature] = {}
        self.blocked_ips: Set[str] = set()
        self.rate_limits: Dict[str, List[datetime]] = {}
        self.whitelist_ips: Set[str] = set()
        self.malicious_patterns = self._load_malicious_patterns()

        # Initialize default rules
        self._initialize_default_rules()
        self._initialize_attack_signatures()

    def _load_malicious_patterns(self) -> Dict[str, List[str]]:
        """Load known malicious patterns"""
        return {
            'sql_injection': [
                r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)",
                r"(--|#|\/\*|\*\/)",
                r"(\b(OR|AND)\s+\d+\s*=\s*\d+)",
                r"('\s*(OR|AND)\s+')",
                r"(\bUNION\s+SELECT\b)",
                r"(\b(INFORMATION_SCHEMA|mysql\.user|pg_user)\b)",
            ],
            'xss': [
                r"(<script[^>]*>.*?</script>)",
                r"(javascript\s*:)",
                r"(on\w+\s*=)",
                r"(<iframe[^>]*>)",
                r"(<object[^>]*>)",
                r"(eval\s*\()",
                r"(document\.(cookie|domain|location))",
            ],
            'lfi': [
                r"(\.\./|\.\.\%2f|\.\.\%5c)",
                r"(/etc/passwd|/etc/shadow|/proc/self/environ)",
                r"(\%00|null\x00)",
                r"(file\s*:|php\s*:|data\s*:)",
            ],
            'rfi': [
                r"(https?://[^/\s]+)",
                r"(ftp://[^/\s]+)",
                r"(\?.*https?://)",
            ],
            'command_injection': [
                r"(\||&|;|`|\$\(|\${)",
                r"(\b(cat|ls|ps|id|whoami|uname|netstat)\b)",
                r"(\bnc\s+-)",
                r"(\bcurl\s+)",
                r"(\bwget\s+)",
            ],
        }

    def _initialize_default_rules(self):
        """Initialize default WAF rules"""
        rules = [
            WAFRule(
                id="SQL_001",
                name="SQL Injection Detection",
                pattern="sql_injection",
                severity="HIGH",
                action="BLOCK",
                description="Detects common SQL injection patterns"
            ),
            WAFRule(
                id="XSS_001",
                name="Cross-Site Scripting Detection",
                pattern="xss",
                severity="HIGH",
                action="BLOCK",
                description="Detects XSS attack patterns"
            ),
            WAFRule(
                id="LFI_001",
                name="Local File Inclusion Detection",
                pattern="lfi",
                severity="MEDIUM",
                action="BLOCK",
                description="Detects local file inclusion attempts"
            ),
            WAFRule(
                id="RFI_001",
                name="Remote File Inclusion Detection",
                pattern="rfi",
                severity="HIGH",
                action="BLOCK",
                description="Detects remote file inclusion attempts"
            ),
            WAFRule(
                id="CMD_001",
                name="Command Injection Detection",
                pattern="command_injection",
                severity="CRITICAL",
                action="BLOCK",
                description="Detects command injection attempts"
            ),
            WAFRule(
                id="RATE_001",
                name="Rate Limiting",
                pattern="",
                severity="MEDIUM",
                action="RATE_LIMIT",
                description="Rate limiting protection"
            ),
        ]

        for rule in rules:
            self.rules[rule.id] = rule

    def _initialize_attack_signatures(self):
        """Initialize attack signatures"""
        signatures = [
            AttackSignature(
                name="Classic SQL Injection",
                patterns=self.malicious_patterns['sql_injection'],
                severity="HIGH",
                category="SQL_INJECTION"
            ),
            AttackSignature(
                name="Cross-Site Scripting",
                patterns=self.malicious_patterns['xss'],
                severity="HIGH",
                category="XSS"
            ),
            AttackSignature(
                name="Local File Inclusion",
                patterns=self.malicious_patterns['lfi'],
                severity="MEDIUM",
                category="LFI"
            ),
            AttackSignature(
                name="Remote File Inclusion",
                patterns=self.malicious_patterns['rfi'],
                severity="HIGH",
                category="RFI"
            ),
            AttackSignature(
                name="Command Injection",
                patterns=self.malicious_patterns['command_injection'],
                severity="CRITICAL",
                category="COMMAND_INJECTION"
            ),
        ]

        for sig in signatures:
            self.signatures[sig.name] = sig

    def add_to_whitelist(self, ip: str):
        """Add IP to whitelist"""
        try:
            ipaddress.ip_address(ip)
            self.whitelist_ips.add(ip)
            logger.info("IP added to whitelist", ip=ip)
        except ValueError:
            logger.error("Invalid IP address for whitelist", ip=ip)

    def add_to_blocklist(self, ip: str, duration_hours: int = 24):
        """Add IP to blocklist"""
        try:
            ipaddress.ip_address(ip)
            self.blocked_ips.add(ip)
            logger.warning("IP added to blocklist", ip=ip, duration=duration_hours)
        except ValueError:
            logger.error("Invalid IP address for blocklist", ip=ip)

    def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is blocked"""
        return ip in self.blocked_ips

    def is_ip_whitelisted(self, ip: str) -> bool:
        """Check if IP is whitelisted"""
        return ip in self.whitelist_ips

    def analyze_request(self, request: Request) -> Tuple[bool, Dict]:
        """Analyze request for threats"""
        client_ip = self._get_client_ip(request)

        # Check whitelist first
        if self.is_ip_whitelisted(client_ip):
            return True, {"status": "whitelisted", "ip": client_ip}

        # Check blocklist
        if self.is_ip_blocked(client_ip):
            logger.warning("Blocked IP attempted access", ip=client_ip)
            return False, {
                "status": "blocked",
                "reason": "IP is blocklisted",
                "ip": client_ip
            }

        # Analyze request content
        threat_found, threat_details = self._analyze_content(request)

        if threat_found:
            logger.warning("Threat detected", **threat_details, ip=client_ip)

            # Auto-block on critical threats
            if threat_details.get('severity') == 'CRITICAL':
                self.add_to_blocklist(client_ip)

            return False, threat_details

        return True, {"status": "clean", "ip": client_ip}

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        # Check X-Forwarded-For header (for load balancers/proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to client IP
        return request.client.host if request.client else "unknown"

    def _analyze_content(self, request: Request) -> Tuple[bool, Dict]:
        """Analyze request content for threats"""
        # Get request data to analyze
        url = str(request.url)
        query_params = str(request.query_params)
        headers = dict(request.headers)

        # Analyze URL and query parameters
        for signature in self.signatures.values():
            if not signature:
                continue

            for pattern in signature.patterns:
                # Check URL
                if re.search(pattern, url, re.IGNORECASE):
                    return True, {
                        "threat_type": signature.category,
                        "threat_name": signature.name,
                        "severity": signature.severity,
                        "location": "url",
                        "pattern": pattern,
                        "matched_content": url
                    }

                # Check query parameters
                if re.search(pattern, query_params, re.IGNORECASE):
                    return True, {
                        "threat_type": signature.category,
                        "threat_name": signature.name,
                        "severity": signature.severity,
                        "location": "query_params",
                        "pattern": pattern,
                        "matched_content": query_params
                    }

        # Check headers for malicious content
        for header_name, header_value in headers.items():
            if self._contains_malicious_content(header_value):
                return True, {
                    "threat_type": "HEADER_INJECTION",
                    "threat_name": "Malicious Header Content",
                    "severity": "MEDIUM",
                    "location": f"header_{header_name}",
                    "matched_content": header_value
                }

        return False, {}

    def _contains_malicious_content(self, content: str) -> bool:
        """Check if content contains malicious patterns"""
        content_lower = content.lower()

        # Check for common attack patterns
        malicious_indicators = [
            '<script', 'javascript:', 'vbscript:', 'onload=', 'onerror=',
            'union select', 'drop table', '../', 'etc/passwd',
            '<?php', '<%', 'eval(', 'exec(', 'system(',
        ]

        return any(indicator in content_lower for indicator in malicious_indicators)


class WAFMiddleware:
    """WAF middleware for FastAPI"""

    def __init__(self):
        self.waf_engine = WAFEngine()

    async def __call__(self, request: Request, call_next):
        """Process request through WAF"""
        # Analyze request
        is_safe, analysis_result = self.waf_engine.analyze_request(request)

        if not is_safe:
            # Log the threat
            logger.warning(
                "WAF blocked request",
                **analysis_result,
                url=str(request.url),
                method=request.method,
                user_agent=request.headers.get("User-Agent", "unknown")
            )

            # Return blocked response
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Request blocked by WAF",
                    "reason": analysis_result.get("threat_name", "Security violation"),
                    "request_id": self._generate_request_id(request)
                }
            )

        # Continue processing if safe
        response = await call_next(request)

        # Add security headers to response
        self._add_security_headers(response)

        return response

    def _generate_request_id(self, request: Request) -> str:
        """Generate unique request ID for tracking"""
        content = f"{request.method}{request.url}{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:8]

    def _add_security_headers(self, response):
        """Add security headers to response"""
        security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }

        for header, value in security_headers.items():
            response.headers[header] = value


# WAF configuration and management
class WAFConfig:
    """WAF configuration management"""

    @staticmethod
    def load_config(config_file: str = "waf_config.json") -> Dict:
        """Load WAF configuration from file"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return WAFConfig.get_default_config()

    @staticmethod
    def get_default_config() -> Dict:
        """Get default WAF configuration"""
        return {
            "enabled": True,
            "block_mode": True,
            "rate_limiting": {
                "enabled": True,
                "requests_per_minute": 60,
                "burst_size": 20
            },
            "geoblocking": {
                "enabled": False,
                "blocked_countries": []
            },
            "custom_rules": [],
            "whitelist": [],
            "blocklist": [],
            "logging": {
                "enabled": True,
                "log_level": "INFO",
                "log_blocked_only": False
            }
        }


# WAF statistics and reporting
class WAFStats:
    """WAF statistics tracking"""

    def __init__(self):
        self.stats = {
            "total_requests": 0,
            "blocked_requests": 0,
            "threats_detected": {},
            "top_blocked_ips": {},
            "last_reset": datetime.now()
        }

    def increment_total_requests(self):
        """Increment total request counter"""
        self.stats["total_requests"] += 1

    def increment_blocked_requests(self, threat_type: str, ip: str):
        """Increment blocked request counter"""
        self.stats["blocked_requests"] += 1

        # Track threat types
        if threat_type not in self.stats["threats_detected"]:
            self.stats["threats_detected"][threat_type] = 0
        self.stats["threats_detected"][threat_type] += 1

        # Track blocked IPs
        if ip not in self.stats["top_blocked_ips"]:
            self.stats["top_blocked_ips"][ip] = 0
        self.stats["top_blocked_ips"][ip] += 1

    def get_stats(self) -> Dict:
        """Get current statistics"""
        total = self.stats["total_requests"]
        blocked = self.stats["blocked_requests"]

        return {
            **self.stats,
            "block_rate": (blocked / total * 100) if total > 0 else 0,
            "uptime": datetime.now() - self.stats["last_reset"]
        }

    def reset_stats(self):
        """Reset statistics"""
        self.stats = {
            "total_requests": 0,
            "blocked_requests": 0,
            "threats_detected": {},
            "top_blocked_ips": {},
            "last_reset": datetime.now()
        }


# Initialize global WAF instance
waf_middleware = WAFMiddleware()
waf_stats = WAFStats()