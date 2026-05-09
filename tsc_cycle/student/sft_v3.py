"""Phase 4 Qwen3.5-9B SFT helper contracts.

This module is intentionally CPU-importable: helpers and callbacks can be tested
without loading the 9B model or touching CUDA. Long training remains owned by the
DGX safe wrappers.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path
from typing import Any, Iterable

from datasets import Dataset
from transformers import TrainerCallback

MODEL_NAME = "Qwen/Qwen3.5-9B"
RUN_ROOT_PREFIX = "v3.0-9B-"
WANDB_PROJECT = "tsc-cycle-v3-9b"
MODEL_COLUMNS = ["input_ids", "attention_mask", "labels"]
PHASE3_COLUMNS = {
    "sample_id",
    "input_ids",
    "attention_mask",
    "labels",
    "raw_length",
    "truncated",
    "prompt_hash",
    "assistant_hash",
}
GRAD_GATE_FILENAME = "grad_gate.json"
LORA_COVERAGE_FILENAME = "lora_coverage.json"
EXPECTED_GATED_DELTANET_LAYERS = 24
EXPECTED_FULL_ATTENTION_LAYERS = 8
V1_RUN_ID = "20260507T032419Z"
RUN_SAFE_COMMAND = ["scripts/dgx_spark/run_safe.sh", "100G", "--"]
PROJECT_PYTHON = "/home/samuel/TSC_CYCLE/.venv/bin/python"
SHELL_METACHAR_RE = re.compile("[;&|`$<>\\n\\r]")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def locked_lora_config_kwargs() -> dict[str, Any]:
    """Return machine-checkable locked PEFT LoRA config values for SFT-01."""
    return {
        "r": 64,
        "lora_alpha": 64,
        "lora_dropout": 0.0,
        "target_modules": "all-linear",
        "bias": "none",
        "task_type": "CAUSAL_LM",
        "coverage_report": LORA_COVERAGE_FILENAME,
        "expected_gated_deltanet_layers": 24,
        "expected_full_attention_layers": 8,
        "require_per_layer_projection_evidence": True,
        "fail_closed_on_coverage_mismatch": True,
    }


def locked_training_arguments_kwargs(output_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Return locked Trainer kwargs for Phase 4 Qwen3.5-9B SFT."""
    return {
        "output_dir": str(output_dir),
        "num_train_epochs": 5,
        "per_device_train_batch_size": 1,
        "gradient_accumulation_steps": 16,
        "learning_rate": 1e-4,
        "lr_scheduler_type": "cosine",
        "warmup_ratio": 0.03,
        "optim": "adamw_torch_fused",
        "max_grad_norm": 0.5,
        "bf16": True,
        "gradient_checkpointing": True,
        "gradient_checkpointing_kwargs": {"use_reentrant": False},
        "logging_steps": 1,
        "eval_strategy": "steps",
        "eval_steps": 200,
        "save_strategy": "steps",
        "save_steps": 200,
        "save_total_limit": 3,
        "load_best_model_at_end": True,
        "metric_for_best_model": "eval_loss",
        "greater_is_better": False,
        "report_to": ["wandb"] if os.environ.get("WANDB_API_KEY") else ["none"],
        "dataloader_num_workers": 1,
        "remove_unused_columns": False,
        "weight_decay": 0.0,
        "packing": False,
        "chat_template": False,
        "apply_chat_template": False,
    }


def load_arrow_split(path: str | os.PathLike[str], *, keep_metadata: bool = False) -> Dataset:
    """Load a Phase 3 Arrow IPC split and optionally prune to Trainer columns."""
    import pyarrow as pa

    arrow_path = Path(path)
    if arrow_path.suffix != ".arrow":
        raise ValueError(f"Phase 4 trainer only accepts .arrow IPC splits, got: {arrow_path}")
    with pa.memory_map(str(arrow_path), "r") as source:
        table = pa.ipc.open_file(source).read_all()
    missing = sorted(PHASE3_COLUMNS - set(table.column_names))
    if missing:
        raise ValueError(f"Arrow split missing required Phase 3 columns: {missing}")
    dataset = Dataset(table)
    if keep_metadata:
        return dataset
    return dataset.remove_columns([column for column in dataset.column_names if column not in MODEL_COLUMNS])


def _sorted_index_p99(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.99) - 1)
    return ordered[min(index, len(ordered) - 1)]


def _finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _failure(gate: str, reason: str) -> dict[str, str]:
    return {"gate": gate, "reason": reason}


def evaluate_grad_gate(rows: Iterable[dict[str, Any]], *, gate_steps: int = 200, p99_limit: float = 3.0, stopped_early: bool = False) -> dict[str, Any]:
    """Evaluate SFT-06 first-200-step loss/grad_norm evidence fail-closed."""
    materialized = [dict(row) for row in rows]
    first_rows = [row for row in materialized if int(row.get("step", 0) or 0) <= gate_steps]
    loss_rows: list[dict[str, Any]] = []
    grad_norm_rows: list[dict[str, Any]] = []
    fatal_failures: list[dict[str, str]] = []

    loss_finite = True
    grad_norm_finite = True
    for row in first_rows:
        step = int(row.get("step", 0) or 0)
        if "loss" in row:
            loss_value = _finite_float(row.get("loss"))
            if loss_value is None:
                loss_finite = False
                fatal_failures.append(_failure("loss_finite", f"non-finite loss at step {step}"))
            else:
                loss_rows.append({"step": step, "loss": loss_value})
        if "grad_norm" in row:
            grad_value = _finite_float(row.get("grad_norm"))
            if grad_value is None:
                grad_norm_finite = False
                fatal_failures.append(_failure("grad_norm_finite", f"non-finite grad_norm at step {step}"))
            else:
                grad_norm_rows.append({"step": step, "grad_norm": grad_value})

    observed_steps = len({int(row.get("step", 0) or 0) for row in first_rows if int(row.get("step", 0) or 0) > 0})
    if observed_steps < gate_steps or len(loss_rows) < gate_steps or len(grad_norm_rows) < gate_steps:
        fatal_failures.append(
            _failure(
                "min_steps",
                f"first-{gate_steps}-step evidence incomplete: observed_steps={observed_steps}, loss_rows={len(loss_rows)}, grad_norm_rows={len(grad_norm_rows)}",
            )
        )

    grad_norm_p99 = _sorted_index_p99([float(row["grad_norm"]) for row in grad_norm_rows])
    if grad_norm_p99 is None:
        fatal_failures.append(_failure("grad_norm_p99", "missing grad_norm evidence"))
    elif grad_norm_p99 >= p99_limit:
        fatal_failures.append(_failure("grad_norm_p99", f"grad_norm p99 {grad_norm_p99} >= {p99_limit}"))

    ok = not fatal_failures
    return {
        "ok": ok,
        "status": "pass" if ok else "fail",
        "gate_steps": gate_steps,
        "observed_steps": observed_steps,
        "steps_evaluated": min(observed_steps, gate_steps),
        "loss_rows": loss_rows,
        "grad_norm_rows": grad_norm_rows,
        "grad_norm_p99": grad_norm_p99,
        "p99_limit": p99_limit,
        "loss_finite": loss_finite,
        "grad_norm_finite": grad_norm_finite,
        "fatal_failures": fatal_failures,
        "stopped_early": stopped_early,
        "requirements_covered": ["SFT-06"],
    }


def grad_gate_report_path(run_root: Path, mode: str) -> Path:
    return Path(run_root) / "reports" / mode / GRAD_GATE_FILENAME


class GradNormAbortCallback(TrainerCallback):
    """Collect first-200 optimizer-step loss/grad_norm logs and abort on SFT-06 failures."""

    def __init__(self, run_root: str | os.PathLike[str], mode: str, *, gate_steps: int = 200, p99_limit: float = 3.0):
        self.run_root = Path(run_root)
        self.mode = mode
        self.gate_steps = gate_steps
        self.p99_limit = p99_limit
        self.rows: list[dict[str, Any]] = []
        self.fatal_failures: list[dict[str, str]] = []
        self.stopped_early = False
        self._last_status: str | None = None

    @property
    def path(self) -> Path:
        return grad_gate_report_path(self.run_root, self.mode)

    def _append_failure(self, gate: str, reason: str) -> None:
        failure = _failure(gate, reason)
        if failure not in self.fatal_failures:
            self.fatal_failures.append(failure)

    def _write_report(self) -> dict[str, Any]:
        report = evaluate_grad_gate(self.rows, gate_steps=self.gate_steps, p99_limit=self.p99_limit, stopped_early=self.stopped_early)
        if self.fatal_failures:
            report["fatal_failures"] = [*self.fatal_failures, *report["fatal_failures"]]
            report["ok"] = False
            report["status"] = "fail"
        _write_json(self.path, report)
        self._last_status = str(report["status"])
        return report

    def on_log(self, args, state, control, logs: dict[str, Any] | None = None, **kwargs):  # noqa: D401, ANN001
        logs = logs or {}
        step = int(getattr(state, "global_step", 0) or logs.get("step", 0) or 0)
        row: dict[str, Any] = {"step": step}
        if "loss" in logs:
            row["loss"] = logs["loss"]
            if _finite_float(logs["loss"]) is None:
                self._append_failure("loss_finite", f"non-finite loss at step {step}")
                self.stopped_early = True
                control.should_training_stop = True
        if "grad_norm" in logs:
            row["grad_norm"] = logs["grad_norm"]
            if _finite_float(logs["grad_norm"]) is None:
                self._append_failure("grad_norm_finite", f"non-finite grad_norm at step {step}")
                self.stopped_early = True
                control.should_training_stop = True
        if step and step <= self.gate_steps and ("loss" in row or "grad_norm" in row):
            self.rows.append(row)
        report = self._write_report()
        if step >= self.gate_steps and (report["grad_norm_p99"] is not None and report["grad_norm_p99"] >= self.p99_limit):
            self.stopped_early = True
            control.should_training_stop = True
            self._write_report()
        return control

    def on_step_end(self, args, state, control, **kwargs):  # noqa: D401, ANN001
        step = int(getattr(state, "global_step", 0) or 0)
        if step >= self.gate_steps:
            report = self._write_report()
            if not report["ok"]:
                self.stopped_early = True
                control.should_training_stop = True
                self._write_report()
        return control


def _tree_evidence(root: Path) -> dict[str, Any]:
    files = sorted(path for path in root.rglob("*") if path.is_file())
    digest = hashlib.sha256()
    mtimes: dict[str, float] = {}
    for path in files:
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        mtimes[rel] = path.stat().st_mtime
    return {
        "artifact_count": len(files),
        "content_sha256": digest.hexdigest(),
        "mtimes": mtimes,
    }


def ensure_v1_frozen(root: str | os.PathLike[str] = Path("runs") / V1_RUN_ID) -> dict[str, Any]:
    """Mark the v1.0 production artifact tree as frozen and remove write bits."""
    root_path = Path(root)
    if root_path.name != V1_RUN_ID:
        raise ValueError(f"FROZEN guard may only target {V1_RUN_ID}, got: {root_path}")
    if not root_path.exists():
        raise FileNotFoundError(f"missing v1.0 artifact root: {root_path}")

    marker = root_path / "FROZEN.md"
    if not marker.exists():
        marker.write_text(
            "# FROZEN\n\nThis v1.0 production artifact tree is read-only for v3.0 Phase 4 SFT.\n",
            encoding="utf-8",
        )
    pre = _tree_evidence(root_path)
    chmod_errors: list[str] = []
    chmod_attempted = False
    for path in sorted([*root_path.rglob("*"), root_path], key=lambda item: len(item.parts), reverse=True):
        try:
            current_mode = path.stat().st_mode
            path.chmod(current_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
            chmod_attempted = True
        except OSError as exc:  # pragma: no cover - platform/permission specific
            chmod_errors.append(f"{path}: {exc}")
    post = _tree_evidence(root_path)
    write_bits_removed = all((path.stat().st_mode & 0o222) == 0 for path in [root_path, *root_path.rglob("*")])
    return {
        "ok": pre["content_sha256"] == post["content_sha256"] and write_bits_removed,
        "root": str(root_path),
        "frozen_marker": str(marker),
        "chmod_attempted": chmod_attempted,
        "chmod_errors": chmod_errors,
        "write_bits_removed": write_bits_removed,
        "pre": pre,
        "post": post,
    }


def validate_run_root(path: str | os.PathLike[str]) -> Path:
    """Accept only isolated Phase 4 run roots named runs/v3.0-9B-* without shell metacharacters."""
    run_root = Path(path)
    text = str(run_root)
    if SHELL_METACHAR_RE.search(text):
        raise ValueError(f"unsafe shell metacharacter in run root: {run_root}")
    if run_root.name == V1_RUN_ID or not run_root.name.startswith(RUN_ROOT_PREFIX):
        raise ValueError(f"run root must use {RUN_ROOT_PREFIX} prefix: {run_root}")
    if run_root.parent.name != "runs":
        raise ValueError(f"run root must be directly under a runs directory: {run_root}")
    return run_root


def phase4_wrapper_command(mode: str, output_root: str | os.PathLike[str]) -> list[str]:
    if mode not in {"dry-run", "full"}:
        raise ValueError(f"unsupported Phase 4 mode: {mode}")
    output_text = str(output_root)
    if SHELL_METACHAR_RE.search(output_text):
        raise ValueError(f"unsafe output root: {output_text}")
    return [
        *RUN_SAFE_COMMAND,
        PROJECT_PYTHON,
        "-m",
        "tsc_cycle.student.train",
        "--mode",
        mode,
        "--output-root",
        output_text,
    ]


def _layer_index(name: str) -> int | None:
    match = re.search(r"(?:^|\.)layers\.(\d+)(?:\.|$)", name)
    return int(match.group(1)) if match else None


def build_lora_coverage_report(model: Any) -> dict[str, Any]:
    module_names = [name for name, _module in model.named_modules()]
    trainable_names: list[str] = []
    if hasattr(model, "named_parameters"):
        trainable_names = sorted(name for name, param in model.named_parameters() if getattr(param, "requires_grad", False))
    lora_module_names = sorted(name for name in module_names if "lora" in name.lower())
    trainable_lora_module_names = sorted({name.rsplit(".", 1)[0] for name in trainable_names if "lora" in name.lower()} | set(lora_module_names))

    gated_layers: dict[int, set[str]] = {}
    full_layers: dict[int, set[str]] = {}
    projection_names: set[str] = set()
    for name in [*module_names, *trainable_lora_module_names]:
        lowered = name.lower()
        layer = _layer_index(name)
        if layer is None:
            continue
        projection = name.split(".")[-1]
        if projection:
            projection_names.add(projection)
        if any(token in lowered for token in ("deltanet", "delta_net", "linear_attn", "linear_attention")):
            gated_layers.setdefault(layer, set()).add(projection)
        if any(token in lowered for token in ("self_attn", "full_attn", "attention")) and not any(token in lowered for token in ("linear_attn", "linear_attention")):
            full_layers.setdefault(layer, set()).add(projection)

    fatal_failures: list[dict[str, str]] = []
    if len(gated_layers) != EXPECTED_GATED_DELTANET_LAYERS:
        fatal_failures.append(_failure("gated_deltanet_layer_count", f"observed {len(gated_layers)} != {EXPECTED_GATED_DELTANET_LAYERS}"))
    if len(full_layers) != EXPECTED_FULL_ATTENTION_LAYERS:
        fatal_failures.append(_failure("full_attention_layer_count", f"observed {len(full_layers)} != {EXPECTED_FULL_ATTENTION_LAYERS}"))
    if not trainable_lora_module_names:
        fatal_failures.append(_failure("trainable_lora_modules", "no trainable LoRA modules observed"))

    return {
        "ok": not fatal_failures,
        "expected_gated_deltanet_layers": 24,
        "expected_full_attention_layers": 8,
        "observed_gated_deltanet_layers": len(gated_layers),
        "observed_full_attention_layers": len(full_layers),
        "gated_deltanet_layer_projections": {str(idx): sorted(values) for idx, values in sorted(gated_layers.items())},
        "full_attention_layer_projections": {str(idx): sorted(values) for idx, values in sorted(full_layers.items())},
        "projection_names": sorted(projection_names),
        "trainable_lora_module_names": trainable_lora_module_names,
        "trainable_lora_module_count": len(trainable_lora_module_names),
        "fatal_failures": fatal_failures,
    }


def write_lora_coverage_report(model: Any, path: str | os.PathLike[str]) -> dict[str, Any]:
    report = build_lora_coverage_report(model)
    _write_json(Path(path), report)
    return report


def arrow_hashes(tokenized_dir: str | os.PathLike[str]) -> dict[str, str]:
    root = Path(tokenized_dir)
    return {f"{split}_arrow": _sha256_file(root / f"{split}.arrow") for split in ("train", "val", "ood_val") if (root / f"{split}.arrow").exists()}
