"""
Enterprise License Management for Janua Python SDK
This module handles license validation and feature gating for enterprise features
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum
import requests


class Plan(Enum):
    """Available pricing plans"""
    COMMUNITY = "community"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Features:
    """Feature flags for different plans"""
    # Community features (always available)
    BASIC_AUTH = "basic_auth"
    USER_MANAGEMENT = "user_management"
    MFA = "mfa"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"
    BASIC_ORGANIZATIONS = "basic_organizations"
    BASIC_WEBHOOKS = "basic_webhooks"

    # Pro features
    ADVANCED_MFA = "advanced_mfa"
    TEAM_MANAGEMENT = "team_management"
    API_KEYS = "api_keys"
    CUSTOM_DOMAINS = "custom_domains"
    PRIORITY_SUPPORT = "priority_support"
    ANALYTICS = "analytics"

    # Enterprise features
    SSO_SAML = "sso_saml"
    SSO_OIDC = "sso_oidc"
    AUDIT_LOGS = "audit_logs"
    CUSTOM_ROLES = "custom_roles"
    WHITE_LABELING = "white_labeling"
    ON_PREMISE = "on_premise"
    COMPLIANCE_REPORTS = "compliance_reports"
    ADVANCED_SECURITY = "advanced_security"
    DEDICATED_SUPPORT = "dedicated_support"
    SLA = "sla"
    CUSTOM_INTEGRATIONS = "custom_integrations"


class LicenseInfo:
    """License information"""
    def __init__(self, data: Dict[str, Any]):
        self.valid = data.get('valid', False)
        self.plan = Plan(data.get('plan', 'community'))
        self.features = data.get('features', [])
        self.organization_id = data.get('organization_id')
        self.expires_at = None
        if data.get('expires_at'):
            self.expires_at = datetime.fromisoformat(data['expires_at'])
        self.seats = data.get('seats')
        self.custom_limits = data.get('custom_limits', {})

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'valid': self.valid,
            'plan': self.plan.value,
            'features': self.features,
            'organization_id': self.organization_id,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'seats': self.seats,
            'custom_limits': self.custom_limits
        }


class EnterpriseError(Exception):
    """Enterprise-specific error"""
    def __init__(self, message: str, code: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class EnterpriseFeatures:
    """Enterprise feature management"""

    # Plan definitions
    PLANS = {
        'community': {
            'name': 'Community',
            'features': [
                Features.BASIC_AUTH,
                Features.USER_MANAGEMENT,
                Features.MFA,
                Features.PASSWORD_RESET,
                Features.EMAIL_VERIFICATION,
                Features.BASIC_ORGANIZATIONS,
                Features.BASIC_WEBHOOKS
            ],
            'limits': {
                'users': 100,
                'organizations': 1,
                'api_requests': 1000,
                'webhooks': 5
            }
        },
        'pro': {
            'name': 'Professional',
            'features': [
                Features.BASIC_AUTH,
                Features.USER_MANAGEMENT,
                Features.MFA,
                Features.PASSWORD_RESET,
                Features.EMAIL_VERIFICATION,
                Features.BASIC_ORGANIZATIONS,
                Features.BASIC_WEBHOOKS,
                Features.ADVANCED_MFA,
                Features.TEAM_MANAGEMENT,
                Features.API_KEYS,
                Features.CUSTOM_DOMAINS,
                Features.PRIORITY_SUPPORT,
                Features.ANALYTICS
            ],
            'limits': {
                'users': 10000,
                'organizations': 10,
                'api_requests': 10000,
                'webhooks': 50
            }
        },
        'enterprise': {
            'name': 'Enterprise',
            'features': [
                Features.BASIC_AUTH,
                Features.USER_MANAGEMENT,
                Features.MFA,
                Features.PASSWORD_RESET,
                Features.EMAIL_VERIFICATION,
                Features.BASIC_ORGANIZATIONS,
                Features.BASIC_WEBHOOKS,
                Features.ADVANCED_MFA,
                Features.TEAM_MANAGEMENT,
                Features.API_KEYS,
                Features.CUSTOM_DOMAINS,
                Features.PRIORITY_SUPPORT,
                Features.ANALYTICS,
                Features.SSO_SAML,
                Features.SSO_OIDC,
                Features.AUDIT_LOGS,
                Features.CUSTOM_ROLES,
                Features.WHITE_LABELING,
                Features.ON_PREMISE,
                Features.COMPLIANCE_REPORTS,
                Features.ADVANCED_SECURITY,
                Features.DEDICATED_SUPPORT,
                Features.SLA,
                Features.CUSTOM_INTEGRATIONS
            ],
            'limits': {
                'users': -1,  # unlimited
                'organizations': -1,
                'api_requests': -1,
                'webhooks': -1
            }
        }
    }

    def __init__(
        self,
        license_key: Optional[str] = None,
        api_url: str = 'https://api.janua.dev',
        cache_timeout: int = 3600
    ):
        self.license_key = license_key
        self.api_url = api_url
        self.cache_timeout = cache_timeout  # seconds
        self._license_cache: Optional[LicenseInfo] = None
        self._cache_expiry: Optional[datetime] = None

    def set_license_key(self, key: str) -> None:
        """Set or update the license key"""
        self.license_key = key
        self.clear_cache()

    def clear_cache(self) -> None:
        """Clear the license cache"""
        self._license_cache = None
        self._cache_expiry = None

    async def validate_license(self) -> LicenseInfo:
        """Validate the current license key"""
        # Return cached license if still valid
        if self._license_cache and self._cache_expiry and datetime.now() < self._cache_expiry:
            return self._license_cache

        if not self.license_key:
            return self._get_community_license()

        try:
            response = requests.post(
                f"{self.api_url}/v1/license/validate",
                json={
                    'key': self.license_key,
                    'sdk': 'janua-python',
                    'version': '1.0.0'
                },
                headers={
                    'Content-Type': 'application/json',
                    'X-License-Key': self.license_key
                },
                timeout=10
            )

            if response.status_code == 402:
                raise EnterpriseError('License expired or invalid', 'LICENSE_EXPIRED')
            elif not response.ok:
                raise EnterpriseError('License validation failed', 'LICENSE_INVALID')

            data = response.json()
            self._license_cache = LicenseInfo(data)
            self._cache_expiry = datetime.now() + timedelta(seconds=self.cache_timeout)
            return self._license_cache

        except requests.RequestException as e:
            # Fallback to community if can't validate
            print(f"License validation failed, falling back to community features: {e}")
            return self._get_community_license()

    def validate_license_sync(self) -> LicenseInfo:
        """Synchronous version of validate_license"""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.validate_license())
        finally:
            loop.close()

    async def has_feature(self, feature: str) -> bool:
        """Check if a specific feature is available"""
        license_info = await self.validate_license()
        return feature in license_info.features

    def has_feature_sync(self, feature: str) -> bool:
        """Synchronous version of has_feature"""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.has_feature(feature))
        finally:
            loop.close()

    async def require_enterprise(self, feature: str) -> None:
        """Require enterprise license for a feature"""
        license_info = await self.validate_license()

        if license_info.plan == Plan.COMMUNITY:
            raise EnterpriseError(
                f"{feature} requires an enterprise license. "
                f"Visit https://janua.dev/pricing or contact sales@janua.dev",
                'ENTERPRISE_REQUIRED',
                {'feature': feature, 'upgrade_url': 'https://janua.dev/pricing'}
            )

        if feature not in license_info.features:
            raise EnterpriseError(
                f"Your {license_info.plan.value} plan doesn't include {feature}. "
                f"Please upgrade your plan.",
                'FEATURE_NOT_AVAILABLE',
                {
                    'feature': feature,
                    'current_plan': license_info.plan.value,
                    'upgrade_url': 'https://janua.dev/pricing'
                }
            )

    def require_enterprise_sync(self, feature: str) -> None:
        """Synchronous version of require_enterprise"""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.require_enterprise(feature))
        finally:
            loop.close()

    def _get_community_license(self) -> LicenseInfo:
        """Get community license (default for open source)"""
        return LicenseInfo({
            'valid': True,
            'plan': 'community',
            'features': self.PLANS['community']['features']
        })

    async def check_rate_limit(self, operation: str) -> Dict[str, Any]:
        """Check rate limits for current plan"""
        license_info = await self.validate_license()

        limits = {
            Plan.COMMUNITY: {'requests': 1000, 'per': 'hour'},
            Plan.PRO: {'requests': 10000, 'per': 'hour'},
            Plan.ENTERPRISE: {'requests': -1, 'per': 'hour'}  # unlimited
        }

        plan_limits = limits[license_info.plan]

        # For enterprise with custom limits
        if license_info.custom_limits and operation in license_info.custom_limits:
            plan_limits['requests'] = license_info.custom_limits[operation]

        # This would typically check against a rate limiting service
        # For now, return mock data
        return {
            'allowed': True,
            'limit': plan_limits['requests'],
            'remaining': plan_limits['requests'],
            'reset_at': datetime.now() + timedelta(hours=1)
        }

    def check_rate_limit_sync(self, operation: str) -> Dict[str, Any]:
        """Synchronous version of check_rate_limit"""
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.check_rate_limit(operation))
        finally:
            loop.close()


def require_license(feature: str):
    """Decorator to require enterprise license for a method"""
    def decorator(func):
        async def async_wrapper(self, *args, **kwargs):
            if hasattr(self, '_enterprise'):
                await self._enterprise.require_enterprise(feature)
            return await func(self, *args, **kwargs)

        def sync_wrapper(self, *args, **kwargs):
            if hasattr(self, '_enterprise'):
                self._enterprise.require_enterprise_sync(feature)
            return func(self, *args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator