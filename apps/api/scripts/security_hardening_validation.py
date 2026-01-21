#!/usr/bin/env python3
"""
Security Hardening and Compliance Validation Script
Phase 3: Production Security Validation

Comprehensive security validation covering:
- OWASP Top 10 compliance
- SOC 2 Type II readiness
- Authentication security validation
- Data encryption verification
- Network security compliance
- Infrastructure hardening checks
"""

import asyncio
import aiohttp
import ssl
import logging
import sys
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import argparse
from dataclasses import dataclass, asdict
import socket
import secrets

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class SecurityCheck:
    """Individual security check result"""
    check_name: str
    category: str
    status: str  # PASSED, FAILED, WARNING, SKIPPED
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    description: str
    recommendation: Optional[str] = None
    evidence: Optional[Dict[str, Any]] = None

class SecurityValidator:
    """Comprehensive security validation suite"""
    
    def __init__(self, api_url: str = "https://api.janua.dev"):
        self.api_url = api_url
        self.results: List[SecurityCheck] = []
        
    def add_check(self, check: SecurityCheck):
        """Add a security check result"""
        self.results.append(check)
        
        status_icon = {
            'PASSED': '✅',
            'FAILED': '❌',
            'WARNING': '⚠️',
            'SKIPPED': '⏭️'
        }
        
        severity_prefix = {
            'CRITICAL': '🚨',
            'HIGH': '🔥',
            'MEDIUM': '⚡',
            'LOW': '💡'
        }
        
        icon = status_icon.get(check.status, '❓')
        severity_icon = severity_prefix.get(check.severity, '')
        
        logger.info(f"{icon} {severity_icon} {check.check_name}: {check.status}")
        if check.status == 'FAILED' and check.recommendation:
            logger.info(f"   💡 Recommendation: {check.recommendation}")

    async def validate_ssl_tls_security(self) -> List[SecurityCheck]:
        """Validate SSL/TLS configuration security"""
        logger.info("🔒 Validating SSL/TLS Security...")
        checks = []
        
        try:
            # Parse URL to get host and port
            from urllib.parse import urlparse
            parsed = urlparse(self.api_url)
            host = parsed.hostname
            port = parsed.port or 443
            
            # Test SSL/TLS configuration
            context = ssl.create_default_context()
            
            with socket.create_connection((host, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
                    
                    # Check TLS version
                    if version in ['TLSv1.2', 'TLSv1.3']:
                        checks.append(SecurityCheck(
                            check_name="TLS Version Security",
                            category="SSL/TLS",
                            status="PASSED",
                            severity="HIGH",
                            description=f"Using secure TLS version: {version}",
                            evidence={"tls_version": version}
                        ))
                    else:
                        checks.append(SecurityCheck(
                            check_name="TLS Version Security",
                            category="SSL/TLS",
                            status="FAILED",
                            severity="CRITICAL",
                            description=f"Insecure TLS version: {version}",
                            recommendation="Upgrade to TLS 1.2 or 1.3",
                            evidence={"tls_version": version}
                        ))
                    
                    # Check cipher suite
                    cipher_name = cipher[0] if cipher else "Unknown"
                    if any(secure in cipher_name for secure in ['ECDHE', 'AES', 'GCM', 'CHACHA20']):
                        checks.append(SecurityCheck(
                            check_name="Cipher Suite Security",
                            category="SSL/TLS",
                            status="PASSED",
                            severity="HIGH",
                            description=f"Using secure cipher: {cipher_name}",
                            evidence={"cipher": cipher}
                        ))
                    else:
                        checks.append(SecurityCheck(
                            check_name="Cipher Suite Security",
                            category="SSL/TLS",
                            status="WARNING",
                            severity="MEDIUM",
                            description=f"Potentially weak cipher: {cipher_name}",
                            recommendation="Review cipher suite configuration",
                            evidence={"cipher": cipher}
                        ))
                    
                    # Check certificate validity
                    not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    days_until_expiry = (not_after - datetime.now()).days
                    
                    if days_until_expiry > 30:
                        checks.append(SecurityCheck(
                            check_name="Certificate Validity",
                            category="SSL/TLS",
                            status="PASSED",
                            severity="HIGH",
                            description=f"Certificate valid for {days_until_expiry} days",
                            evidence={"expires_in_days": days_until_expiry, "not_after": cert['notAfter']}
                        ))
                    else:
                        checks.append(SecurityCheck(
                            check_name="Certificate Validity",
                            category="SSL/TLS",
                            status="WARNING",
                            severity="HIGH",
                            description=f"Certificate expires in {days_until_expiry} days",
                            recommendation="Renew SSL certificate",
                            evidence={"expires_in_days": days_until_expiry, "not_after": cert['notAfter']}
                        ))
        
        except Exception as e:
            checks.append(SecurityCheck(
                check_name="SSL/TLS Configuration",
                category="SSL/TLS",
                status="FAILED",
                severity="CRITICAL",
                description=f"SSL/TLS validation failed: {str(e)}",
                recommendation="Verify SSL/TLS configuration and certificate installation",
                evidence={"error": str(e)}
            ))
        
        for check in checks:
            self.add_check(check)
        
        return checks

    async def validate_security_headers(self) -> List[SecurityCheck]:
        """Validate HTTP security headers"""
        logger.info("🛡️ Validating Security Headers...")
        checks = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url + '/health') as response:
                    headers = response.headers
                    
                    # Check required security headers
                    required_headers = {
                        'strict-transport-security': {
                            'name': 'HSTS Header',
                            'severity': 'HIGH',
                            'check': lambda v: 'max-age' in v.lower() and 'includesubdomains' in v.lower()
                        },
                        'x-content-type-options': {
                            'name': 'Content Type Options',
                            'severity': 'MEDIUM',
                            'check': lambda v: v.lower() == 'nosniff'
                        },
                        'x-frame-options': {
                            'name': 'Frame Options',
                            'severity': 'MEDIUM',
                            'check': lambda v: v.lower() in ['deny', 'sameorigin']
                        },
                        'content-security-policy': {
                            'name': 'Content Security Policy',
                            'severity': 'HIGH',
                            'check': lambda v: "default-src 'self'" in v.lower()
                        },
                        'x-xss-protection': {
                            'name': 'XSS Protection',
                            'severity': 'MEDIUM',
                            'check': lambda v: '1' in v and 'mode=block' in v.lower()
                        },
                        'referrer-policy': {
                            'name': 'Referrer Policy',
                            'severity': 'LOW',
                            'check': lambda v: v.lower() in ['strict-origin', 'strict-origin-when-cross-origin', 'no-referrer']
                        }
                    }
                    
                    for header_key, config in required_headers.items():
                        header_value = headers.get(header_key, '').strip()
                        
                        if header_value and config['check'](header_value):
                            checks.append(SecurityCheck(
                                check_name=config['name'],
                                category="Security Headers",
                                status="PASSED",
                                severity=config['severity'],
                                description=f"Proper {config['name']} header configured",
                                evidence={header_key: header_value}
                            ))
                        elif header_value:
                            checks.append(SecurityCheck(
                                check_name=config['name'],
                                category="Security Headers",
                                status="WARNING",
                                severity=config['severity'],
                                description=f"Weak {config['name']} header configuration",
                                recommendation=f"Review {header_key} header configuration",
                                evidence={header_key: header_value}
                            ))
                        else:
                            checks.append(SecurityCheck(
                                check_name=config['name'],
                                category="Security Headers",
                                status="FAILED",
                                severity=config['severity'],
                                description=f"Missing {config['name']} header",
                                recommendation=f"Add {header_key} header to server configuration",
                                evidence={"missing_header": header_key}
                            ))
        
        except Exception as e:
            checks.append(SecurityCheck(
                check_name="Security Headers Check",
                category="Security Headers",
                status="FAILED",
                severity="HIGH",
                description=f"Failed to check security headers: {str(e)}",
                recommendation="Verify server accessibility and header configuration",
                evidence={"error": str(e)}
            ))
        
        for check in checks:
            self.add_check(check)
        
        return checks

    async def validate_authentication_security(self) -> List[SecurityCheck]:
        """Validate authentication security mechanisms"""
        logger.info("🔐 Validating Authentication Security...")
        checks = []
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test rate limiting on authentication endpoints
                signin_url = f"{self.api_url}/beta/signin"
                
                # Make multiple rapid requests to test rate limiting
                time.time()
                requests_made = 0
                rate_limited = False
                
                for i in range(10):  # Try 10 requests rapidly
                    try:
                        async with session.post(
                            signin_url,
                            json={'email': 'test@example.com', 'password': 'invalid'},
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as response:
                            requests_made += 1
                            if response.status == 429:  # Too Many Requests
                                rate_limited = True
                                break
                            await asyncio.sleep(0.1)  # Brief delay
                    except asyncio.TimeoutError:
                        break
                
                if rate_limited:
                    checks.append(SecurityCheck(
                        check_name="Authentication Rate Limiting",
                        category="Authentication",
                        status="PASSED",
                        severity="HIGH",
                        description="Rate limiting active on authentication endpoints",
                        evidence={"requests_before_limit": requests_made}
                    ))
                else:
                    checks.append(SecurityCheck(
                        check_name="Authentication Rate Limiting",
                        category="Authentication",
                        status="FAILED",
                        severity="HIGH",
                        description="No rate limiting detected on authentication endpoints",
                        recommendation="Implement rate limiting on authentication endpoints",
                        evidence={"requests_made": requests_made}
                    ))
                
                # Test password strength requirements
                weak_passwords = ['123456', 'password', 'admin', 'test']
                password_strength_enforced = False
                
                for weak_password in weak_passwords:
                    try:
                        signup_url = f"{self.api_url}/beta/signup"
                        async with session.post(
                            signup_url,
                            json={
                                'email': f'test.{secrets.token_hex(4)}@example.com',
                                'password': weak_password,
                                'name': 'Test User'
                            },
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as response:
                            if response.status == 400:  # Bad Request - password rejected
                                response_data = await response.json()
                                if 'password' in str(response_data).lower():
                                    password_strength_enforced = True
                                    break
                    except Exception:
                        continue
                
                if password_strength_enforced:
                    checks.append(SecurityCheck(
                        check_name="Password Strength Requirements",
                        category="Authentication",
                        status="PASSED",
                        severity="HIGH",
                        description="Password strength requirements enforced",
                        evidence={"weak_passwords_rejected": True}
                    ))
                else:
                    checks.append(SecurityCheck(
                        check_name="Password Strength Requirements",
                        category="Authentication",
                        status="WARNING",
                        severity="HIGH",
                        description="Password strength requirements not clearly enforced",
                        recommendation="Implement stronger password validation",
                        evidence={"weak_passwords_tested": weak_passwords}
                    ))
        
        except Exception as e:
            checks.append(SecurityCheck(
                check_name="Authentication Security Test",
                category="Authentication",
                status="FAILED",
                severity="HIGH",
                description=f"Failed to test authentication security: {str(e)}",
                recommendation="Verify authentication endpoints are accessible",
                evidence={"error": str(e)}
            ))
        
        for check in checks:
            self.add_check(check)
        
        return checks

    async def validate_input_validation(self) -> List[SecurityCheck]:
        """Validate input validation and injection protection"""
        logger.info("💉 Validating Input Validation Security...")
        checks = []
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test SQL injection protection
                sql_payloads = [
                    "'; DROP TABLE users; --",
                    "' OR '1'='1",
                    "admin'--",
                    "' UNION SELECT * FROM users--"
                ]
                
                sql_injection_protected = True
                for payload in sql_payloads:
                    try:
                        signin_url = f"{self.api_url}/beta/signin"
                        async with session.post(
                            signin_url,
                            json={'email': payload, 'password': 'test'},
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as response:
                            # Server should return 400 (validation error) or 401 (unauthorized)
                            # Not 500 (internal server error which might indicate SQL injection)
                            if response.status == 500:
                                response_text = await response.text()
                                if 'sql' in response_text.lower() or 'database' in response_text.lower():
                                    sql_injection_protected = False
                                    break
                    except Exception:
                        continue
                
                if sql_injection_protected:
                    checks.append(SecurityCheck(
                        check_name="SQL Injection Protection",
                        category="Input Validation",
                        status="PASSED",
                        severity="CRITICAL",
                        description="SQL injection attacks properly handled",
                        evidence={"payloads_tested": len(sql_payloads)}
                    ))
                else:
                    checks.append(SecurityCheck(
                        check_name="SQL Injection Protection",
                        category="Input Validation",
                        status="FAILED",
                        severity="CRITICAL",
                        description="Potential SQL injection vulnerability detected",
                        recommendation="Review database query parameterization and input sanitization",
                        evidence={"vulnerable_payload_found": True}
                    ))
                
                # Test XSS protection
                xss_payloads = [
                    "<script>alert('xss')</script>",
                    "javascript:alert('xss')",
                    "<img src=x onerror=alert('xss')>",
                    "' onmouseover='alert('xss')"
                ]
                
                xss_protected = True
                for payload in xss_payloads:
                    try:
                        signup_url = f"{self.api_url}/beta/signup"
                        async with session.post(
                            signup_url,
                            json={
                                'email': f'test@example.com',
                                'password': 'TestPassword123!',
                                'name': payload
                            },
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as response:
                            # Check if the payload is reflected in the response without sanitization
                            if response.status == 200:
                                response_text = await response.text()
                                if payload in response_text and '<script>' in response_text:
                                    xss_protected = False
                                    break
                    except Exception:
                        continue
                
                if xss_protected:
                    checks.append(SecurityCheck(
                        check_name="XSS Protection",
                        category="Input Validation",
                        status="PASSED",
                        severity="HIGH",
                        description="XSS attacks properly handled",
                        evidence={"payloads_tested": len(xss_payloads)}
                    ))
                else:
                    checks.append(SecurityCheck(
                        check_name="XSS Protection",
                        category="Input Validation",
                        status="FAILED",
                        severity="HIGH",
                        description="Potential XSS vulnerability detected",
                        recommendation="Implement proper input sanitization and output encoding",
                        evidence={"vulnerable_payload_found": True}
                    ))
        
        except Exception as e:
            checks.append(SecurityCheck(
                check_name="Input Validation Test",
                category="Input Validation",
                status="FAILED",
                severity="HIGH",
                description=f"Failed to test input validation: {str(e)}",
                recommendation="Verify API endpoints are accessible for security testing",
                evidence={"error": str(e)}
            ))
        
        for check in checks:
            self.add_check(check)
        
        return checks

    async def validate_session_security(self) -> List[SecurityCheck]:
        """Validate session management security"""
        logger.info("🎫 Validating Session Security...")
        checks = []
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test session token security
                signin_url = f"{self.api_url}/beta/signin"
                
                # Create a test user session
                async with session.post(
                    f"{self.api_url}/beta/signup",
                    json={
                        'email': f'security.test.{secrets.token_hex(4)}@example.com',
                        'password': 'SecureTestPassword123!',
                        'name': 'Security Test User'
                    }
                ) as signup_response:
                    
                    if signup_response.status in [200, 201]:
                        # Now sign in to get session token
                        async with session.post(
                            signin_url,
                            json={
                                'email': f'security.test.{secrets.token_hex(4)}@example.com',
                                'password': 'SecureTestPassword123!'
                            }
                        ) as signin_response:
                            
                            if signin_response.status == 200:
                                signin_data = await signin_response.json()
                                access_token = signin_data.get('access_token', '')
                                
                                # Check token format (should be JWT)
                                if len(access_token.split('.')) == 3:
                                    checks.append(SecurityCheck(
                                        check_name="JWT Token Format",
                                        category="Session Management",
                                        status="PASSED",
                                        severity="MEDIUM",
                                        description="Session tokens use JWT format",
                                        evidence={"token_format": "JWT", "segments": len(access_token.split('.'))}
                                    ))
                                else:
                                    checks.append(SecurityCheck(
                                        check_name="JWT Token Format",
                                        category="Session Management",
                                        status="WARNING",
                                        severity="MEDIUM",
                                        description="Session tokens may not use JWT format",
                                        recommendation="Consider using JWT tokens for better security",
                                        evidence={"token_format": "Non-JWT", "token_length": len(access_token)}
                                    ))
                                
                                # Check token entropy (should be high for security)
                                if len(access_token) >= 32:  # Reasonable minimum length
                                    checks.append(SecurityCheck(
                                        check_name="Token Entropy",
                                        category="Session Management",
                                        status="PASSED",
                                        severity="HIGH",
                                        description="Session tokens have sufficient entropy",
                                        evidence={"token_length": len(access_token)}
                                    ))
                                else:
                                    checks.append(SecurityCheck(
                                        check_name="Token Entropy",
                                        category="Session Management",
                                        status="FAILED",
                                        severity="HIGH",
                                        description="Session tokens may have insufficient entropy",
                                        recommendation="Increase token length and randomness",
                                        evidence={"token_length": len(access_token)}
                                    ))
            
        except Exception as e:
            checks.append(SecurityCheck(
                check_name="Session Security Test",
                category="Session Management",
                status="FAILED",
                severity="HIGH",
                description=f"Failed to test session security: {str(e)}",
                recommendation="Verify session management endpoints are accessible",
                evidence={"error": str(e)}
            ))
        
        for check in checks:
            self.add_check(check)
        
        return checks

    async def validate_infrastructure_security(self) -> List[SecurityCheck]:
        """Validate infrastructure security configurations"""
        logger.info("🏗️ Validating Infrastructure Security...")
        checks = []
        
        try:
            # Check if common security files exist
            security_files = [
                'deployment/production/production-deployment.yml',
                'deployment/nginx-ssl.conf',
                'scripts/apply_database_optimization.py'
            ]
            
            security_configs_present = 0
            for file_path in security_files:
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        if any(keyword in content.lower() for keyword in ['security', 'ssl', 'tls', 'encryption']):
                            security_configs_present += 1
                except FileNotFoundError:
                    continue
            
            if security_configs_present >= len(security_files) * 0.7:  # At least 70% of files present
                checks.append(SecurityCheck(
                    check_name="Security Configuration Files",
                    category="Infrastructure",
                    status="PASSED",
                    severity="MEDIUM",
                    description="Security configuration files present",
                    evidence={"security_configs_found": security_configs_present, "total_checked": len(security_files)}
                ))
            else:
                checks.append(SecurityCheck(
                    check_name="Security Configuration Files",
                    category="Infrastructure",
                    status="WARNING",
                    severity="MEDIUM",
                    description="Some security configuration files missing",
                    recommendation="Ensure all security configuration files are properly deployed",
                    evidence={"security_configs_found": security_configs_present, "total_checked": len(security_files)}
                ))
        
        except Exception as e:
            checks.append(SecurityCheck(
                check_name="Infrastructure Security Check",
                category="Infrastructure",
                status="FAILED",
                severity="MEDIUM",
                description=f"Failed to check infrastructure security: {str(e)}",
                recommendation="Verify security configuration files are accessible",
                evidence={"error": str(e)}
            ))
        
        for check in checks:
            self.add_check(check)
        
        return checks

    def generate_security_report(self) -> Dict[str, Any]:
        """Generate comprehensive security report"""
        # Categorize results
        by_category = {}
        by_status = {'PASSED': 0, 'FAILED': 0, 'WARNING': 0, 'SKIPPED': 0}
        by_severity = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        
        for check in self.results:
            # By category
            if check.category not in by_category:
                by_category[check.category] = {'PASSED': 0, 'FAILED': 0, 'WARNING': 0, 'SKIPPED': 0}
            by_category[check.category][check.status] += 1
            
            # By status
            by_status[check.status] += 1
            
            # By severity
            by_severity[check.severity] += 1
        
        # Calculate security score
        total_checks = len(self.results)
        critical_failed = len([c for c in self.results if c.severity == 'CRITICAL' and c.status == 'FAILED'])
        high_failed = len([c for c in self.results if c.severity == 'HIGH' and c.status == 'FAILED'])
        passed_count = by_status['PASSED']  # Store passed count for potential reporting

        # Security score calculation (weighted by severity)
        score_deductions = (critical_failed * 20) + (high_failed * 10) + (by_status['FAILED'] * 5)
        max_possible_score = total_checks * 10
        security_score = max(0, ((max_possible_score - score_deductions) / max_possible_score) * 100) if total_checks > 0 else 0
        
        # Determine overall security status
        if critical_failed > 0:
            overall_status = "CRITICAL"
        elif high_failed > 0:
            overall_status = "HIGH_RISK"
        elif by_status['FAILED'] > 0:
            overall_status = "MEDIUM_RISK"
        else:
            overall_status = "SECURE"
        
        return {
            'overall_status': overall_status,
            'security_score': round(security_score, 1),
            'total_checks': total_checks,
            'passed_checks': passed_count,
            'summary': by_status,
            'severity_distribution': by_severity,
            'category_breakdown': by_category,
            'critical_issues': [
                {
                    'check_name': c.check_name,
                    'description': c.description,
                    'recommendation': c.recommendation
                }
                for c in self.results 
                if c.severity == 'CRITICAL' and c.status == 'FAILED'
            ],
            'high_priority_issues': [
                {
                    'check_name': c.check_name,
                    'description': c.description,
                    'recommendation': c.recommendation
                }
                for c in self.results 
                if c.severity == 'HIGH' and c.status == 'FAILED'
            ],
            'detailed_results': [asdict(check) for check in self.results],
            'timestamp': datetime.now().isoformat()
        }

    async def run_security_validation(self) -> Dict[str, Any]:
        """Run comprehensive security validation"""
        logger.info("🔐 Starting Security Hardening Validation")
        logger.info("=" * 50)
        
        start_time = datetime.now()
        
        # Run all security validation checks
        validation_checks = [
            ("SSL/TLS Security", self.validate_ssl_tls_security()),
            ("Security Headers", self.validate_security_headers()),
            ("Authentication Security", self.validate_authentication_security()),
            ("Input Validation", self.validate_input_validation()),
            ("Session Security", self.validate_session_security()),
            ("Infrastructure Security", self.validate_infrastructure_security())
        ]
        
        for check_name, check_coro in validation_checks:
            logger.info(f"\n🔍 Running: {check_name}")
            try:
                await check_coro
            except Exception as e:
                logger.error(f"❌ {check_name} failed: {e}")
                self.add_check(SecurityCheck(
                    check_name=f"{check_name} Execution",
                    category="System",
                    status="FAILED",
                    severity="HIGH",
                    description=f"Security check execution failed: {str(e)}",
                    recommendation="Review security validation system and network connectivity"
                ))
        
        # Generate comprehensive report
        report = self.generate_security_report()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Log summary
        logger.info("\n" + "=" * 50)
        logger.info("🔒 SECURITY VALIDATION SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Overall Status: {report['overall_status']}")
        logger.info(f"Security Score: {report['security_score']}/100")
        logger.info(f"Total Checks: {report['total_checks']}")
        logger.info(f"Passed: {report['summary']['PASSED']}")
        logger.info(f"Failed: {report['summary']['FAILED']}")
        logger.info(f"Warnings: {report['summary']['WARNING']}")
        logger.info(f"Duration: {duration:.1f} seconds")
        
        if report['critical_issues']:
            logger.warning(f"🚨 {len(report['critical_issues'])} CRITICAL issues require immediate attention!")
        
        if report['high_priority_issues']:
            logger.warning(f"🔥 {len(report['high_priority_issues'])} HIGH priority issues should be addressed")
        
        # Save detailed report
        report_filename = f"security_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"📄 Detailed security report saved: {report_filename}")
        
        return report

async def main():
    """Main security validation execution"""
    parser = argparse.ArgumentParser(description="Janua Security Hardening Validation")
    parser.add_argument("--url", default="https://api.janua.dev", help="API base URL")
    parser.add_argument("--quick", action="store_true", help="Run quick security checks only")
    
    args = parser.parse_args()
    
    validator = SecurityValidator(api_url=args.url)
    
    try:
        report = await validator.run_security_validation()
        
        # Determine exit code based on security status
        if report['overall_status'] == 'CRITICAL':
            return 2  # Critical security issues
        elif report['overall_status'] in ['HIGH_RISK', 'MEDIUM_RISK']:
            return 1  # Security issues present
        else:
            logger.info("✅ Security validation PASSED - Platform is secure!")
            return 0  # All security checks passed
            
    except KeyboardInterrupt:
        logger.info("Security validation interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Security validation failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)