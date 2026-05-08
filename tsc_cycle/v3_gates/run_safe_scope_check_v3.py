"""run_safe memory scope and swap evidence gate for v3.0 Phase 1."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_OUT = "artifacts/v3/phase1/run_safe_scope.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify swap=0 and run_safe 100G systemd scope.")
    parser.add_argument("--out", default=DEFAULT_OUT)
    return parser


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def check_swap_disabled() -> tuple[bool, str]:
    """Return whether host swap is disabled; never mutate swap state."""
    result = _run(["swapon", "--show", "--noheadings"])
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0 and output == "", output


def _scope_from_cgroup(text: str) -> str | None:
    for line in text.splitlines():
        match = re.search(r"([^/]+\.scope)", line)
        if match:
            return match.group(1)
    return None


def _systemctl_show(scope: str) -> dict[str, str]:
    result = _run(["systemctl", "show", scope, "-p", "MemoryMax", "-p", "MemorySwapMax"])
    values: dict[str, str] = {}
    if result.returncode != 0:
        values["error"] = (result.stdout + result.stderr).strip()
        return values
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def _bytes_for_100g() -> int:
    return 100 * 1024 * 1024 * 1024


def _memory_max_is_100g(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().upper()
    if normalized == "100G":
        return True
    try:
        return int(normalized) == _bytes_for_100g()
    except ValueError:
        return False


def _memory_swap_is_zero(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().lower()
    if normalized in {"0", "0b", "0bytes"}:
        return True
    try:
        return int(normalized) == 0
    except ValueError:
        return False


def inspect_systemd_scope() -> dict[str, Any]:
    cgroup_text = Path("/proc/self/cgroup").read_text(encoding="utf-8")
    scope = _scope_from_cgroup(cgroup_text)
    hints = {
        "RUN_SAFE_MEMORY_MAX": os.environ.get("RUN_SAFE_MEMORY_MAX"),
        "MEMORY_MAX": os.environ.get("MEMORY_MAX"),
    }
    info: dict[str, Any] = {
        "scope": scope,
        "memory_max": None,
        "memory_swap_max": None,
        "inside_systemd_scope": bool(scope),
        "env_hints": {k: v for k, v in hints.items() if v},
        "systemctl_error": None,
    }
    if scope:
        values = _systemctl_show(scope)
        info["memory_max"] = values.get("MemoryMax")
        info["memory_swap_max"] = values.get("MemorySwapMax")
        info["systemctl_error"] = values.get("error")
    if not info["memory_max"] and hints["RUN_SAFE_MEMORY_MAX"]:
        info["memory_max"] = hints["RUN_SAFE_MEMORY_MAX"]
    if not info["memory_max"] and hints["MEMORY_MAX"]:
        info["memory_max"] = hints["MEMORY_MAX"]
    return info


def _write_payload(out_path: Path, payload: dict[str, Any]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out_path = Path(args.out)
    payload: dict[str, Any] = {
        "ok": False,
        "swap_disabled": False,
        "swapon_output": "",
        "scope": None,
        "memory_max": None,
        "memory_swap_max": None,
        "inside_systemd_scope": False,
        "error": None,
    }
    try:
        swap_disabled, swapon_output = check_swap_disabled()
        payload["swap_disabled"] = swap_disabled
        payload["swapon_output"] = swapon_output
        if not swap_disabled:
            raise RuntimeError(
                "swap is enabled; user approval is required before changing swap state "
                "(do not run sudo swapoff -a silently)"
            )

        scope_info = inspect_systemd_scope()
        payload["scope"] = scope_info["scope"]
        payload["memory_max"] = scope_info["memory_max"]
        payload["memory_swap_max"] = scope_info["memory_swap_max"]
        payload["inside_systemd_scope"] = scope_info["inside_systemd_scope"]

        if not payload["inside_systemd_scope"]:
            raise RuntimeError("not inside a systemd .scope; run through scripts/dgx_spark/run_safe.sh 100G --")
        if not _memory_max_is_100g(str(payload["memory_max"])):
            raise RuntimeError(f"MemoryMax is not 100G: {payload['memory_max']}")
        if not _memory_swap_is_zero(str(payload["memory_swap_max"])):
            raise RuntimeError(f"MemorySwapMax is not 0: {payload['memory_swap_max']}")

        payload["ok"] = True
        _write_payload(out_path, payload)
        return 0
    except Exception as exc:  # noqa: BLE001 - gate writes failure artifact before exiting.
        payload["error"] = f"{type(exc).__name__}: {exc}"
        _write_payload(out_path, payload)
        print(f"[RUN-SAFE-SCOPE-V3] FAIL: {payload['error']}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
