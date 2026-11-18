# 03 — Tech Stack and Project Structure

> Goal: build the full project using **free tiers or open source** tools. Where the original design used a paid service, a free replacement is listed.

## 1. Stack

| Layer | Original design | Free choice used in this project |
|---|---|---|
| Frontend | Next.js, TypeScript, Tailwind | Same (Next.js 14+ App Router, shadcn/ui, lucide-react, Recharts, next-themes) |
| Backend | FastAPI, Python | Same (Python 3.11+, Pydantic v2, SQLAlchemy, Alembic) |
| Agent framework | LangGraph | Same |
| LLM gateway | LiteLLM | Same (self-hosted proxy or library mode) |
| LLMs | GPT, Claude, Gemini | Gemini free tier, Groq (Llama), Ollama (local) |
| Vector DB | Qdrant / Pinecone | Qdrant (Docker or free cloud cluster) |
| Embeddings | Paid | `sentence-transformers` (local) or Gemini embeddings |
| Relational DB | Amazon RDS | Supabase PostgreSQL (project database) |
| Cache / locks | ElastiCache | Redis (Docker, or Upstash free) |
| Queue / events | Kafka / SQS | Redis Streams or RabbitMQ (Docker) |
| File storage | S3 | Persistent local filesystem (`./storage/uploads`); no S3 or MinIO in MVP |
| Auth + RBAC | Cognito / Auth0 | Supabase Auth; organization roles and permissions stored in application tables |
| API gateway | Kong | NGINX or Traefik (Docker) |
| Observability | Langfuse, OTel, Grafana | Same, all self-hosted via Docker Compose |
| Guardrails | NeMo, Guardrails AI | Same (open source) plus own regex/PII checks |
| STT | Whisper | `faster-whisper` local, or Groq Whisper API (free tier) |
| TTS | ElevenLabs / Azure | `edge-tts` or Piper (free) |
| Calendar / notifications | Third-party calendar and email | Local mock calendar service and in-app notification center |
| Tickets / chat | Jira, Slack | Internal task tracker and in-app notification center; no external account required |
| CRM | Salesforce | Mock CRM service for development and demos |
| ERP / HRMS / ATS | SAP, Workday | Mock FastAPI services backed by Postgres, or ERPNext in Docker |
| Secrets | AWS Secrets Manager / Vault | `.env` locally, encrypted column in DB for tenant credentials |
| Deployment | AWS EKS, Terraform | Docker Compose for dev; Kubernetes manifests included but demoed on `kind`/`minikube`; optional Oracle Cloud Always Free, Render, Vercel |
| CI/CD | GitHub Actions | Same (free for public repos) |

Free tier limits and model names change often. Always verify before depending on them. LiteLLM fallbacks between configured providers handle rate limits. Initial providers are Gemini, Groq and local Ollama; do not configure OpenRouter, OpenAI or Anthropic for the initial version.

## 2. Model routing rules (LLM gateway)

| Task type | Model tier | Example free route |
|---|---|---|
| Intent classification, simple extraction | Small / fast | Groq `llama-3.1-8b-instant`, Gemini Flash |
| Planning, reasoning, long documents | Larger | Gemini Pro (free tier), Groq 70B |
| Sensitive tenant data | Local only | Ollama `llama3.1` |
| Fallback chain | Any healthy | Gemini -> Groq -> Ollama |

Rules: per-workflow token budget, per-tenant cost budget, retry with exponential backoff and jitter, circuit breaker per provider, redact PII before logging. Never send confidential tenant data to a provider not approved for that tenant.

## 3. Repository structure (monorepo)

```
agentforce-ai/
├── README.md
├── docs/                       # the .md files from this pack
├── .env.example                # copy to .env (never commit .env)
├── docker-compose.yml
├── docker-compose.observability.yml
├── infra/
│   ├── k8s/                    # Kubernetes manifests
│   ├── nginx/
│   └── terraform/              # optional, documentation only
├── frontend/                   # Next.js app
│   ├── app/
│   │   ├── (auth)/login/
│   │   ├── (app)/
│   │   │   ├── dashboard/
│   │   │   ├── employees/          # list, configure, marketplace
│   │   │   ├── workflows/          # list, builder, live view, traces
│   │   │   ├── approvals/
│   │   │   ├── knowledge/
│   │   │   ├── analytics/          # tokens, cost, LLM gateway
│   │   │   ├── observability/
│   │   │   ├── aiops/
│   │   │   ├── audit/
│   │   │   ├── integrations/
│   │   │   ├── voice/
│   │   │   └── settings/
│   │   ├── layout.tsx
│   │   └── providers.tsx
│   ├── components/ui/          # shadcn components
│   ├── components/             # theme-toggle, sidebar, workflow-timeline, approval-card
│   ├── lib/                    # api client, ws client, utils
│   └── styles/globals.css      # tokens from 02_DESIGN_SYSTEM.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/               # config, security, tenant context, logging
│   │   ├── api/v1/             # routers: auth, employees, workflows, approvals, knowledge, analytics, voice
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/
│   │   │   ├── orchestrator/   # LangGraph graph, state, checkpoints
│   │   │   ├── agents/         # hr.py, finance.py, support.py, ops.py, compliance.py, knowledge.py, notification.py, aiops.py
│   │   │   ├── llm_gateway/    # litellm config, routing, budgets
│   │   │   ├── guardrails/     # input, output, tool guards, PII
│   │   │   ├── policy_engine/  # deterministic rules
│   │   │   ├── approvals/
│   │   │   ├── tools/          # tool registry + mock_calendar, notifications, mock_crm, erp
│   │   │   ├── memory/         # redis, postgres, qdrant, ingestion, RAG
│   │   │   ├── voice/          # stt, tts, vad
│   │   │   └── observability/  # otel, langfuse, metrics
│   │   └── workers/            # async workers consuming the event bus
│   ├── mock_services/          # fake ATS, HRMS, ERP, CRM APIs
│   ├── alembic/
│   ├── tests/
│   └── pyproject.toml
└── scripts/                    # seed data, sample resumes, sample invoices
```

## 4. Docker Compose services (development)

`frontend`, `backend`, `worker`, `redis`, `qdrant`, `rabbitmq` (or Redis Streams), `nginx`, `ollama` (optional), `mock-services`. Supabase hosts PostgreSQL and Auth; uploaded files use a persistent local volume. Do not add MinIO or S3.
Observability compose: `langfuse`, `otel-collector`, `prometheus`, `grafana`, `loki`, `tempo`.

## 5. Local setup (target commands)

```bash
git clone <repo> && cd agentforce-ai
cp .env.example .env            # fill in values, see 04_API_KEYS_AND_ENV.md
docker compose up -d            # core services
docker compose -f docker-compose.observability.yml up -d
cd backend && pip install -e . && alembic upgrade head && python scripts/seed.py
uvicorn app.main:app --reload   # http://localhost:8000/docs
cd ../frontend && npm install && npm run dev   # http://localhost:3000
```

## 6. Coding standards

- Python: type hints everywhere, Pydantic models for all inputs/outputs, `ruff` + `black`, async endpoints.
- TypeScript: strict mode, no `any`, server components by default, client components only when needed.
- Every API route validates input, checks auth, and resolves `tenant_id` from the token (never from the request body).
- Every DB query filters by `tenant_id`. Add a test that proves tenant A cannot read tenant B.
- Every tool call is idempotent (idempotency key) and logged.
- No secrets in code. Read config from environment only.
- Write tests for: policy engine, tenant isolation, approval flow, orchestrator retries.
