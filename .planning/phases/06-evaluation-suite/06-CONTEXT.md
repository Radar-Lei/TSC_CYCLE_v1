---
phase: 6
status: ready_for_planning
mode: skip_discuss (auto-generated)
gathered: 2026-05-07
---

# Phase 6: Evaluation Suite - Context

<domain>
## Phase Boundary

三 backend（HF bf16 / GGUF bf16 / GGUF q4_K_M）× 四指标（硬约束满足率 / 教师 MAE / OOD gap / Reasoning 关键字）× 两 split（同分布 val / OOD val）矩阵评测，给出部署 go/no-go 决策。

**Success Criteria** (来自 ROADMAP):
1. `gen_cache/{variant}/{sample_id}.json` 缓存所有生成结果（共 600 prompt × 3 variant = 1800 generation），三 variant 共用 prompt_builder + greedy seed=42
2. `runs/{ts}/eval/per_sample.jsonl` 含四指标逐样本结果：硬约束满足率（按 phase_count 分桶 + trivial 样本排除）、与教师 final MAE / 完全一致率、OOD gap（同分布 vs OOD）、Reasoning 关键字引用质量（规则式打分）
3. `runs/{ts}/eval/report.md` 输出 4 指标 × 3 variant × 2 split 矩阵 + p99 + 失败案例 top-20 + 量化退化结论
4. 部署 go/no-go gate 写入 `runs/{ts}/eval/decision.md`：q4_K_M 在 OOD val 硬约束满足率 ≥ HF bf16 的 95% → go；否则启用 imatrix 重量化或回退 fp16 部署

</domain>

<existing_state>
## Phase 5 收尾产物（直接复用）

| Artifact | Path | 说明 |
|---|---|---|
| HF bf16 model | `runs/20260507T032419Z/merged_bf16/` | transformers AutoModelForCausalLM bf16+SDPA 入口 |
| GGUF bf16 | `runs/20260507T032419Z/gguf/model.bf16.gguf` | llama-server CUDA |
| GGUF q4_K_M | `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` | llama-server CUDA（**已知 MAE>3s**，imatrix backlog flagged）|
| parity 子进程框架 | `tsc_cycle/student/parity_hf.py`, `parity_gguf.py` | 改造为 EVL generation 入口 |
| prompt 构造统一入口 | `tsc_cycle/shared/prompt_builder.py` | EVL 必须复用，不另造 |
| labeled.jsonl | `data/labeled.jsonl` | 含 `split_hint`(id/ood) + `result.solution` 教师答案 |

## Phase 5 关键约束（继承）

- **DGX Spark unified memory 死锁防护**：generation 必须拆子进程，每 backend 一次性加载（不 per-prompt）；llama-server CUDA build 在 `/home/samuel/llama.cpp/build/bin/llama-server`（非 EvoProgTSC 的 CPU build）
- **GGUF 推理路径**：llama-server 启动一次 + urllib POST `/completion`，不要 per-prompt llama-cli cold-start
- **教师答案 schema**：`record["result"]["solution"]`（不是顶层 solution）
- **q4_K_M 已知崩塌信号**：ood prompt `dfb9ae1a` phase_3=158 违反 max_green — EVL 阶段会再现此现象，决策 gate 必须能正确路由

</existing_state>

<decisions>
## Implementation Decisions

### Claude's Discretion
- **数据集**：从 `data/labeled.jsonl` 选 600 prompt（300 id + 300 OOD）— 数量足够覆盖 phase_count 分桶（2/3/4/5/6 相位），seed=42 deterministic
- **generation cache**：`runs/20260507T032419Z/eval/gen_cache/{variant}/{sample_id}.json`，断点续跑（已存在 cache 跳过），三 variant = `hf_bf16` / `gguf_bf16` / `gguf_q4_k_m`
- **生成参数**：greedy seed=42 temp=0 top_k=1，n_predict=384（与 Phase 5 parity 一致）
- **指标计算**：
  - **硬约束**：min_green ≤ final_green ≤ max_green / 整数秒 / 相位覆盖；按 phase_count ∈ {2,3,4,5,6} 分桶；trivial 样本（min==max）排除
  - **教师 MAE**：每相位 |student_final - teacher_final|，整体 mean；同时统计完全一致率（exact_match）
  - **OOD gap**：同一 variant 下 id_split metric vs ood_split metric 的差值
  - **Reasoning 关键字**：规则式 — 检查 `<start_working_out>...<end_working_out>` 段中是否提及 phase_id / min_green / max_green 数字（≥3 个数字命中=full / 1-2=partial / 0=miss）
- **决策 gate**：q4_K_M ood_split 硬约束满足率 / hf_bf16 ood_split 硬约束满足率 ≥ 0.95 → GO；否则 NO-GO 并提 imatrix 重量化路径

### From CLAUDE.md
- 复用 `.venv`，不重装包；不能直接读全 PDF；本机 vllm 不可用；DGX Spark 推理走 SDPA 或 GGUF llama-server CUDA build

</decisions>

<code_context>
## Existing Code Insights

- `tsc_cycle/student/parity_hf.py` (Phase 5)：HF bf16 generation 入口，已处理 SDPA + bf16 dtype + greedy
- `tsc_cycle/student/parity_gguf.py` (Phase 5)：llama-server 启动 + urllib POST，已验证 CUDA 路径
- `tsc_cycle/shared/prompt_builder.py`：prompt 构造唯一入口
- `tsc_cycle/shared/constraint_lint.py`（Phase 1）：硬约束 lint 函数，EVL 直接调用
- `data/labeled.jsonl`：~3000 条 labeled 样本（含 split_hint）
- 子进程隔离模式（Phase 5 已验证）：orchestrator 不 import torch；每 backend 独立 python -m

</code_context>

<specifics>
## Specific Ideas

1. **6 个 plan**（建议）：
   - **Plan 06-01** (wave 1): EVL 数据集选取（600 = 300 id + 300 ood from labeled.jsonl, seed=42），写 `eval_prompts.jsonl`
   - **Plan 06-02** (wave 2): hf_bf16 generation runner（subprocess，断点续 gen_cache）
   - **Plan 06-03** (wave 2): gguf_bf16 generation runner（llama-server）
   - **Plan 06-04** (wave 2): gguf_q4_k_m generation runner（llama-server）
   - **Plan 06-05** (wave 3, deps=02,03,04): metrics 计算（硬约束/MAE/OOD gap/Reasoning），写 `per_sample.jsonl` + `report.md`
   - **Plan 06-06** (wave 4, deps=05): decision gate + 部署 go/no-go 报告
2. **wave 2 三个 generation plan 文件不冲突**（cache 路径分 variant 子目录），可并行
3. **Reasoning 关键字打分**应导出独立 `metrics_reasoning.py`，规则透明，便于人工抽样 sanity check
4. 不再做 imatrix 重量化（仍是 backlog；EVL 只判定是否触发该路径）

</specifics>

<deferred>
## Deferred Ideas

- imatrix 重量化（继续延期，是 backlog；Phase 6 的产物可能强化此项优先级）
- 学生 chat_template GGUF 一致性
- 端到端 web demo / api server

</deferred>
