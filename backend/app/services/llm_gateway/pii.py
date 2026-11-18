"""PII masking utilities for LLM prompts, completions, and trace logging."""

import re

# Comprehensive regex patterns for PII detection
PII_PATTERNS = [
    # Emails
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"), "[EMAIL_REDACTED]"),
    # Credit Card numbers (13 to 19 digits with optional hyphens/spaces)
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "[CARD_REDACTED]"),
    # US Social Security Numbers (XXX-XX-XXXX)
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN_REDACTED]"),
    # Phone numbers (international, US, and local formats)
    (re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b"), "[PHONE_REDACTED]"),
    # Bearer tokens & API Keys
    (re.compile(r"\b(?:sk-[a-zA-Z0-9_\-]{20,}|gsk_[a-zA-Z0-9_\-]{20,}|AQ\.[a-zA-Z0-9_\-]{20,})\b"), "[KEY_REDACTED]"),
]


def mask_pii(text: str) -> str:
    """Masks personally identifiable information from strings prior to logging."""
    if not text:
        return text

    masked = text
    for pattern, replacement in PII_PATTERNS:
        masked = pattern.sub(replacement, masked)
    return masked

