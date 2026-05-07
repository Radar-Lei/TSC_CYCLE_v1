## Summary

- per-sample rows: **1800** (600 samples × 3 backends)
- backends: gguf_bf16, gguf_q4_k_m, hf_bf16
- splits: id, ood
- metrics: constraint_satisfaction, teacher_mae+exact_match, ood_gap, reasoning_tier, latency_p99

## Constraint Satisfaction

Hard-constraint pass rate (trivial samples — `min==max` for all phases — excluded).

| backend | split | lint_ok rate | n (non-trivial) |
|---|---|---|---|
| hf_bf16 | id | 100.0% | 300 |
| hf_bf16 | ood | 99.3% | 300 |
| gguf_bf16 | id | 100.0% | 300 |
| gguf_bf16 | ood | 99.3% | 300 |
| gguf_q4_k_m | id | 100.0% | 300 |
| gguf_q4_k_m | ood | 98.7% | 300 |

### Phase-count buckets (non-trivial, both splits combined)

| backend | phases=2 | phases=3 | phases=4 | phases=5 | phases=6 |
|---|---|---|---|---|---|
| hf_bf16 | 100.0% (n=22) | 99.2% (n=125) | 100.0% (n=318) | 100.0% (n=86) | 100.0% (n=20) |
| gguf_bf16 | 100.0% (n=22) | 99.2% (n=125) | 100.0% (n=318) | 100.0% (n=86) | 100.0% (n=20) |
| gguf_q4_k_m | 100.0% (n=22) | 99.2% (n=125) | 100.0% (n=318) | 100.0% (n=86) | 95.0% (n=20) |

## Teacher MAE

Mean of `abs(int(student_phase) - int(teacher_phase))` averaged per sample, then averaged across samples. Samples with mae=None (unparseable / missing phase) excluded from MAE denominator.

| backend | split | mean MAE (s) | n (mae available) | exact_match rate | n (all) |
|---|---|---|---|---|---|
| hf_bf16 | id | 3.111 | 300 | 4.7% | 300 |
| hf_bf16 | ood | 7.936 | 300 | 12.0% | 300 |
| gguf_bf16 | id | 3.196 | 300 | 5.0% | 300 |
| gguf_bf16 | ood | 7.670 | 300 | 11.3% | 300 |
| gguf_q4_k_m | id | 3.714 | 300 | 4.0% | 300 |
| gguf_q4_k_m | ood | 7.846 | 300 | 13.3% | 300 |

## OOD Gap

`gap = id - ood`. For rate metrics positive gap = OOD degradation; for MAE positive gap = OOD numerically worse (mean MAE higher on OOD → ood>id → gap negative).

| backend | metric | id | ood | gap (id - ood) |
|---|---|---|---|---|
| hf_bf16 | lint_ok | 100.0% | 99.3% | 0.7% |
| hf_bf16 | exact_match | 4.7% | 12.0% | -7.3% |
| hf_bf16 | mae | 3.111 | 7.936 | -4.825 |
| gguf_bf16 | lint_ok | 100.0% | 99.3% | 0.7% |
| gguf_bf16 | exact_match | 5.0% | 11.3% | -6.3% |
| gguf_bf16 | mae | 3.196 | 7.670 | -4.473 |
| gguf_q4_k_m | lint_ok | 100.0% | 98.7% | 1.3% |
| gguf_q4_k_m | exact_match | 4.0% | 13.3% | -9.3% |
| gguf_q4_k_m | mae | 3.714 | 7.846 | -4.132 |

## Reasoning Quality

Rule-based tier from in-reasoning hits (KEYWORDS + min/max integers). 0 → miss · 1-2 → partial · ≥3 → full.

| backend | split | full | partial | miss | n |
|---|---|---|---|---|---|
| hf_bf16 | id | 93.3% | 4.3% | 2.3% | 300 |
| hf_bf16 | ood | 91.3% | 7.0% | 1.7% | 300 |
| gguf_bf16 | id | 94.0% | 3.0% | 3.0% | 300 |
| gguf_bf16 | ood | 91.3% | 6.3% | 2.3% | 300 |
| gguf_q4_k_m | id | 97.3% | 2.0% | 0.7% | 300 |
| gguf_q4_k_m | ood | 95.7% | 4.0% | 0.3% | 300 |

## Latency p99

Per-prompt wall time (seconds). hf_bf16 cache has no `elapsed_sec` field and is reported as N/A.

| backend | n (with elapsed_sec) | mean (s) | p99 (s) |
|---|---|---|---|
| hf_bf16 | 0 | N/A | N/A |
| gguf_bf16 | 600 | 5.294 | 7.636 |
| gguf_q4_k_m | 600 | 2.418 | 3.868 |

## Top-20 Failure Cases

Failure = `lint_ok=False` OR `mae > 5`. Sorted: lint failures first, then by MAE desc.

Total failures: **558** / 1800 rows.

| sample_id | backend | split | violations | mae | exact_match |
|---|---|---|---|---|---|
| `3bfafec87af0` | gguf_q4_k_m | ood | above_max | 39.12 | False |
| `b2ab1142cd24` | hf_bf16 | ood | below_min,below_min | 9.38 | False |
| `b2ab1142cd24` | gguf_bf16 | ood | below_min,below_min | 9.38 | False |
| `b2ab1142cd24` | gguf_q4_k_m | ood | below_min | 9.25 | False |
| `87d4b437e8cd` | gguf_q4_k_m | ood | above_max | 5.67 | False |
| `41a577912fe9` | hf_bf16 | ood | above_max | 0.67 | False |
| `41a577912fe9` | gguf_bf16 | ood | above_max | 0.67 | False |
| `41a577912fe9` | gguf_q4_k_m | ood | above_max | 0.67 | False |
| `7f0aa6b370a0` | gguf_q4_k_m | ood | - | 95.50 | False |
| `b20d2e733d8b` | gguf_q4_k_m | ood | - | 90.50 | False |
| `e6127f2d5bee` | gguf_q4_k_m | ood | - | 74.00 | False |
| `c326e1b87044` | hf_bf16 | ood | - | 60.12 | False |
| `c326e1b87044` | gguf_bf16 | ood | - | 60.12 | False |
| `c326e1b87044` | gguf_q4_k_m | ood | - | 60.12 | False |
| `82543d3843c8` | hf_bf16 | ood | - | 58.67 | False |
| `82543d3843c8` | gguf_bf16 | ood | - | 58.67 | False |
| `3bfafec87af0` | gguf_bf16 | ood | - | 56.12 | False |
| `eec96d95e24e` | gguf_bf16 | ood | - | 56.00 | False |
| `eec96d95e24e` | hf_bf16 | ood | - | 55.80 | False |
| `8c8ee47ed9a2` | gguf_q4_k_m | ood | - | 53.75 | False |

## Quantization Degradation

**Split=id** — gguf_bf16 vs gguf_q4_k_m: lint_ok Δ=0.0% (100.0% → 100.0%); MAE Δ=0.518s (3.196 → 3.714); exact_match Δ=-1.0% (5.0% → 4.0%).
**Split=ood** — gguf_bf16 vs gguf_q4_k_m: lint_ok Δ=-0.7% (99.3% → 98.7%); MAE Δ=0.176s (7.670 → 7.846); exact_match Δ=2.0% (11.3% → 13.3%).

**Verdict:** q4_K_M OOD MAE delta = 0.18s (<3s threshold) → quantization degradation within tolerance; no imatrix re-quantization required.

