"""End-to-end test against the provided PDF and the independent ground truth."""
import json
from pathlib import Path

from table_parser.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "data" / "balance_sheet_after_correction.pdf"
GROUND_TRUTH = ROOT / "data" / "ground_truth.json"


def _load_ground_truth():
    return json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))


def _normalize_rows_for_compare(rows):
    """Reduce a row list to the fields the evaluation cares about."""
    return [
        {
            "row_index": r["row_index"],
            "label": r["label"],
            "depth": r["depth"],
            "row_type": r["row_type"],
            "parent_id": r.get("parent_id"),
            "values": r["values"],
        }
        for r in rows
    ]


def test_end_to_end_matches_ground_truth():
    document = run_pipeline(PDF)
    gt = _load_ground_truth()

    assert len(document.rows) == len(gt["rows"]) == 43

    pred_rows = _normalize_rows_for_compare([r.to_dict() for r in document.rows])
    gt_rows = _normalize_rows_for_compare(gt["rows"])

    assert pred_rows == gt_rows

    assert [c.id for c in document.columns] == ["previous_year", "current_year"]
    assert [c.date for c in document.columns] == ["2025-03-31", "2026-03-31"]
    assert document.unit == "千円"
    assert document.document_type == "consolidated_balance_sheet"


def test_end_to_end_is_deterministic():
    d1 = run_pipeline(PDF)
    d2 = run_pipeline(PDF)
    assert d1.to_dict() == d2.to_dict()


def test_end_to_end_negative_zero_and_dash_preserved():
    document = run_pipeline(PDF)
    rows = {r.label: r for r in document.rows}

    allowance = [r for r in document.rows if r.label == "貸倒引当金"][0]
    assert allowance.values["current_year"].raw == "△0"
    assert allowance.values["current_year"].value == 0
    assert allowance.values["current_year"].is_negative is True
    assert allowance.values["previous_year"].value == -2979

    cip = [r for r in document.rows if r.label == "建設仮勘定"][0]
    assert cip.values["previous_year"].parse_status == "dash"
    assert cip.values["previous_year"].value is None
