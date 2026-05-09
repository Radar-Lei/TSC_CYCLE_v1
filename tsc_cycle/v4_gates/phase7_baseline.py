from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

EXPECTED_MODEL_ID = "Qwen/Qwen3-4B-Thinking-2507"
FORBIDDEN_MODEL_SUBSTRINGS = ("Qwen3.5", "Qwen3.5-9B", "qwen3.5")
FROZEN_BASELINE_ROOT = Path("/home/samuel/TSC_CYCLE/runs/20260507T032419Z")
PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
PROJECT_VENV = PROJECT_ROOT / ".venv/bin/python"
DGX_SETUP_VENV = Path("/home/samuel/dgx-spark-setup/.venv/bin/python")
RUN_SAFE = PROJECT_ROOT / "scripts/dgx_spark/run_safe.sh"
DEFAULT_ENV_OUT = PROJECT_ROOT / "artifacts/v4/phase7/environment.json"
DEFAULT_BASELINE_OUT = PROJECT_ROOT / "artifacts/v4/phase7/baseline_readonly.json"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def assert_output_not_in_frozen_root(path: Path) -> None:
    if _is_relative_to(path, FROZEN_BASELINE_ROOT):
        raise ValueError(f"refusing to write under frozen v1 baseline root: {path}")


def assert_model_id(model_id: str) -> str:
    if any(forbidden in model_id for forbidden in FORBIDDEN_MODEL_SUBSTRINGS):
        raise ValueError(f"forbidden Qwen3.5 model selected: {model_id}")
    if model_id != EXPECTED_MODEL_ID:
        raise ValueError(f"expected {EXPECTED_MODEL_ID}, got {model_id}")
    return model_id


def _probe_python(python: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {"path": str(python), "exists": python.exists(), "packages": {}}
    if not python.exists():
        return payload

    code = """
import importlib.metadata as md
import json
import sys
packages = {}
for name in ['torch', 'transformers', 'bitsandbytes', 'trl', 'pytest']:
    try:
        packages[name] = md.version(name)
    except md.PackageNotFoundError:
        packages[name] = None
print(json.dumps({'executable': sys.executable, 'version': sys.version.split()[0], 'packages': packages}, sort_keys=True))
"""
    result = subprocess.run([str(python), "-c", code], check=False, text=True, capture_output=True, timeout=30)
    payload["returncode"] = result.returncode
    if result.returncode == 0:
        payload.update(json.loads(result.stdout))
    else:
        payload["stderr"] = result.stderr.strip()
    return payload


def _sha256_prefix(path: Path, size: int = 16) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:size]


def snapshot_baseline_root(root: Path = FROZEN_BASELINE_ROOT) -> dict[str, Any]:
    root = root.resolve()
    files = [p for p in root.rglob("*") if p.is_file()] if root.exists() else []
    latest_mtime_ns = max((p.stat().st_mtime_ns for p in files), default=None)
    q4_artifact = root / "gguf/model.q4_K_M.gguf"
    documented_cache = root / "eval/gen_cache/gguf_q4km"
    discovered_q4_caches = sorted(
        str(p.relative_to(root)) for p in (root / "eval/gen_cache").glob("*q4*") if p.exists()
    ) if (root / "eval/gen_cache").exists() else []

    stat = root.stat() if root.exists() else None
    return {
        "root": str(root),
        "exists": root.exists(),
        "mode": oct(stat.st_mode & 0o777) if stat else None,
        "write_bits": stat.st_mode & 0o222 if stat else None,
        "file_count": len(files),
        "latest_mtime_ns": latest_mtime_ns,
        "q4_artifact": {
            "path": str(q4_artifact),
            "exists": q4_artifact.is_file(),
            "size": q4_artifact.stat().st_size if q4_artifact.is_file() else None,
            "sha256_prefix": _sha256_prefix(q4_artifact),
        },
        "documented_cache": {
            "path": str(documented_cache),
            "exists": documented_cache.exists(),
        },
        "discovered_q4_caches": discovered_q4_caches,
    }


def _environment_payload(model_id: str) -> dict[str, Any]:
    fatal_failures: list[dict[str, str]] = []
    warnings: list[str] = []
    try:
        selected = assert_model_id(model_id)
        model_ok = True
    except ValueError as exc:
        selected = model_id
        model_ok = False
        fatal_failures.append({"gate": "model", "reason": str(exc)})

    project_probe = _probe_python(PROJECT_VENV)
    dgx_probe = _probe_python(DGX_SETUP_VENV)
    if not project_probe["exists"]:
        fatal_failures.append({"gate": "project_venv", "reason": f"missing {PROJECT_VENV}"})
    if not dgx_probe["exists"]:
        fatal_failures.append({"gate": "dgx_setup_venv", "reason": f"missing {DGX_SETUP_VENV}"})

    dgx_packages = dgx_probe.get("packages", {}) or {}
    for package in ("bitsandbytes", "trl"):
        if dgx_packages.get(package) is None:
            warnings.append(f"{package} missing in {DGX_SETUP_VENV}; Phase 7 reports only and does not install")

    return {
        "ok": not fatal_failures,
        "fatal_failures": fatal_failures,
        "warnings": warnings,
        "requirements_covered": ["BASE-01", "BASE-02"],
        "model": {"expected": EXPECTED_MODEL_ID, "selected": selected, "ok": model_ok},
        "sys_executable": sys.executable,
        "project_venv": project_probe,
        "dgx_setup_venv": dgx_probe,
        "run_safe": {"path": str(RUN_SAFE), "exists": RUN_SAFE.exists(), "executable": os.access(RUN_SAFE, os.X_OK)},
        "packages": {"project_venv": project_probe.get("packages", {}), "dgx_setup_venv": dgx_packages},
        "mutation_actions": [],
    }


def _baseline_payload() -> dict[str, Any]:
    before = snapshot_baseline_root(FROZEN_BASELINE_ROOT)
    after = snapshot_baseline_root(FROZEN_BASELINE_ROOT)
    compared_fields = ["file_count", "latest_mtime_ns", "q4_artifact"]
    unchanged = all(before[field] == after[field] for field in compared_fields)
    fatal_failures: list[dict[str, str]] = []
    if not before["exists"]:
        fatal_failures.append({"gate": "baseline_root", "reason": f"missing {FROZEN_BASELINE_ROOT}"})
    if not before["q4_artifact"]["exists"]:
        fatal_failures.append({"gate": "q4_artifact", "reason": "missing gguf/model.q4_K_M.gguf"})
    if not unchanged:
        fatal_failures.append({"gate": "baseline_unchanged", "reason": "before/after snapshot changed"})

    warnings: list[str] = []
    if not before["documented_cache"]["exists"]:
        warnings.append("documented cache path gguf_q4km is missing; use discovered q4 cache paths")

    return {
        "ok": not fatal_failures,
        "fatal_failures": fatal_failures,
        "warnings": warnings,
        "requirements_covered": ["BASE-03"],
        "unchanged": unchanged,
        "before": before,
        "after": after,
    }


def evaluate_baseline_gate(
    environment_out: Path = DEFAULT_ENV_OUT,
    baseline_out: Path = DEFAULT_BASELINE_OUT,
    model_id: str = EXPECTED_MODEL_ID,
) -> dict[str, Any]:
    assert_output_not_in_frozen_root(environment_out)
    assert_output_not_in_frozen_root(baseline_out)
    environment = _environment_payload(model_id)
    baseline = _baseline_payload()

    environment_out.parent.mkdir(parents=True, exist_ok=True)
    baseline_out.parent.mkdir(parents=True, exist_ok=True)
    environment_out.write_text(json.dumps(environment, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    baseline_out.write_text(json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "ok": environment["ok"] and baseline["ok"],
        "environment": environment,
        "baseline_readonly": baseline,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run v4 Phase 7 baseline/environment gate")
    parser.add_argument("--model-id", default=EXPECTED_MODEL_ID)
    parser.add_argument("--environment-out", default=str(DEFAULT_ENV_OUT))
    parser.add_argument("--baseline-out", default=str(DEFAULT_BASELINE_OUT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = evaluate_baseline_gate(
        environment_out=Path(args.environment_out),
        baseline_out=Path(args.baseline_out),
        model_id=args.model_id,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
