"""Memory and safety validation tests for the assistant."""

import unittest

from plum360_assistant.conversation_memory import ConversationMemory
from plum360_assistant.safety import validate_user_query


class MemoryAndSafetyTests(unittest.TestCase):
    def test_memory_keeps_recent_turns_only(self) -> None:
        memory = ConversationMemory(max_turns=2)
        memory.add_user_turn("first")
        memory.add_assistant_turn("first answer")
        memory.add_user_turn("second")
        memory.add_assistant_turn("second answer")
        memory.add_user_turn("third")

        self.assertEqual(len(memory.get_history()), 2)
        self.assertEqual(memory.get_history()[-1]["content"], "third")

    def test_invalid_requests_are_blocked(self) -> None:
        ok, message = validate_user_query("Start the pump and deliver medication.")
        self.assertFalse(ok)
        self.assertIn("manual", message.lower())


if __name__ == "__main__":
    unittest.main()
