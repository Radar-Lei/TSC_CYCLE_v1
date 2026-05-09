# Phase 4 Discussion Log

**Phase:** 04 — QLoRA SFT (9B, batch=1, 跑到收敛)
**Date:** 2026-05-09
**Mode:** Auto-generated; `workflow.skip_discuss=true`

## Summary

No interactive questions were asked. The phase context was generated from locked milestone requirements, roadmap success criteria, prior phase outputs, and the `/dgx-spark-training` operational contract.

## Decisions Captured

- Use HF Transformers + TRL + PEFT + bitsandbytes; do not introduce Unsloth/Axolotl/vLLM/new PyTorch.
- Use QLoRA r=64, alpha=64, dropout=0.0, target_modules="all-linear".
- Use batch_size=1, grad_accum=16, packing=False, gradient_checkpointing(use_reentrant=False).
- Use SDPA, DGX Spark safe-run memory cap, artifact isolation, dry-run gate, and early-stopping full run.

## Deferred Ideas

None.
