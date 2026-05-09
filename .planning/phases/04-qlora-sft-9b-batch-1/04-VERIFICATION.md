---
phase: 04-qlora-sft-9b-batch-1
verified: 2026-05-09T00:00:00Z
status: gaps_found
next_phase_allowed: false
---

# Phase 04 Verification

## Verdict

`gaps_found`: Phase 04 implementation is substantially complete, but the phase goal is not complete because no real green dry-run/full-run evidence exists yet. Phase 5 must remain blocked.

## Verified implementation

- Phase 4 SFT contracts and wrappers are implemented for Qwen/Qwen3.5-9B QLoRA.
- Dry-run and full-run wrappers use DGX Spark `run_safe.sh 100G --` pathing and fail-closed preconditions.
- Aggregate SFT report gate fails closed when evidence is missing and keeps `next_phase_allowed=false` without a green full run.
- Code review findings CR-01 through CR-07 and WR-01 are marked fixed in `04-REVIEW.md`.

## Validation run

- `./.venv/bin/python -m pytest tests/test_v3_sft_config.py tests/test_v3_sft_arrow_loader.py tests/test_v3_sft_dry_run.py tests/test_v3_sft_grad_gate.py tests/test_v3_sft_frozen.py tests/test_v3_sft_artifacts.py -q`
  - Result: 38 passed
- `bash -n scripts/run_v3_phase4_dry_run.sh scripts/run_v3_phase4_full.sh`
  - Result: passed

## Remaining blockers

1. No real 500-sample green dry-run report has been produced.
2. No real full-run convergence manifest, adapter handoff, or Phase 4 aggregate report exists.
3. v1.0 FROZEN evidence will be created/validated by wrappers, but current filesystem evidence is not yet green outside a run.

## Next required action

Run a green dry-run first. Only after the user explicitly approves the long training run should `scripts/run_v3_phase4_full.sh "$RUN_ROOT"` be launched. Phase 5 must not begin until a green full-run manifest and aggregate report set `next_phase_allowed=true`.
