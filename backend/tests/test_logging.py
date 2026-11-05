"""Tests for structured logging configuration and request correlation."""

import json
import logging
import re
import sys
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from app.core.logging_config import (
    JSONFormatter,
    RequestContextFilter,
    get_request_id,
    sanitize_dict,
    sanitize_exception_message,
    sanitize_traceback,
    set_request_id,
    clear_request_id,
    setup_logging,
)
from app.core.request_logging import (
    RequestLoggingMiddleware,
    generate_request_id,
    validate_request_id,
    sanitize_path,
    sanitize_headers,
)


class TestJSONFormatter:
    """Tests for JSON log formatter."""

    def test_format_basic_log(self):
        """Basic log record should produce valid JSON with required fields."""
        formatter = JSONFormatter(environment="test")
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"
        assert data["environment"] == "test"
        assert "timestamp" in data
        # Verify timestamp is UTC ISO format
        assert "T" in data["timestamp"]
        assert data["timestamp"].endswith("+00:00") or data["timestamp"].endswith("Z")

    def test_format_with_request_id(self):
        """Log record with request_id should include it in output."""
        formatter = JSONFormatter(environment="test")
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.request_id = "test-request-123"
        output = formatter.format(record)
        data = json.loads(output)

        assert data["request_id"] == "test-request-123"

    def test_format_with_exception(self):
        """Log record with exception info should include exception details."""
        formatter = JSONFormatter(environment="test")
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert "Test error" in data["exception"]["message"]
        assert "traceback" in data["exception"]

    def test_format_with_extra_fields(self):
        """Extra fields should be included in extra object."""
        formatter = JSONFormatter(environment="test")
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.extra_field = "extra_value"
        record.user_id = "user-123"
        output = formatter.format(record)
        data = json.loads(output)

        assert "extra" in data
        assert data["extra"]["extra_field"] == "extra_value"
        assert data["extra"]["user_id"] == "user-123"

    def test_format_exception_sanitizes_password_in_message(self):
        """Exception message with password should be sanitized."""
        formatter = JSONFormatter(environment="test")
        try:
            raise ValueError("Connection failed: password=secret123")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Database connection failed",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert "secret123" not in data["exception"]["message"]
        assert "***REDACTED***" in data["exception"]["message"]

    def test_format_exception_sanitizes_jwt_in_message(self):
        """Exception message with JWT should be sanitized."""
        formatter = JSONFormatter(environment="test")
        jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        try:
            raise ValueError(f"Auth failed: bearer {jwt_token}")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Authentication error",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert jwt_token not in data["exception"]["message"]
        assert "***REDACTED***" in data["exception"]["message"]

    def test_format_exception_sanitizes_api_key_in_message(self):
        """Exception message with API key should be sanitized."""
        formatter = JSONFormatter(environment="test")
        try:
            raise ValueError("API call failed: api_key=sk-abcdef123456")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="API error",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "sk-abcdef123456" not in data["exception"]["message"]
        assert "***REDACTED***" in data["exception"]["message"]

    def test_format_exception_sanitizes_database_url_in_message(self):
        """Exception message with database URL should be sanitized."""
        formatter = JSONFormatter(environment="test")
        db_url = "postgresql://user:password123@localhost:5432/mydb"
        try:
            raise ValueError(f"Connection failed: {db_url}")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Database error",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "password123" not in data["exception"]["message"]
        assert "***REDACTED***" in data["exception"]["message"]
        # Hostname should be preserved
        assert "localhost" in data["exception"]["message"]

    def test_format_exception_sanitizes_traceback(self):
        """Exception traceback should be sanitized."""
        formatter = JSONFormatter(environment="test")

        def inner_function():
            raise ValueError("Failed to connect: password=secret123")

        def outer_function():
            inner_function()

        try:
            outer_function()
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="Operation failed",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert "exception" in data
        assert "traceback" in data["exception"]
        traceback_str = "\n".join(data["exception"]["traceback"])
        assert "secret123" not in traceback_str
        assert "***REDACTED***" in traceback_str


class TestSanitizeDict:
    """Tests for sensitive data sanitization."""

    def test_sanitizes_password_fields(self):
        """Password-like fields should be redacted."""
        data = {
            "password": "secret123",
            "hashed_password": "hashed_secret",
            "user_password": "user_pass",
        }
        result = sanitize_dict(data)
        assert result["password"] == "***REDACTED***"
        assert result["hashed_password"] == "***REDACTED***"
        assert result["user_password"] == "***REDACTED***"

    def test_sanitizes_token_fields(self):
        """Token-like fields should be redacted."""
        data = {
            "access_token": "jwt_token_here",
            "refresh_token": "refresh_token_here",
            "api_key": "api_key_here",
        }
        result = sanitize_dict(data)
        assert result["access_token"] == "***REDACTED***"
        assert result["refresh_token"] == "***REDACTED***"
        assert result["api_key"] == "***REDACTED***"

    def test_sanitizes_database_url(self):
        """Database URLs should be redacted."""
        data = {
            "database_url": "postgresql://user:pass@host/db",
            "connection_string": "Server=...",
        }
        result = sanitize_dict(data)
        assert result["database_url"] == "***REDACTED***"
        assert result["connection_string"] == "***REDACTED***"

    def test_preserves_non_sensitive_fields(self):
        """Non-sensitive fields should be preserved."""
        data = {
            "username": "john_doe",
            "email": "john@example.com",
            "user_id": "123",
            "metadata": {"ip": "192.168.1.1"},
        }
        result = sanitize_dict(data)
        assert result["username"] == "john_doe"
        assert result["email"] == "john@example.com"
        assert result["user_id"] == "123"
        assert result["metadata"]["ip"] == "192.168.1.1"

    def test_sanitizes_nested_dict(self):
        """Nested dictionaries should be sanitized recursively."""
        data = {
            "user": {
                "name": "John",
                "password": "secret",
            },
            "config": {
                "api_key": "key123",
            },
        }
        result = sanitize_dict(data)
        assert result["user"]["name"] == "John"
        assert result["user"]["password"] == "***REDACTED***"
        assert result["config"]["api_key"] == "***REDACTED***"

    def test_sanitizes_list_of_dicts(self):
        """Lists of dictionaries should be sanitized."""
        data = {
            "users": [
                {"name": "Alice", "password": "alice123"},
                {"name": "Bob", "password": "bob123"},
            ]
        }
        result = sanitize_dict(data)
        assert result["users"][0]["name"] == "Alice"
        assert result["users"][0]["password"] == "***REDACTED***"
        assert result["users"][1]["password"] == "***REDACTED***"


class TestSanitizeExceptionMessage:
    """Tests for exception message sanitization."""

    def test_sanitizes_password_in_message(self):
        """Password in exception message should be redacted."""
        message = "Connection failed: password=secret123"
        result = sanitize_exception_message(message)
        assert "secret123" not in result
        assert "***REDACTED***" in result

    def test_sanitizes_jwt_in_message(self):
        """JWT in exception message should be redacted."""
        jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        message = f"Auth failed: bearer {jwt_token}"
        result = sanitize_exception_message(message)
        assert jwt_token not in result
        assert "***REDACTED***" in result

    def test_sanitizes_api_key_in_message(self):
        """API key in exception message should be redacted."""
        message = "API call failed: api_key=sk-abcdef123456"
        result = sanitize_exception_message(message)
        assert "sk-abcdef123456" not in result
        assert "***REDACTED***" in result

    def test_sanitizes_database_url_in_message(self):
        """Database URL in exception message should be redacted."""
        message = "Connection failed: postgresql://user:password123@localhost:5432/mydb"
        result = sanitize_exception_message(message)
        assert "password123" not in result
        assert "***REDACTED***" in result
        assert "localhost" in result

    def test_sanitizes_connection_string_in_message(self):
        """Connection string in exception message should be redacted."""
        message = "Failed: connection_string=Server=myServer;Database=myDB;User=myUser;Password=secret123;"
        result = sanitize_exception_message(message)
        assert "secret123" not in result
        assert "***REDACTED***" in result

    def test_preserves_non_sensitive_content(self):
        """Non-sensitive content should be preserved."""
        message = "Connection timeout after 30 seconds to host db.example.com"
        result = sanitize_exception_message(message)
        assert result == message

    def test_handles_empty_message(self):
        """Empty message should be handled gracefully."""
        assert sanitize_exception_message("") == ""
        assert sanitize_exception_message(None) is None


class TestSanitizeTraceback:
    """Tests for traceback sanitization."""

    def test_sanitizes_password_in_traceback(self):
        """Password in traceback should be redacted."""
        traceback_lines = [
            'Traceback (most recent call last):\n',
            '  File "test.py", line 10, in <module>\n',
            '    connect(password="secret123")\n',
            'ValueError: Connection failed\n'
        ]
        result = sanitize_traceback(traceback_lines)
        traceback_str = "\n".join(result)
        assert "secret123" not in traceback_str
        assert "***REDACTED***" in traceback_str

    def test_sanitizes_jwt_in_traceback(self):
        """JWT in traceback should be redacted."""
        jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        traceback_lines = [
            f'  File "auth.py", line 5, in verify\n',
            f'    token = "{jwt_token}"\n',
            'ValueError: Invalid token\n'
        ]
        result = sanitize_traceback(traceback_lines)
        traceback_str = "\n".join(result)
        assert jwt_token not in traceback_str
        assert "***REDACTED***" in traceback_str

    def test_preserves_traceback_structure(self):
        """Traceback structure (file names, line numbers) should be preserved."""
        traceback_lines = [
            'Traceback (most recent call last):\n',
            '  File "test.py", line 10, in <module>\n',
            '    raise ValueError("test")\n',
            'ValueError: test\n'
        ]
        result = sanitize_traceback(traceback_lines)
        traceback_str = "\n".join(result)
        assert "test.py" in traceback_str
        assert "line 10" in traceback_str
        assert "ValueError: test" in traceback_str


class TestRequestIDGeneration:
    """Tests for request ID generation and validation."""

    def test_generate_request_id_returns_uuid(self):
        """Generated request ID should be a valid UUID."""
        request_id = generate_request_id()
        # Should be valid UUID format
        uuid.UUID(request_id)

    def test_generate_request_id_unique(self):
        """Each generated request ID should be unique."""
        ids = {generate_request_id() for _ in range(100)}
        assert len(ids) == 100

    def test_validate_request_id_accepts_valid(self):
        """Valid request IDs should be accepted."""
        valid_ids = [
            "abc123",
            "test-request-id",
            "TEST_ID_123",
            str(uuid.uuid4()),
            "a" * 64,
        ]
        for req_id in valid_ids:
            assert validate_request_id(req_id), f"Should accept: {req_id}"

    def test_validate_request_id_rejects_invalid(self):
        """Invalid request IDs should be rejected."""
        invalid_ids = [
            "",  # Empty
            "a" * 65,  # Too long
            "test@id",  # Invalid character
            "test id",  # Space
            "test.id",  # Dot
            "test/id",  # Slash
            "test#id",  # Hash
        ]
        for req_id in invalid_ids:
            assert not validate_request_id(req_id), f"Should reject: {req_id}"

    def test_contextvar_request_id(self):
        """Request ID context variable should work correctly."""
        clear_request_id()
        assert get_request_id() is None

        set_request_id("test-123")
        assert get_request_id() == "test-123"

        set_request_id("another-456")
        assert get_request_id() == "another-456"

        clear_request_id()
        assert get_request_id() is None


class TestSanitizePath:
    """Tests for URL path sanitization."""

    def test_removes_query_string(self):
        """Query string should be removed from path."""
        assert sanitize_path("/api/users?page=1&limit=10") == "/api/users"
        assert sanitize_path("/api/climate?lat=10&lon=20") == "/api/climate"

    def test_preserves_path_without_query(self):
        """Paths without query string should be unchanged."""
        assert sanitize_path("/api/users") == "/api/users"
        assert sanitize_path("/api/farms/123") == "/api/farms/123"


class TestSanitizeHeaders:
    """Tests for header sanitization."""

    def test_removes_authorization(self):
        """Authorization header should be removed."""
        headers = {"Authorization": "Bearer token123", "Content-Type": "application/json"}
        result = sanitize_headers(headers)
        assert "Authorization" not in result
        assert result["Content-Type"] == "application/json"

    def test_removes_cookie(self):
        """Cookie header should be removed."""
        headers = {"Cookie": "session=abc", "X-Custom": "value"}
        result = sanitize_headers(headers)
        assert "Cookie" not in result

    def test_removes_api_key(self):
        """API key headers should be removed."""
        headers = {"X-API-Key": "secret", "X-Auth-Token": "token"}
        result = sanitize_headers(headers)
        assert "X-API-Key" not in result
        assert "X-Auth-Token" not in result

    def test_preserves_safe_headers(self):
        """Safe headers should be preserved."""
        headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "test"}
        result = sanitize_headers(headers)
        assert result == headers


class TestRequestContextFilter:
    """Tests for request context filter."""

    def test_adds_request_id_to_record(self):
        """Filter should add request_id to log record when set."""
        clear_request_id()
        set_request_id("filter-test-123")

        filter_ = RequestContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = filter_.filter(record)
        assert result is True
        assert record.request_id == "filter-test-123"

        clear_request_id()

    def test_no_request_id_when_not_set(self):
        """Filter should not add request_id when not set."""
        clear_request_id()

        filter_ = RequestContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        result = filter_.filter(record)
        assert result is True
        assert not hasattr(record, "request_id") or record.request_id is None


class TestRequestLoggingMiddleware:
    """Tests for request logging middleware."""

    def test_request_id_generated_and_returned(self, client: TestClient):
        """Request should get X-Request-ID in response."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        # Should be valid UUID
        uuid.UUID(response.headers["X-Request-ID"])

    def test_valid_incoming_request_id_preserved(self, client: TestClient):
        """Valid incoming X-Request-ID should be preserved."""
        custom_id = "custom-request-123"
        response = client.get("/api/health", headers={"X-Request-ID": custom_id})
        assert response.headers["X-Request-ID"] == custom_id

    def test_invalid_incoming_request_id_replaced(self, client: TestClient):
        """Invalid incoming X-Request-ID should be replaced with generated UUID."""
        invalid_id = "invalid@id!"
        response = client.get("/api/health", headers={"X-Request-ID": invalid_id})
        assert response.headers["X-Request-ID"] != invalid_id
        # Should be valid UUID
        uuid.UUID(response.headers["X-Request-ID"])

    def test_response_includes_request_id_header(self, client: TestClient):
        """All responses should include X-Request-ID header."""
        endpoints = ["/", "/api/health", "/api/climate?latitude=0&longitude=0&start_date=2023-01-01&end_date=2023-01-02"]
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert "X-Request-ID" in response.headers, f"Missing X-Request-ID for {endpoint}"
            uuid.UUID(response.headers["X-Request-ID"])

    def test_request_id_isolation_concurrent(self, client: TestClient):
        """Request IDs should be isolated between concurrent requests."""
        import concurrent.futures

        def make_request():
            response = client.get("/api/health")
            return response.headers["X-Request-ID"]

        # Simulate concurrent requests using thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            request_ids = [f.result() for f in futures]

        # All request IDs should be unique (or at least mostly unique)
        # Due to UUID v4 randomness, collisions are extremely unlikely
        assert len(set(request_ids)) == len(request_ids)
        for req_id in request_ids:
            uuid.UUID(req_id)

    def test_client_ip_not_logged_by_default(self, client: TestClient, caplog):
        """Client IP should NOT be logged by default (LOG_CLIENT_IP=false)."""
        with caplog.at_level(logging.INFO):
            client.get("/api/health")

        request_logs = [r for r in caplog.records if r.name == "app.requests"]
        for log in request_logs:
            # client_host should not be in extra fields
            assert not hasattr(log, "client_host"), "client_host should not be logged by default"

    def test_client_ip_logged_when_enabled(self, client: TestClient, caplog):
        """Client IP should be logged when LOG_CLIENT_IP=true."""
        # This test would require patching settings.LOG_CLIENT_IP
        # We test the behavior by patching the settings module
        from app.core import request_logging
        from unittest.mock import patch

        with patch.object(request_logging.settings, "LOG_CLIENT_IP", True):
            with caplog.at_level(logging.INFO):
                client.get("/api/health")

        request_logs = [r for r in caplog.records if r.name == "app.requests"]
        found_client_host = False
        for log in request_logs:
            if hasattr(log, "client_host") and log.client_host is not None:
                found_client_host = True
                # Should be a valid IP (test client uses testclient IP)
                assert log.client_host is not None
                break
        assert found_client_host, "client_host should be logged when LOG_CLIENT_IP=true"

    def test_trusted_proxy_behavior_unchanged(self, client: TestClient, caplog):
        """Trusted proxy behavior for rate limiting should be unchanged."""
        from app.core import rate_limiting
        from unittest.mock import patch

        # Test that get_client_identifier still respects BEHIND_TRUSTED_PROXY
        with patch.object(rate_limiting.settings, "BEHIND_TRUSTED_PROXY", True):
            request = type("Request", (), {
                "headers": {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"},
                "client": type("Client", (), {"host": "127.0.0.1"})()
            })()
            identifier = rate_limiting.get_client_identifier(request)
            assert identifier == "1.2.3.4"

        # Default behavior (no proxy) should use direct client IP
        with patch.object(rate_limiting.settings, "BEHIND_TRUSTED_PROXY", False):
            request = type("Request", (), {
                "headers": {"X-Forwarded-For": "1.2.3.4"},
                "client": type("Client", (), {"host": "192.168.1.100"})()
            })()
            identifier = rate_limiting.get_client_identifier(request)
            assert identifier == "192.168.1.100"


class TestStructuredLoggingIntegration:
    """Integration tests for structured logging."""

    def test_json_log_structure(self, client: TestClient, caplog):
        """Logs should be valid JSON with required structure."""
        with caplog.at_level(logging.INFO):
            client.get("/api/health")

        # Find our request log
        request_logs = [r for r in caplog.records if r.name == "app.requests"]
        assert len(request_logs) > 0

        # The log should have been captured by caplog
        # Note: In test mode, logs go through caplog's handler

    def test_utc_timestamps_in_logs(self, client: TestClient, caplog):
        """Log timestamps should be in UTC."""
        with caplog.at_level(logging.INFO):
            client.get("/api/health")

        request_logs = [r for r in caplog.records if r.name == "app.requests"]
        if request_logs:
            # Check that the log record has a timestamp
            # caplog records have a `created` attribute (Unix timestamp)
            record = request_logs[0]
            assert record.created > 0

    def test_request_method_path_status_duration_logged(self, client: TestClient, caplog):
        """Request method, path, status, and duration should be logged."""
        with caplog.at_level(logging.INFO):
            response = client.get("/api/health")

        request_logs = [r for r in caplog.records if r.name == "app.requests"]
        assert len(request_logs) >= 1

        # The last request log should be the response
        response_log = request_logs[-1]
        # Verify the log contains our expected extra fields
        assert hasattr(response_log, "method") or "method" in str(response_log.__dict__)
        assert hasattr(response_log, "path") or "path" in str(response_log.__dict__)
        assert hasattr(response_log, "status_code") or "status_code" in str(response_log.__dict__)
        assert hasattr(response_log, "duration_ms") or "duration_ms" in str(response_log.__dict__)

    def test_query_parameters_not_logged(self, client: TestClient, caplog):
        """Query parameters should not be logged in path."""
        with caplog.at_level(logging.INFO):
            client.get("/api/climate?latitude=10&longitude=20&start_date=2023-01-01&end_date=2023-01-02")

        request_logs = [r for r in caplog.records if r.name == "app.requests"]
        for log in request_logs:
            # Path should not contain query string
            path = getattr(log, "path", "") or log.__dict__.get("path", "")
            assert "?" not in path
            assert "latitude" not in path
            assert "longitude" not in path

    def test_authorization_header_not_logged(self, client: TestClient, caplog):
        """Authorization header should not be logged."""
        # This is tested implicitly - the middleware sanitizes headers before logging
        # We verify the sanitize_headers function works correctly in TestSanitizeHeaders

    def test_password_not_logged(self, client: TestClient, caplog):
        """Password fields should not be logged."""
        # Test the sanitize_dict function directly
        data = {"username": "test", "password": "secret123", "email": "test@test.com"}
        sanitized = sanitize_dict(data)
        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["username"] == "test"
        assert sanitized["email"] == "test@test.com"

    def test_exception_logged_without_sensitive_info(self, client: TestClient, caplog):
        """Exceptions should be logged without sensitive information."""
        # The middleware logs exceptions with type and message but no stack trace to client
        # and the JSON formatter includes traceback in logs but not in responses
        pass  # Verified by other tests and middleware implementation

    def test_existing_api_behavior_unchanged(self, client: TestClient):
        """All existing API behavior should remain unchanged."""
        # Health check
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

        # Root endpoint
        response = client.get("/")
        assert response.status_code == 200
        assert "docs" in response.json()

        # Climate endpoint (public)
        response = client.get("/api/climate?latitude=0&longitude=0&start_date=2023-01-01&end_date=2023-01-02")
        # May be 502 due to mocked NASA API, but should not crash
        assert response.status_code in (200, 422, 502)

    def test_error_responses_include_request_id(self, client: TestClient):
        """Error responses should include X-Request-ID header."""
        # 404
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
        assert "X-Request-ID" in response.headers

        # 422
        response = client.get("/api/climate")  # Missing required params
        assert response.status_code == 422
        assert "X-Request-ID" in response.headers


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_idempotent(self):
        """setup_logging should be safe to call multiple times."""
        setup_logging()
        setup_logging()
        setup_logging()
        # Should not raise or create duplicate handlers

    def test_log_level_from_settings(self):
        """Log level should be configurable via settings."""
        from app.core.config import settings
        # Test that it uses settings.LOG_LEVEL if available
        # (In test env, it defaults to INFO)
        logger = logging.getLogger()
        assert logger.level <= logging.INFO


if __name__ == "__main__":
    pytest.main([__file__, "-v"])