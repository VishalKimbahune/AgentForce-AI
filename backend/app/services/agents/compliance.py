"""Compliance AI Employee: audits workflow actions against enterprise policy documents."""

import logging
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.knowledge import knowledge_agent
from app.services.memory.qdrant import qdrant_service

logger = logging.getLogger("agent.compliance")


class ComplianceAgent:
    """Specialized AI Employee checking workforce actions against corporate policies."""

    async def verify_action(
        self,
        action_type: str,
        action_payload: Dict[str, Any],
        tenant_id: str,
        role: str = "auditor",
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Audits an action against uploaded policy documents."""
        query = f"Policy rules and requirements for {action_type}"
        search_res = await knowledge_agent.answer_question(
            query=query,
            tenant_id=tenant_id,
            role=role,
            db=db,
            top_k=3,
        )

        has_policies = search_res["chunks_used"] > 0
        citations = search_res.get("citations", [])

        # Compliance checks
        if action_type in ("send_external_email", "schedule_interview"):
            is_compliant = True
            requires_approval = True
            reason = "External candidate communication requires department manager review"
        elif action_type == "payment":
            amount = float(action_payload.get("amount", 0))
            is_compliant = amount <= 100000
            requires_approval = amount > 1000
            reason = f"Payment of ${amount:.2f} requires approval threshold check"
        else:
            is_compliant = True
            requires_approval = False
            reason = "Action adheres to standard operational parameters"

        return {
            "action_type": action_type,
            "is_compliant": is_compliant,
            "requires_approval": requires_approval,
            "reason": reason,
            "policy_citations": citations,
            "policy_context": search_res.get("answer", "") if has_policies else "Default organization baseline policy applied",
        }


compliance_agent = ComplianceAgent()

