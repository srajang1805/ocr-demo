"""Normalization of Japanese financial-accounting monetary values.

Handles:
- thousands separators (commas),
- the negative marker ``△`` (U+25B3) and ``▲`` (U+25B2),
- dash placeholders such as ``－`` (U+FF0D),
- full-width digits (``０``--``９``) and the full-width comma ``、``.

The normalizer never invents or silently corrects a value: a dash is reported as
``parse_status == "dash"`` with ``value is None`` and is *not* collapsed to zero.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Dash glyphs used as "no balance" placeholders in Japanese financial statements.
DASH_GLYPHS = {
    "\uff0d",  # full-width hyphen-minus －
    "\u2014",  # em dash —
    "\u2015",  # horizontal bar ―
    "\u2013",  # en dash –
    "\u2212",  # minus sign −
    "\u002d",  # hyphen-minus -
    "\u30fc",  # prolonged sound mark ー (often used as a dash)
    "\u2500",  # box drawing horizontal ─
}

# Negative markers used in Japanese accounting.
NEGATIVE_MARKERS = {"\u25b3", "\u25b2", "\u25bc"}  # △ ▲ ▽

_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
_FULLWIDTH_COMMA = "\uff0c"  # 、


@dataclass(frozen=True)
class NormalizedValue:
    """A single normalized monetary cell."""

    raw: Optional[str]
    value: Optional[int]
    is_negative: bool
    parse_status: str  # one of "parsed", "dash", "empty", "unparsed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw": self.raw,
            "value": self.value,
            "is_negative": self.is_negative,
            "parse_status": self.parse_status,
        }


def is_dash(text: Optional[str]) -> bool:
    """Return True if *text* is composed solely of dash placeholder glyphs."""
    if text is None:
        return False
    t = text.strip()
    if t == "":
        return False
    return all(ch in DASH_GLYPHS for ch in t)


def normalize_value(raw: Optional[str]) -> NormalizedValue:
    """Normalize a raw cell string into a :class:`NormalizedValue`.

    Rules:
    - ``None`` / empty string -> ``parse_status == "empty"``, ``value is None``.
    - a dash placeholder -> ``parse_status == "dash"``, ``value is None``.
    - a ``△``-prefixed number -> negative, ``value`` negated (``△0`` -> ``0``).
    - commas are thousands separators and are removed before parsing.
    """
    if raw is None:
        return NormalizedValue(None, None, False, "empty")

    t = raw.strip()
    if t == "":
        return NormalizedValue(raw, None, False, "empty")

    if is_dash(t):
        return NormalizedValue(raw, None, False, "dash")

    is_neg = False
    if t[0] in NEGATIVE_MARKERS:
        is_neg = True
        t = t[1:]
    elif t[0] in ("-", "\u2212"):
        is_neg = True
        t = t[1:]

    # Normalize full-width digits and the full-width comma, drop separators.
    t = t.translate(_FULLWIDTH_DIGITS)
    t = t.replace(_FULLWIDTH_COMMA, ",").replace(",", "")

    if t == "":
        return NormalizedValue(raw, None, is_neg, "unparsed")

    try:
        value = int(t)
    except ValueError:
        return NormalizedValue(raw, None, is_neg, "unparsed")

    if is_neg:
        value = -abs(value)
    return NormalizedValue(raw, value, is_neg, "parsed")


def normalize_text(text: Optional[str]) -> str:
    """Collapse runs of whitespace but otherwise preserve the original string."""
    if text is None:
        return ""
    return " ".join(text.split())
