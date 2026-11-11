"""Local Chroma tests using deterministic fake embeddings."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chromadb
from langchain_chroma import Chroma
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from plum360_assistant.config import ConfigurationError, load_settings
from plum360_assistant.vector_store import (
    create_gemini_embeddings,
    index_chunks,
    search_chunks,
)


def _chunked_document() -> dict:
    return {
        "document_id": "plum360_test",
        "source": "manual.pdf",
        "page_count": 2,
        "chunks": [
            {
                "chunk_id": "plum360_test-chunk-0000",
                "text": "Alarm E301 has a documented cause and warning.",
                "metadata": {
                    "document_id": "plum360_test",
                    "source": "manual.pdf",
                    "page_number": 12,
                    "page_numbers": [12],
                    "section": "Alarms",
                    "chunk_index": 0,
                    "start_index": 0,
                    "token_count": 10,
                    "character_count": 47,
                },
            },
            {
                "chunk_id": "plum360_test-chunk-0001",
                "text": "The connectivity engine communicates with other systems.",
                "metadata": {
                    "document_id": "plum360_test",
                    "source": "manual.pdf",
                    "page_number": None,
                    "page_numbers": [20, 21],
                    "section": None,
                    "chunk_index": 1,
                    "start_index": 50,
                    "token_count": 11,
                    "character_count": 56,
                },
            },
        ],
    }


def _ephemeral_store(collection_name: str) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=DeterministicFakeEmbedding(size=16),
        client=chromadb.EphemeralClient(),
    )


class VectorStoreTests(unittest.TestCase):
    def test_requires_api_key_for_gemini_embeddings(self) -> None:
        with patch.dict(
            os.environ, {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": ""}, clear=True
        ):
            settings = load_settings()

        with self.assertRaisesRegex(ConfigurationError, "GEMINI_API_KEY"):
            create_gemini_embeddings(settings)

    def test_creates_gemini_embedding_client_without_an_api_request(self) -> None:
        values = {
            "GEMINI_API_KEY": "test-key",
            "GEMINI_EMBEDDING_MODEL": "test-embedding-model",
        }
        with patch.dict(os.environ, values, clear=True):
            settings = load_settings()

        embeddings = create_gemini_embeddings(settings)

        self.assertIsInstance(embeddings, GoogleGenerativeAIEmbeddings)
        self.assertEqual(embeddings.model, "test-embedding-model")
        api_key = embeddings.google_api_key
        if api_key is None:
            self.fail("Gemini client did not retain the provided API key.")
        self.assertEqual(api_key.get_secret_value(), "test-key")
        self.assertFalse(embeddings.vertexai)

    def test_indexing_is_idempotent_and_search_preserves_metadata(self) -> None:
        store = _ephemeral_store("manual_test_idempotent")
        chunks = _chunked_document()

        first = index_chunks(
            chunks, store, collection_name="manual_test_idempotent"
        )
        second = index_chunks(
            chunks, store, collection_name="manual_test_idempotent"
        )
        result = search_chunks(chunks["chunks"][0]["text"], store, top_k=1)

        self.assertEqual(first["added"], 2)
        self.assertEqual(first["total_chunks"], 2)
        self.assertEqual(second["added"], 0)
        self.assertEqual(second["unchanged"], 2)
        self.assertEqual(result["results"][0]["page_numbers"], [12])
        self.assertEqual(result["results"][0]["section"], "Alarms")
        self.assertEqual(result["results"][0]["chunk_id"], "plum360_test-chunk-0000")

    def test_updates_changed_chunks_and_removes_stale_chunks(self) -> None:
        store = _ephemeral_store("manual_test_updates")
        original = _chunked_document()
        index_chunks(original, store, collection_name="manual_test_updates")

        changed = _chunked_document()
        changed["chunks"] = [dict(changed["chunks"][0])]
        changed["chunks"][0] = {
            **changed["chunks"][0],
            "text": "Alarm E301 has updated documented context.",
        }
        updated = index_chunks(
            changed, store, collection_name="manual_test_updates"
        )

        self.assertEqual(updated["updated"], 1)
        self.assertEqual(updated["deleted"], 1)
        self.assertEqual(updated["total_chunks"], 1)

    def test_indexing_paces_token_bounded_batches(self) -> None:
        store = _ephemeral_store("manual_test_batches")
        chunks = _chunked_document()

        with patch("plum360_assistant.vector_store.time.sleep") as sleep:
            result = index_chunks(
                chunks,
                store,
                collection_name="manual_test_batches",
                max_batch_tokens=15,
                batch_delay_seconds=30,
            )

        self.assertEqual(result["added"], 2)
        self.assertEqual(result["total_chunks"], 2)
        sleep.assert_called_once_with(30)

    def test_persistent_collection_survives_a_new_process(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "persistent-chroma"
            chunk_data = json.dumps(_chunked_document())
            write_script = """
import json
import sys
from dataclasses import replace
from pathlib import Path
from langchain_core.embeddings import DeterministicFakeEmbedding
from plum360_assistant.config import load_settings
from plum360_assistant.vector_store import create_chroma_store, index_chunks
settings = replace(load_settings(), chroma_persist_directory=Path(sys.argv[1]))
store = create_chroma_store(settings, DeterministicFakeEmbedding(size=16), \"manual_persist_test\")
print(json.dumps(index_chunks(json.loads(sys.argv[2]), store, \"manual_persist_test\")))
"""
            write_result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    write_script,
                    str(database_path),
                    chunk_data,
                ],
                cwd=project_root,
                check=True,
                capture_output=True,
                text=True,
            )
            read_script = """
import json
import sys
from dataclasses import replace
from pathlib import Path
from langchain_core.embeddings import DeterministicFakeEmbedding
from plum360_assistant.config import load_settings
from plum360_assistant.vector_store import create_chroma_store, search_chunks
settings = replace(load_settings(), chroma_persist_directory=Path(sys.argv[1]))
store = create_chroma_store(settings, DeterministicFakeEmbedding(size=16), \"manual_persist_test\")
print(json.dumps(search_chunks(\"Alarm E301 has a documented cause and warning.\", store, 1)))
"""
            read_result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    read_script,
                    str(database_path),
                ],
                cwd=project_root,
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(json.loads(write_result.stdout)["total_chunks"], 2)
        search_result = json.loads(read_result.stdout)
        self.assertEqual(
            search_result["results"][0]["chunk_id"],
            "plum360_test-chunk-0000",
        )
        self.assertEqual(search_result["results"][0]["page_numbers"], [12])


if __name__ == "__main__":
    unittest.main()
