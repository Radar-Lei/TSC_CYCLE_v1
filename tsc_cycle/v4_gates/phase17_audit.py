"""Phase 17 offline saturation audit, policy gate, and prompt protocol guard."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from tsc_cycle.v4_gates.saturation_policy import (
    PHASE12_MANIFEST_PATH,
    PHASE12_PER_SAMPLE_PATH,
    DATASET_PATH,
    SPLIT_DIR,
    compute_saturation_audit,
    project_dataset_phase_decisions,
    project_replay_phase_decisions,
)

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4" / "phase17"
AUDIT_REPORT_PATH = ARTIFACT_ROOT / "saturation_audit_report.json"
POLICY_GATE_PATH = ARTIFACT_ROOT / "saturation_policy_gate.json"
PROMPT_PROTOCOL_REPORT_PATH = ARTIFACT_ROOT / "prompt_protocol_report.json"
FROZEN_V1_ROOT = PROJECT_ROOT / "runs" / "20260507T032419Z"
REQUIREMENTS_COVERED = ["AUDIT-01", "AUDIT-02", "POLICY-01", "POLICY-02", "POLICY-03"]


def _is_under(path: Path, root: Path) -> bool:
    candidate = path.expanduser().resolve(strict=False)
    root = root.expanduser().resolve(strict=False)
    return candidate == root or root in candidate.parents


def reject_unsafe_phase17_output_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    artifact_root = ARTIFACT_ROOT.resolve(strict=False)
    if _is_under(candidate, FROZEN_V1_ROOT):
        raise ValueError(f"Phase 17 report output path is not allowed: {candidate}")
    if _is_under(candidate, artifact_root):
        return candidate
    raise ValueError(f"Phase 17 report output path is not allowed: {candidate}")


def _write_json(path: str | Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    safe_path = reject_unsafe_phase17_output_path(path)
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    safe_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: str | Path) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def evaluate_phase17_audit(
    *,
    dataset_path: str | Path = DATASET_PATH,
    split_dir: str | Path = SPLIT_DIR,
    phase12_manifest_path: str | Path = PHASE12_MANIFEST_PATH,
    phase12_per_sample_path: str | Path = PHASE12_PER_SAMPLE_PATH,
    phase_decisions_jsonl: str | Path | None = None,
    out_path: str | Path | None = POLICY_GATE_PATH,
    audit_out_path: str | Path | None = AUDIT_REPORT_PATH,
    prompt_protocol_out_path: str | Path | None = PROMPT_PROTOCOL_REPORT_PATH,
    example_limit: int = 10,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Evaluate Phase 17 evidence and write safe JSON reports.

    This task-1 shell intentionally delegates detailed threshold and prompt checks
    to later Phase 17 tasks while preserving the final fail-closed payload shape.
    """
    fatal_failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    input_hashes: dict[str, str] = {}
    projections: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    excluded_counts: dict[str, int] = {}

    try:
        dataset_projection = project_dataset_phase_decisions(dataset_path, split_dir=split_dir)
        projections["dataset"] = dataset_projection
        rows.extend(dataset_projection.get("rows") or [])
        for key, value in (dataset_projection.get("excluded_counts") or {}).items():
            excluded_counts[key] = excluded_counts.get(key, 0) + int(value)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        fatal_failures.append({"gate": "dataset_audit", "reason": str(exc)})

    try:
        replay_projection = project_replay_phase_decisions(phase12_manifest_path, phase12_per_sample_path)
        projections["replay"] = replay_projection
        rows.extend(replay_projection.get("rows") or [])
        for key, value in (replay_projection.get("excluded_counts") or {}).items():
            excluded_counts[key] = excluded_counts.get(key, 0) + int(value)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        fatal_failures.append({"gate": "replay_audit", "reason": str(exc)})

    audit = {
        "ok": False,
        "requirements_covered": ["AUDIT-01", "AUDIT-02", "POLICY-01"],
        "total_rows": 0,
        "included_rows": 0,
        "trivial_rows": 0,
        "excluded_counts": excluded_counts,
        "bands": {},
        "representative_examples": [],
    }
    if rows:
        try:
            audit = compute_saturation_audit(rows, example_limit=example_limit, excluded_counts=excluded_counts)
        except (ValueError, TypeError) as exc:
            fatal_failures.append({"gate": "audit_compute", "reason": str(exc)})

    for label, path in {
        "dataset": dataset_path,
        "phase12_manifest": phase12_manifest_path,
        "phase12_per_sample": phase12_per_sample_path,
    }.items():
        path_obj = Path(path)
        if path_obj.exists():
            input_hashes[label] = sha256_file(path_obj)

    ok = not fatal_failures and bool(audit.get("ok", True))
    policy_gate = {
        "ok": ok,
        "next_phase_allowed": ok,
        "requirements_covered": list(REQUIREMENTS_COVERED),
        "thresholds": thresholds or {},
        "gates": {
            "dataset_audit": {"ok": "dataset" in projections},
            "replay_audit": {"ok": "replay" in projections},
            "audit_compute": {"ok": bool(audit.get("ok", False))},
        },
        "fatal_failures": fatal_failures,
        "warnings": warnings,
        "reports": {
            "audit": str(audit_out_path) if audit_out_path is not None else str(AUDIT_REPORT_PATH),
            "policy_gate": str(out_path) if out_path is not None else str(POLICY_GATE_PATH),
            "prompt_protocol": str(prompt_protocol_out_path) if prompt_protocol_out_path is not None else str(PROMPT_PROTOCOL_REPORT_PATH),
        },
        "counts": {
            "total_rows": audit.get("total_rows", 0),
            "included_rows": audit.get("included_rows", 0),
            "trivial_rows": audit.get("trivial_rows", 0),
            "excluded_counts": audit.get("excluded_counts", {}),
        },
        "audit": audit,
        "input_hashes": input_hashes,
    }

    _write_json(audit_out_path, audit)
    _write_json(out_path, policy_gate)
    return policy_gate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Phase 17 saturation audit and policy gate evidence")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--split-dir", type=Path, default=SPLIT_DIR)
    parser.add_argument("--phase12-manifest", type=Path, default=PHASE12_MANIFEST_PATH)
    parser.add_argument("--phase12-per-sample", type=Path, default=PHASE12_PER_SAMPLE_PATH)
    parser.add_argument("--phase-decisions-jsonl", "--eval-outputs", dest="phase_decisions_jsonl", type=Path, default=None)
    parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    parser.add_argument("--out", type=Path, default=POLICY_GATE_PATH)
    parser.add_argument("--audit-out", type=Path, default=AUDIT_REPORT_PATH)
    parser.add_argument("--prompt-protocol-out", type=Path, default=PROMPT_PROTOCOL_REPORT_PATH)
    parser.add_argument("--example-limit", type=int, default=10)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    global ARTIFACT_ROOT
    ARTIFACT_ROOT = Path(args.artifact_root)
    report = evaluate_phase17_audit(
        dataset_path=args.dataset,
        split_dir=args.split_dir,
        phase12_manifest_path=args.phase12_manifest,
        phase12_per_sample_path=args.phase12_per_sample,
        phase_decisions_jsonl=args.phase_decisions_jsonl,
        out_path=args.out,
        audit_out_path=args.audit_out,
        prompt_protocol_out_path=args.prompt_protocol_out,
        example_limit=args.example_limit,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    sys.exit(main())
