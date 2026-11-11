"""Create token-sized, page-aware chunks from extracted document JSON."""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter


LOGGER = logging.getLogger(__name__)
PAGE_MARKER_PATTERN = re.compile(
    r"(?:page\s+)?(?:\d+|[ivxlcdm]+|\d+[-\u2013]\d+)\Z",
    re.IGNORECASE,
)
TOKEN_ENCODING = "cl100k_base"
DEFAULT_CHUNK_SIZE = 900
DEFAULT_CHUNK_OVERLAP = 120


def _repeated_edge_lines(pages: list[dict[str, Any]]) -> set[str]:
    """Find exact lines repeated at page edges, for header-only filtering."""
    page_occurrences: dict[str, set[int]] = defaultdict(set)

    for page in pages:
        page_number = page.get("page_number")
        if not isinstance(page_number, int):
            raise ValueError("Every source page must have an integer page_number.")
        lines = [line.strip() for line in page.get("text", "").splitlines()]
        lines = [line for line in lines if line]
        for line in set(lines[:3] + lines[-3:]):
            if isinstance(page_number, int):
                page_occurrences[line.casefold()].add(page_number)

    return {
        line
        for line, occurrences in page_occurrences.items()
        if len(occurrences) >= 2
    }


def _has_content(
    text: str,
    repeated_edge_lines: set[str],
) -> bool:
    """Return whether a chunk contains more than repeated headers/page markers."""
    for line in text.splitlines():
        candidate = " ".join(line.split())
        if not candidate:
            continue
        if candidate.casefold() in repeated_edge_lines:
            continue
        if PAGE_MARKER_PATTERN.fullmatch(candidate):
            continue
        if re.search(r"[^\W_]", candidate, flags=re.UNICODE):
            return True
    return False


def _prepare_page_text(
    pages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Join pages while retaining character ranges for citation metadata."""
    parts: list[str] = []
    page_ranges: list[dict[str, Any]] = []
    cursor = 0

    for page_index, page in enumerate(pages):
        if page_index:
            parts.append("\n")
            cursor += 1

        text = page.get("text", "")
        if not isinstance(text, str):
            raise ValueError(
                f"Page {page.get('page_number')} has non-text content."
            )
        page_number = page.get("page_number")
        if not isinstance(page_number, int) or page_number < 1:
            raise ValueError("Every source page must have a positive page_number.")
        start = cursor
        end = start + len(text)
        parts.append(text)
        page_ranges.append(
            {
                "page_number": page_number,
                "section": page.get("section"),
                "start": start,
                "end": end,
            }
        )
        cursor = end

    return "".join(parts), page_ranges


def chunk_document(
    document: dict[str, Any],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> dict[str, Any]:
    """Split document text by token size and retain all covered source pages."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be between zero and chunk_size - 1.")

    pages = document.get("pages", [])
    page_text, page_ranges = _prepare_page_text(pages)
    if not page_text.strip():
        raise ValueError("The extracted document has no text to chunk.")

    encoding = tiktoken.get_encoding(TOKEN_ENCODING)
    effective_chunk_size = chunk_size
    effective_chunk_overlap = chunk_overlap

    while True:
        effective_chunk_overlap = min(
            chunk_overlap, effective_chunk_size - 1
        )
        splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=TOKEN_ENCODING,
            chunk_size=effective_chunk_size,
            chunk_overlap=effective_chunk_overlap,
            separators=["\n\n", " ", ""],
            strip_whitespace=True,
        )
        split_texts = splitter.split_text(page_text)
        if all(
            len(encoding.encode(text)) <= chunk_size for text in split_texts
        ):
            break
        if effective_chunk_size <= 1:
            raise RuntimeError(
                "The splitter could not honor the configured maximum chunk size."
            )
        effective_chunk_size -= 1

    repeated_edge_lines = _repeated_edge_lines(pages)
    chunks: list[dict[str, Any]] = []
    skipped_non_content_chunks = 0
    search_from = 0

    for text in split_texts:
        if not _has_content(text, repeated_edge_lines):
            skipped_non_content_chunks += 1
            continue

        start_index = page_text.find(text, search_from)
        if start_index < 0:
            raise ValueError(
                "A chunk could not be mapped back to its source text."
            )
        search_from = start_index + 1
        end_index = start_index + len(text)
        covered_pages = [
            page
            for page in page_ranges
            if start_index < page["end"] and end_index > page["start"]
        ]
        page_numbers = [page["page_number"] for page in covered_pages]
        if not page_numbers:
            raise ValueError(
                f"Chunk at character {start_index} does not map to a source page."
            )

        sections = {page["section"] for page in covered_pages}
        section = (
            next(iter(sections))
            if len(sections) == 1 and None not in sections
            else None
        )
        token_count = len(encoding.encode(text))
        chunk_index = len(chunks)
        chunks.append(
            {
                "chunk_id": f"{document['document_id']}-chunk-{chunk_index:04d}",
                "text": text,
                "metadata": {
                    "document_id": document["document_id"],
                    "source": document["source"],
                    "page_number": page_numbers[0] if len(page_numbers) == 1 else None,
                    "page_numbers": page_numbers,
                    "section": section,
                    "start_index": start_index,
                    "chunk_index": chunk_index,
                    "token_count": token_count,
                    "character_count": len(text),
                },
            }
        )

    token_counts = [chunk["metadata"]["token_count"] for chunk in chunks]
    return {
        "document_id": document["document_id"],
        "source": document["source"],
        "page_count": document.get("page_count", len(pages)),
        "chunking_config": {
            "splitter": "RecursiveCharacterTextSplitter",
            "token_encoding": TOKEN_ENCODING,
            "chunk_size_tokens": chunk_size,
            "chunk_overlap_tokens": chunk_overlap,
            "effective_splitter_chunk_size_tokens": effective_chunk_size,
            "effective_splitter_overlap_tokens": effective_chunk_overlap,
            "separators": ["\\n\\n", " ", ""],
            "split_across_pages": True,
        },
        "chunk_count": len(chunks),
        "summary": {
            "minimum_chunk_tokens": min(token_counts, default=0),
            "maximum_chunk_tokens": max(token_counts, default=0),
            "average_chunk_tokens": (
                round(sum(token_counts) / len(token_counts), 2)
                if token_counts
                else 0
            ),
            "skipped_non_content_chunks": skipped_non_content_chunks,
        },
        "chunks": chunks,
    }


def write_chunks(chunked_document: dict[str, Any], output_path: str | Path) -> Path:
    """Persist chunk text and its source metadata as JSON."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(chunked_document, handle, ensure_ascii=False, indent=2)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create page-aware, token-sized chunks from extracted JSON."
    )
    parser.add_argument(
        "input_json",
        type=Path,
        help="Structured extraction JSON produced by extract_documents.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: <input>_chunks.json).",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Maximum chunk size in tokens (default: {DEFAULT_CHUNK_SIZE}).",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=DEFAULT_CHUNK_OVERLAP,
        help=f"Chunk overlap in tokens (default: {DEFAULT_CHUNK_OVERLAP}).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    document = json.loads(args.input_json.read_text(encoding="utf-8"))
    chunked_document = chunk_document(
        document,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    output_path = args.output or args.input_json.with_name(
        f"{args.input_json.stem}_chunks.json"
    )
    saved_path = write_chunks(chunked_document, output_path)
    LOGGER.info(
        "Created %s chunks from %s pages.",
        chunked_document["chunk_count"],
        chunked_document["page_count"],
    )
    print(
        json.dumps(
            {
                "output": str(saved_path),
                "document_id": chunked_document["document_id"],
                "chunk_count": chunked_document["chunk_count"],
                "summary": chunked_document["summary"],
                "chunking_config": chunked_document["chunking_config"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
