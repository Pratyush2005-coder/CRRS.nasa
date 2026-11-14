"""Structured logging configuration for the FastAPI backend.

Provides centralized JSON log formatting with request correlation IDs,
UTC timestamps, and sensitive data sanitization.
"""

import json
import logging
import re
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.config import settings


# Sensitive field names that should never be logged
SENSITIVE_FIELDS = frozenset({
    "password",
    "hashed_password",
    "secret_key",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "api_key",
    "database_url",
    "connection_string",
    "jwt",
    "token",
    "credential",
    "ssn",
    "social_security",
    "credit_card",
    "cvv",
    "pin",
    "private_key",
    "api_secret",
    "client_secret",
})

# Regex patterns for sanitizing sensitive data in exception messages and tracebacks
SENSITIVE_PATTERNS = [
    # Passwords in various formats
    (re.compile(r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\',}]+)'), r'\1=***REDACTED***'),
    # Bearer tokens / JWTs
    (re.compile(r'(?i)(bearer\s+)([A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+)'), r'\1***REDACTED***'),
    (re.compile(r'(?i)(access_token|refresh_token|id_token)\s*[:=]\s*["\']?([^\s"\',}]+)'), r'\1=***REDACTED***'),
    # API keys
    (re.compile(r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']?([^\s"\',}]+)'), r'\1=***REDACTED***'),
    # Database URLs with credentials
    (re.compile(r'(?i)((?:postgresql|mysql|mongodb|redis)://[^:]+:)([^@]+)(@)'), r'\1***REDACTED***\3'),
    # Generic key=value patterns for sensitive fields
    (re.compile(r'(?i)(secret|key|token|credential)\s*[:=]\s*["\']?([^\s"\',}]+)'), r'\1=***REDACTED***'),
    # Connection strings
    (re.compile(r'(?i)(connection[_-]?string)\s*[:=]\s*["\']?([^\s"\',}]+)'), r'\1=***REDACTED***'),
]


def sanitize_dict(data: dict, max_depth: int = 3, current_depth: int = 0) -> dict:
    """Recursively sanitize a dictionary by redacting sensitive fields.

    Args:
        data: Dictionary to sanitize.
        max_depth: Maximum recursion depth to prevent infinite loops.
        current_depth: Current recursion depth (internal use).

    Returns:
        Sanitized dictionary with sensitive fields redacted.
    """
    if current_depth >= max_depth or not isinstance(data, dict):
        return data

    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
            sanitized[key] = "***REDACTED***"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value, max_depth, current_depth + 1)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_dict(item, max_depth, current_depth + 1)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


def sanitize_exception_message(message: str) -> str:
    """Sanitize sensitive data from exception messages.

    Args:
        message: Exception message string.

    Returns:
        Sanitized message with sensitive values redacted.
    """
    if not message:
        return message

    sanitized = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def sanitize_traceback(traceback_lines: list[str]) -> list[str]:
    """Sanitize sensitive data from traceback lines.

    Args:
        traceback_lines: List of traceback strings from traceback.format_exception.

    Returns:
        Sanitized traceback lines with sensitive values redacted.
    """
    sanitized_lines = []
    for line in traceback_lines:
        sanitized_line = line
        for pattern, replacement in SENSITIVE_PATTERNS:
            sanitized_line = pattern.sub(replacement, sanitized_line)
        sanitized_lines.append(sanitized_line)
    return sanitized_lines


class JSONFormatter(logging.Formatter):
    """JSON log formatter with structured fields and UTC timestamps."""

    def __init__(self, environment: str = "development"):
        super().__init__()
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with consistent structure."""
        # Base log structure
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "environment": self.environment,
        }

        # Add request ID if available in record
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_data["request_id"] = request_id

        # Add extra fields from record
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in {
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "lineno", "funcName", "created",
                "msecs", "relativeCreated", "thread", "threadName",
                "processName", "process", "message", "exc_info", "exc_text",
                "stack_info", "request_id"
            }
        }
        if extra_fields:
            log_data["extra"] = sanitize_dict(extra_fields)

        # Add exception info if present
        if record.exc_info:
            exc_type = record.exc_info[0].__name__ if record.exc_info[0] else "Unknown"
            exc_message = str(record.exc_info[1]) if record.exc_info[1] else ""
            exc_traceback = traceback.format_exception(*record.exc_info)
            log_data["exception"] = {
                "type": exc_type,
                "message": sanitize_exception_message(exc_message),
                "traceback": sanitize_traceback(exc_traceback)
            }

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging() -> None:
    """Configure application-wide structured logging.

    Sets up JSON formatting with UTC timestamps, request correlation,
    and sensitive data sanitization. Safe to call multiple times.
    """
    # Get root logger
    root_logger = logging.getLogger()

    # Set log level from settings (default to INFO)
    log_level = getattr(settings, "LOG_LEVEL", "INFO")
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Create JSON formatter
    formatter = JSONFormatter(environment=settings.ENVIRONMENT)

    # Check if we already have a JSON formatter handler (avoid duplicates)
    has_json_handler = any(
        isinstance(h.formatter, JSONFormatter) for h in root_logger.handlers if h.formatter
    )

    if not has_json_handler:
        # Console handler with JSON formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(root_logger.level)
        root_logger.addHandler(console_handler)

    # Add RequestContextFilter to inject request IDs (only once)
    has_request_filter = any(
        isinstance(f, RequestContextFilter) for f in root_logger.filters
    )
    if not has_request_filter:
        root_logger.addFilter(RequestContextFilter())

    # Prevent propagation to avoid duplicate logs
    root_logger.propagate = False

    # Silence noisy third-party loggers in production
    if settings.ENVIRONMENT == "production":
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Log configuration confirmation
    logger = logging.getLogger(__name__)
    logger.info("Structured logging configured", extra={"log_level": log_level, "environment": settings.ENVIRONMENT})


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)


# Context variable for request correlation ID
import contextvars
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    """Get the current request correlation ID.

    Returns:
        Current request ID if set, None otherwise.
    """
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set the current request correlation ID.

    Args:
        request_id: Request ID to set for the current context.
    """
    request_id_var.set(request_id)


def clear_request_id() -> None:
    """Clear the current request correlation ID."""
    request_id_var.set(None)


class RequestContextFilter(logging.Filter):
    """Logging filter that injects request ID into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add request ID to log record if available."""
        request_id = get_request_id()
        if request_id:
            record.request_id = request_id
        return True