"""Prompt injection detection and neutralization guardrails against direct and indirect adversarial attacks."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("guardrails.injection")

# Compiled regular expressions for direct prompt injection and jailbreak signatures
DIRECT_INJECTION_PATTERNS = [
    # System override directives
    (
        re.compile(r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+)?(?:previous|prior|above|existing|system)\s+(?:instructions|prompts|rules|commands|constraints|directives)\b", re.IGNORECASE),
        "directive_override",
        0.98,
    ),
    # System prompt extraction / leaks
    (
        re.compile(r"\b(?:reveal|print|display|output|show|repeat)\s+(?:your\s+)?(?:system\s+prompt|developer\s+mode\s+prompt|initial\s+instructions|base\s+instructions)\b", re.IGNORECASE),
        "system_prompt_leak",
        0.95,
    ),
    # Role-play jailbreaks (DAN, Developer Mode, AIM, Unrestricted AI)
    (
        re.compile(r"\b(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+(?:in\s+)?(?:developer\s+mode|dan|jailbreak|unrestricted|god\s+mode|root|an\s+ai\s+without\s+rules|unfiltered)\b", re.IGNORECASE),
        "roleplay_jailbreak",
        0.95,
    ),
    # Guardrail and safety bypass directives
    (
        re.compile(r"\b(?:bypass|disable|turn\s+off|skip|override)\s+(?:all\s+)?(?:guardrails|safety\s+filters|policy\s+engine|approval\s+checks|security\s+controls)\b", re.IGNORECASE),
        "safety_bypass",
        0.96,
    ),
    # Delimiter and system boundary spoofing
    (
        re.compile(r"(?:---\s*(?:BEGIN|START)\s+(?:SYSTEM|ADMIN|ROOT)\s+(?:PROMPT|INSTRUCTION|OVERRIDE)\s*---|\[SYSTEM\s*(?:INSTRUCTION|OVERRIDE|DIRECTIVE)\])", re.IGNORECASE),
        "delimiter_spoofing",
        0.99,
    ),
    # Autonomous destructive commands embedded directly
    (
        re.compile(r"\b(?:delete|drop|purge|truncate)\s+(?:all\s+)?(?:database\s+records|users|organizations|audit\s+logs|tables)\b", re.IGNORECASE),
        "destructive_command_injection",
        0.92,
    ),
]

# Patterns for indirect prompt injection hidden inside uploaded resumes or invoices
INDIRECT_DOCUMENT_INJECTION_PATTERNS = [
    (
        re.compile(r"\[SYSTEM\s*(?:OVERRIDE|INSTRUCTION|DIRECTIVE)?\]:?.*?(?:give\s+(?:this\s+)?candidate|rank\s+(?:this\s+)?candidate|score\s+(?:this\s+)?candidate|hire\s+immediately|approve\s+payment)", re.IGNORECASE),
        "document_hidden_instruction",
        0.98,
    ),
    (
        re.compile(r"(?:ignore\s+(?:all\s+)?(?:prior|evaluation|ranking|screening)\s+(?:rules|criteria|instructions)|give\s+(?:this\s+)?candidate\s+(?:a\s+)?100%?\s+score)", re.IGNORECASE),
        "document_evaluation_hijack",
        0.95,
    ),
    (
        re.compile(r"<!--\s*(?:admin_command|system_override|hidden_instruction).*?-->", re.IGNORECASE | re.DOTALL),
        "html_comment_injection",
        0.97,
    ),
]


class InjectionCheckResult(BaseModel):
    """Result of prompt injection security scan."""

    is_injection: bool = False
    confidence: float = 0.0
    matched_patterns: List[str] = Field(default_factory=list)
    category: str = "clean"
    risk_level: str = "low"  # low | medium | high | critical
    detail: str = "Prompt passed security guardrail validation."
    sanitized_text: Optional[str] = None


class PromptInjectionGuard:
    """Security guard detecting and blocking adversarial prompt injection attempts."""

    def scan(self, text: str, is_document: bool = False) -> InjectionCheckResult:
        """Analyzes text for adversarial injection attempts."""
        if not text or not text.strip():
            return InjectionCheckResult()

        matched: List[str] = []
        max_confidence = 0.0
        primary_category = "clean"

        # 1. Direct prompt injection scan
        for pattern, cat, confidence in DIRECT_INJECTION_PATTERNS:
            if pattern.search(text):
                matched.append(cat)
                if confidence > max_confidence:
                    max_confidence = confidence
                    primary_category = cat

        # 2. Indirect document injection scan
        if is_document or not matched:
            for pattern, cat, confidence in INDIRECT_DOCUMENT_INJECTION_PATTERNS:
                if pattern.search(text):
                    matched.append(cat)
                    if confidence > max_confidence:
                        max_confidence = confidence
                        primary_category = cat

        if matched:
            risk = "critical" if max_confidence >= 0.95 else "high"
            logger.warning(
                "Prompt injection detected! Category: %s, Confidence: %.2f, Matches: %s",
                primary_category,
                max_confidence,
                matched,
            )
            return InjectionCheckResult(
                is_injection=True,
                confidence=round(max_confidence, 2),
                matched_patterns=matched,
                category=primary_category,
                risk_level=risk,
                detail=f"Blocked prompt injection attack: detected '{primary_category}' signature.",
            )

        return InjectionCheckResult()

    def sanitize_document(self, text: str) -> Tuple[str, bool, List[str]]:
        """Removes or neutralizes adversarial prompt injection segments from documents."""
        if not text:
            return text, False, []

        sanitized = text
        injections_found: List[str] = []

        # Remove indirect injection blocks from text
        for pattern, cat, _ in INDIRECT_DOCUMENT_INJECTION_PATTERNS:
            if pattern.search(sanitized):
                injections_found.append(cat)
                sanitized = pattern.sub("[ADVERSARIAL_INSTRUCTION_REMOVED]", sanitized)

        # Also remove direct overrides if embedded inside document
        for pattern, cat, _ in DIRECT_INJECTION_PATTERNS:
            if pattern.search(sanitized):
                injections_found.append(cat)
                sanitized = pattern.sub("[ADVERSARIAL_DIRECTIVE_REMOVED]", sanitized)

        was_sanitized = len(injections_found) > 0
        if was_sanitized:
            logger.warning("Sanitized indirect document injection: %s", injections_found)

        return sanitized, was_sanitized, injections_found


prompt_injection_guard = PromptInjectionGuard()

