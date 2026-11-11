"""Tests for choosing between Groq and Gemini chat models."""

import os
import unittest
from unittest import mock

from plum360_assistant.config import ConfigurationError, load_settings
from plum360_assistant.llm import create_chat_model

_BASE_ENV = {
    "APP_ENV": "testing",
    "GEMINI_API_KEY": "",
    "GOOGLE_API_KEY": "",
    "GROQ_API_KEY": "",
    "LLM_PROVIDER": "",
    "GEMINI_CHAT_MODEL": "gemini-a",
    "GEMINI_CHAT_FALLBACK_MODELS": "gemini-b",
    "GROQ_CHAT_MODEL": "groq-a",
    "GROQ_CHAT_FALLBACK_MODELS": "groq-b",
}


def _settings(**overrides):
    env = {**_BASE_ENV, **overrides}
    with mock.patch.dict(os.environ, env), mock.patch("plum360_assistant.config.load_dotenv"):
        return load_settings()


def _model_names(runnable) -> list[str]:
    models = [runnable.runnable, *runnable.fallbacks] if hasattr(runnable, "fallbacks") else [runnable]
    return [getattr(model, "model_name", None) or getattr(model, "model", "") for model in models]


class ProviderSelectionTests(unittest.TestCase):
    def test_groq_key_alone_defaults_to_groq(self) -> None:
        self.assertEqual(_settings(GROQ_API_KEY="g").llm_provider, "groq")

    def test_gemini_is_default_without_groq_key(self) -> None:
        self.assertEqual(_settings(GEMINI_API_KEY="k").llm_provider, "gemini")

    def test_groq_provider_requires_groq_key(self) -> None:
        with self.assertRaises(ConfigurationError):
            _settings(LLM_PROVIDER="groq", GEMINI_API_KEY="k")

    def test_unknown_provider_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            _settings(LLM_PROVIDER="other", GEMINI_API_KEY="k")


class FallbackChainTests(unittest.TestCase):
    def test_groq_first_then_gemini_as_last_resort(self) -> None:
        model = create_chat_model(_settings(GROQ_API_KEY="g", GEMINI_API_KEY="k"))
        names = _model_names(model)
        self.assertEqual(names[:2], ["groq-a", "groq-b"])
        self.assertTrue(all("gemini" in name for name in names[2:]))
        self.assertEqual(len(names), 4)

    def test_gemini_first_then_groq_when_selected(self) -> None:
        model = create_chat_model(
            _settings(LLM_PROVIDER="gemini", GROQ_API_KEY="g", GEMINI_API_KEY="k")
        )
        names = _model_names(model)
        self.assertTrue(all("gemini" in name for name in names[:2]))
        self.assertEqual(names[2:], ["groq-a", "groq-b"])

    def test_no_chat_keys_is_a_configuration_error(self) -> None:
        with self.assertRaises(ConfigurationError):
            create_chat_model(_settings())


if __name__ == "__main__":
    unittest.main()
