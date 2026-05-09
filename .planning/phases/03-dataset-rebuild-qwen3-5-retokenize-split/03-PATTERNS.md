# Phase 03: Dataset Rebuild（Qwen3.5 retokenize + split） - Pattern Map

**Mapped:** 2026-05-09
**Files analyzed:** 10
**Analogs found:** 7 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tsc_cycle/v3_gates/dataset_rebuild_v3.py` | utility / local CLI | batch + transform + file-I/O | `tsc_cycle/v3_gates/phase2_datagen_report.py`; `tsc_cycle/student/dataset.py`; `tsc_cycle/v3_gates/tokenizer_parity_v3.py` | role-match |
| `tests/test_v3_dataset_rebuild.py` | test | batch + file-I/O validation | `tests/test_v3_datagen_merge.py`; `tests/test_v3_dataset_raw_text.py`; `tests/test_v3_tokenizer_parity.py` | role-match |
| `data/splits/v3/train.index.jsonl` | data artifact | file-I/O + batch | `tsc_cycle/v3_gates/phase2_datagen_report.py` JSONL writer pattern | partial |
| `data/splits/v3/val.index.jsonl` | data artifact | file-I/O + batch | `tsc_cycle/v3_gates/phase2_datagen_report.py` JSONL writer pattern | partial |
| `data/splits/v3/ood_val.index.jsonl` | data artifact | file-I/O + batch | `tsc_cycle/v3_gates/phase2_datagen_report.py` JSONL writer pattern | partial |
| `data/splits/v3/manifest.json` | config / manifest artifact | file-I/O + batch | `tsc_cycle/v3_gates/memory_budget_v3.py`; `tsc_cycle/v3_gates/env_smoke_v3.py` JSON artifact writers | partial |
| `data/splits/v3/v1_ood_alignment.json` | data artifact | file-I/O + validation | `tsc_cycle/v3_gates/phase2_datagen_report.py` report/gate evidence pattern | partial |
| `data/tokenized/v3/train.arrow` | data artifact | transform + file-I/O | `tsc_cycle/student/dataset.py` PyArrow table construction; no in-code Arrow IPC writer | partial / no exact analog |
| `data/tokenized/v3/val.arrow` | data artifact | transform + file-I/O | `tsc_cycle/student/dataset.py` PyArrow table construction; no in-code Arrow IPC writer | partial / no exact analog |
| `data/tokenized/v3/ood_val.arrow` | data artifact | transform + file-I/O | `tsc_cycle/student/dataset.py` PyArrow table construction; no in-code Arrow IPC writer | partial / no exact analog |

## Pattern Assignments

### `tsc_cycle/v3_gates/dataset_rebuild_v3.py` (utility/local CLI, batch + transform + file-I/O)

**Primary analogs:**
- `tsc_cycle/v3_gates/phase2_datagen_report.py` for fail-closed JSONL ingestion, validation gates, artifact writes, argparse CLI.
- `tsc_cycle/student/dataset.py` for raw prompt + assistant construction, tokenization, label masking, PyArrow table schema.
- `tsc_cycle/v3_gates/tokenizer_parity_v3.py` for deterministic `random.Random(seed).sample(...)` fixture selection and tokenizer load.
- `tsc_cycle/hashing.py` for canonical SHA-256 helpers.

**Imports / module layout pattern** (`tsc_cycle/v3_gates/phase2_datagen_report.py` lines 0-10):
```python
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tsc_cycle.constraint_lint import validate
```

**Add Phase 3 imports by copying project style from `tsc_cycle/student/dataset.py` lines 20-34:**
```python
import pyarrow as pa
import pyarrow.parquet as pq
from transformers import AutoTokenizer

from tsc_cycle.prompt_builder import (
    TAG_SOLUTION_CLOSE,
    TAG_THINK_OPEN,
    build_full_assistant,
    build_user_prompt,
)
from tsc_cycle.tokenizer_check import (
    assert_no_native_think_in_ids,
    check_tokenizer,
    native_think_token_ids,
)
```
For Phase 3, keep `pyarrow as pa`, `AutoTokenizer`, `build_full_assistant`, `build_user_prompt`, `native_think_token_ids`, `assert_no_native_think_in_ids`; replace Parquet write with Arrow IPC from RESEARCH.md because no in-repo IPC writer exists.

**JSONL read / fail-closed parse pattern** (`tsc_cycle/v3_gates/phase2_datagen_report.py` lines 50-68):
```python
def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"missing JSONL artifact: {path}"]

    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"malformed JSONL {path}:{line_no}: {exc}")
            continue
        if not isinstance(row, dict):
            errors.append(f"JSONL row must be an object {path}:{line_no}")
            continue
        rows.append(row)
    return rows, errors
```

**Existing record accessors to copy/adapt** (`tsc_cycle/v3_gates/phase2_datagen_report.py` lines 71-113):
```python
def _record_sample_id(record: dict[str, Any]) -> str | None:
    sample_id = record.get("sample_id")
    if sample_id is None and isinstance(record.get("input"), dict):
        sample_id = record["input"].get("sample_id")
    return str(sample_id) if sample_id is not None else None


def _record_input(record: dict[str, Any]) -> dict[str, Any]:
    candidate = record.get("input")
    if isinstance(candidate, dict):
        return candidate
    return record


def _record_solution(record: dict[str, Any]) -> Any:
    result = record.get("result")
    if isinstance(result, dict):
        return result.get("solution")
    return record.get("solution")


def _record_result_success(record: dict[str, Any]) -> bool:
    result = record.get("result")
    if isinstance(result, dict) and "success" in result:
        return result.get("success") is True
    return _record_solution(record) is not None


def _record_source(record: dict[str, Any]) -> str:
    for container in (record, _record_input(record)):
        if not isinstance(container, dict):
            continue
        for key in ("source", "source_tag", "split_hint"):
            value = container.get(key)
            if value:
                return str(value)
        metadata = container.get("metadata")
        if isinstance(metadata, dict):
            for key in ("source", "source_tag"):
                value = metadata.get(key)
                if value:
                    return str(value)
    return "unknown"
```

**Gate aggregation pattern** (`tsc_cycle/v3_gates/phase2_datagen_report.py` lines 152-163):
```python
def _add_gate(
    gates: dict[str, Any],
    fatal_failures: list[dict[str, str]],
    name: str,
    passed: bool,
    reason: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    gates[name] = {"ok": bool(passed), "reason": reason, "data": data or {}}
    if not passed:
        fatal_failures.append(_failure(name, reason or "failed"))
```

**Constraint lint pattern** (`tsc_cycle/v3_gates/phase2_datagen_report.py` lines 236-247):
```python
valid_new_rows: list[dict[str, Any]] = []
lint_failures: list[dict[str, Any]] = []
for index, row in enumerate(new_rows):
    sample_id = _record_sample_id(row) or f"row:{index}"
    if not _record_result_success(row):
        lint_failures.append({"sample_id": sample_id, "violations": [{"kind": "result_not_success"}]})
        continue
    lint_result = validate(_record_input(row), _record_solution(row))
    if lint_result.ok:
        valid_new_rows.append(row)
    else:
        lint_failures.append({"sample_id": sample_id, "violations": lint_result.violations})
```

**Raw SFT text builder pattern** (`tsc_cycle/student/dataset.py` lines 57-61):
```python
def build_text(input_obj: dict, reasoning: str, solution: dict[str, int]) -> tuple[str, str]:
    """Returns raw (prompt_text, assistant_text); no tokenizer chat template is used."""
    prompt = build_user_prompt(input_obj)
    assistant = build_full_assistant(reasoning, solution)
    return prompt, assistant
```

**Full assistant format source of truth** (`tsc_cycle/prompt_builder.py` lines 81-87):
```python
def build_full_assistant(reasoning: str, solution: dict[str, int]) -> str:
    """Assemble a full assistant turn for SFT training."""
    sol_json = json.dumps(solution, ensure_ascii=False)
    return (
        f"{TAG_THINK_OPEN}{reasoning}{TAG_THINK_CLOSE}"
        f"{TAG_SOLUTION_OPEN}{sol_json}{TAG_SOLUTION_CLOSE}"
    )
```

**Tokenize + loss-mask pattern** (`tsc_cycle/student/dataset.py` lines 64-89):
```python
def tokenize_one(tokenizer, prompt: str, assistant: str, max_length: int) -> dict[str, list[int] | bool | dict]:
    """Tokenize prompt+assistant raw text; mask prompt with -100 in labels."""
    native_ids = native_think_token_ids(tokenizer)
    full = prompt + "\n" + assistant + tokenizer.eos_token
    enc = tokenizer(full, truncation=True, max_length=max_length, add_special_tokens=False)
    input_ids = enc["input_ids"]

    # Find the boundary: tokenize prompt-only (with the trailing \n), then assistant text begins after.
    pre = tokenizer(prompt + "\n", add_special_tokens=False)["input_ids"]
    n_prompt = len(pre)

    labels = [-100] * len(input_ids)
    for i in range(n_prompt, len(input_ids)):
        labels[i] = input_ids[i]

    # Native think token id leakage check: must NOT appear anywhere in input_ids.
    assert_no_native_think_in_ids(input_ids, native_ids=native_ids)

    metadata = dataset_wiring_metadata()
    return {
        "input_ids": input_ids,
        "attention_mask": [1] * len(input_ids),
        "labels": labels,
        "chat_template_used": metadata["chat_template_used"],
        "metadata": metadata,
    }
```
Phase 3 should harden this pattern by computing untruncated `raw_ids` first, checking native think leakage on raw IDs, recording `raw_len`, then truncating to `max_seq_length=2048`.

**PyArrow table schema pattern** (`tsc_cycle/student/dataset.py` lines 175-185):
```python
table = pa.table({
    "sample_id": [r["sample_id"] for r in rows_tok],
    "input_ids": [r["input_ids"] for r in rows_tok],
    "attention_mask": [r["attention_mask"] for r in rows_tok],
    "labels": [r["labels"] for r in rows_tok],
    "trivial": [r["trivial"] for r in rows_tok],
})
sp_dir = out_root / split
sp_dir.mkdir(exist_ok=True)
pq.write_table(table, sp_dir / "data.parquet")
print(f"wrote {sp_dir}/data.parquet ({len(rows_tok)} rows)")
```
Use the table columns from this excerpt, but write `data/tokenized/v3/{split}.arrow` using `pa.ipc.new_file` from RESEARCH.md instead of `pq.write_table`.

**Deterministic seed sampling pattern** (`tsc_cycle/v3_gates/tokenizer_parity_v3.py` lines 171-197):
```python
def build_prompt_fixture(
    labeled_path: Path = DEFAULT_LABELED,
    ood_inputs_path: Path | None = DEFAULT_OOD_INPUTS,
    out_path: Path = DEFAULT_PROMPT_FIXTURE,
    n: int = DEFAULT_N,
    seed: int = DEFAULT_SEED,
) -> list[dict[str, str]]:
    candidates = _candidate_prompts(labeled_path, ood_inputs_path)
    if len(candidates) < n:
        base = len(candidates)
        for idx in range(n - base):
            payload = _synthetic_boundary_inputs()[idx % len(_synthetic_boundary_inputs())]
            record = {
                "prompt_id": f"synthetic_boundary:repeat:{idx:03d}",
                "source": "synthetic_boundary",
                "text": build_user_prompt(payload),
            }
            candidates.append(record)
        candidates.sort(key=lambda row: row["prompt_id"])

    selected = random.Random(seed).sample(candidates, n)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for row in selected:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
    return selected
```
For Phase 3, apply the same sorted-candidate + `random.Random(42).sample(...)` pattern to select exactly 650 new OOD IDs and 950 val IDs.

**Tokenizer loading pattern** (`tsc_cycle/v3_gates/tokenizer_parity_v3.py` lines 296-299):
```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(args.model)
```
Use `Qwen/Qwen3.5-9B` and do not reinstall or change package versions.

**Max sequence artifact source** (`artifacts/v3/phase1/memory_budget.json` lines 81-83):
```json
"selected_max_seq": 2048,
"selection_reason": "2048 is the largest candidate with both step-1 reserved memory below 85GB and successful 100-step dry-run under run_safe 100G; 2560 passed step-1 but failed 100-step with systemd oom-kill.",
"seq": null,
```
Phase 3 should read this artifact or fail closed if unavailable/malformed; do not choose a new cap.

**JSON artifact writer pattern** (`tsc_cycle/v3_gates/memory_budget_v3.py` lines 98-102):
```python
def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
```

**CLI parser + main pattern** (`tsc_cycle/v3_gates/phase2_datagen_report.py` lines 438-488):
```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Phase 2 v3 datagen merge report and fail-closed merged JSONL")
    parser.add_argument("--old-labeled", default="data/labeled.jsonl")
    parser.add_argument("--new-labeled", default="data/v3/phase2/labeled_new.jsonl")
    parser.add_argument("--rejected", default="data/v3/phase2/rejected_new.jsonl")
    parser.add_argument("--datagen-manifest", default="data/v3/phase2/datagen_manifest.json")
    parser.add_argument("--merged-out", default="data/v3/phase2/labeled_merged.jsonl")
    parser.add_argument("--report-out", default="data/v3/phase2/merge_report.json")
    parser.add_argument("--min-new-valid", type=int, default=6000)
    parser.add_argument("--min-merged-valid", type=int, default=9000)
    parser.add_argument("--expected-old-sha")
    parser.add_argument("--labeler-model", default="gpt-5.5")
    parser.add_argument("--labeler-effort", default="high")
    parser.add_argument("--workers-max", type=int, default=10)
    parser.add_argument(
        "--min-source-attempted",
        default=json.dumps(DEFAULT_MIN_SOURCE_ATTEMPTED, sort_keys=True),
        help="JSON object of required attempted counts per source; use '{}' to disable source coverage gate",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        min_source_attempted = json.loads(args.min_source_attempted)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--min-source-attempted must be a JSON object: {exc}") from exc
    if not isinstance(min_source_attempted, dict):
        raise SystemExit("--min-source-attempted must be a JSON object")
    report = build_phase2_report(
        old_labeled=args.old_labeled,
        new_labeled=args.new_labeled,
        rejected=args.rejected,
        datagen_manifest=args.datagen_manifest,
        merged_out=args.merged_out,
        report_out=args.report_out,
        expected_old_sha=args.expected_old_sha,
        min_new_valid=args.min_new_valid,
        min_merged_valid=args.min_merged_valid,
        labeler_model=args.labeler_model,
        labeler_effort=args.labeler_effort,
        workers_max=args.workers_max,
        min_source_attempted=min_source_attempted,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

---

### `tests/test_v3_dataset_rebuild.py` (test, batch + file-I/O validation)

**Primary analogs:**
- `tests/test_v3_datagen_merge.py` for tmp JSONL fixtures and gate-level report assertions.
- `tests/test_v3_dataset_raw_text.py` for fake tokenizer and raw-text no-chat-template checks.
- `tests/test_v3_tokenizer_parity.py` for deterministic seed assertions.

**Fixture writer pattern** (`tests/test_v3_datagen_merge.py` lines 54-59):
```python
def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path
```

**Large fixture path builder pattern** (`tests/test_v3_datagen_merge.py` lines 66-103):
```python
def _build_paths(
    tmp_path: Path,
    *,
    new_rows: list[dict] | None = None,
    rejected_rows: list[dict] | None = None,
    manifest_counts: dict[str, int] | None = None,
) -> dict[str, Path]:
    old_rows = [_row("a", i) for i in range(3000)]
    if new_rows is None:
        new_rows = [
            *_rows("b", 4250, source="same_dist"),
            *_rows("c", 1250, source="ood"),
            *_rows("d", 500, source="targeted"),
        ]
    if rejected_rows is None:
        rejected_rows = [
            *_rows("e", 1000, source="same_dist"),
            *_rows("f", 250, source="ood"),
            *_rows("0", 250, source="targeted"),
        ]
    if manifest_counts is None:
        manifest_counts = {"same_dist": 5250, "ood": 1500, "targeted": 750}
    old_labels = _write_jsonl(tmp_path / "old_labeled.jsonl", old_rows)
    new_labels = _write_jsonl(tmp_path / "labeled_new.jsonl", new_rows)
    rejects = _write_jsonl(tmp_path / "rejected_new.jsonl", rejected_rows)
    manifest = tmp_path / "datagen_manifest.json"
    manifest.write_text(
        json.dumps({"phase": "02", "sources": ["same_dist", "ood", "targeted"], "counts_written": manifest_counts}),
        encoding="utf-8",
    )
    return {
        "old_labeled_path": old_labels,
        "new_labeled_path": new_labels,
        "rejected_path": rejects,
        "manifest_path": manifest,
        "merged_out_path": tmp_path / "labeled_merged.jsonl",
        "report_out_path": tmp_path / "merge_report.json",
    }
```

**Gate assertion style** (`tests/test_v3_datagen_merge.py` lines 106-134):
```python
def test_merged_valid_count_gate(tmp_path: Path):
    paths = _build_paths(tmp_path)
    old_sha = _sha(paths["old_labeled_path"])

    report = build_phase2_report(
        **paths,
        old_sha_before=old_sha,
        old_sha_after=old_sha,
    )

    assert report["old_sha_before"] == old_sha
    assert report["old_sha_after"] == old_sha
    assert report["old_count"] == 3000
    assert report["new_valid"] == 6000
    assert report["merged_valid"] == 9000
    assert report["old_new_overlap"] == 0
    assert report["all_new_lint_ok"] is True
    assert report["ok"] is True
    assert report["requirements_covered"] == [
        "DATAGEN-01",
        "DATAGEN-02",
        "DATAGEN-03",
        "DATAGEN-04",
        "DATAGEN-05",
        "DATAGEN-06",
        "DATAGEN-07",
    ]
    assert paths["merged_out_path"].exists()
    assert paths["report_out_path"].exists()
```

**Fail-closed no-write assertion pattern** (`tests/test_v3_datagen_merge.py` lines 182-201):
```python
def test_source_attempted_coverage_gate_blocks_partial_targeted_reservoir(tmp_path: Path):
    new_rows = [
        *_rows("b", 5000, source="same_dist"),
        *_rows("c", 1500, source="ood"),
        *_rows("d", 500, source="targeted"),
    ]
    paths = _build_paths(tmp_path, new_rows=new_rows, rejected_rows=[])
    old_sha = _sha(paths["old_labeled_path"])

    report = build_phase2_report(
        **paths,
        old_sha_before=old_sha,
        old_sha_after=old_sha,
    )

    assert report["new_valid"] == 7000
    assert report["source_attempted_counts"]["targeted"] == 500
    assert report["gates"]["source_attempted_coverage"]["ok"] is False
    assert report["ok"] is False
    assert not paths["merged_out_path"].exists()
```

**Fake tokenizer pattern** (`tests/test_v3_dataset_raw_text.py` lines 16-49):
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

    def __call__(self, text, truncation=False, max_length=None, add_special_tokens=False):
        ids = []
        i = 0
        while i < len(text):
            if text.startswith("<think>", i):
                ids.append(99)
                i += len("<think>")
            elif text.startswith("</think>", i):
                ids.append(100)
                i += len("</think>")
            else:
                ids.append(ord(text[i]) + 1000)
                i += 1
        if truncation and max_length is not None:
            ids = ids[:max_length]
        return {"input_ids": ids}
```

**Seed determinism assertion pattern** (`tests/test_v3_tokenizer_parity.py` lines 43-56):
```python
def test_build_prompt_fixture_is_deterministic_with_seed_42(tmp_path: Path) -> None:
    labeled = tmp_path / "labeled.jsonl"
    _write_jsonl(labeled, [_input(i) for i in range(120)])

    out_a = tmp_path / "a.jsonl"
    out_b = tmp_path / "b.jsonl"

    rows_a = build_prompt_fixture(labeled_path=labeled, out_path=out_a, n=100, seed=42)
    rows_b = build_prompt_fixture(labeled_path=labeled, out_path=out_b, n=100, seed=42)

    assert [row["prompt_id"] for row in rows_a] == [row["prompt_id"] for row in rows_b]
    assert out_a.read_text(encoding="utf-8") == out_b.read_text(encoding="utf-8")
    assert len(rows_a) == 100
```

---

### `data/splits/v3/{train,val,ood_val}.index.jsonl` (data artifact, file-I/O + batch)

**Analog:** `tsc_cycle/v3_gates/tokenizer_parity_v3.py` JSONL append/write pattern and `tsc_cycle/hashing.py` hash helpers.

**Write pattern** (`tsc_cycle/v3_gates/tokenizer_parity_v3.py` lines 191-197):
```python
selected = random.Random(seed).sample(candidates, n)
out_path.parent.mkdir(parents=True, exist_ok=True)
with out_path.open("w", encoding="utf-8") as fh:
    for row in selected:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
        fh.write("\n")
return selected
```

**Hash pattern** (`tsc_cycle/hashing.py` lines 9-27):
```python
def canonical_json(obj: Any) -> str:
    """Stable JSON encoding: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sample_id(input_obj: Any) -> str:
    """Sample ID = sha256 of the canonical input JSON. Stable across runs."""
    return sha256_hex(canonical_json(input_obj))


def prompt_hash(prompt: str, model: str, effort: str) -> str:
    """Cache key for teacher response. Includes model + effort so we can
    invalidate when either changes."""
    payload = canonical_json({"prompt": prompt, "model": model, "effort": effort})
    return sha256_hex(payload)
```
Index rows should include at least `sample_id`, split name, source/lineage, `record_hash`, `prompt_hash`, `assistant_hash`, and flags/evidence needed for v1 OOD alignment.

---

### `data/splits/v3/manifest.json` and `data/splits/v3/v1_ood_alignment.json` (manifest/config artifacts, validation + file-I/O)

**Analog:** `tsc_cycle/v3_gates/phase2_datagen_report.py` report payload and `tsc_cycle/v3_gates/memory_budget_v3.py` JSON writer.

**Report payload pattern** (`tsc_cycle/v3_gates/phase2_datagen_report.py` lines 398-429):
```python
report = {
    "ok": ok,
    "fatal_failures": fatal_failures,
    "old_sha_before": old_sha_before_final,
    "old_sha_after": old_sha_after_final,
    "expected_old_sha": expected_old_sha,
    "old_count": len(old_rows),
    "new_valid": new_valid,
    "rejected_count": rejected_count,
    "merged_valid": merged_valid,
    "old_new_overlap": len(old_new_overlap_ids),
    "old_new_overlap_ids_sample": old_new_overlap_ids[:10],
    "source_counts": source_counts,
    "source_attempted_counts": source_attempted_counts,
    "min_source_attempted": source_minimums,
    "manifest_source_counts": manifest_source_counts,
    "all_new_lint_ok": len(lint_failures) == 0,
    "lint_failures_sample": lint_failures[:10],
    "labeler_evidence": labeler_evidence,
    "resume_evidence": resume_evidence,
    "requirements_covered": REQUIREMENTS_COVERED,
    "gates": gates,
    "paths": {
        "old_labeled": str(old_path),
        "new_labeled": str(new_path),
        "rejected": str(rejected_path_final),
        "datagen_manifest": str(manifest_path_final),
        "merged_out": str(merged_path),
        "report_out": str(report_path) if report_path is not None else None,
    },
    "merged_written": merged_written,
}
```

**Write after pass / report write pattern** (`tsc_cycle/v3_gates/phase2_datagen_report.py` lines 389-433):
```python
ok = not fatal_failures
merged_written = False
if ok:
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    with merged_path.open("w", encoding="utf-8") as fh:
        for row in [*old_rows, *valid_new_rows]:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    merged_written = True

# ... report dict construction ...

if report_path is not None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
```
For Phase 3, prefer building all split/tokenization rows and fatal failures first; only write index, manifest, and Arrow files after gates pass.

---

### `data/tokenized/v3/{train,val,ood_val}.arrow` (data artifact, transform + file-I/O)

**Closest in-code analog:** `tsc_cycle/student/dataset.py` constructs a PyArrow table but writes Parquet. No in-repo Arrow IPC writer exists.

**Use existing table columns from** `tsc_cycle/student/dataset.py` lines 175-181:
```python
table = pa.table({
    "sample_id": [r["sample_id"] for r in rows_tok],
    "input_ids": [r["input_ids"] for r in rows_tok],
    "attention_mask": [r["attention_mask"] for r in rows_tok],
    "labels": [r["labels"] for r in rows_tok],
    "trivial": [r["trivial"] for r in rows_tok],
})
```

**Write pattern to use from RESEARCH.md / Apache Arrow docs** (no codebase analog):
```python
with pa.OSFile(str(out_path), "wb") as sink:
    with pa.ipc.new_file(sink, table.schema) as writer:
        writer.write_table(table)
```

Keep split filenames exactly `train.arrow`, `val.arrow`, `ood_val.arrow`; do not create v1-era `data/tokenized/{split}/data.parquet` directories.

## Shared Patterns

### Authentication / Authorization
Not applicable. Phase 3 is a local dataset rebuild CLI and does not introduce a request/response surface.

### Error Handling / Fail-Closed Gates
**Source:** `tsc_cycle/v3_gates/phase2_datagen_report.py` lines 152-163, 389-433.  
**Apply to:** `dataset_rebuild_v3.py`, artifact write decisions, tests.

Use `fatal_failures` + `gates` with `ok = not fatal_failures`; avoid partial artifact writes when any invariant fails.

### Raw Prompt and Assistant Formatting
**Source:** `tsc_cycle/prompt_builder.py` lines 62-87 and `tsc_cycle/student/dataset.py` lines 57-61.  
**Apply to:** tokenization and hash generation.

Always build raw strings with `build_user_prompt(...)` and `build_full_assistant(...)`; do not call tokenizer chat templates.

### Native `<think>` Leak Prevention
**Source:** `tsc_cycle/student/dataset.py` lines 64-89; `tests/test_v3_dataset_raw_text.py` lines 67-75.  
**Apply to:** tokenization function and truncation tests.

Check native think IDs before writing. Phase 3 should check untruncated IDs as RESEARCH.md requires.

### Deterministic Splitting
**Source:** `tsc_cycle/v3_gates/tokenizer_parity_v3.py` lines 171-197 and `tests/test_v3_tokenizer_parity.py` lines 43-56.  
**Apply to:** OOD subset and val split selection.

Sort candidates by sample ID, use `random.Random(42).sample(...)`, persist selected IDs and hashes.

### Hashing / Reproducibility
**Source:** `tsc_cycle/hashing.py` lines 9-27; `tests/test_hashing.py` lines 3-31.  
**Apply to:** index rows, manifest, v1 OOD alignment proof.

Use canonical JSON with sorted keys and no whitespace before SHA-256 hashing.

### Pytest Style
**Source:** `tests/test_v3_datagen_merge.py` and `tests/test_v3_dataset_raw_text.py`.  
**Apply to:** `tests/test_v3_dataset_rebuild.py`.

Use `tmp_path`, local fixture writers, direct function calls, and fail-closed assertions (`assert not output.exists()` when gates fail).

## No Analog Found

Files/patterns with no close exact match in the codebase; planner should use RESEARCH.md patterns for these parts:

| File / Pattern | Role | Data Flow | Reason |
|----------------|------|-----------|--------|
| `data/tokenized/v3/train.arrow` exact Arrow IPC writer | data artifact | transform + file-I/O | Codebase only writes PyArrow tables to Parquet via `pq.write_table`; no `pa.ipc.new_file` usage found. |
| `data/tokenized/v3/val.arrow` exact Arrow IPC writer | data artifact | transform + file-I/O | Same as above. |
| `data/tokenized/v3/ood_val.arrow` exact Arrow IPC writer | data artifact | transform + file-I/O | Same as above. |
| Exact 80/10/10 split with v1 OOD pinned + new OOD subset | utility logic | batch | Existing `split_bucket` hash split puts every OOD row into `val_ood`; Phase 3 needs new exact-size seeded split logic. |

## Metadata

**Analog search scope:** `/home/samuel/TSC_CYCLE/tsc_cycle`, `/home/samuel/TSC_CYCLE/tests`, `/home/samuel/TSC_CYCLE/scripts`  
**Focused directories:** `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates`, `/home/samuel/TSC_CYCLE/tsc_cycle/student`, `/home/samuel/TSC_CYCLE/tests`  
**Files scanned:** 61 Python files broad search; 35 Python files focused analog set  
**Project skills:** no `.claude/skills` or `.agents/skills` directory found under `/home/samuel/TSC_CYCLE`  
**Pattern extraction date:** 2026-05-09
