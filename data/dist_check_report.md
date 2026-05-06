# Distribution Check Report

Reference: `reality.log`
Same-dist: `data/inputs.jsonl` (10621 samples worth of values per field)
OOD:       `data/ood_inputs.jsonl`

## Same-dist KS test (target: p > 0.05 on every field)

| Field | n_sample | n_ref | KS | p-value | pass |
|---|---|---|---|---|---|
| capacity | 10621 | 1679 | 0.0026 | 1 | ✓ |
| max_green | 10621 | 1679 | 0.0071 | 1 | ✓ |
| min_green | 10621 | 1679 | 0.0051 | 1 | ✓ |
| pred_saturation | 10621 | 1679 | 0.0075 | 1 | ✓ |
| pred_wait | 10621 | 1679 | 0.0081 | 1 | ✓ |

## OOD KS test (target: at least one field with p < 0.01 OR per-sample ood_dims marker)

| Field | n_sample | n_ref | KS | p-value | OOD? |
|---|---|---|---|---|---|
| capacity | 1286 | 1679 | 0.0988 | 1.221e-06 | ✓ |
| max_green | 1286 | 1679 | 0.3221 | 2.509e-67 | ✓ |
| min_green | 1286 | 1679 | 0.3049 | 2.754e-60 | ✓ |
| pred_saturation | 1286 | 1679 | 0.0967 | 2.194e-06 | ✓ |
| pred_wait | 1286 | 1679 | 0.0832 | 7.709e-05 | ✓ |

## OOD per-dimension activation count

| Dimension | Samples |
|---|---|
| wide_range | 77 |
| phase_count | 71 |
| saturation | 69 |
| narrow_range | 63 |
| capacity | 56 |
| wait | 54 |
| range_combo | 54 |
