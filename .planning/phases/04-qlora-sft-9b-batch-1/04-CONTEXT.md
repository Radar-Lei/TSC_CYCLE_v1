# Phase 4: QLoRA SFT (9B, batch=1, 跑到收敛) - Context

**Gathered:** 2026-05-09
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

在 DGX Spark 上完成 Qwen3.5-9B 的 QLoRA r=64 SFT：先做 500-sample dry-run early-exit gate，再进行全量训练直到 early-stopping 收敛；训练 artifact 与 v1.0 物理隔离，并保护 v1.0 production artifact 不被触碰。

</domain>

<decisions>
## Implementation Decisions

### Locked Training Stack
- **D-01:** 使用 HF Transformers + TRL + PEFT + bitsandbytes 路线；不引入 Unsloth、Axolotl、新 PyTorch 版本或 vLLM。
- **D-02:** 训练环境复用本项目 `.venv` / `/home/samuel/dgx-spark-setup/.venv` 的 DGX Spark 已验证栈，遵循 `/dgx-spark-training` skill。
- **D-03:** 注意力实现必须为 SDPA；禁止安装或依赖 upstream `flash-attn` CUDA 12 wheel。

### Locked Hyperparameters and Gates
- **D-04:** QLoRA 固定 `r=64`, `lora_alpha=64`, `lora_dropout=0.0`, `target_modules="all-linear"`。
- **D-05:** 训练固定 `batch_size=1`, `gradient_accumulation_steps=16`, `packing=False`, `gradient_checkpointing(use_reentrant=False)`。
- **D-06:** optimizer/scheduler 固定 `adamw_torch_fused`, `lr=1e-4`, cosine schedule with warmup, `max_grad_norm=0.5`。
- **D-07:** 500-sample dry-run gate 必须在进入全量训练前通过：OOD 硬约束满足率 ≥95%，前 200 step `grad_norm p99 < 3.0` 且无 NaN；失败则 abort，不进入 full run。
- **D-08:** 全量训练不设 6h 上限；使用 early-stopping callback，val loss patience=3，监控间隔 200 steps，最大 epoch 上限 5。

### Runtime Safety and Artifact Isolation
- **D-09:** 长训练必须通过 `scripts/dgx_spark/env.sh` 环境与 `scripts/dgx_spark/run_safe.sh 100G -- ...` 或等价 `systemd-run --scope -p MemoryMax=100G -p MemorySwapMax=0` 执行。
- **D-10:** Phase 4 输出路径使用 `runs/v3.0-9B-{utc_timestamp}/`，wandb project 使用 `tsc-cycle-v3-9b`，不得混入 v1.0 run 目录。
- **D-11:** `runs/20260507T032419Z/` 必须写入 `FROZEN.md` 并 `chmod -w`；Phase 4 流程只读引用，禁止写入。

### Claude's Discretion
- 具体训练脚本拆分、测试文件命名、dry-run 评测抽样实现、checkpoint 保存频率、日志字段和 manifest 结构由下游 researcher/planner 决定，但必须满足 SFT-01..SFT-08 和上面锁定决策。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project and Requirements
- `.planning/PROJECT.md` — v3.0 milestone goal, environment lock, baseline-to-beat, and out-of-scope constraints.
- `.planning/REQUIREMENTS.md` — SFT-01..SFT-08 requirements and v3.0 traceability.
- `.planning/ROADMAP.md` — Phase 4 goal, dependencies, and success criteria.

### Upstream Phase Evidence
- `artifacts/v3/phase1/phase1_gate_report.json` — aggregate Phase 1 hard gate evidence.
- `artifacts/v3/phase1/memory_budget.json` — selected max sequence length and memory evidence for Phase 4.
- `artifacts/v3/phase1/env_smoke.json` — Qwen3.5-9B environment smoke evidence.
- `artifacts/v3/phase1/run_safe_scope.json` — DGX Spark safe-run/scope evidence.
- `artifacts/v3/phase1/tokenizer_audit.json` — tokenizer/custom-tag/native-think evidence.
- `data/splits/v3/rebuild_report.json` — final Phase 3 split/tokenization report; must be green before training.
- `data/splits/v3/manifest.json` — split/tokenization artifact hashes.
- `data/tokenized/v3/train.arrow`, `data/tokenized/v3/val.arrow`, `data/tokenized/v3/ood_val.arrow` — Phase 4 training/validation inputs.

### Existing Training and Runtime Code
- `tsc_cycle/student/train.py` — v1.0 student SFT entrypoint/pattern to adapt for v3.0.
- `tsc_cycle/student/dataset.py` — existing dataset loading/formatting utilities.
- `scripts/run_train_bg.sh` — existing training wrapper pattern.
- `scripts/dgx_spark/env.sh` — DGX Spark environment variables and SDPA/Triton setup.
- `scripts/dgx_spark/run_safe.sh` — memory-capped training wrapper.
- `tsc_cycle/v3_gates/memory_budget_v3.py` — Phase 1 memory sweep/dry-run patterns.

### DGX Spark Skill Contract
- `/dgx-spark-training` skill — authoritative operational constraints for DGX Spark training: reuse known-good env, no flash-attn, SDPA, swap/OOM protection, verify before training.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tsc_cycle/student/train.py`: existing QLoRA/SFT-style training entrypoint should be reused or adapted instead of creating an unrelated trainer.
- `tsc_cycle/student/dataset.py`: existing student dataset handling is the likely integration point for Arrow inputs or for refactoring a v3 loader.
- `tsc_cycle/v3_gates/memory_budget_v3.py`: contains Qwen3.5 loading / memory safety patterns from Phase 1.
- `scripts/dgx_spark/run_safe.sh` and `scripts/dgx_spark/env.sh`: mandatory runtime wrappers for any long training command.

### Established Patterns
- v3 gates fail closed and write JSON reports/manifests with explicit `ok`, `gates`, and `fatal_failures` fields.
- Phase wrappers use project `.venv/bin/python`, `set -euo pipefail`, fixed v3 paths, and baseline diff guards when touching legacy data/artifacts.
- Phase 3 produced Arrow IPC artifacts and manifest hashes; Phase 4 should consume those exact paths rather than rebuilding data ad hoc.

### Integration Points
- Training input: `data/tokenized/v3/{train,val,ood_val}.arrow` plus split metadata under `data/splits/v3/`.
- Run output: `runs/v3.0-9B-{utc_timestamp}/` containing adapter, configs, metrics, dry-run gate report, and full-run manifest.
- Safety integration: v1.0 artifact directory `runs/20260507T032419Z/` must be frozen before training begins.

</code_context>

<specifics>
## Specific Ideas

No new user decisions were requested because discussion is configured to skip; downstream agents should treat ROADMAP/REQUIREMENTS plus this context as locked.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-QLoRA SFT (9B, batch=1, 跑到收敛)*
*Context gathered: 2026-05-09*
