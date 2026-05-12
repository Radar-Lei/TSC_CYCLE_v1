"""HF bf16 parity runner — independent subprocess.

Loads merged_bf16 HF model, runs deterministic greedy decoding on the frozen
parity prompts, writes per-prompt SOLUTION + tail to JSON, and exits so that
CUDA / unified-memory is fully released before the next backend starts.

Invoked by ``tsc_cycle.student.parity`` orchestrator via ``python -m``. Must
not be imported in-process by any other backend (avoids DGX Spark unified
memory deadlock with subsequent llama-cli child processes).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from tsc_cycle.prompt_builder import (
    build_assistant_prefill,
    build_user_prompt,
    parse_assistant_output,
)


def _hf_generate(model, tokenizer, user_prompt: str, n_predict: int) -> str:
    """Greedy bf16 decode; returns decoded text **including** the prefilled
    opening think tag so downstream parser sees the full conversation."""
    full = user_prompt + "\n" + build_assistant_prefill()
    enc = tokenizer(full, return_tensors="pt").to("cuda")
    out = model.generate(
        input_ids=enc.input_ids,
        attention_mask=enc.attention_mask,
        max_new_tokens=n_predict,
        do_sample=False,
        temperature=0.0,
        top_k=1,
        pad_token_id=tokenizer.eos_token_id,
    )
    new_ids = out[0][enc.input_ids.shape[1]:]
    return build_assistant_prefill() + tokenizer.decode(new_ids, skip_special_tokens=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="HF bf16 parity runner (single backend, exits to free GPU)")
    ap.add_argument("--merged-hf", default="runs/20260507T032419Z/merged_bf16",
                    help="Path to merged_bf16 HF directory")
    ap.add_argument("--prompts", default="runs/20260507T032419Z/gguf/parity_prompts.jsonl",
                    help="Frozen parity prompts JSONL")
    ap.add_argument("--out", default="runs/20260507T032419Z/gguf/parity_hf.json",
                    help="Output JSON path")
    ap.add_argument("--n-predict", type=int, default=384)
    args = ap.parse_args()

    prompts_path = Path(args.prompts)
    if not prompts_path.exists():
        print(f"[PARITY-HF] FAIL: prompts file missing: {prompts_path}", file=sys.stderr)
        return 2
    records = [json.loads(line) for line in prompts_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    n = len(records)
    print(f"[PARITY-HF] loaded {n} prompts from {prompts_path}", file=sys.stderr)

    print(f"[PARITY-HF] loading merged_bf16 from {args.merged_hf}", file=sys.stderr)
    tok = AutoTokenizer.from_pretrained(args.merged_hf)
    model = AutoModelForCausalLM.from_pretrained(
        args.merged_hf,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
        device_map={"": 0},
    )
    model.eval()
    torch.manual_seed(42)

    results: list[dict] = []
    t0 = time.time()
    with torch.inference_mode():
        for i, rec in enumerate(records, 1):
            sid = rec.get("sample_id", f"idx{i}")
            split = rec.get("split_hint", "?")
            try:
                user_prompt = build_user_prompt(rec["input"])
                text = _hf_generate(model, tok, user_prompt, args.n_predict)
                _, sol = parse_assistant_output(text)
                err = None if sol is not None else "solution_unparseable"
                results.append({
                    "sample_id": sid,
                    "split_hint": split,
                    "solution": sol,
                    "parse_error": err,
                    "tail": text[-300:],
                })
            except Exception as exc:  # pragma: no cover — defensive
                results.append({
                    "sample_id": sid,
                    "split_hint": split,
                    "solution": None,
                    "parse_error": f"exception: {type(exc).__name__}: {exc}",
                    "tail": "",
                })
            if i % 5 == 0 or i == n:
                print(f"[PARITY-HF] progress {i}/{n} elapsed={time.time()-t0:.1f}s", file=sys.stderr)

    total_sec = time.time() - t0

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "backend": "hf_bf16",
        "merged_hf": str(args.merged_hf),
        "n_prompts": n,
        "n_predict": args.n_predict,
        "total_sec": total_sec,
        "results": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[PARITY-HF] OK total={total_sec:.1f}s out={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
