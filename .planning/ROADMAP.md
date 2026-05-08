# Milestone v3.0 Roadmap — 9B 基座切换 + 数据扩量到 10K

**Milestone:** v3.0
**Granularity:** standard
**Total Phases:** 6
**Coverage:** 39/39 requirements mapped
**Created:** 2026-05-08

## Phases

- [ ] **Phase 1: 环境 + Tokenizer + 显存 + llama.cpp 四合一硬门禁** — 9B/Qwen3.5 兼容性硬门禁；任一 fatal gate fail → milestone abort
- [ ] **Phase 2: 数据扩量到 10K（教师只标新增 7K）** — 合成 7K 新输入 + GPT-5.5 high 并发标注 + lint，目标合并集 ≥9000 valid
- [ ] **Phase 3: Dataset Rebuild（Qwen3.5 retokenize + split）** — 80/10/10 split (seed=42)、Qwen3.5 tokenizer 重 tokenize、截断率 ≤5%
- [ ] **Phase 4: QLoRA SFT (9B, batch=1, 跑到收敛)** — 500-sample 1h dry-run early-exit gate + 全量训练 + early-stopping，不设 6h 上限
- [ ] **Phase 5: Merge + GGUF Export + imatrix** — LoRA merge → fp16 GGUF → Q4_K_M（imatrix 必跑），三精度 SOLUTION smoke
- [ ] **Phase 6: Eval Matrix + 三阈值决策门** — 4 variant matrix（含 v1.0 q4_K_M baseline read-only mount）+ GO/NO-GO/用户决策三态 decision.md

## Phase Details

### Phase 1: 环境 + Tokenizer + 显存 + llama.cpp 四合一硬门禁
**Goal**: 在投入任何训练 / 数据扩量成本前，4 项 9B 切换的不可逆假设全部硬验证；任一 fatal gate 失败立即 milestone abort。
**Depends on**: Nothing (first phase)
**Requirements**: ENV-01, ENV-02, ENV-03, TOK-01, TOK-02, TOK-03, TOK-04, MEM-01, MEM-02, MEM-03
**Success Criteria** (what must be TRUE):
  1. `Qwen/Qwen3.5-9B` 在本机 `/home/samuel/TSC_CYCLE/.venv` 上以 `Qwen3_5ForCausalLM` + bnb 4-bit NF4 + SDPA 完成 1-step forward smoke pass，加载后 `model.named_parameters()` 不含 `vision*` 名空间
  2. 4 个自定义思考标签在 Qwen3.5 tokenizer 下全部拆为 ≥3 sub-tokens；native `<think>`/`</think>` 在 248K vocab 中的 token id 写入 `tokenizer_audit.json`（不硬编码 v1.0 的 151667/151668）；HF encode ↔ `llama-tokenize` 在 100 prompt 上 100% parity
  3. `memory_budget_v3.py` 在 5 候选 max_seq ∈ {1536, 2048, 2560, 3072, 4096} 上完成实测；选定 peak<85GB 最大值；100-step 训练 dry-run 在 100GB cap 内不 OOM
  4. 本机 `/home/samuel/projects/EvoProgTSC/llama.cpp` micro-convert dry-run 端到端 pass：dummy LoRA → bf16 GGUF → q4_K_M GGUF → `llama-cli` 推理 5 token 无 segfault
  5. 训练运行模板（`systemd-run --scope -p MemoryMax=100G -p MemorySwapMax=0` + swap=0）就位并验证一次空跑
**Plans:** 6 plans
Plans:
**Wave 1**
- [x] 01-01-PLAN.md — Qwen3.5 causal-LM environment smoke gate + run_safe/swap artifact gate
- [x] 01-02-PLAN.md — Dynamic tokenizer audit + raw-text dataset/native-ID leakage wiring
- [x] 01-05-PLAN.md — Qwen3.5 llama.cpp micro-convert + tokenizer GGUF fixture gate

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 01-03-PLAN.md — HF tokenizer ↔ llama-tokenize 100-prompt parity using GGUF fixture
- [x] 01-04-PLAN.md — Qwen3.5 memory budget sweep + 100-step dry-run gate

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 01-06-PLAN.md — Phase 1 all-gates runner + aggregate fatal report

### Phase 2: 数据扩量到 10K（教师只标新增 7K）
**Goal**: 在不动 v1.0 `data/labeled.jsonl` 字节的前提下，扩展合成输入分布、用 GPT-5.5 high 并发标注新增 ≥7K 输入，过硬约束 lint 后与 v1.0 合并得到 ≥9000 valid 训练集。
**Depends on**: Phase 1
**Requirements**: DATAGEN-01, DATAGEN-02, DATAGEN-03, DATAGEN-04, DATAGEN-05, DATAGEN-06, DATAGEN-07
**Success Criteria** (what must be TRUE):
  1. 合成输入分布扩展到三类（同分布密集填充 / OOD 边界 / v1.0 高 MAE 与 lint reject targeted），生成 ≥7K 新输入且与 v1.0 现有 3K 不重叠（去重后）
  2. GPT-5.5 high + reasoning_effort=high 标注完成；并发 ≤10 worker；JSONL append 进度持久化；中断可断点续跑且不重复调用
  3. 教师输出过硬约束 lint（min_green ≤ final ≤ max_green、整数秒、相位顺序、覆盖全相位），lint 失败样本丢弃不重生成；最终合并集 ≥9000 valid samples
  4. v1.0 `data/labeled.jsonl` git diff clean（read-only mount 引用，字节级不变）；新增样本写入隔离路径
**Plans:** 5 plans
Plans:
**Wave 0**
- [x] 02-01-PLAN.md — Wave 0 RED tests for DATAGEN-01..07 invariants

**Wave 1** *(blocked on Wave 0 completion)*
- [x] 02-02-PLAN.md — Three-source isolated Phase 2 input reservoir generator
- [x] 02-03-PLAN.md — Phase 2-safe GPT-5.5 high labeler hardening and smoke/full wrappers

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 02-04-PLAN.md — Merge/report gate proving frozen baseline, lint-pass new labels, and ≥9000 merged valid

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 02-05-PLAN.md — Operational end-to-end wrapper with paid full-run approval checkpoint

### Phase 3: Dataset Rebuild（Qwen3.5 retokenize + split）
**Goal**: 用 Qwen3.5 tokenizer 重新 tokenize 合并后的 ≥9000 valid 数据集，做 80/10/10 split (seed=42)，OOD val 包含 v1.0 OOD val 全集以保跨里程碑可比。
**Depends on**: Phase 1, Phase 2
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04
**Success Criteria** (what must be TRUE):
  1. 80/10/10 split (train/val/ood_val) 落盘到 `data/splits/v3/`，seed=42；OOD val 包含 v1.0 OOD val 全集 + v3.0 新增 OOD subset
  2. Qwen3.5 tokenizer 重 tokenize 输出到 `data/tokenized/v3/{train,val,ood_val}.arrow`
  3. 截断率 ≤5%（max_seq_length 用 Phase 1 MEM-01 选定值）
  4. split 索引文件 + 样本哈希持久化，便于评测复现并校验 v1.0 OOD val 子集对齐
**Plans**: TBD

### Phase 4: QLoRA SFT (9B, batch=1, 跑到收敛)
**Goal**: 在 DGX Spark 上完成 Qwen3.5-9B QLoRA r=64 SFT，500-sample dry-run 通过后进入全量训练（不设 6h 上限，靠 early-stopping 收敛），artifact 与 v1.0 物理隔离。
**Depends on**: Phase 1, Phase 3
**Requirements**: SFT-01, SFT-02, SFT-03, SFT-04, SFT-05, SFT-06, SFT-07, SFT-08
**Success Criteria** (what must be TRUE):
  1. QLoRA r=64 / alpha=64 / lora_dropout=0.0 / target_modules="all-linear" 命中 24 GatedDeltaNet linear-attention 层 + 8 full-attention 层全部 projections（`model.named_modules()` dry-run 枚举确认）
  2. 训练超参锁定：lr=1e-4 cosine + warmup、max_grad_norm=0.5、optimizer=`adamw_torch_fused`、bs=1 + grad_accum=16 (effective batch 16)、packing=False、gradient_checkpointing(use_reentrant=False)
  3. 500-sample 1h dry-run early-exit gate 通过：OOD 硬约束满足率 ≥95%；前 200 step grad_norm p99<3.0 且无 NaN
  4. 全量训练完成（不设 6h 上限），early-stopping callback 触发收敛（val loss patience=3，监控间隔 200 steps；最大 epoch 上限 5）；adapter 落盘到 `runs/v3.0-9B-{utc_timestamp}/`
  5. v1.0 production artifact `runs/20260507T032419Z/` 标记 FROZEN.md + `chmod -w`，v3.0 流程零写入；wandb project=`tsc-cycle-v3-9b` 与 v1.0 严格隔离
**Plans**: TBD

### Phase 5: Merge + GGUF Export + imatrix
**Goal**: LoRA merge → bf16 HF safetensors → fp16 GGUF → q4_K_M GGUF（imatrix 必跑），三精度生成合法 SOLUTION 段，HF/llama-tokenize parity。
**Depends on**: Phase 4
**Requirements**: GGUF-01, GGUF-02, GGUF-03, GGUF-04, GGUF-05
**Success Criteria** (what must be TRUE):
  1. 全链路 pass：merge → bf16 safetensors → `convert_hf_to_gguf.py` 走 Qwen3_5ForCausalLM 路径产出 fp16 GGUF → `llama-quantize` Q4_K_M 产出 q4_K_M GGUF
  2. imatrix 校准必跑（v3.0 升为强制；GatedDeltaNet 24/32 层 q4_K_M 保真度未在 v1.0 dense 模型上验证）；imatrix 校准集 100-200 样本来自训练集
  3. 5-prompt smoke 在 HF bf16 / fp16 GGUF / q4_K_M GGUF 三精度均生成合法 SOLUTION 段（含完整 `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>` 结构）
  4. HF tokenize ↔ llama-tokenize parity 验证通过（与 Phase 1 TOK-03 fixture 共用）
  5. q4_K_M 崩塌时 fallback 路径（升级到 q5_K_M，部署 size +25%）已明文记录在 export 脚本与 runbook 中
**Plans**: TBD

### Phase 6: Eval Matrix + 三阈值决策门
**Goal**: 4 variant 评测矩阵 + 跨里程碑严格可比（v1.0 baseline read-only mount 不重跑）+ 三阈值并存的 GO/NO-GO/用户决策三态结论；NO-GO 也是有效里程碑产出（"4B 已是甜点"）。
**Depends on**: Phase 5
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05
**Success Criteria** (what must be TRUE):
  1. 4 variant matrix 评测完成：(a) hf_bf16_v3 (b) gguf_q4_v3 (c) gguf_q4_v1_baseline read-only mount 不重跑 (d) optional gguf_fp16_v3
  2. v1.0 baseline 的 generation cache (`runs/20260507T032419Z/eval/gen_cache/gguf_q4km/`) 直接 mount 引用，禁止重生成（保持跨里程碑严格可比）
  3. 决策门三阈值并存全部评估：`q4_v3 vs fp16_v3 ≥ 0.95` ∧ `q4_v3 vs q4_v1 ≥ 1.00` ∧ `q4_v3 hard_constraint_pass ≥ 98%`
  4. 报告含 v3-v1 差值 + 95% bootstrap CI + p99/max-abs tail metrics（不只看均值）
  5. `decision.md` 给出 GO / NO-GO / 用户决策三态结论；NO-GO（"4B 已是甜点"）是合法且有效的 milestone 产出
**Plans**: TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. 环境 + Tokenizer + 显存 + llama.cpp 四合一硬门禁 | 0/6 | Not started | - |
| 2. 数据扩量到 10K（教师只标新增 7K） | 0/5 | Planned | - |
| 3. Dataset Rebuild（Qwen3.5 retokenize + split） | 0/0 | Not started | - |
| 4. QLoRA SFT (9B, batch=1, 跑到收敛) | 0/0 | Not started | - |
| 5. Merge + GGUF Export + imatrix | 0/0 | Not started | - |
| 6. Eval Matrix + 三阈值决策门 | 0/0 | Not started | - |

## Coverage Map

All 39 v3.0 requirements mapped to exactly one phase:

| Category | Requirements | Phase |
|----------|--------------|-------|
| ENV (3) | ENV-01, ENV-02, ENV-03 | Phase 1 |
| TOK (4) | TOK-01, TOK-02, TOK-03, TOK-04 | Phase 1 |
| MEM (3) | MEM-01, MEM-02, MEM-03 | Phase 1 |
| DATAGEN (7) | DATAGEN-01..07 | Phase 2 |
| DATA (4) | DATA-01..04 | Phase 3 |
| SFT (8) | SFT-01..08 | Phase 4 |
| GGUF (5) | GGUF-01..05 | Phase 5 |
| EVAL (5) | EVAL-01..05 | Phase 6 |

**Coverage:** 39/39 ✓ — no orphans, no duplicates.

## Dependency DAG

```
Phase 1 (硬门禁) ──► Phase 2 (数据扩量) ──► Phase 3 (Rebuild) ──► Phase 4 (SFT) ──► Phase 5 (Export) ──► Phase 6 (Eval)
       │                                          ▲
       └──────────────────────────────────────────┘
       (Phase 1 选定 max_seq_length 直接喂 Phase 3)
```

**Critical path:** Phase 4 (training) 是唯一可能跨夜运行的 phase（不设 6h 上限）；其他 phase 均 ≤ 1 day。
