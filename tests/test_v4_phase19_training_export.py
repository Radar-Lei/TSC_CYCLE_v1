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

    phase19_source = (PROJECT_ROOT / "tsc_cycle/v4_gates/phase19_training.py").read_text(encoding="utf-8")
    assert "AutoTokenizer.from_pretrained(config.model_name, trust_remote_code=False, local_files_only=True)" in phase19_source

    train_source = (PROJECT_ROOT / "tsc_cycle/student/train.py").read_text(encoding="utf-8")
    assert "full v4.2 training must not use --max-steps" in train_source
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
    assert "validate_phase19_pretrain_inputs(run_root, tokenized_dir=data_dir)" in v42_source
    assert v42_source.index("require_canonical_tokenized_dir(data_dir, run_root)") < v42_source.index("validate_phase19_pretrain_inputs(run_root, tokenized_dir=data_dir)") < v42_source.index("load_qlora_model_and_tokenizer(model_name")


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
    split_ids_sha256 = {}
    for split, sample_id in {"train": "train-1", "val": "val-1", "ood_val": "ood-1"}.items():
        _write_jsonl(split_dir / f"{split}.index.jsonl", [{"sample_id": sample_id, "split": split, "record_hash": "r" * 64, "prompt_hash": "p" * 64, "assistant_hash": "a" * 64}])
        split_ids_sha256[split] = __import__("hashlib").sha256(json.dumps([sample_id], ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()
    _write_json(split_dir / "manifest.json", {"ok": True, "split_counts": {"train": 1, "val": 1, "ood_val": 1}, "split_ids_sha256": split_ids_sha256})
    report = _write_json(
        tmp_path / "artifacts/v4_2/phase18/reconstruction_report.json",
        {
            "ok": True,
            "next_phase_allowed": True,
            "requirements_covered": ["DATA-01", "DATA-02"],
            "counts": {"retained_rows": 3},
            "dataset_hashes": {"calibrated_jsonl_sha256": __import__("hashlib").sha256(dataset.read_bytes()).hexdigest()},
            "splits": {"split_counts": {"train": 1, "val": 1, "ood_val": 1}, "split_ids_sha256": split_ids_sha256},
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
    assert result["gates"]["phase18_handoff"]["ok"] is True
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

    co_tamper_report = _write_json(
        tmp_path / "co_tamper_phase18.json",
        {"ok": True, "next_phase_allowed": True, "requirements_covered": ["DATA-01", "DATA-02"], "dataset_hashes": {"calibrated_jsonl_sha256": __import__("hashlib").sha256(dataset.read_bytes()).hexdigest()}, "splits": {"split_counts": {"train": 1, "val": 1, "ood_val": 1}, "split_ids_sha256": dict(split_ids_sha256, train="x" * 64)}},
    )
    co_tamper = tokenize_phase18_handoff(Phase19TrainingConfig(calibrated_jsonl=dataset, split_dir=split_dir, tokenized_dir=tmp_path / "co-tamper-tokenized", phase18_report=co_tamper_report, artifacts_dir=tmp_path / "co-tamper-artifacts"), tokenizer=FakeQwen4BTokenizer())
    assert co_tamper["ok"] is False
    assert any(failure["gate"] == "split_ids" for failure in co_tamper["fatal_failures"])

    bad_report = _write_json(tmp_path / "bad_phase18.json", {"ok": False, "next_phase_allowed": False})
    bad_config = Phase19TrainingConfig(calibrated_jsonl=dataset, split_dir=split_dir, tokenized_dir=tmp_path / "bad-tokenized", phase18_report=bad_report, artifacts_dir=tmp_path / "bad-artifacts")
    bad = tokenize_phase18_handoff(bad_config, tokenizer=FakeQwen4BTokenizer())
    assert bad["ok"] is False
    assert any(failure["gate"] == "phase18_handoff" for failure in bad["fatal_failures"])

    missing_hash_report = _write_json(
        tmp_path / "missing_hash_phase18.json",
        {"ok": True, "next_phase_allowed": True, "requirements_covered": ["DATA-01", "DATA-02"], "splits": {"split_counts": {"train": 1, "val": 1, "ood_val": 1}, "split_ids_sha256": split_ids_sha256}},
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
        {"ok": True, "next_phase_allowed": True, "requirements_covered": ["DATA-01", "DATA-02"], "dataset_hashes": {"calibrated_jsonl_sha256": __import__("hashlib").sha256(dataset.read_bytes()).hexdigest()}, "splits": {"split_counts": {"train": 1, "val": 1, "ood_val": 1}, "split_ids_sha256": split_ids_sha256}},
    )
    malformed_config = Phase19TrainingConfig(calibrated_jsonl=dataset, split_dir=split_dir, tokenized_dir=tmp_path / "malformed-tokenized", phase18_report=malformed_report, artifacts_dir=tmp_path / "malformed-artifacts")
    malformed = tokenize_phase18_handoff(malformed_config, tokenizer=FakeQwen4BTokenizer())
    assert malformed["ok"] is False
    assert malformed["gates"]["native_think_token_leak"]["data"]["failures_sample"][0]["error"] == "malformed_solution"

    leak_rows = [_phase19_sample("train-1", reasoning="native <think> leak", split="train"), _phase19_sample("val-1", split="val"), _phase19_sample("ood-1", split="ood_val")]
    _write_jsonl(dataset, leak_rows)
    leak_report = _write_json(
        tmp_path / "leak_phase18.json",
        {"ok": True, "next_phase_allowed": True, "requirements_covered": ["DATA-01", "DATA-02"], "dataset_hashes": {"calibrated_jsonl_sha256": __import__("hashlib").sha256(dataset.read_bytes()).hexdigest()}, "splits": {"split_counts": {"train": 1, "val": 1, "ood_val": 1}, "split_ids_sha256": split_ids_sha256}},
    )
    leak_config = Phase19TrainingConfig(calibrated_jsonl=dataset, split_dir=split_dir, tokenized_dir=tmp_path / "leak-tokenized", phase18_report=leak_report, artifacts_dir=tmp_path / "leak-artifacts")
    leak = tokenize_phase18_handoff(leak_config, tokenizer=FakeQwen4BTokenizer())
    assert leak["ok"] is False
    assert leak["gates"]["native_think_token_leak"]["ok"] is False
    assert not (leak_config.tokenized_dir / "train.arrow").exists()


def test_phase19_training_default_cli_fails_closed_without_handoff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from tsc_cycle.v4_gates import phase19_training  # noqa: PLC0415

    original_config = phase19_training.Phase19TrainingConfig
    artifacts_dir = tmp_path / PHASE19_ARTIFACTS_DIR
    monkeypatch.setattr(
        phase19_training,
        "Phase19TrainingConfig",
        lambda: original_config(
            calibrated_jsonl=tmp_path / "data/v4_2/phase18/labeled_calibrated.jsonl",
            split_dir=tmp_path / "data/v4_2/phase18/splits",
            tokenized_dir=tmp_path / V42_TOKENIZED_DIR,
            phase18_report=tmp_path / PHASE18_REPORT,
            artifacts_dir=artifacts_dir,
        ),
    )

    exit_code = phase19_training.main([])
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert output["ok"] is False
    assert output["requirements_covered"] == []
    assert any(failure["gate"] == "phase18_handoff" for failure in output["fatal_failures"])
    assert _read_json(artifacts_dir / "tokenization_report.json") == output


def _hash_directory(root: Path) -> str:
    h = __import__("hashlib").sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        h.update(path.relative_to(root).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
    return h.hexdigest()


def _make_adapter(adapter_dir: Path) -> str:
    adapter_dir.mkdir(parents=True, exist_ok=True)
    (adapter_dir / "adapter_config.json").write_text('{"base_model_name_or_path":"Qwen/Qwen3-4B-Thinking-2507"}\n', encoding="utf-8")
    weights = adapter_dir / "adapter_model.safetensors"
    weights.write_bytes(b"phase19 adapter bytes")
    return _hash_directory(adapter_dir)


def _locked_phase19_training_args() -> dict:
    return {
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
        "dataloader_num_workers": 1,
        "remove_unused_columns": False,
        "weight_decay": 0.0,
        "packing": False,
        "attn_implementation": "sdpa",
        "load_in_4bit": True,
        "bnb_4bit_quant_type": "nf4",
        "bnb_4bit_compute_dtype": "bfloat16",
        "bnb_4bit_use_double_quant": True,
        "chat_template_used": False,
        "apply_chat_template": False,
    }


def _locked_phase19_lora_config() -> dict:
    return {"r": 64, "lora_alpha": 64, "lora_dropout": 0.0, "target_modules": "all-linear", "bias": "none", "task_type": "CAUSAL_LM"}


def _copy_phase19_lineage(root: Path) -> Path:
    import shutil

    for relative in [
        "data/v4_2/phase18/labeled_calibrated.jsonl",
        "artifacts/v4_2/phase18/reconstruction_report.json",
        "artifacts/v4_2/phase19/tokenization_report.json",
    ]:
        source = PROJECT_ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for relative in ["data/v4_2/phase18/splits", "data/v4_2/phase18/tokenized"]:
        shutil.copytree(PROJECT_ROOT / relative, root / relative, dirs_exist_ok=True)
    return root


def _make_phase19_lineage(root: Path) -> tuple[dict, dict, dict, dict]:
    manifest = _read_json(root / "data/v4_2/phase18/tokenized/manifest.json")
    phase18 = dict(manifest["phase18"])
    phase18["calibrated_jsonl"] = str(root / "data/v4_2/phase18/labeled_calibrated.jsonl")
    phase18["phase18_report"] = str(root / "artifacts/v4_2/phase18/reconstruction_report.json")
    phase18["split_manifest"] = str(root / "data/v4_2/phase18/splits/manifest.json")
    tokenized_paths = {split: str(root / f"data/v4_2/phase18/tokenized/{split}.arrow") for split in ("train", "val", "ood_val")}
    tokenized_sha256 = manifest["tokenized_sha256"]
    phase18_artifact_hashes = {
        "calibrated_jsonl_sha256": phase18["calibrated_jsonl_sha256"],
        "phase18_report_sha256": phase18["phase18_report_sha256"],
        "train.arrow": tokenized_sha256["train"],
        "val.arrow": tokenized_sha256["val"],
        "ood_val.arrow": tokenized_sha256["ood_val"],
    }
    return phase18, tokenized_paths, tokenized_sha256, phase18_artifact_hashes


def test_phase19_training_report_gate_requires_v42_handoff_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tsc_cycle.v4_gates import phase19_training as phase19_gate  # noqa: PLC0415

    lineage_root = _copy_phase19_lineage(tmp_path / "lineage")
    monkeypatch.setattr(phase19_gate, "PROJECT_ROOT", lineage_root)
    validate_phase19_training_report = phase19_gate.validate_phase19_training_report
    run_root = tmp_path / "runs" / "v4.2-4B-20260518T120000Z"
    adapter_dir = run_root / "adapter"
    adapter_sha = _make_adapter(adapter_dir)
    phase18, tokenized_paths, tokenized_sha256, phase18_artifact_hashes = _make_phase19_lineage(lineage_root)
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
            "training_args": _locked_phase19_training_args(),
            "lora_config": _locked_phase19_lora_config(),
            "trainer_state": {"global_step": 657, "max_steps": 657},
            "requirements_covered": ["TRAIN-01"],
            "completed": True,
        },
    )

    non_object_phase18 = run_root / "non_object_phase18.json"
    non_object_phase18.write_text("[]\n", encoding="utf-8")
    handoff_rejected = _sft_v42_contract().check_phase18_handoff(non_object_phase18)
    assert handoff_rejected["ok"] is False
    assert any("must be an object" in failure["reason"] for failure in handoff_rejected["fatal_failures"])
    bad_requirements_phase18 = _write_json(run_root / "bad_requirements_phase18.json", {"ok": True, "next_phase_allowed": True, "requirements_covered": 1})
    bad_requirements_rejected = _sft_v42_contract().check_phase18_handoff(bad_requirements_phase18)
    assert bad_requirements_rejected["ok"] is False
    assert any("must be a list" in failure["reason"] for failure in bad_requirements_rejected["fatal_failures"])
    malformed_failures_phase18 = _write_json(run_root / "malformed_failures_phase18.json", {"ok": False, "next_phase_allowed": False, "requirements_covered": ["DATA-01", "DATA-02"], "fatal_failures": "bad"})
    malformed_failures_rejected = _sft_v42_contract().check_phase18_handoff(malformed_failures_phase18)
    assert malformed_failures_rejected["ok"] is False
    assert isinstance(malformed_failures_rejected["fatal_failures"], list)
    assert any("fatal_failures must be a list" in failure["reason"] for failure in malformed_failures_rejected["fatal_failures"])
    nonempty_failures_phase18 = _write_json(run_root / "nonempty_failures_phase18.json", {"ok": True, "next_phase_allowed": True, "requirements_covered": ["DATA-01", "DATA-02"], "fatal_failures": [{"gate": "x", "reason": "bad"}]})
    nonempty_failures_rejected = _sft_v42_contract().check_phase18_handoff(nonempty_failures_phase18)
    assert nonempty_failures_rejected["ok"] is False
    assert nonempty_failures_rejected["fatal_failures"]

    accepted = validate_phase19_training_report(run_root, report_path=report)

    assert accepted["ok"] is True
    assert accepted["next_phase_allowed"] is True
    assert accepted["requirements_covered"] == ["TRAIN-01"]
    assert accepted["artifact_manifest"]["sha256"]["adapter_sha256"] == adapter_sha
    assert accepted["artifact_manifest"]["sha256"]["data_manifest_sha256"] == data_sha
    assert accepted["gates"]["phase18_artifact_hashes"]["ok"] is True

    malformed_training_coverage = _read_json(report)
    malformed_training_coverage["requirements_covered"] = {"TRAIN-01": False}
    malformed_training_coverage_report = _write_json(run_root / "malformed_training_coverage.json", malformed_training_coverage)
    malformed_training_coverage_rejected = validate_phase19_training_report(run_root, report_path=malformed_training_coverage_report)
    assert malformed_training_coverage_rejected["ok"] is False
    assert any(failure["gate"] == "requirements_covered" and "must be a list" in failure["reason"] for failure in malformed_training_coverage_rejected["fatal_failures"])

    nonempty_training_failures = _read_json(report)
    nonempty_training_failures["fatal_failures"] = [{"gate": "x", "reason": "bad"}]
    nonempty_training_failures_report = _write_json(run_root / "nonempty_training_failures.json", nonempty_training_failures)
    nonempty_training_failures_rejected = validate_phase19_training_report(run_root, report_path=nonempty_training_failures_report)
    assert nonempty_training_failures_rejected["ok"] is False
    assert any(failure["gate"] == "fatal_failures" for failure in nonempty_training_failures_rejected["fatal_failures"])

    wrong_lora = _read_json(report)
    wrong_lora["lora_config"]["target_modules"] = ["q_proj"]
    wrong_lora_report = _write_json(run_root / "wrong_lora.json", wrong_lora)
    wrong_lora_rejected = validate_phase19_training_report(run_root, report_path=wrong_lora_report)
    assert wrong_lora_rejected["ok"] is False
    assert any(failure["gate"] == "qlora_settings" for failure in wrong_lora_rejected["fatal_failures"])

    wrong_args = _read_json(report)
    wrong_args["training_args"]["bnb_4bit_use_double_quant"] = False
    wrong_args["training_args"]["chat_template_used"] = True
    wrong_args_report = _write_json(run_root / "wrong_args.json", wrong_args)
    wrong_args_rejected = validate_phase19_training_report(run_root, report_path=wrong_args_report)
    assert wrong_args_rejected["ok"] is False
    assert any(failure["gate"] == "training_args" for failure in wrong_args_rejected["fatal_failures"])

    bounded_args = _read_json(report)
    bounded_args["training_args"]["max_steps"] = 1
    bounded_args["trainer_state"] = {"global_step": 1, "max_steps": 1}
    bounded_args_report = _write_json(run_root / "bounded_args.json", bounded_args)
    bounded_args_rejected = validate_phase19_training_report(run_root, report_path=bounded_args_report)
    assert bounded_args_rejected["ok"] is False
    assert any(failure["gate"] in {"training_args", "completed"} for failure in bounded_args_rejected["fatal_failures"])

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

    outside_report = _write_json(tmp_path / "outside_phase19_sft_report.json", _read_json(report))
    outside_report_rejected = validate_phase19_training_report(run_root, report_path=outside_report)
    assert outside_report_rejected["ok"] is False
    assert any(failure["gate"] == "report_path" for failure in outside_report_rejected["fatal_failures"])

    report_dir = run_root / "phase19_sft_report_dir.json"
    report_dir.mkdir()
    report_dir_rejected = validate_phase19_training_report(run_root, report_path=report_dir)
    assert report_dir_rejected["ok"] is False
    assert any(failure["gate"] == "model_config" for failure in report_dir_rejected["fatal_failures"])

    bad_steps = _read_json(report)
    bad_steps["trainer_state"] = {"global_step": "abc", "max_steps": "def"}
    bad_steps_report = _write_json(run_root / "bad_steps.json", bad_steps)
    bad_steps_rejected = validate_phase19_training_report(run_root, report_path=bad_steps_report)
    assert bad_steps_rejected["ok"] is False
    assert any(failure["gate"] == "completed" and "non-negative integer" in failure["reason"] for failure in bad_steps_rejected["fatal_failures"])

    next_phase_false = _read_json(report)
    next_phase_false["next_phase_allowed"] = False
    next_phase_false_report = _write_json(run_root / "next_phase_false.json", next_phase_false)
    next_phase_false_rejected = validate_phase19_training_report(run_root, report_path=next_phase_false_report)
    assert next_phase_false_rejected["ok"] is False
    assert any(failure["gate"] == "next_phase_allowed" for failure in next_phase_false_rejected["fatal_failures"])

    malformed_count_manifest = _read_json(data_manifest)
    malformed_count_manifest["split_counts"]["train"] = 1.9
    malformed_count_manifest_path = _write_json(run_root / "malformed_count_manifest.json", malformed_count_manifest)
    malformed_count_report = _read_json(report)
    malformed_count_report["data_manifest_path"] = str(malformed_count_manifest_path)
    malformed_count_report["data_manifest_sha256"] = __import__("hashlib").sha256(malformed_count_manifest_path.read_bytes()).hexdigest()
    malformed_count_report_path = _write_json(run_root / "malformed_count_report.json", malformed_count_report)
    malformed_count_rejected = validate_phase19_training_report(run_root, report_path=malformed_count_report_path)
    assert malformed_count_rejected["ok"] is False
    assert any(failure["gate"] == "split_counts" and "non-negative integer" in failure["reason"] for failure in malformed_count_rejected["fatal_failures"])

    low_count_manifest = _read_json(data_manifest)
    low_count_manifest["split_counts"]["train"] = 1
    low_count_manifest_path = _write_json(run_root / "low_count_manifest.json", low_count_manifest)
    low_count_report = _read_json(report)
    low_count_report["data_manifest_path"] = str(low_count_manifest_path)
    low_count_report["data_manifest_sha256"] = __import__("hashlib").sha256(low_count_manifest_path.read_bytes()).hexdigest()
    low_count_report["trainer_state"] = {"global_step": 1, "max_steps": 1}
    low_count_report_path = _write_json(run_root / "low_count_report.json", low_count_report)
    low_count_rejected = validate_phase19_training_report(run_root, report_path=low_count_report_path)
    assert low_count_rejected["ok"] is False
    assert any(failure["gate"] == "split_counts" for failure in low_count_rejected["fatal_failures"])
    assert any(failure["gate"] == "completed" for failure in low_count_rejected["fatal_failures"])

    unicode_count_manifest = _read_json(data_manifest)
    unicode_count_manifest["split_counts"]["train"] = "１２"
    unicode_count_manifest_path = _write_json(run_root / "unicode_count_manifest.json", unicode_count_manifest)
    unicode_count_report = _read_json(report)
    unicode_count_report["data_manifest_path"] = str(unicode_count_manifest_path)
    unicode_count_report["data_manifest_sha256"] = __import__("hashlib").sha256(unicode_count_manifest_path.read_bytes()).hexdigest()
    unicode_count_report_path = _write_json(run_root / "unicode_count_report.json", unicode_count_report)
    unicode_count_rejected = validate_phase19_training_report(run_root, report_path=unicode_count_report_path)
    assert unicode_count_rejected["ok"] is False
    assert any(failure["gate"] == "split_counts" and "non-negative integer" in failure["reason"] for failure in unicode_count_rejected["fatal_failures"])

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
    with pytest.raises(ValueError, match="tokenized_dir must be canonical"):
        write_phase19_training_reports(tmp_path / "outside" / "runs" / "v4.2-4B-20260518T150000Z", mode="full", elapsed=1.0, trainer_state={"global_step": 1, "max_steps": 1}, adapter_dir=adapter_dir, targs_kwargs={"bf16": True}, tokenized_dir=tmp_path / "outside" / "data/v4_2/phase18/tokenized")

    outside_adapter = tmp_path / "runs" / "v4.0-4B-20260509T184844Z" / "adapter"
    outside_adapter_sha = _make_adapter(outside_adapter)
    outside = _read_json(report)
    outside["adapter_path"] = str(outside_adapter)
    outside["adapter_sha256"] = outside_adapter_sha
    outside_report = _write_json(run_root / "outside_adapter_report.json", outside)
    outside_rejected = validate_phase19_training_report(run_root, report_path=outside_report)
    assert outside_rejected["ok"] is False
    assert outside_rejected["gates"]["adapter_hash"]["data"]["actual"] is None
    assert any(failure["gate"] == "adapter_path" for failure in outside_rejected["fatal_failures"])

    outside_data_manifest = tmp_path / "outside_phase19_data_manifest.json"
    outside_data_manifest.write_text("not json", encoding="utf-8")
    outside_data = _read_json(report)
    outside_data["data_manifest_path"] = str(outside_data_manifest)
    outside_data["data_manifest_sha256"] = "x" * 64
    outside_data_report = _write_json(run_root / "outside_data_report.json", outside_data)
    outside_data_rejected = validate_phase19_training_report(run_root, report_path=outside_data_report)
    assert outside_data_rejected["ok"] is False
    assert outside_data_rejected["gates"]["data_manifest_hash"]["data"]["actual"] is None
    assert any(failure["gate"] == "data_manifest_path" for failure in outside_data_rejected["fatal_failures"])

    wrong_adapter_config = _read_json(report)
    (adapter_dir / "adapter_config.json").write_text('{"base_model_name_or_path":"Qwen/Qwen3.5-9B"}\n', encoding="utf-8")
    wrong_adapter_report = _write_json(run_root / "wrong_adapter_config_report.json", wrong_adapter_config)
    wrong_adapter_rejected = validate_phase19_training_report(run_root, report_path=wrong_adapter_report)
    assert wrong_adapter_rejected["ok"] is False
    assert any(failure["gate"] == "adapter_config" for failure in wrong_adapter_rejected["fatal_failures"])
    assert any(failure["gate"] == "adapter_hash" for failure in wrong_adapter_rejected["fatal_failures"])
    (adapter_dir / "adapter_config.json").write_text('{"base_model_name_or_path":"Qwen/Qwen3-4B-Thinking-2507"}\n', encoding="utf-8")

    token_report = lineage_root / "artifacts/v4_2/phase19/tokenization_report.json"
    token_payload = _read_json(token_report)
    token_payload["tokenized_sha256"]["train"] = "z" * 64
    token_report.write_text(json.dumps(token_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    token_report_rejected = validate_phase19_training_report(run_root, report_path=report)
    assert token_report_rejected["ok"] is False
    assert any(failure["gate"] == "phase18_artifact_hashes" for failure in token_report_rejected["fatal_failures"])
    token_payload["tokenized_sha256"]["train"] = phase18_artifact_hashes["train.arrow"]
    token_report.write_text(json.dumps(token_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    import pyarrow as pa  # noqa: PLC0415

    train_arrow = lineage_root / "data/v4_2/phase18/tokenized/train.arrow"
    original_arrow = train_arrow.read_bytes()
    with pa.memory_map(str(train_arrow), "r") as source:
        table = pa.ipc.open_file(source).read_all()
    rows = table.to_pylist()
    rows[0]["input_ids"] = list(rows[0]["input_ids"])
    rows[0]["input_ids"][0] = 999999
    tampered = pa.Table.from_pylist(rows, schema=table.schema)
    with pa.OSFile(str(train_arrow), "wb") as sink:
        with pa.ipc.new_file(sink, tampered.schema) as writer:
            writer.write_table(tampered)
    tampered_arrow_rejected = validate_phase19_training_report(run_root, report_path=report)
    assert tampered_arrow_rejected["ok"] is False
    assert any(failure["gate"] == "tokenized_content" for failure in tampered_arrow_rejected["fatal_failures"])
    train_arrow.write_bytes(b"not arrow")
    corrupt_arrow_rejected = validate_phase19_training_report(run_root, report_path=report)
    assert corrupt_arrow_rejected["ok"] is False
    assert any("invalid tokenized split" in failure["reason"] for failure in corrupt_arrow_rejected["fatal_failures"])
    train_arrow.write_bytes(original_arrow)

    calibrated = lineage_root / "data/v4_2/phase18/labeled_calibrated.jsonl"
    calibrated.write_text(calibrated.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    forged_anchor_manifest = _read_json(data_manifest)
    forged_anchor_manifest["phase18"]["calibrated_jsonl_sha256"] = __import__("hashlib").sha256(calibrated.read_bytes()).hexdigest()
    forged_anchor_manifest_path = _write_json(run_root / "forged_anchor_manifest.json", forged_anchor_manifest)
    forged_anchor_report = _read_json(report)
    forged_anchor_report["data_manifest_path"] = str(forged_anchor_manifest_path)
    forged_anchor_report["data_manifest_sha256"] = __import__("hashlib").sha256(forged_anchor_manifest_path.read_bytes()).hexdigest()
    forged_anchor_report["phase18_artifact_hashes"] = dict(phase18_artifact_hashes, calibrated_jsonl_sha256=forged_anchor_manifest["phase18"]["calibrated_jsonl_sha256"])
    forged_anchor_report_path = _write_json(run_root / "forged_anchor_report.json", forged_anchor_report)
    forged_anchor_rejected = validate_phase19_training_report(run_root, report_path=forged_anchor_report_path)
    assert forged_anchor_rejected["ok"] is False
    assert any(failure["gate"] == "calibrated_jsonl_sha256" for failure in forged_anchor_rejected["fatal_failures"])

    split_manifest = lineage_root / "data/v4_2/phase18/splits/manifest.json"
    split_payload = _read_json(split_manifest)
    split_payload["split_ids_sha256"]["train"] = "x" * 64
    split_manifest.write_text(json.dumps(split_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    split_manifest_rejected = validate_phase19_training_report(run_root, report_path=report)
    assert split_manifest_rejected["ok"] is False
    assert any(failure["gate"] == "tokenized_content" for failure in split_manifest_rejected["fatal_failures"])

    wrapper = (PROJECT_ROOT / "scripts/run_v4_phase19_train.sh").read_text(encoding="utf-8")
    assert "<<'PY'" in wrapper
    assert 'Path("$RUN_ROOT")' not in wrapper
    assert 'os.environ["RUN_ROOT"]' in wrapper
    assert "scripts/dgx_spark/run_safe.sh" in wrapper
    assert "100G --" in wrapper
    assert "TRITON_PTXAS_PATH" in wrapper
    assert "tsc_cycle.student.train" in wrapper
    assert "--phase v4_2" in wrapper
    for forbidden in ["pip install", "uv pip install", "vllm", "flash-attn", "unsloth", "axolotl", "git worktree", "runs/20260507T032419Z"]:
        assert forbidden not in wrapper


def _make_phase19_training_handoff(run_root: Path) -> Path:
    adapter_dir = run_root / "adapter"
    adapter_sha = _make_adapter(adapter_dir)
    phase18, tokenized_paths, tokenized_sha256, phase18_artifact_hashes = _make_phase19_lineage(PROJECT_ROOT)
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
            "training_args": _locked_phase19_training_args(),
            "lora_config": _locked_phase19_lora_config(),
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
    (merged / "tokenizer_config.json").write_text('{"tokenizer_class":"Qwen2Tokenizer"}\n', encoding="utf-8")
    config_only_report = write_export_report(run_root=run_root, export_plan=plan, out=run_root / "config_only_export_report.json")
    assert config_only_report["ok"] is False
    assert any("tokenizer materializer" in failure["reason"] for failure in config_only_report["fatal_failures"])
    assert any("config.json" in failure["reason"] for failure in config_only_report["fatal_failures"])
    (merged / "config.json").write_text('{"model_type":"qwen2"}\n', encoding="utf-8")
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
    assert accepted["artifacts"]["merged_hf_materializer"][0]["sha256"] == __import__("hashlib").sha256(b'{"model_type":"qwen2"}\n').hexdigest()

    forged_materializer = _read_json(run_root / "phase19_export_report.json")
    forged_materializer["artifacts"]["merged_hf_materializer"] = []
    forged_materializer_path = _write_json(run_root / "forged_materializer.json", forged_materializer)
    rejected_materializer = validate_phase19_export_report(run_root=run_root, report_path=forged_materializer_path)
    assert rejected_materializer["ok"] is False
    assert any("merged HF materializer" in failure["reason"] for failure in rejected_materializer["fatal_failures"])

    missing_train02 = _read_json(run_root / "phase19_export_report.json")
    missing_train02["requirements_covered"] = []
    missing_train02_path = _write_json(run_root / "missing_train02.json", missing_train02)
    rejected_train02 = validate_phase19_export_report(run_root=run_root, report_path=missing_train02_path)
    assert rejected_train02["ok"] is False
    assert any(failure["gate"] == "requirements_covered" for failure in rejected_train02["fatal_failures"])

    malformed_export_coverage = _read_json(run_root / "phase19_export_report.json")
    malformed_export_coverage["requirements_covered"] = {"TRAIN-02": False}
    malformed_export_coverage_path = _write_json(run_root / "malformed_export_coverage.json", malformed_export_coverage)
    rejected_export_coverage = validate_phase19_export_report(run_root=run_root, report_path=malformed_export_coverage_path)
    assert rejected_export_coverage["ok"] is False
    assert rejected_export_coverage["requirements_covered"] == []
    assert any(failure["gate"] == "requirements_covered" and "must be a list" in failure["reason"] for failure in rejected_export_coverage["fatal_failures"])

    export_not_allowed = _read_json(run_root / "phase19_export_report.json")
    export_not_allowed["next_phase_allowed"] = False
    export_not_allowed_path = _write_json(run_root / "export_not_allowed.json", export_not_allowed)
    rejected_export_not_allowed = validate_phase19_export_report(run_root=run_root, report_path=export_not_allowed_path)
    assert rejected_export_not_allowed["ok"] is False
    assert any(failure["gate"] == "next_phase_allowed" for failure in rejected_export_not_allowed["fatal_failures"])

    outside_export_report = _write_json(tmp_path / "outside_phase19_export_report.json", _read_json(run_root / "phase19_export_report.json"))
    rejected_outside_export = validate_phase19_export_report(run_root=run_root, report_path=outside_export_report)
    assert rejected_outside_export["ok"] is False
    assert any(failure["gate"] == "report_path" for failure in rejected_outside_export["fatal_failures"])

    missing_hash = _read_json(run_root / "phase19_export_report.json")
    missing_hash["artifacts"]["gguf_q4_K_M"].pop("sha256")
    missing_hash_path = _write_json(run_root / "missing_hash.json", missing_hash)
    rejected_hash = validate_phase19_export_report(run_root=run_root, report_path=missing_hash_path)
    assert rejected_hash["ok"] is False
    assert any(failure["gate"] == "artifact_hash" for failure in rejected_hash["fatal_failures"])

    wrong_tool = _read_json(run_root / "phase19_export_report.json")
    wrong_tool["llama_cpp"]["quantize"] = "/bin/true"
    wrong_tool_path = _write_json(run_root / "wrong_tool.json", wrong_tool)
    rejected_tool = validate_phase19_export_report(run_root=run_root, report_path=wrong_tool_path)
    assert rejected_tool["ok"] is False
    assert any(failure["gate"] == "llama-quantize" for failure in rejected_tool["fatal_failures"])

    wrong_command = _read_json(run_root / "phase19_export_report.json")
    wrong_command["commands"]["quantize_q4_K_M"][0] = "/bin/true"
    wrong_command_path = _write_json(run_root / "wrong_command.json", wrong_command)
    rejected_command = validate_phase19_export_report(run_root=run_root, report_path=wrong_command_path)
    assert rejected_command["ok"] is False
    assert any(failure["gate"] == "commands" and "reported quantize tool" in failure["reason"] for failure in rejected_command["fatal_failures"])

    wrong_merge_command = _read_json(run_root / "phase19_export_report.json")
    wrong_merge_command["commands"]["merge_hf"][wrong_merge_command["commands"]["merge_hf"].index("--run-root") + 1] = str(tmp_path / "runs" / "v4.2-4B-other")
    wrong_merge_command_path = _write_json(run_root / "wrong_merge_command.json", wrong_merge_command)
    rejected_merge_command = validate_phase19_export_report(run_root=run_root, report_path=wrong_merge_command_path)
    assert rejected_merge_command["ok"] is False
    assert any(failure["gate"] == "commands" and "reported run_root" in failure["reason"] for failure in rejected_merge_command["fatal_failures"])

    wrong_outtype_command = _read_json(run_root / "phase19_export_report.json")
    wrong_outtype_command["commands"]["convert_fp16"][wrong_outtype_command["commands"]["convert_fp16"].index("--outtype") + 1] = "q8_0"
    wrong_outtype_command_path = _write_json(run_root / "wrong_outtype_command.json", wrong_outtype_command)
    rejected_outtype_command = validate_phase19_export_report(run_root=run_root, report_path=wrong_outtype_command_path)
    assert rejected_outtype_command["ok"] is False
    assert any(failure["gate"] == "commands" and "f16 outtype" in failure["reason"] for failure in rejected_outtype_command["fatal_failures"])

    malformed_export_failures = _read_json(run_root / "phase19_export_report.json")
    malformed_export_failures["fatal_failures"] = "bad"
    malformed_export_failures_path = _write_json(run_root / "malformed_export_failures.json", malformed_export_failures)
    rejected_export_failures = validate_phase19_export_report(run_root=run_root, report_path=malformed_export_failures_path)
    assert rejected_export_failures["ok"] is False
    assert any(failure["gate"] == "fatal_failures" for failure in rejected_export_failures["fatal_failures"])

    nonempty_export_failures = _read_json(run_root / "phase19_export_report.json")
    nonempty_export_failures["fatal_failures"] = [{"gate": "x", "reason": "bad"}]
    nonempty_export_failures_path = _write_json(run_root / "nonempty_export_failures.json", nonempty_export_failures)
    rejected_nonempty_export_failures = validate_phase19_export_report(run_root=run_root, report_path=nonempty_export_failures_path)
    assert rejected_nonempty_export_failures["ok"] is False
    assert any(failure["gate"] == "fatal_failures" for failure in rejected_nonempty_export_failures["fatal_failures"])

    original_tokenizer = (merged / "tokenizer.json").read_bytes()
    (merged / "tokenizer.json").write_bytes(b"")
    zero_tokenizer = _read_json(run_root / "phase19_export_report.json")
    zero_tokenizer_path = _write_json(run_root / "zero_tokenizer.json", zero_tokenizer)
    rejected_zero_tokenizer = validate_phase19_export_report(run_root=run_root, report_path=zero_tokenizer_path)
    assert rejected_zero_tokenizer["ok"] is False
    assert any("tokenizer materializer" in failure["reason"] for failure in rejected_zero_tokenizer["fatal_failures"])
    (merged / "tokenizer.json").write_bytes(original_tokenizer)

    (merged / "special_tokens_map.json").write_text('{"eos_token":"<|endoftext|>"}\n', encoding="utf-8")
    missing_tokenizer = _read_json(run_root / "phase19_export_report.json")
    missing_tokenizer_path = _write_json(run_root / "missing_tokenizer.json", missing_tokenizer)
    rejected_tokenizer = validate_phase19_export_report(run_root=run_root, report_path=missing_tokenizer_path)
    assert rejected_tokenizer["ok"] is False
    assert any("tokenizer evidence" in failure["reason"] for failure in rejected_tokenizer["fatal_failures"])
    (merged / "special_tokens_map.json").unlink()

    outside_artifact = tmp_path / "outside_model.fp16.gguf"
    outside_artifact.write_bytes(b"outside fp16")
    outside_artifact_report = _read_json(run_root / "phase19_export_report.json")
    outside_artifact_report["paths"]["gguf_fp16"] = str(outside_artifact)
    outside_artifact_report_path = _write_json(run_root / "outside_artifact_report.json", outside_artifact_report)
    rejected_outside_artifact = validate_phase19_export_report(run_root=run_root, report_path=outside_artifact_report_path)
    assert rejected_outside_artifact["ok"] is False
    assert any("invalid gguf_fp16 path" in failure["reason"] for failure in rejected_outside_artifact["fatal_failures"])

    outside_merged = tmp_path / "outside_merged_hf"
    outside_merged.mkdir()
    (outside_merged / "model.safetensors").write_bytes(b"outside merged")
    outside_merged_report = _read_json(run_root / "phase19_export_report.json")
    outside_merged_report["paths"]["merged_hf"] = str(outside_merged)
    outside_merged_report_path = _write_json(run_root / "outside_merged_report.json", outside_merged_report)
    rejected_outside_merged = validate_phase19_export_report(run_root=run_root, report_path=outside_merged_report_path)
    assert rejected_outside_merged["ok"] is False
    assert any("invalid merged_hf path" in failure["reason"] for failure in rejected_outside_merged["fatal_failures"])

    forged = _read_json(run_root / "phase19_export_report.json")
    (run_root / "gguf" / "model.q4_K_M.gguf").unlink()
    forged["artifacts"]["gguf_q4_K_M"]["exists"] = True
    forged["artifacts"]["gguf_q4_K_M"]["sha256"] = "f" * 64
    forged_path = _write_json(run_root / "forged_export_report.json", forged)
    rejected_forged = validate_phase19_export_report(run_root=run_root, report_path=forged_path)
    assert rejected_forged["ok"] is False
    assert any(failure["gate"] in {"artifact_exists", "artifact_hash"} for failure in rejected_forged["fatal_failures"])
    (run_root / "gguf" / "model.q4_K_M.gguf").write_bytes(b"q4 gguf")

    forged_handoff_mismatch = _read_json(run_root / "phase19_export_report.json")
    forged_handoff_mismatch["phase19_handoff"]["adapter_sha256"] = "0" * 64
    forged_handoff_mismatch_path = _write_json(run_root / "forged_handoff_mismatch_export_report.json", forged_handoff_mismatch)
    rejected_handoff_mismatch = validate_phase19_export_report(run_root=run_root, report_path=forged_handoff_mismatch_path)
    assert rejected_handoff_mismatch["ok"] is False
    assert any(failure["gate"] == "phase19_handoff" for failure in rejected_handoff_mismatch["fatal_failures"])

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
    phase19_no_root = parser.parse_args(["--export-phase", "phase19"])
    assert "v4.2-4B-" in phase19_no_root.run_root
    assert Path(phase19_no_root.phase19_report) == Path(phase19_no_root.run_root) / "phase19_sft_report.json"

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

    (llama_cpp / "llama-quantize").chmod(0o644)
    bad_tool_plan = build_export_plan(run_root=run_root, phase19_report=training_report, llama_cpp_dir=llama_cpp)
    assert bad_tool_plan["ok"] is False
    assert any(failure["gate"] == "llama-quantize" for failure in bad_tool_plan["fatal_failures"])
    (llama_cpp / "llama-quantize").chmod(0o755)

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
