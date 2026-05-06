# Phase 6 SUMMARY — Evaluation Suite (script-ready)

**Status:** Script ready; blocked on Phase 5 outputs.

## Implementation
- `tsc_cycle/eval/run_eval.py` — 3 backends × 4 metrics × 2 splits matrix:
  - backends: hf_bf16 (transformers) / gguf_bf16 (llama-cli) / gguf_q4 (llama-cli)
  - metrics:
    - constraint_satisfaction (lint pass rate; phase_count buckets; trivial excluded)
    - teacher_mae / teacher_exact (vs labeled.jsonl gold)
    - reasoning_keyword (rule-based: pred_saturation / min_green / max_green / pred_wait)
    - ood_gap (val_id vs val_ood spread per backend)
  - cache: `gen_cache/{variant}/{sample_id}.json`
  - decision gate: q4 OOD constraint_satisfaction ≥ 0.95 × hf_bf16 OOD constraint_satisfaction
- Outputs: `runs/{ts}/eval/{per_sample.jsonl, report.md, decision.md}`
