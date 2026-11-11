"""Tests for page-aware, token-sized chunking."""

import unittest

import tiktoken

from scripts.chunk_documents import chunk_document


class ChunkDocumentTests(unittest.TestCase):
    def test_chunks_preserve_pages_and_respect_token_size(self) -> None:
        document = {
            "document_id": "plum360_test",
            "source": "manual.pdf",
            "pages": [
                {
                    "page_number": page_number,
                    "section": "Working with Alarms",
                    "text": (
                        "Alarm E301 describes a condition and its cause. "
                        "The associated response and warning remain in this text. "
                    )
                }
                for page_number in range(1, 31)
            ],
        }
        document["page_count"] = len(document["pages"])
        encoding = tiktoken.get_encoding("cl100k_base")

        chunked = chunk_document(document, chunk_size=40, chunk_overlap=8)
        source_text = "\n".join(page["text"] for page in document["pages"])
        page_ranges = []
        cursor = 0
        for index, page in enumerate(document["pages"]):
            if index:
                cursor += 1
            start = cursor
            cursor += len(page["text"])
            page_ranges.append((page["page_number"], start, cursor))

        self.assertGreater(chunked["chunk_count"], 1)
        self.assertTrue(
            all(
                len(encoding.encode(chunk["text"])) <= 40
                for chunk in chunked["chunks"]
            )
        )
        self.assertTrue(
            all(
                chunk["metadata"]["document_id"] == "plum360_test"
                and chunk["metadata"]["source"] == "manual.pdf"
                and chunk["metadata"]["page_numbers"]
                for chunk in chunked["chunks"]
            )
        )
        for chunk in chunked["chunks"]:
            start = chunk["metadata"]["start_index"]
            end = start + len(chunk["text"])
            self.assertEqual(source_text[start:end], chunk["text"])
            expected_pages = [
                page_number
                for page_number, page_start, page_end in page_ranges
                if start < page_end and end > page_start
            ]
            self.assertEqual(chunk["metadata"]["page_numbers"], expected_pages)
        self.assertTrue(
            any(
                chunk["metadata"]["section"] == "Working with Alarms"
                for chunk in chunked["chunks"]
            )
        )

    def test_chunk_can_map_content_across_a_page_boundary(self) -> None:
        document = {
            "document_id": "plum360_test",
            "source": "manual.pdf",
            "page_count": 2,
            "pages": [
                {
                    "page_number": 1,
                    "section": None,
                    "text": "Alarm E301 has a documented cause",
                },
                {
                    "page_number": 2,
                    "section": None,
                    "text": "and associated warning in the next page.",
                },
            ],
        }

        chunked = chunk_document(document, chunk_size=40, chunk_overlap=5)

        self.assertEqual(chunked["chunk_count"], 1)
        self.assertEqual(chunked["chunks"][0]["metadata"]["page_numbers"], [1, 2])
        self.assertIsNone(chunked["chunks"][0]["metadata"]["page_number"])
        self.assertIn("associated warning", chunked["chunks"][0]["text"])

    def test_skips_chunks_containing_only_repeated_headers_and_page_numbers(self) -> None:
        document = {
            "document_id": "plum360_test",
            "source": "manual.pdf",
            "page_count": 2,
            "pages": [
                {
                    "page_number": 1,
                    "section": None,
                    "text": "System Operating Manual\ni",
                },
                {
                    "page_number": 2,
                    "section": None,
                    "text": "System Operating Manual\nii",
                },
            ],
        }

        chunked = chunk_document(document, chunk_size=40, chunk_overlap=5)

        self.assertEqual(chunked["chunk_count"], 0)
        self.assertEqual(chunked["summary"]["skipped_non_content_chunks"], 1)


if __name__ == "__main__":
    unittest.main()
