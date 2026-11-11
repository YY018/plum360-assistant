"""Extract page-aware document text and validate generated extraction files."""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any

from scripts.inspect_documents import extract_pdf_text


LOGGER = logging.getLogger(__name__)
DOCUMENT_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")


def normalize_page_text(text: str) -> str:
    """Normalize line endings and excess blank lines without removing content."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    cleaned: list[str] = []
    previous_line_was_blank = True

    for line in lines:
        if line.strip():
            cleaned.append(line)
            previous_line_was_blank = False
        elif cleaned and not previous_line_was_blank:
            cleaned.append("")
            previous_line_was_blank = True

    while cleaned and not cleaned[-1]:
        cleaned.pop()

    return "\n".join(cleaned)


def build_extraction_document(
    inspection_report: dict[str, Any],
    document_id: str,
) -> dict[str, Any]:
    """Create structured page records from a completed PDF inspection."""
    if not DOCUMENT_ID_PATTERN.fullmatch(document_id):
        raise ValueError(
            "document_id must contain only letters, digits, underscores, and hyphens."
        )
    if inspection_report.get("status") == "FAILED":
        errors = inspection_report.get("errors", [])
        raise ValueError(
            "PDF inspection failed: " + "; ".join(errors or ["unknown error"])
        )

    pages = []
    for inspected_page in inspection_report.get("pages", []):
        raw_text = inspected_page.get("text", "")
        if not isinstance(raw_text, str):
            raise ValueError(
                f"Page {inspected_page.get('page_number')} has non-text content."
            )

        text = normalize_page_text(raw_text)
        pages.append(
            {
                "page_number": inspected_page["page_number"],
                "section": None,
                "text": text,
                "text_length": len(text),
                "word_count": len(text.split()),
                "extraction_status": inspected_page.get(
                    "extraction_status", "UNKNOWN"
                ),
                "extraction_error": inspected_page.get("extraction_error"),
            }
        )

    return {
        "document_id": document_id,
        "source": inspection_report.get("file", {}).get("filename"),
        "page_count": inspection_report.get("page_count", len(pages)),
        "inspection_status": inspection_report.get("status"),
        "metadata": inspection_report.get("metadata", {}),
        "extraction_warnings": inspection_report.get("extraction_warnings", []),
        "extraction_errors": inspection_report.get("errors", []),
        "pages": pages,
    }


def validate_extraction_document(
    document: dict[str, Any],
) -> dict[str, Any]:
    """Check page coverage, numbering, and stored text metrics."""
    pages = document.get("pages", [])
    page_count = document.get("page_count", 0)
    page_numbers = [page.get("page_number") for page in pages]

    checks = {
        "page_count_matches": len(pages) == page_count,
        "page_numbers_unique": len(page_numbers) == len(set(page_numbers)),
        "page_numbers_sequential": page_numbers == list(range(1, page_count + 1)),
        "text_lengths_match": all(
            page.get("text_length") == len(page.get("text", "")) for page in pages
        ),
        "word_counts_match": all(
            page.get("word_count") == len(page.get("text", "").split())
            for page in pages
        ),
    }

    errors = [
        f"Validation check failed: {check_name}."
        for check_name, passed in checks.items()
        if not passed
    ]
    warnings: list[str] = []

    low_text_pages = [
        page["page_number"]
        for page in pages
        if page.get("extraction_status") == "LOW_TEXT"
    ]
    empty_pages = [
        page["page_number"]
        for page in pages
        if page.get("extraction_status") == "EMPTY"
    ]
    image_only_pages = [
        page["page_number"]
        for page in pages
        if page.get("extraction_status") == "IMAGE_ONLY"
    ]
    failed_pages = [
        page["page_number"]
        for page in pages
        if page.get("extraction_status") == "FAILED"
    ]

    if low_text_pages:
        warnings.append(f"Low-text pages need review: {low_text_pages}.")
    if empty_pages:
        warnings.append(f"Pages with no extracted text: {empty_pages}.")
    if image_only_pages:
        warnings.append(f"Image-only pages may need visual/OCR review: {image_only_pages}.")
    if failed_pages:
        errors.append(f"Page extraction failed on pages: {failed_pages}.")

    status = "FAIL" if errors else "PASS_WITH_WARNINGS" if warnings else "PASS"
    return {
        "document_id": document.get("document_id"),
        "source": document.get("source"),
        "status": status,
        "page_count": page_count,
        "checks": checks,
        "summary": {
            "pages_with_text": sum(bool(page.get("text", "").strip()) for page in pages),
            "pages_with_low_text": len(low_text_pages),
            "empty_pages": len(empty_pages),
            "image_only_pages": len(image_only_pages),
            "pages_with_errors": len(failed_pages),
            "total_characters": sum(page.get("text_length", 0) for page in pages),
            "total_words": sum(page.get("word_count", 0) for page in pages),
        },
        "warnings": warnings,
        "errors": errors,
        "scope_note": (
            "Structural checks do not replace visual review of the source PDF."
        ),
    }


def extract_pdf_document(
    pdf_path: str | Path,
    document_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Inspect a PDF, normalize its page text, and validate the structured result."""
    inspection_report = extract_pdf_text(pdf_path)
    document = build_extraction_document(inspection_report, document_id)
    validation_report = validate_extraction_document(document)
    return document, validation_report


def _render_text_document(document: dict[str, Any]) -> str:
    """Render extracted pages in a readable text format without dropping content."""
    lines = [
        f"Document ID: {document['document_id']}",
        f"Source: {document['source']}",
        f"Pages: {document['page_count']}",
        "",
    ]

    for page in document["pages"]:
        lines.append(f"--- Page {page['page_number']} ---")
        if page["section"]:
            lines.append(f"Section: {page['section']}")
        if page["text"]:
            lines.append(page["text"])
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_extraction_outputs(
    document: dict[str, Any],
    validation_report: dict[str, Any],
    output_directory: str | Path,
) -> dict[str, Path]:
    """Write structured JSON, readable TXT, and a validation report."""
    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    document_id = document["document_id"]

    paths = {
        "json": output_dir / f"{document_id}.json",
        "text": output_dir / f"{document_id}.txt",
        "validation": output_dir / f"{document_id}_validation_report.json",
    }

    with paths["json"].open("w", encoding="utf-8") as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2)
    paths["text"].write_text(_render_text_document(document), encoding="utf-8")
    with paths["validation"].open("w", encoding="utf-8") as handle:
        json.dump(validation_report, handle, ensure_ascii=False, indent=2)

    return paths


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract PDF text by page and write structured outputs."
    )
    parser.add_argument("pdf_path", type=Path, help="Path to the source PDF.")
    parser.add_argument(
        "--document-id",
        required=True,
        help="Stable identifier for the extracted document.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "processed",
        help="Output directory (default: data/processed).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    document, validation_report = extract_pdf_document(
        args.pdf_path, args.document_id
    )
    for warning in document["extraction_warnings"]:
        LOGGER.warning("%s", warning)
    for error in document["extraction_errors"]:
        LOGGER.error("%s", error)
    for warning in validation_report["warnings"]:
        LOGGER.warning("%s", warning)
    for error in validation_report["errors"]:
        LOGGER.error("%s", error)

    paths = write_extraction_outputs(
        document, validation_report, args.output_dir
    )
    print(
        json.dumps(
            {
                "status": validation_report["status"],
                "outputs": {name: str(path) for name, path in paths.items()},
                "summary": validation_report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if validation_report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
