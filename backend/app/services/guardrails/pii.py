"""Personally Identifiable Information (PII) scanning and masking guardrails."""

import logging
import re
from typing import Dict, List, Optional
from pydantic import BaseModel

logger = logging.getLogger("guardrails.pii")

# Comprehensive regex patterns for PII detection and redaction
PII_RULES = [
    (
        "EMAIL",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
        "[EMAIL_REDACTED]",
    ),
    (
        "CREDIT_CARD",
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        "[CARD_REDACTED]",
    ),
    (
        "SSN",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[SSN_REDACTED]",
    ),
    (
        "PHONE",
        re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b"),
        "[PHONE_REDACTED]",
    ),
    (
        "API_KEY",
        re.compile(r"\b(?:sk-[a-zA-Z0-9_\-]{20,}|gsk_[a-zA-Z0-9_\-]{20,}|AQ\.[a-zA-Z0-9_\-]{20,})\b"),
        "[KEY_REDACTED]",
    ),
    (
        "BANK_ACCOUNT",
        re.compile(r"\b(?:IBAN|ACCOUNT|ROUTING)[:\s]+[A-Z0-9]{8,24}\b", re.IGNORECASE),
        "[ACCOUNT_REDACTED]",
    ),
]


class PIIEntity(BaseModel):
    category: str
    redacted_as: str
    count: int = 1


class PIIGuard:
    """Detects and redacts PII before prompts, completions, and logs are persisted or transmitted."""

    def mask(self, text: str) -> str:
        """Redacts all detected PII patterns from text."""
        if not text:
            return text

        masked = text
        for _, pattern, replacement in PII_RULES:
            masked = pattern.sub(replacement, masked)
        return masked

    def scan(self, text: str) -> List[PIIEntity]:
        """Scans text and returns inventory of detected PII categories."""
        if not text:
            return []

        results: List[PIIEntity] = []
        for cat, pattern, repl in PII_RULES:
            matches = pattern.findall(text)
            if matches:
                results.append(
                    PIIEntity(
                        category=cat,
                        redacted_as=repl,
                        count=len(matches),
                    )
                )
        return results

    def contains_pii(self, text: str) -> bool:
        """Checks if text contains any PII entities."""
        if not text:
            return False
        return any(pattern.search(text) for _, pattern, _ in PII_RULES)


pii_guard = PIIGuard()
mask_pii = pii_guard.mask

