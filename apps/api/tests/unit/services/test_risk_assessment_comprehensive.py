import pytest
pytestmark = pytest.mark.asyncio


"""
Comprehensive unit tests for RiskAssessmentService - targeting 100% coverage
This test covers all risk assessment operations, fraud detection, security analysis
Expected to cover 310 lines in app/services/risk_assessment_service.py
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import patch

from app.services.risk_assessment_service import RiskAssessmentService


class TestRiskAssessmentServiceInitialization:
    """Test risk assessment service initialization and configuration."""

    def test_risk_assessment_service_init(self):
        """Test risk assessment service initializes correctly."""
        service = RiskAssessmentService()

        assert hasattr(service, 'redis_client')
        assert hasattr(service, 'ml_model')
        assert hasattr(service, 'risk_thresholds')
        assert hasattr(service, 'fraud_patterns')

    def test_risk_thresholds_configuration(self):
        """Test risk threshold configuration."""
        service = RiskAssessmentService()

        assert 'low' in service.risk_thresholds
        assert 'medium' in service.risk_thresholds
        assert 'high' in service.risk_thresholds
        assert 'critical' in service.risk_thresholds

        # Verify threshold values are properly ordered
        assert service.risk_thresholds['low'] < service.risk_thresholds['medium']
        assert service.risk_thresholds['medium'] < service.risk_thresholds['high']
        assert service.risk_thresholds['high'] < service.risk_thresholds['critical']


class TestUserRiskAssessment:
    """Test user-based risk assessment functionality."""

    def setup_method(self):
        """Setup for each test."""
        self.service = RiskAssessmentService()

    @pytest.mark.asyncio
    async def test_assess_user_risk_low_risk_user(self):
        """Test risk assessment for low-risk user."""
        user_data = {
            "id": str(uuid4()),
            "email": "user@legitimate-company.com",
            "registration_date": datetime.now() - timedelta(days=30),
            "login_count": 50,
            "failed_login_attempts": 1,
            "ip_address": "192.168.1.100",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "country": "US"
        }

        with patch.object(self.service, '_check_ip_reputation') as mock_ip, \
             patch.object(self.service, '_analyze_behavior_patterns') as mock_behavior, \
             patch.object(self.service, '_check_device_fingerprint') as mock_device:

            mock_ip.return_value = {"score": 10, "reputation": "good"}
            mock_behavior.return_value = {"score": 15, "patterns": []}
            mock_device.return_value = {"score": 5, "risk_level": "low"}

            result = await self.service.assess_user_risk(user_data)

            assert result["risk_level"] == "low"
            assert result["risk_score"] <= self.service.risk_thresholds["medium"]
            assert "recommendations" in result

    @pytest.mark.asyncio
    async def test_assess_user_risk_high_risk_user(self):
        """Test risk assessment for high-risk user."""
        user_data = {
            "id": str(uuid4()),
            "email": "suspicious@temp-email.com",
            "registration_date": datetime.now() - timedelta(minutes=5),
            "login_count": 100,
            "failed_login_attempts": 25,
            "ip_address": "tor-exit-node.com",
            "user_agent": "Suspicious Bot/1.0",
            "country": "XX"
        }

        with patch.object(self.service, '_check_ip_reputation') as mock_ip, \
             patch.object(self.service, '_analyze_behavior_patterns') as mock_behavior, \
             patch.object(self.service, '_check_device_fingerprint') as mock_device:

            mock_ip.return_value = {"score": 80, "reputation": "malicious"}
            mock_behavior.return_value = {"score": 90, "patterns": ["rapid_registration", "bot_behavior"]}
            mock_device.return_value = {"score": 85, "risk_level": "high"}

            result = await self.service.assess_user_risk(user_data)

            assert result["risk_level"] == "high"
            assert result["risk_score"] >= self.service.risk_thresholds["high"]
            assert len(result["risk_factors"]) > 0

    @pytest.mark.asyncio
    async def test_assess_user_risk_new_user(self):
        """Test risk assessment for new user with limited data."""
        user_data = {
            "id": str(uuid4()),
            "email": "newuser@example.com",
            "registration_date": datetime.now(),
            "login_count": 1,
            "failed_login_attempts": 0,
            "ip_address": "192.168.1.200",
            "user_agent": "Mozilla/5.0 (Mac OS X)",
            "country": "CA"
        }

        with patch.object(self.service, '_check_ip_reputation') as mock_ip, \
             patch.object(self.service, '_analyze_behavior_patterns') as mock_behavior, \
             patch.object(self.service, '_check_device_fingerprint') as mock_device:

            mock_ip.return_value = {"score": 20, "reputation": "unknown"}
            mock_behavior.return_value = {"score": 25, "patterns": ["new_user"]}
            mock_device.return_value = {"score": 30, "risk_level": "medium"}

            result = await self.service.assess_user_risk(user_data)

            assert result["risk_level"] in ["low", "medium"]
            assert "new_user" in result.get("analysis_notes", "")


class TestIPReputationChecking:
    """Test IP address reputation checking functionality."""

    def setup_method(self):
        """Setup for each test."""
        self.service = RiskAssessmentService()

    @pytest.mark.asyncio
    async def test_check_ip_reputation_clean_ip(self):
        """Test IP reputation check for clean IP address."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value.json.return_value = {
                "ip": "192.168.1.100",
                "reputation": "good",
                "threat_score": 5,
                "categories": [],
                "country": "US"
            }
            mock_get.return_value.status_code = 200

            result = await self.service._check_ip_reputation("192.168.1.100")

            assert result["reputation"] == "good"
            assert result["score"] <= 20
            assert "192.168.1.100" in result["analysis"]

    @pytest.mark.asyncio
    async def test_check_ip_reputation_malicious_ip(self):
        """Test IP reputation check for malicious IP address."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value.json.return_value = {
                "ip": "malicious.tor-node.com",
                "reputation": "malicious",
                "threat_score": 95,
                "categories": ["tor_exit_node", "known_attacker"],
                "country": "XX"
            }
            mock_get.return_value.status_code = 200

            result = await self.service._check_ip_reputation("malicious.tor-node.com")

            assert result["reputation"] == "malicious"
            assert result["score"] >= 80
            assert "tor_exit_node" in result["categories"]

    @pytest.mark.asyncio
    async def test_check_ip_reputation_api_failure(self):
        """Test IP reputation check when API fails."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = Exception("API unavailable")

            result = await self.service._check_ip_reputation("192.168.1.100")

            assert result["reputation"] == "unknown"
            assert result["score"] == 50  # Default moderate score
            assert "API error" in result["analysis"]

    @pytest.mark.asyncio
    async def test_check_ip_reputation_private_ip(self):
        """Test IP reputation check for private IP addresses."""
        private_ips = ["192.168.1.1", "10.0.0.1", "172.16.0.1", "127.0.0.1"]

        for ip in private_ips:
            result = await self.service._check_ip_reputation(ip)

            assert result["reputation"] == "private"
            assert result["score"] <= 10
            assert "private" in result["analysis"].lower()


class TestBehaviorPatternAnalysis:
    """Test behavior pattern analysis functionality."""

    def setup_method(self):
        """Setup for each test."""
        self.service = RiskAssessmentService()

    @pytest.mark.asyncio
    async def test_analyze_behavior_patterns_normal_behavior(self):
        """Test behavior analysis for normal user patterns."""
        user_data = {
            "login_count": 30,
            "failed_login_attempts": 2,
            "registration_date": datetime.now() - timedelta(days=15),
            "last_login": datetime.now() - timedelta(hours=2),
            "login_frequency": "regular",
            "session_duration_avg": 1800,  # 30 minutes
            "countries_accessed": ["US"],
            "devices_used": 2
        }

        result = await self.service._analyze_behavior_patterns(user_data)

        assert result["score"] <= 30
        assert "normal_behavior" in result["patterns"]
        assert result["risk_level"] == "low"

    @pytest.mark.asyncio
    async def test_analyze_behavior_patterns_suspicious_behavior(self):
        """Test behavior analysis for suspicious patterns."""
        user_data = {
            "login_count": 500,
            "failed_login_attempts": 100,
            "registration_date": datetime.now() - timedelta(hours=1),
            "last_login": datetime.now() - timedelta(minutes=1),
            "login_frequency": "rapid",
            "session_duration_avg": 30,  # 30 seconds
            "countries_accessed": ["US", "RU", "CN", "KP", "IR"],
            "devices_used": 50
        }

        result = await self.service._analyze_behavior_patterns(user_data)

        assert result["score"] >= 70
        assert "rapid_login_attempts" in result["patterns"]
        assert "multiple_countries" in result["patterns"]
        assert "short_sessions" in result["patterns"]
        assert result["risk_level"] == "high"

    @pytest.mark.asyncio
    async def test_analyze_behavior_patterns_bot_behavior(self):
        """Test behavior analysis for bot-like patterns."""
        user_data = {
            "login_count": 1000,
            "failed_login_attempts": 0,
            "registration_date": datetime.now() - timedelta(hours=2),
            "last_login": datetime.now(),
            "login_frequency": "constant",
            "session_duration_avg": 10,  # 10 seconds exactly
            "countries_accessed": ["US"],
            "devices_used": 1,
            "user_agent": "Bot/1.0",
            "request_interval_consistency": 0.99  # Highly consistent timing
        }

        result = await self.service._analyze_behavior_patterns(user_data)

        assert result["score"] >= 80
        assert "bot_behavior" in result["patterns"]
        assert "automated_activity" in result["patterns"]


class TestDeviceFingerprintAnalysis:
    """Test device fingerprinting and analysis."""

    def setup_method(self):
        """Setup for each test."""
        self.service = RiskAssessmentService()

    @pytest.mark.asyncio
    async def test_check_device_fingerprint_legitimate_device(self):
        """Test device fingerprint for legitimate device."""
        device_data = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "screen_resolution": "1920x1080",
            "timezone": "America/New_York",
            "language": "en-US",
            "platform": "Win32",
            "plugins": ["PDF Viewer", "Chrome PDF Viewer"],
            "canvas_fingerprint": "abc123def456",
            "webgl_fingerprint": "webgl789xyz"
        }

        result = await self.service._check_device_fingerprint(device_data)

        assert result["risk_level"] == "low"
        assert result["score"] <= 20
        assert "legitimate_browser" in result["analysis"]

    @pytest.mark.asyncio
    async def test_check_device_fingerprint_suspicious_device(self):
        """Test device fingerprint for suspicious device."""
        device_data = {
            "user_agent": "HeadlessChrome/1.0",
            "screen_resolution": "800x600",
            "timezone": "",
            "language": "",
            "platform": "Linux",
            "plugins": [],
            "canvas_fingerprint": "",
            "webgl_fingerprint": ""
        }

        result = await self.service._check_device_fingerprint(device_data)

        assert result["risk_level"] == "high"
        assert result["score"] >= 70
        assert "headless_browser" in result["analysis"]

    @pytest.mark.asyncio
    async def test_check_device_fingerprint_known_device(self):
        """Test device fingerprint for known/recognized device."""
        device_data = {
            "device_id": "known_device_123",
            "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)",
            "screen_resolution": "414x896",
            "timezone": "America/Los_Angeles",
            "language": "en-US"
        }

        with patch.object(self.service, '_check_device_history') as mock_history:
            mock_history.return_value = {
                "is_known": True,
                "first_seen": datetime.now() - timedelta(days=30),
                "login_count": 25,
                "trust_score": 85
            }

            result = await self.service._check_device_fingerprint(device_data)

            assert result["risk_level"] == "low"
            assert result["score"] <= 15
            assert "known_device" in result["analysis"]


class TestFraudDetection:
    """Test fraud detection algorithms."""

    def setup_method(self):
        """Setup for each test."""
        self.service = RiskAssessmentService()

    @pytest.mark.asyncio
    async def test_detect_fraud_patterns_account_takeover(self):
        """Test detection of account takeover patterns."""
        activity_data = {
            "user_id": str(uuid4()),
            "recent_activities": [
                {"action": "login", "ip": "192.168.1.100", "timestamp": datetime.now() - timedelta(hours=2)},
                {"action": "password_change", "ip": "suspicious.ip.com", "timestamp": datetime.now() - timedelta(hours=1)},
                {"action": "login", "ip": "suspicious.ip.com", "timestamp": datetime.now() - timedelta(minutes=30)},
                {"action": "profile_update", "ip": "suspicious.ip.com", "timestamp": datetime.now()}
            ]
        }

        result = await self.service.detect_fraud_patterns(activity_data)

        assert "account_takeover" in result["detected_patterns"]
        assert result["fraud_score"] >= 70
        assert result["recommendation"] == "immediate_action"

    @pytest.mark.asyncio
    async def test_detect_fraud_patterns_credential_stuffing(self):
        """Test detection of credential stuffing attacks."""
        activity_data = {
            "ip_address": "attacker.ip.com",
            "recent_activities": [
                {"action": "failed_login", "username": "user1@example.com", "timestamp": datetime.now() - timedelta(minutes=10)},
                {"action": "failed_login", "username": "user2@example.com", "timestamp": datetime.now() - timedelta(minutes=9)},
                {"action": "failed_login", "username": "user3@example.com", "timestamp": datetime.now() - timedelta(minutes=8)},
                {"action": "failed_login", "username": "user4@example.com", "timestamp": datetime.now() - timedelta(minutes=7)},
                {"action": "failed_login", "username": "user5@example.com", "timestamp": datetime.now() - timedelta(minutes=6)}
            ]
        }

        result = await self.service.detect_fraud_patterns(activity_data)

        assert "credential_stuffing" in result["detected_patterns"]
        assert result["fraud_score"] >= 80
        assert "multiple_account_attempts" in result["indicators"]

    @pytest.mark.asyncio
    async def test_detect_fraud_patterns_velocity_abuse(self):
        """Test detection of velocity abuse patterns."""
        activity_data = {
            "user_id": str(uuid4()),
            "recent_activities": [
                {"action": "api_call", "endpoint": "/api/create", "timestamp": datetime.now() - timedelta(seconds=i)}
                for i in range(100)  # 100 API calls in 100 seconds
            ]
        }

        result = await self.service.detect_fraud_patterns(activity_data)

        assert "velocity_abuse" in result["detected_patterns"]
        assert result["fraud_score"] >= 60
        assert "rate_limit_exceeded" in result["indicators"]


class TestRiskMitigation:
    """Test risk mitigation strategies."""

    def setup_method(self):
        """Setup for each test."""
        self.service = RiskAssessmentService()

    @pytest.mark.asyncio
    async def test_suggest_mitigation_strategies_low_risk(self):
        """Test mitigation suggestions for low-risk scenarios."""
        risk_assessment = {
            "risk_level": "low",
            "risk_score": 15,
            "risk_factors": ["new_user"],
            "detected_patterns": []
        }

        result = await self.service.suggest_mitigation_strategies(risk_assessment)

        assert "continue_monitoring" in result["strategies"]
        assert result["urgency"] == "low"
        assert "immediate_action" not in result["strategies"]

    @pytest.mark.asyncio
    async def test_suggest_mitigation_strategies_high_risk(self):
        """Test mitigation suggestions for high-risk scenarios."""
        risk_assessment = {
            "risk_level": "high",
            "risk_score": 85,
            "risk_factors": ["malicious_ip", "bot_behavior", "rapid_attempts"],
            "detected_patterns": ["credential_stuffing", "account_takeover"]
        }

        result = await self.service.suggest_mitigation_strategies(risk_assessment)

        assert "immediate_block" in result["strategies"]
        assert "require_additional_verification" in result["strategies"]
        assert "alert_security_team" in result["strategies"]
        assert result["urgency"] == "critical"

    @pytest.mark.asyncio
    async def test_suggest_mitigation_strategies_medium_risk(self):
        """Test mitigation suggestions for medium-risk scenarios."""
        risk_assessment = {
            "risk_level": "medium",
            "risk_score": 45,
            "risk_factors": ["unknown_device", "multiple_countries"],
            "detected_patterns": ["unusual_activity"]
        }

        result = await self.service.suggest_mitigation_strategies(risk_assessment)

        assert "enhanced_monitoring" in result["strategies"]
        assert "step_up_authentication" in result["strategies"]
        assert result["urgency"] == "medium"


class TestRealtimeMonitoring:
    """Test real-time risk monitoring capabilities."""

    def setup_method(self):
        """Setup for each test."""
        self.service = RiskAssessmentService()

    @pytest.mark.asyncio
    async def test_realtime_risk_monitor_normal_activity(self):
        """Test real-time monitoring for normal activity."""
        with patch.object(self.service, '_get_activity_stream') as mock_stream:
            mock_stream.return_value = [
                {"user_id": "user1", "action": "login", "timestamp": datetime.now()},
                {"user_id": "user2", "action": "logout", "timestamp": datetime.now()},
                {"user_id": "user3", "action": "view_page", "timestamp": datetime.now()}
            ]

            result = await self.service.monitor_realtime_risk()

            assert result["status"] == "normal"
            assert result["active_threats"] == 0
            assert len(result["activity_summary"]) > 0

    @pytest.mark.asyncio
    async def test_realtime_risk_monitor_detected_threats(self):
        """Test real-time monitoring when threats are detected."""
        with patch.object(self.service, '_get_activity_stream') as mock_stream, \
             patch.object(self.service, 'detect_fraud_patterns') as mock_fraud:

            mock_stream.return_value = [
                {"user_id": "attacker1", "action": "failed_login", "ip": "malicious.ip", "timestamp": datetime.now()},
                {"user_id": "attacker1", "action": "failed_login", "ip": "malicious.ip", "timestamp": datetime.now()},
                {"user_id": "attacker1", "action": "failed_login", "ip": "malicious.ip", "timestamp": datetime.now()}
            ]

            mock_fraud.return_value = {
                "detected_patterns": ["brute_force"],
                "fraud_score": 90,
                "recommendation": "immediate_action"
            }

            result = await self.service.monitor_realtime_risk()

            assert result["status"] == "threat_detected"
            assert result["active_threats"] > 0
            assert len(result["threat_details"]) > 0


class TestErrorHandling:
    """Test error handling scenarios in risk assessment service."""

    def setup_method(self):
        """Setup for each test."""
        self.service = RiskAssessmentService()

    @pytest.mark.asyncio
    async def test_handle_ml_model_failure(self):
        """Test handling of ML model failures."""
        user_data = {"id": str(uuid4()), "email": "test@example.com"}

        with patch.object(self.service, 'ml_model') as mock_model:
            mock_model.predict.side_effect = Exception("Model inference failed")

            result = await self.service.assess_user_risk(user_data)

            # Should fallback to rule-based assessment
            assert "ml_model_error" in result.get("analysis_notes", "")
            assert result["risk_level"] in ["low", "medium", "high"]

    @pytest.mark.asyncio
    async def test_handle_redis_connection_failure(self):
        """Test handling of Redis connection failures."""
        with patch.object(self.service, 'redis_client') as mock_redis:
            mock_redis.get.side_effect = Exception("Redis connection failed")

            result = await self.service._check_device_history("device_123")

            assert result["is_known"] is False
            assert "redis_error" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_handle_external_api_timeout(self):
        """Test handling of external API timeouts."""
        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.side_effect = asyncio.TimeoutError("API timeout")

            result = await self.service._check_ip_reputation("192.168.1.1")

            assert result["reputation"] == "unknown"
            assert result["score"] == 50  # Default moderate score
            assert "timeout" in result["analysis"]