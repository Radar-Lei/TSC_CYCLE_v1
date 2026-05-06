# Phase 4 SUMMARY — Dataset + QLoRA SFT (script-ready)

**Status:** Script ready; blocked on Phase 3 output (`data/labeled.jsonl`).

## Implementation
- `tsc_cycle/student/dataset.py` — deterministic 80/10/10 split (val_id by sample_id-hash bucket %10; val_ood from `split_hint=="ood"`); p99-based max_length (cap 4096); arrow/parquet output; loss-mask labels (-100 for prompt portion); native `<think>` id leakage assert
- `tsc_cycle/student/train.py` — Qwen3-4B-Thinking-2507 + bnb 4-bit NF4 + LoRA r=64 α=128 (Q/K/V/O + gate/up/down) + SDPA + bf16 + gradient_checkpointing non-reentrant + boot-time tokenizer_check + bnb dummy forward warmup + 5-prompt smoke callback at end of each epoch (closing rate + native think leak check); HF Trainer (TRL drift mitigated by using raw Trainer with manually masked labels)
- `scripts/dgx_spark/run_safe.sh 100G -- python -m tsc_cycle.student.train` per ENV-05/TRN-08

## Notes
- TRL 1.3.0 in venv (newer than CLAUDE.md's 0.22.x anchor). Bypassing TRL by writing labels manually via DataCollatorForSeq2Seq — same effect as `SFTTrainer(packing=False)` but no API drift exposure.
- transformers 5.8.0 (newer than 4.56.x anchor). HF Trainer / PEFT / BitsAndBytesConfig still on the same names.
