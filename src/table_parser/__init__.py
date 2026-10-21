"""Document Intelligence table parser for Japanese financial statements."""

from .normalizer import NormalizedValue, normalize_value, is_dash
from .pdf_loader import PdfPage, Word, load_pdf, render_page
from .pipeline import run_pipeline, Pipeline

__all__ = [
    "NormalizedValue",
    "normalize_value",
    "is_dash",
    "PdfPage",
    "Word",
    "load_pdf",
    "render_page",
    "Pipeline",
    "run_pipeline",
]

__version__ = "0.1.0"
