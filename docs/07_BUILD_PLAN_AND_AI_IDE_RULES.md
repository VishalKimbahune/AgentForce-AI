# 07 — Build Plan and AI IDE Rules

> Instructions for the AI IDE (Cursor, Windsurf, Claude Code, Copilot, etc.). Read all files in `/docs` before writing code.

## 1. Files to read and their purpose

| File | Use it for |
|---|---|
| `01_PROJECT_OVERVIEW_AND_ARCHITECTURE.md` | What we build, principles, agents, flows |
| `02_DESIGN_SYSTEM.md` | All UI decisions, theme toggle, tokens |
| `03_TECH_STACK_AND_PROJECT_STRUCTURE.md` | Stack, folders, standards |
| `04_API_KEYS_AND_ENV.md` | Environment variable names (values come from `.env`) |
| `05_USERS_FEATURES_AND_EXPECTED_OUTPUT.md` | Screens, journeys, acceptance checklist |
| `06_DATABASE_AND_API_SPEC.md` | Tables, endpoints, event payloads |

## 2. Rules for the AI IDE

1. Follow the folder structure in file 03. Do not invent new top-level folders.
2. Use only design tokens from file 02. No hardcoded colors, no gradients, no shadows.
3. Build the **light/dark toggle first** and test every new page in both themes.
4. Never hardcode secrets. Read from environment variables named in file 04. Never print them.
5. Never let an agent call a database, raw HTTP client, or credential directly. All external actions go through the Tool Executor.
6. Never route agent-to-agent calls directly. Go through the orchestrator or event bus.
7. All sensitive actions pass through the deterministic Policy Engine before execution.
8. Every DB query and vector search includes `tenant_id`. Add a test for it.
9. Use Pydantic schemas for all API and agent inputs/outputs. Validate LLM JSON output and retry (max 2) on failure.
10. All retries are bounded, with exponential backoff and jitter. Add timeouts to every external call.
11. Make tool executions idempotent using idempotency keys.
12. Work in small steps. After each step: run the app, run tests, summarize what changed, and stop for review if a decision is ambiguous.
13. If a free provider's model name or API has changed, check its current docs instead of guessing.
14. Prefer simple code. Mock external systems (ATS, HRMS, ERP, payments) with local FastAPI services instead of real integrations.
15. Write a short comment or docstring for non-obvious logic only. No dead code, no TODO placeholders left behind.
16. Do not add Google OAuth, Gmail, Google Calendar, Slack, Jira, S3, MinIO, Supabase Storage, OpenRouter, OpenAI or Anthropic in the MVP. Use Supabase Auth/PostgreSQL, local persistent file storage, mock business services and in-app notifications.

## 3. Build phases

### Phase 0: Foundation (Day 1 to 2)
- [ ] Monorepo scaffold, `docker-compose.yml` with Redis, Qdrant and RabbitMQ (Supabase provides Auth and PostgreSQL; uploads use a persistent local volume).
- [ ] FastAPI app with `/health`, config loader, logging with correlation IDs.
- [ ] Next.js app with Tailwind, shadcn/ui, **theme toggle**, sidebar layout, tokens from file 02.
- [ ] Alembic migrations for application tables (organizations, users, memberships, agents, workflows); link `users.id` to Supabase Auth user IDs.

**Done when:** both apps run, theme toggles and persists, Supabase connection works, and application DB migrations run.

### Phase 1: Auth and tenancy (Day 3 to 4)
- [ ] Supabase Auth sign-up/sign-in/session handling in frontend; FastAPI JWT verification and `/me`; create application profile and organization after sign-up.
- [ ] RBAC dependency (`require_role`). Tenant context middleware.
- [ ] Test: tenant A cannot read tenant B.

**Done when:** Supabase login works end to end, FastAPI verifies access tokens, and the tenant-isolation test passes.

### Phase 2: LLM gateway (Day 5)
- [ ] LiteLLM config with Gemini, Groq and Ollama only.
- [ ] Routing by task type, fallback chain, retry/backoff, circuit breaker.
- [ ] Log every call to `llm_requests` (tokens, cost, latency). Redact PII.

**Done when:** killing one provider key still returns a response through fallback.

### Phase 3: Orchestrator and first agent (Day 6 to 9)
- [ ] LangGraph graph: Intent -> Planner -> Orchestrator -> Agent -> Verifier.
- [ ] Message schema, checkpoints in Postgres, step limit, cancellation.
- [ ] SSE endpoint and live workflow timeline in the UI.
- [ ] HR agent: resume parsing (pypdf, python-docx), JD matching with embeddings, ranking.

**Done when:** "Rank these resumes for the Python JD" runs with a live timeline and a trace.

### Phase 4: Knowledge and RAG (Day 10 to 11)
- [ ] Upload, chunk, embed, store in Qdrant with tenant and role filters.
- [ ] Hybrid search, citations, delete propagation.
- [ ] Knowledge agent and compliance agent use it.

**Done when:** a question over uploaded policy returns an answer with source citations.

### Phase 5: Tools, policy and approvals (Day 12 to 15)
- [ ] Tool registry and executor with idempotency and logs.
- [ ] Mock calendar tool and internal in-app notification tool; no Google OAuth, Gmail, Google Calendar, Slack or Jira integrations.
- [ ] Policy engine with seeded rules and unit tests.
- [ ] Approval service, approval center UI, pause and resume of LangGraph, expiry, reject, delegate.

**Done when:** interview scheduling pauses for approval and only sends after approve. Reject and expiry send nothing.

### Phase 6: Finance and Operations agents (Day 16 to 18)
- [ ] Mock ERP and mock payment API.
- [ ] Invoice extraction, PO matching, duplicate and anomaly detection.
- [ ] Report generation (PDF/PPT) and in-app notification delivery with approval.

**Done when:** all three journeys in file 05 complete.

### Phase 7: Guardrails (Day 19)
- [ ] Prompt injection detection, PII masking, output schema validation, tool parameter validation.
- [ ] Red-team tests: injection in a resume, attempt to read another tenant, attempt to pay without approval.

**Done when:** all red-team tests are blocked and logged.

### Phase 8: Voice (Day 20 to 21)
- [ ] WebSocket streaming, VAD, Whisper STT, edge-tts TTS.
- [ ] Push-to-talk and continuous modes, interrupt, live captions.
- [ ] Same policy and approval path as text.

**Done when:** a spoken command completes a workflow and speaks the result.

### Phase 9: Observability and AIOps (Day 22 to 24)
- [ ] OpenTelemetry tracing across API, orchestrator, agent, LLM, tool.
- [ ] Langfuse for LLM traces, Prometheus metrics, Grafana dashboards, Loki logs.
- [ ] Analytics pages (tokens, cost, agent health).
- [ ] AIOps agent: detect failure spike or cost spike, produce hypothesis and recommendation, remediation goes through approval.

**Done when:** a forced failure creates an incident with a root-cause hypothesis.

### Phase 10: Polish and deploy (Day 25 to 28)
- [ ] Marketplace, audit log export, integration pages, settings.
- [ ] Seed script and demo data.
- [ ] Kubernetes manifests, GitHub Actions CI (lint, test, build).
- [ ] README with setup, screenshots and architecture diagram.

## 4. Testing checklist

| Area | Test |
|---|---|
| Tenant isolation | API, DB and vector search never leak across tenants |
| Policy engine | Table-driven tests for every rule in file 06 section 8 |
| Approvals | approve, reject, expire, double-approve blocked, permission revalidated |
| Orchestrator | retry, timeout, cancel, resume after restart, step-limit stop |
| LLM gateway | fallback on 429 and timeout, budget exceeded |
| Guardrails | injection, PII, malformed JSON |
| Voice | interrupt, STT failure fallback, same approval path |
| Idempotency | duplicate submit returns same workflow |

## 5. Definition of done (whole project)

- All items under "Must work in the demo" in file 05 are checked.
- All phase "Done when" conditions are met.
- No secrets in the repo. `.env.example` is complete.
- Both themes verified on every page.
- README explains setup in under 10 commands.
- A 3-minute demo can be run from seed data: recruitment, finance, and approvals.

## 6. Prompt to give the AI IDE at the start

```
You are building AgentForce AI. First read every file in /docs (01 to 07).
Follow 07_BUILD_PLAN_AND_AI_IDE_RULES.md strictly.
Start with Phase 0 only. Create the monorepo scaffold, Docker Compose, FastAPI health endpoint,
and the Next.js app with the light/dark toggle using the tokens in 02_DESIGN_SYSTEM.md.
When Phase 0 is done, summarize what you built, list how to run it, and wait for my confirmation
before starting Phase 1.
```

## 7. Prompt to continue each phase

```
Continue with Phase <N> from 07_BUILD_PLAN_AND_AI_IDE_RULES.md.
Respect the rules in section 2. Run tests when finished, tell me what passed,
and list anything you could not complete.
```
