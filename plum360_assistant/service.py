"""Shared question-answering service used by the Streamlit app and the API."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable, Iterator

from plum360_assistant.config import ConfigurationError
from plum360_assistant.conversation_memory import ConversationMemory


class AssistantUnavailableError(RuntimeError):
    """Raised with a user-facing message when the assistant cannot answer.

    ``kind`` distinguishes configuration, index, and model failures so callers
    can surface the right message (or HTTP status) instead of a generic one.
    """

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass(frozen=True)
class AssistantAnswer:
    answer: str
    citations: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def get_agent() -> Any:
    """Build the LangGraph agent once per process and reuse it.

    Failures are not cached by ``lru_cache``, so a fixed configuration is picked
    up on the next call without restarting.
    """
    from plum360_assistant.agent import build_agent_graph
    from plum360_assistant.config import load_settings
    from plum360_assistant.llm import create_chat_model
    from plum360_assistant.vector_store import (
        create_chroma_store,
        create_gemini_embeddings,
    )

    try:
        settings = load_settings()
        embeddings = create_gemini_embeddings(settings)
        store = create_chroma_store(settings, embeddings)
        llm = create_chat_model(settings)
    except ConfigurationError as exc:
        raise AssistantUnavailableError("configuration", f"Configuration error: {exc}") from exc

    try:
        indexed_chunks = store._collection.count()
    except Exception as exc:  # Chroma storage problems (missing/corrupt files).
        raise AssistantUnavailableError(
            "index", f"The local manual index could not be opened: {exc}"
        ) from exc
    if indexed_chunks == 0:
        raise AssistantUnavailableError(
            "index",
            "The manual index is empty. Run `python -m scripts.index_chunks "
            "data/processed/plum360_manual_chunks.json` first.",
        )

    return build_agent_graph(store, llm)


_NO_ANSWER = "I could not find enough evidence in the manual."

# Graph nodes whose LLM output is the user-facing answer (router output is not).
_ANSWER_NODES = {"respond_conversationally", "generate_grounded_answer"}

# Status shown to the user after each graph node finishes.
_STAGE_AFTER_NODE = {
    "retrieve_manual_information": "reading",
    "refine_search": "refining",
}


def _initial_state(question: str, history: Iterable[dict[str, str]] | None, max_turns: int) -> dict:
    memory = ConversationMemory(max_turns=max_turns)
    memory.load_from_messages(history or [])
    return {
        "question": question,
        "conversation_history": memory.get_recent_messages(),
        "chat_history": memory.get_history(),
    }


def _model_error(exc: Exception) -> AssistantUnavailableError:
    detail = " ".join(str(exc).split())[:300] or type(exc).__name__
    return AssistantUnavailableError(
        "model", f"The language model could not complete the request: {detail}"
    )


def answer_question(
    question: str, history: Iterable[dict[str, str]] | None = None, max_turns: int = 8
) -> AssistantAnswer:
    """Run the manual agent for one question with this caller's own history."""
    graph = get_agent()
    try:
        state = graph.invoke(_initial_state(question, history, max_turns))
    except AssistantUnavailableError:
        raise
    except Exception as exc:
        raise _model_error(exc) from exc

    answer = state.get("generated_answer") or _NO_ANSWER
    return AssistantAnswer(answer=answer, citations=list(state.get("source_references", [])))


def stream_answer(
    question: str, history: Iterable[dict[str, str]] | None = None, max_turns: int = 8
) -> Iterator[dict[str, Any]]:
    """Run the agent and yield progress events as they happen.

    Event shapes:
      {"type": "status", "stage": "thinking" | "searching" | "reading" | "refining"}
      {"type": "token", "text": "..."}    answer text as Gemini writes it
      {"type": "done", "answer": "...", "citations": [...], "route": "..."}
      {"type": "error", "kind": "...", "message": "..."}

    The ``done`` answer is authoritative: the manual path may post-process the
    streamed text (complete alarm actions) or replace it if verification fails.
    """
    from plum360_assistant.agent.router import message_text

    yield {"type": "status", "stage": "thinking"}
    try:
        graph = get_agent()
        final_state: dict[str, Any] = {}
        for mode, payload in graph.stream(
            _initial_state(question, history, max_turns),
            stream_mode=["updates", "messages", "values"],
        ):
            if mode == "messages":
                chunk, metadata = payload
                if metadata.get("langgraph_node") in _ANSWER_NODES:
                    text = message_text(chunk)
                    if text:
                        yield {"type": "token", "text": text}
            elif mode == "updates":
                for node, update in payload.items():
                    if node == "route_intent" and (update or {}).get("route") == "manual":
                        yield {"type": "status", "stage": "searching"}
                    elif node in _STAGE_AFTER_NODE:
                        yield {"type": "status", "stage": _STAGE_AFTER_NODE[node]}
            elif mode == "values":
                final_state = payload
    except AssistantUnavailableError as exc:
        yield {"type": "error", "kind": exc.kind, "message": exc.message}
        return
    except Exception as exc:
        error = _model_error(exc)
        yield {"type": "error", "kind": error.kind, "message": error.message}
        return

    yield {
        "type": "done",
        "answer": final_state.get("generated_answer") or _NO_ANSWER,
        "citations": list(final_state.get("source_references", [])),
        "sources": source_pages(final_state),
        "route": final_state.get("route", ""),
    }


def source_pages(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Pair each citation with its PDF page numbers so clients can show pages."""
    references = state.get("source_references") or []
    results = state.get("retrieval_results") or []
    return [
        {"citation": reference, "pages": [int(page) for page in (result.get("page_numbers") or [])]}
        for reference, result in zip(references, results)
    ]
