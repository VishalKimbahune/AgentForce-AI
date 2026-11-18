# QA Environment Report: AgentForce AI

**Generated At:** 2026-11-11  
**Target Environment:** Local Dedicated QA Environment  
**Evaluation Scope:** Complete Application Testing & Validation

---

## 1. System Runtime & Host Information

| Component | Specification |
|---|---|
| **Operating System** | Windows 11 Professional (Build 10.0.26300, 64-bit AMD64) |
| **Python Runtime** | Python 3.12.6 (tags/v3.12.6:a4a2d2b) [MSC v.1940 64 bit] |
| **Node.js Runtime** | Node.js v24.15.0 |
| **Package Manager** | npm 11.12.1 |
| **Shell** | PowerShell 5.1 / 7.x |

---

## 2. Core Dependencies & Framework Versions

### Backend (`backend/pyproject.toml`)
- **Web Framework:** FastAPI `0.110.0`
- **ASGI Server:** Uvicorn (standard) `0.28.0` with WatchFiles reloader
- **ORM & DB Access:** SQLAlchemy `2.0.28`, aiosqlite `0.20.0`, asyncpg `0.29.0`, psycopg2-binary `2.9.9`
- **Validation:** Pydantic `2.6.0`, Pydantic-Settings `2.2.0`
- **Auth & Tokens:** PyJWT `2.8.0` (HS256)
- **HTTP Client:** HTTPX `0.27.0`
- **Vector Database:** Qdrant Client `1.8.0+`
- **Speech & Audio:** Faster-Whisper (CPU int8), Edge-TTS (`en-IN-NeerjaNeural`), PyDub, SoundFile
- **Document Ingestion:** PyPDF `4.0+`, python-docx `1.1+`
- **Orchestration:** LangGraph / StateGraph cognitive architecture
- **Observability:** OpenTelemetry Python SDK `1.23+`, Prometheus Client `0.20.0`

### Frontend (`frontend/package.json`)
- **Core Framework:** Next.js `14.2.15` (App Router)
- **UI Library:** React `18.3.1`, React DOM `18.3.1`
- **Styling:** Tailwind CSS `3.4.14`, PostCSS `8.4.47`, Autoprefixer `10.4.20`
- **Theme Engine:** `next-themes` `0.3.0` (Monochrome minimalist tokens)
- **Icons:** `lucide-react` `0.454.0`
- **Client Auth:** `@supabase/supabase-js` `2.45.0` with local demo session fallback

---

## 3. Active Background Services & Ports

| Service | Host / Port | Status | Health Evidence |
|---|---|---|---|
| **FastAPI Backend Core** | `http://127.0.0.1:8000` | **HEALTHY** | `GET /health` -> `HTTP 200` (`status: ok`, `version: 0.1.0`) |
| **FastAPI Readiness Probe** | `http://127.0.0.1:8000/ready` | **HEALTHY** | `GET /ready` -> `HTTP 200` (`database: connected`) |
| **Prometheus Metrics** | `http://127.0.0.1:8000/metrics` | **HEALTHY** | `GET /metrics` -> `HTTP 200` (standard exposition format) |
| **Next.js Web Portal** | `http://localhost:3000` | **HEALTHY** | `GET /` -> `HTTP 200` (Compiled, 16 static/dynamic routes) |
| **SQLite QA Database** | `backend/agentforce.db` | **HEALTHY** | Active, 6.4 MB populated with master seed dataset |
| **Qdrant Vector Store** | In-Memory / Local Service | **HEALTHY** | Vector collection initialized with tenant/role security filters |

---

## 4. Configuration Names Inventory (Sanitized)

All secrets and credentials have been verified as present in configuration structures and redacted from logs:

```ini
# LLM Providers & Gateways
GEMINI_API_KEY                  # Configured / Local fallback
GROQ_API_KEY                    # Configured / Local fallback
OLLAMA_BASE_URL                 # Configured (http://localhost:11434)
LITELLM_MASTER_KEY              # Configured (sanitized)

# Supabase Auth & PostgreSQL
NEXT_PUBLIC_SUPABASE_URL        # Configured (HTTPS URL)
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY # Configured (Public anon key)
SUPABASE_JWT_SECRET             # Configured (Min 32-char HMAC secret)
SUPABASE_JWKS_URL               # Configured (Well-known JWKS URL)
DATABASE_URL                    # Configured (sqlite+aiosqlite:///backend/agentforce.db)
DATABASE_URL_SYNC               # Configured (sqlite:///backend/agentforce.db)

# Messaging & Cache
REDIS_URL                       # Configured (redis://localhost:6379/0)
QDRANT_URL                      # Configured (http://localhost:6333)
RABBITMQ_URL                    # Configured (amqp://guest:guest@localhost:5672/)

# File Storage
STORAGE_PROVIDER                # "local"
LOCAL_STORAGE_PATH              # "./storage/uploads"
MAX_UPLOAD_SIZE_MB              # 25

# Business Mock Connectors
ERP_BASE_URL                    # Configured (http://localhost:8100)
ATS_BASE_URL                    # Configured (http://localhost:8101)
HRMS_BASE_URL                   # Configured (http://localhost:8102)
CRM_BASE_URL                    # Configured (http://localhost:8103)

# Voice Configuration
STT_PROVIDER                    # "faster_whisper"
WHISPER_MODEL                   # "small" / "tiny"
TTS_PROVIDER                    # "edge_tts"
TTS_VOICE                       # "en-IN-NeerjaNeural"

# Platform Governance
APP_ENV                         # "development"
APP_BASE_URL                    # "http://localhost:8000"
FRONTEND_URL                    # "http://localhost:3000"
MAX_WORKFLOW_STEPS              # 30
MAX_TOOL_CALLS_PER_TASK         # 10
MAX_RETRIES                     # 3
APPROVAL_EXPIRY_HOURS           # 24
```

---

## 5. Architectural Stubs, Mocks, and Limitations

1. **Database Fallback:** The active instance uses local SQLite (`backend/agentforce.db`) via `aiosqlite`. All tables and foreign keys are enforced; production PostgreSQL migration scripts are located in `backend/alembic/`.
2. **Third-Party OAuth & Cloud Connectors:** In accordance with Project Rule 2 (Free tiers and local only), all external services (Google Calendar, Gmail, Jira, Slack, Workday, SAP) are executed via deterministic local mock adapters (`app.services.tools.mock_erp`, `app.services.tools.registry`). Real monetary disbursements or external emails are never transmitted.
3. **Voice Processing:** Whisper runs locally on CPU (`int8` precision) without external cloud speech API dependencies. Edge-TTS runs via local asynchronous synthesis.
4. **LLM Gateway:** When external live model keys are omitted or rate-limited, the 3-tier circuit breaker falls back to local deterministic responses or Ollama.

