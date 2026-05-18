---
phase: 19-4b-qlora-retrain-export
reviewed: "2026-05-18T16:08:15Z"
depth: standard
files_reviewed: 8
files_reviewed_list:
  - tsc_cycle/student/sft_v42.py
  - tsc_cycle/v4_gates/phase19_training.py
  - tsc_cycle/student/train.py
  - scripts/run_v4_phase19_train.sh
  - tsc_cycle/v4_gates/phase19_export.py
  - tsc_cycle/student/export_gguf.py
  - scripts/run_v4_phase19_export.sh
  - tests/test_v4_phase19_training_export.py
findings:
  critical: 6
  warning: 2
  info: 0
  total: 8
status: issues_found
---

# Phase 19: Code Review Report

**Reviewed:** 2026-05-18T16:08:15Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed the Phase 19 v4.2 training/export gates, CLI entrypoints, shell wrappers, and tests. The implementation still has fail-open evidence gates: TRAIN-01 can be satisfied by smoke/incomplete or forged reports, TRAIN-02 can be satisfied by self-reported artifact hashes without actual GGUF files, and export can be driven by an adapter-selected base model instead of the locked Qwen3-4B-Thinking-2507 baseline. Path-safety and import-boundary issues remain.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: BLOCKER — TRAIN-01 gate accepts smoke/dry-run or incomplete training as complete

**File:** `tsc_cycle/v4_gates/phase19_training.py:420-424`, `tsc_cycle/v4_gates/phase19_training.py:542-545`

**Issue:** `write_phase19_training_reports()` marks every non-`full` mode as `completed=True`, and also treats `max_steps == 0` as completed for full mode. `validate_phase19_training_report()` then only trusts the report's `completed` and `ok` booleans and never requires `mode == "full"` or a positive completed training step count. A smoke/dry-run report with minimal forged evidence can therefore unlock TRAIN-01 and the export handoff.

**Fix:** Require full-mode evidence in both report writing and validation; do not grant TRAIN-01 coverage for smoke/dry-run reports.

```python
mode_ok = training.get("mode") == "full"
state = training.get("trainer_state") if isinstance(training.get("trainer_state"), dict) else {}
global_step = int(state.get("global_step") or 0)
max_steps = int(state.get("max_steps") or 0)
completed_ok = (
    mode_ok
    and training.get("completed") is True
    and training.get("ok") is True
    and global_step > 0
    and (max_steps <= 0 or global_step >= max_steps)
)
```

### CR-02: BLOCKER — TRAIN-01 data provenance can be spoofed with arbitrary non-empty hashes

**File:** `tsc_cycle/v4_gates/phase19_training.py:377-386`, `tsc_cycle/v4_gates/phase19_training.py:404-419`, `tsc_cycle/v4_gates/phase19_training.py:517-522`, `tsc_cycle/student/train.py:533`, `tsc_cycle/student/train.py:557-559`

**Issue:** The validator only checks that `phase18_artifact_hashes` contains non-empty keys. It does not recompute the Phase 18 report hash, tokenized Arrow hashes, or verify that `phase19_data_manifest.json` matches those reported values. Separately, `train.py` accepts `--tokenized-dir`, but `write_phase19_training_reports()` always reads the default tokenized manifest via `_tokenized_manifest_hashes()` with no `data_dir` parameter, so the report can describe a different dataset than the one trained on. This allows TRAIN-01 evidence to be spoofed or misbound.

**Fix:** Pass the actual `data_dir` into `write_phase19_training_reports()`, recompute hashes from that directory, and validate the report against the manifest and on-disk artifacts.

```python
def write_phase19_training_reports(..., tokenized_dir: Path, ...):
    tokenized = _tokenized_manifest_hashes(tokenized_dir / "manifest.json")

# validation
manifest = _read_json(data_manifest)
expected = {
    "calibrated_jsonl_sha256": manifest["phase18"]["calibrated_jsonl_sha256"],
    "phase18_report_sha256": manifest["phase18"]["phase18_report_sha256"],
    "train.arrow": manifest["tokenized_sha256"]["train"],
    "val.arrow": manifest["tokenized_sha256"]["val"],
    "ood_val.arrow": manifest["tokenized_sha256"]["ood_val"],
}
if phase18_hashes != expected:
    _fail(failures, "phase18_artifact_hashes", "reported hashes do not match data manifest")
```

### CR-03: BLOCKER — Training report validation accepts adapter/data paths outside the requested v4.2 run root

**File:** `tsc_cycle/v4_gates/phase19_training.py:503-515`

**Issue:** `validate_phase19_training_report()` uses `adapter_path` and `data_manifest_path` directly from the report and only checks their hashes. It never requires those paths to be under the requested v4.2 `run_root` or rejects frozen/v4.0 paths. A report for a new v4.2 run can therefore point at an existing v4.0 or frozen adapter/data manifest and pass if the self-reported hashes match.

**Fix:** Resolve and constrain all report paths before hashing them.

```python
def _require_under_root(path: Path, root: Path, gate: str) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if "v4.0-4B-" in resolved.as_posix() or resolved.name == "20260507T032419Z":
        raise ValueError(f"{gate} points at forbidden prior artifact: {resolved}")
    resolved.relative_to(root_resolved)
    return resolved

adapter = _require_under_root(Path(training.get("adapter_path") or root / "adapter"), root, "adapter_path")
data_manifest = _require_under_root(Path(training.get("data_manifest_path") or root / "phase19_data_manifest.json"), root, "data_manifest_path")
```

### CR-04: BLOCKER — TRAIN-02 export validation trusts self-reported artifact hashes and existence flags

**File:** `tsc_cycle/v4_gates/phase19_export.py:351-363`

**Issue:** `validate_phase19_export_report()` checks only the JSON report's `exists` and `sha256` fields for GGUF and merged HF artifacts. It does not verify that the reported paths exist, are non-empty, or that the hashes match the actual files. A hand-written export report with fake `exists: true` and fake hashes can pass TRAIN-02 without `merged_hf`, `model.fp16.gguf`, or `model.q4_K_M.gguf` existing.

**Fix:** Recompute artifact records from the validated `paths` values and compare them to the report before accepting TRAIN-02.

```python
for key, path_key in (("gguf_fp16", "gguf_fp16"), ("gguf_q4_K_M", "gguf_q4_K_M")):
    actual_record, actual_failures = _artifact_record(Path(paths[path_key]))
    failures.extend(actual_failures)
    reported = artifacts.get(key) if isinstance(artifacts.get(key), dict) else {}
    if reported.get("sha256") != actual_record.get("sha256"):
        failures.append({"gate": "artifact_hash", "reason": f"sha256 mismatch for {key}"})

merged_records, merged_failures = _directory_manifest(Path(paths["merged_hf"]), ("*.safetensors",))
failures.extend(merged_failures)
```

### CR-05: BLOCKER — GGUF export can load an adapter-selected base model instead of the locked v4.2 model

**File:** `tsc_cycle/student/export_gguf.py:43-60`, `tsc_cycle/v4_gates/phase19_training.py:503-506`

**Issue:** `merge_to_fp16()` defaults the base model from `adapter_config.json` (`base_model_name_or_path`) and does not enforce `Qwen/Qwen3-4B-Thinking-2507`. The Phase 19 training validator only checks that `adapter_config.json` exists, not what base model it names. A poisoned or stale adapter config can make Phase 19 export merge against a v4.0, Qwen3.5, local, or otherwise unintended base model while the report still claims v4.2 compliance.

**Fix:** Validate `adapter_config.json` during TRAIN-01 handoff and enforce the same locked base in the export path.

```python
adapter_config = _read_json(adapter / "adapter_config.json")
base_model = adapter_config.get("base_model_name_or_path")
if base_model != MODEL_NAME:
    _fail(failures, "adapter_config", f"adapter base model must be {MODEL_NAME}, got {base_model}")

# in merge_to_fp16 for phase19
model_name = base_model or _base_model_from_adapter_config(adapter_dir)
if model_name != BASE_MODEL:
    raise Phase10ExportError(f"refusing unlocked base model: {model_name}")
```

### CR-06: BLOCKER — Training shell wrapper interpolates RUN_ROOT into an unquoted Python heredoc

**File:** `scripts/run_v4_phase19_train.sh:18-22`

**Issue:** The wrapper expands `$RUN_ROOT` directly inside an unquoted heredoc that becomes Python source: `Path("$RUN_ROOT")`. The preceding shell `case` only checks the prefix pattern and does not reject double quotes, so a crafted argument can break the Python string before `validate_run_root()` ever runs. This is an injection risk in a wrapper intended to enforce path safety.

**Fix:** Pass `RUN_ROOT` via the environment or argv and single-quote the heredoc delimiter so the shell never expands user-controlled text into code.

```bash
RUN_ROOT="$RUN_ROOT" "$PY" - <<'PY'
import os
from pathlib import Path
from tsc_cycle.student.sft_v42 import check_phase18_handoff, validate_run_root
root = validate_run_root(Path(os.environ["RUN_ROOT"]))
phase18 = check_phase18_handoff(Path("artifacts/v4_2/phase18/reconstruction_report.json"))
if phase18.get("ok") is not True or phase18.get("next_phase_allowed") is not True:
    raise SystemExit("Phase 18 handoff is not green")
PY
```

## Warnings

### WR-01: WARNING — `sft_v42` imports heavy test/runtime dependencies at module import time

**File:** `tsc_cycle/student/sft_v42.py:10-11`

**Issue:** `sft_v42` imports `TrainerCallback`, `_TrainingArgumentsEvidence`, `_load_json_rows`, and `load_arrow_split` from `sft_v4`. Importing `sft_v4` imports `datasets` and `transformers` at module import time. This makes lightweight gate/tests that only need constants or path validation depend on the full training stack, undermining the stated heavy-dependency isolation.

**Fix:** Move shared pure helpers (`_TrainingArgumentsEvidence`, `_load_json_rows`, `MODEL_COLUMNS`) into a lightweight module, and lazy-import `load_arrow_split`/`TrainerCallback` only where training actually needs them.

### WR-02: WARNING — Malformed `solution` values crash tokenization instead of producing a controlled red report

**File:** `tsc_cycle/v4_gates/phase19_training.py:90-95`

**Issue:** `_record_solution()` casts every solution value with `int(val)` without handling `TypeError` or `ValueError`. A malformed Phase 18 row therefore aborts the tokenization command with a traceback instead of returning a fail-closed tokenization report with a specific fatal failure.

**Fix:** Catch conversion failures and surface them as row-level tokenization failures.

```python
def _record_solution(record: dict[str, Any]) -> dict[str, int]:
    value = _record_result(record).get("solution", {})
    if not isinstance(value, dict):
        raise ValueError("solution must be an object")
    try:
        return {str(key): int(val) for key, val in value.items()}
    except (TypeError, ValueError) as exc:
        raise ValueError(f"solution contains non-integer value: {exc}") from exc
```

---

_Reviewed: 2026-05-18T16:08:15Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
