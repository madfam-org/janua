"""
Comprehensive Input Validation Middleware Test Suite
Tests for security validation, sanitization, and malicious input detection
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request

from app.middleware.input_validation import (
    ComprehensiveInputValidationMiddleware,
    ValidationRules,
    InputSanitizer,
    InputValidator,
    create_input_validation_middleware,
)

pytestmark = pytest.mark.asyncio


class TestValidationRulesConstants:
    """Test ValidationRules class constants."""

    def test_sql_injection_patterns_exist(self):
        """Test SQL injection patterns are defined."""
        assert len(ValidationRules.SQL_INJECTION_PATTERNS) > 0
        assert any("SELECT" in p for p in ValidationRules.SQL_INJECTION_PATTERNS)
        assert any("DROP" in p for p in ValidationRules.SQL_INJECTION_PATTERNS)

    def test_xss_patterns_exist(self):
        """Test XSS patterns are defined."""
        assert len(ValidationRules.XSS_PATTERNS) > 0
        assert any("script" in p for p in ValidationRules.XSS_PATTERNS)
        assert any("javascript" in p for p in ValidationRules.XSS_PATTERNS)

    def test_path_traversal_patterns_exist(self):
        """Test path traversal patterns are defined."""
        assert len(ValidationRules.PATH_TRAVERSAL_PATTERNS) > 0
        # Patterns use regex escaped .. as \.\./
        assert any("\\." in p or "etc" in p for p in ValidationRules.PATH_TRAVERSAL_PATTERNS)

    def test_command_injection_patterns_exist(self):
        """Test command injection patterns are defined."""
        assert len(ValidationRules.COMMAND_INJECTION_PATTERNS) > 0

    def test_password_complexity_defined(self):
        """Test password complexity rules are defined."""
        assert "uppercase" in ValidationRules.PASSWORD_COMPLEXITY
        assert "lowercase" in ValidationRules.PASSWORD_COMPLEXITY
        assert "digit" in ValidationRules.PASSWORD_COMPLEXITY
        assert "special" in ValidationRules.PASSWORD_COMPLEXITY

    def test_field_size_limits(self):
        """Test field size limits are defined."""
        assert ValidationRules.MAX_EMAIL_LENGTH == 254
        assert ValidationRules.MAX_NAME_LENGTH == 100
        assert ValidationRules.MAX_URL_LENGTH == 2048
        assert ValidationRules.MAX_TEXT_LENGTH == 10000
        assert ValidationRules.MAX_JSON_SIZE == 1048576

    def test_password_length_limits(self):
        """Test password length limits."""
        assert ValidationRules.PASSWORD_MIN_LENGTH == 8
        assert ValidationRules.PASSWORD_MAX_LENGTH == 128


class TestInputSanitizerHTML:
    """Test InputSanitizer HTML sanitization."""

    def test_sanitize_html_removes_script_tags(self):
        """Test script tags are removed."""
        text = "<script>alert('xss')</script>Hello"
        result = InputSanitizer.sanitize_html(text)

        # bleach removes the tags but keeps text content
        assert "<script>" not in result
        assert "</script>" not in result
        assert "Hello" in result

    def test_sanitize_html_allows_safe_tags(self):
        """Test allowed HTML tags are preserved."""
        text = "<p>Paragraph</p><strong>Bold</strong>"
        result = InputSanitizer.sanitize_html(text)

        assert "<p>" in result
        assert "<strong>" in result

    def test_sanitize_html_removes_iframe(self):
        """Test iframe tags are removed."""
        text = "<iframe src='evil.com'></iframe>Content"
        result = InputSanitizer.sanitize_html(text)

        assert "<iframe" not in result
        assert "Content" in result

    def test_sanitize_html_allows_links_with_href(self):
        """Test anchor tags with href are preserved."""
        text = '<a href="https://example.com" title="Example">Link</a>'
        result = InputSanitizer.sanitize_html(text)

        assert "<a" in result
        assert "href" in result


class TestInputSanitizerFilename:
    """Test InputSanitizer filename sanitization."""

    def test_sanitize_filename_removes_path_components(self):
        """Test path components are removed from filename."""
        result = InputSanitizer.sanitize_filename("../../../etc/passwd")

        assert ".." not in result
        assert "/" not in result

    def test_sanitize_filename_removes_special_chars(self):
        """Test special characters are removed."""
        result = InputSanitizer.sanitize_filename("file<>:\"|?*.txt")

        assert "<" not in result
        assert ">" not in result
        assert "?" not in result
        assert "*" not in result

    def test_sanitize_filename_preserves_valid_chars(self):
        """Test valid filename characters are preserved."""
        result = InputSanitizer.sanitize_filename("valid_file-name.txt")

        assert result == "valid_file-name.txt"

    def test_sanitize_filename_truncates_long_names(self):
        """Test long filenames are truncated."""
        long_name = "a" * 300 + ".txt"
        result = InputSanitizer.sanitize_filename(long_name)

        assert len(result) <= 255


class TestInputSanitizerURL:
    """Test InputSanitizer URL sanitization."""

    def test_sanitize_url_accepts_https(self):
        """Test HTTPS URLs are accepted."""
        result = InputSanitizer.sanitize_url("https://example.com/path")

        assert result is not None
        assert "https://" in result

    def test_sanitize_url_accepts_http(self):
        """Test HTTP URLs are accepted."""
        result = InputSanitizer.sanitize_url("http://example.com/path")

        assert result is not None
        assert "http://" in result

    def test_sanitize_url_rejects_javascript(self):
        """Test javascript: URLs are rejected."""
        result = InputSanitizer.sanitize_url("javascript:alert('xss')")

        assert result is None

    def test_sanitize_url_rejects_data(self):
        """Test data: URLs are rejected."""
        result = InputSanitizer.sanitize_url("data:text/html,<script>alert(1)</script>")

        assert result is None

    def test_sanitize_url_handles_invalid_url(self):
        """Test invalid URLs return None."""
        result = InputSanitizer.sanitize_url("not-a-valid-url")

        # Should either be None or have no scheme
        assert result is None or "://" not in result


class TestInputSanitizerJSON:
    """Test InputSanitizer JSON sanitization."""

    def test_sanitize_json_handles_dict(self):
        """Test dict sanitization."""
        data = {"key": "value", "nested": {"inner": "data"}}
        result = InputSanitizer.sanitize_json(data)

        assert result["key"] == "value"
        assert result["nested"]["inner"] == "data"

    def test_sanitize_json_handles_list(self):
        """Test list sanitization."""
        data = ["item1", "item2", {"key": "value"}]
        result = InputSanitizer.sanitize_json(data)

        assert len(result) == 3
        assert result[0] == "item1"
        assert result[2]["key"] == "value"

    def test_sanitize_json_limits_array_size(self):
        """Test large arrays are limited."""
        data = list(range(2000))
        result = InputSanitizer.sanitize_json(data)

        assert len(result) <= 1000

    def test_sanitize_json_limits_nesting_depth(self):
        """Test deeply nested JSON raises error."""
        # Create deeply nested structure
        data = {"level": None}
        current = data
        for i in range(15):
            current["level"] = {"level": None}
            current = current["level"]

        with pytest.raises(ValueError, match="too deep"):
            InputSanitizer.sanitize_json(data)

    def test_sanitize_json_filters_long_keys(self):
        """Test long keys are filtered out."""
        long_key = "a" * 300
        data = {long_key: "value", "short": "kept"}
        result = InputSanitizer.sanitize_json(data)

        assert long_key not in result
        assert "short" in result


class TestInputSanitizerString:
    """Test InputSanitizer string sanitization."""

    def test_sanitize_string_removes_null_bytes(self):
        """Test null bytes are removed."""
        text = "hello\x00world"
        result = InputSanitizer.sanitize_string(text)

        assert "\x00" not in result
        assert "helloworld" in result

    def test_sanitize_string_normalizes_whitespace(self):
        """Test whitespace is normalized."""
        text = "hello   \t\n  world"
        result = InputSanitizer.sanitize_string(text)

        assert result == "hello world"

    def test_sanitize_string_truncates_long_text(self):
        """Test long strings are truncated."""
        text = "a" * 20000
        result = InputSanitizer.sanitize_string(text, max_length=100)

        assert len(result) == 100

    def test_sanitize_string_handles_empty(self):
        """Test empty string handling."""
        result = InputSanitizer.sanitize_string("")

        assert result == ""


class TestInputValidatorEmail:
    """Test InputValidator email validation."""

    def test_validate_email_accepts_valid(self):
        """Test valid emails are accepted."""
        assert InputValidator.validate_email("user@example.com") is True
        assert InputValidator.validate_email("user.name@example.com") is True
        assert InputValidator.validate_email("user+tag@example.com") is True

    def test_validate_email_rejects_invalid(self):
        """Test invalid emails are rejected."""
        assert InputValidator.validate_email("not-an-email") is False
        assert InputValidator.validate_email("@example.com") is False
        assert InputValidator.validate_email("user@") is False

    def test_validate_email_rejects_too_long(self):
        """Test emails exceeding max length are rejected."""
        long_email = "a" * 250 + "@example.com"
        assert InputValidator.validate_email(long_email) is False

    def test_validate_email_rejects_suspicious_patterns(self):
        """Test suspicious email patterns are rejected."""
        # Numeric-only local part
        assert InputValidator.validate_email("12345@example.com") is False


class TestInputValidatorPassword:
    """Test InputValidator password validation."""

    def test_validate_password_accepts_strong(self):
        """Test strong passwords are accepted."""
        # Password with no sequential chars (123, abc, etc.)
        result = InputValidator.validate_password("Str0ngP@ssw0rd!X")

        assert result["valid"] is True
        assert result["strength"] in ["medium", "strong"]

    def test_validate_password_rejects_short(self):
        """Test short passwords are rejected."""
        result = InputValidator.validate_password("Ab1!")

        assert result["valid"] is False
        assert any("8 characters" in issue for issue in result["issues"])

    def test_validate_password_rejects_too_long(self):
        """Test passwords exceeding max length are rejected."""
        long_password = "Aa1!" + "a" * 130
        result = InputValidator.validate_password(long_password)

        assert result["valid"] is False
        assert any("128 characters" in issue for issue in result["issues"])

    def test_validate_password_requires_complexity(self):
        """Test password complexity is required."""
        result = InputValidator.validate_password("alllowercase")

        assert result["valid"] is False
        assert any("uppercase" in issue or "digit" in issue for issue in result["issues"])

    def test_validate_password_rejects_common(self):
        """Test common passwords are rejected."""
        result = InputValidator.validate_password("password123")

        assert result["valid"] is False
        assert any("common" in issue for issue in result["issues"])

    def test_validate_password_rejects_sequential(self):
        """Test sequential characters are flagged."""
        result = InputValidator.validate_password("MyPass123456!")

        assert result["valid"] is False
        assert any("sequential" in issue for issue in result["issues"])

    def test_validate_password_rejects_repeated(self):
        """Test repeated characters are flagged."""
        result = InputValidator.validate_password("Passssssword1!")

        assert result["valid"] is False
        assert any("repeated" in issue for issue in result["issues"])


class TestInputValidatorUsername:
    """Test InputValidator username validation."""

    def test_validate_username_accepts_valid(self):
        """Test valid usernames are accepted."""
        assert InputValidator.validate_username("user123") is True
        assert InputValidator.validate_username("user_name") is True
        assert InputValidator.validate_username("user-name") is True

    def test_validate_username_rejects_short(self):
        """Test short usernames are rejected."""
        assert InputValidator.validate_username("ab") is False

    def test_validate_username_rejects_long(self):
        """Test long usernames are rejected."""
        long_username = "a" * 35
        assert InputValidator.validate_username(long_username) is False

    def test_validate_username_rejects_special_chars(self):
        """Test special characters are rejected."""
        assert InputValidator.validate_username("user@name") is False
        assert InputValidator.validate_username("user name") is False
        assert InputValidator.validate_username("user!name") is False


class TestInputValidatorURL:
    """Test InputValidator URL validation."""

    def test_validate_url_accepts_https(self):
        """Test HTTPS URLs are accepted."""
        assert InputValidator.validate_url("https://example.com/path") is True

    def test_validate_url_accepts_http(self):
        """Test HTTP URLs are accepted."""
        assert InputValidator.validate_url("http://example.com/path") is True

    def test_validate_url_rejects_no_scheme(self):
        """Test URLs without scheme are rejected."""
        assert InputValidator.validate_url("example.com/path") is False

    def test_validate_url_rejects_ftp(self):
        """Test FTP URLs are rejected."""
        assert InputValidator.validate_url("ftp://example.com/file") is False

    def test_validate_url_rejects_too_long(self):
        """Test URLs exceeding max length are rejected."""
        long_url = "https://example.com/" + "a" * 2100
        assert InputValidator.validate_url(long_url) is False


class TestInputValidatorDate:
    """Test InputValidator date validation."""

    def test_validate_date_accepts_valid(self):
        """Test valid dates are accepted."""
        assert InputValidator.validate_date("2024-01-15") is True
        assert InputValidator.validate_date("2023-12-31") is True

    def test_validate_date_rejects_invalid_format(self):
        """Test invalid date formats are rejected."""
        assert InputValidator.validate_date("01-15-2024") is False
        assert InputValidator.validate_date("2024/01/15") is False

    def test_validate_date_rejects_invalid_date(self):
        """Test invalid dates are rejected."""
        assert InputValidator.validate_date("2024-13-01") is False
        assert InputValidator.validate_date("2024-02-30") is False


class TestInputValidatorMaliciousPatterns:
    """Test InputValidator malicious pattern detection."""

    def test_detect_sql_injection(self):
        """Test SQL injection detection."""
        threats = InputValidator.detect_malicious_patterns("SELECT * FROM users")
        assert "sql_injection" in threats

        threats = InputValidator.detect_malicious_patterns("1 OR 1=1")
        assert "sql_injection" in threats

        threats = InputValidator.detect_malicious_patterns("'; DROP TABLE users;--")
        assert "sql_injection" in threats

    def test_detect_xss(self):
        """Test XSS detection."""
        threats = InputValidator.detect_malicious_patterns("<script>alert('xss')</script>")
        assert "xss" in threats

        threats = InputValidator.detect_malicious_patterns("javascript:alert(1)")
        assert "xss" in threats

        threats = InputValidator.detect_malicious_patterns('<img onerror="alert(1)">')
        assert "xss" in threats

    def test_detect_path_traversal(self):
        """Test path traversal detection."""
        threats = InputValidator.detect_malicious_patterns("../../../etc/passwd")
        assert "path_traversal" in threats

        threats = InputValidator.detect_malicious_patterns("%2e%2e/")
        assert "path_traversal" in threats

    def test_detect_command_injection(self):
        """Test command injection detection."""
        threats = InputValidator.detect_malicious_patterns("; rm -rf /")
        assert "command_injection" in threats

        threats = InputValidator.detect_malicious_patterns("| cat /etc/passwd")
        assert "command_injection" in threats

    def test_safe_input_no_threats(self):
        """Test safe input returns no threats."""
        threats = InputValidator.detect_malicious_patterns("Hello, this is a normal message")
        assert len(threats) == 0


class TestComprehensiveMiddlewareInitialization:
    """Test ComprehensiveInputValidationMiddleware initialization."""

    def test_initialization_default_strict(self):
        """Test middleware initializes with strict mode by default."""
        app = MagicMock()
        middleware = ComprehensiveInputValidationMiddleware(app)

        assert middleware.strict_mode is True
        assert middleware.validation_error_tracker == {}

    def test_initialization_non_strict(self):
        """Test middleware initializes with non-strict mode."""
        app = MagicMock()
        middleware = ComprehensiveInputValidationMiddleware(app, strict_mode=False)

        assert middleware.strict_mode is False

    def test_factory_function(self):
        """Test create_input_validation_middleware factory."""
        app = MagicMock()
        middleware = create_input_validation_middleware(app, strict_mode=False)

        assert isinstance(middleware, ComprehensiveInputValidationMiddleware)
        assert middleware.strict_mode is False


class TestMiddlewareSkipPaths:
    """Test middleware skips certain paths."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return ComprehensiveInputValidationMiddleware(app)

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.headers = {}
        request.query_params = {}
        request.client.host = "127.0.0.1"
        return request

    async def test_skips_health_endpoint(self, middleware, mock_request):
        """Test middleware skips /health endpoint."""
        mock_request.url.path = "/health"
        call_next = AsyncMock(return_value=MagicMock())

        await middleware.dispatch(mock_request, call_next)

        call_next.assert_called_once()

    async def test_skips_docs_endpoint(self, middleware, mock_request):
        """Test middleware skips /docs endpoint."""
        mock_request.url.path = "/docs"
        call_next = AsyncMock(return_value=MagicMock())

        await middleware.dispatch(mock_request, call_next)

        call_next.assert_called_once()

    async def test_skips_redoc_endpoint(self, middleware, mock_request):
        """Test middleware skips /redoc endpoint."""
        mock_request.url.path = "/redoc"
        call_next = AsyncMock(return_value=MagicMock())

        await middleware.dispatch(mock_request, call_next)

        call_next.assert_called_once()

    async def test_skips_openapi_endpoint(self, middleware, mock_request):
        """Test middleware skips /openapi.json endpoint."""
        mock_request.url.path = "/openapi.json"
        call_next = AsyncMock(return_value=MagicMock())

        await middleware.dispatch(mock_request, call_next)

        call_next.assert_called_once()


class TestMiddlewareClientIP:
    """Test middleware client IP extraction."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return ComprehensiveInputValidationMiddleware(app)

    def test_get_client_ip_direct(self, middleware):
        """Test direct client IP extraction."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client.host = "192.168.1.1"

        ip = middleware.get_client_ip(request)

        assert ip == "192.168.1.1"

    def test_get_client_ip_from_forwarded(self, middleware):
        """Test IP from X-Forwarded-For header."""
        request = MagicMock(spec=Request)
        request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        request.client.host = "127.0.0.1"

        ip = middleware.get_client_ip(request)

        assert ip == "10.0.0.1"

    def test_get_client_ip_unknown(self, middleware):
        """Test unknown client IP."""
        request = MagicMock(spec=Request)
        request.headers = {}
        request.client = None

        ip = middleware.get_client_ip(request)

        assert ip == "unknown"


class TestMiddlewareValidationAbuse:
    """Test middleware validation abuse tracking."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return ComprehensiveInputValidationMiddleware(app)

    def test_is_validation_abuse_false_initially(self, middleware):
        """Test no abuse detected initially."""
        assert middleware.is_validation_abuse("192.168.1.1") is False

    def test_track_validation_error(self, middleware):
        """Test validation error tracking."""
        middleware.track_validation_error("192.168.1.1")

        assert "192.168.1.1" in middleware.validation_error_tracker
        assert len(middleware.validation_error_tracker["192.168.1.1"]) == 1

    def test_is_validation_abuse_after_many_errors(self, middleware):
        """Test abuse detected after many errors."""
        # Track many errors
        for _ in range(15):
            middleware.track_validation_error("192.168.1.1")

        assert middleware.is_validation_abuse("192.168.1.1") is True


class TestMiddlewareHeaderValidation:
    """Test middleware header validation."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return ComprehensiveInputValidationMiddleware(app, strict_mode=True)

    async def test_validate_headers_accepts_valid(self, middleware):
        """Test valid headers are accepted."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.headers = {"Content-Type": "application/json"}

        result = await middleware.validate_headers(request)

        assert result["valid"] is True

    async def test_validate_headers_rejects_suspicious(self, middleware):
        """Test suspicious headers are rejected in strict mode."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.headers = {"X-Original-URL": "/admin"}

        result = await middleware.validate_headers(request)

        assert result["valid"] is False
        assert any("Suspicious header" in e for e in result["errors"])

    async def test_validate_headers_rejects_header_injection(self, middleware):
        """Test header injection is rejected."""
        request = MagicMock(spec=Request)
        request.method = "GET"
        request.headers = {"X-Custom": "value\r\nInjected: header"}

        result = await middleware.validate_headers(request)

        assert result["valid"] is False
        assert any("injection" in e for e in result["errors"])

    async def test_validate_headers_checks_content_type_for_post(self, middleware):
        """Test content-type validation for POST requests."""
        request = MagicMock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "text/plain"}

        result = await middleware.validate_headers(request)

        assert result["valid"] is False
        assert any("content-type" in e for e in result["errors"])


class TestMiddlewareQueryParamValidation:
    """Test middleware query parameter validation."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return ComprehensiveInputValidationMiddleware(app)

    def test_validate_query_params_accepts_valid(self, middleware):
        """Test valid query params are accepted."""
        request = MagicMock(spec=Request)
        request.query_params = {"page": "1", "limit": "20"}

        result = middleware.validate_query_params(request)

        assert result["valid"] is True

    def test_validate_query_params_detects_threats(self, middleware):
        """Test threats in query params are detected."""
        request = MagicMock(spec=Request)
        request.query_params = {"search": "'; DROP TABLE users;--"}

        result = middleware.validate_query_params(request)

        assert result["valid"] is False
        assert any("sql_injection" in e for e in result["errors"])

    def test_validate_query_params_validates_pagination(self, middleware):
        """Test pagination params are validated."""
        request = MagicMock(spec=Request)
        request.query_params = {"limit": "-1"}

        result = middleware.validate_query_params(request)

        assert result["valid"] is False

    def test_validate_query_params_validates_email(self, middleware):
        """Test email query param is validated."""
        request = MagicMock(spec=Request)
        request.query_params = {"email": "not-an-email"}

        result = middleware.validate_query_params(request)

        assert result["valid"] is False


class TestMiddlewarePathParamValidation:
    """Test middleware path parameter validation."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return ComprehensiveInputValidationMiddleware(app)

    def test_validate_path_params_accepts_valid(self, middleware):
        """Test valid paths are accepted."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/users/123"

        result = middleware.validate_path_params(request)

        assert result["valid"] is True

    def test_validate_path_params_detects_traversal(self, middleware):
        """Test path traversal is detected."""
        request = MagicMock(spec=Request)
        request.url.path = "/api/v1/../../../etc/passwd"

        result = middleware.validate_path_params(request)

        assert result["valid"] is False
        assert any("traversal" in e for e in result["errors"])

    def test_validate_path_params_detects_double_slash(self, middleware):
        """Test double slash is detected."""
        request = MagicMock(spec=Request)
        request.url.path = "/api//v1/users"

        result = middleware.validate_path_params(request)

        assert result["valid"] is False


class TestMiddlewareThreatScanning:
    """Test middleware threat scanning."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        app = MagicMock()
        return ComprehensiveInputValidationMiddleware(app)

    def test_scan_for_threats_in_string(self, middleware):
        """Test threat scanning in strings."""
        data = "<script>alert('xss')</script>"
        threats = middleware.scan_for_threats(data)

        assert "xss" in threats

    def test_scan_for_threats_in_dict(self, middleware):
        """Test threat scanning in dictionaries."""
        data = {"user": "admin", "query": "SELECT * FROM users"}
        threats = middleware.scan_for_threats(data)

        assert "sql_injection" in threats

    def test_scan_for_threats_in_nested_structure(self, middleware):
        """Test threat scanning in nested structures."""
        data = {
            "level1": {
                "level2": ["safe", "javascript:alert(1)"]
            }
        }
        threats = middleware.scan_for_threats(data)

        assert "xss" in threats

    def test_scan_for_threats_safe_data(self, middleware):
        """Test safe data returns no threats."""
        data = {"name": "John", "email": "john@example.com"}
        threats = middleware.scan_for_threats(data)

        assert len(threats) == 0
