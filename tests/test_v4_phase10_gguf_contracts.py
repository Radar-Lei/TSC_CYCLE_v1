from __future__ import annotations

import ast
import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
FROZEN_V1_ROOT = PROJECT_ROOT / "runs" / "20260507T032419Z"
PHASE9_RUN_ROOT = PROJECT_ROOT / "runs" / "v4.0-4B-20260509T184844Z"
DEFAULT_LLAMA_CPP = Path("/home/samuel/projects/EvoProgTSC/llama.cpp")

FORBIDDEN_COLLECTION_IMPORTS = {"torch", "transformers", "peft"}
FORBIDDEN_WRAPPER_TERMS = {
    "pip install",
    "uv pip install",
    "install flash-attn",
    "flash-attn",
    "vllm",
    "git worktree",
    "worktree add",
    "runs/20260507T032419Z",
}


@pytest.fixture(autouse=True)
def _phase10_modules_are_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 10 RED contracts must never load model/GPU stacks at collection time."""
    real_import = importlib.import_module

    def guarded_import(name: str, package: str | None = None):
        root = name.split(".", 1)[0]
        if root in FORBIDDEN_COLLECTION_IMPORTS:
            raise AssertionError(f"Phase 10 contract imported heavyweight dependency during test execution: {name}")
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", guarded_import)


def _phase10_export_contract():
    return importlib.import_module("tsc_cycle.v4_gates.phase10_export")


def _phase10_tokenizer_contract():
    return importlib.import_module("tsc_cycle.v4_gates.phase10_tokenizer_parity")


def _phase10_report_contract():
    return importlib.import_module("tsc_cycle.v4_gates.phase10_report")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _make_adapter(tmp_path: Path) -> tuple[Path, str]:
    adapter_dir = tmp_path / "runs" / "v4.0-4B-20260509T184844Z" / "adapter"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "adapter_config.json").write_text('{"base_model_name_or_path":"Qwen/Qwen3-4B-Thinking-2507"}\n', encoding="utf-8")
    weights = adapter_dir / "adapter_model.safetensors"
    weights.write_bytes(b"compact fake adapter weights")
    return adapter_dir, _sha256_file(weights)


def _phase9_report(tmp_path: Path, *, ok: bool = True, next_phase_allowed: bool = True) -> tuple[Path, Path, str]:
    adapter_dir, adapter_sha = _make_adapter(tmp_path)
    report_path = _write_json(
        tmp_path / "runs" / "v4.0-4B-20260509T184844Z" / "phase9_sft_report.json",
        {
            "ok": ok,
            "next_phase_allowed": next_phase_allowed,
            "run_root": str(adapter_dir.parent),
            "adapter_path": str(adapter_dir),
            "artifact_manifest": {
                "paths": {"adapter": str(adapter_dir), "run_root": str(adapter_dir.parent)},
                "sha256": {"adapter_sha256": adapter_sha},
            },
            "gates": {
                "phase10_handoff": {
                    "ok": True,
                    "data": {"adapter_path": str(adapter_dir), "adapter_sha256": adapter_sha, "next_phase_allowed": True},
                }
            },
        },
    )
    return report_path, adapter_dir, adapter_sha


def _sample_input() -> dict[str, Any]:
    return {
        "sample_id": "phase10-fixture-0001",
        "split_hint": "ood_val",
        "input": {
            "sample_id": "phase10-fixture-0001",
            "split_hint": "ood_val",
            "prediction": {
                "phase_waits": [
                    {"phase_id": 1, "min_green": 10, "max_green": 40, "pred_wait": 3.0, "pred_saturation": 0.25, "capacity": 30},
                    {"phase_id": 2, "min_green": 15, "max_green": 50, "pred_wait": 7.0, "pred_saturation": 0.70, "capacity": 30},
                    {"phase_id": 3, "min_green": 12, "max_green": 45, "pred_wait": 5.0, "pred_saturation": 0.55, "capacity": 30},
                ]
            },
        },
    }


def _good_output(solution: dict[str, int] | None = None) -> str:
    if solution is None:
        solution = {"1": 20, "2": 30, "3": 25}
    return (
        "<start_working_out>根据饱和度分配绿灯，并检查每个相位上下限。</end_working_out>"
        f"<SOLUTION>{json.dumps(solution, ensure_ascii=False, sort_keys=True)}</SOLUTION>"
    )


def _write_backend_report(path: Path, backend: str, output_text: str, *, solution: dict[str, int] | None = None) -> Path:
    return _write_json(
        path,
        {
            "backend": backend,
            "n_prompts": 1,
            "n_predict": 128,
            "results": [
                {
                    "sample_id": "phase10-fixture-0001",
                    "split_hint": "ood_val",
                    "text": output_text,
                    "output_text": output_text,
                    "tail": output_text[-200:],
                    "solution": solution,
                    "parse_error": None,
                }
            ],
        },
    )


def test_phase10_contracts_do_not_import_heavy_model_stacks_at_collection() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])

    assert imported_roots.isdisjoint(FORBIDDEN_COLLECTION_IMPORTS), (
        "Phase 10 contracts must use lazy imports and must not import torch/transformers/peft in test collection"
    )
    forbidden_student_import = "tsc_cycle.student" + ".export_gguf"
    assert forbidden_student_import not in source, "student export module imports GPU stacks; Phase 10 tests must target lazy v4_gates wrappers"


def test_phase9_handoff_requires_green_report_adapter_files_and_sha(tmp_path: Path) -> None:
    mod = _phase10_export_contract()
    report_path, adapter_dir, adapter_sha = _phase9_report(tmp_path)

    handoff = mod.load_phase9_handoff(report_path)

    assert handoff["ok"] is True
    assert handoff["next_phase_allowed"] is True
    assert Path(handoff["adapter_path"]) == adapter_dir
    assert handoff["adapter_sha256"] == adapter_sha
    assert Path(handoff["adapter_files"]["adapter_model"]).name == "adapter_model.safetensors"
    assert Path(handoff["adapter_files"]["adapter_config"]).name == "adapter_config.json"
    assert "GGUF4B-01" in handoff["requirements_covered"]

    bad_report, _, _ = _phase9_report(tmp_path / "bad", ok=False)
    with pytest.raises((AssertionError, ValueError, RuntimeError), match="phase9|handoff|ok|next_phase|adapter|sha"):
        mod.load_phase9_handoff(bad_report)

    missing_sha = json.loads(report_path.read_text(encoding="utf-8"))
    missing_sha["artifact_manifest"]["sha256"].pop("adapter_sha256")
    missing_sha_path = _write_json(tmp_path / "missing_sha" / "phase9_sft_report.json", missing_sha)
    with pytest.raises((AssertionError, ValueError, RuntimeError), match="sha|adapter"):
        mod.load_phase9_handoff(missing_sha_path)


def test_export_plan_paths_llama_cpp_defaults_and_tool_fail_closed(tmp_path: Path) -> None:
    mod = _phase10_export_contract()
    report_path, adapter_dir, adapter_sha = _phase9_report(tmp_path)
    llama_cpp = tmp_path / "llama.cpp"
    llama_cpp.mkdir()
    convert = llama_cpp / "convert_hf_to_gguf.py"
    quantize = llama_cpp / "llama-quantize"
    tokenize = llama_cpp / "llama-tokenize"
    server = llama_cpp / "llama-server"
    for tool in (convert, quantize, tokenize, server):
        tool.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        tool.chmod(0o755)

    plan = mod.plan_phase10_export(
        phase9_report=report_path,
        run_root=tmp_path / "runs" / "v4.0-4B-20260509T184844Z",
        llama_cpp_dir=llama_cpp,
    )

    assert plan["ok"] is True
    assert Path(plan["adapter_path"]) == adapter_dir
    assert plan["adapter_sha256"] == adapter_sha
    assert Path(plan["paths"]["merged_hf"]).name == "merged_hf"
    assert Path(plan["paths"]["gguf_fp16"]).as_posix().endswith("gguf/model.fp16.gguf")
    assert Path(plan["paths"]["gguf_q4_K_M"]).as_posix().endswith("gguf/model.q4_K_M.gguf")
    assert Path(plan["paths"]["export_report"]).name == "phase10_export_report.json"
    assert Path(plan["llama_cpp"]["root"]) == llama_cpp
    assert Path(plan["llama_cpp"]["convert"]) == convert
    assert Path(plan["llama_cpp"]["quantize"]) == quantize
    assert Path(plan["llama_cpp"]["tokenize"]) == tokenize
    assert Path(plan["llama_cpp"]["server"]) == server
    assert "GGUF4B-01" in plan["requirements_covered"]
    assert not _is_under(Path(plan["paths"]["merged_hf"]), FROZEN_V1_ROOT)
    assert not _is_under(Path(plan["paths"]["export_report"]), FROZEN_V1_ROOT)

    default_plan = mod.plan_phase10_export(phase9_report=report_path, run_root=tmp_path / "default_run")
    assert Path(default_plan["llama_cpp"]["root"]) == DEFAULT_LLAMA_CPP

    convert.unlink()
    failed = mod.plan_phase10_export(phase9_report=report_path, run_root=tmp_path / "missing_tool", llama_cpp_dir=llama_cpp)
    assert failed["ok"] is False
    assert any("convert" in failure["gate"] or "convert" in failure["reason"] for failure in failed["fatal_failures"])


def test_rejects_output_writes_under_frozen_production_baseline(tmp_path: Path) -> None:
    mod = _phase10_export_contract()
    report_path, _, _ = _phase9_report(tmp_path)

    with pytest.raises((AssertionError, ValueError, RuntimeError), match="frozen|read.?only|20260507T032419Z"):
        mod.plan_phase10_export(phase9_report=report_path, run_root=FROZEN_V1_ROOT)

    assert mod.is_forbidden_output_path(FROZEN_V1_ROOT / "gguf" / "phase10_export_report.json") is True
    assert mod.is_forbidden_output_path(PHASE9_RUN_ROOT / "gguf" / "phase10_export_report.json") is False


def test_phase10_wrappers_forbid_dependency_installs_unsupported_runtimes_and_worktrees() -> None:
    mod = _phase10_export_contract()
    wrappers = mod.phase10_wrapper_commands(run_root=PHASE9_RUN_ROOT, llama_cpp_dir=DEFAULT_LLAMA_CPP)

    assert wrappers, "Phase 10 implementation must expose auditable wrapper commands before runtime plans execute"
    commands_text = json.dumps(wrappers, ensure_ascii=False).lower()
    for forbidden in FORBIDDEN_WRAPPER_TERMS:
        assert forbidden.lower() not in commands_text, f"Phase 10 wrappers must not include forbidden command text: {forbidden}"
    assert "convert_hf_to_gguf.py" in commands_text
    assert "llama-quantize" in commands_text
    assert str(PHASE9_RUN_ROOT).lower() in commands_text


def test_fixed_prompt_fixture_is_deterministic_and_includes_required_fields() -> None:
    mod = _phase10_tokenizer_contract()
    record = _sample_input()

    prompt_a = mod.build_phase10_prompt_fixture(record)
    prompt_b = mod.build_phase10_prompt_fixture(json.loads(json.dumps(record, ensure_ascii=False)))

    assert prompt_a == prompt_b
    assert prompt_a["sample_id"] == "phase10-fixture-0001"
    assert prompt_a["split_hint"] == "ood_val"
    assert prompt_a["input"] == record["input"]
    assert "prompt" in prompt_a and "cycle_predict_input_json" in prompt_a["prompt"]
    assert "<start_working_out>" in prompt_a["assistant_prefill"]
    assert "GGUF4B-02" in prompt_a["requirements_covered"]
    assert "GGUF4B-03" in prompt_a["requirements_covered"]


def test_tokenizer_parity_requires_exact_hf_llama_token_ids_and_diagnostics() -> None:
    mod = _phase10_tokenizer_contract()
    prompt = {"sample_id": "tok-1", "prompt": "abc <start_working_out>"}

    ok = mod.compare_tokenizer_parity(prompt, hf_token_ids=[1, 2, 3, 4], llama_token_ids=[1, 2, 3, 4])
    assert ok["ok"] is True
    assert ok["match"] is True
    assert ok["mismatch_diagnostics"] == []
    assert "GGUF4B-03" in ok["requirements_covered"]

    bad = mod.compare_tokenizer_parity(prompt, hf_token_ids=[1, 2, 3, 4], llama_token_ids=[1, 9, 3])
    assert bad["ok"] is False
    assert bad["match"] is False
    assert bad["hf_token_ids"] == [1, 2, 3, 4]
    assert bad["llama_token_ids"] == [1, 9, 3]
    assert bad["mismatch_diagnostics"]
    assert bad["mismatch_diagnostics"][0]["index"] == 1
    assert any(diag["kind"] in {"id_mismatch", "length_mismatch"} for diag in bad["mismatch_diagnostics"])


def test_smoke_protocol_requires_complete_custom_tags_for_all_three_backends(tmp_path: Path) -> None:
    mod = _phase10_report_contract()
    sample = _sample_input()
    backend_reports = {
        "hf": _write_backend_report(tmp_path / "hf.json", "hf", _good_output()),
        "gguf_fp16": _write_backend_report(tmp_path / "fp16.json", "gguf_fp16", _good_output()),
        "gguf_q4_K_M": _write_backend_report(tmp_path / "q4.json", "gguf_q4_K_M", _good_output()),
    }

    report = mod.evaluate_three_backend_smoke(samples=[sample], backend_reports=backend_reports)

    assert report["ok"] is True
    assert report["gates"]["protocol_hf"]["ok"] is True
    assert report["gates"]["protocol_gguf_fp16"]["ok"] is True
    assert report["gates"]["protocol_gguf_q4_K_M"]["ok"] is True
    assert set(report["backends"]) == {"hf", "gguf_fp16", "gguf_q4_K_M"}
    assert set(report["requirements_covered"]) >= {"GGUF4B-02", "GGUF4B-04"}

    malformed = _write_backend_report(tmp_path / "bad_q4.json", "gguf_q4_K_M", "<start_working_out>x<end_working_out><SOLUTION>{}</SOLUTION>")
    bad_report = mod.evaluate_three_backend_smoke(samples=[sample], backend_reports={**backend_reports, "gguf_q4_K_M": malformed})
    assert bad_report["ok"] is False
    assert bad_report["gates"]["protocol_gguf_q4_K_M"]["ok"] is False
    assert any("malformed" in failure["reason"].lower() or "end_working_out" in failure["reason"] for failure in bad_report["fatal_failures"])

    native = _write_backend_report(tmp_path / "native_q4.json", "gguf_q4_K_M", "<think>x</think><SOLUTION>{}</SOLUTION>")
    native_report = mod.evaluate_three_backend_smoke(samples=[sample], backend_reports={**backend_reports, "gguf_q4_K_M": native})
    assert native_report["ok"] is False
    assert native_report["gates"]["protocol_gguf_q4_K_M"]["ok"] is False
    assert any("native" in failure["reason"].lower() or "<think>" in failure["reason"] for failure in native_report["fatal_failures"])


def test_hard_constraint_smoke_validates_integer_phase_coverage_and_bounds(tmp_path: Path) -> None:
    mod = _phase10_report_contract()
    sample = _sample_input()
    backend_reports = {
        "hf": _write_backend_report(tmp_path / "hf.json", "hf", _good_output()),
        "gguf_fp16": _write_backend_report(tmp_path / "fp16.json", "gguf_fp16", _good_output()),
        "gguf_q4_K_M": _write_backend_report(tmp_path / "q4.json", "gguf_q4_K_M", _good_output({"1": 20, "2": 30, "3": 25})),
    }

    report = mod.evaluate_three_backend_smoke(samples=[sample], backend_reports=backend_reports)
    assert report["gates"]["hard_constraints_gguf_q4_K_M"]["ok"] is True

    missing_phase = _write_backend_report(tmp_path / "missing_phase.json", "gguf_q4_K_M", _good_output({"1": 20, "2": 30}))
    missing_report = mod.evaluate_three_backend_smoke(samples=[sample], backend_reports={**backend_reports, "gguf_q4_K_M": missing_phase})
    assert missing_report["ok"] is False
    assert missing_report["gates"]["hard_constraints_gguf_q4_K_M"]["ok"] is False
    assert any("coverage" in failure["reason"].lower() or "phase" in failure["reason"].lower() for failure in missing_report["fatal_failures"])

    out_of_bounds = _write_backend_report(tmp_path / "bounds.json", "gguf_q4_K_M", _good_output({"1": 9, "2": 30, "3": 25}))
    bounds_report = mod.evaluate_three_backend_smoke(samples=[sample], backend_reports={**backend_reports, "gguf_q4_K_M": out_of_bounds})
    assert bounds_report["ok"] is False
    assert any("bounds" in failure["reason"].lower() or "min" in failure["reason"].lower() for failure in bounds_report["fatal_failures"])

    non_integer = _write_backend_report(tmp_path / "non_integer.json", "gguf_q4_K_M", _good_output({"1": 20, "2": 30, "3": 25}).replace('"2": 30', '"2": 30.5'))
    integer_report = mod.evaluate_three_backend_smoke(samples=[sample], backend_reports={**backend_reports, "gguf_q4_K_M": non_integer})
    assert integer_report["ok"] is False
    assert any("integer" in failure["reason"].lower() for failure in integer_report["fatal_failures"])


def test_q4_collapse_records_q5_decision_required_with_reasons(tmp_path: Path) -> None:
    mod = _phase10_report_contract()
    sample = _sample_input()
    backend_reports = {
        "hf": _write_backend_report(tmp_path / "hf.json", "hf", _good_output()),
        "gguf_fp16": _write_backend_report(tmp_path / "fp16.json", "gguf_fp16", _good_output()),
        "gguf_q4_K_M": _write_backend_report(tmp_path / "q4_collapse.json", "gguf_q4_K_M", "<start_working_out>collapsed</end_working_out><SOLUTION>{}</SOLUTION>"),
    }

    report = mod.evaluate_three_backend_smoke(samples=[sample], backend_reports=backend_reports)

    assert report["ok"] is False
    assert report["q5_K_M_decision_required"] is True
    assert report["q5_K_M_decision_reasons"]
    assert any("q4" in reason.lower() or "collapse" in reason.lower() or "hard" in reason.lower() for reason in report["q5_K_M_decision_reasons"])
    assert "GGUF4B-04" in report["requirements_covered"]


def test_aggregate_phase10_report_requires_export_tokenizer_and_smoke_gates(tmp_path: Path) -> None:
    mod = _phase10_report_contract()
    export_report = _write_json(
        tmp_path / "phase10_export_report.json",
        {
            "ok": True,
            "requirements_covered": ["GGUF4B-01"],
            "paths": {
                "merged_hf": str(tmp_path / "merged_hf"),
                "gguf_fp16": str(tmp_path / "gguf" / "model.fp16.gguf"),
                "gguf_q4_K_M": str(tmp_path / "gguf" / "model.q4_K_M.gguf"),
            },
        },
    )
    tokenizer_report = _write_json(
        tmp_path / "tokenizer_parity_report.json",
        {"ok": True, "requirements_covered": ["GGUF4B-03"], "all_match": True, "mismatch_diagnostics": []},
    )
    smoke_report = _write_json(
        tmp_path / "three_backend_smoke_report.json",
        {"ok": True, "requirements_covered": ["GGUF4B-02", "GGUF4B-04"], "q5_K_M_decision_required": False},
    )

    report = mod.evaluate_phase10_report(
        export_report=export_report,
        tokenizer_report=tokenizer_report,
        smoke_report=smoke_report,
        out_path=tmp_path / "phase10_gate_report.json",
    )

    assert report["ok"] is True
    assert report["next_phase_allowed"] is True
    assert report["requirements_covered"] == ["GGUF4B-01", "GGUF4B-02", "GGUF4B-03", "GGUF4B-04"]
    assert (tmp_path / "phase10_gate_report.json").exists()

    broken_smoke = _write_json(tmp_path / "broken_smoke.json", {"ok": False, "requirements_covered": ["GGUF4B-02"], "fatal_failures": [{"gate": "q4", "reason": "collapse"}], "q5_K_M_decision_required": True})
    blocked = mod.evaluate_phase10_report(
        export_report=export_report,
        tokenizer_report=tokenizer_report,
        smoke_report=broken_smoke,
        out_path=tmp_path / "blocked.json",
    )
    assert blocked["ok"] is False
    assert blocked["next_phase_allowed"] is False
    assert blocked["q5_K_M_decision_required"] is True
    assert any(failure["gate"] == "smoke_report" for failure in blocked["fatal_failures"])
