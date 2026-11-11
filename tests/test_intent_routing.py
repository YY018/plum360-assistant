"""Tests for routing between conversational replies and manual retrieval."""

import unittest

import chromadb
from langchain_chroma import Chroma
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.messages import AIMessage

from plum360_assistant.agent import build_agent_graph
from plum360_assistant.agent.router import (
    CONVERSATION,
    MANUAL,
    classify_heuristically,
    parse_route,
)


class _ScriptedModel:
    """Returns queued replies and records what it was asked."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list = []

    def invoke(self, payload):
        self.calls.append(payload)
        return AIMessage(content=self.replies.pop(0))


def _empty_store(name: str) -> Chroma:
    return Chroma(
        collection_name=name,
        embedding_function=DeterministicFakeEmbedding(size=16),
        client=chromadb.EphemeralClient(),
    )


class HeuristicRoutingTests(unittest.TestCase):
    def test_small_talk_is_conversation(self) -> None:
        for text in ["hi", "Hello there!", "how u doing", "how are you?", "thanks so much",
                     "what can you do?", "who are you", "ok", "bye"]:
            self.assertEqual(classify_heuristically(text), CONVERSATION, text)

    def test_follow_ups_are_conversation(self) -> None:
        for text in ["can you explain that more simply", "make it shorter", "rephrase please"]:
            self.assertEqual(classify_heuristically(text), CONVERSATION, text)

    def test_device_questions_are_manual(self) -> None:
        for text in ["What does alarm E301 indicate?", "how do I clean the infuser",
                     "hi, what does E302 mean?", "how do I prime the cassette",
                     "battery life of the pump"]:
            self.assertEqual(classify_heuristically(text), MANUAL, text)

    def test_ambiguous_messages_defer_to_the_llm(self) -> None:
        self.assertIsNone(classify_heuristically("what's the capital of France"))

    def test_router_reply_parsing_defaults_to_manual(self) -> None:
        self.assertEqual(parse_route("CHAT"), CONVERSATION)
        self.assertEqual(parse_route("MANUAL"), MANUAL)
        self.assertEqual(parse_route("unsure"), MANUAL)


class GraphRoutingTests(unittest.TestCase):
    def test_greeting_gets_llm_reply_without_retrieval(self) -> None:
        llm = _ScriptedModel("Doing well, thanks! Ask me about the manual.")
        graph = build_agent_graph(_empty_store("route_greeting"), llm=llm)

        result = graph.invoke({"question": "how u doing", "chat_history": []})

        self.assertEqual(result["route"], CONVERSATION)
        self.assertEqual(result["generated_answer"], "Doing well, thanks! Ask me about the manual.")
        self.assertEqual(result["source_references"], [])
        self.assertEqual(result.get("retrieval_results", []), [])
        self.assertEqual(len(llm.calls), 1)  # no router call for obvious small talk

    def test_follow_up_receives_role_tagged_history(self) -> None:
        llm = _ScriptedModel("Simpler: turn it off and replace the pump.")
        graph = build_agent_graph(_empty_store("route_follow_up"), llm=llm)
        history = [
            {"role": "user", "content": "What is E301?"},
            {"role": "assistant", "content": "E301 is an audio alarm failure."},
        ]

        graph.invoke({"question": "explain that more simply", "chat_history": history})

        messages = llm.calls[0]
        self.assertEqual([type(m).__name__ for m in messages],
                         ["SystemMessage", "HumanMessage", "AIMessage", "HumanMessage"])

    def test_llm_router_decides_ambiguous_messages(self) -> None:
        llm = _ScriptedModel("CHAT", "I'm focused on the Plum 360 manual.")
        graph = build_agent_graph(_empty_store("route_llm"), llm=llm)

        result = graph.invoke({"question": "what's the capital of France"})

        self.assertEqual(result["route"], CONVERSATION)
        self.assertIn("Plum 360", result["generated_answer"])

    def test_greeting_without_llm_uses_fallback_text(self) -> None:
        graph = build_agent_graph(_empty_store("route_no_llm"))
        result = graph.invoke({"question": "hello"})
        self.assertIn("Plum 360 manual assistant", result["generated_answer"])


if __name__ == "__main__":
    unittest.main()
