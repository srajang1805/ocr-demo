# Document Intelligence Table Parser

A reproducible, coordinate-based table extraction system for **Japanese financial
statements**. Given a one-page PDF (a consolidated balance sheet, 連結貸借対照表), it
reconstructs the table into structured JSON and flat CSV, preserving Japanese labels,
monetary notation (`△` negatives, `－` dash placeholders, thousands separators),
column headers, row hierarchy, and source row order.

The current baseline is a lightweight, fully local pipeline: it requires **no API keys
or paid services** to run, and no OCR/VLM fallback is claimed (see *Limitations*).

---

## 1. Problem statement

Japanese financial tables encode information in ways that defeat naive text extraction:

- **Two value columns** (previous fiscal year / current fiscal year) that must not be
  shifted between columns.
- **Negative amounts** marked with `△` (e.g. `△2,979` = −2,979).
- **Dash placeholders** `－` meaning "no balance" — *not* zero.
- **Indentation-based hierarchy** (`資産の部` → `流動資産` → detail rows), including
  repeated labels such as `その他` and `減価償却累計額`.
- **Subtotals and grand totals** whose displayed value can differ from the sum of the
  displayed components by a few units of the reporting unit (rounding / reporting
  conventions).

The goal is a *measurably correct* reconstruction — row labels, raw strings, numeric
values, structure — with an honest evaluation against independent ground truth.

---

## 2. Architecture and design decisions

```
document-table-parser/
├── README.md
├── requirements.txt
├── .gitignore
├── data/
│   ├── balance_sheet_after_correction.pdf   # input
│   └── ground_truth.json                    # independent, manual annotation
├── src/table_parser/
│   ├── pdf_loader.py        # Stage A: PyMuPDF words + bboxes + rendering
│   ├── layout_extractor.py  # Stage B: rows/columns from coordinates
│   ├── normalizer.py        # Stage C: monetary value normalization
│   ├── hierarchy.py         # Stage D: depth / parent / row type
│   ├── validator.py         # arithmetic consistency diagnostics
│   ├── extractor_interface.py  # model-independent TableExtractor ABC
│   ├── models.py            # shared dataclasses
│   └── pipeline.py          # orchestration + default CoordinateExtractor
├── scripts/
│   ├── run_parser.py        # one-command extraction -> output.json / output.csv
│   └── evaluate.py          # one-command evaluation -> evaluation.json / .md
├── tests/
│   ├── test_normalizer.py
│   ├── test_layout.py
│   ├── test_hierarchy.py
│   └── test_end_to_end.py
└── outputs/                 # generated (JSON, CSV, evaluation)
```

**Stages**

1. **A — Ingestion** (`pdf_loader.py`): PyMuPDF opens the PDF and extracts per-word
   bounding boxes plus page text. Multi-page is supported in the data model even though
   the sample has one page.
2. **B — Layout** (`layout_extractor.py`): value columns are discovered by clustering
   the right edges of numeric tokens (rather than assuming a fixed column count or
   spacing); rows are discovered by clustering word y-centers; labels (left) are
   separated from values (right) by the leftmost value column.
3. **C — Normalization** (`normalizer.py`): each cell stores `raw`, `value`,
   `is_negative`, `parse_status` (`parsed` / `dash` / `empty` / `unparsed`). Dash is
   *not* collapsed to zero.
4. **D — Hierarchy** (`hierarchy.py`): depth from indentation (label x-position
   clustering), parent from the nearest preceding shallower row, row type from the
   label pattern. Parents are referenced by stable row id (`row_N`), so repeated labels
   remain unambiguous.
5. **Validation** (`validator.py`): arithmetic checks on every `合計` row (diagnostic
   only — never rewrites values).

**Design decisions**

- **Coordinates over spaces**: row/column reconstruction never relies on the number of
  spaces in extracted text.
- **Two representations**: source-faithful `raw` strings are always kept alongside
  normalized numeric `value`s.
- **No silent corrections**: a dash stays a dash; an unparseable cell is reported, not
  guessed.
- **Model-independent interface**: `TableExtractor` (in `extractor_interface.py`)
  isolates the extraction engine so an OCR/VLM engine can be dropped in without
  rewriting normalization or evaluation. The shipped engine is `CoordinateExtractor`.

---

## 3. Installation

Python 3.9+ is required. The only runtime dependency is `pymupdf`; `pytest` is needed
for tests.

```bash
pip install -r requirements.txt
```

> On this Windows environment Python is invoked as `py` (the Windows launcher);
> `python` and `py` are interchangeable below.

---

## 4. One-command extraction

From the project root (`document-table-parser/`):

```bash
python scripts/run_parser.py
```

Defaults: input `data/balance_sheet_after_correction.pdf`, output dir `outputs/`.
This writes `outputs/output.json` and `outputs/output.csv`.

```bash
# explicit paths
python scripts/run_parser.py --input data/balance_sheet_after_correction.pdf --output-dir outputs
```

---

## 5. One-command evaluation

```bash
python scripts/evaluate.py
```

Defaults: ground truth `data/ground_truth.json`, predicted `outputs/output.json`.
Writes `outputs/evaluation.json` and `outputs/evaluation_report.md`.

---

## 6. Tests

```bash
python -m pytest
```

Covers: comma integers, `△2,979` → −2979, `△0` preservation, `－` dash, whitespace and
Japanese labels, two-column reconstruction, row order, parent-child hierarchy, empty /
unparseable cells, duplicated / missing rows, determinism, and a full end-to-end check
against the PDF and ground truth.

---

## 7. Input / output schema

### Input

A PDF with selectable text. `data/balance_sheet_after_correction.pdf`.

### `output.json`

```jsonc
{
  "document": {
    "source_file": "balance_sheet_after_correction.pdf",
    "document_type": "consolidated_balance_sheet",
    "language": "ja",
    "unit": "千円",
    "page_count": 1,
    "pages": [1],
    "columns": [
      {"id": "previous_year", "label": "前連結会計年度", "date": "2025-03-31"},
      {"id": "current_year",  "label": "当連結会計年度", "date": "2026-03-31"}
    ]
  },
  "rows": [
    {
      "id": "row_2",
      "row_index": 2,
      "label": "現金及び預金",
      "label_en": null,            // optional English annotation (currently null)
      "depth": 2,
      "row_type": "detail",
      "parent_id": "row_1",        // stable positional reference
      "parent_label": "流動資産",   // human-readable, not used for matching
      "source": {"page": 1, "y": 172.27, "x0": 88.2},
      "values": {
        "previous_year": {"raw": "2,002,429", "value": 2002429, "is_negative": false, "parse_status": "parsed"},
        "current_year":  {"raw": "608,281",   "value": 608281,  "is_negative": false, "parse_status": "parsed"}
      }
    }
  ],
  "warnings": [ /* arithmetic diagnostics */ ]
}
```

`row_type` values: `section`, `subsection`, `detail`, `subtotal`, `total`,
`depreciation`, `net`.

### `output.csv`

Flat UTF-8 (with BOM) table with columns:

```
row_id, row_index, parent_id, depth, row_type, label,
previous_year_raw, current_year_raw, previous_year_value, current_year_value
```

Both `_raw` (source-faithful) and `_value` (normalized integer) are kept for every
column. Cells with no balance are empty; dash placeholders keep `－` in the `_raw`
column and empty in the `_value` column.

**Opening the CSV in a spreadsheet**: the file is UTF-8 with BOM, so Excel / Google
Sheets / LibreOffice open it directly with correct Japanese. Do *not* rely on an
"Import" wizard that guesses CP1252; if your tool misreads it, re-import specifying
UTF-8 encoding. Note that `_raw` values like `2,002,429` are CSV-quoted because they
contain the thousands-separator comma — this is expected and correct; use the `_value`
columns for numeric computation.

---

## 8. Metrics and their definitions

Ground-truth and predicted rows are matched **by `row_index`** (positional, stable).
Let `C` = matched rows, `G` = ground-truth rows, `P` = predicted rows.

- **Row detection** (precision/recall/F1): `precision = |C|/|P|`, `recall = |C|/|G|`.
- **Row-label accuracy**: fraction of `C` with an exact `label` match.
- **Raw-string accuracy**: over every *value cell* (ground-truth `parse_status !=
  "empty"`, i.e. `raw` is not null), the fraction whose predicted `raw` equals the
  ground-truth `raw` exactly. Cells whose row is missing from the prediction are
  included in the denominator and count as a mismatch (predicted value absent).
- **Normalized numeric accuracy**: over every ground-truth cell with `parse_status ==
  "parsed"`, the fraction where the prediction is also `parsed` *and* has the same
  `value`. A missing row's parsed cell counts as a parsing failure.
- **Cell exact-match accuracy**: over every value cell, the fraction where `raw`,
  `value`, `is_negative`, and `parse_status` all match.
- **Depth accuracy** / **parent-child accuracy** / **row-type accuracy**: fraction of
  `C` whose `depth` / `parent_id` / `row_type` match exactly.
- **Ordering accuracy**: 1.0 iff the predicted `row_index` sequence equals the
  ground-truth sequence (row order preserved).
- **Arithmetic checks** (diagnostic): each `合計` row is compared to the sum of its
  section's net leaves; a non-zero `diff` is reported as a warning and never changes an
  extracted value.

**How anomalies are scored** (no silent exclusions):

- *Missing / extra rows* reduce row detection precision/recall, are listed
  explicitly, and the value cells of a missing row are counted against the cell-level
  metrics — nothing is silently dropped from a denominator.
- *Duplicated rows* (same `row_index` twice in either file) are detected and reported;
  the matcher keeps the last occurrence.
- *Unparsed cells* (`parse_status != "parsed"` where the ground truth is `parsed`) are
  counted as numeric parsing failures and lower numeric accuracy.
- *Dash vs zero* are distinct: a dash has `value: null` and is never compared against
  a numeric zero.

---

## 9. Actual measured results

Input: `balance_sheet_after_correction.pdf` (1 page, 43 rows, 74 value cells).

| Metric | Result |
|---|---|
| Expected / predicted rows | 43 / 43 |
| Label-exact rows | 43 |
| Missing / extra rows | 0 / 0 |
| Expected value cells | 74 |
| Exact matching cells (raw) | 74 |
| Numeric parsing failures | 0 |
| Structural mismatches | 0 |
| Row-label accuracy | 100.00% |
| Raw-string accuracy | 100.00% |
| Normalized numeric accuracy | 100.00% |
| Cell exact-match accuracy | 100.00% |
| Row detection P / R / F1 | 100.00% each |
| Depth / parent-child / row-type / ordering accuracy | 100.00% each |
| Arithmetic validation warnings | 12 (diagnostic only) |

All 29 automated tests pass. The pipeline is deterministic (repeated runs produce
identical output).

**Arithmetic note (important):** the 12 warnings are *not* extraction errors. For
example, `流動資産合計` (previous year) is printed as `5,863,684` while the sum of the
listed detail rows is `5,863,681` (diff 3); `資産合計` differs from the sum of its
components by 8. These small, systematic offsets are an inherent property of the source
document (rounding / reporting convention) and are reproduced verbatim rather than
"corrected". See the arithmetic table in `outputs/evaluation_report.md`.

---

## 10. Known limitations and failure cases

- **Single digital sample.** This is validated on one digitally generated, selectable
  PDF. It does **not** demonstrate generalization to arbitrary or scanned documents.
- **Scanned / image-only PDFs.** The coordinate extractor requires embedded text. A
  scanned page needs an OCR or vision-language model (see *Next steps*); no such backend
  is implemented or claimed here.
- **Fixed table shape assumptions.** Column detection assumes right-aligned numeric
  columns and a left label region. It is robust to the number of columns but assumes a
  single label cell per row and single-line labels.
- **Wrapped / merged labels** spanning multiple lines or vertical merges are not
  handled and would likely be split into separate rows.
- **Repeated label resolution** relies on positional parent references (`parent_id`),
  which is correct here but assumes a linear reading order.
- **Arithmetic offsets** in the source (see above) are reported, not resolved; they are
  a property of the data, not the extractor.
- **Column-name mapping** (`previous_year`/`current_year`) is inferred from the
  `前/当` prefix in header labels; unusual column headers would fall back to `col_0`,
  `col_1`, …
- **No confidence scores.** Uncertain cells are surfaced via `parse_status ==
  "unparsed"` rather than a continuous confidence; a human-review step is not wired in.

---

## 11. Next steps (future work — not implemented)

- Add an **OCR / VLM extractor** behind `TableExtractor` (e.g. a table-recognition
  model or a vision-language model) for scanned pages, and emit per-cell **confidence
  scores** plus a human-review queue for low-confidence cells.
- Build a **larger annotated benchmark** of Japanese financial statements (multiple
  pages, multiple periods, merged cells, wrapped labels) and turn the current metrics
  into a regression suite that blocks regressions.
- Handle **multi-page tables** with repeated headers and section continuation, and
  **merged cells** via line/rule detection (`page.get_drawings()`).
- Extend normalization to more notations (e.g. `(2,979)` accounting negatives, `千`
  / `百万` multipliers) and cross-check arithmetic within tolerances derived from the
  reporting unit.
- Optional English translations as `label_en` annotations (currently `null`).

---

## 12. Reproducibility

```bash
pip install -r requirements.txt   # install deps
python scripts/run_parser.py      # -> outputs/output.json, outputs/output.csv
python scripts/evaluate.py        # -> outputs/evaluation.json, outputs/evaluation_report.md
python -m pytest                  # 29 tests
```

All commands are run from the project root. The ground truth
(`data/ground_truth.json`) is a manual annotation kept separate from the extraction
code, so evaluation is not circular.
