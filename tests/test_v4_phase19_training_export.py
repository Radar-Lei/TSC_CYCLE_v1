from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL = "Qwen/Qwen3-4B-Thinking-2507"
V42_TOKENIZED_DIR = Path("data/v4_2/phase18/tokenized")
PHASE18_REPORT = Path("artifacts/v4_2/phase18/reconstruction_report.json")
PHASE19_ARTIFACTS_DIR = Path("artifacts/v4_2/phase19")
FORBIDDEN_MARKERS = [
    "Qwen/Qwen3.5-9B",
    "data/tokenized/v3",
    "runs/v3.0-9B-",
    "runs/v4.0-4B-",
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


def _sft_v42_contract():
    from tsc_cycle.student import sft_v42  # noqa: PLC0415

    return sft_v42


def test_v42_training_defaults_lock_phase18_data_and_qwen4b_stack(tmp_path: Path) -> None:
    sft_v42 = _sft_v42_contract()

    assert sft_v42.MODEL_NAME == EXPECTED_MODEL
    assert sft_v42.RUN_ROOT_PREFIX == "v4.2-4B-"
    assert sft_v42.WANDB_PROJECT == "tsc-cycle-v4-4b"
    assert Path(sft_v42.TOKENIZED_DIR) == V42_TOKENIZED_DIR
    assert Path(sft_v42.PHASE18_RECONSTRUCTION_REPORT) == PHASE18_REPORT
    assert Path(sft_v42.PHASE19_ARTIFACTS_DIR) == PHASE19_ARTIFACTS_DIR

    assert sft_v42.locked_lora_config_kwargs() == {
        "r": 64,
        "lora_alpha": 64,
        "lora_dropout": 0.0,
        "target_modules": "all-linear",
        "bias": "none",
        "task_type": "CAUSAL_LM",
    }
    args = sft_v42.locked_training_arguments_kwargs(tmp_path / "runs" / "v4.2-4B-20260518T000000Z" / "full")
    assert args["bf16"] is True
    assert args["attn_implementation"] == "sdpa"
    assert args["packing"] is False
    assert args["chat_template_used"] is False
    assert args["apply_chat_template"] is False
    assert args["load_in_4bit"] is True
    assert args["bnb_4bit_quant_type"] == "nf4"
    assert args["bnb_4bit_compute_dtype"] in {"bfloat16", "bf16"}
    assert args["bnb_4bit_use_double_quant"] is True

    accepted = tmp_path / "runs" / "v4.2-4B-20260518T000000Z"
    assert sft_v42.validate_run_root(accepted) == accepted
    rejected = [
        tmp_path / "runs" / "v4.0-4B-20260509T184844Z",
        tmp_path / "runs" / "v3.0-9B-20260510T000000Z",
        Path("runs/20260507T032419Z"),
        tmp_path / "runs",
        tmp_path / "data" / "v4_2",
        tmp_path / "artifacts" / "v4_2",
        tmp_path / "runs" / "v4.2-4B-bad;rm",
    ]
    for bad in rejected:
        with pytest.raises(ValueError):
            sft_v42.validate_run_root(bad)

    defaults_text = json.dumps(
        {
            "model": sft_v42.MODEL_NAME,
            "run_prefix": sft_v42.RUN_ROOT_PREFIX,
            "tokenized_dir": str(sft_v42.TOKENIZED_DIR),
            "phase18_report": str(sft_v42.PHASE18_RECONSTRUCTION_REPORT),
            "phase19_artifacts": str(sft_v42.PHASE19_ARTIFACTS_DIR),
            "training_args": args,
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).lower()
    for forbidden in FORBIDDEN_MARKERS:
        assert forbidden.lower() not in defaults_text

    assert "TRAIN-01" in sft_v42.REQUIREMENTS_COVERED

    train_source = (PROJECT_ROOT / "tsc_cycle/student/train.py").read_text(encoding="utf-8")
    tree = ast.parse(train_source)
    phase_choices = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "--phase":
                for keyword in node.keywords:
                    if keyword.arg == "choices" and isinstance(keyword.value, ast.List):
                        phase_choices = [elt.value for elt in keyword.value.elts if isinstance(elt, ast.Constant)]
    assert "v4_2" in phase_choices
    assert "if args.phase == \"v4\"" in train_source
    assert "if args.phase == \"v4_2\"" in train_source
