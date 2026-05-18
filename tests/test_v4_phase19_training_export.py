from __future__ import annotations

import ast
import json
import sys
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
    assert "transformers" not in sys.modules
    assert "datasets" not in sys.modules

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
    v42_source = train_source[train_source.index('if args.phase == "v4_2"') : train_source.index('model_name = args.model or MODEL_NAME')]
    assert "require_canonical_tokenized_dir(data_dir, run_root)" in v42_source
    assert v42_source.index("require_canonical_tokenized_dir(data_dir, run_root)") < v42_source.index("load_qlora_model_and_tokenizer(model_name")


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

    missing_hash_report = _write_json(
        tmp_path / "missing_hash_phase18.json",
        {"ok": True, "next_phase_allowed": True, "requirements_covered": ["DATA-01", "DATA-02"], "splits": {"split_counts": {"train": 1, "val": 1, "ood_val": 1}}},
    )
    missing_hash_config = Phase19TrainingConfig(calibrated_jsonl=dataset, split_dir=split_dir, tokenized_dir=tmp_path / "missing-hash-tokenized", phase18_report=missing_hash_report, artifacts_dir=tmp_path / "missing-hash-artifacts")
    missing_hash = tokenize_phase18_handoff(missing_hash_config, tokenizer=FakeQwen4BTokenizer())
    assert missing_hash["ok"] is False
    assert any(failure["gate"] == "calibrated_jsonl_sha256" for failure in missing_hash["fatal_failures"])

    malformed_rows = [_phase19_sample("train-1", split="train"), _phase19_sample("val-1", split="val"), _phase19_sample("ood-1", split="ood_val")]
    malformed_rows[0]["result"]["solution"] = {"1": 20.5, "2": True}
    _write_jsonl(dataset, malformed_rows)
    malformed_report = _write_json(
        tmp_path / "malformed_phase18.json",
        {"ok": True, "next_phase_allowed": True, "requirements_covered": ["DATA-01", "DATA-02"], "dataset_hashes": {"calibrated_jsonl_sha256": __import__("hashlib").sha256(dataset.read_bytes()).hexdigest()}, "splits": {"split_counts": {"train": 1, "val": 1, "ood_val": 1}}},
    )
    malformed_config = Phase19TrainingConfig(calibrated_jsonl=dataset, split_dir=split_dir, tokenized_dir=tmp_path / "malformed-tokenized", phase18_report=malformed_report, artifacts_dir=tmp_path / "malformed-artifacts")
    malformed = tokenize_phase18_handoff(malformed_config, tokenizer=FakeQwen4BTokenizer())
    assert malformed["ok"] is False
    assert malformed["gates"]["native_think_token_leak"]["data"]["failures_sample"][0]["error"] == "malformed_solution"

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


def _make_phase19_lineage(root: Path) -> tuple[dict, dict, dict, dict]:
    phase18_root = root / "data/v4_2/phase18"
    calibrated = phase18_root / "labeled_calibrated.jsonl"
    calibrated.parent.mkdir(parents=True, exist_ok=True)
    calibrated.write_bytes(b"calibrated jsonl\n")
    phase18_report = root / "artifacts/v4_2/phase18/reconstruction_report.json"
    _write_json(phase18_report, {"ok": True, "next_phase_allowed": True, "requirements_covered": ["DATA-01", "DATA-02"]})
    tokenized_dir = phase18_root / "tokenized"
    tokenized_dir.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val", "ood_val"):
        (tokenized_dir / f"{split}.arrow").write_bytes(f"{split} arrow\n".encode("utf-8"))
    phase18 = {
        "calibrated_jsonl": str(calibrated),
        "calibrated_jsonl_sha256": __import__("hashlib").sha256(calibrated.read_bytes()).hexdigest(),
        "phase18_report": str(phase18_report),
        "phase18_report_sha256": __import__("hashlib").sha256(phase18_report.read_bytes()).hexdigest(),
    }
    tokenized_paths = {split: str(tokenized_dir / f"{split}.arrow") for split in ("train", "val", "ood_val")}
    tokenized_sha256 = {split: __import__("hashlib").sha256((tokenized_dir / f"{split}.arrow").read_bytes()).hexdigest() for split in ("train", "val", "ood_val")}
    phase18_artifact_hashes = {
        "calibrated_jsonl_sha256": phase18["calibrated_jsonl_sha256"],
        "phase18_report_sha256": phase18["phase18_report_sha256"],
        "train.arrow": tokenized_sha256["train"],
        "val.arrow": tokenized_sha256["val"],
        "ood_val.arrow": tokenized_sha256["ood_val"],
    }
    return phase18, tokenized_paths, tokenized_sha256, phase18_artifact_hashes


def test_phase19_training_report_gate_requires_v42_handoff_evidence(tmp_path: Path) -> None:
    from tsc_cycle.v4_gates.phase19_training import validate_phase19_training_report  # noqa: PLC0415

    run_root = tmp_path / "runs" / "v4.2-4B-20260518T120000Z"
    adapter_dir = run_root / "adapter"
    adapter_sha = _make_adapter(adapter_dir)
    phase18, tokenized_paths, tokenized_sha256, phase18_artifact_hashes = _make_phase19_lineage(tmp_path)
    data_manifest = _write_json(
        run_root / "phase19_data_manifest.json",
        {
            "phase18": phase18,
            "tokenized_paths": tokenized_paths,
            "tokenized_sha256": tokenized_sha256,
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
            "phase18_artifact_hashes": phase18_artifact_hashes,
            "training_args": {"bf16": True, "attn_implementation": "sdpa", "load_in_4bit": True, "bnb_4bit_quant_type": "nf4", "packing": False},
            "lora_config": {"r": 64, "lora_alpha": 64, "lora_dropout": 0.0, "target_modules": "all-linear"},
            "trainer_state": {"global_step": 657, "max_steps": 657},
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

    smoke = _read_json(report)
    smoke["mode"] = "smoke"
    smoke["trainer_state"] = {"global_step": 1, "max_steps": 1}
    smoke_report = _write_json(run_root / "smoke_report.json", smoke)
    smoke_rejected = validate_phase19_training_report(run_root, report_path=smoke_report)
    assert smoke_rejected["ok"] is False
    assert any(failure["gate"] == "completed" for failure in smoke_rejected["fatal_failures"])

    incomplete = _read_json(report)
    incomplete["trainer_state"] = {"global_step": 1, "max_steps": 657}
    incomplete_report = _write_json(run_root / "incomplete_report.json", incomplete)
    incomplete_rejected = validate_phase19_training_report(run_root, report_path=incomplete_report)
    assert incomplete_rejected["ok"] is False
    assert any(failure["gate"] == "completed" for failure in incomplete_rejected["fatal_failures"])

    forged_manifest_payload = _read_json(data_manifest)
    forged_manifest_payload["phase18"]["calibrated_jsonl_sha256"] = "x" * 64
    forged_manifest_payload["tokenized_sha256"]["train"] = "y" * 64
    forged_manifest_path = _write_json(run_root / "forged_data_manifest.json", forged_manifest_payload)
    forged_manifest = _read_json(report)
    forged_manifest["data_manifest_path"] = str(forged_manifest_path)
    forged_manifest["data_manifest_sha256"] = __import__("hashlib").sha256(forged_manifest_path.read_bytes()).hexdigest()
    forged_manifest["phase18_artifact_hashes"] = {"calibrated_jsonl_sha256": "x" * 64, "phase18_report_sha256": phase18_artifact_hashes["phase18_report_sha256"], "train.arrow": "y" * 64, "val.arrow": phase18_artifact_hashes["val.arrow"], "ood_val.arrow": phase18_artifact_hashes["ood_val.arrow"]}
    forged_manifest_report = _write_json(run_root / "forged_manifest_report.json", forged_manifest)
    forged_manifest_rejected = validate_phase19_training_report(run_root, report_path=forged_manifest_report)
    assert forged_manifest_rejected["ok"] is False
    assert any(failure["gate"] == "phase18_artifact_hashes" for failure in forged_manifest_rejected["fatal_failures"])

    outside_lineage = tmp_path / "outside" / "labeled_calibrated.jsonl"
    outside_lineage.parent.mkdir(parents=True, exist_ok=True)
    outside_lineage.write_bytes(b"calibrated jsonl\n")
    outside_manifest_payload = _read_json(data_manifest)
    outside_manifest_payload["phase18"]["calibrated_jsonl"] = str(outside_lineage)
    outside_manifest_path = _write_json(run_root / "outside_lineage_manifest.json", outside_manifest_payload)
    outside_lineage_report = _read_json(report)
    outside_lineage_report["data_manifest_path"] = str(outside_manifest_path)
    outside_lineage_report["data_manifest_sha256"] = __import__("hashlib").sha256(outside_manifest_path.read_bytes()).hexdigest()
    outside_lineage_report_path = _write_json(run_root / "outside_lineage_report.json", outside_lineage_report)
    outside_lineage_rejected = validate_phase19_training_report(run_root, report_path=outside_lineage_report_path)
    assert outside_lineage_rejected["ok"] is False
    assert any(failure["gate"] == "phase18_lineage_path" for failure in outside_lineage_rejected["fatal_failures"])

    from tsc_cycle.v4_gates.phase19_training import write_phase19_training_reports  # noqa: PLC0415

    with pytest.raises(ValueError, match="tokenized_dir must be canonical"):
        write_phase19_training_reports(run_root, mode="full", elapsed=1.0, trainer_state={"global_step": 1, "max_steps": 1}, adapter_dir=adapter_dir, targs_kwargs={"bf16": True}, tokenized_dir=tmp_path / "outside-tokenized")

    outside_adapter = tmp_path / "runs" / "v4.0-4B-20260509T184844Z" / "adapter"
    outside_adapter_sha = _make_adapter(outside_adapter)
    outside = _read_json(report)
    outside["adapter_path"] = str(outside_adapter)
    outside["adapter_sha256"] = outside_adapter_sha
    outside_report = _write_json(run_root / "outside_adapter_report.json", outside)
    outside_rejected = validate_phase19_training_report(run_root, report_path=outside_report)
    assert outside_rejected["ok"] is False
    assert any(failure["gate"] == "adapter_path" for failure in outside_rejected["fatal_failures"])

    wrong_adapter_config = _read_json(report)
    (adapter_dir / "adapter_config.json").write_text('{"base_model_name_or_path":"Qwen/Qwen3.5-9B"}\n', encoding="utf-8")
    wrong_adapter_report = _write_json(run_root / "wrong_adapter_config_report.json", wrong_adapter_config)
    wrong_adapter_rejected = validate_phase19_training_report(run_root, report_path=wrong_adapter_report)
    assert wrong_adapter_rejected["ok"] is False
    assert any(failure["gate"] == "adapter_config" for failure in wrong_adapter_rejected["fatal_failures"])
    (adapter_dir / "adapter_config.json").write_text('{"base_model_name_or_path":"Qwen/Qwen3-4B-Thinking-2507"}\n', encoding="utf-8")

    wrapper = (PROJECT_ROOT / "scripts/run_v4_phase19_train.sh").read_text(encoding="utf-8")
    assert "<<'PY'" in wrapper
    assert 'Path("$RUN_ROOT")' not in wrapper
    assert 'os.environ["RUN_ROOT"]' in wrapper
    assert "scripts/dgx_spark/run_safe.sh" in wrapper
    assert "100G --" in wrapper
    assert "tsc_cycle.student.train" in wrapper
    assert "--phase v4_2" in wrapper
    for forbidden in ["pip install", "uv pip install", "vllm", "flash-attn", "unsloth", "axolotl", "git worktree", "runs/20260507T032419Z"]:
        assert forbidden not in wrapper


def _make_phase19_training_handoff(run_root: Path) -> Path:
    adapter_dir = run_root / "adapter"
    adapter_sha = _make_adapter(adapter_dir)
    phase18, tokenized_paths, tokenized_sha256, phase18_artifact_hashes = _make_phase19_lineage(run_root.parents[1])
    data_manifest = _write_json(
        run_root / "phase19_data_manifest.json",
        {
            "phase18": phase18,
            "tokenized_paths": tokenized_paths,
            "tokenized_sha256": tokenized_sha256,
            "split_counts": {"train": 3500, "val": 452, "ood_val": 580},
            "requirements_covered": ["TRAIN-01"],
        },
    )
    data_sha = __import__("hashlib").sha256(data_manifest.read_bytes()).hexdigest()
    return _write_json(
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
            "phase18_artifact_hashes": phase18_artifact_hashes,
            "training_args": {"bf16": True, "attn_implementation": "sdpa", "load_in_4bit": True, "bnb_4bit_quant_type": "nf4", "packing": False},
            "lora_config": {"r": 64, "lora_alpha": 64, "lora_dropout": 0.0, "target_modules": "all-linear"},
            "trainer_state": {"global_step": 657, "max_steps": 657},
            "requirements_covered": ["TRAIN-01"],
            "completed": True,
        },
    )


def _make_fake_llama_cpp(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name in ("convert_hf_to_gguf.py", "llama-quantize", "llama-tokenize", "llama-server"):
        tool = root / name
        tool.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        tool.chmod(0o755)
    return root


def test_v42_export_plan_and_report_require_merged_hf_and_gguf_hashes(tmp_path: Path) -> None:
    from tsc_cycle.v4_gates.phase19_export import build_export_plan, validate_phase19_export_report, write_export_report  # noqa: PLC0415

    run_root = tmp_path / "runs" / "v4.2-4B-20260518T130000Z"
    training_report = _make_phase19_training_handoff(run_root)
    llama_cpp = _make_fake_llama_cpp(tmp_path / "llama.cpp")

    plan = build_export_plan(run_root=run_root, phase19_report=training_report, llama_cpp_dir=llama_cpp)

    assert plan["ok"] is True
    assert plan["requirements_covered"] == ["TRAIN-02"]
    assert plan["phase19_handoff"]["ok"] is True
    assert plan["phase19_handoff"]["requirements_covered"] == ["TRAIN-01"]
    assert Path(plan["paths"]["merged_hf"]) == run_root / "merged_hf"
    assert Path(plan["paths"]["gguf_fp16"]) == run_root / "gguf" / "model.fp16.gguf"
    assert Path(plan["paths"]["gguf_q4_K_M"]) == run_root / "gguf" / "model.q4_K_M.gguf"
    assert Path(plan["paths"]["export_report"]) == run_root / "phase19_export_report.json"
    commands_text = json.dumps(plan["commands"], ensure_ascii=False)
    assert "convert_hf_to_gguf.py" in commands_text
    assert "llama-quantize" in commands_text
    assert "Q4_K_M" in commands_text

    merged = run_root / "merged_hf"
    merged.mkdir(parents=True)
    (merged / "model.safetensors").write_bytes(b"merged hf weights")
    (merged / "tokenizer.json").write_text('{"tokenizer":"qwen"}\n', encoding="utf-8")
    (run_root / "gguf").mkdir(parents=True)
    (run_root / "gguf" / "model.fp16.gguf").write_bytes(b"fp16 gguf")
    (run_root / "gguf" / "model.q4_K_M.gguf").write_bytes(b"q4 gguf")

    report = write_export_report(run_root=run_root, export_plan=plan, out=run_root / "phase19_export_report.json")
    accepted = validate_phase19_export_report(run_root=run_root, report_path=run_root / "phase19_export_report.json")

    assert report["ok"] is True
    assert accepted["ok"] is True
    assert accepted["requirements_covered"] == ["TRAIN-02"]
    assert accepted["artifacts"]["gguf_fp16"]["sha256"] == __import__("hashlib").sha256(b"fp16 gguf").hexdigest()
    assert accepted["artifacts"]["gguf_q4_K_M"]["sha256"] == __import__("hashlib").sha256(b"q4 gguf").hexdigest()
    assert accepted["artifacts"]["merged_hf_safetensors"][0]["sha256"] == __import__("hashlib").sha256(b"merged hf weights").hexdigest()

    missing_train02 = _read_json(run_root / "phase19_export_report.json")
    missing_train02["requirements_covered"] = []
    missing_train02_path = _write_json(run_root / "missing_train02.json", missing_train02)
    rejected_train02 = validate_phase19_export_report(run_root=run_root, report_path=missing_train02_path)
    assert rejected_train02["ok"] is False
    assert any(failure["gate"] == "requirements_covered" for failure in rejected_train02["fatal_failures"])

    missing_hash = _read_json(run_root / "phase19_export_report.json")
    missing_hash["artifacts"]["gguf_q4_K_M"].pop("sha256")
    missing_hash_path = _write_json(run_root / "missing_hash.json", missing_hash)
    rejected_hash = validate_phase19_export_report(run_root=run_root, report_path=missing_hash_path)
    assert rejected_hash["ok"] is False
    assert any(failure["gate"] == "artifact_hash" for failure in rejected_hash["fatal_failures"])

    forged = _read_json(run_root / "phase19_export_report.json")
    (run_root / "gguf" / "model.q4_K_M.gguf").unlink()
    forged["artifacts"]["gguf_q4_K_M"]["exists"] = True
    forged["artifacts"]["gguf_q4_K_M"]["sha256"] = "f" * 64
    forged_path = _write_json(run_root / "forged_export_report.json", forged)
    rejected_forged = validate_phase19_export_report(run_root=run_root, report_path=forged_path)
    assert rejected_forged["ok"] is False
    assert any(failure["gate"] in {"artifact_exists", "artifact_hash"} for failure in rejected_forged["fatal_failures"])
    (run_root / "gguf" / "model.q4_K_M.gguf").write_bytes(b"q4 gguf")

    forged_handoff = _read_json(run_root / "phase19_export_report.json")
    bad_training = _read_json(training_report)
    bad_training["requirements_covered"] = []
    _write_json(training_report, bad_training)
    forged_handoff["phase19_handoff"] = {"ok": True, "next_phase_allowed": True, "requirements_covered": ["TRAIN-01"]}
    forged_handoff_path = _write_json(run_root / "forged_handoff_export_report.json", forged_handoff)
    rejected_handoff = validate_phase19_export_report(run_root=run_root, report_path=forged_handoff_path)
    assert rejected_handoff["ok"] is False
    assert any(failure["gate"] == "phase19_handoff" for failure in rejected_handoff["fatal_failures"])
    training_report = _make_phase19_training_handoff(run_root)

    with pytest.raises(ValueError):
        build_export_plan(run_root=tmp_path / "runs" / "v4.0-4B-20260509T184844Z", phase19_report=training_report, llama_cpp_dir=llama_cpp)
    with pytest.raises(ValueError):
        build_export_plan(run_root=tmp_path / "runs" / "20260507T032419Z", phase19_report=training_report, llama_cpp_dir=llama_cpp)
    with pytest.raises(ValueError):
        build_export_plan(run_root=run_root, phase19_report=training_report, llama_cpp_dir=llama_cpp, merged_dir=tmp_path / "outside" / "merged_hf")

    bad_training = _read_json(training_report)
    bad_training["requirements_covered"] = []
    bad_training_path = _write_json(run_root / "bad_training.json", bad_training)
    bad_plan = build_export_plan(run_root=run_root, phase19_report=bad_training_path, llama_cpp_dir=llama_cpp)
    assert bad_plan["ok"] is False
    assert any(failure["gate"] == "phase19_handoff" for failure in bad_plan["fatal_failures"])


def test_v42_wrappers_forbid_dependency_installs_unsupported_runtimes_and_frozen_roots(tmp_path: Path) -> None:
    from tsc_cycle.student.export_gguf import build_parser  # noqa: PLC0415
    from tsc_cycle.v4_gates.phase19_export import build_export_plan, phase19_wrapper_commands  # noqa: PLC0415

    run_root = tmp_path / "runs" / "v4.2-4B-20260518T140000Z"
    training_report = _make_phase19_training_handoff(run_root)
    llama_cpp = _make_fake_llama_cpp(tmp_path / "llama.cpp")
    parser = build_parser()

    phase10_defaults = parser.parse_args([])
    assert phase10_defaults.phase9_report.endswith("phase9_sft_report.json")
    assert "v4.0-4B-20260509T184844Z" in phase10_defaults.run_root

    export_source = (PROJECT_ROOT / "tsc_cycle/student/export_gguf.py").read_text(encoding="utf-8")
    assert "trust_remote_code=not enforce_base_model" in export_source
    assert "tokenizer_source = model_name if enforce_base_model else adapter_dir" in export_source

    phase19_defaults = parser.parse_args(["--export-phase", "phase19", "--run-root", str(run_root), "--llama-cpp", str(llama_cpp)])
    assert Path(phase19_defaults.phase19_report) == run_root / "phase19_sft_report.json"

    phase19_args = parser.parse_args(["--export-phase", "phase19", "--run-root", str(run_root), "--phase19-report", str(training_report), "--llama-cpp", str(llama_cpp)])
    assert phase19_args.export_phase == "phase19"
    assert Path(phase19_args.phase19_report) == training_report
    assert Path(phase19_args.merged_dir) == run_root / "merged_hf"
    assert Path(phase19_args.fp16_gguf) == run_root / "gguf" / "model.fp16.gguf"
    assert Path(phase19_args.q4_gguf) == run_root / "gguf" / "model.q4_K_M.gguf"
    assert Path(phase19_args.report) == run_root / "phase19_export_report.json"

    wrapper_path = PROJECT_ROOT / "scripts/run_v4_phase19_export.sh"
    wrapper = wrapper_path.read_text(encoding="utf-8")
    assert "scripts/dgx_spark/run_safe.sh" in wrapper
    assert "100G --" in wrapper
    assert "python" in wrapper and "-m tsc_cycle.student.export_gguf" in wrapper
    assert "--export-phase phase19" in wrapper
    assert "--phase19-report" in wrapper
    assert "phase19_sft_report.json" in wrapper
    assert "phase19_export_report.json" in wrapper
    assert "runs/v4.2-4B-" in wrapper

    plan = build_export_plan(run_root=run_root, phase19_report=training_report, llama_cpp_dir=llama_cpp)
    commands_text = json.dumps({"wrapper": wrapper, "commands": plan["commands"], "phase19_wrapper_commands": phase19_wrapper_commands(run_root, llama_cpp)}, ensure_ascii=False).lower()
    for forbidden in ["pip install", "uv pip install", "vllm", "flash-attn", "flash_attn", "unsloth", "axolotl", "git worktree", "runs/20260507T032419Z", "runs/v4.0-4B-"]:
        assert forbidden.lower() not in commands_text
    assert "scripts/dgx_spark/run_safe.sh" in commands_text
    assert "convert_hf_to_gguf.py" in commands_text
    assert "llama-quantize" in commands_text
    assert str(run_root).lower() in commands_text

    for broad in [tmp_path, tmp_path / "runs", tmp_path / "data", tmp_path / "artifacts"]:
        with pytest.raises(ValueError):
            build_export_plan(run_root=broad, phase19_report=training_report, llama_cpp_dir=llama_cpp)
    with pytest.raises(ValueError):
        build_export_plan(run_root=run_root, phase19_report=training_report, llama_cpp_dir=llama_cpp, q4_gguf=tmp_path / "outside.gguf")
