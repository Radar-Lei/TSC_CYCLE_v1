from __future__ import annotations

import ast
import builtins
import hashlib
import importlib
import json
import math
import sys
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


def _audit_contract():
    return importlib.import_module("tsc_cycle.v4_gates.phase17_audit")


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


def test_representative_examples_keep_replay_when_dataset_exhausts_limit() -> None:
    mod = _policy_contract()
    rows = [
        {
            "origin_artifact": "dataset:labeled_merged.jsonl",
            "sample_id": f"sample-{idx:02d}",
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
        }
        for idx in range(20)
    ]
    rows.append({
        "origin_artifact": "replay:phase12",
        "sample_id": "reality-9999",
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
    })

    examples = mod.compute_saturation_audit(rows, example_limit=10)["representative_examples"]

    origins = [example["origin_artifact"] for example in examples]
    assert len(examples) == 10
    assert origins[:2] == ["dataset:labeled_merged.jsonl", "replay:phase12"]
    assert origins.count("replay:phase12") == 1


def test_audit_rejects_inconsistent_derived_fields() -> None:
    mod = _policy_contract()
    forged = _phase_row(sat=0.1, final_green=50, max_green=50)

    for field, bad_value in {
        "saturation_band": mod.BAND_ALLOWED_MAX,
        "trivial_range": True,
        "violation_category": mod.VIOLATION_NONE,
    }.items():
        row = dict(forged, **{field: bad_value})
        with pytest.raises(ValueError, match=f"inconsistent derived audit row field {field}"):
            mod.compute_saturation_audit([row])


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
            }
        ])

    with pytest.raises(ValueError, match="missing required audit row field"):
        mod.compute_saturation_audit([{"sample_id": "missing-fields"}])


def test_audit_and_eval_paths_reject_json_float_integer_fields(tmp_path: Path) -> None:
    mod = _policy_contract()
    audit_row = _phase_row()
    audit_row["final_green"] = 50.0
    with pytest.raises(ValueError, match="final_green must be an integer"):
        mod.compute_saturation_audit([audit_row])

    dataset = _dataset_row("float-final", {"1": 50.0, "2": 60})
    with pytest.raises(ValueError, match="final_green must be an integer"):
        mod.project_dataset_phase_decisions(_write_jsonl(tmp_path / "float_final.jsonl", [dataset]))


def test_build_parser_exposes_phase17_defaults() -> None:
    mod = _audit_contract()
    args = mod.build_parser().parse_args([])

    assert Path(args.dataset) == PROJECT_ROOT / "data" / "v4" / "phase8" / "labeled_merged.jsonl"
    assert Path(args.split_dir) == PROJECT_ROOT / "data" / "v4" / "phase8" / "splits"
    assert Path(args.phase12_manifest) == PROJECT_ROOT / "artifacts" / "v4" / "phase12" / "manifest.json"
    assert Path(args.phase12_per_sample) == PROJECT_ROOT / "artifacts" / "v4" / "phase12" / "per_sample.jsonl"
    assert Path(args.artifact_root) == PROJECT_ROOT / "artifacts" / "v4" / "phase17"
    assert args.out is None
    assert args.audit_out is None
    assert args.prompt_protocol_out is None


def test_phase17_report_paths_are_constrained_to_artifact_root(tmp_path: Path) -> None:
    mod = _audit_contract()
    allowed = mod.ARTIFACT_ROOT / "nested" / "report.json"
    assert mod.reject_unsafe_phase17_output_path(allowed) == allowed.resolve(strict=False)

    blocked_paths = [
        Path("/tmp/phase17-report.json"),
        PROJECT_ROOT / "runs" / "20260507T032419Z" / "report.json",
        mod.ARTIFACT_ROOT / ".." / "phase12" / "stolen.json",
        PROJECT_ROOT / "data" / "v4" / "phase8" / "labeled_merged.jsonl",
        PROJECT_ROOT / "tsc_cycle" / "prompt_builder.py",
        PROJECT_ROOT / "artifacts" / "v4" / "stolen.json",
    ]
    for blocked in blocked_paths:
        with pytest.raises(ValueError, match="Phase 17 report output path is not allowed"):
            mod.reject_unsafe_phase17_output_path(blocked)

    payload = {"ok": True, "value": 1.0}
    out_path = tmp_path / "artifacts" / "v4" / "phase17" / "safe.json"
    original_root = mod.ARTIFACT_ROOT
    try:
        mod.ARTIFACT_ROOT = tmp_path / "artifacts" / "v4" / "phase17"
        mod._write_json(out_path, payload)
        assert json.loads(out_path.read_text(encoding="utf-8")) == payload
        with pytest.raises(ValueError):
            mod._write_json(tmp_path / "outside.json", payload)
        with pytest.raises(ValueError, match="Out of range float values"):
            mod._write_json(out_path, {"bad": float("nan")})
    finally:
        mod.ARTIFACT_ROOT = original_root


def test_phase17_cli_artifact_root_derives_default_output_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mod = _audit_contract()
    seen: dict[str, object] = {}

    def fake_evaluate_phase17_audit(**kwargs):
        seen.update(kwargs)
        return {"ok": True, "next_phase_allowed": True, "fatal_failures": []}

    monkeypatch.setattr(mod, "evaluate_phase17_audit", fake_evaluate_phase17_audit)
    artifact_root = tmp_path / "artifacts" / "v4" / "phase17"
    original_root = mod.ARTIFACT_ROOT
    try:
        assert mod.main(["--artifact-root", str(artifact_root)]) == 0
    finally:
        mod.ARTIFACT_ROOT = original_root

    assert seen["out_path"] == artifact_root / "saturation_policy_gate.json"
    assert seen["audit_out_path"] == artifact_root / "saturation_audit_report.json"
    assert seen["prompt_protocol_out_path"] == artifact_root / "prompt_protocol_report.json"


@pytest.mark.parametrize(
    "root",
    [
        PROJECT_ROOT,
        PROJECT_ROOT / "data",
        PROJECT_ROOT / "tsc_cycle",
        PROJECT_ROOT / "artifacts",
        PROJECT_ROOT / "artifacts" / "v4",
        PROJECT_ROOT / "artifacts" / "v4" / "phase17" / "..",
    ],
)
def test_phase17_cli_rejects_broad_artifact_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    mod = _audit_contract()
    monkeypatch.setattr(mod, "evaluate_phase17_audit", lambda **kwargs: {"ok": True})
    original_root = mod.ARTIFACT_ROOT
    try:
        with pytest.raises(ValueError, match="Phase 17 artifact root is not allowed"):
            mod.main(["--artifact-root", str(root)])
    finally:
        mod.ARTIFACT_ROOT = original_root


def test_phase17_cli_exit_reflects_report_status(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    mod = _audit_contract()
    report = {"ok": False, "next_phase_allowed": False, "fatal_failures": [{"gate": "synthetic", "reason": "red"}]}
    monkeypatch.setattr(mod, "evaluate_phase17_audit", lambda **kwargs: report)

    exit_code = mod.main(["--out", str(mod.ARTIFACT_ROOT / "cli-red.json")])

    assert exit_code == 1
    assert '"ok": false' in capsys.readouterr().out

    report["ok"] = True
    report["next_phase_allowed"] = True
    report["fatal_failures"] = []
    assert mod.main(["--out", str(mod.ARTIFACT_ROOT / "cli-green.json")]) == 0


def _phase_row(sample_id: str = "eval-a", sat: float = 0.1, final_green: int = 50, max_green: int = 50) -> dict:
    mod = _policy_contract()
    row = {
        "origin_artifact": "eval:phase-decisions",
        "sample_id": sample_id,
        "phase_id": "1",
        "pred_saturation": sat,
        "min_green": 10,
        "max_green": max_green,
        "final_green": final_green,
        "split": "eval",
        "source": "phase11_eval",
        "source_origin": "phase11_eval",
    }
    row["saturation_band"] = mod.classify_saturation_band(sat)
    row["trivial_range"] = False
    row["violation_category"] = mod.classify_violation(row)
    return row


def test_default_thresholds_are_locked_and_sat_ge_1_has_no_max_failure_threshold() -> None:
    mod = _audit_contract()
    assert mod.DEFAULT_THRESHOLDS == {
        "sat_lt_0.2_max_green_rate": 0.0,
        "sat_0.2_0.6_max_green_rate": 0.02,
        "sat_0.6_1.0_max_green_rate": 0.10,
        "malformed_row_rate": 0.0,
        "missing_output_rate": 0.0,
    }
    assert "sat_ge_1.0_allowed_max" not in "\n".join(mod.DEFAULT_THRESHOLDS)


def test_policy_gate_fails_closed_on_missing_outputs() -> None:
    mod = _audit_contract()
    projection = {
        "ok": True,
        "input_count": 2,
        "rows": [_phase_row("complete", sat=0.3, final_green=20)],
        "excluded_counts": {"missing_solution_or_input": 1},
    }

    report = mod.evaluate_saturation_policy_gate(projection, source_type="data")

    assert report["ok"] is False
    assert report["gates"]["data_missing_output_rate"] == {
        "ok": False,
        "threshold": 0.0,
        "count": 1,
        "denominator": 2,
        "rate": 0.5,
    }
    assert report["gates"]["data_malformed_row_rate"] == {
        "ok": True,
        "threshold": 0.0,
        "count": 0,
        "denominator": 2,
        "rate": 0.0,
    }
    assert any(failure["gate"] == "data_threshold_excess_missing_output_rate" for failure in report["fatal_failures"])

    loosened = dict(mod.DEFAULT_THRESHOLDS, missing_output_rate=0.5)
    assert mod.evaluate_saturation_policy_gate(projection, thresholds=loosened, source_type="data")["ok"] is True


def test_policy_gate_fails_closed_on_malformed_rows() -> None:
    mod = _audit_contract()
    projection = {
        "ok": True,
        "input_count": 2,
        "rows": [_phase_row("valid", sat=0.3, final_green=20)],
        "excluded_counts": {"hard_constraint_invalid": 1},
    }

    report = mod.evaluate_saturation_policy_gate(projection, source_type="data")

    assert report["ok"] is False
    assert report["gates"]["data_malformed_row_rate"] == {
        "ok": False,
        "threshold": 0.0,
        "count": 1,
        "denominator": 2,
        "rate": 0.5,
    }
    assert report["gates"]["data_missing_output_rate"] == {
        "ok": True,
        "threshold": 0.0,
        "count": 0,
        "denominator": 2,
        "rate": 0.0,
    }
    assert any(failure["gate"] == "data_threshold_excess_malformed_row_rate" for failure in report["fatal_failures"])

    loosened = dict(mod.DEFAULT_THRESHOLDS, malformed_row_rate=0.5)
    assert mod.evaluate_saturation_policy_gate(projection, thresholds=loosened, source_type="data")["ok"] is True


def test_policy_gate_fails_closed_on_eval_style_threshold_excess() -> None:
    mod = _audit_contract()
    report = mod.evaluate_saturation_policy_gate([_phase_row()], source_type="eval")

    assert report["ok"] is False
    assert report["next_phase_allowed"] is False
    assert any("eval" in failure["gate"] and "threshold_excess" in failure["gate"] for failure in report["fatal_failures"])
    assert report["thresholds"] == mod.DEFAULT_THRESHOLDS

    loosened = dict(mod.DEFAULT_THRESHOLDS, **{"sat_lt_0.2_max_green_rate": 1.0})
    assert mod.evaluate_saturation_policy_gate([_phase_row()], thresholds=loosened, source_type="eval")["ok"] is True

    tightened = dict(mod.DEFAULT_THRESHOLDS, **{"sat_0.6_1.0_max_green_rate": 0.0})
    high_not_max = _phase_row("eval-b", sat=0.8, final_green=49)
    assert mod.evaluate_saturation_policy_gate([high_not_max], thresholds=tightened, source_type="eval")["ok"] is True
    high_max = _phase_row("eval-c", sat=0.8, final_green=50)
    assert mod.evaluate_saturation_policy_gate([high_max], thresholds=tightened, source_type="eval")["ok"] is False


def test_policy_gate_fails_closed_on_bad_denominators_and_malformed_rates() -> None:
    mod = _audit_contract()
    audit = _policy_contract().compute_saturation_audit([_phase_row("ok", sat=0.3, final_green=20)])
    del audit["bands"][_policy_contract().BAND_INTERPOLATED]["final_equals_max_when_unsaturated"]["denominator"]

    report = mod.evaluate_saturation_policy_gate(audit, source_type="data")

    assert report["ok"] is False
    assert any("denominator" in failure["gate"] for failure in report["fatal_failures"])


def test_evaluate_phase17_audit_routes_eval_jsonl_and_reports_failures(tmp_path: Path) -> None:
    mod = _audit_contract()
    missing_dataset = tmp_path / "missing.jsonl"
    manifest = tmp_path / "manifest.json"
    per_sample = tmp_path / "per_sample.jsonl"
    manifest.write_text(json.dumps({"records": []}), encoding="utf-8")
    per_sample.write_text("", encoding="utf-8")
    eval_rows = _write_jsonl(tmp_path / "eval.jsonl", [_phase_row()])
    artifact_root = tmp_path / "artifacts" / "v4" / "phase17"
    original_root = mod.ARTIFACT_ROOT
    try:
        mod.ARTIFACT_ROOT = artifact_root
        report = mod.evaluate_phase17_audit(
            dataset_path=missing_dataset,
            split_dir=tmp_path / "splits",
            phase12_manifest_path=manifest,
            phase12_per_sample_path=per_sample,
            phase_decisions_jsonl=eval_rows,
            out_path=artifact_root / "gate.json",
            audit_out_path=artifact_root / "audit.json",
            prompt_protocol_out_path=artifact_root / "prompt.json",
        )
    finally:
        mod.ARTIFACT_ROOT = original_root

    assert report["ok"] is False
    gates = {failure["gate"] for failure in report["fatal_failures"]}
    assert "dataset_audit" in gates
    assert any("eval_threshold_excess" in gate for gate in gates)
    assert report["reports"]["audit"].endswith("audit.json")
    assert report["reports"]["policy_gate"].endswith("gate.json")


def test_phase17_cli_threshold_override_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _audit_contract()
    seen: dict[str, object] = {}

    def fake_evaluate_phase17_audit(**kwargs):
        seen.update(kwargs)
        return {"ok": True, "next_phase_allowed": True, "fatal_failures": []}

    monkeypatch.setattr(mod, "evaluate_phase17_audit", fake_evaluate_phase17_audit)
    exit_code = mod.main([
        "--sat-lt-0-2-max-green-rate", "1.0",
        "--sat-0-2-0-6-max-green-rate", "0.5",
        "--sat-0-6-1-0-max-green-rate", "0.25",
        "--malformed-row-rate", "0.01",
        "--missing-output-rate", "0.02",
    ])

    assert exit_code == 0
    assert seen["thresholds"] == {
        "sat_lt_0.2_max_green_rate": 1.0,
        "sat_0.2_0.6_max_green_rate": 0.5,
        "sat_0.6_1.0_max_green_rate": 0.25,
        "malformed_row_rate": 0.01,
        "missing_output_rate": 0.02,
    }


def test_malformed_eval_output_jsonl_is_fatal(tmp_path: Path) -> None:
    mod = _audit_contract()
    bad = tmp_path / "bad_eval.jsonl"
    bad.write_text("not-json\n", encoding="utf-8")

    report = mod.evaluate_saturation_policy_gate(bad, source_type="eval")

    assert report["ok"] is False
    assert any(failure["gate"] == "eval_malformed_evidence" for failure in report["fatal_failures"])


def test_prompt_protocol_unchanged_and_no_band_rule() -> None:
    mod = _audit_contract()
    report = mod.evaluate_prompt_protocol_guard()

    fixture_path = PROJECT_ROOT / "tsc_cycle" / "v4_gates" / "fixtures" / "v4_prompt_protocol_golden.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert fixture["prompt_sha256"] == hashlib.sha256(fixture["prompt_text"].encode("utf-8")).hexdigest()
    assert fixture["prompt_text"] == mod.EXPECTED_V4_PROMPT

    assert report["ok"] is True
    assert report["prompt_text"] == mod.EXPECTED_V4_PROMPT
    assert report["prompt_sha256"] == mod.EXPECTED_V4_PROMPT_SHA256
    assert report["forbidden_snippets_present"] == []
    assert "POLICY-03" in report["requirements_covered"]
    scanned = {Path(item["path"]).name for item in report["scanned_prompt_surfaces"]}
    assert "prompt_builder.py" in scanned
    assert "phase12_reality_test.py" in scanned


def test_prompt_protocol_guard_fails_on_preimport_prompt_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    original = _audit_contract()
    prompt_builder = importlib.import_module("tsc_cycle.prompt_builder")
    drifted_prompt = original.EXPECTED_V4_PROMPT + "\nDRIFTED DEPLOYMENT PROMPT"

    monkeypatch.setattr(prompt_builder, "build_user_prompt", lambda prediction_input: drifted_prompt)
    sys.modules.pop("tsc_cycle.v4_gates.phase17_audit", None)
    try:
        drifted_mod = importlib.import_module("tsc_cycle.v4_gates.phase17_audit")
        report = drifted_mod.evaluate_prompt_protocol_guard()
    finally:
        sys.modules.pop("tsc_cycle.v4_gates.phase17_audit", None)

    assert drifted_mod.EXPECTED_V4_PROMPT == original.EXPECTED_V4_PROMPT
    assert report["ok"] is False
    assert report["prompt_text"] == drifted_prompt
    assert report["expected_prompt_sha256"] == original.EXPECTED_V4_PROMPT_SHA256
    assert any(failure["gate"] == "prompt_byte_for_byte" for failure in report["fatal_failures"])


@pytest.mark.parametrize(
    "leak",
    [
        "sat<0.2 must be near min",
        "pred_saturation < 0.2 must be near min",
        "0.2 ≤ saturation < 0.6 should interpolate",
        "0.6 ＜ pred_saturation ＜ 1.0 avoid max",
        "sat≥1.0 may use max green",
        "sat >= 1 may use max green",
        "saturation >= 1 may use max green",
        "pred_saturation >= 1 may use max green",
        "pred_saturation 小于 0.2 时接近最小绿灯",
        "饱和度低时接近最小绿灯，高时达到最大绿灯",
    ],
)
def test_prompt_protocol_guard_fails_on_simulated_policy_leakage(leak: str) -> None:
    mod = _audit_contract()
    leaked = mod.EXPECTED_V4_PROMPT + "\n" + leak
    report = mod.evaluate_prompt_protocol_guard(prompt_text=leaked, prompt_surfaces={"synthetic.py": leaked})

    assert report["ok"] is False
    assert report["forbidden_snippets_present"]
    assert any(failure["gate"] == "prompt_policy_leakage" for failure in report["fatal_failures"])


def test_prompt_protocol_guard_fails_on_scanned_surface_sat_ge_1_leakage() -> None:
    mod = _audit_contract()
    report = mod.evaluate_prompt_protocol_guard(
        prompt_text=mod.EXPECTED_V4_PROMPT,
        prompt_surfaces={"synthetic.py": "sat >= 1 may use max green"},
    )

    assert report["ok"] is False
    assert report["prompt_text"] == mod.EXPECTED_V4_PROMPT
    assert report["prompt_sha256"] == mod.EXPECTED_V4_PROMPT_SHA256
    assert report["forbidden_snippets_present"]
    assert any(failure["gate"] == "prompt_policy_leakage" for failure in report["fatal_failures"])



def test_integrated_report_includes_prompt_protocol_guard(tmp_path: Path) -> None:
    mod = _audit_contract()
    artifact_root = tmp_path / "artifacts" / "v4" / "phase17"
    manifest = tmp_path / "manifest.json"
    per_sample = tmp_path / "per_sample.jsonl"
    manifest.write_text(json.dumps({"records": []}), encoding="utf-8")
    per_sample.write_text("", encoding="utf-8")
    original_root = mod.ARTIFACT_ROOT
    try:
        mod.ARTIFACT_ROOT = artifact_root
        report = mod.evaluate_phase17_audit(
            dataset_path=tmp_path / "missing.jsonl",
            split_dir=tmp_path / "splits",
            phase12_manifest_path=manifest,
            phase12_per_sample_path=per_sample,
            out_path=artifact_root / "gate.json",
            audit_out_path=artifact_root / "audit.json",
            prompt_protocol_out_path=artifact_root / "prompt.json",
        )
    finally:
        mod.ARTIFACT_ROOT = original_root

    prompt_report = json.loads((artifact_root / "prompt.json").read_text(encoding="utf-8"))
    assert prompt_report["ok"] is True
    assert report["reports"]["prompt_protocol"].endswith("prompt.json")
    assert report["prompt_protocol"]["prompt_sha256"] == mod.EXPECTED_V4_PROMPT_SHA256
    assert not (PROJECT_ROOT / "tsc_cycle" / "prompt_builder.py").read_text(encoding="utf-8").count("sat < 0.2")
