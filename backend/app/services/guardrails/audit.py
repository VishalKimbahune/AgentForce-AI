"""Security audit logger and incident tracking for guardrail violations."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("guardrails.audit")

# In-memory security incidents store for telemetry and automated red-team verification
SECURITY_INCIDENTS: List[Dict[str, Any]] = []


class SecurityIncident(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    correlation_id: Optional[str] = None
    threat_category: str
    risk_level: str  # low | medium | high | critical
    detail: str
    blocked: bool = True
    payload_sample: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SecurityAuditLogger:
    """Records blocked attacks, security violations, and red-team attempts."""

    def record_incident(
        self,
        event_type: str,
        threat_category: str,
        risk_level: str,
        detail: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        payload_sample: Optional[Dict[str, Any]] = None,
    ) -> SecurityIncident:
        incident = SecurityIncident(
            event_type=event_type,
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=correlation_id,
            threat_category=threat_category,
            risk_level=risk_level,
            detail=detail,
            blocked=True,
            payload_sample=payload_sample,
        )
        data = incident.model_dump()
        SECURITY_INCIDENTS.append(data)

        logger.warning(
            "SECURITY GUARDRAIL BLOCKED: [%s] Category=%s, Risk=%s, Tenant=%s - %s",
            event_type,
            threat_category,
            risk_level,
            tenant_id or "global",
            detail,
        )
        return incident

    def get_incidents(
        self,
        tenant_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries logged security incidents with optional filters."""
        results = SECURITY_INCIDENTS
        if tenant_id:
            results = [i for i in results if i.get("tenant_id") == tenant_id]
        if event_type:
            results = [i for i in results if i.get("event_type") == event_type]
        return results


security_logger = SecurityAuditLogger()

