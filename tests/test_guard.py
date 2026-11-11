"""Tests for the demo request guard (rate limits, budget, access code)."""

import unittest
from unittest import mock

from backend.guard import GuardError, RequestGuard
from plum360_assistant.service import AssistantAnswer


class RequestGuardTests(unittest.TestCase):
    def test_per_client_hourly_limit_resets_after_an_hour(self) -> None:
        guard = RequestGuard(per_client_per_hour=2, daily_budget=0)
        guard.reserve("a", now=1000)
        guard.reserve("a", now=1001)
        with self.assertRaises(GuardError) as ctx:
            guard.reserve("a", now=1002)
        self.assertEqual(ctx.exception.status, 429)
        self.assertGreater(ctx.exception.retry_after, 0)
        guard.reserve("b", now=1002)  # other clients are unaffected
        guard.reserve("a", now=1000 + 3601)  # window has rolled

    def test_daily_budget_is_shared_across_clients(self) -> None:
        guard = RequestGuard(per_client_per_hour=0, daily_budget=2)
        guard.reserve("a", now=0)
        guard.reserve("b", now=1)
        with self.assertRaises(GuardError) as ctx:
            guard.reserve("c", now=2)
        self.assertIn("daily", ctx.exception.message)
        guard.reserve("c", now=86401)
        self.assertEqual(guard.status()["daily_budget"], 2)

    def test_question_length_and_access_code(self) -> None:
        guard = RequestGuard(max_question_chars=10, access_code="secret")
        with self.assertRaises(GuardError) as ctx:
            guard.check_question("x" * 11)
        self.assertEqual(ctx.exception.status, 413)
        with self.assertRaises(GuardError) as ctx:
            guard.check_access(None)
        self.assertEqual(ctx.exception.status, 401)
        with self.assertRaises(GuardError):
            guard.check_access("wrong")
        guard.check_access("secret")
        RequestGuard(access_code="").check_access(None)  # no code configured

    def test_zero_disables_a_check(self) -> None:
        guard = RequestGuard(per_client_per_hour=0, daily_budget=0, max_question_chars=0)
        for i in range(50):
            guard.reserve("a", now=i)
        guard.check_question("x" * 10000)


class GuardedEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        from fastapi.testclient import TestClient

        from backend import main

        self.main = main
        self.client = TestClient(main.app)
        self.original = main.guard

    def tearDown(self) -> None:
        self.main.guard = self.original

    def test_limit_messages_reach_the_client(self) -> None:
        self.main.guard = RequestGuard(per_client_per_hour=1, daily_budget=0)
        with mock.patch.object(self.main, "answer_question", return_value=AssistantAnswer("A", [])):
            first = self.client.post("/chat", json={"question": "What is E301?"})
            second = self.client.post("/chat", json={"question": "What is E301?"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertIn("limit", second.json()["detail"])
        self.assertIn("Retry-After", second.headers)

    def test_access_code_is_required_on_the_stream_endpoint(self) -> None:
        self.main.guard = RequestGuard(access_code="demo123")
        denied = self.client.post("/chat/stream", json={"question": "What is E301?"})
        self.assertEqual(denied.status_code, 401)
        with mock.patch.object(self.main, "stream_answer", return_value=iter([{"type": "done", "answer": "A", "citations": [], "route": "manual"}])):
            allowed = self.client.post(
                "/chat/stream", json={"question": "What is E301?"}, headers={"X-Access-Code": "demo123"}
            )
        self.assertEqual(allowed.status_code, 200)

    def test_refused_questions_do_not_use_the_budget(self) -> None:
        self.main.guard = RequestGuard(per_client_per_hour=0, daily_budget=1)
        self.client.post("/chat", json={"question": "change pump settings now"})
        self.assertEqual(self.main.guard.status()["used_today"], 0)
        self.assertEqual(self.client.get("/limits").json()["daily_budget"], 1)


if __name__ == "__main__":
    unittest.main()
