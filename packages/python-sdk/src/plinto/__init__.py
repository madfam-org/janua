"""
Plinto Python SDK
Official Python SDK for Plinto - Modern authentication and user management platform
"""

from .client import PlintoClient
from .auth import AuthClient
from .users import UserClient
from .organizations import OrganizationClient
from .types import (
    User,
    Session,
    AuthTokens,
    SignUpRequest,
    SignInRequest,
    SignInResponse,
    SignUpResponse,
    UpdateUserRequest,
    OrganizationInfo,
    OrganizationMembership,
    PlintoError,
)
from .exceptions import (
    PlintoAPIError,
    AuthenticationError,
    ValidationError,
    NotFoundError,
    RateLimitError,
)

__version__ = "0.1.0"

__all__ = [
    "PlintoClient",
    "AuthClient",
    "UserClient",
    "OrganizationClient",
    "User",
    "Session",
    "AuthTokens",
    "SignUpRequest",
    "SignInRequest",
    "SignInResponse",
    "SignUpResponse",
    "UpdateUserRequest",
    "OrganizationInfo",
    "OrganizationMembership",
    "PlintoError",
    "PlintoAPIError",
    "AuthenticationError",
    "ValidationError",
    "NotFoundError",
    "RateLimitError",
]