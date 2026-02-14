"""Application settings."""

from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    app_name: str = "openclaw-agent"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/openclaw"
    model_fallback_order: tuple[str, ...] = ("openai", "anthropic", "ollama")
    model_openai_model: str = "gpt-4.1"
    model_openai_base_url: str = "https://api.openai.com"
    model_openai_timeout_seconds: float = 60.0
    model_openai_max_retries: int = 2
    model_openai_initial_backoff_seconds: float = 0.5
    model_openai_max_backoff_seconds: float = 4.0
    model_anthropic_model: str = "claude-sonnet-4-5"
    model_anthropic_base_url: str = "https://api.anthropic.com"
    model_anthropic_version: str = "2023-06-01"
    model_anthropic_timeout_seconds: float = 60.0
    model_anthropic_max_retries: int = 2
    model_anthropic_initial_backoff_seconds: float = 0.5
    model_anthropic_max_backoff_seconds: float = 4.0
    model_ollama_model: str = "llama3.2"
    model_ollama_base_url: str = "http://localhost:11434"
    model_ollama_timeout_seconds: float = 90.0
    model_ollama_max_retries: int = 2
    model_ollama_initial_backoff_seconds: float = 0.5
    model_ollama_max_backoff_seconds: float = 4.0
    vm_provider: str = "disposable-vm"

    @classmethod
    def from_env(cls) -> "Settings":
        fallback_order = os.getenv("OPENCLAW_MODEL_FALLBACK_ORDER", "openai,anthropic,ollama")
        parsed_fallback = tuple(part.strip() for part in fallback_order.split(",") if part.strip())
        if not parsed_fallback:
            parsed_fallback = ("openai", "anthropic", "ollama")

        return cls(
            app_name=os.getenv("OPENCLAW_APP_NAME", "openclaw-agent"),
            app_env=os.getenv("OPENCLAW_APP_ENV", "development"),
            api_host=os.getenv("OPENCLAW_API_HOST", "0.0.0.0"),
            api_port=int(os.getenv("OPENCLAW_API_PORT", "8000")),
            redis_url=os.getenv("OPENCLAW_REDIS_URL", "redis://localhost:6379/0"),
            database_url=os.getenv(
                "OPENCLAW_DATABASE_URL",
                "postgresql+psycopg://postgres:postgres@localhost:5432/openclaw",
            ),
            model_fallback_order=parsed_fallback,
            model_openai_model=os.getenv("OPENCLAW_MODEL_OPENAI_MODEL", "gpt-4.1"),
            model_openai_base_url=os.getenv("OPENCLAW_MODEL_OPENAI_BASE_URL", "https://api.openai.com"),
            model_openai_timeout_seconds=float(
                os.getenv("OPENCLAW_MODEL_OPENAI_TIMEOUT_SECONDS", "60.0")
            ),
            model_openai_max_retries=int(os.getenv("OPENCLAW_MODEL_OPENAI_MAX_RETRIES", "2")),
            model_openai_initial_backoff_seconds=float(
                os.getenv("OPENCLAW_MODEL_OPENAI_INITIAL_BACKOFF_SECONDS", "0.5")
            ),
            model_openai_max_backoff_seconds=float(
                os.getenv("OPENCLAW_MODEL_OPENAI_MAX_BACKOFF_SECONDS", "4.0")
            ),
            model_anthropic_model=os.getenv("OPENCLAW_MODEL_ANTHROPIC_MODEL", "claude-sonnet-4-5"),
            model_anthropic_base_url=os.getenv(
                "OPENCLAW_MODEL_ANTHROPIC_BASE_URL",
                "https://api.anthropic.com",
            ),
            model_anthropic_version=os.getenv(
                "OPENCLAW_MODEL_ANTHROPIC_VERSION",
                "2023-06-01",
            ),
            model_anthropic_timeout_seconds=float(
                os.getenv("OPENCLAW_MODEL_ANTHROPIC_TIMEOUT_SECONDS", "60.0")
            ),
            model_anthropic_max_retries=int(
                os.getenv("OPENCLAW_MODEL_ANTHROPIC_MAX_RETRIES", "2")
            ),
            model_anthropic_initial_backoff_seconds=float(
                os.getenv("OPENCLAW_MODEL_ANTHROPIC_INITIAL_BACKOFF_SECONDS", "0.5")
            ),
            model_anthropic_max_backoff_seconds=float(
                os.getenv("OPENCLAW_MODEL_ANTHROPIC_MAX_BACKOFF_SECONDS", "4.0")
            ),
            model_ollama_model=os.getenv("OPENCLAW_MODEL_OLLAMA_MODEL", "llama3.2"),
            model_ollama_base_url=os.getenv(
                "OPENCLAW_MODEL_OLLAMA_BASE_URL",
                "http://localhost:11434",
            ),
            model_ollama_timeout_seconds=float(
                os.getenv("OPENCLAW_MODEL_OLLAMA_TIMEOUT_SECONDS", "90.0")
            ),
            model_ollama_max_retries=int(os.getenv("OPENCLAW_MODEL_OLLAMA_MAX_RETRIES", "2")),
            model_ollama_initial_backoff_seconds=float(
                os.getenv("OPENCLAW_MODEL_OLLAMA_INITIAL_BACKOFF_SECONDS", "0.5")
            ),
            model_ollama_max_backoff_seconds=float(
                os.getenv("OPENCLAW_MODEL_OLLAMA_MAX_BACKOFF_SECONDS", "4.0")
            ),
            vm_provider=os.getenv("OPENCLAW_VM_PROVIDER", "disposable-vm"),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
