"""Model-independent extractor interface.

The coordinate-based extractor (``layout_extractor``) is the default. An OCR or
vision-language-model extractor can be added by implementing
:class:`TableExtractor` and returning a :class:`~table_parser.models.DocumentTable`
with the same schema, so normalization and evaluation are reused unchanged.

No VLM/OCR backend is shipped by default, and none is claimed to work: the core
project runs without credentials.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from .models import DocumentTable


class TableExtractor(ABC):
    """Interface for a table extraction engine."""

    name: str = "base"

    @abstractmethod
    def extract(self, pdf_path: Union[str, Path]) -> DocumentTable:
        """Extract a :class:`DocumentTable` from a PDF path."""
        raise NotImplementedError
