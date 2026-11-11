"""Tests for page-level PDF inspection results."""

import tempfile
import unittest
from pathlib import Path

import pymupdf

from scripts.inspect_documents import extract_pdf_text


class ExtractPdfTextTests(unittest.TestCase):
    def test_reports_page_word_counts_statuses_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "inspection-test.pdf"
            document = pymupdf.open()
            document.new_page().insert_text(
                (72, 72),
                "This page contains enough words to exceed the short text threshold.",
            )
            document.new_page().insert_text((72, 72), "Plum page.")
            document.new_page()
            document.save(pdf_path)
            document.close()

            report = extract_pdf_text(pdf_path)

        self.assertEqual(report["status"], "SUCCESS_WITH_WARNINGS")
        self.assertEqual(
            [page["extraction_status"] for page in report["pages"]],
            ["SUCCESS", "LOW_TEXT", "EMPTY"],
        )
        self.assertEqual(report["pages"][0]["word_count"], 11)
        self.assertEqual(report["pages"][1]["word_count"], 2)
        self.assertEqual(report["pages"][2]["word_count"], 0)
        self.assertEqual(
            report["summary"],
            {
                "pages_with_text": 2,
                "pages_with_low_text": 1,
                "empty_pages": 1,
                "image_only_pages": 0,
                "pages_with_errors": 0,
            },
        )


if __name__ == "__main__":
    unittest.main()
