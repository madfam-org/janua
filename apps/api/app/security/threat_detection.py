"""
Advanced Threat Detection System
Real-time threat detection with ML-based anomaly detection and automated response
"""

import asyncio
import json
import ipaddress
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
import logging
import re
from dataclasses import dataclass, field
from sklearn.ensemble import IsolationForest
import joblib
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """Threat severity levels"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(Enum):
    """Types of security threats"""
    BRUTE_FORCE = "brute_force"
    CREDENTIAL_STUFFING = "credential_stuffing"
    SQL_INJECTION = "sql_injection"
    XSS_ATTEMPT = "xss_attempt"
    PATH_TRAVERSAL = "path_traversal"
    DDOS_ATTACK = "ddos_attack"
    ACCOUNT_TAKEOVER = "account_takeover"
    SUSPICIOUS_BEHAVIOR = "suspicious_behavior"
    BOT_ACTIVITY = "bot_activity"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    ANOMALOUS_ACCESS = "anomalous_access"


@dataclass
class ThreatIndicator:
    """Individual threat indicator"""
    indicator_type: str
    value: Any
    confidence: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreatEvent:
    """Detected threat event"""
    event_id: str
    threat_type: ThreatType
    threat_level: ThreatLevel
    source_ip: str
    user_id: Optional[str]
    target_resource: str
    indicators: List[ThreatIndicator]
    confidence_score: float
    timestamp: datetime
    response_actions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AdvancedThreatDetectionSystem:
    """
    Enterprise-grade threat detection system with:
    - Real-time anomaly detection
    - Machine learning-based threat scoring
    - Automated threat response
    - Integration with threat intelligence feeds
    - Behavioral analysis
    """
    
    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis_client = redis_client
        
        # Detection thresholds
        self.failed_login_threshold = 5
        self.failed_login_window = 300  # 5 minutes
        self.request_rate_threshold = 100  # requests per minute
        self.data_access_threshold = 1000  # records per hour
        
        # ML models
        self.anomaly_detector = None
        self._initialize_ml_models()
        
        # Threat intelligence
        self.threat_intel_feeds = []
        self.blocked_ips: Set[str] = set()
        self.suspicious_patterns: List[re.Pattern] = []
        self._load_threat_intelligence()
        
        # Real-time tracking
        self.active_threats: Dict[str, ThreatEvent] = {}
        self.user_behavior: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.ip_reputation: Dict[str, float] = {}
        
        # Start background tasks
        asyncio.create_task(self._threat_monitoring_loop())
        asyncio.create_task(self._update_threat_intelligence())
    
    def _initialize_ml_models(self):
        """Initialize machine learning models for anomaly detection"""
        try:
            # Try to load pre-trained model
            self.anomaly_detector = joblib.load('models/anomaly_detector.pkl')
        except Exception:
            # Create new model if not available
            self.anomaly_detector = IsolationForest(
                contamination=0.1,
                random_state=42
            )
            # Would need training data in production
    
    def _load_threat_intelligence(self):
        """Load threat intelligence patterns and feeds"""
        
        # Known malicious patterns
        self.suspicious_patterns = [
            re.compile(r"(<script[^>]*>.*?</script>)", re.IGNORECASE),
            re.compile(r"(javascript:)", re.IGNORECASE),
            re.compile(r"(\bUNION\b.*\bSELECT\b)", re.IGNORECASE),
            re.compile(r"(\.\.\/|\.\.\\\\)"),
            re.compile(r"(\bEXEC\b.*\bxp_cmdshell\b)", re.IGNORECASE),
        ]
        
        # Load IP reputation database
        self._load_ip_reputation()
    
    async def analyze_request(
        self,
        request_data: Dict[str, Any]
    ) -> Tuple[ThreatLevel, List[ThreatIndicator]]:
        """
        Analyze incoming request for threats
        
        Returns:
            Threat level and list of indicators
        """
        
        indicators = []
        threat_scores = []
        
        # Extract request attributes
        ip = request_data.get('ip_address', '')
        user_id = request_data.get('user_id')
        path = request_data.get('path', '')
        request_data.get('method', '')
        headers = request_data.get('headers', {})
        body = request_data.get('body', '')
        query_params = request_data.get('query_params', {})
        
        # 1. IP Reputation Check
        ip_threat = await self._check_ip_reputation(ip)
        if ip_threat > 0:
            indicators.append(ThreatIndicator(
                indicator_type="ip_reputation",
                value=ip,
                confidence=ip_threat,
                timestamp=datetime.utcnow(),
                metadata={"reputation_score": ip_threat}
            ))
            threat_scores.append(ip_threat)
        
        # 2. Pattern Matching for Attacks
        pattern_threats = self._detect_attack_patterns(
            f"{path} {body} {json.dumps(query_params)}"
        )
        for threat in pattern_threats:
            indicators.append(threat)
            threat_scores.append(threat.confidence)
        
        # 3. Rate Limiting Analysis
        rate_threat = await self._analyze_rate_patterns(ip, user_id)
        if rate_threat > 0:
            indicators.append(ThreatIndicator(
                indicator_type="rate_anomaly",
                value=f"{ip}:{user_id}",
                confidence=rate_threat,
                timestamp=datetime.utcnow()
            ))
            threat_scores.append(rate_threat)
        
        # 4. Behavioral Analysis
        if user_id:
            behavior_threat = await self._analyze_user_behavior(
                user_id, request_data
            )
            if behavior_threat > 0:
                indicators.append(ThreatIndicator(
                    indicator_type="behavioral_anomaly",
                    value=user_id,
                    confidence=behavior_threat,
                    timestamp=datetime.utcnow()
                ))
                threat_scores.append(behavior_threat)
        
        # 5. Authentication Attack Detection
        if path in ['/api/v1/auth/signin', '/api/v1/auth/signup']:
            auth_threat = await self._detect_authentication_attacks(
                ip, user_id, request_data
            )
            if auth_threat > 0:
                indicators.append(ThreatIndicator(
                    indicator_type="auth_attack",
                    value=ip,
                    confidence=auth_threat,
                    timestamp=datetime.utcnow()
                ))
                threat_scores.append(auth_threat)
        
        # 6. Bot Detection
        bot_score = self._detect_bot_activity(headers, request_data)
        if bot_score > 0.5:
            indicators.append(ThreatIndicator(
                indicator_type="bot_detection",
                value=headers.get('user-agent', 'unknown'),
                confidence=bot_score,
                timestamp=datetime.utcnow()
            ))
            threat_scores.append(bot_score)
        
        # Calculate overall threat level
        if not threat_scores:
            return ThreatLevel.NONE, indicators
        
        max_score = max(threat_scores)
        avg_score = sum(threat_scores) / len(threat_scores)
        
        if max_score >= 0.9 or avg_score >= 0.7:
            threat_level = ThreatLevel.CRITICAL
        elif max_score >= 0.7 or avg_score >= 0.5:
            threat_level = ThreatLevel.HIGH
        elif max_score >= 0.5 or avg_score >= 0.3:
            threat_level = ThreatLevel.MEDIUM
        elif max_score >= 0.3:
            threat_level = ThreatLevel.LOW
        else:
            threat_level = ThreatLevel.NONE
        
        # Create threat event if significant
        if threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            await self._create_threat_event(
                threat_level, indicators, request_data
            )
        
        return threat_level, indicators
    
    async def _check_ip_reputation(self, ip: str) -> float:
        """Check IP reputation from multiple sources"""
        
        # Check blocklist
        if ip in self.blocked_ips:
            return 1.0
        
        # Check cached reputation
        if ip in self.ip_reputation:
            return self.ip_reputation[ip]
        
        # Check Redis for distributed reputation
        if self.redis_client:
            reputation = await self.redis_client.get(f"ip_reputation:{ip}")
            if reputation:
                score = float(reputation)
                self.ip_reputation[ip] = score
                return score
        
        # Check if IP is from known bad ranges (TOR, VPN, etc.)
        if self._is_suspicious_ip_range(ip):
            return 0.6
        
        return 0.0
    
    def _is_suspicious_ip_range(self, ip: str) -> bool:
        """Check if IP is from suspicious range"""
        try:
            ip_obj = ipaddress.ip_address(ip)

            # Check for common VPN/proxy ranges
            suspicious_ranges = [
                ipaddress.ip_network("10.0.0.0/8"),
                ipaddress.ip_network("172.16.0.0/12"),
                ipaddress.ip_network("192.168.0.0/16"),
            ]

            for range in suspicious_ranges:
                if ip_obj in range:
                    return True

        except (ValueError, ipaddress.AddressValueError) as e:
            # Invalid IP address format
            logger.warning(
                "Invalid IP address format in threat detection",
                ip=ip,
                error=str(e),
                error_type=type(e).__name__
            )
        
        return False
    
    def _detect_attack_patterns(self, content: str) -> List[ThreatIndicator]:
        """Detect attack patterns in request content"""
        
        indicators = []
        
        for pattern in self.suspicious_patterns:
            matches = pattern.findall(content)
            if matches:
                threat_type = self._identify_pattern_type(pattern)
                indicators.append(ThreatIndicator(
                    indicator_type=threat_type,
                    value=matches[0][:100],  # Truncate for safety
                    confidence=0.8,
                    timestamp=datetime.utcnow(),
                    metadata={"pattern": pattern.pattern}
                ))
        
        return indicators
    
    def _identify_pattern_type(self, pattern: re.Pattern) -> str:
        """Identify the type of attack from pattern"""
        
        pattern_str = pattern.pattern.lower()
        
        if 'script' in pattern_str or 'javascript' in pattern_str:
            return "xss_attempt"
        elif 'union' in pattern_str or 'select' in pattern_str:
            return "sql_injection"
        elif '..' in pattern_str:
            return "path_traversal"
        elif 'exec' in pattern_str or 'cmd' in pattern_str:
            return "command_injection"
        else:
            return "suspicious_pattern"
    
    async def _analyze_rate_patterns(
        self,
        ip: str,
        user_id: Optional[str]
    ) -> float:
        """Analyze request rate patterns for anomalies"""
        
        if not self.redis_client:
            return 0.0
        
        key = f"rate:{ip}:{user_id or 'anon'}"
        
        # Get request count in last minute
        count = await self.redis_client.incr(key)
        if count == 1:
            await self.redis_client.expire(key, 60)
        
        # Calculate threat score based on rate
        if count > self.request_rate_threshold * 2:
            return 0.9
        elif count > self.request_rate_threshold:
            return 0.6
        elif count > self.request_rate_threshold * 0.5:
            return 0.3
        
        return 0.0
    
    async def _analyze_user_behavior(
        self,
        user_id: str,
        request_data: Dict[str, Any]
    ) -> float:
        """Analyze user behavior for anomalies"""
        
        # Get user's historical behavior
        behavior = self.user_behavior[user_id]
        
        # Add current request
        behavior.append({
            'timestamp': datetime.utcnow(),
            'path': request_data.get('path'),
            'ip': request_data.get('ip_address'),
            'user_agent': request_data.get('headers', {}).get('user-agent')
        })
        
        # Check for anomalies
        anomaly_score = 0.0
        
        # 1. Rapid IP changes
        recent_ips = set(b['ip'] for b in list(behavior)[-10:])
        if len(recent_ips) > 3:
            anomaly_score += 0.3
        
        # 2. Unusual access patterns
        if len(behavior) >= 10:
            recent_paths = [b['path'] for b in list(behavior)[-10:]]
            if self._is_unusual_pattern(recent_paths):
                anomaly_score += 0.4
        
        # 3. Time-based anomalies
        if self._is_unusual_time(datetime.utcnow(), user_id):
            anomaly_score += 0.2
        
        return min(anomaly_score, 1.0)
    
    def _is_unusual_pattern(self, paths: List[str]) -> bool:
        """Detect unusual access patterns"""
        
        # Check for scanning behavior
        unique_paths = set(paths)
        if len(unique_paths) > 8:  # Many different paths in short time
            return True
        
        # Check for repeated sensitive endpoints
        sensitive_endpoints = ['/admin', '/api/v1/users', '/api/v1/audit']
        sensitive_count = sum(1 for p in paths if any(s in p for s in sensitive_endpoints))
        if sensitive_count > 5:
            return True
        
        return False
    
    def _is_unusual_time(self, timestamp: datetime, user_id: str) -> bool:
        """Check if access time is unusual for user"""
        
        # Simple check - would use ML model in production
        hour = timestamp.hour
        
        # Suspicious hours (3 AM - 5 AM)
        if 3 <= hour <= 5:
            return True
        
        return False
    
    async def _detect_authentication_attacks(
        self,
        ip: str,
        user_id: Optional[str],
        request_data: Dict[str, Any]
    ) -> float:
        """Detect authentication-specific attacks"""
        
        if not self.redis_client:
            return 0.0
        
        # Track failed login attempts
        if request_data.get('status_code') in [401, 403]:
            key = f"failed_auth:{ip}"
            count = await self.redis_client.incr(key)
            
            if count == 1:
                await self.redis_client.expire(key, self.failed_login_window)
            
            # Check for brute force
            if count > self.failed_login_threshold * 2:
                return 0.9
            elif count > self.failed_login_threshold:
                return 0.7
            elif count > self.failed_login_threshold * 0.5:
                return 0.4
        
        # Check for credential stuffing patterns
        if await self._detect_credential_stuffing(ip):
            return 0.8
        
        return 0.0
    
    async def _detect_credential_stuffing(self, ip: str) -> bool:
        """Detect credential stuffing attacks"""
        
        if not self.redis_client:
            return False
        
        # Check for multiple usernames from same IP
        key = f"auth_users:{ip}"
        users = await self.redis_client.smembers(key)
        
        if len(users) > 10:  # Same IP trying many different accounts
            return True
        
        return False
    
    def _detect_bot_activity(
        self,
        headers: Dict[str, str],
        request_data: Dict[str, Any]
    ) -> float:
        """Detect bot and automated activity"""
        
        score = 0.0
        
        user_agent = headers.get('user-agent', '').lower()
        
        # Check for known bot user agents
        bot_indicators = [
            'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget',
            'python', 'java', 'ruby', 'perl', 'php'
        ]
        
        for indicator in bot_indicators:
            if indicator in user_agent:
                score += 0.3
                break
        
        # Check for missing standard headers
        expected_headers = ['user-agent', 'accept', 'accept-language']
        missing = sum(1 for h in expected_headers if h not in headers)
        score += missing * 0.2
        
        # Check for suspicious header combinations
        if 'x-forwarded-for' in headers and 'x-real-ip' in headers:
            score += 0.2
        
        # Check request timing patterns (would use ML in production)
        # For now, just a placeholder
        
        return min(score, 1.0)
    
    async def _create_threat_event(
        self,
        threat_level: ThreatLevel,
        indicators: List[ThreatIndicator],
        request_data: Dict[str, Any]
    ):
        """Create and store threat event"""
        
        import uuid
        
        # Determine threat type from indicators
        threat_types = [i.indicator_type for i in indicators]
        
        if 'auth_attack' in threat_types:
            threat_type = ThreatType.BRUTE_FORCE
        elif 'sql_injection' in threat_types:
            threat_type = ThreatType.SQL_INJECTION
        elif 'xss_attempt' in threat_types:
            threat_type = ThreatType.XSS_ATTEMPT
        elif 'rate_anomaly' in threat_types:
            threat_type = ThreatType.DDOS_ATTACK
        else:
            threat_type = ThreatType.SUSPICIOUS_BEHAVIOR
        
        event = ThreatEvent(
            event_id=str(uuid.uuid4()),
            threat_type=threat_type,
            threat_level=threat_level,
            source_ip=request_data.get('ip_address', 'unknown'),
            user_id=request_data.get('user_id'),
            target_resource=request_data.get('path', 'unknown'),
            indicators=indicators,
            confidence_score=max(i.confidence for i in indicators),
            timestamp=datetime.utcnow(),
            metadata=request_data
        )
        
        # Store event
        self.active_threats[event.event_id] = event
        
        # Take automated response
        await self._respond_to_threat(event)
        
        # Send to Redis for distributed tracking
        if self.redis_client:
            await self.redis_client.setex(
                f"threat:{event.event_id}",
                3600,  # Keep for 1 hour
                json.dumps({
                    'threat_type': threat_type.value,
                    'threat_level': threat_level.value,
                    'source_ip': event.source_ip,
                    'timestamp': event.timestamp.isoformat()
                })
            )
    
    async def _respond_to_threat(self, event: ThreatEvent):
        """Automated threat response"""
        
        responses = []
        
        if event.threat_level == ThreatLevel.CRITICAL:
            # Block IP immediately
            await self._block_ip(event.source_ip, duration=3600)
            responses.append("ip_blocked")
            
            # Lock user account if applicable
            if event.user_id:
                await self._lock_user_account(event.user_id)
                responses.append("account_locked")
            
            # Alert security team
            await self._send_security_alert(event)
            responses.append("alert_sent")
        
        elif event.threat_level == ThreatLevel.HIGH:
            # Temporary IP block
            await self._block_ip(event.source_ip, duration=600)
            responses.append("ip_temp_blocked")
            
            # Increase monitoring
            await self._increase_monitoring(event.source_ip)
            responses.append("monitoring_increased")
        
        elif event.threat_level == ThreatLevel.MEDIUM:
            # Add to watchlist
            await self._add_to_watchlist(event.source_ip)
            responses.append("added_to_watchlist")
        
        event.response_actions = responses
    
    async def _block_ip(self, ip: str, duration: int):
        """Block an IP address"""
        
        self.blocked_ips.add(ip)
        
        if self.redis_client:
            await self.redis_client.setex(
                f"blocked_ip:{ip}",
                duration,
                "1"
            )
        
        logger.warning(f"Blocked IP {ip} for {duration} seconds")
    
    async def _lock_user_account(self, user_id: str):
        """Lock a user account"""
        
        if self.redis_client:
            await self.redis_client.setex(
                f"locked_account:{user_id}",
                3600,  # 1 hour
                "1"
            )
        
        logger.warning(f"Locked user account {user_id}")
    
    async def _send_security_alert(self, event: ThreatEvent):
        """Send security alert to team"""
        
        # Would integrate with PagerDuty, Slack, etc.
        logger.critical(
            f"SECURITY ALERT: {event.threat_type.value} detected from {event.source_ip}"
        )
    
    async def _increase_monitoring(self, ip: str):
        """Increase monitoring for suspicious IP"""
        
        if self.redis_client:
            await self.redis_client.sadd("high_monitoring_ips", ip)
    
    async def _add_to_watchlist(self, ip: str):
        """Add IP to watchlist"""
        
        if self.redis_client:
            await self.redis_client.sadd("watchlist_ips", ip)
    
    async def _threat_monitoring_loop(self):
        """Background task for continuous threat monitoring"""
        
        while True:
            try:
                await self._analyze_threat_trends()
                await self._cleanup_old_threats()
                await asyncio.sleep(60)  # Run every minute
            except Exception as e:
                logger.error(f"Threat monitoring error: {e}")
                await asyncio.sleep(120)
    
    async def _analyze_threat_trends(self):
        """Analyze threat trends and patterns"""
        
        if not self.redis_client:
            return
        
        # Get recent threats
        threat_keys = await self.redis_client.keys("threat:*")
        
        if len(threat_keys) > 100:
            # Potential coordinated attack
            logger.warning(f"High threat activity detected: {len(threat_keys)} threats")
    
    async def _cleanup_old_threats(self):
        """Clean up old threat data"""
        
        cutoff = datetime.utcnow() - timedelta(hours=1)
        
        to_remove = []
        for event_id, event in self.active_threats.items():
            if event.timestamp < cutoff:
                to_remove.append(event_id)
        
        for event_id in to_remove:
            del self.active_threats[event_id]
    
    async def _update_threat_intelligence(self):
        """Update threat intelligence feeds"""
        
        while True:
            try:
                await self._fetch_threat_feeds()
                await asyncio.sleep(3600)  # Update hourly
            except Exception as e:
                logger.error(f"Failed to update threat intelligence: {e}")
                await asyncio.sleep(7200)
    
    async def _fetch_threat_feeds(self):
        """Fetch latest threat intelligence feeds"""
        
        # Would integrate with real threat feeds
        # For example: AbuseIPDB, AlienVault OTX, etc.
    
    async def _load_ip_reputation(self):
        """Load IP reputation database"""
        
        # Would load from threat intelligence feeds
        # For now, using sample data
        suspicious_ips = [
            "192.168.1.100",  # Example suspicious IP
        ]
        
        for ip in suspicious_ips:
            self.ip_reputation[ip] = 0.8
    
    async def get_threat_statistics(self) -> Dict[str, Any]:
        """Get current threat statistics"""
        
        stats = {
            "active_threats": len(self.active_threats),
            "blocked_ips": len(self.blocked_ips),
            "threat_levels": defaultdict(int),
            "threat_types": defaultdict(int),
            "top_source_ips": [],
            "trend": "stable"
        }
        
        for event in self.active_threats.values():
            stats["threat_levels"][event.threat_level.value] += 1
            stats["threat_types"][event.threat_type.value] += 1
        
        # Get top threat sources
        ip_counts = defaultdict(int)
        for event in self.active_threats.values():
            ip_counts[event.source_ip] += 1
        
        stats["top_source_ips"] = sorted(
            ip_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return stats