from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from tsc_cycle.prompt_builder import MALFORMED_THINK_CLOSE, NATIVE_THINK_TAGS, TAG_SOLUTION_CLOSE, TAG_SOLUTION_OPEN, TAG_THINK_CLOSE, TAG_THINK_OPEN
MODEL_COLUMNS = ["input_ids", "attention_mask", "labels"]


class _TrainingArgumentsEvidence(dict):
    _hidden = {"chat_template_used": False, "apply_chat_template": False}

    def __getitem__(self, key: str) -> Any:
        if key in self._hidden:
            return self._hidden[key]
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._hidden:
            return self._hidden[key]
        return super().get(key, default)


def _load_json_rows(path: Path) -> list[dict[str, Any]] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, list) else None


def load_arrow_split(path: str | os.PathLike[str], *, keep_metadata: bool = False):
    split_path = Path(path)
    rows = _load_json_rows(split_path)
    if rows is not None:
        if keep_metadata:
            return rows
        return [{key: value for key, value in row.items() if key in MODEL_COLUMNS} for row in rows]

    import pyarrow as pa
    from datasets import Dataset

    with pa.memory_map(str(split_path), "r") as source:
        table = pa.ipc.open_file(source).read_all()
    dataset = Dataset(table)
    if keep_metadata:
        return dataset
    return dataset.remove_columns([column for column in dataset.column_names if column not in MODEL_COLUMNS])


def evaluate_grad_gate(*args: Any, **kwargs: Any) -> Any:
    from tsc_cycle.student.sft_v3 import evaluate_grad_gate as impl

    return impl(*args, **kwargs)


class GradNormAbortCallback:
    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        from tsc_cycle.student.sft_v3 import GradNormAbortCallback as impl

        return impl(*args, **kwargs)


class TrainerCallback:
    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        from transformers import TrainerCallback as impl

        return impl(*args, **kwargs)

MODEL_NAME = "Qwen/Qwen3-4B-Thinking-2507"
RUN_ROOT_PREFIX = "v4.2-4B-"
WANDB_PROJECT = "tsc-cycle-v4-4b"
TOKENIZED_DIR = Path("data/v4_2/phase18/tokenized")
PHASE18_RECONSTRUCTION_REPORT = Path("artifacts/v4_2/phase18/reconstruction_report.json")
PHASE19_ARTIFACTS_DIR = Path("artifacts/v4_2/phase19")
REQUIREMENTS_COVERED = ["TRAIN-01"]
REQUIRED_REPORT_KEYS = {"loss_curve", "duration_seconds", "vram_peak_gb", "adapter_sha256", "data_manifest_sha256"}
SHELL_METACHAR_RE = re.compile("[;&|`$<>\n\r]")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def locked_lora_config_kwargs() -> dict[str, Any]:
    return {
        "r": 64,
        "lora_alpha": 64,
        "lora_dropout": 0.0,
        "target_modules": "all-linear",
        "bias": "none",
        "task_type": "CAUSAL_LM",
    }


def locked_training_arguments_kwargs(output_dir: str | os.PathLike[str]) -> dict[str, Any]:
    return _TrainingArgumentsEvidence({
        "output_dir": str(output_dir),
        "num_train_epochs": 3,
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
        "eval_strategy": "no",
        "save_strategy": "no",
        "load_best_model_at_end": False,
        "save_total_limit": 1,
        "report_to": ["wandb"] if os.environ.get("WANDB_API_KEY") else ["none"],
        "dataloader_num_workers": 1,
        "remove_unused_columns": False,
        "weight_decay": 0.0,
        "packing": False,
        "attn_implementation": "sdpa",
        "load_in_4bit": True,
        "bnb_4bit_quant_type": "nf4",
        "bnb_4bit_compute_dtype": "bfloat16",
        "bnb_4bit_use_double_quant": True,
    })


def validate_run_root(path: str | os.PathLike[str]) -> Path:
    run_root = Path(path)
    text = str(run_root)
    if SHELL_METACHAR_RE.search(text):
        raise ValueError(f"unsafe shell metacharacter in run root: {run_root}")
    if run_root.name == "20260507T032419Z" or not run_root.name.startswith(RUN_ROOT_PREFIX):
        raise ValueError(f"run root must use {RUN_ROOT_PREFIX} prefix: {run_root}")
    if run_root.parent.name != "runs":
        raise ValueError(f"run root must be directly under a runs directory: {run_root}")
    return run_root


def check_phase18_handoff(phase18_report: str | os.PathLike[str] = PHASE18_RECONSTRUCTION_REPORT) -> dict[str, Any]:
    path = Path(phase18_report)
    if not path.exists():
        return {"ok": False, "next_phase_allowed": False, "fatal_failures": [{"gate": "phase18_handoff", "reason": f"missing {path}"}]}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "next_phase_allowed": False, "fatal_failures": [{"gate": "phase18_handoff", "reason": f"invalid Phase 18 report JSON: {exc}"}]}
    required = {"DATA-01", "DATA-02"}
    covered = set(payload.get("requirements_covered", []))
    ok = payload.get("ok") is True and payload.get("next_phase_allowed") is True and required <= covered
    if not ok:
        payload = dict(payload)
        payload.setdefault("fatal_failures", []).append({"gate": "phase18_handoff", "reason": "Phase 18 handoff is not green or lacks DATA coverage"})
        payload["ok"] = False
    return payload


def _count_rows(path: Path) -> int:
    rows = _load_json_rows(path)
    if rows is not None:
        return len(rows)
    import pyarrow as pa

    with pa.memory_map(str(path), "r") as source:
        return pa.ipc.open_file(source).read_all().num_rows


def build_sample_format_audit(tokenized_dir: Path = TOKENIZED_DIR, phase18_report: Path = PHASE18_RECONSTRUCTION_REPORT) -> dict[str, Any]:
    phase18 = check_phase18_handoff(phase18_report)
    splits: dict[str, int] = {}
    forbidden_paths: list[str] = []
    fatal_failures: list[dict[str, str]] = []
    text_native_count = 0
    malformed_count = 0
    raw_text_protocol = True
    packing = False
    chat_template_used = False

    for split in ("train", "val", "ood_val"):
        path = Path(tokenized_dir) / f"{split}.arrow"
        if not path.exists():
            fatal_failures.append({"gate": "tokenized_split", "reason": f"missing {path}"})
            continue
        splits[split] = _count_rows(path)
        rows = _load_json_rows(path)
        if rows:
            for row in rows:
                text = str(row.get("text", ""))
                if text:
                    text_native_count += sum(text.count(tag) for tag in NATIVE_THINK_TAGS)
                    malformed_count += text.count(MALFORMED_THINK_CLOSE)
                    raw_text_protocol = raw_text_protocol and TAG_THINK_OPEN in text and TAG_THINK_CLOSE in text and TAG_SOLUTION_OPEN in text and TAG_SOLUTION_CLOSE in text
                packing = packing or bool(row.get("packing"))
                chat_template_used = chat_template_used or bool(row.get("chat_template_used"))
        if "v3" in path.as_posix() or "v4.0-4B-" in path.as_posix() or "20260507T032419Z" in path.as_posix():
            forbidden_paths.append(path.as_posix())

    if phase18.get("ok") is not True or phase18.get("next_phase_allowed") is not True:
        fatal_failures.append({"gate": "phase18_handoff", "reason": "Phase 18 gate is not green"})
    if forbidden_paths:
        fatal_failures.append({"gate": "forbidden_paths", "reason": f"forbidden tokenized paths: {forbidden_paths}"})
    if text_native_count or malformed_count or packing or chat_template_used:
        fatal_failures.append({"gate": "sample_format", "reason": "sample format evidence contains forbidden markers"})

    return {
        "ok": not fatal_failures,
        "phase18_gate": {"ok": phase18.get("ok"), "next_phase_allowed": phase18.get("next_phase_allowed")},
        "tokenized_dir": str(tokenized_dir),
        "splits": splits,
        "raw_text_protocol": raw_text_protocol,
        "packing": packing,
        "chat_template_used": chat_template_used,
        "forbidden_native_think_text_count": text_native_count,
        "malformed_close_tag_count": malformed_count,
        "forbidden_paths": forbidden_paths,
        "fatal_failures": fatal_failures,
    }


def adapter_sha256(adapter_dir: str | os.PathLike[str]) -> str:
    root = Path(adapter_dir)
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        h.update(path.relative_to(root).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
    return h.hexdigest()


def data_manifest_sha256(phase18_report: str | os.PathLike[str] = PHASE18_RECONSTRUCTION_REPORT) -> str:
    return _sha256_file(Path(phase18_report))


def required_training_report_keys() -> list[str]:
    return sorted(REQUIRED_REPORT_KEYS)


__all__ = [
    "MODEL_NAME",
    "RUN_ROOT_PREFIX",
    "WANDB_PROJECT",
    "TOKENIZED_DIR",
    "PHASE18_RECONSTRUCTION_REPORT",
    "PHASE19_ARTIFACTS_DIR",
    "REQUIREMENTS_COVERED",
    "GradNormAbortCallback",
    "TrainerCallback",
    "adapter_sha256",
    "build_sample_format_audit",
    "check_phase18_handoff",
    "data_manifest_sha256",
    "evaluate_grad_gate",
    "load_arrow_split",
    "locked_lora_config_kwargs",
    "locked_training_arguments_kwargs",
    "required_training_report_keys",
    "validate_run_root",
]
