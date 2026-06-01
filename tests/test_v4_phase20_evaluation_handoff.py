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


def test_load_phase20_generated_outputs_repairs_single_bound_drift(tmp_path: Path) -> None:
    mod = _mod()
    prompts = tmp_path / "artifacts" / "v4_2" / "phase20" / "eval_prompts.jsonl"
    cache_dir = tmp_path / "artifacts" / "v4_2" / "phase20" / "gen_cache" / "v4_2_hf"
    outputs = tmp_path / "artifacts" / "v4_2" / "phase20" / "eval_outputs.jsonl"
    prompt_rows = [
        {"sample_id": "s1", "split_hint": "ood_val", "slice_hint": "ood_val", "input": _input(0.3, max_green=57), "teacher_solution": {"1": 57, "2": 70}, "phase_count": 2, "trivial": False},
    ]
    prompt_rows[0]["input"]["prediction"]["phase_waits"][0]["min_green"] = 57
    _write_jsonl(prompts, prompt_rows)
    cache_dir.mkdir(parents=True)
    (cache_dir / "s1.json").write_text(json.dumps({"sample_id": "s1", "raw_text": _raw({"1": 59, "2": 70}), "solution": {"1": 59, "2": 70}, "parse_error": None}), encoding="utf-8")

    rows = mod.load_phase20_generated_outputs(prompts_path=prompts, cache_dir=cache_dir, out_path=outputs)

    assert rows[0]["solution"] == {"1": 57, "2": 70}
    assert rows[0]["normalization_repair"]["kind"] == "hard_bound_clamp"
    assert rows[0]["normalization_repair"]["changes"] == [{"phase": "1", "from": 59, "to": 57, "min": 57, "max": 57}]
    assert '"1": 59' in rows[0]["raw_text"]


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
    assert report["advisory"]["normalization_repairs"] == 0
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
    script_path = PROJECT_ROOT / "scripts" / "run_v4_phase20_eval.sh"
    if not script_path.exists():
        pytest.skip("launcher is added by Task 20-01-02")
    script = script_path.read_text(encoding="utf-8")
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


def test_phase20_replay_renderer_rejects_protocol_lint_or_saturation_failure() -> None:
    mod = importlib.import_module("tsc_cycle.v4_gates.phase20_log_render")
    record = {"sample_id": "r1", "crossing_id": "c1", "timestamp": "2026-05-19 00:00:00", "input": _input(0.1, max_green=60), "input_sha256": "abc"}
    ok_output = {"sample_id": "r1", "input_sha256": "abc", "raw_text": _raw({"1": 20, "2": 70}), "backend": "tsc-cycle-v4.2-q4_K_M"}
    mod.ensure_phase20_output_passes(record, ok_output)
    rendered = mod.render_phase20_reality_test_log([record], [ok_output])
    assert "tsc-cycle-v4.2-q4_K_M" in rendered
    assert "【cycle_predict_input_json】" in rendered
    assert "sat_lt_0.2" not in rendered

    for bad_output in (
        {**ok_output, "sample_id": "other"},
        {**ok_output, "input_sha256": "wrong"},
        {**ok_output, "raw_text": _raw(native_think=True)},
        {**ok_output, "raw_text": _raw({"1": 999, "2": 70})},
        {**ok_output, "raw_text": _raw({"1": 60, "2": 70})},
    ):
        with pytest.raises(ValueError):
            mod.ensure_phase20_output_passes(record, bad_output)


def test_phase20_reality_report_requires_full_non_dry_run_and_preflights(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = importlib.import_module("tsc_cycle.v4_gates.phase20_reality_test")
    monkeypatch.setattr(mod, "validate_phase19_export_report", _phase19_ok)
    monkeypatch.setattr(mod, "validate_phase20_eval_report", lambda *a, **k: {"ok": True, "next_phase_allowed": True, "requirements_covered": ["EVAL-01"], "fatal_failures": []})
    model = tmp_path / "runs" / "v4.2-4B-test" / "gguf" / "model.q4_K_M.gguf"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"model")
    final_log = tmp_path / "artifacts" / "v4_2" / "phase20" / "reality_test.log"
    report_path = tmp_path / "artifacts" / "v4_2" / "phase20" / "reality_replay_report.json"
    record = {"sample_id": "r1", "crossing_id": "c1", "timestamp": "2026-05-19 00:00:00", "input": _input(0.1), "input_sha256": "abc"}
    output = {"sample_id": "r1", "input_sha256": "abc", "raw_text": _raw({"1": 20, "2": 70}), "backend": "tsc-cycle-v4.2-q4_K_M", "timeout": False}

    dry = mod.evaluate_phase20_replay_report(records=[record], outputs=[output], model_artifact=model, model_sha256=mod.sha256_file(model), input_sha256="input", output_sha256="output", final_log_path=final_log, report_path=report_path, dry_run=True)
    assert dry["ok"] is False
    assert "EVAL-02" not in dry["requirements_covered"]

    limited = mod.evaluate_phase20_replay_report(records=[record], outputs=[output], model_artifact=model, model_sha256=mod.sha256_file(model), input_sha256="input", output_sha256="output", final_log_path=final_log, report_path=report_path, dry_run=False, limit=1, total_input_count=2)
    assert limited["ok"] is False
    assert "EVAL-02" not in limited["requirements_covered"]

    text = importlib.import_module("tsc_cycle.v4_gates.phase20_log_render").render_phase20_reality_test_log([record], [output])
    final_log.parent.mkdir(parents=True, exist_ok=True)
    final_log.write_text(text, encoding="utf-8")
    accepted = mod.evaluate_phase20_replay_report(records=[record], outputs=[output], model_artifact=model, model_sha256=mod.sha256_file(model), input_sha256="input", output_sha256=mod.sha256_text(text), final_log_path=final_log, report_path=report_path, dry_run=False)
    assert accepted["ok"] is True
    assert accepted["requirements_covered"] == ["EVAL-02"]

    monkeypatch.setattr(mod, "validate_phase20_eval_report", lambda *a, **k: {"ok": False, "next_phase_allowed": False, "requirements_covered": [], "fatal_failures": [{"gate": "eval"}]})
    blocked = mod.evaluate_phase20_replay_report(records=[record], outputs=[output], model_artifact=model, model_sha256=mod.sha256_file(model), input_sha256="input", output_sha256=mod.sha256_text(text), final_log_path=final_log, report_path=report_path, dry_run=False)
    assert blocked["ok"] is False
    assert any(failure["gate"].startswith("phase20_eval") for failure in blocked["fatal_failures"])


def test_phase20_reality_module_imports_no_heavy_stack_and_lazy_gguf_helpers() -> None:
    path = PROJECT_ROOT / "tsc_cycle" / "v4_gates" / "phase20_reality_test.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert not (imported_roots & FORBIDDEN_IMPORT_ROOTS)
    assert "from tsc_cycle.student.parity_gguf import" in source
    assert "def _run_live" in source
    assert source.index("def _run_live") < source.index("from tsc_cycle.student.parity_gguf import")
    mod = importlib.import_module("tsc_cycle.v4_gates.phase20_reality_test")
    for name in ("extract_reality_inputs", "run_phase20_reality_replay", "validate_phase20_replay_report", "main"):
        assert hasattr(mod, name)


def test_phase20_reality_launcher_contract_is_v42_dgx_safe() -> None:
    script_path = PROJECT_ROOT / "scripts" / "run_v4_phase20_reality_test.sh"
    if not script_path.exists():
        pytest.skip("launcher is added by Task 20-02-02")
    script = script_path.read_text(encoding="utf-8")
    assert "/home/samuel/TSC_CYCLE/runs/v4.2-4B-20260518T111519Z/gguf/model.q4_K_M.gguf" in script
    assert "/home/samuel/TSC_CYCLE/artifacts/v4_2/phase20" in script
    assert "/home/samuel/TSC_CYCLE/artifacts/v4_2/phase20/reality_test.log" in script
    assert "/home/samuel/llama.cpp/build/bin/llama-server" in script
    assert "--resume" in script
    assert "--n-predict 384" in script
    assert "--retry-n-predict 768" in script
    assert "--timeout-sec 600" in script
    assert "--ngl 99" in script
    assert "--threads 4" in script
    assert "--ctx-size 4096" in script
    assert "tsc-cycle-v4.2-q4_K_M" in script
    assert "vllm" not in script.lower()
    assert "/home/samuel/TSC_CYCLE/reality_test.log" not in script
    assert "artifacts/v4/phase12" not in script
    assert "runs/v4.0-4B-" not in script


def _phase_row(sample_id: str, phase_id: str, *, final_green: int, hard_ok: bool = True, sat: float = 0.1, max_green: int = 60) -> dict:
    violation = "final_equals_max_when_unsaturated" if final_green == max_green and sat < 1.0 else "none"
    return {
        "sample_id": sample_id,
        "phase_id": phase_id,
        "pred_saturation": sat,
        "min_green": 20,
        "max_green": max_green,
        "final_green": final_green,
        "split": "replay",
        "source": "fixture",
        "origin_artifact": "fixture",
        "hard_constraint_ok": hard_ok,
        "violation_category": violation,
    }


def test_phase20_comparison_gate_blocks_hard_regression_or_unreduced_saturation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = importlib.import_module("tsc_cycle.v4_gates.phase20_comparison")
    monkeypatch.setattr(mod, "validate_phase20_eval_report", lambda *a, **k: {"ok": True, "next_phase_allowed": True, "requirements_covered": ["EVAL-01"], "fatal_failures": []})
    monkeypatch.setattr(mod, "validate_phase20_replay_report", lambda *a, **k: {"ok": True, "next_phase_allowed": True, "requirements_covered": ["EVAL-02"], "fatal_failures": []})
    baseline = [_phase_row("s1", "1", final_green=60), _phase_row("s2", "1", final_green=60)]
    improved = [_phase_row("s1", "1", final_green=20), _phase_row("s2", "1", final_green=20)]
    report_path = tmp_path / "artifacts" / "v4_2" / "phase20" / "comparison_report.json"

    report = mod.compare_v4_v42_outputs(baseline_rows=baseline, v42_rows=improved, report_path=report_path)
    assert report["ok"] is True
    assert report["requirements_covered"] == ["EVAL-03"]
    assert "teacher_mae" not in json.dumps(report.get("decision_inputs", {})).lower()

    hard_regression = mod.compare_v4_v42_outputs(baseline_rows=baseline, v42_rows=[{**improved[0], "hard_constraint_ok": False}, improved[1]], report_path=report_path)
    assert hard_regression["ok"] is False
    assert hard_regression["requirements_covered"] == []
    assert any(failure["gate"] == "hard_constraint_regression" for failure in hard_regression["fatal_failures"])

    unchanged = mod.compare_v4_v42_outputs(baseline_rows=baseline, v42_rows=baseline, report_path=report_path)
    assert unchanged["ok"] is False
    assert any(failure["gate"] == "saturation_not_reduced" for failure in unchanged["fatal_failures"])

    monkeypatch.setattr(mod, "validate_phase20_eval_report", lambda *a, **k: {"ok": False, "next_phase_allowed": False, "requirements_covered": [], "fatal_failures": [{"gate": "eval"}]})
    blocked = mod.compare_v4_v42_outputs(baseline_rows=baseline, v42_rows=improved, report_path=report_path)
    assert blocked["ok"] is False
    assert any(failure["gate"] == "phase20_eval" for failure in blocked["fatal_failures"])


def test_phase20_handoff_recomputes_hashes_and_requires_green_gates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mod = importlib.import_module("tsc_cycle.v4_gates.phase20_handoff")
    monkeypatch.setattr(mod, "validate_phase20_eval_report", lambda *a, **k: {"ok": True, "next_phase_allowed": True, "requirements_covered": ["EVAL-01"], "fatal_failures": []})
    monkeypatch.setattr(mod, "validate_phase20_replay_report", lambda *a, **k: {"ok": True, "next_phase_allowed": True, "requirements_covered": ["EVAL-02"], "fatal_failures": []})
    monkeypatch.setattr(mod, "validate_phase20_comparison_report", lambda *a, **k: {"ok": True, "next_phase_allowed": True, "requirements_covered": ["EVAL-03"], "fatal_failures": []})
    run_root = tmp_path / "runs" / "v4.2-4B-test"
    artifact_root = tmp_path / "artifacts" / "v4_2" / "phase20"
    paths = {
        "training_report": run_root / "phase19_sft_report.json",
        "export_report": run_root / "phase19_export_report.json",
        "q4_gguf": run_root / "gguf" / "model.q4_K_M.gguf",
        "eval_report": artifact_root / "eval_report.json",
        "replay_log": artifact_root / "reality_test.log",
        "replay_report": artifact_root / "reality_replay_report.json",
        "comparison_report": artifact_root / "comparison_report.json",
    }
    for name, path in paths.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"name": name, "ok": True}), encoding="utf-8")
    manifest_path = artifact_root / "handoff_manifest.json"

    manifest = mod.write_phase20_handoff(run_root=run_root, artifact_root=artifact_root, manifest_path=manifest_path)
    assert manifest["ok"] is True
    assert manifest["requirements_covered"] == ["EVAL-01", "EVAL-02", "EVAL-03"]
    assert manifest["artifacts"]["q4_gguf"]["sha256"] == mod.sha256_file(paths["q4_gguf"])
    assert manifest_path.exists()
    validated = mod.validate_phase20_handoff(manifest_path=manifest_path, run_root=run_root, artifact_root=artifact_root)
    assert validated["ok"] is True

    paths["eval_report"].unlink()
    failed = mod.validate_phase20_handoff(manifest_path=manifest_path, run_root=run_root, artifact_root=artifact_root)
    assert failed["ok"] is False
    assert failed["requirements_covered"] == []

    paths["eval_report"].write_text("{}", encoding="utf-8")
    bad_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad_manifest["artifacts"]["q4_gguf"]["path"] = str(tmp_path / "runs" / "v4.0-4B-bad" / "gguf" / "model.q4_K_M.gguf")
    manifest_path.write_text(json.dumps(bad_manifest), encoding="utf-8")
    rejected = mod.validate_phase20_handoff(manifest_path=manifest_path, run_root=run_root, artifact_root=artifact_root)
    assert rejected["ok"] is False
    assert any(failure["gate"] == "artifact_scope" for failure in rejected["fatal_failures"])


def test_phase20_comparison_and_handoff_imports_are_lightweight() -> None:
    for rel, names in {
        "tsc_cycle/v4_gates/phase20_comparison.py": ("compare_v4_v42_outputs", "write_phase20_comparison_report", "validate_phase20_comparison_report", "main"),
        "tsc_cycle/v4_gates/phase20_handoff.py": ("write_phase20_handoff", "validate_phase20_handoff", "main"),
    }.items():
        path = PROJECT_ROOT / rel
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])
        assert not (imported_roots & FORBIDDEN_IMPORT_ROOTS)
        mod = importlib.import_module(rel.removesuffix(".py").replace("/", "."))
        for name in names:
            assert hasattr(mod, name)
