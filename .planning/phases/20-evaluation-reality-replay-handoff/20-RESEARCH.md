---
phase: 20-evaluation-reality-replay-handoff
status: complete
researched: 2026-05-19
requirements: [EVAL-01, EVAL-02, EVAL-03]
---

# Phase 20 Research: Evaluation & Reality Replay Handoff

## Research Question

What does Phase 20 need to plan well so maintainers can decide whether v4.2 is better than v4.0 without rewarding reproduction of bad teacher labels?

## Phase Requirements

- **EVAL-01:** Evaluate the calibrated model with hard-constraint, parse/lint, protocol, and saturation policy gates while demoting or replacing old teacher-MAE as a primary success metric.
- **EVAL-02:** Replay `reality.log` with the calibrated v4.2 q4_K_M GGUF model and generate a new `reality_test.log` that passes parse, lint, protocol, and saturation policy gates.
- **EVAL-03:** Compare v4.0 and v4.2 outputs to confirm low-saturation max-green failures are removed or reduced to the approved threshold without regressing hard-constraint validity.

## Constraints and Existing Decisions

- v4.2 stays on `Qwen/Qwen3-4B-Thinking-2507` and the existing DGX Spark-safe QLoRA/export stack.
- Final deployment system prompt and inference prompt remain unchanged from the v4 protocol.
- The saturation band rule is offline-only: audit, data filtering/relabeling, training validation, and evaluation gates.
- Do not introduce vLLM on this machine.
- Phase 20 depends on the accepted Phase 19 run root: `runs/v4.2-4B-20260518T111519Z`.
- Phase 20 should add v4.2-specific evaluation/replay/handoff gates instead of mutating v4.0 Phase 11/12 defaults.

## Upstream Inputs

### Phase 17 Saturation Policy Gate

- `tsc_cycle/v4_gates/saturation_policy.py` provides saturation band classification, violation classification, and dataset/replay projection helpers.
- `tsc_cycle/v4_gates/phase17_audit.py` provides `evaluate_saturation_policy_gate`.
- Phase 17 established that v4.0 can pass parse/lint/protocol while failing saturation policy. Phase 20 should use this as the key comparison axis.

### Phase 18 Calibrated Dataset

- Source data: `data/v4_2/phase18/labeled_calibrated.jsonl`.
- Split metadata: `data/v4_2/phase18/splits/manifest.json` and split index JSONL files.
- Reconstruction report: `artifacts/v4_2/phase18/reconstruction_report.json`.
- Phase 18 used filter mode and preserved Phase 8 split membership.

### Phase 19 Training and Export

- Canonical run root: `runs/v4.2-4B-20260518T111519Z`.
- Training report: `runs/v4.2-4B-20260518T111519Z/phase19_sft_report.json`.
- Export report: `runs/v4.2-4B-20260518T111519Z/phase19_export_report.json`.
- Replay model: `runs/v4.2-4B-20260518T111519Z/gguf/model.q4_K_M.gguf`.
- Phase 20 should call `tsc_cycle.v4_gates.phase19_export.validate_phase19_export_report` or equivalent handoff validation before accepting replay/eval evidence.

## Existing Code Patterns to Reuse

### Output Parsing and Constraint Lint

- `tsc_cycle.prompt_builder.parse_assistant_output` parses the custom v4 assistant output protocol.
- `tsc_cycle.constraint_lint.validate` validates phase coverage/order, integer seconds, and min/max green constraints.
- Phase 20 should treat parse/lint failures as hard failures.

### Phase 12 Replay and Log Rendering

- `tsc_cycle/v4_gates/phase12_reality_test.py` contains `extract_reality_inputs`, `write_final_log_atomically`, and live replay helpers.
- `tsc_cycle/v4_gates/phase12_log_render.py` contains `lint_phase12_payload`, `ensure_phase12_output_passes`, and `render_reality_test_log`.
- Phase 20 should reuse these patterns but write v4.2-scoped artifacts under `artifacts/v4_2/phase20/` and avoid overwriting v4.0 defaults unless explicitly planned.

### Phase 11 Metrics and Decision Gate

- `tsc_cycle/eval/phase11_metrics.py` contains old teacher-comparison metrics.
- `tsc_cycle/eval/phase11_decision.py` contains old threshold logic that includes teacher-MAE.
- Phase 20 should not use teacher-MAE as a primary gate because the v4.2 dataset intentionally avoids rewarding reproduction of bad teacher labels. Teacher-MAE can remain diagnostic/advisory.

### Phase 19 Fail-Closed Reports

- Phase 19 gates use report fields: `ok`, `next_phase_allowed`, `requirements_covered`, `fatal_failures`, `warnings`, `gates`, and artifact manifests.
- Phase 20 should follow this report shape for evaluation, replay, comparison, and final handoff reports.

## Recommended Architecture

Split Phase 20 into three executable slices:

1. **Evaluation Gate:** Build a v4.2 evaluation/report gate that validates Phase 19 export handoff, runs parse/lint/protocol checks, computes saturation policy failures, and demotes teacher-MAE to advisory.
2. **Reality Replay Gate:** Replay `reality.log` with the v4.2 q4_K_M GGUF through llama.cpp-compatible tooling, generate a v4.2 `reality_test.log`, and validate parse/lint/protocol/saturation policy.
3. **Comparison and Handoff:** Compare v4.0 vs v4.2 policy outcomes, assert low-saturation max-green failures are removed or below threshold without hard-constraint regression, then write an accepted handoff manifest containing HF/GGUF/report/replay paths and hashes.

## Validation Architecture

Phase 20 plans should include automated checks for:

- Phase 19 TRAIN-02 export report validates green before Phase 20 uses artifacts.
- q4_K_M GGUF path exists under `runs/v4.2-4B-20260518T111519Z/gguf/model.q4_K_M.gguf` and hash matches export report.
- Eval/replay outputs parse with `parse_assistant_output`.
- Eval/replay outputs pass `constraint_lint.validate`.
- Outputs do not use native `<think>`/`</think>` tags and preserve custom protocol.
- Saturation policy gate passes on v4.2 eval/replay outputs, especially low-saturation max-green cases.
- v4.0 vs v4.2 comparison report shows no hard-constraint validity regression.
- Teacher-MAE is absent from blocking pass/fail criteria or marked advisory.
- Final handoff report contains reproducible paths and sha256 hashes for training report, export report, q4_K_M GGUF, v4.2 eval report, v4.2 replay log/report, and comparison report.

## Pitfalls

- Do not make teacher-MAE a blocking success metric; it can reward reproducing bad teacher labels.
- Do not change the deployment prompt or inference protocol to include saturation rules.
- Do not overwrite v4.0 Phase 11/12 artifacts as the only evidence; use v4.2-scoped outputs.
- Do not accept self-reported artifact paths/hashes without recomputing on disk.
- Do not accept replay logs that only pass parse/lint while failing saturation policy.
- Do not treat smoke/incomplete replay as accepted EVAL-02 evidence.
- Do not introduce new inference infrastructure requiring vLLM.

## Planner Notes

- Every plan should name the requirement IDs it satisfies.
- Prefer v4.2-specific modules under `tsc_cycle/v4_gates/` and tests in `tests/test_v4_phase20_*.py` or an equivalent focused regression file.
- Keep generated runtime outputs under `artifacts/v4_2/phase20/` and consume Phase 19 artifacts from the canonical run root.
- Include a final verifier-friendly report with `ok: true`, `next_phase_allowed: true`, and `requirements_covered: ["EVAL-01", "EVAL-02", "EVAL-03"]` only after all gates pass.
