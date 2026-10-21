#!/usr/bin/env python
"""Run the table parser on a PDF and write output.json and output.csv."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def _add_project_root_to_path() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def write_json(document, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(document.to_dict(), f, ensure_ascii=False, indent=2)


def write_csv(document, path: Path) -> None:
    col_ids = [c.id for c in document.columns]
    header = (
        ["row_id", "row_index", "parent_id", "depth", "row_type", "label"]
        + [f"{cid}_raw" for cid in col_ids]
        + [f"{cid}_value" for cid in col_ids]
    )
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for r in document.rows:
            row = [r.id, r.row_index, r.parent_id if r.parent_id else "", r.depth, r.row_type, r.label]
            for cid in col_ids:
                cell = r.values.get(cid)
                raw = cell.raw if cell and cell.parse_status != "empty" else ""
                row.append(raw)
            for cid in col_ids:
                cell = r.values.get(cid)
                value = cell.value if cell and cell.value is not None else ""
                row.append(value)
            writer.writerow(row)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Extract a Japanese financial table from a PDF.")
    parser.add_argument(
        "--input",
        type=str,
        default="data/balance_sheet_after_correction.pdf",
        help="Path to the input PDF.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs",
        help="Directory for output.json and output.csv.",
    )
    args = parser.parse_args()

    _add_project_root_to_path()
    from table_parser.pipeline import run_pipeline  # noqa: E402

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"error: input file not found: {input_path}", file=sys.stderr)
        return 1

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    document = run_pipeline(input_path)
    write_json(document, out_dir / "output.json")
    write_csv(document, out_dir / "output.csv")

    print(f"rows:        {len(document.rows)}")
    print(f"columns:     {', '.join(c.id for c in document.columns)}")
    print(f"unit:        {document.unit}")
    print(f"doc type:    {document.document_type}")
    print(f"warnings:    {len(document.warnings)}")
    print(f"wrote:       {out_dir / 'output.json'}")
    print(f"wrote:       {out_dir / 'output.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
