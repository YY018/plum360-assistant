"""Tests for manual page rendering, page labels, and the manual endpoints."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pymupdf

from plum360_assistant import manual_pages
from plum360_assistant.service import source_pages


def _clear_caches() -> None:
    manual_pages._document.cache_clear()
    manual_pages.render_page_png.cache_clear()
    manual_pages.page_labels.cache_clear()


class ManualPagesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / "manual.pdf"
        document = pymupdf.open()
        for header, label in [("Cover", None), ("Plum 360 Infuser", "1-1"), ("Plum 360 Infuser", "1-2")]:
            page = document.new_page(width=396, height=612)
            page.insert_text((40, 40), header)
            if label:
                page.insert_text((40, 60), label)
            page.insert_text((40, 120), "Body text for the page.")
        document.save(path)
        document.close()

        self.env = mock.patch.dict(os.environ, {"MANUAL_PDF_PATH": str(path)})
        self.env.start()
        _clear_caches()

    def tearDown(self) -> None:
        _clear_caches()
        self.env.stop()
        self.tmp.cleanup()

    def test_page_labels_map_to_pdf_pages(self) -> None:
        self.assertEqual(manual_pages.page_labels(), {"1-1": 2, "1-2": 3})
        self.assertEqual(manual_pages.page_label(3), "1-2")

    def test_render_returns_png_and_rejects_out_of_range_pages(self) -> None:
        self.assertTrue(manual_pages.render_page_png(1).startswith(b"\x89PNG"))
        with self.assertRaises(manual_pages.ManualUnavailableError):
            manual_pages.render_page_png(4)
        with self.assertRaises(manual_pages.ManualUnavailableError):
            manual_pages.render_page_png(0)

    def test_endpoints_serve_info_and_pages(self) -> None:
        from fastapi.testclient import TestClient

        from backend.main import app

        client = TestClient(app)
        info = client.get("/manual").json()
        self.assertEqual(info, {"available": True, "page_count": 3, "labels": {"1-1": 2, "1-2": 3}})

        page = client.get("/manual/pages/2.png")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers["content-type"], "image/png")
        self.assertEqual(client.get("/manual/pages/99.png").status_code, 404)

    def test_missing_pdf_is_reported_as_unavailable(self) -> None:
        from fastapi.testclient import TestClient

        from backend.main import app

        with mock.patch.dict(os.environ, {"MANUAL_PDF_PATH": str(Path(self.tmp.name) / "missing.pdf")}):
            _clear_caches()
            client = TestClient(app)
            self.assertFalse(client.get("/manual").json()["available"])
            self.assertEqual(client.get("/manual/pages/1.png").status_code, 404)


class SourcePagesTests(unittest.TestCase):
    def test_citations_are_paired_with_page_numbers(self) -> None:
        state = {
            "source_references": ["manual.pdf (pages 12, 13)", "manual.pdf (pages 40)"],
            "retrieval_results": [{"page_numbers": [12, 13]}, {"page_numbers": [40]}, {"page_numbers": [99]}],
        }
        self.assertEqual(
            source_pages(state),
            [
                {"citation": "manual.pdf (pages 12, 13)", "pages": [12, 13]},
                {"citation": "manual.pdf (pages 40)", "pages": [40]},
            ],
        )


if __name__ == "__main__":
    unittest.main()
