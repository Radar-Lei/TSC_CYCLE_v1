"""Phase 10: merge v4 LoRA adapter, convert HF safetensors to GGUF fp16, then quantize q4_K_M.

This module is intentionally executable-only for the heavy model stack: gate/planning
code lives in :mod:`tsc_cycle.v4_gates.phase10_export` so tests can import it without
loading torch/transformers/peft at collection time.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from tsc_cycle.v4_gates.phase10_export import (
    DEFAULT_LLAMA_CPP,
    DEFAULT_PHASE9_REPORT,
    PHASE9_RUN_ROOT,
    Phase10ExportError,
    plan_phase10_export,
    write_export_report,
)

BASE_MODEL = "Qwen/Qwen3-4B-Thinking-2507"


def _lazy_model_stack():
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    return torch, PeftModel, AutoModelForCausalLM, AutoTokenizer


def _base_model_from_adapter_config(adapter_dir: Path) -> str:
    config_path = adapter_dir / "adapter_config.json"
    if not config_path.is_file():
        return BASE_MODEL
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return BASE_MODEL
    value = payload.get("base_model_name_or_path")
    return value if isinstance(value, str) and value else BASE_MODEL


def merge_to_fp16(adapter_dir: Path, out_merged: Path, base_model: str | None = None) -> None:
    torch, PeftModel, AutoModelForCausalLM, AutoTokenizer = _lazy_model_stack()
    model_name = base_model or _base_model_from_adapter_config(adapter_dir)
    print(f"[MERGE] reload base with SDPA: {model_name}", flush=True)
    base = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,
        attn_implementation="sdpa",
        device_map={"": 0},
    )
    print(f"[MERGE] attach LoRA adapter: {adapter_dir}", flush=True)
    peft_model = PeftModel.from_pretrained(base, adapter_dir)
    print("[MERGE] merge_and_unload", flush=True)
    merged = peft_model.merge_and_unload()
    out_merged.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(out_merged, safe_serialization=True)
    tokenizer = AutoTokenizer.from_pretrained(adapter_dir, trust_remote_code=True)
    tokenizer.save_pretrained(out_merged)
    print(f"[MERGE] done: {out_merged}", flush=True)


def hf_to_gguf_fp16(merged_dir: Path, out_gguf: Path, *, convert: Path, python: str = sys.executable) -> list[str]:
    out_gguf.parent.mkdir(parents=True, exist_ok=True)
    cmd = [python, str(convert), str(merged_dir), "--outfile", str(out_gguf), "--outtype", "f16"]
    print("[CONVERT] " + json.dumps(cmd, ensure_ascii=False), flush=True)
    subprocess.run(cmd, check=True)
    return cmd


def quantize_q4(in_gguf: Path, out_gguf: Path, *, quantize: Path) -> list[str]:
    out_gguf.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(quantize), str(in_gguf), str(out_gguf), "Q4_K_M"]
    print("[QUANT] " + json.dumps(cmd, ensure_ascii=False), flush=True)
    subprocess.run(cmd, check=True)
    return cmd


def run_export(args: argparse.Namespace) -> dict[str, Any]:
    plan = plan_phase10_export(
        phase9_report=Path(args.phase9_report),
        run_root=Path(args.run_root),
        llama_cpp_dir=Path(args.llama_cpp),
        merged_dir=Path(args.merged_dir),
        fp16_gguf=Path(args.fp16_gguf),
        q4_gguf=Path(args.q4_gguf),
        report=Path(args.report),
    )
    if not plan["ok"]:
        raise Phase10ExportError(f"phase10 export plan is red: {plan['fatal_failures']}")

    adapter_dir = Path(str(plan["adapter_path"]))
    merged_dir = Path(args.merged_dir)
    fp16_gguf = Path(args.fp16_gguf)
    q4_gguf = Path(args.q4_gguf)
    llama_cpp = plan["llama_cpp"]

    merge_to_fp16(adapter_dir, merged_dir, base_model=args.base_model)
    convert_cmd = hf_to_gguf_fp16(merged_dir, fp16_gguf, convert=Path(llama_cpp["convert"]), python=args.python)
    quant_cmd = quantize_q4(fp16_gguf, q4_gguf, quantize=Path(llama_cpp["quantize"]))

    plan.setdefault("commands", {})["convert_fp16"] = convert_cmd
    plan.setdefault("commands", {})["quantize_q4_K_M"] = quant_cmd
    return write_export_report(Path(args.run_root), plan, Path(args.report))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge v4 adapter and export GGUF fp16/q4_K_M")
    parser.add_argument("--phase9-report", default=str(DEFAULT_PHASE9_REPORT))
    parser.add_argument("--run-root", default=str(PHASE9_RUN_ROOT))
    parser.add_argument("--llama-cpp", default=os.environ.get("LLAMA_CPP_DIR", str(DEFAULT_LLAMA_CPP)))
    parser.add_argument("--merged-dir", default=str(PHASE9_RUN_ROOT / "merged_hf"))
    parser.add_argument("--fp16-gguf", default=str(PHASE9_RUN_ROOT / "gguf" / "model.fp16.gguf"))
    parser.add_argument("--q4-gguf", default=str(PHASE9_RUN_ROOT / "gguf" / "model.q4_K_M.gguf"))
    parser.add_argument("--report", default=str(PHASE9_RUN_ROOT / "phase10_export_report.json"))
    parser.add_argument("--base-model", default=None)
    parser.add_argument("--python", default=sys.executable)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_export(args)
    print("\n=== PHASE 10 EXPORT DONE ===", flush=True)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), flush=True)
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
