# 01 — Project Overview and Architecture

> Read this file first. It is the source of truth for what we are building and why.

## 1. Project identity

| Field | Value |
|---|---|
| Name | AgentForce AI |
| Tagline | "Create AI Employees, Not AI Chatbots." |
| Type | Multi-tenant Enterprise SaaS, Agentic AI platform |
| Domain | Agentic AI, Workforce Automation, LLMOps, AIOps, Voice AI |
| Positioning | "The Operating System for AI Employees" |

## 2. One-paragraph description

AgentForce AI lets an organization create, deploy and manage **AI Employees** (HR, Finance, Support, Operations, Compliance, Knowledge, Notification, AIOps). Users do not chat with a bot. They **assign work** ("Screen 500 resumes and schedule the top 20"). A central orchestrator breaks the work into tasks, dispatches them to specialized agents, and executes them through controlled tools. Critical actions (payments, external communications when enabled, deletions) always require **human approval**. Everything is observable, auditable and tenant-isolated.

## 3. Problem and solution

**Problem:** companies waste time on repetitive digital work (resume screening, invoice processing, report generation, ticket triage). Existing automation is rule-based, fragmented and cannot handle multi-step decisions.

**Solution:** a governed digital workforce. Agents that plan, collaborate, remember company policy, use real tools, and ask a human before risky actions.

## 4. Core principles (never violate)

1. Agents never talk directly to each other. All messages go through the **Workforce Orchestrator** or the event bus.
2. Agents never access databases or raw credentials. All external actions go through the **Tool Executor**.
3. A **deterministic Policy Engine** (plain code, not an LLM) decides what needs approval.
4. Silence or timeout is **never** approval.
5. Every request carries `tenant_id`, `workflow_id`, `correlation_id`. No cross-tenant data access, ever.
6. Voice commands follow the exact same auth and approval rules as text.
7. Retries are bounded. Use exponential backoff with jitter, timeouts, and a dead-letter queue.

## 5. Feature list

1. Multi-agent workforce management
2. AI Employee marketplace (installable agent templates)
3. Voice-based task assignment (STT + TTS)
4. Human approval center
5. Agent memory and knowledge base (RAG)
6. LLM gateway with multi-model routing and fallback
7. Guardrails and compliance controls
8. Observability dashboard (traces, cost, success rate)
9. AIOps monitoring with suggested fixes
10. Auth with roles (RBAC) and organizations

## 6. High-level architecture (layers, top to bottom)

```
Users / Clients      Web app, Voice, REST/Webhooks, Supabase Auth (JWT, optional MFA)
        |
Edge + API Gateway   WAF, Kong/NGINX, FastAPI core, workflow intake (sync vs async)
        |
Orchestration        LangGraph: Intent agent, Planner, Orchestrator, Verifier/Supervisor
        |
AI Employees         HR, Finance, Support, Operations, Compliance, Knowledge, Notification, AIOps
        |
Security + Approval  Guardrails, Policy Engine, Approval Service, Secrets
        |
Platform Services    LLM Gateway (LiteLLM), Tool Executor, Event Bus, Memory + RAG
        |
Data Stores          Supabase PostgreSQL, Redis, Qdrant, persistent local file storage
        |
External Systems     Mock Calendar, Mock ATS/HRMS/ERP/CRM, internal notifications, LLM providers

Cross-cutting: OpenTelemetry, Langfuse, Prometheus, Grafana, Loki
```

### Authentication and storage decisions for version 1

- **Authentication:** Supabase Auth handles sign-up, sign-in, session refresh, sign-out and optional MFA. The frontend uses the Supabase client. FastAPI validates Supabase-issued access tokens and derives the authenticated user ID from the verified token. Do not implement a separate password store or custom refresh-token system.
- **Database:** Use the project's Supabase PostgreSQL database for application data. Store the Supabase Auth user ID in the application `users.id` field and link it to organization memberships.
- **Files:** Store uploaded resumes, invoices and knowledge documents on a persistent local filesystem for the initial version. Do not add S3, MinIO or another object-storage service. Keep file access behind a storage service so the implementation can be changed later if deployment requirements change.
- **No third-party workspace integrations in the MVP:** Do not require Google, Gmail, Google Calendar, Slack or Jira accounts. Use mock calendar/ATS/HRMS/ERP services and an in-app notification center.

## 7. Request lifecycle

```
User request
 -> Auth + tenant validation + input validation
 -> Intent agent (classify, extract entities, ask clarifying question if ambiguous)
 -> Planner (tasks, dependencies, cost estimate)
 -> Orchestrator (dispatch sequential/parallel, checkpoint state)
 -> Specialized AI employees (use tools through Tool Executor)
 -> Policy Engine (risk check on each sensitive action)
 -> Approval Service (if required; workflow pauses and resumes)
 -> Verifier (validate outputs, reject invalid)
 -> Final report to user (real-time updates over WebSocket/SSE)
```

## 8. Inter-agent message schema

Every message between agents (through the orchestrator) must contain:

```json
{
  "task_id": "uuid",
  "workflow_id": "uuid",
  "tenant_id": "uuid",
  "source_agent": "planner",
  "destination_agent": "hr",
  "task_description": "Screen resumes against JD #12",
  "input_context": {},
  "expected_output_schema": {},
  "priority": "normal",
  "deadline": "ISO-8601",
  "permissions": ["resume:read"],
  "status": "pending",
  "correlation_id": "uuid"
}
```

## 9. Agents and responsibilities

| Agent | Does | Integrations | Hard restriction |
|---|---|---|---|
| HR | Resume parsing, JD matching, ranking, interview scheduling, onboarding | Mock Calendar, ATS (mock) | No sharing salary data |
| Finance | Invoice extraction, PO matching, anomaly detection, reports | Mock ERP and accounting data | Never executes payments without human approval |
| Support | Ticket triage, KB answers, escalation, sentiment | Mock CRM and internal support inbox | Escalate low-confidence answers |
| Operations | Reports, deadline monitoring, notifications | Internal task tracker and notification center | Read-mostly |
| Compliance | Policy checks, sensitive data detection, audit trail | Knowledge base | Cannot be overridden by other agents |
| Knowledge | Ingestion, semantic search, RAG, citations | Qdrant | Tenant-filtered retrieval only |
| Notification | In-app notifications, approval reminders, workflow updates | Internal notification center | Sends only approved content |
| AIOps | Health monitoring, log analysis, root cause, recommendations | Prometheus, Loki | No destructive infra changes without approval |

## 10. Execution patterns to support

Sequential, parallel, conditional, handoff, retry, timeout, cancellation, human approval and resume, rollback or compensation, dead-letter queue.

## 11. Example collaboration

User: "Recruit five data engineers within our approved budget."
1. Intent agent identifies a recruitment workflow.
2. Planner creates the plan.
3. HR screens candidates.
4. Compliance checks hiring policy.
5. Finance verifies the budget.
6. HR prepares interview slots.
7. Notification creates in-app interview invitations after approval.
8. Verifier validates completion.
9. User receives a consolidated report.

## 12. Failure handling summary

| Failure | Detection | Recovery |
|---|---|---|
| LLM provider down or rate-limited | Timeout, 429, health check | Fallback model via LiteLLM, circuit breaker |
| Agent returns malformed JSON | Schema validation | Retry with repair prompt, max 2 attempts, then escalate |
| Agent infinite loop | Step and tool-call counters | Hard step limit, cancel, alert |
| Tool/API failure | Non-2xx, timeout | Bounded retries with backoff, then dead-letter queue |
| Duplicate request | Idempotency key | Return original result |
| Approval rejected or expired | Approval status | Stop workflow, notify user, never auto-approve |
| Service restart mid-workflow | Checkpoint in PostgreSQL | Resume from last LangGraph checkpoint |

Not every external action can be rolled back. Use compensating actions where possible and flag the rest for human review.

## 13. Out of scope for version 1

Real banking payments, real SAP integration, mobile apps, on-premise installer, custom model training.
