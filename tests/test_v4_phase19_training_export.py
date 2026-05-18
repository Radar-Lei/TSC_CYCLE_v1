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


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
    return path


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


class FakeQwen4BTokenizer:
    eos_token = "<eos>"

    def __init__(self) -> None:
        self.chat_template_used = False
        self.calls: list[dict] = []
        self.checked_untruncated_native_ids: list[list[int]] = []

    def __len__(self) -> int:
        return 151669

    def apply_chat_template(self, *args, **kwargs) -> None:
        self.chat_template_used = True
        raise AssertionError("Phase 19 tokenization must use raw prompt/assistant text")

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        assert add_special_tokens is False
        if text == "<think>":
            return [151667]
        if text == "</think>":
            return [151668]
        return self._ids(text)

    def __call__(self, text: str, *, add_special_tokens: bool = False, truncation: bool = False, max_length: int | None = None) -> dict[str, list[int]]:
        assert add_special_tokens is False
        ids = self._ids(text)
        self.calls.append({"add_special_tokens": add_special_tokens, "truncation": truncation, "max_length": max_length, "ids": list(ids)})
        if not truncation and any(token_id in {151667, 151668} for token_id in ids):
            self.checked_untruncated_native_ids.append(list(ids))
        if truncation and max_length is not None:
            ids = ids[:max_length]
        return {"input_ids": ids}

    def _ids(self, text: str) -> list[int]:
        ids: list[int] = []
        i = 0
        while i < len(text):
            if text.startswith("<think>", i):
                ids.append(151667)
                i += len("<think>")
            elif text.startswith("</think>", i):
                ids.append(151668)
                i += len("</think>")
            else:
                ids.append(1000 + (ord(text[i]) % 200))
                i += 1
        return ids


def _phase19_sample(sample_id: str, reasoning: str = "Balance green time by calibrated saturation.", split: str = "train") -> dict:
    return {
        "sample_id": sample_id,
        "split": split,
        "source": "same_dist",
        "input": {
            "sample_id": sample_id,
            "prediction": {
                "as_of": "2026-05-18 00:00:00",
                "phase_waits": [
                    {"phase_id": 1, "pred_wait": 5.0, "pred_saturation": 0.20, "min_green": 10, "max_green": 60, "capacity": 40},
                    {"phase_id": 2, "pred_wait": 12.0, "pred_saturation": 0.55, "min_green": 15, "max_green": 70, "capacity": 40},
                ],
            },
        },
        "result": {"success": True, "reasoning": reasoning, "solution": {"1": 20, "2": 38}},
    }


def test_phase18_handoff_tokenizes_calibrated_splits_with_protocol_hashes(tmp_path: Path) -> None:
    from tsc_cycle.v4_gates.phase19_training import Phase19TrainingConfig, tokenize_phase18_handoff  # noqa: PLC0415

    rows = [_phase19_sample("train-1", split="train"), _phase19_sample("val-1", split="val"), _phase19_sample("ood-1", split="ood_val")]
    dataset = _write_jsonl(tmp_path / "data/v4_2/phase18/labeled_calibrated.jsonl", rows)
    split_dir = tmp_path / "data/v4_2/phase18/splits"
    for split, sample_id in {"train": "train-1", "val": "val-1", "ood_val": "ood-1"}.items():
        _write_jsonl(split_dir / f"{split}.index.jsonl", [{"sample_id": sample_id, "split": split, "record_hash": "r" * 64, "prompt_hash": "p" * 64, "assistant_hash": "a" * 64}])
    _write_json(split_dir / "manifest.json", {"ok": True, "split_counts": {"train": 1, "val": 1, "ood_val": 1}, "split_ids_sha256": {"train": "t", "val": "v", "ood_val": "o"}})
    report = _write_json(
        tmp_path / "artifacts/v4_2/phase18/reconstruction_report.json",
        {
            "ok": True,
            "next_phase_allowed": True,
            "requirements_covered": ["DATA-01", "DATA-02"],
            "counts": {"retained_rows": 3},
            "dataset_hashes": {"calibrated_jsonl_sha256": __import__("hashlib").sha256(dataset.read_bytes()).hexdigest()},
            "splits": {"split_counts": {"train": 1, "val": 1, "ood_val": 1}},
        },
    )
    config = Phase19TrainingConfig(
        calibrated_jsonl=dataset,
        split_dir=split_dir,
        tokenized_dir=tmp_path / V42_TOKENIZED_DIR,
        phase18_report=report,
        artifacts_dir=tmp_path / PHASE19_ARTIFACTS_DIR,
        max_seq_length=2048,
    )

    result = tokenize_phase18_handoff(config, tokenizer=FakeQwen4BTokenizer())

    assert result["ok"] is True
    assert result["requirements_covered"] == ["TRAIN-01"]
    assert result["split_counts"] == {"train": 1, "val": 1, "ood_val": 1}
    assert result["phase18"]["calibrated_jsonl_sha256"] == __import__("hashlib").sha256(dataset.read_bytes()).hexdigest()
    assert "phase18_report_sha256" in result["phase18"]
    assert result["gates"]["phase18_handoff"]["ok"] is True
    assert result["gates"]["native_think_token_leak"]["ok"] is True
    assert result["gates"]["split_counts"]["ok"] is True
    manifest = _read_json(config.tokenized_dir / "manifest.json")
    assert manifest["ok"] is True
    assert manifest["split_counts"] == {"train": 1, "val": 1, "ood_val": 1}
    assert set(manifest["tokenized_sha256"]) == {"train", "val", "ood_val"}
    for split in ("train", "val", "ood_val"):
        arrow_path = config.tokenized_dir / f"{split}.arrow"
        assert arrow_path.exists()
        table = __import__("pyarrow").ipc.open_file(__import__("pyarrow").memory_map(str(arrow_path), "r")).read_all()
        assert table.num_rows == 1
        assert {"sample_id", "input_ids", "attention_mask", "labels", "raw_length", "truncated", "prompt_hash", "assistant_hash"} <= set(table.column_names)

    bad_report = _write_json(tmp_path / "bad_phase18.json", {"ok": False, "next_phase_allowed": False})
    bad_config = Phase19TrainingConfig(calibrated_jsonl=dataset, split_dir=split_dir, tokenized_dir=tmp_path / "bad-tokenized", phase18_report=bad_report, artifacts_dir=tmp_path / "bad-artifacts")
    bad = tokenize_phase18_handoff(bad_config, tokenizer=FakeQwen4BTokenizer())
    assert bad["ok"] is False
    assert any(failure["gate"] == "phase18_handoff" for failure in bad["fatal_failures"])

    leak_rows = [_phase19_sample("train-1", reasoning="native <think> leak", split="train"), _phase19_sample("val-1", split="val"), _phase19_sample("ood-1", split="ood_val")]
    _write_jsonl(dataset, leak_rows)
    leak_report = _write_json(
        tmp_path / "leak_phase18.json",
        {"ok": True, "next_phase_allowed": True, "requirements_covered": ["DATA-01", "DATA-02"], "dataset_hashes": {"calibrated_jsonl_sha256": __import__("hashlib").sha256(dataset.read_bytes()).hexdigest()}, "splits": {"split_counts": {"train": 1, "val": 1, "ood_val": 1}}},
    )
    leak_config = Phase19TrainingConfig(calibrated_jsonl=dataset, split_dir=split_dir, tokenized_dir=tmp_path / "leak-tokenized", phase18_report=leak_report, artifacts_dir=tmp_path / "leak-artifacts")
    leak = tokenize_phase18_handoff(leak_config, tokenizer=FakeQwen4BTokenizer())
    assert leak["ok"] is False
    assert leak["gates"]["native_think_token_leak"]["ok"] is False
    assert not (leak_config.tokenized_dir / "train.arrow").exists()


def _make_adapter(adapter_dir: Path) -> str:
    adapter_dir.mkdir(parents=True, exist_ok=True)
    (adapter_dir / "adapter_config.json").write_text('{"base_model_name_or_path":"Qwen/Qwen3-4B-Thinking-2507"}\n', encoding="utf-8")
    weights = adapter_dir / "adapter_model.safetensors"
    weights.write_bytes(b"phase19 adapter bytes")
    return __import__("hashlib").sha256(weights.read_bytes()).hexdigest()


def test_phase19_training_report_gate_requires_v42_handoff_evidence(tmp_path: Path) -> None:
    from tsc_cycle.v4_gates.phase19_training import validate_phase19_training_report  # noqa: PLC0415

    run_root = tmp_path / "runs" / "v4.2-4B-20260518T120000Z"
    adapter_dir = run_root / "adapter"
    adapter_sha = _make_adapter(adapter_dir)
    data_manifest = _write_json(
        run_root / "phase19_data_manifest.json",
        {
            "phase18": {"calibrated_jsonl_sha256": "c" * 64, "phase18_report_sha256": "r" * 64},
            "tokenized_sha256": {"train": "t" * 64, "val": "v" * 64, "ood_val": "o" * 64},
            "split_counts": {"train": 3500, "val": 452, "ood_val": 580},
            "requirements_covered": ["TRAIN-01"],
        },
    )
    data_sha = __import__("hashlib").sha256(data_manifest.read_bytes()).hexdigest()
    report = _write_json(
        run_root / "phase19_sft_report.json",
        {
            "ok": True,
            "next_phase_allowed": True,
            "model_name": EXPECTED_MODEL,
            "run_root": str(run_root),
            "mode": "full",
            "loss_curve": [{"step": 1, "loss": 1.25}],
            "duration_seconds": 123.0,
            "vram_peak_gb": 42.0,
            "adapter_path": str(adapter_dir),
            "adapter_sha256": adapter_sha,
            "data_manifest_path": str(data_manifest),
            "data_manifest_sha256": data_sha,
            "phase18_artifact_hashes": {"calibrated_jsonl_sha256": "c" * 64, "phase18_report_sha256": "r" * 64, "train.arrow": "t" * 64, "val.arrow": "v" * 64, "ood_val.arrow": "o" * 64},
            "training_args": {"bf16": True, "attn_implementation": "sdpa", "load_in_4bit": True, "bnb_4bit_quant_type": "nf4", "packing": False},
            "lora_config": {"r": 64, "lora_alpha": 64, "lora_dropout": 0.0, "target_modules": "all-linear"},
            "requirements_covered": ["TRAIN-01"],
            "completed": True,
        },
    )

    accepted = validate_phase19_training_report(run_root, report_path=report)

    assert accepted["ok"] is True
    assert accepted["next_phase_allowed"] is True
    assert accepted["requirements_covered"] == ["TRAIN-01"]
    assert accepted["artifact_manifest"]["sha256"]["adapter_sha256"] == adapter_sha
    assert accepted["artifact_manifest"]["sha256"]["data_manifest_sha256"] == data_sha
    assert accepted["gates"]["phase18_artifact_hashes"]["ok"] is True

    wrong_model = _read_json(report)
    wrong_model["model_name"] = "Qwen/Qwen3.5-9B"
    wrong_report = _write_json(run_root / "wrong_model.json", wrong_model)
    rejected = validate_phase19_training_report(run_root, report_path=wrong_report)
    assert rejected["ok"] is False
    assert any(failure["gate"] == "model_config" for failure in rejected["fatal_failures"])

    v40_root = tmp_path / "runs" / "v4.0-4B-20260509T184844Z"
    v40_report = dict(_read_json(report), run_root=str(v40_root))
    bad_root_report = _write_json(run_root / "bad_root.json", v40_report)
    bad_root = validate_phase19_training_report(v40_root, report_path=bad_root_report)
    assert bad_root["ok"] is False
    assert any(failure["gate"] == "run_root" for failure in bad_root["fatal_failures"])

    missing_hashes = _read_json(report)
    missing_hashes["phase18_artifact_hashes"] = {}
    missing_report = _write_json(run_root / "missing_hashes.json", missing_hashes)
    missing = validate_phase19_training_report(run_root, report_path=missing_report)
    assert missing["ok"] is False
    assert any(failure["gate"] == "phase18_artifact_hashes" for failure in missing["fatal_failures"])

    wrapper = (PROJECT_ROOT / "scripts/run_v4_phase19_train.sh").read_text(encoding="utf-8")
    assert "scripts/dgx_spark/run_safe.sh" in wrapper
    assert "100G --" in wrapper
    assert "tsc_cycle.student.train" in wrapper
    assert "--phase v4_2" in wrapper
    for forbidden in ["pip install", "uv pip install", "vllm", "flash-attn", "unsloth", "axolotl", "git worktree", "runs/20260507T032419Z"]:
        assert forbidden not in wrapper
