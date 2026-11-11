"""FastAPI backend for the Plum 360 assistant."""

from __future__ import annotations

import json
import os
import threading
from contextlib import asynccontextmanager
from typing import Iterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from plum360_assistant.manual_pages import (
    ManualUnavailableError,
    page_count,
    page_labels,
    render_page_png,
)
from plum360_assistant.safety import MEDICAL_SCOPE_WARNING, validate_user_query
from plum360_assistant.service import (
    AssistantUnavailableError,
    answer_question,
    get_agent,
    stream_answer,
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    # Build the agent (index, embeddings, model clients) in the background at
    # startup so the first user question doesn't pay the setup cost. Errors are
    # ignored here; they are reported on the first request instead.
    def warm_up() -> None:
        try:
            get_agent()
        except Exception:
            pass
        try:
            page_labels()
        except Exception:
            pass

    threading.Thread(target=warm_up, daemon=True).start()
    yield


app = FastAPI(title="Plum 360 Assistant API", version="1.0.0", lifespan=lifespan)
_DEFAULT_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
]
# Extra browser origins (comma-separated), e.g. a deployed frontend URL.
_EXTRA_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEFAULT_ORIGINS + _EXTRA_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration and index problems are server-side setup issues (503);
# model failures come from the upstream Gemini API (502).
_ERROR_STATUS = {"configuration": 503, "index": 503, "model": 502}


class ChatRequest(BaseModel):
    question: str
    # Conversation history is owned by the client and sent with each request,
    # so concurrent users never share state on the server.
    history: list[dict[str, str]] | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[str]
    safety_message: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "plum360-assistant"}


@app.get("/manual")
def manual_info() -> dict:
    """Whether the manual PDF is available, its size, and printed page labels."""
    try:
        return {"available": True, "page_count": page_count(), "labels": page_labels()}
    except ManualUnavailableError:
        return {"available": False, "page_count": 0, "labels": {}}


@app.get("/manual/pages/{page_number}.png")
def manual_page(page_number: int) -> Response:
    """One rendered page of the locally stored manual (1-based PDF page)."""
    try:
        image = render_page_png(page_number)
    except ManualUnavailableError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=image,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=86400"},
    )


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    ok, safety_message = validate_user_query(request.question)
    if not ok:
        return ChatResponse(answer=safety_message, citations=[], safety_message=MEDICAL_SCOPE_WARNING)

    try:
        result = answer_question(request.question, request.history)
    except AssistantUnavailableError as exc:
        raise HTTPException(
            status_code=_ERROR_STATUS.get(exc.kind, 500), detail=exc.message
        ) from exc

    return ChatResponse(answer=result.answer, citations=result.citations)


@app.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Stream progress, answer tokens, and the final answer as NDJSON lines."""
    ok, safety_message = validate_user_query(request.question)

    def events() -> Iterator[str]:
        if not ok:
            stream = iter([{
                "type": "done",
                "answer": safety_message,
                "citations": [],
                "route": "safety",
                "safety_message": MEDICAL_SCOPE_WARNING,
            }])
        else:
            stream = stream_answer(request.question, request.history)
        for event in stream:
            yield json.dumps(event) + "\n"

    return StreamingResponse(
        events(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
