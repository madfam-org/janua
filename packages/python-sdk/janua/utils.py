"""
Utility functions for the Janua Python SDK.

This module provides utility functions for token validation, webhook verification,
and other common operations.
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs, ParseResult

import jwt
from jwt import PyJWTError

from .exceptions import InvalidTokenError, TokenExpiredError, WebhookVerificationError


def validate_webhook_signature(
    payload: Union[str, bytes, Dict[str, Any]],
    signature: str,
    secret: str,
    timestamp: Optional[int] = None,
    tolerance: int = 300,
) -> bool:
    """
    Validate a webhook signature.

    Args:
        payload: The webhook payload
        signature: The signature from the webhook header
        secret: The webhook secret
        timestamp: Optional timestamp to prevent replay attacks
        tolerance: Time tolerance in seconds for timestamp validation

    Returns:
        True if the signature is valid

    Raises:
        WebhookVerificationError: If signature validation fails
    """
    # Convert payload to bytes if needed
    if isinstance(payload, dict):
        payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    elif isinstance(payload, str):
        payload_bytes = payload.encode()
    else:
        payload_bytes = payload

    # Validate timestamp if provided
    if timestamp:
        current_time = int(time.time())
        if abs(current_time - timestamp) > tolerance:
            raise WebhookVerificationError(
                "Webhook timestamp is too old",
                details={"timestamp": timestamp, "current_time": current_time}
            )
        
        # Include timestamp in signature calculation
        payload_bytes = f"{timestamp}.".encode() + payload_bytes

    # Calculate expected signature
    expected_signature = hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()

    # Compare signatures (constant-time comparison)
    if not hmac.compare_digest(signature.lower(), expected_signature.lower()):
        raise WebhookVerificationError("Invalid webhook signature")

    return True


def parse_jwt_without_verification(token: str) -> Dict[str, Any]:
    """
    Parse a JWT without verification (for extracting claims).

    WARNING: This does not verify the token and should only be used
    for extracting claims when verification is handled elsewhere.

    Args:
        token: JWT token string

    Returns:
        Dictionary of token claims

    Raises:
        InvalidTokenError: If the token format is invalid
    """
    try:
        # Decode without verification
        claims = jwt.decode(token, options={"verify_signature": False})
        return claims
    except PyJWTError as e:
        raise InvalidTokenError(f"Invalid token format: {str(e)}")


def is_token_expired(token: str, leeway: int = 0) -> bool:
    """
    Check if a JWT token is expired.

    Args:
        token: JWT token string
        leeway: Number of seconds of leeway for expiration

    Returns:
        True if the token is expired
    """
    try:
        claims = parse_jwt_without_verification(token)
        exp = claims.get("exp")
        
        if not exp:
            return False
        
        current_time = time.time()
        return current_time > (exp + leeway)
    except InvalidTokenError:
        # If we can't parse the token, consider it expired
        return True


class TokenValidator:
    """JWT token validator with caching and verification."""

    def __init__(
        self,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        algorithms: Optional[list] = None,
        public_key: Optional[str] = None,
        secret: Optional[str] = None,
    ):
        """
        Initialize the token validator.

        Args:
            issuer: Expected token issuer
            audience: Expected token audience
            algorithms: Allowed signing algorithms
            public_key: Public key for RS256 verification
            secret: Secret for HS256 verification
        """
        self.issuer = issuer
        self.audience = audience
        self.algorithms = algorithms or ["RS256", "HS256"]
        self.public_key = public_key
        self.secret = secret

    def validate(self, token: str, leeway: int = 0) -> Dict[str, Any]:
        """
        Validate and decode a JWT token.

        Args:
            token: JWT token string
            leeway: Number of seconds of leeway for expiration

        Returns:
            Dictionary of token claims

        Raises:
            InvalidTokenError: If validation fails
            TokenExpiredError: If the token is expired
        """
        # Determine the verification key
        if self.public_key:
            key = self.public_key
        elif self.secret:
            key = self.secret
        else:
            raise InvalidTokenError("No verification key configured")

        try:
            # Decode and verify the token
            claims = jwt.decode(
                token,
                key,
                algorithms=self.algorithms,
                issuer=self.issuer,
                audience=self.audience,
                leeway=leeway,
            )
            return claims
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(f"Token validation failed: {str(e)}")


def encode_base64url(data: bytes) -> str:
    """
    Encode bytes to base64url format.

    Args:
        data: Bytes to encode

    Returns:
        Base64url encoded string
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def decode_base64url(data: str) -> bytes:
    """
    Decode base64url string to bytes.

    Args:
        data: Base64url encoded string

    Returns:
        Decoded bytes
    """
    # Add padding if necessary
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += "=" * padding
    
    return base64.urlsafe_b64decode(data)


def generate_code_challenge(code_verifier: str) -> str:
    """
    Generate a PKCE code challenge from a code verifier.

    Args:
        code_verifier: The code verifier string

    Returns:
        Code challenge for PKCE flow
    """
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return encode_base64url(digest)


def generate_state(length: int = 32) -> str:
    """
    Generate a random state parameter for OAuth flows.

    Args:
        length: Length of the state parameter

    Returns:
        Random state string
    """
    import secrets
    return secrets.token_urlsafe(length)


def build_url(base_url: str, path: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> str:
    """
    Build a URL with optional path and query parameters.

    Args:
        base_url: Base URL
        path: Optional path to append
        params: Optional query parameters

    Returns:
        Complete URL string
    """
    parsed = urlparse(base_url)
    
    # Add path if provided
    if path:
        # Ensure path starts with /
        if not path.startswith("/"):
            path = "/" + path
        # Combine with existing path
        if parsed.path and not parsed.path.endswith("/"):
            full_path = parsed.path + path
        else:
            full_path = (parsed.path or "") + path
    else:
        full_path = parsed.path

    # Add query parameters
    query = parsed.query
    if params:
        # Parse existing query parameters
        existing_params = parse_qs(query)
        # Add new parameters
        for key, value in params.items():
            if value is not None:
                existing_params[key] = [str(value)]
        # Rebuild query string
        query = urlencode(existing_params, doseq=True)

    # Rebuild URL
    return urlunparse(ParseResult(
        scheme=parsed.scheme,
        netloc=parsed.netloc,
        path=full_path,
        params=parsed.params,
        query=query,
        fragment=parsed.fragment,
    ))


def parse_iso_datetime(date_string: str) -> datetime:
    """
    Parse an ISO 8601 datetime string.

    Args:
        date_string: ISO 8601 formatted datetime string

    Returns:
        Datetime object
    """
    # Handle various ISO 8601 formats
    if date_string.endswith("Z"):
        date_string = date_string[:-1] + "+00:00"
    
    try:
        # Try parsing with timezone
        return datetime.fromisoformat(date_string)
    except ValueError:
        # Try without timezone
        try:
            dt = datetime.fromisoformat(date_string)
            # Assume UTC if no timezone
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            # Last resort: manual parsing
            import re
            match = re.match(
                r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?",
                date_string
            )
            if match:
                year, month, day, hour, minute, second, microsecond = match.groups()
                microsecond = int(microsecond.ljust(6, "0")[:6]) if microsecond else 0
                return datetime(
                    int(year), int(month), int(day),
                    int(hour), int(minute), int(second),
                    microsecond, tzinfo=timezone.utc
                )
            raise ValueError(f"Cannot parse datetime: {date_string}")


def format_iso_datetime(dt: datetime) -> str:
    """
    Format a datetime object as ISO 8601 string.

    Args:
        dt: Datetime object

    Returns:
        ISO 8601 formatted string
    """
    # Ensure timezone aware
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return dt.isoformat()


def get_expires_at(expires_in: int) -> datetime:
    """
    Calculate expiration datetime from seconds.

    Args:
        expires_in: Number of seconds until expiration

    Returns:
        Expiration datetime
    """
    return datetime.now(timezone.utc) + timedelta(seconds=expires_in)


def is_expired(expires_at: datetime, buffer_seconds: int = 60) -> bool:
    """
    Check if a datetime has expired with optional buffer.

    Args:
        expires_at: Expiration datetime
        buffer_seconds: Buffer time in seconds before actual expiration

    Returns:
        True if expired (or will expire within buffer)
    """
    # Ensure timezone aware
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    buffer = timedelta(seconds=buffer_seconds)
    return datetime.now(timezone.utc) + buffer >= expires_at


def sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Sanitize headers by removing sensitive information.

    Args:
        headers: Dictionary of headers

    Returns:
        Sanitized headers dictionary
    """
    sensitive_headers = {
        "authorization",
        "x-api-key",
        "x-auth-token",
        "cookie",
        "set-cookie",
    }
    
    sanitized = {}
    for key, value in headers.items():
        if key.lower() in sensitive_headers:
            sanitized[key] = "***REDACTED***"
        else:
            sanitized[key] = value
    
    return sanitized


def retry_with_backoff(
    func,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
):
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Add randomness to delays

    Returns:
        Function result

    Raises:
        Last exception if all attempts fail
    """
    import random
    
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            last_exception = e
            
            if attempt < max_attempts - 1:
                # Calculate next delay
                if jitter:
                    actual_delay = delay * (0.5 + random.random())
                else:
                    actual_delay = delay
                
                time.sleep(min(actual_delay, max_delay))
                delay *= exponential_base

    if last_exception is not None:
        raise last_exception
    raise RuntimeError(f"Function failed after {max_attempts} attempts")


def validate_email(email: str) -> bool:
    """
    Basic email validation.

    Args:
        email: Email address to validate

    Returns:
        True if email format is valid
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password_strength(
    password: str,
    min_length: int = 8,
    require_uppercase: bool = True,
    require_lowercase: bool = True,
    require_numbers: bool = True,
    require_special: bool = False,
) -> tuple[bool, list[str]]:
    """
    Validate password strength.

    Args:
        password: Password to validate
        min_length: Minimum password length
        require_uppercase: Require uppercase letters
        require_lowercase: Require lowercase letters
        require_numbers: Require numbers
        require_special: Require special characters

    Returns:
        Tuple of (is_valid, list of unmet requirements)
    """
    errors = []
    
    if len(password) < min_length:
        errors.append(f"Password must be at least {min_length} characters long")
    
    if require_uppercase and not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")
    
    if require_lowercase and not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")
    
    if require_numbers and not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one number")
    
    if require_special:
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        if not any(c in special_chars for c in password):
            errors.append("Password must contain at least one special character")
    
    return len(errors) == 0, errors