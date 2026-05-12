from __future__ import annotations

import ast
import importlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
FROZEN_V1_ROOT = PROJECT_ROOT / "runs" / "20260507T032419Z"
V4_RUN_ROOT = PROJECT_ROOT / "runs" / "v4.0-4B-20260509T184844Z"
PHASE11_OUT_ROOT = V4_RUN_ROOT / "eval_phase11"
V4_HF = "v4_hf"
V4_Q4 = "v4_gguf_q4_k_m"
V1_Q4 = "v1_gguf_q4_k_m"
REQUIRED_BACKENDS = {V4_HF, V4_Q4, V1_Q4}
FORBIDDEN_COLLECTION_IMPORTS = {"torch", "transformers", "peft", "bitsandbytes", "vllm", "flash_attn"}


@pytest.fixture(autouse=True)
def _phase11_modules_are_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 11 contracts must never load model/GPU stacks during test execution."""
    real_import = importlib.import_module

    def guarded_import(name: str, package: str | None = None):
        root = name.split(".", 1)[0]
        if root in FORBIDDEN_COLLECTION_IMPORTS:
            raise AssertionError(f"Phase 11 contract imported heavyweight dependency during test execution: {name}")
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", guarded_import)


def _phase11_matrix_contract():
    return importlib.import_module("tsc_cycle.eval.phase11_matrix")


def _phase11_decision_contract():
    return importlib.import_module("tsc_cycle.eval.phase11_decision")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _gate_metrics(
    *,
    hard_pass: float = 0.98,
    q4_vs_hf_ratio: float = 0.95,
    hard_delta_ci_low: float = -0.01,
    mae_delta_ci_high: float = 0.5,
    phase10_handoff_ok: bool = True,
    frozen_v1_evidence_ok: bool = True,
) -> dict[str, Any]:
    return {
        "phase10_handoff": {
            "ok": phase10_handoff_ok,
            "report_path": str(V4_RUN_ROOT / "phase10_gguf_report.json"),
            "q4_collapse": False,
            "phase10_smoke_mae_sensitivity_flag": True,
        },
        "frozen_v1_baseline": {
            "ok": frozen_v1_evidence_ok,
            "root": str(FROZEN_V1_ROOT),
            "per_sample": str(FROZEN_V1_ROOT / "eval" / "per_sample.jsonl"),
        },
        "backends": {
            V4_HF: {"ood_hard_constraint_pass": 1.0, "ood_teacher_mae": 6.0, "format_pass": 1.0},
            V4_Q4: {"ood_hard_constraint_pass": hard_pass, "ood_teacher_mae": 6.2, "format_pass": 1.0},
            V1_Q4: {"ood_hard_constraint_pass": 0.9867, "ood_teacher_mae": 7.8457, "format_pass": 1.0},
        },
        "q4_vs_hf": {"hard_pass_ratio": q4_vs_hf_ratio},
        "baseline_comparison": {
            "slice": "v1_comparable_ood",
            "hard_pass_delta_ci": {"lower": hard_delta_ci_low, "upper": 0.02, "confidence": 0.95},
            "teacher_mae_delta_ci": {"lower": -0.2, "upper": mae_delta_ci_high, "confidence": 0.95},
        },
        "tail_stats": {
            V4_Q4: {
                "sample_mae_p99": 9.0,
                "sample_mae_max": 10.0,
                "per_phase_abs_err_p99": 15.0,
                "per_phase_abs_err_max": 16.0,
            }
        },
        "artifacts": {
            "v4_q4": str(V4_RUN_ROOT / "gguf" / "model.q4_K_M.gguf"),
            "v1_q4": str(FROZEN_V1_ROOT / "gguf" / "model.q4_K_M.gguf"),
            "decision_md": str(PHASE11_OUT_ROOT / "decision.md"),
        },
        "contribution": {
            "expanded_data": "v4 expanded OOD is reported separately from v1-comparable OOD.",
            "tag_fix": "Malformed <end_working_out> and native <think> failures are tracked through format pass.",
        },
    }


def _paired_rows() -> list[dict[str, Any]]:
    return [
        {"sample_id": "ood-001", "slice": "v1_comparable_ood", "v4_q4_hard_pass": True, "v1_q4_hard_pass": True, "v4_q4_teacher_mae": 3.0, "v1_q4_teacher_mae": 3.5},
        {"sample_id": "ood-002", "slice": "v1_comparable_ood", "v4_q4_hard_pass": True, "v1_q4_hard_pass": True, "v4_q4_teacher_mae": 4.0, "v1_q4_teacher_mae": 5.0},
        {"sample_id": "ood-003", "slice": "v1_comparable_ood", "v4_q4_hard_pass": False, "v1_q4_hard_pass": True, "v4_q4_teacher_mae": 8.0, "v1_q4_teacher_mae": 7.0},
        {"sample_id": "ood-004", "slice": "v1_comparable_ood", "v4_q4_hard_pass": True, "v1_q4_hard_pass": False, "v4_q4_teacher_mae": 2.0, "v1_q4_teacher_mae": 3.0},
    ]


def _tiny_per_sample_rows() -> list[dict[str, Any]]:
    return [
        {"sample_id": "s1", "backend": V4_Q4, "split_hint": "ood", "lint_ok": True, "parse_error": None, "solution": {"1": 20}, "mae": 0.0, "per_phase_abs_err": [0, 1]},
        {"sample_id": "s2", "backend": V4_Q4, "split_hint": "ood", "lint_ok": True, "parse_error": None, "solution": {"1": 21}, "mae": 2.0, "per_phase_abs_err": [2, 3]},
        {"sample_id": "s3", "backend": V4_Q4, "split_hint": "ood", "lint_ok": False, "parse_error": "solution_unparseable", "solution": None, "mae": None, "per_phase_abs_err": []},
        {"sample_id": "s1", "backend": V4_HF, "split_hint": "ood", "lint_ok": True, "parse_error": None, "solution": {"1": 20}, "mae": 0.0, "per_phase_abs_err": [0]},
        {"sample_id": "s2", "backend": V4_HF, "split_hint": "ood", "lint_ok": True, "parse_error": None, "solution": {"1": 21}, "mae": 1.0, "per_phase_abs_err": [1]},
        {"sample_id": "s1", "backend": V1_Q4, "split_hint": "ood", "lint_ok": True, "parse_error": None, "solution": {"1": 22}, "mae": 2.0, "per_phase_abs_err": [2]},
        {"sample_id": "s2", "backend": V1_Q4, "split_hint": "ood", "lint_ok": True, "parse_error": None, "solution": {"1": 22}, "mae": 1.0, "per_phase_abs_err": [1]},
    ]


def test_phase11_contracts_do_not_import_heavy_model_stacks_at_collection() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])

    assert imported_roots.isdisjoint(FORBIDDEN_COLLECTION_IMPORTS), (
        "Phase 11 contracts must use lazy imports and must not import torch/transformers/peft/"
        "bitsandbytes/vllm/flash_attn in test collection"
    )
    forbidden_student_module = "tsc_cycle." + "student"
    assert forbidden_student_module not in source, "Phase 11 RED contracts must target lightweight eval/gate modules, not GPU student modules"


def test_phase11_backend_normalization_contracts() -> None:
    mod = _phase11_matrix_contract()

    aliases = {
        "hf": V4_HF,
        "hf_bf16": V4_HF,
        "v4_hf": V4_HF,
        "v4 hf": V4_HF,
        "gguf_q4_K_M": V4_Q4,
        "q4_K_M": V4_Q4,
        "v4_gguf_q4_k_m": V4_Q4,
        "v4 q4_K_M": V4_Q4,
        "v1": V1_Q4,
        "v1_q4": V1_Q4,
        "v1_gguf_q4_k_m": V1_Q4,
        "frozen_v1_q4_K_M": V1_Q4,
    }
    for raw, expected in aliases.items():
        assert mod.normalize_backend_id(raw) == expected

    with pytest.raises((AssertionError, ValueError, KeyError), match="backend|unknown|unsupported"):
        mod.normalize_backend_id("gguf_fp16")


def test_phase11_matrix_rejects_frozen_v1_outputs_and_allows_v4_eval_root(tmp_path: Path) -> None:
    mod = _phase11_matrix_contract()

    forbidden_paths = [
        FROZEN_V1_ROOT,
        FROZEN_V1_ROOT / "eval" / "decision.md",
        FROZEN_V1_ROOT / "eval" / "gen_cache" / "gguf_q4_k_m" / "sample.json",
    ]
    for path in forbidden_paths:
        with pytest.raises((AssertionError, ValueError, RuntimeError), match="frozen|read.?only|20260507T032419Z"):
            mod.reject_frozen_v1_output_path(path)

    allowed = PHASE11_OUT_ROOT / "metrics.json"
    assert mod.reject_frozen_v1_output_path(allowed) in {None, str(allowed), allowed}
    assert mod.reject_frozen_v1_output_path(tmp_path / "eval_phase11" / "metrics.json") in {None, str(tmp_path / "eval_phase11" / "metrics.json"), tmp_path / "eval_phase11" / "metrics.json"}


def test_phase11_matrix_config_includes_required_backends_and_v1_is_read_only() -> None:
    mod = _phase11_matrix_contract()

    config = mod.build_phase11_matrix_config(run_root=V4_RUN_ROOT, frozen_v1_root=FROZEN_V1_ROOT, out_root=PHASE11_OUT_ROOT)

    backends = config["backends"] if isinstance(config, dict) else config.backends
    if isinstance(backends, dict):
        backend_ids = set(backends)
        v1_cfg = backends[V1_Q4]
    else:
        backend_ids = {entry["id"] if isinstance(entry, dict) else entry.id for entry in backends}
        v1_cfg = next(entry for entry in backends if (entry["id"] if isinstance(entry, dict) else entry.id) == V1_Q4)

    assert backend_ids == REQUIRED_BACKENDS
    assert str(PHASE11_OUT_ROOT) in json.dumps(config, default=str)
    assert str(FROZEN_V1_ROOT) in json.dumps(config, default=str)
    assert (v1_cfg["read_only"] if isinstance(v1_cfg, dict) else v1_cfg.read_only) is True
    assert (v1_cfg["generate"] if isinstance(v1_cfg, dict) else v1_cfg.generate) is False


def test_phase11_bootstrap_ci_is_paired_deterministic_and_exposes_required_intervals() -> None:
    mod = _phase11_decision_contract()

    ci_a = mod.bootstrap_ci(_paired_rows(), seed=42, n_resamples=200, confidence=0.95)
    ci_b = mod.bootstrap_ci(list(reversed(_paired_rows())), seed=42, n_resamples=200, confidence=0.95)

    assert ci_a == ci_b, "Phase 11 bootstrap must be deterministic for seed=42 and order-independent by sample_id"
    assert ci_a["seed"] == 42
    assert ci_a["n_resamples"] == 200
    assert ci_a["slice"] == "v1_comparable_ood"
    assert set(ci_a["metrics"]) >= {"hard_pass_delta", "teacher_mae_delta"}
    assert ci_a["metrics"]["hard_pass_delta"]["lower"] <= ci_a["metrics"]["hard_pass_delta"]["upper"]
    assert ci_a["metrics"]["teacher_mae_delta"]["lower"] <= ci_a["metrics"]["teacher_mae_delta"]["upper"]

    with pytest.raises((AssertionError, ValueError, RuntimeError), match="paired|empty|comparable|sample"):
        mod.bootstrap_ci([], seed=42, n_resamples=10)


def test_phase11_tail_stats_include_sample_and_per_phase_p99_and_max_abs() -> None:
    mod = _phase11_decision_contract()

    tail = mod.compute_tail_stats(_tiny_per_sample_rows(), backend=V4_Q4, split="ood")

    assert set(tail) >= {"sample_mae_p99", "sample_mae_max", "per_phase_abs_err_p99", "per_phase_abs_err_max"}
    assert tail["sample_mae_max"] == 2.0
    assert tail["per_phase_abs_err_max"] == 3
    assert tail["sample_mae_p99"] >= 0.0
    assert tail["per_phase_abs_err_p99"] >= 0.0

    with pytest.raises((AssertionError, ValueError, RuntimeError), match="mae|empty|denominator|finite"):
        mod.compute_tail_stats([{"backend": V4_Q4, "split_hint": "ood", "mae": None, "per_phase_abs_err": []}], backend=V4_Q4, split="ood")


def test_phase11_metrics_json_contains_eval4b02_sections(tmp_path: Path) -> None:
    mod = _phase11_decision_contract()

    metrics = mod.build_phase11_metrics_json(
        per_sample_rows=_tiny_per_sample_rows(),
        bootstrap=mod.bootstrap_ci(_paired_rows(), seed=42, n_resamples=200, confidence=0.95),
        phase10_handoff={"ok": True, "report_path": str(V4_RUN_ROOT / "phase10_gguf_report.json"), "phase10_smoke_mae_sensitivity_flag": True},
        frozen_v1_baseline={"ok": True, "root": str(FROZEN_V1_ROOT), "per_sample": str(FROZEN_V1_ROOT / "eval" / "per_sample.jsonl")},
        out_path=tmp_path / "metrics.json",
    )

    assert metrics["ok"] is True
    assert (tmp_path / "metrics.json").exists()
    assert set(metrics["backends"]) == REQUIRED_BACKENDS
    for backend_id in REQUIRED_BACKENDS:
        assert set(metrics["backends"][backend_id]) >= {"ood_hard_constraint_pass", "teacher_mae", "format_pass"}
    assert "q4_vs_hf" in metrics and "hard_pass_ratio" in metrics["q4_vs_hf"]
    assert "baseline_comparison" in metrics and "hard_pass_delta_ci" in metrics["baseline_comparison"]
    assert "teacher_mae_delta_ci" in metrics["baseline_comparison"]
    assert "tail_stats" in metrics
    assert set(metrics["requirements_covered"]) >= {"EVAL4B-01", "EVAL4B-02", "EVAL4B-03", "EVAL4B-04"}


def test_phase11_decision_gate_thresholds_are_locked_and_fail_closed() -> None:
    mod = _phase11_decision_contract()

    passing = mod.evaluate_phase11_decision(_gate_metrics())
    assert passing["verdict"] == "GO"
    assert passing["ok"] is True
    assert passing["thresholds"] == {
        "v4_q4_hard_constraint_pass_min": 0.98,
        "q4_vs_hf_hard_pass_ratio_min": 0.95,
        "hard_pass_delta_ci_lower_min": -0.01,
        "teacher_mae_delta_ci_upper_max_sec": 0.5,
    }

    failing_cases = {
        "hard_pass": _gate_metrics(hard_pass=0.9799),
        "q4_vs_hf_ratio": _gate_metrics(q4_vs_hf_ratio=0.9499),
        "hard_delta_ci_low": _gate_metrics(hard_delta_ci_low=-0.0101),
        "mae_delta_ci_high": _gate_metrics(mae_delta_ci_high=0.5001),
        "missing_phase10_handoff": _gate_metrics(phase10_handoff_ok=False),
        "missing_frozen_v1_evidence": _gate_metrics(frozen_v1_evidence_ok=False),
        "nan_denominator": _gate_metrics(q4_vs_hf_ratio=float("nan")),
    }
    for name, metrics in failing_cases.items():
        decision = mod.evaluate_phase11_decision(metrics)
        assert decision["verdict"] in {"NO_GO", "USER_DECISION_REQUIRED"}, name
        assert decision["ok"] is False, name
        assert decision["next_phase_allowed"] is False, name
        assert decision["fatal_failures"], name


def test_phase11_decision_markdown_explains_contributions_and_artifact_paths() -> None:
    mod = _phase11_decision_contract()
    metrics = _gate_metrics()
    decision = mod.evaluate_phase11_decision(metrics)

    markdown = mod.render_decision_markdown(metrics=metrics, decision=decision)

    assert any(verdict in markdown for verdict in ("GO", "NO-GO", "NO_GO", "USER_DECISION"))
    assert str(V4_RUN_ROOT / "gguf" / "model.q4_K_M.gguf") in markdown
    assert str(FROZEN_V1_ROOT) in markdown
    assert "expanded" in markdown.lower() or "扩展" in markdown
    assert "tag" in markdown.lower() or "标签" in markdown
    assert "Phase 10" in markdown and ("MAE" in markdown or "sensitivity" in markdown.lower() or "敏感" in markdown)


def test_phase11_report_fails_closed_on_missing_handoff_or_baseline_evidence(tmp_path: Path) -> None:
    mod = _phase11_decision_contract()
    missing_handoff = _write_json(tmp_path / "missing_phase10.json", {"ok": False, "next_phase_allowed": False})
    missing_baseline = tmp_path / "missing_v1_per_sample.jsonl"

    report = mod.evaluate_phase11_report(
        metrics=_gate_metrics(),
        phase10_handoff_report=missing_handoff,
        frozen_v1_per_sample=missing_baseline,
        out_path=tmp_path / "phase11_gate_report.json",
    )

    assert report["ok"] is False
    assert report["next_phase_allowed"] is False
    assert any("phase10" in failure["gate"].lower() or "handoff" in failure["reason"].lower() for failure in report["fatal_failures"])
    assert any("v1" in failure["gate"].lower() or "baseline" in failure["reason"].lower() for failure in report["fatal_failures"])
