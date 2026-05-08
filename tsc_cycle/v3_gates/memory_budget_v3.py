"""Qwen3.5-9B memory budget sweep gate for v3 Phase 1.

Long GPU runs must be invoked externally through:
  scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.memory_budget_v3

This module records that wrapper requirement in JSON artifacts but never invokes sudo,
systemd-run, or run_safe itself.
"""

from __future__ import annotations

import argparse
import gc
import json
import time
from pathlib import Path
from typing import Any, Iterable

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

MODEL_NAME = "Qwen/Qwen3.5-9B"
DEFAULT_OUT = "artifacts/v3/phase1/memory_budget.json"
RUN_SAFE_COMMAND = "scripts/dgx_spark/run_safe.sh 100G --"
STRICT_MEMORY_THRESHOLD_GB = 85.0


def default_seqs() -> list[int]:
    """Return the exact required max_seq_length candidates for MEM-01."""
    return [1536, 2048, 2560, 3072, 4096]


def _is_success(record: dict[str, Any]) -> bool:
    status = str(record.get("status", "")).lower()
    if status in {"ok", "success", "passed"}:
        return True
    if "ok" in record:
        return bool(record["ok"])
    return False


def select_max_seq(results: Iterable[dict[str, Any]], threshold_gb: float = STRICT_MEMORY_THRESHOLD_GB) -> int | None:
    """Select the largest successful measured seq with peak_reserved_gb strictly below threshold.

    The comparison is intentionally strict (`<85.0` by default), matching the
    MEM-01 hard gate. Failed or unmeasured candidates are ignored.
    """
    eligible: list[int] = []
    for record in results:
        if not _is_success(record):
            continue
        peak = record.get("peak_reserved_gb")
        if peak is None:
            continue
        if float(peak) < threshold_gb:
            eligible.append(int(record["seq"]))
    if not eligible:
        return None
    return max(eligible)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure Qwen3.5-9B QLoRA memory budget candidates")
    parser.add_argument("--model", default=MODEL_NAME)
    parser.add_argument("--seqs", nargs="+", type=int, default=default_seqs())
    parser.add_argument("--seq", type=int, default=None, help="Run a single dry-run sequence length")
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accum", type=int, default=16)
    parser.add_argument("--lora-r", type=int, default=64)
    parser.add_argument("--lora-alpha", type=int, default=64)
    return parser


def command_metadata(args: argparse.Namespace) -> dict[str, Any]:
    module_cmd = [
        "python",
        "-m",
        "tsc_cycle.v3_gates.memory_budget_v3",
        "--model",
        args.model,
    ]
    if args.seq is not None:
        module_cmd.extend(["--seq", str(args.seq)])
    else:
        module_cmd.extend(["--seqs", *[str(seq) for seq in args.seqs]])
    module_cmd.extend(["--steps", str(args.steps), "--out", args.out])
    return {
        "run_safe_required": True,
        "run_safe_memory_max": "100G",
        "run_safe_command_prefix": RUN_SAFE_COMMAND,
        "documented_invocation": f"{RUN_SAFE_COMMAND} {' '.join(module_cmd)}",
        "module_command": module_cmd,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")


def _gb(num_bytes: int) -> float:
    return round(num_bytes / (1024**3), 3)


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


def make_batch(seq: int, batch_size: int, vocab_size: int) -> dict[str, torch.Tensor]:
    input_ids = torch.randint(0, vocab_size, (batch_size, seq), device="cuda", dtype=torch.long)
    attention_mask = torch.ones_like(input_ids)
    labels = input_ids.clone()
    return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


def cleanup_cuda() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


def run_candidate(model, tokenizer, seq: int, steps: int, batch_size: int, grad_accum: int) -> dict[str, Any]:
    record: dict[str, Any] = {
        "seq": seq,
        "status": "ok",
        "ok": True,
        "steps": steps,
        "peak_allocated_gb": None,
        "peak_reserved_gb": None,
        "elapsed_seconds": None,
        "error": None,
    }
    cleanup_cuda()
    torch.cuda.reset_peak_memory_stats()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    started = time.time()
    try:
        optimizer.zero_grad(set_to_none=True)
        for step in range(steps):
            batch = make_batch(seq, batch_size, len(tokenizer))
            outputs = model(**batch)
            loss = outputs.loss / grad_accum
            loss.backward()
            if ((step + 1) % grad_accum == 0) or (step + 1 == steps):
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
            del batch, outputs, loss
        torch.cuda.synchronize()
        record["peak_allocated_gb"] = _gb(torch.cuda.max_memory_allocated())
        record["peak_reserved_gb"] = _gb(torch.cuda.max_memory_reserved())
    except torch.cuda.OutOfMemoryError as exc:
        record.update({"status": "oom", "ok": False, "error": str(exc)})
        if torch.cuda.is_available():
            record["peak_allocated_gb"] = _gb(torch.cuda.max_memory_allocated())
            record["peak_reserved_gb"] = _gb(torch.cuda.max_memory_reserved())
    except Exception as exc:  # pragma: no cover - integration-only failure path
        record.update({"status": "error", "ok": False, "error": f"{type(exc).__name__}: {exc}"})
        if torch.cuda.is_available():
            record["peak_allocated_gb"] = _gb(torch.cuda.max_memory_allocated())
            record["peak_reserved_gb"] = _gb(torch.cuda.max_memory_reserved())
    finally:
        record["elapsed_seconds"] = round(time.time() - started, 3)
        del optimizer
        cleanup_cuda()
    return record


def build_payload(args: argparse.Namespace, results: list[dict[str, Any]]) -> dict[str, Any]:
    selected = args.seq if args.seq is not None and results and results[0].get("ok") else select_max_seq(results)
    ok = selected is not None
    status = "ok" if ok else "failed"
    payload = {
        "ok": ok,
        "status": status,
        "model": args.model,
        "seqs": args.seqs,
        "seq": args.seq,
        "steps": args.steps,
        "batch_size": args.batch_size,
        "grad_accum": args.grad_accum,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "lora_dropout": 0.0,
        "target_modules": "all-linear",
        "gradient_checkpointing_kwargs": {"use_reentrant": False},
        "threshold_gb": STRICT_MEMORY_THRESHOLD_GB,
        "run_safe_required": True,
        "selected_max_seq": selected,
        "results": results,
        "command": command_metadata(args),
        "error": None if ok else "no successful measured sequence below strict threshold",
    }
    if args.seq is not None and results:
        payload.update(
            {
                "peak_allocated_gb": results[0].get("peak_allocated_gb"),
                "peak_reserved_gb": results[0].get("peak_reserved_gb"),
                "error": results[0].get("error"),
            }
        )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not torch.cuda.is_available():
        payload = build_payload(args, [])
        payload.update({"status": "error", "ok": False, "error": "CUDA is required for memory budget measurement"})
        write_json(Path(args.out), payload)
        return 1

    model, tokenizer = load_qlora_model(args.model, args.lora_r, args.lora_alpha)
    seqs = [args.seq] if args.seq is not None else list(args.seqs)
    results: list[dict[str, Any]] = []
    try:
        for seq in seqs:
            results.append(run_candidate(model, tokenizer, seq, args.steps, args.batch_size, args.grad_accum))
    finally:
        del model, tokenizer
        cleanup_cuda()

    payload = build_payload(args, results)
    write_json(Path(args.out), payload)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
