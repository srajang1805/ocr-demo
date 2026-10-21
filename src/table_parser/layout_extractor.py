"""Stage B: layout and table reconstruction from text coordinates.

Recovers logical rows and the value columns by clustering word bounding boxes,
rather than assuming a fixed number of spaces. The algorithm is coordinate based:

1. Drop footer words (page numbers).
2. Locate the table body (below the column-header date lines).
3. Detect value columns by clustering the right edges of numeric tokens.
4. Group words into rows by vertical alignment (y-center).
5. For each row, split left-hand label tokens from right-hand value tokens and
   assign each value token to the nearest detected column.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .models import ColumnSpec
from .normalizer import NEGATIVE_MARKERS, is_dash
from .pdf_loader import PdfPage, Word

#: Maximum vertical distance (points) between words considered part of the same row.
Y_TOLERANCE = 5.0
#: Footer region: ignore words whose top is this far from the bottom of the page.
FOOTER_MARGIN = 45.0
#: Tolerance used when clustering the right edges of numeric cells into columns.
COLUMN_X_TOLERANCE = 15.0
#: Tolerance used when clustering label x-positions into indentation levels.
DEPTH_X_TOLERANCE = 6.0

_KNOWN_COLUMN_LABELS = (
    "前連結会計年度",
    "当連結会計年度",
    "前事業年度",
    "当事業年度",
    "前年度",
    "当年度",
)


@dataclass
class RawRow:
    """A raw (unnormalized) logical row."""

    page: int
    y: float
    label: str
    label_x0: Optional[float]
    cells: dict  # column_id -> raw string


@dataclass
class RawTable:
    """Raw extraction result before normalization and hierarchy assignment."""

    source_file: str
    page_count: int
    pages: List[int]
    unit: Optional[str]
    document_type: str
    language: str
    columns: List[ColumnSpec]
    rows: List[RawRow]


@dataclass
class _Column:
    """Internal representation of a detected value column."""

    right_edge: float
    left_edge: float


def _looks_numeric(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if is_dash(t):
        return True
    if t[0] in NEGATIVE_MARKERS:
        return True
    return any(ch.isdigit() for ch in t)


def _fullwidth_to_ascii(s: str) -> str:
    return s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))


def _cluster_1d(values: List[float], tol: float) -> List[List[float]]:
    """Cluster a sorted list of 1-D values by proximity."""
    values = sorted(values)
    clusters: List[List[float]] = []
    for v in values:
        if clusters and v - clusters[-1][-1] <= tol:
            clusters[-1].append(v)
        else:
            clusters.append([v])
    return clusters


def _parse_unit(text: str) -> Optional[str]:
    m = re.search(r"（単位[：:]\s*([^）)]+)[）)]", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"単位[：:]\s*([^\s）)]+)", text)
    return m.group(1).strip() if m else None


def _parse_dates(text: str) -> List[Tuple[int, int, int]]:
    norm = _fullwidth_to_ascii(text)
    dates: List[Tuple[int, int, int]] = []
    for m in re.finditer(r"\((\d{4})\s*年\s*(\d{1,2})月\s*(\d{1,2})", norm):
        dates.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return dates


def _detect_column_labels(text: str) -> List[str]:
    labels: List[str] = []
    for m in re.finditer("|".join(_KNOWN_COLUMN_LABELS), text):
        labels.append(m.group(0))
    if len(labels) == 2:
        return labels
    # Generic fallback: any CJK word ending in 年度.
    return re.findall(r"[\u3040-\u30ff\u4e00-\u9fff]{1,20}年度", text)


def _fmt_date(ymd: Optional[Tuple[int, int, int]]) -> Optional[str]:
    if ymd is None:
        return None
    y, m, d = ymd
    return f"{y:04d}-{m:02d}-{d:02d}"


def _assign_column_ids(labels: List[str]) -> List[str]:
    if len(labels) == 2:
        first, second = labels[0] or "", labels[1] or ""
        if "前" in first and "当" in second:
            return ["previous_year", "current_year"]
    return [f"col_{i}" for i in range(len(labels))]


def _drop_footer(page: PdfPage) -> List[Word]:
    threshold = page.height - FOOTER_MARGIN
    return [w for w in page.words if w.y0 < threshold]


def _detect_body_start(words: List[Word]) -> float:
    """Return the y-coordinate at which the table body begins."""
    for w in words:
        if w.text.endswith("の部"):
            return w.y0 - 1.0
    # Fallback: just below the last date/column-header line.
    max_y = 0.0
    for w in words:
        if re.fullmatch(r"\(\d{4}", w.text) or "年" in w.text:
            max_y = max(max_y, w.y1)
    return max_y + 2.0


def _detect_columns(body_words: List[Word]) -> List[_Column]:
    """Cluster numeric tokens by right edge to discover value columns."""
    numeric = [w for w in body_words if _looks_numeric(w.text)]
    if not numeric:
        return []
    clusters = _cluster_1d([w.x1 for w in numeric], COLUMN_X_TOLERANCE)
    cols: List[_Column] = []
    for c in clusters:
        right = max(c)
        members = [w for w in numeric if abs(w.x1 - right) <= COLUMN_X_TOLERANCE]
        left = min(w.x0 for w in members)
        cols.append(_Column(right_edge=right, left_edge=left))
    cols.sort(key=lambda c: c.right_edge)
    return cols


def _assign_column(x1: float, cols: List[_Column]) -> int:
    return min(range(len(cols)), key=lambda k: abs(cols[k].right_edge - x1))


def _group_rows(body_words: List[Word]) -> List[List[Word]]:
    ordered = sorted(body_words, key=lambda w: (w.y0, w.x0))
    rows: List[List[Word]] = []
    current: List[Word] = []
    current_y: Optional[float] = None
    for w in ordered:
        yc = (w.y0 + w.y1) / 2.0
        if current_y is None or abs(yc - current_y) <= Y_TOLERANCE:
            current.append(w)
            current_y = sum((x.y0 + x.y1) / 2.0 for x in current) / len(current)
        else:
            rows.append(current)
            current = [w]
            current_y = yc
    if current:
        rows.append(current)
    return rows


def _assemble_row(
    page_number: int,
    row_words: List[Word],
    cols: List[_Column],
    label_boundary: float,
) -> Optional[RawRow]:
    label_words = sorted(
        [w for w in row_words if w.x0 < label_boundary], key=lambda w: w.x0
    )
    value_words = [w for w in row_words if w.x0 >= label_boundary]

    if not label_words:
        return None

    label = "".join(w.text for w in label_words)
    label_x0 = label_words[0].x0
    cells: dict = {}
    for w in value_words:
        col_idx = _assign_column(w.x1, cols)
        cells[col_idx] = cells.get(col_idx, "") + w.text

    y = min(w.y0 for w in row_words)
    return RawRow(
        page=page_number,
        y=y,
        label=label,
        label_x0=label_x0,
        cells=cells,
    )


def build_raw_table(pages: List[PdfPage], source_file: str) -> RawTable:
    """Extract a raw table (rows + columns, unnormalized) from all pages."""
    full_text = "\n".join(p.text for p in pages)

    unit = _parse_unit(full_text)
    dates = _parse_dates(full_text)
    labels = _detect_column_labels(full_text)

    if "連結貸借対照表" in full_text:
        document_type = "consolidated_balance_sheet"
    elif "貸借対照表" in full_text:
        document_type = "balance_sheet"
    else:
        document_type = "table"

    columns: Optional[List[_Column]] = None
    all_rows: List[RawRow] = []

    for page in pages:
        words = _drop_footer(page)
        body_start = _detect_body_start(words)
        body_words = [w for w in words if w.y0 >= body_start]

        # Detect columns on the first page that actually contains numeric value
        # tokens (a title page or cover page may precede the table). Reuse the
        # discovered columns for every subsequent page.
        if not columns:
            columns = _detect_columns(body_words)

        if not columns:
            continue

        label_boundary = min(c.left_edge for c in columns) - 1.0
        for group in _group_rows(body_words):
            raw_row = _assemble_row(page.number, group, columns, label_boundary)
            if raw_row is not None:
                all_rows.append(raw_row)

    col_ids = _assign_column_ids(labels)
    column_specs: List[ColumnSpec] = []
    for i, c in enumerate(columns):
        cid = col_ids[i] if i < len(col_ids) else f"col_{i}"
        clabel = labels[i] if i < len(labels) else None
        cdate = _fmt_date(dates[i]) if i < len(dates) else None
        column_specs.append(ColumnSpec(id=cid, label=clabel, date=cdate))

    # Remap integer column indices in RawRow.cells to stable column ids.
    for row in all_rows:
        remapped = {}
        for idx, raw in row.cells.items():
            cid = col_ids[idx] if idx < len(col_ids) else f"col_{idx}"
            remapped[cid] = raw
        row.cells = remapped

    return RawTable(
        source_file=source_file,
        page_count=len(pages),
        pages=[p.number for p in pages],
        unit=unit,
        document_type=document_type,
        language="ja",
        columns=column_specs,
        rows=all_rows,
    )
