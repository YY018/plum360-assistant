"""Streamlit application smoke test."""

import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_homepage_renders_plum_scope_and_safety_message(self) -> None:
        app_path = Path(__file__).resolve().parents[1] / "app.py"
        app = AppTest.from_file(str(app_path)).run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.title[0].value, "Plum 360 Assistant")
        self.assertTrue(
            any(
                "not yet connected to this interface" in element.value
                for element in app.info
            )
        )
        self.assertTrue(
            any("not a medical device" in element.value for element in app.warning)
        )


if __name__ == "__main__":
    unittest.main()
