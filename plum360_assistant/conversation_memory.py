"""Conversation memory utilities for the Plum 360 assistant."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterable


@dataclass
class ConversationMemory:
    """Keeps a bounded chat transcript for the current session."""

    max_turns: int = 8
    _history: Deque[dict[str, str]] = field(default_factory=deque)

    def add_turn(self, role: str, content: str) -> None:
        if not content:
            return
        self._history.append({"role": role, "content": content.strip()})
        while len(self._history) > self.max_turns:
            self._history.popleft()

    def add_user_turn(self, content: str) -> None:
        self.add_turn("user", content)

    def add_assistant_turn(self, content: str) -> None:
        self.add_turn("assistant", content)

    def get_history(self) -> list[dict[str, str]]:
        return list(self._history)

    def get_recent_messages(self) -> list[str]:
        return [turn["content"] for turn in self._history if turn["content"]]

    def load_from_messages(self, messages: Iterable[dict[str, str]]) -> None:
        self._history.clear()
        for message in list(messages)[-self.max_turns :]:
            role = str(message.get("role", "user"))
            content = str(message.get("content", "")).strip()
            if content:
                self._history.append({"role": role, "content": content})

    def clear(self) -> None:
        self._history.clear()
