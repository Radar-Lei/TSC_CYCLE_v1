# Phase 17: Audit & Saturation Policy Gate - Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 3 new/modified files
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tsc_cycle/v4_gates/saturation_policy.py` | utility/service | transform + batch | `tsc_cycle/eval/phase11_metrics.py` + `tsc_cycle/eval/phase11_decision.py` | role-match |
| `tsc_cycle/v4_gates/phase17_audit.py` | CLI/report gate | file-I/O + batch | `tsc_cycle/v4_gates/phase12_report.py` | exact |
| `tests/test_v4_phase17_saturation_policy.py` | test | contract + batch | `tests/test_phase12_reality_log_generation.py` + `tests/test_v4_phase11_eval_matrix.py` | exact |

## Pattern Assignments

### `tsc_cycle/v4_gates/saturation_policy.py` (utility/service, transform + batch)

**Primary analogs:**
- `tsc_cycle/eval/phase11_metrics.py` for JSONL reads, per-row projection, aggregation, and JSON-safe report writing.
- `tsc_cycle/eval/phase11_decision.py` for threshold gates, finite numeric checks, and fail-closed decision payloads.
- `tsc_cycle/constraint_lint.py` for hard-constraint validation and trivial-range handling.

**Imports pattern** (`tsc_cycle/eval/phase11_metrics.py` lines 7-28):
```python
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

from tsc_cycle.eval.metrics_constraints import score_constraint
from tsc_cycle.eval.metrics_mae import score_mae
from tsc_cycle.eval.metrics_reasoning import score_reasoning
from tsc_cycle.eval.phase11_matrix import (
    FROZEN_V1_ROOT,
    PHASE11_OUT_ROOT,
    V1_Q4,
    V4_HF,
    V4_Q4,
    normalize_backend_id,
    reject_frozen_v1_output_path,
)
```

For Phase 17, keep this lightweight/stdlib style, but import only existing lightweight modules such as `tsc_cycle.constraint_lint.validate`, `tsc_cycle.constraint_lint.is_trivial`, and `tsc_cycle.prompt_builder` where needed. Do not import GPU/model stacks.

**JSONL ingestion pattern** (`tsc_cycle/eval/phase11_metrics.py` lines 36-47):
```python
def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"JSONL row is not an object at {path}:{line_no}")
            rows.append(obj)
    return rows
```

Use this directly for `data/v4/phase8/labeled_merged.jsonl`, split index JSONL files, and Phase 12 `per_sample.jsonl` evidence. Fail closed on malformed/non-object rows.

**Aggregation pattern** (`tsc_cycle/eval/phase11_metrics.py` lines 217-260):
```python
def _rate(rows: list[dict[str, Any]], key: str, *, exclude_trivial: bool = False) -> dict[str, Any]:
    denom_rows = [r for r in rows if not (exclude_trivial and r.get("trivial"))]
    if not denom_rows:
        return {"value": float("nan"), "n": 0, "passes": 0}
    passes = sum(1 for r in denom_rows if bool(r.get(key)))
    return {"value": passes / len(denom_rows), "n": len(denom_rows), "passes": passes}


def _mean(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    vals = _finite_values(rows, key)
    if not vals:
        return {"value": float("nan"), "n": 0}
    return {"value": sum(vals) / len(vals), "n": len(vals)}
```

Adapt for Phase 17 band/source/split counters: compute denominator rows explicitly, exclude or separately categorize `min_green == max_green` per-phase rows, and surface `n`/`passes` in every band.

**Report-build pattern** (`tsc_cycle/eval/phase11_metrics.py` lines 311-396):
```python
def compute_phase11_metrics(per_sample_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not per_sample_rows:
        raise ValueError("compute_phase11_metrics requires non-empty per-sample rows")

    slices: dict[str, Any] = {}
    aggregates: dict[str, Any] = {}
    for slice_name in ("v1_comparable_ood", "v4_expanded_ood", "overall_ood"):
        slices[slice_name] = {"backends": {}}
        aggregates[slice_name] = {}
        for backend in BACKENDS:
            sub = _slice_rows(per_sample_rows, backend=backend, slice_name=slice_name)
            if not sub:
                continue
            agg = _aggregate_for(sub)
            slices[slice_name]["backends"][backend] = agg
            aggregates[slice_name][backend] = agg
```

Phase 17 should expose a single canonical `compute_saturation_audit(...)` or similar function that accepts projected phase-decision rows and returns structured `bands`, `sources`, `splits`, `representative_examples`, `excluded_counts`, and `requirements_covered`.

**Threshold/fail-closed pattern** (`tsc_cycle/eval/phase11_decision.py` lines 28-33, 64-83, 177-290):
```python
THRESHOLDS = {
    "v4_q4_hard_constraint_pass_min": 0.98,
    "q4_vs_hf_hard_pass_ratio_min": 0.95,
    "hard_pass_delta_ci_lower_min": -0.01,
    "teacher_mae_delta_ci_upper_max_sec": 0.5,
}


def _finite_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _gate(ok: bool, reason: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": bool(ok), "reason": reason, "data": data or {}}
```

Use the same threshold table + finite check pattern for Phase 17 policy thresholds, e.g. low-saturation max-green rate limits. Any missing/non-finite denominator or threshold input should become a fatal failure, not a silent pass.

**Hard-constraint/trivial pattern** (`tsc_cycle/constraint_lint.py` lines 34-89, 92-95):
```python
def validate(prediction_input: dict[str, Any], output: Any) -> LintResult:
    """Validate output against the input's hard constraints.

    Parameters
    ----------
    prediction_input : dict
        {"prediction": {"phase_waits": [{"phase_id": int, "min_green": int, "max_green": int, ...}, ...]}}
    output : Any
        Should be {"<phase_id>": <int_seconds>, ...}.
    """
    result = LintResult(ok=True)

    if not isinstance(output, dict):
        result.add(Violation.NOT_DICT, got=type(output).__name__)
        return result

    waits = prediction_input.get("prediction", {}).get("phase_waits", [])
    expected_ids = [str(w["phase_id"]) for w in waits]
    ...

def is_trivial(prediction_input: dict[str, Any]) -> bool:
    """Trivial sample: all phases have min_green == max_green (forced single value)."""
    waits = prediction_input.get("prediction", {}).get("phase_waits", [])
    return bool(waits) and all(w["min_green"] == w["max_green"] for w in waits)
```

Before saturation-policy interpretation, validate parsed solutions with `validate(...)`. For per-phase triviality, mirror this concept at row level with `min_green == max_green` and report those rows separately.

---

### `tsc_cycle/v4_gates/phase17_audit.py` (CLI/report gate, file-I/O + batch)

**Primary analog:** `tsc_cycle/v4_gates/phase12_report.py`

**Secondary analog:** `tsc_cycle/v4_gates/phase12_reality_test.py` for Phase 12 manifest/per-sample extraction and output path safety.

**Imports/constants pattern** (`tsc_cycle/v4_gates/phase12_report.py` lines 2-23):
```python
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from tsc_cycle.constraint_lint import validate
from tsc_cycle.prompt_builder import parse_assistant_output
from tsc_cycle.v4_gates.phase12_log_render import DEFAULT_BACKEND_LABEL, render_reality_test_log

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
REALITY_TEST_LOG = PROJECT_ROOT / "reality_test.log"
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4" / "phase12"
REPORT_PATH = ARTIFACT_ROOT / "phase12_report.json"
MANIFEST_PATH = ARTIFACT_ROOT / "manifest.json"
PER_SAMPLE_PATH = ARTIFACT_ROOT / "per_sample.jsonl"
```

For Phase 17, define explicit absolute defaults:
- `DATASET_PATH = PROJECT_ROOT / "data" / "v4" / "phase8" / "labeled_merged.jsonl"`
- `SPLIT_DIR = PROJECT_ROOT / "data" / "v4" / "phase8" / "splits"`
- `PHASE12_MANIFEST_PATH = PROJECT_ROOT / "artifacts" / "v4" / "phase12" / "manifest.json"`
- `PHASE12_PER_SAMPLE_PATH = PROJECT_ROOT / "artifacts" / "v4" / "phase12" / "per_sample.jsonl"`
- `ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4" / "phase17"`
- `AUDIT_REPORT_PATH`, `POLICY_GATE_PATH`, and optional `PROMPT_PROTOCOL_REPORT_PATH` under `ARTIFACT_ROOT`.

**Path safety + JSON write pattern** (`tsc_cycle/v4_gates/phase12_report.py` lines 26-53):
```python
def _is_under(path: Path, root: Path) -> bool:
    candidate = path.expanduser().resolve(strict=False)
    root = root.expanduser().resolve(strict=False)
    return candidate == root or root in candidate.parents


def sha256_file(path: str | Path) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _reject_unsafe_report_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    artifact_root = ARTIFACT_ROOT.resolve(strict=False)
    if candidate == REPORT_PATH.resolve(strict=False) or _is_under(candidate, artifact_root):
        return candidate
    raise ValueError(f"Phase 12 report output path is not allowed: {candidate}")


def _write_json(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    safe_path = _reject_unsafe_report_path(path)
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    safe_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
```

Copy this shape and rename the error text to Phase 17. Keep `allow_nan=False` for policy reports.

**Fail-closed report evaluator pattern** (`tsc_cycle/v4_gates/phase12_report.py` lines 79-206):
```python
def evaluate_phase12_report(
    *,
    records: Iterable[Any],
    outputs: Iterable[dict[str, Any]],
    model_artifact: str | Path,
    model_sha256: str,
    input_sha256: str,
    output_sha256: str,
    out_path: str | Path | None = None,
    dry_run: bool = False,
    manifest_path: str | Path = MANIFEST_PATH,
    per_sample_path: str | Path = PER_SAMPLE_PATH,
    final_log_path: str | Path = REALITY_TEST_LOG,
) -> dict[str, Any]:
    """Evaluate Phase 12 evidence and fail closed on any missing gate."""
    recs = _normalise_records(records)
    outs = list(outputs)
    fatal_failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    ...
    payload = {
        "ok": full_generation_ok,
        "next_phase_allowed": full_generation_ok,
        "dry_run": bool(dry_run),
        "input_count": len(recs),
        "output_count": len(outs),
        "parse_ok_count": parse_ok_count,
        "lint_ok_count": lint_ok_count,
        "protocol_ok_count": protocol_ok_count,
        "timeout_count": timeout_count,
        "model_artifact": str(model_path),
        "model_sha256": str(model_sha256),
        "input_sha256": str(input_sha256),
        "output_sha256": str(output_sha256),
        "fatal_failures": fatal_failures,
        "warnings": warnings,
        "reports": {
            "manifest": str(manifest_path),
            "per_sample": str(per_sample_path),
            "final_log": str(final_log_path),
            "reality_test_log": str(final_log_path),
            "gate_report": str(out_path) if out_path is not None else str(REPORT_PATH),
        },
        "requirements_covered": list(REQUIREMENTS_COVERED),
    }
    _write_json(Path(out_path) if out_path is not None else None, payload)
    return payload
```

Phase 17 should return the same top-level shape: `ok`, `next_phase_allowed`, `requirements_covered`, `gates`, `fatal_failures`, `warnings`, `reports`, and counts. Add Phase 17-specific sections for dataset audit, replay audit, saturation policy thresholds, and prompt protocol guard.

**CLI pattern** (`tsc_cycle/v4_gates/phase12_report.py` lines 209-252):
```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Phase 12 reality replay gate evidence")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--per-sample", type=Path, default=PER_SAMPLE_PATH)
    parser.add_argument("--reality-test-log", type=Path, default=REALITY_TEST_LOG)
    parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    parser.add_argument("--out", type=Path, default=REPORT_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest.exists() else {}
    outputs = _load_jsonl(args.per_sample)
    records = manifest.get("records") or []
    report = evaluate_phase12_report(...)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report.get("ok") is True else 1
```

Copy the `build_parser()` + `main()` + nonzero-on-red pattern. Phase 17 parser should expose dataset path, split dir, Phase 12 manifest/per-sample paths, artifact root, out paths, threshold overrides, and representative example limit.

**Phase 12 structured evidence pattern** (`tsc_cycle/v4_gates/phase12_reality_test.py` lines 107-130, 176-214):
```python
def extract_reality_inputs(log_path: str | Path = REALITY_LOG) -> list[dict[str, Any]]:
    text = Path(log_path).read_text(encoding="utf-8")
    records: list[dict[str, Any]] = []
    for header_match, block in _iter_log_blocks(text):
        if header_match.group("type") != "prompt":
            continue
        header = _prompt_header(header_match)
        for match in INPUT_FRAME_RE.finditer(block):
            payload_text = match.group("payload").strip()
            payload = json.loads(payload_text)
            if not isinstance(payload, dict):
                raise ValueError("framed reality input JSON must be an object")
            sample_id = f"reality-{len(records) + 1:04d}"
            ...
            records.append(asdict(record))
    return records
```

Prefer Phase 12 `manifest.json` records + `per_sample.jsonl` outputs for replay audit. Only use `extract_reality_inputs()` when Phase 12 structured evidence is absent or explicitly requested.

---

### `tests/test_v4_phase17_saturation_policy.py` (test, contract + batch)

**Primary analogs:**
- `tests/test_phase12_reality_log_generation.py` for lazy imports, path-safety tests, report fail-closed assertions, and parser default checks.
- `tests/test_v4_phase11_eval_matrix.py` for threshold/finiteness tests.
- `tests/test_v4_phase8_dataset_rebuild.py` for JSONL fixtures, source/split assertions, and gate report assertions.

**Lazy import / no heavy stack pattern** (`tests/test_phase12_reality_log_generation.py` lines 22-45):
```python
FORBIDDEN_COLLECTION_IMPORTS = {"torch", "transformers", "peft", "bitsandbytes", "vllm", "flash_attn"}


@pytest.fixture(autouse=True)
def _phase12_modules_are_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 12 contracts must never load model/GPU stacks during test execution."""
    real_import = importlib.import_module

    def guarded_import(name: str, package: str | None = None):
        root = name.split(".", 1)[0]
        if root in FORBIDDEN_COLLECTION_IMPORTS:
            raise AssertionError(f"Phase 12 contract imported heavyweight dependency during test execution: {name}")
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", guarded_import)


def _phase12_reality_contract():
    return importlib.import_module("tsc_cycle.v4_gates.phase12_reality_test")
```

Copy for Phase 17 with `_phase17_policy_contract()` and `_phase17_audit_contract()` lazy imports. Add AST source check as in Phase 12/11 tests.

**Fixture helper pattern** (`tests/test_phase12_reality_log_generation.py` lines 95-129):
```python
def _record(sample_id: str = "reality-0001") -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "crossing_id": "1",
        "timestamp": "2026-04-27 00:02:27",
        "input_sha256": "input-hash-1",
        "input": {
            "prediction": {
                "as_of": "2026-04-27 00:02:27",
                "phase_waits": [
                    {"phase_id": 1, "pred_wait": 0.4, "pred_saturation": 0.0083, "min_green": 50, "max_green": 80, "capacity": 48},
                    {"phase_id": 2, "pred_wait": 1.0, "pred_saturation": 0.025, "min_green": 20, "max_green": 45, "capacity": 40},
                ],
            }
        },
    }
```

Use small in-test records to cover all saturation band boundaries and representative example fields.

**Report fail-closed assertion pattern** (`tests/test_phase12_reality_log_generation.py` lines 274-335):
```python
passing = mod.evaluate_phase12_report(**base_kwargs)
assert passing["ok"] is True
assert passing["next_phase_allowed"] is True
assert passing["input_count"] == 1
assert passing["parse_ok_count"] == 1
assert passing["lint_ok_count"] == 1

failing_cases = {
    "parse_error": {...},
    "lint_false": {...},
    "wrong_input_count": {...},
    "missing_artifact_hash": {...},
}
for name, kwargs in failing_cases.items():
    report = mod.evaluate_phase12_report(**kwargs)
    assert report["ok"] is False, name
    assert report["next_phase_allowed"] is False, name
    assert report["fatal_failures"], name
```

Copy this table-driven style for threshold excess, missing dataset, malformed JSONL, missing replay outputs, hard-constraint failures, non-finite saturation, and prompt leakage.

**Threshold boundary/fail-closed pattern** (`tests/test_v4_phase11_eval_matrix.py` lines 258-286):
```python
def test_phase11_decision_gate_thresholds_are_locked_and_fail_closed() -> None:
    mod = _phase11_decision_contract()

    passing = mod.evaluate_phase11_decision(_gate_metrics())
    assert passing["verdict"] == "GO"
    assert passing["ok"] is True
    assert passing["thresholds"] == {
        "v4_q4_hard_constraint_pass_min": 0.98,
        "q4_vs_hf_hard_pass_ratio_min": 0.95,
        "hard_pass_delta_ci_lower_min": -0.01,
        "teacher_mae_delta_ci_upper_max_sec": 0.5,
    }

    failing_cases = {
        "hard_pass": _gate_metrics(hard_pass=0.9799),
        "q4_vs_hf_ratio": _gate_metrics(q4_vs_hf_ratio=0.9499),
        "nan_denominator": _gate_metrics(q4_vs_hf_ratio=float("nan")),
    }
    for name, metrics in failing_cases.items():
        decision = mod.evaluate_phase11_decision(metrics)
        assert decision["ok"] is False, name
        assert decision["next_phase_allowed"] is False, name
        assert decision["fatal_failures"], name
```

Add explicit Phase 17 classifier boundary tests for `0.1999`, `0.2`, `0.5999`, `0.6`, `0.9999`, and `1.0`, plus threshold failure cases.

**JSONL fixture helpers** (`tests/test_v4_phase8_dataset_rebuild.py` lines 43-63, 74-115):
```python
def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
    return path
```

Use these helpers to build tiny dataset JSONL, split index JSONL, Phase 12 manifest, and per-sample JSONL fixtures under `tmp_path`.

**Parser defaults pattern** (`tests/test_phase12_reality_log_generation.py` lines 471-484):
```python
def test_build_parsers_expose_phase12_defaults() -> None:
    reality_mod = _phase12_reality_contract()
    report_mod = _phase12_report_contract()

    reality_args = reality_mod.build_parser().parse_args([])
    report_args = report_mod.build_parser().parse_args([])

    assert Path(reality_args.reality_log) == REALITY_LOG
    assert Path(reality_args.out_log) == REALITY_TEST_LOG
    assert Path(reality_args.artifact_root) == PHASE12_ARTIFACT_ROOT
    assert Path(reality_args.gguf_path) == APPROVED_Q4_MODEL
    assert Path(report_args.reality_test_log) == REALITY_TEST_LOG
    assert Path(report_args.artifact_root) == PHASE12_ARTIFACT_ROOT
```

Add a Phase 17 parser default test asserting all defaults point to `data/v4/phase8`, `artifacts/v4/phase12`, and `artifacts/v4/phase17`, not frozen v1 or arbitrary temp paths.

**Gate report assertion pattern** (`tests/test_v4_phase8_dataset_rebuild.py` lines 510-563):
```python
report = evaluate_phase8_report(**paths, out_path=tmp_path / V4_ARTIFACTS_DIR / "phase8_gate_report.json")

assert report["ok"] is True
assert report["next_phase_allowed"] is True
assert report["requirements_covered"] == ["DATA4B-01", "DATA4B-02", "DATA4B-03", "DATA4B-04", "DATA4B-05"]
assert report["gates"]["phase7_next_phase_allowed"]["ok"] is True
assert report["gates"]["source_manifest"]["ok"] is True
...
```

For Phase 17, assert coverage includes `AUDIT-01`, `AUDIT-02`, `POLICY-01`, `POLICY-02`, and `POLICY-03`; assert red gates populate `fatal_failures` and set `next_phase_allowed` false.

## Shared Patterns

### Authentication / Authorization

Not applicable. Phase 17 is an offline local CLI/report gate with no HTTP/session surface.

### Path Safety

**Source:** `tsc_cycle/v4_gates/phase12_report.py` lines 26-53 and `tsc_cycle/v4_gates/phase12_reality_test.py` lines 78-87.
**Apply to:** `phase17_audit.py` report writers and any JSON/JSONL artifact output.

```python
def _is_under(path: Path, root: Path) -> bool:
    candidate = path.expanduser().resolve(strict=False)
    root = root.expanduser().resolve(strict=False)
    return candidate == root or root in candidate.parents


def _reject_unsafe_report_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    artifact_root = ARTIFACT_ROOT.resolve(strict=False)
    if candidate == REPORT_PATH.resolve(strict=False) or _is_under(candidate, artifact_root):
        return candidate
    raise ValueError(f"Phase 12 report output path is not allowed: {candidate}")
```

Phase 17 should allow only `artifacts/v4/phase17/*` outputs and reject frozen v1 roots/unrelated paths.

### Error Handling / Fail-Closed Reports

**Source:** `tsc_cycle/v4_gates/phase12_report.py` lines 96-106, 127-134, 180-206; `tsc_cycle/eval/phase11_decision.py` lines 234-253.
**Apply to:** saturation policy evaluator, audit wrapper, CLI exit codes, and tests.

```python
fatal_failures: list[dict[str, str]] = []
warnings: list[dict[str, str]] = []
...
if len(recs) != len(outs):
    fatal_failures.append({"gate": "output_count", "reason": f"input/output count mismatch: {len(recs)} != {len(outs)}"})
...
payload = {
    "ok": full_generation_ok,
    "next_phase_allowed": full_generation_ok,
    "fatal_failures": fatal_failures,
    "warnings": warnings,
    "requirements_covered": list(REQUIREMENTS_COVERED),
}
```

### Prompt Protocol Preservation

**Source:** `tsc_cycle/prompt_builder.py` lines 41-82 and 100-122.
**Apply to:** `tests/test_v4_phase17_saturation_policy.py` POLICY-03 tests and `phase17_audit.py` prompt protocol report.

```python
SYSTEM_PROMPT = "你是交通信号配时优化专家。"

USER_TEMPLATE = """{system}
【cycle_predict_input_json】{input_json}【/cycle_predict_input_json】
...
决策提示（非硬约束）：
- 最终决策以 pred_saturation 为主，capacity 仅供参考。
...
"""


def build_user_prompt(prediction_input: dict[str, Any]) -> str:
    input_json = json.dumps(prediction_input, indent=2, ensure_ascii=False)
    return USER_TEMPLATE.format(system=SYSTEM_PROMPT, input_json=input_json)
```

Tests should verify no explicit saturation band strings such as `sat < 0.2`, `0.2 <= sat < 0.6`, `0.6 <= sat < 1.0`, or `sat >= 1.0` appear in deployment prompts.

### Hard Constraint First, Policy Second

**Source:** `tsc_cycle/constraint_lint.py` lines 34-89.
**Apply to:** dataset and replay per-phase projection before policy classification.

```python
lint = validate(record["input"], solution)
if lint.ok:
    lint_ok_count += 1
```

Do not count invalid/unparseable outputs as policy successes. Report parse/lint exclusions and fail closed when required evidence cannot be interpreted.

### Human-Inspectable Examples

**Source:** `tests/test_phase12_reality_log_generation.py` lines 95-129 and Phase 12 output records lines 176-214.
**Apply to:** representative violation rows from dataset and replay.

Each example should include at least: `origin_artifact`, `sample_id`, `phase_id`, `pred_saturation`, `saturation_band`, `min_green`, `max_green`, `final_green`, `split`, `source`, and `violation_category`.

## No Analog Found

No target file lacks an analog. The closest analogs are role/data-flow matches from existing v4 gate, Phase 11 eval, Phase 12 replay, and pytest contract patterns.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| none | — | — | All Phase 17 targets have close existing v4 analogs. |

## Metadata

**Analog search scope:** `tsc_cycle/v4_gates/*.py`, `tsc_cycle/eval/phase11_*.py`, `tsc_cycle/prompt_builder.py`, `tsc_cycle/constraint_lint.py`, `tests/test_phase12_reality_log_generation.py`, `tests/test_v4_phase11_eval_matrix.py`, `tests/test_v4_phase8_dataset_rebuild.py`
**Files scanned:** 10 primary analog files plus project context/research files
**Project skill directories:** `.claude/` exists but has no `skills/`; `.agents/` not present
**Pattern extraction date:** 2026-05-18
