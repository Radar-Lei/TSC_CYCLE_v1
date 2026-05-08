# Phase 1: 环境 + Tokenizer + 显存 + llama.cpp 四合一硬门禁 - Pattern Map

**Mapped:** 2026-05-08
**Files analyzed:** 12
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `tsc_cycle/v3_gates/__init__.py` | config | request-response | `tsc_cycle/student/__init__.py` | exact |
| `tsc_cycle/v3_gates/env_smoke_v3.py` | utility | file-I/O | `tsc_cycle/student/train.py` | role-match |
| `tsc_cycle/v3_gates/tokenizer_audit_v3.py` | utility | transform | `tsc_cycle/tokenizer_check.py` | exact |
| `tsc_cycle/v3_gates/tokenizer_parity_v3.py` | utility | file-I/O | `tsc_cycle/student/tokenize_sanity.py` + `tsc_cycle/student/parity_prompts.py` | role-match |
| `tsc_cycle/v3_gates/memory_budget_v3.py` | utility | batch | `tsc_cycle/student/train.py` | role-match |
| `tsc_cycle/v3_gates/gguf_microconvert_v3.py` | utility | file-I/O | `tsc_cycle/student/export_gguf.py` | exact |
| `tsc_cycle/v3_gates/phase1_report.py` | utility | transform | `tsc_cycle/student/parity_merge.py` | role-match |
| `scripts/run_v3_phase1_gates.sh` | utility | batch | `scripts/run_pipeline.sh` | role-match |
| `scripts/dgx_spark/verify.py` | utility | request-response | `scripts/dgx_spark/verify.py` | exact-modify |
| `tsc_cycle/tokenizer_check.py` | utility | transform | `tsc_cycle/tokenizer_check.py` | exact-modify |
| `tsc_cycle/student/dataset.py` | utility | transform | `tsc_cycle/student/dataset.py` | exact-modify |
| `tests/test_v3_gates.py` | test | request-response | `tests/test_prompt_builder.py` | role-match |

## Pattern Assignments

### `tsc_cycle/v3_gates/env_smoke_v3.py` (utility, file-I/O)

**Analog:** `tsc_cycle/student/train.py`

**Imports pattern** (lines 8-28):
```python
from __future__ import annotations

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

**CLI pattern** (lines 117-132):
```python
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/tokenized")
    ap.add_argument("--model", default=MODEL_NAME)
    ap.add_argument("--output-dir", default=None, help="default runs/{ts}/train/")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--lora-r", type=int, default=64)
    ap.add_argument("--lora-alpha", type=int, default=128)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--save-strategy", default="epoch")
    ap.add_argument("--logging-steps", type=int, default=10)
    ap.add_argument("--max-steps", type=int, default=-1, help=">0 for dry-run / smoke")
    args = ap.parse_args()
```

**Model load + SDPA + NF4 pattern** (lines 140-164):
```python
tokenizer = AutoTokenizer.from_pretrained(args.model)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token
tokenizer.padding_side = "right"
boot_tokenizer_check(tokenizer)

bnb_cfg = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
    args.model,
    quantization_config=bnb_cfg,
    attn_implementation="sdpa",
    torch_dtype=torch.bfloat16,
    device_map={"": 0},
)
model.config.use_cache = False
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                        gradient_checkpointing_kwargs={"use_reentrant": False})
```

**Forward smoke pattern** (lines 59-69):
```python
def bnb_warmup(model, tokenizer, device: str = "cuda") -> None:
    model.eval()
    with torch.no_grad():
        prompt = build_user_prompt({"prediction": {"as_of": "x", "phase_waits": [
            {"phase_id": 1, "pred_wait": 1.0, "pred_saturation": 0.05, "min_green": 20, "max_green": 45, "capacity": 30}
        ]}})
        ids = tokenizer(prompt, return_tensors="pt").to(device)
        _ = model(**ids)
    model.train()
    print("BOOT-OK: bnb 4-bit warmup forward complete")
```

**Planner notes:** 改默认模型为 `Qwen/Qwen3.5-9B`，写 `--out artifacts/v3/phase1/env_smoke.json`，不要导入不需要的 `Trainer/datasets`。新增 causal LM/Qwen3.5 架构检查和 `vision_param_count == 0` fatal gate。

---

### `tsc_cycle/v3_gates/tokenizer_audit_v3.py` (utility, transform)

**Analog:** `tsc_cycle/tokenizer_check.py`

**Tag source pattern** (lines 13-24):
```python
from __future__ import annotations

from dataclasses import dataclass

from tsc_cycle.prompt_builder import (
    TAG_SOLUTION_CLOSE,
    TAG_SOLUTION_OPEN,
    TAG_THINK_CLOSE,
    TAG_THINK_OPEN,
)

CUSTOM_TAGS = (TAG_THINK_OPEN, TAG_THINK_CLOSE, TAG_SOLUTION_OPEN, TAG_SOLUTION_CLOSE)
```

**Core audit pattern** (lines 36-69):
```python
def check_tokenizer(tokenizer) -> CheckResult:
    details: dict = {"custom_tags": {}, "native_think": {}, "vocab_size": None}
    details["vocab_size"] = len(tokenizer)

    bad_custom: list[str] = []
    for tag in CUSTOM_TAGS:
        ids = tokenizer.encode(tag, add_special_tokens=False)
        details["custom_tags"][tag] = ids
        if len(ids) < 2:
            bad_custom.append(tag)

    open_ids = tokenizer.encode("<think>", add_special_tokens=False)
    close_ids = tokenizer.encode("</think>", add_special_tokens=False)
    details["native_think"] = {
        "<think>": open_ids,
        "</think>": close_ids,
        "expected_open_id": NATIVE_THINK_OPEN_ID,
        "expected_close_id": NATIVE_THINK_CLOSE_ID,
    }

    bad_native = []
    if open_ids != [NATIVE_THINK_OPEN_ID]:
        bad_native.append(f"<think> = {open_ids} (want [{NATIVE_THINK_OPEN_ID}])")
    if close_ids != [NATIVE_THINK_CLOSE_ID]:
        bad_native.append(f"</think> = {close_ids} (want [{NATIVE_THINK_CLOSE_ID}])")

    ok = not bad_custom and not bad_native
    details["bad_custom_tags"] = bad_custom
    details["bad_native_think"] = bad_native
    return CheckResult(ok=ok, details=details)
```

**Planner notes:** v3 必须改为 custom tag `len(ids) >= 3`；原生 `<think>`/`</think>` 只要求单 token 并动态记录实际 ID，不再使用 4B 固定 ID。输出 JSON 包含 tokenizer length/vocab size、special token map、added vocab hits、failure list。

---

### `tsc_cycle/v3_gates/tokenizer_parity_v3.py` (utility, file-I/O)

**Analogs:** `tsc_cycle/student/tokenize_sanity.py`, `tsc_cycle/student/parity_prompts.py`

**HF encode pattern** (`tokenize_sanity.py` lines 79-82, 155-160):
```python
def build_hf_tokenizer(merged_hf: str):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(merged_hf)


def encode_hf(tokenizer, text: str) -> list[int]:
    return list(tokenizer.encode(text, add_special_tokens=False))


def encode_gguf(bpe, text: str) -> list[int]:
    return list(bpe.encode(text, add_special_tokens=False).ids)
```

**Artifact + fatal assertion pattern** (`tokenize_sanity.py` lines 219-235):
```python
out_path.parent.mkdir(parents=True, exist_ok=True)
with out_path.open("w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)

if not all_custom_match:
    bad = [r["tag"] for r in custom_records if not r["match"]]
    _fail(f"custom tags hf!=gguf: {bad}; wrote diagnostic to {out_path}")
if not all_custom_multi_token:
    bad = [r["tag"] for r in custom_records if not r["is_multi_token"]]
    _fail(f"custom tags not multi-token (in vocab as added tokens): {bad}")
```

**Deterministic JSONL read/write pattern** (`parity_prompts.py` lines 26-37, 79-84):
```python
def _iter_records(labeled_path: Path) -> Iterator[dict]:
    with labeled_path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(
                    f"[PARITY-PROMPTS] malformed json at {labeled_path}:{line_no}: {exc}"
                ) from exc


def write_jsonl(out_path: Path, records: list[dict]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
```

**Planner notes:** v3 是 HF `AutoTokenizer.encode(..., add_special_tokens=False)` 与 `llama-tokenize` 的 100 prompt 精确比对；先跑 `llama-tokenize --help` 判定是否需要 GGUF tokenizer/model fixture，缺 fixture 时 fail closed。

---

### `tsc_cycle/v3_gates/memory_budget_v3.py` (utility, batch)

**Analog:** `tsc_cycle/student/train.py`

**LoRA/k-bit training pattern** (lines 148-174):
```python
bnb_cfg = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)
model = AutoModelForCausalLM.from_pretrained(
    args.model,
    quantization_config=bnb_cfg,
    attn_implementation="sdpa",
    torch_dtype=torch.bfloat16,
    device_map={"": 0},
)
model.config.use_cache = False
model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                        gradient_checkpointing_kwargs={"use_reentrant": False})

lora_cfg = LoraConfig(
    r=args.lora_r,
    lora_alpha=args.lora_alpha,
    lora_dropout=args.lora_dropout,
    bias="none",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    task_type="CAUSAL_LM",
)
model = get_peft_model(model, lora_cfg)
model.print_trainable_parameters()
```

**Trainer dry-run arguments pattern** (lines 191-211):
```python
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
```

**Planner notes:** 对 `--seqs 1536 2048 2560 3072 4096` 循环；每个候选前 `torch.cuda.reset_peak_memory_stats()`；捕获 OOM 并记录；选择 peak `<85GB` 的最大 seq。v3 使用 batch=1、grad_accum=16、LoRA r=64/alpha=64/dropout=0.0、all-linear 或项目等价 target modules。

---

### `tsc_cycle/v3_gates/gguf_microconvert_v3.py` (utility, file-I/O)

**Analog:** `tsc_cycle/student/export_gguf.py`

**Imports/path constants** (lines 6-23):
```python
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from tsc_cycle.tokenizer_check import EXPECTED_VOCAB_SIZE, check_tokenizer

LLAMA_CPP = Path(os.environ.get("LLAMA_CPP_DIR", "/home/samuel/projects/EvoProgTSC/llama.cpp"))
CONVERT = LLAMA_CPP / "convert_hf_to_gguf.py"
QUANTIZE = LLAMA_CPP / "llama-quantize"
```

**Merge pattern** (lines 25-46):
```python
def merge_to_bf16(adapter_dir: Path, out_merged: Path, base_model: str) -> None:
    print(f"[MERGE] reload base in bf16: {base_model}")
    base = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
        device_map={"": 0},
    )
    print(f"[MERGE] attach LoRA adapter: {adapter_dir}")
    peft_model = PeftModel.from_pretrained(base, adapter_dir)
    print("[MERGE] merge_and_unload")
    merged = peft_model.merge_and_unload()
    out_merged.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(out_merged, safe_serialization=True)
    tok = AutoTokenizer.from_pretrained(adapter_dir)
    tok.save_pretrained(out_merged)
    res = check_tokenizer(tok)
    if not res.ok:
        raise SystemExit(f"tokenizer_check failed post-merge: {res.details}")
    print(f"[MERGE] done; merged vocab_size={len(tok)}")
```

**convert/quantize subprocess pattern** (lines 49-64):
```python
def hf_to_gguf_bf16(merged_dir: Path, out_gguf: Path) -> None:
    out_gguf.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "python", str(CONVERT),
        str(merged_dir),
        "--outfile", str(out_gguf),
        "--outtype", "bf16",
    ]
    print("[CONVERT] " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def quantize(in_gguf: Path, out_gguf: Path, kind: str = "Q4_K_M") -> None:
    cmd = [str(QUANTIZE), str(in_gguf), str(out_gguf), kind]
    print("[QUANT] " + " ".join(cmd))
    subprocess.run(cmd, check=True)
```

**llama-cli smoke pattern** (`tsc_cycle/eval/parity.py` lines 30-43):
```python
def _gguf_generate(llama_cli: Path, gguf: Path, prompt: str, n_predict: int = 512) -> str:
    full = prompt + "\n" + build_assistant_prefill()
    cmd = [
        str(llama_cli),
        "-m", str(gguf),
        "-p", full,
        "-n", str(n_predict),
        "--temp", "0",
        "--top-k", "1",
        "--seed", "42",
        "--no-display-prompt",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=180)
    return build_assistant_prefill() + res.stdout
```

**Planner notes:** 先验证 `/home/samuel/projects/EvoProgTSC/llama.cpp` 下 `convert_hf_to_gguf.py`、`llama-quantize`、`llama-cli`、`llama-tokenize`（如存在）路径。summary JSON 记录命令、return code、GGUF path/size、5-token inference tail。

---

### `tsc_cycle/v3_gates/phase1_report.py` (utility, transform)

**Analog:** `tsc_cycle/student/parity_merge.py`

**Load/report skeleton** (lines 13-25, 120-139):
```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_results(path: Path) -> tuple[dict[str, dict], dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {r["sample_id"]: r for r in raw["results"]}, raw

out_path = Path(args.out)
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"[PARITY-MERGE] wrote {out_path} overall_mae_q4_vs_hf={overall_mae_q4:.3f} parse_failures={len(parse_failures)}")

fail_ratio = len(parse_failures) / n if n else 0.0
if fail_ratio > 0.25:
    print(f"[PARITY-MERGE] FAIL: parse_failure ratio {fail_ratio:.2%} > 25%", file=sys.stderr)
    return 1
return 0
```

**Planner notes:** 聚合 `artifacts/v3/phase1/` 的 env/tokenizer/parity/memory/train_100step/gguf JSON，输出 `phase1_gate_report.json`，包含 `pass`、`fatal`、`fatal_reason`、每个 gate 的 artifact path。不要像 analog 一样追加 `.planning/STATE.md`。

---

### `scripts/run_v3_phase1_gates.sh` (utility, batch)

**Analog:** `scripts/run_pipeline.sh`

**Strict shell setup** (lines 8-17):
```bash
set -euo pipefail

# shellcheck source=/dev/null
source scripts/dgx_spark/env.sh
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"

TS="${TS:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="runs/${TS}"
mkdir -p "$RUN_DIR"
ln -sfn "$TS" runs/latest
```

**run_safe wrapped step pattern** (lines 48-58):
```bash
ADAPTER_DIR="$RUN_DIR/train/adapter"
if [ ! -d "$ADAPTER_DIR" ]; then
  echo "=== Phase 4b: QLoRA SFT (run_safe.sh wrapper) ==="
  scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.student.train \
    --output-dir "$RUN_DIR/train"
fi

if [ ! -f "$RUN_DIR/gguf/model.q4_K_M.gguf" ]; then
  echo "=== Phase 5: Merge + GGUF Export ==="
  python -m tsc_cycle.student.export_gguf --adapter "$ADAPTER_DIR" --out "$RUN_DIR"
fi
```

**Planner notes:** Phase 1 runner 按 env_smoke → tokenizer_audit → tokenizer_parity → memory_budget → 100-step → gguf_microconvert → phase1_report 顺序执行；`set -euo pipefail` 保证第一处失败即停。

---

### `scripts/dgx_spark/verify.py` (utility, request-response)

**Analog:** same file.

**Environment check pattern** (lines 19-43):
```python
def main() -> int:
    print("=== DGX Spark Environment Check ===")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Machine: {platform.machine()}")
    print(f"nvidia-smi: {run(['nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader'])}")
    print(f"Swap: {run(['swapon', '--show']) or 'disabled'}")
    print(f"MemAvailable: {run(['awk', '/MemAvailable/ {printf \"%.1f GiB\", $2/1024/1024}', '/proc/meminfo'])}")

    import torch
    print(f"torch: {torch.__version__}")
    print(f"torch CUDA: {torch.version.cuda}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        print("ERROR: CUDA is not available to PyTorch")
        return 1
```

**Import posture to modify** (lines 44-52):
```python
for name in ["transformers", "accelerate", "datasets", "peft", "deepspeed", "vllm"]:
    mod = __import__(name)
    print(f"{name}: {getattr(mod, '__version__', 'ok')}")

flash_attn = importlib.util.find_spec("flash_attn") is not None
print(f"flash_attn installed: {flash_attn}")
if flash_attn and platform.machine() == "aarch64":
    print("ERROR: upstream flash-attn should not be installed on DGX Spark")
    return 1
```

**Planner notes:** `vllm` 必须从硬 import 改为 optional/warning-only；项目明确暂时不能使用 vLLM。保留 flash-attn aarch64 fail closed。

---

### `tsc_cycle/tokenizer_check.py` (utility, transform)

**Analog:** same file.

**Hardcoded constants to replace** (lines 24-28):
```python
CUSTOM_TAGS = (TAG_THINK_OPEN, TAG_THINK_CLOSE, TAG_SOLUTION_OPEN, TAG_SOLUTION_CLOSE)
NATIVE_THINK_OPEN_ID = 151667   # <think>
NATIVE_THINK_CLOSE_ID = 151668  # </think>
EXPECTED_VOCAB_SIZE = 151936    # Qwen3-4B-Thinking-2507
```

**Leakage guard pattern** (lines 72-77):
```python
def assert_no_native_think_in_ids(token_ids: list[int]) -> None:
    """Raise AssertionError if either native think token id appears."""
    if NATIVE_THINK_OPEN_ID in token_ids:
        raise AssertionError(f"native <think> id {NATIVE_THINK_OPEN_ID} present in token_ids")
    if NATIVE_THINK_CLOSE_ID in token_ids:
        raise AssertionError(f"native </think> id {NATIVE_THINK_CLOSE_ID} present in token_ids")
```

**Planner notes:** 保留函数名/调用风格，但让 native IDs 来自 tokenizer 动态 encode 或 audit JSON；不要再导出 4B 固定 ID 给 v3 路径使用。

---

### `tsc_cycle/student/dataset.py` (utility, transform)

**Analog:** same file.

**Imports needing refactor** (lines 20-34):
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
    NATIVE_THINK_CLOSE_ID,
    NATIVE_THINK_OPEN_ID,
    check_tokenizer,
)
```

**Tokenize + mask + native leakage pattern** (lines 52-74):
```python
def tokenize_one(tokenizer, prompt: str, assistant: str, max_length: int) -> dict[str, list[int]]:
    full = prompt + "\n" + assistant + tokenizer.eos_token
    enc = tokenizer(full, truncation=True, max_length=max_length, add_special_tokens=False)
    input_ids = enc["input_ids"]

    pre = tokenizer(prompt + "\n", add_special_tokens=False)["input_ids"]
    n_prompt = len(pre)

    labels = [-100] * len(input_ids)
    for i in range(n_prompt, len(input_ids)):
        labels[i] = input_ids[i]

    if NATIVE_THINK_OPEN_ID in input_ids or NATIVE_THINK_CLOSE_ID in input_ids:
        raise AssertionError("native <think>/</think> token id found in tokenized sample")

    return {
        "input_ids": input_ids,
        "attention_mask": [1] * len(input_ids),
        "labels": labels,
    }
```

**Planner notes:** 保留 loss masking；把 native leakage check 改成动态 native IDs。

---

### `tests/test_v3_gates.py` (test, request-response)

**Analog:** `tests/test_prompt_builder.py`

**Fixture/import style** (lines 0-23):
```python
import json

from tsc_cycle.prompt_builder import (
    TAG_SOLUTION_CLOSE,
    TAG_SOLUTION_OPEN,
    TAG_THINK_CLOSE,
    TAG_THINK_OPEN,
    build_assistant_prefill,
    build_full_assistant,
    build_user_prompt,
    parse_assistant_output,
)

EX_INPUT = {
    "prediction": {
        "as_of": "2026-04-27 00:02:27",
        "phase_waits": [
            {"phase_id": 1, "pred_wait": 0.4, "pred_saturation": 0.0083,
             "min_green": 50, "max_green": 80, "capacity": 48},
            {"phase_id": 2, "pred_wait": 1.0, "pred_saturation": 0.025,
             "min_green": 20, "max_green": 45, "capacity": 40},
        ],
    }
}
```

**Assertion style** (lines 26-41):
```python
def test_user_prompt_contains_required_blocks():
    p = build_user_prompt(EX_INPUT)
    assert "你是交通信号配时优化专家。" in p
    assert "【cycle_predict_input_json】" in p and "【/cycle_predict_input_json】" in p
    assert "硬约束（必须满足）" in p
    assert "<start_working_out>" in p and "<end_working_out>" in p
    assert "<SOLUTION>" in p and "</SOLUTION>" in p
```

**Planner notes:** 测试只覆盖 fake tokenizer、report aggregation、module import、CLI parse helper；不在 pytest 中加载真实 Qwen3.5/GPU/llama.cpp。

## Shared Patterns

### Python CLI entrypoint
**Source:** `tsc_cycle/student/train.py` lines 117-132, 243-244  
**Apply to:** all `tsc_cycle/v3_gates/*.py`
```python
def main() -> int:
    ap = argparse.ArgumentParser()
    args = ap.parse_args()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

### JSON artifact writing
**Source:** `tsc_cycle/student/tokenize_sanity.py` lines 219-221  
**Apply to:** all gate JSON outputs
```python
out_path.parent.mkdir(parents=True, exist_ok=True)
with out_path.open("w", encoding="utf-8") as fh:
    json.dump(payload, fh, ensure_ascii=False, indent=2)
```

### DGX Spark safe execution
**Source:** `scripts/dgx_spark/run_safe.sh` lines 23-38  
**Apply to:** long GPU/model gates
```bash
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

### DGX Spark environment variables
**Source:** `scripts/dgx_spark/env.sh` lines 9-14  
**Apply to:** shell runner and validation commands
```bash
export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda}"
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:${LD_LIBRARY_PATH:-}"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-12.1a}"
export TRITON_PTXAS_PATH="${TRITON_PTXAS_PATH:-$CUDA_HOME/bin/ptxas}"
export PYTORCH_ALLOC_CONF="${PYTORCH_ALLOC_CONF:-expandable_segments:True,max_split_size_mb:128}"
```

### Tokenizer protocol literals
**Source:** `tsc_cycle/prompt_builder.py` lines 21-31  
**Apply to:** tokenizer audit/parity/dataset; do not duplicate custom-tag literals
```python
TAG_THINK_OPEN = "<start_working_out>"
TAG_THINK_CLOSE = "<end_working_out>"
TAG_SOLUTION_OPEN = "<SOLUTION>"
TAG_SOLUTION_CLOSE = "</SOLUTION>"
LEGACY_THINK_CLOSE = "</end_working_out>"
```

### Fail-closed error style
**Source:** `tsc_cycle/student/tokenize_sanity.py` lines 74-76; `tsc_cycle/student/parity_gguf.py` lines 182-189  
**Apply to:** all gates
```python
def _fail(msg: str) -> None:
    print(f"[TOKENIZE-SANITY] FAIL: {msg}", file=sys.stderr)
    sys.exit(1)

if not gguf_path.exists():
    print(f"[PARITY-GGUF {args.backend_label}] FAIL: gguf missing: {gguf_path}", file=sys.stderr)
    return 2
```

## No Analog Found

所有 Phase 1 预期新增/修改文件均找到可复用 analog。

| File | Role | Data Flow | Reason |
|---|---|---|---|

## Metadata

**Analog search scope:** `tsc_cycle/**/*.py`, `scripts/**/*.sh`, `tests/**/*.py`, `pyproject.toml`; excludes `.git`, `.venv`, `artifacts`, `runs`  
**Files scanned:** 36  
**Strong analogs read:** `tsc_cycle/student/train.py`, `tsc_cycle/tokenizer_check.py`, `tsc_cycle/student/tokenize_sanity.py`, `tsc_cycle/student/export_gguf.py`, `scripts/dgx_spark/run_safe.sh`, `scripts/dgx_spark/env.sh`, `scripts/dgx_spark/verify.py`, `tsc_cycle/student/parity_prompts.py`, `tsc_cycle/eval/parity.py`, `tsc_cycle/student/parity_merge.py`, `scripts/run_pipeline.sh`, `tests/test_prompt_builder.py`  
**Pattern extraction date:** 2026-05-08
