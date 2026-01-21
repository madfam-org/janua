"""
Compliance Monitor Main Orchestrator
High-level orchestration and SOC2 compliance logic.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import redis.asyncio as aioredis


from .control_status import ControlStatus, ControlResult, ComplianceEvidence
from .control_monitor import ControlMonitor
from .evidence_collector import EvidenceCollector


logger = logging.getLogger(__name__)


class ComplianceMonitor:
    """
    Primary compliance monitoring system for SOC2 and enterprise requirements.
    Automates control testing, evidence collection, and compliance reporting.
    """

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.redis_client = redis_client
        self.evidence_storage = Path("compliance/evidence")
        self.evidence_storage.mkdir(parents=True, exist_ok=True)

        # Initialize specialized monitors
        self.control_monitor = ControlMonitor(redis_client)
        self.evidence_collector = EvidenceCollector(self.evidence_storage)

        # SOC2 control mapping
        self.soc2_controls = {
            # Common Criteria (CC) - Security
            "CC1.1": "Control Environment - Governance Structure",
            "CC1.2": "Control Environment - Board Oversight",
            "CC2.1": "Communication - Policy Communication",
            "CC2.2": "Communication - Training and Awareness",
            "CC3.1": "Risk Assessment - Risk Identification",
            "CC3.2": "Risk Assessment - Risk Analysis",
            "CC4.1": "Monitoring - Control Effectiveness",
            "CC4.2": "Monitoring - Deficiency Communication",
            "CC5.1": "Control Activities - Selection and Development",
            "CC5.2": "Control Activities - Technology Controls",
            "CC6.1": "Logical Access - User Access Provisioning",
            "CC6.2": "Logical Access - User Authentication",
            "CC6.3": "Logical Access - User Authorization",
            "CC6.6": "Logical Access - System Access Removal",
            "CC6.7": "Logical Access - Privileged User Access",
            "CC6.8": "Logical Access - User Access Reviews",
            "CC7.1": "System Operations - Data Backup and Recovery",
            "CC7.2": "System Operations - System Monitoring",
            "CC7.3": "System Operations - Environmental Protections",
            "CC7.4": "System Operations - System Capacity",
            "CC8.1": "Change Management - Authorization",

            # Availability (A)
            "A1.1": "Availability - System Processing",
            "A1.2": "Availability - System Monitoring",
            "A1.3": "Availability - System Recovery",

            # Processing Integrity (PI)
            "PI1.1": "Processing Integrity - Input Validation",
            "PI1.2": "Processing Integrity - Data Processing",
            "PI1.3": "Processing Integrity - Output Validation",

            # Confidentiality (C)
            "C1.1": "Confidentiality - Information Classification",
            "C1.2": "Confidentiality - Access Controls",

            # Privacy (P)
            "P1.1": "Privacy - Notice and Communication",
            "P2.1": "Privacy - Choice and Consent",
            "P3.1": "Privacy - Collection",
            "P4.1": "Privacy - Use, Retention, and Disposal",
            "P5.1": "Privacy - Access",
            "P6.1": "Privacy - Disclosure to Third Parties",
            "P7.1": "Privacy - Quality",
            "P8.1": "Privacy - Monitoring and Enforcement"
        }

    async def run_daily_monitoring(self) -> Dict[str, Any]:
        """Run comprehensive daily compliance monitoring"""
        logger.info("Starting daily compliance monitoring cycle")

        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "monitoring_cycle": "daily",
            "controls_tested": {},
            "evidence_collected": [],
            "exceptions_identified": [],
            "recommendations": []
        }

        try:
            # Test security controls
            security_results = await self.test_security_controls()
            results["controls_tested"]["security"] = security_results

            # Test availability controls
            availability_results = await self.test_availability_controls()
            results["controls_tested"]["availability"] = availability_results

            # Test processing integrity
            integrity_results = await self.test_processing_integrity()
            results["controls_tested"]["processing_integrity"] = integrity_results

            # Test access controls
            access_results = await self.test_access_controls()
            results["controls_tested"]["access"] = access_results

            # Collect evidence
            evidence = await self.collect_daily_evidence()
            results["evidence_collected"] = evidence

            # Generate compliance summary
            summary = await self.generate_compliance_summary(results)
            results["summary"] = summary

            logger.info(f"Daily monitoring completed. Controls tested: {len(results['controls_tested'])}")
            return results

        except Exception as e:
            logger.error(f"Daily monitoring failed: {str(e)}")
            results["error"] = str(e)
            return results

    async def test_security_controls(self) -> Dict[str, ControlResult]:
        """Test security-related SOC2 controls"""
        security_controls = ["CC1.1", "CC1.2", "CC2.1", "CC2.2", "CC3.1", "CC3.2"]
        results = {}

        for control_id in security_controls:
            try:
                result = await self.control_monitor.test_control(control_id)
                results[control_id] = result
            except Exception as e:
                logger.error(f"Failed to test security control {control_id}: {str(e)}")
                results[control_id] = ControlResult(
                    control_id=control_id,
                    status=ControlStatus.NOT_TESTED,
                    effectiveness_score=0.0,
                    test_date=datetime.utcnow(),
                    evidence=[],
                    deficiencies=[f"Test failed: {str(e)}"],
                    recommendations=["Retry test with proper configuration"],
                    testing_method="automated",
                    tester="system"
                )

        return results

    async def test_availability_controls(self) -> Dict[str, ControlResult]:
        """Test availability-related SOC2 controls"""
        availability_controls = ["A1.1", "A1.2", "A1.3", "CC7.1", "CC7.2", "CC7.4"]
        results = {}

        for control_id in availability_controls:
            try:
                result = await self.control_monitor.test_control(control_id)
                results[control_id] = result
            except Exception as e:
                logger.error(f"Failed to test availability control {control_id}: {str(e)}")
                results[control_id] = ControlResult(
                    control_id=control_id,
                    status=ControlStatus.NOT_TESTED,
                    effectiveness_score=0.0,
                    test_date=datetime.utcnow(),
                    evidence=[],
                    deficiencies=[f"Test failed: {str(e)}"],
                    recommendations=["Check system availability monitoring"],
                    testing_method="automated",
                    tester="system"
                )

        return results

    async def test_processing_integrity(self) -> Dict[str, ControlResult]:
        """Test processing integrity SOC2 controls"""
        integrity_controls = ["PI1.1", "PI1.2", "PI1.3"]
        results = {}

        for control_id in integrity_controls:
            try:
                result = await self.control_monitor.test_control(control_id)
                results[control_id] = result
            except Exception as e:
                logger.error(f"Failed to test processing integrity control {control_id}: {str(e)}")
                results[control_id] = ControlResult(
                    control_id=control_id,
                    status=ControlStatus.NOT_TESTED,
                    effectiveness_score=0.0,
                    test_date=datetime.utcnow(),
                    evidence=[],
                    deficiencies=[f"Test failed: {str(e)}"],
                    recommendations=["Validate data processing integrity"],
                    testing_method="automated",
                    tester="system"
                )

        return results

    async def test_access_controls(self) -> Dict[str, ControlResult]:
        """Test access control SOC2 controls"""
        access_controls = ["CC6.1", "CC6.2", "CC6.3", "CC6.6", "CC6.7", "CC6.8"]
        results = {}

        for control_id in access_controls:
            try:
                result = await self.control_monitor.test_control(control_id)
                results[control_id] = result
            except Exception as e:
                logger.error(f"Failed to test access control {control_id}: {str(e)}")
                results[control_id] = ControlResult(
                    control_id=control_id,
                    status=ControlStatus.NOT_TESTED,
                    effectiveness_score=0.0,
                    test_date=datetime.utcnow(),
                    evidence=[],
                    deficiencies=[f"Test failed: {str(e)}"],
                    recommendations=["Review access control implementation"],
                    testing_method="automated",
                    tester="system"
                )

        return results

    async def collect_daily_evidence(self) -> List[ComplianceEvidence]:
        """Collect daily compliance evidence"""
        try:
            evidence_list = []

            # Collect system-generated evidence
            system_evidence = await self.evidence_collector.collect_system_evidence()
            evidence_list.extend(system_evidence)

            # Collect security logs
            security_evidence = await self.evidence_collector.collect_security_logs()
            evidence_list.extend(security_evidence)

            # Collect access logs
            access_evidence = await self.evidence_collector.collect_access_logs()
            evidence_list.extend(access_evidence)

            return evidence_list

        except Exception as e:
            logger.error(f"Failed to collect daily evidence: {str(e)}")
            return []

    async def generate_compliance_summary(self, monitoring_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate compliance monitoring summary"""
        try:
            total_controls = 0
            effective_controls = 0

            for category, controls in monitoring_results.get("controls_tested", {}).items():
                for control_id, result in controls.items():
                    total_controls += 1
                    if isinstance(result, ControlResult) and result.status == ControlStatus.EFFECTIVE:
                        effective_controls += 1

            effectiveness_percentage = (effective_controls / total_controls * 100) if total_controls > 0 else 0

            summary = {
                "total_controls_tested": total_controls,
                "effective_controls": effective_controls,
                "effectiveness_percentage": round(effectiveness_percentage, 2),
                "evidence_items_collected": len(monitoring_results.get("evidence_collected", [])),
                "exceptions_count": len(monitoring_results.get("exceptions_identified", [])),
                "monitoring_status": "completed",
                "next_monitoring": (datetime.utcnow() + timedelta(days=1)).isoformat()
            }

            return summary

        except Exception as e:
            logger.error(f"Failed to generate compliance summary: {str(e)}")
            return {"error": str(e)}

    async def get_compliance_status(self) -> Dict[str, Any]:
        """Get current compliance status overview"""
        try:
            status = {
                "timestamp": datetime.utcnow().isoformat(),
                "soc2_controls": {},
                "overall_effectiveness": 0.0,
                "last_monitoring": None,
                "pending_reviews": 0
            }

            # Get latest control results
            for control_id in self.soc2_controls.keys():
                # This would typically query a database for latest results
                status["soc2_controls"][control_id] = {
                    "description": self.soc2_controls[control_id],
                    "status": "not_tested",
                    "last_test_date": None,
                    "effectiveness_score": 0.0
                }

            return status

        except Exception as e:
            logger.error(f"Failed to get compliance status: {str(e)}")
            return {"error": str(e)}

    def get_control_description(self, control_id: str) -> str:
        """Get description for a SOC2 control"""
        return self.soc2_controls.get(control_id, f"Unknown control: {control_id}")

    async def schedule_control_test(self, control_id: str, test_date: datetime) -> bool:
        """Schedule a control test for a specific date"""
        try:
            if self.redis_client:
                schedule_key = f"compliance:scheduled_tests:{control_id}"
                await self.redis_client.setex(schedule_key, 86400 * 30, test_date.isoformat())  # 30 days TTL

            logger.info(f"Scheduled control test for {control_id} on {test_date}")
            return True

        except Exception as e:
            logger.error(f"Failed to schedule control test: {str(e)}")
            return False