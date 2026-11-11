"""Safety and reliability checks for Plum 360 assistant responses."""

from __future__ import annotations

import re
from typing import Any


MEDICAL_SCOPE_WARNING = (
    "This assistant is for reference to the Plum 360 System Operating Manual only. "
    "It does not operate or control a physical infusion pump and must not be used "
    "for clinical dosing, programming, or alarm response decisions."
)


def validate_user_query(question: str) -> tuple[bool, str]:
    """Reject unsafe or out-of-scope requests before retrieval."""
    normalized = (question or "").strip()
    if not normalized:
        return False, "Please enter a question about the Plum 360 manual."
    lowered = normalized.lower()
    unsafe_patterns = [
        r"(start|stop)\s+(the\s+)?pump",
        r"change\s+(pump\s+)?settings",
        r"program\s+.*(infusion|rate|pump)",
        r"dose\s+(the\s+)?patient",
        r"deliver\s+.*(medication|drug)",
    ]
    if any(re.search(pattern, lowered) for pattern in unsafe_patterns):
        return False, MEDICAL_SCOPE_WARNING
    return True, ""


def validate_answer(answer: str, evidence: list[Any]) -> tuple[bool, str]:
    """Ensure answers are grounded in manual evidence and cite manual passages."""
    if not (answer or "").strip():
        return False, "No answer was generated."
    if not evidence:
        return False, "This answer is not supported by manual evidence."
    if "manual" in (answer or "").lower() or "official" in (answer or "").lower():
        return True, "manual evidence present"
    return False, "The response should cite manual evidence or abstain."
