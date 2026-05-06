"""20-prompt parity test: HF bf16 vs GGUF bf16 vs GGUF q4_K_M.

Greedy decoding (do_sample=False / temperature=0). seed=42.
Reports per-sample MAE on `final` per phase across the 3 backends.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from tsc_cycle.prompt_builder import build_assistant_prefill, build_user_prompt, parse_assistant_output


def _hf_generate(model, tokenizer, prompt: str, device: str = "cuda", max_new: int = 512) -> str:
    full = prompt + "\n" + build_assistant_prefill()
    enc = tokenizer(full, return_tensors="pt").to(device)
    out = model.generate(**enc, max_new_tokens=max_new, do_sample=False, temperature=0.0)
    new_ids = out[0][enc["input_ids"].shape[1]:]
    return build_assistant_prefill() + tokenizer.decode(new_ids, skip_special_tokens=False)


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged-hf", required=True, help="merged_bf16 dir")
    ap.add_argument("--gguf-bf16", required=True)
    ap.add_argument("--gguf-q4", required=True)
    ap.add_argument("--inputs", default="data/ood_inputs.jsonl")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--llama-cli", default=os.environ.get("LLAMA_CLI", "/home/samuel/projects/EvoProgTSC/llama.cpp/llama-cli"))
    ap.add_argument("--out", default="runs/latest/parity.json")
    args = ap.parse_args()

    rng = random.Random(42)
    samples = [json.loads(line) for line in Path(args.inputs).read_text(encoding="utf-8").splitlines() if line.strip()]
    rng.shuffle(samples)
    samples = samples[: args.n]

    print(f"[PARITY] HF bf16 inference on {args.n} samples")
    tok = AutoTokenizer.from_pretrained(args.merged_hf)
    hf_model = AutoModelForCausalLM.from_pretrained(args.merged_hf, torch_dtype=torch.bfloat16,
                                                    attn_implementation="sdpa", device_map={"": 0})
    hf_model.eval()
    hf_outs = []
    for s in samples:
        prompt = build_user_prompt(s)
        text = _hf_generate(hf_model, tok, prompt)
        _, sol = parse_assistant_output(text)
        hf_outs.append({"sample_id": s["sample_id"], "solution": sol, "text": text[-200:]})
    del hf_model
    torch.cuda.empty_cache()

    print(f"[PARITY] GGUF bf16 via {args.llama_cli}")
    bf16_outs = []
    for s in samples:
        prompt = build_user_prompt(s)
        text = _gguf_generate(Path(args.llama_cli), Path(args.gguf_bf16), prompt)
        _, sol = parse_assistant_output(text)
        bf16_outs.append({"sample_id": s["sample_id"], "solution": sol})

    print(f"[PARITY] GGUF Q4_K_M")
    q4_outs = []
    for s in samples:
        prompt = build_user_prompt(s)
        text = _gguf_generate(Path(args.llama_cli), Path(args.gguf_q4), prompt)
        _, sol = parse_assistant_output(text)
        q4_outs.append({"sample_id": s["sample_id"], "solution": sol})

    # MAE q4 vs hf, bf16 vs hf
    def mae(a, b) -> float:
        if a is None or b is None:
            return float("nan")
        keys = set(a) & set(b)
        if not keys:
            return float("nan")
        return sum(abs(int(a[k]) - int(b[k])) for k in keys) / len(keys)

    rows = []
    for i, s in enumerate(samples):
        rows.append({
            "sample_id": s["sample_id"],
            "hf": hf_outs[i]["solution"],
            "gguf_bf16": bf16_outs[i]["solution"],
            "gguf_q4": q4_outs[i]["solution"],
            "mae_bf16_vs_hf": mae(bf16_outs[i]["solution"], hf_outs[i]["solution"]),
            "mae_q4_vs_hf": mae(q4_outs[i]["solution"], hf_outs[i]["solution"]),
        })

    valid_q4 = [r["mae_q4_vs_hf"] for r in rows if not (r["mae_q4_vs_hf"] != r["mae_q4_vs_hf"])]
    avg_mae_q4 = sum(valid_q4) / len(valid_q4) if valid_q4 else float("nan")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"rows": rows, "avg_mae_q4_vs_hf": avg_mae_q4}, indent=2), encoding="utf-8")
    print(f"\nq4_K_M avg MAE vs HF bf16: {avg_mae_q4:.2f} (gate: ≤ 3.0)")
    print(f"saved {args.out}")
    return 0 if avg_mae_q4 <= 3.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
