"""Gemini embedding and persistent Chroma utilities for manual chunks."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from pydantic import SecretStr

from plum360_assistant.config import ConfigurationError, Settings


DEFAULT_COLLECTION_NAME = "plum360_manual"


def create_gemini_embeddings(settings: Settings) -> Embeddings:
    """Create the Gemini embedding client without making a request."""
    if not settings.gemini_api_key:
        raise ConfigurationError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) is required to generate or query embeddings."
        )

    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    return GoogleGenerativeAIEmbeddings(
        model=settings.gemini_embedding_model,
        api_key=SecretStr(settings.gemini_api_key),
        vertexai=False,
    )


LOCAL_COLLECTION_NAME = "plum360_manual_local"
MODEL_CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "models"

# BGE retrieval models expect this instruction in front of short queries.
_BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class LocalEmbeddings(Embeddings):
    """On-device embeddings via fastembed (ONNX, CPU). No API key or quota.

    The model (about 130 MB for bge-small) downloads once into data/models/.
    """

    def __init__(self, model_name: str, cache_dir: Path = MODEL_CACHE_DIR) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model = None

    def _load(self):
        if self._model is None:
            from fastembed import TextEmbedding

            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = TextEmbedding(model_name=self.model_name, cache_dir=str(self.cache_dir))
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._load().embed(list(texts))]

    def embed_query(self, text: str) -> list[float]:
        if "bge" in self.model_name.lower():
            text = _BGE_QUERY_PREFIX + text
        return next(iter(self._load().embed([text]))).tolist()


def create_embeddings(settings: Settings) -> Embeddings:
    """Embeddings for the configured provider (local by default)."""
    if settings.embedding_provider == "gemini":
        return create_gemini_embeddings(settings)
    return LocalEmbeddings(settings.local_embedding_model)


def collection_for(settings: Settings) -> str:
    """Each embedding provider has its own collection (vector sizes differ)."""
    if settings.embedding_provider == "gemini":
        return DEFAULT_COLLECTION_NAME
    return LOCAL_COLLECTION_NAME


def create_chroma_store(
    settings: Settings,
    embeddings: Embeddings,
    collection_name: str | None = None,
) -> Chroma:
    """Open or create the persistent local Chroma collection."""
    collection_name = collection_name or collection_for(settings)
    persist_directory = Path(settings.chroma_persist_directory)
    persist_directory.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=str(persist_directory),
    )


def _chunk_documents(
    chunked_document: dict[str, Any],
) -> tuple[str, list[str], list[Document]]:
    """Validate chunk data and map metadata to Chroma-safe scalar values."""
    document_id = chunked_document.get("document_id")
    source = chunked_document.get("source")
    chunks = chunked_document.get("chunks")
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("Chunk file must contain a non-empty document_id.")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Chunk file must contain a non-empty source filename.")
    if not isinstance(chunks, list) or not chunks:
        raise ValueError("Chunk file must contain at least one chunk.")

    documents: list[Document] = []
    ids: list[str] = []
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        text = chunk.get("text")
        metadata = chunk.get("metadata")
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            raise ValueError("Every chunk must have a non-empty chunk_id.")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Chunk {chunk_id} has no text.")
        if not isinstance(metadata, dict):
            raise ValueError(f"Chunk {chunk_id} has invalid metadata.")
        if metadata.get("document_id") != document_id:
            raise ValueError(f"Chunk {chunk_id} has a mismatched document_id.")
        if metadata.get("source") != source:
            raise ValueError(f"Chunk {chunk_id} has a mismatched source.")

        page_numbers = metadata.get("page_numbers")
        if (
            not isinstance(page_numbers, list)
            or not page_numbers
            or any(not isinstance(page, int) or page < 1 for page in page_numbers)
        ):
            raise ValueError(f"Chunk {chunk_id} has invalid page numbers.")

        chroma_metadata: dict[str, str | int | float | bool] = {
            "document_id": document_id,
            "source": source,
            "chunk_id": chunk_id,
            "page_numbers": ",".join(str(page) for page in page_numbers),
        }
        single_page = metadata.get("page_number")
        if single_page is not None:
            if not isinstance(single_page, int) or single_page < 1:
                raise ValueError(f"Chunk {chunk_id} has an invalid page_number.")
            chroma_metadata["page_number"] = single_page
        section = metadata.get("section")
        if section is not None:
            if not isinstance(section, str):
                raise ValueError(f"Chunk {chunk_id} has an invalid section.")
            chroma_metadata["section"] = section

        for field in ("chunk_index", "start_index", "token_count"):
            value = metadata.get(field)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"Chunk {chunk_id} has an invalid {field}.")
            chroma_metadata[field] = value

        ids.append(chunk_id)
        documents.append(Document(page_content=text, metadata=chroma_metadata))

    if len(ids) != len(set(ids)):
        raise ValueError("Chunk IDs must be unique within a document.")

    return document_id, ids, documents


def index_chunks(
    chunked_document: dict[str, Any],
    vector_store: Chroma,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    max_batch_tokens: int | None = None,
    batch_delay_seconds: float = 0,
) -> dict[str, Any]:
    """Synchronize one document's chunks without creating duplicate records."""
    if max_batch_tokens is not None and max_batch_tokens < 1:
        raise ValueError("max_batch_tokens must be greater than zero.")
    if batch_delay_seconds < 0:
        raise ValueError("batch_delay_seconds must not be negative.")

    document_id, chunk_ids, documents = _chunk_documents(chunked_document)
    existing = vector_store.get(
        where={"document_id": document_id},
        include=["documents", "metadatas"],
    )
    existing_ids = existing.get("ids", [])
    existing_texts = existing.get("documents") or []
    existing_metadatas = existing.get("metadatas") or []
    if not (
        len(existing_ids) == len(existing_texts) == len(existing_metadatas)
    ):
        raise RuntimeError("Chroma returned inconsistent existing chunk data.")
    existing_by_id = {
        chunk_id: (text, metadata)
        for chunk_id, text, metadata in zip(
            existing_ids, existing_texts, existing_metadatas
        )
    }

    current_ids = set(chunk_ids)
    stale_ids = sorted(set(existing_ids) - current_ids)
    if stale_ids:
        vector_store.delete(ids=stale_ids)

    documents_to_write: list[Document] = []
    ids_to_write: list[str] = []
    added = 0
    updated = 0
    unchanged = 0
    for chunk_id, document in zip(chunk_ids, documents):
        existing_chunk = existing_by_id.get(chunk_id)
        if existing_chunk is None:
            added += 1
        elif (
            existing_chunk[0] == document.page_content
            and existing_chunk[1] == document.metadata
        ):
            unchanged += 1
            continue
        else:
            updated += 1
        ids_to_write.append(chunk_id)
        documents_to_write.append(document)

    if documents_to_write and max_batch_tokens is None:
        vector_store.add_documents(documents_to_write, ids=ids_to_write)
    elif documents_to_write:
        batches: list[tuple[list[Document], list[str]]] = []
        batch_documents: list[Document] = []
        batch_ids: list[str] = []
        batch_tokens = 0
        for document, chunk_id in zip(documents_to_write, ids_to_write):
            token_count = document.metadata["token_count"]
            if token_count > max_batch_tokens:
                raise ValueError(
                    f"Chunk {chunk_id} exceeds max_batch_tokens."
                )
            if batch_documents and batch_tokens + token_count > max_batch_tokens:
                batches.append((batch_documents, batch_ids))
                batch_documents = []
                batch_ids = []
                batch_tokens = 0
            batch_documents.append(document)
            batch_ids.append(chunk_id)
            batch_tokens += token_count
        if batch_documents:
            batches.append((batch_documents, batch_ids))

        for batch_index, (batch_docs, batch_chunk_ids) in enumerate(batches):
            if batch_index and batch_delay_seconds:
                time.sleep(batch_delay_seconds)
            vector_store.add_documents(batch_docs, ids=batch_chunk_ids)

    final_ids = vector_store.get(
        where={"document_id": document_id},
        include=["metadatas"],
    ).get("ids", [])
    return {
        "document_id": document_id,
        "collection": collection_name,
        "added": added,
        "updated": updated,
        "unchanged": unchanged,
        "deleted": len(stale_ids),
        "total_chunks": len(final_ids),
    }


def _result(text: str, metadata: dict[str, Any], distance: float | None) -> dict[str, Any]:
    raw_page_numbers = metadata.get("page_numbers", "")
    try:
        page_numbers = [int(value) for value in raw_page_numbers.split(",") if value]
    except (AttributeError, ValueError) as exc:
        raise RuntimeError("A retrieved chunk has invalid page-number metadata.") from exc
    return {
        "text": text,
        "distance": distance,
        "document_id": metadata["document_id"],
        "source": metadata["source"],
        "page_numbers": page_numbers,
        "section": metadata.get("section"),
        "chunk_id": metadata["chunk_id"],
    }


# Keyword indexes per vector store, rebuilt when the chunk count changes.
_keyword_indexes: dict[int, tuple[int, Any]] = {}


def _keyword_index(vector_store: Chroma):
    from plum360_assistant.keyword_search import KeywordIndex

    stored = vector_store.get(include=["documents", "metadatas"])
    count = len(stored["ids"])
    cached = _keyword_indexes.get(id(vector_store))
    if cached and cached[0] == count:
        return cached[1]
    index = KeywordIndex([
        {"text": text or "", "metadata": metadata or {}}
        for text, metadata in zip(stored["documents"], stored["metadatas"])
    ])
    _keyword_indexes[id(vector_store)] = (count, index)
    return index


def search_chunks(
    query: str,
    vector_store: Chroma,
    top_k: int = 5,
    hybrid: bool = True,
) -> dict[str, Any]:
    """Search the manual and return text with page-aware source metadata.

    With ``hybrid`` (the default), vector similarity and BM25 keyword rankings
    are fused, so exact manual terms are found even when their embedding ranks
    them low. ``distance`` is None for chunks found only by keyword.
    """
    if not query.strip():
        raise ValueError("Search query must not be empty.")
    if top_k < 1:
        raise ValueError("top_k must be greater than zero.")

    candidate_count = max(top_k * 4, 20) if hybrid else top_k
    matches = vector_store.similarity_search_with_score(query, k=candidate_count)
    by_id: dict[str, dict[str, Any]] = {}
    vector_ranking = []
    for document, distance in matches:
        result = _result(document.page_content, document.metadata, float(distance))
        by_id[result["chunk_id"]] = result
        vector_ranking.append(result["chunk_id"])

    if not hybrid:
        ordered = vector_ranking
    else:
        from plum360_assistant.keyword_search import reciprocal_rank_fusion

        index = _keyword_index(vector_store)
        keyword_ranking = []
        for position, _score in index.search(query, candidate_count):
            document = index.documents[position]
            chunk_id = document["metadata"].get("chunk_id")
            if not chunk_id:
                continue
            by_id.setdefault(chunk_id, _result(document["text"], document["metadata"], None))
            keyword_ranking.append(chunk_id)
        ordered = reciprocal_rank_fusion([vector_ranking, keyword_ranking])

    return {
        "query": query,
        "score_type": "hybrid rank (vector + BM25)" if hybrid else "distance (lower is closer)",
        "results": [by_id[chunk_id] for chunk_id in ordered[:top_k]],
    }
