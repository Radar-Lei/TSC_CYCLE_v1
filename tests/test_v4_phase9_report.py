from __future__ import annotations

import hashlib
import json
from pathlib import Path

REQUIREMENTS = ["SFT4B-01", "SFT4B-02", "SFT4B-03", "SFT4B-04"]


def _contract():
    from tsc_cycle.v4_gates.phase9_report import evaluate_phase9_report  # noqa: PLC0415

    return evaluate_phase9_report


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _green_run_root(tmp_path: Path) -> Path:
    run_root = tmp_path / "runs" / "v4.0-4B-20260510T010203Z"
    adapter_dir = run_root / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    (adapter_dir / "adapter_model.safetensors").write_bytes(b"phase9-adapter")
    (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
    phase8_manifest = run_root / "phase8_data_manifest.json"
    _write_json(phase8_manifest, {"source_manifest_sha256": "a" * 64, "phase8_gate_report_sha256": "b" * 64})
    smoke_report = _write_json(
        run_root / "smoke_report.json",
        {"ok": True, "next_phase_allowed": True, "requirements_covered": ["SFT4B-02"], "fatal_failures": []},
    )
    training_report = _write_json(
        run_root / "training_report.json",
        {
            "ok": True,
            "model_name": "Qwen/Qwen3-4B-Thinking-2507",
            "run_root": str(run_root),
            "loss_curve": [{"step": 1, "loss": 1.5}, {"step": 2, "loss": 1.2}],
            "duration_seconds": 120.0,
            "vram_peak_gb": 46.5,
            "adapter_path": str(adapter_dir),
            "adapter_sha256": _sha256(adapter_dir / "adapter_model.safetensors"),
            "data_manifest_path": str(phase8_manifest),
            "data_manifest_sha256": _sha256(phase8_manifest),
            "phase8_artifact_hashes": {"phase8_gate_report.json": "c" * 64, "train.arrow": "d" * 64, "val.arrow": "e" * 64, "ood_val.arrow": "f" * 64},
            "requirements_covered": REQUIREMENTS,
            "smoke_report_path": str(smoke_report),
        },
    )
    _write_json(
        run_root / "phase10_handoff.json",
        {
            "adapter_path": str(adapter_dir),
            "run_root": str(run_root),
            "report_path": str(training_report),
            "adapter_sha256": _sha256(adapter_dir / "adapter_model.safetensors"),
            "data_manifest_sha256": _sha256(phase8_manifest),
            "next_phase_allowed": True,
        },
    )
    return run_root


def test_phase9_report_passes_only_with_complete_training_evidence_and_handoff(tmp_path: Path) -> None:
    run_root = _green_run_root(tmp_path)
    out = tmp_path / "artifacts" / "v4" / "phase9" / "phase9_gate_report.json"

    report = _contract()(run_root, out=out)

    assert report["ok"] is True
    assert report["next_phase_allowed"] is True
    assert report["requirements_covered"] == REQUIREMENTS
    assert report["gates"]["loss_curve"]["ok"] is True
    assert report["gates"]["duration_seconds"]["ok"] is True
    assert report["gates"]["vram_peak_gb"]["ok"] is True
    assert report["gates"]["adapter_hash"]["ok"] is True
    assert report["gates"]["data_manifest_hash"]["ok"] is True
    assert report["gates"]["phase8_artifact_hashes"]["ok"] is True
    assert report["gates"]["requirements_covered"]["ok"] is True
    assert report["gates"]["phase10_handoff"]["ok"] is True
    assert out.exists()
    assert report["artifact_manifest"]["paths"]["adapter"] == str(run_root / "adapter")
    assert report["artifact_manifest"]["paths"]["run_root"] == str(run_root)
    assert report["artifact_manifest"]["paths"]["report"] == str(run_root / "training_report.json")
    assert report["artifact_manifest"]["sha256"]["adapter_sha256"] == _sha256(run_root / "adapter" / "adapter_model.safetensors")
    assert report["artifact_manifest"]["sha256"]["data_manifest_sha256"] == _sha256(run_root / "phase8_data_manifest.json")


def _assert_blocks(tmp_path: Path, mutator, gate: str) -> None:
    run_root = _green_run_root(tmp_path)
    payload_path = run_root / "training_report.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    mutator(payload, run_root)
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    report = _contract()(run_root)
    assert report["ok"] is False
    assert report["next_phase_allowed"] is False
    assert any(failure["gate"] == gate for failure in report["fatal_failures"])


def test_phase9_report_fails_closed_for_missing_training_metrics(tmp_path: Path) -> None:
    _assert_blocks(tmp_path, lambda payload, _root: payload.__setitem__("loss_curve", []), "loss_curve")
    _assert_blocks(tmp_path, lambda payload, _root: payload.__setitem__("duration_seconds", 0), "duration_seconds")
    _assert_blocks(tmp_path, lambda payload, _root: payload.__setitem__("vram_peak_gb", None), "vram_peak_gb")


def test_phase9_report_fails_closed_for_hash_mismatch_or_missing_phase8_hashes(tmp_path: Path) -> None:
    _assert_blocks(tmp_path, lambda payload, _root: payload.__setitem__("adapter_sha256", "0" * 64), "adapter_hash")
    _assert_blocks(tmp_path, lambda payload, _root: payload.__setitem__("data_manifest_sha256", "0" * 64), "data_manifest_hash")
    _assert_blocks(tmp_path, lambda payload, _root: payload.__setitem__("phase8_artifact_hashes", {}), "phase8_artifact_hashes")


def test_phase9_report_fails_closed_for_incomplete_sft4b_coverage(tmp_path: Path) -> None:
    _assert_blocks(tmp_path, lambda payload, _root: payload.__setitem__("requirements_covered", ["SFT4B-01", "SFT4B-02", "SFT4B-03"]), "requirements_covered")


def test_phase9_report_fails_closed_for_bad_phase10_handoff(tmp_path: Path) -> None:
    run_root = _green_run_root(tmp_path)
    handoff = run_root / "phase10_handoff.json"
    handoff_payload = json.loads(handoff.read_text(encoding="utf-8"))
    handoff_payload["next_phase_allowed"] = False
    handoff.write_text(json.dumps(handoff_payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    report = _contract()(run_root)
    assert report["ok"] is False
    assert report["next_phase_allowed"] is False
    assert any(failure["gate"] == "phase10_handoff" for failure in report["fatal_failures"])


def test_phase9_report_rejects_non_v4_or_frozen_run_roots(tmp_path: Path) -> None:
    for run_root in [tmp_path / "runs" / "v3.0-9B-20260510T010203Z", Path("/home/samuel/TSC_CYCLE/runs/20260507T032419Z")]:
        report = _contract()(run_root)
        assert report["ok"] is False
        assert report["next_phase_allowed"] is False
        assert any(failure["gate"] == "run_root" for failure in report["fatal_failures"])
