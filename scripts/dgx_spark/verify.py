#!/usr/bin/env python3
"""Verify a DGX Spark CUDA 13 training environment."""

from __future__ import annotations

import importlib.util
import os
import platform
import subprocess
import sys


def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:  # noqa: BLE001
        return f"unavailable: {exc}"


def main() -> int:
    print("=== DGX Spark Environment Check ===")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Machine: {platform.machine()}")
    print(f"nvidia-smi: {run(['nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader'])}")
    print(f"Swap: {run(['swapon', '--show']) or 'disabled'}")
    print(f"MemAvailable: {run(['awk', '/MemAvailable/ {printf \"%.1f GiB\", $2/1024/1024}', '/proc/meminfo'])}")
    print()

    import torch

    print(f"torch: {torch.__version__}")
    print(f"torch CUDA: {torch.version.cuda}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if not torch.cuda.is_available():
        print("ERROR: CUDA is not available to PyTorch")
        return 1

    print(f"GPU: {torch.cuda.get_device_name(0)}")
    x = torch.randn(1024, 1024, device="cuda", dtype=torch.bfloat16)
    y = x @ x
    torch.cuda.synchronize()
    print(f"bf16 matmul: {tuple(y.shape)} {y.dtype} {y.device}")
    print()

    required_packages = ["transformers", "accelerate", "datasets", "peft"]
    optional_packages = ["deepspeed", "vllm"]

    for name in required_packages:
        try:
            mod = __import__(name)
        except ImportError as exc:
            print(f"ERROR: required {name}: unavailable ({exc})")
            return 1
        print(f"{name}: {getattr(mod, '__version__', 'ok')}")

    for name in optional_packages:
        try:
            mod = __import__(name)
        except ImportError:
            print(f"optional {name}: unavailable")
            continue
        print(f"optional {name}: {getattr(mod, '__version__', 'ok')}")

    flash_attn = importlib.util.find_spec("flash_attn") is not None
    print(f"flash_attn installed: {flash_attn}")
    if flash_attn and platform.machine() == "aarch64":
        print("ERROR: upstream flash-attn should not be installed on DGX Spark")
        return 1

    ptxas = os.environ.get("TRITON_PTXAS_PATH")
    print(f"TRITON_PTXAS_PATH: {ptxas or 'unset'}")
    if not ptxas or not os.path.exists(ptxas):
        print("ERROR: set TRITON_PTXAS_PATH=/usr/local/cuda/bin/ptxas")
        return 1

    print()
    print("OK: DGX Spark training environment is ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
