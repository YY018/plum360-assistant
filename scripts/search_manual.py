"""Search the persistent Plum 360 Chroma collection."""

from __future__ import annotations

import argparse
import json

from plum360_assistant.config import ConfigurationError, load_settings
from plum360_assistant.vector_store import (
    create_chroma_store,
    create_gemini_embeddings,
    search_chunks,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Search indexed manual chunks and show their source pages."
    )
    parser.add_argument("query", help="Question or search phrase.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--collection", default="plum360_manual")
    args = parser.parse_args()

    settings = load_settings()
    try:
        embeddings = create_gemini_embeddings(settings)
    except ConfigurationError as exc:
        parser.error(str(exc))

    vector_store = create_chroma_store(
        settings,
        embeddings,
        collection_name=args.collection,
    )
    result = search_chunks(args.query, vector_store, top_k=args.top_k)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
