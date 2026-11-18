"""Structured logging with correlation IDs and sensitive data protection."""

import logging
import re
import sys
from typing import Any
from app.core.correlation import correlation_id


# Basic regex patterns for sensitive tokens/keys/passwords
SENSITIVE_PATTERNS = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(['\"]?password['\"]?\s*[:=]\s*['\"])[^'\"]+(['\"])", re.IGNORECASE), r"\1[REDACTED]\2"),
    (re.compile(r"(['\"]?secret['\"]?\s*[:=]\s*['\"])[^'\"]+(['\"])", re.IGNORECASE), r"\1[REDACTED]\2"),
    (re.compile(r"(['\"]?api_?key['\"]?\s*[:=]\s*['\"])[^'\"]+(['\"])", re.IGNORECASE), r"\1[REDACTED]\2"),
]


class CorrelationFilter(logging.Filter):
    """Filter that injects the correlation_id into the log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        cid = correlation_id.get()
        record.correlation_id = cid or "-"
        return True


class PIIRedactingFormatter(logging.Formatter):
    """Formatter that redacts common sensitive values from log output."""

    def format(self, record: logging.LogRecord) -> str:
        orig = super().format(record)
        redacted = orig
        for pattern, replacement in SENSITIVE_PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted


def setup_logging(log_level: str = "INFO") -> None:
    """Configures root and app loggers."""
    log_format = "%(asctime)s [%(levelname)s] [corr_id:%(correlation_id)s] %(name)s - %(message)s"
    formatter = PIIRedactingFormatter(fmt=log_format, datefmt="%Y-%m-%d %H:%M:%S")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(CorrelationFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Clear existing handlers to avoid duplicates
    root_logger.handlers = [handler]

    # Less noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
