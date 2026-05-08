# Phase 2: 数据扩量到 10K（教师只标新增 7K） - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 13
**Analogs found:** 11 / 13

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tsc_cycle/sample_inputs.py` | utility / data generator | batch, transform, file-I/O | `tsc_cycle/sample_inputs.py` + `tsc_cycle/distribution_fit.py` | exact for same-dist/OOD, role-match for targeted |
| `tsc_cycle/teacher/labeler.py` | service / CLI orchestrator | request-response, batch, file-I/O | `tsc_cycle/teacher/labeler.py` | exact |
| `tsc_cycle/manifest.py` | utility / config-report | batch, file-I/O | `tsc_cycle/manifest.py` + `tsc_cycle/v3_gates/phase1_report.py` | exact |
| `scripts/dist_check.py` | utility / report CLI | batch, transform, file-I/O | `scripts/dist_check.py` | exact |
| `tests/conftest.py` | test fixture module | file-I/O, mock setup | `tests/test_v3_phase1_report.py` + `tests/test_v3_dataset_raw_text.py` | role-match |
| `tests/test_v3_datagen_inputs.py` | test | batch, transform, file-I/O | `tests/test_hashing.py` + `tests/test_constraint_lint.py` + `tests/test_v3_phase1_report.py` | role-match |
| `tests/test_v3_labeler.py` | test | request-response, file-I/O, mock | `tests/test_prompt_builder.py` + `tests/test_v3_dataset_raw_text.py` | partial |
| `tests/test_v3_datagen_merge.py` | test | batch, file-I/O | `tests/test_v3_phase1_report.py` | role-match |
| `data/v3/phase2/inputs_*.jsonl` | generated data artifact | batch, file-I/O | `tsc_cycle/sample_inputs.py` | exact |
| `data/v3/phase2/labeled_new.jsonl` / `rejected_new.jsonl` | generated data artifact | request-response, append-only file-I/O | `tsc_cycle/teacher/labeler.py` | exact |
| `data/v3/phase2/labeled_merged.jsonl` | generated data artifact | batch, file-I/O | `tsc_cycle/teacher/labeler.py` JSONL helpers | partial |
| `data/v3/phase2/datagen_manifest.json` / `merge_report.json` | generated report artifact | batch, file-I/O | `tsc_cycle/manifest.py` + `tsc_cycle/v3_gates/phase1_report.py` | role-match |
| `raw_responses/v3_phase2/*.json` | generated cache artifact | request-response, file-I/O | `tsc_cycle/teacher/client.py` | exact |

## Pattern Assignments

### `tsc_cycle/sample_inputs.py` (utility / data generator, batch + transform + file-I/O)

**Analog:** `tsc_cycle/sample_inputs.py` and `tsc_cycle/distribution_fit.py`

**Imports pattern** (`tsc_cycle/sample_inputs.py` lines 2-11):
```python
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from tsc_cycle.constraint_lint import is_trivial
from tsc_cycle.hashing import sample_id
```

**Same-distribution sampler pattern** (`tsc_cycle/sample_inputs.py` lines 28-56):
```python
def _sample_in_distribution(rng: random.Random, prior: dict[str, Any], crossing_id: int = 1) -> dict:
    pc_keys = list(map(int, prior["phase_count_distribution"].keys()))
    pc_w = list(prior["phase_count_distribution"].values())
    n_phase = rng.choices(pc_keys, weights=pc_w, k=1)[0]

    range_modes = prior["range_modes_top"][:10]
    range_w = [r["count"] for r in range_modes]

    waits = []
    for i in range(n_phase):
        rmode = rng.choices(range_modes, weights=range_w, k=1)[0]
        per_pos = prior["per_position"].get(str(i), {}) or {}
        sat_vals = (per_pos.get("pred_saturation", {}) or {}).get("values_all") \
            or (per_pos.get("pred_saturation", {}) or {}).get("values_sample") or [0.05]
        wait_vals = (per_pos.get("pred_wait", {}) or {}).get("values_all") \
            or (per_pos.get("pred_wait", {}) or {}).get("values_sample") or [1.0]
        cap_vals = (per_pos.get("capacity", {}) or {}).get("values_all") \
            or (per_pos.get("capacity", {}) or {}).get("values_sample") or [40]
        waits.append({
            "phase_id": i + 1,
            "pred_wait": rng.choice(wait_vals),
            "pred_saturation": rng.choice(sat_vals),
            "min_green": int(rmode["min_green"]),
            "max_green": int(rmode["max_green"]),
            "capacity": int(rng.choice(cap_vals)),
        })

    return {"prediction": {"as_of": _ts(rng), "phase_waits": waits, "_crossing_id": crossing_id}}
```

**OOD mutation pattern** (`tsc_cycle/sample_inputs.py` lines 59-114):
```python
def _apply_ood_mutations(rng: random.Random, sample: dict, prior: dict) -> tuple[dict, list[str]]:
    """Mutate an in-distribution sample to satisfy ≥1 OOD dimension."""
    mutations: list[str] = []
    waits = sample["prediction"]["phase_waits"]
    n_dims = rng.randint(1, 2)
    chosen = rng.sample(OOD_DIMENSIONS, k=n_dims)

    for dim in chosen:
        if dim == "phase_count":
            target_n = rng.choice(OOD_PHASE_COUNTS)
            if target_n < len(waits):
                waits = waits[:target_n]
            else:
                template = waits[-1].copy()
                while len(waits) < target_n:
                    template = template.copy()
                    waits.append(template)
            for i, w in enumerate(waits):
                w["phase_id"] = i + 1
        elif dim == "range_combo":
            seen_combos = {(r["min_green"], r["max_green"]) for r in prior["range_modes_top"]}
            for w in waits:
                while True:
                    mn = rng.choice(OOD_MIN_VALUES)
                    mx = rng.choice(OOD_MAX_VALUES)
                    if mn < mx and (mn, mx) not in seen_combos:
                        w["min_green"], w["max_green"] = mn, mx
                        break
```

**Dedupe + tagging + JSONL write pattern** (`tsc_cycle/sample_inputs.py` lines 127-168):
```python
def sample(prior: dict, n_id: int, n_ood: int, seed: int = 42) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    id_samples: list[dict] = []
    ood_samples: list[dict] = []
    seen: set[str] = set()

    while len(id_samples) < n_id:
        rng_local = random.Random(rng.random())
        s = _sample_in_distribution(rng_local, prior)
        sid = sample_id(s)
        if sid in seen:
            continue
        seen.add(sid)
        s["sample_id"] = sid
        s["split_hint"] = "id"
        s["trivial"] = is_trivial(s)
        id_samples.append(s)

def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
```

**Log/eval artifact extraction style** (`tsc_cycle/distribution_fit.py` lines 28-48):
```python
def iter_prompts(log_path: Path):
    """Yield each (crossing_id, prediction_dict) embedded in reality.log."""
    text = log_path.read_text(encoding="utf-8", errors="replace")
    blocks = text.split("\n--------------------------------------------------------------------------------\n")
    for blk in blocks:
        if "type=prompt" not in blk:
            continue
        m = re.search(r"crossing_id=(\d+)", blk)
        crossing_id = int(m.group(1)) if m else -1
        i = blk.find(JSON_OPEN)
        if i < 0:
            continue
        i += len(JSON_OPEN)
        j = blk.find(JSON_CLOSE, i)
        if j < 0:
            continue
        try:
            data = json.loads(blk[i:j])
        except json.JSONDecodeError:
            continue
        yield crossing_id, data
```

**Planner notes:** Extend the existing sampler rather than creating a parallel generator. For Phase 2, add source tags (`same_dist`, `ood`, `targeted`), exclude old IDs via `hashing.sample_id()`, and write only under `data/v3/phase2/`.

---

### `tsc_cycle/teacher/labeler.py` (service / CLI orchestrator, request-response + append-only file-I/O)

**Analog:** `tsc_cycle/teacher/labeler.py`

**Imports pattern** (lines 17-29):
```python
import argparse
import json
import os
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tsc_cycle.constraint_lint import validate
from tsc_cycle.prompt_builder import build_user_prompt
from tsc_cycle.teacher.client import TeacherClient
```

**JSONL resume / done-set pattern** (lines 36-56):
```python
def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_done_ids(*paths: Path) -> set[str]:
    ids: set[str] = set()
    for p in paths:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if "sample_id" in obj:
                    ids.add(obj["sample_id"])
            except json.JSONDecodeError:
                continue
    return ids
```

**CLI + environment preflight pattern** (lines 59-75):
```python
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default="data/inputs.jsonl")
    ap.add_argument("--ood-inputs", default="data/ood_inputs.jsonl")
    ap.add_argument("--labeled", default="data/labeled.jsonl")
    ap.add_argument("--rejected", default="data/rejected.jsonl")
    ap.add_argument("--cost-out", default="runs/latest/teacher_cost.json")
    ap.add_argument("--reject-stats", default="runs/latest/teacher_reject_stats.json")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit; useful for 50-sample smoke")
    ap.add_argument("--model", default="gpt-5.5")
    ap.add_argument("--effort", default="high")
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set; aborting.", file=sys.stderr)
        return 2
```

**Prompt → API → lint → accepted/rejected record pattern** (lines 105-124):
```python
def process(s: dict) -> dict:
    prompt = build_user_prompt(s)
    res = client.call(prompt)
    record = {
        "sample_id": s["sample_id"],
        "split_hint": s.get("split_hint", "id"),
        "trivial": s.get("trivial", False),
        "ood_dims": s.get("ood_dims", []),
        "input": s,
        "result": res.to_dict(),
    }
    if not res.success:
        record["reject_reason"] = res.error or "api_failure"
        return {"ok": False, "record": record, "reject_kind": "api_or_usage"}
    cl = validate(s, res.solution or {})
    if not cl.ok:
        record["reject_reason"] = "constraint_violation"
        record["violations"] = cl.violations
        return {"ok": False, "record": record, "reject_kind": cl.violations[0]["kind"] if cl.violations else "unknown"}
    return {"ok": True, "record": record, "reject_kind": None}
```

**ThreadPool + append+flush pattern** (lines 126-151):
```python
with ThreadPoolExecutor(max_workers=args.workers) as ex:
    futs = [ex.submit(process, s) for s in pending]
    for i, fut in enumerate(as_completed(futs)):
        r = fut.result()
        rec = r["record"]
        u = (rec["result"].get("usage") or {})
        total_input_tokens += u.get("input_tokens", 0) or 0
        total_completion_tokens += u.get("output_tokens", 0) or 0
        rsn = ((u.get("output_tokens_details") or {}).get("reasoning_tokens") or 0)
        total_reasoning_tokens += rsn
        if r["ok"]:
            with lab_lock:
                lab_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                lab_f.flush()
            n_ok += 1
        else:
            reject_kinds[r["reject_kind"] or "unknown"] += 1
            with rej_lock:
                rej_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                rej_f.flush()
            n_rej += 1
```

**Cost/reject report pattern** (lines 156-178):
```python
cost = {
    "model": args.model,
    "effort": args.effort,
    "elapsed_s": elapsed,
    "n_ok": n_ok,
    "n_rej": n_rej,
    "reject_rate": n_rej / max(n_ok + n_rej, 1),
    "input_tokens": total_input_tokens,
    "completion_tokens": total_completion_tokens,
    "reasoning_tokens": total_reasoning_tokens,
    "estimated_usd_input": cost_in,
    "estimated_usd_output": cost_out,
    "estimated_usd_total": cost_in + cost_out,
}
Path(args.cost_out).write_text(json.dumps(cost, indent=2), encoding="utf-8")
Path(args.reject_stats).parent.mkdir(parents=True, exist_ok=True)
Path(args.reject_stats).write_text(json.dumps(dict(reject_kinds), indent=2), encoding="utf-8")
```

**Planner notes:** Keep this file as the Phase 2 labeler entry point. Add new CLI args by following existing argparse style: `--input-files`, `--exclude-labeled`, `--cache-dir`, and hard-fail or clamp if `--workers > 10`. Never allow Phase 2 output path to equal protected `data/labeled.jsonl`.

---

### `tsc_cycle/teacher/client.py` (API client / service, request-response + cache file-I/O)

**Analog:** `tsc_cycle/teacher/client.py`

**Dataclass config + cache dir pattern** (lines 65-85):
```python
@dataclass
class TeacherClient:
    model: str = "gpt-5.5"
    reasoning_effort: str = "high"
    timeout: float = 300.0
    max_retries: int = 3
    base_backoff: float = 2.0
    cache_dir: Path = field(default_factory=lambda: Path("raw_responses"))
    api_key: str | None = None
    base_url: str | None = None
    require_reasoning_tokens_min: int = 100  # TCH-02

    def __post_init__(self) -> None:
        kwargs: dict[str, Any] = {}
        kwargs["api_key"] = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not kwargs["api_key"]:
            raise RuntimeError("OPENAI_API_KEY not set")
        kwargs["base_url"] = self.base_url or os.environ.get("OPENAI_BASE_URL")
        kwargs["timeout"] = self.timeout
        self._client = OpenAI(**{k: v for k, v in kwargs.items() if v is not None})
        self.cache_dir.mkdir(parents=True, exist_ok=True)
```

**Responses API call pattern** (lines 110-126):
```python
def _call_responses(self, prompt: str) -> tuple[str, dict, dict]:
    """Return (output_text, raw_dict, usage_dict)."""
    resp = self._client.responses.create(
        model=self.model,
        input=prompt,
        reasoning={"effort": self.reasoning_effort},
    )
    raw = resp.model_dump()
    text = ""
    for o in resp.output:
        if getattr(o, "type", None) == "message":
            for c in (getattr(o, "content", None) or []):
                if getattr(c, "type", None) == "output_text":
                    text += c.text or ""
    usage = raw.get("usage") or {}
    return text, raw, usage
```

**Cache hit + parse + store pattern** (lines 128-141 and 170-186):
```python
if not force:
    cached = self._load_cache(prompt)
    if cached:
        p = cached["parsed"]
        return TeacherResult(
            success=True,
            reasoning=p["reasoning"],
            solution=p["solution"],
            raw=cached["raw"],
            usage=cached["raw"].get("usage"),
            response_id=cached["raw"].get("id", ""),
        )

reasoning, solution = parse_assistant_output(text)
if solution is None:
    raise ValueError(f"no parseable SOLUTION block in response (text head: {text[:200]!r})")

parsed = {"reasoning": reasoning, "solution": {str(k): int(v) for k, v in solution.items()}}
payload = {"parsed": parsed, "raw": raw}
self._store_cache(prompt, payload)
```

**Rate limit + retry pattern** (lines 188-210):
```python
except RateLimitError as e:
    wait = 60.0
    hdrs = getattr(getattr(e, "response", None), "headers", None) or {}
    if hdrs.get("Retry-After"):
        try:
            wait = float(hdrs["Retry-After"])
        except ValueError:
            pass
    last_err = f"ratelimit:{e!s}"
    time.sleep(min(wait, 120.0))
    attempts -= 1  # do not count
    continue
except (APITimeoutError, APIConnectionError, APIError, BadRequestError) as e:
    last_err = f"{type(e).__name__}:{e!s}"
    if attempt + 1 < self.max_retries:
        time.sleep(self.base_backoff * (2**attempt))
    continue
```

**Planner notes:** Do not hand-roll another OpenAI client. Phase 2 labeler should pass `cache_dir=Path(args.cache_dir)` into this existing client.

---

### `tsc_cycle/manifest.py` (manifest utility, batch + file-I/O)

**Analog:** `tsc_cycle/manifest.py` and `tsc_cycle/v3_gates/phase1_report.py`

**Imports and hash dependency pattern** (`tsc_cycle/manifest.py` lines 4-12):
```python
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tsc_cycle.hashing import canonical_json, sha256_hex
```

**Git SHA + run dir pattern** (`tsc_cycle/manifest.py` lines 14-32):
```python
def git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=os.getcwd(), text=True, stderr=subprocess.DEVNULL
        )
        return out.strip()
    except Exception:
        return "unknown"


def now_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def make_run_dir(run_id: str | None = None, base: str = "runs") -> Path:
    rid = run_id or now_run_id()
    p = Path(base) / rid
    p.mkdir(parents=True, exist_ok=True)
    return p
```

**Manifest write/update pattern** (`tsc_cycle/manifest.py` lines 35-57):
```python
def write_manifest(run_dir: Path, config: dict[str, Any], stages: dict[str, str]) -> Path:
    payload = {
        "git_sha": git_sha(),
        "config_hash": sha256_hex(canonical_json(config)),
        "config": config,
        "stages": stages,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    out = run_dir / "manifest.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def update_stage(run_dir: Path, stage: str, status: str, **extra: Any) -> None:
    p = run_dir / "manifest.json"
    if not p.exists():
        raise FileNotFoundError(p)
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("stages", {})[stage] = status
    if extra:
        data.setdefault("stage_details", {})[stage] = extra
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
```

**Gate/report JSON writer pattern** (`tsc_cycle/v3_gates/phase1_report.py` lines 161-168):
```python
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = evaluate_gates(args.artifacts, args.gguf_report)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1
```

**Planner notes:** Put Phase 2 provenance helpers here if source code is needed. Manifest/report fields should include old SHA before/after, old count, new valid count, merged valid count, overlap counts, reject counts, source distribution counts, and output paths. Do not serialize API keys.

---

### `scripts/dist_check.py` (report CLI, transform + file-I/O)

**Analog:** `scripts/dist_check.py`

**CLI + file collection pattern** (lines 62-75):
```python
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default="data/inputs.jsonl")
    ap.add_argument("--ood", default="data/ood_inputs.jsonl")
    ap.add_argument("--log", default="reality.log")
    ap.add_argument("--out", default="data/dist_check_report.md")
    args = ap.parse_args()

    ref = collect_log_values(Path(args.log))
    id_vals = collect_jsonl_values(Path(args.id))
    ood_vals = collect_jsonl_values(Path(args.ood))

    id_rows = ks_report("same_dist", id_vals, ref)
    ood_rows = ks_report("ood", ood_vals, ref)
```

**Markdown report write pattern** (lines 84-128):
```python
lines = [
    "# Distribution Check Report",
    "",
    f"Reference: `{args.log}`",
    f"Same-dist: `{args.id}` ({sum(r['n_sample'] for r in id_rows[:1])} samples worth of values per field)",
    f"OOD:       `{args.ood}`",
    "",
    "## Same-dist KS test (target: p > 0.05 on every field)",
    "",
    "| Field | n_sample | n_ref | KS | p-value | pass |",
    "|---|---|---|---|---|---|",
]
# ... append rows ...
Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {args.out}")
```

**Planner notes:** If Phase 2 needs a datagen report generator, copy this CLI/report style but write under `data/v3/phase2/datagen_report.md`.

---

### `tests/conftest.py` (test fixtures, file-I/O + mocks)

**Analog:** `tests/test_v3_phase1_report.py` and `tests/test_v3_dataset_raw_text.py`

**Temp file helper pattern** (`tests/test_v3_phase1_report.py` lines 7-12):
```python
def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
```

**Fixture builder pattern** (`tests/test_v3_phase1_report.py` lines 13-67):
```python
def passing_artifacts(tmp_path: Path) -> tuple[Path, Path]:
    artifacts = tmp_path / "artifacts"
    gguf = tmp_path / "gguf_microconvert.json"
    exe = tmp_path / "llama-tokenize"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    exe.chmod(0o755)
    tokenizer_gguf = tmp_path / "tokenizer.gguf"
    q4_gguf = tmp_path / "model.q4_K_M.gguf"
    tokenizer_gguf.write_text("gguf", encoding="utf-8")
    q4_gguf.write_text("gguf", encoding="utf-8")
    # ... write JSON artifacts ...
    return artifacts, gguf
```

**Fake dependency pattern** (`tests/test_v3_dataset_raw_text.py` lines 16-33):
```python
class FakeTokenizer:
    eos_token = "<eos>"

    def __init__(self):
        self.chat_template_used = False

    def apply_chat_template(self, *args, **kwargs):
        self.chat_template_used = True
        raise AssertionError("apply_chat_template must not be used for v3 SFT raw-text assembly")

    def encode(self, text, add_special_tokens=False):
        assert add_special_tokens is False
        if text == "<think>":
            return [99]
        if text == "</think>":
            return [100]
        return [ord(ch) + 1000 for ch in text]
```

**Planner notes:** Use `tmp_path` fixtures and small synthetic JSONL files. Keep tests pure and avoid real OpenAI calls.

---

### `tests/test_v3_datagen_inputs.py` (test, batch + transform + file-I/O)

**Analogs:** `tests/test_hashing.py`, `tests/test_constraint_lint.py`, `tests/test_v3_phase1_report.py`

**Hash identity assertion pattern** (`tests/test_hashing.py` lines 3-31):
```python
def test_canonical_json_stable_ordering():
    a = {"b": 2, "a": 1, "nested": {"y": 1, "x": 0}}
    b = {"a": 1, "b": 2, "nested": {"x": 0, "y": 1}}
    assert canonical_json(a) == canonical_json(b)


def test_sample_id_deterministic():
    obj = {"prediction": {"as_of": "2026-04-27", "phase_waits": [{"phase_id": 1}]}}
    assert sample_id(obj) == sample_id(obj)
    assert len(sample_id(obj)) == 64


def test_prompt_hash_includes_model_and_effort():
    p = "hello"
    assert prompt_hash(p, "gpt-5.5", "high") != prompt_hash(p, "gpt-5.5", "low")
    assert prompt_hash(p, "gpt-5.5", "high") != prompt_hash(p, "gpt-5", "high")
```

**Minimal input factory pattern** (`tests/test_constraint_lint.py` lines 3-8):
```python
def _input(phases):
    return {"prediction": {"phase_waits": [
        {"phase_id": pid, "min_green": mn, "max_green": mx,
         "pred_wait": 1.0, "pred_saturation": 0.05, "capacity": 30}
        for pid, mn, mx in phases
    ]}}
```

**Planner notes:** Test source ratios, source tags, old-ID exclusion, self-dedupe, targeted seed provenance, and no direct reuse of eval seed IDs.

---

### `tests/test_v3_labeler.py` (test, request-response + file-I/O + mock)

**Analogs:** `tests/test_prompt_builder.py`, `tests/test_v3_dataset_raw_text.py`, `tsc_cycle/teacher/labeler.py`

**Protocol parse tests pattern** (`tests/test_prompt_builder.py` lines 48-75):
```python
def test_full_assistant_roundtrip():
    txt = build_full_assistant("reasoning text", {"1": 60, "2": 30})
    assert txt.startswith(TAG_THINK_OPEN)
    assert TAG_THINK_CLOSE in txt
    assert TAG_SOLUTION_OPEN in txt and TAG_SOLUTION_CLOSE in txt
    reasoning, solution = parse_assistant_output(txt)
    assert reasoning == "reasoning text"
    assert solution == {"1": 60, "2": 30}


def test_parse_missing_solution_returns_none():
    body = TAG_THINK_OPEN + "thinking" + TAG_THINK_CLOSE
    r, s = parse_assistant_output(body)
    assert s is None
```

**Negative assertion style** (`tests/test_prompt_builder.py` lines 121-135):
```python
def test_user_prompt_no_old_close_tag():
    p = build_user_prompt(EX_INPUT)
    assert "</end_working_out>" not in p
    assert "<end_working_out>" in p


def test_full_assistant_uses_new_close_tag():
    txt = build_full_assistant("r", {"1": 60})
    assert "</end_working_out>" not in txt
    assert "<end_working_out>" in txt
```

**Planner notes:** Mock `TeacherClient.call()` to return success/failure objects. Assert workers >10 fails, `effort` defaults high, lint failures are written to rejected and never requeued, done IDs from labeled+rejected are skipped, and cache-dir is passed to the client constructor.

---

### `tests/test_v3_datagen_merge.py` (test, batch + file-I/O)

**Analog:** `tests/test_v3_phase1_report.py`

**Gate evaluation assertion pattern** (lines 70-89):
```python
def test_all_gates_passing_allows_next_phase(tmp_path: Path):
    artifacts, gguf = passing_artifacts(tmp_path)

    report = evaluate_gates(artifacts, gguf)

    assert report["ok"] is True
    assert report["next_phase_allowed"] is True
    assert report["fatal_failures"] == []
    assert report["requirements_covered"] == [
        "ENV-01",
        "ENV-02",
        "ENV-03",
        "TOK-01",
        "TOK-02",
        "TOK-03",
        "TOK-04",
        "MEM-01",
        "MEM-02",
        "MEM-03",
    ]
```

**Failure case pattern** (lines 92-119):
```python
def test_tokenizer_parity_99_fails(tmp_path: Path):
    artifacts, gguf = passing_artifacts(tmp_path)
    write_json(artifacts / "tokenizer_parity.json", {"ok": True, "matched": 99, "mismatched": 1, "parse_failed": 0, "gguf": "x"})

    report = evaluate_gates(artifacts, gguf)

    assert report["ok"] is False
    assert any(item["gate"] == "tokenizer_parity" for item in report["fatal_failures"])
```

**Planner notes:** Mirror the Phase 1 gate style for Phase 2 merge gates: old SHA unchanged, new valid ≥6000, merged valid ≥9000, old/new overlap zero, all new accepted rows pass `constraint_lint.validate()`.

---

## Shared Patterns

### Canonical sample identity

**Source:** `tsc_cycle/hashing.py` lines 9-20  
**Apply to:** sampler, dedupe, targeted perturbation, merge gates, tests
```python
def canonical_json(obj: Any) -> str:
    """Stable JSON encoding: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sample_id(input_obj: Any) -> str:
    """Sample ID = sha256 of the canonical input JSON. Stable across runs."""
    return sha256_hex(canonical_json(input_obj))
```

### Hard-constraint lint gate

**Source:** `tsc_cycle/constraint_lint.py` lines 34-89  
**Apply to:** labeler accept/reject path, merge validation, tests
```python
def validate(prediction_input: dict[str, Any], output: Any) -> LintResult:
    result = LintResult(ok=True)

    if not isinstance(output, dict):
        result.add(Violation.NOT_DICT, got=type(output).__name__)
        return result

    waits = prediction_input.get("prediction", {}).get("phase_waits", [])
    expected_ids = [str(w["phase_id"]) for w in waits]

    output_keys = list(output.keys())
    if set(output_keys) != set(expected_ids):
        result.add(Violation.PHASE_MISMATCH, expected=expected_ids, got=output_keys)
        return result

    if output_keys != expected_ids:
        result.add(Violation.PHASE_ORDER, expected=expected_ids, got=output_keys)

    for w in waits:
        pid = str(w["phase_id"])
        v = output.get(pid)
        if isinstance(v, bool) or not isinstance(v, int):
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

### Prompt protocol and parser

**Source:** `tsc_cycle/prompt_builder.py` lines 21-31, 62-72, 90-125  
**Apply to:** teacher calls, tests, raw response parsing; do not change prompt text in Phase 2
```python
TAG_THINK_OPEN = "<start_working_out>"
TAG_THINK_CLOSE = "<end_working_out>"
TAG_SOLUTION_OPEN = "<SOLUTION>"
TAG_SOLUTION_CLOSE = "</SOLUTION>"
LEGACY_THINK_CLOSE = "</end_working_out>"
SYSTEM_PROMPT = "你是交通信号配时优化专家。"


def build_user_prompt(prediction_input: dict[str, Any]) -> str:
    input_json = json.dumps(prediction_input, indent=2, ensure_ascii=False)
    return USER_TEMPLATE.format(system=SYSTEM_PROMPT, input_json=input_json)


def parse_assistant_output(text: str) -> tuple[str, dict[str, int] | None]:
    if LEGACY_THINK_CLOSE in text:
        return "", None
    # parse reasoning and SOLUTION blocks; return solution=None on bad/missing JSON
```

### Append-only progress and resume safety

**Source:** `tsc_cycle/teacher/labeler.py` lines 42-56 and 126-151  
**Apply to:** full label run, smoke run, any generated JSONL progress
```python
done = _read_done_ids(Path(args.labeled), Path(args.rejected))
pending = [s for s in all_inputs if s["sample_id"] not in done]

with ThreadPoolExecutor(max_workers=args.workers) as ex:
    futs = [ex.submit(process, s) for s in pending]
    for i, fut in enumerate(as_completed(futs)):
        r = fut.result()
        if r["ok"]:
            with lab_lock:
                lab_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                lab_f.flush()
        else:
            with rej_lock:
                rej_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                rej_f.flush()
```

### API cache namespace and atomic cache writes

**Source:** `tsc_cycle/teacher/client.py` lines 89-106  
**Apply to:** `raw_responses/v3_phase2/` isolated cache
```python
def cache_path(self, prompt: str) -> Path:
    ph = prompt_hash(prompt, self.model, self.reasoning_effort)
    return self.cache_dir / f"{ph}.json"


def _store_cache(self, prompt: str, payload: dict) -> None:
    p = self.cache_path(prompt)
    tmp = p.with_suffix(".json.tmp." + sha256_hex(str(time.time()))[:8])
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)
```

### JSON report / manifest style

**Source:** `tsc_cycle/manifest.py` lines 35-45 and `tsc_cycle/v3_gates/phase1_report.py` lines 161-168  
**Apply to:** `datagen_manifest.json`, `merge_report.json`, gate reports
```python
payload = {
    "git_sha": git_sha(),
    "config_hash": sha256_hex(canonical_json(config)),
    "config": config,
    "stages": stages,
    "created_at": datetime.now(timezone.utc).isoformat(),
}
out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
```

## No Analog Found

| File / Capability | Role | Data Flow | Reason |
|-------------------|------|-----------|--------|
| Targeted sampler from `runs/20260507T032419Z/eval/per_sample.jsonl` high-MAE / lint-fail rows | utility / data generator | batch, transform | No existing code selects eval failure seeds and perturbs neighborhoods. Use `sample_inputs.py` mutation style + `distribution_fit.py` file parsing style. |
| Exact Phase 2 merge builder for frozen v1 + isolated new labels | utility / data assembler | batch, file-I/O | No dedicated dataset merge helper exists. Use JSONL helpers from `labeler.py`, identity from `hashing.py`, lint from `constraint_lint.py`, and manifest/report style from `manifest.py`. |

## Metadata

**Analog search scope:** `/home/samuel/TSC_CYCLE/tsc_cycle`, `/home/samuel/TSC_CYCLE/tests`, `/home/samuel/TSC_CYCLE/scripts`  
**Files scanned:** 46 Python/shell/toml files  
**Pattern extraction date:** 2026-05-08
