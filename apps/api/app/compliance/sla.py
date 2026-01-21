"""
Enterprise SLA monitoring and reporting infrastructure for compliance and customer commitments.
Tracks service level objectives, uptime guarantees, and enterprise performance requirements.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import statistics
import redis.asyncio as aioredis
import psutil
from sqlalchemy import select, and_, func

from app.core.database import get_session
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


class SLAStatus(str, Enum):
    """SLA compliance status"""
    MEETING = "meeting"           # Above SLA threshold
    AT_RISK = "at_risk"          # Close to SLA threshold
    BREACH = "breach"            # Below SLA threshold
    CRITICAL = "critical"        # Significantly below SLA threshold


class MetricType(str, Enum):
    """Types of SLA metrics"""
    UPTIME = "uptime"                    # System availability percentage
    RESPONSE_TIME = "response_time"      # API response time (ms)
    ERROR_RATE = "error_rate"           # Error percentage
    THROUGHPUT = "throughput"           # Requests per second
    RECOVERY_TIME = "recovery_time"     # Incident recovery time (minutes)
    SUPPORT_RESPONSE = "support_response" # Support ticket response time


class AlertLevel(str, Enum):
    """SLA alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class ServiceLevelObjective:
    """Service Level Objective definition"""
    slo_id: str
    name: str
    description: str
    metric_type: MetricType
    target_value: float              # Target value (e.g., 99.9 for uptime %)
    warning_threshold: float         # Warning threshold (e.g., 99.5)
    critical_threshold: float        # Critical threshold (e.g., 99.0)
    measurement_window_hours: int    # Measurement window (e.g., 24, 168, 720)
    measurement_unit: str           # Unit (%, ms, count, etc.)

    # Enterprise commitments
    customer_facing: bool = False    # Customer-facing SLA
    regulatory_required: bool = False # Required for compliance
    penalty_applicable: bool = False  # SLA credits/penalties apply

    # Monitoring configuration
    check_interval_minutes: int = 5
    alert_enabled: bool = True
    escalation_enabled: bool = True

    created_at: datetime = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


@dataclass
class SLAMeasurement:
    """Individual SLA measurement point"""
    measurement_id: str
    slo_id: str
    measured_value: float
    timestamp: datetime
    status: SLAStatus
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SLAReport:
    """SLA performance report"""
    report_id: str
    slo_id: str
    reporting_period_start: datetime
    reporting_period_end: datetime

    # Performance metrics
    actual_performance: float
    target_performance: float
    compliance_percentage: float

    # Breach information
    total_breaches: int
    total_breach_minutes: float
    longest_breach_minutes: float

    # Statistical data
    measurements_count: int
    min_value: float
    max_value: float
    average_value: float
    p95_value: float
    p99_value: float

    # Compliance assessment
    sla_status: SLAStatus
    customer_impact: bool
    credits_applicable: bool

    generated_at: datetime = None

    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.utcnow()


class SLAMonitor:
    """
    Enterprise SLA monitoring system for tracking service level objectives
    and generating compliance reports for customer commitments.
    """

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis_client = redis_client
        self.sla_storage = Path("compliance/sla")
        self.sla_storage.mkdir(parents=True, exist_ok=True)

        # Standard enterprise SLOs
        self.default_slos = self._create_default_slos()

    def _create_default_slos(self) -> List[ServiceLevelObjective]:
        """Create standard enterprise SLOs"""
        return [
            # System Uptime - Customer-facing 99.9% SLA
            ServiceLevelObjective(
                slo_id="uptime-customer",
                name="System Uptime - Customer SLA",
                description="Customer-facing uptime guarantee",
                metric_type=MetricType.UPTIME,
                target_value=99.9,          # 99.9% uptime
                warning_threshold=99.5,     # Warning at 99.5%
                critical_threshold=99.0,    # Critical at 99.0%
                measurement_window_hours=720,  # 30 days
                measurement_unit="%",
                customer_facing=True,
                regulatory_required=True,
                penalty_applicable=True,
                check_interval_minutes=1
            ),

            # API Response Time - Customer-facing 1s SLA
            ServiceLevelObjective(
                slo_id="api-response-time",
                name="API Response Time",
                description="API endpoint response time SLA",
                metric_type=MetricType.RESPONSE_TIME,
                target_value=1000,          # 1000ms (1 second)
                warning_threshold=1500,     # Warning at 1.5s
                critical_threshold=3000,    # Critical at 3s
                measurement_window_hours=24,  # 24 hours
                measurement_unit="ms",
                customer_facing=True,
                penalty_applicable=True,
                check_interval_minutes=5
            ),

            # Error Rate - Internal monitoring
            ServiceLevelObjective(
                slo_id="api-error-rate",
                name="API Error Rate",
                description="API error rate monitoring",
                metric_type=MetricType.ERROR_RATE,
                target_value=1.0,           # 1% error rate
                warning_threshold=2.0,      # Warning at 2%
                critical_threshold=5.0,     # Critical at 5%
                measurement_window_hours=24,
                measurement_unit="%",
                customer_facing=False,
                alert_enabled=True
            ),

            # Support Response Time - Customer-facing
            ServiceLevelObjective(
                slo_id="support-response-critical",
                name="Critical Support Response",
                description="Critical support ticket response time",
                metric_type=MetricType.SUPPORT_RESPONSE,
                target_value=60,            # 60 minutes
                warning_threshold=45,       # Warning at 45 min
                critical_threshold=30,      # Critical at 30 min
                measurement_window_hours=168,  # 7 days
                measurement_unit="minutes",
                customer_facing=True,
                penalty_applicable=True
            ),

            # Database Response Time - Internal
            ServiceLevelObjective(
                slo_id="database-response-time",
                name="Database Response Time",
                description="Database query response time",
                metric_type=MetricType.RESPONSE_TIME,
                target_value=500,           # 500ms
                warning_threshold=750,      # Warning at 750ms
                critical_threshold=1000,    # Critical at 1s
                measurement_window_hours=24,
                measurement_unit="ms",
                customer_facing=False
            ),

            # Authentication Service Uptime
            ServiceLevelObjective(
                slo_id="auth-uptime",
                name="Authentication Service Uptime",
                description="Authentication service availability",
                metric_type=MetricType.UPTIME,
                target_value=99.95,         # 99.95% uptime
                warning_threshold=99.9,     # Warning at 99.9%
                critical_threshold=99.5,    # Critical at 99.5%
                measurement_window_hours=168,  # 7 days
                measurement_unit="%",
                customer_facing=True,
                regulatory_required=True
            )
        ]

    async def initialize_slos(self) -> bool:
        """Initialize default SLOs if not already created"""
        try:
            for slo in self.default_slos:
                await self._save_slo(slo)

            logger.info(f"Initialized {len(self.default_slos)} default SLOs")
            return True

        except Exception as e:
            logger.error(f"Error initializing SLOs: {e}")
            return False

    async def measure_all_slos(self) -> Dict[str, Any]:
        """Measure all active SLOs and update status"""
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "measurements": {},
            "alerts_generated": [],
            "breaches_detected": [],
            "summary": {}
        }

        try:
            slos = await self.get_all_slos()

            for slo in slos:
                try:
                    measurement = await self._measure_slo(slo)
                    results["measurements"][slo.slo_id] = asdict(measurement)

                    # Check for alerts
                    alerts = await self._check_sla_alerts(slo, measurement)
                    if alerts:
                        results["alerts_generated"].extend(alerts)

                    # Check for breaches
                    if measurement.status in [SLAStatus.BREACH, SLAStatus.CRITICAL]:
                        results["breaches_detected"].append({
                            "slo_id": slo.slo_id,
                            "name": slo.name,
                            "status": measurement.status,
                            "actual_value": measurement.measured_value,
                            "target_value": slo.target_value,
                            "customer_facing": slo.customer_facing
                        })

                except Exception as e:
                    logger.error(f"Error measuring SLO {slo.slo_id}: {e}")

            # Generate summary
            results["summary"] = await self._generate_measurement_summary(results)

        except Exception as e:
            logger.error(f"Error in SLA measurement cycle: {e}")
            results["error"] = str(e)

        return results

    async def generate_sla_report(self, slo_id: str, hours: int = 24) -> SLAReport:
        """Generate SLA performance report for specified period"""
        slo = await self.get_slo(slo_id)
        if not slo:
            raise ValueError(f"SLO not found: {slo_id}")

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        measurements = await self._get_measurements(slo_id, start_time, end_time)

        if not measurements:
            raise ValueError(f"No measurements found for SLO {slo_id} in specified period")

        # Calculate performance metrics
        values = [m.measured_value for m in measurements]

        # For uptime, calculate actual uptime percentage
        if slo.metric_type == MetricType.UPTIME:
            actual_performance = self._calculate_uptime_percentage(measurements)
        elif slo.metric_type == MetricType.RESPONSE_TIME:
            actual_performance = statistics.mean(values)
        elif slo.metric_type == MetricType.ERROR_RATE:
            actual_performance = statistics.mean(values)
        else:
            actual_performance = statistics.mean(values)

        # Calculate compliance
        if slo.metric_type == MetricType.UPTIME:
            compliance_percentage = min(100.0, (actual_performance / slo.target_value) * 100)
        elif slo.metric_type in [MetricType.RESPONSE_TIME, MetricType.ERROR_RATE]:
            # For response time and error rate, lower is better
            compliant_measurements = len([v for v in values if v <= slo.target_value])
            compliance_percentage = (compliant_measurements / len(values)) * 100
        else:
            compliant_measurements = len([v for v in values if v >= slo.target_value])
            compliance_percentage = (compliant_measurements / len(values)) * 100

        # Calculate breach information
        breach_measurements = [m for m in measurements if m.status in [SLAStatus.BREACH, SLAStatus.CRITICAL]]

        if breach_measurements:
            # Calculate breach duration (simplified - assumes continuous monitoring)
            breach_minutes = len(breach_measurements) * slo.check_interval_minutes
            longest_breach = slo.check_interval_minutes  # Simplified calculation
        else:
            breach_minutes = 0.0
            longest_breach = 0.0

        # Determine SLA status
        if actual_performance >= slo.target_value:
            sla_status = SLAStatus.MEETING
        elif actual_performance >= slo.warning_threshold:
            sla_status = SLAStatus.AT_RISK
        elif actual_performance >= slo.critical_threshold:
            sla_status = SLAStatus.BREACH
        else:
            sla_status = SLAStatus.CRITICAL

        # Calculate statistical metrics
        sorted_values = sorted(values)
        p95_index = int(len(sorted_values) * 0.95)
        p99_index = int(len(sorted_values) * 0.99)

        report = SLAReport(
            report_id=f"SLA-{slo_id}-{start_time.strftime('%Y%m%d%H%M')}-{end_time.strftime('%Y%m%d%H%M')}",
            slo_id=slo_id,
            reporting_period_start=start_time,
            reporting_period_end=end_time,
            actual_performance=actual_performance,
            target_performance=slo.target_value,
            compliance_percentage=compliance_percentage,
            total_breaches=len(breach_measurements),
            total_breach_minutes=breach_minutes,
            longest_breach_minutes=longest_breach,
            measurements_count=len(measurements),
            min_value=min(values),
            max_value=max(values),
            average_value=statistics.mean(values),
            p95_value=sorted_values[p95_index] if p95_index < len(sorted_values) else max(values),
            p99_value=sorted_values[p99_index] if p99_index < len(sorted_values) else max(values),
            sla_status=sla_status,
            customer_impact=slo.customer_facing and sla_status in [SLAStatus.BREACH, SLAStatus.CRITICAL],
            credits_applicable=slo.penalty_applicable and compliance_percentage < 100.0
        )

        await self._save_sla_report(report)
        return report

    async def get_uptime_tracker(self) -> "UptimeTracker":
        """Get uptime tracking utility"""
        return UptimeTracker(self.redis_client)

    async def get_customer_sla_dashboard(self) -> Dict[str, Any]:
        """Get customer-facing SLA dashboard data"""
        dashboard = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy",
            "sla_metrics": [],
            "recent_incidents": [],
            "uptime_statistics": {}
        }

        try:
            # Get customer-facing SLOs
            slos = await self.get_customer_facing_slos()

            overall_compliant = True

            for slo in slos:
                # Get latest report
                report = await self.generate_sla_report(slo.slo_id, hours=slo.measurement_window_hours)

                metric_data = {
                    "name": slo.name,
                    "current_performance": report.actual_performance,
                    "target": slo.target_value,
                    "unit": slo.measurement_unit,
                    "status": report.sla_status,
                    "compliance_percentage": report.compliance_percentage,
                    "measurement_window_hours": slo.measurement_window_hours
                }

                dashboard["sla_metrics"].append(metric_data)

                if report.sla_status in [SLAStatus.BREACH, SLAStatus.CRITICAL]:
                    overall_compliant = False

            dashboard["overall_status"] = "healthy" if overall_compliant else "degraded"

            # Get uptime statistics
            uptime_tracker = await self.get_uptime_tracker()
            dashboard["uptime_statistics"] = await uptime_tracker.get_uptime_summary()

        except Exception as e:
            logger.error(f"Error generating customer SLA dashboard: {e}")
            dashboard["error"] = str(e)
            dashboard["overall_status"] = "unknown"

        return dashboard

    # Private helper methods

    async def _measure_slo(self, slo: ServiceLevelObjective) -> SLAMeasurement:
        """Measure individual SLO"""
        measurement_id = f"{slo.slo_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

        if slo.metric_type == MetricType.UPTIME:
            measured_value = await self._measure_uptime(slo)
        elif slo.metric_type == MetricType.RESPONSE_TIME:
            measured_value = await self._measure_response_time(slo)
        elif slo.metric_type == MetricType.ERROR_RATE:
            measured_value = await self._measure_error_rate(slo)
        elif slo.metric_type == MetricType.THROUGHPUT:
            measured_value = await self._measure_throughput(slo)
        else:
            logger.warning(f"Unsupported metric type: {slo.metric_type}")
            measured_value = 0.0

        # Determine status based on thresholds
        if slo.metric_type in [MetricType.RESPONSE_TIME, MetricType.ERROR_RATE]:
            # Lower is better for these metrics
            if measured_value <= slo.target_value:
                status = SLAStatus.MEETING
            elif measured_value <= slo.warning_threshold:
                status = SLAStatus.AT_RISK
            elif measured_value <= slo.critical_threshold:
                status = SLAStatus.BREACH
            else:
                status = SLAStatus.CRITICAL
        else:
            # Higher is better for uptime, throughput
            if measured_value >= slo.target_value:
                status = SLAStatus.MEETING
            elif measured_value >= slo.warning_threshold:
                status = SLAStatus.AT_RISK
            elif measured_value >= slo.critical_threshold:
                status = SLAStatus.BREACH
            else:
                status = SLAStatus.CRITICAL

        measurement = SLAMeasurement(
            measurement_id=measurement_id,
            slo_id=slo.slo_id,
            measured_value=measured_value,
            timestamp=datetime.utcnow(),
            status=status,
            metadata={
                "measurement_method": f"automated_{slo.metric_type}",
                "measurement_window_hours": slo.measurement_window_hours
            }
        )

        await self._save_measurement(measurement)
        return measurement

    async def _measure_uptime(self, slo: ServiceLevelObjective) -> float:
        """Measure system uptime percentage"""
        try:
            # Check system responsiveness
            system_responsive = await self._check_system_health()

            if system_responsive:
                return 100.0  # Currently up
            else:
                return 0.0    # Currently down

        except Exception as e:
            logger.error(f"Error measuring uptime: {e}")
            return 0.0

    async def _measure_response_time(self, slo: ServiceLevelObjective) -> float:
        """Measure API response time"""
        try:
            # Simulate API response time measurement
            # In real implementation, this would make actual API calls
            import time

            start_time = time.time()

            # Mock API health check
            await asyncio.sleep(0.1)  # Simulate API call

            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000

            return response_time_ms

        except Exception as e:
            logger.error(f"Error measuring response time: {e}")
            return 5000.0  # Return high value to indicate failure

    async def _measure_error_rate(self, slo: ServiceLevelObjective) -> float:
        """Measure API error rate"""
        try:
            async with get_session() as session:
                # Count total requests and errors in the last hour
                one_hour_ago = datetime.utcnow() - timedelta(hours=1)

                total_requests_query = select(func.count(AuditLog.id)).where(
                    and_(
                        AuditLog.action.in_(['api_request', 'authentication', 'api_success']),
                        AuditLog.created_at >= one_hour_ago
                    )
                )

                error_requests_query = select(func.count(AuditLog.id)).where(
                    and_(
                        AuditLog.action.in_(['api_error', 'authentication_failed']),
                        AuditLog.created_at >= one_hour_ago
                    )
                )

                total_result = await session.execute(total_requests_query)
                error_result = await session.execute(error_requests_query)

                total_requests = total_result.scalar() or 0
                error_requests = error_result.scalar() or 0

                if total_requests == 0:
                    return 0.0

                error_rate = (error_requests / total_requests) * 100
                return error_rate

        except Exception as e:
            logger.error(f"Error measuring error rate: {e}")
            return 10.0  # Return high error rate to indicate measurement failure

    async def _measure_throughput(self, slo: ServiceLevelObjective) -> float:
        """Measure system throughput (requests per second)"""
        try:
            async with get_session() as session:
                # Count requests in the last minute
                one_minute_ago = datetime.utcnow() - timedelta(minutes=1)

                requests_query = select(func.count(AuditLog.id)).where(
                    and_(
                        AuditLog.action.in_(['api_request', 'authentication']),
                        AuditLog.created_at >= one_minute_ago
                    )
                )

                result = await session.execute(requests_query)
                requests_per_minute = result.scalar() or 0

                # Convert to requests per second
                requests_per_second = requests_per_minute / 60.0
                return requests_per_second

        except Exception as e:
            logger.error(f"Error measuring throughput: {e}")
            return 0.0

    async def _check_system_health(self) -> bool:
        """Check if system is healthy and responsive"""
        try:
            # Check database connectivity
            async with get_session() as session:
                result = await session.execute(select(1))
                if result.scalar() != 1:
                    return False

            # Check system resources
            cpu_usage = psutil.cpu_percent(interval=1)
            memory_usage = psutil.virtual_memory().percent

            if cpu_usage > 95 or memory_usage > 98:
                return False

            return True

        except Exception as e:
            logger.error(f"System health check failed: {e}")
            return False

    async def _check_sla_alerts(self, slo: ServiceLevelObjective, measurement: SLAMeasurement) -> List[Dict[str, Any]]:
        """Check if measurement triggers SLA alerts"""
        alerts = []

        if not slo.alert_enabled:
            return alerts

        alert_level = None
        message = ""

        if measurement.status == SLAStatus.CRITICAL:
            alert_level = AlertLevel.EMERGENCY
            message = f"CRITICAL SLA BREACH: {slo.name} at {measurement.measured_value}{slo.measurement_unit}"
        elif measurement.status == SLAStatus.BREACH:
            alert_level = AlertLevel.CRITICAL
            message = f"SLA BREACH: {slo.name} at {measurement.measured_value}{slo.measurement_unit}"
        elif measurement.status == SLAStatus.AT_RISK:
            alert_level = AlertLevel.WARNING
            message = f"SLA AT RISK: {slo.name} at {measurement.measured_value}{slo.measurement_unit}"

        if alert_level:
            alert = {
                "alert_id": f"SLA-{slo.slo_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "slo_id": slo.slo_id,
                "slo_name": slo.name,
                "alert_level": alert_level,
                "message": message,
                "measured_value": measurement.measured_value,
                "target_value": slo.target_value,
                "customer_facing": slo.customer_facing,
                "timestamp": measurement.timestamp.isoformat()
            }

            alerts.append(alert)

            # Log alert for incident management
            logger.warning(f"SLA Alert: {message}")

        return alerts

    async def _generate_measurement_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of measurement results"""
        measurements = results.get("measurements", {})

        summary = {
            "total_slos_measured": len(measurements),
            "slos_meeting_target": 0,
            "slos_at_risk": 0,
            "slos_in_breach": 0,
            "customer_facing_breaches": 0,
            "total_alerts": len(results.get("alerts_generated", [])),
            "critical_alerts": 0
        }

        for measurement_data in measurements.values():
            status = measurement_data.get("status")

            if status == SLAStatus.MEETING:
                summary["slos_meeting_target"] += 1
            elif status == SLAStatus.AT_RISK:
                summary["slos_at_risk"] += 1
            elif status in [SLAStatus.BREACH, SLAStatus.CRITICAL]:
                summary["slos_in_breach"] += 1

        # Count customer-facing breaches
        for breach in results.get("breaches_detected", []):
            if breach.get("customer_facing"):
                summary["customer_facing_breaches"] += 1

        # Count critical alerts
        for alert in results.get("alerts_generated", []):
            if alert.get("alert_level") in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY]:
                summary["critical_alerts"] += 1

        return summary

    def _calculate_uptime_percentage(self, measurements: List[SLAMeasurement]) -> float:
        """Calculate uptime percentage from measurements"""
        if not measurements:
            return 0.0

        up_measurements = len([m for m in measurements if m.measured_value > 0])
        total_measurements = len(measurements)

        return (up_measurements / total_measurements) * 100.0

    # Storage methods

    async def get_slo(self, slo_id: str) -> Optional[ServiceLevelObjective]:
        """Get SLO by ID"""
        slo_file = self.sla_storage / f"slos/{slo_id}.json"

        if not slo_file.exists():
            return None

        try:
            with open(slo_file, 'r') as f:
                slo_data = json.load(f)

            # Convert datetime strings back to datetime objects
            for field in ['created_at', 'updated_at']:
                if slo_data.get(field):
                    slo_data[field] = datetime.fromisoformat(slo_data[field])

            return ServiceLevelObjective(**slo_data)

        except Exception as e:
            logger.error(f"Error loading SLO {slo_id}: {e}")
            return None

    async def get_all_slos(self) -> List[ServiceLevelObjective]:
        """Get all SLOs"""
        slos = []
        slos_dir = self.sla_storage / "slos"

        if not slos_dir.exists():
            return slos

        for slo_file in slos_dir.glob("*.json"):
            slo = await self.get_slo(slo_file.stem)
            if slo:
                slos.append(slo)

        return slos

    async def get_customer_facing_slos(self) -> List[ServiceLevelObjective]:
        """Get customer-facing SLOs"""
        all_slos = await self.get_all_slos()
        return [slo for slo in all_slos if slo.customer_facing]

    async def _save_slo(self, slo: ServiceLevelObjective):
        """Save SLO to storage"""
        slos_dir = self.sla_storage / "slos"
        slos_dir.mkdir(parents=True, exist_ok=True)

        slo_file = slos_dir / f"{slo.slo_id}.json"
        slo_data = asdict(slo)

        # Convert datetime objects to ISO strings
        for field in ['created_at', 'updated_at']:
            if slo_data.get(field):
                slo_data[field] = slo_data[field].isoformat()

        with open(slo_file, 'w') as f:
            json.dump(slo_data, f, indent=2, default=str)

    async def _save_measurement(self, measurement: SLAMeasurement):
        """Save measurement to storage"""
        measurements_dir = self.sla_storage / "measurements" / measurement.slo_id
        measurements_dir.mkdir(parents=True, exist_ok=True)

        measurement_file = measurements_dir / f"{measurement.measurement_id}.json"
        measurement_data = asdict(measurement)

        # Convert datetime to ISO string
        measurement_data["timestamp"] = measurement_data["timestamp"].isoformat()

        with open(measurement_file, 'w') as f:
            json.dump(measurement_data, f, indent=2, default=str)

    async def _save_sla_report(self, report: SLAReport):
        """Save SLA report to storage"""
        reports_dir = self.sla_storage / "reports" / report.slo_id
        reports_dir.mkdir(parents=True, exist_ok=True)

        report_file = reports_dir / f"{report.report_id}.json"
        report_data = asdict(report)

        # Convert datetime objects to ISO strings
        for field in ['reporting_period_start', 'reporting_period_end', 'generated_at']:
            if report_data.get(field):
                report_data[field] = report_data[field].isoformat()

        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)

    async def _get_measurements(self, slo_id: str, start_time: datetime, end_time: datetime) -> List[SLAMeasurement]:
        """Get measurements for SLO in time range"""
        measurements = []
        measurements_dir = self.sla_storage / "measurements" / slo_id

        if not measurements_dir.exists():
            return measurements

        for measurement_file in measurements_dir.glob("*.json"):
            try:
                with open(measurement_file, 'r') as f:
                    measurement_data = json.load(f)

                timestamp = datetime.fromisoformat(measurement_data["timestamp"])

                if start_time <= timestamp <= end_time:
                    measurement_data["timestamp"] = timestamp
                    measurements.append(SLAMeasurement(**measurement_data))

            except Exception as e:
                logger.error(f"Error loading measurement from {measurement_file}: {e}")

        return sorted(measurements, key=lambda x: x.timestamp)


class UptimeTracker:
    """Specialized uptime tracking for high-precision availability monitoring"""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis_client = redis_client
        self.uptime_key = "janua:uptime"

    async def record_uptime_check(self, is_up: bool, timestamp: Optional[datetime] = None):
        """Record uptime status check"""
        if timestamp is None:
            timestamp = datetime.utcnow()

        if self.redis_client:
            try:
                # Store uptime status with timestamp
                status_value = 1 if is_up else 0
                await self.redis_client.zadd(
                    f"{self.uptime_key}:status",
                    {timestamp.timestamp(): status_value}
                )

                # Keep last 30 days of data
                cutoff_timestamp = (timestamp - timedelta(days=30)).timestamp()
                await self.redis_client.zremrangebyscore(
                    f"{self.uptime_key}:status",
                    0,
                    cutoff_timestamp
                )

            except Exception as e:
                logger.error(f"Error recording uptime check: {e}")

    async def get_uptime_percentage(self, hours: int = 24) -> float:
        """Get uptime percentage for specified period"""
        if not self.redis_client:
            return 99.9  # Default high uptime if Redis unavailable

        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)

            # Get status checks in time range
            status_checks = await self.redis_client.zrangebyscore(
                f"{self.uptime_key}:status",
                start_time.timestamp(),
                end_time.timestamp(),
                withscores=True
            )

            if not status_checks:
                return 99.9  # Assume up if no data

            total_checks = len(status_checks)
            up_checks = sum(1 for value, _ in status_checks if int(value) == 1)

            return (up_checks / total_checks) * 100.0

        except Exception as e:
            logger.error(f"Error calculating uptime percentage: {e}")
            return 99.9

    async def get_uptime_summary(self) -> Dict[str, Any]:
        """Get comprehensive uptime summary"""
        summary = {
            "current_status": "up",
            "uptime_24h": await self.get_uptime_percentage(24),
            "uptime_7d": await self.get_uptime_percentage(168),
            "uptime_30d": await self.get_uptime_percentage(720),
            "last_incident": None,
            "incident_count_30d": 0
        }

        try:
            # Check current system health
            system_healthy = await self._check_current_health()
            summary["current_status"] = "up" if system_healthy else "down"

            # Get recent incidents (simplified)
            summary["incident_count_30d"] = await self._count_recent_incidents()

        except Exception as e:
            logger.error(f"Error generating uptime summary: {e}")
            summary["error"] = str(e)

        return summary

    async def _check_current_health(self) -> bool:
        """Check current system health"""
        try:
            # Basic health checks
            async with get_session() as session:
                result = await session.execute(select(1))
                return result.scalar() == 1

        except Exception:
            return False

    async def _count_recent_incidents(self) -> int:
        """Count recent downtime incidents"""
        # This would integrate with incident management system
        # For now, return 0
        return 0