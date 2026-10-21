"""Shared data models for the table parser."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .normalizer import NormalizedValue


@dataclass
class ColumnSpec:
    """A single value column (reporting period)."""

    id: str
    label: Optional[str] = None
    date: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "date": self.date}


@dataclass
class Row:
    """A single logical table row."""

    id: str
    row_index: int
    label: str
    depth: int
    row_type: str
    values: dict[str, NormalizedValue]
    parent_id: Optional[str] = None
    parent_label: Optional[str] = None
    label_en: Optional[str] = None
    source: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "row_index": self.row_index,
            "label": self.label,
            "label_en": self.label_en,
            "depth": self.depth,
            "row_type": self.row_type,
            "parent_id": self.parent_id,
            "parent_label": self.parent_label,
            "source": self.source,
            "values": {k: v.to_dict() for k, v in self.values.items()},
        }


@dataclass
class DocumentTable:
    """The full extracted document table."""

    source_file: str
    document_type: str
    language: str
    unit: Optional[str]
    columns: list[ColumnSpec]
    rows: list[Row]
    page_count: int = 1
    pages: list[int] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document": {
                "source_file": self.source_file,
                "document_type": self.document_type,
                "language": self.language,
                "unit": self.unit,
                "page_count": self.page_count,
                "pages": self.pages,
                "columns": [c.to_dict() for c in self.columns],
            },
            "rows": [r.to_dict() for r in self.rows],
            "warnings": self.warnings,
        }
