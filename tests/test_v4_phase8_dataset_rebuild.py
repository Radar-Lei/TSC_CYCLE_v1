from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

FROZEN_V1_ROOT = Path("/home/samuel/TSC_CYCLE/runs/20260507T032419Z")
EXPECTED_MODEL_ID = "Qwen/Qwen3-4B-Thinking-2507"
V4_SPLIT_DIR = Path("data/v4/phase8/splits")
V4_TOKENIZED_DIR = Path("data/v4/phase8/tokenized")
V4_ARTIFACTS_DIR = Path("artifacts/v4/phase8")
V3_MERGED_ONLY_SOURCE = Path("data/v3/phase2/labeled_merged.jsonl")


def _dataset_contract():
    from tsc_cycle.v4_gates.dataset_rebuild import (  # noqa: PLC0415
        Phase8DatasetConfig,
        build_parser,
        build_v4_source_dataset,
        build_v4_splits_and_tokenized,
    )

    return {
        "Phase8DatasetConfig": Phase8DatasetConfig,
        "build_parser": build_parser,
        "build_v4_source_dataset": build_v4_source_dataset,
        "build_v4_splits_and_tokenized": build_v4_splits_and_tokenized,
    }


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_hash(row: dict[str, Any]) -> str:
    return _sha256_bytes(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _sample(
    sample_id: str,
    *,
    lineage: str,
    split_hint: str = "same_dist",
    reasoning: str = "Allocate green by predicted saturation while respecting every bound.",
    solution: dict[str, int] | None = None,
) -> dict[str, Any]:
    phase_ids = [1, 2, 3]
    if solution is None:
        solution = {str(phase_id): 24 + phase_id for phase_id in phase_ids}
    return {
        "sample_id": sample_id,
        "lineage": lineage,
        "source": split_hint,
        "split_hint": split_hint,
        "input": {
            "sample_id": sample_id,
            "lineage": lineage,
            "source": split_hint,
            "split_hint": split_hint,
            "prediction": {
                "as_of": "2026-05-10 00:00:00",
                "phase_waits": [
                    {
                        "phase_id": phase_id,
                        "pred_wait": float((sum(ord(ch) for ch in sample_id) + phase_id) % 60),
                        "pred_saturation": 0.10 + phase_id / 100,
                        "min_green": 10,
                        "max_green": 90,
                        "capacity": 40 + phase_id,
                    }
                    for phase_id in phase_ids
                ],
            },
        },
        "result": {
            "success": True,
            "reasoning": reasoning,
            "solution": solution,
        },
    }


def _source_fixtures(tmp_path: Path) -> tuple[Path, Path, list[dict[str, Any]], list[dict[str, Any]]]:
    v1_rows = [
        _sample("shared-dedupe", lineage="v1.0", split_hint="ood", reasoning="v1 row uses <end_working_out> typo once."),
        _sample("v1-ood-comparable-0001", lineage="v1.0", split_hint="ood"),
        _sample("v1-same-0002", lineage="v1.0", split_hint="same_dist"),
    ]
    v3_duplicate = _sample("shared-dedupe", lineage="v3.0", split_hint="ood", reasoning="v1 row uses </end_working_out> typo once.")
    v3_rows = [
        v3_duplicate,
        _sample("v3-extended-ood-0001", lineage="v3.0", split_hint="ood", reasoning="extended OOD row"),
        _sample("v3-same-0002", lineage="v3.0", split_hint="same_dist"),
    ]
    v1_path = _write_jsonl(tmp_path / "sources" / "v1_valid_labeled.jsonl", v1_rows)
    v3_path = _write_jsonl(tmp_path / "sources" / "v3_new_lint_pass_labeled.jsonl", v3_rows)
    return v1_path, v3_path, v1_rows, v3_rows


def _phase8_config(tmp_path: Path, v1_path: Path, v3_path: Path, **overrides: Any):
    contract = _dataset_contract()
    Phase8DatasetConfig = contract["Phase8DatasetConfig"]
    kwargs = {
        "v1_valid_labeled_jsonl": v1_path,
        "v3_new_lint_pass_labeled_jsonl": v3_path,
        "split_dir": tmp_path / V4_SPLIT_DIR,
        "tokenized_dir": tmp_path / V4_TOKENIZED_DIR,
        "artifacts_dir": tmp_path / V4_ARTIFACTS_DIR,
        "model_name": EXPECTED_MODEL_ID,
        "seed": 42,
        "max_seq_length": 2048,
        "max_truncation_rate": 0.05,
    }
    kwargs.update(overrides)
    return Phase8DatasetConfig(**kwargs)


def test_source_dataset_requires_exact_v1_and_v3_sources_not_v3_merged_only(tmp_path: Path) -> None:
    contract = _dataset_contract()
    v1_path, v3_path, _v1_rows, _v3_rows = _source_fixtures(tmp_path)
    config = _phase8_config(tmp_path, v1_path, v3_path)

    report = contract["build_v4_source_dataset"](config)

    assert report["ok"] is True, "DATA4B-01 source merge must accept explicit v1 valid and v3 new lint-pass JSONL files"
    assert report["requirements_covered"] == ["DATA4B-01"]
    assert report["source_counts"] == {"v1_valid": 3, "v3_new_lint_pass": 3}
    assert report["deduped_count"] == 5
    assert report["duplicates"]["v3_duplicate_rows"] == 1
    assert Path(report["source_manifest_path"]) == tmp_path / V4_ARTIFACTS_DIR / "source_manifest.json"
    assert Path(report["cleaning_report_path"]) == tmp_path / V4_ARTIFACTS_DIR / "cleaning_report.json"
    assert Path(report["merged_jsonl_path"]) == tmp_path / V4_SPLIT_DIR / "labeled_merged.normalized.jsonl"
    assert not _is_under(Path(report["merged_jsonl_path"]), FROZEN_V1_ROOT)

    manifest = _read_json(tmp_path / V4_ARTIFACTS_DIR / "source_manifest.json")
    assert manifest["ok"] is True
    assert manifest["sources"] == {
        "v1_valid_labeled_jsonl": str(v1_path),
        "v3_new_lint_pass_labeled_jsonl": str(v3_path),
    }
    assert V3_MERGED_ONLY_SOURCE.as_posix() not in json.dumps(manifest, ensure_ascii=False)
    assert manifest["source_sha256"] == {"v1_valid": _sha256_file(v1_path), "v3_new_lint_pass": _sha256_file(v3_path)}
    assert manifest["source_counts"] == {"v1_valid": 3, "v3_new_lint_pass": 3}
    assert manifest["duplicate_counts"]["v3_duplicate_rows"] == 1
    assert "DATA4B-01" in manifest["requirements_covered"]
    assert len(manifest["sample_hashes"]) == 5

    forbidden_config = _phase8_config(
        tmp_path / "forbidden",
        tmp_path / "missing_v1.jsonl",
        tmp_path / "missing_v3.jsonl",
        merged_input=tmp_path / V3_MERGED_ONLY_SOURCE,
    )
    forbidden_report = contract["build_v4_source_dataset"](forbidden_config)
    assert forbidden_report["ok"] is False, "DATA4B-01 must not be satisfied by data/v3/phase2/labeled_merged.jsonl as a single source"
    assert any(failure["gate"] == "explicit_two_sources" for failure in forbidden_report["fatal_failures"])


def test_label_normalization_rewrites_malformed_close_and_fails_on_native_think_tags(tmp_path: Path) -> None:
    contract = _dataset_contract()
    v1_path, v3_path, _v1_rows, _v3_rows = _source_fixtures(tmp_path)
    config = _phase8_config(tmp_path, v1_path, v3_path)

    report = contract["build_v4_source_dataset"](config)

    assert report["ok"] is True, "TAG-02 normalization is part of DATA4B-01 source cleaning"
    cleaning = _read_json(tmp_path / V4_ARTIFACTS_DIR / "cleaning_report.json")
    assert cleaning["ok"] is True
    assert cleaning["malformed_think_close_replacements"] == 1
    assert cleaning["forbidden_native_think_rows"] == []
    assert cleaning["forbidden_malformed_close_after_normalization"] == []
    assert "DATA4B-01" in cleaning["requirements_covered"]

    merged_rows = _read_jsonl(tmp_path / V4_SPLIT_DIR / "labeled_merged.normalized.jsonl")
    merged_text = json.dumps(merged_rows, ensure_ascii=False)
    assert "</end_working_out>" in merged_text
    assert "<end_working_out>" not in merged_text
    assert "<think>" not in merged_text
    assert "</think>" not in merged_text

    native_rows = [_sample("bad-native", lineage="v1.0", split_hint="same_dist", reasoning="native <think> leak")]
    native_v1 = _write_jsonl(tmp_path / "native" / "v1.jsonl", native_rows)
    native_v3 = _write_jsonl(tmp_path / "native" / "v3.jsonl", [_sample("ok-v3", lineage="v3.0")])
    native_config = _phase8_config(tmp_path / "native", native_v1, native_v3)
    native_report = contract["build_v4_source_dataset"](native_config)

    assert native_report["ok"] is False, "DATA4B-01 must fail closed on native <think>/</think> text leakage"
    native_cleaning = _read_json(tmp_path / "native" / V4_ARTIFACTS_DIR / "cleaning_report.json")
    assert native_cleaning["ok"] is False
    assert native_cleaning["forbidden_native_think_rows"] == ["bad-native"]
    assert not (tmp_path / "native" / V4_SPLIT_DIR / "labeled_merged.normalized.jsonl").exists()


def test_canonical_hash_dedupe_prefers_v1_rows_and_records_manifest_evidence(tmp_path: Path) -> None:
    contract = _dataset_contract()
    v1_path, v3_path, v1_rows, v3_rows = _source_fixtures(tmp_path)
    config = _phase8_config(tmp_path, v1_path, v3_path)

    report = contract["build_v4_source_dataset"](config)

    assert report["ok"] is True
    merged_rows = _read_jsonl(tmp_path / V4_SPLIT_DIR / "labeled_merged.normalized.jsonl")
    shared_rows = [row for row in merged_rows if row["sample_id"] == "shared-dedupe"]
    assert len(shared_rows) == 1
    assert shared_rows[0]["lineage"] == "v1.0", "DATA4B-01 deterministic dedupe must prefer v1 rows over duplicate v3 rows"
    assert shared_rows[0]["result"]["reasoning"] == "v1 row uses </end_working_out> typo once."

    manifest = _read_json(tmp_path / V4_ARTIFACTS_DIR / "source_manifest.json")
    shared_hash = _canonical_hash(shared_rows[0])
    assert shared_hash in manifest["sample_hashes"]
    assert manifest["dedupe_key"] == "canonical_normalized_record_sha256"
    assert manifest["duplicate_counts"] == {
        "total_duplicate_rows": 1,
        "v1_duplicate_rows": 0,
        "v3_duplicate_rows": 1,
    }
    assert manifest["duplicate_samples"][0]["kept_source"] == "v1_valid"
    assert manifest["duplicate_samples"][0]["dropped_source"] == "v3_new_lint_pass"
    assert manifest["duplicate_samples"][0]["sample_id"] == "shared-dedupe"
    assert manifest["source_sha256"]["v1_valid"] == _sha256_file(v1_path)
    assert manifest["source_sha256"]["v3_new_lint_pass"] == _sha256_file(v3_path)
    assert manifest["source_counts"]["v1_valid"] == len(v1_rows)
    assert manifest["source_counts"]["v3_new_lint_pass"] == len(v3_rows)
    assert set(manifest["requirements_covered"]) >= {"DATA4B-01"}

    for path_text in json.dumps(report, ensure_ascii=False).split('"'):
        if path_text.startswith(str(tmp_path)):
            assert not _is_under(Path(path_text), FROZEN_V1_ROOT)
