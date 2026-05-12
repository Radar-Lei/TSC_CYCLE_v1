from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tsc_cycle.student.sft_v4 import validate_run_root

REQUIREMENTS = ["SFT4B-01", "SFT4B-02", "SFT4B-03", "SFT4B-04"]
MODEL_NAME = "Qwen/Qwen3-4B-Thinking-2507"


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _gate(ok: bool, reason: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": bool(ok), "reason": reason, "data": data or {}}


def _fail(failures: list[dict[str, str]], gate: str, reason: str) -> None:
    failures.append({"gate": gate, "reason": reason})


def _valid_run_root(run_root: Path, failures: list[dict[str, str]]) -> bool:
    try:
        validate_run_root(run_root)
    except ValueError as exc:
        _fail(failures, "run_root", str(exc))
        return False
    return True


def _adapter_hash(adapter: Path) -> str | None:
    return _sha256_file(adapter / "adapter_model.safetensors")


def evaluate_phase9_report(run_root: str | Path, out: str | Path | None = None) -> dict[str, Any]:
    root = Path(run_root)
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    gates: dict[str, Any] = {}

    root_ok = _valid_run_root(root, failures)
    gates["run_root"] = _gate(root_ok, None if root_ok else "invalid Phase 9 run root", {"run_root": str(root)})
    training_path = root / "training_report.json"
    training = _load_json(training_path)
    smoke_path = Path(training.get("smoke_report_path") or root / "smoke_report.json")
    smoke = _load_json(smoke_path)
    handoff_path = root / "phase10_handoff.json"
    handoff = _load_json(handoff_path)

    model_ok = training.get("model_name") == MODEL_NAME
    gates["model_config"] = _gate(model_ok, None if model_ok else "model_name is not locked Qwen3-4B", {"model_name": training.get("model_name")})
    if not model_ok:
        _fail(failures, "model_config", "model_name is not locked Qwen3-4B")

    loss_curve = training.get("loss_curve") if isinstance(training.get("loss_curve"), list) else []
    loss_ok = bool(loss_curve)
    gates["loss_curve"] = _gate(loss_ok, None if loss_ok else "loss_curve is missing or empty", {"points": len(loss_curve)})
    if not loss_ok:
        _fail(failures, "loss_curve", "loss_curve is missing or empty")

    duration = training.get("duration_seconds")
    duration_ok = isinstance(duration, (int, float)) and duration > 0
    gates["duration_seconds"] = _gate(duration_ok, None if duration_ok else "duration_seconds must be > 0", {"duration_seconds": duration})
    if not duration_ok:
        _fail(failures, "duration_seconds", "duration_seconds must be > 0")

    vram = training.get("vram_peak_gb")
    vram_ok = isinstance(vram, (int, float)) and vram >= 0
    gates["vram_peak_gb"] = _gate(vram_ok, None if vram_ok else "vram_peak_gb is missing", {"vram_peak_gb": vram})
    if not vram_ok:
        _fail(failures, "vram_peak_gb", "vram_peak_gb is missing")

    adapter = Path(training.get("adapter_path") or root / "adapter")
    adapter_hash = _adapter_hash(adapter)
    adapter_ok = adapter_hash is not None and training.get("adapter_sha256") == adapter_hash and (adapter / "adapter_config.json").exists()
    gates["adapter_hash"] = _gate(adapter_ok, None if adapter_ok else "adapter hash mismatch or adapter files missing", {"expected": training.get("adapter_sha256"), "actual": adapter_hash})
    if not adapter_ok:
        _fail(failures, "adapter_hash", "adapter hash mismatch or adapter files missing")

    data_manifest = Path(training.get("data_manifest_path") or root / "phase8_data_manifest.json")
    data_hash = _sha256_file(data_manifest)
    data_ok = data_hash is not None and training.get("data_manifest_sha256") == data_hash
    gates["data_manifest_hash"] = _gate(data_ok, None if data_ok else "data manifest hash mismatch or missing", {"expected": training.get("data_manifest_sha256"), "actual": data_hash})
    if not data_ok:
        _fail(failures, "data_manifest_hash", "data manifest hash mismatch or missing")

    phase8_hashes = training.get("phase8_artifact_hashes") if isinstance(training.get("phase8_artifact_hashes"), dict) else {}
    phase8_ok = bool(phase8_hashes)
    gates["phase8_artifact_hashes"] = _gate(phase8_ok, None if phase8_ok else "phase8 artifact hashes are missing", {"count": len(phase8_hashes)})
    if not phase8_ok:
        _fail(failures, "phase8_artifact_hashes", "phase8 artifact hashes are missing")

    covered = set(training.get("requirements_covered", []))
    requirements_ok = set(REQUIREMENTS) <= covered
    gates["requirements_covered"] = _gate(requirements_ok, None if requirements_ok else "SFT4B coverage incomplete", {"covered": sorted(covered)})
    if not requirements_ok:
        _fail(failures, "requirements_covered", "SFT4B coverage incomplete")

    smoke_ok = smoke.get("ok") is True and (smoke.get("next_phase_allowed") is True or smoke.get("full_train_allowed") is True) and "SFT4B-02" in smoke.get("requirements_covered", [])
    gates["pretrain_smoke"] = _gate(smoke_ok, None if smoke_ok else "pretrain smoke report is not green", {"path": str(smoke_path)})
    if not smoke_ok:
        warnings.append({"gate": "pretrain_smoke", "warning": "pretrain smoke report not found or not green"})

    handoff_ok = (
        handoff.get("next_phase_allowed") is True
        and handoff.get("adapter_path") == str(adapter)
        and handoff.get("run_root") == str(root)
        and handoff.get("report_path") == str(training_path)
        and handoff.get("adapter_sha256") == adapter_hash
        and handoff.get("data_manifest_sha256") == data_hash
    )
    gates["phase10_handoff"] = _gate(handoff_ok, None if handoff_ok else "Phase 10 handoff is incomplete or mismatched", handoff)
    if not handoff_ok:
        _fail(failures, "phase10_handoff", "Phase 10 handoff is incomplete or mismatched")

    ok = not failures
    artifact_manifest = {
        "paths": {
            "run_root": str(root),
            "adapter": str(adapter),
            "report": str(training_path),
            "data_manifest": str(data_manifest),
            "phase10_handoff": str(handoff_path),
        },
        "sha256": {
            "adapter_sha256": adapter_hash,
            "data_manifest_sha256": data_hash,
            "training_report": _sha256_file(training_path),
            "phase10_handoff": _sha256_file(handoff_path),
        },
    }
    report = {
        "ok": ok,
        "next_phase_allowed": ok,
        "requirements_covered": [req for req in REQUIREMENTS if req in covered] if ok else [req for req in REQUIREMENTS if req in covered],
        "gates": gates,
        "fatal_failures": failures,
        "warnings": warnings,
        "artifact_manifest": artifact_manifest,
        "run_root": str(root),
        "adapter_path": str(adapter),
    }
    if out is not None:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate v4 Phase 9 SFT handoff report")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--out", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = evaluate_phase9_report(args.run_root, out=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
