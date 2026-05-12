from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tsc_cycle.cleanup_inventory import CANONICAL_V4_ASSETS, resolve_repo_path


PACKAGE_ID = "v4.0-qwen3-4b-9k"
MANIFEST_PATH = "reproduction/v4.0-qwen3-4b-9k-manifest.json"
GUIDE_PATH = "reproduction/v4.0-qwen3-4b-9k-guide.md"
DEFAULT_INVENTORY_PATH = ".planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json"

REQUIRED_SOURCE_PATHS = {
    "data/v4/phase8/labeled_merged.jsonl": "Merged v4 labeled dataset used for Qwen3-4B 9k SFT.",
    "data/v4/phase8/splits/manifest.json": "v4 Phase 8 split manifest with train/val/OOD counts.",
    "data/v4/phase8/splits/train.index.jsonl": "v4 Phase 8 train split index.",
    "data/v4/phase8/splits/val.index.jsonl": "v4 Phase 8 validation split index.",
    "data/v4/phase8/splits/ood_val.index.jsonl": "v4 Phase 8 OOD validation split index.",
}

OPTIONAL_REBUILD_CACHE_PATHS = {
    "data/v4/phase8/tokenized/train.arrow": "Tokenized train Arrow cache; useful when skipping tokenization, not required source.",
    "data/v4/phase8/tokenized/val.arrow": "Tokenized validation Arrow cache; useful when skipping tokenization, not required source.",
    "data/v4/phase8/tokenized/ood_val.arrow": "Tokenized OOD validation Arrow cache; useful when skipping tokenization, not required source.",
}

OPTIONAL_AUDIT_PATHS = {
    "runs/v4.0-4B-20260509T184844Z/eval_phase11/matrix_manifest.json": "Phase 11 evaluation matrix manifest.",
    "runs/v4.0-4B-20260509T184844Z/eval_phase11/metrics.json": "Phase 11 evaluation metrics JSON.",
    "runs/v4.0-4B-20260509T184844Z/eval_phase11/per_sample.jsonl": "Phase 11 per-sample evaluation audit evidence.",
    "runs/v4.0-4B-20260509T184844Z/eval_phase11/report.md": "Phase 11 human metrics report.",
    "runs/v4.0-4B-20260509T184844Z/eval_phase11/decision.md": "Phase 11 GO decision narrative.",
}

OBSOLETE_LEGACY_PATHS = {
    "runs/20260507T032419Z/gguf/model.q4_K_M.gguf": "v1 q4_K_M historical baseline; not the v4 target.",
    "data/v3": "v3 data lineage; not required for the v4.0 Qwen3-4B 9k package.",
    "artifacts/v3": "v3 gate reports; historical audit only.",
    "runs/v3.0-gates": "v3 gate run outputs; historical audit only.",
    "raw_responses": "Legacy teacher/API raw responses; not reproducer-facing v4 source.",
    "reality.log": "Original input distribution log; v4 final replay output is reality_test.log.",
}

LOCAL_TEMPORARY_PATHS = {
    ".env": "Local environment file; metadata only, payload omitted.",
    ".venv": "Local virtual environment; not part of reproduction package.",
    ".claude": "Local agent state; not part of reproduction package.",
    ".pytest_cache": "Local pytest cache; not part of reproduction package.",
    "tsc_cycle/__pycache__": "Local Python bytecode cache; not part of reproduction package.",
}

TEXT_LINE_SUFFIXES = (".jsonl", ".log", ".md", ".py")


def _resolve_repo_path(repo_root: Path | str, path: Path | str) -> Path:
    return resolve_repo_path(path, repo_root)


def _repo_relative(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _line_count(path: Path) -> int:
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def _load_json(path: Path) -> Any:
    if not path.exists() or not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_inventory(repo_root: Path, inventory_path: Path | str | None) -> dict[str, Any]:
    rel_or_abs = inventory_path if inventory_path is not None else DEFAULT_INVENTORY_PATH
    path = _resolve_repo_path(repo_root, rel_or_abs)
    if not path.exists():
        return {"entries": []}
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"inventory must be a JSON object: {path}")
    return data


def _inventory_entry(inventory: dict[str, Any], rel_path: str) -> dict[str, Any] | None:
    for entry in inventory.get("entries", []):
        if entry.get("path") == rel_path:
            return entry
    return None


def _asset(
    repo_root: Path,
    rel_path: str,
    *,
    category: str,
    role: str,
    description: str,
    required: bool,
    inventory: dict[str, Any],
    counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    path = _resolve_repo_path(repo_root, rel_path)
    exists = path.exists()
    entry: dict[str, Any] = {
        "path": rel_path,
        "category": category,
        "role": role,
        "description": description,
        "required": required,
        "exists": exists,
        "source": "disk_metadata",
    }
    if category == "local_temporary":
        return {
            "path": rel_path,
            "category": category,
            "exists": exists,
        }

    inv_entry = _inventory_entry(inventory, rel_path)
    if inv_entry is not None:
        entry["phase13_classification"] = inv_entry.get("classification")
        entry["phase15_allowed"] = inv_entry.get("phase15_allowed")
        entry["recommended_action"] = inv_entry.get("recommended_action")
    if path.is_file():
        entry["size_bytes"] = path.stat().st_size
        entry["sha256"] = _sha256_file(path)
        if rel_path.endswith(TEXT_LINE_SUFFIXES):
            entry["line_count"] = _line_count(path)
    else:
        entry["size_bytes"] = path.stat().st_size if exists else 0
        entry["sha256"] = None
    if counts:
        entry["counts"] = counts
    return entry


def _split_counts(repo_root: Path) -> dict[str, int]:
    manifest = _load_json(repo_root / "data/v4/phase8/splits/manifest.json")
    counts: dict[str, int] = {}
    if isinstance(manifest, dict):
        split_counts = manifest.get("split_counts")
        if isinstance(split_counts, dict):
            for key in ("train", "val", "ood_val"):
                value = split_counts.get(key)
                if isinstance(value, int):
                    counts[f"{key}_rows"] = value
        splits = manifest.get("splits")
        if isinstance(splits, dict):
            for key in ("train", "val", "ood_val"):
                value = splits.get(key)
                if isinstance(value, dict):
                    count = value.get("count") or value.get("rows") or value.get("n")
                    if isinstance(count, int):
                        counts.setdefault(f"{key}_rows", count)
                elif isinstance(value, int):
                    counts.setdefault(f"{key}_rows", value)
        for key in ("train_count", "val_count", "ood_val_count", "total", "total_rows"):
            if isinstance(manifest.get(key), int):
                counts[key] = manifest[key]
    return counts


def _phase12_counts(repo_root: Path) -> dict[str, int]:
    report = _load_json(repo_root / "artifacts/v4/phase12/phase12_report.json")
    counts: dict[str, int] = {}
    if isinstance(report, dict):
        for key in ("input_count", "output_count", "parse_ok_count", "lint_ok_count", "protocol_ok_count", "timeout_count"):
            if isinstance(report.get(key), int):
                counts[key] = report[key]
        if isinstance(report.get("output_count"), int):
            counts["phase12_outputs"] = report["output_count"]
    return counts


def _expected_counts_for_asset(repo_root: Path, rel_path: str) -> dict[str, int]:
    if rel_path == "data/v4/phase8/labeled_merged.jsonl":
        path = _resolve_repo_path(repo_root, rel_path)
        return {"labeled_rows": _line_count(path)} if path.is_file() else {}
    if rel_path == "data/v4/phase8/splits/manifest.json":
        counts = _split_counts(repo_root)
        split_index_paths = {
            "train_rows": "data/v4/phase8/splits/train.index.jsonl",
            "val_rows": "data/v4/phase8/splits/val.index.jsonl",
            "ood_val_rows": "data/v4/phase8/splits/ood_val.index.jsonl",
        }
        for key, split_path in split_index_paths.items():
            path = _resolve_repo_path(repo_root, split_path)
            if path.is_file():
                counts[key] = _line_count(path)
        return counts
    if rel_path == "artifacts/v4/phase12/per_sample.jsonl":
        path = _resolve_repo_path(repo_root, rel_path)
        counts = _phase12_counts(repo_root)
        if path.is_file():
            counts["phase12_outputs"] = _line_count(path)
        return counts
    if rel_path in {"artifacts/v4/phase12/phase12_report.json", "artifacts/v4/phase12/manifest.json", "reality_test.log"}:
        return _phase12_counts(repo_root)
    return {}


def _validate_asset_counts(repo_root: Path, rel_path: str, asset_counts: Any) -> list[str]:
    expected = _expected_counts_for_asset(repo_root, rel_path)
    if not expected:
        return []
    if not isinstance(asset_counts, dict):
        return [f"{rel_path}: missing counts metadata"]
    errors: list[str] = []
    for key, expected_value in expected.items():
        actual_value = asset_counts.get(key)
        if actual_value != expected_value:
            errors.append(f"{rel_path}: counts.{key} mismatch manifest={actual_value} disk={expected_value}")
    return errors


def _final_artifacts(repo_root: Path) -> dict[str, Any]:
    phase10 = _load_json(repo_root / "runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json")
    phase11 = _load_json(repo_root / "artifacts/v4/phase11/phase11_gate_report.json")
    phase12 = _load_json(repo_root / "artifacts/v4/phase12/phase12_report.json")
    return {
        "q4_K_M": "runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf",
        "phase10_reported_q4_sha256": (phase10 or {}).get("artifact_manifest", {}).get("sha256", {}).get("gguf_q4_K_M") if isinstance(phase10, dict) else None,
        "phase11_verdict": (phase11 or {}).get("decision", {}).get("verdict") if isinstance(phase11, dict) else None,
        "phase11_recommended_artifact": _repo_relative(Path((phase11 or {}).get("recommended_artifact")), repo_root) if isinstance(phase11, dict) and (phase11 or {}).get("recommended_artifact") else None,
        "phase12_model_sha256": (phase12 or {}).get("model_sha256") if isinstance(phase12, dict) else None,
        "phase12_output_sha256": (phase12 or {}).get("output_sha256") if isinstance(phase12, dict) else None,
    }


def _category_assets(repo_root: Path, inventory: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    phase12_counts = _phase12_counts(repo_root)
    split_counts = _split_counts(repo_root)
    categories = {
        "required_evidence": [],
        "required_source": [],
        "optional_rebuild_cache": [],
        "optional_audit": [],
        "obsolete_legacy": [],
        "local_temporary": [],
    }
    for rel_path, description in sorted(CANONICAL_V4_ASSETS.items()):
        counts = phase12_counts if rel_path in {"artifacts/v4/phase12/per_sample.jsonl", "artifacts/v4/phase12/phase12_report.json", "artifacts/v4/phase12/manifest.json", "reality_test.log"} else None
        categories["required_evidence"].append(
            _asset(repo_root, rel_path, category="required_evidence", role="canonical_v4_evidence", description=description, required=True, inventory=inventory, counts=counts)
        )
    for rel_path, description in sorted(REQUIRED_SOURCE_PATHS.items()):
        counts = None
        if rel_path == "data/v4/phase8/labeled_merged.jsonl":
            disk_path = _resolve_repo_path(repo_root, rel_path)
            counts = {"labeled_rows": _line_count(disk_path)} if disk_path.exists() else {}
        elif rel_path == "data/v4/phase8/splits/manifest.json":
            counts = split_counts
        categories["required_source"].append(
            _asset(repo_root, rel_path, category="required_source", role="v4_dataset_source", description=description, required=True, inventory=inventory, counts=counts)
        )
    for rel_path, description in sorted(OPTIONAL_REBUILD_CACHE_PATHS.items()):
        categories["optional_rebuild_cache"].append(
            _asset(repo_root, rel_path, category="optional_rebuild_cache", role="rebuild_cache", description=description, required=False, inventory=inventory)
        )
    for rel_path, description in sorted(OPTIONAL_AUDIT_PATHS.items()):
        categories["optional_audit"].append(
            _asset(repo_root, rel_path, category="optional_audit", role="audit_evidence", description=description, required=False, inventory=inventory)
        )
    for rel_path, description in sorted(OBSOLETE_LEGACY_PATHS.items()):
        categories["obsolete_legacy"].append(
            _asset(repo_root, rel_path, category="obsolete_legacy", role="not_v4_target", description=description, required=False, inventory=inventory)
        )
    for rel_path, description in sorted(LOCAL_TEMPORARY_PATHS.items()):
        categories["local_temporary"].append(
            _asset(repo_root, rel_path, category="local_temporary", role="metadata_only_local_state", description=description, required=False, inventory=inventory)
        )
    return categories


def build_package_manifest(repo_root: Path | str, inventory_path: Path | str | None = None) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    _resolve_repo_path(root, root)
    inventory = _load_inventory(root, inventory_path)
    assets = _category_assets(root, inventory)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": "2026-05-12",
        "package_id": PACKAGE_ID,
        "source_of_truth": {
            "manifest": MANIFEST_PATH,
            "guide": GUIDE_PATH,
            "note": "Repo-level reproduction files are the reproducer-facing source of truth; .planning/phases is provenance input only.",
        },
        "phase14_scope": "Non-destructive metadata packaging only: no delete, archive, move, retrain, dataset regeneration, or model inference.",
        "final_artifacts": _final_artifacts(root),
        "assets": assets,
        "verification_commands": [
            "python -m tsc_cycle.reproduction_manifest --check reproduction/v4.0-qwen3-4b-9k-manifest.json",
            "PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/test_v4_reproduction_package.py tests/test_cleanup_inventory.py -q",
        ],
        "provenance_inputs": [
            DEFAULT_INVENTORY_PATH,
            ".planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.md",
            "artifacts/v4/phase12/phase12_report.json",
            "artifacts/v4/phase12/manifest.json",
            "data/v4/phase8/splits/manifest.json",
            "artifacts/v4/phase11/phase11_gate_report.json",
            "runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json",
            "runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json",
        ],
    }
    return manifest


def write_manifest_json(manifest: dict[str, Any], output_path: Path | str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _md_cell(value: Any) -> str:
    text = ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)
    return text.translate({ord("|"): "\\|", ord("\n"): " "})


def _asset_table(title: str, assets: list[dict[str, Any]]) -> list[str]:
    lines = [f"### {title}", "", "| path | exists | size_bytes | sha256 | counts | note |", "|------|--------|------------|--------|--------|------|"]
    for asset in assets:
        counts = json.dumps(asset.get("counts", {}), ensure_ascii=False, sort_keys=True)
        lines.append(
            f"| {_md_cell(asset['path'])} | {_md_cell(asset.get('exists'))} | {_md_cell(asset.get('size_bytes'))} | {_md_cell(asset.get('sha256'))} | {_md_cell(counts)} | {_md_cell(asset.get('description', ''))} |"
        )
    lines.append("")
    return lines


def _local_temporary_asset_table(title: str, assets: list[dict[str, Any]]) -> list[str]:
    lines = [f"### {title}", "", "| path | category | exists |", "|------|----------|--------|"]
    for asset in assets:
        lines.append(f"| {_md_cell(asset['path'])} | {_md_cell(asset.get('category'))} | {_md_cell(asset.get('exists'))} |")
    lines.append("")
    return lines


def write_guide_markdown(manifest: dict[str, Any], output_path: Path | str) -> None:
    final_path = manifest["final_artifacts"]["q4_K_M"]
    entries = {asset["path"]: asset for category in manifest["assets"].values() for asset in category}
    final_hash = entries[final_path]["sha256"]
    phase12_outputs = entries["artifacts/v4/phase12/per_sample.jsonl"].get("counts", {}).get("phase12_outputs")
    labeled_rows = entries["data/v4/phase8/labeled_merged.jsonl"].get("counts", {}).get("labeled_rows")
    lines: list[str] = [
        "# v4.0 Qwen3-4B 9k Reproduction Package",
        "",
        f"Package ID: `{manifest['package_id']}`.",
        "",
        "Start here: use `reproduction/v4.0-qwen3-4b-9k-manifest.json` for machine-readable hashes, sizes, counts, and categories. This guide is the human entry point.",
        "",
        "do not use `.planning/phases/` as the source of truth; those files are provenance inputs only. The repo-level `reproduction/` files define the reproducer-facing package boundary.",
        "",
        "## Final v4 Target",
        "",
        f"- Final q4_K_M GGUF: `{final_path}`",
        f"- SHA-256: `{final_hash}`",
        "- Final replay output: `reality_test.log`",
        f"- Phase 12 replay outputs: `{phase12_outputs}`",
        f"- v4 labeled merged rows: `{labeled_rows}`",
        "- v1/v3/raw outputs are not the v4 target; the v1 q4_K_M file is historical only.",
        "",
        "## Verification Commands",
        "",
    ]
    for command in manifest["verification_commands"]:
        lines.extend(["```bash", command, "```", ""])
    lines.extend([
        "Short forms from the repository root:",
        "",
        "```bash",
        "python -m tsc_cycle.reproduction_manifest --check reproduction/v4.0-qwen3-4b-9k-manifest.json",
        "PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/test_v4_reproduction_package.py tests/test_cleanup_inventory.py -q",
        "```",
        "",
        "## Package Categories",
        "",
        "Required evidence and source assets are needed to locate and audit the shipped v4 package. Optional rebuild caches and audit files help inspection but are not required source. Obsolete legacy and local temporary entries are explicitly not the v4 target.",
        "",
    ])
    category_titles = {
        "required_evidence": "Required Evidence",
        "required_source": "Required Source/Data Inputs",
        "optional_rebuild_cache": "Optional Rebuild Cache",
        "optional_audit": "Optional Audit Evidence",
        "obsolete_legacy": "Obsolete Legacy / Not the v4 Target",
        "local_temporary": "Local Temporary Metadata Only",
    }
    for category, title in category_titles.items():
        assets = manifest["assets"].get(category, [])
        if category == "local_temporary":
            lines.extend(_local_temporary_asset_table(title, assets))
        else:
            lines.extend(_asset_table(title, assets))
    lines.extend([
        "## Scope",
        "",
        manifest["phase14_scope"],
        "",
        "The manifest/guide recompute disk metadata and serialize metadata only; they do not include file payloads, secrets, cache payloads, or local environment payloads.",
        "",
    ])
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _manifest_assets(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    assets = manifest.get("assets")
    if not isinstance(assets, dict):
        return []
    return [asset for category_assets in assets.values() if isinstance(category_assets, list) for asset in category_assets]


def _validate_manifest_structure(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("package_id") != PACKAGE_ID:
        errors.append(f"package_id mismatch manifest={manifest.get('package_id')} expected={PACKAGE_ID}")

    assets = manifest.get("assets")
    if not isinstance(assets, dict):
        errors.append("assets must be a JSON object")
        return errors

    required_categories = {
        "required_evidence": set(CANONICAL_V4_ASSETS),
        "required_source": set(REQUIRED_SOURCE_PATHS),
    }
    for category, required_paths in required_categories.items():
        category_assets = assets.get(category)
        if not isinstance(category_assets, list):
            errors.append(f"assets.{category} must be a list")
            continue
        category_paths = {asset.get("path") for asset in category_assets if isinstance(asset, dict)}
        for rel_path in sorted(required_paths - category_paths):
            errors.append(f"{rel_path}: missing from assets.{category}")
    return errors


def validate_manifest_against_disk(manifest: dict[str, Any], repo_root: Path | str) -> list[str]:
    root = Path(repo_root).resolve()
    errors: list[str] = []
    errors.extend(_validate_manifest_structure(manifest))
    required_categories = {"required_evidence", "required_source"}
    assets_by_category = manifest.get("assets") if isinstance(manifest.get("assets"), dict) else {}
    for category, assets in assets_by_category.items():
        if not isinstance(assets, list):
            errors.append(f"assets.{category} must be a list")
            continue
        for asset in assets:
            if not isinstance(asset, dict):
                errors.append(f"invalid asset in {category}: expected JSON object")
                continue
            rel_path = asset.get("path")
            if not isinstance(rel_path, str):
                errors.append(f"missing path in {category}")
                continue
            try:
                path = _resolve_repo_path(root, rel_path)
            except ValueError as exc:
                errors.append(f"{rel_path}: {exc}")
                continue
            if category in required_categories and not path.exists():
                errors.append(f"{rel_path}: required asset missing")
                continue
            if category == "local_temporary":
                forbidden_keys = sorted({"line_count", "sha256", "size_bytes"} & set(asset))
                if forbidden_keys:
                    errors.append(f"{rel_path}: local_temporary must omit {', '.join(forbidden_keys)}")
                continue
            if not path.is_file():
                continue
            actual_size = path.stat().st_size
            if asset.get("size_bytes") != actual_size:
                errors.append(f"{rel_path}: size mismatch manifest={asset.get('size_bytes')} disk={actual_size}")
            actual_sha = _sha256_file(path)
            if asset.get("sha256") != actual_sha:
                errors.append(f"{rel_path}: sha256 mismatch manifest={asset.get('sha256')} disk={actual_sha}")
            if rel_path.endswith(TEXT_LINE_SUFFIXES):
                actual_lines = _line_count(path)
                if asset.get("line_count") != actual_lines:
                    errors.append(f"{rel_path}: line_count mismatch manifest={asset.get('line_count')} disk={actual_lines}")
            errors.extend(_validate_asset_counts(root, rel_path, asset.get("counts")))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or validate the v4.0 Qwen3-4B 9k reproduction manifest.")
    parser.add_argument("--repo-root", default=str(Path.cwd()), help="Repository root")
    parser.add_argument("--inventory", default=None, help="Phase 13 inventory JSON path")
    parser.add_argument("--output-json", default=MANIFEST_PATH, help="Manifest JSON output path")
    parser.add_argument("--output-guide", default=GUIDE_PATH, help="Guide Markdown output path")
    parser.add_argument("--check", nargs="?", const=MANIFEST_PATH, help="Validate an existing manifest path instead of writing outputs")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    if args.check:
        check_path = _resolve_repo_path(repo_root, args.check)
        manifest = _load_json(check_path)
        if not isinstance(manifest, dict):
            print(f"invalid manifest: {check_path}")
            return 2
        errors = validate_manifest_against_disk(manifest, repo_root)
        if errors:
            for error in errors:
                print(error)
            return 1
        print(f"OK: {check_path}")
        return 0

    manifest = build_package_manifest(repo_root, args.inventory)
    write_manifest_json(manifest, _resolve_repo_path(repo_root, args.output_json))
    write_guide_markdown(manifest, _resolve_repo_path(repo_root, args.output_guide))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
