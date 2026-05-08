"""Qwen3.5-9B memory budget sweep gate for v3 Phase 1.

Long GPU runs must be invoked externally through:
  scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.v3_gates.memory_budget_v3

This module records that wrapper requirement in JSON artifacts but never invokes sudo,
systemd-run, or run_safe itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = {
        "ok": False,
        "status": "runtime_not_implemented",
        "model": args.model,
        "seqs": args.seqs,
        "seq": args.seq,
        "steps": args.steps,
        "batch_size": args.batch_size,
        "grad_accum": args.grad_accum,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "threshold_gb": STRICT_MEMORY_THRESHOLD_GB,
        "command": command_metadata(args),
        "error": "runtime path is implemented in Task 04-02",
    }
    write_json(Path(args.out), payload)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
