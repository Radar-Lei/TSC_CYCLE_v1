# Phase 12: home-samuel-tsc-cycle-reality-log-reality-test-log - Pattern Map

**Mapped:** 2026-05-11
**Files analyzed:** 5
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tsc_cycle/v4_gates/phase12_reality_test.py` | utility / local CLI | file-I/O + batch + request-response | `tsc_cycle/eval/generate_gguf.py` | exact |
| `tsc_cycle/v4_gates/phase12_report.py` | report gate | batch + file-I/O + fail-closed validation | `tsc_cycle/v4_gates/phase11_eval_report.py` | role-match |
| `scripts/run_phase12_reality_test.sh` | utility / config script | batch + file-I/O | `scripts/run_v4_phase11_eval_matrix.sh` | exact |
| `tests/test_phase12_reality_log_generation.py` | test | file-I/O + transform + fail-closed validation | `tests/test_v4_phase11_eval_matrix.py` | role-match |
| `artifacts/v4/phase12/{manifest.json,per_sample.jsonl,phase12_report.json}` | report artifact | batch + file-I/O | `tsc_cycle/v4_gates/phase11_eval_report.py` | role-match |
| `reality_test.log` | output log artifact | file-I/O | `reality.log` | exact |

## Pattern Assignments

### `tsc_cycle/v4_gates/phase12_reality_test.py` (utility / local CLI, file-I/O + batch + request-response)

**Analog:** `tsc_cycle/eval/generate_gguf.py`  
**Supporting analogs:** `tsc_cycle/student/parity_gguf.py`, `tsc_cycle/prompt_builder.py`, `tsc_cycle/constraint_lint.py`, `tsc_cycle/eval/metrics_constraints.py`, `tsc_cycle/eval/metrics_reasoning.py`, `tsc_cycle/eval/phase11_matrix.py`

**Imports pattern** (`tsc_cycle/eval/generate_gguf.py` lines 36-55):
```python
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from tsc_cycle.prompt_builder import (
    build_assistant_prefill,
    build_user_prompt,
    parse_assistant_output,
)
from tsc_cycle.student.parity_gguf import (
    _find_free_port,
    _kill_server,
    _post_completion,
    _spawn_server,
    _wait_health,
)
```

**Reality input extraction pattern** (`reality.log` lines 15-22, 54-56; use regex only around framed input):
```text
2026-04-27 00:02:27|INFO|type=prompt|crossing_id=1

你是交通信号配时优化专家。
【cycle_predict_input_json】{
  "prediction": {
    "as_of": "2026-04-27 00:02:27",
    "phase_waits": [
...
  }
}【/cycle_predict_input_json】
```
Copy the framed-JSON approach from research: scan only `type=prompt` blocks / `【cycle_predict_input_json】...【/cycle_predict_input_json】`; never use old `RAW:`, `REASONING:`, or `PARSED:` blocks as source answers.

**Prompt/protocol pattern** (`tsc_cycle/prompt_builder.py` lines 22-39, 72-88):
```python
TAG_THINK_OPEN = "<start_working_out>"
TAG_THINK_CLOSE = "</end_working_out>"
TAG_SOLUTION_OPEN = "<SOLUTION>"
TAG_SOLUTION_CLOSE = "</SOLUTION>"

MALFORMED_THINK_CLOSE = "<end_working_out>"
NATIVE_THINK_TAGS = ("<think>", "</think>")
FULL_OUTPUT_RE = re.compile(
    rf"^{re.escape(TAG_THINK_OPEN)}(?P<reasoning>.*?){re.escape(TAG_THINK_CLOSE)}"
    rf"{re.escape(TAG_SOLUTION_OPEN)}(?P<solution>.*?){re.escape(TAG_SOLUTION_CLOSE)}$",
    re.DOTALL,
)
PREFILL_OUTPUT_RE = re.compile(
    rf"^(?P<reasoning>.*?){re.escape(TAG_THINK_CLOSE)}"
    rf"{re.escape(TAG_SOLUTION_OPEN)}(?P<solution>.*?){re.escape(TAG_SOLUTION_CLOSE)}$",
    re.DOTALL,
)
```
```python
def build_user_prompt(prediction_input: dict[str, Any]) -> str:
    """Build the user-side prompt text (system + framed JSON + instructions).

    Parameters
    ----------
    prediction_input : dict
        {"prediction": {"as_of": str, "phase_waits": [...]}}.
    """
    # Pretty-printed JSON to match reality.log exactly (2-space indent).
    input_json = json.dumps(prediction_input, indent=2, ensure_ascii=False)
    return USER_TEMPLATE.format(system=SYSTEM_PROMPT, input_json=input_json)


def build_assistant_prefill() -> str:
    """The assistant turn MUST start with the opening think tag — model only
    learns content, not the tag emission decision."""
    return TAG_THINK_OPEN
```

**GGUF request-response inference pattern** (`tsc_cycle/eval/generate_gguf.py` lines 145-173):
```python
infer_t0 = time.time()
for i, rec in enumerate(todo, 1):
    sid = rec["sample_id"]
    split = rec.get("split_hint", "?")
    user_prompt = build_user_prompt(rec["input"])
    full = user_prompt + "\n" + build_assistant_prefill()
    text, meta = _post_completion(port, full, args.n_predict, args.timeout_sec)
    if meta["timeout"]:
        sol, err = None, "timeout"
    elif meta.get("http_status") is None:
        sol, err = None, f"http_error: {meta.get('error', 'unknown')}"
    else:
        _, sol = parse_assistant_output(text)
        err = None if sol is not None else "solution_unparseable"

    out = {
        "sample_id": sid,
        "split_hint": split,
        "backend": label,
        "solution": sol,
        "parse_error": err,
        "raw_text": text,
        "elapsed_sec": meta["elapsed_sec"],
        "n_predict": args.n_predict,
        "seed": 42,
    }
    (cache_dir / f"{sid}.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

**Server lifecycle/auth/network boundary pattern** (`tsc_cycle/student/parity_gguf.py` lines 117-143, 146-160):
```python
def _spawn_server(
    llama_server: Path,
    gguf_path: Path,
    port: int,
    ngl: int,
    threads: int,
    ctx_size: int,
    log_path: Path,
) -> subprocess.Popen:
    cmd = [
        str(llama_server),
        "-m", str(gguf_path),
        "--host", "127.0.0.1",
        "--port", str(port),
        "-ngl", str(ngl),
        "-t", str(threads),
        "-c", str(ctx_size),
        "--no-webui",
    ]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = log_path.open("w", encoding="utf-8")
    print(f"[PARITY-GGUF] spawning server: {' '.join(cmd)}", file=sys.stderr)
    proc = subprocess.Popen(
        cmd, stdout=log_fh, stderr=log_fh,
        preexec_fn=os.setsid,  # own process group → clean teardown via SIGTERM
    )
    return proc
```
```python
def _kill_server(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)
```

**Request body / deterministic decode pattern** (`tsc_cycle/student/parity_gguf.py` lines 69-103):
```python
def _post_completion(
    port: int,
    prompt: str,
    n_predict: int,
    timeout_sec: int,
) -> tuple[str, dict]:
    """POST /completion; returns (content_text_with_prefill, meta).

    meta = {"timeout": bool, "elapsed_sec": float, "http_status": int|None}
    """
    body = json.dumps({
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": 0.0,
        "top_k": 1,
        "seed": 42,
        "cache_prompt": True,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/completion",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        elapsed = time.time() - t0
        content = payload.get("content", "")
        return (
            build_assistant_prefill() + content,
            {"timeout": False, "elapsed_sec": elapsed, "http_status": resp.status},
        )
```

**Hard-constraint validation pattern** (`tsc_cycle/constraint_lint.py` lines 34-89):
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

    # Key set match
    output_keys = list(output.keys())
    if set(output_keys) != set(expected_ids):
        result.add(
            Violation.PHASE_MISMATCH,
            expected=expected_ids,
            got=output_keys,
        )
        return result  # downstream checks meaningless if phases don't match

    # Phase ORDER must match input order (we treat dict insertion order as semantic)
    if output_keys != expected_ids:
        result.add(Violation.PHASE_ORDER, expected=expected_ids, got=output_keys)

    # Per-phase validation
    for w in waits:
        pid = str(w["phase_id"])
        v = output.get(pid)
        # int check (reject bool, since bool is subclass of int)
        if isinstance(v, bool) or not isinstance(v, int):
            # Accept floats only if integral
            if isinstance(v, float) and v.is_integer():
                v = int(v)
            else:
                result.add(Violation.NOT_INTEGER, phase=pid, got=v)
                continue

        if v < w["min_green"]:
            result.add(Violation.BELOW_MIN, phase=pid, value=v, min=w["min_green"])
        if v > w["max_green"]:
            result.add(Violation.ABOVE_MAX, phase=pid, value=v, max=w["max_green"])

    return result
```

**Metrics pattern for per-sample report** (`tsc_cycle/eval/metrics_constraints.py` lines 14-43; `tsc_cycle/eval/metrics_reasoning.py` lines 22-55):
```python
def score_constraint(prediction_input: dict, solution: dict | None) -> dict[str, Any]:
    """Score a single (input, student_solution) pair against hard constraints."""
    trivial = is_trivial(prediction_input)
    if solution is None:
        return {"lint_ok": False, "violations": ["unparseable"], "trivial": trivial}
    res = validate(prediction_input, solution)
    kinds: list[str] = []
    for v in res.violations or []:
        if isinstance(v, dict):
            kinds.append(str(v.get("kind", "unknown")))
        elif hasattr(v, "value"):
            kinds.append(v.value)
        else:
            kinds.append(str(v))
    return {"lint_ok": bool(res.ok), "violations": kinds, "trivial": trivial}
```
```python
def score_reasoning(raw_text: str, prediction_input: dict) -> dict[str, Any]:
    """Score the reasoning segment of a model response."""
    reasoning, _ = parse_assistant_output(raw_text or "")
    if not reasoning:
        return {"reasoning_tier": "miss", "hit_count": 0,
                "keywords_found": [], "numbers_found": []}

    kws = [k for k in KEYWORDS if k in reasoning]
    ...
    return {"reasoning_tier": tier, "hit_count": hits,
            "keywords_found": kws, "numbers_found": sorted(nums_in_reasoning)}
```

**Path safety / fail-closed output pattern** (`tsc_cycle/eval/phase11_matrix.py` lines 48-91; adapt roots to `PROJECT_ROOT`, `artifacts/v4/phase12`, and final `reality_test.log`):
```python
def _is_under(path: Path, root: Path) -> bool:
    path = Path(path).expanduser().resolve(strict=False)
    root = Path(root).expanduser().resolve(strict=False)
    return path == root or root in path.parents


def reject_frozen_v1_output_path(path: str | Path) -> Path:
    """Reject any would-be output path under the frozen v1 run root."""
    candidate = Path(path).expanduser()
    if _is_under(candidate, FROZEN_V1_ROOT):
        raise ValueError(
            "refusing to write under frozen read-only v1 baseline "
            f"20260507T032419Z: {candidate}"
        )
    return candidate
```

---

### `scripts/run_phase12_reality_test.sh` (utility / config script, batch + file-I/O)

**Analog:** `scripts/run_v4_phase11_eval_matrix.sh`

**Shell wrapper pattern** (`scripts/run_v4_phase11_eval_matrix.sh` lines 0-10):
```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/home/samuel/TSC_CYCLE"
RUN_ROOT="/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z"
PHASE11_ROOT="${RUN_ROOT}/eval_phase11"
FROZEN_V1_ROOT="/home/samuel/TSC_CYCLE/runs/20260507T032419Z"
PYTHON="/home/samuel/TSC_CYCLE/.venv/bin/python"
LLAMA_SERVER="/home/samuel/llama.cpp/build/bin/llama-server"
export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}"
cd "${PROJECT_ROOT}"
```

**Preflight artifact handoff check pattern** (`scripts/run_v4_phase11_eval_matrix.sh` lines 12-29; adapt to Phase 11 gate report `recommended_artifact`):
```bash
"${PYTHON}" - <<'PY'
import json
from pathlib import Path
report = Path('/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json')
data = json.loads(report.read_text(encoding='utf-8'))
assert data.get('ok') is True, data.get('fatal_failures')
assert data.get('next_phase_allowed') is True, data
assert (data.get('phase11_handoff') or {}).get('allowed') is True, data.get('phase11_handoff')
paths = (data.get('artifact_manifest') or {}).get('paths') or {}
expected = {
    'merged_hf': '/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/merged_hf',
    'gguf_q4_K_M': '/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf',
}
for key, value in expected.items():
    assert paths.get(key) == value, (key, paths.get(key), value)
    assert Path(value).exists(), value
print('[PHASE11] Phase 10 handoff OK:', report)
PY
```

**Executable check and module invocation pattern** (`scripts/run_v4_phase11_eval_matrix.sh` lines 31-57):
```bash
if [[ ! -x "${LLAMA_SERVER}" ]]; then
  echo "missing executable llama-server: ${LLAMA_SERVER}" >&2
  exit 1
fi

"${PYTHON}" -m tsc_cycle.eval.generate_gguf \
  --gguf-path "${RUN_ROOT}/gguf/model.q4_K_M.gguf" \
  --backend-label v4_gguf_q4_k_m \
  --prompts "${PHASE11_ROOT}/eval_prompts.jsonl" \
  --cache-dir "${PHASE11_ROOT}/gen_cache/v4_gguf_q4_k_m" \
  --llama-server "${LLAMA_SERVER}"
```

For Phase 12, call `python -m tsc_cycle.v4_gates.phase12_reality_test` with absolute defaults:
- `--reality-log /home/samuel/TSC_CYCLE/reality.log`
- `--out-log /home/samuel/TSC_CYCLE/reality_test.log`
- `--artifact-root /home/samuel/TSC_CYCLE/artifacts/v4/phase12`
- `--gguf-path /home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf`
- `--llama-server /home/samuel/llama.cpp/build/bin/llama-server`

---

### `tests/test_phase12_reality_log_generation.py` (test, file-I/O + transform + fail-closed validation)

**Analog:** `tests/test_v4_phase11_eval_matrix.py`  
**Supporting analogs:** `tests/test_prompt_builder.py`, `tests/test_constraint_lint.py`

**Lazy import / no GPU stack pattern** (`tests/test_v4_phase11_eval_matrix.py` lines 1-37):
```python
import ast
import importlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
FORBIDDEN_COLLECTION_IMPORTS = {"torch", "transformers", "peft", "bitsandbytes", "vllm", "flash_attn"}


@pytest.fixture(autouse=True)
def _phase11_modules_are_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 11 contracts must never load model/GPU stacks during test execution."""
    real_import = importlib.import_module

    def guarded_import(name: str, package: str | None = None):
        root = name.split(".", 1)[0]
        if root in FORBIDDEN_COLLECTION_IMPORTS:
            raise AssertionError(f"Phase 11 contract imported heavyweight dependency during test execution: {name}")
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", guarded_import)


def _phase11_matrix_contract():
    return importlib.import_module("tsc_cycle.eval.phase11_matrix")
```

**Path/reject contract pattern** (`tests/test_v4_phase11_eval_matrix.py` lines 165-179):
```python
def test_phase11_matrix_rejects_frozen_v1_outputs_and_allows_v4_eval_root(tmp_path: Path) -> None:
    mod = _phase11_matrix_contract()

    forbidden_paths = [
        FROZEN_V1_ROOT,
        FROZEN_V1_ROOT / "eval" / "decision.md",
        FROZEN_V1_ROOT / "eval" / "gen_cache" / "gguf_q4_k_m" / "sample.json",
    ]
    for path in forbidden_paths:
        with pytest.raises((AssertionError, ValueError, RuntimeError), match="frozen|read.?only|20260507T032419Z"):
            mod.reject_frozen_v1_output_path(path)

    allowed = PHASE11_OUT_ROOT / "metrics.json"
    assert mod.reject_frozen_v1_output_path(allowed) in {None, str(allowed), allowed}
```

Adapt this to Phase 12 allowed outputs: `/home/samuel/TSC_CYCLE/reality_test.log` and `/home/samuel/TSC_CYCLE/artifacts/v4/phase12/**`; reject output under frozen runs and unrelated paths.

**Prompt builder protocol tests to copy** (`tests/test_prompt_builder.py` lines 26-45, 58-63, 98-134):
```python
def test_user_prompt_contains_required_blocks():
    p = build_user_prompt(EX_INPUT)
    assert "你是交通信号配时优化专家。" in p
    assert "【cycle_predict_input_json】" in p and "【/cycle_predict_input_json】" in p
    assert "硬约束（必须满足）" in p
    assert "<start_working_out>" in p and "</end_working_out>" in p
    assert "<SOLUTION>" in p and "</SOLUTION>" in p


def test_assistant_prefill():
    assert build_assistant_prefill() == TAG_THINK_OPEN
```
```python
def test_parse_with_prefill_only():
    # Output as model would emit: prefilled <start_working_out> NOT in text, only the new close
    body = "step-by-step</end_working_out><SOLUTION>{\"1\":60}</SOLUTION>"
    r, s = parse_assistant_output(body)
    assert r == "step-by-step"
    assert s == {"1": 60}
```
```python
def test_parse_rejects_malformed_close_tag():
    body = (
        "<start_working_out>x<end_working_out>"
        "<SOLUTION>{\"1\":60}</SOLUTION>"
    )
    r, s = parse_assistant_output(body)
    assert r == ""
    assert s is None
...
def test_full_assistant_uses_slash_close_tag():
    txt = build_full_assistant("r", {"1": 60})
    assert "</end_working_out>" in txt
    assert "<end_working_out>" not in txt
```

**Constraint lint test pattern** (`tests/test_constraint_lint.py` lines 11-17, 60-65, 75-79):
```python
def test_valid_output():
    inp = _input([(1, 50, 80), (2, 20, 45)])
    out = {"1": 60, "2": 30}
    res = validate(inp, out)
    assert res.ok
    assert res.violations == []
```
```python
def test_phase_order_violation():
    inp = _input([(1, 50, 80), (2, 20, 45)])
    out = {"2": 30, "1": 60}  # wrong order
    res = validate(inp, out)
    assert not res.ok
    assert any(v["kind"] == Violation.PHASE_ORDER.value for v in res.violations)
```
```python
def test_bool_rejected_as_int():
    inp = _input([(1, 50, 80)])
    res = validate(inp, {"1": True})
    assert not res.ok
    assert res.violations[0]["kind"] == Violation.NOT_INTEGER.value
```

Test cases planner should include:
- Extracts only prompt framed JSON and ignores preceding `type=result` content.
- Produces deterministic sample IDs and count for fixture logs.
- Uses Phase 11 `recommended_artifact` / v4 q4 path by default.
- Renders raw output with full `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` protocol.
- Fails closed and does not write final `reality_test.log` when parse/lint errors exist.

---

### `artifacts/v4/phase12/{manifest.json,per_sample.jsonl,phase12_report.json}` (report artifact, batch + file-I/O)

**Analog:** `tsc_cycle/v4_gates/phase11_eval_report.py`  
**Supporting analog:** `tsc_cycle/eval/generate_gguf.py`

**Report constants / output location pattern** (`tsc_cycle/v4_gates/phase11_eval_report.py` lines 13-23):
```python
PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4" / "phase11"
GATE_REPORT_PATH = ARTIFACT_ROOT / "phase11_gate_report.json"
MATRIX_MANIFEST_PATH = PHASE11_OUT_ROOT / "matrix_manifest.json"
PER_SAMPLE_PATH = PHASE11_OUT_ROOT / "per_sample.jsonl"
REPORT_MD_PATH = PHASE11_OUT_ROOT / "report.md"
EVAL_PROMPTS_PATH = PHASE11_OUT_ROOT / "eval_prompts.jsonl"
V4_Q4_ARTIFACT = V4_RUN_ROOT / "gguf" / "model.q4_K_M.gguf"
```

**JSON write / allowed output pattern** (`tsc_cycle/v4_gates/phase11_eval_report.py` lines 35-56):
```python
def _write_json(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    reject_frozen_v1_output_path(path)
    _assert_allowed_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _is_under(path: Path, root: Path) -> bool:
    path = path.expanduser().resolve(strict=False)
    root = root.expanduser().resolve(strict=False)
    return path == root or root in path.parents


def _assert_allowed_output(path: str | Path) -> None:
    candidate = Path(path)
    if _is_under(candidate, FROZEN_V1_ROOT):
        raise ValueError(f"refusing Phase 11 report output under frozen v1 root: {candidate}")
    if not (_is_under(candidate, PHASE11_OUT_ROOT) or _is_under(candidate, ARTIFACT_ROOT)):
        raise ValueError(f"Phase 11 report output must be under eval_phase11 or artifacts/v4/phase11: {candidate}")
```

**Gate helper / file check pattern** (`tsc_cycle/v4_gates/phase11_eval_report.py` lines 58-77):
```python
def _gate(ok: bool, reason: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": bool(ok), "reason": reason, "data": data or {}}


def _check_file(path: Path, label: str, failures: list[dict[str, str]], *, nonempty: bool = True) -> bool:
    if not path.exists():
        failures.append({"gate": label, "reason": f"missing {label}: {path}"})
        return False
    if nonempty and path.is_file() and path.stat().st_size <= 0:
        failures.append({"gate": label, "reason": f"empty {label}: {path}"})
        return False
    return True


def _check_dir(path: Path, label: str, failures: list[dict[str, str]]) -> bool:
    if not path.is_dir():
        failures.append({"gate": label, "reason": f"missing directory {label}: {path}"})
        return False
    return True
```

**Aggregate report shape pattern** (`tsc_cycle/v4_gates/phase11_eval_report.py` lines 193-217):
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
    "phase11_handoff": {
        "allowed": ok,
        "report_path": str(out_path) if out_path is not None else str(GATE_REPORT_PATH),
        "status": decision.get("verdict", "NO_GO"),
    },
}
```

For Phase 12, use analogous keys:
- `ok`, `next_phase_allowed`, `requirements_covered` (`P12-IMPLICIT-01`..`05`)
- `input_count`, `cache_count`, `parse_ok_count`, `lint_ok_count`, `reasoning_tier_counts`
- `model_artifact`, `model_sha256`, `input_sha256`, `output_sha256`
- `reports.manifest`, `reports.per_sample`, `reports.reality_test_log`, `reports.server_log`

---

### `reality_test.log` (output log artifact, file-I/O)

**Analog:** `reality.log`

**Prompt block format to preserve** (`reality.log` lines 15-82):
```text
2026-04-27 00:02:27|INFO|type=prompt|crossing_id=1

你是交通信号配时优化专家。
【cycle_predict_input_json】{
  "prediction": {
    "as_of": "2026-04-27 00:02:27",
    "phase_waits": [
      {
        "phase_id": 1,
        "pred_wait": 0.4,
        "pred_saturation": 0.0083,
        "min_green": 50,
        "max_green": 80,
        "capacity": 48
      },
...
}【/cycle_predict_input_json】
...
--------------------------------------------------------------------------------
```

**Existing result block shape to adapt, not copy blindly** (`reality.log` lines 83-97):
```text
2026-04-27 00:02:33|INFO|type=result|engine=lmstudio|crossing_id=1
RAW:


<SOLUTION>{"1":50,"2":20,"3":45,"4":20}</SOLUTION>
REASONING:
先保持原始相位顺序，并检查每个相位的最小绿灯、最大绿灯与整数秒约束。...
PARSED:
{
  "1": 50,
  "2": 20,
  "3": 45,
  "4": 20
}
--------------------------------------------------------------------------------
```

Phase 12 should render the new model output under `RAW:` as the full protocol, not the old split/missing-think format:
```text
RAW:
<start_working_out>...</end_working_out><SOLUTION>{"1":50,...}</SOLUTION>
PARSED:
{...}
LINT:
{"ok": true, "violations": []}
```
Use `build_user_prompt()` for prompt text instead of copying old prompt text from `reality.log`; old `result` blocks are ignored.

## Shared Patterns

### Protocol / no native think tags
**Source:** `tsc_cycle/prompt_builder.py` lines 22-39, 100-122  
**Apply to:** `tsc_cycle/v4_gates/phase12_reality_test.py`, `tests/test_phase12_reality_log_generation.py`, `reality_test.log`
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

    try:
        parsed = json.loads(match.group("solution").strip())
    except json.JSONDecodeError:
        return "", None

    if not isinstance(parsed, dict):
        return "", None
    if any(isinstance(value, bool) or not isinstance(value, int) for value in parsed.values()):
        return "", None

    return match.group("reasoning").strip(), {str(key): value for key, value in parsed.items()}
```

### Localhost llama-server only
**Source:** `tsc_cycle/student/parity_gguf.py` lines 126-135  
**Apply to:** Phase 12 GGUF replay runner
```python
cmd = [
    str(llama_server),
    "-m", str(gguf_path),
    "--host", "127.0.0.1",
    "--port", str(port),
    "-ngl", str(ngl),
    "-t", str(threads),
    "-c", str(ctx_size),
    "--no-webui",
]
```

### Per-sample cache before final output
**Source:** `tsc_cycle/eval/generate_gguf.py` lines 10-13, 160-173  
**Apply to:** `artifacts/v4/phase12/gen_cache/{sample_id}.json`, then final `reality_test.log` only after gate passes.
```python
out = {
    "sample_id": sid,
    "split_hint": split,
    "backend": label,
    "solution": sol,
    "parse_error": err,
    "raw_text": text,
    "elapsed_sec": meta["elapsed_sec"],
    "n_predict": args.n_predict,
    "seed": 42,
}
(cache_dir / f"{sid}.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
```

### Fail-closed report gates
**Source:** `tsc_cycle/v4_gates/phase11_eval_report.py` lines 184-199  
**Apply to:** Phase 12 report should return nonzero when not all samples parse/lint/pass protocol.
```python
ok = not failures and decision.get("ok") is True
gates = {
    "phase10_handoff": _gate(bool(phase10_report.get("ok") is True and phase10_report.get("next_phase_allowed") is True), None if phase10_report.get("ok") is True else "Phase 10 handoff not green", {"path": str(phase10_path)}),
    "matrix_manifest": _gate(bool(matrix and set((matrix.get("backends") or {}).keys()) == {V4_HF, V4_Q4, V1_Q4}), None if matrix else "matrix manifest failed", {"path": str(manifest_path)}),
    "metrics_json": _gate(bool(metrics_payload and metrics_payload.get("decision_inputs") is not None), None if metrics_payload else "metrics JSON failed", {"path": str(metrics if not isinstance(metrics, dict) else METRICS_PATH)}),
    "decision": _gate(decision.get("ok") is True, None if decision.get("ok") is True else "Phase 11 decision is not GO", {"verdict": decision.get("verdict")}),
    "frozen_v1_read_only": _gate(bool(frozen_path.exists() and not _is_under(GATE_REPORT_PATH, FROZEN_V1_ROOT)), None if frozen_path.exists() else "frozen v1 evidence missing", {"root": str(FROZEN_V1_ROOT)}),
}
```

### Heavy dependencies forbidden in tests / module collection
**Source:** `tests/test_v4_phase11_eval_matrix.py` lines 19-33  
**Apply to:** `tests/test_phase12_reality_log_generation.py`; production module should not import torch/transformers/vllm.
```python
FORBIDDEN_COLLECTION_IMPORTS = {"torch", "transformers", "peft", "bitsandbytes", "vllm", "flash_attn"}

@pytest.fixture(autouse=True)
def _phase11_modules_are_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 11 contracts must never load model/GPU stacks during test execution."""
    real_import = importlib.import_module

    def guarded_import(name: str, package: str | None = None):
        root = name.split(".", 1)[0]
        if root in FORBIDDEN_COLLECTION_IMPORTS:
            raise AssertionError(f"Phase 11 contract imported heavyweight dependency during test execution: {name}")
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", guarded_import)
```

## No Analog Found

All planned files/artifacts have close analogs in the codebase.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| None | — | — | — |

## Metadata

**Analog search scope:** `/home/samuel/TSC_CYCLE/tsc_cycle/**/*.py`, `/home/samuel/TSC_CYCLE/scripts/**/*.sh`, `/home/samuel/TSC_CYCLE/tests/**/*.py`, `/home/samuel/TSC_CYCLE/reality.log`  
**Files scanned:** 126 Python/shell files plus `reality.log` sample  
**Strong analogs read:** 11 files (`generate_gguf.py`, `parity_gguf.py`, `prompt_builder.py`, `constraint_lint.py`, `metrics_constraints.py`, `metrics_reasoning.py`, `phase11_matrix.py`, `phase11_eval_report.py`, `run_v4_phase11_eval_matrix.sh`, `test_v4_phase11_eval_matrix.py`, `reality.log`)  
**Pattern extraction date:** 2026-05-11
