"""
Privacy Data Models
Data structures for privacy impact assessments and data subject request responses.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any

from app.models.compliance import DataCategory, LegalBasis


@dataclass
class DataSubjectRequestResponse:
    """Response to a data subject request"""

    request_id: str
    response_type: str
    data: Optional[Dict[str, Any]]
    export_url: Optional[str]
    completion_time: datetime
    notes: Optional[str]


@dataclass
class PrivacyImpactAssessment:
    """Privacy Impact Assessment (PIA) for GDPR compliance"""

    pia_id: str
    title: str
    description: str
    project_name: str
    data_processing_purpose: str

    # Data categories and processing
    data_categories: List[DataCategory]
    processing_activities: List[str]
    legal_basis: List[LegalBasis]
    data_subjects: List[str]

    # Risk assessment
    privacy_risks: List[Dict[str, Any]]
    risk_level: str  # low, medium, high, very_high
    mitigation_measures: List[str]

    # Consultation and approval
    stakeholder_consultation: bool
    dpo_consultation: bool
    approved_by: Optional[str]
    approval_date: Optional[datetime]

    # Review and monitoring
    review_date: datetime
    monitoring_measures: List[str]

    created_at: datetime
    updated_at: datetime
