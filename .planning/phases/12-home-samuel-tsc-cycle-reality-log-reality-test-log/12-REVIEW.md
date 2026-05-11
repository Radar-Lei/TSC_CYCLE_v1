---
phase: 12-home-samuel-tsc-cycle-reality-log-reality-test-log
reviewed: 2026-05-11T12:57:46Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - tests/test_phase12_reality_log_generation.py
  - tsc_cycle/v4_gates/phase12_reality_test.py
  - tsc_cycle/v4_gates/phase12_report.py
  - scripts/run_phase12_reality_test.sh
findings:
  critical: 6
  warning: 2
  info: 0
  total: 8
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-05-11T12:57:46Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the Phase 12 reality.log replay CLI, report evaluator, shell runner, and contract tests for correctness, path safety, fail-closed behavior, protocol validation, and test reliability. The implementation contains multiple fail-open audit and path-safety defects: hashes are not real SHA-256 values, cached outputs are not bound to current inputs, gate reports trust self-reported per-sample fields, and both final-log/report output paths can be directed outside the Phase 12 allowlist.

## Critical Issues

### CR-01: BLOCKER - Audit hashes are deliberately corrupted

**File:** `tsc_cycle/v4_gates/phase12_reality_test.py:59-63`

**Issue:** `sha256_text()` computes a SHA-256 digest and then rewrites every `999` substring to `998`. This means `input_sha256`, `output_sha256`, and `raw_sha256` are not actual SHA-256 digests and cannot be used to verify audit evidence. It also creates artificial collisions between different real digests after replacement.

**Fix:** Return the digest unchanged and adjust tests so stale-output sentinels are checked only in parsed payload fields, not hash strings.

```python
def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

### CR-02: BLOCKER - Resume cache is keyed only by sample_id and cached lint is trusted

**File:** `tsc_cycle/v4_gates/phase12_reality_test.py:143-145,296-300`

**Issue:** `--resume` loads `gen_cache/reality-XXXX.json` solely by `sample_id`, without checking `input_sha256`, model hash/backend, generation parameters, or whether the cached raw output still satisfies the current input. `_ensure_output_passes()` then trusts `output["lint"]` if present instead of recomputing lint from `raw_text` against the current record. A stale cache from a previous `reality.log` can therefore pass the final gate and be rendered into `reality_test.log` for the wrong input.

**Fix:** Validate cache metadata before reuse, and always recompute parse/lint from `raw_text` and the current `record["input"]` during final gating.

```python
cached = _load_cache(cache_path)
if cached is not None:
    if cached.get("input_sha256") != record["input_sha256"]:
        cached = None
    else:
        _ensure_output_passes(record, cached)  # recomputes lint internally
        outputs.append(cached)
        continue
```

Also change `_ensure_output_passes()` to ignore cached `lint` as authority:

```python
reasoning, solution = parse_assistant_output(raw)
if not reasoning or solution is None:
    raise ValueError(...)
lint_payload = _lint_payload(record["input"], solution)
if lint_payload.get("ok") is not True:
    raise ValueError(...)
```

### CR-03: BLOCKER - `--out-log` path allowlist is bypassable

**File:** `tsc_cycle/v4_gates/phase12_reality_test.py:184-188,359-360`

**Issue:** The CLI only calls `reject_unsafe_phase12_output_path(args.out_log)` when `--out-log` equals the default final log. Any custom output path outside the project, such as `/tmp/reality_test.log`, bypasses production path validation and is written by `write_final_log_atomically()`. The helper also explicitly skips validation for paths outside `PROJECT_ROOT`, creating a data-loss path if the CLI is invoked with an unintended absolute path.

**Fix:** Enforce the Phase 12 allowlist for every production `--out-log`. If tests need temporary paths, add an explicit test-only parameter rather than making the production helper fail open.

```python
# main()
reject_unsafe_phase12_output_path(args.out_log)

# write_final_log_atomically()
out_path = reject_unsafe_phase12_output_path(out_log)
```

### CR-04: BLOCKER - Gate report does not verify the final log or artifact hashes

**File:** `tsc_cycle/v4_gates/phase12_report.py:118-124,146-155`

**Issue:** `evaluate_phase12_report()` only checks that `model_sha256`, `input_sha256`, and `output_sha256` are non-empty strings. It never verifies that `final_log_path` exists, that its actual SHA-256 matches `output_sha256`, or that `model_artifact` exists and matches `model_sha256`. A report can therefore return `ok=True` while `reality_test.log` is missing, stale, or corrupted.

**Fix:** Compute and compare hashes from disk before setting `ok=True`. The generation flow should write the final log first, then emit the final gate report, or produce a separate pre-write report that cannot authorize the next phase.

```python
if not Path(final_log_path).is_file():
    fatal_failures.append({"gate": "final_log", "reason": "missing final reality_test.log"})
elif sha256_file(final_log_path) != output_sha256:
    fatal_failures.append({"gate": "output_sha256", "reason": "final log hash mismatch"})

if not model_path.is_file() or sha256_file(model_path) != model_sha256:
    fatal_failures.append({"gate": "model_sha256", "reason": "model artifact hash mismatch"})
```

### CR-05: BLOCKER - Report evaluator trusts per-sample self-reported parse/lint fields

**File:** `tsc_cycle/v4_gates/phase12_report.py:96-102`

**Issue:** `parse_ok_count` is based on `output["solution"]` and `output["parse_error"]`; `lint_ok_count` is based on `output["lint_ok"]` or `output["lint"]["ok"]`. These fields come from `per_sample.jsonl`, which is exactly the evidence being audited. If a cached or malformed row claims `lint_ok=True` while `raw_text` violates constraints, the report can pass. `protocol_ok_count` parses `raw_text`, but lint is never recomputed against the matching input record.

**Fix:** Treat `raw_text` plus the corresponding `record["input"]` as the source of truth. Parse raw output, validate it with `tsc_cycle.constraint_lint.validate()`, and compare the recomputed solution to any serialized `solution` field only as a consistency check.

```python
from tsc_cycle.constraint_lint import validate

for record, output in zip(recs, outs, strict=False):
    reasoning, solution = parse_assistant_output(str(output.get("raw_text") or ""))
    if reasoning and solution is not None:
        parse_ok_count += 1
        lint = validate(record["input"], solution)
        if lint.ok:
            lint_ok_count += 1
```

### CR-06: BLOCKER - Report writer can overwrite arbitrary paths

**File:** `tsc_cycle/v4_gates/phase12_report.py:29-35,165`

**Issue:** `_write_json()` only rejects paths under the frozen v1 root. The `--out` argument can point to unrelated project files or arbitrary writable paths, and the function will create parent directories and overwrite the target. This violates the Phase 12 path-safety model and can cause data loss.

**Fix:** Reuse the same Phase 12 output allowlist as the generation CLI: allow only `ARTIFACT_ROOT` report paths, the canonical report path, or explicitly approved temporary test paths.

```python
def _reject_unsafe_report_path(path: Path) -> Path:
    candidate = path.expanduser().resolve(strict=False)
    artifact_root = ARTIFACT_ROOT.resolve(strict=False)
    if candidate == REPORT_PATH.resolve(strict=False) or _is_under(candidate, artifact_root):
        return candidate
    raise ValueError(f"Phase 12 report output path is not allowed: {candidate}")
```

## Warnings

### WR-01: WARNING - Reality input extraction is not scoped to prompt blocks

**File:** `tsc_cycle/v4_gates/phase12_reality_test.py:107-112`

**Issue:** `extract_reality_inputs()` scans the entire log for `【cycle_predict_input_json】...【/cycle_predict_input_json】` frames and then attaches the nearest previous prompt header. It does not verify that the frame is actually inside a `type=prompt` block. If a result block echoes or contains a stale framed JSON snippet, it can be ingested as a new Phase 12 input.

**Fix:** Split the log into typed records using `HEADER_RE` and separators, then parse framed JSON only from blocks whose header is `type=prompt`. Reject or ignore frames in result/noise blocks.

### WR-02: WARNING - Heavy-import contract test does not inspect the implementation modules

**File:** `tests/test_phase12_reality_log_generation.py:23-34,129-145`

**Issue:** The test named `test_phase12_contracts_do_not_import_heavy_model_stacks_at_collection` parses the test file itself and monkeypatches `importlib.import_module`, but top-level imports inside the target implementation modules are resolved through Python's normal import machinery. A direct `import torch` in `phase12_reality_test.py` or `phase12_report.py` would not be caught by the AST check and may not be blocked by the monkeypatch.

**Fix:** Parse the target module source files for forbidden imports and/or monkeypatch `builtins.__import__` while importing the Phase 12 modules.

---

_Reviewed: 2026-05-11T12:57:46Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
