"""Phase 5: merge LoRA → bf16 base, then HF → GGUF bf16 → Q4_K_M.

Usage:
  python -m tsc_cycle.student.export_gguf --adapter runs/<ts>/train/adapter --out runs/<ts>
"""

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
    if len(tok) != res.details["vocab_size"]:
        pass  # ok
    print(f"[MERGE] done; merged vocab_size={len(tok)}")


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", required=True, help="path to QLoRA adapter dir")
    ap.add_argument("--base-model", default="Qwen/Qwen3-4B-Thinking-2507")
    ap.add_argument("--out", required=True, help="output base dir; writes merged_bf16/, gguf/")
    args = ap.parse_args()

    out = Path(args.out)
    merged_dir = out / "merged_bf16"
    gguf_dir = out / "gguf"
    bf16_gguf = gguf_dir / "model.bf16.gguf"
    q4_gguf = gguf_dir / "model.q4_K_M.gguf"

    merge_to_bf16(Path(args.adapter), merged_dir, args.base_model)
    hf_to_gguf_bf16(merged_dir, bf16_gguf)
    quantize(bf16_gguf, q4_gguf, "Q4_K_M")

    sizes = {
        "merged_bf16_dir": str(merged_dir),
        "gguf_bf16": {"path": str(bf16_gguf), "size_mb": bf16_gguf.stat().st_size // (1024*1024)},
        "gguf_q4_K_M": {"path": str(q4_gguf), "size_mb": q4_gguf.stat().st_size // (1024*1024)},
    }
    (out / "export_summary.json").write_text(json.dumps(sizes, indent=2), encoding="utf-8")
    print("\n=== EXPORT DONE ===")
    print(json.dumps(sizes, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
