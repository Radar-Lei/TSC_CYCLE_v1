"""Phase 4 SFT manifest evaluator.

This lightweight gate keeps artifact checks fail-closed while later Phase 4 plans
add the full aggregate report workflow.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIREMENTS_COVERED = [
    "SFT-01",
    "SFT-02",
    "SFT-03",
    "SFT-04",
    "SFT-05",
    "SFT-06",
    "SFT-07",
    "SFT-08",
]
WANDB_PROJECT = "tsc-cycle-v3-9b"


def _failure(gate: str, reason: str) -> dict[str, str]:
    return {"gate": gate, "reason": reason}


def _load_json(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if not path.exists():
        return {}, [_failure("manifest", f"missing manifest: {path}")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [_failure("manifest", f"malformed JSON: {exc}")]
    if not isinstance(payload, dict):
        return {}, [_failure("manifest", "manifest must be a JSON object")]
    return payload, []


def _require_path(payload: dict[str, Any], key: str, failures: list[dict[str, str]]) -> str:
    value = payload.get(key)
    if not value:
        failures.append(_failure(key, f"missing {key}"))
        return ""
    path = Path(str(value))
    if not path.exists():
        failures.append(_failure(key, f"path does not exist: {path}"))
    return str(path)


def evaluate_sft_manifest(manifest_path: str | Path) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    payload, failures = _load_json(manifest_path)

    requirements = payload.get("requirements_covered", [])
    if requirements != REQUIREMENTS_COVERED:
        failures.append(_failure("requirements_covered", "manifest must cover SFT-01 through SFT-08 exactly"))

    run_root = str(payload.get("run_root", manifest_path.parent))
    if not Path(run_root).name.startswith("v3.0-9B-"):
        failures.append(_failure("run_root", "run_root must be isolated under v3.0-9B-*"))

    wandb_project = payload.get("wandb_project")
    if wandb_project != WANDB_PROJECT:
        failures.append(_failure("wandb_project", f"wandb_project must be {WANDB_PROJECT}"))

    paths = {
        "adapter_path": _require_path(payload, "adapter_path", failures),
        "dry_run_report": _require_path(payload, "dry_run_report", failures),
        "full_run_report": _require_path(payload, "full_run_report", failures),
    }

    dry_report = payload.get("dry_run_report")
    if dry_report and Path(str(dry_report)).exists():
        dry_payload, dry_failures = _load_json(Path(str(dry_report)))
        failures.extend(_failure("dry_run_report", item["reason"]) for item in dry_failures)
        if dry_payload and dry_payload.get("ok") is not True:
            failures.append(_failure("dry_run_report", "dry-run report is not ok"))
    else:
        failures.append(_failure("dry_run_report", "missing dry-run gate evidence"))

    full_report = payload.get("full_run_report")
    if full_report and Path(str(full_report)).exists():
        full_payload, full_failures = _load_json(Path(str(full_report)))
        failures.extend(_failure("full_run_report", item["reason"]) for item in full_failures)
        if full_payload and full_payload.get("ok") is not True:
            failures.append(_failure("full_run_report", "full-run report is not ok"))
    else:
        failures.append(_failure("full_run_report", "missing full-run evidence"))

    frozen_evidence = payload.get("frozen_evidence")
    if not isinstance(frozen_evidence, dict) or frozen_evidence.get("write_bits_removed") is not True:
        failures.append(_failure("frozen_evidence", "missing read-only v1.0 FROZEN evidence"))

    lora_coverage_path = str(payload.get("lora_coverage_path", ""))
    if not lora_coverage_path or not Path(lora_coverage_path).exists():
        failures.append(_failure("lora_coverage_path", "missing lora_coverage.json evidence"))

    arrow_hashes = payload.get("arrow_hashes", {})
    if not isinstance(arrow_hashes, dict) or not all(isinstance(arrow_hashes.get(key), str) and len(arrow_hashes[key]) == 64 for key in ("train_arrow", "val_arrow", "ood_val_arrow")):
        failures.append(_failure("arrow_hashes", "missing train/val/ood_val Arrow SHA-256 hashes"))

    gates = payload.get("gates", {}) if isinstance(payload.get("gates"), dict) else {}
    manifest_failures = payload.get("fatal_failures", []) if isinstance(payload.get("fatal_failures"), list) else []
    failures.extend(item for item in manifest_failures if isinstance(item, dict) and "gate" in item)

    ok = not failures and payload.get("ok") is True
    return {
        "ok": ok,
        "run_root": run_root,
        "wandb_project": wandb_project,
        "paths": paths,
        "requirements_covered": requirements,
        "arrow_hashes": arrow_hashes if isinstance(arrow_hashes, dict) else {},
        "lora_coverage_path": lora_coverage_path,
        "frozen_evidence": frozen_evidence if isinstance(frozen_evidence, dict) else {},
        "gates": gates,
        "fatal_failures": failures,
    }
