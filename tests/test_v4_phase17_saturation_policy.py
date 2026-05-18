from __future__ import annotations

import ast
import builtins
import importlib
import json
import math
from pathlib import Path

import pytest

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
FORBIDDEN_COLLECTION_IMPORTS = {"torch", "transformers", "peft", "bitsandbytes", "vllm", "flash_attn", "openai"}


@pytest.fixture(autouse=True)
def _phase17_modules_are_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = importlib.import_module

    def guarded_import(name: str, package: str | None = None):
        root = name.split(".", 1)[0]
        if root in FORBIDDEN_COLLECTION_IMPORTS:
            raise AssertionError(f"Phase 17 contract imported heavyweight dependency during test execution: {name}")
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", guarded_import)


def _policy_contract():
    return importlib.import_module("tsc_cycle.v4_gates.saturation_policy")


def test_phase17_policy_module_does_not_import_heavy_model_stacks(monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = PROJECT_ROOT / "tsc_cycle" / "v4_gates" / "saturation_policy.py"
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert imported_roots.isdisjoint(FORBIDDEN_COLLECTION_IMPORTS)
    assert source.count("def classify_saturation_band(") == 1

    real_import = builtins.__import__

    def guarded_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        root = name.split(".", 1)[0]
        if root in FORBIDDEN_COLLECTION_IMPORTS:
            raise AssertionError(f"Phase 17 implementation imported heavyweight dependency during module import: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    importlib.import_module("tsc_cycle.v4_gates.saturation_policy")


def test_saturation_band_boundaries() -> None:
    mod = _policy_contract()

    assert mod.classify_saturation_band(0.1999) == mod.BAND_NEAR_MIN
    assert mod.classify_saturation_band(0.2) == mod.BAND_INTERPOLATED
    assert mod.classify_saturation_band(0.5999) == mod.BAND_INTERPOLATED
    assert mod.classify_saturation_band(0.6) == mod.BAND_HIGH_NOT_MAX
    assert mod.classify_saturation_band(0.9999) == mod.BAND_HIGH_NOT_MAX
    assert mod.classify_saturation_band(1.0) == mod.BAND_ALLOWED_MAX
    assert mod.classify_saturation_band(1.5) == mod.BAND_ALLOWED_MAX

    for bad in (None, "not-a-number", float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError, match="finite"):
            mod.classify_saturation_band(bad)

    low_max = {
        "pred_saturation": 0.1,
        "min_green": 10,
        "max_green": 50,
        "final_green": 50,
    }
    assert mod.classify_violation(low_max) == mod.VIOLATION_UNSATURATED_MAX_GREEN

    saturated_max = {**low_max, "pred_saturation": 1.0}
    assert mod.classify_violation(saturated_max) == mod.VIOLATION_ALLOWED_SATURATED_MAX_GREEN

    forced = {**low_max, "min_green": 40, "max_green": 40, "final_green": 40}
    assert mod.classify_violation(forced) == mod.VIOLATION_FORCED_TRIVIAL_RANGE

    normal = {**low_max, "final_green": 20}
    assert mod.classify_violation(normal) == mod.VIOLATION_NONE
    assert "POLICY-01" in mod.REQUIREMENTS_COVERED


def _write_jsonl(path: Path, rows: list[dict] | list[object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            if isinstance(row, str):
                fh.write(row + "\n")
            else:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def _dataset_row(sample_id: str, solution: dict[str, int] | None = None) -> dict:
    return {
        "sample_id": sample_id,
        "source": "ambiguous-source-hint",
        "source_origin": "v1_valid",
        "split_hint": "id",
        "input": {
            "prediction": {
                "phase_waits": [
                    {"phase_id": 1, "pred_saturation": 0.1, "min_green": 10, "max_green": 50, "pred_wait": 1.0, "capacity": 10},
                    {"phase_id": 2, "pred_saturation": 1.1, "min_green": 20, "max_green": 60, "pred_wait": 2.0, "capacity": 10},
                ]
            }
        },
        "result": {"success": True, "solution": solution or {"1": 50, "2": 60}},
    }


def test_dataset_audit_bands_by_split_and_source(tmp_path: Path) -> None:
    mod = _policy_contract()
    dataset = _write_jsonl(tmp_path / "labeled_merged.jsonl", [_dataset_row("sample-a")])
    split_dir = tmp_path / "splits"
    _write_jsonl(split_dir / "train.index.jsonl", [{"sample_id": "sample-a", "split": "train", "source": "phase8-source", "source_origin": "v1_valid"}])

    projection = mod.project_dataset_phase_decisions(dataset, split_dir=split_dir)

    assert projection["ok"] is True
    assert projection["input_count"] == 1
    assert projection["phase_row_count"] == 2
    assert projection["excluded_counts"] == {}
    rows = projection["rows"]
    required = {
        "origin_artifact",
        "sample_id",
        "phase_id",
        "pred_saturation",
        "saturation_band",
        "min_green",
        "max_green",
        "final_green",
        "split",
        "source",
        "violation_category",
        "trivial_range",
    }
    assert all(required <= set(row) for row in rows)
    assert rows[0]["split"] == "train"
    assert rows[0]["source"] == "phase8-source"
    assert rows[0]["origin_artifact"] == "dataset:labeled_merged.jsonl"
    assert rows[0]["saturation_band"] == mod.BAND_NEAR_MIN
    assert rows[0]["violation_category"] == mod.VIOLATION_UNSATURATED_MAX_GREEN
    assert rows[1]["saturation_band"] == mod.BAND_ALLOWED_MAX
    assert rows[1]["violation_category"] == mod.VIOLATION_ALLOWED_SATURATED_MAX_GREEN

    audit = mod.compute_saturation_audit(rows)
    assert audit["by_split"]["train"]["total_rows"] == 2
    assert audit["by_source"]["phase8-source"]["total_rows"] == 2
    assert audit["bands"][mod.BAND_NEAR_MIN]["final_equals_max_when_unsaturated"]["count"] == 1


def test_dataset_projection_surfaces_malformed_and_hard_constraint_invalid_rows(tmp_path: Path) -> None:
    mod = _policy_contract()
    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text('{"sample_id":"ok"}\nnot-json\n', encoding="utf-8")
    with pytest.raises(ValueError, match="malformed JSONL"):
        mod.project_dataset_phase_decisions(malformed)

    dataset = _write_jsonl(tmp_path / "bad_lint.jsonl", [_dataset_row("bad", {"1": 999, "2": 60})])
    projection = mod.project_dataset_phase_decisions(dataset)
    assert projection["ok"] is True
    assert projection["rows"] == []
    assert projection["excluded_counts"]["hard_constraint_invalid"] == 1
    assert projection["excluded_samples"][0]["sample_id"] == "bad"


def test_replay_projection_uses_structured_phase12_evidence_and_fails_on_mismatch(tmp_path: Path) -> None:
    mod = _policy_contract()
    records = [
        {
            "sample_id": "reality-0001",
            "input": _dataset_row("unused")["input"],
            "input_sha256": "hash-1",
        }
    ]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"records": records}, ensure_ascii=False), encoding="utf-8")
    per_sample = _write_jsonl(tmp_path / "per_sample.jsonl", [{"sample_id": "reality-0001", "solution": {"1": 50, "2": 60}, "lint_ok": True}])

    projection = mod.project_replay_phase_decisions(manifest, per_sample)

    assert projection["ok"] is True
    assert projection["phase_row_count"] == 2
    assert projection["rows"][0]["origin_artifact"] == "replay:phase12"
    assert projection["rows"][0]["sample_id"] == "reality-0001"

    mismatched = _write_jsonl(tmp_path / "mismatched.jsonl", [{"sample_id": "reality-9999", "solution": {"1": 50, "2": 60}}])
    with pytest.raises(ValueError, match="sample_id order"):
        mod.project_replay_phase_decisions(manifest, mismatched)

    non_object = _write_jsonl(tmp_path / "non_object.jsonl", ['["not", "object"]'])
    with pytest.raises(ValueError, match="JSONL row is not an object"):
        mod.project_replay_phase_decisions(manifest, non_object)


def test_representative_failures_include_dataset_and_replay_fields() -> None:
    mod = _policy_contract()
    rows = [
        {
            "origin_artifact": "dataset:labeled_merged.jsonl",
            "sample_id": "sample-a",
            "phase_id": "1",
            "pred_saturation": 0.1,
            "saturation_band": mod.BAND_NEAR_MIN,
            "min_green": 10,
            "max_green": 50,
            "final_green": 50,
            "split": "train",
            "source": "phase8-source",
            "violation_category": mod.VIOLATION_UNSATURATED_MAX_GREEN,
            "trivial_range": False,
        },
        {
            "origin_artifact": "replay:phase12",
            "sample_id": "reality-0001",
            "phase_id": "2",
            "pred_saturation": 0.5,
            "saturation_band": mod.BAND_INTERPOLATED,
            "min_green": 20,
            "max_green": 60,
            "final_green": 60,
            "split": "replay",
            "source": "phase12_replay",
            "violation_category": mod.VIOLATION_UNSATURATED_MAX_GREEN,
            "trivial_range": False,
        },
        {
            "origin_artifact": "dataset:labeled_merged.jsonl",
            "sample_id": "forced",
            "phase_id": "3",
            "pred_saturation": 0.0,
            "saturation_band": mod.BAND_NEAR_MIN,
            "min_green": 30,
            "max_green": 30,
            "final_green": 30,
            "split": "train",
            "source": "phase8-source",
            "violation_category": mod.VIOLATION_FORCED_TRIVIAL_RANGE,
            "trivial_range": True,
        },
    ]

    audit = mod.compute_saturation_audit(rows, example_limit=5, excluded_counts={"hard_constraint_invalid": 2})

    assert audit["requirements_covered"] == ["AUDIT-01", "AUDIT-02", "POLICY-01"]
    assert audit["total_rows"] == 3
    assert audit["included_rows"] == 2
    assert audit["trivial_rows"] == 1
    assert audit["excluded_counts"]["hard_constraint_invalid"] == 2
    near_min = audit["bands"][mod.BAND_NEAR_MIN]
    assert near_min["total_rows"] == 2
    assert near_min["trivial_rows"] == 1
    assert near_min["final_equals_max_when_unsaturated"] == {"count": 1, "denominator": 1, "rate": 1.0}
    assert audit["by_split"]["train"]["final_equals_max_when_unsaturated"] == {"count": 1, "denominator": 1, "rate": 1.0}
    assert audit["by_source"]["phase8-source"]["trivial_rows"] == 1
    assert audit["by_origin"]["dataset:labeled_merged.jsonl"]["trivial_rows"] == 1
    assert audit["by_origin"]["replay:phase12"]["final_equals_max_when_unsaturated"]["count"] == 1

    examples = audit["representative_examples"]
    assert [example["origin_artifact"] for example in examples] == ["dataset:labeled_merged.jsonl", "replay:phase12"]
    required = {
        "origin_artifact",
        "sample_id",
        "phase_id",
        "pred_saturation",
        "saturation_band",
        "min_green",
        "max_green",
        "final_green",
        "split",
        "source",
        "violation_category",
    }
    assert all(required <= set(example) for example in examples)
    assert all(example["violation_category"] == mod.VIOLATION_UNSATURATED_MAX_GREEN for example in examples)


def test_audit_fails_closed_on_missing_nonfinite_denominator_data() -> None:
    mod = _policy_contract()
    with pytest.raises(ValueError, match="finite"):
        mod.compute_saturation_audit([
            {
                "origin_artifact": "dataset:labeled_merged.jsonl",
                "sample_id": "bad",
                "phase_id": "1",
                "pred_saturation": float("nan"),
                "min_green": 10,
                "max_green": 50,
                "final_green": 50,
                "split": "train",
                "source": "phase8-source",
                "trivial_range": False,
            }
        ])

    with pytest.raises(ValueError, match="missing required audit row field"):
        mod.compute_saturation_audit([{"sample_id": "missing-fields"}])
