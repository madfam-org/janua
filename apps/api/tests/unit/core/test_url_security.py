"""
Unit tests for URL security validation module.

Tests the open redirect prevention functionality (CWE-601 mitigation).
"""

import pytest

from app.core.url_security import (
    is_safe_redirect_url,
    validate_redirect_url,
    validate_oauth_redirect_uri,
    get_allowed_redirect_hosts,
    _host_matches_pattern,
)  # noqa: F401 - Test imports


class TestHostMatching:
    """Tests for host pattern matching."""

    def test_exact_match(self):
        """Test exact host matching."""
        assert _host_matches_pattern("localhost", "localhost")
        assert _host_matches_pattern("janua.dev", "janua.dev")
        assert not _host_matches_pattern("janua.dev", "other.dev")

    def test_wildcard_subdomain_match(self):
        """Test wildcard subdomain matching."""
        assert _host_matches_pattern("app.janua.dev", "*.janua.dev")
        assert _host_matches_pattern("api.janua.dev", "*.janua.dev")
        assert _host_matches_pattern("admin.janua.dev", "*.janua.dev")
        # Base domain should also match
        assert _host_matches_pattern("janua.dev", "*.janua.dev")

    def test_wildcard_does_not_match_parent(self):
        """Test that wildcard doesn't match unrelated domains."""
        assert not _host_matches_pattern("evil.com", "*.janua.dev")
        assert not _host_matches_pattern("janua.dev.evil.com", "*.janua.dev")

    def test_case_insensitive_matching(self):
        """Test that matching is case-insensitive."""
        assert _host_matches_pattern("JANUA.DEV", "janua.dev")
        assert _host_matches_pattern("App.Janua.Dev", "*.janua.dev")

    def test_port_stripped_from_host(self):
        """Test that ports are stripped from host for matching."""
        assert _host_matches_pattern("localhost:3000", "localhost")
        assert _host_matches_pattern("janua.dev:443", "janua.dev")


class TestIsSafeRedirectUrl:
    """Tests for is_safe_redirect_url function."""

    def test_relative_urls_allowed_by_default(self):
        """Test that relative URLs are allowed by default."""
        assert is_safe_redirect_url("/dashboard")
        assert is_safe_redirect_url("/api/v1/auth")
        assert is_safe_redirect_url("/oauth/authorize?client_id=test")
        assert is_safe_redirect_url("/")

    def test_relative_urls_blocked_when_disabled(self):
        """Test that relative URLs can be blocked."""
        assert not is_safe_redirect_url("/dashboard", allow_relative=False)

    def test_empty_url_rejected(self):
        """Test that empty URLs are rejected."""
        assert not is_safe_redirect_url("")
        assert not is_safe_redirect_url("   ")
        assert not is_safe_redirect_url(None)

    def test_javascript_urls_blocked(self):
        """Test that javascript: URLs are blocked."""
        assert not is_safe_redirect_url("javascript:alert(1)")
        assert not is_safe_redirect_url("JAVASCRIPT:alert(1)")
        assert not is_safe_redirect_url("javascript://comment%0aalert(1)")

    def test_data_urls_blocked(self):
        """Test that data: URLs are blocked."""
        assert not is_safe_redirect_url("data:text/html,<script>alert(1)</script>")
        assert not is_safe_redirect_url("DATA:text/html,attack")

    def test_vbscript_urls_blocked(self):
        """Test that vbscript: URLs are blocked."""
        assert not is_safe_redirect_url("vbscript:msgbox(1)")

    def test_file_urls_blocked(self):
        """Test that file: URLs are blocked."""
        assert not is_safe_redirect_url("file:///etc/passwd")

    def test_protocol_relative_urls_validated(self):
        """Test that protocol-relative URLs are validated."""
        # Protocol-relative URLs to allowed hosts should work
        assert not is_safe_redirect_url("//evil.com/path")
        # This would need to match allowed hosts

    def test_double_slash_path_blocked(self):
        """Test that relative URLs starting with // are blocked."""
        assert not is_safe_redirect_url("//evil.com")

    def test_backslash_urls_blocked(self):
        """Test that URLs with backslashes are blocked (browser parsing tricks)."""
        assert not is_safe_redirect_url("/\\evil.com")
        assert not is_safe_redirect_url("\\\\evil.com")

    def test_allowed_hosts_work(self):
        """Test that absolute URLs to allowed hosts work."""
        allowed = ["localhost", "janua.dev", "*.janua.dev"]
        assert is_safe_redirect_url("https://janua.dev/dashboard", allowed_hosts=allowed)
        assert is_safe_redirect_url("https://app.janua.dev/callback", allowed_hosts=allowed)
        assert is_safe_redirect_url("http://localhost:3000/auth", allowed_hosts=allowed)

    def test_external_hosts_blocked(self):
        """Test that external hosts are blocked."""
        allowed = ["localhost", "janua.dev"]
        assert not is_safe_redirect_url("https://evil.com/callback", allowed_hosts=allowed)
        assert not is_safe_redirect_url("https://attacker.com/steal", allowed_hosts=allowed)


class TestValidateRedirectUrl:
    """Tests for validate_redirect_url function."""

    def test_safe_url_returned_unchanged(self):
        """Test that safe URLs are returned unchanged."""
        assert validate_redirect_url("/dashboard") == "/dashboard"
        assert validate_redirect_url("/api/v1/callback") == "/api/v1/callback"

    def test_unsafe_url_returns_default(self):
        """Test that unsafe URLs return the default."""
        assert validate_redirect_url("javascript:alert(1)") == "/"
        assert validate_redirect_url("https://evil.com") == "/"

    def test_custom_default_url(self):
        """Test that custom default URLs work."""
        assert validate_redirect_url("javascript:alert(1)", default_url="/home") == "/home"
        assert validate_redirect_url("https://evil.com", default_url="/login") == "/login"


class TestValidateOauthRedirectUri:
    """Tests for OAuth redirect URI validation."""

    def test_exact_match_required(self):
        """Test that OAuth URIs require exact matching."""
        registered = [
            "https://app.example.com/callback",
            "https://app.example.com/oauth/callback",
        ]
        assert validate_oauth_redirect_uri("https://app.example.com/callback", registered)
        assert validate_oauth_redirect_uri("https://app.example.com/oauth/callback", registered)
        assert not validate_oauth_redirect_uri("https://app.example.com/other", registered)

    def test_trailing_slash_normalized(self):
        """Test that trailing slashes are normalized."""
        registered = ["https://app.example.com/callback/"]
        assert validate_oauth_redirect_uri("https://app.example.com/callback", registered)

    def test_scheme_must_match(self):
        """Test that scheme must match exactly."""
        registered = ["https://app.example.com/callback"]
        assert not validate_oauth_redirect_uri("http://app.example.com/callback", registered)

    def test_host_must_match(self):
        """Test that host must match exactly."""
        registered = ["https://app.example.com/callback"]
        assert not validate_oauth_redirect_uri("https://evil.example.com/callback", registered)

    def test_empty_values_rejected(self):
        """Test that empty values are rejected."""
        assert not validate_oauth_redirect_uri("", ["https://example.com"])
        assert not validate_oauth_redirect_uri("https://example.com", [])
        assert not validate_oauth_redirect_uri(None, ["https://example.com"])


class TestGetAllowedRedirectHosts:
    """Tests for get_allowed_redirect_hosts function."""

    def test_includes_default_hosts(self):
        """Test that default hosts are included."""
        hosts = get_allowed_redirect_hosts()
        assert "localhost" in hosts
        assert "127.0.0.1" in hosts
        assert "janua.dev" in hosts
        assert "*.janua.dev" in hosts

    def test_no_duplicates(self):
        """Test that there are no duplicate hosts."""
        hosts = get_allowed_redirect_hosts()
        assert len(hosts) == len(set(hosts))
