"""Tests for structured page extraction and validation."""

import json
import tempfile
import unittest
from pathlib import Path

import pymupdf

from scripts.extract_documents import (
    extract_pdf_document,
    normalize_page_text,
    write_extraction_outputs,
)


class ExtractionPipelineTests(unittest.TestCase):
    def test_normalize_page_text_keeps_content_and_collapses_blank_lines(self) -> None:
        source = "Heading  \r\n\r\n\r\nWARNING:  Keep this spacing.   \r\n"

        self.assertEqual(
            normalize_page_text(source),
            "Heading\n\nWARNING:  Keep this spacing.",
        )

    def test_extracts_pages_and_writes_validated_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            pdf_path = temp_path / "source.pdf"
            document_pdf = pymupdf.open()
            document_pdf.new_page().insert_text(
                (72, 72),
                "Plum 360 Infuser\nWARNING: Preserve this manual text.",
            )
            document_pdf.new_page().insert_text(
                (72, 72),
                "Alarm reference information stays with the page text in this extraction test.",
            )
            document_pdf.save(pdf_path)
            document_pdf.close()

            document, validation = extract_pdf_document(
                pdf_path, "plum360_test"
            )
            output_paths = write_extraction_outputs(
                document, validation, temp_path / "processed"
            )

            saved_document = json.loads(
                output_paths["json"].read_text(encoding="utf-8")
            )
            saved_validation = json.loads(
                output_paths["validation"].read_text(encoding="utf-8")
            )
            text_output = output_paths["text"].read_text(encoding="utf-8")

        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))
        self.assertEqual(saved_document["source"], "source.pdf")
        self.assertEqual(
            [page["page_number"] for page in saved_document["pages"]], [1, 2]
        )
        self.assertTrue(all(page["section"] is None for page in saved_document["pages"]))
        self.assertIn("WARNING: Preserve this manual text.", text_output)
        self.assertIn("--- Page 2 ---", text_output)
        self.assertEqual(saved_validation["summary"]["pages_with_text"], 2)


if __name__ == "__main__":
    unittest.main()
