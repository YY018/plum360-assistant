"""Environment-backed application settings."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


class ConfigurationError(ValueError):
    """Raised when an application setting has an invalid value."""


@dataclass(frozen=True)
class Settings:
    app_env: str
    gemini_api_key: str | None
    gemini_embedding_model: str
    gemini_chat_model: str
    gemini_chat_fallback_models: tuple[str, ...]
    chroma_persist_directory: Path
    # Which provider writes answers: "gemini" or "groq". Embeddings (manual
    # search) always use Gemini so the existing index stays valid.
    llm_provider: str = "gemini"
    groq_api_key: str | None = None
    groq_chat_model: str = "openai/gpt-oss-120b"
    groq_chat_fallback_models: tuple[str, ...] = ()


def load_settings() -> Settings:
    """Load project-local .env values and validate the supported settings."""
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env", override=False)

    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if app_env not in {"development", "testing", "production"}:
        raise ConfigurationError(
            "APP_ENV must be one of: development, testing, production."
        )

    gemini_embedding_model = os.getenv(
        "GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"
    ).strip()
    if not gemini_embedding_model:
        raise ConfigurationError("GEMINI_EMBEDDING_MODEL must not be empty.")

    gemini_chat_model = os.getenv(
        "GEMINI_CHAT_MODEL", "gemini-3.8-flash"
    ).strip()
    if not gemini_chat_model:
        raise ConfigurationError("GEMINI_CHAT_MODEL must not be empty.")

    # Tried in order when the primary chat model is overloaded, rate limited,
    # or unavailable. Set to an empty value to disable fallbacks.
    gemini_chat_fallback_models = tuple(
        model
        for model in (
            item.strip()
            for item in os.getenv(
                "GEMINI_CHAT_FALLBACK_MODELS",
                "gemini-3.6-flash,gemini-3.5-flash,gemini-3.5-flash-lite,"
                "gemini-3.7-flash,gemini-3.1-flash-lite,gemini-3.8-flash",
            ).split(",")
        )
        if model and model != gemini_chat_model
    )

    raw_chroma_directory = os.getenv(
        "CHROMA_PERSIST_DIRECTORY", "data/chroma_db"
    ).strip()
    if not raw_chroma_directory:
        raise ConfigurationError("CHROMA_PERSIST_DIRECTORY must not be empty.")
    chroma_persist_directory = Path(raw_chroma_directory)
    if not chroma_persist_directory.is_absolute():
        chroma_persist_directory = project_root / chroma_persist_directory

    raw_gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not raw_gemini_api_key:
        raw_gemini_api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    gemini_api_key = raw_gemini_api_key or None

    groq_api_key = os.getenv("GROQ_API_KEY", "").strip() or None
    groq_chat_model = (
        os.getenv("GROQ_CHAT_MODEL", "openai/gpt-oss-120b").strip()
        or "openai/gpt-oss-120b"
    )
    groq_chat_fallback_models = _model_list(
        os.getenv("GROQ_CHAT_FALLBACK_MODELS", "qwen/qwen3.8-27b,openai/gpt-oss-20b"), groq_chat_model
    )

    # Default to Groq when only its key is configured for chat.
    llm_provider = os.getenv("LLM_PROVIDER", "").strip().lower() or (
        "groq" if groq_api_key else "gemini"
    )
    if llm_provider not in {"gemini", "groq"}:
        raise ConfigurationError("LLM_PROVIDER must be one of: gemini, groq.")
    if llm_provider == "groq" and not groq_api_key:
        raise ConfigurationError("LLM_PROVIDER=groq requires GROQ_API_KEY.")

    return Settings(
        app_env=app_env,
        gemini_api_key=gemini_api_key,
        gemini_embedding_model=gemini_embedding_model,
        gemini_chat_model=gemini_chat_model,
        gemini_chat_fallback_models=gemini_chat_fallback_models,
        chroma_persist_directory=chroma_persist_directory,
        llm_provider=llm_provider,
        groq_api_key=groq_api_key,
        groq_chat_model=groq_chat_model,
        groq_chat_fallback_models=groq_chat_fallback_models,
    )


def _model_list(raw: str, primary: str) -> tuple[str, ...]:
    """Parse a comma-separated model list, dropping blanks and the primary."""
    return tuple(
        model for model in (item.strip() for item in raw.split(",")) if model and model != primary
    )
