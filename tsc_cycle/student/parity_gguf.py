"""GGUF parity runner via llama-cli — shared by bf16 and q4_K_M backends.

Spawns llama-cli with ``-ngl 99`` (full GPU offload) per prompt. The
``--gguf-path`` and ``--backend-label`` flags differentiate the two
backends; output JSON shape is identical across them so ``parity_merge``
can index uniformly.

Fixes a bug in the legacy ``tsc_cycle.eval.parity._gguf_generate``:
1. legacy command lacked ``-ngl`` → CPU-only inference timed out at 180s
2. legacy timeout was 180s; bumped default to 600s
This module **does not** import torch/transformers — only stdlib + project
prompt builder. That means it is safe to launch this subprocess after the
HF backend has fully exited, with no unified-memory deadlock.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from tsc_cycle.prompt_builder import (
    build_assistant_prefill,
    build_user_prompt,
    parse_assistant_output,
)


def _gguf_generate(
    llama_cli: Path,
    gguf_path: Path,
    user_prompt: str,
    n_predict: int,
    timeout_sec: int,
    ngl: int,
    threads: int,
) -> tuple[str, dict]:
    """Run one llama-cli invocation; return (decoded_text_with_prefill, meta).

    meta = {"timeout": bool, "elapsed_sec": float, "returncode": int|None}
    """
    full = user_prompt + "\n" + build_assistant_prefill()
    cmd = [
        str(llama_cli),
        "-m", str(gguf_path),
        "-p", full,
        "-n", str(n_predict),
        "--temp", "0",
        "--top-k", "1",
        "--seed", "42",
        "-ngl", str(ngl),
        "--threads", str(threads),
        "--no-display-prompt",
        "--simple-io",
    ]
    t0 = time.time()
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        return "", {"timeout": True, "elapsed_sec": elapsed, "returncode": None}

    elapsed = time.time() - t0
    return (
        build_assistant_prefill() + res.stdout,
        {"timeout": False, "elapsed_sec": elapsed, "returncode": res.returncode},
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="GGUF parity runner via llama-cli")
    ap.add_argument("--gguf-path", required=True, help="Path to .gguf file (bf16 or q4_K_M)")
    ap.add_argument("--backend-label", required=True,
                    help='e.g. "gguf_bf16" or "gguf_q4_K_M"')
    ap.add_argument("--prompts", default="runs/20260507T032419Z/gguf/parity_prompts.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--llama-cli", default="/home/samuel/projects/EvoProgTSC/llama.cpp/llama-cli")
    ap.add_argument("--n-predict", type=int, default=384)
    ap.add_argument("--timeout-sec", type=int, default=600)
    ap.add_argument("--ngl", type=int, default=99, help="GPU layers to offload (default 99 = all)")
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    llama_cli = Path(args.llama_cli)
    gguf_path = Path(args.gguf_path)
    if not llama_cli.exists():
        print(f"[PARITY-GGUF {args.backend_label}] FAIL: llama-cli missing: {llama_cli}", file=sys.stderr)
        return 2
    if not gguf_path.exists():
        print(f"[PARITY-GGUF {args.backend_label}] FAIL: gguf missing: {gguf_path}", file=sys.stderr)
        return 2

    prompts_path = Path(args.prompts)
    records = [json.loads(line) for line in prompts_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    n = len(records)
    print(f"[PARITY-GGUF {args.backend_label}] loaded {n} prompts; ngl={args.ngl} threads={args.threads} timeout={args.timeout_sec}s",
          file=sys.stderr)

    results: list[dict] = []
    t0 = time.time()
    for i, rec in enumerate(records, 1):
        sid = rec.get("sample_id", f"idx{i}")
        split = rec.get("split_hint", "?")
        user_prompt = build_user_prompt(rec["input"])
        text, meta = _gguf_generate(
            llama_cli, gguf_path, user_prompt,
            args.n_predict, args.timeout_sec, args.ngl, args.threads,
        )
        if meta["timeout"]:
            sol, err = None, "timeout"
        else:
            _, sol = parse_assistant_output(text)
            err = None if sol is not None else "solution_unparseable"
        results.append({
            "sample_id": sid,
            "split_hint": split,
            "solution": sol,
            "parse_error": err,
            "elapsed_sec": meta["elapsed_sec"],
            "timeout": meta["timeout"],
            "returncode": meta.get("returncode"),
            "tail": text[-300:],
        })
        if i % 5 == 0 or i == n:
            print(f"[PARITY-GGUF {args.backend_label}] progress {i}/{n} cumulative={time.time()-t0:.1f}s",
                  file=sys.stderr)

    total_sec = time.time() - t0
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "backend": args.backend_label,
        "gguf_path": str(gguf_path),
        "llama_cli": str(llama_cli),
        "ngl": args.ngl,
        "threads": args.threads,
        "n_prompts": n,
        "n_predict": args.n_predict,
        "timeout_sec": args.timeout_sec,
        "total_sec": total_sec,
        "results": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[PARITY-GGUF {args.backend_label}] OK total={total_sec:.1f}s out={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
