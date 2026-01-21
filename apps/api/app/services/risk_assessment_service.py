"""
Risk assessment service for Zero-Trust authentication
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
try:
    import numpy as np
    from sklearn.ensemble import IsolationForest
    import user_agents
    ML_AVAILABLE = True
    # Type aliases for when ML is available
    NDArray = np.ndarray
except ImportError:
    ML_AVAILABLE = False
    np = None
    IsolationForest = None
    # Fallback type alias when ML is not available
    NDArray = Any

from ..models import User, Session
try:
    from ..models.zero_trust import (
        RiskAssessment, RiskLevel, DeviceProfile, DeviceTrustLevel,
        AccessPolicy, AccessDecision, BehaviorBaseline, ThreatIntelligence,
        PolicyEvaluation, AdaptiveChallenge, AuthenticationMethod
    )
    ZERO_TRUST_MODELS_AVAILABLE = True
except ImportError:
    ZERO_TRUST_MODELS_AVAILABLE = False
    RiskAssessment = None
    RiskLevel = None
    DeviceProfile = None
    DeviceTrustLevel = None
    AccessPolicy = None
    AccessDecision = None
    BehaviorBaseline = None
    ThreatIntelligence = None
    PolicyEvaluation = None
    AdaptiveChallenge = None
    AuthenticationMethod = None

logger = logging.getLogger(__name__)


class RiskAssessmentService:
    """Service for assessing authentication risk and making access decisions"""
    
    def __init__(self):
        self.geoip_reader = None
        self.anomaly_detector = None
        self._init_geoip()
        self._init_anomaly_detector()
    
    def _init_geoip(self):
        """Initialize GeoIP database for location-based risk assessment"""
        try:
            # In production, use actual GeoIP2 database
            # self.geoip_reader = geoip2.database.Reader('/path/to/GeoLite2-City.mmdb')
            pass
        except Exception as e:
            logger.warning(f"GeoIP initialization failed: {e}")
    
    def _init_anomaly_detector(self):
        """Initialize anomaly detection model"""
        try:
            self.anomaly_detector = IsolationForest(
                contamination=0.1,
                random_state=42
            )
        except Exception as e:
            logger.warning(f"Anomaly detector initialization failed: {e}")
    
    async def assess_risk(
        self,
        db: AsyncSession,
        user_id: Optional[str] = None,
        ip_address: str = None,
        user_agent: str = None,
        device_fingerprint: str = None,
        auth_method: str = None,
        resource: str = None
    ) -> Dict[str, Any]:
        """
        Comprehensive risk assessment for authentication attempt
        
        Returns risk assessment with score, level, and access decision
        """
        try:
            # Initialize risk scores
            location_risk = await self._assess_location_risk(db, ip_address, user_id)
            device_risk = await self._assess_device_risk(db, device_fingerprint, user_id)
            behavior_risk = await self._assess_behavior_risk(db, user_id, ip_address, user_agent)
            network_risk = await self._assess_network_risk(db, ip_address)
            threat_risk = await self._assess_threat_intelligence(db, ip_address, user_id)
            
            # Calculate weighted overall risk
            risk_weights = {
                'location': 0.2,
                'device': 0.25,
                'behavior': 0.25,
                'network': 0.15,
                'threat': 0.15
            }
            
            overall_risk = (
                location_risk * risk_weights['location'] +
                device_risk * risk_weights['device'] +
                behavior_risk * risk_weights['behavior'] +
                network_risk * risk_weights['network'] +
                threat_risk * risk_weights['threat']
            )
            
            # Determine risk level
            risk_level = self._calculate_risk_level(overall_risk)
            
            # Get applicable access policies
            access_decision, required_auth = await self._evaluate_access_policies(
                db, user_id, risk_level, resource
            )
            
            # Collect risk factors and anomalies
            risk_factors = await self._collect_risk_factors(
                db, user_id, ip_address, device_fingerprint
            )
            
            anomalies = await self._detect_anomalies(
                db, user_id, ip_address, user_agent, device_fingerprint
            )
            
            # Create risk assessment record
            assessment = RiskAssessment(
                user_id=user_id,
                overall_risk_score=overall_risk,
                location_risk_score=location_risk,
                device_risk_score=device_risk,
                behavior_risk_score=behavior_risk,
                network_risk_score=network_risk,
                risk_level=risk_level,
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint,
                risk_factors=risk_factors,
                anomalies_detected=anomalies,
                access_decision=access_decision,
                required_auth_methods=required_auth,
                expires_at=datetime.utcnow() + timedelta(minutes=30)
            )
            
            db.add(assessment)
            await db.commit()
            
            return {
                'assessment_id': str(assessment.id),
                'risk_score': overall_risk,
                'risk_level': risk_level.value,
                'access_decision': access_decision.value,
                'required_auth_methods': required_auth,
                'risk_factors': risk_factors,
                'anomalies': anomalies,
                'expires_at': assessment.expires_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            # Default to high risk on error
            return {
                'risk_score': 0.8,
                'risk_level': RiskLevel.HIGH.value,
                'access_decision': AccessDecision.CHALLENGE.value,
                'required_auth_methods': ['mfa'],
                'error': str(e)
            }
    
    async def _assess_location_risk(
        self, 
        db: AsyncSession, 
        ip_address: str, 
        user_id: Optional[str]
    ) -> float:
        """Assess risk based on location"""
        risk_score = 0.0
        
        if not ip_address:
            return 0.5  # Unknown location is medium risk
        
        try:
            # Check if IP is from known VPN/proxy/Tor
            if await self._is_suspicious_ip(db, ip_address):
                risk_score += 0.3
            
            # Check if location is unusual for user
            if user_id:
                is_new_location = await self._is_new_location(db, user_id, ip_address)
                if is_new_location:
                    risk_score += 0.2
                
                # Check for impossible travel
                impossible_travel = await self._check_impossible_travel(
                    db, user_id, ip_address
                )
                if impossible_travel:
                    risk_score += 0.4
            
            # Check if location is in high-risk country
            if self.geoip_reader:
                try:
                    response = self.geoip_reader.city(ip_address)
                    country = response.country.iso_code
                    if country in self._get_high_risk_countries():
                        risk_score += 0.2
                except Exception:
                    pass
            
        except Exception as e:
            logger.warning(f"Location risk assessment error: {e}")
            risk_score = 0.3
        
        return min(risk_score, 1.0)
    
    async def _assess_device_risk(
        self, 
        db: AsyncSession, 
        device_fingerprint: str, 
        user_id: Optional[str]
    ) -> float:
        """Assess risk based on device trust"""
        if not device_fingerprint:
            return 0.6  # Unknown device is higher risk
        
        risk_score = 0.0
        
        try:
            # Check device profile
            device = await db.execute(
                select(DeviceProfile).where(
                    DeviceProfile.device_fingerprint == device_fingerprint
                )
            )
            device_profile = device.scalar_one_or_none()
            
            if not device_profile:
                # New device
                risk_score = 0.5
            else:
                # Assess based on trust level
                trust_scores = {
                    DeviceTrustLevel.UNTRUSTED: 0.8,
                    DeviceTrustLevel.KNOWN: 0.3,
                    DeviceTrustLevel.MANAGED: 0.1,
                    DeviceTrustLevel.TRUSTED: 0.0
                }
                risk_score = trust_scores.get(device_profile.trust_level, 0.5)
                
                # Check compliance
                if not device_profile.is_compliant:
                    risk_score += 0.2
                
                # Check if rooted/jailbroken
                if device_profile.is_rooted:
                    risk_score += 0.3
                
                # Check recent failed attempts
                if device_profile.failed_auth_count > 3:
                    risk_score += 0.2
        
        except Exception as e:
            logger.warning(f"Device risk assessment error: {e}")
            risk_score = 0.5
        
        return min(risk_score, 1.0)
    
    async def _assess_behavior_risk(
        self, 
        db: AsyncSession, 
        user_id: Optional[str], 
        ip_address: str,
        user_agent: str
    ) -> float:
        """Assess risk based on user behavior"""
        if not user_id:
            return 0.3
        
        risk_score = 0.0
        
        try:
            # Get user's behavior baseline
            baseline_result = await db.execute(
                select(BehaviorBaseline).where(
                    BehaviorBaseline.user_id == user_id
                )
            )
            baseline = baseline_result.scalar_one_or_none()
            
            if not baseline or not baseline.learning_completed_at:
                # No baseline established yet
                return 0.2
            
            # Check login time anomaly
            current_hour = datetime.utcnow().hour
            current_day = datetime.utcnow().weekday()
            
            if baseline.typical_login_times:
                hour_freq = baseline.typical_login_times.get(str(current_hour), 0)
                if hour_freq < 0.05:  # Less than 5% of logins at this hour
                    risk_score += 0.2
            
            if baseline.typical_login_days:
                day_freq = baseline.typical_login_days.get(str(current_day), 0)
                if day_freq < 0.1:  # Less than 10% of logins on this day
                    risk_score += 0.1
            
            # Check for velocity anomaly
            recent_logins = await self._get_recent_login_count(db, user_id, hours=1)
            if baseline.login_velocity_baseline:
                if recent_logins > baseline.login_velocity_baseline * 3:
                    risk_score += 0.3
            
            # Check user agent anomaly
            if user_agent and baseline.typical_user_agents:
                ua = user_agents.parse(user_agent)
                browser_family = ua.browser.family
                if browser_family not in baseline.typical_user_agents:
                    risk_score += 0.1
        
        except Exception as e:
            logger.warning(f"Behavior risk assessment error: {e}")
            risk_score = 0.3
        
        return min(risk_score, 1.0)
    
    async def _assess_network_risk(
        self, 
        db: AsyncSession, 
        ip_address: str
    ) -> float:
        """Assess risk based on network indicators"""
        risk_score = 0.0
        
        try:
            # Check if IP is blacklisted
            if await self._is_blacklisted_ip(db, ip_address):
                risk_score += 0.5
            
            # Check reputation score (would integrate with external service)
            reputation = await self._get_ip_reputation(ip_address)
            if reputation < 0.3:  # Low reputation
                risk_score += 0.3
            elif reputation < 0.6:  # Medium reputation
                risk_score += 0.1
            
            # Check for datacenter/hosting provider IP
            if await self._is_datacenter_ip(ip_address):
                risk_score += 0.2
        
        except Exception as e:
            logger.warning(f"Network risk assessment error: {e}")
            risk_score = 0.2
        
        return min(risk_score, 1.0)
    
    async def _assess_threat_intelligence(
        self, 
        db: AsyncSession, 
        ip_address: str, 
        user_id: Optional[str]
    ) -> float:
        """Assess risk based on threat intelligence"""
        risk_score = 0.0
        
        try:
            # Check IP against threat intelligence
            if ip_address:
                threat_result = await db.execute(
                    select(ThreatIntelligence).where(
                        and_(
                            ThreatIntelligence.indicator_type == 'ip',
                            ThreatIntelligence.indicator_value == ip_address,
                            ThreatIntelligence.is_active == True
                        )
                    )
                )
                threat = threat_result.scalar_one_or_none()
                
                if threat:
                    threat_scores = {
                        RiskLevel.LOW: 0.2,
                        RiskLevel.MEDIUM: 0.4,
                        RiskLevel.HIGH: 0.7,
                        RiskLevel.CRITICAL: 0.9
                    }
                    risk_score = threat_scores.get(threat.threat_level, 0.5)
            
            # Check user email against threat intelligence
            if user_id:
                user_result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user and user.email:
                    email_threat_result = await db.execute(
                        select(ThreatIntelligence).where(
                            and_(
                                ThreatIntelligence.indicator_type == 'email',
                                ThreatIntelligence.indicator_value == user.email,
                                ThreatIntelligence.is_active == True
                            )
                        )
                    )
                    email_threat = email_threat_result.scalar_one_or_none()
                    
                    if email_threat:
                        risk_score = max(risk_score, 0.6)
        
        except Exception as e:
            logger.warning(f"Threat intelligence assessment error: {e}")
        
        return min(risk_score, 1.0)
    
    def _calculate_risk_level(self, risk_score: float) -> RiskLevel:
        """Convert risk score to risk level"""
        if risk_score < 0.25:
            return RiskLevel.LOW
        elif risk_score < 0.5:
            return RiskLevel.MEDIUM
        elif risk_score < 0.75:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL
    
    async def _evaluate_access_policies(
        self,
        db: AsyncSession,
        user_id: Optional[str],
        risk_level: RiskLevel,
        resource: Optional[str]
    ) -> Tuple[AccessDecision, List[str]]:
        """Evaluate access policies and determine decision"""
        try:
            # Get applicable policies
            policies_result = await db.execute(
                select(AccessPolicy).where(
                    AccessPolicy.is_enabled == True
                ).order_by(AccessPolicy.priority.desc())
            )
            policies = policies_result.scalars().all()
            
            for policy in policies:
                # Check if policy applies
                if not self._policy_applies(policy, user_id, resource):
                    continue
                
                # Evaluate conditions
                if self._evaluate_policy_conditions(policy.conditions, {
                    'risk_level': risk_level.value,
                    'user_id': user_id,
                    'resource': resource
                }):
                    return policy.access_decision, policy.required_auth_methods
            
            # Default decision based on risk level
            if risk_level == RiskLevel.LOW:
                return AccessDecision.ALLOW, []
            elif risk_level == RiskLevel.MEDIUM:
                return AccessDecision.ALLOW, ['mfa']
            elif risk_level == RiskLevel.HIGH:
                return AccessDecision.CHALLENGE, ['mfa', 'captcha']
            else:
                return AccessDecision.STEP_UP, ['mfa', 'biometric']
        
        except Exception as e:
            logger.error(f"Policy evaluation error: {e}")
            return AccessDecision.CHALLENGE, ['mfa']
    
    async def _collect_risk_factors(
        self,
        db: AsyncSession,
        user_id: Optional[str],
        ip_address: str,
        device_fingerprint: str
    ) -> Dict[str, Any]:
        """Collect detailed risk factors"""
        factors = {}
        
        try:
            if ip_address:
                factors['ip_address'] = ip_address
                factors['is_vpn'] = await self._is_vpn_ip(ip_address)
                factors['is_tor'] = await self._is_tor_ip(ip_address)
                factors['is_proxy'] = await self._is_proxy_ip(ip_address)
            
            if device_fingerprint:
                factors['device_fingerprint'] = device_fingerprint
                factors['is_new_device'] = await self._is_new_device(
                    db, user_id, device_fingerprint
                )
            
            if user_id:
                factors['recent_failed_attempts'] = await self._get_failed_attempts(
                    db, user_id
                )
                factors['account_age_days'] = await self._get_account_age(db, user_id)
        
        except Exception as e:
            logger.warning(f"Risk factor collection error: {e}")
        
        return factors
    
    async def _detect_anomalies(
        self,
        db: AsyncSession,
        user_id: Optional[str],
        ip_address: str,
        user_agent: str,
        device_fingerprint: str
    ) -> List[str]:
        """Detect behavioral anomalies"""
        anomalies = []
        
        try:
            if user_id:
                # Check for unusual login patterns
                if await self._is_unusual_login_time(db, user_id):
                    anomalies.append("unusual_login_time")
                
                if await self._is_unusual_location(db, user_id, ip_address):
                    anomalies.append("unusual_location")
                
                if await self._has_concurrent_sessions_different_locations(db, user_id):
                    anomalies.append("concurrent_sessions_different_locations")
                
                # Use ML-based anomaly detection if available
                if self.anomaly_detector:
                    features = await self._extract_features(
                        db, user_id, ip_address, user_agent
                    )
                    if features is not None:
                        prediction = self.anomaly_detector.predict([features])
                        if prediction[0] == -1:  # Anomaly detected
                            anomalies.append("ml_anomaly_detected")
        
        except Exception as e:
            logger.warning(f"Anomaly detection error: {e}")
        
        return anomalies
    
    # Helper methods
    async def _is_suspicious_ip(self, db: AsyncSession, ip_address: str) -> bool:
        """Check if IP is from VPN/Proxy/Tor"""
        return (
            await self._is_vpn_ip(ip_address) or
            await self._is_tor_ip(ip_address) or
            await self._is_proxy_ip(ip_address)
        )
    
    async def _is_vpn_ip(self, ip_address: str) -> bool:
        """Check if IP is from VPN provider"""
        # In production, integrate with VPN detection service
        return False
    
    async def _is_tor_ip(self, ip_address: str) -> bool:
        """Check if IP is Tor exit node"""
        # In production, check against Tor exit node list
        return False
    
    async def _is_proxy_ip(self, ip_address: str) -> bool:
        """Check if IP is proxy"""
        # In production, integrate with proxy detection service
        return False
    
    async def _is_datacenter_ip(self, ip_address: str) -> bool:
        """Check if IP belongs to datacenter/hosting provider"""
        # In production, check against datacenter IP ranges
        return False
    
    async def _is_blacklisted_ip(self, db: AsyncSession, ip_address: str) -> bool:
        """Check if IP is blacklisted"""
        # Check internal blacklist
        return False
    
    async def _get_ip_reputation(self, ip_address: str) -> float:
        """Get IP reputation score (0-1, higher is better)"""
        # In production, integrate with IP reputation service
        return 0.7
    
    async def _is_new_location(
        self, 
        db: AsyncSession, 
        user_id: str, 
        ip_address: str
    ) -> bool:
        """Check if login is from new location"""
        # Check user's location history
        return False
    
    async def _check_impossible_travel(
        self,
        db: AsyncSession,
        user_id: str,
        ip_address: str
    ) -> bool:
        """Check for impossible travel scenarios"""
        # Compare with recent login locations and times
        return False
    
    async def _is_new_device(
        self,
        db: AsyncSession,
        user_id: str,
        device_fingerprint: str
    ) -> bool:
        """Check if device is new for user"""
        if not user_id or not device_fingerprint:
            return True
        
        result = await db.execute(
            select(DeviceProfile).where(
                and_(
                    DeviceProfile.user_id == user_id,
                    DeviceProfile.device_fingerprint == device_fingerprint
                )
            )
        )
        return result.scalar_one_or_none() is None
    
    async def _get_recent_login_count(
        self,
        db: AsyncSession,
        user_id: str,
        hours: int = 1
    ) -> int:
        """Get count of recent login attempts"""
        since = datetime.utcnow() - timedelta(hours=hours)
        result = await db.execute(
            select(func.count(Session.id)).where(
                and_(
                    Session.user_id == user_id,
                    Session.created_at >= since
                )
            )
        )
        return result.scalar() or 0
    
    async def _get_failed_attempts(
        self,
        db: AsyncSession,
        user_id: str,
        hours: int = 24
    ) -> int:
        """Get count of recent failed login attempts"""
        # In production, track failed attempts in audit log
        return 0
    
    async def _get_account_age(self, db: AsyncSession, user_id: str) -> int:
        """Get account age in days"""
        result = await db.execute(
            select(User.created_at).where(User.id == user_id)
        )
        created_at = result.scalar()
        if created_at:
            return (datetime.utcnow() - created_at).days
        return 0
    
    async def _is_unusual_login_time(
        self,
        db: AsyncSession,
        user_id: str
    ) -> bool:
        """Check if login time is unusual for user"""
        # Compare with user's typical login patterns
        return False
    
    async def _is_unusual_location(
        self,
        db: AsyncSession,
        user_id: str,
        ip_address: str
    ) -> bool:
        """Check if location is unusual for user"""
        # Compare with user's typical locations
        return False
    
    async def _has_concurrent_sessions_different_locations(
        self,
        db: AsyncSession,
        user_id: str
    ) -> bool:
        """Check for concurrent sessions from different locations"""
        # Check active sessions and their locations
        return False
    
    async def _extract_features(
        self,
        db: AsyncSession,
        user_id: str,
        ip_address: str,
        user_agent: str
    ) -> Optional[NDArray]:
        """Extract features for ML-based anomaly detection"""
        # Extract numerical features for anomaly detection
        return None
    
    def _get_high_risk_countries(self) -> List[str]:
        """Get list of high-risk country codes"""
        # In production, maintain dynamic list based on threat intelligence
        return []
    
    def _policy_applies(
        self,
        policy: AccessPolicy,
        user_id: Optional[str],
        resource: Optional[str]
    ) -> bool:
        """Check if policy applies to current context"""
        # Check user and resource scope
        if policy.applies_to_users and user_id:
            if user_id not in policy.applies_to_users:
                return False
        
        if policy.applies_to_resources and resource:
            # Check resource patterns
            for pattern in policy.applies_to_resources:
                if pattern in resource:
                    return True
            return False
        
        return True
    
    def _evaluate_policy_conditions(
        self,
        conditions: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate policy conditions against context"""
        # Simple JSON logic evaluation
        # In production, use more sophisticated rule engine
        try:
            if 'and' in conditions:
                return all(
                    self._evaluate_condition(cond, context)
                    for cond in conditions['and']
                )
            elif 'or' in conditions:
                return any(
                    self._evaluate_condition(cond, context)
                    for cond in conditions['or']
                )
            else:
                return self._evaluate_condition(conditions, context)
        except Exception:
            return False
    
    def _evaluate_condition(
        self,
        condition: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """Evaluate single condition"""
        for field, check in condition.items():
            value = context.get(field)
            
            if isinstance(check, dict):
                if 'in' in check:
                    if value not in check['in']:
                        return False
                elif 'not_in' in check:
                    if value in check['not_in']:
                        return False
                elif 'eq' in check:
                    if value != check['eq']:
                        return False
            else:
                if value != check:
                    return False
        
        return True