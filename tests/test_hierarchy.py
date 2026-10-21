"""Tests for hierarchy assignment (Stage D)."""
from table_parser.hierarchy import build_rows, classify_row_type
from table_parser.layout_extractor import RawRow
from table_parser.models import ColumnSpec
from table_parser.normalizer import normalize_value


def test_classify_row_type():
    assert classify_row_type("資産の部", False, 0) == "section"
    assert classify_row_type("流動資産", False, 1) == "subsection"
    assert classify_row_type("現金及び預金", True, 2) == "detail"
    assert classify_row_type("流動資産合計", True, 2) == "subtotal"
    assert classify_row_type("資産合計", True, 1) == "total"
    assert classify_row_type("減価償却累計額", True, 4) == "depreciation"
    assert classify_row_type("建物及び構築物（純額）", True, 4) == "net"


def _make_raw_rows():
    # Replicates a shallow subset of the balance-sheet hierarchy.
    rows = [
        RawRow(page=1, y=150, label="資産の部", label_x0=62.3, cells={}),
        RawRow(page=1, y=162, label="流動資産", label_x0=75.2, cells={}),
        RawRow(page=1, y=174, label="現金及び預金", label_x0=88.2, cells={"previous_year": "2,002,429", "current_year": "608,281"}),
        RawRow(page=1, y=186, label="流動資産合計", label_x0=88.2, cells={"previous_year": "5,863,684", "current_year": "3,377,407"}),
    ]
    return rows


def _normalized(rows, columns):
    norm = {}
    for idx, r in enumerate(rows):
        for cid, raw in r.cells.items():
            norm[(idx, cid)] = normalize_value(raw)
    return norm


def test_build_rows_assigns_depth_parent_and_order():
    columns = [ColumnSpec("previous_year"), ColumnSpec("current_year")]
    raw_rows = _make_raw_rows()
    norm = _normalized(raw_rows, columns)
    rows = build_rows(raw_rows, columns, norm)

    assert [r.row_index for r in rows] == [0, 1, 2, 3]
    assert [r.id for r in rows] == ["row_0", "row_1", "row_2", "row_3"]

    assert rows[0].depth == 0
    assert rows[0].parent_id is None
    assert rows[1].depth == 1
    assert rows[1].parent_id == "row_0"
    assert rows[1].parent_label == "資産の部"
    assert rows[2].depth == 2
    assert rows[2].parent_id == "row_1"
    assert rows[3].depth == 2
    assert rows[3].parent_id == "row_1"

    assert rows[0].row_type == "section"
    assert rows[1].row_type == "subsection"
    assert rows[2].row_type == "detail"
    assert rows[3].row_type == "subtotal"


def test_repeated_labels_use_positional_parent_reference():
    # Two rows with the same label "その他" under different parents must still
    # reference their parents unambiguously by row id, not by label string.
    raw_rows = [
        RawRow(page=1, y=150, label="資産の部", label_x0=62.3, cells={}),
        RawRow(page=1, y=162, label="流動資産", label_x0=75.2, cells={}),
        RawRow(page=1, y=174, label="その他", label_x0=88.2, cells={"previous_year": "1", "current_year": "2"}),
        RawRow(page=1, y=186, label="固定資産", label_x0=75.2, cells={}),
        RawRow(page=1, y=198, label="その他", label_x0=101.3, cells={"previous_year": "3", "current_year": "4"}),
    ]
    columns = [ColumnSpec("previous_year"), ColumnSpec("current_year")]
    norm = _normalized(raw_rows, columns)
    rows = build_rows(raw_rows, columns, norm)

    assert rows[2].label == "その他"
    assert rows[2].parent_id == "row_1"
    assert rows[4].label == "その他"
    assert rows[4].parent_id == "row_3"
