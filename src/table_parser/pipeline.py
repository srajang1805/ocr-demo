"""Pipeline orchestration: ingestion -> layout -> normalization -> hierarchy -> validation."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple, Union

from .extractor_interface import TableExtractor
from .hierarchy import build_rows
from .layout_extractor import RawTable, build_raw_table
from .models import DocumentTable
from .normalizer import NormalizedValue, normalize_value
from .pdf_loader import load_pdf
from .validator import arithmetic_checks


class CoordinateExtractor(TableExtractor):
    """Default extractor built on PyMuPDF word coordinates."""

    name = "coordinate"

    def extract(self, pdf_path: Union[str, Path]) -> DocumentTable:
        pages = load_pdf(pdf_path)
        source_name = Path(pdf_path).name
        raw = build_raw_table(pages, source_name)

        normalized: Dict[Tuple[int, str], NormalizedValue] = {}
        for idx, raw_row in enumerate(raw.rows):
            for col_id, raw_cell in raw_row.cells.items():
                normalized[(idx, col_id)] = normalize_value(raw_cell)

        rows = build_rows(raw.rows, raw.columns, normalized)
        warnings = arithmetic_checks(rows, [c.id for c in raw.columns])

        return DocumentTable(
            source_file=raw.source_file,
            document_type=raw.document_type,
            language=raw.language,
            unit=raw.unit,
            columns=raw.columns,
            rows=rows,
            page_count=raw.page_count,
            pages=raw.pages,
            warnings=warnings,
        )


class Pipeline:
    """Runs a configured extractor against an input PDF."""

    def __init__(self, extractor: TableExtractor | None = None):
        self.extractor = extractor or CoordinateExtractor()

    def run(self, pdf_path: Union[str, Path]) -> DocumentTable:
        return self.extractor.extract(pdf_path)


def run_pipeline(pdf_path: Union[str, Path]) -> DocumentTable:
    """Convenience entry point using the default coordinate extractor."""
    return Pipeline().run(pdf_path)
