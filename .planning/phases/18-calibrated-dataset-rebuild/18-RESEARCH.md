# Phase 18: Calibrated Dataset Rebuild - Research

**Researched:** 2026-05-18
**Mode:** local codebase research after subagent stream failures

## Phase Requirements

Phase 18 covers DATA-01 and DATA-02:

- DATA-01: build a calibrated v4.2 training dataset by filtering or relabeling v4 examples that violate the saturation policy gate while preserving protocol format and hard-constraint validity.
- DATA-02: produce a reconstruction report with source counts, rejected/relabelled counts, policy-pass rates, hard-constraint pass rates, dataset hashes, and split artifacts.

Success requires a maintainer-facing rebuild path from current v4 Phase 8 data into a v4.2 dataset that later Phase 19 training can consume without changing the final deployment prompt protocol.

## Current Dataset Sources and Formats

Primary source is `data/v4/phase8/labeled_merged.jsonl`. Existing Phase 8 code (`tsc_cycle/v4_gates/dataset_rebuild.py`) treats each row as a dictionary with:

- `sample_id` at row, input, or metadata level.
- `input.prediction.phase_waits[*]` containing `phase_id`, `pred_saturation`, `min_green`, `max_green`, and related fields.
- `result.reasoning` and `result.solution` for assistant construction.
- provenance-like fields such as `source`, `split_hint`, `source_origin`, `lineage`.

Current split artifacts live under `data/v4/phase8/splits/`:

- `train.index.jsonl`
- `val.index.jsonl`
- `ood_val.index.jsonl`
- `manifest.json`
- `v1_ood_alignment.json`

Existing Phase 8 indexes record deterministic provenance and hashes: `sample_id`, `split`, `lineage`, `source_origin`, `source`, `record_hash`, `input_hash`, `solution_hash`, `prompt_hash`, `assistant_hash`, `raw_index`, `seed`, and `is_v1_ood`.

Existing Phase 8 reports live under `artifacts/v4/phase8/`:

- `source_manifest.json`
- `cleaning_report.json`
- `rebuild_report.json`
- `phase8_gate_report.json`

The Phase 8 rebuild uses deterministic ordering by sample id, canonical JSON hashing through `tsc_cycle.hashing`, `build_user_prompt`, and `build_full_assistant`, and avoids writing under the frozen v1 baseline root.

## Hard-Constraint and Protocol Validation Patterns

`tsc_cycle.constraint_lint.validate(prediction_input, output)` is the canonical hard-constraint validator. It verifies phase key set, phase order, integer outputs, min bounds, and max bounds.

`tsc_cycle.prompt_builder.build_user_prompt(input)` and `build_full_assistant(reasoning, solution)` are the canonical protocol builders. The required assistant protocol remains `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>`. Phase 18 should not modify `prompt_builder.py` or expose explicit saturation-band rules in prompt text.

Phase 8 tokenization code already builds prompt + assistant from raw text, rejects native think token leakage, tracks truncation, and writes Arrow files. Phase 18 should reuse that behavior rather than creating a new training data format.

## Phase 17 Reuse

Phase 17 created reusable offline policy helpers:

- `classify_saturation_band`
- `classify_violation`
- `project_dataset_phase_decisions`
- `compute_saturation_audit`
- `evaluate_saturation_policy_gate`

Default Phase 17 thresholds are:

- `sat_lt_0.2_max_green_rate = 0.0`
- `sat_0.2_0.6_max_green_rate = 0.02`
- `sat_0.6_1.0_max_green_rate = 0.10`
- `malformed_row_rate = 0.0`
- `missing_output_rate = 0.0`

Phase 18 should use Phase 17 projection/gate semantics for validation, but calibration decisions should be per sample. If any non-trivial phase in a sample has `final_green == max_green` with `pred_saturation < 1.0`, the source row is a policy-violating row. Forced trivial ranges (`min_green == max_green`) are not repair targets.

## Recommended Implementation Shape

Add a new lightweight module and CLI, likely `tsc_cycle/v4_gates/calibrated_dataset_rebuild.py`, plus tests in `tests/test_v4_phase18_calibrated_dataset_rebuild.py`.

Default outputs should be isolated under v4.2-specific paths:

- `data/v4_2/phase18/labeled_calibrated.jsonl`
- `data/v4_2/phase18/splits/*.index.jsonl`
- `data/v4_2/phase18/tokenized/*.arrow`
- `artifacts/v4_2/phase18/reconstruction_report.json`
- optional policy/audit report under `artifacts/v4_2/phase18/`

The CLI should accept the current v4 merged dataset and split dir as inputs, preserve source row shape, and write calibrated data only under v4.2/phase18 paths. It should reject writes under frozen v1, `data/v4/phase8`, and broad repo/source roots.

Calibration default should be `filter` rather than relabel. Rationale: relabeling numeric phase decisions would require rewriting reasoning text to stay semantically aligned, which risks protocol/provenance drift. Filtering removes violating examples while preserving exact row protocol and hard constraints for retained examples. A `--mode filter` default can leave a future relabel mode explicit, but Phase 18 success can be satisfied by filtering because DATA-01 says filtering or relabeling.

Split reconstruction should preserve deterministic split membership for retained rows where possible by reading Phase 8 split indexes and writing retained sample ids into corresponding v4.2 split indexes. This avoids re-randomizing downstream train/val/OOD semantics and preserves Phase 8 deterministic split lineage. If a sample is filtered out, it disappears from its split; no sample should move splits during Phase 18.

Tokenized Arrow output can reuse Phase 8 helpers by making Phase 18 produce a merged JSONL and then either:

1. call Phase 8 tokenization/split helpers with v4.2 paths, or
2. copy the minimal split/index/tokenization logic needed to keep Phase 18 report semantics explicit.

Prefer minimal reuse of Phase 8 helpers where safe, but do not rebuild from original v1/v3 sources again; Phase 18 source is the current v4 Phase 8 merged dataset plus split indexes.

## Report Requirements

`reconstruction_report.json` should include:

- `ok`, `next_phase_allowed`, `requirements_covered` containing DATA-01 and DATA-02.
- source paths and input hashes.
- `source_counts`: input rows, retained rows, rejected rows, relabelled rows, missing/malformed rows, hard-constraint-invalid rows.
- `policy`: pre-calibration and post-calibration policy gate reports or compact pass-rate summary.
- `hard_constraints`: pass/fail counts and pass rate before/after retained filtering.
- `splits`: counts and split id hashes for train/val/ood_val.
- `dataset_hashes`: calibrated JSONL sha256 plus per-row sample hash digest.
- `representative_rejections`: deterministic examples with sample id, phase id, band, saturation, min/max/final green, split/source, and rejection reason.
- output paths for merged JSONL, split indexes, tokenized files if generated.

## Risks and Defaults

- **Relabeling risk:** changing `result.solution` without rewriting reasoning can create training contradictions. Default to filtering.
- **Denominator hiding risk:** filtering can make post-calibration pass rates green while hiding large rejection volume. Report rejected counts/rates and representative examples.
- **Split drift risk:** rerandomizing splits can invalidate Phase 8/Phase 19 comparisons. Preserve split membership for retained samples.
- **Prompt leakage risk:** keep policy code offline and avoid editing prompt surfaces.
- **Path safety risk:** only write v4.2 Phase 18 outputs; never overwrite Phase 8 v4 data.

## Validation Architecture

Use TDD tests for:

1. Filtering removes low-saturation max-green rows while retaining allowed saturated max-green and forced trivial rows.
2. Retained rows pass `constraint_lint.validate` and prompt/assistant protocol construction.
3. Split indexes preserve existing membership for retained rows and contain deterministic hashes.
4. Reconstruction report includes all DATA-02 fields and post-calibration policy gate is green on retained rows.
5. CLI defaults point to v4 source inputs and v4.2 output paths, with path-safety tests rejecting frozen v1 and Phase 8 output targets.

Run targeted tests after each task:

`/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase18_calibrated_dataset_rebuild.py -q`

Run regression before verification:

`/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase18_calibrated_dataset_rebuild.py tests/test_v4_phase17_saturation_policy.py tests/test_v4_phase8_dataset_rebuild.py -q`
