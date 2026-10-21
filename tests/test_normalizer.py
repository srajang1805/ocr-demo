"""Tests for the monetary-value normalizer."""
from table_parser.normalizer import (
    DASH_GLYPHS,
    is_dash,
    normalize_text,
    normalize_value,
)


def test_positive_integer_with_commas():
    v = normalize_value("2,002,429")
    assert v.value == 2002429
    assert v.parse_status == "parsed"
    assert v.is_negative is False
    assert v.raw == "2,002,429"


def test_negative_triangle_marker():
    v = normalize_value("△2,979")
    assert v.value == -2979
    assert v.is_negative is True
    assert v.parse_status == "parsed"
    assert v.raw == "△2,979"


def test_negative_zero_preserves_marker_but_normalizes_to_zero():
    v = normalize_value("△0")
    assert v.value == 0
    assert v.is_negative is True
    assert v.parse_status == "parsed"
    assert v.raw == "△0"


def test_dash_placeholder_is_not_zero():
    v = normalize_value("－")
    assert v.value is None
    assert v.parse_status == "dash"
    assert v.is_negative is False
    assert v.raw == "－"


def test_all_dash_glyphs_recognized():
    for glyph in DASH_GLYPHS:
        assert is_dash(glyph)
        assert normalize_value(glyph).parse_status == "dash"


def test_ascii_minus_negative():
    v = normalize_value("-1,234")
    assert v.value == -1234
    assert v.is_negative is True
    assert v.parse_status == "parsed"


def test_fullwidth_digits_and_comma():
    v = normalize_value("１２３，４５６")
    assert v.value == 123456
    assert v.parse_status == "parsed"


def test_empty_and_none_do_not_crash():
    assert normalize_value(None).parse_status == "empty"
    assert normalize_value("").parse_status == "empty"
    assert normalize_value("   ").parse_status == "empty"


def test_unparseable_value():
    v = normalize_value("abc")
    assert v.value is None
    assert v.parse_status == "unparsed"


def test_whitespace_inside_number_is_ignored():
    v = normalize_value(" 1,234 ")
    assert v.value == 1234
    assert v.parse_status == "parsed"


def test_normalize_text_collapses_whitespace_preserves_japanese():
    assert normalize_text("  現金 及び  預金 ") == "現金 及び 預金"
    assert normalize_text("流動資産") == "流動資産"
    assert normalize_text(None) == ""
