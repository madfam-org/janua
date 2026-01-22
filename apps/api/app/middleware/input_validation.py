"""
Comprehensive Input Validation Middleware
Enterprise-grade validation for all API inputs with security focus
"""

import re
import json
import bleach
from typing import Any, Dict, List, Optional, Set
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from email_validator import validate_email, EmailNotValidError
import phonenumbers
from datetime import datetime
import ipaddress
import urllib.parse
import logging

logger = logging.getLogger(__name__)


class ValidationRules:
    """Centralized validation rules and patterns"""

    # Security patterns to detect malicious input
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE)\b)",
        r"(--|#|\/\*|\*\/)",
        r"(\bOR\b\s*\d+\s*=\s*\d+)",
        r"(\bAND\b\s*\d+\s*=\s*\d+)",
        r"(';|\";\s*--)",
        r"(\bEXEC\b|\bEXECUTE\b)",
        r"(xp_cmdshell|sp_executesql)",
    ]

    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
        r"<embed[^>]*>",
        r"<object[^>]*>",
        r"eval\s*\(",
        r"expression\s*\(",
    ]

    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\\.\\\\",
        r"%2e%2e/",
        r"\.\.%2f",
        r"\.\./\.\./",
        r"\/etc\/passwd",
        r"C:\\\\Windows",
    ]

    COMMAND_INJECTION_PATTERNS = [
        r";\s*\w+",
        r"\|\s*\w+",
        r"`[^`]*`",
        r"\$\([^)]*\)",
        r"&&\s*\w+",
        r"\|\|\s*\w+",
    ]

    # Valid formats
    USERNAME_PATTERN = r"^[a-zA-Z0-9_-]{3,30}$"
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_MAX_LENGTH = 128
    PASSWORD_COMPLEXITY = {
        "uppercase": r"[A-Z]",
        "lowercase": r"[a-z]",
        "digit": r"\d",
        "special": r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]",
    }

    # Field size limits
    MAX_EMAIL_LENGTH = 254
    MAX_NAME_LENGTH = 100
    MAX_URL_LENGTH = 2048
    MAX_TEXT_LENGTH = 10000
    MAX_JSON_SIZE = 1048576  # 1MB

    # Rate limit for validation errors per IP
    MAX_VALIDATION_ERRORS_PER_MINUTE = 10


class InputSanitizer:
    """Sanitize and clean user inputs"""

    @staticmethod
    def sanitize_html(text: str) -> str:
        """Remove dangerous HTML tags and attributes"""
        allowed_tags = ["p", "br", "span", "div", "strong", "em", "u", "a"]
        allowed_attributes = {"a": ["href", "title"]}

        return bleach.clean(text, tags=allowed_tags, attributes=allowed_attributes, strip=True)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize file names to prevent directory traversal"""
        # Remove path components
        filename = filename.replace("\\", "/").split("/")[-1]

        # Remove special characters
        filename = re.sub(r"[^a-zA-Z0-9._-]", "", filename)

        # Limit length
        max_length = 255
        if len(filename) > max_length:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = name[: max_length - len(ext) - 1] + "." + ext if ext else name[:max_length]

        return filename

    @staticmethod
    def sanitize_url(url: str) -> Optional[str]:
        """Validate and sanitize URLs"""
        try:
            parsed = urllib.parse.urlparse(url)

            # Only allow http/https
            if parsed.scheme not in ["http", "https"]:
                return None

            # Reconstruct clean URL
            return urllib.parse.urlunparse(parsed)
        except (ValueError, UnicodeError, Exception):
            return None

    @staticmethod
    def sanitize_json(data: Any, max_depth: int = 10) -> Any:
        """Recursively sanitize JSON data"""

        def _sanitize(obj: Any, depth: int = 0) -> Any:
            if depth > max_depth:
                raise ValueError("JSON nesting too deep")

            if isinstance(obj, dict):
                return {
                    InputSanitizer.sanitize_string(k): _sanitize(v, depth + 1)
                    for k, v in obj.items()
                    if k and len(str(k)) < 256  # Limit key length
                }
            elif isinstance(obj, list):
                return [_sanitize(item, depth + 1) for item in obj[:1000]]  # Limit array size
            elif isinstance(obj, str):
                return InputSanitizer.sanitize_string(obj)
            elif isinstance(obj, (int, float, bool, type(None))):
                return obj
            else:
                return str(obj)  # Convert unknown types to string

        return _sanitize(data)

    @staticmethod
    def sanitize_string(text: str, max_length: int = 10000) -> str:
        """Basic string sanitization"""
        if not text:
            return text

        # Truncate to max length
        text = text[:max_length]

        # Remove null bytes
        text = text.replace("\x00", "")

        # Normalize whitespace
        text = " ".join(text.split())

        return text


class InputValidator:
    """Comprehensive input validation logic"""

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email address format and domain"""
        try:
            # Use email-validator library (validates and normalizes)
            validate_email(email, check_deliverability=False)

            # Additional checks
            if len(email) > ValidationRules.MAX_EMAIL_LENGTH:
                return False

            # Check for suspicious patterns
            suspicious_patterns = [
                r".*\+\d{10,}@",  # Excessive plus addressing
                r"^[0-9]+@",  # Numeric-only local part
                r"@.*\d{5,}\.",  # Excessive numbers in domain
            ]

            for pattern in suspicious_patterns:
                if re.match(pattern, email):
                    logger.warning(f"Suspicious email pattern detected: {email}")
                    return False

            return True
        except EmailNotValidError:
            return False

    @staticmethod
    def validate_password(password: str) -> Dict[str, Any]:
        """Validate password strength and complexity"""

        issues = []

        # Length check
        if len(password) < ValidationRules.PASSWORD_MIN_LENGTH:
            issues.append(
                f"Password must be at least {ValidationRules.PASSWORD_MIN_LENGTH} characters"
            )
        if len(password) > ValidationRules.PASSWORD_MAX_LENGTH:
            issues.append(
                f"Password must be at most {ValidationRules.PASSWORD_MAX_LENGTH} characters"
            )

        # Complexity checks
        complexity_met = 0
        for check_name, pattern in ValidationRules.PASSWORD_COMPLEXITY.items():
            if re.search(pattern, password):
                complexity_met += 1

        if complexity_met < 3:
            issues.append(
                "Password must contain at least 3 of: uppercase, lowercase, digit, special character"
            )

        # Common password check (simplified)
        common_passwords = [
            "password",
            "123456",
            "password123",
            "admin",
            "letmein",
            "welcome",
            "monkey",
            "dragon",
            "master",
            "qwerty",
        ]
        if password.lower() in common_passwords:
            issues.append("Password is too common")

        # Sequential character check
        if re.search(r"(012|123|234|345|456|567|678|789|890|abc|bcd|cde|def)", password.lower()):
            issues.append("Password contains sequential characters")

        # Repeated character check
        if re.search(r"(.)\1{3,}", password):
            issues.append("Password contains too many repeated characters")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "strength": "strong"
            if complexity_met == 4
            else "medium"
            if complexity_met >= 3
            else "weak",
        }

    @staticmethod
    def validate_username(username: str) -> bool:
        """Validate username format"""

        if not username or len(username) < 3 or len(username) > 30:
            return False

        return bool(re.match(ValidationRules.USERNAME_PATTERN, username))

    @staticmethod
    def validate_phone_number(phone: str, region: str = "US") -> bool:
        """Validate phone number format"""
        try:
            parsed = phonenumbers.parse(phone, region)
            return phonenumbers.is_valid_number(parsed)
        except phonenumbers.phonenumberutil.NumberParseException:
            return False

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format and safety"""

        if len(url) > ValidationRules.MAX_URL_LENGTH:
            return False

        try:
            parsed = urllib.parse.urlparse(url)

            # Must have scheme and netloc
            if not parsed.scheme or not parsed.netloc:
                return False

            # Only allow safe schemes
            if parsed.scheme not in ["http", "https"]:
                return False

            # Check for IP addresses (could be suspicious)
            try:
                ipaddress.ip_address(parsed.netloc)
                logger.warning(f"URL contains IP address: {url}")
                # Could reject, but for now just log
            except ValueError:
                pass  # Not an IP, which is good

            return True
        except (ValueError, UnicodeError, Exception):
            return False

    @staticmethod
    def validate_date(date_str: str, format: str = "%Y-%m-%d") -> bool:
        """Validate date string format"""
        try:
            datetime.strptime(date_str, format)
            return True
        except ValueError:
            return False

    @staticmethod
    def detect_malicious_patterns(text: str) -> List[str]:
        """Detect potential security threats in input"""

        threats = []

        # Check for SQL injection
        for pattern in ValidationRules.SQL_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                threats.append("sql_injection")
                break

        # Check for XSS
        for pattern in ValidationRules.XSS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                threats.append("xss")
                break

        # Check for path traversal
        for pattern in ValidationRules.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                threats.append("path_traversal")
                break

        # Check for command injection
        for pattern in ValidationRules.COMMAND_INJECTION_PATTERNS:
            if re.search(pattern, text):
                threats.append("command_injection")
                break

        return threats


class ComprehensiveInputValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate and sanitize all incoming requests
    Provides defense-in-depth against injection attacks and malformed input
    """

    def __init__(self, app, strict_mode: bool = True):
        super().__init__(app)
        self.strict_mode = strict_mode
        self.validation_error_tracker: Dict[str, List[datetime]] = {}

    async def dispatch(self, request: Request, call_next):
        """Validate all incoming request data"""

        # Skip validation for health checks and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        try:
            # Check for excessive validation errors (possible attack)
            client_ip = self.get_client_ip(request)
            if self.is_validation_abuse(client_ip):
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": "Too many validation errors"},
                )

            # Validate headers
            validation_result = await self.validate_headers(request)
            if not validation_result["valid"]:
                self.track_validation_error(client_ip)
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Invalid headers", "errors": validation_result["errors"]},
                )

            # Validate and sanitize body for POST/PUT/PATCH
            if request.method in ["POST", "PUT", "PATCH"]:
                validation_result = await self.validate_body(request)
                if not validation_result["valid"]:
                    self.track_validation_error(client_ip)
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "detail": "Invalid request body",
                            "errors": validation_result["errors"],
                        },
                    )

            # Validate query parameters
            validation_result = self.validate_query_params(request)
            if not validation_result["valid"]:
                self.track_validation_error(client_ip)
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "detail": "Invalid query parameters",
                        "errors": validation_result["errors"],
                    },
                )

            # Validate path parameters
            validation_result = self.validate_path_params(request)
            if not validation_result["valid"]:
                self.track_validation_error(client_ip)
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "detail": "Invalid path parameters",
                        "errors": validation_result["errors"],
                    },
                )

            # All validations passed, continue
            response = await call_next(request)
            return response

        except Exception as e:
            logger.error(f"Input validation error: {e}")
            if self.strict_mode:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"detail": "Input validation failed"},
                )
            else:
                # Log but allow request in non-strict mode
                return await call_next(request)

    async def validate_headers(self, request: Request) -> Dict[str, Any]:
        """Validate request headers"""

        errors = []

        # Check for suspicious headers
        suspicious_headers = [
            "X-Forwarded-Host",  # Can be used for cache poisoning
            "X-Original-URL",  # Can bypass security controls
            "X-Rewrite-URL",  # Can bypass security controls
        ]

        for header in suspicious_headers:
            if header in request.headers:
                logger.warning(f"Suspicious header detected: {header}")
                if self.strict_mode:
                    errors.append(f"Suspicious header: {header}")

        # Validate content-type for body requests
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")

            allowed_content_types = [
                "application/json",
                "application/x-www-form-urlencoded",
                "multipart/form-data",
            ]

            if not any(ct in content_type for ct in allowed_content_types):
                errors.append(f"Invalid content-type: {content_type}")

        # Check for header injection
        for header_name, header_value in request.headers.items():
            if "\r" in header_value or "\n" in header_value:
                errors.append(f"Header injection detected in {header_name}")

        return {"valid": len(errors) == 0, "errors": errors}

    async def validate_body(self, request: Request) -> Dict[str, Any]:
        """Validate and sanitize request body"""

        errors = []

        try:
            # Read body
            body = await request.body()

            # Check size
            if len(body) > ValidationRules.MAX_JSON_SIZE:
                errors.append("Request body too large")
                return {"valid": False, "errors": errors}

            # Parse JSON
            if body:
                content_type = request.headers.get("content-type", "")

                if "application/json" in content_type:
                    try:
                        data = json.loads(body)

                        # Sanitize JSON data
                        sanitized = InputSanitizer.sanitize_json(data)

                        # Check for malicious patterns in all string values
                        threats = self.scan_for_threats(sanitized)
                        if threats:
                            errors.append(
                                f"Potential security threats detected: {', '.join(threats)}"
                            )

                        # Store sanitized data for downstream use
                        request.state.sanitized_body = sanitized

                    except json.JSONDecodeError:
                        errors.append("Invalid JSON format")
                    except ValueError as e:
                        errors.append(str(e))

        except Exception as e:
            logger.error(f"Body validation error: {e}")
            errors.append("Failed to validate request body")

        return {"valid": len(errors) == 0, "errors": errors}

    def validate_query_params(self, request: Request) -> Dict[str, Any]:
        """Validate query parameters"""

        errors = []

        for param_name, param_value in request.query_params.items():
            # Check for malicious patterns
            threats = InputValidator.detect_malicious_patterns(param_value)
            if threats:
                errors.append(f"Threats in parameter '{param_name}': {', '.join(threats)}")

            # Validate specific parameter types
            if param_name == "email" and param_value:
                if not InputValidator.validate_email(param_value):
                    errors.append(f"Invalid email in parameter '{param_name}'")

            elif param_name in ["limit", "offset", "page", "size"] and param_value:
                try:
                    val = int(param_value)
                    if val < 0 or val > 10000:
                        errors.append(f"Invalid range for parameter '{param_name}'")
                except ValueError:
                    errors.append(f"Parameter '{param_name}' must be an integer")

        return {"valid": len(errors) == 0, "errors": errors}

    def validate_path_params(self, request: Request) -> Dict[str, Any]:
        """Validate path parameters"""

        errors = []
        path = str(request.url.path)

        # Check for path traversal attempts
        if ".." in path or "//" in path:
            errors.append("Path traversal attempt detected")

        # Check for encoded path traversal
        threats = InputValidator.detect_malicious_patterns(urllib.parse.unquote(path))
        if threats:
            errors.append(f"Threats in path: {', '.join(threats)}")

        return {"valid": len(errors) == 0, "errors": errors}

    def scan_for_threats(self, data: Any) -> Set[str]:
        """Recursively scan data structure for threats"""

        threats = set()

        def _scan(obj: Any):
            if isinstance(obj, str):
                detected = InputValidator.detect_malicious_patterns(obj)
                threats.update(detected)
            elif isinstance(obj, dict):
                for value in obj.values():
                    _scan(value)
            elif isinstance(obj, list):
                for item in obj:
                    _scan(item)

        _scan(data)
        return threats

    def get_client_ip(self, request: Request) -> str:
        """Get client IP address"""

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def is_validation_abuse(self, client_ip: str) -> bool:
        """Check if client is abusing validation errors"""

        now = datetime.utcnow()

        # Clean old entries
        if client_ip in self.validation_error_tracker:
            self.validation_error_tracker[client_ip] = [
                ts for ts in self.validation_error_tracker[client_ip] if (now - ts).seconds < 60
            ]

        # Check rate
        if client_ip in self.validation_error_tracker:
            return (
                len(self.validation_error_tracker[client_ip])
                >= ValidationRules.MAX_VALIDATION_ERRORS_PER_MINUTE
            )

        return False

    def track_validation_error(self, client_ip: str):
        """Track validation error for rate limiting"""

        if client_ip not in self.validation_error_tracker:
            self.validation_error_tracker[client_ip] = []

        self.validation_error_tracker[client_ip].append(datetime.utcnow())


def create_input_validation_middleware(app, strict_mode: bool = True):
    """Factory function to create input validation middleware"""
    return ComprehensiveInputValidationMiddleware(app, strict_mode=strict_mode)
