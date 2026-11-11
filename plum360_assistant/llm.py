"""Chat model setup (Groq or Gemini) for concise manual-grounded answers."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

from plum360_assistant.config import ConfigurationError, Settings

# A short timeout lets an overloaded model fail fast so the next model in the
# fallback chain can answer instead of the user waiting.
_REQUEST_TIMEOUT_SECONDS = 25


def _gemini_client(settings: Settings, model: str) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model=model,
        api_key=SecretStr(settings.gemini_api_key or ""),
        vertexai=False,
        temperature=0,
        retries=0,
        request_timeout=_REQUEST_TIMEOUT_SECONDS,
        # Summarizing retrieved passages needs no extended reasoning; disabling
        # thinking cuts time-to-first-token from many seconds to about one.
        thinking_budget=0,
    )


def _groq_reasoning_options(model: str) -> dict[str, str]:
    """Keep reasoning models fast and keep their reasoning out of the answer."""
    name = model.lower()
    if name.startswith("openai/gpt-oss"):
        return {"reasoning_format": "hidden", "reasoning_effort": "low"}
    if "qwen3" in name:
        return {"reasoning_format": "hidden"}
    return {}


def _groq_client(settings: Settings, model: str) -> BaseChatModel:
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=model,
        api_key=SecretStr(settings.groq_api_key or ""),
        temperature=0,
        # The free tier has a tokens-per-minute cap; Groq's 429 responses say
        # how long to wait, and the SDK honors that before retrying.
        max_retries=2,
        timeout=_REQUEST_TIMEOUT_SECONDS,
        **_groq_reasoning_options(model),
    )


def _gemini_chain(settings: Settings) -> list[BaseChatModel]:
    if not settings.gemini_api_key:
        return []
    models = (settings.gemini_chat_model, *settings.gemini_chat_fallback_models)
    return [_gemini_client(settings, model) for model in models]


def _groq_chain(settings: Settings) -> list[BaseChatModel]:
    if not settings.groq_api_key:
        return []
    models = (settings.groq_chat_model, *settings.groq_chat_fallback_models)
    return [_groq_client(settings, model) for model in models]


def create_chat_model(settings: Settings) -> BaseChatModel | Runnable:
    """Create the chat model chain without making a request.

    The configured provider's models are tried first, in order; the other
    provider's models (when its key is set) act as a last resort. Any failed
    call (overload, rate limit, timeout, retired model) moves to the next model.
    """
    if settings.llm_provider == "groq":
        chain = _groq_chain(settings) + _gemini_chain(settings)
    else:
        chain = _gemini_chain(settings) + _groq_chain(settings)

    if not chain:
        raise ConfigurationError(
            "Set GROQ_API_KEY or GEMINI_API_KEY to generate summarized answers."
        )
    primary, fallbacks = chain[0], chain[1:]
    return primary.with_fallbacks(fallbacks) if fallbacks else primary


# Backwards-compatible name used by the service and scripts.
create_gemini_chat_model = create_chat_model
