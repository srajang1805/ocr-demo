"""Stage D: hierarchical structure (depth, parent, row type)."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .layout_extractor import DEPTH_X_TOLERANCE, RawRow
from .models import ColumnSpec, Row
from .normalizer import NormalizedValue


def classify_row_type(label: str, has_values: bool, depth: int) -> str:
    """Classify a row based on its label and whether it carries values."""
    if label.endswith("の部"):
        return "section"
    if label.endswith("合計"):
        # A 合計 row at the shallowest structural level is the grand total.
        return "total" if depth <= 1 else "subtotal"
    if label == "減価償却累計額":
        return "depreciation"
    if label.endswith("（純額）"):
        return "net"
    if not has_values:
        return "subsection"
    return "detail"


def _cluster(values: List[float], tol: float) -> List[List[float]]:
    values = sorted(values)
    clusters: List[List[float]] = []
    for v in values:
        if clusters and v - clusters[-1][-1] <= tol:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return clusters


def _assign_depths(rows: List[Row]) -> None:
    """Derive indentation depth by clustering label x-positions."""
    xs = [r.source.get("x0") for r in rows if r.source.get("x0") is not None]
    if not xs:
        for r in rows:
            r.depth = 0
        return

    clusters = _cluster(sorted(set(xs)), DEPTH_X_TOLERANCE)
    level_for_value: Dict[float, int] = {}
    for level, cluster in enumerate(clusters):
        for v in cluster:
            level_for_value[v] = level

    for r in rows:
        x0 = r.source.get("x0")
        if x0 is None:
            r.depth = 0
            continue
        best = min(level_for_value, key=lambda v: abs(v - x0))
        r.depth = level_for_value[best]


def _assign_parents(rows: List[Row]) -> None:
    for i, r in enumerate(rows):
        r.parent_id = None
        r.parent_label = None
        for j in range(i - 1, -1, -1):
            if rows[j].depth < r.depth:
                r.parent_id = rows[j].id
                r.parent_label = rows[j].label
                break


def build_rows(
    raw_rows: List[RawRow],
    columns: List[ColumnSpec],
    normalized: Dict[Tuple[int, str], NormalizedValue],
) -> List[Row]:
    """Convert raw rows plus normalized cells into structured :class:`Row` objects.

    ``normalized`` maps ``(row_position, column_id) -> NormalizedValue``. Every row
    receives a cell entry for every column (empty when the source had no value),
    so downstream flat outputs (CSV) have a stable column layout.
    """
    col_ids = [c.id for c in columns]
    rows: List[Row] = []

    for idx, raw in enumerate(raw_rows):
        values: Dict[str, NormalizedValue] = {}
        for cid in col_ids:
            cell = normalized.get((idx, cid))
            values[cid] = cell if cell is not None else NormalizedValue(None, None, False, "empty")

        has_values = any(v.parse_status != "empty" for v in values.values())
        row = Row(
            id=f"row_{idx}",
            row_index=idx,
            label=raw.label,
            depth=0,
            row_type="detail",
            values=values,
            source={"page": raw.page, "y": raw.y, "x0": raw.label_x0},
        )
        rows.append(row)

    _assign_depths(rows)
    for r in rows:
        has_values = any(v.parse_status != "empty" for v in r.values.values())
        r.row_type = classify_row_type(r.label, has_values, r.depth)
    _assign_parents(rows)
    return rows
