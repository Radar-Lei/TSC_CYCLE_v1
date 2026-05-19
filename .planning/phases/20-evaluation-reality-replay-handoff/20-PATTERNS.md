# Phase 20: Evaluation & Reality Replay Handoff - Pattern Map

**Mapped:** 2026-05-19
**Files analyzed:** 8 planned new/modified files
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tsc_cycle/v4_gates/phase20_eval.py` | service/gate | batch, transform, file-I/O | `tsc_cycle/eval/phase11_metrics.py` + `tsc_cycle/v4_gates/phase17_audit.py` | role-match |
| `tsc_cycle/v4_gates/phase20_reality_test.py` | service/CLI | request-response, streaming, file-I/O | `tsc_cycle/v4_gates/phase12_reality_test.py` | exact |
| `tsc_cycle/v4_gates/phase20_log_render.py` | utility | transform, file-I/O | `tsc_cycle/v4_gates/phase12_log_render.py` | exact |
| `tsc_cycle/v4_gates/phase20_comparison.py` | service/gate | batch, transform | `tsc_cycle/eval/phase11_decision.py` + `tsc_cycle/v4_gates/saturation_policy.py` | role-match |
| `tsc_cycle/v4_gates/phase20_handoff.py` | service/gate | file-I/O, batch | `tsc_cycle/v4_gates/phase19_export.py` + `tsc_cycle/v4_gates/phase11_eval_report.py` | role-match |
| `scripts/run_v4_phase20_eval.sh` | utility/script | batch | `scripts/run_v4_phase11_eval_matrix.sh` + `scripts/run_v4_phase19_export.sh` | role-match |
| `scripts/run_v4_phase20_reality_test.sh` | utility/script | request-response, file-I/O | `scripts/run_phase12_reality_test.sh` | exact |
| `tests/test_v4_phase20_evaluation_replay_handoff.py` | test | batch, file-I/O | `tests/test_phase12_reality_log_generation.py` + `tests/test_v4_phase17_saturation_policy.py` + `tests/test_v4_phase19_training_export.py` | role-match |

## Pattern Assignments

### `tsc_cycle/v4_gates/phase20_eval.py` (service/gate, batch + transform + file-I/O)

**Analog:** `tsc_cycle/eval/phase11_metrics.py`, `tsc_cycle/v4_gates/phase17_audit.py`, `tsc_cycle/v4_gates/phase19_export.py`

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

**Per-sample scoring pattern** (`tsc_cycle/eval/phase11_metrics.py` lines 86-117):
```python
def _score_v4_cache(prompt: dict[str, Any], cache: dict[str, Any], *, backend: str, cache_file: Path) -> dict[str, Any]:
    solution = cache.get("solution")
    raw_text = cache.get("raw_text", "") or ""
    constraints = score_constraint(prompt.get("input") or {}, solution)
    mae = score_mae(solution, prompt.get("teacher_solution") or {})
    reasoning = score_reasoning(raw_text, prompt.get("input") or {})
    return {
        "backend": backend,
        "model_lineage": "v4_4b",
        "artifact_kind": "hf" if backend == V4_HF else "gguf_q4_k_m",
        "sample_id": str(prompt["sample_id"]),
        "split_hint": prompt.get("split_hint"),
        "slice_hint": prompt.get("slice_hint") or prompt.get("split_hint"),
        "phase_count": prompt.get("phase_count"),
        "trivial": bool(prompt.get("trivial", False) or constraints.get("trivial", False)),
        "format_ok": _format_ok(cache),
        "lint_ok": bool(constraints["lint_ok"]),
        "violations": constraints["violations"],
        "mae": mae["mae"],
        "exact_match": mae["exact_match"],
        "n_phases": mae["n_phases"],
        "per_phase_abs_err": mae["per_phase_abs_err"],
        "reasoning_tier": reasoning["reasoning_tier"],
        "hit_count": reasoning["hit_count"],
        "keywords_found": reasoning["keywords_found"],
        "numbers_found": reasoning["numbers_found"],
        "solution": solution,
        "parse_error": cache.get("parse_error"),
```

**Metric aggregation pattern** (`tsc_cycle/eval/phase11_metrics.py` lines 311-396): copy structure, but Phase 20 must remove teacher-MAE from blocking decision inputs and add saturation-policy counts as blocking gates.
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

**Saturation policy gate integration** (`tsc_cycle/v4_gates/phase17_audit.py` lines 268-328):
```python
def evaluate_saturation_policy_gate(
    rows_or_audit: Any,
    thresholds: dict[str, Any] | None = None,
    source_type: str = "data",
) -> dict[str, Any]:
    """Apply the reusable POLICY-02 low-saturation max-green threshold gate."""
    active_thresholds, fatal_failures = _finite_thresholds(thresholds)
    source = str(source_type or "unknown")
    audit, evidence_failures = _coerce_rows_or_audit(rows_or_audit)
    for failure in evidence_failures:
        fatal_failures.append({"gate": f"{source}_malformed_evidence", "reason": failure["reason"]})
```

**Phase 19 handoff validation before eval** (`tsc_cycle/v4_gates/phase19_export.py` lines 371-383):
```python
def validate_phase19_export_report(run_root: Path, report_path: Path | None = None, out: Path | None = None) -> dict[str, Any]:
    root = _require_v42_run_root(Path(run_root))
    path = Path(report_path) if report_path is not None else root / "phase19_export_report.json"
    gates: dict[str, Any] = {}
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        failures = [{"gate": "report_path", "reason": f"export report must stay under run root: {path}"}]
        result = {"ok": False, "next_phase_allowed": False, "requirements_covered": [], "gates": gates, "fatal_failures": failures, "report_path": str(path)}
```

**Planner note:** Phase 20 eval should call `validate_phase19_export_report(Path("/home/samuel/TSC_CYCLE/runs/v4.2-4B-20260518T111519Z"))`, then parse/lint generated outputs, project per-phase rows with saturation helpers, and emit `artifacts/v4_2/phase20/eval_report.json` with `requirements_covered: ["EVAL-01"]`. Teacher-MAE may appear under `advisory` only, not under blocking `decision_inputs`.

---

### `tsc_cycle/v4_gates/phase20_reality_test.py` (service/CLI, request-response + streaming + file-I/O)

**Analog:** `tsc_cycle/v4_gates/phase12_reality_test.py`

**Imports + dependencies pattern** (`tsc_cycle/v4_gates/phase12_reality_test.py` lines 14-23):
```python
from tsc_cycle.eval.metrics_constraints import score_constraint
from tsc_cycle.eval.metrics_reasoning import score_reasoning
from tsc_cycle.prompt_builder import build_assistant_prefill, build_user_prompt, parse_assistant_output
from tsc_cycle.v4_gates.phase12_log_render import (
    DEFAULT_BACKEND_LABEL,
    ensure_phase12_output_passes,
    lint_phase12_payload,
    render_reality_test_log,
)
from tsc_cycle.v4_gates.phase12_report import evaluate_phase12_report
```

**v4.2 constants should copy shape but change roots** (`tsc_cycle/v4_gates/phase12_reality_test.py` lines 25-36):
```python
PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
REALITY_LOG = PROJECT_ROOT / "reality.log"
FINAL_LOG = PROJECT_ROOT / "reality_test.log"
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4" / "phase12"
CACHE_DIR = ARTIFACT_ROOT / "gen_cache"
MANIFEST_PATH = ARTIFACT_ROOT / "manifest.json"
PER_SAMPLE_PATH = ARTIFACT_ROOT / "per_sample.jsonl"
REPORT_PATH = ARTIFACT_ROOT / "phase12_report.json"
SERVER_LOG = ARTIFACT_ROOT / "llama_server.log"
PHASE11_GATE_REPORT = PROJECT_ROOT / "artifacts" / "v4" / "phase11" / "phase11_gate_report.json"
APPROVED_MODEL_ARTIFACT = PROJECT_ROOT / "runs" / "v4.0-4B-20260509T184844Z" / "gguf" / "model.q4_K_M.gguf"
```

For Phase 20, replace with `ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4_2" / "phase20"`, `APPROVED_MODEL_ARTIFACT = PROJECT_ROOT / "runs" / "v4.2-4B-20260518T111519Z" / "gguf" / "model.q4_K_M.gguf"`, and final log path should be v4.2-scoped unless the plan explicitly chooses to overwrite `/home/samuel/TSC_CYCLE/reality_test.log` after all gates pass.

**Reality input extraction pattern** (`tsc_cycle/v4_gates/phase12_reality_test.py` lines 107-130):
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
```

**Live llama-server replay pattern** (`tsc_cycle/v4_gates/phase12_reality_test.py` lines 276-319):
```python
def _run_live(records: list[dict[str, Any]], args: argparse.Namespace, cache_dir: Path, model_sha: str) -> list[dict[str, Any]]:
    from tsc_cycle.student.parity_gguf import _find_free_port, _kill_server, _post_completion, _spawn_server, _wait_health

    port = _find_free_port()
    proc = _spawn_server(Path(args.llama_server), Path(args.gguf_path), port, args.ngl, args.threads, args.ctx_size, SERVER_LOG)
    try:
        if not _wait_health(port, args.timeout_sec):
            raise RuntimeError(f"llama-server did not become healthy; see {SERVER_LOG}")
        outputs: list[dict[str, Any]] = []
        for record in records:
            cache_path = cache_dir / f"{record['sample_id']}.json"
            if args.resume:
                cached = _load_cache(cache_path)
                if cached is not None and _cache_matches_current_run(cached, record, args, model_sha):
                    outputs.append(cached)
                    continue
            prompt = build_user_prompt(record["input"]) + "\n" + build_assistant_prefill()
            text, meta = _post_completion(port, prompt, args.n_predict, args.timeout_sec)
```

**Manifest + fail-closed report pattern** (`tsc_cycle/v4_gates/phase12_reality_test.py` lines 390-445):
```python
_write_per_sample(outputs, per_sample_path)
rendered = render_reality_test_log(records, outputs, backend_label=args.backend_label)
output_sha = sha256_text(rendered)

manifest = {
    "ok": True,
    "dry_run": bool(args.dry_run),
    "started_at_epoch": started,
    "elapsed_sec": time.time() - started,
    "reality_log": str(args.reality_log),
    "out_log": str(args.out_log),
    "artifact_root": str(artifact_root),
    "model_artifact": str(args.gguf_path),
    "model_sha256": model_sha,
    "input_sha256": input_log_sha,
    "output_sha256": output_sha,
    "input_count": len(records),
    "output_count": len(outputs),
    "limit": args.limit,
    "backend_label": args.backend_label,
```

**Planner note:** Phase 20 replay must add a saturation-policy projection/gate after parse/lint and before accepted `ok: true`. Dry-run/smoke reports cannot satisfy EVAL-02.

---

### `tsc_cycle/v4_gates/phase20_log_render.py` (utility, transform + file-I/O)

**Analog:** `tsc_cycle/v4_gates/phase12_log_render.py`

**Parse/lint gate before rendering** (`tsc_cycle/v4_gates/phase12_log_render.py` lines 14-35):
```python
def lint_phase12_payload(prediction_input: dict[str, Any], solution: dict[str, int] | None) -> dict[str, Any]:
    """Recompute Phase 12 constraint lint from the audited input and parsed solution."""
    if solution is None:
        return {"ok": False, "violations": [{"kind": "unparseable"}]}
    lint = validate(prediction_input, solution)
    return {"ok": bool(lint.ok), "violations": lint.violations}


def ensure_phase12_output_passes(record: dict[str, Any], output: dict[str, Any]) -> None:
    """Fail closed unless raw_text parses and lints against the matching current input."""
    if output.get("sample_id") != record.get("sample_id"):
        raise ValueError(f"Phase 12 sample_id mismatch: {output.get('sample_id')} != {record.get('sample_id')}")
    if output.get("input_sha256") and output.get("input_sha256") != record.get("input_sha256"):
        raise ValueError(f"Phase 12 input hash mismatch for {record.get('sample_id')}")
    raw = str(output.get("raw_text") or "")
    reasoning, solution = parse_assistant_output(raw)
    if not reasoning or solution is None:
        raise ValueError(f"Phase 12 protocol/parse gate failed for {record.get('sample_id')}")
```

**Canonical log render pattern** (`tsc_cycle/v4_gates/phase12_log_render.py` lines 37-64):
```python
def render_reality_test_log(
    records: Iterable[dict[str, Any]],
    outputs: Iterable[dict[str, Any]],
    *,
    backend_label: str = DEFAULT_BACKEND_LABEL,
) -> str:
    """Render the canonical Phase 12 final log from audited inputs and raw outputs."""
    recs = list(records)
    outs = list(outputs)
    if len(recs) != len(outs):
        raise ValueError(f"cannot render Phase 12 log with count mismatch: {len(recs)} != {len(outs)}")
    chunks: list[str] = []
    for record, output in zip(recs, outs, strict=True):
        ensure_phase12_output_passes(record, output)
        timestamp = record.get("timestamp") or record.get("as_of") or "unknown-time"
        crossing = record.get("crossing_id") or "unknown"
        prompt = build_user_prompt(record["input"])
        _, parsed = parse_assistant_output(str(output.get("raw_text") or ""))
```

**Planner note:** Keep prompt bytes unchanged via `build_user_prompt`; do not add saturation instructions to the rendered prompt. Add saturation gate in report data, not in log prompt text.

---

### `tsc_cycle/v4_gates/phase20_comparison.py` (service/gate, batch + transform)

**Analog:** `tsc_cycle/eval/phase11_decision.py` and `tsc_cycle/v4_gates/saturation_policy.py`

**Deterministic paired comparison pattern** (`tsc_cycle/eval/phase11_decision.py` lines 139-164):
```python
def bootstrap_ci(
    paired_rows: list[dict[str, Any]],
    *,
    seed: int = 42,
    n_resamples: int = 2000,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Return deterministic paired bootstrap CIs for hard-pass and MAE deltas."""
    if not paired_rows:
        raise ValueError("bootstrap_ci requires non-empty paired comparable sample rows")
    rows = sorted(paired_rows, key=lambda r: str(r.get("sample_id", "")))
    left_hard = [{"sample_id": r["sample_id"], "value": 1.0 if r.get("v4_q4_hard_pass") else 0.0} for r in rows]
    right_hard = [{"sample_id": r["sample_id"], "value": 1.0 if r.get("v1_q4_hard_pass") else 0.0} for r in rows]
```

**Fail-closed gate assembly pattern** (`tsc_cycle/eval/phase11_decision.py` lines 177-290):
```python
def evaluate_phase11_decision(
    metrics: dict[str, Any],
    *,
    phase10_report: dict[str, Any] | None = None,
    advisory_warnings: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Evaluate the locked U-01 Phase 11 GO/NO-GO/USER_DECISION gate."""
    failures: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = list(advisory_warnings or [])
    warnings.extend(_pending_cache_warnings(metrics))
```

**Saturation row normalization pattern** (`tsc_cycle/v4_gates/saturation_policy.py` lines 341-373):
```python
def _normalise_audit_row(row: dict[str, Any]) -> dict[str, Any]:
    required = {
        "origin_artifact",
        "sample_id",
        "phase_id",
        "pred_saturation",
        "min_green",
        "max_green",
        "final_green",
        "split",
        "source",
    }
    missing = sorted(field for field in required if field not in row)
    if missing:
        raise ValueError(f"missing required audit row field(s): {', '.join(missing)}")
```

**Planner note:** The comparison report should compare v4.0 vs v4.2 saturation-policy outcomes, not teacher-MAE. Required blocking claims: low-saturation max-green failures removed or under thresholds, and hard-constraint validity not regressed.

---

### `tsc_cycle/v4_gates/phase20_handoff.py` (service/gate, file-I/O + batch)

**Analog:** `tsc_cycle/v4_gates/phase19_export.py` and `tsc_cycle/v4_gates/phase11_eval_report.py`

**Fail-closed report shape with artifacts** (`tsc_cycle/v4_gates/phase19_export.py` lines 346-368):
```python
report = {
    "ok": not fatal_failures,
    "next_phase_allowed": not fatal_failures,
    "requirements_covered": list(REQUIREMENTS_COVERED) if not fatal_failures else [],
    "run_root": str(root),
    "phase19_report": export_plan.get("phase19_report"),
    "phase19_handoff": export_plan.get("phase19_handoff"),
    "paths": dict(paths),
    "llama_cpp": export_plan.get("llama_cpp"),
    "commands": export_plan.get("commands"),
    "wrapper_commands": export_plan.get("wrapper_commands"),
    "artifacts": {
        "merged_hf_safetensors": merged_records,
        "merged_hf_materializer": hf_materializer_records,
        "merged_hf_tokenizer": tokenizer_files,
        "gguf_fp16": fp16_record,
        "gguf_q4_K_M": q4_record,
    },
    "fatal_failures": fatal_failures,
    "warnings": [],
}
```

**Aggregate handoff report pattern** (`tsc_cycle/v4_gates/phase11_eval_report.py` lines 193-217):
```python
payload = {
    "ok": ok,
    "next_phase_allowed": ok,
    "requirements_covered": list(REQUIREMENTS_COVERED),
    "gates": gates,
    "fatal_failures": failures,
    "warnings": warnings,
    "decision": decision,
    "recommended_artifact": decision.get("recommended_artifact"),
    "fallback_artifact": decision.get("fallback_artifact") or str(V1_Q4_ARTIFACT),
    "reports": {
        "phase10_handoff": str(phase10_path),
        "matrix_manifest": str(manifest_path),
        "metrics_json": str(metrics if not isinstance(metrics, dict) else METRICS_PATH),
        "metrics_report_md": str(report_path),
        "decision_md": str(decision_path),
        "per_sample": str(per_sample_path),
        "gate_report": str(out_path) if out_path is not None else str(GATE_REPORT_PATH),
    },
```

**Artifact hash recomputation pattern** (`tsc_cycle/v4_gates/phase19_export.py` lines 28-33, 244-254):
```python
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
```
```python
def _artifact_record(path: Path, *, required: bool = True) -> tuple[dict[str, Any], list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    record: dict[str, Any] = {"path": str(path), "exists": Path(path).exists()}
    if Path(path).is_file():
        size = Path(path).stat().st_size
        record.update({"size_bytes": size, "sha256": sha256_file(Path(path)) if size > 0 else None})
```

**Planner note:** Final Phase 20 handoff must contain hashes for training report, export report, q4_K_M GGUF, eval report, replay log/report, comparison report, and final handoff report. Set `requirements_covered: ["EVAL-01", "EVAL-02", "EVAL-03"]` only when all gates pass.

---

### `scripts/run_v4_phase20_eval.sh` (utility/script, batch)

**Analog:** `scripts/run_v4_phase11_eval_matrix.sh` and `scripts/run_v4_phase19_export.sh`

**Shell wrapper pattern** (`scripts/run_v4_phase19_export.sh` lines 1-20):
```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/samuel/TSC_CYCLE"
PY="$ROOT/.venv/bin/python"
LLAMA_CPP="${LLAMA_CPP_DIR:-/home/samuel/projects/EvoProgTSC/llama.cpp}"

if [[ $# -gt 1 ]]; then
  printf 'usage: %s [RUN_ROOT]\n' "$0" >&2
  exit 2
fi

RUN_ROOT="${1:-runs/v4.2-4B-$(date -u +%Y%m%dT%H%M%SZ)}"
case "$RUN_ROOT" in
  runs/v4.2-4B-*|*/runs/v4.2-4B-*) ;;
  *) printf 'RUN_ROOT must match runs/v4.2-4B-*\n' >&2; exit 2 ;;
esac
cd "$ROOT"
```

**Eval generation sequence pattern** (`scripts/run_v4_phase11_eval_matrix.sh` lines 36-57):
```bash
"${PYTHON}" -m tsc_cycle.eval.phase11_matrix \
  --run-root "${RUN_ROOT}" \
  --out-root "${PHASE11_ROOT}" \
  --frozen-v1-root "${FROZEN_V1_ROOT}" \
  --phase10-report "${RUN_ROOT}/phase10_gguf_report.json" \
  --labeled "${PROJECT_ROOT}/data/v4/phase8/labeled_merged.jsonl" \
  --alignment "${PROJECT_ROOT}/data/v4/phase8/splits/v1_ood_alignment.json" \
  --seed 42 \
  --n-id 300 \
  --n-expanded-ood 300

"${PROJECT_ROOT}/scripts/dgx_spark/run_safe.sh" 100G -- "${PYTHON}" -m tsc_cycle.eval.generate_hf \
  --merged-hf "${RUN_ROOT}/merged_hf" \
  --prompts "${PHASE11_ROOT}/eval_prompts.jsonl" \
  --cache-dir "${PHASE11_ROOT}/gen_cache/v4_hf"
```

**Planner note:** Phase 20 eval script should hard-code accepted run root default `runs/v4.2-4B-20260518T111519Z`, validate `phase19_export_report.json` first, use `scripts/dgx_spark/run_safe.sh 100G --` for HF generation, and not install dependencies or use vLLM.

---

### `scripts/run_v4_phase20_reality_test.sh` (utility/script, request-response + file-I/O)

**Analog:** `scripts/run_phase12_reality_test.sh`

**Preflight and constants pattern** (`scripts/run_phase12_reality_test.sh` lines 1-15):
```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/samuel/TSC_CYCLE"
PYTHON="/home/samuel/TSC_CYCLE/.venv/bin/python"
REALITY_LOG="/home/samuel/TSC_CYCLE/reality.log"
OUT_LOG="/home/samuel/TSC_CYCLE/reality_test.log"
ARTIFACT_ROOT="/home/samuel/TSC_CYCLE/artifacts/v4/phase12"
GGUF_PATH="/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf"
LLAMA_SERVER="/home/samuel/llama.cpp/build/bin/llama-server"
PHASE11_REPORT="/home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json"
BACKEND_LABEL="tsc-cycle-v4-q4_K_M"

export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"
cd "${PROJECT_ROOT}"
```

**Handoff gate preflight pattern** (`scripts/run_phase12_reality_test.sh` lines 36-51):
```bash
"${PYTHON}" - <<'PY'
import json
from pathlib import Path
report_path = Path('/home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json')
if not report_path.exists():
    raise SystemExit(f'missing Phase 11 gate report: {report_path}')
report = json.loads(report_path.read_text(encoding='utf-8'))
expected = '/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf'
if report.get('ok') is not True:
    raise SystemExit(f'Phase 11 report is not ok: {report.get("fatal_failures")}')
if report.get('next_phase_allowed') is not True:
    raise SystemExit('Phase 11 report does not allow next phase')
if report.get('recommended_artifact') != expected:
    raise SystemExit(f'Phase 11 recommended artifact mismatch: {report.get("recommended_artifact")} != {expected}')
```

**Replay invocation pattern** (`scripts/run_phase12_reality_test.sh` lines 55-68):
```bash
"${PYTHON}" -m tsc_cycle.v4_gates.phase12_reality_test \
  --reality-log "${REALITY_LOG}" \
  --out-log "${OUT_LOG}" \
  --artifact-root "${ARTIFACT_ROOT}" \
  --gguf-path "${GGUF_PATH}" \
  --llama-server "${LLAMA_SERVER}" \
  --backend-label "${BACKEND_LABEL}" \
  --resume \
  --n-predict 384 \
  --retry-n-predict 768 \
  --timeout-sec 600 \
  --ngl 99 \
  --threads 4 \
  --ctx-size 4096
```

**Planner note:** Replace Phase 11 gate preflight with Phase 20 eval/export preflight. Use `ARTIFACT_ROOT=/home/samuel/TSC_CYCLE/artifacts/v4_2/phase20`, `GGUF_PATH=/home/samuel/TSC_CYCLE/runs/v4.2-4B-20260518T111519Z/gguf/model.q4_K_M.gguf`, and backend label such as `tsc-cycle-v4.2-q4_K_M`.

---

### `tests/test_v4_phase20_evaluation_replay_handoff.py` (test, batch + file-I/O)

**Analog:** `tests/test_phase12_reality_log_generation.py`, `tests/test_v4_phase17_saturation_policy.py`, `tests/test_v4_phase19_training_export.py`

**Lazy import guard pattern** (`tests/test_phase12_reality_log_generation.py` lines 25-36):
```python
@pytest.fixture(autouse=True)
def _phase12_modules_are_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 12 contracts must never load model/GPU stacks during test execution."""
    real_import = importlib.import_module

    def guarded_import(name: str, package: str | None = None):
        root = name.split(".", 1)[0]
        if root in FORBIDDEN_COLLECTION_IMPORTS:
            raise AssertionError(f"Phase 12 contract imported heavyweight dependency during test execution: {name}")
        return real_import(name, package)
```

**Parse/lint/report fail-closed test pattern** (`tests/test_phase12_reality_log_generation.py` lines 274-335):
```python
def test_report_evaluation_fails_closed_on_parse_lint_count_or_hash_failures(tmp_path: Path) -> None:
    mod = _phase12_report_contract()
    final_log = tmp_path / "reality_test.log"
    records = [_record("reality-0001")]
    outputs = [_good_output("reality-0001")]
    canonical_log = _phase12_reality_contract().render_reality_test_log(records, outputs)
    final_log.write_text(canonical_log, encoding="utf-8")
    model_artifact = tmp_path / "model.q4_K_M.gguf"
    model_artifact.write_bytes(b"fake model artifact")
```

**Saturation threshold test pattern** (`tests/test_v4_phase17_saturation_policy.py` lines 687-704):
```python
def test_policy_gate_fails_closed_on_eval_style_threshold_excess() -> None:
    mod = _audit_contract()
    report = mod.evaluate_saturation_policy_gate([_phase_row()], source_type="eval")

    assert report["ok"] is False
    assert report["next_phase_allowed"] is False
    assert any("eval" in failure["gate"] and "threshold_excess" in failure["gate"] for failure in report["fatal_failures"])
    assert report["thresholds"] == mod.DEFAULT_THRESHOLDS
```

**Phase 19 export handoff test pattern** (`tests/test_v4_phase19_training_export.py` lines 850-858):
```python
report = write_export_report(run_root=run_root, export_plan=plan, out=run_root / "phase19_export_report.json")
accepted = validate_phase19_export_report(run_root=run_root, report_path=run_root / "phase19_export_report.json")

assert report["ok"] is True
assert accepted["ok"] is True
assert accepted["requirements_covered"] == ["TRAIN-02"]
assert accepted["artifacts"]["gguf_fp16"]["sha256"] == __import__("hashlib").sha256(b"fp16 gguf").hexdigest()
assert accepted["artifacts"]["gguf_q4_K_M"]["sha256"] == __import__("hashlib").sha256(b"q4 gguf").hexdigest()
```

**Planner note:** Phase 20 tests should verify: no heavy imports at collection; export report must validate before eval/replay; teacher-MAE is advisory only; native `<think>` is rejected; saturation failures block eval and replay; v4.2 artifacts stay under `artifacts/v4_2/phase20/`; no v4.0 Phase 11/12 defaults are overwritten as sole evidence.

## Shared Patterns

### Protocol parsing and custom tag rejection
**Source:** `tsc_cycle/prompt_builder.py` lines 100-122  
**Apply to:** `phase20_eval.py`, `phase20_reality_test.py`, `phase20_log_render.py`, tests
```python
def parse_assistant_output(text: str) -> tuple[str, dict[str, int] | None]:
    """Parse model output into (reasoning, solution_dict)."""
    if MALFORMED_THINK_CLOSE in text or any(tag in text for tag in NATIVE_THINK_TAGS):
        return "", None

    stripped = text.strip()
    match = FULL_OUTPUT_RE.fullmatch(stripped)
    if match is None and TAG_THINK_OPEN not in stripped:
        match = PREFILL_OUTPUT_RE.fullmatch(stripped)
    if match is None:
        return "", None
```

### Hard-constraint lint
**Source:** `tsc_cycle/constraint_lint.py` lines 34-89  
**Apply to:** all eval/replay/report files
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
```

### Saturation band and violation classification
**Source:** `tsc_cycle/v4_gates/saturation_policy.py` lines 59-90  
**Apply to:** Phase 20 eval, replay, comparison
```python
def classify_saturation_band(sat: Any) -> str:
    """Classify a finite saturation value into the POLICY-01 half-open band."""
    sat_f = _finite_float(sat, field="pred_saturation")
    if sat_f < 0.2:
        return BAND_NEAR_MIN
    if sat_f < 0.6:
        return BAND_INTERPOLATED
    if sat_f < 1.0:
        return BAND_HIGH_NOT_MAX
    return BAND_ALLOWED_MAX


def classify_violation(row: dict[str, Any]) -> str:
    """Classify one projected per-phase decision into a stable audit category."""
    band = classify_saturation_band(row.get("pred_saturation"))
```

### Fail-closed gate payload shape
**Source:** `tsc_cycle/v4_gates/phase17_audit.py` lines 476-507  
**Apply to:** all Phase 20 reports
```python
policy_gate = {
    "ok": ok,
    "next_phase_allowed": ok,
    "requirements_covered": list(REQUIREMENTS_COVERED),
    "thresholds": _finite_thresholds(thresholds)[0],
    "gates": {
        "dataset_audit": {"ok": "dataset" in projections},
        "replay_audit": {"ok": "replay" in projections},
        "eval_audit": {"ok": phase_decisions_jsonl is None or "eval" in projections},
        "audit_compute": {"ok": bool(audit.get("ok", False))},
        "policy_thresholds": threshold_reports,
        "prompt_protocol": {"ok": prompt_protocol.get("ok") is True},
    },
    "fatal_failures": fatal_failures,
    "warnings": warnings,
```

### v4.2 path safety and forbidden legacy roots
**Source:** `tsc_cycle/v4_gates/phase19_export.py` lines 72-94  
**Apply to:** Phase 20 output paths and handoff files
```python
def is_forbidden_output_path(path: Path) -> bool:
    candidate = Path(path)
    return _is_under(candidate, FROZEN_BASELINE_ROOT) or "v4.0-4B-" in candidate.as_posix()


def _require_v42_run_root(run_root: Path) -> Path:
    root = validate_run_root(run_root)
    if root.name in FORBIDDEN_ROOT_NAMES or "v4.0-4B-" in root.as_posix():
        raise ValueError(f"Phase 19 export run root must be v4.2 only: {root}")
```

### Heavy model imports are lazy in gate modules
**Source:** `tests/test_phase12_reality_log_generation.py` lines 131-149  
**Apply to:** Phase 20 tests and module design
```python
def test_phase12_contracts_do_not_import_heavy_model_stacks_at_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    module_paths = [
        PROJECT_ROOT / "tsc_cycle" / "v4_gates" / "phase12_reality_test.py",
        PROJECT_ROOT / "tsc_cycle" / "v4_gates" / "phase12_report.py",
    ]
    for module_path in module_paths:
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots: set[str] = set()
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| None | - | - | Existing Phase 11, 12, 17, and 19 code provides role-match or exact analogs for all planned Phase 20 files. |

## Metadata

**Analog search scope:** `/home/samuel/TSC_CYCLE/tsc_cycle`, `/home/samuel/TSC_CYCLE/tests`, `/home/samuel/TSC_CYCLE/scripts`, `/home/samuel/TSC_CYCLE/.planning/phases`  
**Files scanned:** source/test/script listings across project; stopped after strong matches in Phase 11/12/17/19 files  
**Pattern extraction date:** 2026-05-19
