"""Configuration validation tests."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from plum360_assistant.config import ConfigurationError, load_settings


class LoadSettingsTests(unittest.TestCase):
    def test_defaults_allow_placeholder_app_without_api_key(self) -> None:
        with patch("plum360_assistant.config.load_dotenv"), patch.dict(
            os.environ, {}, clear=True
        ):
            settings = load_settings()

        self.assertEqual(settings.app_env, "development")
        self.assertEqual(settings.gemini_embedding_model, "gemini-embedding-001")
        self.assertEqual(settings.gemini_chat_model, "gemini-3.8-flash")
        self.assertEqual(
            settings.chroma_persist_directory,
            Path(__file__).resolve().parents[1] / "data" / "chroma_db",
        )
        self.assertFalse(settings.gemini_api_key)

    def test_reads_and_trims_environment_values(self) -> None:
        values = {
            "APP_ENV": " testing ",
            "GEMINI_EMBEDDING_MODEL": " example-embedding-model ",
            "GEMINI_CHAT_MODEL": " example-chat-model ",
            "CHROMA_PERSIST_DIRECTORY": " custom/vector-store ",
            "GEMINI_API_KEY": " example-gemini-key ",
        }
        with patch.dict(os.environ, values, clear=True):
            settings = load_settings()

        self.assertEqual(settings.app_env, "testing")
        self.assertEqual(settings.gemini_embedding_model, "example-embedding-model")
        self.assertEqual(settings.gemini_chat_model, "example-chat-model")
        self.assertEqual(
            settings.chroma_persist_directory,
            Path(__file__).resolve().parents[1] / "custom" / "vector-store",
        )
        self.assertEqual(settings.gemini_api_key, "example-gemini-key")

    def test_reads_google_api_key_alias(self) -> None:
        values = {"GEMINI_API_KEY": "  ", "GOOGLE_API_KEY": " google-key "}
        with patch.dict(os.environ, values, clear=True):
            settings = load_settings()

        self.assertEqual(settings.gemini_api_key, "google-key")

    def test_rejects_unsupported_environment(self) -> None:
        with patch.dict(os.environ, {"APP_ENV": "staging"}, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "APP_ENV"):
                load_settings()

    def test_rejects_empty_embedding_model_name(self) -> None:
        with patch.dict(
            os.environ, {"GEMINI_EMBEDDING_MODEL": "  "}, clear=True
        ):
            with self.assertRaisesRegex(
                ConfigurationError, "GEMINI_EMBEDDING_MODEL"
            ):
                load_settings()

    def test_rejects_empty_chat_model_name(self) -> None:
        with patch.dict(os.environ, {"GEMINI_CHAT_MODEL": "  "}, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "GEMINI_CHAT_MODEL"):
                load_settings()


if __name__ == "__main__":
    unittest.main()
