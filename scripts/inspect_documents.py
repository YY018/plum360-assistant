"""Focused PDF inspection utilities for extracting text and basic document data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pymupdf as fitz


def _safe_metadata_value(value: Any) -> Any:
    """Return a cleaned metadata value or None when the field is missing."""
    if value in (None, "", "None"):
        return None
    return value


def _read_metadata(document: fitz.Document, file_path: Path) -> dict[str, Any]:
    """Read the PDF metadata that is explicitly present in the file."""
    raw_metadata = document.metadata or {}

    metadata = {
        "document_title": _safe_metadata_value(raw_metadata.get("title")),
        "author": _safe_metadata_value(raw_metadata.get("author")),
        "subject": _safe_metadata_value(raw_metadata.get("subject")),
        "creator": _safe_metadata_value(raw_metadata.get("creator")),
        "producer": _safe_metadata_value(raw_metadata.get("producer")),
        "creation_date": _safe_metadata_value(raw_metadata.get("creationDate")),
        "modification_date": _safe_metadata_value(raw_metadata.get("modDate")),
        "pdf_version": getattr(document, "pdf_version", None),
        "page_count": len(document),
        "filename": file_path.name,
        "file_size_bytes": file_path.stat().st_size if file_path.exists() else None,
    }

    return metadata


def extract_pdf_text(pdf_path: str | Path) -> dict[str, Any]:
    """Open a PDF, extract page-by-page text, and return a structured inspection result.

    This function is intentionally narrow: it focuses on reliable extraction and basic
    document inspection without modifying the source PDF.
    """
    target_path = Path(pdf_path)
    report: dict[str, Any] = {
        "status": "FAILED",
        "file": {
            "path": str(target_path),
            "filename": target_path.name,
            "exists": target_path.exists(),
            "file_size_bytes": target_path.stat().st_size if target_path.exists() else None,
        },
        "metadata": {},
        "page_count": 0,
        "summary": {
            "pages_with_text": 0,
            "pages_with_low_text": 0,
            "empty_pages": 0,
            "image_only_pages": 0,
            "pages_with_errors": 0,
        },
        "pages": [],
        "extraction_warnings": [],
        "errors": [],
    }

    if not target_path.exists():
        report["errors"].append("File does not exist.")
        return report

    try:
        with fitz.open(str(target_path)) as document:
            report["metadata"] = _read_metadata(document, target_path)
            report["page_count"] = len(document)

            for page_number in range(len(document)):
                page_entry: dict[str, Any] = {
                    "page_number": page_number + 1,
                    "text": "",
                    "extraction_error": None,
                    "extraction_status": "FAILED",
                    "has_extractable_text": False,
                    "text_length": 0,
                    "word_count": 0,
                    "likely_blank_or_unreadable": False,
                    "likely_image_only": False,
                    "needs_ocr_review": False,
                }

                try:
                    page = document[page_number]
                    page_images = page.get_images(full=True)
                    page_text = page.get_text("text") or ""
                    page_entry["text"] = page_text
                    page_entry["text_length"] = len(page_text)
                    page_entry["word_count"] = len(page_text.split())
                    page_entry["has_extractable_text"] = bool(page_text.strip())

                    if not page_text.strip():
                        if page_images:
                            page_entry["extraction_status"] = "IMAGE_ONLY"
                            page_entry["likely_image_only"] = True
                            page_entry["needs_ocr_review"] = True
                            report["extraction_warnings"].append(
                                f"Page {page_number + 1}: no text extracted; image-only page detected. OCR review recommended."
                            )
                        else:
                            page_entry["extraction_status"] = "EMPTY"
                            page_entry["likely_blank_or_unreadable"] = True
                            report["extraction_warnings"].append(
                                f"Page {page_number + 1}: no extractable text found."
                            )
                    elif len(page_text.strip()) < 50:
                        page_entry["extraction_status"] = "LOW_TEXT"
                        report["extraction_warnings"].append(
                            f"Page {page_number + 1}: unusually little text extracted for a normal page."
                        )
                    else:
                        page_entry["extraction_status"] = "SUCCESS"

                except Exception as exc:  # pragma: no cover - defensive guard for single-page failures
                    page_entry["extraction_error"] = str(exc)
                    report["errors"].append(f"Page {page_number + 1}: {exc}")
                    report["extraction_warnings"].append(
                        f"Page {page_number + 1}: extraction failed and was recorded without crashing the process."
                    )

                report["pages"].append(page_entry)

            report["summary"] = {
                "pages_with_text": sum(
                    page["has_extractable_text"] for page in report["pages"]
                ),
                "pages_with_low_text": sum(
                    page["extraction_status"] == "LOW_TEXT"
                    for page in report["pages"]
                ),
                "empty_pages": sum(
                    page["extraction_status"] == "EMPTY"
                    for page in report["pages"]
                ),
                "image_only_pages": sum(
                    page["extraction_status"] == "IMAGE_ONLY"
                    for page in report["pages"]
                ),
                "pages_with_errors": sum(
                    page["extraction_status"] == "FAILED"
                    for page in report["pages"]
                ),
            }

            if report["errors"]:
                report["status"] = "NEEDS_REVIEW"
            elif report["extraction_warnings"]:
                report["status"] = "SUCCESS_WITH_WARNINGS"
            else:
                report["status"] = "SUCCESS"

    except Exception as exc:
        report["errors"].append(f"Failed to open or read PDF: {exc}")
        report["status"] = "FAILED"

    return report


def save_inspection_report(report: dict[str, Any], output_path: str | Path) -> Path:
    """Save a structured PDF inspection result to a JSON file.

    The function writes the report as JSON and creates parent directories when needed.
    It does not modify the original source PDF.
    """
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    return destination


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract text and basic metadata from a PDF file.")
    parser.add_argument("pdf_path", type=str, help="Path to the PDF file to inspect.")
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to save the JSON inspection report.",
    )
    args = parser.parse_args()

    result = extract_pdf_text(args.pdf_path)
    output_target = Path(args.output) if args.output else Path(args.pdf_path).with_suffix("_inspection_report.json")
    saved_path = save_inspection_report(result, output_target)
    print(json.dumps({"status": result["status"], "output_path": str(saved_path)}, indent=2, ensure_ascii=False))
