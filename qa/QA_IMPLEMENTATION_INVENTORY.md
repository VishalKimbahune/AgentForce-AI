# QA Implementation Inventory: AgentForce AI

**Generated At:** 2026-11-11  
**Repository State:** Complete Build (Phases 0 through 10)  
**Standard Categories:** Implemented, Partial, Mocked, Missing, Blocked

---

## 1. Product Screens Inventory (Docs 02 & 05)

| Screen # | Name / Purpose | Frontend File & Route | Associated API Routes | Database Models | Status | Notes / Stubs |
|---|---|---|---|---|---|---|
| **1** | **Login and Org Setup** | `frontend/app/(auth)/login/page.tsx` (`/login`) | `POST /api/v1/auth/demo-login`, `POST /auth/complete-profile` | `User`, `Organization`, `Membership` | **Implemented** | Supabase auth integration with 1-click local demo session fallback. |
| **2** | **Dashboard Overview** | `frontend/app/dashboard/page.tsx` (`/dashboard`) | `GET /api/v1/analytics/tokens`, `GET /api/v1/workflows` | `Workflow`, `ApprovalRequest` | **Implemented** | High-level KPI summary, token burn metrics, quick workflow launcher. |
| **3** | **AI Employees Roster** | `frontend/app/employees/page.tsx` (`/employees`) | `GET /api/v1/agents`, `PATCH /api/v1/agents/{id}` | `Agent` | **Implemented** | Displays installed AI Employees (HR, Finance, Ops, AIOps) with active/paused status. |
| **4** | **Agent Marketplace** | `frontend/app/employees/page.tsx` (Marketplace tab) | `GET /api/v1/marketplace/templates`, `POST /api/v1/marketplace/templates/{id}/install` | `AgentTemplate`, `Agent` | **Implemented** | 6 pre-configured templates with 1-click tenant workspace installation. |
| **5** | **Employee Configuration** | `frontend/app/employees/page.tsx` (Config drawer) | `PATCH /api/v1/agents/{id}` | `Agent` | **Implemented** | Model policy override, status toggle, system prompt customization. |
| **6** | **Assign Work (Intake)** | `frontend/app/workflows/page.tsx` (`/workflows`) | `POST /api/v1/workflows`, `GET /api/v1/workflows` | `Workflow`, `WorkflowTask` | **Implemented** | Text prompt intake, file attachments, quick prompt pills. |
| **7** | **Workflow Builder** | `frontend/app/workflows/page.tsx` | `POST /api/v1/workflows` | `Workflow`, `WorkflowTask` | **Implemented** | Autonomous decomposition via LangGraph Planner node. |
| **8** | **Live Workflow Execution** | `frontend/app/workflows/[id]/page.tsx` (`/workflows/[id]`) | `GET /api/v1/workflows/{id}`, `GET /api/v1/workflows/{id}/events` (SSE) | `Workflow`, `WorkflowCheckpoint`, `AgentMessage` | **Implemented** | Real-time SSE timeline stream broadcasting node transitions. |
| **9** | **Agent Traces & Debug** | `frontend/app/workflows/[id]/page.tsx` (Traces tab) | `GET /api/v1/workflows/{id}` | `WorkflowCheckpoint`, `ToolExecution` | **Implemented** | Message-by-message execution trace, tool execution details, token costs. |
| **10** | **Approval Center (HITL)** | `frontend/app/approvals/page.tsx` (`/approvals`) | `GET /api/v1/approvals`, `POST /api/v1/approvals/{id}/approve`, `POST /api/v1/approvals/{id}/reject` | `ApprovalRequest` | **Implemented** | Human-in-the-loop review card, risk level badge, role hierarchy validation. |
| **11** | **Knowledge Base (RAG)** | `frontend/app/knowledge/page.tsx` (`/knowledge`) | `POST /api/v1/documents`, `GET /api/v1/knowledge/search` | `Document`, `DocumentChunk` | **Implemented** | Multipart PDF/DOCX ingestion, token chunking, Qdrant vector search. |
| **12** | **LLM Analytics** | `frontend/app/analytics/page.tsx` (`/analytics`) | `GET /api/v1/analytics/tokens`, `GET /api/v1/analytics/costs` | `Workflow` | **Implemented** | Cost estimation, token breakdown by model, latency distributions. |
| **13** | **Agent Observability** | `frontend/app/analytics/page.tsx` | `GET /metrics` | In-memory OTel Spans | **Implemented** | Prometheus metric exposition (`agentforce_llm_requests_total`, latencies). |
| **14** | **AIOps Self-Healing** | `frontend/app/aiops/page.tsx` (`/aiops`) | `GET /api/v1/aiops/incidents`, `POST /api/v1/aiops/simulate-failure`, `POST /api/v1/aiops/incidents/{id}/remediate` | `AIOpsIncident`, `ApprovalRequest` | **Implemented** | Autonomous anomaly detection, root-cause hypothesis, governed remediation. |
| **15** | **Compliance Audit Trail** | `frontend/app/audit-logs/page.tsx` (`/audit-logs`) | `GET /api/v1/audit-logs`, `GET /api/v1/audit-logs?export=csv` | `AuditLog` | **Implemented** | Filterable audit logs with streaming RFC 4180 CSV export. |
| **16** | **Integrations Center** | `frontend/app/integrations/page.tsx` (`/integrations`) | `GET /api/v1/integrations` | `mock_erp`, `mock_ats` | **Mocked (By Design)** | Local deterministic mock connectors for ERP, ATS, Calendar, and Payments. |
| **17** | **Voice Assistant** | `frontend/app/voice/page.tsx` (`/voice`) | `POST /api/v1/voice/speak`, `WS /api/v1/voice/stream` | `VoiceSession` | **Implemented** | VAD energy detection, Faster-Whisper STT on CPU int8, Edge-TTS synthesis. |
| **18** | **Settings & Budgets** | `frontend/app/settings/page.tsx` (`/settings`) | `GET /api/v1/organizations`, `PATCH /api/v1/organizations` | `Organization`, `Membership`, `ApiKey` | **Implemented** | Daily token budget controls, member role listing, monochrome theme toggle. |

---

## 2. Backend REST API Routes Inventory (`backend/app/api/v1/`)

| Method | Endpoint Path | Source Handler File | Description & Authorization | Status |
|---|---|---|---|---|
| `GET` | `/health` | `app/api/v1/health.py` | Top-level health probe with version & correlation ID | **Implemented** |
| `GET` | `/ready` | `app/api/v1/health.py` | Readiness probe checking DB, Redis, and Qdrant readiness | **Implemented** |
| `GET` | `/metrics` | `app/main.py` | Prometheus exposition endpoint for operational scrapers | **Implemented** |
| `GET` | `/api/v1/me` | `app/api/v1/auth.py` | Returns caller identity, memberships, and roles | **Implemented** |
| `POST` | `/api/v1/auth/complete-profile` | `app/api/v1/auth.py` | Completes workspace registration upon initial signup | **Implemented** |
| `POST` | `/api/v1/auth/demo-login` | `app/api/v1/auth.py` | Signs in pre-seeded demo personas without cloud Supabase | **Implemented** |
| `GET` | `/api/v1/organizations` | `app/api/v1/org.py` | Returns tenant organization profile and daily budget | **Implemented** |
| `GET` | `/api/v1/organizations/members` | `app/api/v1/org.py` | Lists team members and assigned RBAC roles | **Implemented** |
| `POST` | `/api/v1/workflows` | `app/api/v1/workflows.py` | Submits new autonomous workflow task for intake | **Implemented** |
| `GET` | `/api/v1/workflows` | `app/api/v1/workflows.py` | Lists workflows strictly filtered by caller tenant ID | **Implemented** |
| `GET` | `/api/v1/workflows/{id}` | `app/api/v1/workflows.py` | Returns workflow details, task nodes, and checkpoint state | **Implemented** |
| `GET` | `/api/v1/workflows/{id}/events`| `app/api/v1/workflows.py` | Server-Sent Events stream for real-time timeline updates | **Implemented** |
| `POST` | `/api/v1/workflows/{id}/cancel`| `app/api/v1/workflows.py` | Cancels in-flight workflow and prevents downstream tool calls | **Implemented** |
| `POST` | `/api/v1/documents` | `app/api/v1/documents.py` | Multipart upload for PDF, DOCX, and TXT policy documents | **Implemented** |
| `GET` | `/api/v1/documents` | `app/api/v1/documents.py` | Lists ingested documents in tenant repository | **Implemented** |
| `GET` | `/api/v1/knowledge/search` | `app/api/v1/knowledge.py` | Semantic vector search in Qdrant with tenant & role filter | **Implemented** |
| `GET` | `/api/v1/approvals` | `app/api/v1/approvals.py` | Lists pending approval requests for caller tenant | **Implemented** |
| `POST` | `/api/v1/approvals/{id}/approve` | `app/api/v1/approvals.py` | Approves request with role hierarchy validation & resumes graph | **Implemented** |
| `POST` | `/api/v1/approvals/{id}/reject` | `app/api/v1/approvals.py` | Rejects pending action with audit note | **Implemented** |
| `GET` | `/api/v1/integrations` | `app/api/v1/integrations.py` | Returns status of local mock services (ERP, ATS, CRM) | **Implemented** |
| `POST` | `/api/v1/voice/speak` | `app/api/v1/voice.py` | Edge-TTS streaming MP3 synthesis endpoint | **Implemented** |
| `WS` | `/api/v1/voice/stream` | `app/api/v1/voice.py` | WebSocket streaming speech transcription & synthesis | **Implemented** |
| `GET` | `/api/v1/aiops/incidents` | `app/api/v1/aiops.py` | Lists detected operational anomalies and incidents | **Implemented** |
| `POST` | `/api/v1/aiops/simulate-failure` | `app/api/v1/aiops.py` | Simulates an ATS failure to test auto-diagnosis | **Implemented** |
| `POST` | `/api/v1/aiops/incidents/{id}/remediate` | `app/api/v1/aiops.py` | Requests governed remediation for operational incident | **Implemented** |
| `GET` | `/api/v1/marketplace/templates` | `app/api/v1/marketplace.py`| Lists pre-configured AI Employee templates | **Implemented** |
| `POST` | `/api/v1/marketplace/templates/{id}/install` | `app/api/v1/marketplace.py` | Provisions agent into tenant roster | **Implemented** |
| `GET` | `/api/v1/agents` | `app/api/v1/marketplace.py`| Lists installed AI Employees for tenant | **Implemented** |
| `PATCH`| `/api/v1/agents/{id}` | `app/api/v1/marketplace.py`| Updates agent configuration or pauses/resumes agent | **Implemented** |
| `GET` | `/api/v1/audit-logs` | `app/api/v1/audit_logs.py` | Filterable compliance audit log stream | **Implemented** |
| `GET` | `/api/v1/audit-logs?export=csv`| `app/api/v1/audit_logs.py` | RFC 4180 streaming CSV export for compliance officers | **Implemented** |
| `POST` | `/api/v1/audit-logs` | `app/api/v1/audit_logs.py` | Records immutable audit event | **Implemented** |

---

## 3. Specialized AI Employees Inventory (`app/services/agents/`)

| Employee Name | Implementation Class & File | Capability & Core Tools | Governance Guardrails | Status |
|---|---|---|---|---|
| **HR Talent Recruiter** | `HRAgent` in `app/services/agents/hr.py` | PDF/DOCX resume parsing, skills extraction, JD candidate ranking (0–100%), calendar slot staging | Policy #HR-2026-01: Prohibits autonomous external emails; pauses for manager approval. Indirect prompt injection neutralized in resumes. | **Implemented** |
| **Finance & Invoice Auditor** | `FinanceAgent` in `app/services/agents/finance.py` | Invoice line-item extraction, 3-way PO matching, duplicate detection (`INV-9001`), price variance flags (`INV-103`) | Policy #FIN-2026-04: Disallow rogue payment executions; batches over $10,000 require dual manager sign-off. | **Implemented** |
| **Operations Reporter** | `OpsAgent` in `app/services/agents/ops.py` | 30-day ERP KPI aggregation, deterministic math checks, PDF executive reporting (`reportlab`) | Validates calculated metrics against raw ERP transactions; notifies leadership in-app. | **Implemented** |
| **AIOps Self-Healing** | `AIOpsAgent` in `app/services/agents/aiops.py` | Health metrics anomaly detection, root-cause hypothesis generation, governed circuit-breaker resets | Level-2 Manager approval required prior to restarting adapters or altering infra. | **Implemented** |

---

## 4. Security & Guardrails Inventory (`app/services/guardrails/`)

| Guardrail Module | Class & File | Threat Mitigated | Behavior Upon Violation | Status |
|---|---|---|---|---|
| **Prompt Injection Guard** | `PromptInjectionGuard` in `app/services/guardrails/injection.py` | Direct jailbreaks, roleplay bypasses, directive overrides, indirect resume/document injections | Blocks direct attacks with HTTP 400 (`safety_bypass`); neutralizes indirect document payloads; logs security incident. | **Implemented** |
| **PII Redactor** | `PIIGuard` in `app/services/guardrails/pii.py` | Unintended transmission of PII (Email, Phone, SSN, Credit Card, API Key) to LLMs | Masks sensitive tokens with placeholders (`[EMAIL_REDACTED]`, `[PHONE_REDACTED]`, `[CREDENTIAL_REDACTED]`). | **Implemented** |
| **Tool Parameter Guard** | `ToolParameterGuard` in `app/services/guardrails/tool_bounds.py` | Unauthorized agent disbursement, negative payment amounts, rogue agent tool executions | Blocks unauthorized agent calls with HTTP 403; logs high-severity security incident in audit trail. | **Implemented** |
| **Output Validator** | `OutputValidator` in `app/services/guardrails/output.py` | Malformed JSON responses, missing schema fields, dangerous HTML script tag injection | Strips executable script tags; raises validation errors for malformed schema keys. | **Implemented** |
| **Security Logger** | `SecurityLogger` in `app/services/guardrails/security_logger.py` | Silent security tampering | Persists structured threat records (`SECURITY_INCIDENTS`) with tenant ID, risk level, and sanitized payload samples. | **Implemented** |

---

## 5. Local Mock Adapters Inventory (`app/services/tools/mock_erp.py`)

All external integrations execute via deterministic local mock adapters in strict adherence to Rule 2:
- `MOCK_PURCHASE_ORDERS`: Pre-seeded POs (`PO-2026-001`, `PO-2026-002`, `PO-2026-003`).
- `ALREADY_PAID_INVOICES`: Historical duplicate ledger tracking `INV-9001`.
- `MOCK_OPERATIONS_METRICS`: 30-day historical metrics for revenue, uptime (99.94%), throughput (4,210 req/s), and error rate (0.02%).
- `MOCK_CALENDAR_EVENTS`: In-memory interview booking ledger with conflict detection.
- `MOCK_NOTIFICATIONS`: In-app notification queue for managerial approval alerts.

