# 04 — API Keys, Secrets and Environment Fields

> Source of truth for the environment variable names used by AgentForce AI. Keep real values in a local `.env` file only.

## 1. Security rules

1. Commit `.env.example`, never `.env`. Add `.env` and uploaded files to `.gitignore`.
2. Never paste real secrets into documentation, source code, screenshots or shared chats.
3. If a secret leaks, revoke and regenerate it immediately.
4. Load values from environment variables at runtime. Never print or log secret values.
5. Supabase Auth manages user passwords, access tokens and refresh sessions. Do not create a second password/JWT authentication system.
6. The Supabase publishable key may be used by the frontend. Never expose a Supabase secret/service-role key in browser code. The MVP does not need a service-role key.

## 2. LLM providers

| Variable | Provider / purpose | Where to get it | Value |
|---|---|---|---|
| `GEMINI_API_KEY` | Gemini API; primary hosted model option | https://aistudio.google.com/apikey | `__________` |
| `GROQ_API_KEY` | Groq inference; fallback hosted model option | https://console.groq.com/keys | `__________` |
| `OLLAMA_BASE_URL` | Local Ollama endpoint; no API key | https://ollama.com/download | `http://localhost:11434` |
| `LITELLM_MASTER_KEY` | Optional key for a self-hosted LiteLLM proxy; generate a strong random value | Your own generated secret | `__________` |

Use only Gemini, Groq and Ollama in the initial configuration. OpenRouter, OpenAI and Anthropic variables are intentionally excluded. `LITELLM_MASTER_KEY` is only required if LiteLLM is deployed in proxy mode; it is not needed when using LiteLLM as a library.

## 3. Supabase authentication and PostgreSQL

Create a Supabase project at https://supabase.com/dashboard.

| Variable | Description | Where to get it | Value |
|---|---|---|---|
| `SUPABASE_URL` | Project URL | Supabase Dashboard → Project Settings → API | `__________` |
| `SUPABASE_PUBLISHABLE_KEY` | Browser-safe publishable key | Supabase Dashboard → Project Settings → API Keys | `__________` |
| `SUPABASE_JWKS_URL` | Public signing-key endpoint used by the backend to verify Supabase JWTs | `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json` | `__________` |
| `DATABASE_URL` | Supabase PostgreSQL connection string | Supabase Dashboard → Connect → connection string; use the connection mode suitable for your runtime | `__________` |

**Authentication implementation rules**

- Frontend sign-up, sign-in, sign-out and session refresh use the Supabase client SDK.
- FastAPI receives `Authorization: Bearer <access_token>` and verifies the JWT using the project's JWKS and the token's supported signing algorithm. Validate signature, issuer, audience and expiry.
- Use the verified token's `sub` claim as the Supabase Auth user ID. Resolve organization memberships and roles from application tables.
- Do not store user passwords in the application database. Do not use `JWT_SECRET`, `NEXTAUTH_SECRET`, `NEXTAUTH_URL`, or custom refresh-token endpoints.
- Do not use a Supabase service-role/secret key in the frontend. Prefer normal user-scoped access and enforce authorization in FastAPI and database policies.
- Configure Supabase Auth redirect URLs for the local frontend URL in the Supabase dashboard if email confirmation or password-reset flows are enabled.

## 4. Database, cache, vector search and local file storage

| Variable | Description | Default / example | Value |
|---|---|---|---|
| `REDIS_URL` | Redis cache, locks and transient workflow state | `redis://localhost:6379/0` | `__________` |
| `QDRANT_URL` | Local Qdrant endpoint | `http://localhost:6333` | `__________` |
| `RABBITMQ_URL` | RabbitMQ event bus | `amqp://guest:guest@localhost:5672/` | `__________` |
| `STORAGE_PROVIDER` | Initial file-storage backend | `local` | `local` |
| `LOCAL_STORAGE_PATH` | Persistent directory for uploaded files | `./storage/uploads` | `./storage/uploads` |
| `MAX_UPLOAD_SIZE_MB` | Maximum upload size per file | `25` | `25` |

No S3, MinIO, Supabase Storage, object-storage endpoint, bucket, or storage access keys are used in this version. Ensure `LOCAL_STORAGE_PATH` is on a persistent disk/volume and is not publicly served directly. Files must be accessed through authenticated backend endpoints with tenant and role checks.

For local development, Redis, Qdrant and RabbitMQ can run through Docker Compose. Supabase hosts the PostgreSQL database and authentication.

## 5. Application security

| Variable | Description | How to create | Value |
|---|---|---|---|
| `ENCRYPTION_KEY` | Optional application key for encrypting any future tenant integration credentials stored by the backend | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` | `__________` |

Do not add `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `NEXTAUTH_SECRET` or `NEXTAUTH_URL`. Supabase Auth owns token issuance and refresh. The application may define authorization/session behavior, but it must not mint a competing login token.

## 6. Mock business services

The MVP does not require Google, Gmail, Google Calendar, Slack, Jira or HubSpot accounts. Use local mock services and internal features.

| Variable | Description | Default |
|---|---|---|
| `ERP_BASE_URL` | Local mock ERP service | `http://localhost:8100` |
| `ATS_BASE_URL` | Local mock applicant tracking service | `http://localhost:8101` |
| `HRMS_BASE_URL` | Local mock HRMS service | `http://localhost:8102` |
| `CRM_BASE_URL` | Local mock CRM service, if implemented | `http://localhost:8103` |

These are local service URLs, not API credentials. Do not add API key/secret variables for mock services unless the mock service actually implements authentication.

## 7. Voice

| Variable | Description | Default |
|---|---|---|
| `STT_PROVIDER` | Speech-to-text provider | `faster_whisper` |
| `WHISPER_MODEL` | Local Whisper model size (`base`, `small`, `medium`) | `small` |
| `TTS_PROVIDER` | Text-to-speech provider | `edge_tts` |
| `TTS_VOICE` | Voice name | `en-IN-NeerjaNeural` |

The initial voice setup is local and does not require ElevenLabs or Azure credentials.

## 8. Observability

| Variable | Description | Default |
|---|---|---|
| `LANGFUSE_PUBLIC_KEY` | Langfuse project public key (optional if self-hosted without key auth) | blank |
| `LANGFUSE_SECRET_KEY` | Langfuse project secret key | blank |
| `LANGFUSE_HOST` | Langfuse endpoint | `http://localhost:3001` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OpenTelemetry collector endpoint | `http://localhost:4317` |

Prometheus, Grafana, Loki and Tempo are configured as infrastructure services in Docker Compose, not as application secrets. Their internal service URLs should live in service configuration unless the backend directly needs them.

## 9. Platform configuration

| Variable | Description | Default |
|---|---|---|
| `APP_ENV` | `development` or `production` | `development` |
| `APP_BASE_URL` | Backend URL | `http://localhost:8000` |
| `FRONTEND_URL` | Frontend URL | `http://localhost:3000` |
| `MAX_WORKFLOW_STEPS` | Hard step limit per workflow | `30` |
| `MAX_TOOL_CALLS_PER_TASK` | Tool-loop protection | `10` |
| `MAX_RETRIES` | Bounded retries | `3` |
| `APPROVAL_EXPIRY_HOURS` | Approval request expiry | `24` |

Per-tenant token budgets and payment approval thresholds belong in the database's organization settings and policy rules, not in one global environment variable.

## 10. Ready-to-copy `.env.example`

```env
# LLM PROVIDERS
GEMINI_API_KEY=your-gemini-api-key
GROQ_API_KEY=your-groq-api-key
OLLAMA_BASE_URL=http://localhost:11434
LITELLM_MASTER_KEY=sk-agentforce-litellm-proxy-master-key-placeholder

# Supabase Auth + PostgreSQL
NEXT_PUBLIC_SUPABASE_URL=https://your-project-ref.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=your-supabase-publishable-key
SUPABASE_JWT_SECRET=your-supabase-jwt-secret-min-32-chars
DATABASE_URL=

# Local infrastructure
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Local file storage (no S3 or MinIO)
STORAGE_PROVIDER=local
LOCAL_STORAGE_PATH=./storage/uploads
MAX_UPLOAD_SIZE_MB=25

# Application encryption (only if needed for stored integration credentials)
ENCRYPTION_KEY=


# Mock business services
ERP_BASE_URL=http://localhost:8100
ATS_BASE_URL=http://localhost:8101
HRMS_BASE_URL=http://localhost:8102
CRM_BASE_URL=http://localhost:8103

# Voice AI
STT_PROVIDER=faster_whisper
WHISPER_MODEL=small
TTS_PROVIDER=edge_tts
TTS_VOICE=en-IN-NeerjaNeural

# Observability
LANGFUSE_SECRET_KEY=your-langfuse-secret-key
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
LANGFUSE_HOST=http://localhost:3001
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Platform
APP_ENV=development
APP_BASE_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000
MAX_WORKFLOW_STEPS=30
MAX_TOOL_CALLS_PER_TASK=10
MAX_RETRIES=3
APPROVAL_EXPIRY_HOURS=24
```

## 11. Minimum setup to start

For the first local version, configure:

1. `SUPABASE_URL`
2. `SUPABASE_PUBLISHABLE_KEY`
3. `SUPABASE_JWKS_URL`
4. `DATABASE_URL`
5. `GEMINI_API_KEY` or `GROQ_API_KEY` (or use local Ollama)
6. `REDIS_URL`
7. `QDRANT_URL`
8. `RABBITMQ_URL` if RabbitMQ is enabled in the chosen development setup

`LITELLM_MASTER_KEY` is only needed for LiteLLM proxy mode. `ENCRYPTION_KEY` is only needed when the backend encrypts stored credentials. Leave optional observability and mock-service values at their defaults until those components are implemented.
