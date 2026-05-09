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
