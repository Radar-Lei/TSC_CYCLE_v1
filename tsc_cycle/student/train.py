"""QLoRA SFT training entrypoint — Phase 4.

Run via:
  scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.student.train

NOT to be run directly without run_safe.sh in DGX Spark — unified memory swap-off requirement.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForSeq2Seq,
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
from tsc_cycle.tokenizer_check import (
    NATIVE_THINK_CLOSE_ID,
    NATIVE_THINK_OPEN_ID,
    check_tokenizer,
)

MODEL_NAME = "Qwen/Qwen3-4B-Thinking-2507"


def load_split(parquet_path: Path) -> Dataset:
    import pyarrow.parquet as pq
    t = pq.read_table(parquet_path)
    return Dataset(t)


def boot_tokenizer_check(tokenizer) -> None:
    res = check_tokenizer(tokenizer)
    if not res.ok:
        raise SystemExit(f"BOOT-FAIL: tokenizer_check: {res.details}")
    print("BOOT-OK: tokenizer check passed")


def bnb_warmup(model, tokenizer, device: str = "cuda") -> None:
    """Take the sm_121 PTX JIT first-step penalty before training starts."""
    model.eval()
    with torch.no_grad():
        prompt = build_user_prompt({"prediction": {"as_of": "x", "phase_waits": [
            {"phase_id": 1, "pred_wait": 1.0, "pred_saturation": 0.05, "min_green": 20, "max_green": 45, "capacity": 30}
        ]}})
        ids = tokenizer(prompt, return_tensors="pt").to(device)
        _ = model(**ids)
    model.train()
    print("BOOT-OK: bnb 4-bit warmup forward complete")


def smoke_generate(model, tokenizer, n: int = 5, device: str = "cuda") -> dict:
    model.eval()
    closing_ok = 0
    native_leak = 0
    with torch.no_grad():
        for i in range(n):
            prompt = build_user_prompt({"prediction": {"as_of": f"smoke-{i}", "phase_waits": [
                {"phase_id": 1, "pred_wait": 1.0, "pred_saturation": 0.05, "min_green": 20, "max_green": 45, "capacity": 30},
                {"phase_id": 2, "pred_wait": 0.8, "pred_saturation": 0.04, "min_green": 50, "max_green": 80, "capacity": 40},
            ]}})
            full = prompt + "\n" + build_assistant_prefill()
            inp = tokenizer(full, return_tensors="pt").to(device)
            out = model.generate(**inp, max_new_tokens=512, do_sample=False)
            new_ids = out[0][inp["input_ids"].shape[1]:].tolist()
            decoded = tokenizer.decode(new_ids)
            _, sol = parse_assistant_output(build_assistant_prefill() + decoded)
            if (TAG_THINK_CLOSE in decoded) and (TAG_SOLUTION_CLOSE in decoded):
                closing_ok += 1
            if NATIVE_THINK_OPEN_ID in new_ids or NATIVE_THINK_CLOSE_ID in new_ids:
                native_leak += 1
    model.train()
    return {"n": n, "closing_ok": closing_ok, "native_leak": native_leak}


class SmokeCallback(TrainerCallback):
    def __init__(self, tokenizer, every_n_epochs: int = 1):
        self.tokenizer = tokenizer
        self.every = every_n_epochs

    def on_epoch_end(self, args, state, control, **kwargs):
        model = kwargs["model"]
        result = smoke_generate(model, self.tokenizer, n=5)
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
        with open(Path(args.output_dir) / "smoke.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"epoch": state.epoch, **result}) + "\n")
        print(f"[SMOKE] epoch {state.epoch}: closing_ok={result['closing_ok']}/5 native_leak={result['native_leak']}/5")

        # Versioned snapshot per epoch (NOT final adapter — watchdog waits for `adapter/`)
        snap_dir = Path(args.output_dir) / f"adapter_epoch{int(round(state.epoch))}"
        model.save_pretrained(snap_dir)
        self.tokenizer.save_pretrained(snap_dir)
        print(f"[SMOKE] saved snapshot: {snap_dir}")
        return control


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/tokenized")
    ap.add_argument("--model", default=MODEL_NAME)
    ap.add_argument("--output-dir", default=None, help="default runs/{ts}/train/")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--lora-r", type=int, default=64)
    ap.add_argument("--lora-alpha", type=int, default=128)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--save-strategy", default="epoch")
    ap.add_argument("--logging-steps", type=int, default=10)
    ap.add_argument("--max-steps", type=int, default=-1, help=">0 for dry-run / smoke")
    args = ap.parse_args()

    if args.output_dir is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        args.output_dir = f"runs/{ts}/train"

    print(f"[BOOT] output_dir={args.output_dir} epochs={args.epochs} bs={args.batch_size}x{args.grad_accum}")

    # --- Tokenizer + boot check ---
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    boot_tokenizer_check(tokenizer)

    # --- Model: 4-bit NF4 base ---
    bnb_cfg = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=bnb_cfg,
        attn_implementation="sdpa",
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                            gradient_checkpointing_kwargs={"use_reentrant": False})

    lora_cfg = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    bnb_warmup(model, tokenizer)

    # --- Datasets ---
    train_ds = load_split(Path(args.data_dir) / "train" / "data.parquet")
    val_id_ds = load_split(Path(args.data_dir) / "val_id" / "data.parquet")
    print(f"train={len(train_ds)} val_id={len(val_id_ds)}")

    # Drop sample_id / trivial — Trainer needs only model inputs
    keep = ["input_ids", "attention_mask", "labels"]
    train_ds = train_ds.remove_columns([c for c in train_ds.column_names if c not in keep])
    val_id_ds = val_id_ds.remove_columns([c for c in val_id_ds.column_names if c not in keep])

    collator = DataCollatorForSeq2Seq(tokenizer, padding="longest", label_pad_token_id=-100)

    # --- Trainer ---
    targs = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        bf16=True,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=args.logging_steps,
        save_strategy="no",
        save_total_limit=1,
        eval_strategy="no",
        report_to=["wandb"] if os.environ.get("WANDB_API_KEY") else ["none"],
        dataloader_num_workers=1,
        remove_unused_columns=False,
        max_steps=args.max_steps,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        weight_decay=0.0,
    )

    trainer = Trainer(
        model=model,
        args=targs,
        train_dataset=train_ds,
        eval_dataset=val_id_ds,
        data_collator=collator,
        callbacks=[SmokeCallback(tokenizer)],
    )

    # --- Pre-flight 100-step extrapolation (only if not max_steps mode) ---
    if args.max_steps <= 0:
        print("[BOOT] training start...")
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    print(f"[DONE] training {elapsed/3600:.2f}h")

    # Save adapter
    adapter_dir = Path(args.output_dir) / "adapter"
    trainer.model.save_pretrained(adapter_dir)
    tokenizer.save_pretrained(adapter_dir)
    print(f"saved adapter: {adapter_dir}")

    # Append summary to train_log.jsonl
    log = Path(args.output_dir) / "train_log.jsonl"
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"event": "training_complete", "elapsed_h": elapsed / 3600}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
