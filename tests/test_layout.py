"""Tests for layout reconstruction (Stage B)."""
from table_parser.layout_extractor import (
    _assign_column,
    _cluster_1d,
    _detect_columns,
    _group_rows,
    _looks_numeric,
    build_raw_table,
)
from table_parser.pdf_loader import PdfPage, Word


def _w(x0, y0, x1, y1, text, page=1):
    return Word(x0, y0, x1, y1, text, page)


def test_looks_numeric():
    assert _looks_numeric("2,002,429") is True
    assert _looks_numeric("△2,979") is True
    assert _looks_numeric("－") is True
    assert _looks_numeric("現金及び預金") is False
    assert _looks_numeric("") is False


def test_cluster_1d_groups_by_tolerance():
    clusters = _cluster_1d([1.0, 2.0, 20.0, 21.0, 22.0], tol=5.0)
    assert clusters == [[1.0, 2.0], [20.0, 21.0, 22.0]]


def test_detect_columns_finds_two_right_aligned_columns():
    words = [
        _w(356, 174, 397, 184, "2,002,429"),
        _w(490, 174, 522, 184, "608,281"),
        _w(356, 186, 397, 196, "2,019,476"),
        _w(490, 186, 522, 196, "884,339"),
    ]
    cols = _detect_columns(words)
    assert len(cols) == 2
    # Columns are sorted left-to-right by right edge.
    assert cols[0].right_edge < cols[1].right_edge
    assert abs(cols[0].right_edge - 397.5) < 1.0
    assert abs(cols[1].right_edge - 522.6) < 1.0


def test_assign_column_uses_nearest_right_edge():
    cols = _detect_columns(
        [
            _w(356, 174, 397, 184, "2,002,429"),
            _w(490, 174, 522, 184, "608,281"),
        ]
    )
    assert _assign_column(397.4, cols) == 0
    assert _assign_column(522.4, cols) == 1


def test_group_rows_by_y_center():
    words = [
        _w(88, 174, 142, 184, "現金及び預金"),
        _w(356, 174, 397, 184, "2,002,429"),
        _w(490, 174, 522, 184, "608,281"),
        _w(88, 186, 115, 196, "売掛金"),
        _w(356, 186, 397, 196, "2,019,476"),
        _w(490, 186, 522, 196, "884,339"),
    ]
    groups = _group_rows(words)
    assert len(groups) == 2
    assert [len(g) for g in groups] == [3, 3]


def _synthetic_page():
    header_text = (
        "（単位：千円）\n前連結会計年度\n(2025 年３月31 日)\n"
        "当連結会計年度\n(2026 年３月31 日)\n"
    )
    words = [
        _w(50, 100, 120, 110, "（単位：千円）"),
        _w(300, 100, 370, 110, "前連結会計年度"),
        _w(430, 100, 500, 110, "当連結会計年度"),
        _w(300, 112, 320, 122, "(2025"),
        _w(322, 112, 360, 122, "年３月31"),
        _w(363, 112, 376, 122, "日)"),
        _w(430, 112, 445, 122, "(2026"),
        _w(447, 112, 485, 122, "年３月31"),
        _w(488, 112, 501, 122, "日)"),
        # body
        _w(62, 150, 98, 160, "資産の部"),
        _w(75, 162, 111, 172, "流動資産"),
        _w(88, 174, 142, 184, "現金及び預金"),
        _w(356, 174, 397, 184, "2,002,429"),
        _w(490, 174, 522, 184, "608,281"),
        _w(88, 186, 115, 196, "売掛金"),
        _w(356, 186, 397, 196, "2,019,476"),
        _w(490, 186, 522, 196, "884,339"),
        _w(88, 198, 142, 208, "流動資産合計"),
        _w(356, 198, 397, 208, "5,863,684"),
        _w(481, 198, 522, 208, "3,377,407"),
    ]
    return PdfPage(number=1, width=595, height=842, text=header_text, words=words)


def test_build_raw_table_reconstructs_two_columns_and_rows():
    raw = build_raw_table([_synthetic_page()], "test.pdf")
    assert [c.id for c in raw.columns] == ["previous_year", "current_year"]
    assert raw.columns[0].date == "2025-03-31"
    assert raw.columns[1].date == "2026-03-31"
    assert raw.unit == "千円"

    labels = [r.label for r in raw.rows]
    assert labels == ["資産の部", "流動資産", "現金及び預金", "売掛金", "流動資産合計"]

    cash = raw.rows[2]
    assert cash.cells["previous_year"] == "2,002,429"
    assert cash.cells["current_year"] == "608,281"

    total = raw.rows[4]
    assert total.cells["previous_year"] == "5,863,684"
    assert total.cells["current_year"] == "3,377,407"


def test_build_raw_table_detects_columns_on_later_page():
    # A title/cover page with no numeric tokens must not prevent table detection on
    # a subsequent page.
    title_page = PdfPage(number=1, width=595, height=842, text="表紙", words=[_w(100, 100, 200, 110, "表紙")])
    body_page = _synthetic_page()
    body_page.number = 2

    raw = build_raw_table([title_page, body_page], "test.pdf")

    labels = [r.label for r in raw.rows]
    assert labels == ["資産の部", "流動資産", "現金及び預金", "売掛金", "流動資産合計"]
    assert raw.rows[2].cells["previous_year"] == "2,002,429"
    assert all(r.page == 2 for r in raw.rows)
