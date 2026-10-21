"""Diagnostic validation: arithmetic consistency checks.

These checks are *diagnostics*, not corrections. Displayed financial totals can
legitimately differ from the sum of their displayed components due to rounding or
reporting conventions, so the pipeline never rewrites an extracted value based on
an arithmetic mismatch. Each ``合計`` (subtotal/total) row is checked against the
sum of the "net" leaves in its section.

Leaf rules (applied within a section, i.e. between the subtotal and the nearest
preceding row of shallower depth):
- section / subsection header rows and nested ``合計`` rows are excluded;
- ``減価償却累計額`` (accumulated depreciation) rows are excluded;
- a gross row that is immediately followed by a ``減価償却累計額`` row is excluded
  (its ``（純額）`` net row carries the net contribution);
- ``（純額）`` net rows contribute their own value;
- a dash placeholder contributes 0 for the purposes of arithmetic only.
"""
from __future__ import annotations

from typing import List, Optional

from .models import Row


def _numeric(row: Row, col_id: str) -> Optional[int]:
    cell = row.values.get(col_id)
    if cell is None:
        return None
    if cell.parse_status == "parsed":
        return cell.value
    if cell.parse_status == "dash":
        return 0
    return None


def _section_leaf_sum(rows: List[Row], subtotal_idx: int, col_id: str) -> Optional[int]:
    """Sum the net leaves of the section closed by ``rows[subtotal_idx]``."""
    depth = rows[subtotal_idx].depth
    start = None
    for j in range(subtotal_idx - 1, -1, -1):
        if rows[j].depth < depth:
            start = j
            break
    if start is None:
        return None

    total = 0
    k = start + 1
    while k < subtotal_idx:
        r = rows[k]
        label = r.label
        if label.endswith("合計"):
            k += 1
            continue
        if r.row_type in ("section", "subsection"):
            k += 1
            continue
        if label == "減価償却累計額":
            k += 1
            continue
        if label.endswith("（純額）"):
            v = _numeric(r, col_id)
            if v is None:
                return None
            total += v
            k += 1
            continue
        # Gross / plain detail row: skip if immediately followed by depreciation.
        nxt = rows[k + 1] if k + 1 < subtotal_idx else None
        if nxt is not None and nxt.label == "減価償却累計額":
            k += 1
            continue
        v = _numeric(r, col_id)
        if v is None:
            return None
        total += v
        k += 1
    return total


def arithmetic_checks(rows: List[Row], column_ids: List[str]) -> List[dict]:
    """Return a list of arithmetic warnings (one per subtotal row per column)."""
    warnings: List[dict] = []
    for col_id in column_ids:
        for i, r in enumerate(rows):
            if not r.label.endswith("合計"):
                continue
            expected = _section_leaf_sum(rows, i, col_id)
            cell = r.values.get(col_id)
            if expected is None or cell is None or cell.parse_status != "parsed":
                warnings.append(
                    {
                        "row_index": i,
                        "label": r.label,
                        "column": col_id,
                        "check": "unverifiable",
                        "expected": expected,
                        "actual": None if cell is None else cell.value,
                        "diff": None,
                    }
                )
                continue
            diff = cell.value - expected
            warnings.append(
                {
                    "row_index": i,
                    "label": r.label,
                    "column": col_id,
                    "check": "ok" if diff == 0 else "mismatch",
                    "expected": expected,
                    "actual": cell.value,
                    "diff": diff,
                }
            )
    return warnings
