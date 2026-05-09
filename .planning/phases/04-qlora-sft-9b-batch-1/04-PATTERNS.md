# Phase 04: QLoRA SFT (9B, batch=1, 跑到收敛) - Pattern Map

**Mapped:** 2026-05-09
**Files analyzed:** 12
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `tsc_cycle/student/train.py` | trainer entrypoint | batch + file-I/O + event-driven callbacks | `tsc_cycle/student/train.py` + `tsc_cycle/v3_gates/memory_budget_v3.py` | exact scaffold |
| `tsc_cycle/student/sft_v3.py` | service/utility | batch + transform + file-I/O | `tsc_cycle/v3_gates/dataset_rebuild_v3.py` + `tsc_cycle/v3_gates/memory_budget_v3.py` | exact for Arrow/QLoRA helpers |
| `tsc_cycle/v3_gates/sft_dry_run_v3.py` | gate/eval harness | batch + request-response generation + transform | `tsc_cycle/v3_gates/phase2_datagen_report.py` + `tsc_cycle/constraint_lint.py` | role-match |
| `tsc_cycle/v3_gates/sft_report_v3.py` | aggregate report gate | batch + file-I/O | `tsc_cycle/v3_gates/phase1_report.py` + `tsc_cycle/v3_gates/dataset_rebuild_v3.py` | exact |
| `scripts/run_v3_phase4_dry_run.sh` | wrapper script | batch + process execution + file-I/O | `scripts/run_v3_phase1_gates.sh` + `scripts/dgx_spark/run_safe.sh` | exact |
| `scripts/run_v3_phase4_full.sh` | wrapper script | batch + process execution + file-I/O | `scripts/run_v3_phase1_gates.sh` + `scripts/dgx_spark/run_safe.sh` | exact |
| `tests/test_v3_sft_config.py` | test | request-response unit assertions | `tests/test_v3_memory_budget.py` + `tests/test_v3_dataset_rebuild.py` | role-match |
| `tests/test_v3_sft_arrow_loader.py` | test | file-I/O + transform | `tests/test_v3_dataset_rebuild.py` | exact |
| `tests/test_v3_sft_dry_run.py` | test | batch + validation transform | `tests/test_v3_labeler.py` + `tests/test_v3_phase1_report.py` | role-match |
| `tests/test_v3_sft_grad_gate.py` | test | event-driven callback | `tests/test_v3_memory_budget.py` | partial |
| `tests/test_v3_sft_frozen.py` | test | file-I/O + guard | `tests/test_run_safe_script.py` + `scripts/run_v3_phase3_dataset_rebuild.sh` | role-match |
| `tests/test_v3_sft_artifacts.py` | test | file-I/O + manifest validation | `tests/test_v3_phase1_report.py` + `tests/test_v3_dataset_rebuild.py` | role-match |

## Pattern Assignments

### `tsc_cycle/student/train.py` (trainer entrypoint, batch + file-I/O + event-driven callbacks)

**Analogs:** `tsc_cycle/student/train.py`, `tsc_cycle/v3_gates/memory_budget_v3.py`

**Imports pattern** (`tsc_cycle/student/train.py` lines 10-28):
```python
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)
```

**Tokenizer safety pattern** (`tsc_cycle/student/train.py` lines 52-56):
```python
def boot_tokenizer_check(tokenizer) -> None:
    res = check_tokenizer(tokenizer)
    if not res.ok:
        raise SystemExit(f"BOOT-FAIL: tokenizer_check: {res.details}")
    print("BOOT-OK: tokenizer check passed")
```

**QLoRA model-load pattern to copy and update for Qwen3.5-9B** (`tsc_cycle/v3_gates/memory_budget_v3.py` lines 109-144):
```python
def load_qlora_model(model_name: str, lora_r: int, lora_alpha: int):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    bnb_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_cfg,
        attn_implementation="sdpa",
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )
    lora_cfg = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        lora_dropout=0.0,
        bias="none",
        target_modules="all-linear",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    model.train()
    return model, tokenizer
```

**Trainer construction pattern** (`tsc_cycle/student/train.py` lines 188-220), but Phase 4 must lock `batch_size=1`, `grad_accum=16`, `optim="adamw_torch_fused"`, `max_grad_norm=0.5`, `eval_strategy="steps"`, `eval_steps=200`, `save_strategy="steps"`, `save_steps=200`, `load_best_model_at_end=True`, `metric_for_best_model="eval_loss"`, and early stopping:
```python
collator = DataCollatorForSeq2Seq(tokenizer, padding="longest", label_pad_token_id=-100)

targs = TrainingArguments(
    output_dir=args.output_dir,
    num_train_epochs=args.epochs,
    per_device_train_batch_size=args.batch_size,
    gradient_accumulation_steps=args.grad_accum,
    learning_rate=args.lr,
    bf16=True,
    gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": False},
    logging_steps=args.logging_steps,
    save_strategy="no",
    save_total_limit=1,
    eval_strategy="no",
    report_to=["wandb"] if os.environ.get("WANDB_API_KEY") else ["none"],
    dataloader_num_workers=1,
    remove_unused_columns=False,
    max_steps=args.max_steps,
    warmup_ratio=0.03,
    lr_scheduler_type="cosine",
    weight_decay=0.0,
)

trainer = Trainer(
    model=model,
    args=targs,
    train_dataset=train_ds,
    eval_dataset=val_id_ds,
    data_collator=collator,
    callbacks=[SmokeCallback(tokenizer)],
)
```

**Adapter/log save pattern** (`tsc_cycle/student/train.py` lines 230-239):
```python
adapter_dir = Path(args.output_dir) / "adapter"
trainer.model.save_pretrained(adapter_dir)
tokenizer.save_pretrained(adapter_dir)
print(f"saved adapter: {adapter_dir}")

log = Path(args.output_dir) / "train_log.jsonl"
with log.open("a", encoding="utf-8") as f:
    f.write(json.dumps({"event": "training_complete", "elapsed_h": elapsed / 3600}) + "\n")
```

---

### `tsc_cycle/student/sft_v3.py` (service/utility, batch + transform + file-I/O)

**Analogs:** `tsc_cycle/v3_gates/dataset_rebuild_v3.py`, `tsc_cycle/student/dataset.py`, `tsc_cycle/v3_gates/memory_budget_v3.py`

**Arrow IPC writer/reader convention source** (`tsc_cycle/v3_gates/dataset_rebuild_v3.py` lines 355-374):
```python
def write_arrow_split(path: Path, rows_tok: list[dict[str, Any]]) -> None:
    import pyarrow as pa

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "sample_id": [row["sample_id"] for row in rows_tok],
            "input_ids": [row["input_ids"] for row in rows_tok],
            "attention_mask": [row["attention_mask"] for row in rows_tok],
            "labels": [row["labels"] for row in rows_tok],
            "raw_length": [row["raw_length"] for row in rows_tok],
            "truncated": [row["truncated"] for row in rows_tok],
            "prompt_hash": [row["prompt_hash"] for row in rows_tok],
            "assistant_hash": [row["assistant_hash"] for row in rows_tok],
        }
    )
    with pa.OSFile(str(path), "wb") as sink:
        with pa.ipc.new_file(sink, table.schema) as writer:
            writer.write_table(table)
```

**Legacy dataset column-pruning pattern to adapt from parquet to Arrow IPC** (`tsc_cycle/student/train.py` lines 178-188):
```python
train_ds = load_split(Path(args.data_dir) / "train" / "data.parquet")
val_id_ds = load_split(Path(args.data_dir) / "val_id" / "data.parquet")
print(f"train={len(train_ds)} val_id={len(val_id_ds)}")

keep = ["input_ids", "attention_mask", "labels"]
train_ds = train_ds.remove_columns([c for c in train_ds.column_names if c not in keep])
val_id_ds = val_id_ds.remove_columns([c for c in val_id_ds.column_names if c not in keep])
```

**Config/report JSON write pattern** (`tsc_cycle/v3_gates/memory_budget_v3.py` lines 98-102):
```python
def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
```

**LoRA locked config pattern** (`tsc_cycle/v3_gates/memory_budget_v3.py` lines 134-141):
```python
lora_cfg = LoraConfig(
    r=lora_r,
    lora_alpha=lora_alpha,
    lora_dropout=0.0,
    bias="none",
    target_modules="all-linear",
    task_type="CAUSAL_LM",
)
```

---

### `tsc_cycle/v3_gates/sft_dry_run_v3.py` (gate/eval harness, batch + generation + transform)

**Analogs:** `tsc_cycle/constraint_lint.py`, `tsc_cycle/prompt_builder.py`, `tsc_cycle/v3_gates/phase2_datagen_report.py`

**Constraint lint pattern** (`tsc_cycle/constraint_lint.py` lines 34-89):
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
        result.add(
            Violation.PHASE_MISMATCH,
            expected=expected_ids,
            got=output_keys,
        )
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

**Prompt/output parse pattern** (`tsc_cycle/prompt_builder.py` lines 90-125):
```python
def parse_assistant_output(text: str) -> tuple[str, dict[str, int] | None]:
    reasoning = ""
    solution: dict[str, int] | None = None

    if LEGACY_THINK_CLOSE in text:
        return "", None

    if TAG_THINK_OPEN in text and TAG_THINK_CLOSE in text:
        a = text.index(TAG_THINK_OPEN) + len(TAG_THINK_OPEN)
        b = text.index(TAG_THINK_CLOSE, a)
        reasoning = text[a:b].strip()
    elif TAG_THINK_CLOSE in text:
        b = text.index(TAG_THINK_CLOSE)
        reasoning = text[:b].strip()

    if TAG_SOLUTION_OPEN in text and TAG_SOLUTION_CLOSE in text:
        a = text.index(TAG_SOLUTION_OPEN) + len(TAG_SOLUTION_OPEN)
        b = text.index(TAG_SOLUTION_CLOSE, a)
        try:
            parsed = json.loads(text[a:b].strip())
            if isinstance(parsed, dict):
                solution = {str(k): int(v) for k, v in parsed.items()}
        except (json.JSONDecodeError, ValueError, TypeError):
            solution = None

    return reasoning, solution
```

**Gate recording pattern** (`tsc_cycle/v3_gates/phase2_datagen_report.py` lines 152-163):
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

**Apply to dry-run:** sample deterministic 500 rows from `ood_val.arrow`, generate from the dry-run adapter, call `parse_assistant_output`, call `validate(prediction_input, solution)`, and fail closed unless `hard_constraint_pass_rate >= 0.95`, `grad_norm_p99 < 3.0`, and no NaN/Inf.

---

### `tsc_cycle/v3_gates/sft_report_v3.py` (aggregate report gate, batch + file-I/O)

**Analogs:** `tsc_cycle/v3_gates/phase1_report.py`, `tsc_cycle/v3_gates/dataset_rebuild_v3.py`

**Artifact loader and gate helper** (`tsc_cycle/v3_gates/phase1_report.py` lines 23-48):
```python
def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"missing artifact: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON {path}: {exc}"


def _gate(name: str, passed: bool, reason: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": bool(passed), "reason": reason, "data": data or {}}


def _add_result(gates: dict[str, Any], failures: list[dict[str, str]], name: str, passed: bool, reason: str | None, data: dict[str, Any] | None = None) -> None:
    gates[name] = _gate(name, passed, reason, data)
    if not passed:
        failures.append({"gate": name, "reason": reason or "failed"})
```

**Aggregate evaluate pattern** (`tsc_cycle/v3_gates/phase1_report.py` lines 50-56, 142-150):
```python
def evaluate_gates(artifacts: str | Path, gguf_report: str | Path) -> dict[str, Any]:
    artifacts = Path(artifacts)
    gguf_report = Path(gguf_report)
    gates: dict[str, Any] = {}
    failures: list[dict[str, str]] = []
    warnings: list[str] = []

    ok = not failures
    return {
        "ok": ok,
        "fatal_failures": failures,
        "warnings": warnings,
        "gates": gates,
        "requirements_covered": REQUIREMENTS_COVERED,
        "next_phase_allowed": ok,
    }
```

**Manifest hash pattern** (`tsc_cycle/v3_gates/dataset_rebuild_v3.py` lines 448-459):
```python
def _artifact_manifest(config: DatasetRebuildConfig, report: dict[str, Any]) -> dict[str, Any]:
    paths = {
        "train_index": config.split_dir / "train.index.jsonl",
        "val_index": config.split_dir / "val.index.jsonl",
        "ood_val_index": config.split_dir / "ood_val.index.jsonl",
        "v1_ood_alignment": config.split_dir / "v1_ood_alignment.json",
        "rebuild_report": config.report_out,
        "train_arrow": config.tokenized_dir / "train.arrow",
        "val_arrow": config.tokenized_dir / "val.arrow",
        "ood_val_arrow": config.tokenized_dir / "ood_val.arrow",
    }
    return {"paths": {name: str(path) for name, path in paths.items()}, "sha256": _artifact_hashes(paths), "ok": report.get("ok") is True}
```

---

### `scripts/run_v3_phase4_dry_run.sh` and `scripts/run_v3_phase4_full.sh` (wrapper scripts, batch + process execution)

**Analogs:** `scripts/run_v3_phase1_gates.sh`, `scripts/run_v3_phase3_dataset_rebuild.sh`, `scripts/dgx_spark/run_safe.sh`

**Project-root/interpreter/env pattern** (`scripts/run_v3_phase1_gates.sh` lines 1-15):
```bash
#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="/home/samuel/TSC_CYCLE/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "ERROR: required interpreter missing or not executable: $PY" >&2
  exit 1
fi

source scripts/dgx_spark/env.sh
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
```

**run_safe invocation pattern** (`scripts/run_v3_phase1_gates.sh` lines 24-31, 55-59):
```bash
scripts/dgx_spark/run_safe.sh 100G -- "$PY" -m tsc_cycle.v3_gates.run_safe_scope_check_v3 \
  --out "$ARTIFACTS/run_safe_scope.json"

scripts/dgx_spark/run_safe.sh 100G -- "$PY" -m tsc_cycle.v3_gates.memory_budget_v3 \
  --model Qwen/Qwen3.5-9B \
  --seqs 1536 2048 2560 3072 4096 \
  --out "$ARTIFACTS/memory_budget.json"
```

**Input guard pattern before destructive work** (`scripts/run_v3_phase3_dataset_rebuild.sh` lines 12-25):
```bash
for path in \
  data/v3/phase2/labeled_merged.jsonl \
  data/v3/phase2/merge_report.json \
  artifacts/v3/phase1/memory_budget.json \
  artifacts/v3/phase1/tokenizer_audit.json; do
  if [[ ! -f "${path}" ]]; then
    echo "ERROR: missing required Phase 3 input: ${path}" >&2
    exit 1
  fi
done

if ! git diff --quiet -- data/labeled.jsonl; then
  echo "ERROR: data/labeled.jsonl has uncommitted changes before Phase 3 rebuild; refusing to continue." >&2
  exit 1
fi
```

**DGX safe wrapper contract** (`scripts/dgx_spark/run_safe.sh` lines 17-21, 39-54):
```bash
free_gb=$(awk '/MemAvailable/ {printf "%.0f", $2/1024/1024}' /proc/meminfo)
if [ "$free_gb" -lt 60 ]; then
    echo "ERROR: only ${free_gb}GB MemAvailable; clean up before training."
    exit 1
fi

exec sudo systemd-run --scope \
    --uid="$(id -un)" \
    --gid="$(id -gn)" \
    --expand-environment=no \
    -p "MemoryMax=$MEMORY_MAX" \
    -p MemorySwapMax=0 \
    --same-dir \
    --setenv="CUDA_HOME=$CUDA_HOME" \
    --setenv="PATH=$PATH" \
    --setenv="LD_LIBRARY_PATH=$LD_LIBRARY_PATH" \
    --setenv="TORCH_CUDA_ARCH_LIST=$TORCH_CUDA_ARCH_LIST" \
    --setenv="TRITON_PTXAS_PATH=$TRITON_PTXAS_PATH" \
    --setenv="PYTORCH_ALLOC_CONF=$PYTORCH_ALLOC_CONF" \
    bash -c 'echo 500 > /proc/self/oom_score_adj 2>/dev/null || true; exec "$@"' \
    dgx-spark-training \
    "$@"
```

**Apply to wrappers:** use absolute `/home/samuel/TSC_CYCLE/.venv/bin/python`, set `WANDB_PROJECT=tsc-cycle-v3-9b`, enforce `runs/v3.0-9B-{utc}` output roots, verify Phase 3 Arrow/report files exist, verify `runs/20260507T032419Z/FROZEN.md` exists/read-only before launching training.

---

### `tests/test_v3_sft_config.py` (test, request-response unit assertions)

**Analogs:** `tests/test_v3_memory_budget.py`, `tests/test_v3_dataset_rebuild.py`

**Lightweight fake object pattern** (`tests/test_v3_memory_budget.py` lines 3-15):
```python
class FakeParam:
    def __init__(self, requires_grad):
        self.requires_grad = requires_grad


class FakeModel:
    def __init__(self):
        self.frozen = FakeParam(False)
        self.trainable = FakeParam(True)

    def parameters(self):
        return [self.frozen, self.trainable]
```

**Locked invariant assertions pattern** (`tests/test_v3_memory_budget.py` lines 17-24, 27-36):
```python
def test_default_seqs_are_required_measured_candidates():
    assert default_seqs() == [1536, 2048, 2560, 3072, 4096]


def test_iter_trainable_parameters_filters_frozen_base_weights():
    model = FakeModel()

    assert list(iter_trainable_parameters(model)) == [model.trainable]
```

**Config import indirection pattern** (`tests/test_v3_dataset_rebuild.py` lines 8-25):
```python
def _dataset_contract():
    from tsc_cycle.v3_gates.dataset_rebuild_v3 import (  # noqa: PLC0415
        DEFAULT_MAX_SEQ_LENGTH,
        DEFAULT_SEED,
        DatasetRebuildConfig,
        build_phase3_dataset,
        build_split_plan,
        tokenize_record,
    )

    return {
        "DEFAULT_MAX_SEQ_LENGTH": DEFAULT_MAX_SEQ_LENGTH,
        "DEFAULT_SEED": DEFAULT_SEED,
        "DatasetRebuildConfig": DatasetRebuildConfig,
        "build_phase3_dataset": build_phase3_dataset,
        "build_split_plan": build_split_plan,
        "tokenize_record": tokenize_record,
    }
```

**Apply to SFT config tests:** assert model default `Qwen/Qwen3.5-9B`, LoRA `r=64/alpha=64/dropout=0.0/target_modules="all-linear"`, batch `1`, grad accum `16`, `packing=False` by absence/no TRL packing, optimizer `adamw_torch_fused`, `max_grad_norm=0.5`, eval/save every `200`, max epochs `5`, and output root prefix `runs/v3.0-9B-`.

---

### `tests/test_v3_sft_arrow_loader.py` (test, file-I/O + transform)

**Analog:** `tests/test_v3_dataset_rebuild.py`

**Arrow IPC open/assert pattern** (`tests/test_v3_dataset_rebuild.py` lines 262-267, 269-300):
```python
def _open_arrow(path: Path):
    import pyarrow as pa  # noqa: PLC0415

    with pa.memory_map(str(path), "r") as source:
        return pa.ipc.open_file(source).read_all()


def test_writes_arrow_ipc_files(tmp_path: Path) -> None:
    config, tokenizer, report = _phase3_dataset(tmp_path)

    assert report["ok"] is True
    assert tokenizer.chat_template_used is False
    assert report["tokenized_paths"] == {
        "train": str(config.tokenized_dir / "train.arrow"),
        "val": str(config.tokenized_dir / "val.arrow"),
        "ood_val": str(config.tokenized_dir / "ood_val.arrow"),
    }

    expected_columns = {
        "sample_id",
        "input_ids",
        "attention_mask",
        "labels",
        "raw_length",
        "truncated",
        "prompt_hash",
        "assistant_hash",
    }
    expected_rows = {"train": 7601, "val": 950, "ood_val": 950}
    for split_name, expected_count in expected_rows.items():
        arrow_path = config.tokenized_dir / f"{split_name}.arrow"
        assert arrow_path.exists()
        table = _open_arrow(arrow_path)
        assert table.num_rows == expected_count
        assert set(table.column_names) == expected_columns
        assert "chat_template" not in table.schema.metadata if table.schema.metadata else True
        assert "metadata" not in table.column_names

    assert not (tmp_path / "data" / "tokenized" / "train" / "data.parquet").exists()
```

**Apply to loader tests:** create tiny IPC files with the same columns, load through `load_arrow_split`, assert Trainer dataset keeps only `input_ids`, `attention_mask`, `labels`, while metadata is still available for reports before pruning.

---

### `tests/test_v3_sft_dry_run.py` (test, batch + validation transform)

**Analogs:** `tests/test_v3_labeler.py`, `tests/test_v3_phase1_report.py`

**Synthetic sample pattern** (`tests/test_v3_labeler.py` lines 27-53):
```python
def _sample(as_of: str = "2026-05-02 00:00:00", *, min_green: int = 20, max_green: int = 60) -> dict:
    item = {
        "prediction": {
            "as_of": as_of,
            "phase_waits": [
                {
                    "phase_id": 1,
                    "pred_wait": 3.0,
                    "pred_saturation": 0.10,
                    "min_green": min_green,
                    "max_green": max_green,
                    "capacity": 30,
                },
                {
                    "phase_id": 2,
                    "pred_wait": 4.0,
                    "pred_saturation": 0.20,
                    "min_green": min_green,
                    "max_green": max_green,
                    "capacity": 40,
                },
            ],
        }
    }
    item["sample_id"] = sample_id(item)
    item["source"] = "same_dist"
    return item
```

**Fail-closed report assertion pattern** (`tests/test_v3_phase1_report.py` lines 112-119):
```python
def test_memory_peak_85_is_strict_failure(tmp_path: Path):
    artifacts, gguf = passing_artifacts(tmp_path)
    write_json(artifacts / "memory_budget.json", {"ok": True, "selected_max_seq": 2048, "results": [{"seq": 2048, "peak_reserved_gb": 85.0, "status": "ok"}]})

    report = evaluate_gates(artifacts, gguf)

    assert report["ok"] is False
    assert any(item["gate"] == "memory_budget" for item in report["fatal_failures"])
```

**Lint failure not accepted pattern** (`tests/test_v3_labeler.py` lines 288-321):
```python
def test_lint_failure_dropped_not_retried(tmp_path: Path):
    sample = _sample(min_green=20, max_green=60)
    input_path = _write_jsonl(tmp_path / "inputs.jsonl", [sample])
    old_labeled = _write_jsonl(tmp_path / "old_labeled.jsonl", [])
    labeled = tmp_path / "labeled_new.jsonl"
    rejected = tmp_path / "rejected_new.jsonl"
    fake = FakeClient(FakeResult(solution={"1": 10, "2": 35}))

    args = build_parser().parse_args([...])

    run_labeling(args, client_factory=lambda **_: fake)

    rejected_rows = [json.loads(line) for line in rejected.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert fake.prompts == [build_user_prompt(sample)]
    assert (not labeled.exists()) or labeled.read_text(encoding="utf-8") == ""
    assert len(rejected_rows) == 1
    assert rejected_rows[0]["sample_id"] == sample["sample_id"]
    assert rejected_rows[0]["reject_reason"] == "constraint_violation"
```

**Apply to dry-run tests:** assert reports fail when sample count is not 500, pass rate is `<0.95`, `grad_norm_p99 >= 3.0`, or `loss_finite=false`; assert full-run allow flag is false unless all gates pass.

---

### `tests/test_v3_sft_grad_gate.py` (test, event-driven callback)

**Analog:** `tsc_cycle/student/train.py` callback pattern + `tests/test_v3_memory_budget.py` fake-object pattern

**Callback mutation/logging pattern** (`tsc_cycle/student/train.py` lines 96-114):
```python
class SmokeCallback(TrainerCallback):
    def __init__(self, tokenizer, every_n_epochs: int = 1):
        self.tokenizer = tokenizer
        self.every = every_n_epochs

    def on_epoch_end(self, args, state, control, **kwargs):
        model = kwargs["model"]
        result = smoke_generate(model, self.tokenizer, n=5)
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        with open(Path(args.output_dir) / "smoke.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"epoch": state.epoch, **result}) + "\n")
        print(f"[SMOKE] epoch {state.epoch}: closing_ok={result['closing_ok']}/5 native_leak={result['native_leak']}/5")

        snap_dir = Path(args.output_dir) / f"adapter_epoch{int(round(state.epoch))}"
        model.save_pretrained(snap_dir)
        self.tokenizer.save_pretrained(snap_dir)
        print(f"[SMOKE] saved snapshot: {snap_dir}")
        return control
```

**Apply to grad gate tests:** instantiate callback with fake `state.global_step`, fake `control.should_training_stop`, feed `on_log(..., logs={"loss": ..., "grad_norm": ...})`; assert p99 and NaN/Inf failures append to `fatal_failures`, set `should_training_stop=True`, and write a gate JSON with `ok=false`.

---

### `tests/test_v3_sft_frozen.py` (test, file-I/O + guard)

**Analogs:** `tests/test_run_safe_script.py`, `scripts/run_v3_phase3_dataset_rebuild.sh`

**Subprocess wrapper test pattern** (`tests/test_run_safe_script.py` lines 11-47):
```python
def test_run_safe_fails_fast_when_noninteractive_systemd_run_sudo_is_unavailable(tmp_path: Path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    (fake_bin / "awk").write_text("#!/bin/sh\necho 128\n", encoding="utf-8")
    (fake_bin / "awk").chmod(0o755)

    (fake_bin / "sudo").write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"-n\" ] && [ \"$2\" = \"/usr/bin/systemd-run\" ] && [ \"$3\" = \"--version\" ]; then\n"
        "  echo 'sudo: a password is required' >&2\n"
        "  exit 1\n"
        "fi\n"
        "echo 'UNSAFE systemd-run attempted without preflight' >&2\n"
        "exit 42\n",
        encoding="utf-8",
    )
    (fake_bin / "sudo").chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["CUDA_HOME"] = str(tmp_path / "cuda")

    result = subprocess.run(
        [str(RUN_SAFE), "100G", "--", "true"],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 1
    assert "UNSAFE systemd-run attempted" not in result.stderr
    assert "non-interactive sudo" in result.stderr
    assert "NOPASSWD" in result.stderr
```

**Baseline diff guard pattern** (`scripts/run_v3_phase3_dataset_rebuild.sh` lines 23-45):
```bash
if ! git diff --quiet -- data/labeled.jsonl; then
  echo "ERROR: data/labeled.jsonl has uncommitted changes before Phase 3 rebuild; refusing to continue." >&2
  exit 1
fi

"${PYTHON}" -m tsc_cycle.v3_gates.dataset_rebuild_v3 \
  --merged-jsonl data/v3/phase2/labeled_merged.jsonl \
  --phase2-report data/v3/phase2/merge_report.json \
  --memory-budget artifacts/v3/phase1/memory_budget.json \
  --tokenizer-audit artifacts/v3/phase1/tokenizer_audit.json \
  --splits-dir data/splits/v3 \
  --tokenized-dir data/tokenized/v3 \
  --report-out data/splits/v3/rebuild_report.json \
  --seed 42 \
  --expected-train 7601 \
  --expected-val 950 \
  --expected-ood-val 950 \
  --max-truncation-rate 0.05

if ! git diff --quiet -- data/labeled.jsonl; then
  echo "ERROR: data/labeled.jsonl changed after Phase 3 rebuild; refusing to continue." >&2
  exit 1
fi
```

**Apply to FROZEN tests:** use tmp `runs/20260507T032419Z`, create file tree, call guard, assert `FROZEN.md` exists, write bits removed where platform allows, hash/mtime unchanged after wrapper validation, and reject output dirs outside `runs/v3.0-9B-*`.

---

### `tests/test_v3_sft_artifacts.py` (test, file-I/O + manifest validation)

**Analogs:** `tests/test_v3_phase1_report.py`, `tests/test_v3_dataset_rebuild.py`

**Passing artifact fixture pattern** (`tests/test_v3_phase1_report.py` lines 13-67):
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

    write_json(
        artifacts / "env_smoke.json",
        {"ok": True, "model_class": "Qwen3_5ForCausalLM", "architectures": ["Qwen3_5ForCausalLM"], "vision_param_count": 0},
    )
    ...
    return artifacts, gguf
```

**Manifest assertion pattern** (`tests/test_v3_dataset_rebuild.py` lines 186-197):
```python
manifest = json.loads((config.split_dir / "manifest.json").read_text(encoding="utf-8"))
assert manifest["ok"] is True
assert manifest["seed"] == 42
assert manifest["input_sha256"] == _sha(merged)
assert manifest["split_sizes"] == {"train": 7601, "val": 950, "ood_val": 950}
assert manifest["requirements_covered"] == ["DATA-01", "DATA-04"]

alignment = json.loads((config.split_dir / "v1_ood_alignment.json").read_text(encoding="utf-8"))
assert alignment["all_v1_ood_in_ood_val"] is True
assert alignment["v1_ood_count"] == 300
assert alignment["new_ood_count"] == 650
assert len(alignment["v1_ood_sample_ids_sha256"]) == 64
```

**Apply to artifact tests:** assert `sft_manifest.json` and aggregate `sft_report_v3` include `ok`, `gates`, `fatal_failures`, `requirements_covered=["SFT-01".."SFT-08"]`, run root, dry/full report paths, adapter path, input Arrow hashes, LoRA coverage path, and FROZEN guard evidence.

## Shared Patterns

### Fail-closed gate reports
**Sources:** `tsc_cycle/v3_gates/phase1_report.py`, `tsc_cycle/v3_gates/phase2_datagen_report.py`, `tsc_cycle/v3_gates/dataset_rebuild_v3.py`

**Apply to:** `sft_dry_run_v3.py`, `sft_report_v3.py`, trainer config validation, tests

Use machine-readable payloads with `ok`, `gates`, `fatal_failures`, `requirements_covered`, and `paths`/`artifact_manifest`. Do not proceed to full run unless all prior gates have `ok=true`.

### DGX Spark runtime safety
**Sources:** `scripts/dgx_spark/env.sh` lines 9-15, `scripts/dgx_spark/run_safe.sh` lines 39-54

**Apply to:** all Phase 4 dry/full wrapper scripts and long training commands

```bash
export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda}"
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-12.1a}"
export TRITON_PTXAS_PATH="${TRITON_PTXAS_PATH:-$CUDA_HOME/bin/ptxas}"
export PYTORCH_ALLOC_CONF="${PYTORCH_ALLOC_CONF:-expandable_segments:True,max_split_size_mb:128}"
```

### Tokenizer/native-think safety
**Source:** `tsc_cycle/tokenizer_check.py` lines 41-89

**Apply to:** train bootstrap, Arrow loader validation, dry-run generation lint

```python
def native_think_token_ids(tokenizer) -> set[int]:
    ids: set[int] = set()
    for encoded in lookup_native_think_ids(tokenizer).values():
        if len(encoded) == 1:
            ids.add(encoded[0])
    return ids


def assert_no_native_think_in_ids(token_ids: Iterable[int], native_ids: set[int] | frozenset[int] | None = None) -> None:
    if native_ids is None:
        raise ValueError("native_ids must be provided from native_think_token_ids(tokenizer)")

    found = set(token_ids) & set(native_ids)
    if found:
        bad = min(found)
        raise AssertionError(f"native think token id {bad} present in token_ids")
```

### Prompt and solution protocol
**Source:** `tsc_cycle/prompt_builder.py` lines 21-31, 81-87

**Apply to:** dry-run generation, SFT data provenance checks, tests

```python
TAG_THINK_OPEN = "<start_working_out>"
TAG_THINK_CLOSE = "<end_working_out>"
TAG_SOLUTION_OPEN = "<SOLUTION>"
TAG_SOLUTION_CLOSE = "</SOLUTION>"
LEGACY_THINK_CLOSE = "</end_working_out>"

SYSTEM_PROMPT = "你是交通信号配时优化专家。"

def build_full_assistant(reasoning: str, solution: dict[str, int]) -> str:
    sol_json = json.dumps(solution, ensure_ascii=False)
    return (
        f"{TAG_THINK_OPEN}{reasoning}{TAG_THINK_CLOSE}"
        f"{TAG_SOLUTION_OPEN}{sol_json}{TAG_SOLUTION_CLOSE}"
    )
```

### Artifact hashing/manifest pattern
**Sources:** `tsc_cycle/v3_gates/dataset_rebuild_v3.py` lines 49-57, 207-237

**Apply to:** `sft_report_v3.py`, `sft_manifest.json`, FROZEN guard evidence

```python
def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_hashes(paths: dict[str, Path]) -> dict[str, str]:
    return {name: _sha256_file(path) for name, path in paths.items() if path.exists()}
```

## No Analog Found

All planned Phase 4 files have usable analogs. The only new behavior without an exact codebase implementation is the `GradNormAbortCallback`; implement it using the existing `TrainerCallback` structure from `SmokeCallback` plus the fail-closed gate report style from v3 gate modules.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tsc_cycle/student/sft_v3.py` callback section | callback utility | event-driven | No existing grad-norm p99 callback; use `SmokeCallback` event method shape and v3 gate JSON patterns. |

## Metadata

**Analog search scope:** `/home/samuel/TSC_CYCLE/tsc_cycle`, `/home/samuel/TSC_CYCLE/scripts`, `/home/samuel/TSC_CYCLE/tests`, project `.claude` / `.agents` skill directories

**Files scanned:** 48 listed source/test/script files; 22 files read directly for pattern extraction

**Pattern extraction date:** 2026-05-09
