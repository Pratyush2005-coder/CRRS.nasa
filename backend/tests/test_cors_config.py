"""CORS configuration tests."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app


class TestCORSConfigParsing:
    """Test CORS_ORIGINS parsing and validation."""

    def test_default_development_origins(self):
        """Test default development origins are used when no env var set."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]

    def test_single_production_origin(self):
        """Test single production origin from comma-separated string."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            CORS_ORIGINS="https://app.example.com",
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == ["https://app.example.com"]

    def test_multiple_comma_separated_origins(self):
        """Test multiple comma-separated production origins."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            CORS_ORIGINS="https://app.example.com,https://admin.example.com,https://api.example.com",
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == [
            "https://app.example.com",
            "https://admin.example.com",
            "https://api.example.com",
        ]

    def test_whitespace_handling(self):
        """Test whitespace around origins is trimmed."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            CORS_ORIGINS="  https://app.example.com , https://admin.example.com  ",
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == [
            "https://app.example.com",
            "https://admin.example.com",
        ]

    def test_empty_comma_entry_rejected(self):
        """Test empty entries in comma-separated list are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS="https://app.example.com,,https://admin.example.com",
                _env_file=None,
            )
        assert "empty" in str(exc_info.value).lower()

    def test_empty_json_entry_rejected(self):
        """Test empty entries in JSON list are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS=["https://app.example.com", "", "https://admin.example.com"],
                _env_file=None,
            )
        assert "empty" in str(exc_info.value).lower()

    def test_whitespace_only_json_entry_rejected(self):
        """Test whitespace-only entries in JSON list are rejected."""
        with pytest.raises(ValidationError):
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS=["https://app.example.com", "   ", "https://admin.example.com"],
                _env_file=None,
            )

    def test_wildcard_rejected_comma_format(self):
        """Test wildcard origin rejected in comma-separated format."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS="*",
                _env_file=None,
            )
        assert "wildcard" in str(exc_info.value).lower()

    def test_wildcard_rejected_json_format(self):
        """Test wildcard origin rejected in JSON format."""
        with pytest.raises(ValidationError):
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS=["*"],
                _env_file=None,
            )

    def test_malformed_url_rejected(self):
        """Test malformed URLs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS="not-a-url",
                _env_file=None,
            )
        assert "invalid" in str(exc_info.value).lower()

    def test_missing_scheme_rejected(self):
        """Test URLs without http/https scheme are rejected."""
        with pytest.raises(ValidationError):
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS="app.example.com",
                _env_file=None,
            )

    def test_invalid_scheme_rejected(self):
        """Test URLs with invalid scheme are rejected."""
        with pytest.raises(ValidationError):
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS="ftp://example.com",
                _env_file=None,
            )

    def test_empty_string_rejected(self):
        """Test empty CORS_ORIGINS string is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS="",
                _env_file=None,
            )
        assert "empty" in str(exc_info.value).lower()

    def test_path_rejected(self):
        """Test origins with paths are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS="https://example.com/path",
                _env_file=None,
            )
        assert "path" in str(exc_info.value).lower()

    def test_query_string_rejected(self):
        """Test origins with query strings are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS="https://example.com?foo=bar",
                _env_file=None,
            )
        assert "query" in str(exc_info.value).lower()

    def test_fragment_rejected(self):
        """Test origins with fragments are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS="https://example.com#anchor",
                _env_file=None,
            )
        assert "fragment" in str(exc_info.value).lower()

    def test_embedded_credentials_rejected(self):
        """Test origins with embedded username/password are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS="https://user:pass@example.com",
                _env_file=None,
            )
        assert "credential" in str(exc_info.value).lower()

    def test_invalid_port_rejected(self):
        """Test origins with invalid port (>65535) are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS="https://example.com:99999",
                _env_file=None,
            )
        assert "port" in str(exc_info.value).lower()

    def test_port_zero_rejected(self):
        """Test origins with port 0 are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS="https://example.com:0",
                _env_file=None,
            )
        assert "port" in str(exc_info.value).lower()

    def test_valid_port_accepted(self):
        """Test origins with valid ports are accepted."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            CORS_ORIGINS="https://example.com:8443",
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == ["https://example.com:8443"]

    def test_json_list_format_still_works(self):
        """Test JSON list format from .env.example still works."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            CORS_ORIGINS=["https://app.example.com", "https://admin.example.com"],
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == [
            "https://app.example.com",
            "https://admin.example.com",
        ]

    def test_json_list_with_whitespace(self):
        """Test JSON list with whitespace is trimmed."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            CORS_ORIGINS=["  https://app.example.com  ", "https://admin.example.com"],
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == [
            "https://app.example.com",
            "https://admin.example.com",
        ]

    def test_duplicate_origins_deduplicated(self):
        """Test duplicate origins are deduplicated preserving order."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            CORS_ORIGINS="https://a.com,https://a.com,https://b.com,https://a.com",
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == ["https://a.com", "https://b.com"]

    def test_duplicate_origins_json_deduplicated(self):
        """Test duplicate origins in JSON list are deduplicated."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            CORS_ORIGINS=["https://a.com", "https://b.com", "https://a.com"],
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == ["https://a.com", "https://b.com"]

    def test_ipv6_loopback_handled(self):
        """Test IPv6 loopback address is handled correctly."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            CORS_ORIGINS="http://[::1]:3000",
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == ["http://[::1]:3000"]

    def test_invalid_ipv6_rejected(self):
        """Test invalid IPv6 addresses are rejected."""
        with pytest.raises(ValidationError):
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                CORS_ORIGINS="http://[invalid]",
                _env_file=None,
            )


class TestCORSProductionHTTPRestriction:
    """Test production HTTP restriction."""

    def test_production_rejects_http_non_localhost(self):
        """Production rejects HTTP for non-localhost hosts."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                ENVIRONMENT="production",
                CORS_ORIGINS="http://evil.com",
                _env_file=None,
            )
        assert "http" in str(exc_info.value).lower()
        assert "production" in str(exc_info.value).lower()

    def test_production_accepts_https(self):
        """Production accepts HTTPS origins."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            ENVIRONMENT="production",
            CORS_ORIGINS="https://app.example.com",
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == ["https://app.example.com"]

    def test_production_accepts_http_localhost(self):
        """Production accepts HTTP for localhost."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            ENVIRONMENT="production",
            CORS_ORIGINS="http://localhost:3000",
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == ["http://localhost:3000"]

    def test_production_accepts_http_127_0_0_1(self):
        """Production accepts HTTP for 127.0.0.1."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            ENVIRONMENT="production",
            CORS_ORIGINS="http://127.0.0.1:3000",
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == ["http://127.0.0.1:3000"]

    def test_production_accepts_http_ipv6_loopback(self):
        """Production accepts HTTP for IPv6 loopback."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            ENVIRONMENT="production",
            CORS_ORIGINS="http://[::1]:3000",
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == ["http://[::1]:3000"]

    def test_development_accepts_http_non_localhost(self):
        """Development accepts HTTP for non-localhost (permissive for dev)."""
        settings = Settings(
            SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
            ENVIRONMENT="development",
            CORS_ORIGINS="http://evil.com",
            _env_file=None,
        )
        assert settings.CORS_ORIGINS == ["http://evil.com"]

    def test_production_rejects_http_localhost_with_path(self):
        """Production rejects HTTP localhost with path."""
        with pytest.raises(ValidationError):
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                ENVIRONMENT="production",
                CORS_ORIGINS="http://localhost:3000/path",
                _env_file=None,
            )

    def test_production_rejects_http_non_localhost_with_port(self):
        """Production rejects HTTP non-localhost even with explicit port."""
        with pytest.raises(ValidationError):
            Settings(
                SECRET_KEY="test-secret-key-for-testing-only-32-chars-minimum",
                ENVIRONMENT="production",
                CORS_ORIGINS="http://evil.com:8080",
                _env_file=None,
            )


class TestCORSIntegration:
    """Integration tests for CORS behavior with the FastAPI app."""

    def test_default_origins_allowed(self):
        """Test default development origins are allowed."""
        client = TestClient(app)
        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200
        assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
        assert response.headers.get("Access-Control-Allow-Credentials") == "true"

    def test_localhost_variants_allowed(self):
        """Test all default localhost variants work."""
        client = TestClient(app)
        for origin in [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]:
            response = client.get("/api/health", headers={"Origin": origin})
            assert response.status_code == 200, f"Failed for {origin}"
            assert response.headers.get("Access-Control-Allow-Origin") == origin

    def test_unlisted_origin_rejected(self):
        """Test origins not in CORS_ORIGINS are rejected (no ACAO header)."""
        client = TestClient(app)
        response = client.get(
            "/api/health",
            headers={"Origin": "https://evil.com"},
        )
        assert response.headers.get("Access-Control-Allow-Origin") is None
        assert response.status_code == 200

    def test_cors_preflight_with_security_headers(self):
        """Test CORS preflight includes security headers."""
        client = TestClient(app)
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code in (200, 400)
        assert response.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
        assert response.headers.get("Access-Control-Allow-Credentials") == "true"
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert response.headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"

    def test_cors_preflight_unlisted_origin(self):
        """Test CORS preflight for unlisted origin."""
        client = TestClient(app)
        response = client.options(
            "/api/health",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("Access-Control-Allow-Origin") is None

    def test_credentials_header_always_present_for_allowed(self):
        """Test allow_credentials=True results in ACA-Credentials header."""
        client = TestClient(app)
        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.headers.get("Access-Control-Allow-Credentials") == "true"

    def test_security_headers_on_cors_response(self):
        """Test security headers present on CORS responses."""
        client = TestClient(app)
        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert response.headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=()"

    def test_vary_header_present(self):
        """Test Vary: Origin header is present for CORS responses."""
        client = TestClient(app)
        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"},
        )
        vary = response.headers.get("Vary", "")
        assert "Origin" in vary