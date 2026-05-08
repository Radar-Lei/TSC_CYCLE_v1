# TSC-CYCLE — 思考型 4B 学生模型蒸馏

## What This Is

把 GPT-5.5 high（教师）在「交通信号配时（TSC）周期绿灯时长决策」任务上的能力，
通过合成数据 SFT 蒸馏到 Qwen3-4B-Thinking-2507（学生），最终产出能在本地以
GGUF（fp16 + q4_K_M）部署、且带显式思考过程的 4B 推理模型。

服务对象是 EvoProgTSC 系列项目中需要「便宜、可本地部署、可解释」的 TSC 决策端点。

## Core Value

学生模型在 OOD（reality.log 分布之外的合成输入）上仍然满足全部硬约束
（min_green ≤ final ≤ max_green、整数秒、相位顺序、覆盖全相位），
并在数值决策上接近 GPT-5.5 high 教师 —— 不是过拟合到 reality.log。

## Current State

**v1.0 SHIPPED** (2026-05-07) — 端到端蒸馏 pipeline 闭环，部署裁决 **GO**：q4_K_M GGUF (2.4GB) 在 OOD val 上硬约束满足率 98.7%（vs HF bf16 99.3%，ratio=0.9933 ≥ 0.95 阈值），教师 MAE Δ +0.18s（远低于 3s）。

**Deployment artifact**: `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` — 可直接装载到 EvoProgTSC TSC 决策端点。

**v2.0 强化版 ABANDONED** (2026-05-08) — 完成 Phase 7（标签协议全链路迁移），Phase 8（10K 数据扩容）已规划未执行；用户决定放弃 v2.0、直接切到更大基座。归档见 `milestones/v2.0-abandoned/`。

See `milestones/v1.0-ROADMAP.md` for phase breakdown.

## Current Milestone: v3.0 9B 基座切换

**Goal:** 把学生模型基座从 Qwen3-4B-Thinking-2507 切换到 **Qwen3.5-9B**（Qwen3.6 系列目前无 sub-10B 模型），重做端到端蒸馏 pipeline；证明 9B 学生在硬约束/教师 MAE/思考格式稳定性上达标且可在 DGX Spark + llama.cpp 部署。

**Target features:**
- 验证 Qwen3.5-9B 架构与 DGX Spark + `/dgx-spark-training` v1.0 已知良好环境的兼容性（不引入新环境）。
- Qwen3.5 tokenizer 适配：核实自定义思考标签（`<start_working_out>` / `<end_working_out>` / `<SOLUTION>`）在新 tokenizer 中仍被拆为 sub-token、不与原生 thinking token 冲突。
- 沿用 v1.0 数据生成 + GPT-5.5 high 标注 pipeline；评估是否需要为 9B 扩量。
- QLoRA r=64 SFT，**batch_size=1** + gradient_accumulation 调到合适 effective batch；6h 预算下 9B + r=64 可行性早期验证。
- LoRA merge → fp16 → q4_K_M GGUF；llama.cpp `convert_hf_to_gguf.py` 是否已注册 Qwen3.5 架构需核实。
- 评测对齐 v1.0 baseline：硬约束 / 教师 MAE Δ / OOD / q4 vs fp16 ratio ≥ 0.95。

**Baseline to beat:** v1.0 q4_K_M OOD lint=98.7%，HF bf16=99.3%，教师 MAE Δ +0.18s；v3.0 必须证明 9B 升级带来可验证收益（或反之，证明 4B 已是甜点）。

**Environment lock:** 训练环境严格沿用 `/dgx-spark-training` skill + `/home/samuel/dgx-spark-setup/.venv`（v1.0 已验证）。本里程碑不引入新训练框架/新版本 PyTorch。

## Requirements

### Validated (v1.0)

- [x] reality.log 输入分布形式化 + 合成数据生成器 — Validated in Phase 1-2
- [x] 3000 样本合成（同分布 + OOD 扩展） — Validated in Phase 2
- [x] GPT-5.5 high 并发标注（≤10 worker，≥2700 valid） — Validated in Phase 3
- [x] 硬约束 lint 过滤 — Validated in Phase 3
- [x] 80/10/10 split — Validated in Phase 4
- [x] DGX Spark QLoRA r=64 SFT ≤6h — Validated in Phase 4
- [x] LoRA merge → bf16 → GGUF bf16 → q4_K_M — Validated in Phase 5
- [x] 评测套件（硬约束 / MAE / OOD / Reasoning） + 部署 go/no-go — Validated in Phase 6

### Validated (v2.0 partial — abandoned)

- [x] 思考结束标签全链路从 `</end_working_out>` 修正为 `<end_working_out>` — Validated in v2.0 Phase 7（迁移本身是好的，与 v3.0 兼容，沿用）

### Active (v3.0)

- [ ] 学生基座切换到 Qwen3.5-9B（架构兼容性 + tokenizer 兼容性已论证）。
- [ ] QLoRA r=64 SFT 在 batch_size=1 + 沿用 `/dgx-spark-training` 环境下 6h 预算可行。
- [ ] q4_K_M GGUF 导出（llama.cpp 支持已核实），9B 学生 q4 vs fp16 ratio ≥ 0.95。
- [ ] OOD 硬约束、教师 MAE、思考格式稳定性达到或超过 v1.0 baseline。

### Out of Scope (v3.0)

- 在线/RL 优化（GRPO 等）— 本里程碑只做 SFT 蒸馏
- 教师模型改用别家 API — 锁定 GPT-5.5 high；reasoning_effort 不降档
- Qwen3.6 系列基座 — 该系列目前最小 27B，与"小模型本地部署" Core Value 冲突且超出 DGX Spark 6h 预算
- 模型原生 `<think>...</think>` 标签 — 与 memory 验证过的自定义标签方案冲突，且 reality.log 已是自定义标签格式
- 全参 SFT — 9B 在 DGX Spark 100GB 上做全参不可行；锁 QLoRA r=64
- vLLM 推理 — 本机现状不能用 vLLM，最终部署走 llama.cpp / GGUF
- 引入新训练栈（Unsloth on Spark / Axolotl / 新 PyTorch 版本）— 锁定 `/dgx-spark-training` v1.0 已验证环境，不接受环境变更带来的额外风险
- batch_size > 1 — 用户明确要求 batch_size=1（与 9B 显存压力一致）

## Context

**领域**：TSC（Traffic Signal Control）周期绿灯时长决策。输入是各相位的预测等待车辆数、
预测饱和度、容量、min/max_green；输出是各相位下一周期绿灯秒数（整数、上下限内）。
prompt/输出协议见 `reality.log`。

**先验积累（来自 memory + 既有项目）**：
- `EvoProgTSC` 项目（`/home/samuel/projects/EvoProgTSC/evoprog/llm/client.py`）已有
  openai 库 + reasoning_effort + 重试 + JSON Schema 结构化输出的成熟封装，可直接复用
- Qwen3 tokenizer 中 `<think>`(151667)/`</think>`(151668) 是 added tokens 且预训练
  权重对其有先入语义；用作自定义 SFT 标签会导致语义冲突 → 必须使用词表外的多 sub-token 标签
  （`<start_working_out>` / `<end_working_out>` / `<SOLUTION>` / `</SOLUTION>`，与 reality.log 一致）
- 既有 SFT 经验记载 2 epochs 是必要的，1 epoch 不够；本项目 QLoRA 也至少 2 epochs 起

**`reality.log` 的角色**：
- 仅作为输入参数分布的统计先验（相位数、各字段值域、组合模式），不参与训练标签
- 不直接当作训练输入（那样会过拟合 reality.log 的分布）；必须扩展到更宽分布
- 旧 lmstudio 教师的输出（reality.log 中的 RAW/REASONING/PARSED 字段）一律不用

**硬件 / 训练栈**：
- DGX Spark：GB10 aarch64、CUDA 13，禁用 flash-attn CUDA 12 wheels，必走 SDPA/Triton 路径
- 已有可复用的虚拟环境：`/home/samuel/dgx-spark-setup/.venv`（来自 `/dgx-spark-training` skill）
- 量化部署：llama.cpp `convert_hf_to_gguf.py` → `llama-quantize`（EvoProgTSC 仓库已 build cuda 版）
- 参考实现：`/home/samuel/dgx-spark-setup` 本地仓库 + `/dgx-spark-training` skill（权威源；上游 https://github.com/natolambert/dgx-spark-setup）
- **明确不参考** waybarrios/dgx-spark-finetune-llm

## Constraints

- **Tech stack**: 学生 = Qwen3-4B-Thinking-2507；训练 = QLoRA r=64（HF Transformers + PEFT 或 Unsloth，待 RESEARCH 验证）；蒸馏 API = OpenAI gpt-5.5 + reasoning_effort=high；导出 = llama.cpp GGUF
- **Hardware**: DGX Spark GB10 aarch64 CUDA 13；遵循 `/dgx-spark-training` 全部约束（无 flash-attn cu12、SDPA、swap/OOM 防护、复用已知良好 venv）
- **Timeline**: 单次端到端微调（不含数据生成）控制在 **6 小时以内**；数据生成单独的 4–6h 阶段
- **API**: 教师 API 并发 ≤ **10 worker**；遇 RPM/TPM 触发指数退避
- **Budget**: GPT-5.5 high 调用以 3000 样本为预算上限的设计点；超出需另议
- **Tokenizer 安全**: 训练任何思考标签都必须验证它会被拆成多个 sub-token（不在词表内、且不与原生 `<think>` 冲突）
- **数据约束**: 教师输出必须通过硬约束 lint（min/max/整数/相位覆盖）才能进训练集

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 学生基座选 Qwen3-4B-Thinking-2507 | 已具备 reasoning 能力可加速学习；架构成熟，DGX Spark 训练栈完全支持 | — Pending（trade-off：原生 RL 调成 `<think>`，强行换标签需要充分 SFT 覆盖） |
| 思考标签沿用 reality.log 体系 `<start_working_out>.../</end_working_out><SOLUTION>...</SOLUTION>` | memory 验证过不与 Qwen3 tokenizer 冲突；reality.log 已是此格式，下游 prompt builder 不必改 | ✓ Good |
| 教师固定 GPT-5.5 high，reasoning_effort=high | 蒸馏只在最强教师上才有最大收益 | — Pending |
| 不采用 reality.log 标签，重新让教师标注 | 旧 lmstudio 输出有偏；教师为准 | ✓ Good |
| 输入分布扩展合成（防过拟合） | reality.log 分布窄，OOD 泛化是 Core Value | ✓ Good |
| QLoRA r=64 + merge → GGUF | DGX Spark 6h 内最稳路径；以 `/home/samuel/dgx-spark-setup` + `/dgx-spark-training` 为准（natolambert 上游），不参考 waybarrios | — Pending |
| 训练 / val / OOD val = 80/10/10 | OOD val 单列以验证泛化，避免随机划分掩盖过拟合 | — Pending |
| 首轮规模 3000 样本，并发 ≤10 | API 速率友好；先打通闭环再扩量 | — Pending |
| GGUF 同时导出 fp16 与 q4_K_M | 部署灵活；q4_K_M 需单独评测以防量化崩塌 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-08 — v2.0 abandoned, milestone v3.0 9B 基座切换 started*
