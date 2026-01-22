"""
Compliance Control Status Models and Enums
Pure data structures for compliance monitoring without business logic dependencies.
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any


class ControlStatus(str, Enum):
    """SOC2 control effectiveness status"""

    EFFECTIVE = "effective"
    INEFFECTIVE = "ineffective"
    NEEDS_IMPROVEMENT = "needs_improvement"
    NOT_TESTED = "not_tested"
    EXCEPTION = "exception"


class EvidenceType(str, Enum):
    """Types of compliance evidence"""

    SYSTEM_GENERATED = "system_generated"
    MANUAL_REVIEW = "manual_review"
    DOCUMENTATION = "documentation"
    SCREENSHOT = "screenshot"
    INTERVIEW = "interview"
    OBSERVATION = "observation"


@dataclass
class ControlResult:
    """Result of a compliance control test"""

    control_id: str
    status: ControlStatus
    effectiveness_score: float
    test_date: datetime
    evidence: List[str]
    deficiencies: List[str]
    recommendations: List[str]
    testing_method: str
    tester: str
    next_test_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ComplianceEvidence:
    """Compliance evidence record"""

    evidence_id: str
    control_id: str
    evidence_type: EvidenceType
    description: str
    collection_date: datetime
    collector: str
    file_path: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    validation_status: str = "pending"
    retention_date: Optional[datetime] = None
