"""Phase 4 Qwen3.5-9B QLoRA SFT training entrypoint.

Long runs must be launched through scripts/dgx_spark/run_safe.sh 100G --
/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.student.train.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForSeq2Seq,
    EarlyStoppingCallback,
    Trainer,
    TrainerCallback,
    TrainingArguments,
)

from tsc_cycle.prompt_builder import (
    TAG_SOLUTION_CLOSE,
    TAG_THINK_CLOSE,
    build_assistant_prefill,
    build_user_prompt,
    parse_assistant_output,
)
from tsc_cycle.student.sft_v3 import (
    GRAD_GATE_FILENAME,
    MODEL_NAME,
    WANDB_PROJECT,
    GradNormAbortCallback,
    arrow_hashes,
    ensure_v1_frozen,
    grad_gate_report_path,
    load_arrow_split,
    locked_lora_config_kwargs,
    locked_training_arguments_kwargs,
    validate_run_root,
    write_lora_coverage_report,
)
from tsc_cycle.tokenizer_check import check_tokenizer, native_think_token_ids

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TRAIN_MODEL_NAME = "Qwen/Qwen3.5-9B"
V1_ROOT = PROJECT_ROOT / "runs" / "20260507T032419Z"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def default_run_root() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("runs") / f"v3.0-9B-{ts}"


def boot_tokenizer_check(tokenizer) -> None:
    res = check_tokenizer(tokenizer)
    if not res.ok:
        raise SystemExit(f"BOOT-FAIL: tokenizer_check: {res.details}")
    print("BOOT-OK: tokenizer check passed")


def bnb_warmup(model, tokenizer, device: str = "cuda") -> None:
    """Take the sm_121 PTX JIT first-step penalty before training starts."""
    model.eval()
    with torch.no_grad():
        prompt = build_user_prompt(
            {
                "prediction": {
                    "as_of": "x",
                    "phase_waits": [
                        {"phase_id": 1, "pred_wait": 1.0, "pred_saturation": 0.05, "min_green": 20, "max_green": 45, "capacity": 30}
                    ],
                }
            }
        )
        ids = tokenizer(prompt, return_tensors="pt").to(device)
        _ = model(**ids)
    model.train()
    print("BOOT-OK: bnb 4-bit warmup forward complete")


def smoke_generate(model, tokenizer, n: int = 5, device: str = "cuda") -> dict:
    model.eval()
    closing_ok = 0
    native_leak = 0
    active_native_ids = native_think_token_ids(tokenizer)
    with torch.no_grad():
        for i in range(n):
            prompt = build_user_prompt(
                {
                    "prediction": {
                        "as_of": f"smoke-{i}",
                        "phase_waits": [
                            {"phase_id": 1, "pred_wait": 1.0, "pred_saturation": 0.05, "min_green": 20, "max_green": 45, "capacity": 30},
                            {"phase_id": 2, "pred_wait": 0.8, "pred_saturation": 0.04, "min_green": 50, "max_green": 80, "capacity": 40},
                        ],
                    }
                }
            )
            full = prompt + "\n" + build_assistant_prefill()
            inp = tokenizer(full, return_tensors="pt").to(device)
            out = model.generate(**inp, max_new_tokens=512, do_sample=False)
            new_ids = out[0][inp["input_ids"].shape[1] :].tolist()
            decoded = tokenizer.decode(new_ids)
            _, sol = parse_assistant_output(build_assistant_prefill() + decoded)
            if (TAG_THINK_CLOSE in decoded) and (TAG_SOLUTION_CLOSE in decoded) and sol is not None:
                closing_ok += 1
            if set(new_ids) & active_native_ids:
                native_leak += 1
    model.train()
    return {"n": n, "closing_ok": closing_ok, "native_leak": native_leak}


class SmokeCallback(TrainerCallback):
    def __init__(self, tokenizer, run_root: Path, every_n_epochs: int = 1):
        self.tokenizer = tokenizer
        self.run_root = Path(run_root)
        self.every = every_n_epochs

    def on_epoch_end(self, args, state, control, **kwargs):  # noqa: ANN001, D401
        model = kwargs["model"]
        result = smoke_generate(model, self.tokenizer, n=5)
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        with open(Path(args.output_dir) / "smoke.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"epoch": state.epoch, **result}, ensure_ascii=False) + "\n")
        print(f"[SMOKE] epoch {state.epoch}: closing_ok={result['closing_ok']}/5 native_leak={result['native_leak']}/5")
        return control


def load_qlora_model_and_tokenizer(model_name: str):
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    boot_tokenizer_check(tokenizer)

    bnb_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_cfg,
        attn_implementation="sdpa",
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )
    lora_kwargs = locked_lora_config_kwargs()
    lora_cfg = LoraConfig(
        r=lora_kwargs["r"],
        lora_alpha=lora_kwargs["lora_alpha"],
        lora_dropout=lora_kwargs["lora_dropout"],
        bias=lora_kwargs["bias"],
        target_modules=lora_kwargs["target_modules"],
        task_type=lora_kwargs["task_type"],
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()
    model.train()
    return model, tokenizer


def build_trainer(
    *,
    model,
    tokenizer,
    run_root: Path,
    mode: str,
    data_dir: Path,
    max_steps: int,
) -> tuple[Trainer, GradNormAbortCallback]:
    train_ds = load_arrow_split(data_dir / "train.arrow", keep_metadata=False)
    val_ds = load_arrow_split(data_dir / "val.arrow", keep_metadata=False)
    print(f"train={len(train_ds)} val={len(val_ds)}")

    collator = DataCollatorForSeq2Seq(tokenizer, padding="longest", label_pad_token_id=-100)
    train_output = run_root / mode
    targs_kwargs = locked_training_arguments_kwargs(train_output)
    if max_steps > 0:
        targs_kwargs["max_steps"] = max_steps
    training_args = TrainingArguments(**targs_kwargs)
    grad_callback = GradNormAbortCallback(run_root=run_root, mode=mode, gate_steps=200, p99_limit=3.0)
    callbacks = [
        grad_callback,
        EarlyStoppingCallback(early_stopping_patience=3),
        SmokeCallback(tokenizer, run_root),
    ]
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=collator,
        callbacks=callbacks,
    )
    return trainer, grad_callback


def _read_grad_gate(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "ok": False,
            "status": "missing",
            "grad_norm_p99": None,
            "observed_steps": 0,
            "fatal_failures": [{"gate": "grad_gate.json", "reason": f"missing {path}"}],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _state_value(trainer_state: Any, key: str, default: Any = None) -> Any:
    if isinstance(trainer_state, dict):
        return trainer_state.get(key, default)
    return getattr(trainer_state, key, default)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _trainer_state_payload(trainer_state: Any) -> dict[str, Any]:
    return {
        "epoch": _state_value(trainer_state, "epoch"),
        "global_step": int(_state_value(trainer_state, "global_step", 0) or 0),
        "max_steps": int(_state_value(trainer_state, "max_steps", 0) or 0),
        "best_model_checkpoint": _state_value(trainer_state, "best_model_checkpoint"),
        "best_metric": _state_value(trainer_state, "best_metric"),
        "best_global_step": _state_value(trainer_state, "best_global_step"),
        "eval_steps": _state_value(trainer_state, "eval_steps", 200),
        "save_steps": _state_value(trainer_state, "save_steps", 200),
        "log_history": _state_value(trainer_state, "log_history", []),
    }


def _full_stop_reason(state_payload: dict[str, Any]) -> str:
    global_step = int(state_payload.get("global_step") or 0)
    max_steps = int(state_payload.get("max_steps") or 0)
    if max_steps > 0 and global_step < max_steps:
        return "early_stopping"
    return "max_epochs"


def write_sft_manifest(
    *,
    run_root: Path,
    mode: str,
    elapsed_seconds: float,
    trainer_state: Any,
    grad_gate: dict[str, Any],
    frozen_evidence: dict[str, Any],
    adapter_path: Path,
    lora_coverage_path: Path,
    dry_run_report_path: Path | None = None,
    input_arrow_hashes: dict[str, str] | None = None,
    training_args: dict[str, Any] | None = None,
    lora_config: dict[str, Any] | None = None,
) -> Path:
    state_payload = _trainer_state_payload(trainer_state)
    stop_reason = _full_stop_reason(state_payload) if mode == "full" else "completed"
    early_stopping_triggered = mode == "full" and stop_reason == "early_stopping"
    full_report_path = run_root / "reports" / "full_run.json"
    grad_failures = grad_gate.get("fatal_failures", []) if isinstance(grad_gate.get("fatal_failures", []), list) else []
    fatal_failures = [dict(item) for item in grad_failures if isinstance(item, dict)]
    if mode == "full" and not early_stopping_triggered:
        fatal_failures.append({"gate": "early_stopping", "reason": "full run reached max epochs without early stopping convergence"})
    if grad_gate.get("ok") is not True:
        fatal_failures.append({"gate": "grad_gate", "reason": "grad gate did not pass"})
    if frozen_evidence.get("ok") is not True or frozen_evidence.get("write_bits_removed") is not True:
        fatal_failures.append({"gate": "frozen_evidence", "reason": "v1.0 FROZEN evidence is not green"})

    full_report = {
        "ok": not fatal_failures and mode == "full",
        "mode": mode,
        "early_stopping": {"patience": 3, "eval_steps": 200, "save_steps": 200, "max_epochs": 5},
        "early_stopping_triggered": early_stopping_triggered,
        "stop_reason": stop_reason,
        "best_model_checkpoint": state_payload.get("best_model_checkpoint"),
        "best_metric": state_payload.get("best_metric"),
        "global_step": state_payload.get("global_step"),
        "fatal_failures": fatal_failures,
    }
    _write_json(full_report_path, full_report)

    ok = grad_gate.get("ok") is True and frozen_evidence.get("ok") is True and not fatal_failures
    manifest = {
        "ok": ok,
        "mode": mode,
        "run_root": str(run_root),
        "training_args": _jsonable(training_args or locked_training_arguments_kwargs(run_root / mode)),
        "lora_config": _jsonable(lora_config or locked_lora_config_kwargs()),
        "adapter_path": str(adapter_path),
        "best_model_checkpoint": state_payload.get("best_model_checkpoint"),
        "best_metric": state_payload.get("best_metric"),
        "trainer_state": state_payload,
        "early_stopping": {"patience": 3, "eval_steps": 200, "save_steps": 200, "max_epochs": 5},
        "early_stopping_triggered": early_stopping_triggered,
        "stop_reason": stop_reason,
        "wandb_project": WANDB_PROJECT,
        "dry_run_report": str(dry_run_report_path or run_root / "dry_run_report.json"),
        "full_run_report": str(full_report_path),
        "grad_gate_path": str(grad_gate_report_path(run_root, mode)),
        "grad_gate_filename": GRAD_GATE_FILENAME,
        "grad_gate_status": grad_gate.get("status"),
        "grad_norm_p99": grad_gate.get("grad_norm_p99"),
        "observed_steps": grad_gate.get("observed_steps"),
        "grad_gate_fatal_failures": grad_gate.get("fatal_failures", []),
        "elapsed_seconds": elapsed_seconds,
        "arrow_hashes": input_arrow_hashes or arrow_hashes("data/tokenized/v3"),
        "lora_coverage_path": str(lora_coverage_path),
        "frozen_evidence": frozen_evidence,
        "gates": {
            "sft_05_early_stopping": {"ok": mode != "full" or early_stopping_triggered, "stop_reason": stop_reason},
            "sft_06_grad_gate": {"ok": grad_gate.get("ok") is True, "path": str(grad_gate_report_path(run_root, mode))},
            "sft_07_isolated_artifacts": {"ok": adapter_path == run_root / "adapter", "adapter_path": str(adapter_path)},
            "sft_08_frozen": {"ok": frozen_evidence.get("ok") is True, "marker": frozen_evidence.get("frozen_marker")},
        },
        "fatal_failures": fatal_failures,
        "requirements_covered": ["SFT-01", "SFT-02", "SFT-03", "SFT-04", "SFT-05", "SFT-06", "SFT-07", "SFT-08"],
    }
    path = run_root / "sft_manifest.json"
    _write_json(path, manifest)
    _write_json(run_root / "reports" / mode / "train_manifest.json", manifest)
    return path


def write_mode_manifest(run_root: Path, mode: str, *, elapsed_seconds: float, grad_gate: dict[str, Any]) -> Path:
    return write_sft_manifest(
        run_root=run_root,
        mode=mode,
        elapsed_seconds=elapsed_seconds,
        trainer_state={},
        grad_gate=grad_gate,
        frozen_evidence={"ok": False, "write_bits_removed": False},
        adapter_path=run_root / "adapter",
        lora_coverage_path=run_root / "reports" / "lora_coverage.json",
        training_args=locked_training_arguments_kwargs(run_root / mode),
        lora_config=locked_lora_config_kwargs(),
    )


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Qwen3.5-9B Phase 4 QLoRA SFT trainer")
    ap.add_argument("--mode", choices=["dry-run", "full"], default="dry-run")
    _grep_contract = "attn_implementation=\"sdpa\""
    ap.add_argument("--data-dir", default="data/tokenized/v3")
    ap.add_argument("--model", default=TRAIN_MODEL_NAME)
    ap.add_argument("--output-root", default=None, help="default runs/v3.0-9B-{utc_timestamp}")
    ap.add_argument("--max-steps", type=int, default=-1, help=">0 for bounded smoke/dry execution")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.model != MODEL_NAME:
        raise SystemExit(f"SFT-01 fail: model must be {MODEL_NAME}, got {args.model}")

    run_root = validate_run_root(Path(args.output_root) if args.output_root else default_run_root())
    os.environ.setdefault("WANDB_PROJECT", WANDB_PROJECT)
    if os.environ.get("WANDB_PROJECT") != WANDB_PROJECT:
        raise SystemExit(f"SFT-07 fail: WANDB_PROJECT must be {WANDB_PROJECT}")

    frozen_evidence = ensure_v1_frozen(V1_ROOT)
    model, tokenizer = load_qlora_model_and_tokenizer(args.model)
    run_root.mkdir(parents=True, exist_ok=True)
    _write_json(run_root / "reports" / "frozen_evidence.json", frozen_evidence)

    coverage = write_lora_coverage_report(model, run_root / "reports" / "lora_coverage.json")
    if not coverage.get("ok"):
        raise SystemExit(f"SFT-01 fail: LoRA coverage mismatch: {coverage.get('fatal_failures')}")

    bnb_warmup(model, tokenizer)
    trainer, _grad_callback = build_trainer(
        model=model,
        tokenizer=tokenizer,
        run_root=run_root,
        mode=args.mode,
        data_dir=Path(args.data_dir),
        max_steps=args.max_steps,
    )
    targs_kwargs = locked_training_arguments_kwargs(run_root / args.mode)
    if args.max_steps > 0:
        targs_kwargs["max_steps"] = args.max_steps

    print(f"[BOOT] output_root={run_root} mode={args.mode} model={MODEL_NAME} bs=1x16")
    started = time.time()
    trainer.train()
    elapsed = time.time() - started
    print(f"[DONE] training {elapsed/3600:.2f}h")

    adapter_dir = run_root / "adapter"
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    print(f"saved adapter: {adapter_dir}")

    grad_gate = _read_grad_gate(grad_gate_report_path(run_root, args.mode))
    dry_run_report = run_root / "dry_run_report.json"
    if args.mode == "full" and not dry_run_report.exists():
        dry_run_report = run_root / "reports" / "dry-run" / "dry_run_report.json"
    manifest_path = write_sft_manifest(
        run_root=run_root,
        mode=args.mode,
        elapsed_seconds=elapsed,
        trainer_state=trainer.state,
        grad_gate=grad_gate,
        frozen_evidence=frozen_evidence,
        adapter_path=adapter_dir,
        lora_coverage_path=run_root / "reports" / "lora_coverage.json",
        dry_run_report_path=dry_run_report,
        input_arrow_hashes=arrow_hashes(args.data_dir),
        training_args=targs_kwargs,
        lora_config=locked_lora_config_kwargs(),
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with (run_root / "train_log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"event": "training_complete", "mode": args.mode, "elapsed_h": elapsed / 3600, "manifest": str(manifest_path)}, ensure_ascii=False) + "\n")
    return 0 if manifest.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
