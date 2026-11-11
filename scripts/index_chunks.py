"""Embed chunk JSON (locally or with Gemini) and synchronize it to local Chroma."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from plum360_assistant.config import ConfigurationError, load_settings
from plum360_assistant.vector_store import (
    create_chroma_store,
    collection_for,
    create_embeddings,
    index_chunks,
)

GEMINI_BATCH_TOKEN_LIMIT = 10_000
GEMINI_BATCH_DELAY_SECONDS = 30


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate embeddings for document chunks and index them locally."
    )
    parser.add_argument(
        "chunks_json",
        type=Path,
        help="Chunk JSON produced by scripts.chunk_documents.",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Chroma collection name (default: chosen by EMBEDDING_PROVIDER).",
    )
    args = parser.parse_args()

    settings = load_settings()
    try:
        embeddings = create_embeddings(settings)
    except ConfigurationError as exc:
        parser.error(str(exc))

    collection = args.collection or collection_for(settings)
    # Gemini's free tier needs paced batches; local embedding does not.
    remote = settings.embedding_provider == "gemini"
    vector_store = create_chroma_store(
        settings,
        embeddings,
        collection_name=collection,
    )
    chunked_document = json.loads(args.chunks_json.read_text(encoding="utf-8"))
    result = index_chunks(
        chunked_document,
        vector_store,
        collection_name=collection,
        max_batch_tokens=GEMINI_BATCH_TOKEN_LIMIT if remote else 200_000,
        batch_delay_seconds=GEMINI_BATCH_DELAY_SECONDS if remote else 0,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
