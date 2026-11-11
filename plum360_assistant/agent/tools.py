"""Retrieval and verification tools for the Plum 360 manual agent."""

from __future__ import annotations

from typing import Any

from langchain_chroma import Chroma
from langchain_core.tools import tool

from plum360_assistant.vector_store import search_chunks


def _normalize_section(section: str | None) -> str:
    return (section or "").strip()


def _filter_section(results: list[dict[str, Any]], section: str | None) -> list[dict[str, Any]]:
    if not section:
        return results
    section_name = _normalize_section(section).lower()
    return [
        result
        for result in results
        if _normalize_section(result.get("section")).lower() == section_name
    ]


def _result_payload(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "results": results,
        "source_references": [
            {
                "source": result.get("source", "manual"),
                "page_numbers": result.get("page_numbers", []),
                "section": result.get("section"),
                "chunk_id": result.get("chunk_id"),
            }
            for result in results
        ],
    }


def search_manual_factory(vector_store: Chroma):
    @tool
    def search_manual(query: str, section: str | None = None, top_k: int = 3) -> dict[str, Any]:
        """Search the indexed Plum 360 manual for relevant passages."""
        payload = search_chunks(query, vector_store, top_k=top_k)
        results = payload.get("results", [])
        filtered = _filter_section(results, section)
        return _result_payload(filtered or results)

    return search_manual


def search_by_alarm_code_factory(vector_store: Chroma):
    @tool
    def search_by_alarm_code(alarm_code: str, top_k: int = 3) -> dict[str, Any]:
        """Search the manual for a specific alarm code such as E301 or N160."""
        normalized = (alarm_code or "").strip()
        if not normalized:
            return {"results": [], "source_references": []}
        query = f"{normalized} alarm"
        payload = search_chunks(query, vector_store, top_k=top_k)
        results = payload.get("results", [])
        return _result_payload(results)

    return search_by_alarm_code


def search_by_section_factory(vector_store: Chroma):
    @tool
    def search_by_section(section: str, query: str = "", top_k: int = 3) -> dict[str, Any]:
        """Retrieve relevant chunks from a named manual section."""
        section_name = _normalize_section(section)
        if not section_name:
            return {"results": [], "source_references": []}
        search_query = f"{query} {section_name}".strip() or section_name
        payload = search_chunks(search_query, vector_store, top_k=top_k)
        results = _filter_section(payload.get("results", []), section_name)
        return _result_payload(results or payload.get("results", []))

    return search_by_section


def retrieve_document_context_factory(vector_store: Chroma):
    @tool
    def retrieve_document_context(
        query: str,
        page_numbers: str | None = None,
        top_k: int = 3,
    ) -> dict[str, Any]:
        """Retrieve related context or nearby pages when more evidence is needed."""
        if not query.strip():
            return {"results": [], "source_references": []}
        payload = search_chunks(query, vector_store, top_k=top_k)
        results = payload.get("results", [])
        if page_numbers:
            requested_pages = {
                int(part.strip())
                for part in page_numbers.split(",")
                if part.strip()
            }
            results = [
                result
                for result in results
                if set(result.get("page_numbers", [])) & requested_pages
            ]
        return _result_payload(results)

    return retrieve_document_context


def verify_answer_factory():
    @tool
    def verify_answer(answer: str, source_references: list[str] | None = None) -> dict[str, Any]:
        """Check that an answer is supported by the retrieved source references."""
        normalized_answer = (answer or "").strip()
        refs = source_references or []
        supported = bool(normalized_answer and refs)
        reason = (
            "supported by the retrieved manual passages."
            if supported
            else "unsupported because the answer is missing manual evidence."
        )
        return {"supported": supported, "reason": reason}

    return verify_answer
