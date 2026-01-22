"""
API versioning and compatibility management for SDK consumption.

Provides version detection, compatibility checking, and graceful handling
of API changes across different client SDK versions.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, date
import re


class APIVersion(str, Enum):
    """Supported API versions."""
    V1 = "v1"
    V2 = "v2"  # Future version
    BETA = "beta"
    PREVIEW = "preview"


class CompatibilityLevel(str, Enum):
    """Compatibility levels between API versions."""
    FULLY_COMPATIBLE = "fully_compatible"
    BACKWARD_COMPATIBLE = "backward_compatible"
    BREAKING_CHANGES = "breaking_changes"
    DEPRECATED = "deprecated"
    UNSUPPORTED = "unsupported"


@dataclass
class VersionInfo:
    """Information about a specific API version."""
    version: str
    release_date: date
    deprecation_date: Optional[date] = None
    end_of_life_date: Optional[date] = None
    is_stable: bool = True
    is_preview: bool = False
    supported_features: Optional[Set[str]] = None
    breaking_changes: Optional[List[str]] = None
    migration_notes: Optional[List[str]] = None

    def __post_init__(self):
        if self.supported_features is None:
            self.supported_features = set()
        if self.breaking_changes is None:
            self.breaking_changes = []
        if self.migration_notes is None:
            self.migration_notes = []

    @property
    def is_deprecated(self) -> bool:
        """Check if this version is deprecated."""
        if not self.deprecation_date:
            return False
        return datetime.now().date() >= self.deprecation_date

    @property
    def is_end_of_life(self) -> bool:
        """Check if this version is end-of-life."""
        if not self.end_of_life_date:
            return False
        return datetime.now().date() >= self.end_of_life_date


class APIVersionManager:
    """
    Manages API version compatibility and feature detection.

    This class provides the logic for SDK clients to handle different
    API versions gracefully and provide appropriate warnings or errors.
    """

    def __init__(self):
        self._versions: Dict[str, VersionInfo] = {}
        self._feature_compatibility: Dict[str, Dict[str, bool]] = {}
        self._initialize_version_data()

    def _initialize_version_data(self) -> None:
        """Initialize version information and compatibility matrices."""
        # V1 - Current stable version
        self._versions["v1"] = VersionInfo(
            version="v1",
            release_date=date(2024, 1, 1),
            is_stable=True,
            supported_features={
                "authentication",
                "user_management",
                "organization_management",
                "mfa",
                "passkeys",
                "webhooks",
                "sessions",
                "oauth",
                "admin_operations",
                "audit_logging"
            }
        )

        # V2 - Future version with enhanced features
        self._versions["v2"] = VersionInfo(
            version="v2",
            release_date=date(2024, 6, 1),
            is_stable=False,
            is_preview=True,
            supported_features={
                "authentication",
                "user_management",
                "organization_management",
                "mfa",
                "passkeys",
                "webhooks",
                "sessions",
                "oauth",
                "admin_operations",
                "audit_logging",
                "advanced_analytics",
                "bulk_operations",
                "real_time_notifications",
                "sso_saml",
                "scim_provisioning"
            },
            breaking_changes=[
                "User response format includes additional security fields",
                "Pagination response structure changed",
                "Some endpoint URLs have changed",
                "Error response format enhanced"
            ],
            migration_notes=[
                "Update user model to handle new security fields",
                "Modify pagination handling logic",
                "Update endpoint URLs in API calls",
                "Handle enhanced error response format"
            ]
        )

        # Initialize feature compatibility matrix
        self._feature_compatibility = {
            "v1": {
                "authentication": True,
                "user_management": True,
                "organization_management": True,
                "mfa": True,
                "passkeys": True,
                "webhooks": True,
                "sessions": True,
                "oauth": True,
                "admin_operations": True,
                "audit_logging": True,
                "advanced_analytics": False,
                "bulk_operations": False,
                "real_time_notifications": False,
                "sso_saml": False,
                "scim_provisioning": False
            },
            "v2": {
                "authentication": True,
                "user_management": True,
                "organization_management": True,
                "mfa": True,
                "passkeys": True,
                "webhooks": True,
                "sessions": True,
                "oauth": True,
                "admin_operations": True,
                "audit_logging": True,
                "advanced_analytics": True,
                "bulk_operations": True,
                "real_time_notifications": True,
                "sso_saml": True,
                "scim_provisioning": True
            }
        }

    def get_version_info(self, version: str) -> Optional[VersionInfo]:
        """Get information about a specific API version."""
        return self._versions.get(version)

    def get_latest_stable_version(self) -> str:
        """Get the latest stable API version."""
        stable_versions = [
            (v.version, v.release_date)
            for v in self._versions.values()
            if v.is_stable and not v.is_end_of_life
        ]

        if not stable_versions:
            return "v1"  # Fallback

        # Sort by release date and return the latest
        stable_versions.sort(key=lambda x: x[1], reverse=True)
        return stable_versions[0][0]

    def get_compatibility_level(self, from_version: str, to_version: str) -> CompatibilityLevel:
        """
        Determine compatibility level between two API versions.

        Args:
            from_version: Source version (current SDK version)
            to_version: Target version (API version)

        Returns:
            Compatibility level indicating the safety of the transition
        """
        from_info = self.get_version_info(from_version)
        to_info = self.get_version_info(to_version)

        if not from_info or not to_info:
            return CompatibilityLevel.UNSUPPORTED

        # Same version is fully compatible
        if from_version == to_version:
            return CompatibilityLevel.FULLY_COMPATIBLE

        # Check if either version is end-of-life
        if from_info.is_end_of_life or to_info.is_end_of_life:
            return CompatibilityLevel.UNSUPPORTED

        # Check for breaking changes
        if to_info.breaking_changes:
            return CompatibilityLevel.BREAKING_CHANGES

        # Check deprecation status
        if from_info.is_deprecated:
            return CompatibilityLevel.DEPRECATED

        # Default to backward compatible for minor version differences
        return CompatibilityLevel.BACKWARD_COMPATIBLE

    def check_feature_support(self, version: str, feature: str) -> bool:
        """
        Check if a specific feature is supported in the given API version.

        Args:
            version: API version to check
            feature: Feature name to check

        Returns:
            True if the feature is supported, False otherwise
        """
        version_features = self._feature_compatibility.get(version, {})
        return version_features.get(feature, False)

    def get_missing_features(self, version: str, required_features: List[str]) -> List[str]:
        """
        Get a list of features that are not supported in the given version.

        Args:
            version: API version to check
            required_features: List of required features

        Returns:
            List of unsupported features
        """
        missing = []
        for feature in required_features:
            if not self.check_feature_support(version, feature):
                missing.append(feature)
        return missing

    def get_version_warnings(self, version: str) -> List[str]:
        """
        Get warnings for using a specific API version.

        Returns:
            List of warning messages
        """
        warnings = []
        version_info = self.get_version_info(version)

        if not version_info:
            warnings.append(f"Unknown API version: {version}")
            return warnings

        if version_info.is_end_of_life:
            warnings.append(f"API version {version} is end-of-life and no longer supported")

        elif version_info.is_deprecated:
            warnings.append(f"API version {version} is deprecated")
            if version_info.end_of_life_date:
                warnings.append(f"Version {version} will be end-of-life on {version_info.end_of_life_date}")

        if version_info.is_preview:
            warnings.append(f"API version {version} is in preview and may have breaking changes")

        return warnings

    def recommend_version_upgrade(self, current_version: str) -> Optional[Dict[str, Any]]:
        """
        Recommend a version upgrade if beneficial.

        Args:
            current_version: Current API version being used

        Returns:
            Upgrade recommendation with details, or None if no upgrade needed
        """
        current_info = self.get_version_info(current_version)
        if not current_info:
            return None

        latest_stable = self.get_latest_stable_version()
        latest_info = self.get_version_info(latest_stable)

        # No upgrade needed if already on latest stable
        if current_version == latest_stable:
            return None

        # Recommend upgrade if current version is deprecated or has issues
        should_upgrade = (
            current_info.is_deprecated or
            current_info.is_end_of_life or
            current_info.is_preview
        )

        if not should_upgrade:
            return None

        # Calculate new features available
        current_features = current_info.supported_features
        latest_features = latest_info.supported_features
        new_features = latest_features - current_features

        compatibility = self.get_compatibility_level(current_version, latest_stable)

        return {
            "recommended_version": latest_stable,
            "current_version": current_version,
            "compatibility_level": compatibility.value,
            "new_features": list(new_features),
            "breaking_changes": latest_info.breaking_changes,
            "migration_notes": latest_info.migration_notes,
            "urgency": "high" if current_info.is_end_of_life else "medium" if current_info.is_deprecated else "low"
        }


class VersionMiddleware:
    """
    Middleware for handling API version detection and compatibility.

    This provides request/response processing for version-aware SDK behavior.
    """

    def __init__(self, version_manager: APIVersionManager):
        self.version_manager = version_manager

    def process_request_headers(self, headers: Dict[str, str], sdk_version: str) -> Dict[str, str]:
        """
        Process request headers to include version information.

        Args:
            headers: Original request headers
            sdk_version: SDK version being used

        Returns:
            Updated headers with version information
        """
        updated_headers = headers.copy()

        # Add SDK version header
        updated_headers["X-SDK-Version"] = sdk_version

        # Add client capabilities header
        updated_headers["X-Client-Capabilities"] = "pagination,bulk_operations,real_time"

        # Add API version preference
        if "Accept" not in updated_headers:
            updated_headers["Accept"] = "application/json"

        return updated_headers

    def process_response_headers(self, response_headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract version information from response headers.

        Args:
            response_headers: Response headers from API

        Returns:
            Extracted version information
        """
        info = {}

        # Extract API version
        api_version = response_headers.get("X-API-Version")
        if api_version:
            info["api_version"] = api_version
            info["version_info"] = self.version_manager.get_version_info(api_version)

        # Extract deprecation warnings
        deprecation_warning = response_headers.get("X-API-Deprecation-Warning")
        if deprecation_warning:
            info["deprecation_warning"] = deprecation_warning

        # Extract rate limiting info
        rate_limit_remaining = response_headers.get("X-RateLimit-Remaining")
        if rate_limit_remaining:
            info["rate_limit_remaining"] = int(rate_limit_remaining)

        return info

    def check_version_compatibility(self, sdk_version: str, api_version: str) -> Dict[str, Any]:
        """
        Check compatibility between SDK version and API version.

        Args:
            sdk_version: Version of the SDK being used
            api_version: Version of the API being accessed

        Returns:
            Compatibility analysis results
        """
        # Parse SDK version to extract API version expectation
        # SDK versions might be like "janua-python-1.2.3-api-v1"
        expected_api_version = self._extract_api_version_from_sdk(sdk_version)

        compatibility = self.version_manager.get_compatibility_level(
            expected_api_version, api_version
        )

        warnings = self.version_manager.get_version_warnings(api_version)

        upgrade_recommendation = self.version_manager.recommend_version_upgrade(
            expected_api_version
        )

        return {
            "compatible": compatibility != CompatibilityLevel.UNSUPPORTED,
            "compatibility_level": compatibility.value,
            "warnings": warnings,
            "upgrade_recommendation": upgrade_recommendation,
            "expected_api_version": expected_api_version,
            "actual_api_version": api_version
        }

    def _extract_api_version_from_sdk(self, sdk_version: str) -> str:
        """
        Extract expected API version from SDK version string.

        Args:
            sdk_version: Full SDK version string

        Returns:
            Expected API version (defaults to v1)
        """
        # Try to extract API version from SDK version string
        # Patterns: "1.2.3-api-v1", "janua-python-1.2.3-v1", "v1.2.3"
        patterns = [
            r"-api-(v\d+)",
            r"-(v\d+)$",
            r"^(v\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, sdk_version, re.IGNORECASE)
            if match:
                return match.group(1).lower()

        # Default to v1 if no version found
        return "v1"


# Utility functions for SDK implementations
def create_version_manager() -> APIVersionManager:
    """Create a pre-configured version manager."""
    return APIVersionManager()


def create_version_middleware(version_manager: Optional[APIVersionManager] = None) -> VersionMiddleware:
    """Create version middleware with optional custom version manager."""
    if version_manager is None:
        version_manager = create_version_manager()
    return VersionMiddleware(version_manager)


def parse_sdk_version(version_string: str) -> Dict[str, str]:
    """
    Parse SDK version string into components.

    Args:
        version_string: SDK version string (e.g., "janua-python-1.2.3-api-v1")

    Returns:
        Parsed version components
    """
    # Pattern: platform-language-version-api-version
    pattern = r"(?:janua-)?(\w+)-(\d+\.\d+\.\d+)(?:-api-)?(v\d+)?"
    match = re.match(pattern, version_string, re.IGNORECASE)

    if match:
        language, version, api_version = match.groups()
        return {
            "language": language,
            "version": version,
            "api_version": api_version or "v1",
            "full_version": version_string
        }

    # Fallback parsing
    return {
        "language": "unknown",
        "version": "unknown",
        "api_version": "v1",
        "full_version": version_string
    }