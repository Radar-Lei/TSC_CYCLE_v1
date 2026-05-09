# Dataset Card

**Tokenizer:** Qwen/Qwen3-4B-Thinking-2507  
**max_length:** 1164 (p99=1100, buffer=64, cap=4096)

## Splits
| split | n | trivial |
|---|---|---|
| train | 2433 | 0 |
| val_id | 267 | 0 |
| val_ood | 300 | 0 |

## Token length distribution (full sequence)
min=751 p50=901 p90=972 p99=1100 max=1249

## Phase count distribution per split
- train: 3->518, 4->1548, 5->367
- val_id: 3->64, 4->167, 5->36
- val_ood: 2->22, 3->58, 4->129, 5->42, 6->20, 7->10, 8->19

## v4.0 Phase 8 — 4B dataset rebuild

This section is the DATA4B-05 human-auditable provenance record for the v4.0 Phase 8 Qwen3-4B dataset rebuild. Runtime gates and training inputs are derived from generated artifacts, not from hand-authored counts.

### Scope and model

| Field | Value |
|---|---|
| Training tokenizer/model | `Qwen/Qwen3-4B-Thinking-2507` |
| Split seed | `42` |
| Split ratio | `80/10/10` |
| Max sequence length used by Phase 8 rebuild | `2048` |
| Tokenized artifact directory | `data/v4/phase8/tokenized` |

### Source artifacts

| Artifact | Path | SHA256 |
|---|---|---|
| v4 source manifest | `artifacts/v4/phase8/source_manifest.json` | `ddd30b83034e57a96ba0b053150ccd0a7a8b6c7a07f7756e6d4402af426baac5` |
| cleaning report | `artifacts/v4/phase8/cleaning_report.json` | `7984e2a34d7bfd266a288901e69d34af34b56b0ef906d63e6b8b5fe2a5569a80` |
| split manifest | `data/v4/phase8/splits/manifest.json` | `1be9f885dba7f939a0b4cdb1bffe57d9b5ee973a02e2c9c7889da2449ab80ce0` |
| rebuild report | `artifacts/v4/phase8/rebuild_report.json` | `af2b8fe7d0e875f71253d175a374e8a09b53de7f8bc2ed3f42b3d19cc0983b5b` |

### Input sources and source hashes

| Source boundary | Exact path | Rows | SHA256 |
|---|---|---:|---|
| v1 valid labeled source | `/home/samuel/TSC_CYCLE/data/labeled.jsonl` | 3000 | `2214301555f22640e542234abcd9c5f0e3f6982df08c894124af45367ad30809` |
| v3 new lint-pass labeled source | `/home/samuel/TSC_CYCLE/data/v3/phase2/labeled_new.jsonl` | 6501 | `63086e63faf8e203f5ccf771235b3366533aa639297cf2d4fa142c72884cf191` |

Source merge evidence from `artifacts/v4/phase8/source_manifest.json`:

- Deduped v4 source rows: `9501`.
- Duplicate counts: total `0`, v1 duplicate rows `0`, v3 duplicate rows `0`.
- Sample hash digest: `6d31e22788d5b89b0cc57b9f1baf2c3d5c6204ab5e57173c342242399ff80f9b` over `9501` sample hashes.

### Label normalization and native-think safety

Label cleaning evidence from `artifacts/v4/phase8/cleaning_report.json`:

- Malformed `</end_working_out>` close-tag normalization replacements: `6516`.
- Remaining malformed close tags after normalization: `0`.
- Native `<think>` / `</think>` text occurrences after cleaning: `0`.
- Forbidden native-think rows: `[]`.
- Forbidden malformed close rows after normalization: `[]`.

Protocol boundary:

- Allowed reasoning labels are textual custom tags such as `<start_working_out>` and `</end_working_out>`, followed by `<SOLUTION>...</SOLUTION>`.
- Native Qwen `<think>` / `</think>` text is forbidden in training samples.
- Native Qwen think token IDs `[151667, 151668]` are forbidden in tokenized samples and are checked before truncation.

### Split and tokenization evidence

Split evidence from `data/v4/phase8/splits/manifest.json`:

| Split | Rows | Split ID SHA256 |
|---|---:|---|
| train | 7601 | `e1dc2723d8ee41af5247b5cb2e06d476062e05ad2e6e1c5090f8905631ea0b1b` |
| val | 950 | `504fa9b030898a4574afd86a4166a008e018a668e17f41d2c6427f59a22fba95` |
| ood_val | 950 | `bb2f785fa139d7d9044ae73a56d89b1027d87f2d88ecf8dc8e9758ddac49ce5e` |

Split index paths:

- Train index: `/home/samuel/TSC_CYCLE/data/v4/phase8/splits/train.index.jsonl`
- Validation index: `/home/samuel/TSC_CYCLE/data/v4/phase8/splits/val.index.jsonl`
- OOD validation index: `/home/samuel/TSC_CYCLE/data/v4/phase8/splits/ood_val.index.jsonl`

OOD boundary evidence:

- v1 OOD alignment: `all_v1_ood_in_ood_val=true`, `v1_ood_count=0`, `ood_val_v1_ood_count=0`, sample ID digest `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
- v3 extended OOD selected count: `950`.

Tokenization and truncation evidence from `artifacts/v4/phase8/rebuild_report.json`:

- Tokenized output paths:
  - train: `/home/samuel/TSC_CYCLE/data/v4/phase8/tokenized/train.arrow`
  - val: `/home/samuel/TSC_CYCLE/data/v4/phase8/tokenized/val.arrow`
  - ood_val: `/home/samuel/TSC_CYCLE/data/v4/phase8/tokenized/ood_val.arrow`
- Truncation max sequence length: `2048`.
- Truncation over-length count: `0` of `9501` samples.
- Truncation over-length rate: `0.0` with maximum allowed rate `0.05`.
- Maximum raw tokenized length observed: `1355`.
- Native think token leak failures: `0` sampled failures, gate green.

### v1 / v3 / v4 artifact boundaries

- v1 artifacts are source/reference only for this phase: `/home/samuel/TSC_CYCLE/data/labeled.jsonl` is read as the v1 valid labeled source. Frozen v1 run artifacts under `runs/20260507T032419Z/` remain read-only and are not Phase 8 write targets.
- v3 artifacts are source/reference only for this phase: `/home/samuel/TSC_CYCLE/data/v3/phase2/labeled_new.jsonl` is read as the v3 new lint-pass labeled source. `data/v3/phase2/labeled_merged.jsonl` is not accepted as a single merged source for DATA4B-01.
- v4 Phase 8 writes are isolated to `data/v4/phase8/` and `artifacts/v4/phase8/`, including `data/v4/phase8/labeled_merged.jsonl`, `data/v4/phase8/splits/`, `data/v4/phase8/tokenized/`, and the Phase 8 JSON reports.
