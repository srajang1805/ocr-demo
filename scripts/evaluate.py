#!/usr/bin/env python
"""Evaluate parser output against independent ground truth.

Produces ``evaluation.json`` (machine-readable metrics) and
``evaluation_report.md`` (human-readable report).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional


def _add_project_root_to_path() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _cell(row: Dict[str, Any], cid: str) -> Dict[str, Any]:
    return row.get("values", {}).get(cid, {})


def _is_value_cell(cell: Dict[str, Any]) -> bool:
    return cell.get("parse_status", "empty") != "empty"


def compare(gt: Dict[str, Any], pred: Dict[str, Any]) -> Dict[str, Any]:
    """Compare two document tables and return metrics plus a mismatch list.

    Rows are matched by ``row_index`` (positional). Cell-level metrics are computed
    over *all* ground-truth value cells, including cells whose row is missing from the
    prediction; a missing row counts as a raw-string mismatch and (where the ground
    truth is numeric) a numeric parsing failure, so dropped rows cannot inflate
    cell-level accuracy.
    """
    gt_rows = gt["rows"]
    pred_rows = pred["rows"]
    gt_cols = [c["id"] for c in gt["document"]["columns"]]
    pred_cols = [c["id"] for c in pred["document"]["columns"]]

    gt_by_idx: Dict[int, Dict[str, Any]] = {r["row_index"]: r for r in gt_rows}
    pred_by_idx: Dict[int, Dict[str, Any]] = {r["row_index"]: r for r in pred_rows}

    gt_dup = [i for i, c in Counter(r["row_index"] for r in gt_rows).items() if c > 1]
    pred_dup = [i for i, c in Counter(r["row_index"] for r in pred_rows).items() if c > 1]

    gt_idx = set(gt_by_idx)
    pred_idx = set(pred_by_idx)
    common = sorted(gt_idx & pred_idx)
    missing = sorted(gt_idx - pred_idx)
    extra = sorted(pred_idx - gt_idx)

    mismatches: List[Dict[str, Any]] = []

    label_exact = 0
    depth_exact = 0
    parent_exact = 0
    rowtype_exact = 0

    raw_cells = 0
    raw_exact = 0
    cell_exact = 0
    numeric_cells = 0
    numeric_exact = 0
    numeric_parse_failures = 0

    page_for_gt = gt["document"].get("page", 1)

    def _record(page, idx, label, column, field, expected, predicted) -> None:
        mismatches.append(
            {
                "page": page,
                "row_index": idx,
                "row_label": label,
                "column": column,
                "field": field,
                "expected": expected,
                "predicted": predicted,
            }
        )

    def _compare_cell(idx, row_label, page, cid, gc, pc) -> None:
        nonlocal raw_cells, raw_exact, cell_exact
        nonlocal numeric_cells, numeric_exact, numeric_parse_failures
        if not _is_value_cell(gc):
            return
        raw_cells += 1
        pc_raw = pc.get("raw") if pc else None
        if pc_raw == gc.get("raw"):
            raw_exact += 1
        else:
            _record(page, idx, row_label, cid, "raw", gc.get("raw"), pc_raw)

        if (
            pc
            and pc.get("raw") == gc.get("raw")
            and pc.get("value") == gc.get("value")
            and pc.get("is_negative") == gc.get("is_negative")
            and pc.get("parse_status") == gc.get("parse_status")
        ):
            cell_exact += 1

        if gc.get("parse_status") == "parsed":
            numeric_cells += 1
            if (
                pc
                and pc.get("parse_status") == "parsed"
                and pc.get("value") == gc.get("value")
            ):
                numeric_exact += 1
            else:
                numeric_parse_failures += 1

    for idx in common:
        g = gt_by_idx[idx]
        p = pred_by_idx[idx]
        page = p.get("source", {}).get("page", page_for_gt)

        if p.get("label") == g.get("label"):
            label_exact += 1
        else:
            _record(page, idx, g.get("label"), None, "label", g.get("label"), p.get("label"))

        if p.get("depth") == g.get("depth"):
            depth_exact += 1
        else:
            _record(page, idx, g.get("label"), None, "depth", g.get("depth"), p.get("depth"))

        if p.get("parent_id") == g.get("parent_id"):
            parent_exact += 1
        else:
            _record(page, idx, g.get("label"), None, "parent_id", g.get("parent_id"), p.get("parent_id"))

        if p.get("row_type") == g.get("row_type"):
            rowtype_exact += 1

        for cid in gt_cols:
            _compare_cell(idx, g.get("label"), page, cid, _cell(g, cid), _cell(p, cid))

    for idx in missing:
        g = gt_by_idx[idx]
        _record(page_for_gt, idx, g.get("label"), None, "label", g.get("label"), None)
        for cid in gt_cols:
            _compare_cell(idx, g.get("label"), page_for_gt, cid, _cell(g, cid), None)

    n_common = len(common)
    n_gt_unique = len(gt_idx)
    n_pred_unique = len(pred_idx)

    precision = n_common / n_pred_unique if n_pred_unique else 0.0
    recall = n_common / n_gt_unique if n_gt_unique else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    pred_seq = [r["row_index"] for r in pred_rows]
    gt_seq = [r["row_index"] for r in gt_rows]
    ordering_ok = pred_seq == gt_seq

    structural_mismatches = (
        (n_common - depth_exact) + (n_common - parent_exact) + (n_common - rowtype_exact)
    )

    return {
        "summary": {
            "expected_rows": len(gt_rows),
            "predicted_rows": len(pred_rows),
            "matched_rows": n_common,
            "label_exact_rows": label_exact,
            "missing_rows": missing,
            "extra_rows": extra,
            "duplicated_gt_rows": gt_dup,
            "duplicated_pred_rows": pred_dup,
            "expected_value_cells": raw_cells,
            "exact_matching_cells": raw_exact,
            "numeric_parsing_failures": numeric_parse_failures,
            "structural_mismatches": structural_mismatches,
        },
        "metrics": {
            "row_label_accuracy": label_exact / n_common if n_common else None,
            "raw_string_accuracy": raw_exact / raw_cells if raw_cells else None,
            "numeric_accuracy": numeric_exact / numeric_cells if numeric_cells else None,
            "cell_exact_match_accuracy": cell_exact / raw_cells if raw_cells else None,
            "row_detection_precision": precision,
            "row_detection_recall": recall,
            "row_detection_f1": f1,
            "depth_accuracy": depth_exact / n_common if n_common else None,
            "parent_child_accuracy": parent_exact / n_common if n_common else None,
            "row_type_accuracy": rowtype_exact / n_common if n_common else None,
            "ordering_accuracy": 1.0 if ordering_ok else 0.0,
            "column_set_match": gt_cols == pred_cols,
        },
        "arithmetic": {
            "warnings": pred.get("warnings", []),
            "count": len(pred.get("warnings", [])),
        },
        "mismatches": mismatches,
    }


def _render_report(result: Dict[str, Any], gt_path: str, pred_path: str) -> str:
    s = result["summary"]
    m = result["metrics"]

    def pct(x: Optional[float]) -> str:
        return "n/a" if x is None else f"{x * 100:.2f}%"

    lines = [
        "# Evaluation report",
        "",
        f"- Ground truth: `{gt_path}`",
        f"- Predicted:    `{pred_path}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Expected rows | {s['expected_rows']} |",
        f"| Predicted rows | {s['predicted_rows']} |",
        f"| Matched rows (by row index) | {s['matched_rows']} |",
        f"| Label-exact rows | {s['label_exact_rows']} |",
        f"| Missing rows | {len(s['missing_rows'])} |",
        f"| Extra rows | {len(s['extra_rows'])} |",
        f"| Expected value cells | {s['expected_value_cells']} |",
        f"| Exact matching cells (raw) | {s['exact_matching_cells']} |",
        f"| Numeric parsing failures | {s['numeric_parsing_failures']} |",
        f"| Structural mismatches | {s['structural_mismatches']} |",
        f"| Arithmetic validation warnings | {result['arithmetic']['count']} |",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Row-label accuracy | {pct(m['row_label_accuracy'])} |",
        f"| Raw-string accuracy | {pct(m['raw_string_accuracy'])} |",
        f"| Normalized numeric accuracy | {pct(m['numeric_accuracy'])} |",
        f"| Cell exact-match accuracy | {pct(m['cell_exact_match_accuracy'])} |",
        f"| Row detection precision | {pct(m['row_detection_precision'])} |",
        f"| Row detection recall | {pct(m['row_detection_recall'])} |",
        f"| Row detection F1 | {pct(m['row_detection_f1'])} |",
        f"| Depth accuracy | {pct(m['depth_accuracy'])} |",
        f"| Parent-child accuracy | {pct(m['parent_child_accuracy'])} |",
        f"| Row-type accuracy | {pct(m['row_type_accuracy'])} |",
        f"| Ordering accuracy | {pct(m['ordering_accuracy'])} |",
        f"| Column-set match | {m['column_set_match']} |",
        "",
    ]

    if s["missing_rows"]:
        lines.append("## Missing rows")
        lines.append("")
        for i in s["missing_rows"]:
            lines.append(f"- row_index {i}")
        lines.append("")

    if s["extra_rows"]:
        lines.append("## Extra rows")
        lines.append("")
        for i in s["extra_rows"]:
            lines.append(f"- row_index {i}")
        lines.append("")

    if s.get("duplicated_gt_rows") or s.get("duplicated_pred_rows"):
        lines.append("## Duplicated rows")
        lines.append("")
        for i in s.get("duplicated_gt_rows", []):
            lines.append(f"- ground truth row_index {i}")
        for i in s.get("duplicated_pred_rows", []):
            lines.append(f"- predicted row_index {i}")
        lines.append("")

    lines.append("## Mismatches")
    lines.append("")
    if not result["mismatches"]:
        lines.append("None.")
    else:
        lines.append(
            "| page | row_index | row_label | column | field | expected | predicted |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for mm in result["mismatches"]:
            lines.append(
                f"| {mm['page']} | {mm['row_index']} | {mm['row_label']} | "
                f"{mm['column']} | {mm['field']} | {mm['expected']} | {mm['predicted']} |"
            )
    lines.append("")

    lines.append("## Arithmetic validation")
    lines.append("")
    warnings = result["arithmetic"]["warnings"]
    if not warnings:
        lines.append("No subtotal/total rows to check.")
    else:
        lines.append(
            "Arithmetic checks are diagnostics: displayed totals may differ from the sum of "
            "displayed components due to rounding or reporting conventions. They do not rewrite "
            "extracted values."
        )
        lines.append("")
        lines.append("| row_index | label | column | check | expected | actual | diff |")
        lines.append("|---|---|---|---|---|---|---|")
        for w in warnings:
            lines.append(
                f"| {w['row_index']} | {w['label']} | {w['column']} | {w['check']} | "
                f"{w['expected']} | {w['actual']} | {w['diff']} |"
            )
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Evaluate parser output against ground truth.")
    parser.add_argument("--ground-truth", type=str, default="data/ground_truth.json")
    parser.add_argument("--output", type=str, default="outputs/output.json")
    parser.add_argument("--output-dir", type=str, default="outputs")
    args = parser.parse_args()

    gt_path = Path(args.ground_truth)
    pred_path = Path(args.output)
    if not gt_path.exists():
        print(f"error: ground truth not found: {gt_path}", file=sys.stderr)
        return 1
    if not pred_path.exists():
        print(f"error: output not found: {pred_path}", file=sys.stderr)
        return 1

    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    pred = json.loads(pred_path.read_text(encoding="utf-8"))

    result = compare(gt, pred)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    eval_json = out_dir / "evaluation.json"
    eval_json.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    report = _render_report(result, str(gt_path), str(pred_path))
    (out_dir / "evaluation_report.md").write_text(report, encoding="utf-8")

    s = result["summary"]
    m = result["metrics"]
    print(f"expected rows:       {s['expected_rows']}")
    print(f"predicted rows:      {s['predicted_rows']}")
    print(f"matched rows:        {s['matched_rows']}")
    print(f"label accuracy:      {m['row_label_accuracy']:.4f}" if m["row_label_accuracy"] is not None else "label accuracy: n/a")
    print(f"raw-string accuracy: {m['raw_string_accuracy']:.4f}" if m["raw_string_accuracy"] is not None else "raw-string accuracy: n/a")
    print(f"numeric accuracy:    {m['numeric_accuracy']:.4f}" if m["numeric_accuracy"] is not None else "numeric accuracy: n/a")
    print(f"cell exact-match:    {m['cell_exact_match_accuracy']:.4f}" if m["cell_exact_match_accuracy"] is not None else "cell exact-match: n/a")
    print(f"row F1:              {m['row_detection_f1']:.4f}")
    print(f"mismatches:          {len(result['mismatches'])}")
    print(f"wrote: {eval_json}")
    print(f"wrote: {out_dir / 'evaluation_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
