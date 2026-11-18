"""Output schema validation, JSON sanitization, and hallucination defense guardrails."""

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple, Type
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("guardrails.output")

# Regex to strip unsafe scripts and dangerous executable HTML tags
UNSAFE_HTML_PATTERN = re.compile(
    r"<\s*(?:script|iframe|object|embed|style|svg\s+onload|img\s+onerror).*?>.*?(?:<\s*/\s*(?:script|iframe|object|embed|style)\s*>)?",
    re.IGNORECASE | re.DOTALL,
)


class OutputValidationResult(BaseModel):
    is_valid: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    sanitized: bool = False


class OutputGuard:
    """Validates LLM and agent JSON output against strict Pydantic schemas."""

    def extract_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """Extracts JSON from text, accommodating markdown code fences if present."""
        if not raw_text:
            return None

        clean = raw_text.strip()

        # Handle ```json ... ``` blocks
        if "```" in clean:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
            if match:
                clean = match.group(1).strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            logger.debug("Failed to decode JSON from text: %s", str(e))
            return None

    def validate_schema(
        self,
        raw_output: Any,
        schema_cls: Type[BaseModel],
    ) -> OutputValidationResult:
        """Validates output against a target Pydantic schema."""
        data_dict: Optional[Dict[str, Any]] = None

        if isinstance(raw_output, str):
            data_dict = self.extract_json(raw_output)
            if data_dict is None:
                return OutputValidationResult(
                    is_valid=False,
                    error="Malformed JSON output: could not parse into valid JSON object",
                )
        elif isinstance(raw_output, dict):
            data_dict = raw_output
        elif isinstance(raw_output, BaseModel):
            data_dict = raw_output.model_dump()
        else:
            return OutputValidationResult(
                is_valid=False,
                error=f"Unsupported output type: {type(raw_output)}",
            )

        try:
            validated_obj = schema_cls.model_validate(data_dict)
            return OutputValidationResult(
                is_valid=True,
                data=validated_obj.model_dump(),
            )
        except ValidationError as val_err:
            error_details = "; ".join(f"{err['loc']}: {err['msg']}" for err in val_err.errors())
            logger.warning("Output schema validation failed: %s", error_details)
            return OutputValidationResult(
                is_valid=False,
                error=f"Output schema mismatch: {error_details}",
            )

    def sanitize_text(self, text: str) -> Tuple[str, bool]:
        """Strips dangerous executable scripts and malicious markup."""
        if not text:
            return text, False

        cleaned = UNSAFE_HTML_PATTERN.sub("[UNSAFE_SCRIPT_REMOVED]", text)
        was_sanitized = cleaned != text
        return cleaned, was_sanitized


output_guard = OutputGuard()

