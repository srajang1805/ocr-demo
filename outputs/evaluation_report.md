# Evaluation report

- Ground truth: `data\ground_truth.json`
- Predicted:    `outputs\output.json`

## Summary

| Metric | Value |
|---|---|
| Expected rows | 43 |
| Predicted rows | 43 |
| Matched rows (by row index) | 43 |
| Label-exact rows | 43 |
| Missing rows | 0 |
| Extra rows | 0 |
| Expected value cells | 74 |
| Exact matching cells (raw) | 74 |
| Numeric parsing failures | 0 |
| Structural mismatches | 0 |
| Arithmetic validation warnings | 12 |

## Metrics

| Metric | Value |
|---|---|
| Row-label accuracy | 100.00% |
| Raw-string accuracy | 100.00% |
| Normalized numeric accuracy | 100.00% |
| Cell exact-match accuracy | 100.00% |
| Row detection precision | 100.00% |
| Row detection recall | 100.00% |
| Row detection F1 | 100.00% |
| Depth accuracy | 100.00% |
| Parent-child accuracy | 100.00% |
| Row-type accuracy | 100.00% |
| Ordering accuracy | 100.00% |
| Column-set match | True |

## Mismatches

None.

## Arithmetic validation

Arithmetic checks are diagnostics: displayed totals may differ from the sum of displayed components due to rounding or reporting conventions. They do not rewrite extracted values.

| row_index | label | column | check | expected | actual | diff |
|---|---|---|---|---|---|---|
| 12 | 流動資産合計 | previous_year | mismatch | 5863681 | 5863684 | 3 |
| 29 | 有形固定資産合計 | previous_year | mismatch | 1429093 | 1429094 | 1 |
| 33 | 無形固定資産合計 | previous_year | mismatch | 44260 | 44261 | 1 |
| 40 | 投資その他の資産合計 | previous_year | mismatch | 197068 | 197069 | 1 |
| 41 | 固定資産合計 | previous_year | mismatch | 1670421 | 1670426 | 5 |
| 42 | 資産合計 | previous_year | mismatch | 7534102 | 7534110 | 8 |
| 12 | 流動資産合計 | current_year | mismatch | 3377405 | 3377407 | 2 |
| 29 | 有形固定資産合計 | current_year | mismatch | 1352607 | 1352610 | 3 |
| 33 | 無形固定資産合計 | current_year | mismatch | 35868 | 35869 | 1 |
| 40 | 投資その他の資産合計 | current_year | mismatch | 369361 | 369362 | 1 |
| 41 | 固定資産合計 | current_year | mismatch | 1757836 | 1757841 | 5 |
| 42 | 資産合計 | current_year | mismatch | 5135241 | 5135249 | 8 |
