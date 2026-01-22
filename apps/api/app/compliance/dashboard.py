"""
Compliance Dashboard for real-time monitoring and executive reporting.
SOC2 control effectiveness, compliance metrics, and SLA performance visualization.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
import json
import uuid
import redis.asyncio as aioredis
from sqlalchemy import select, and_, func, desc

from app.core.database import get_session
from app.models.compliance import (
    ComplianceControl,
    DataBreachIncident,
    ComplianceFramework,
    DataSubjectRequest,
    RequestStatus,
)
from app.models.audit import AuditLog
from app.core.config import get_settings
from .audit import AuditLogger
from .monitor import ComplianceMonitor, ControlStatus
from .sla import SLAMonitor

logger = logging.getLogger(__name__)
settings = get_settings()


class DashboardTimeframe(str, Enum):
    """Time frames for dashboard metrics"""

    REALTIME = "realtime"  # Last 15 minutes
    HOURLY = "hourly"  # Last 24 hours
    DAILY = "daily"  # Last 30 days
    WEEKLY = "weekly"  # Last 12 weeks
    MONTHLY = "monthly"  # Last 12 months
    QUARTERLY = "quarterly"  # Last 4 quarters
    YEARLY = "yearly"  # Last 5 years


class MetricStatus(str, Enum):
    """Status indicators for metrics"""

    EXCELLENT = "excellent"  # 95-100%
    GOOD = "good"  # 85-94%
    WARNING = "warning"  # 70-84%
    CRITICAL = "critical"  # Below 70%
    UNKNOWN = "unknown"  # No data


class AlertLevel(str, Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class ComplianceMetric:
    """Individual compliance metric with trend data"""

    metric_id: str
    name: str
    description: str
    value: float
    target: float
    unit: str
    status: MetricStatus
    trend: str  # "up", "down", "stable"
    change_percentage: float
    last_updated: datetime
    data_points: List[Dict[str, Any]]


@dataclass
class SOC2ControlSummary:
    """SOC2 control effectiveness summary"""

    control_id: str
    control_name: str
    control_family: str
    status: ControlStatus
    effectiveness_score: float
    last_tested: Optional[datetime]
    deficiencies: int
    evidence_count: int
    risk_level: str


@dataclass
class ComplianceDashboardData:
    """Complete dashboard data structure"""

    organization_id: str
    generated_at: datetime
    timeframe: DashboardTimeframe

    # High-level summary
    overall_compliance_score: float
    active_incidents: int
    open_deficiencies: int
    sla_performance: float

    # Framework-specific metrics
    soc2_metrics: Dict[str, Any]
    gdpr_metrics: Dict[str, Any]
    security_metrics: Dict[str, Any]

    # Control effectiveness
    control_summary: List[SOC2ControlSummary]
    control_trends: Dict[str, List[float]]

    # SLA and performance
    sla_metrics: Dict[str, Any]
    uptime_metrics: Dict[str, Any]
    response_time_metrics: Dict[str, Any]

    # Incidents and risks
    incident_summary: Dict[str, Any]
    risk_assessment: Dict[str, Any]

    # Alerts and notifications
    active_alerts: List[Dict[str, Any]]
    recent_events: List[Dict[str, Any]]


class ComplianceDashboard:
    """Real-time compliance monitoring dashboard"""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis = redis_client
        self.compliance_monitor = ComplianceMonitor(redis_client)
        self.sla_monitor = SLAMonitor(redis_client)
        self.audit_logger = AuditLogger(redis_client)

    async def get_dashboard_data(
        self,
        organization_id: str,
        timeframe: DashboardTimeframe = DashboardTimeframe.DAILY,
        include_trends: bool = True,
        cache_timeout: int = 300,  # 5 minutes
    ) -> ComplianceDashboardData:
        """Generate comprehensive dashboard data"""

        cache_key = f"compliance:dashboard:{organization_id}:{timeframe.value}"

        # Try to get cached data
        if self.redis:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                try:
                    return ComplianceDashboardData(**json.loads(cached_data))
                except Exception as e:
                    # Log cache deserialization error and regenerate
                    logger.warning(
                        "Failed to deserialize cached dashboard data, regenerating",
                        organization_id=str(organization_id),
                        error=str(e),
                        error_type=type(e).__name__,
                    )

        # Generate fresh dashboard data
        dashboard_data = await self._generate_dashboard_data(
            organization_id, timeframe, include_trends
        )

        # Cache the result
        if self.redis:
            await self.redis.setex(
                cache_key, cache_timeout, json.dumps(asdict(dashboard_data), default=str)
            )

        return dashboard_data

    async def get_real_time_metrics(self, organization_id: str) -> Dict[str, Any]:
        """Get real-time compliance metrics"""

        current_time = datetime.utcnow()
        start_time = current_time - timedelta(minutes=15)

        async with get_session() as session:
            # Recent audit events
            recent_events = await session.execute(
                select(AuditLog)
                .where(
                    and_(
                        AuditLog.created_at >= start_time,
                        func.coalesce(
                            AuditLog.metadata["compliance_event"]["organization_id"].astext,
                            "default",
                        )
                        == organization_id,
                    )
                )
                .order_by(desc(AuditLog.created_at))
                .limit(50)
            )
            events = recent_events.scalars().all()

            # Event statistics
            event_stats = {
                "total_events": len(events),
                "security_events": len([e for e in events if e.event_type == "security_event"]),
                "failed_logins": len(
                    [e for e in events if e.event_type == "user_access" and e.outcome == "failure"]
                ),
                "privileged_access": len(
                    [e for e in events if e.event_type == "privileged_access"]
                ),
                "system_changes": len([e for e in events if e.event_type == "system_change"]),
            }

            # Active incidents
            active_incidents = await session.execute(
                select(func.count(DataBreachIncident.id)).where(
                    and_(
                        DataBreachIncident.status.in_(["open", "investigating", "containment"]),
                        DataBreachIncident.organization_id == uuid.UUID(organization_id),
                    )
                )
            )
            incident_count = active_incidents.scalar() or 0

            # Pending data subject requests
            pending_requests = await session.execute(
                select(func.count(DataSubjectRequest.id)).where(
                    and_(
                        DataSubjectRequest.status.in_(
                            [RequestStatus.RECEIVED, RequestStatus.IN_PROGRESS]
                        ),
                        DataSubjectRequest.organization_id == uuid.UUID(organization_id),
                    )
                )
            )
            pending_count = pending_requests.scalar() or 0

        # System health indicators
        health_metrics = {
            "event_rate": len(events) / 15,  # Events per minute
            "error_rate": len([e for e in events if e.outcome == "failure"]) / max(len(events), 1),
            "security_alert_rate": event_stats["security_events"] / 15,
            "active_incidents": incident_count,
            "pending_dsr": pending_count,
        }

        # Alert generation
        alerts = []

        if health_metrics["error_rate"] > 0.1:  # >10% error rate
            alerts.append(
                {
                    "level": AlertLevel.WARNING.value,
                    "message": f"High error rate detected: {health_metrics['error_rate']:.1%}",
                    "timestamp": current_time.isoformat(),
                    "metric": "error_rate",
                }
            )

        if incident_count > 0:
            alerts.append(
                {
                    "level": AlertLevel.CRITICAL.value,
                    "message": f"{incident_count} active security incidents",
                    "timestamp": current_time.isoformat(),
                    "metric": "active_incidents",
                }
            )

        if pending_count > 10:
            alerts.append(
                {
                    "level": AlertLevel.WARNING.value,
                    "message": f"{pending_count} pending data subject requests",
                    "timestamp": current_time.isoformat(),
                    "metric": "pending_dsr",
                }
            )

        return {
            "timestamp": current_time.isoformat(),
            "event_statistics": event_stats,
            "health_metrics": health_metrics,
            "alerts": alerts,
            "recent_events": [
                {
                    "timestamp": event.created_at.isoformat(),
                    "type": event.event_type,
                    "action": event.action,
                    "outcome": event.outcome,
                    "resource": f"{event.resource_type}:{event.resource_id}",
                }
                for event in events[:10]
            ],
        }

    async def get_soc2_control_dashboard(
        self, organization_id: str, timeframe: DashboardTimeframe = DashboardTimeframe.MONTHLY
    ) -> Dict[str, Any]:
        """Generate SOC2 control effectiveness dashboard"""

        time_window = self._get_time_window(timeframe)
        start_time = datetime.utcnow() - time_window

        async with get_session() as session:
            # Get all SOC2 controls
            controls_result = await session.execute(
                select(ComplianceControl).where(
                    and_(
                        ComplianceControl.compliance_framework == ComplianceFramework.SOC2,
                        ComplianceControl.organization_id == uuid.UUID(organization_id),
                        ComplianceControl.is_active == True,
                    )
                )
            )
            controls = controls_result.scalars().all()

            # Control family summary
            family_summary = {}
            control_details = []

            for control in controls:
                family = control.control_family or "Other"

                if family not in family_summary:
                    family_summary[family] = {
                        "total_controls": 0,
                        "effective_controls": 0,
                        "controls_with_deficiencies": 0,
                        "average_score": 0,
                    }

                family_summary[family]["total_controls"] += 1

                # Calculate effectiveness score based on rating
                if control.effectiveness_rating == "effective":
                    effectiveness_score = 100
                elif control.effectiveness_rating == "partially_effective":
                    effectiveness_score = 75
                elif control.effectiveness_rating == "ineffective":
                    effectiveness_score = 0
                else:
                    effectiveness_score = 50  # Not tested or unknown rating

                if effectiveness_score >= 85:
                    family_summary[family]["effective_controls"] += 1

                deficiency_count = len(control.deficiencies_identified or [])
                if deficiency_count > 0:
                    family_summary[family]["controls_with_deficiencies"] += 1

                control_details.append(
                    {
                        "control_id": control.control_id,
                        "control_name": control.control_name,
                        "family": family,
                        "effectiveness_score": effectiveness_score,
                        "status": control.effectiveness_rating or "not_tested",
                        "last_tested": control.last_tested_date.isoformat()
                        if control.last_tested_date
                        else None,
                        "deficiencies": deficiency_count,
                        "implementation_status": control.implementation_status,
                        "test_frequency": control.test_frequency,
                    }
                )

            # Calculate family averages
            for family, data in family_summary.items():
                family_controls = [c for c in control_details if c["family"] == family]
                if family_controls:
                    data["average_score"] = sum(
                        c["effectiveness_score"] for c in family_controls
                    ) / len(family_controls)
                    data["effectiveness_rate"] = data["effective_controls"] / data["total_controls"]

            # Overall SOC2 metrics
            total_controls = len(controls)
            effective_controls = len([c for c in control_details if c["effectiveness_score"] >= 85])
            overall_effectiveness = effective_controls / total_controls if total_controls > 0 else 0

            # Control testing metrics
            recently_tested = len(
                [c for c in controls if c.last_tested_date and c.last_tested_date >= start_time]
            )
            testing_coverage = recently_tested / total_controls if total_controls > 0 else 0

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "timeframe": timeframe.value,
            "organization_id": organization_id,
            "overall_metrics": {
                "total_controls": total_controls,
                "effective_controls": effective_controls,
                "overall_effectiveness": overall_effectiveness,
                "testing_coverage": testing_coverage,
                "controls_with_deficiencies": len(
                    [c for c in control_details if c["deficiencies"] > 0]
                ),
            },
            "family_summary": family_summary,
            "control_details": control_details,
            "compliance_status": {
                "status": "compliant"
                if overall_effectiveness >= 0.95
                else "partially_compliant"
                if overall_effectiveness >= 0.8
                else "non_compliant",
                "score": int(overall_effectiveness * 100),
                "last_assessment": datetime.utcnow().isoformat(),
            },
        }

    async def get_sla_performance_dashboard(
        self, organization_id: str, timeframe: DashboardTimeframe = DashboardTimeframe.DAILY
    ) -> Dict[str, Any]:
        """Generate SLA performance dashboard"""

        # Get SLA performance data from SLA monitor
        sla_data = await self.sla_monitor.get_sla_performance_summary(
            organization_id=organization_id, days=self._get_days_from_timeframe(timeframe)
        )

        # Get uptime metrics
        uptime_data = await self.sla_monitor.calculate_uptime_percentage(
            organization_id=organization_id, days=self._get_days_from_timeframe(timeframe)
        )

        # Response time analysis
        response_time_data = await self._get_response_time_metrics(organization_id, timeframe)

        # SLA breach analysis
        breach_analysis = await self._get_sla_breach_analysis(organization_id, timeframe)

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "timeframe": timeframe.value,
            "organization_id": organization_id,
            "uptime_metrics": uptime_data,
            "response_time_metrics": response_time_data,
            "sla_performance": sla_data,
            "breach_analysis": breach_analysis,
            "executive_summary": {
                "overall_uptime": uptime_data.get("overall_percentage", 0),
                "sla_compliance_rate": sla_data.get("compliance_rate", 0),
                "average_response_time": response_time_data.get("average_response_time", 0),
                "total_breaches": breach_analysis.get("total_breaches", 0),
                "critical_breaches": breach_analysis.get("critical_breaches", 0),
            },
        }

    async def get_executive_summary(
        self, organization_id: str, timeframe: DashboardTimeframe = DashboardTimeframe.MONTHLY
    ) -> Dict[str, Any]:
        """Generate executive-level compliance summary"""

        # Get key metrics in parallel
        soc2_data, sla_data, security_data, privacy_data = await asyncio.gather(
            self.get_soc2_control_dashboard(organization_id, timeframe),
            self.get_sla_performance_dashboard(organization_id, timeframe),
            self._get_security_metrics(organization_id, timeframe),
            self._get_privacy_metrics(organization_id, timeframe),
        )

        # Calculate overall compliance score
        soc2_score = soc2_data["overall_metrics"]["overall_effectiveness"] * 100
        sla_score = sla_data["executive_summary"]["sla_compliance_rate"] * 100
        security_score = security_data.get("security_posture_score", 85)
        privacy_score = privacy_data.get("gdpr_compliance_score", 85)

        overall_score = (soc2_score + sla_score + security_score + privacy_score) / 4

        # Risk assessment
        risk_indicators = []
        if soc2_score < 85:
            risk_indicators.append("SOC2 control effectiveness below target")
        if sla_data["executive_summary"]["total_breaches"] > 0:
            risk_indicators.append("SLA breaches detected")
        if security_data.get("security_incidents", 0) > 0:
            risk_indicators.append("Active security incidents")
        if privacy_data.get("overdue_dsr", 0) > 0:
            risk_indicators.append("Overdue data subject requests")

        risk_level = (
            "high"
            if len(risk_indicators) >= 3
            else "medium"
            if len(risk_indicators) >= 1
            else "low"
        )

        return {
            "organization_id": organization_id,
            "report_period": timeframe.value,
            "generated_at": datetime.utcnow().isoformat(),
            "executive_summary": {
                "overall_compliance_score": round(overall_score, 1),
                "risk_level": risk_level,
                "total_risk_indicators": len(risk_indicators),
                "compliance_status": "compliant" if overall_score >= 85 else "requires_attention",
            },
            "key_metrics": {
                "soc2_effectiveness": round(soc2_score, 1),
                "sla_performance": round(sla_score, 1),
                "security_posture": round(security_score, 1),
                "privacy_compliance": round(privacy_score, 1),
                "uptime_percentage": sla_data["executive_summary"]["overall_uptime"],
                "active_incidents": security_data.get("active_incidents", 0),
                "control_deficiencies": soc2_data["overall_metrics"]["controls_with_deficiencies"],
            },
            "risk_indicators": risk_indicators,
            "trending": {
                "compliance_trend": "stable",  # Would calculate from historical data
                "incident_trend": "decreasing"
                if security_data.get("security_incidents", 0) == 0
                else "stable",
                "sla_trend": "stable",
            },
            "recommendations": [
                "Continue quarterly SOC2 control testing",
                "Monitor SLA performance for early breach detection",
                "Review and update security policies quarterly",
                "Ensure timely response to data subject requests",
            ],
            "next_review_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
        }

    # Helper methods

    async def _generate_dashboard_data(
        self, organization_id: str, timeframe: DashboardTimeframe, include_trends: bool
    ) -> ComplianceDashboardData:
        """Generate complete dashboard data"""

        # Parallel data collection
        soc2_data, sla_data, real_time_data = await asyncio.gather(
            self.get_soc2_control_dashboard(organization_id, timeframe),
            self.get_sla_performance_dashboard(organization_id, timeframe),
            self.get_real_time_metrics(organization_id),
        )

        # Generate control summaries
        control_summary = []
        for control in soc2_data["control_details"]:
            control_summary.append(
                SOC2ControlSummary(
                    control_id=control["control_id"],
                    control_name=control["control_name"],
                    control_family=control["family"],
                    status=ControlStatus.EFFECTIVE
                    if control["effectiveness_score"] >= 85
                    else ControlStatus.NEEDS_IMPROVEMENT,
                    effectiveness_score=control["effectiveness_score"],
                    last_tested=datetime.fromisoformat(control["last_tested"])
                    if control["last_tested"]
                    else None,
                    deficiencies=control["deficiencies"],
                    evidence_count=0,  # Would be calculated from evidence collection
                    risk_level="low"
                    if control["effectiveness_score"] >= 85
                    else "medium"
                    if control["effectiveness_score"] >= 70
                    else "high",
                )
            )

        return ComplianceDashboardData(
            organization_id=organization_id,
            generated_at=datetime.utcnow(),
            timeframe=timeframe,
            overall_compliance_score=soc2_data["compliance_status"]["score"],
            active_incidents=real_time_data["health_metrics"]["active_incidents"],
            open_deficiencies=soc2_data["overall_metrics"]["controls_with_deficiencies"],
            sla_performance=sla_data["executive_summary"]["sla_compliance_rate"] * 100,
            soc2_metrics=soc2_data,
            gdpr_metrics={},  # Would be populated with GDPR-specific metrics
            security_metrics=real_time_data,
            control_summary=control_summary,
            control_trends={},  # Would include historical trend data
            sla_metrics=sla_data,
            uptime_metrics=sla_data["uptime_metrics"],
            response_time_metrics=sla_data["response_time_metrics"],
            incident_summary={"active": real_time_data["health_metrics"]["active_incidents"]},
            risk_assessment={"level": "low"},  # Would be calculated based on multiple factors
            active_alerts=real_time_data["alerts"],
            recent_events=real_time_data["recent_events"],
        )

    async def _get_response_time_metrics(
        self, organization_id: str, timeframe: DashboardTimeframe
    ) -> Dict[str, Any]:
        """Get response time metrics for various services"""

        # Note: time_window could be used to query actual performance metrics
        # For now, simplified response time analysis is returned
        # In production, this would query actual performance metrics
        return {
            "average_response_time": 150,  # milliseconds
            "p95_response_time": 300,
            "p99_response_time": 500,
            "api_response_times": {"authentication": 50, "data_access": 200, "reporting": 400},
            "trend": "stable",
            "target_met": True,
        }

    async def _get_sla_breach_analysis(
        self, organization_id: str, timeframe: DashboardTimeframe
    ) -> Dict[str, Any]:
        """Analyze SLA breaches for the given timeframe"""

        time_window = self._get_time_window(timeframe)
        start_time = datetime.utcnow() - time_window

        # Query SLA breaches from audit logs
        async with get_session() as session:
            breach_events = await session.execute(
                select(AuditLog).where(
                    and_(
                        AuditLog.created_at >= start_time,
                        AuditLog.event_type == "sla_breach",
                        func.coalesce(
                            AuditLog.metadata["compliance_event"]["organization_id"].astext,
                            "default",
                        )
                        == organization_id,
                    )
                )
            )
            breaches = breach_events.scalars().all()

            # Analyze breach patterns
            breach_by_type = {}
            critical_breaches = 0

            for breach in breaches:
                breach_type = breach.metadata.get("sla_type", "unknown")
                severity = breach.metadata.get("severity", "medium")

                breach_by_type[breach_type] = breach_by_type.get(breach_type, 0) + 1

                if severity in ["high", "critical"]:
                    critical_breaches += 1

        return {
            "total_breaches": len(breaches),
            "critical_breaches": critical_breaches,
            "breach_by_type": breach_by_type,
            "average_resolution_time": 120,  # minutes
            "repeat_breaches": 0,  # Would calculate from historical data
            "trend": "decreasing" if len(breaches) < 5 else "stable",
        }

    async def _get_security_metrics(
        self, organization_id: str, timeframe: DashboardTimeframe
    ) -> Dict[str, Any]:
        """Get security-related metrics"""

        time_window = self._get_time_window(timeframe)
        start_time = datetime.utcnow() - time_window

        async with get_session() as session:
            # Security incidents
            incidents = await session.execute(
                select(func.count(DataBreachIncident.id)).where(
                    and_(
                        DataBreachIncident.discovered_at >= start_time,
                        DataBreachIncident.organization_id == uuid.UUID(organization_id),
                    )
                )
            )
            incident_count = incidents.scalar() or 0

            # Failed login attempts
            failed_logins = await session.execute(
                select(func.count(AuditLog.id)).where(
                    and_(
                        AuditLog.created_at >= start_time,
                        AuditLog.event_type == "user_access",
                        AuditLog.outcome == "failure",
                        func.coalesce(
                            AuditLog.metadata["compliance_event"]["organization_id"].astext,
                            "default",
                        )
                        == organization_id,
                    )
                )
            )
            failed_login_count = failed_logins.scalar() or 0

        # Calculate security posture score
        security_score = 100
        if incident_count > 0:
            security_score -= min(incident_count * 20, 50)
        if failed_login_count > 100:  # High threshold for failed logins
            security_score -= 15

        return {
            "security_incidents": incident_count,
            "failed_logins": failed_login_count,
            "security_posture_score": max(security_score, 0),
            "active_incidents": incident_count,  # Simplified - would check active status
            "vulnerability_score": 85,  # Would come from vulnerability scanning
            "patch_compliance": 95,  # Would come from patch management system
        }

    async def _get_privacy_metrics(
        self, organization_id: str, timeframe: DashboardTimeframe
    ) -> Dict[str, Any]:
        """Get privacy and GDPR-related metrics"""

        time_window = self._get_time_window(timeframe)
        start_time = datetime.utcnow() - time_window

        async with get_session() as session:
            # Data subject requests
            total_requests = await session.execute(
                select(func.count(DataSubjectRequest.id)).where(
                    and_(
                        DataSubjectRequest.received_at >= start_time,
                        DataSubjectRequest.organization_id == uuid.UUID(organization_id),
                    )
                )
            )
            request_count = total_requests.scalar() or 0

            # Overdue requests
            overdue_requests = await session.execute(
                select(func.count(DataSubjectRequest.id)).where(
                    and_(
                        DataSubjectRequest.response_due_date < datetime.utcnow(),
                        DataSubjectRequest.status.in_(
                            [RequestStatus.RECEIVED, RequestStatus.IN_PROGRESS]
                        ),
                        DataSubjectRequest.organization_id == uuid.UUID(organization_id),
                    )
                )
            )
            overdue_count = overdue_requests.scalar() or 0

        # Calculate GDPR compliance score
        gdpr_score = 100
        if overdue_count > 0:
            gdpr_score -= min(overdue_count * 10, 50)

        return {
            "total_dsr": request_count,
            "overdue_dsr": overdue_count,
            "gdpr_compliance_score": max(gdpr_score, 0),
            "consent_management_score": 90,  # Would calculate from consent records
            "data_retention_compliance": 95,  # Would calculate from retention policies
        }

    def _get_time_window(self, timeframe: DashboardTimeframe) -> timedelta:
        """Convert timeframe to timedelta"""
        windows = {
            DashboardTimeframe.REALTIME: timedelta(minutes=15),
            DashboardTimeframe.HOURLY: timedelta(hours=24),
            DashboardTimeframe.DAILY: timedelta(days=30),
            DashboardTimeframe.WEEKLY: timedelta(weeks=12),
            DashboardTimeframe.MONTHLY: timedelta(days=365),
            DashboardTimeframe.QUARTERLY: timedelta(days=1460),  # 4 years
            DashboardTimeframe.YEARLY: timedelta(days=1825),  # 5 years
        }
        return windows.get(timeframe, timedelta(days=30))

    def _get_days_from_timeframe(self, timeframe: DashboardTimeframe) -> int:
        """Convert timeframe to days"""
        days = {
            DashboardTimeframe.REALTIME: 1,
            DashboardTimeframe.HOURLY: 1,
            DashboardTimeframe.DAILY: 30,
            DashboardTimeframe.WEEKLY: 84,
            DashboardTimeframe.MONTHLY: 365,
            DashboardTimeframe.QUARTERLY: 1460,
            DashboardTimeframe.YEARLY: 1825,
        }
        return days.get(timeframe, 30)


class ComplianceMetrics:
    """Compliance metrics calculation and aggregation"""

    def __init__(self, dashboard: ComplianceDashboard):
        self.dashboard = dashboard

    async def calculate_compliance_trends(
        self, organization_id: str, metric_name: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Calculate trend data for specific compliance metrics"""

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Generate daily data points
        trend_data = []
        current_date = start_date

        while current_date <= end_date:
            # For each day, calculate the metric value
            # This is simplified - in production would query historical data

            if metric_name == "overall_compliance":
                value = 85 + (current_date.day % 10)  # Simulated trend
            elif metric_name == "sla_performance":
                value = 95 + (current_date.day % 5)
            elif metric_name == "control_effectiveness":
                value = 90 + (current_date.day % 8)
            else:
                value = 80

            trend_data.append(
                {
                    "date": current_date.isoformat(),
                    "value": value,
                    "target": 85 if metric_name != "sla_performance" else 99,
                }
            )

            current_date += timedelta(days=1)

        return trend_data

    async def generate_compliance_scorecard(self, organization_id: str) -> Dict[str, Any]:
        """Generate comprehensive compliance scorecard"""

        dashboard_data = await self.dashboard.get_dashboard_data(organization_id)

        scorecard = {
            "organization_id": organization_id,
            "generated_at": datetime.utcnow().isoformat(),
            "overall_score": dashboard_data.overall_compliance_score,
            "grade": self._calculate_grade(dashboard_data.overall_compliance_score),
            "framework_scores": {
                "soc2": dashboard_data.soc2_metrics.get("compliance_status", {}).get("score", 0),
                "gdpr": 85,  # Would be calculated from GDPR metrics
                "security": 88,  # Would be calculated from security metrics
                "operational": dashboard_data.sla_performance,
            },
            "key_performance_indicators": {
                "uptime_percentage": dashboard_data.uptime_metrics.get("overall_percentage", 0),
                "incident_response_time": 30,  # minutes
                "control_effectiveness": len(
                    [
                        c
                        for c in dashboard_data.control_summary
                        if c.status == ControlStatus.EFFECTIVE
                    ]
                )
                / len(dashboard_data.control_summary)
                * 100
                if dashboard_data.control_summary
                else 0,
                "sla_compliance_rate": dashboard_data.sla_performance,
                "data_subject_response_rate": 95,  # Would be calculated from DSR data
            },
            "risk_assessment": {
                "overall_risk_level": "low",
                "critical_findings": len(
                    [
                        alert
                        for alert in dashboard_data.active_alerts
                        if alert.get("level") == "critical"
                    ]
                ),
                "open_deficiencies": dashboard_data.open_deficiencies,
                "remediation_timeline": "30 days",
            },
        }

        return scorecard

    def _calculate_grade(self, score: float) -> str:
        """Calculate letter grade from numerical score"""
        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 85:
            return "B+"
        elif score >= 80:
            return "B"
        elif score >= 75:
            return "C+"
        elif score >= 70:
            return "C"
        else:
            return "F"
