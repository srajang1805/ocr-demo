"""Stage A: PDF ingestion via PyMuPDF.

Extracts page text and per-word bounding boxes, and can render pages to PNG.
Supports multi-page documents: every page is loaded, although the supplied
example has a single page.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Union

import pymupdf


@dataclass(frozen=True)
class Word:
    """A single word token with its bounding box (PDF points, top-left origin)."""

    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    page: int


@dataclass
class PdfPage:
    """A single page of the input document."""

    number: int  # 1-based page number
    width: float
    height: float
    text: str
    words: List[Word]


def load_pdf(path: Union[str, Path]) -> List[PdfPage]:
    """Open *path* and return a :class:`PdfPage` per page."""
    doc = pymupdf.open(str(path))
    pages: List[PdfPage] = []
    try:
        for i, page in enumerate(doc):
            rect = page.rect
            words = [
                Word(
                    x0=float(w[0]),
                    y0=float(w[1]),
                    x1=float(w[2]),
                    y1=float(w[3]),
                    text=w[4],
                    page=i + 1,
                )
                for w in page.get_text("words")
            ]
            pages.append(
                PdfPage(
                    number=i + 1,
                    width=float(rect.width),
                    height=float(rect.height),
                    text=page.get_text("text"),
                    words=words,
                )
            )
    finally:
        doc.close()
    return pages


def render_page(
    path: Union[str, Path], page_number: int = 1, dpi: int = 150
) -> bytes:
    """Render *page_number* to a PNG image and return the raw bytes."""
    doc = pymupdf.open(str(path))
    try:
        page = doc[page_number - 1]
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("png")
    finally:
        doc.close()
