from __future__ import annotations

import ast
import builtins
import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

import pytest

from tsc_cycle.constraint_lint import validate
from tsc_cycle.prompt_builder import parse_assistant_output

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
REALITY_LOG = PROJECT_ROOT / "reality.log"
REALITY_TEST_LOG = PROJECT_ROOT / "reality_test.log"
PHASE12_ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4" / "phase12"
APPROVED_Q4_MODEL = PROJECT_ROOT / "runs" / "v4.0-4B-20260509T184844Z" / "gguf" / "model.q4_K_M.gguf"
FROZEN_V1_ROOT = PROJECT_ROOT / "runs" / "20260507T032419Z"
FROZEN_V1_Q4_MODEL = FROZEN_V1_ROOT / "gguf" / "model.q4_K_M.gguf"
FORBIDDEN_COLLECTION_IMPORTS = {"torch", "transformers", "peft", "bitsandbytes", "vllm", "flash_attn"}


@pytest.fixture(autouse=True)
def _phase12_modules_are_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 12 contracts must never load model/GPU stacks during test execution."""
    real_import = importlib.import_module

    def guarded_import(name: str, package: str | None = None):
        root = name.split(".", 1)[0]
        if root in FORBIDDEN_COLLECTION_IMPORTS:
            raise AssertionError(f"Phase 12 contract imported heavyweight dependency during test execution: {name}")
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", guarded_import)


def _phase12_reality_contract():
    return importlib.import_module("tsc_cycle.v4_gates.phase12_reality_test")


def _phase12_report_contract():
    return importlib.import_module("tsc_cycle.v4_gates.phase12_report")


def _compact_reality_log() -> str:
    return """2026-04-27 00:02:25|INFO|type=result|engine=lmstudio|crossing_id=0
RAW:
<start_working_out>stale reasoning</end_working_out><SOLUTION>{"1":999}</SOLUTION>
REASONING:
stale result must not be parsed as input
PARSED:
{"1": 999}
--------------------------------------------------------------------------------
2026-04-27 00:02:27|INFO|type=prompt|crossing_id=1

你是交通信号配时优化专家。
【cycle_predict_input_json】{
  "prediction": {
    "as_of": "2026-04-27 00:02:27",
    "phase_waits": [
      {"phase_id": 1, "pred_wait": 0.4, "pred_saturation": 0.0083, "min_green": 50, "max_green": 80, "capacity": 48},
      {"phase_id": 2, "pred_wait": 1.0, "pred_saturation": 0.025, "min_green": 20, "max_green": 45, "capacity": 40}
    ]
  }
}【/cycle_predict_input_json】
--------------------------------------------------------------------------------
2026-04-27 00:02:33|INFO|type=result|engine=lmstudio|crossing_id=1
RAW:
<SOLUTION>{"1":50,"2":20}</SOLUTION>
REASONING:
old split reasoning must be ignored
PARSED:
{"1": 50, "2": 20}
--------------------------------------------------------------------------------
2026-04-27 00:03:27|INFO|type=prompt|crossing_id=2

【cycle_predict_input_json】{
  "prediction": {
    "as_of": "2026-04-27 00:03:27",
    "phase_waits": [
      {"phase_id": 3, "pred_wait": 4.0, "pred_saturation": 0.3, "min_green": 25, "max_green": 60, "capacity": 42}
    ]
  }
}【/cycle_predict_input_json】
--------------------------------------------------------------------------------
RAW:
this trailing RAW/PARSED noise is outside any prompt and must not be used
PARSED:
{"3": 60}
"""


def _record(sample_id: str = "reality-0001") -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "crossing_id": "1",
        "timestamp": "2026-04-27 00:02:27",
        "input_sha256": "input-hash-1",
        "input": {
            "prediction": {
                "as_of": "2026-04-27 00:02:27",
                "phase_waits": [
                    {"phase_id": 1, "pred_wait": 0.4, "pred_saturation": 0.0083, "min_green": 50, "max_green": 80, "capacity": 48},
                    {"phase_id": 2, "pred_wait": 1.0, "pred_saturation": 0.025, "min_green": 20, "max_green": 45, "capacity": 40},
                ],
            }
        },
    }


def _good_output(sample_id: str = "reality-0001") -> dict[str, Any]:
    raw = "<start_working_out>先检查相位顺序、上下界和整数秒，再按等待压力分配。</end_working_out><SOLUTION>{\"1\":60,\"2\":30}</SOLUTION>"
    reasoning, solution = parse_assistant_output(raw)
    assert reasoning
    assert solution == {"1": 60, "2": 30}
    lint = validate(_record(sample_id)["input"], solution)
    assert lint.ok
    return {
        "sample_id": sample_id,
        "raw_text": raw,
        "reasoning": reasoning,
        "solution": solution,
        "parse_error": None,
        "lint_ok": True,
        "lint": {"ok": True, "violations": []},
    }


def test_phase12_contracts_do_not_import_heavy_model_stacks_at_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    module_paths = [
        PROJECT_ROOT / "tsc_cycle" / "v4_gates" / "phase12_reality_test.py",
        PROJECT_ROOT / "tsc_cycle" / "v4_gates" / "phase12_report.py",
    ]
    for module_path in module_paths:
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0])

        assert imported_roots.isdisjoint(FORBIDDEN_COLLECTION_IMPORTS), (
            f"{module_path} must use lazy imports and must not import torch/transformers/peft/"
            "bitsandbytes/vllm/flash_attn during collection"
        )

    real_import = builtins.__import__

    def guarded_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        root = name.split(".", 1)[0]
        if root in FORBIDDEN_COLLECTION_IMPORTS:
            raise AssertionError(f"Phase 12 implementation imported heavyweight dependency during module import: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    importlib.import_module("tsc_cycle.v4_gates.phase12_reality_test")
    importlib.import_module("tsc_cycle.v4_gates.phase12_report")


def test_extract_reality_inputs_uses_only_prompt_framed_json(tmp_path: Path) -> None:
    mod = _phase12_reality_contract()
    log_path = tmp_path / "reality.log"
    log_path.write_text(_compact_reality_log(), encoding="utf-8")

    records = mod.extract_reality_inputs(log_path)

    assert len(records) == 2
    first = records[0] if isinstance(records[0], dict) else records[0].__dict__
    second = records[1] if isinstance(records[1], dict) else records[1].__dict__
    assert first["input"]["prediction"]["phase_waits"][0]["phase_id"] == 1
    assert second["input"]["prediction"]["phase_waits"][0]["phase_id"] == 3
    payload_joined = json.dumps([first["input"], second["input"]], ensure_ascii=False, sort_keys=True)
    assert "999" not in payload_joined
    assert "stale" not in payload_joined
    assert "RAW:" not in payload_joined
    assert "REASONING:" not in payload_joined
    assert "PARSED:" not in payload_joined
    assert first["input_sha256"] != second["input_sha256"]
    assert first["input_sha256"] == hashlib.sha256(
        json.dumps(first["input"], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def test_production_reality_log_has_426_unique_inputs_when_present() -> None:
    if not REALITY_LOG.exists():
        pytest.skip(f"reality.log not present: {REALITY_LOG}")
    mod = _phase12_reality_contract()

    records = mod.extract_reality_inputs(REALITY_LOG)
    hashes = [(record["input_sha256"] if isinstance(record, dict) else record.input_sha256) for record in records]

    assert len(records) == 426
    assert len(set(hashes)) == 426


def test_default_model_artifact_is_phase11_recommended_v4_q4_not_frozen_v1() -> None:
    mod = _phase12_reality_contract()

    selected = Path(mod.default_model_artifact())

    assert selected == APPROVED_Q4_MODEL
    assert selected != FROZEN_V1_Q4_MODEL
    assert "v4.0-4B-20260509T184844Z" in str(selected)
    assert "20260507T032419Z" not in str(selected)


def test_path_safety_allows_only_phase12_outputs_and_rejects_frozen_or_unrelated_paths(tmp_path: Path) -> None:
    mod = _phase12_reality_contract()
    allowed_paths = [
        REALITY_TEST_LOG,
        Path(str(REALITY_TEST_LOG) + ".tmp"),
        PHASE12_ARTIFACT_ROOT / "manifest.json",
        PHASE12_ARTIFACT_ROOT / "gen_cache" / "reality-0001.json",
    ]
    for path in allowed_paths:
        accepted = mod.reject_unsafe_phase12_output_path(path)
        assert accepted in {None, str(path), path}

    rejected_paths = [
        FROZEN_V1_ROOT,
        FROZEN_V1_ROOT / "eval" / "phase12_report.json",
        PROJECT_ROOT / "runs" / "20260507T032419Z" / "reality_test.log",
        PROJECT_ROOT / "reality.log",
        tmp_path / "reality_test.log",
        Path("/tmp/reality_test.log"),
    ]
    for path in rejected_paths:
        with pytest.raises((AssertionError, ValueError, RuntimeError), match="Phase 12|phase12|frozen|reality_test|allowed|refus"):
            mod.reject_unsafe_phase12_output_path(path)


def test_render_reality_test_log_preserves_full_custom_raw_protocol() -> None:
    mod = _phase12_reality_contract()
    record = _record()
    output = _good_output()

    rendered = mod.render_reality_test_log([record], [output])

    assert "type=prompt" in rendered
    assert "type=result" in rendered
    assert "engine=tsc-cycle-v4-q4_K_M" in rendered
    assert "RAW:" in rendered
    assert "<start_working_out>" in rendered
    assert "</end_working_out>" in rendered
    assert "<SOLUTION>" in rendered and "</SOLUTION>" in rendered
    assert "PARSED:" in rendered
    assert '"1": 60' in rendered or '"1":60' in rendered
    assert "LINT:" in rendered
    assert '"ok": true' in rendered.lower()
    assert "<think>" not in rendered
    assert "</think>" not in rendered
    assert "<end_working_out>" not in rendered


def test_render_rejects_native_think_and_malformed_close_tags() -> None:
    mod = _phase12_reality_contract()
    bad_outputs = [
        {**_good_output(), "raw_text": "<think>x</think><SOLUTION>{\"1\":60,\"2\":30}</SOLUTION>"},
        {**_good_output(), "raw_text": "<start_working_out>x<end_working_out><SOLUTION>{\"1\":60,\"2\":30}</SOLUTION>"},
    ]

    for output in bad_outputs:
        reasoning, solution = parse_assistant_output(output["raw_text"])
        assert reasoning == ""
        assert solution is None
        with pytest.raises((AssertionError, ValueError, RuntimeError), match="think|protocol|parse|malformed"):
            mod.render_reality_test_log([_record()], [output])


def test_report_evaluation_fails_closed_on_parse_lint_count_or_hash_failures(tmp_path: Path) -> None:
    mod = _phase12_report_contract()
    final_log = tmp_path / "reality_test.log"
    final_log.write_text("audited final log\n", encoding="utf-8")
    model_artifact = tmp_path / "model.q4_K_M.gguf"
    model_artifact.write_bytes(b"fake model artifact")
    base_kwargs = {
        "records": [_record("reality-0001")],
        "outputs": [_good_output("reality-0001")],
        "model_artifact": model_artifact,
        "model_sha256": hashlib.sha256(b"fake model artifact").hexdigest(),
        "input_sha256": "input-log-hash",
        "output_sha256": hashlib.sha256(b"audited final log\n").hexdigest(),
        "out_path": None,
        "final_log_path": final_log,
    }

    passing = mod.evaluate_phase12_report(**base_kwargs)
    assert passing["ok"] is True
    assert passing["next_phase_allowed"] is True
    assert passing["input_count"] == 1
    assert passing["parse_ok_count"] == 1
    assert passing["lint_ok_count"] == 1
    assert passing["model_artifact"] == str(model_artifact.resolve(strict=False))
    for key in ("input_sha256", "output_sha256"):
        assert passing[key]

    failing_cases = {
        "parse_error": {**base_kwargs, "outputs": [{**_good_output(), "raw_text": "malformed output", "parse_error": None, "solution": {"1": 60, "2": 30}}]},
        "lint_false": {
            **base_kwargs,
            "outputs": [
                {
                    **_good_output(),
                    "raw_text": "<start_working_out>越界输出。</end_working_out><SOLUTION>{\"1\":999,\"2\":20}</SOLUTION>",
                    "lint_ok": True,
                    "lint": {"ok": True, "violations": []},
                }
            ],
        },
        "missing_reasoning": {**base_kwargs, "outputs": [{**_good_output(), "raw_text": "<start_working_out></end_working_out><SOLUTION>{\"1\":60,\"2\":30}</SOLUTION>"}]},
        "wrong_input_count": {**base_kwargs, "records": [_record("reality-0001"), _record("reality-0002")]},
        "missing_artifact_hash": {**base_kwargs, "model_sha256": ""},
        "missing_final_log": {**base_kwargs, "final_log_path": tmp_path / "missing_reality_test.log"},
        "bad_output_hash": {**base_kwargs, "output_sha256": hashlib.sha256(b"stale\n").hexdigest()},
        "bad_model_hash": {**base_kwargs, "model_sha256": hashlib.sha256(b"stale model").hexdigest()},
    }
    for name, kwargs in failing_cases.items():
        report = mod.evaluate_phase12_report(**kwargs)
        assert report["ok"] is False, name
        assert report["next_phase_allowed"] is False, name
        assert report["fatal_failures"], name


def test_report_payload_contains_phase12_audit_fields(tmp_path: Path) -> None:
    mod = _phase12_report_contract()
    final_log = tmp_path / "reality_test.log"
    final_log.write_text("audited final log\n", encoding="utf-8")
    model_artifact = tmp_path / "model.q4_K_M.gguf"
    model_artifact.write_bytes(b"fake model artifact")

    report = mod.evaluate_phase12_report(
        records=[_record()],
        outputs=[_good_output()],
        model_artifact=model_artifact,
        model_sha256=hashlib.sha256(b"fake model artifact").hexdigest(),
        input_sha256="input-log-hash",
        output_sha256=hashlib.sha256(b"audited final log\n").hexdigest(),
        out_path=None,
        final_log_path=final_log,
    )

    assert set(report) >= {
        "ok",
        "next_phase_allowed",
        "input_count",
        "parse_ok_count",
        "lint_ok_count",
        "model_artifact",
        "input_sha256",
        "output_sha256",
    }
    assert "reports" in report
    assert "requirements_covered" in report


def test_report_out_path_allows_only_phase12_artifact_paths(tmp_path: Path) -> None:
    mod = _phase12_report_contract()
    final_log = tmp_path / "reality_test.log"
    final_log.write_text("audited final log\n", encoding="utf-8")
    model_artifact = tmp_path / "model.q4_K_M.gguf"
    model_artifact.write_bytes(b"fake model artifact")
    kwargs = {
        "records": [_record()],
        "outputs": [_good_output()],
        "model_artifact": model_artifact,
        "model_sha256": hashlib.sha256(b"fake model artifact").hexdigest(),
        "input_sha256": "input-log-hash",
        "output_sha256": hashlib.sha256(b"audited final log\n").hexdigest(),
        "final_log_path": final_log,
    }

    allowed = PHASE12_ARTIFACT_ROOT / "test_phase12_path_safety_report.json"
    mod.evaluate_phase12_report(**kwargs, out_path=allowed)
    assert allowed.exists()
    allowed.unlink()

    with pytest.raises((AssertionError, ValueError, RuntimeError), match="Phase 12|phase12|allowed|refus"):
        mod.evaluate_phase12_report(**kwargs, out_path=tmp_path / "phase12_report.json")


def test_final_log_is_not_written_when_any_gate_fails(tmp_path: Path) -> None:
    mod = _phase12_reality_contract()
    final_log = tmp_path / "reality_test.log"
    tmp_log = tmp_path / "reality_test.log.tmp"
    failed_outputs = [{**_good_output(), "raw_text": "malformed output", "parse_error": None, "solution": {"1": 60, "2": 30}}]

    with pytest.raises((AssertionError, ValueError, RuntimeError), match="parse|lint|gate|fail"):
        mod.write_final_log_atomically(
            text="partial content must not become final\n",
            out_log=final_log,
            records=[_record()],
            outputs=failed_outputs,
            allow_test_path=True,
        )

    assert not final_log.exists()
    if tmp_log.exists():
        assert tmp_log.read_text(encoding="utf-8")


def test_build_parsers_expose_phase12_defaults() -> None:
    reality_mod = _phase12_reality_contract()
    report_mod = _phase12_report_contract()

    reality_args = reality_mod.build_parser().parse_args([])
    report_args = report_mod.build_parser().parse_args([])

    assert Path(reality_args.reality_log) == REALITY_LOG
    assert Path(reality_args.out_log) == REALITY_TEST_LOG
    assert Path(reality_args.artifact_root) == PHASE12_ARTIFACT_ROOT
    assert Path(reality_args.gguf_path) == APPROVED_Q4_MODEL
    assert Path(report_args.reality_test_log) == REALITY_TEST_LOG
    assert Path(report_args.artifact_root) == PHASE12_ARTIFACT_ROOT
