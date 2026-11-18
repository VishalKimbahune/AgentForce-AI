# 06 — Database Schema and API Specification

> Contract between frontend, backend and agents. Do not change names without updating this file.

## 1. Conventions

- IDs are UUIDs. Timestamps are UTC (`timestamptz`).
- Every tenant-owned table has `tenant_id` (FK to `organizations.id`) and an index on it. Supabase Auth owns identity credentials; the application schema stores profile and tenant membership data only.
- Every query filters by `tenant_id` taken from the JWT, never from the request body.
- Soft delete via `deleted_at` where retention rules apply. Audit records are append-only.
- API base: `/api/v1`. JSON only. Errors use `{ "error": { "code": "string", "message": "string", "correlation_id": "uuid" } }`.

## 2. PostgreSQL tables

```
organizations(id, name, plan, daily_token_budget, created_at)
users(id, email, name, mfa_enabled, created_at)  -- id matches Supabase auth.users.id; no local password hash
memberships(id, tenant_id, user_id, role)            -- role: owner|manager|approver|member|auditor
api_keys(id, tenant_id, name, key_hash, scopes[], last_used_at, revoked_at)

agents(id, tenant_id, name, type, system_prompt, model_policy JSONB,
       allowed_tools[], knowledge_scopes[], approval_rules JSONB,
       status, template_id NULL, created_by, created_at)
agent_templates(id, name, type, description, default_config JSONB, required_integrations[], published)

workflows(id, tenant_id, created_by, input_text, input_source,  -- text|voice|api
          status, plan JSONB, idempotency_key, trace_id, correlation_id,
          cost_usd, tokens_used, started_at, finished_at)
          -- status: pending|planning|running|waiting_approval|completed|failed|cancelled
workflow_tasks(id, workflow_id, tenant_id, agent_id, name, depends_on[],
               status, input JSONB, output JSONB, error, attempts,
               started_at, finished_at)
workflow_checkpoints(id, workflow_id, state JSONB, step, created_at)
agent_messages(id, workflow_id, tenant_id, source_agent, destination_agent,
               payload JSONB, correlation_id, created_at)

approval_requests(id, tenant_id, workflow_id, task_id, requested_by_agent,
                  action_type, action_payload JSONB, risk_level, reason,
                  status, required_role, level, expires_at,
                  decided_by NULL, decided_at NULL, decision_note NULL)
                  -- status: pending|approved|rejected|expired|cancelled
policy_rules(id, tenant_id, action_type, conditions JSONB, effect)  -- effect: allow|require_approval|deny

integrations(id, tenant_id, provider, status, config JSONB, connected_by, created_at)  -- mock/internal adapters in MVP; no third-party OAuth credentials
tool_executions(id, tenant_id, workflow_id, task_id, tool_name, params_redacted JSONB,
                idempotency_key, status, response_redacted JSONB, duration_ms, created_at)

documents(id, tenant_id, name, storage_key, mime_type, status, version,
          allowed_roles[], tags[], uploaded_by, created_at, deleted_at)
document_chunks(id, document_id, tenant_id, chunk_index, text, qdrant_point_id)

llm_requests(id, tenant_id, workflow_id, task_id, provider, model, prompt_version,
             input_tokens, output_tokens, cost_usd, latency_ms, status, fallback_from NULL, created_at)

audit_logs(id, tenant_id, actor_type, actor_id, action, resource_type, resource_id,
           details_redacted JSONB, ip, correlation_id, created_at)   -- append-only
outbox_events(id, tenant_id, topic, payload JSONB, published_at NULL, created_at)
aiops_incidents(id, tenant_id, severity, summary, root_cause_hypothesis,
                recommendation, status, created_at, resolved_at)
```

Indexes: `(tenant_id, status, created_at)` on workflows and approvals, `(workflow_id)` on tasks/messages, GIN on JSONB filters used in the UI.

## 3. Redis keys

| Key pattern | Use | TTL |
|---|---|---|
| `authz:{user_id}` | Optional cached authorization/membership data (Supabase owns auth sessions) | 5m |
| `wf:state:{workflow_id}` | Short-term workflow state | 24h |
| `lock:wf:{workflow_id}` | Distributed lock | 30s renewable |
| `rate:{tenant_id}:{route}` | Rate limit counter | 1m |
| `idem:{tenant_id}:{key}` | Idempotency result | 24h |
| `cache:llm:{hash}` | Optional response cache | 1h |

## 4. Qdrant

- One collection `knowledge`, payload fields: `tenant_id`, `document_id`, `version`, `allowed_roles`, `chunk_index`, `source_name`, `page`.
- Every search **must** include a `tenant_id` filter plus role filter. Add a test that fails if a search runs without it.
- Chunking: 500 to 800 tokens, 80 overlap. Hybrid search (vector + keyword) then rerank, return citations.
- On document delete: delete points by `document_id` and mark chunks deleted.

### File storage rules

- `documents.storage_key` is a relative path/key managed by the backend storage service, not a public URL.
- MVP storage is a persistent local directory configured by `LOCAL_STORAGE_PATH`; do not use S3, MinIO or Supabase Storage.
- Store files outside the frontend's public directory. Downloads must pass through authenticated API endpoints with tenant and `allowed_roles` checks.
- Validate file size, MIME type and content; generate server-side filenames; prevent path traversal; do not trust user-supplied paths.
- Back up the persistent upload directory together with the database, and document that ephemeral deployment disks are not suitable for this setup.

## 5. REST endpoints

### Auth
Authentication is handled by Supabase Auth in the frontend using the Supabase client SDK. Supabase manages sign-up, sign-in, password reset, optional MFA, session refresh and sign-out. FastAPI validates the Supabase access token on protected routes; it does not issue a second access/refresh-token pair.

| Method | Path | Notes |
|---|---|---|
| GET | `/me` | Returns application profile, organization memberships and roles for the verified Supabase user |
| POST | `/auth/complete-profile` | Creates or completes the application profile and initial organization after Supabase sign-up; idempotent |
| POST | `/org/members/invitations` | Creates an organization invitation; invite acceptance uses the Supabase-authenticated user |

The application `users.id` must equal the authenticated Supabase `auth.users.id`. Never accept a user ID or `tenant_id` from the request body as the authenticated identity. Resolve tenant membership from the database using the verified JWT subject.

### Organization
| GET/PATCH | `/org` | Settings, budgets |
| GET/POST | `/org/members` | List, invite |
| PATCH/DELETE | `/org/members/{id}` | Change role, remove |

### AI employees
| Method | Path | Notes |
|---|---|---|
| GET | `/agents` | List |
| POST | `/agents` | Create from scratch or `template_id` |
| GET/PATCH/DELETE | `/agents/{id}` | Configure |
| GET | `/marketplace/templates` | Templates |
| POST | `/marketplace/templates/{id}/install` | Creates an agent |

### Workflows
| Method | Path | Notes |
|---|---|---|
| POST | `/workflows` | Body: `{ "input": "text", "attachments": [], "agent_ids": [] }`. Header `Idempotency-Key`. Returns `202` with `workflow_id` |
| GET | `/workflows` | Filter by status, date |
| GET | `/workflows/{id}` | Status, plan, tasks, cost |
| GET | `/workflows/{id}/messages` | Agent message trace |
| GET | `/workflows/{id}/events` | SSE stream of live updates |
| POST | `/workflows/{id}/cancel` | Cancel |
| POST | `/workflows/{id}/retry` | Retry failed tasks |

### Approvals
| GET | `/approvals?status=pending` | My pending approvals |
| GET | `/approvals/{id}` | Details with action payload |
| POST | `/approvals/{id}/approve` | Body `{ "note": "" }`. Revalidates permissions and payload hash before execution |
| POST | `/approvals/{id}/reject` | Body `{ "note": "" }` |
| POST | `/approvals/{id}/delegate` | Body `{ "to_user_id": "" }` |

### Knowledge
| POST | `/documents` | Multipart upload, triggers ingestion |
| GET | `/documents` | List with status |
| DELETE | `/documents/{id}` | Removes file, chunks, vectors |
| POST | `/knowledge/search` | `{ "query": "", "top_k": 5 }` returns chunks with citations |

### Voice
| WS | `/voice/stream` | Binary audio in, JSON events out (`partial_transcript`, `final_transcript`, `agent_status`, `tts_audio_chunk`, `error`). Client can send `{ "type": "interrupt" }` |
| POST | `/voice/transcribe` | Fallback: upload audio file |

### Integrations
| GET | `/integrations` | Status of built-in and local mock adapters (calendar, ATS, HRMS, ERP, CRM) |
| GET | `/integrations/{id}` | Adapter details and health |
| POST | `/integrations/{id}/test` | Runs a safe connectivity/health check |
| DELETE | `/integrations/{id}` | Disable an adapter |

No Google OAuth, Gmail, Google Calendar, Slack or Jira OAuth/connect endpoints are part of the MVP. Calendar scheduling and notifications use local mock/internal services.

### Analytics and operations
| GET | `/analytics/overview` | Workflows, success rate, hours saved |
| GET | `/analytics/llm` | Per model: requests, latency, tokens, cost, fallbacks |
| GET | `/analytics/agents` | Success/failure rate per agent |
| GET | `/aiops/incidents` | List incidents |
| POST | `/aiops/incidents/{id}/remediate` | Creates an approval request |
| GET | `/audit-logs` | Filters + CSV export |
| GET | `/health` | Liveness. `/ready` checks dependencies |

### Webhooks (inbound)
`POST /webhooks/{provider}` verify signature, reject old timestamps (replay protection), enqueue event.

## 6. Realtime events (SSE / WebSocket payload)

```json
{
  "type": "task.started | task.completed | task.failed | approval.requested | workflow.completed | workflow.failed",
  "workflow_id": "uuid",
  "task_id": "uuid",
  "agent": "hr",
  "message": "Screened 14 of 20 resumes",
  "timestamp": "ISO-8601",
  "correlation_id": "uuid"
}
```

## 7. Tool registry contract

```json
{
  "name": "mock_calendar.create_event",
  "description": "Create an interview event in the local mock calendar service",
  "input_schema": {},
  "output_schema": {},
  "side_effect": "write",
  "requires_approval_default": true,
  "allowed_agents": ["hr"],
  "rate_limit_per_min": 30,
  "idempotent": true
}
```

Policy engine input: `{ tenant_id, user_role, agent, tool, params, amount?, recipient_domain? }`. Output: `allow | require_approval(level, reason) | deny(reason)`. Pure code, unit-tested, no LLM.

## 8. Default policy rules (seed)

| Action | Rule |
|---|---|
| `payment.execute` | Always require approval (finance manager), deny if agent is not Finance |
| `email.send_external` | Require approval when recipients are outside org domain or content flagged sensitive |
| `record.delete` | Require approval (admin) |
| `employee_record.update` | Require approval (HR manager) |
| `refund.issue` | Require approval above configured amount |
| `infra.change` | Require approval, deny anything touching IAM or security controls |
| `document.read` | Allow only if user role in `allowed_roles` |
