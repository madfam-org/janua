"""
Privacy Types and Enums
Pure enums and type definitions for the privacy compliance system.
"""

from enum import Enum


class PrivacyRightType(str, Enum):
    """GDPR privacy rights under Articles 15-22"""

    ACCESS = "access"  # Article 15 - Right of access
    RECTIFICATION = "rectification"  # Article 16 - Right to rectification
    ERASURE = "erasure"  # Article 17 - Right to be forgotten
    PORTABILITY = "portability"  # Article 20 - Right to data portability
    RESTRICTION = "restriction"  # Article 18 - Right to restriction
    OBJECTION = "objection"  # Article 21 - Right to object
    AUTOMATED_DECISION = "automated_decision"  # Article 22 - Automated decision-making


class DataExportFormat(str, Enum):
    """Supported formats for data export"""

    JSON = "json"
    CSV = "csv"
    XML = "xml"
    PDF = "pdf"


class RetentionAction(str, Enum):
    """Actions to take when retention period expires"""

    DELETE = "delete"
    ANONYMIZE = "anonymize"
    ARCHIVE = "archive"
    REVIEW = "review"
