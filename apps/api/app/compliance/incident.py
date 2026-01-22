"""
Security incident response system for enterprise compliance and SOC2 requirements.
Automated incident detection, classification, response coordination, and compliance reporting.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import uuid
from sqlalchemy import select, and_, func

from app.core.database import get_session
from app.models.audit import AuditLog
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class IncidentSeverity(str, Enum):
    """Security incident severity levels aligned with SOC2 requirements"""
    CRITICAL = "critical"      # System compromise, data breach, service down
    HIGH = "high"             # Security violation, privileged access misuse
    MEDIUM = "medium"         # Policy violation, suspicious activity
    LOW = "low"              # Minor security issue, informational
    INFO = "info"            # Security awareness, routine monitoring


class IncidentStatus(str, Enum):
    """Incident lifecycle status"""
    OPEN = "open"
    INVESTIGATING = "investigating"
    CONTAINMENT = "containment"
    REMEDIATION = "remediation"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentCategory(str, Enum):
    """Security incident categories for classification"""
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    DATA_BREACH = "data_breach"
    MALWARE = "malware"
    PHISHING = "phishing"
    POLICY_VIOLATION = "policy_violation"
    SYSTEM_COMPROMISE = "system_compromise"
    DENIAL_OF_SERVICE = "denial_of_service"
    INSIDER_THREAT = "insider_threat"
    CONFIGURATION_ERROR = "configuration_error"
    COMPLIANCE_VIOLATION = "compliance_violation"


class AlertType(str, Enum):
    """Types of security alerts that can trigger incidents"""
    AUTHENTICATION_FAILURE = "authentication_failure"
    PRIVILEGED_ACCESS = "privileged_access"
    UNUSUAL_ACTIVITY = "unusual_activity"
    SYSTEM_ANOMALY = "system_anomaly"
    COMPLIANCE_BREACH = "compliance_breach"
    SECURITY_CONTROL_FAILURE = "security_control_failure"


@dataclass
class SecurityAlert:
    """Security alert that may trigger incident response"""
    alert_id: str
    alert_type: AlertType
    severity: IncidentSeverity
    title: str
    description: str
    source_system: str
    affected_assets: List[str]
    detection_time: datetime
    raw_data: Dict[str, Any]
    user_id: Optional[str] = None
    organization_id: Optional[str] = None
    ip_address: Optional[str] = None
    escalated: bool = False


@dataclass
class SecurityIncident:
    """Security incident requiring response and documentation"""
    incident_id: str
    title: str
    description: str
    severity: IncidentSeverity
    category: IncidentCategory
    status: IncidentStatus

    # Timeline
    created_at: datetime
    detected_at: datetime
    acknowledged_at: Optional[datetime] = None
    contained_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None

    # Assignment and escalation
    assigned_to: Optional[str] = None
    escalated_to: Optional[str] = None
    external_ticket: Optional[str] = None

    # Impact assessment
    affected_users: List[str] = None
    affected_systems: List[str] = None
    data_compromised: bool = False
    service_impact: bool = False

    # Response actions
    containment_actions: List[str] = None
    remediation_actions: List[str] = None
    evidence_collected: List[str] = None

    # Compliance and reporting
    regulatory_reporting_required: bool = False
    customer_notification_required: bool = False
    breach_notification_sent: bool = False

    # Related items
    related_alerts: List[str] = None
    related_incidents: List[str] = None

    # Metadata
    tags: List[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.affected_users is None:
            self.affected_users = []
        if self.affected_systems is None:
            self.affected_systems = []
        if self.containment_actions is None:
            self.containment_actions = []
        if self.remediation_actions is None:
            self.remediation_actions = []
        if self.evidence_collected is None:
            self.evidence_collected = []
        if self.related_alerts is None:
            self.related_alerts = []
        if self.related_incidents is None:
            self.related_incidents = []
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}


class IncidentResponse:
    """
    Enterprise security incident response system for SOC2 compliance.
    Handles detection, classification, response coordination, and documentation.
    """

    def __init__(self):
        self.incident_storage = Path("compliance/incidents")
        self.incident_storage.mkdir(parents=True, exist_ok=True)

        # Response team configuration
        self.security_team_email = settings.SECURITY_TEAM_EMAIL if hasattr(settings, 'SECURITY_TEAM_EMAIL') else None
        self.ciso_email = settings.CISO_EMAIL if hasattr(settings, 'CISO_EMAIL') else None
        self.legal_team_email = settings.LEGAL_TEAM_EMAIL if hasattr(settings, 'LEGAL_TEAM_EMAIL') else None

        # SLA timelines (minutes)
        self.response_slas = {
            IncidentSeverity.CRITICAL: 15,  # 15 minutes
            IncidentSeverity.HIGH: 60,      # 1 hour
            IncidentSeverity.MEDIUM: 240,   # 4 hours
            IncidentSeverity.LOW: 1440,     # 24 hours
            IncidentSeverity.INFO: 2880     # 48 hours
        }

    async def process_alert(self, alert: SecurityAlert) -> Optional[SecurityIncident]:
        """Process security alert and determine if incident should be created"""
        logger.info(f"Processing security alert: {alert.alert_id}")

        try:
            # Evaluate alert for incident creation
            should_create_incident = await self._evaluate_alert_for_incident(alert)

            if should_create_incident:
                incident = await self._create_incident_from_alert(alert)
                await self._initiate_incident_response(incident)
                return incident
            else:
                # Log alert for monitoring but don't create incident
                await self._log_security_alert(alert)
                return None

        except Exception as e:
            logger.error(f"Error processing alert {alert.alert_id}: {e}")
            # Create incident for processing failure
            return await self._create_alert_processing_incident(alert, str(e))

    async def create_incident(self, title: str, description: str, severity: IncidentSeverity,
                            category: IncidentCategory, **kwargs) -> SecurityIncident:
        """Manually create security incident"""
        incident_id = f"INC-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

        incident = SecurityIncident(
            incident_id=incident_id,
            title=title,
            description=description,
            severity=severity,
            category=category,
            status=IncidentStatus.OPEN,
            created_at=datetime.utcnow(),
            detected_at=datetime.utcnow(),
            **kwargs
        )

        await self._save_incident(incident)
        await self._initiate_incident_response(incident)

        logger.info(f"Security incident created: {incident_id}")
        return incident

    async def update_incident(self, incident_id: str, **updates) -> Optional[SecurityIncident]:
        """Update existing incident"""
        incident = await self.get_incident(incident_id)

        if not incident:
            logger.error(f"Incident not found: {incident_id}")
            return None

        # Update incident fields
        for field, value in updates.items():
            if hasattr(incident, field):
                setattr(incident, field, value)

        # Auto-update timestamps based on status changes
        if 'status' in updates:
            await self._update_incident_timestamps(incident, updates['status'])

        await self._save_incident(incident)

        # Check for escalation requirements
        await self._check_escalation_requirements(incident)

        logger.info(f"Incident updated: {incident_id}")
        return incident

    async def escalate_incident(self, incident_id: str, escalation_reason: str) -> bool:
        """Escalate incident to higher severity or management"""
        incident = await self.get_incident(incident_id)

        if not incident:
            logger.error(f"Cannot escalate - incident not found: {incident_id}")
            return False

        # Escalate severity if not already critical
        if incident.severity != IncidentSeverity.CRITICAL:
            old_severity = incident.severity
            incident.severity = IncidentSeverity.HIGH if incident.severity == IncidentSeverity.MEDIUM else IncidentSeverity.CRITICAL

            # Add escalation to incident timeline
            incident.remediation_actions.append(
                f"Escalated from {old_severity} to {incident.severity}: {escalation_reason}"
            )

        # Escalate to management
        incident.escalated_to = self.ciso_email or "security-management@company.com"

        await self._save_incident(incident)
        await self._send_escalation_notification(incident, escalation_reason)

        logger.warning(f"Incident escalated: {incident_id} - {escalation_reason}")
        return True

    async def get_incident(self, incident_id: str) -> Optional[SecurityIncident]:
        """Retrieve incident by ID"""
        incident_file = self.incident_storage / f"{incident_id}.json"

        if not incident_file.exists():
            return None

        try:
            with open(incident_file, 'r') as f:
                incident_data = json.load(f)

            # Convert datetime strings back to datetime objects
            for field in ['created_at', 'detected_at', 'acknowledged_at', 'contained_at', 'resolved_at', 'closed_at']:
                if incident_data.get(field):
                    incident_data[field] = datetime.fromisoformat(incident_data[field])

            return SecurityIncident(**incident_data)

        except Exception as e:
            logger.error(f"Error loading incident {incident_id}: {e}")
            return None

    async def get_open_incidents(self) -> List[SecurityIncident]:
        """Get all open incidents"""
        incidents = []

        for incident_file in self.incident_storage.glob("INC-*.json"):
            incident = await self.get_incident(incident_file.stem)

            if incident and incident.status not in [IncidentStatus.RESOLVED, IncidentStatus.CLOSED]:
                incidents.append(incident)

        return sorted(incidents, key=lambda x: x.created_at, reverse=True)

    async def get_incidents_by_severity(self, severity: IncidentSeverity) -> List[SecurityIncident]:
        """Get incidents by severity level"""
        incidents = []

        for incident_file in self.incident_storage.glob("INC-*.json"):
            incident = await self.get_incident(incident_file.stem)

            if incident and incident.severity == severity:
                incidents.append(incident)

        return sorted(incidents, key=lambda x: x.created_at, reverse=True)

    async def get_incident_metrics(self, days: int = 30) -> Dict[str, Any]:
        """Get incident response metrics for compliance reporting"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        incidents = []

        for incident_file in self.incident_storage.glob("INC-*.json"):
            incident = await self.get_incident(incident_file.stem)

            if incident and incident.created_at >= cutoff_date:
                incidents.append(incident)

        metrics = {
            "reporting_period_days": days,
            "total_incidents": len(incidents),
            "incidents_by_severity": {},
            "incidents_by_category": {},
            "incidents_by_status": {},
            "average_response_time_minutes": 0,
            "average_resolution_time_hours": 0,
            "sla_compliance_rate": 0,
            "escalation_rate": 0,
            "repeat_incidents": 0
        }

        if not incidents:
            return metrics

        # Calculate metrics
        for severity in list(IncidentSeverity):
            metrics["incidents_by_severity"][severity] = len([i for i in incidents if i.severity == severity])

        for category in list(IncidentCategory):
            metrics["incidents_by_category"][category] = len([i for i in incidents if i.category == category])

        for status in list(IncidentStatus):
            metrics["incidents_by_status"][status] = len([i for i in incidents if i.status == status])

        # Response time metrics
        response_times = []
        resolution_times = []
        sla_met = 0

        for incident in incidents:
            if incident.acknowledged_at:
                response_time = (incident.acknowledged_at - incident.detected_at).total_seconds() / 60
                response_times.append(response_time)

                # Check SLA compliance
                sla_minutes = self.response_slas.get(incident.severity, 1440)
                if response_time <= sla_minutes:
                    sla_met += 1

            if incident.resolved_at:
                resolution_time = (incident.resolved_at - incident.detected_at).total_seconds() / 3600
                resolution_times.append(resolution_time)

        if response_times:
            metrics["average_response_time_minutes"] = sum(response_times) / len(response_times)
            metrics["sla_compliance_rate"] = (sla_met / len(response_times)) * 100

        if resolution_times:
            metrics["average_resolution_time_hours"] = sum(resolution_times) / len(resolution_times)

        # Escalation rate
        escalated_incidents = len([i for i in incidents if i.escalated_to])
        if incidents:
            metrics["escalation_rate"] = (escalated_incidents / len(incidents)) * 100

        return metrics

    async def generate_incident_report(self, incident_id: str) -> Dict[str, Any]:
        """Generate comprehensive incident report for compliance"""
        incident = await self.get_incident(incident_id)

        if not incident:
            raise ValueError(f"Incident not found: {incident_id}")

        # Calculate timeline metrics
        timeline = {}
        if incident.acknowledged_at:
            timeline["response_time_minutes"] = (incident.acknowledged_at - incident.detected_at).total_seconds() / 60

        if incident.contained_at:
            timeline["containment_time_hours"] = (incident.contained_at - incident.detected_at).total_seconds() / 3600

        if incident.resolved_at:
            timeline["resolution_time_hours"] = (incident.resolved_at - incident.detected_at).total_seconds() / 3600

        # SLA compliance
        sla_minutes = self.response_slas.get(incident.severity, 1440)
        sla_met = timeline.get("response_time_minutes", float('inf')) <= sla_minutes

        report = {
            "incident_summary": {
                "incident_id": incident.incident_id,
                "title": incident.title,
                "severity": incident.severity,
                "category": incident.category,
                "status": incident.status,
                "created_at": incident.created_at.isoformat(),
                "detected_at": incident.detected_at.isoformat()
            },
            "impact_assessment": {
                "affected_users": len(incident.affected_users),
                "affected_systems": incident.affected_systems,
                "data_compromised": incident.data_compromised,
                "service_impact": incident.service_impact
            },
            "response_metrics": {
                "timeline": timeline,
                "sla_compliance": sla_met,
                "escalated": bool(incident.escalated_to),
                "containment_actions": len(incident.containment_actions),
                "remediation_actions": len(incident.remediation_actions)
            },
            "compliance_requirements": {
                "regulatory_reporting_required": incident.regulatory_reporting_required,
                "customer_notification_required": incident.customer_notification_required,
                "breach_notification_sent": incident.breach_notification_sent
            },
            "evidence_collected": incident.evidence_collected,
            "lessons_learned": self._extract_lessons_learned(incident),
            "report_generated_at": datetime.utcnow().isoformat()
        }

        return report

    # Private helper methods

    async def _evaluate_alert_for_incident(self, alert: SecurityAlert) -> bool:
        """Evaluate if alert should trigger incident creation"""
        # Always create incidents for critical and high severity alerts
        if alert.severity in [IncidentSeverity.CRITICAL, IncidentSeverity.HIGH]:
            return True

        # Create incidents for authentication failures with high frequency
        if alert.alert_type == AlertType.AUTHENTICATION_FAILURE:
            recent_failures = await self._count_recent_auth_failures(alert.user_id, alert.ip_address)
            if recent_failures >= 5:  # 5 failures in short time
                return True

        # Create incidents for privileged access anomalies
        if alert.alert_type == AlertType.PRIVILEGED_ACCESS:
            return True

        # Create incidents for compliance breaches
        if alert.alert_type == AlertType.COMPLIANCE_BREACH:
            return True

        # Check for similar alerts that might indicate pattern
        similar_alerts = await self._find_similar_alerts(alert)
        if len(similar_alerts) >= 3:  # 3 similar alerts indicate pattern
            return True

        return False

    async def _create_incident_from_alert(self, alert: SecurityAlert) -> SecurityIncident:
        """Create security incident from alert"""
        incident_id = f"INC-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

        # Determine incident category based on alert type
        category_mapping = {
            AlertType.AUTHENTICATION_FAILURE: IncidentCategory.UNAUTHORIZED_ACCESS,
            AlertType.PRIVILEGED_ACCESS: IncidentCategory.INSIDER_THREAT,
            AlertType.UNUSUAL_ACTIVITY: IncidentCategory.POLICY_VIOLATION,
            AlertType.SYSTEM_ANOMALY: IncidentCategory.SYSTEM_COMPROMISE,
            AlertType.COMPLIANCE_BREACH: IncidentCategory.COMPLIANCE_VIOLATION,
            AlertType.SECURITY_CONTROL_FAILURE: IncidentCategory.CONFIGURATION_ERROR
        }

        category = category_mapping.get(alert.alert_type, IncidentCategory.POLICY_VIOLATION)

        incident = SecurityIncident(
            incident_id=incident_id,
            title=f"Security Alert: {alert.title}",
            description=alert.description,
            severity=alert.severity,
            category=category,
            status=IncidentStatus.OPEN,
            created_at=datetime.utcnow(),
            detected_at=alert.detection_time,
            affected_users=[alert.user_id] if alert.user_id else [],
            affected_systems=alert.affected_assets,
            related_alerts=[alert.alert_id],
            metadata={
                "source_alert": asdict(alert),
                "auto_created": True
            }
        )

        await self._save_incident(incident)
        return incident

    async def _create_alert_processing_incident(self, alert: SecurityAlert, error: str) -> SecurityIncident:
        """Create incident for alert processing failure"""
        incident_id = f"INC-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

        incident = SecurityIncident(
            incident_id=incident_id,
            title="Alert Processing Failure",
            description=f"Failed to process security alert {alert.alert_id}: {error}",
            severity=IncidentSeverity.MEDIUM,
            category=IncidentCategory.CONFIGURATION_ERROR,
            status=IncidentStatus.OPEN,
            created_at=datetime.utcnow(),
            detected_at=datetime.utcnow(),
            metadata={
                "failed_alert": asdict(alert),
                "processing_error": error,
                "auto_created": True
            }
        )

        await self._save_incident(incident)
        return incident

    async def _initiate_incident_response(self, incident: SecurityIncident):
        """Initiate incident response procedures"""
        logger.info(f"Initiating incident response for {incident.incident_id}")

        try:
            # Immediate response based on severity
            if incident.severity == IncidentSeverity.CRITICAL:
                await self._critical_incident_response(incident)
            elif incident.severity == IncidentSeverity.HIGH:
                await self._high_incident_response(incident)

            # Send notifications
            await self._send_incident_notifications(incident)

            # Auto-assign based on category
            await self._auto_assign_incident(incident)

            # Set up monitoring and escalation timers
            await self._setup_incident_monitoring(incident)

        except Exception as e:
            logger.error(f"Error initiating incident response for {incident.incident_id}: {e}")

    async def _critical_incident_response(self, incident: SecurityIncident):
        """Immediate response for critical incidents"""
        # Immediate containment actions
        incident.containment_actions.append(f"Critical incident declared at {datetime.utcnow()}")

        # Escalate immediately to CISO
        if self.ciso_email:
            incident.escalated_to = self.ciso_email

        # Mark for regulatory reporting if data breach
        if incident.category == IncidentCategory.DATA_BREACH:
            incident.regulatory_reporting_required = True
            incident.customer_notification_required = True

        await self._save_incident(incident)

    async def _high_incident_response(self, incident: SecurityIncident):
        """Response for high severity incidents"""
        # Document response initiation
        incident.containment_actions.append(f"High severity incident response initiated at {datetime.utcnow()}")

        # Consider escalation based on category
        if incident.category in [IncidentCategory.DATA_BREACH, IncidentCategory.SYSTEM_COMPROMISE]:
            incident.regulatory_reporting_required = True

        await self._save_incident(incident)

    async def _send_incident_notifications(self, incident: SecurityIncident):
        """Send incident notifications to response team"""
        # This would integrate with actual notification systems (email, Slack, PagerDuty)
        logger.info(f"Sending notifications for incident {incident.incident_id}")

        notification_data = {
            "incident_id": incident.incident_id,
            "title": incident.title,
            "severity": incident.severity,
            "category": incident.category,
            "created_at": incident.created_at.isoformat()
        }

        # Log notification for audit trail
        await self._log_incident_notification(notification_data)

    async def _auto_assign_incident(self, incident: SecurityIncident):
        """Auto-assign incident based on category and severity"""
        # Assignment logic based on incident characteristics
        if incident.category in [IncidentCategory.DATA_BREACH, IncidentCategory.SYSTEM_COMPROMISE]:
            incident.assigned_to = self.security_team_email or "security-team@company.com"
        elif incident.category == IncidentCategory.COMPLIANCE_VIOLATION:
            incident.assigned_to = self.legal_team_email or "compliance-team@company.com"
        else:
            incident.assigned_to = self.security_team_email or "security-team@company.com"

        await self._save_incident(incident)

    async def _setup_incident_monitoring(self, incident: SecurityIncident):
        """Set up automated monitoring and escalation for incident"""
        # This would set up background tasks to monitor SLA compliance
        # and auto-escalate if response times are exceeded
        logger.info(f"Setting up monitoring for incident {incident.incident_id}")

    async def _update_incident_timestamps(self, incident: SecurityIncident, new_status: IncidentStatus):
        """Update incident timestamps based on status changes"""
        now = datetime.utcnow()

        if new_status == IncidentStatus.INVESTIGATING and not incident.acknowledged_at:
            incident.acknowledged_at = now
        elif new_status == IncidentStatus.CONTAINMENT and not incident.contained_at:
            incident.contained_at = now
        elif new_status == IncidentStatus.RESOLVED and not incident.resolved_at:
            incident.resolved_at = now
        elif new_status == IncidentStatus.CLOSED and not incident.closed_at:
            incident.closed_at = now

    async def _check_escalation_requirements(self, incident: SecurityIncident):
        """Check if incident meets escalation criteria"""
        if incident.status in [IncidentStatus.RESOLVED, IncidentStatus.CLOSED]:
            return

        # Check SLA compliance
        if incident.acknowledged_at:
            response_time = (incident.acknowledged_at - incident.detected_at).total_seconds() / 60
            sla_minutes = self.response_slas.get(incident.severity, 1440)

            if response_time > sla_minutes:
                await self.escalate_incident(incident.incident_id, "SLA breach - response time exceeded")

        # Check for long-running incidents
        age_hours = (datetime.utcnow() - incident.created_at).total_seconds() / 3600

        escalation_thresholds = {
            IncidentSeverity.CRITICAL: 4,    # 4 hours
            IncidentSeverity.HIGH: 24,       # 24 hours
            IncidentSeverity.MEDIUM: 72,     # 72 hours
        }

        threshold = escalation_thresholds.get(incident.severity)
        if threshold and age_hours > threshold and not incident.escalated_to:
            await self.escalate_incident(incident.incident_id, f"Long-running incident - {age_hours:.1f} hours")

    async def _send_escalation_notification(self, incident: SecurityIncident, reason: str):
        """Send escalation notification to management"""
        logger.warning(f"Escalation notification for {incident.incident_id}: {reason}")

    async def _save_incident(self, incident: SecurityIncident):
        """Save incident to storage"""
        incident_file = self.incident_storage / f"{incident.incident_id}.json"

        incident_data = asdict(incident)

        # Convert datetime objects to ISO strings for JSON serialization
        for field in ['created_at', 'detected_at', 'acknowledged_at', 'contained_at', 'resolved_at', 'closed_at']:
            if incident_data.get(field):
                incident_data[field] = incident_data[field].isoformat()

        with open(incident_file, 'w') as f:
            json.dump(incident_data, f, indent=2, default=str)

    async def _log_security_alert(self, alert: SecurityAlert):
        """Log security alert for audit trail"""
        logger.info(f"Security alert logged: {alert.alert_id} - {alert.title}")

    async def _log_incident_notification(self, notification_data: Dict[str, Any]):
        """Log incident notification for audit trail"""
        logger.info(f"Incident notification sent: {notification_data}")

    async def _count_recent_auth_failures(self, user_id: Optional[str], ip_address: Optional[str]) -> int:
        """Count recent authentication failures for user or IP"""
        if not user_id and not ip_address:
            return 0

        try:
            async with get_session() as session:
                query = select(func.count(AuditLog.id)).where(
                    and_(
                        AuditLog.action == "failed_login",
                        AuditLog.created_at >= datetime.utcnow() - timedelta(minutes=15)
                    )
                )

                if user_id:
                    query = query.where(AuditLog.user_id == user_id)

                if ip_address:
                    query = query.where(AuditLog.metadata.op('->>')('ip_address') == ip_address)

                result = await session.execute(query)
                return result.scalar() or 0

        except Exception as e:
            logger.error(f"Error counting auth failures: {e}")
            return 0

    async def _find_similar_alerts(self, alert: SecurityAlert) -> List[str]:
        """Find similar alerts in recent timeframe"""
        # This would search for alerts with similar characteristics
        # For implementation, return empty list
        return []

    def _extract_lessons_learned(self, incident: SecurityIncident) -> List[str]:
        """Extract lessons learned from incident for improvement"""
        lessons = []

        # Standard lessons based on incident characteristics
        if incident.severity == IncidentSeverity.CRITICAL:
            lessons.append("Review emergency response procedures for critical incidents")

        if len(incident.containment_actions) == 0:
            lessons.append("Improve containment action documentation and procedures")

        if incident.data_compromised:
            lessons.append("Review data protection controls and access management")

        if incident.category == IncidentCategory.CONFIGURATION_ERROR:
            lessons.append("Enhance configuration management and change control processes")

        return lessons


# Utility functions for alert generation

async def create_authentication_failure_alert(user_id: str, ip_address: str, failure_count: int) -> SecurityAlert:
    """Create alert for authentication failures"""
    severity = IncidentSeverity.MEDIUM if failure_count < 5 else IncidentSeverity.HIGH

    return SecurityAlert(
        alert_id=f"AUTH-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}",
        alert_type=AlertType.AUTHENTICATION_FAILURE,
        severity=severity,
        title=f"Multiple Authentication Failures",
        description=f"User {user_id} failed authentication {failure_count} times from IP {ip_address}",
        source_system="authentication",
        affected_assets=["authentication_service"],
        detection_time=datetime.utcnow(),
        user_id=user_id,
        ip_address=ip_address,
        raw_data={
            "failure_count": failure_count,
            "detection_window_minutes": 15
        }
    )


async def create_privileged_access_alert(user_id: str, action: str, resource: str) -> SecurityAlert:
    """Create alert for privileged access activities"""
    return SecurityAlert(
        alert_id=f"PRIV-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}",
        alert_type=AlertType.PRIVILEGED_ACCESS,
        severity=IncidentSeverity.MEDIUM,
        title=f"Privileged Access: {action}",
        description=f"User {user_id} performed privileged action '{action}' on {resource}",
        source_system="audit_system",
        affected_assets=[resource],
        detection_time=datetime.utcnow(),
        user_id=user_id,
        raw_data={
            "action": action,
            "resource": resource,
            "requires_review": True
        }
    )


async def create_system_anomaly_alert(system: str, metric: str, value: float, threshold: float) -> SecurityAlert:
    """Create alert for system anomalies"""
    severity = IncidentSeverity.HIGH if value > threshold * 2 else IncidentSeverity.MEDIUM

    return SecurityAlert(
        alert_id=f"SYS-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}",
        alert_type=AlertType.SYSTEM_ANOMALY,
        severity=severity,
        title=f"System Anomaly: {metric}",
        description=f"System {system} metric '{metric}' at {value:.2f} exceeds threshold {threshold:.2f}",
        source_system="monitoring",
        affected_assets=[system],
        detection_time=datetime.utcnow(),
        raw_data={
            "metric": metric,
            "current_value": value,
            "threshold": threshold,
            "deviation_percentage": ((value - threshold) / threshold) * 100
        }
    )