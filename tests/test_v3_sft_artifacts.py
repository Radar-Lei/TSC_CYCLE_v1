from __future__ import annotations

import json
from pathlib import Path


REQUIREMENTS_COVERED = [
    "SFT-01",
    "SFT-02",
    "SFT-03",
    "SFT-04",
    "SFT-05",
    "SFT-06",
    "SFT-07",
    "SFT-08",
]


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _passing_manifest(tmp_path: Path) -> Path:
    run_root = tmp_path / "runs" / "v3.0-9B-20260509T000000Z"
    dry_report = run_root / "reports" / "dry_run_gate.json"
    full_report = run_root / "reports" / "full_run.json"
    adapter = run_root / "adapter"
    lora_coverage = run_root / "reports" / "lora_coverage.json"
    adapter.mkdir(parents=True)
    lora_coverage.parent.mkdir(parents=True, exist_ok=True)
    _write_json(dry_report, {"ok": True, "sample_count": 500, "ood_hard_constraint_pass_rate": 0.95})
    _write_json(full_report, {"ok": True, "early_stopping": {"patience": 3}, "best_adapter": str(adapter)})
    _write_json(lora_coverage, {"ok": True, "expected_gated_deltanet_layers": 24, "expected_full_attention_layers": 8})
    manifest = {
        "ok": True,
        "requirements_covered": REQUIREMENTS_COVERED,
        "run_root": str(run_root),
        "wandb_project": "tsc-cycle-v3-9b",
        "dry_run_report": str(dry_report),
        "full_run_report": str(full_report),
        "adapter_path": str(adapter),
        "arrow_hashes": {
            "train_arrow": "t" * 64,
            "val_arrow": "v" * 64,
            "ood_val_arrow": "o" * 64,
        },
        "lora_coverage_path": str(lora_coverage),
        "frozen_evidence": {
            "root": "runs/20260507T032419Z",
            "frozen_marker": "runs/20260507T032419Z/FROZEN.md",
            "write_bits_removed": True,
            "pre": {"content_sha256": "a" * 64},
            "post": {"content_sha256": "a" * 64},
        },
        "gates": {
            "sft_01_lora_config": {"ok": True},
            "sft_04_dry_run": {"ok": True},
            "sft_08_frozen": {"ok": True},
        },
        "fatal_failures": [],
    }
    manifest_path = run_root / "sft_manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def test_sft_07_d10_manifest_contains_isolated_run_artifacts_and_wandb_project(tmp_path: Path) -> None:
    from tsc_cycle.v3_gates.sft_report_v3 import evaluate_sft_manifest  # noqa: PLC0415

    manifest_path = _passing_manifest(tmp_path)
    result = evaluate_sft_manifest(manifest_path)

    assert result["ok"] is True
    assert result["run_root"].endswith("v3.0-9B-20260509T000000Z")
    assert result["wandb_project"] == "tsc-cycle-v3-9b"
    assert result["paths"]["adapter_path"].endswith("adapter")
    assert result["paths"]["dry_run_report"].endswith("dry_run_gate.json")
    assert result["paths"]["full_run_report"].endswith("full_run.json")


def test_sft_01_to_sft_08_manifest_covers_all_requirements_and_evidence(tmp_path: Path) -> None:
    from tsc_cycle.v3_gates.sft_report_v3 import evaluate_sft_manifest  # noqa: PLC0415

    manifest_path = _passing_manifest(tmp_path)
    result = evaluate_sft_manifest(manifest_path)

    assert result["requirements_covered"] == REQUIREMENTS_COVERED
    assert "SFT-08" in result["requirements_covered"]
    assert result["arrow_hashes"]["train_arrow"] == "t" * 64
    assert result["arrow_hashes"]["val_arrow"] == "v" * 64
    assert result["arrow_hashes"]["ood_val_arrow"] == "o" * 64
    assert result["lora_coverage_path"].endswith("lora_coverage.json")
    assert result["frozen_evidence"]["write_bits_removed"] is True


def test_artifact_report_fails_closed_when_adapter_exists_without_gate_evidence(tmp_path: Path) -> None:
    from tsc_cycle.v3_gates.sft_report_v3 import evaluate_sft_manifest  # noqa: PLC0415

    run_root = tmp_path / "runs" / "v3.0-9B-20260509T000000Z"
    adapter = run_root / "adapter"
    adapter.mkdir(parents=True)
    manifest_path = run_root / "sft_manifest.json"
    _write_json(manifest_path, {"adapter_path": str(adapter), "wandb_project": "tsc-cycle-v3-9b"})

    result = evaluate_sft_manifest(manifest_path)

    assert result["ok"] is False
    assert any(item["gate"] == "requirements_covered" for item in result["fatal_failures"])
    assert any(item["gate"] == "dry_run_report" for item in result["fatal_failures"])
    assert any(item["gate"] == "frozen_evidence" for item in result["fatal_failures"])


def test_full_manifest_fails_closed_without_early_stopping(tmp_path: Path) -> None:
    from tsc_cycle.student.train import write_sft_manifest  # noqa: PLC0415
    from tsc_cycle.v3_gates.sft_report_v3 import evaluate_sft_manifest  # noqa: PLC0415

    run_root = tmp_path / "runs" / "v3.0-9B-20260509T000000Z"
    adapter = run_root / "adapter"
    adapter.mkdir(parents=True)
    dry_report = run_root / "dry_run_report.json"
    lora_coverage = run_root / "reports" / "lora_coverage.json"
    grad_gate = run_root / "reports" / "full" / "grad_gate.json"
    _write_json(dry_report, {"ok": True, "full_run_allowed": True, "sample_count": 500})
    _write_json(lora_coverage, {"ok": True})
    _write_json(grad_gate, {"ok": True, "status": "pass", "observed_steps": 200, "grad_norm_p99": 1.2, "fatal_failures": []})

    manifest_path = write_sft_manifest(
        run_root=run_root,
        mode="full",
        elapsed_seconds=12.0,
        trainer_state={
            "global_step": 1000,
            "max_steps": 1000,
            "best_model_checkpoint": str(run_root / "full" / "checkpoint-800"),
            "best_metric": 0.42,
        },
        grad_gate={"ok": True, "status": "pass", "observed_steps": 200, "grad_norm_p99": 1.2, "fatal_failures": []},
        frozen_evidence={"ok": True, "write_bits_removed": True, "pre": {"content_sha256": "a" * 64}, "post": {"content_sha256": "a" * 64}},
        adapter_path=adapter,
        lora_coverage_path=lora_coverage,
        dry_run_report_path=dry_report,
        input_arrow_hashes={"train_arrow": "t" * 64, "val_arrow": "v" * 64, "ood_val_arrow": "o" * 64},
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = evaluate_sft_manifest(manifest_path)

    assert payload["early_stopping_triggered"] is False
    assert payload["stop_reason"] == "max_epochs"
    assert payload["ok"] is False
    assert result["ok"] is False
    assert any(item["gate"] == "early_stopping" for item in result["fatal_failures"])


def test_full_manifest_is_green_only_with_early_stopping_evidence(tmp_path: Path) -> None:
    from tsc_cycle.student.train import write_sft_manifest  # noqa: PLC0415
    from tsc_cycle.v3_gates.sft_report_v3 import evaluate_sft_manifest  # noqa: PLC0415

    run_root = tmp_path / "runs" / "v3.0-9B-20260509T000000Z"
    adapter = run_root / "adapter"
    best_checkpoint = run_root / "full" / "checkpoint-800"
    adapter.mkdir(parents=True)
    best_checkpoint.mkdir(parents=True)
    dry_report = run_root / "dry_run_report.json"
    lora_coverage = run_root / "reports" / "lora_coverage.json"
    grad_gate_path = run_root / "reports" / "full" / "grad_gate.json"
    _write_json(dry_report, {"ok": True, "full_run_allowed": True, "sample_count": 500})
    _write_json(lora_coverage, {"ok": True})
    _write_json(grad_gate_path, {"ok": True, "status": "pass", "observed_steps": 200, "grad_norm_p99": 1.2, "fatal_failures": []})

    manifest_path = write_sft_manifest(
        run_root=run_root,
        mode="full",
        elapsed_seconds=12.0,
        trainer_state={
            "global_step": 800,
            "max_steps": 1000,
            "best_model_checkpoint": str(best_checkpoint),
            "best_metric": 0.42,
            "epoch": 3.5,
        },
        grad_gate={"ok": True, "status": "pass", "observed_steps": 200, "grad_norm_p99": 1.2, "fatal_failures": []},
        frozen_evidence={"ok": True, "write_bits_removed": True, "pre": {"content_sha256": "a" * 64}, "post": {"content_sha256": "a" * 64}},
        adapter_path=adapter,
        lora_coverage_path=lora_coverage,
        dry_run_report_path=dry_report,
        input_arrow_hashes={"train_arrow": "t" * 64, "val_arrow": "v" * 64, "ood_val_arrow": "o" * 64},
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = evaluate_sft_manifest(manifest_path)

    assert payload["ok"] is True
    assert payload["early_stopping"] == {"patience": 3, "eval_steps": 200, "save_steps": 200, "max_epochs": 5}
    assert payload["early_stopping_triggered"] is True
    assert payload["stop_reason"] == "early_stopping"
    assert payload["best_model_checkpoint"] == str(best_checkpoint)
    assert payload["best_metric"] == 0.42
    assert result["ok"] is True
