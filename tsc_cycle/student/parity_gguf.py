"""GGUF parity runner via llama-server — shared by bf16 and q4_K_M backends.

Why llama-server (not llama-cli per prompt): on DGX Spark GB10, each
``llama-cli`` subprocess pays ~5 minutes of cold-start for the 4B model
(model load + CUDA context init + KV-cache pre-allocation, even with
``-c 4096``). Per-prompt subprocess.run of cli was empirically blocked
at >5 min/prompt * 20 prompts = ~100 min/backend, exceeding the plan's
1500 s/backend timing assertion. Switching to llama-server amortises
the cold-start across all 20 prompts (load once, POST 20 times).

The orchestrator still runs each backend in its own python subprocess
(parity_gguf invocation), so the unified-memory deadlock guard is
preserved: the server is spawned and reaped within this single
process; CUDA context is fully released when the process exits.

Spawns:
    /home/samuel/llama.cpp/build/bin/llama-server
        -m <gguf-path> -ngl 99 -c 4096 -t 4 --host 127.0.0.1 --port <p>

Then for each prompt POSTs ``/completion`` with deterministic params
(temperature=0, top_k=1, seed=42, n_predict=384). Output JSON shape is
identical across bf16 / q4 backends so parity_merge can index uniformly.

This module **does not** import torch/transformers/peft — only stdlib +
project prompt builder.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from tsc_cycle.prompt_builder import (
    build_assistant_prefill,
    build_user_prompt,
    parse_assistant_output,
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_health(port: int, timeout_sec: int) -> bool:
    """Poll /health until 200 or timeout. Returns True if healthy."""
    deadline = time.time() + timeout_sec
    url = f"http://127.0.0.1:{port}/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionResetError, OSError):
            pass
        time.sleep(2)
    return False


def _post_completion(
    port: int,
    prompt: str,
    n_predict: int,
    timeout_sec: int,
) -> tuple[str, dict]:
    """POST /completion; returns (content_text_with_prefill, meta).

    meta = {"timeout": bool, "elapsed_sec": float, "http_status": int|None}
    """
    body = json.dumps({
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": 0.0,
        "top_k": 1,
        "seed": 42,
        "cache_prompt": True,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/completion",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        elapsed = time.time() - t0
        content = payload.get("content", "")
        return (
            build_assistant_prefill() + content,
            {"timeout": False, "elapsed_sec": elapsed, "http_status": resp.status},
        )
    except (TimeoutError, urllib.error.URLError) as exc:
        elapsed = time.time() - t0
        is_timeout = isinstance(exc, TimeoutError) or (
            isinstance(exc, urllib.error.URLError) and "timed out" in str(exc).lower()
        )
        return "", {
            "timeout": is_timeout,
            "elapsed_sec": elapsed,
            "http_status": None,
            "error": str(exc),
        }


def _spawn_server(
    llama_server: Path,
    gguf_path: Path,
    port: int,
    ngl: int,
    threads: int,
    ctx_size: int,
    log_path: Path,
) -> subprocess.Popen:
    cmd = [
        str(llama_server),
        "-m", str(gguf_path),
        "--host", "127.0.0.1",
        "--port", str(port),
        "-ngl", str(ngl),
        "-t", str(threads),
        "-c", str(ctx_size),
        "--no-webui",
    ]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_fh = log_path.open("w", encoding="utf-8")
    print(f"[PARITY-GGUF] spawning server: {' '.join(cmd)}", file=sys.stderr)
    proc = subprocess.Popen(
        cmd, stdout=log_fh, stderr=log_fh,
        preexec_fn=os.setsid,  # own process group → clean teardown via SIGTERM
    )
    return proc


def _kill_server(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)


def main() -> int:
    ap = argparse.ArgumentParser(description="GGUF parity runner via llama-server (model loaded once)")
    ap.add_argument("--gguf-path", required=True)
    ap.add_argument("--backend-label", required=True)
    ap.add_argument("--prompts", default="runs/20260507T032419Z/gguf/parity_prompts.jsonl")
    ap.add_argument("--out", required=True)
    # NOTE: EvoProgTSC/llama.cpp build is CPU-only; the /home/samuel/llama.cpp
    # build links libggml-cuda.so + cuBLAS and detects GB10 (122GB VRAM).
    ap.add_argument("--llama-server", default="/home/samuel/llama.cpp/build/bin/llama-server")
    ap.add_argument("--n-predict", type=int, default=384)
    ap.add_argument("--timeout-sec", type=int, default=600,
                    help="Per-prompt HTTP timeout")
    ap.add_argument("--server-startup-sec", type=int, default=180,
                    help="Time budget for /health to come up")
    ap.add_argument("--ngl", type=int, default=99)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--ctx-size", type=int, default=4096)
    args = ap.parse_args()

    llama_server = Path(args.llama_server)
    gguf_path = Path(args.gguf_path)
    if not llama_server.exists():
        print(f"[PARITY-GGUF {args.backend_label}] FAIL: llama-server missing: {llama_server}", file=sys.stderr)
        return 2
    if not gguf_path.exists():
        print(f"[PARITY-GGUF {args.backend_label}] FAIL: gguf missing: {gguf_path}", file=sys.stderr)
        return 2

    prompts_path = Path(args.prompts)
    records = [json.loads(line) for line in prompts_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    n = len(records)

    port = _find_free_port()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    server_log = out_path.parent / f"server_{args.backend_label}.log"

    print(f"[PARITY-GGUF {args.backend_label}] n={n} ngl={args.ngl} threads={args.threads} "
          f"ctx={args.ctx_size} timeout={args.timeout_sec}s port={port}", file=sys.stderr)

    proc = _spawn_server(llama_server, gguf_path, port, args.ngl, args.threads,
                         args.ctx_size, server_log)
    server_t0 = time.time()
    try:
        if not _wait_health(port, args.server_startup_sec):
            print(f"[PARITY-GGUF {args.backend_label}] FAIL: /health never returned 200 within "
                  f"{args.server_startup_sec}s; see {server_log}", file=sys.stderr)
            return 3
        startup_sec = time.time() - server_t0
        print(f"[PARITY-GGUF {args.backend_label}] server healthy after {startup_sec:.1f}s", file=sys.stderr)

        results: list[dict] = []
        infer_t0 = time.time()
        for i, rec in enumerate(records, 1):
            sid = rec.get("sample_id", f"idx{i}")
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
            results.append({
                "sample_id": sid,
                "split_hint": split,
                "solution": sol,
                "parse_error": err,
                "elapsed_sec": meta["elapsed_sec"],
                "timeout": meta["timeout"],
                "http_status": meta.get("http_status"),
                "tail": text[-300:],
            })
            if i % 5 == 0 or i == n:
                print(f"[PARITY-GGUF {args.backend_label}] progress {i}/{n} "
                      f"cumulative_infer={time.time()-infer_t0:.1f}s",
                      file=sys.stderr)

        infer_sec = time.time() - infer_t0
        # total_sec = startup + inference (this is the wall time the user
        # sees; matches plan's "single backend total_sec" semantics)
        total_sec = startup_sec + infer_sec
    finally:
        _kill_server(proc)
        print(f"[PARITY-GGUF {args.backend_label}] server reaped", file=sys.stderr)

    out_path.write_text(json.dumps({
        "backend": args.backend_label,
        "gguf_path": str(gguf_path),
        "llama_server": str(llama_server),
        "ngl": args.ngl,
        "threads": args.threads,
        "ctx_size": args.ctx_size,
        "n_prompts": n,
        "n_predict": args.n_predict,
        "timeout_sec": args.timeout_sec,
        "server_startup_sec": startup_sec,
        "inference_sec": infer_sec,
        "total_sec": total_sec,
        "results": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[PARITY-GGUF {args.backend_label}] OK total={total_sec:.1f}s "
          f"(startup={startup_sec:.1f}s + infer={infer_sec:.1f}s) out={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
