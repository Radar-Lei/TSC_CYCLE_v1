from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_CLASSIFICATIONS = {
    "v4 reproduction source",
    "v4 evidence",
    "archived legacy",
    "temporary",
    "removable",
}

CANONICAL_V4_ASSETS = {
    "runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf": "Phase 11 recommended q4_K_M deployment artifact and Phase 12 replay model.",
    "reality_test.log": "Final Phase 12 reality replay output with 426/426 parse, lint, and protocol gate successes.",
    "artifacts/v4/phase8/phase8_gate_report.json": "v4 Phase 8 dataset rebuild gate report named by state as key evidence.",
    "runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json": "v4 QLoRA SFT report and Phase 10 handoff evidence.",
    "runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json": "v4 GGUF export report containing fp16/q4 paths and q4 checksum.",
    "artifacts/v4/phase11/phase11_gate_report.json": "v4 eval matrix GO decision report.",
    "artifacts/v4/phase12/phase12_report.json": "Final replay report with model/output hashes and success counts.",
    "artifacts/v4/phase12/manifest.json": "Phase 12 replay manifest supporting final reality_test.log evidence.",
    "artifacts/v4/phase12/per_sample.jsonl": "Phase 12 per-sample replay evidence supporting final gate counts.",
}

CANONICAL_EVIDENCE_PATHS = [
    ".planning/STATE.md",
    ".planning/phases/13-inventory-cleanup-boundaries/13-CONTEXT.md",
    ".planning/phases/13-inventory-cleanup-boundaries/13-RESEARCH.md",
]

LOCAL_METADATA_PATHS = [
    ".env",
    ".venv",
    ".claude",
    ".pytest_cache",
    "tsc_cycle/__pycache__",
    ".claude/worktrees",
]

GROUP_ROOTS = {
    "data": "data",
    "artifacts": "artifacts",
    "runs": "runs",
    "planning": ".planning",
    "tests": "tests",
    "source": "tsc_cycle",
    "scripts": "scripts",
}

REQUIRED_ENTRY_FIELDS = {
    "path",
    "group",
    "classification",
    "recommended_action",
    "phase15_allowed",
    "rationale",
    "risk_if_deleted",
    "evidence_paths",
    "git_status",
    "size_bytes",
    "high_impact",
}


def resolve_repo_path(path: Path | str, repo_root: Path | str = Path.cwd()) -> Path:
    root = Path(repo_root).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes repository root: {path}") from exc
    return resolved


def _to_repo_relative(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _path_group(rel_path: str) -> str:
    if rel_path == ".":
        return "root"
    first = rel_path.split("/", 1)[0]
    if first == ".planning":
        return "planning"
    if first in {"data", "artifacts", "runs", "tests"}:
        return first
    if first == "tsc_cycle":
        return "source"
    if first == "scripts":
        return "scripts"
    if first in {".env", ".venv", ".claude", ".pytest_cache", "__pycache__"}:
        return "local"
    return "root"


def _git_status(repo_root: Path) -> dict[str, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain", "--untracked-files=normal"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return {}
    statuses: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line:
            continue
        status = line[:2].strip() or "clean"
        raw_path = line[3:] if len(line) > 3 else ""
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        if raw_path:
            statuses[raw_path] = status
    return statuses


def _status_for(path: str, statuses: dict[str, str]) -> str:
    if path in statuses:
        return statuses[path]
    prefix = path.rstrip("/") + "/"
    child_states = sorted({state for rel, state in statuses.items() if rel.startswith(prefix)})
    if child_states:
        return ",".join(child_states)
    return "clean"


def _safe_size(path: Path) -> int:
    try:
        if path.is_file():
            return path.stat().st_size
        if path.is_dir():
            total = 0
            for child in path.rglob("*"):
                try:
                    if child.is_file():
                        total += child.stat().st_size
                except OSError:
                    continue
            return total
        return 0
    except OSError:
        return 0


def _entry(
    *,
    rel_path: str,
    repo_root: Path,
    statuses: dict[str, str],
    group: str | None = None,
    classification: str,
    recommended_action: str,
    phase15_allowed: str,
    rationale: str,
    risk_if_deleted: str,
    evidence_paths: list[str] | None = None,
    high_impact: bool = False,
) -> dict[str, Any]:
    if classification not in ALLOWED_CLASSIFICATIONS:
        raise ValueError(f"unsupported classification: {classification}")
    full_path = repo_root if rel_path == "." else repo_root / rel_path
    return {
        "path": rel_path,
        "group": group or _path_group(rel_path),
        "classification": classification,
        "recommended_action": recommended_action,
        "phase15_allowed": phase15_allowed,
        "rationale": rationale,
        "risk_if_deleted": risk_if_deleted,
        "evidence_paths": evidence_paths or [],
        "git_status": _status_for(rel_path, statuses),
        "size_bytes": _safe_size(full_path),
        "high_impact": high_impact,
        "exists": full_path.exists(),
        "is_dir": full_path.is_dir(),
    }


def _canonical_entry(rel_path: str, repo_root: Path, statuses: dict[str, str]) -> dict[str, Any]:
    return _entry(
        rel_path=rel_path,
        repo_root=repo_root,
        statuses=statuses,
        classification="v4 evidence",
        recommended_action="keep",
        phase15_allowed="no_delete",
        rationale=CANONICAL_V4_ASSETS[rel_path],
        risk_if_deleted="Deleting this asset would break or weaken the shipped v4.0 Qwen3-4B reproduction and verification chain.",
        evidence_paths=CANONICAL_EVIDENCE_PATHS,
        high_impact=True,
    )


def _local_metadata_entry(rel_path: str, repo_root: Path, statuses: dict[str, str]) -> dict[str, Any]:
    return _entry(
        rel_path=rel_path,
        repo_root=repo_root,
        statuses=statuses,
        group="local",
        classification="temporary",
        recommended_action="manual_review_before_remove",
        phase15_allowed="manual_review_required",
        rationale="Local ignored, secret, cache, virtualenv, or agent/worktree state is inventoried as metadata only and must not serialize file payloads.",
        risk_if_deleted="May disrupt the local developer environment, credentials, caches, or active agent state if removed without maintainer confirmation.",
        evidence_paths=[".gitignore", ".planning/phases/13-inventory-cleanup-boundaries/13-RESEARCH.md"],
        high_impact=True,
    )


def _group_entry(group: str, rel_path: str, repo_root: Path, statuses: dict[str, str]) -> dict[str, Any]:
    if group == "data":
        return _entry(
            rel_path=rel_path,
            repo_root=repo_root,
            statuses=statuses,
            group=group,
            classification="v4 reproduction source",
            recommended_action="keep_or_archive",
            phase15_allowed="manual_review_required",
            rationale="Data contains v4 Phase 8 labeled, split, and tokenized assets plus legacy lineage that Phase 14 must separate before cleanup.",
            risk_if_deleted="Deleting data before package definition could break v4 dataset reproduction or erase lineage from the v3 expanded source.",
            evidence_paths=[".planning/PROJECT.md", ".planning/phases/13-inventory-cleanup-boundaries/13-RESEARCH.md"],
            high_impact=True,
        )
    if group == "artifacts":
        return _entry(
            rel_path=rel_path,
            repo_root=repo_root,
            statuses=statuses,
            group=group,
            classification="v4 evidence",
            recommended_action="keep_or_archive",
            phase15_allowed="manual_review_required",
            rationale="Artifacts include canonical v4 Phase 8/11/12 reports and legacy audit evidence; canonical children are separately marked no_delete.",
            risk_if_deleted="Deleting artifacts can remove gate reports needed to audit shipped v4.0 decisions.",
            evidence_paths=[".planning/STATE.md", ".planning/phases/13-inventory-cleanup-boundaries/13-RESEARCH.md"],
            high_impact=True,
        )
    if group == "runs":
        return _entry(
            rel_path=rel_path,
            repo_root=repo_root,
            statuses=statuses,
            group=group,
            classification="v4 evidence",
            recommended_action="keep_or_archive",
            phase15_allowed="manual_review_required",
            rationale="Runs contains the canonical v4 q4_K_M artifact, v4 training/export reports, v1 baseline, and bulky legacy outputs requiring per-path review.",
            risk_if_deleted="Deleting runs wholesale would destroy the shipped v4 deployment artifact and historical baselines.",
            evidence_paths=[".planning/STATE.md", ".planning/phases/13-inventory-cleanup-boundaries/13-RESEARCH.md"],
            high_impact=True,
        )
    if group == "planning":
        return _entry(
            rel_path=rel_path,
            repo_root=repo_root,
            statuses=statuses,
            group=group,
            classification="v4 reproduction source",
            recommended_action="keep_or_archive",
            phase15_allowed="manual_review_required",
            rationale="Planning state records v4.1 cleanup boundaries and v4.0 preservation context; old phases should be inventoried before archive decisions.",
            risk_if_deleted="Deleting planning history or state could remove decisions needed to justify cleanup boundaries.",
            evidence_paths=[".planning/STATE.md", ".planning/ROADMAP.md"],
            high_impact=True,
        )
    if group == "tests":
        return _entry(
            rel_path=rel_path,
            repo_root=repo_root,
            statuses=statuses,
            group=group,
            classification="v4 reproduction source",
            recommended_action="keep",
            phase15_allowed="no_delete",
            rationale="Tests protect source behavior and v4 gate contracts, including the Phase 13 inventory contract.",
            risk_if_deleted="Deleting tests would remove the safety net proving cleanup did not break reproduction or gate behavior.",
            evidence_paths=["pyproject.toml", ".planning/phases/13-inventory-cleanup-boundaries/13-VALIDATION.md"],
            high_impact=True,
        )
    raise ValueError(f"unsupported group: {group}")


def _source_or_script_entry(group: str, rel_path: str, repo_root: Path, statuses: dict[str, str]) -> dict[str, Any]:
    return _entry(
        rel_path=rel_path,
        repo_root=repo_root,
        statuses=statuses,
        group=group,
        classification="v4 reproduction source",
        recommended_action="keep",
        phase15_allowed="no_delete",
        rationale="Source and script entry points are needed for tests, reports, and v4 reproduction gates; cleanup must preserve imports unless later review proves otherwise.",
        risk_if_deleted="Deleting source or scripts can break validation commands and reproduction entry points.",
        evidence_paths=[".planning/PROJECT.md", ".planning/phases/13-inventory-cleanup-boundaries/13-RESEARCH.md"],
        high_impact=True,
    )


def _root_entry(rel_path: str, repo_root: Path, statuses: dict[str, str]) -> dict[str, Any]:
    if rel_path in {"CLAUDE.md", "pyproject.toml", "uv.lock"}:
        classification = "v4 reproduction source"
        action = "keep"
        allowed = "no_delete"
        rationale = "Root project configuration or instructions are required for safe validation and reproduction."
        risk = "Deleting root configuration can break test discovery, build metadata, or required project constraints."
        evidence = [".planning/PROJECT.md"]
        high_impact = True
    else:
        classification = "archived legacy"
        action = "keep_or_archive"
        allowed = "manual_review_required"
        rationale = "Root-level file requires role-based review before cleanup; untracked or modified status alone is not a deletion signal."
        risk = "Deleting root files before review may remove documentation, logs, or user-facing evidence."
        evidence = [".planning/phases/13-inventory-cleanup-boundaries/13-RESEARCH.md"]
        high_impact = rel_path.endswith(".log") or rel_path == "reality.log"
    return _entry(
        rel_path=rel_path,
        repo_root=repo_root,
        statuses=statuses,
        classification=classification,
        recommended_action=action,
        phase15_allowed=allowed,
        rationale=rationale,
        risk_if_deleted=risk,
        evidence_paths=evidence,
        high_impact=high_impact,
    )


def _discover_top_level_entries(repo_root: Path, statuses: dict[str, str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for group, rel_path in GROUP_ROOTS.items():
        path = repo_root / rel_path
        if path.exists():
            if group in {"source", "scripts"}:
                entries.append(_source_or_script_entry(group, rel_path, repo_root, statuses))
            else:
                entries.append(_group_entry(group, rel_path, repo_root, statuses))
    for child in sorted(repo_root.iterdir(), key=lambda p: p.name):
        rel_path = _to_repo_relative(child, repo_root)
        if rel_path in GROUP_ROOTS.values() or rel_path in {".git"}:
            continue
        if rel_path in LOCAL_METADATA_PATHS or rel_path.startswith(".") and rel_path in {".env", ".venv", ".claude", ".pytest_cache"}:
            continue
        if child.is_file():
            entries.append(_root_entry(rel_path, repo_root, statuses))
    return entries


def _extra_version_entries(repo_root: Path, statuses: dict[str, str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    version_paths = {
        "data/v4/phase8": ("data", "v4 reproduction source", "keep_or_archive", "manual_review_required", "v4 Phase 8 dataset rebuild outputs are reproduction candidates pending Phase 14 package selection."),
        "data/v3": ("data", "archived legacy", "archive_candidate", "archive_only", "v3 expanded data is lineage for v4 but not the final v4.1 reproduction target."),
        "artifacts/v3": ("artifacts", "archived legacy", "archive_candidate", "archive_only", "v3 reports are historical audit evidence and should be archived rather than deleted blindly."),
        "runs/v3.0-gates": ("runs", "archived legacy", "archive_candidate", "archive_only", "v3 gate outputs are bulky legacy artifacts outside the v4.0 Qwen3-4B reproduction target."),
        "runs/20260507T032419Z": ("runs", "archived legacy", "keep_or_archive", "manual_review_required", "v1 q4_K_M baseline is a read-only historical reference, not the v4.1 target."),
        "runs/v4.0-4B-20260509T184844Z": ("runs", "v4 evidence", "keep", "no_delete", "v4.0 training/export/eval run root contains canonical q4 model and required reports."),
    }
    for rel_path, (group, classification, action, allowed, rationale) in version_paths.items():
        if (repo_root / rel_path).exists():
            entries.append(
                _entry(
                    rel_path=rel_path,
                    repo_root=repo_root,
                    statuses=statuses,
                    group=group,
                    classification=classification,
                    recommended_action=action,
                    phase15_allowed=allowed,
                    rationale=rationale,
                    risk_if_deleted="Loss of this path could remove reproduction lineage, baseline comparison, or canonical v4 evidence before Phase 14/15 decisions.",
                    evidence_paths=[".planning/PROJECT.md", ".planning/STATE.md"],
                    high_impact=True,
                )
            )
    return entries


def _ensure_local_entries(repo_root: Path, statuses: dict[str, str]) -> list[dict[str, Any]]:
    return [_local_metadata_entry(rel_path, repo_root, statuses) for rel_path in LOCAL_METADATA_PATHS]


def _groups_summary(entries: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for entry in entries:
        group = entry["group"]
        group_summary = summary.setdefault(group, {"entries": 0, "high_impact": 0, "size_bytes": 0})
        group_summary["entries"] += 1
        group_summary["size_bytes"] += int(entry.get("size_bytes", 0))
        if entry.get("high_impact"):
            group_summary["high_impact"] += 1
    return summary


def build_inventory(repo_root: Path | str = Path.cwd()) -> dict[str, Any]:
    root = resolve_repo_path(Path(repo_root), repo_root).resolve()
    statuses = _git_status(root)
    entries: list[dict[str, Any]] = []
    entries.extend(_discover_top_level_entries(root, statuses))
    entries.extend(_extra_version_entries(root, statuses))
    entries.extend(_canonical_entry(rel_path, root, statuses) for rel_path in sorted(CANONICAL_V4_ASSETS))
    entries.extend(_ensure_local_entries(root, statuses))

    deduped = {entry["path"]: entry for entry in entries}
    ordered_entries = [deduped[path] for path in sorted(deduped)]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo_root": str(root),
        "groups": _groups_summary(ordered_entries),
        "entries": ordered_entries,
    }


def write_inventory_json(inventory: dict[str, Any], output_path: Path | str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a read-only TSC-CYCLE cleanup inventory JSON.")
    parser.add_argument("--repo-root", default=str(Path.cwd()), help="Repository root to inventory")
    parser.add_argument("--output-json", required=True, help="Phase 13 inventory JSON output path")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    output_path = resolve_repo_path(args.output_json, repo_root)
    inventory = build_inventory(repo_root)
    write_inventory_json(inventory, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
