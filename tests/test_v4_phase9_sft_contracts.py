from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

EXPECTED_MODEL = "Qwen/Qwen3-4B-Thinking-2507"
RUN_ROOT_PREFIX = "v4.0-4B-"
TOKENIZED_DIR = Path("data/v4/phase8/tokenized")
PHASE8_GATE_REPORT = Path("artifacts/v4/phase8/phase8_gate_report.json")
REQUIRED_REPORT_KEYS = {"loss_curve", "duration_seconds", "vram_peak_gb", "adapter_sha256", "data_manifest_sha256"}
FORBIDDEN_MARKERS = [
    "Qwen/Qwen3.5-9B",
    "data/tokenized/v3",
    "data/v3/phase3/tokenized",
    "runs/v3.0-9B-",
    "runs/20260507T032419Z",
    "packing=True",
    "apply_chat_template",
    "vllm",
    "flash_attn",
    "flash-attn",
    "unsloth",
    "axolotl",
    "pip install",
    "uv pip install",
]


def _contract():
    from tsc_cycle.student import sft_v4  # noqa: PLC0415

    return sft_v4


def _green_phase8_report(tmp_path: Path) -> Path:
    path = tmp_path / PHASE8_GATE_REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "ok": True,
                "next_phase_allowed": True,
                "requirements_covered": ["DATA4B-01", "DATA4B-02", "DATA4B-03", "DATA4B-04", "DATA4B-05"],
                "artifact_manifest": {
                    "paths": ["data/v4/phase8/tokenized/train.arrow", "data/v4/phase8/tokenized/val.arrow", "data/v4/phase8/tokenized/ood_val.arrow"],
                    "sha256": {"source_manifest": "a" * 64},
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return path


def _write_arrow_placeholder(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path


def test_locked_model_and_paths_are_qwen4b_v4_only() -> None:
    sft_v4 = _contract()

    assert sft_v4.MODEL_NAME == EXPECTED_MODEL
    assert "Qwen3.5" not in sft_v4.MODEL_NAME
    assert sft_v4.RUN_ROOT_PREFIX == RUN_ROOT_PREFIX
    assert sft_v4.WANDB_PROJECT == "tsc-cycle-v4-4b"
    assert Path(sft_v4.TOKENIZED_DIR) == TOKENIZED_DIR
    assert Path(sft_v4.PHASE8_GATE_REPORT) == PHASE8_GATE_REPORT

    defaults_text = json.dumps(
        {
            "model": sft_v4.MODEL_NAME,
            "run_prefix": sft_v4.RUN_ROOT_PREFIX,
            "tokenized_dir": str(sft_v4.TOKENIZED_DIR),
            "phase8_report": str(sft_v4.PHASE8_GATE_REPORT),
        },
        ensure_ascii=False,
    )
    for forbidden in ["Qwen/Qwen3.5-9B", "data/tokenized/v3", "runs/v3.0-9B-", "runs/20260507T032419Z"]:
        assert forbidden not in defaults_text


def test_locked_lora_config_matches_shipped_4b_route() -> None:
    config = _contract().locked_lora_config_kwargs()

    assert config == {
        "r": 64,
        "lora_alpha": 64,
        "lora_dropout": 0.0,
        "target_modules": "all-linear",
        "bias": "none",
        "task_type": "CAUSAL_LM",
    }


def test_training_arguments_lock_raw_text_sdpa_nf4_and_forbid_wrong_stacks(tmp_path: Path) -> None:
    args = _contract().locked_training_arguments_kwargs(tmp_path / "runs" / "v4.0-4B-20260510T000000Z")

    assert args["bf16"] is True
    assert args["attn_implementation"] == "sdpa"
    assert args["packing"] is False
    assert args["chat_template_used"] is False
    assert args["apply_chat_template"] is False
    assert args["load_in_4bit"] is True
    assert args["bnb_4bit_quant_type"] == "nf4"
    assert args["bnb_4bit_compute_dtype"] in {"bfloat16", "bf16"}
    assert str(args["output_dir"]).endswith("runs/v4.0-4B-20260510T000000Z")

    args_text = json.dumps(args, ensure_ascii=False, sort_keys=True, default=str).lower()
    for forbidden in FORBIDDEN_MARKERS:
        assert forbidden.lower() not in args_text


def test_run_root_validation_accepts_only_isolated_v4_roots(tmp_path: Path) -> None:
    sft_v4 = _contract()
    good = tmp_path / "runs" / "v4.0-4B-20260510T010203Z"
    assert sft_v4.validate_run_root(good) == good

    bad_roots = [
        tmp_path / "runs" / "v3.0-9B-20260510T010203Z",
        Path("/home/samuel/TSC_CYCLE/runs/20260507T032419Z"),
        tmp_path / "runs" / "v4.0-9B-20260510T010203Z",
        tmp_path / "runs" / "latest",
    ]
    for bad in bad_roots:
        with pytest.raises(ValueError):
            sft_v4.validate_run_root(bad)


def test_phase8_handoff_and_raw_text_split_audit_require_green_gate(tmp_path: Path) -> None:
    sft_v4 = _contract()
    tokenized_dir = tmp_path / TOKENIZED_DIR
    for split in ["train", "val", "ood_val"]:
        _write_arrow_placeholder(
            tokenized_dir / f"{split}.arrow",
            [
                {
                    "sample_id": f"{split}-1",
                    "text": "<start_working_out>reason</end_working_out><SOLUTION>{\"1\": 30}</SOLUTION>",
                    "raw_text_protocol": True,
                    "chat_template_used": False,
                    "packing": False,
                }
            ],
        )
    phase8_report = _green_phase8_report(tmp_path)

    audit = sft_v4.build_sample_format_audit(tokenized_dir, phase8_report)

    assert audit["ok"] is True
    assert audit["phase8_gate"]["ok"] is True
    assert audit["phase8_gate"]["next_phase_allowed"] is True
    assert audit["tokenized_dir"] == str(tokenized_dir)
    assert audit["splits"] == {"train": 1, "val": 1, "ood_val": 1}
    assert audit["raw_text_protocol"] is True
    assert audit["packing"] is False
    assert audit["chat_template_used"] is False
    assert audit["forbidden_native_think_text_count"] == 0
    assert audit["forbidden_paths"] == []

    red_report = tmp_path / "red_phase8_gate.json"
    red_report.write_text(json.dumps({"ok": True, "next_phase_allowed": False}), encoding="utf-8")
    red = sft_v4.build_sample_format_audit(tokenized_dir, red_report)
    assert red["ok"] is False
    assert red["phase8_gate"]["next_phase_allowed"] is False


def test_load_arrow_split_preserves_metadata_only_when_requested(tmp_path: Path) -> None:
    sft_v4 = _contract()
    split = _write_arrow_placeholder(
        tmp_path / "train.arrow",
        [
            {
                "sample_id": "row-1",
                "input_ids": [1, 2, 3],
                "labels": [1, 2, 3],
                "metadata": {"lineage": "v4"},
            }
        ],
    )

    without_metadata = sft_v4.load_arrow_split(split)
    with_metadata = sft_v4.load_arrow_split(split, keep_metadata=True)

    assert len(without_metadata) == 1
    assert "metadata" not in without_metadata[0]
    assert with_metadata[0]["metadata"] == {"lineage": "v4"}


def test_hash_helpers_and_report_contract_require_phase9_evidence(tmp_path: Path) -> None:
    sft_v4 = _contract()
    adapter_dir = tmp_path / "runs" / "v4.0-4B-20260510T010203Z" / "adapter"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "adapter_model.safetensors").write_bytes(b"adapter-bytes")
    phase8_report = _green_phase8_report(tmp_path)

    adapter_hash = sft_v4.adapter_sha256(adapter_dir)
    data_hash = sft_v4.data_manifest_sha256(phase8_report)

    assert len(adapter_hash) == 64
    assert len(data_hash) == 64
    assert adapter_hash != data_hash

    report_contract = sft_v4.required_training_report_keys()
    assert REQUIRED_REPORT_KEYS <= set(report_contract)
