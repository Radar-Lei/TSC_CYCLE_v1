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


REQUIRED_MARKDOWN_HEADINGS = [
    "# Phase 13 Inventory & Cleanup Boundaries",
    "## Scope and Non-Destructive Guarantee",
    "## Required Group Summary",
    "## Canonical v4.0 No-Delete Assets",
    "## High-Impact Cleanup Boundaries",
    "## Legacy / Temporary / Removable Candidates",
    "## Phase 15 Preconditions",
]

HIGH_IMPACT_MARKDOWN_FIELDS = {
    "classification",
    "recommended_action",
    "phase15_allowed",
    "rationale",
    "risk_if_deleted",
    "evidence_paths",
}


def test_write_inventory_markdown_covers_required_sections_and_groups(tmp_path):
    from tsc_cycle.cleanup_inventory import build_inventory, write_inventory_markdown

    inventory = build_inventory(REPO_ROOT)
    output_path = tmp_path / "inventory.md"

    write_inventory_markdown(inventory, output_path)
    report = output_path.read_text(encoding="utf-8")

    for heading in REQUIRED_MARKDOWN_HEADINGS:
        assert heading in report

    for group in REQUIRED_GROUPS:
        assert f"| {group} |" in report or f"### {group}" in report

    assert "Phase 13 is non-destructive" in report
    assert "Phase 15" in report


def test_markdown_lists_canonical_v4_assets_as_keep_no_delete(tmp_path):
    from tsc_cycle.cleanup_inventory import build_inventory, write_inventory_markdown

    output_path = tmp_path / "inventory.md"
    write_inventory_markdown(build_inventory(REPO_ROOT), output_path)
    report = output_path.read_text(encoding="utf-8")

    canonical_section = report.split("## Canonical v4.0 No-Delete Assets", 1)[1].split(
        "## High-Impact Cleanup Boundaries", 1
    )[0]
    for asset in CANONICAL_V4_ASSETS:
        assert asset in canonical_section
    assert "keep" in canonical_section
    assert "no_delete" in canonical_section


def test_markdown_exposes_high_impact_rationale_fields(tmp_path):
    from tsc_cycle.cleanup_inventory import build_inventory, write_inventory_markdown

    output_path = tmp_path / "inventory.md"
    write_inventory_markdown(build_inventory(REPO_ROOT), output_path)
    report = output_path.read_text(encoding="utf-8")

    high_impact_section = report.split("## High-Impact Cleanup Boundaries", 1)[1].split(
        "## Legacy / Temporary / Removable Candidates", 1
    )[0]
    for field in HIGH_IMPACT_MARKDOWN_FIELDS:
        assert field in high_impact_section
    assert "remove now" not in report.lower()
    assert "delete now" not in report.lower()


def test_markdown_excludes_secret_values(tmp_path):
    from tsc_cycle.cleanup_inventory import build_inventory, write_inventory_markdown

    output_path = tmp_path / "inventory.md"
    write_inventory_markdown(build_inventory(REPO_ROOT), output_path)
    report = output_path.read_text(encoding="utf-8")

    assert "OPENAI_API_KEY=" not in report
    assert "sk-" not in report
    assert "file_contents" not in report
    assert "content" not in report


def test_cli_supports_output_markdown(tmp_path):
    from tsc_cycle.cleanup_inventory import main

    output_json = tmp_path / "inventory.json"
    output_md = tmp_path / "inventory.md"

    assert main(["--repo-root", str(REPO_ROOT), "--output-json", str(output_json), "--output-md", str(output_md)]) == 0
    assert output_json.exists()
    assert output_md.exists()

    report = output_md.read_text(encoding="utf-8")
    assert "# Phase 13 Inventory & Cleanup Boundaries" in report
    assert "Phase 13 is non-destructive" in report
