"""Application configuration loaded from environment variables."""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Platform configuration
    APP_ENV: str = "development"
    APP_BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    MAX_WORKFLOW_STEPS: int = 30
    MAX_TOOL_CALLS_PER_TASK: int = 10
    MAX_RETRIES: int = 3
    APPROVAL_EXPIRY_HOURS: int = 24

    # LLM Providers (Gemini, Groq, local Ollama only)
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LITELLM_MASTER_KEY: Optional[str] = None

    # Supabase Auth + PostgreSQL
    NEXT_PUBLIC_SUPABASE_URL: Optional[str] = None
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: Optional[str] = None
    SUPABASE_JWT_SECRET: Optional[str] = None
    SUPABASE_JWKS_URL: Optional[str] = None
    DATABASE_URL: str = "sqlite+aiosqlite:///./agentforce.db"
    DATABASE_URL_SYNC: Optional[str] = None

    # Local infrastructure
    REDIS_URL: str = "redis://localhost:6379/0"
    QDRANT_URL: str = "http://localhost:6333"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # Local file storage
    STORAGE_PROVIDER: str = "local"
    LOCAL_STORAGE_PATH: str = "./storage/uploads"
    MAX_UPLOAD_SIZE_MB: int = 25

    # Application encryption (optional, for tenant credentials)
    ENCRYPTION_KEY: Optional[str] = None

    # Mock business services
    ERP_BASE_URL: str = "http://localhost:8100"
    ATS_BASE_URL: str = "http://localhost:8101"
    HRMS_BASE_URL: str = "http://localhost:8102"
    CRM_BASE_URL: str = "http://localhost:8103"

    # Voice
    STT_PROVIDER: str = "faster_whisper"
    WHISPER_MODEL: str = "tiny"
    TTS_PROVIDER: str = "edge_tts"
    TTS_VOICE: str = "en-IN-NeerjaNeural"

    # Observability
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_BASE_URL: Optional[str] = "https://us.cloud.langfuse.com"
    LANGFUSE_HOST: str = "http://localhost:3001"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def resolved_database_url(self) -> str:
        if "sqlite" in self.DATABASE_URL and "./agentforce.db" in self.DATABASE_URL:
            backend_dir = Path(__file__).resolve().parent.parent.parent
            db_path = (backend_dir / "agentforce.db").as_posix()
            if self.DATABASE_URL.startswith("sqlite+aiosqlite:///"):
                return f"sqlite+aiosqlite:///{db_path}"
            return f"sqlite:///{db_path}"
        return self.DATABASE_URL

    @property
    def resolved_sync_database_url(self) -> str:
        if self.DATABASE_URL_SYNC:
            return self.DATABASE_URL_SYNC
        url = self.resolved_database_url
        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        if url.startswith("sqlite+aiosqlite://"):
            return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
        return url


settings = Settings()

