"""Top-level parity orchestrator — DGX Spark unified-memory safe.

Serially launches **four independent subprocesses** so that GPU / unified
memory is fully released between backends:

    1. ``python -m tsc_cycle.student.parity_hf``    — HF bf16 (transformers)
    2. ``python -m tsc_cycle.student.parity_gguf``  — GGUF bf16  (llama-cli)
    3. ``python -m tsc_cycle.student.parity_gguf``  — GGUF q4_K_M (llama-cli)
    4. ``python -m tsc_cycle.student.parity_merge`` — write parity_report.json

This module **must not** import torch / transformers / GGUF — keeping the
orchestrator footprint tiny ensures no model state lingers across the
``subprocess.run`` boundaries (the historical root cause of OOM-deadlocks
on DGX Spark Blackwell with concurrent llama-cli children).

Pre-flight checks (fail-fast):
    * ``swapon --show`` must be empty (DGX Spark unified-memory + swap
      death-spiral mitigation per project CLAUDE.md).

Per-step diagnostics: ``nvidia-smi`` memory-used/free is printed to stderr
before and after each backend so a regression in subprocess GPU release is
visible in the run log.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _diag(label: str) -> None:
    """Print nvidia-smi memory snapshot to stderr; never fails the run."""
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.free", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        out = res.stdout.strip().replace("\n", " | ")
        print(f"[DIAG {label}] {out or '(no output)'}", file=sys.stderr)
    except Exception as exc:  # pragma: no cover
        print(f"[DIAG {label}] nvidia-smi unavailable: {exc}", file=sys.stderr)


def _run(cmd: list[str], stage: str) -> None:
    """Run a subprocess; raise SystemExit with same code on non-zero."""
    print(f"[PARITY] >>> {stage}: {' '.join(cmd)}", file=sys.stderr)
    res = subprocess.run(cmd, check=False)
    if res.returncode != 0:
        print(f"[PARITY] FAIL stage={stage} rc={res.returncode}", file=sys.stderr)
        raise SystemExit(res.returncode)


def main() -> int:
    ap = argparse.ArgumentParser(description="Three-backend parity orchestrator (subprocess-isolated)")
    ap.add_argument("--merged-hf", default="runs/20260507T032419Z/merged_bf16")
    ap.add_argument("--gguf-bf16", default="runs/20260507T032419Z/gguf/model.bf16.gguf")
    ap.add_argument("--gguf-q4", default="runs/20260507T032419Z/gguf/model.q4_K_M.gguf")
    ap.add_argument("--prompts", default="runs/20260507T032419Z/gguf/parity_prompts.jsonl")
    ap.add_argument("--hf-out", default="runs/20260507T032419Z/gguf/parity_hf.json")
    ap.add_argument("--bf16-out", default="runs/20260507T032419Z/gguf/parity_gguf_bf16.json")
    ap.add_argument("--q4-out", default="runs/20260507T032419Z/gguf/parity_gguf_q4.json")
    ap.add_argument("--report", default="runs/20260507T032419Z/gguf/parity_report.json")
    # See parity_gguf.py for rationale: switched from llama-cli (per-prompt
    # subprocess.run with ~5 min cold-start each) to llama-server (one model
    # load, then HTTP POST per prompt). The EvoProgTSC build is CPU-only;
    # /home/samuel/llama.cpp/build/bin is the CUDA-linked variant.
    ap.add_argument("--llama-server", default="/home/samuel/llama.cpp/build/bin/llama-server")
    ap.add_argument("--n-predict", type=int, default=384)
    ap.add_argument("--timeout-sec", type=int, default=600)
    args = ap.parse_args()

    # --- Pre-flight: swap must be off (DGX Spark unified-memory deadlock guard).
    swap = subprocess.run(["swapon", "--show"], capture_output=True, text=True, check=False)
    if swap.stdout.strip():
        print(f"[PARITY] FAIL: swap is ON (will OOM-deadlock on DGX Spark):\n{swap.stdout}", file=sys.stderr)
        print("[PARITY] mitigation: sudo swapoff -a", file=sys.stderr)
        return 2
    print("[PARITY] swap=off OK", file=sys.stderr)

    # --- Pre-flight: required artifacts exist.
    for label, p in [("merged_hf", args.merged_hf), ("gguf_bf16", args.gguf_bf16),
                     ("gguf_q4", args.gguf_q4), ("prompts", args.prompts),
                     ("llama_server", args.llama_server)]:
        if not Path(p).exists():
            print(f"[PARITY] FAIL: missing {label}: {p}", file=sys.stderr)
            return 2

    py = sys.executable

    # --- Stage 1: HF bf16 (transformers in its own process; exits to free GPU).
    _diag("pre_hf")
    _run([
        py, "-m", "tsc_cycle.student.parity_hf",
        "--merged-hf", args.merged_hf,
        "--prompts", args.prompts,
        "--out", args.hf_out,
        "--n-predict", str(args.n_predict),
    ], stage="parity_hf")
    _diag("post_hf")

    # --- Stage 2: GGUF bf16 via llama-cli.
    _diag("pre_bf16")
    _run([
        py, "-m", "tsc_cycle.student.parity_gguf",
        "--gguf-path", args.gguf_bf16,
        "--backend-label", "gguf_bf16",
        "--prompts", args.prompts,
        "--out", args.bf16_out,
        "--llama-server", args.llama_server,
        "--n-predict", str(args.n_predict),
        "--timeout-sec", str(args.timeout_sec),
    ], stage="parity_gguf_bf16")
    _diag("post_bf16")

    # --- Stage 3: GGUF q4_K_M via llama-cli.
    _diag("pre_q4")
    _run([
        py, "-m", "tsc_cycle.student.parity_gguf",
        "--gguf-path", args.gguf_q4,
        "--backend-label", "gguf_q4_K_M",
        "--prompts", args.prompts,
        "--out", args.q4_out,
        "--llama-server", args.llama_server,
        "--n-predict", str(args.n_predict),
        "--timeout-sec", str(args.timeout_sec),
    ], stage="parity_gguf_q4")
    _diag("post_q4")

    # --- Stage 4: merge + report.
    _run([
        py, "-m", "tsc_cycle.student.parity_merge",
        "--hf-json", args.hf_out,
        "--bf16-json", args.bf16_out,
        "--q4-json", args.q4_out,
        "--out", args.report,
    ], stage="parity_merge")

    print(f"[PARITY] ALL OK report={args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
