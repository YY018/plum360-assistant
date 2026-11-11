"""LangGraph agent tests for manual-grounded retrieval and routing."""

import unittest

import chromadb
from langchain_chroma import Chroma
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.messages import AIMessage

from plum360_assistant.agent import build_agent_graph
from plum360_assistant.vector_store import index_chunks


def _ephemeral_store(collection_name: str) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=DeterministicFakeEmbedding(size=16),
        client=chromadb.EphemeralClient(),
    )


def _manual_document() -> dict:
    return {
        "document_id": "plum360_test",
        "source": "manual.pdf",
        "page_count": 2,
        "chunks": [
            {
                "chunk_id": "plum360_test-chunk-0000",
                "text": (
                    "Audio alarm failure.\nHigh\nE301\n"
                    "Audio alarm is OFF but sensed ON, or ON but sensed OFF.\n"
                    "Power off the infuser.\nReplace pump.\n"
                    "Backlight failure.\nHigh\nE302\n"
                    "Backlight voltage out of range.\nPower off the infuser."
                ),
                "metadata": {
                    "document_id": "plum360_test",
                    "source": "manual.pdf",
                    "page_number": 12,
                    "page_numbers": [12],
                    "section": "Alarms",
                    "chunk_index": 0,
                    "start_index": 0,
                    "token_count": 10,
                    "character_count": 47,
                },
            },
            {
                "chunk_id": "plum360_test-chunk-0001",
                "text": "The connectivity engine communicates with other systems.",
                "metadata": {
                    "document_id": "plum360_test",
                    "source": "manual.pdf",
                    "page_number": 20,
                    "page_numbers": [20],
                    "section": "Connectivity",
                    "chunk_index": 1,
                    "start_index": 50,
                    "token_count": 11,
                    "character_count": 56,
                },
            },
        ],
    }


class _SummaryModel:
    def __init__(self) -> None:
        self.prompt = ""

    def invoke(self, prompt: str) -> AIMessage:
        self.prompt = prompt
        return AIMessage(
            content=(
                "E301 is a high-priority audio alarm failure: the alarm is sensed "
                "ON when switched off, or OFF when switched on. The manual states "
                "to power off and replace the pump."
            )
        )


class LangGraphAgentTests(unittest.TestCase):
    def test_alarm_question_routes_to_alarm_search_and_returns_citation(self) -> None:
        store = _ephemeral_store("agent_alarm")
        index_chunks(_manual_document(), store, collection_name="agent_alarm")
        graph = build_agent_graph(store)

        result = graph.invoke({"question": "What does alarm E301 indicate?"})

        self.assertEqual(result["tool_name"], "search_by_alarm_code")
        self.assertTrue(result["answer_supported"])
        self.assertTrue(result["source_references"])
        self.assertIn("manual.pdf", result["source_references"][0])
        self.assertIn("E301", result["generated_answer"])

    def test_llm_summarizes_retrieved_alarm_evidence_and_keeps_citation(self) -> None:
        store = _ephemeral_store("agent_alarm_summary")
        index_chunks(_manual_document(), store, collection_name="agent_alarm_summary")
        llm = _SummaryModel()
        graph = build_agent_graph(store, llm=llm)

        result = graph.invoke({"question": "What does alarm E301 indicate?"})

        self.assertIn("E301", result["generated_answer"])
        self.assertIn(
            "Manual-listed action: Power off the infuser. Replace pump.",
            result["generated_answer"],
        )
        self.assertIn("Power off the infuser.\nReplace pump.", llm.prompt)
        self.assertNotIn("E302", llm.prompt)
        self.assertTrue(result["answer_supported"])
        self.assertIn("manual.pdf", result["source_references"][0])

    def test_irrelevant_question_abstains_when_manual_evidence_is_missing(self) -> None:
        store = _ephemeral_store("agent_irrelevant")
        index_chunks(_manual_document(), store, collection_name="agent_irrelevant")
        graph = build_agent_graph(store)

        result = graph.invoke({"question": "How do I tune a guitar?"})

        self.assertEqual(result["relevance_assessment"], "insufficient")
        self.assertIn("does not provide enough supported information", result["generated_answer"])


if __name__ == "__main__":
    unittest.main()
