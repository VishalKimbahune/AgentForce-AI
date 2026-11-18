"""Deterministic policy engine enforcing enterprise rules, authorization boundaries, and human-in-the-loop approvals."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.core.dependencies import ROLES_HIERARCHY
from app.services.guardrails import security_logger


class PolicyEffect(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class PolicyEvaluation(BaseModel):
    effect: PolicyEffect
    reason: str
    required_role: str = "manager"
    level: int = 1
    risk_level: str = "medium"  # low | medium | high | critical


class PolicyContext(BaseModel):
    tenant_id: str
    user_role: str = "member"
    agent: str
    action_type: str
    params: Dict[str, Any] = Field(default_factory=dict)
    amount: Optional[float] = None
    recipient_domain: Optional[str] = None
    allowed_roles: Optional[List[str]] = None


class PolicyEngine:
    """Pure-code deterministic policy engine implementing rules from docs/06 Section 8."""

    def evaluate(self, ctx: PolicyContext) -> PolicyEvaluation:
        action = ctx.action_type.lower()
        agent = ctx.agent.lower()
        role = ctx.user_role.lower()

        # -------------------------------------------------------------
        # Rule 1: payment.execute
        # Always require approval (finance manager); deny if agent is not Finance
        # -------------------------------------------------------------
        if action == "payment.execute" or action == "payment":
            if "finance" not in agent and agent != "orchestrator":
                security_logger.record_incident(
                    event_type="security.unauthorized_payment_attempt",
                    threat_category="unauthorized_agent_disbursement",
                    risk_level="high",
                    detail=f"Unauthorized agent '{agent}' attempted to trigger payment execution",
                    tenant_id=ctx.tenant_id,
                    payload_sample=ctx.params,
                )
                return PolicyEvaluation(
                    effect=PolicyEffect.DENY,
                    reason="Unauthorized agent: Only Finance AI Employee can request payment execution",
                    risk_level="high",
                )
            amount = ctx.amount or ctx.params.get("amount", 0.0)
            risk = "critical" if amount > 50000 else "high"
            return PolicyEvaluation(
                effect=PolicyEffect.REQUIRE_APPROVAL,
                reason=f"Payment execution of ${amount:.2f} requires mandatory Finance Manager approval",
                required_role="manager",
                level=2 if amount > 10000 else 1,
                risk_level=risk,
            )

        # -------------------------------------------------------------
        # Rule 2: email.send_external / interview.send_invitation
        # Require approval when recipients are outside org domain or scheduling candidate interviews
        # -------------------------------------------------------------
        if action in ("email.send_external", "interview.send_invitation", "interview.schedule"):
            recipient_domain = ctx.recipient_domain or ctx.params.get("recipient_domain")
            is_external = recipient_domain not in ("acme.com", "company.internal", "localhost")
            candidate_count = len(ctx.params.get("candidates", []))

            if is_external or candidate_count > 0:
                return PolicyEvaluation(
                    effect=PolicyEffect.REQUIRE_APPROVAL,
                    reason="External candidate communication and interview invitations require Department Manager approval",
                    required_role="manager",
                    level=1,
                    risk_level="medium",
                )
            return PolicyEvaluation(
                effect=PolicyEffect.ALLOW,
                reason="Internal communication allowed without approval",
            )

        # -------------------------------------------------------------
        # Rule 2b: report.distribute
        # Require approval (Operations/Department Manager or Owner) to distribute executive reports
        # -------------------------------------------------------------
        if action in ("report.distribute", "report.send_to_leadership"):
            return PolicyEvaluation(
                effect=PolicyEffect.REQUIRE_APPROVAL,
                reason="Distributing executive business reports to leadership requires Department Head approval",
                required_role="manager",
                level=1,
                risk_level="medium",
            )

        # -------------------------------------------------------------
        # Rule 3: record.delete
        # Require approval (admin/owner)
        # -------------------------------------------------------------
        if action == "record.delete":
            return PolicyEvaluation(
                effect=PolicyEffect.REQUIRE_APPROVAL,
                reason="Permanent record deletion requires Organization Owner/Admin authorization",
                required_role="owner",
                level=2,
                risk_level="high",
            )

        # -------------------------------------------------------------
        # Rule 4: employee_record.update
        # Require approval (HR manager)
        # -------------------------------------------------------------
        if action == "employee_record.update":
            return PolicyEvaluation(
                effect=PolicyEffect.REQUIRE_APPROVAL,
                reason="Modifications to employee personnel records require HR Manager sign-off",
                required_role="manager",
                level=1,
                risk_level="medium",
            )

        # -------------------------------------------------------------
        # Rule 5: refund.issue
        # Require approval above configured amount ($500)
        # -------------------------------------------------------------
        if action == "refund.issue":
            amount = ctx.amount or ctx.params.get("amount", 0.0)
            if amount > 500.0:
                return PolicyEvaluation(
                    effect=PolicyEffect.REQUIRE_APPROVAL,
                    reason=f"Customer refund of ${amount:.2f} exceeds auto-approval threshold ($500.00)",
                    required_role="manager",
                    level=1,
                    risk_level="medium",
                )
            return PolicyEvaluation(
                effect=PolicyEffect.ALLOW,
                reason=f"Refund under $500.00 auto-approved",
            )

        # -------------------------------------------------------------
        # Rule 6: infra.change
        # Deny anything touching IAM or security controls; require approval otherwise
        # -------------------------------------------------------------
        if action == "infra.change":
            target = str(ctx.params.get("target", "")).lower()
            if any(forbidden in target for forbidden in ("iam", "security", "firewall", "credentials", "keys")):
                return PolicyEvaluation(
                    effect=PolicyEffect.DENY,
                    reason="Autonomous modifications to IAM policies and security controls are strictly prohibited",
                    risk_level="critical",
                )
            return PolicyEvaluation(
                effect=PolicyEffect.REQUIRE_APPROVAL,
                reason=f"Infrastructure change to {target} requires Lead Architect review",
                required_role="owner",
                level=2,
                risk_level="high",
            )

        # -------------------------------------------------------------
        # Rule 7: document.read
        # Allow only if user role in allowed_roles
        # -------------------------------------------------------------
        if action == "document.read":
            allowed = ctx.allowed_roles or ctx.params.get("allowed_roles", [])
            user_rank = ROLES_HIERARCHY.get(role, 0)
            if role == "owner":
                return PolicyEvaluation(effect=PolicyEffect.ALLOW, reason="Owner has global read permission")
            if role in allowed:
                return PolicyEvaluation(effect=PolicyEffect.ALLOW, reason="Role permitted by document ACL")
            security_logger.record_incident(
                event_type="security.unauthorized_access_attempt",
                threat_category="document_acl_violation",
                risk_level="high",
                detail=f"User role '{role}' is not in allowed document roles: {allowed}",
                tenant_id=ctx.tenant_id,
            )
            return PolicyEvaluation(
                effect=PolicyEffect.DENY,
                reason=f"User role '{role}' is not in allowed document roles: {allowed}",
                risk_level="high",
            )

        # Default fallback: allow standard internal queries
        return PolicyEvaluation(
            effect=PolicyEffect.ALLOW,
            reason="Action conforms to standard operational workforce policy",
        )


policy_engine = PolicyEngine()

