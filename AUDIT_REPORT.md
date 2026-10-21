# Audit Report — Document Intelligence Table Parser

This report documents an independent audit of the existing coordinate-based parser for
Japanese financial statements, the fixes applied, and the verified results. It is
written to be read skeptically: the reported 100% accuracy on the sample is real but
narrowly scoped.

---

## 1. What was audited

- All source modules under `src/table_parser/` (`pdf_loader`, `layout_extractor`,
  `normalizer`, `hierarchy`, `validator`, `models`, `extractor_interface`, `pipeline`).
- `scripts/run_parser.py` and `scripts/evaluate.py`.
- All tests under `tests/`.
- `data/ground_truth.json`, `README.md`, and the generated
  `outputs/{output.json, output.csv, evaluation.json, evaluation_report.md}`.

The ground truth was re-verified **independently of the parser** by extracting the raw
PDF words with a separate, throwaway script and comparing every label (43/43) and every
value (74/74) directly against the annotation. All matched; the ground truth is a
faithful, independent transcription of the rendered PDF, not a copy of parser output.

---

## 2. Verified sample metrics

Re-run after the fixes described below (input `data/balance_sheet_after_correction.pdf`):

| Metric | Result |
|---|---|
| Expected / predicted rows | 43 / 43 |
| Matched rows | 43 |
| Label-exact rows | 43 |
| Missing / extra / duplicated rows | 0 / 0 / 0 |
| Expected value cells | 74 |
| Exact matching cells (raw) | 74 |
| Numeric parsing failures | 0 |
| Structural mismatches | 0 |
| Row-label accuracy | 100.00% |
| Raw-string accuracy | 100.00% |
| Normalized numeric accuracy | 100.00% |
| Cell exact-match accuracy | 100.00% |
| Row detection precision / recall / F1 | 100.00% each |
| Depth / parent-child / row-type / ordering accuracy | 100.00% each |

These numbers are genuine (they were re-computed, not copied), but they hold only for
this single, digitally generated, single-panel balance sheet. They do **not**
generalize to other document formats.

The 12 arithmetic warnings are **not** extraction errors: the source document's printed
subtotals differ from the sum of its printed components by 1–8 thousand yen (e.g.
`資産合計` = 7,534,110 vs component-sum 7,534,102). These are reproduced verbatim and
reported as diagnostics, never "corrected".

---

## 3. Discovered flaws

### 3.1 [HIGH] Evaluator silently excluded missing rows from cell metrics — FIXED

`scripts/evaluate.py::compare` iterated only over rows matched by `row_index`
(`common`). If the parser dropped a row entirely, that row's value cells were excluded
from the `raw_cells` denominator, so `raw_string_accuracy`, `cell_exact_match_accuracy`,
and `numeric_accuracy` could stay at 100% even though real cells were missing. Missing
rows were only penalized by row-detection recall, which is a coarse signal.

**Fix:** cell-level accounting now runs over *all* ground-truth value cells. A value
cell whose row is absent from the prediction counts as a raw-string mismatch and (where
the ground truth is numeric) a numeric parsing failure. Regression test
`test_missing_row_cells_penalize_cell_metrics` locks this in. Sample metrics are
unchanged (there are no missing rows), so this is a pure robustness fix.

### 3.2 [MEDIUM] Column detection only ran on the first page — FIXED

`layout_extractor.build_raw_table` detected value columns once, on page 1, and then
`continue`d past any page with no columns. If page 1 was a title/cover page with no
numeric tokens, `columns` became an empty list (never `None` again) and **every** page
was skipped, producing zero rows. The inner `if columns is None: columns = []` was dead
code (`_detect_columns` never returns `None`).

**Fix:** columns are now (re-)detected on the first page that actually contains numeric
value tokens, then reused for subsequent pages. Regression test
`test_build_raw_table_detects_columns_on_later_page` covers the title-page-first case.

### 3.3 [LOW] `structural_mismatches` and summary row counts — FIXED

- `structural_mismatches` counted only depth and parent mismatches, omitting row-type
  mismatches (even though `row_type_accuracy` was reported separately).
- `summary.expected_rows` / `predicted_rows` used the *deduplicated* index-set size, so
  a document with a duplicated row would under-report the true emitted row count.

**Fix:** `structural_mismatches` now includes row-type mismatches; the summary reports
actual list lengths while precision/recall still use distinct indices (documented).

### 3.4 [INFO] Positional row matching can cascade-misalign after a mid-table drop

Matching is by `row_index` only. Dropping a *middle* row shifts every subsequent
predicted `row_index` by one, producing a run of label mismatches plus a spurious
"missing last row". This is honest (accuracy drops) but the `missing_rows` list then
points at the wrong index. Not fixed — a content-based sequence alignment would be a
larger change with no benefit for the single-document sample. Documented here.

### 3.5 [INFO] `ordering_accuracy` is weak for this parser

Because `row_index` *is* the source order, `ordering_accuracy` is trivially satisfied by
construction for the coordinate parser. It is retained for interface-compatibility with
alternative extractors (which might reorder), but it does not detect reordering of this
specific parser.

---

## 4. Changes made

| File | Change |
|---|---|
| `scripts/evaluate.py` | Cell metrics now include missing-row cells; `structural_mismatches` includes row-type; summary counts report actual lengths. |
| `src/table_parser/layout_extractor.py` | Column detection retried on the first page containing numeric tokens (fixes multi-page). |
| `tests/test_evaluate.py` | Added `test_missing_row_cells_penalize_cell_metrics`. |
| `tests/test_layout.py` | Added `test_build_raw_table_detects_columns_on_later_page`. |
| `README.md` | Updated metric definitions, anomaly-scoring notes, limitations, and test count. |

No extracted values, ground-truth values, or column assignments were changed to make
totals reconcile. The ground truth was **not** modified (no verified error was found).

---

## 5. Automated test results

```
$ python -m pytest
29 passed in ~1.3s
```

Covered: normalization (commas, `△` negatives, `△0`, dash, full-width digits),
layout (two-column reconstruction, column detection, row grouping), hierarchy
(depth/parent/row-type, repeated labels), evaluation (missing/extra/duplicated rows,
parse failures, missing-row cell penalties), and end-to-end (matches ground truth,
determinism, dash/negative-zero preservation).

---

## 6. OCR / VLM extension assessment

- The deterministic `CoordinateExtractor` remains the baseline.
- A clean, model-independent interface (`TableExtractor`) already exists; an OCR/VLM
  engine can be added behind it without touching normalization or evaluation.
- **Not implemented, and deliberately so.** No OCR library (`pytesseract`, `easyocr`,
  `torch`) is installed, no Tesseract binary is on PATH, and no VLM credentials are
  available. Installing a Japanese-capable OCR stack would be a large, rushed change.
  No OCR/VLM results, benchmark comparisons, or confidence scores are claimed.

---

## 7. Reproducibility and code-quality checks

- Dependencies are minimal: `pymupdf` (runtime) + `pytest` (dev).
- Paths are configurable via `--input`, `--output-dir`, `--ground-truth`, `--output`;
  defaults work from the project root. Windows/Linux path handling uses `pathlib`.
- Japanese text survives JSON (UTF-8, `ensure_ascii=False`) and CSV (UTF-8 **with BOM**)
  round trips.
- Repeated runs are deterministic (asserted by `test_end_to_end_is_deterministic`).
- Errors surface via non-zero exit codes and stderr messages; extraction failures are
  not swallowed.
- No credentials, caches, virtualenvs, or build artifacts are committed
  (`.gitignore` covers `__pycache__`, `.pytest_cache`, venvs). Note: `.pytest_cache/`
  and `__pycache__/` currently exist on disk from running the tests but are ignored.

---

## 8. Remaining limitations

1. Validated on **one** document; no evidence of generalization to other formats.
2. Requires **selectable text** (no OCR). Scanned PDFs are unsupported.
3. Assumes a single-panel table with a left label column and horizontal single-word
   section headers (see README §10, "Fixed table shape assumptions").
4. Wrapped/multi-line labels and merged cells are not handled.
5. No confidence scores or human-review hook.
6. Positional row matching (see §3.4) and a weak `ordering_accuracy` (§3.5).
7. Arithmetic discrepancies in the source are reported, not reconciled.

---

## 9. Implemented vs future work

**Implemented (verified):** coordinate ingestion, right-edge column clustering,
y-center row clustering, Japanese monetary normalization (`△`/`－`/commas/full-width),
indentation hierarchy with positional parent IDs, arithmetic diagnostics, an
independent ground truth, JSON/CSV outputs, a multi-metric evaluator, and 29 passing
tests including an end-to-end check.

**Future work (not implemented):** OCR/VLM extraction, scanned-page support, a larger
multi-document annotated benchmark, broader layout support (multi-panel, vertical
text), merged-cell and wrapped-label handling, per-cell confidence scores, and English
`label_en` annotations.
