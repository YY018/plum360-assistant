"""Tests for choosing local or Gemini embeddings and their collections."""

import os
import unittest
from unittest import mock

from plum360_assistant.config import ConfigurationError, load_settings
from plum360_assistant.keyword_search import index_terms
from plum360_assistant.vector_store import (
    DEFAULT_COLLECTION_NAME,
    LOCAL_COLLECTION_NAME,
    LocalEmbeddings,
    collection_for,
    create_embeddings,
)


def _settings(**env):
    base = {"APP_ENV": "testing", "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "GROQ_API_KEY": "g",
            "LLM_PROVIDER": "", "EMBEDDING_PROVIDER": "", "LOCAL_EMBEDDING_MODEL": ""}
    with mock.patch.dict(os.environ, {**base, **env}), mock.patch("plum360_assistant.config.load_dotenv"):
        return load_settings()


class EmbeddingProviderTests(unittest.TestCase):
    def test_local_is_the_default_and_needs_no_key(self) -> None:
        settings = _settings()
        self.assertEqual(settings.embedding_provider, "local")
        embeddings = create_embeddings(settings)
        self.assertIsInstance(embeddings, LocalEmbeddings)
        self.assertEqual(embeddings.model_name, "BAAI/bge-small-en-v1.5")
        self.assertIsNone(embeddings._model)  # the model loads lazily, on first use
        self.assertEqual(collection_for(settings), LOCAL_COLLECTION_NAME)

    def test_gemini_embeddings_use_their_own_collection(self) -> None:
        settings = _settings(EMBEDDING_PROVIDER="gemini", GEMINI_API_KEY="k")
        self.assertEqual(collection_for(settings), DEFAULT_COLLECTION_NAME)
        self.assertNotIsInstance(create_embeddings(settings), LocalEmbeddings)

    def test_gemini_embeddings_require_a_key(self) -> None:
        with self.assertRaises(ConfigurationError):
            create_embeddings(_settings(EMBEDDING_PROVIDER="gemini"))

    def test_unknown_provider_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            _settings(EMBEDDING_PROVIDER="other")

    def test_groq_only_configuration_has_no_gemini_fallbacks(self) -> None:
        from plum360_assistant.llm import create_chat_model

        model = create_chat_model(_settings())
        names = [m.model_name for m in [model.runnable, *model.fallbacks]]
        self.assertTrue(names)
        self.assertFalse(any("gemini" in name for name in names))


class PhraseTermTests(unittest.TestCase):
    def test_adjacent_words_become_phrase_terms(self) -> None:
        self.assertEqual(
            index_terms("delivery rate range"),
            ["delivery", "rate", "range", "delivery_rate", "rate_range"],
        )


if __name__ == "__main__":
    unittest.main()
