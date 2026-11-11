"""Typed state for the Plum 360 LangGraph agent."""

from __future__ import annotations

from typing import TypedDict


class RetrievalMatch(TypedDict):
    """Normalized metadata for a retrieved manual chunk."""

    text: str
    distance: float
    document_id: str
    source: str
    page_numbers: list[int]
    section: str | None
    chunk_id: str


class AgentState(TypedDict, total=False):
    """State tracked across the agent workflow."""

    question: str
    conversation_history: list[str]
    # Role-tagged turns ({'role', 'content'}) for conversational replies.
    chat_history: list[dict[str, str]]
    # 'manual' (retrieval) or 'conversation' (direct LLM reply).
    route: str
    retrieved_documents: list[str]
    retrieval_results: list[RetrievalMatch]
    relevance_assessment: str
    generated_answer: str
    source_references: list[str]
    verification_result: str
    retry_count: int
    tool_name: str
    answer_supported: bool
