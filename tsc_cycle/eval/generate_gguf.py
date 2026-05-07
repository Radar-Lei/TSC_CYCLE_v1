"""GGUF EVL generation runner — shared by gguf_bf16 and gguf_q4_K_M backends.

Based on tsc_cycle/student/parity_gguf.py (single-load llama-server pattern),
adapted for the 600-prompt evaluation suite with per-sample cache files
(matching tsc_cycle.eval.generate_hf schema).

Why llama-server (not llama-cli per prompt): on DGX Spark GB10, each
``llama-cli`` subprocess pays ~5 minutes of cold-start. Server amortises
load across all 600 prompts.

Why per-sample JSON files (not one aggregated JSON): supports interrupt
recovery — re-running skips already-generated samples. Matches the
generate_hf.py cache schema so plan 06-05 can index uniformly across
all four backends.

Spawns:
    /home/samuel/llama.cpp/build/bin/llama-server
        -m <gguf-path> -ngl 99 -c 4096 -t 4 --host 127.0.0.1 --port <p>

Then for each NEW prompt POSTs ``/completion`` with deterministic params
(temperature=0, top_k=1, seed=42, n_predict=384). Cache schema:

    {"sample_id", "split_hint", "backend", "solution", "parse_error",
     "raw_text", "elapsed_sec", "n_predict", "seed"}

This module **does not** import torch/transformers/peft.

Usage:
    python -m tsc_cycle.eval.generate_gguf \\
        --gguf-path runs/.../gguf/model.bf16.gguf \\
        --backend-label gguf_bf16 \\
        --prompts runs/.../eval/eval_prompts.jsonl \\
        --cache-dir runs/.../eval/gen_cache/gguf_bf16 \\
        --n-predict 384
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from tsc_cycle.prompt_builder import (
    build_assistant_prefill,
    build_user_prompt,
    parse_assistant_output,
)
from tsc_cycle.student.parity_gguf import (
    _find_free_port,
    _kill_server,
    _post_completion,
    _spawn_server,
    _wait_health,
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="GGUF EVL generation runner via llama-server (model loaded once)"
    )
    ap.add_argument("--gguf-path", required=True)
    ap.add_argument(
        "--backend-label",
        required=True,
        help="e.g. gguf_bf16 or gguf_q4_K_M; written into every cache file's "
             "`backend` field; also used in cache filename layout if caller "
             "embeds it in --cache-dir.",
    )
    ap.add_argument(
        "--prompts",
        default="runs/20260507T032419Z/eval/eval_prompts.jsonl",
    )
    ap.add_argument("--cache-dir", required=True)
    # NOTE: must use the /home/samuel/llama.cpp build (links libggml-cuda.so +
    # cuBLAS, detects GB10 122GB VRAM). Do NOT use any CPU-only build.
    ap.add_argument(
        "--llama-server",
        default="/home/samuel/llama.cpp/build/bin/llama-server",
    )
    ap.add_argument("--n-predict", type=int, default=384)
    ap.add_argument("--timeout-sec", type=int, default=600,
                    help="Per-prompt HTTP timeout")
    ap.add_argument("--server-startup-sec", type=int, default=180,
                    help="Time budget for /health to come up")
    ap.add_argument("--ngl", type=int, default=99)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--ctx-size", type=int, default=4096)
    args = ap.parse_args()

    label = args.backend_label
    llama_server = Path(args.llama_server)
    gguf_path = Path(args.gguf_path)
    if not llama_server.exists():
        print(f"[GEN-GGUF {label}] FAIL: llama-server missing: {llama_server}",
              file=sys.stderr)
        return 2
    if not gguf_path.exists():
        print(f"[GEN-GGUF {label}] FAIL: gguf missing: {gguf_path}",
              file=sys.stderr)
        return 2

    prompts_path = Path(args.prompts)
    records = [
        json.loads(line)
        for line in prompts_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    n = len(records)
    if n == 0:
        print(f"[GEN-GGUF {label}] FAIL: no prompts in {prompts_path}",
              file=sys.stderr)
        return 2

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    todo = [r for r in records if not (cache_dir / f"{r['sample_id']}.json").exists()]
    n_todo = len(todo)
    if n_todo == 0:
        print(f"[GEN-GGUF {label}] OK all-cached n={n} cache_dir={cache_dir}")
        return 0

    print(f"[GEN-GGUF {label}] resume: {n - n_todo}/{n} cached, {n_todo} todo",
          file=sys.stderr)

    port = _find_free_port()
    server_log = cache_dir.parent / f"server_{label}.log"
    print(f"[GEN-GGUF {label}] n_todo={n_todo} ngl={args.ngl} threads={args.threads} "
          f"ctx={args.ctx_size} timeout={args.timeout_sec}s port={port} "
          f"server_log={server_log}", file=sys.stderr)

    proc = _spawn_server(llama_server, gguf_path, port, args.ngl, args.threads,
                         args.ctx_size, server_log)
    server_t0 = time.time()
    try:
        if not _wait_health(port, args.server_startup_sec):
            print(f"[GEN-GGUF {label}] FAIL: /health never returned 200 within "
                  f"{args.server_startup_sec}s; see {server_log}", file=sys.stderr)
            return 3
        startup_sec = time.time() - server_t0
        print(f"[GEN-GGUF {label}] server healthy after {startup_sec:.1f}s",
              file=sys.stderr)

        infer_t0 = time.time()
        for i, rec in enumerate(todo, 1):
            sid = rec["sample_id"]
            split = rec.get("split_hint", "?")
            user_prompt = build_user_prompt(rec["input"])
            full = user_prompt + "\n" + build_assistant_prefill()
            text, meta = _post_completion(port, full, args.n_predict, args.timeout_sec)
            if meta["timeout"]:
                sol, err = None, "timeout"
            elif meta.get("http_status") is None:
                sol, err = None, f"http_error: {meta.get('error', 'unknown')}"
            else:
                _, sol = parse_assistant_output(text)
                err = None if sol is not None else "solution_unparseable"

            out = {
                "sample_id": sid,
                "split_hint": split,
                "backend": label,
                "solution": sol,
                "parse_error": err,
                "raw_text": text,
                "elapsed_sec": meta["elapsed_sec"],
                "n_predict": args.n_predict,
                "seed": 42,
            }
            (cache_dir / f"{sid}.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            if i % 10 == 0 or i == n_todo:
                print(f"[GEN-GGUF {label}] progress {i}/{n_todo} "
                      f"elapsed={time.time() - infer_t0:.1f}s",
                      file=sys.stderr)
    finally:
        _kill_server(proc)
        print(f"[GEN-GGUF {label}] server reaped", file=sys.stderr)

    total_cached = sum(
        1 for r in records if (cache_dir / f"{r['sample_id']}.json").exists()
    )
    print(f"[GEN-GGUF {label}] OK generated={n_todo} total_cached={total_cached} "
          f"server_log={server_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
