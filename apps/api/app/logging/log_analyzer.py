"""
Log Analyzer and Aggregation Tools
Advanced log analysis, pattern detection, and metrics extraction
"""

import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import statistics
from enum import Enum
import redis.asyncio as aioredis
import structlog

from app.config import settings

logger = structlog.get_logger()


class LogLevel(Enum):
    """Log level enumeration"""
    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: datetime
    level: str
    message: str
    service: str
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    trace_id: Optional[str] = None
    event_type: Optional[str] = None
    duration_ms: Optional[float] = None
    status_code: Optional[int] = None
    error_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LogPattern:
    """Detected log pattern"""
    pattern_id: str
    pattern_type: str
    frequency: int
    first_seen: datetime
    last_seen: datetime
    sample_messages: List[str] = field(default_factory=list)
    affected_users: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance metrics extracted from logs"""
    total_requests: int
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    error_rate: float
    slowest_endpoints: List[Tuple[str, float]]
    error_distribution: Dict[str, int]
    time_period: str


@dataclass
class SecurityAlert:
    """Security alert from log analysis"""
    alert_id: str
    severity: AlertSeverity
    alert_type: str
    description: str
    timestamp: datetime
    affected_users: List[str]
    source_ips: List[str]
    evidence: Dict[str, Any]
    recommendations: List[str]


class LogAnalyzer:
    """Advanced log analysis and pattern detection"""

    def __init__(self):
        self.redis_client: Optional[aioredis.Redis] = None
        self.known_patterns: Dict[str, LogPattern] = {}
        self.performance_cache: Dict[str, PerformanceMetrics] = {}

        # Pattern detection rules
        self.error_patterns = {
            "database_timeout": r"(?i)database.*timeout|connection.*timeout|query.*timeout",
            "authentication_failure": r"(?i)authentication.*failed|invalid.*credentials|unauthorized",
            "rate_limit_exceeded": r"(?i)rate.*limit.*exceeded|too.*many.*requests",
            "external_api_failure": r"(?i)external.*api.*error|service.*unavailable|502|503|504",
            "memory_error": r"(?i)out.*of.*memory|memory.*error|allocation.*failed",
            "permission_denied": r"(?i)permission.*denied|access.*denied|forbidden",
            "sql_injection": r"(?i)sql.*injection|union.*select|drop.*table|update.*set",
            "xss_attempt": r"(?i)<script|javascript:|onload=|onerror=",
        }

        # Performance thresholds
        self.performance_thresholds = {
            "slow_request": 1000,  # ms
            "very_slow_request": 5000,  # ms
            "high_error_rate": 0.05,  # 5%
            "critical_error_rate": 0.10,  # 10%
        }

        # Security detection rules
        self.security_patterns = {
            "brute_force": {
                "event_type": "authentication_failure",
                "threshold": 5,
                "time_window": 300,  # 5 minutes
            },
            "credential_stuffing": {
                "event_type": "authentication_failure",
                "threshold": 10,
                "time_window": 600,  # 10 minutes
                "unique_users": 5,
            },
            "privilege_escalation": {
                "event_type": "authorization_denied",
                "threshold": 3,
                "time_window": 300,
            },
            "data_exfiltration": {
                "event_type": "data_export",
                "threshold": 1000,  # records
                "time_window": 3600,  # 1 hour
            },
        }

    async def initialize_redis(self):
        """Initialize Redis connection for log storage"""
        try:
            self.redis_client = aioredis.from_url(
                f"redis://{getattr(settings, 'REDIS_HOST', 'localhost')}:{getattr(settings, 'REDIS_PORT', 6379)}/3",
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Log analyzer Redis connection initialized")
        except Exception as e:
            logger.error("Failed to initialize log analyzer Redis", error=str(e))

    async def store_log_entry(self, log_entry: LogEntry):
        """Store log entry for analysis"""
        if not self.redis_client:
            return

        try:
            # Store log entry
            log_data = {
                "timestamp": log_entry.timestamp.isoformat(),
                "level": log_entry.level,
                "message": log_entry.message,
                "service": log_entry.service,
                "request_id": log_entry.request_id,
                "user_id": log_entry.user_id,
                "trace_id": log_entry.trace_id,
                "event_type": log_entry.event_type,
                "duration_ms": log_entry.duration_ms,
                "status_code": log_entry.status_code,
                "error_type": log_entry.error_type,
                "metadata": json.dumps(log_entry.metadata) if log_entry.metadata else None
            }

            # Store in Redis with timestamp-based key
            timestamp = int(log_entry.timestamp.timestamp() * 1000)
            log_key = f"log:{timestamp}:{log_entry.request_id or 'unknown'}"

            await self.redis_client.hset(log_key, mapping=log_data)

            # Add to time-based index
            await self.redis_client.zadd("logs:timeline", {log_key: timestamp})

            # Add to level-based index
            await self.redis_client.zadd(f"logs:level:{log_entry.level.lower()}", {log_key: timestamp})

            # Add to event type index if available
            if log_entry.event_type:
                await self.redis_client.zadd(f"logs:event:{log_entry.event_type}", {log_key: timestamp})

            # Add to user index if available
            if log_entry.user_id:
                await self.redis_client.zadd(f"logs:user:{log_entry.user_id}", {log_key: timestamp})

            # Set expiration (keep logs for 30 days)
            await self.redis_client.expire(log_key, 2592000)

        except Exception as e:
            logger.error("Failed to store log entry", error=str(e))

    async def analyze_logs(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Perform comprehensive log analysis for time period"""
        if not self.redis_client:
            return {"error": "Redis not available"}

        try:
            # Get logs in time range
            start_ts = int(start_time.timestamp() * 1000)
            end_ts = int(end_time.timestamp() * 1000)

            log_keys = await self.redis_client.zrangebyscore("logs:timeline", start_ts, end_ts)

            if not log_keys:
                return {"message": "No logs found in time range"}

            # Retrieve log entries
            logs = []
            for log_key in log_keys:
                log_data = await self.redis_client.hgetall(log_key)
                if log_data:
                    # Parse log entry
                    log_entry = LogEntry(
                        timestamp=datetime.fromisoformat(log_data['timestamp']),
                        level=log_data['level'],
                        message=log_data['message'],
                        service=log_data['service'],
                        request_id=log_data.get('request_id'),
                        user_id=log_data.get('user_id'),
                        trace_id=log_data.get('trace_id'),
                        event_type=log_data.get('event_type'),
                        duration_ms=float(log_data['duration_ms']) if log_data.get('duration_ms') else None,
                        status_code=int(log_data['status_code']) if log_data.get('status_code') else None,
                        error_type=log_data.get('error_type'),
                        metadata=json.loads(log_data['metadata']) if log_data.get('metadata') else {}
                    )
                    logs.append(log_entry)

            # Perform analysis
            analysis = {
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                    "duration_hours": (end_time - start_time).total_seconds() / 3600
                },
                "summary": await self._analyze_summary(logs),
                "performance": await self._analyze_performance(logs),
                "errors": await self._analyze_errors(logs),
                "security": await self._analyze_security(logs),
                "patterns": await self._detect_patterns(logs),
                "recommendations": await self._generate_recommendations(logs)
            }

            return analysis

        except Exception as e:
            logger.error("Failed to analyze logs", error=str(e))
            return {"error": "Analysis failed"}

    async def _analyze_summary(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Generate summary statistics"""
        if not logs:
            return {}

        level_counts = Counter(log.level for log in logs)
        event_type_counts = Counter(log.event_type for log in logs if log.event_type)
        unique_users = len(set(log.user_id for log in logs if log.user_id))
        unique_requests = len(set(log.request_id for log in logs if log.request_id))

        return {
            "total_logs": len(logs),
            "level_distribution": dict(level_counts),
            "event_type_distribution": dict(event_type_counts.most_common(10)),
            "unique_users": unique_users,
            "unique_requests": unique_requests,
            "time_span": {
                "first_log": min(log.timestamp for log in logs).isoformat(),
                "last_log": max(log.timestamp for log in logs).isoformat()
            }
        }

    async def _analyze_performance(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Analyze performance metrics"""
        request_logs = [log for log in logs if log.duration_ms is not None]

        if not request_logs:
            return {"message": "No performance data available"}

        durations = [log.duration_ms for log in request_logs]
        durations.sort()

        # Status code analysis
        status_codes = [log.status_code for log in request_logs if log.status_code]
        error_responses = len([sc for sc in status_codes if sc >= 400])
        total_responses = len(status_codes)

        # Endpoint analysis
        endpoint_performance = defaultdict(list)
        for log in request_logs:
            if hasattr(log.metadata, 'get') and log.metadata.get('http_path'):
                endpoint_performance[log.metadata['http_path']].append(log.duration_ms)

        slowest_endpoints = []
        for endpoint, times in endpoint_performance.items():
            avg_time = statistics.mean(times)
            slowest_endpoints.append((endpoint, avg_time))
        slowest_endpoints.sort(key=lambda x: x[1], reverse=True)

        return {
            "total_requests": len(request_logs),
            "avg_response_time": statistics.mean(durations),
            "median_response_time": statistics.median(durations),
            "p95_response_time": durations[int(len(durations) * 0.95)] if durations else 0,
            "p99_response_time": durations[int(len(durations) * 0.99)] if durations else 0,
            "min_response_time": min(durations),
            "max_response_time": max(durations),
            "error_rate": error_responses / total_responses if total_responses > 0 else 0,
            "slow_requests": len([d for d in durations if d > self.performance_thresholds["slow_request"]]),
            "very_slow_requests": len([d for d in durations if d > self.performance_thresholds["very_slow_request"]]),
            "slowest_endpoints": slowest_endpoints[:10]
        }

    async def _analyze_errors(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Analyze error patterns and distribution"""
        error_logs = [log for log in logs if log.level.upper() in ['ERROR', 'CRITICAL']]

        if not error_logs:
            return {"message": "No errors found"}

        # Error type distribution
        error_types = Counter(log.error_type for log in error_logs if log.error_type)
        error_messages = Counter(log.message for log in error_logs)

        # Error timeline
        error_timeline = defaultdict(int)
        for log in error_logs:
            hour_key = log.timestamp.replace(minute=0, second=0, microsecond=0)
            error_timeline[hour_key.isoformat()] += 1

        # Users affected by errors
        affected_users = set(log.user_id for log in error_logs if log.user_id)

        return {
            "total_errors": len(error_logs),
            "error_rate": len(error_logs) / len(logs) if logs else 0,
            "error_types": dict(error_types.most_common(10)),
            "common_error_messages": dict(error_messages.most_common(10)),
            "affected_users": len(affected_users),
            "error_timeline": dict(error_timeline)
        }

    async def _analyze_security(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Analyze security events and threats"""
        security_logs = [log for log in logs if log.event_type == "security_event"]

        # Authentication failures
        auth_failures = [log for log in logs if log.event_type == "authentication"]
        failed_auths = [log for log in auth_failures if log.metadata.get('auth_success') is False]

        # Authorization denials
        authz_denials = [log for log in logs if log.event_type == "authorization"]
        denied_authz = [log for log in authz_denials if log.metadata.get('authz_allowed') is False]

        # Suspicious patterns
        suspicious_ips = self._detect_suspicious_ips(logs)
        brute_force_attempts = self._detect_brute_force(failed_auths)

        return {
            "security_events": len(security_logs),
            "authentication_failures": len(failed_auths),
            "authorization_denials": len(denied_authz),
            "suspicious_ips": suspicious_ips,
            "brute_force_attempts": brute_force_attempts,
            "security_recommendations": self._generate_security_recommendations(security_logs)
        }

    async def _detect_patterns(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Detect patterns in log messages"""
        patterns_detected = {}

        # Check for known error patterns
        for pattern_name, pattern_regex in self.error_patterns.items():
            matches = []
            for log in logs:
                if re.search(pattern_regex, log.message):
                    matches.append({
                        "timestamp": log.timestamp.isoformat(),
                        "message": log.message,
                        "user_id": log.user_id,
                        "request_id": log.request_id
                    })

            if matches:
                patterns_detected[pattern_name] = {
                    "count": len(matches),
                    "first_occurrence": matches[0]["timestamp"],
                    "last_occurrence": matches[-1]["timestamp"],
                    "sample_logs": matches[:5]  # First 5 occurrences
                }

        return patterns_detected

    async def _generate_recommendations(self, logs: List[LogEntry]) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []

        # Performance recommendations
        slow_requests = [log for log in logs if log.duration_ms and log.duration_ms > self.performance_thresholds["slow_request"]]
        if len(slow_requests) > len(logs) * 0.1:  # More than 10% slow requests
            recommendations.append("High number of slow requests detected. Consider optimizing database queries and API endpoints.")

        # Error rate recommendations
        error_logs = [log for log in logs if log.level.upper() in ['ERROR', 'CRITICAL']]
        if len(error_logs) > len(logs) * self.performance_thresholds["high_error_rate"]:
            recommendations.append("High error rate detected. Review error logs and implement proper error handling.")

        # Security recommendations
        auth_failures = [log for log in logs if log.event_type == "authentication" and log.metadata.get('auth_success') is False]
        if len(auth_failures) > 10:
            recommendations.append("Multiple authentication failures detected. Consider implementing account lockout policies.")

        return recommendations

    def _detect_suspicious_ips(self, logs: List[LogEntry]) -> List[Dict[str, Any]]:
        """Detect suspicious IP addresses"""
        ip_activity = defaultdict(lambda: {"requests": 0, "errors": 0, "failed_auths": 0})

        for log in logs:
            client_ip = log.metadata.get('client_ip')
            if not client_ip:
                continue

            ip_activity[client_ip]["requests"] += 1

            if log.level.upper() in ['ERROR', 'CRITICAL']:
                ip_activity[client_ip]["errors"] += 1

            if log.event_type == "authentication" and log.metadata.get('auth_success') is False:
                ip_activity[client_ip]["failed_auths"] += 1

        suspicious_ips = []
        for ip, activity in ip_activity.items():
            # Define suspicious criteria
            if (activity["failed_auths"] > 5 or
                activity["errors"] > activity["requests"] * 0.5 or
                activity["requests"] > 100):  # High volume
                suspicious_ips.append({
                    "ip": ip,
                    "activity": activity,
                    "risk_score": self._calculate_ip_risk_score(activity)
                })

        return sorted(suspicious_ips, key=lambda x: x["risk_score"], reverse=True)

    def _detect_brute_force(self, auth_failure_logs: List[LogEntry]) -> List[Dict[str, Any]]:
        """Detect potential brute force attacks"""
        # Group by IP and time windows
        ip_attempts = defaultdict(list)

        for log in auth_failure_logs:
            client_ip = log.metadata.get('client_ip')
            if client_ip:
                ip_attempts[client_ip].append(log.timestamp)

        brute_force_attempts = []
        for ip, timestamps in ip_attempts.items():
            # Sort timestamps
            timestamps.sort()

            # Check for rapid-fire attempts (5+ failures in 5 minutes)
            for i in range(len(timestamps) - 4):
                window_start = timestamps[i]
                window_end = timestamps[i + 4]

                if (window_end - window_start).total_seconds() <= 300:  # 5 minutes
                    brute_force_attempts.append({
                        "ip": ip,
                        "start_time": window_start.isoformat(),
                        "end_time": window_end.isoformat(),
                        "attempts": 5,
                        "severity": "high"
                    })
                    break

        return brute_force_attempts

    def _calculate_ip_risk_score(self, activity: Dict[str, int]) -> float:
        """Calculate risk score for an IP address"""
        score = 0.0

        # Failed authentication attempts
        score += activity["failed_auths"] * 2

        # Error rate
        if activity["requests"] > 0:
            error_rate = activity["errors"] / activity["requests"]
            score += error_rate * 10

        # High volume requests
        if activity["requests"] > 50:
            score += min(activity["requests"] / 10, 10)

        return min(score, 100.0)  # Cap at 100

    def _generate_security_recommendations(self, security_logs: List[LogEntry]) -> List[str]:
        """Generate security-specific recommendations"""
        recommendations = []

        if len(security_logs) > 10:
            recommendations.append("Multiple security events detected. Review security monitoring and incident response procedures.")

        high_severity = [log for log in security_logs if log.metadata.get('security_severity') == 'high']
        if high_severity:
            recommendations.append("High-severity security events detected. Immediate investigation recommended.")

        return recommendations

    async def get_log_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """Get recent log statistics"""
        if not self.redis_client:
            return {"error": "Redis not available"}

        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        try:
            analysis = await self.analyze_logs(start_time, end_time)
            return analysis
        except Exception as e:
            logger.error("Failed to get log statistics", error=str(e))
            return {"error": "Failed to retrieve statistics"}

    async def cleanup_old_logs(self, days: int = 30):
        """Clean up logs older than specified days"""
        if not self.redis_client:
            return

        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            cutoff_ts = int(cutoff_time.timestamp() * 1000)

            # Get old log keys
            old_log_keys = await self.redis_client.zrangebyscore("logs:timeline", 0, cutoff_ts)

            # Delete old logs
            if old_log_keys:
                await self.redis_client.delete(*old_log_keys)
                await self.redis_client.zremrangebyscore("logs:timeline", 0, cutoff_ts)

                logger.info("Cleaned up old logs", deleted_count=len(old_log_keys), cutoff_days=days)

        except Exception as e:
            logger.error("Failed to cleanup old logs", error=str(e))


# Global log analyzer instance
log_analyzer = LogAnalyzer()


# Helper functions
async def initialize_log_analyzer():
    """Initialize the log analyzer"""
    await log_analyzer.initialize_redis()


async def analyze_recent_logs(hours: int = 24) -> Dict[str, Any]:
    """Analyze recent logs for patterns and issues"""
    return await log_analyzer.get_log_statistics(hours)


async def store_log_for_analysis(log_data: Dict[str, Any]):
    """Store a log entry for analysis"""
    try:
        log_entry = LogEntry(
            timestamp=datetime.fromisoformat(log_data['timestamp']),
            level=log_data['level'],
            message=log_data['message'],
            service=log_data.get('service', 'unknown'),
            request_id=log_data.get('request_id'),
            user_id=log_data.get('user_id'),
            trace_id=log_data.get('trace_id'),
            event_type=log_data.get('event_type'),
            duration_ms=log_data.get('duration_ms'),
            status_code=log_data.get('status_code'),
            error_type=log_data.get('error_type'),
            metadata=log_data.get('metadata', {})
        )

        await log_analyzer.store_log_entry(log_entry)

    except Exception as e:
        logger.error("Failed to store log for analysis", error=str(e))