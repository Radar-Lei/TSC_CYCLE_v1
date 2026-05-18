# Phase 19: 4B QLoRA Retrain & Export - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Maintainer can retrain the latest `Qwen/Qwen3-4B-Thinking-2507` student on the calibrated v4.2 dataset using the existing DGX Spark-safe QLoRA stack, then export reproducible merged HF, GGUF fp16, and GGUF q4_K_M artifacts with hashes and reports.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, Phase 18 outputs, requirements, and codebase conventions to guide decisions.

### Fixed Scope
- Reuse the existing DGX Spark-safe QLoRA path; do not introduce a new base model or training framework.
- Stay on `Qwen/Qwen3-4B-Thinking-2507`.
- Consume Phase 18 calibrated dataset artifacts under `data/v4_2/phase18/`.
- Preserve v4 prompt/protocol behavior; do not alter deployment prompt surfaces.
- Export merged HF plus GGUF fp16 and q4_K_M artifacts with reproducible paths, hashes, and reports.

</decisions>

<code_context>
## Existing Code Insights

Primary analogs and likely implementation targets:

- `tsc_cycle/student/sft_v4.py` — existing v4 QLoRA/SFT training stack.
- `scripts/run_v4_phase9_train.sh` and `scripts/run_v4_phase9_smoke.sh` — existing Phase 9 launch wrappers.
- `tsc_cycle/v4_gates/phase9_smoke.py` and `tsc_cycle/v4_gates/phase9_report.py` — existing training smoke/report gates.
- `tsc_cycle/v4_gates/phase10_export.py`, `phase10_report.py`, `phase10_tokenizer_parity.py` — existing export/report/parity gates.
- `scripts/run_v4_phase10_export.sh`, `run_v4_phase10_smoke.sh`, `run_v4_phase10_tokenizer_parity.sh` — existing export wrappers.
- Existing v4.0 run artifacts live under `runs/v4.0-4B-20260509T184844Z/` and provide report/output shape references.

Phase 18 verified artifacts available for Phase 19:

- `data/v4_2/phase18/labeled_calibrated.jsonl` — 4532 retained rows.
- `data/v4_2/phase18/splits/manifest.json` — train 3500, val 452, ood_val 580.
- `data/v4_2/phase18/splits/*.index.jsonl` — deterministic retained split indexes.
- `artifacts/v4_2/phase18/reconstruction_report.json` — `ok: true`, post policy gate passes, calibrated JSONL sha256 `f60c263571c938c506db3dc919fdbd1528dba4e271764c8de106b4a626be0d00`.

</code_context>

<specifics>
## Specific Ideas

- Create v4.2-specific wrappers/gates rather than modifying v4.0 scripts in place when that reduces risk.
- Prefer dry-run/smoke-testable code paths for planning and validation; full training may be long-running and should have resumable/background launch artifacts.
- Reports must explicitly reference the Phase 18 calibrated dataset, split manifest, prompt/protocol expectations, run path, base model, QLoRA parameters, and export hashes.

</specifics>

<deferred>
## Deferred Ideas

- Evaluation of calibrated model quality belongs to Phase 20.
- Deployment endpoint integration remains out of scope.
- New training frameworks/base models are out of scope.

</deferred>
