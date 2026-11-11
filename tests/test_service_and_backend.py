"""Tests for the shared answer service and the stateless FastAPI backend."""

import unittest
from unittest import mock

from plum360_assistant import service
from plum360_assistant.service import (
    AssistantAnswer,
    AssistantUnavailableError,
    answer_question,
)


class _FakeGraph:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self.error = error

    def invoke(self, state: dict) -> dict:
        self.calls.append(state)
        if self.error:
            raise self.error
        return {"generated_answer": "Answer.", "source_references": ["manual.pdf (pages 12)"]}


class AnswerServiceTests(unittest.TestCase):
    def test_uses_only_the_callers_history(self) -> None:
        graph = _FakeGraph()
        with mock.patch.object(service, "get_agent", return_value=graph):
            first = answer_question("Q1", [{"role": "user", "content": "alice"}])
            answer_question("Q2", [{"role": "user", "content": "bob"}])

        self.assertEqual(first, AssistantAnswer("Answer.", ["manual.pdf (pages 12)"]))
        self.assertEqual(graph.calls[0]["conversation_history"], ["alice"])
        self.assertEqual(graph.calls[1]["conversation_history"], ["bob"])

    def test_model_failure_is_reported_distinctly(self) -> None:
        graph = _FakeGraph(error=RuntimeError("quota"))
        with mock.patch.object(service, "get_agent", return_value=graph):
            with self.assertRaises(AssistantUnavailableError) as ctx:
                answer_question("Q", None)
        self.assertEqual(ctx.exception.kind, "model")

    def test_missing_chat_api_keys_is_a_configuration_error(self) -> None:
        # Local embeddings need no key, but answers need Groq or Gemini.
        service.get_agent.cache_clear()
        with mock.patch.dict(
            "os.environ",
            {"GEMINI_API_KEY": "", "GOOGLE_API_KEY": "", "GROQ_API_KEY": "", "LLM_PROVIDER": ""},
        ), mock.patch("plum360_assistant.config.load_dotenv"):
            with self.assertRaises(AssistantUnavailableError) as ctx:
                service.get_agent()
        self.assertEqual(ctx.exception.kind, "configuration")
        service.get_agent.cache_clear()


class BackendTests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        from backend import main

        self.main = main
        self.client = TestClient(main.app)

    def test_chat_passes_request_history_and_returns_citations(self) -> None:
        with mock.patch.object(
            self.main, "answer_question", return_value=AssistantAnswer("A", ["src"])
        ) as answer:
            response = self.client.post(
                "/chat",
                json={"question": "What is E301?", "history": [{"role": "user", "content": "hi"}]},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["citations"], ["src"])
        answer.assert_called_once_with("What is E301?", [{"role": "user", "content": "hi"}])

    def test_errors_map_to_http_status(self) -> None:
        for kind, status in (("configuration", 503), ("index", 503), ("model", 502)):
            with mock.patch.object(
                self.main,
                "answer_question",
                side_effect=AssistantUnavailableError(kind, f"{kind} problem"),
            ):
                response = self.client.post("/chat", json={"question": "What is E301?"})
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.json()["detail"], f"{kind} problem")


class StreamingBackendTests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        from backend import main

        self.main = main
        self.client = TestClient(main.app)

    def _events(self, response) -> list[dict]:
        import json

        return [json.loads(line) for line in response.text.splitlines() if line.strip()]

    def test_stream_relays_service_events_as_ndjson(self) -> None:
        events = [
            {"type": "status", "stage": "thinking"},
            {"type": "token", "text": "Hel"},
            {"type": "token", "text": "lo"},
            {"type": "done", "answer": "Hello", "citations": [], "route": "conversation"},
        ]
        with mock.patch.object(self.main, "stream_answer", return_value=iter(events)) as stream:
            response = self.client.post(
                "/chat/stream", json={"question": "hi", "history": [{"role": "user", "content": "x"}]}
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/x-ndjson"))
        self.assertEqual(self._events(response), events)
        stream.assert_called_once_with("hi", [{"role": "user", "content": "x"}])

    def test_stream_refuses_unsafe_requests_without_running_the_agent(self) -> None:
        with mock.patch.object(self.main, "stream_answer") as stream:
            response = self.client.post("/chat/stream", json={"question": "change pump settings"})
        events = self._events(response)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "done")
        self.assertEqual(events[0]["route"], "safety")
        stream.assert_not_called()


class StreamAnswerTests(unittest.TestCase):
    def test_stream_reports_model_errors_as_events(self) -> None:
        class _FailingGraph:
            def stream(self, *args, **kwargs):
                raise RuntimeError("503 overloaded")

        with mock.patch.object(service, "get_agent", return_value=_FailingGraph()):
            events = list(service.stream_answer("What is E301?"))
        self.assertEqual(events[0], {"type": "status", "stage": "thinking"})
        self.assertEqual(events[-1]["type"], "error")
        self.assertEqual(events[-1]["kind"], "model")
        self.assertIn("503 overloaded", events[-1]["message"])

    def test_stream_emits_tokens_only_from_answer_nodes(self) -> None:
        from langchain_core.messages import AIMessageChunk

        class _Graph:
            def stream(self, *args, **kwargs):
                yield "updates", {"route_intent": {"route": "manual"}}
                yield "messages", (AIMessageChunk(content="CHAT"), {"langgraph_node": "route_intent"})
                yield "updates", {"retrieve_manual_information": {}}
                yield "messages", (
                    AIMessageChunk(content="Answer"),
                    {"langgraph_node": "generate_grounded_answer"},
                )
                yield "values", {
                    "generated_answer": "Answer",
                    "source_references": ["manual.pdf (pages 1)"],
                    "route": "manual",
                }

        with mock.patch.object(service, "get_agent", return_value=_Graph()):
            events = list(service.stream_answer("What is E301?"))

        self.assertEqual(
            [event.get("stage") or event.get("text") or event["type"] for event in events],
            ["thinking", "searching", "reading", "Answer", "done"],
        )
        self.assertEqual(events[-1]["citations"], ["manual.pdf (pages 1)"])


if __name__ == "__main__":
    unittest.main()
