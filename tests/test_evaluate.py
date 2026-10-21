"""Tests for the evaluation harness (missing / extra / duplicated rows)."""
import importlib.util
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load_evaluate():
    spec = importlib.util.spec_from_file_location("evaluate", SCRIPTS / "evaluate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _doc(rows):
    return {
        "document": {
            "page": 1,
            "columns": [{"id": "previous_year"}, {"id": "current_year"}],
        },
        "rows": rows,
    }


def _row(idx, label, value=None):
    def cell(raw, val, status):
        return {"raw": raw, "value": val, "is_negative": False, "parse_status": status}

    values = {
        "previous_year": cell(value, value, "parsed" if value is not None else "empty"),
        "current_year": cell(None, None, "empty"),
    }
    return {"row_index": idx, "label": label, "depth": 1, "row_type": "detail",
            "parent_id": None, "values": values}


def test_missing_and_extra_rows_detected():
    evaluate = _load_evaluate()
    gt = _doc([_row(0, "A", 1), _row(1, "B", 2), _row(2, "C", 3)])
    pred = _doc([_row(0, "A", 1), _row(1, "B", 2), _row(3, "D", 4)])
    result = evaluate.compare(gt, pred)
    assert result["summary"]["missing_rows"] == [2]
    assert result["summary"]["extra_rows"] == [3]
    assert result["metrics"]["row_detection_precision"] == 2 / 3
    assert result["metrics"]["row_detection_recall"] == 2 / 3


def test_duplicated_rows_detected():
    evaluate = _load_evaluate()
    gt = _doc([_row(0, "A", 1), _row(0, "A2", 1)])
    pred = _doc([_row(0, "A", 1)])
    result = evaluate.compare(gt, pred)
    assert result["summary"]["duplicated_gt_rows"] == [0]
    assert result["summary"]["duplicated_pred_rows"] == []


def test_label_mismatch_recorded():
    evaluate = _load_evaluate()
    gt = _doc([_row(0, "A", 1)])
    pred = _doc([_row(0, "B", 1)])
    result = evaluate.compare(gt, pred)
    assert result["metrics"]["row_label_accuracy"] == 0.0
    assert any(m["field"] == "label" for m in result["mismatches"])


def test_numeric_parse_failure_counted():
    evaluate = _load_evaluate()
    gt = _doc([_row(0, "A", 5)])
    pred = _doc([_row(0, "A", None)])
    pred["rows"][0]["values"]["previous_year"] = {
        "raw": "－", "value": None, "is_negative": False, "parse_status": "dash",
    }
    result = evaluate.compare(gt, pred)
    assert result["summary"]["numeric_parsing_failures"] == 1
    assert result["metrics"]["numeric_accuracy"] == 0.0


def test_missing_row_cells_penalize_cell_metrics():
    # A dropped row must lower cell-level accuracy, not be silently excluded from
    # the denominator.
    evaluate = _load_evaluate()
    gt = _doc([_row(0, "A", 10), _row(1, "B", 20)])
    pred = _doc([_row(0, "A", 10)])  # row 1 dropped entirely

    result = evaluate.compare(gt, pred)

    assert result["summary"]["missing_rows"] == [1]
    # Both ground-truth value cells are counted in the denominator.
    assert result["summary"]["expected_value_cells"] == 2
    assert result["summary"]["exact_matching_cells"] == 1
    assert result["metrics"]["raw_string_accuracy"] == 0.5
    assert result["metrics"]["cell_exact_match_accuracy"] == 0.5
    # The missing numeric cell is a parsing failure.
    assert result["summary"]["numeric_parsing_failures"] == 1
    assert result["metrics"]["numeric_accuracy"] == 0.5
    # A raw mismatch for the missing cell is recorded.
    assert any(
        m["field"] == "raw" and m["row_index"] == 1 and m["predicted"] is None
        for m in result["mismatches"]
    )
