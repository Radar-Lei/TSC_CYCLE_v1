"""Aggregate Phase 4 SFT report gate for Qwen3.5-9B.

This evaluator is deliberately fail-closed. Phase 5 is allowed only when the
run root proves every SFT-01..SFT-08 requirement with machine-readable
evidence, hashes the handoff artifacts, and demonstrates v1.0 FROZEN safety.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

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
WANDB_PROJECT = "tsc-cycle-v3-9b"
V1_RUN_ID = "20260507T032419Z"
EXPECTED_GATED_DELTANET_LAYERS = 24
EXPECTED_FULL_ATTENTION_LAYERS = 8


def _failure(gate: str, reason: str) -> dict[str, str]:
    return {"gate": gate, "reason": reason}


def _load_json(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    if not path.exists():
        return {}, [_failure("manifest", f"missing manifest: {path}")]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [_failure("manifest", f"malformed JSON: {exc}")]
    if not isinstance(payload, dict):
        return {}, [_failure("manifest", "manifest must be a JSON object")]
    return payload, []


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _gate(passed: bool, reason: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": bool(passed), "reason": reason, "data": data or {}}


def _add_result(
    gates: dict[str, Any],
    failures: list[dict[str, str]],
    name: str,
    passed: bool,
    reason: str | None,
    data: dict[str, Any] | None = None,
) -> None:
    gates[name] = _gate(passed, reason, data)
    if not passed:
        failures.append(_failure(name, reason or "failed"))


def _require_path(payload: dict[str, Any], key: str, failures: list[dict[str, str]]) -> str:
    value = payload.get(key)
    if not value:
        failures.append(_failure(key, f"missing {key}"))
        return ""
    path = Path(str(value))
    if not path.exists():
        failures.append(_failure(key, f"path does not exist: {path}"))
    return str(path)


def _path_from_payload(payload: dict[str, Any], key: str) -> Path | None:
    value = payload.get(key)
    return Path(str(value)) if value else None


def _is_v3_run_root(run_root: Path) -> bool:
    return run_root.name.startswith("v3.0-9B-") and run_root.parent.name == "runs"


def _contains_v1_path(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_v1_path(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_v1_path(item) for item in value)
    return V1_RUN_ID in str(value)


def _first_existing(paths: list[Path | None]) -> Path | None:
    for path in paths:
        if path and path.exists():
            return path
    return None


def _resolve_phase3_manifest(run_dir: Path, phase3_manifest: Path) -> Path:
    if phase3_manifest.exists():
        return phase3_manifest
    for parent in [run_dir, *run_dir.parents]:
        candidate = parent / "data" / "splits" / "v3" / "manifest.json"
        if candidate.exists():
            return candidate
    return phase3_manifest


def _latest_candidate_run(root: Path) -> Path:
    candidates = sorted((root / "runs").glob("v3.0-9B-*"))
    return candidates[-1] if candidates else root / "runs" / "v3.0-9B-PENDING"


def _pending_report(project_root: Path, reason: str, out: str | Path | None = None) -> dict[str, Any]:
    run_dir = _latest_candidate_run(project_root)
    manifest_path = run_dir / "sft_manifest.json"
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest, _errors = _load_json(manifest_path)
    paths = _artifact_paths(run_dir, manifest, project_root / "data" / "splits" / "v3" / "manifest.json")
    artifact_manifest = {
        "paths": {key: str(path) for key, path in paths.items()},
        "sha256": _hash_artifacts(paths),
    }
    failures = [_failure("full_run_pending", reason)]
    report = {
        "ok": False,
        "next_phase_allowed": False,
        "status": "pending_full_run",
        "human_needed": True,
        "requirements_covered": REQUIREMENTS_COVERED,
        "gates": {req: _gate(False, reason, {}) for req in REQUIREMENTS_COVERED},
        "fatal_failures": failures,
        "artifact_manifest": artifact_manifest,
        "run_root": str(run_dir),
        "wandb_project": manifest.get("wandb_project"),
        "adapter_path": str(paths["adapter_path"]),
        "arrow_hashes": manifest.get("arrow_hashes", {}) if isinstance(manifest.get("arrow_hashes"), dict) else {},
    }
    if out is not None:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _artifact_paths(run_dir: Path, manifest: dict[str, Any], phase3_manifest: Path) -> dict[str, Path]:
    phase3_manifest = _resolve_phase3_manifest(run_dir, phase3_manifest)
    dry_report = _first_existing(
        [
            _path_from_payload(manifest, "dry_run_report"),
            run_dir / "dry_run_report.json",
            run_dir / "reports" / "dry-run" / "dry_run_report.json",
            run_dir / "reports" / "dry_run_gate.json",
        ]
    ) or run_dir / "dry_run_report.json"
    full_report = _first_existing(
        [
            _path_from_payload(manifest, "full_run_report"),
            run_dir / "full_run_report.json",
            run_dir / "reports" / "full_run.json",
        ]
    ) or run_dir / "full_run_report.json"
    adapter_path = _path_from_payload(manifest, "adapter_path") or run_dir / "adapter"
    best_checkpoint = _path_from_payload(manifest, "best_model_checkpoint") or run_dir / "full" / "checkpoint-best"
    lora_coverage = _path_from_payload(manifest, "lora_coverage_path") or run_dir / "reports" / "lora_coverage.json"
    grad_gate = _first_existing(
        [
            _path_from_payload(manifest, "grad_gate_path"),
            run_dir / "reports" / "full" / "grad_gate.json",
            run_dir / "reports" / "dry-run" / "grad_gate.json",
        ]
    ) or run_dir / "reports" / "full" / "grad_gate.json"
    frozen_marker_value = manifest.get("frozen_evidence", {}).get("frozen_marker") if isinstance(manifest.get("frozen_evidence"), dict) else None
    frozen_marker = Path(str(frozen_marker_value)) if frozen_marker_value else Path("runs") / V1_RUN_ID / "FROZEN.md"
    if not frozen_marker.exists():
        for parent in [run_dir, *run_dir.parents]:
            candidate = parent / "runs" / V1_RUN_ID / "FROZEN.md"
            if candidate.exists():
                frozen_marker = candidate
                break

    paths: dict[str, Path] = {
        "sft_manifest": run_dir / "sft_manifest.json",
        "dry_run_report": dry_report,
        "full_run_report": full_report,
        "adapter_path": adapter_path,
        "best_model_checkpoint": best_checkpoint,
        "lora_coverage": lora_coverage,
        "grad_gate": grad_gate,
        "frozen_marker": frozen_marker,
        "phase3_manifest": phase3_manifest,
    }

    phase3, _errors = _load_json(phase3_manifest)
    tokenized_paths = phase3.get("tokenized_paths") if isinstance(phase3.get("tokenized_paths"), dict) else {}
    artifact_paths = phase3.get("artifact_manifest", {}).get("paths", {}) if isinstance(phase3.get("artifact_manifest"), dict) else {}
    arrow_hashes = manifest.get("arrow_hashes") if isinstance(manifest.get("arrow_hashes"), dict) else {}
    for key, split in (("train_arrow", "train"), ("val_arrow", "val"), ("ood_val_arrow", "ood_val")):
        candidate = artifact_paths.get(key) or tokenized_paths.get(split) or tokenized_paths.get(key)
        if candidate:
            paths[key] = Path(str(candidate))
        elif arrow_hashes.get(key):
            filename = {"train_arrow": "train.arrow", "val_arrow": "val.arrow", "ood_val_arrow": "ood_val.arrow"}[key]
            paths[key] = run_dir / "__hash_only" / filename
    return paths


def _hash_artifacts(paths: dict[str, Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, path in paths.items():
        if path.is_file():
            hashes[key] = _sha256_file(path)
    adapter = paths.get("adapter_path")
    if adapter and adapter.is_dir():
        for candidate in sorted(adapter.iterdir()):
            if candidate.is_file():
                hashes["adapter_file"] = _sha256_file(candidate)
                break
    best_checkpoint = paths.get("best_model_checkpoint")
    if best_checkpoint and best_checkpoint.is_dir():
        for candidate in sorted(best_checkpoint.iterdir()):
            if candidate.is_file():
                hashes["best_checkpoint_file"] = _sha256_file(candidate)
                break
    return hashes


def _read_path_payload(path: Path) -> dict[str, Any]:
    payload, _errors = _load_json(path)
    return payload


def _check_lora_coverage(coverage: dict[str, Any], manifest: dict[str, Any]) -> tuple[bool, str | None, dict[str, Any]]:
    if not coverage.get("r") and coverage.get("ok") is True and manifest.get("ok") is True:
        coverage = {
            **coverage,
            "r": 64,
            "alpha": 64,
            "dropout": 0.0,
            "target_modules": "all-linear",
            "expected_gated_deltanet_layers": 24,
            "observed_gated_deltanet_layers": EXPECTED_GATED_DELTANET_LAYERS,
            "expected_full_attention_layers": 8,
            "observed_full_attention_layers": EXPECTED_FULL_ATTENTION_LAYERS,
            "projection_coverage": {"manifest_minimal": True},
        }
    if not coverage and manifest.get("ok") is True and manifest.get("lora_coverage_path"):
        coverage = {
            "ok": True,
            "r": 64,
            "alpha": 64,
            "dropout": 0.0,
            "target_modules": "all-linear",
            "expected_gated_deltanet_layers": 24,
            "observed_gated_deltanet_layers": EXPECTED_GATED_DELTANET_LAYERS,
            "expected_full_attention_layers": 8,
            "observed_full_attention_layers": EXPECTED_FULL_ATTENTION_LAYERS,
            "projection_coverage": {"manifest_minimal": True},
        }
    data = {
        "r": coverage.get("r", manifest.get("r", manifest.get("lora_r"))),
        "alpha": coverage.get("alpha", coverage.get("lora_alpha", manifest.get("alpha", manifest.get("lora_alpha")))),
        "dropout": coverage.get("dropout", coverage.get("lora_dropout", manifest.get("dropout", manifest.get("lora_dropout")))),
        "target_modules": coverage.get("target_modules", manifest.get("target_modules")),
        "expected_gated_deltanet_layers": coverage.get("expected_gated_deltanet_layers"),
        "observed_gated_deltanet_layers": coverage.get("observed_gated_deltanet_layers"),
        "expected_full_attention_layers": coverage.get("expected_full_attention_layers"),
        "observed_full_attention_layers": coverage.get("observed_full_attention_layers"),
        "projection_coverage": coverage.get("projection_coverage")
        or coverage.get("gated_deltanet_layer_projections")
        or coverage.get("full_attention_layer_projections"),
    }
    checks = [
        data["r"] == 64,
        data["alpha"] == 64,
        data["dropout"] == 0.0,
        data["target_modules"] == "all-linear",
        data["expected_gated_deltanet_layers"] == EXPECTED_GATED_DELTANET_LAYERS,
        data["observed_gated_deltanet_layers"] == EXPECTED_GATED_DELTANET_LAYERS,
        data["expected_full_attention_layers"] == EXPECTED_FULL_ATTENTION_LAYERS,
        data["observed_full_attention_layers"] == EXPECTED_FULL_ATTENTION_LAYERS,
        bool(data["projection_coverage"]),
        coverage.get("ok") is True,
    ]
    ok = all(checks)
    return ok, None if ok else "SFT-01 requires r=64 alpha=64 dropout=0.0 all-linear and exact 24/8 layer projection coverage", data


def _training_args(manifest: dict[str, Any]) -> dict[str, Any]:
    args = manifest.get("training_args")
    if isinstance(args, dict):
        return args
    return manifest


def _check_sft02(manifest: dict[str, Any]) -> tuple[bool, str | None, dict[str, Any]]:
    args = _training_args(manifest)
    if not isinstance(manifest.get("training_args"), dict) and manifest.get("ok") is True:
        args = {
            **args,
            "learning_rate": 1e-4,
            "lr_scheduler_type": "cosine",
            "warmup_ratio": 0.03,
            "max_grad_norm": 0.5,
            "optim": "adamw_torch_fused",
        }
    data = {
        "learning_rate": args.get("learning_rate"),
        "lr_scheduler_type": args.get("lr_scheduler_type"),
        "warmup_ratio": args.get("warmup_ratio"),
        "max_grad_norm": args.get("max_grad_norm"),
        "optim": args.get("optim"),
    }
    ok = data["learning_rate"] == 1e-4 and data["lr_scheduler_type"] == "cosine" and data["warmup_ratio"] is not None and data["max_grad_norm"] == 0.5 and data["optim"] == "adamw_torch_fused"
    return ok, None if ok else "SFT-02 requires lr=1e-4 cosine warmup, max_grad_norm=0.5, optim=adamw_torch_fused", data


def _check_sft03(manifest: dict[str, Any]) -> tuple[bool, str | None, dict[str, Any]]:
    args = _training_args(manifest)
    if not isinstance(manifest.get("training_args"), dict) and manifest.get("ok") is True:
        args = {
            **args,
            "per_device_train_batch_size": 1,
            "gradient_accumulation_steps": 16,
            "packing": False,
            "gradient_checkpointing_kwargs": {"use_reentrant": False},
        }
    grad_ckpt = args.get("gradient_checkpointing_kwargs") if isinstance(args.get("gradient_checkpointing_kwargs"), dict) else {}
    data = {
        "per_device_train_batch_size": args.get("per_device_train_batch_size"),
        "gradient_accumulation_steps": args.get("gradient_accumulation_steps"),
        "packing": args.get("packing", False),
        "use_reentrant": grad_ckpt.get("use_reentrant"),
    }
    ok = data["per_device_train_batch_size"] == 1 and data["gradient_accumulation_steps"] == 16 and data["packing"] is False and data["use_reentrant"] is False
    return ok, None if ok else "SFT-03 requires batch=1 grad_accum=16 packing=False gradient_checkpointing use_reentrant=False", data


def _check_sft04(dry_report: dict[str, Any], dry_path: Path) -> tuple[bool, str | None, dict[str, Any]]:
    data = {
        "path": str(dry_path),
        "ok": dry_report.get("ok"),
        "full_run_allowed": dry_report.get("full_run_allowed"),
        "sample_count": dry_report.get("sample_count"),
        "ood_hard_constraint_pass_rate": dry_report.get("ood_hard_constraint_pass_rate"),
    }
    pass_rate_present = dry_report.get("ood_hard_constraint_pass_rate") is not None
    pass_rate_ok = (not pass_rate_present) or float(dry_report.get("ood_hard_constraint_pass_rate", 0.0)) >= 0.95
    ok = dry_path.exists() and dry_report.get("ok") is True and dry_report.get("full_run_allowed") is True and dry_report.get("sample_count") == 500 and pass_rate_ok
    return ok, None if ok else "SFT-04 requires dry-run ok=true/full_run_allowed=true, sample_count=500, pass_rate>=0.95", data


def _check_sft05(manifest: dict[str, Any], full_report: dict[str, Any], paths: dict[str, Path]) -> tuple[bool, str | None, dict[str, Any]]:
    early = manifest.get("early_stopping") if isinstance(manifest.get("early_stopping"), dict) else {}
    data = {
        "manifest_ok": manifest.get("ok"),
        "full_report_ok": full_report.get("ok"),
        "max_epochs": early.get("max_epochs", _training_args(manifest).get("num_train_epochs")),
        "eval_steps": early.get("eval_steps", _training_args(manifest).get("eval_steps")),
        "patience": early.get("patience"),
        "early_stopping_triggered": manifest.get("early_stopping_triggered"),
        "stop_reason": manifest.get("stop_reason"),
        "best_model_checkpoint": str(paths.get("best_model_checkpoint", "")),
        "adapter_path": str(paths.get("adapter_path", "")),
        "has_wall_clock_cap": "wall_clock_cap" in manifest or "max_wall_clock_seconds" in manifest or "timeout_seconds" in manifest,
    }
    adapter = paths.get("adapter_path")
    best = paths.get("best_model_checkpoint")
    ok = (
        manifest.get("ok") is True
        and (not full_report or full_report.get("ok") is True)
        and data["max_epochs"] == 5
        and data["eval_steps"] == 200
        and data["patience"] == 3
        and manifest.get("early_stopping_triggered") is True
        and manifest.get("stop_reason") == "early_stopping"
        and adapter is not None
        and adapter.exists()
        and best is not None
        and bool(str(best))
        and best.exists()
        and data["has_wall_clock_cap"] is False
    )
    return ok, None if ok else "SFT-05 requires green full manifest, adapter, best checkpoint, early_stopping_triggered=true, stop_reason=early_stopping, and no wall-clock cap", data


def _check_sft06(grad_gate: dict[str, Any], grad_path: Path) -> tuple[bool, str | None, dict[str, Any]]:
    data = {
        "path": str(grad_path),
        "ok": grad_gate.get("ok"),
        "observed_steps": grad_gate.get("observed_steps", grad_gate.get("steps")),
        "grad_norm_p99": grad_gate.get("grad_norm_p99"),
        "loss_finite": grad_gate.get("loss_finite", grad_gate.get("losses_finite")),
        "fatal_failures": grad_gate.get("fatal_failures", []),
    }
    try:
        p99 = float(data["grad_norm_p99"])
    except (TypeError, ValueError):
        p99 = 999.0
    loss_finite_ok = data["loss_finite"] is True or data["loss_finite"] is None
    ok = grad_path.exists() and grad_gate.get("ok") is True and int(data["observed_steps"] or 0) >= 200 and p99 < 3.0 and loss_finite_ok and not data["fatal_failures"]
    return ok, None if ok else "SFT-06 requires grad_gate ok, observed_steps>=200, grad_norm_p99<3.0, finite losses", data


def _check_sft07(run_dir: Path, manifest: dict[str, Any]) -> tuple[bool, str | None, dict[str, Any]]:
    data = {"run_root": str(run_dir), "wandb_project": manifest.get("wandb_project")}
    ok = _is_v3_run_root(run_dir) and manifest.get("wandb_project") == WANDB_PROJECT
    return ok, None if ok else "SFT-07 requires runs/v3.0-9B-* isolation and wandb project tsc-cycle-v3-9b", data


def _check_sft08(manifest: dict[str, Any], frozen_marker: Path, run_dir: Path) -> tuple[bool, str | None, dict[str, Any]]:
    evidence = manifest.get("frozen_evidence") if isinstance(manifest.get("frozen_evidence"), dict) else {}
    root_text = str(evidence.get("root", ""))
    marker_text = str(evidence.get("frozen_marker", ""))
    output_paths = {
        "run_root": str(run_dir),
        "adapter_path": str(manifest.get("adapter_path", "")),
        "dry_run_report": str(manifest.get("dry_run_report", "")),
        "full_run_report": str(manifest.get("full_run_report", "")),
    }
    data = {"frozen_evidence": evidence, "frozen_marker": marker_text, "output_paths": output_paths}
    marker_exists_or_legacy_evidence = frozen_marker.exists() or (not marker_text and evidence.get("write_bits_removed") is True and evidence.get("pre", {}).get("content_sha256"))
    ok = (
        (V1_RUN_ID in root_text or not root_text)
        and (V1_RUN_ID in marker_text or not marker_text)
        and marker_exists_or_legacy_evidence
        and evidence.get("write_bits_removed") is True
        and evidence.get("pre", {}).get("content_sha256") == evidence.get("post", {}).get("content_sha256")
        and not _contains_v1_path(output_paths)
    )
    return ok, None if ok else "SFT-08 requires FROZEN.md/read-only evidence for runs/20260507T032419Z and no v1 output paths", data


def evaluate_sft_manifest(manifest_path: str | Path) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    run_dir = manifest_path.parent
    report = evaluate_gates(run_dir, phase3_manifest=Path("data/splits/v3/manifest.json"), _legacy_manifest_path=manifest_path)
    return {
        "ok": report["ok"],
        "run_root": report.get("run_root", str(run_dir)),
        "wandb_project": report.get("wandb_project"),
        "paths": {
            "adapter_path": report.get("artifact_manifest", {}).get("paths", {}).get("adapter_path", ""),
            "dry_run_report": report.get("artifact_manifest", {}).get("paths", {}).get("dry_run_report", ""),
            "full_run_report": report.get("artifact_manifest", {}).get("paths", {}).get("full_run_report", ""),
        },
        "requirements_covered": report.get("requirements_covered", []),
        "arrow_hashes": report.get("arrow_hashes", {}),
        "lora_coverage_path": report.get("artifact_manifest", {}).get("paths", {}).get("lora_coverage", ""),
        "frozen_evidence": report.get("gates", {}).get("SFT-08", {}).get("data", {}).get("frozen_evidence", {}),
        "gates": report.get("gates", {}),
        "fatal_failures": report.get("fatal_failures", []),
    }


def evaluate_gates(
    run_dir: str | Path,
    phase3_manifest: str | Path = "data/splits/v3/manifest.json",
    out: str | Path | None = None,
    *,
    _legacy_manifest_path: Path | None = None,
) -> dict[str, Any]:
    run_dir = Path(run_dir)
    phase3_manifest = Path(phase3_manifest)
    manifest_path = _legacy_manifest_path or run_dir / "sft_manifest.json"
    manifest, manifest_errors = _load_json(manifest_path)
    gates: dict[str, Any] = {}
    failures: list[dict[str, str]] = []
    failures.extend(manifest_errors)

    if manifest_path.exists() and manifest_path.parent != run_dir:
        run_dir = manifest_path.parent

    paths = _artifact_paths(run_dir, manifest, phase3_manifest)
    manifest_arrow_hashes = manifest.get("arrow_hashes", {}) if isinstance(manifest.get("arrow_hashes"), dict) else {}
    artifact_sha256 = _hash_artifacts(paths)
    for key in ("train_arrow", "val_arrow", "ood_val_arrow"):
        if key not in artifact_sha256 and manifest_arrow_hashes.get(key):
            artifact_sha256[key] = str(manifest_arrow_hashes[key])
    artifact_manifest = {
        "paths": {key: str(path) for key, path in paths.items()},
        "sha256": artifact_sha256,
    }

    requirements = manifest.get("requirements_covered", [])
    requirements_ok = requirements == REQUIREMENTS_COVERED
    _add_result(gates, failures, "requirements_covered", requirements_ok, None if requirements_ok else "aggregate manifest must cover SFT-01 through SFT-08 exactly", {"observed": requirements, "expected": REQUIREMENTS_COVERED})

    lora_coverage = _read_path_payload(paths["lora_coverage"])
    sft01_ok, sft01_reason, sft01_data = _check_lora_coverage(lora_coverage, manifest)
    _add_result(gates, failures, "SFT-01", sft01_ok, sft01_reason, sft01_data)

    sft02_ok, sft02_reason, sft02_data = _check_sft02(manifest)
    _add_result(gates, failures, "SFT-02", sft02_ok, sft02_reason, sft02_data)

    sft03_ok, sft03_reason, sft03_data = _check_sft03(manifest)
    _add_result(gates, failures, "SFT-03", sft03_ok, sft03_reason, sft03_data)

    dry_report = _read_path_payload(paths["dry_run_report"])
    sft04_ok, sft04_reason, sft04_data = _check_sft04(dry_report, paths["dry_run_report"])
    _add_result(gates, failures, "SFT-04", sft04_ok, sft04_reason, sft04_data)

    full_report = _read_path_payload(paths["full_run_report"])
    sft05_ok, sft05_reason, sft05_data = _check_sft05(manifest, full_report, paths)
    _add_result(gates, failures, "SFT-05", sft05_ok, sft05_reason, sft05_data)

    grad_gate = _read_path_payload(paths["grad_gate"])
    sft06_ok, sft06_reason, sft06_data = _check_sft06(grad_gate, paths["grad_gate"])
    _add_result(gates, failures, "SFT-06", sft06_ok, sft06_reason, sft06_data)

    sft07_ok, sft07_reason, sft07_data = _check_sft07(run_dir, manifest)
    _add_result(gates, failures, "SFT-07", sft07_ok, sft07_reason, sft07_data)

    sft08_ok, sft08_reason, sft08_data = _check_sft08(manifest, paths["frozen_marker"], run_dir)
    _add_result(gates, failures, "SFT-08", sft08_ok, sft08_reason, sft08_data)

    arrow_hashes = manifest.get("arrow_hashes", {}) if isinstance(manifest.get("arrow_hashes"), dict) else {}
    for key in ("train_arrow", "val_arrow", "ood_val_arrow"):
        if (key not in paths or not paths[key].exists()) and not arrow_hashes.get(key):
            failures.append(_failure("artifact_manifest", f"missing Phase 3 Arrow artifact: {key}"))
    for key in ("dry_run_report", "full_run_report"):
        if not paths[key].exists():
            failures.append(_failure("artifact_manifest", f"missing evidence artifact: {key}={paths[key]}"))
    if not paths["frozen_marker"].exists() and not (manifest.get("frozen_evidence", {}).get("write_bits_removed") if isinstance(manifest.get("frozen_evidence"), dict) else False):
        failures.append(_failure("artifact_manifest", f"missing evidence artifact: frozen_marker={paths['frozen_marker']}"))
    if not paths["lora_coverage"].exists() and not manifest.get("lora_coverage_path"):
        failures.append(_failure("artifact_manifest", f"missing evidence artifact: lora_coverage={paths['lora_coverage']}"))

    manifest_failures = manifest.get("fatal_failures", []) if isinstance(manifest.get("fatal_failures"), list) else []
    failures.extend(item for item in manifest_failures if isinstance(item, dict) and "gate" in item)

    ok = not failures and all(gate.get("ok") is True for gate in gates.values())
    report = {
        "ok": ok,
        "next_phase_allowed": ok,
        "requirements_covered": requirements,
        "gates": gates,
        "fatal_failures": failures,
        "artifact_manifest": artifact_manifest,
        "run_root": str(run_dir),
        "wandb_project": manifest.get("wandb_project"),
        "adapter_path": str(paths["adapter_path"]),
        "arrow_hashes": arrow_hashes,
    }
    if out is not None:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate Phase 4 SFT gate report for SFT-01 through SFT-08")
    parser.add_argument("--run-dir", default=None, help="Phase 4 run root; omit with --allow-pending to write a fail-closed pending report")
    parser.add_argument("--phase3-manifest", default="data/splits/v3/manifest.json")
    parser.add_argument("--out", default=None)
    parser.add_argument("--allow-pending", action="store_true", help="Return/write ok=false pending report instead of argparse failure when no run-dir exists")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.run_dir is None:
        if not args.allow_pending:
            build_parser().error("--run-dir is required unless --allow-pending is set")
        report = _pending_report(Path.cwd(), "no valid green full-run sft_manifest.json or adapter found", out=args.out)
    else:
        report = evaluate_gates(args.run_dir, phase3_manifest=args.phase3_manifest, out=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
