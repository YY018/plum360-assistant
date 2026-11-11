"""Decide whether a message needs the manual (RAG) or a conversational reply."""

from __future__ import annotations

import re
from typing import Any, Iterable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

MANUAL = "manual"
CONVERSATION = "conversation"

# Device vocabulary: any of these means the user wants manual content, so we
# skip the LLM router call entirely (saves latency and free-tier quota).
_MANUAL_TERMS = re.compile(
    r"\b(alarms?|alerts?|errors?|codes?|faults?|malfunction|troubleshoot\w*|pumps?|"
    r"infus\w*|cassettes?|administration\s+sets?|prim(e|ing)|occlusions?|"
    r"air[- ]in[- ]line|batter(y|ies)|charg\w*|clean\w*|disinfect\w*|maintenance|"
    r"inspect\w*|service|specifications?|warnings?|cautions?|precautions?|"
    r"drug\s+librar(y|ies)|secondary|piggyback|bolus|titrat\w*|rate|volume|vtbi|"
    r"dose|dosing|setup|set\s+up|install\w*|load\w*|power|display|screen|keypad|"
    r"connectivity|wireless|network|mounting|pole\s+clamp|manual|section|page|"
    r"plum|hospira|icu\s*medical|lockout|standby|nurse\s+call|distal|proximal)\b",
    re.IGNORECASE,
)
_ALARM_CODE = re.compile(r"\b[A-Za-z]\d{2,4}\b")

# Short social messages that never need retrieval.
_SMALL_TALK = re.compile(
    r"^\s*(hi+|hello+|hey+|hiya|yo|howdy|greetings|good\s+(morning|afternoon|evening|night)|"
    r"how\s+(are|r)\s+(you|u)|how\s+(are|r)\s+(you|u)\s+doing|how\s+(you|u)\s+doing|"
    r"how'?s\s+it\s+going|what'?s\s+up|sup|wh?at\s+can\s+(you|u)\s+do|who\s+are\s+(you|u)|"
    r"what\s+are\s+(you|u)|help|thanks?(\s+you)?|thank\s+(you|u)|thx|ty|cheers|"
    r"ok(ay)?|cool|great|nice|awesome|perfect|got\s+it|bye|goodbye|see\s+(you|ya))"
    r"[\s!.?,]*(there|again|so\s+much|a\s+lot|buddy|mate)?[\s!.?,]*$",
    re.IGNORECASE,
)

# References to the previous turn ("explain that", "shorter", "in simple words").
_FOLLOW_UP = re.compile(
    r"\b(explain\s+(that|this|it)|simpl(er|ify|e\s+words)|shorter|summari[sz]e\s+(that|this|it)|"
    r"rephrase|what\s+do\s+you\s+mean|say\s+(that|it)\s+again|in\s+other\s+words|"
    r"bullet\s+points?|eli5)\b",
    re.IGNORECASE,
)

ROUTER_PROMPT = (
    "You route messages for a Plum 360 infusion pump manual assistant.\n"
    "Reply with exactly one word:\n"
    "MANUAL - the user wants information about the Plum 360 device, its alarms, "
    "procedures, features, settings, safety, cleaning, or specifications.\n"
    "CHAT - greetings, small talk, thanks, questions about the assistant itself, "
    "requests to rephrase or simplify the previous answer, or anything unrelated "
    "to the device.\n\n"
    "Recent conversation:\n{history}\n\nMessage: {question}\n\nRoute:"
)

CONVERSATION_SYSTEM_PROMPT = (
    "You are the Plum 360 manual assistant, a friendly, concise reference helper "
    "for the Plum 360 infusion pump System Operating Manual.\n"
    "- Reply naturally to greetings, small talk, and thanks in one to three short "
    "sentences, and invite the user to ask about the manual when it fits.\n"
    "- If asked what you can do: you search the System Operating Manual and "
    "summarize alarms, troubleshooting, setup, priming, programming features, "
    "cleaning, maintenance, and specifications, citing manual pages.\n"
    "- If asked to rephrase, simplify, or summarize your previous answer, do so "
    "using ONLY the content of that previous answer. Add no new facts.\n"
    "- Never answer device, clinical, medication, dosing, or alarm questions from "
    "your own general knowledge; tell the user to ask it as a manual question so "
    "you can look it up.\n"
    "- Politely decline unrelated tasks (coding, trivia, essays) and explain that "
    "you are focused on the Plum 360 manual.\n"
    "- You are not a medical device and must not give clinical advice."
)


def classify_heuristically(question: str) -> str | None:
    """Return a route for obvious messages, or None when the LLM should decide."""
    text = question.strip()
    if not text:
        return CONVERSATION
    if _SMALL_TALK.match(text) or _FOLLOW_UP.search(text):
        return CONVERSATION
    if _ALARM_CODE.search(text) or _MANUAL_TERMS.search(text):
        return MANUAL
    return None


def parse_route(text: str) -> str:
    """Map the router model's reply to a route, defaulting to the manual."""
    return CONVERSATION if re.search(r"\bCHAT\b", text or "", re.IGNORECASE) else MANUAL


def format_history(history: Iterable[dict[str, str]], limit: int = 4) -> str:
    turns = list(history)[-limit:]
    if not turns:
        return "(none)"
    return "\n".join(
        f"{turn.get('role', 'user')}: {(turn.get('content') or '')[:400]}" for turn in turns
    )


def conversation_messages(
    question: str, history: Iterable[dict[str, str]]
) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(content=CONVERSATION_SYSTEM_PROMPT)]
    for turn in history:
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        if turn.get("role") == "assistant":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))
    messages.append(HumanMessage(content=question))
    return messages


def message_text(response: Any) -> str:
    """Extract plain text from a chat model response."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            block["text"].strip()
            for block in content
            if isinstance(block, dict)
            and isinstance(block.get("text"), str)
            and block["text"].strip()
        )
    return ""


FALLBACK_GREETING = (
    "Hi! I'm the Plum 360 manual assistant. Ask me about an alarm, a procedure, "
    "cleaning, or a device feature, and I'll look it up in the System Operating "
    "Manual with page references."
)
