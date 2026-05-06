# State: TSC-CYCLE

**Last updated:** 2026-05-07

## Project Reference

**Core Value:** 学生模型在 OOD 输入上仍满足全部硬约束（min_green ≤ final ≤ max_green、整数秒、相位顺序、覆盖全相位），且数值决策接近 GPT-5.5 high 教师 — 不过拟合 reality.log。

**Current Focus:** Roadmap initialized; Phase 1 (Environment + Foundations) ready to plan.

## Current Position

- **Milestone:** v1 distillation
- **Phase:** Phase 1 — Environment + Foundations (not started)
- **Plan:** N/A (planning not yet started)
- **Status:** Roadmap drafted, awaiting `/gsd-plan-phase 1`
- **Progress:** 0/6 phases complete `[░░░░░░]`

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases complete | 0 / 6 |
| v1 requirements mapped | 47 / 47 |
| v1 requirements completed | 0 / 47 |

## Accumulated Context

### Key Decisions (locked)

- 学生基座 = Qwen/Qwen3-4B-Thinking-2507（不切 Qwen3.5/3.6）
- 自定义思考标签 `<start_working_out>` / `</end_working_out>` / `<SOLUTION>` / `</SOLUTION>`，绕开 `apply_chat_template`，绝不 `add_tokens()` 自定义标签
- 教师固定 GPT-5.5 high，reasoning_effort 不降档，`usage.reasoning_tokens > 100` 校验
- 训练栈：`/home/samuel/dgx-spark-setup/.venv` + TRL+PEFT+bitsandbytes==0.48.0 原生栈（**不**用 Unsloth）
- 训练全程在 `run_safe.sh 100G --`（systemd-run MemoryMax=100G MemorySwapMax=0）内
- merge 必须 bf16 reload base（非 4-bit），导出走本机 EvoProgTSC/llama.cpp `convert_hf_to_gguf.py` + `llama-quantize`
- 教师约束违反样本丢弃不重试（避免 prompt 漂移）
- 80/10/10 split：train / 同分布 val / OOD val（OOD 单列）
- **明确不参考** waybarrios/dgx-spark-finetune-llm

### Open Todos

- [ ] Plan Phase 1
- [ ] Phase 1 entry: 调用 `/dgx-spark-training` skill 把 venv 克隆到 `/home/samuel/TSC_CYCLE/.venv`

### Blockers

(None)

### Research Flags Carried Forward

- Phase 4: Thinking-2507 unlearn 原生 `<think>` 所需 epoch 数无对照；首 epoch 末 5-prompt smoke 决定是否升 3 epochs / alpha=192
- Phase 5: Qwen3-Thinking + 自定义标签 + bf16 GGUF parity 无公开 benchmark；20-prompt parity 必跑
- Phase 6: q4_K_M 长 thinking 退化率独有未知；MAE>3s 触发 imatrix 重量化预案
- 全程: OpenAI 账户 tier RPM/TPM 实际限额未知，`max_workers=5` 起步

## Session Continuity

**Last session:** Roadmap creation — derived 6 phases from 47 v1 requirements (ENV/FND/DGEN/TCH/DSET/TRN/EXP/EVL), validated 100% coverage, established Phase 1 as hard fail-fast gate.

**Next action:** `/gsd-plan-phase 1` — decompose Phase 1 (Environment + Foundations) into executable plans.

---
*State initialized: 2026-05-07*
