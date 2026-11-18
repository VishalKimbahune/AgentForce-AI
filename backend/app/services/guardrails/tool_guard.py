"""Tool parameter validation, path traversal defense, and argument security guardrails."""

import logging
import math
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("guardrails.tool")

# Dangerous path traversal patterns
PATH_TRAVERSAL_PATTERN = re.compile(r"(?:\.\./|\.\.\\|/\.\.|\\\.\.)", re.IGNORECASE)

# Dangerous SQL injection tokens in raw tool parameters
SQL_INJECTION_PATTERN = re.compile(
    r"\b(?:UNION\s+SELECT|DROP\s+TABLE|OR\s+1=1|--|;\s*SHUTDOWN)\b",
    re.IGNORECASE,
)


class ToolGuard:
    """Validates parameters before tool execution to prevent injection and corruption."""

    def validate_parameters(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """Scans tool input parameters for security violations."""
        if not isinstance(params, dict):
            return False, f"Tool parameters must be a dictionary, got {type(params)}"

        # 1. Path traversal check on all string values
        for key, val in params.items():
            if isinstance(val, str):
                if PATH_TRAVERSAL_PATTERN.search(val):
                    logger.warning(
                        "Path traversal attack blocked in tool '%s' param '%s': %s",
                        tool_name,
                        key,
                        val,
                    )
                    return False, f"Path traversal attack detected in parameter '{key}'"

                if SQL_INJECTION_PATTERN.search(val):
                    logger.warning(
                        "SQL injection fragment blocked in tool '%s' param '%s': %s",
                        tool_name,
                        key,
                        val,
                    )
                    return False, f"SQL injection fragment detected in parameter '{key}'"

        # 2. Financial payment guard
        if "payment" in tool_name or "amount" in params:
            amount = params.get("total_amount", params.get("amount"))
            if amount is not None:
                try:
                    amt_float = float(amount)
                    if math.isnan(amt_float) or math.isinf(amt_float):
                        return False, "Invalid payment amount: NaN or Infinity is prohibited"
                    if amt_float < 0:
                        return False, f"Invalid payment amount: negative value ${amt_float:.2f} is prohibited"
                except (ValueError, TypeError):
                    return False, f"Invalid payment amount format: {amount}"

        # 3. Notification recipient check
        if "notification" in tool_name or "recipient" in params:
            recipient = str(params.get("recipient", ""))
            if any(c in recipient for c in ("\r", "\n", "\0", "<script>")):
                return False, f"Malformed recipient header in parameter 'recipient'"

        return True, None


tool_guard = ToolGuard()

