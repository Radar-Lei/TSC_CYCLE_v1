from __future__ import annotations


EXPECTED_MODEL_NAME = "Qwen/Qwen3.5-9B"
EXPECTED_REQUIREMENTS = ["SFT-01", "SFT-02", "SFT-03", "SFT-05", "SFT-07"]


def _sft_contract():
    from tsc_cycle.student.sft_v3 import (  # noqa: PLC0415
        MODEL_NAME,
        RUN_ROOT_PREFIX,
        WANDB_PROJECT,
        locked_lora_config_kwargs,
        locked_training_arguments_kwargs,
    )

    return {
        "MODEL_NAME": MODEL_NAME,
        "RUN_ROOT_PREFIX": RUN_ROOT_PREFIX,
        "WANDB_PROJECT": WANDB_PROJECT,
        "locked_lora_config_kwargs": locked_lora_config_kwargs,
        "locked_training_arguments_kwargs": locked_training_arguments_kwargs,
    }


def test_sft_01_d04_lora_config_locks_qwen35_9b_and_all_linear() -> None:
    contract = _sft_contract()

    assert contract["MODEL_NAME"] == EXPECTED_MODEL_NAME
    lora = contract["locked_lora_config_kwargs"]()

    # D-04 / SFT-01: QLoRA must not silently inherit v1.0 alpha/dropout/target list defaults.
    assert lora["r"] == 64
    assert lora["lora_alpha"] == 64
    assert lora["lora_dropout"] == 0.0
    assert lora["target_modules"] == "all-linear"
    assert lora["bias"] == "none"
    assert lora["task_type"] == "CAUSAL_LM"


def test_sft_01_d04_lora_coverage_contract_requires_hybrid_layer_evidence() -> None:
    contract = _sft_contract()
    lora = contract["locked_lora_config_kwargs"]()

    # D-04 / SFT-01: Qwen3.5 hybrid architecture coverage must be explicit in lora_coverage.json.
    assert lora["coverage_report"] == "lora_coverage.json"
    assert lora["expected_gated_deltanet_layers"] == 24
    assert lora["expected_full_attention_layers"] == 8
    assert lora["require_per_layer_projection_evidence"] is True
    assert lora["fail_closed_on_coverage_mismatch"] is True


def test_sft_02_d06_optimizer_scheduler_and_clip_are_locked(tmp_path) -> None:
    contract = _sft_contract()
    args = contract["locked_training_arguments_kwargs"](str(tmp_path / "runs" / "v3.0-9B-20260509T000000Z"))

    # D-06 / SFT-02: optimizer/scheduler/clip choices are safety gates, not tunable defaults.
    assert args["learning_rate"] == 1e-4
    assert args["lr_scheduler_type"] == "cosine"
    assert args["warmup_ratio"] > 0
    assert args["optim"] == "adamw_torch_fused"
    assert args["max_grad_norm"] == 0.5


def test_sft_03_d05_batch_accum_checkpointing_and_no_packing_are_locked(tmp_path) -> None:
    contract = _sft_contract()
    args = contract["locked_training_arguments_kwargs"](str(tmp_path / "runs" / "v3.0-9B-20260509T000000Z"))

    # D-05 / SFT-03: batch=1, effective batch=16, no packing, no chat-template preprocessing.
    assert args["per_device_train_batch_size"] == 1
    assert args["gradient_accumulation_steps"] == 16
    assert args["gradient_checkpointing"] is True
    assert args["gradient_checkpointing_kwargs"] == {"use_reentrant": False}
    assert args.get("packing") in (None, False)
    assert args.get("chat_template") in (None, False)
    assert args.get("apply_chat_template") in (None, False)


def test_training_arguments_init_kwargs_filters_sft_only_evidence_keys(tmp_path) -> None:
    from tsc_cycle.student.train import training_arguments_init_kwargs  # noqa: PLC0415

    contract = _sft_contract()
    raw = contract["locked_training_arguments_kwargs"](str(tmp_path / "runs" / "v3.0-9B-20260509T000000Z"))
    init_kwargs = training_arguments_init_kwargs(raw)

    assert raw["packing"] is False
    assert raw["chat_template"] is False
    assert raw["apply_chat_template"] is False
    assert "packing" not in init_kwargs
    assert "chat_template" not in init_kwargs
    assert "apply_chat_template" not in init_kwargs
    assert init_kwargs["output_dir"] == raw["output_dir"]
    assert init_kwargs["per_device_train_batch_size"] == 1
    assert init_kwargs["gradient_accumulation_steps"] == 16
    assert init_kwargs["gradient_checkpointing_kwargs"] == {"use_reentrant": False}


def test_sft_05_d08_early_stopping_eval_and_best_model_settings_are_locked(tmp_path) -> None:
    contract = _sft_contract()
    args = contract["locked_training_arguments_kwargs"](str(tmp_path / "runs" / "v3.0-9B-20260509T000000Z"))

    # D-08 / SFT-05: full run has no 6h cap; convergence is controlled by steps eval + best model.
    assert args["num_train_epochs"] == 5
    assert args["eval_strategy"] == "steps"
    assert args["eval_steps"] == 200
    assert args["save_strategy"] == "steps"
    assert args["save_steps"] == 200
    assert args["save_total_limit"] == 3
    assert args["load_best_model_at_end"] is True
    assert args["metric_for_best_model"] == "eval_loss"
    assert args["greater_is_better"] is False
    assert "max_time" not in args
    assert "time_limit" not in args


def test_sft_07_d10_run_root_and_wandb_project_are_isolated() -> None:
    contract = _sft_contract()

    assert contract["RUN_ROOT_PREFIX"] == "v3.0-9B-"
    assert contract["WANDB_PROJECT"] == "tsc-cycle-v3-9b"
