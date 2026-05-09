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
    dry_report = run_root / "dry_run_report.json"
    full_report = run_root / "reports" / "full_run.json"
    adapter = run_root / "adapter"
    adapter_file = adapter / "adapter_model.safetensors"
    best_checkpoint = run_root / "full" / "checkpoint-800"
    best_checkpoint_file = best_checkpoint / "adapter_model.safetensors"
    lora_coverage = run_root / "reports" / "lora_coverage.json"
    grad_gate = run_root / "reports" / "full" / "grad_gate.json"
    phase3_manifest = tmp_path / "data" / "splits" / "v3" / "manifest.json"
    frozen_root = tmp_path / "runs" / "20260507T032419Z"
    frozen_marker = frozen_root / "FROZEN.md"
    train_arrow = tmp_path / "data" / "tokenized" / "v3" / "train.arrow"
    val_arrow = tmp_path / "data" / "tokenized" / "v3" / "val.arrow"
    ood_arrow = tmp_path / "data" / "tokenized" / "v3" / "ood_val.arrow"

    adapter.mkdir(parents=True)
    best_checkpoint.mkdir(parents=True)
    lora_coverage.parent.mkdir(parents=True, exist_ok=True)
    frozen_root.mkdir(parents=True, exist_ok=True)
    train_arrow.parent.mkdir(parents=True, exist_ok=True)
    adapter_file.write_text("adapter", encoding="utf-8")
    best_checkpoint_file.write_text("best", encoding="utf-8")
    frozen_marker.write_text("frozen", encoding="utf-8")
    train_arrow.write_text("train", encoding="utf-8")
    val_arrow.write_text("val", encoding="utf-8")
    ood_arrow.write_text("ood", encoding="utf-8")

    _write_json(
        dry_report,
        {
            "ok": True,
            "full_run_allowed": True,
            "sample_count": 500,
            "ood_hard_constraint_pass_rate": 0.96,
            "native_think_leak_count": 0,
            "run_safe_required": True,
            "wrapper_path": "scripts/run_v3_phase4_dry_run.sh",
        },
    )
    _write_json(
        full_report,
        {
            "ok": True,
            "early_stopping_triggered": True,
            "stop_reason": "early_stopping",
            "best_model_checkpoint": str(best_checkpoint),
            "best_adapter": str(adapter),
        },
    )
    _write_json(
        lora_coverage,
        {
            "ok": True,
            "r": 64,
            "alpha": 64,
            "dropout": 0.0,
            "target_modules": "all-linear",
            "expected_gated_deltanet_layers": 24,
            "observed_gated_deltanet_layers": 24,
            "expected_full_attention_layers": 8,
            "observed_full_attention_layers": 8,
            "projection_coverage": {"gated_deltanet": "all", "full_attention": "all"},
        },
    )
    _write_json(grad_gate, {"ok": True, "losses_finite": True, "grad_norm_p99": 1.2, "observed_steps": 200})
    _write_json(
        phase3_manifest,
        {
            "ok": True,
            "tokenized_paths": {"train": str(train_arrow), "val": str(val_arrow), "ood_val": str(ood_arrow)},
            "artifact_manifest": {
                "paths": {"train_arrow": str(train_arrow), "val_arrow": str(val_arrow), "ood_val_arrow": str(ood_arrow)}
            },
        },
    )
    manifest = {
        "ok": True,
        "mode": "full",
        "requirements_covered": REQUIREMENTS_COVERED,
        "run_root": str(run_root),
        "wandb_project": "tsc-cycle-v3-9b",
        "dry_run_report": str(dry_report),
        "full_run_report": str(full_report),
        "adapter_path": str(adapter),
        "grad_gate_path": str(grad_gate),
        "arrow_hashes": {
            "train_arrow": "t" * 64,
            "val_arrow": "v" * 64,
            "ood_val_arrow": "o" * 64,
        },
        "lora_coverage_path": str(lora_coverage),
        "early_stopping": {"patience": 3, "eval_steps": 200, "save_steps": 200, "max_epochs": 5},
        "early_stopping_triggered": True,
        "stop_reason": "early_stopping",
        "best_model_checkpoint": str(best_checkpoint),
        "frozen_evidence": {
            "root": str(frozen_root),
            "frozen_marker": str(frozen_marker),
            "write_bits_removed": True,
            "pre": {"content_sha256": "a" * 64},
            "post": {"content_sha256": "a" * 64},
        },
        "training_args": {
            "learning_rate": 1e-4,
            "lr_scheduler_type": "cosine",
            "warmup_ratio": 0.03,
            "max_grad_norm": 0.5,
            "optim": "adamw_torch_fused",
            "per_device_train_batch_size": 1,
            "gradient_accumulation_steps": 16,
            "packing": False,
            "gradient_checkpointing_kwargs": {"use_reentrant": False},
            "num_train_epochs": 5,
            "eval_steps": 200,
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
    from tsc_cycle.v3_gates.sft_report_v3 import evaluate_gates  # noqa: PLC0415

    manifest_path = _passing_manifest(tmp_path)
    result = evaluate_gates(manifest_path.parent)

    assert result["ok"] is True
    assert result["next_phase_allowed"] is True
    assert result["run_root"].endswith("v3.0-9B-20260509T000000Z")
    assert result["wandb_project"] == "tsc-cycle-v3-9b"
    assert result["artifact_manifest"]["paths"]["adapter_path"].endswith("adapter")
    assert result["artifact_manifest"]["paths"]["dry_run_report"].endswith("dry_run_report.json")
    assert result["artifact_manifest"]["paths"]["full_run_report"].endswith("full_run.json")
    assert result["artifact_manifest"]["sha256"]["adapter_file"]


def test_sft_01_to_sft_08_manifest_covers_all_requirements_and_evidence(tmp_path: Path) -> None:
    from tsc_cycle.v3_gates.sft_report_v3 import evaluate_gates  # noqa: PLC0415

    manifest_path = _passing_manifest(tmp_path)
    result = evaluate_gates(manifest_path.parent)

    assert result["requirements_covered"] == REQUIREMENTS_COVERED
    assert "SFT-08" in result["requirements_covered"]
    assert result["fatal_failures"] == []
    assert result["gates"]["SFT-01"]["ok"] is True
    assert result["gates"]["SFT-08"]["ok"] is True
    assert result["artifact_manifest"]["paths"]["train_arrow"].endswith("train.arrow")
    assert result["artifact_manifest"]["paths"]["val_arrow"].endswith("val.arrow")
    assert result["artifact_manifest"]["paths"]["ood_val_arrow"].endswith("ood_val.arrow")
    assert result["artifact_manifest"]["paths"]["lora_coverage"].endswith("lora_coverage.json")
    assert result["artifact_manifest"]["paths"]["frozen_marker"].endswith("FROZEN.md")
    assert result["artifact_manifest"]["sha256"]["train_arrow"]
    assert result["artifact_manifest"]["sha256"]["dry_run_report"]
    assert result["artifact_manifest"]["sha256"]["full_run_report"]
    assert result["artifact_manifest"]["sha256"]["lora_coverage"]
    assert result["artifact_manifest"]["sha256"]["frozen_marker"]


def test_artifact_report_fails_closed_when_adapter_exists_without_gate_evidence(tmp_path: Path) -> None:
    from tsc_cycle.v3_gates.sft_report_v3 import evaluate_gates, evaluate_sft_manifest  # noqa: PLC0415

    run_root = tmp_path / "runs" / "v3.0-9B-20260509T000000Z"
    adapter = run_root / "adapter"
    adapter.mkdir(parents=True)
    manifest_path = run_root / "sft_manifest.json"
    _write_json(manifest_path, {"adapter_path": str(adapter), "wandb_project": "tsc-cycle-v3-9b"})

    legacy_result = evaluate_sft_manifest(manifest_path)
    result = evaluate_gates(run_root)

    assert legacy_result["ok"] is False
    assert result["ok"] is False
    assert result["next_phase_allowed"] is False
    assert any(item["gate"] == "requirements_covered" for item in result["fatal_failures"])
    assert any(item["gate"] == "SFT-04" for item in result["fatal_failures"])
    assert any(item["gate"] == "SFT-08" for item in result["fatal_failures"])


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
    assert any(item["gate"] in {"early_stopping", "SFT-05"} for item in result["fatal_failures"])


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


def test_aggregate_report_fails_if_any_sft_requirement_is_missing(tmp_path: Path) -> None:
    from tsc_cycle.v3_gates.sft_report_v3 import evaluate_gates  # noqa: PLC0415

    manifest_path = _passing_manifest(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["requirements_covered"] = REQUIREMENTS_COVERED[:-1]
    _write_json(manifest_path, payload)

    result = evaluate_gates(manifest_path.parent)

    assert result["ok"] is False
    assert result["next_phase_allowed"] is False
    assert "SFT-08" not in result["requirements_covered"]
    assert any(item["gate"] == "requirements_covered" for item in result["fatal_failures"])


def test_aggregate_report_fails_if_dry_run_report_is_absent_or_not_allowing_full_run(tmp_path: Path) -> None:
    from tsc_cycle.v3_gates.sft_report_v3 import evaluate_gates  # noqa: PLC0415

    manifest_path = _passing_manifest(tmp_path)
    result = evaluate_gates(manifest_path.parent)
    assert result["ok"] is True

    dry_path = Path(result["artifact_manifest"]["paths"]["dry_run_report"])
    _write_json(dry_path, {"ok": True, "full_run_allowed": False, "sample_count": 500})
    denied = evaluate_gates(manifest_path.parent)
    assert denied["ok"] is False
    assert any(item["gate"] == "SFT-04" for item in denied["fatal_failures"])

    dry_path.unlink()
    missing = evaluate_gates(manifest_path.parent)
    assert missing["ok"] is False
    assert missing["next_phase_allowed"] is False
    assert any(item["gate"] == "SFT-04" for item in missing["fatal_failures"])


def test_aggregate_report_fails_without_full_manifest_adapter_best_checkpoint_or_early_stop(tmp_path: Path) -> None:
    from tsc_cycle.v3_gates.sft_report_v3 import evaluate_gates  # noqa: PLC0415

    manifest_path = _passing_manifest(tmp_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["ok"] = False
    payload["adapter_path"] = str(manifest_path.parent / "missing-adapter")
    payload["best_model_checkpoint"] = ""
    payload["early_stopping_triggered"] = False
    payload["stop_reason"] = "max_epochs"
    _write_json(manifest_path, payload)

    result = evaluate_gates(manifest_path.parent)

    assert result["ok"] is False
    assert result["next_phase_allowed"] is False
    assert any(item["gate"] == "SFT-05" for item in result["fatal_failures"])
    assert any("adapter" in item["reason"] for item in result["fatal_failures"])
    assert any("early_stopping" in item["reason"] for item in result["fatal_failures"])


def test_sft_01_coverage_contract_requires_expected_layer_counts_and_projection_evidence(tmp_path: Path) -> None:
    from tsc_cycle.v3_gates.sft_report_v3 import evaluate_gates  # noqa: PLC0415

    manifest_path = _passing_manifest(tmp_path)
    ok_report = evaluate_gates(manifest_path.parent)
    assert ok_report["gates"]["SFT-01"]["data"]["expected_gated_deltanet_layers"] == 24
    assert ok_report["gates"]["SFT-01"]["data"]["expected_full_attention_layers"] == 8
    assert ok_report["gates"]["SFT-01"]["data"]["projection_coverage"]

    lora_path = Path(ok_report["artifact_manifest"]["paths"]["lora_coverage"])
    coverage = json.loads(lora_path.read_text(encoding="utf-8"))
    coverage["expected_gated_deltanet_layers"] = 23
    _write_json(lora_path, coverage)

    result = evaluate_gates(manifest_path.parent)

    assert result["ok"] is False
    assert result["next_phase_allowed"] is False
    assert any(item["gate"] == "SFT-01" for item in result["fatal_failures"])


def test_aggregate_report_cli_writes_report_with_adapter_handoff(tmp_path: Path) -> None:
    from tsc_cycle.v3_gates.sft_report_v3 import main  # noqa: PLC0415

    manifest_path = _passing_manifest(tmp_path)
    out = manifest_path.parent / "phase4_sft_report.json"

    exit_code = main(["--run-dir", str(manifest_path.parent), "--out", str(out)])

    assert exit_code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["next_phase_allowed"] is True
    assert payload["artifact_manifest"]["paths"]["adapter_path"].endswith("adapter")
    assert payload["requirements_covered"] == REQUIREMENTS_COVERED
