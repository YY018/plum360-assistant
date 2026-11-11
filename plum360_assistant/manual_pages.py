"""Render pages and figures from the locally stored manual PDF.

The PDF is private project data (kept under the git-ignored ``data/``
directory); nothing here sends it anywhere.
"""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANUAL_PDF = (
    PROJECT_ROOT / "data" / "raw" / "manuals" / "plum_360_som_pn-ifu0000340_21658851.pdf"
)

# Printed page labels look like "2-14" or "11-6" (section-page).
_LABEL = re.compile(r"^\s*(\d{1,2}-\d{1,3})\s*$")

# PyMuPDF documents are not thread-safe; FastAPI serves requests in a pool.
_lock = threading.Lock()


class ManualUnavailableError(RuntimeError):
    """Raised when the manual PDF is missing or a page does not exist."""


def manual_pdf_path() -> Path:
    raw = os.getenv("MANUAL_PDF_PATH", "").strip()
    if not raw:
        return DEFAULT_MANUAL_PDF
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


@lru_cache(maxsize=1)
def _document():
    import pymupdf

    path = manual_pdf_path()
    if not path.is_file():
        raise ManualUnavailableError(f"Manual PDF not found at {path}.")
    return pymupdf.open(path)


def page_count() -> int:
    with _lock:
        return _document().page_count


def _check_page(page_number: int) -> None:
    if not 1 <= page_number <= page_count():
        raise ManualUnavailableError(f"Page {page_number} is outside the manual.")


@lru_cache(maxsize=96)
def render_page_png(page_number: int, dpi: int = 144) -> bytes:
    """Render one PDF page (1-based) to PNG bytes."""
    _check_page(page_number)
    with _lock:
        return _document()[page_number - 1].get_pixmap(dpi=dpi).tobytes("png")


@lru_cache(maxsize=1)
def page_labels() -> dict[str, int]:
    """Map printed labels (for example "11-6") to 1-based PDF page numbers.

    Each body page prints its label in the running header or footer, so the
    first and last few lines of the page text are checked.
    """
    labels: dict[str, int] = {}
    with _lock:
        document = _document()
        for index in range(document.page_count):
            lines = [line for line in document[index].get_text().splitlines() if line.strip()]
            for line in lines[:3] + lines[-3:]:
                match = _LABEL.match(line)
                if match and match.group(1) not in labels:
                    labels[match.group(1)] = index + 1
                    break
    return labels


def page_label(page_number: int) -> str | None:
    for label, number in page_labels().items():
        if number == page_number:
            return label
    return None


@dataclass(frozen=True)
class Figure:
    slug: str
    page: int
    label: str
    caption: str
    # Clip rectangle as fractions of the page (x0, y0, x1, y1).
    clip: tuple[float, float, float, float]


FIGURES: tuple[Figure, ...] = (
    Figure("infuser-front", 45, "2-1", "The infuser with its Connectivity Engine module",
           (0.22, 0.54, 0.80, 0.875)),
    Figure("keypad-display", 46, "2-2", "Alphanumeric keypad and display",
           (0.05, 0.355, 0.96, 0.905)),
    Figure("administration-set", 58, "2-14", "A Plum administration set and its parts",
           (0.17, 0.265, 0.89, 0.684)),
    Figure("cassette", 59, "2-15", "The PlumSet cassette",
           (0.11, 0.215, 0.89, 0.485)),
)


def render_figure_png(figure: Figure, dpi: int = 220) -> bytes:
    import pymupdf

    _check_page(figure.page)
    with _lock:
        page = _document()[figure.page - 1]
        width, height = page.rect.width, page.rect.height
        x0, y0, x1, y1 = figure.clip
        clip = pymupdf.Rect(x0 * width, y0 * height, x1 * width, y1 * height)
        return page.get_pixmap(dpi=dpi, clip=clip).tobytes("png")
