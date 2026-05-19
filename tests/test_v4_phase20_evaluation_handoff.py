from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
FORBIDDEN_IMPORT_ROOTS = {"torch", "transformers", "peft", "bitsandbytes", "vllm"}


def _mod():
    return importlib.import_module("tsc_cycle.v4_gates.phase20_eval")


def _input(sat: float = 0.1, *, max_green: int = 60) -> dict:
    return {
        "prediction": {
            "as_of": "2026-05-19T00:00:00Z",
            "phase_waits": [
                {"phase_id": 1, "pred_wait": 1.0, "pred_saturation": sat, "min_green": 20, "max_green": max_green, "capacity": 30},
                {"phase_id": 2, "pred_wait": 30.0, "pred_saturation": 1.1, "min_green": 25, "max_green": 70, "capacity": 30},
            ],
        }
    }


def _raw(solution: dict[str, int] | None = None, *, native_think: bool = False) -> str:
    if native_think:
        return '<think>bad</think><SOLUTION>{"1": 20, "2": 70}</SOLUTION>'
    solution = solution or {"1": 20, "2": 70}
    return (
        "<start_working_out>reasoning without native tags</end_working_out>"
        f"<SOLUTION>{json.dumps(solution)}</SOLUTION>"
    )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _phase19_ok(*args, **kwargs) -> dict:
    return {"ok": True, "next_phase_allowed": True, "requirements_covered": ["TRAIN-02"], "fatal_failures": []}


def test_phase20_eval_module_imports_no_heavy_model_stack() -> None:
    path = PROJECT_ROOT / "tsc_cycle" / "v4_gates" / "phase20_eval.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert not (imported_roots & FORBIDDEN_IMPORT_ROOTS)
    mod = _mod()
    for name in (
        "build_phase20_eval_prompts",
        "load_phase20_generated_outputs",
        "evaluate_phase20_outputs",
        "write_phase20_eval_report",
        "validate_phase20_eval_report",
        "main",
    ):
        assert hasattr(mod, name)


def test_build_phase20_eval_prompts_uses_calibrated_phase18_val_and_ood_split_rows(tmp_path: Path) -> None:
    mod = _mod()
    labeled = tmp_path / "data" / "v4_2" / "phase18" / "labeled_calibrated.jsonl"
    val_index = tmp_path / "data" / "v4_2" / "phase18" / "splits" / "val.index.jsonl"
    ood_index = tmp_path / "data" / "v4_2" / "phase18" / "splits" / "ood_val.index.jsonl"
    out = tmp_path / "artifacts" / "v4_2" / "phase20" / "eval_prompts.jsonl"
    manifest = tmp_path / "artifacts" / "v4_2" / "phase20" / "eval_prompt_manifest.json"

    _write_jsonl(labeled, [
        {"sample_id": "val-1", "input": _input(0.3), "result": {"solution": {"1": 30, "2": 70}}, "trivial": False},
        {"sample_id": "ood-1", "input": _input(0.8), "result": {"solution": {"1": 45, "2": 70}}, "trivial": False},
        {"sample_id": "train-1", "input": _input(0.1), "result": {"solution": {"1": 20, "2": 70}}, "trivial": False},
    ])
    _write_jsonl(val_index, [{"sample_id": "val-1"}])
    _write_jsonl(ood_index, [{"sample_id": "ood-1"}])

    rows = mod.build_phase20_eval_prompts(
        labeled_path=labeled,
        split_indexes=(val_index, ood_index),
        out_path=out,
        manifest_path=manifest,
    )

    assert out.exists()
    assert manifest.exists()
    assert [row["sample_id"] for row in rows] == ["val-1", "ood-1"]
    assert {row["slice_hint"] for row in rows} == {"val", "ood_val"}
    assert rows[0]["split_hint"] == "val"
    assert set(rows[0]) >= {"sample_id", "split_hint", "slice_hint", "input", "teacher_solution", "phase_count", "trivial"}
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["source_labeled_path"].endswith("data/v4_2/phase18/labeled_calibrated.jsonl")
    assert manifest_payload["slice_counts"] == {"ood_val": 1, "val": 1}


def test_load_phase20_generated_outputs_normalizes_cache_and_fails_closed_on_missing(tmp_path: Path) -> None:
    mod = _mod()
    prompts = tmp_path / "artifacts" / "v4_2" / "phase20" / "eval_prompts.jsonl"
    cache_dir = tmp_path / "artifacts" / "v4_2" / "phase20" / "gen_cache" / "v4_2_hf"
    outputs = tmp_path / "artifacts" / "v4_2" / "phase20" / "eval_outputs.jsonl"
    prompt_rows = [
        {"sample_id": "s1", "split_hint": "val", "slice_hint": "val", "input": _input(), "teacher_solution": {"1": 20, "2": 70}, "phase_count": 2, "trivial": False},
        {"sample_id": "s2", "split_hint": "ood_val", "slice_hint": "ood_val", "input": _input(0.9), "teacher_solution": {"1": 50, "2": 70}, "phase_count": 2, "trivial": False},
    ]
    _write_jsonl(prompts, prompt_rows)
    cache_dir.mkdir(parents=True)
    (cache_dir / "s1.json").write_text(json.dumps({"sample_id": "s1", "raw_text": _raw(), "solution": {"1": 20, "2": 70}, "parse_error": None}), encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        mod.load_phase20_generated_outputs(prompts_path=prompts, cache_dir=cache_dir, out_path=outputs)

    (cache_dir / "s2.json").write_text(json.dumps({"sample_id": "s2", "raw_text": _raw({"1": 50, "2": 70}), "solution": {"1": 50, "2": 70}, "parse_error": None}), encoding="utf-8")
    rows = mod.load_phase20_generated_outputs(prompts_path=prompts, cache_dir=cache_dir, out_path=outputs)

    assert outputs.exists()
    assert len(rows) == 2
    assert rows[0]["backend"] == "v4_2_hf"
    assert rows[0]["source_prompt"]["slice_hint"] == "val"
    assert rows[0]["solution"] == {"1": 20, "2": 70}
    assert rows[0]["raw_text"].startswith("<start_working_out>")


def test_phase20_report_requires_phase19_export_and_teacher_mae_is_advisory_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _mod()
    outputs = tmp_path / "artifacts" / "v4_2" / "phase20" / "eval_outputs.jsonl"
    report_path = tmp_path / "artifacts" / "v4_2" / "phase20" / "eval_report.json"
    row = {
        "sample_id": "s1",
        "split_hint": "val",
        "slice_hint": "val",
        "input": _input(),
        "teacher_solution": {"1": 40, "2": 70},
        "raw_text": _raw({"1": 20, "2": 70}),
        "solution": {"1": 20, "2": 70},
        "parse_error": None,
        "backend": "v4_2_hf",
        "phase_count": 2,
        "trivial": False,
    }
    _write_jsonl(outputs, [row])
    monkeypatch.setattr(mod, "validate_phase19_export_report", lambda *a, **k: {"ok": False, "next_phase_allowed": False, "requirements_covered": [], "fatal_failures": [{"gate": "phase19"}]})
    blocked = mod.evaluate_phase20_outputs(outputs_path=outputs, run_root=tmp_path / "runs" / "v4.2-4B-test", report_path=report_path)
    assert blocked["ok"] is False
    assert blocked["next_phase_allowed"] is False
    assert blocked["requirements_covered"] == []
    assert any(failure["gate"].startswith("phase19") for failure in blocked["fatal_failures"])

    monkeypatch.setattr(mod, "validate_phase19_export_report", _phase19_ok)
    report = mod.evaluate_phase20_outputs(outputs_path=outputs, run_root=tmp_path / "runs" / "v4.2-4B-test", report_path=report_path)
    assert report["ok"] is True
    assert report["next_phase_allowed"] is True
    assert report["requirements_covered"] == ["EVAL-01"]
    assert "teacher_mae" in report["advisory"]
    assert "decision_inputs" not in report or "teacher_mae" not in json.dumps(report.get("decision_inputs", {})).lower()
    assert "teacher_mae" not in json.dumps(report["gates"]).lower()
    written = mod.write_phase20_eval_report(report, report_path)
    assert written["ok"] is True
    assert mod.validate_phase20_eval_report(report_path=report_path, run_root=tmp_path / "runs" / "v4.2-4B-test")["ok"] is True


@pytest.mark.parametrize(
    "bad_row_update",
    [
        {"raw_text": _raw(native_think=True), "solution": {"1": 20, "2": 70}, "parse_error": None},
        {"raw_text": "not parseable", "solution": None, "parse_error": "solution_unparseable"},
        {"raw_text": _raw({"1": 999, "2": 70}), "solution": {"1": 999, "2": 70}, "parse_error": None},
        {"raw_text": _raw({"1": 60, "2": 70}), "solution": {"1": 60, "2": 70}, "parse_error": None},
    ],
)
def test_phase20_report_fails_closed_on_parse_lint_protocol_or_saturation_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_row_update: dict) -> None:
    mod = _mod()
    outputs = tmp_path / "artifacts" / "v4_2" / "phase20" / "eval_outputs.jsonl"
    row = {
        "sample_id": "s1",
        "split_hint": "val",
        "slice_hint": "val",
        "input": _input(0.1, max_green=60),
        "teacher_solution": {"1": 20, "2": 70},
        "raw_text": _raw({"1": 20, "2": 70}),
        "solution": {"1": 20, "2": 70},
        "parse_error": None,
        "backend": "v4_2_hf",
        "phase_count": 2,
        "trivial": False,
    }
    row.update(bad_row_update)
    _write_jsonl(outputs, [row])
    monkeypatch.setattr(mod, "validate_phase19_export_report", _phase19_ok)

    report = mod.evaluate_phase20_outputs(outputs_path=outputs, run_root=tmp_path / "runs" / "v4.2-4B-test")

    assert report["ok"] is False
    assert report["next_phase_allowed"] is False
    assert report["requirements_covered"] == []
    assert report["fatal_failures"]


def test_phase20_eval_launcher_contract_is_v42_dgx_safe() -> None:
    script = (PROJECT_ROOT / "scripts" / "run_v4_phase20_eval.sh").read_text(encoding="utf-8")
    assert "PROJECT_ROOT=/home/samuel/TSC_CYCLE" in script
    assert "PYTHON=/home/samuel/TSC_CYCLE/.venv/bin/python" in script
    assert "/home/samuel/TSC_CYCLE/runs/v4.2-4B-20260518T111519Z" in script
    assert "/home/samuel/TSC_CYCLE/runs/v4.2-4B-20260518T111519Z/merged_hf" in script
    assert "/home/samuel/TSC_CYCLE/artifacts/v4_2/phase20" in script
    assert "vllm" not in script.lower()
    assert "/home/samuel/TSC_CYCLE/scripts/dgx_spark/run_safe.sh 100G -- /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.eval.generate_hf" in script
    assert "--merged-hf /home/samuel/TSC_CYCLE/runs/v4.2-4B-20260518T111519Z/merged_hf" in script
    assert "--prompts /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/eval_prompts.jsonl" in script
    assert "--cache-dir /home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/gen_cache/v4_2_hf" in script
    assert "--n-predict 384" in script
    assert "build-prompts" in script
    assert "normalize-outputs" in script
    assert "evaluate" in script
    assert "artifacts/v4/phase11" not in script
    assert "phase12" not in script
    assert "runs/v4.0-4B-" in script
    assert "RUN_ROOT must match runs/v4.2-4B-*" in script
