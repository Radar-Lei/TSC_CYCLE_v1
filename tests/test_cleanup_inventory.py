from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest


REPO_ROOT = Path("/home/samuel/TSC_CYCLE")

ALLOWED_CLASSIFICATIONS = {
    "v4 reproduction source",
    "v4 evidence",
    "archived legacy",
    "temporary",
    "removable",
}

REQUIRED_GROUPS = {"root", "data", "artifacts", "runs", "planning", "tests"}

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

CANONICAL_V4_ASSETS = {
    "runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf",
    "reality_test.log",
    "artifacts/v4/phase8/phase8_gate_report.json",
    "runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json",
    "runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json",
    "artifacts/v4/phase11/phase11_gate_report.json",
    "artifacts/v4/phase12/phase12_report.json",
    "artifacts/v4/phase12/manifest.json",
    "artifacts/v4/phase12/per_sample.jsonl",
}

LOCAL_METADATA_PATHS = {
    ".env",
    ".venv",
    ".claude",
    ".pytest_cache",
    "tsc_cycle/__pycache__",
    ".claude/worktrees",
}


def _build_inventory(repo_root: Path = REPO_ROOT) -> dict:
    from tsc_cycle.cleanup_inventory import build_inventory

    return build_inventory(repo_root)


def _entries_by_path(inventory: dict) -> dict[str, dict]:
    return {entry["path"]: entry for entry in inventory["entries"]}


def test_inventory_covers_required_groups():
    inventory = _build_inventory()

    assert set(inventory) >= {"schema_version", "generated_at", "repo_root", "groups", "entries"}
    assert isinstance(inventory["entries"], list)
    assert inventory["entries"], "inventory must include repository entries"

    groups = {entry["group"] for entry in inventory["entries"]}
    assert REQUIRED_GROUPS <= groups

    for entry in inventory["entries"]:
        assert REQUIRED_ENTRY_FIELDS <= set(entry), entry
        assert entry["classification"] in ALLOWED_CLASSIFICATIONS


def test_high_impact_groups_have_rationale():
    inventory = _build_inventory()
    high_impact_entries = [entry for entry in inventory["entries"] if entry["high_impact"]]

    assert high_impact_entries, "expected high-impact cleanup-sensitive entries"
    for entry in high_impact_entries:
        assert entry["recommended_action"], entry
        assert entry["phase15_allowed"], entry
        assert entry["rationale"], entry
        assert entry["risk_if_deleted"], entry
        assert entry["evidence_paths"], entry


def test_canonical_v4_assets_are_no_delete():
    inventory = _build_inventory()
    by_path = _entries_by_path(inventory)

    missing = CANONICAL_V4_ASSETS - set(by_path)
    assert not missing

    for path in CANONICAL_V4_ASSETS:
        entry = by_path[path]
        assert entry["classification"] == "v4 evidence"
        assert entry["recommended_action"] == "keep"
        assert entry["phase15_allowed"] == "no_delete"
        assert entry["evidence_paths"], entry
        assert entry["risk_if_deleted"], entry


def test_inventory_generator_is_read_only_and_secret_metadata_only():
    import tsc_cycle.cleanup_inventory as cleanup_inventory

    source = inspect.getsource(cleanup_inventory)
    destructive_tokens = ["unlink(", "rmtree(", "remove(", "rename(", "replace("]
    for token in destructive_tokens:
        assert token not in source, f"destructive call is forbidden: {token}"

    inventory = _build_inventory()
    by_path = _entries_by_path(inventory)
    serialized = json.dumps(inventory, ensure_ascii=False)

    assert "OPENAI_API_KEY=" not in serialized
    assert "sk-" not in serialized
    assert "file_contents" not in serialized
    assert "content" not in serialized

    for path in LOCAL_METADATA_PATHS:
        assert path in by_path, f"missing metadata-only local entry: {path}"
        entry = by_path[path]
        assert entry["classification"] in {"temporary", "removable"}
        assert entry["recommended_action"] in {"manual_review_before_remove", "remove_candidate"}
        assert entry["phase15_allowed"] in {"manual_review_required", "remove_candidate"}
        assert REQUIRED_ENTRY_FIELDS <= set(entry)
        assert set(entry) <= REQUIRED_ENTRY_FIELDS | {"exists", "is_dir"}


def test_repo_relative_path_guard_rejects_outside_root():
    from tsc_cycle.cleanup_inventory import resolve_repo_path

    assert resolve_repo_path("data", REPO_ROOT) == REPO_ROOT / "data"

    with pytest.raises(ValueError):
        resolve_repo_path("../outside", REPO_ROOT)

    with pytest.raises(ValueError):
        resolve_repo_path("/tmp/outside-tsc-cycle", REPO_ROOT)
