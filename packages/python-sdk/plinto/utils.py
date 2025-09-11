"""
Utility functions for the Plinto SDK
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import jwt


def validate_webhook_signature(
    payload: str,
    signature: str,
    secret: str,
    timestamp: Optional[str] = None,
    tolerance: int = 300,  # 5 minutes
) -> bool:
    """
    Validate webhook signature from Plinto
    
    Args:
        payload: Raw webhook payload string
        signature: Signature from X-Plinto-Signature header
        secret: Webhook endpoint secret
        timestamp: Timestamp from X-Plinto-Timestamp header
        tolerance: Maximum age of webhook in seconds
        
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Validate timestamp if provided
        if timestamp:
            webhook_time = int(timestamp)
            current_time = int(time.time())
            
            if abs(current_time - webhook_time) > tolerance:
                return False
            
            # Include timestamp in signature verification
            signed_payload = f"{timestamp}.{payload}"
        else:
            signed_payload = payload
        
        # Compute expected signature
        expected_signature = hmac.new(
            secret.encode(),
            signed_payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures (use hmac.compare_digest for timing-safe comparison)
        return hmac.compare_digest(f"sha256={expected_signature}", signature)
        
    except (ValueError, TypeError):
        return False


def parse_jwt_without_verification(token: str) -> Optional[Dict[str, Any]]:
    """
    Parse JWT token without verification (for debugging/inspection)
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload or None if invalid
    """
    try:
        # Split token into parts
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        # Decode payload (add padding if needed)
        payload_part = parts[1]
        padding = 4 - (len(payload_part) % 4)
        if padding != 4:
            payload_part += '=' * padding
        
        payload_bytes = base64.urlsafe_b64decode(payload_part)
        return json.loads(payload_bytes.decode())
        
    except (ValueError, json.JSONDecodeError):
        return None


def is_token_expired(token: str) -> bool:
    """
    Check if JWT token is expired without verification
    
    Args:
        token: JWT token string
        
    Returns:
        True if token is expired, False otherwise
    """
    payload = parse_jwt_without_verification(token)
    if not payload:
        return True
    
    exp = payload.get('exp')
    if not exp:
        return True
    
    return time.time() >= exp


def format_datetime(dt: datetime) -> str:
    """
    Format datetime for API requests
    
    Args:
        dt: Datetime object
        
    Returns:
        ISO formatted datetime string
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def parse_datetime(dt_str: str) -> datetime:
    """
    Parse datetime from API response
    
    Args:
        dt_str: ISO formatted datetime string
        
    Returns:
        Datetime object
    """
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))


def build_query_params(params: Dict[str, Any]) -> Dict[str, str]:
    """
    Build query parameters for API requests
    
    Args:
        params: Dictionary of parameters
        
    Returns:
        Dictionary with string values for query params
    """
    query_params = {}
    
    for key, value in params.items():
        if value is None:
            continue
        elif isinstance(value, bool):
            query_params[key] = str(value).lower()
        elif isinstance(value, (list, tuple)):
            # Convert lists to comma-separated strings
            query_params[key] = ','.join(str(v) for v in value)
        elif isinstance(value, datetime):
            query_params[key] = format_datetime(value)
        else:
            query_params[key] = str(value)
    
    return query_params


def mask_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mask sensitive data for logging
    
    Args:
        data: Dictionary potentially containing sensitive data
        
    Returns:
        Dictionary with sensitive fields masked
    """
    sensitive_fields = {
        'password', 'token', 'secret', 'key', 'authorization',
        'access_token', 'refresh_token', 'api_key', 'webhook_secret'
    }
    
    masked_data = {}
    
    for key, value in data.items():
        lower_key = key.lower()
        
        if any(field in lower_key for field in sensitive_fields):
            if isinstance(value, str) and len(value) > 8:
                masked_data[key] = f"{value[:4]}***{value[-4:]}"
            else:
                masked_data[key] = "***"
        elif isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(value)
        elif isinstance(value, list):
            masked_data[key] = [
                mask_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            masked_data[key] = value
    
    return masked_data


def generate_device_fingerprint() -> str:
    """
    Generate a simple device fingerprint for session tracking
    
    Returns:
        Device fingerprint string
    """
    import platform
    import socket
    
    try:
        # Get basic system info
        system_info = f"{platform.system()}-{platform.release()}-{platform.machine()}"
        hostname = socket.gethostname()
        
        # Create fingerprint
        fingerprint_data = f"{system_info}-{hostname}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]
        
    except Exception:
        # Fallback to random string
        import secrets
        return secrets.token_hex(8)


def validate_email(email: str) -> bool:
    """
    Simple email validation
    
    Args:
        email: Email address to validate
        
    Returns:
        True if email appears valid, False otherwise
    """
    import re
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    import re
    
    # Remove or replace unsafe characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Ensure it's not empty
    if not sanitized:
        sanitized = 'file'
    
    # Limit length
    if len(sanitized) > 255:
        name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
        max_name_length = 255 - len(ext) - 1 if ext else 255
        sanitized = f"{name[:max_name_length]}.{ext}" if ext else name[:255]
    
    return sanitized


def encode_base64url(data: bytes) -> str:
    """
    Encode bytes as base64url (URL-safe base64 without padding)
    
    Args:
        data: Bytes to encode
        
    Returns:
        Base64url encoded string
    """
    return base64.urlsafe_b64encode(data).decode().rstrip('=')


def decode_base64url(data: str) -> bytes:
    """
    Decode base64url string to bytes
    
    Args:
        data: Base64url encoded string
        
    Returns:
        Decoded bytes
    """
    # Add padding if needed
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data += '=' * padding
    
    return base64.urlsafe_b64decode(data)


class TokenValidator:
    """JWT token validator with configurable options"""
    
    def __init__(
        self,
        public_key: Optional[str] = None,
        algorithms: Optional[list] = None,
        verify_signature: bool = True,
        verify_exp: bool = True,
        verify_aud: bool = False,
        verify_iss: bool = False,
    ):
        self.public_key = public_key
        self.algorithms = algorithms or ['HS256', 'RS256']
        self.verify_signature = verify_signature
        self.verify_exp = verify_exp
        self.verify_aud = verify_aud
        self.verify_iss = verify_iss
    
    def validate_token(
        self,
        token: str,
        audience: Optional[str] = None,
        issuer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate JWT token
        
        Args:
            token: JWT token string
            audience: Expected audience
            issuer: Expected issuer
            
        Returns:
            Decoded and validated payload
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        options = {
            'verify_signature': self.verify_signature,
            'verify_exp': self.verify_exp,
            'verify_aud': self.verify_aud,
            'verify_iss': self.verify_iss,
        }
        
        return jwt.decode(
            token,
            self.public_key,
            algorithms=self.algorithms,
            audience=audience,
            issuer=issuer,
            options=options,
        )