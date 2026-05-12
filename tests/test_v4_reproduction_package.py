from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_EVIDENCE_PATHS = {
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

REQUIRED_SOURCE_PATHS = {
    "data/v4/phase8/labeled_merged.jsonl",
    "data/v4/phase8/splits/manifest.json",
    "data/v4/phase8/splits/train.index.jsonl",
    "data/v4/phase8/splits/val.index.jsonl",
    "data/v4/phase8/splits/ood_val.index.jsonl",
}

OPTIONAL_REBUILD_CACHE_PATHS = {
    "data/v4/phase8/tokenized/train.arrow",
    "data/v4/phase8/tokenized/val.arrow",
    "data/v4/phase8/tokenized/ood_val.arrow",
}

FORBIDDEN_SERIALIZED_TEXT = [
    "OPENAI_API_KEY=",
    "sk-",
    ".env contents",
    ".venv/",
    ".claude/",
    "worktree payload",
]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def _assets_by_category(manifest: dict) -> dict[str, list[dict]]:
    return manifest["assets"]


def _entries_by_path(manifest: dict) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    for assets in _assets_by_category(manifest).values():
        for asset in assets:
            entries[asset["path"]] = asset
    return entries


def _build_manifest() -> dict:
    from tsc_cycle.reproduction_manifest import build_package_manifest

    return build_package_manifest(REPO_ROOT)


def test_manifest_lists_required_v4_assets():
    manifest = _build_manifest()
    assets = _assets_by_category(manifest)
    by_path = _entries_by_path(manifest)

    assert REQUIRED_EVIDENCE_PATHS <= {asset["path"] for asset in assets["required_evidence"]}
    assert REQUIRED_SOURCE_PATHS <= {asset["path"] for asset in assets["required_source"]}
    assert not (OPTIONAL_REBUILD_CACHE_PATHS & {asset["path"] for asset in assets["required_evidence"]})
    assert not (OPTIONAL_REBUILD_CACHE_PATHS & {asset["path"] for asset in assets["required_source"]})

    assert manifest["source_of_truth"]["manifest"] == "reproduction/v4.0-qwen3-4b-9k-manifest.json"
    assert manifest["source_of_truth"]["guide"] == "reproduction/v4.0-qwen3-4b-9k-guide.md"
    assert ".planning/phases/" not in json.dumps(manifest["source_of_truth"], ensure_ascii=False)

    for path in REQUIRED_EVIDENCE_PATHS | REQUIRED_SOURCE_PATHS:
        assert by_path[path]["exists"] is True, path
        assert by_path[path]["sha256"], path
        assert by_path[path]["size_bytes"] > 0, path


def test_manifest_hashes_and_counts_match_disk():
    manifest = _build_manifest()
    by_path = _entries_by_path(manifest)

    for path, asset in by_path.items():
        disk_path = REPO_ROOT / path
        if disk_path.is_file():
            assert asset["sha256"] == _sha256_file(disk_path), path
            assert asset["size_bytes"] == disk_path.stat().st_size, path
            if path.endswith((".jsonl", ".log", ".md", ".py")):
                assert asset["line_count"] == _line_count(disk_path), path

    phase12 = by_path["artifacts/v4/phase12/per_sample.jsonl"]
    labeled = by_path["data/v4/phase8/labeled_merged.jsonl"]
    split_manifest = by_path["data/v4/phase8/splits/manifest.json"]
    assert phase12["line_count"] == 426
    assert phase12["counts"]["phase12_outputs"] == 426
    assert labeled["line_count"] == 9501
    assert labeled["counts"]["labeled_rows"] == 9501
    assert split_manifest["counts"] == {"ood_val_rows": 950, "train_rows": 7601, "val_rows": 950}


def test_manifest_classifies_required_optional_and_obsolete_assets():
    manifest = _build_manifest()
    assets = _assets_by_category(manifest)

    assert set(assets) >= {
        "required_evidence",
        "required_source",
        "optional_rebuild_cache",
        "optional_audit",
        "obsolete_legacy",
        "local_temporary",
    }

    assert OPTIONAL_REBUILD_CACHE_PATHS <= {asset["path"] for asset in assets["optional_rebuild_cache"]}
    obsolete_paths = {asset["path"] for asset in assets["obsolete_legacy"]}
    assert "runs/20260507T032419Z/gguf/model.q4_K_M.gguf" in obsolete_paths
    assert "data/v3" in obsolete_paths
    assert "artifacts/v3" in obsolete_paths
    assert "runs/v3.0-gates" in obsolete_paths
    assert "raw_responses" in obsolete_paths
    assert "reality.log" in obsolete_paths

    required_paths = {asset["path"] for asset in assets["required_evidence"]}
    assert "runs/20260507T032419Z/gguf/model.q4_K_M.gguf" not in required_paths
    assert "runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf" in required_paths

    local_paths = {asset["path"] for asset in assets["local_temporary"]}
    assert {".env", ".venv", ".claude"} <= local_paths

    for asset in assets["local_temporary"]:
        assert set(asset) == {"path", "category", "exists"}
        assert asset["category"] == "local_temporary"
        assert "sha256" not in asset
        assert "line_count" not in asset
        assert "size_bytes" not in asset


def test_guide_exposes_hashes_counts_and_commands(tmp_path):
    from tsc_cycle.reproduction_manifest import write_guide_markdown

    manifest = _build_manifest()
    guide_path = tmp_path / "guide.md"
    write_guide_markdown(manifest, guide_path)
    guide = guide_path.read_text(encoding="utf-8")

    entries = _entries_by_path(manifest)
    final_asset = entries["runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf"]
    phase12_outputs = entries["artifacts/v4/phase12/per_sample.jsonl"]["counts"]["phase12_outputs"]
    labeled_rows = entries["data/v4/phase8/labeled_merged.jsonl"]["counts"]["labeled_rows"]
    required_text = [
        "v4.0-qwen3-4b-9k-manifest.json",
        "runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf",
        final_asset["sha256"],
        "reality_test.log",
        f"Phase 12 replay outputs: `{phase12_outputs}`",
        f"v4 labeled merged rows: `{labeled_rows}`",
        "python -m tsc_cycle.reproduction_manifest --check",
        "tests/test_v4_reproduction_package.py",
    ]
    for text in required_text:
        assert text in guide

    assert "/home/samuel/TSC_CYCLE" not in guide
    assert all("/home/samuel/TSC_CYCLE" not in command for command in manifest["verification_commands"])
    assert "not the v4 target" in guide
    assert "do not use `.planning/phases/` as the source of truth" in guide


def test_reproduction_manifest_is_non_destructive_and_secret_safe(tmp_path):
    import tsc_cycle.reproduction_manifest as reproduction_manifest

    source = inspect.getsource(reproduction_manifest)
    destructive_tokens = ["unlink(", "rmtree(", "remove(", "rename(", "replace(", "shutil.move", "shutil.rmtree"]
    for token in destructive_tokens:
        assert token not in source, f"destructive call is forbidden: {token}"

    manifest = _build_manifest()
    guide_path = tmp_path / "guide.md"
    reproduction_manifest.write_guide_markdown(manifest, guide_path)
    serialized = json.dumps(manifest, ensure_ascii=False) + guide_path.read_text(encoding="utf-8")

    for asset in manifest["assets"]["local_temporary"]:
        assert set(asset) == {"path", "category", "exists"}
        assert asset["category"] == "local_temporary"
        assert "sha256" not in asset
        assert "line_count" not in asset
        assert "size_bytes" not in asset

    for forbidden in FORBIDDEN_SERIALIZED_TEXT:
        assert forbidden not in serialized
    assert "file_contents" not in serialized
    assert "content" not in serialized


def test_manifest_check_rejects_tampered_semantic_counts():
    from tsc_cycle.reproduction_manifest import validate_manifest_against_disk

    manifest = _build_manifest()
    by_path = _entries_by_path(manifest)
    by_path["artifacts/v4/phase12/per_sample.jsonl"]["counts"]["phase12_outputs"] = -1
    by_path["data/v4/phase8/labeled_merged.jsonl"]["counts"]["labeled_rows"] = -1
    by_path["data/v4/phase8/splits/manifest.json"]["counts"]["train_rows"] = -1

    errors = validate_manifest_against_disk(manifest, REPO_ROOT)

    assert any("phase12_outputs mismatch" in error for error in errors)
    assert any("labeled_rows mismatch" in error for error in errors)
    assert any("train_rows mismatch" in error for error in errors)


def test_repo_relative_path_guard_rejects_outside_root():
    from tsc_cycle.reproduction_manifest import _resolve_repo_path

    assert _resolve_repo_path(REPO_ROOT, "reproduction") == REPO_ROOT / "reproduction"

    with pytest.raises(ValueError):
        _resolve_repo_path(REPO_ROOT, "../outside")

    with pytest.raises(ValueError):
        _resolve_repo_path(REPO_ROOT, "/tmp/outside-tsc-cycle")
