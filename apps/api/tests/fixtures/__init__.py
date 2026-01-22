"""
Test Fixtures Package
Created: January 13, 2025

This package contains reusable pytest fixtures for integration testing.

Available Fixtures:
- users.py: User model fixtures (test_user, test_admin, etc.)
- organizations.py: Organization model fixtures
- sessions.py: Session model fixtures
- external_mocks.py: External service mocks (db, redis, slack, etc.)

Usage in conftest.py:
    from tests.fixtures.users import *
    from tests.fixtures.organizations import *
    from tests.fixtures.sessions import *
    from tests.fixtures.external_mocks import *
"""

# Export commonly used test constants
TEST_PASSWORD = "TestPassword123!"

# Re-export external mock fixtures for pytest discovery
from tests.fixtures.external_mocks import (
    mock_db_session,
    mock_redis_client,
    mock_email_service,
    mock_webhook_service,
    mock_slack_client,
    sample_user_data,
    sample_organization_data,
    sample_alert_data,
    sample_compliance_data,
)

__all__ = [
    "TEST_PASSWORD",
    "mock_db_session",
    "mock_redis_client",
    "mock_email_service",
    "mock_webhook_service",
    "mock_slack_client",
    "sample_user_data",
    "sample_organization_data",
    "sample_alert_data",
    "sample_compliance_data",
]
