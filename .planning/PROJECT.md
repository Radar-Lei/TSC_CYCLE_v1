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

**v1.0 deployment artifact**: formerly `runs/20260507T032419Z/gguf/model.q4_K_M.gguf`; removed from this working tree during v4.1 cleanup because it is not part of the v4 Qwen3-4B 9k reproduction package.

**v2.0 强化版 ABANDONED** (2026-05-08) — 完成 Phase 7（标签协议全链路迁移），Phase 8（10K 数据扩容）已规划未执行；用户决定放弃 v2.0、直接切到更大基座。归档见 `.planning/milestones/v2.0-abandoned/`。

**v3.0 9B 基座切换 STOPPED** (2026-05-10) — Phase 1-3 完成，扩展数据与 Qwen3.5 retokenize/split 已产出；Phase 4 发现 Qwen3.5-9B 在本机训练太慢，用户决定停止 9B 路线，回到 v1 的 4B 基座。

**v4.0 SHIPPED** (2026-05-11) — 回到 `Qwen/Qwen3-4B-Thinking-2507`，复用 v3 lint-pass 扩展数据重建 Qwen3-4B 数据集，修复全链路思考协议为 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>`，完成 4B QLoRA 重训、merge、GGUF fp16/q4_K_M 导出、eval matrix GO 决策与 426 条 `reality.log` 输入 replay。

**v4.0 deployment artifact**: `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf` — Phase 11 推荐 q4_K_M GGUF；`reality_test.log` 已由该模型生成并通过 426/426 parse、lint、protocol gate。

See `milestones/v4.0-ROADMAP.md` and `milestones/v4.0-REQUIREMENTS.md` for shipped v4.0 details.

**v4.1 SHIPPED** (2026-05-12) — 项目清理 / v4 最小复现包完成：建立 repo-level reproduction manifest/guide，删除非 v4 复现必需的 legacy/cache clutter，并通过 no-cache manifest/test handoff 验证保留的 v4.0 Qwen3-4B 9k 包仍可复核。

**v4.1 reproduction entry point**: `reproduction/v4.0-qwen3-4b-9k-guide.md` and `reproduction/v4.0-qwen3-4b-9k-manifest.json`.

See `milestones/v4.1-ROADMAP.md` and `milestones/v4.1-REQUIREMENTS.md` for shipped v4.1 details.

## Current Milestone: None — awaiting next milestone

**Last completed milestone:** v4.1 项目清理 / v4 最小复现包。

**Validated features:**
- 盘点当前根目录、data/artifacts/runs/planning/tests 中哪些文件属于 v4.0 复现权威源，哪些是旧里程碑、临时文件或重复产物。— Validated in Phase 13 via `inventory.json` and `inventory.md`
- 建立 v4 最小复现包边界：代码、配置、数据 manifest/必要数据、最终报告、最终 q4_K_M GGUF、`reality_test.log` 及必要验证证据。— Validated in Phase 14 via `reproduction/v4.0-qwen3-4b-9k-manifest.json` and `reproduction/v4.0-qwen3-4b-9k-guide.md`
- 将与 v4 无关或非必要的文件安全移除，并保证清理后测试与复现入口仍可运行。— Validated in Phase 15 via direct cleanup, cleanup notes, manifest check, and cleanup/reproduction pytest subset
- 补齐复现说明或清单，让外部人员知道从哪里开始、哪些产物是最终产物、如何验证 v4 结果。— Validated in Phase 16 via no-cache manifest/test handoff verification

## Next Milestone Goals

下一里程碑聚焦 v4.1 清理完成后的部署或分析方向，暂不纳入当前范围：

- 将 v4.0 q4_K_M artifact 接入 EvoProgTSC 决策端点并做端到端部署验证。
- 对显式思考协议做 thinking on/off 对照，量化其对最终绿灯决策的边际收益。
- 若部署端发现量化敏感性，补做 imatrix 或 q5_K_M fallback 路线。

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

### Validated (v4.0)

- [x] 学生基座回退到 `Qwen/Qwen3-4B-Thinking-2507`，沿用 v1 已验证训练与 GGUF 导出路径 — Validated in Phase 7
- [x] 复用 v3 扩展数据，重建 Qwen3-4B tokenizer 下的 split/tokenized dataset — Validated in Phase 8
- [x] 全链路标签协议固定为 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>`，禁止 `<end_working_out>` 和原生 `<think>` — Validated in Phase 7-12
- [x] 重新完成 4B QLoRA SFT、merge、GGUF fp16/q4_K_M 导出与 eval matrix — Validated in Phase 9-11
- [x] OOD 硬约束、教师 MAE、思考格式稳定性达到 v4.0 GO gate，并完成 `reality_test.log` replay — Validated in Phase 11-12

### Lessons (v2.0/v3.0 stopped)

- [x] v2.0 标签迁移方向需要纠正：本项目协议应使用 `</end_working_out>` 作为思考结束标签，而不是 `<end_working_out>`。
- [x] v3.0 Phase 1-3 产出的扩展数据有复用价值，但 Qwen3.5-9B 本机训练太慢，不适合作为当前路线。

### Validated (v4.1)

- [x] v4.1 清理当前项目目录中与 v4.0 Qwen3-4B 9k 训练复现无关的文件，形成最小复现包。— Validated in Phase 15
- [x] v4.1 保留并标注 v4.0 复现权威源：代码、配置、必要数据/manifest、最终模型、最终报告和验证证据。— Validated in Phase 16
- [x] v4.1 清理后仍能运行关键测试、报告生成或验证入口，证明复现链路没有被破坏。— Validated in Phase 16

### Active

- [ ] 下一里程碑待定义。

### Out of Scope (current route)

- Qwen3.5-9B 继续训练 — 本机训练太慢，当前路线回到 4B
- Qwen3.6 系列基座 — 系列最小 27B，与"小模型本地部署" Core Value 冲突
- 模型原生 `<think>...</think>` 标签 — 与自定义协议冲突
- 使用 `<end_working_out>` 作为结束标签 — 用户明确要求结束标签是 `</end_working_out>`
- 在线/RL 优化（GRPO 等）— 当前路线只做 SFT 蒸馏
- 全参 SFT — 当前目标是本地可训练、可部署的 QLoRA 4B 路线
- vLLM 推理 — 本机现状不能用 vLLM，最终部署走 llama.cpp / GGUF
- 引入新训练栈（Unsloth on Spark / Axolotl / 新 PyTorch 版本）— 锁定 `/dgx-spark-training` v1.0 已验证环境
- v4.1 不重新训练、不新增模型能力、不做 imatrix/q5_K_M 或 thinking on/off 新实验、不接入 EvoProgTSC 部署端点 — 当前范围只做项目清理与复现打包

## Context

**领域**：TSC（Traffic Signal Control）周期绿灯时长决策。输入是各相位的预测等待车辆数、
预测饱和度、容量、min/max_green；输出是各相位下一周期绿灯秒数（整数、上下限内）。
prompt/输出协议见 `reality.log`。

**先验积累（来自 memory + 既有项目）**：
- `EvoProgTSC` 项目（`/home/samuel/projects/EvoProgTSC/evoprog/llm/client.py`）已有
  openai 库 + reasoning_effort + 重试 + JSON Schema 结构化输出的成熟封装，可直接复用
- Qwen3 tokenizer 中 `<think>`(151667)/`</think>`(151668) 是 added tokens 且预训练
  权重对其有先入语义；用作自定义 SFT 标签会导致语义冲突 → 必须使用词表外的多 sub-token 标签
  （`<start_working_out>` / `</end_working_out>` / `<SOLUTION>` / `</SOLUTION>`，与 reality.log 一致）
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
| 学生基座选 Qwen3-4B-Thinking-2507 | 已具备 reasoning 能力可加速学习；架构成熟，DGX Spark 训练栈完全支持；v3.0 9B 训练过慢后重新确认为当前甜点基座 | ✓ Good |
| 思考标签沿用 reality.log 体系 `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` | 用户确认结束标签必须是 `</end_working_out>`；不与 Qwen3 tokenizer 原生 `<think>` 协议混用 | ✓ Good |
| 教师固定 GPT-5.5 high，reasoning_effort=high | 蒸馏只在最强教师上才有最大收益 | ✓ Good |
| 不采用 reality.log 标签，重新让教师标注 | 旧 lmstudio 输出有偏；教师为准 | ✓ Good |
| 输入分布扩展合成（防过拟合） | reality.log 分布窄，OOD 泛化是 Core Value | ✓ Good |
| QLoRA r=64 + merge → GGUF | DGX Spark 6h 内最稳路径；以 `/home/samuel/dgx-spark-setup` + `/dgx-spark-training` 为准（natolambert 上游），不参考 waybarrios | ✓ Good |
| 训练 / val / OOD val = 80/10/10 | OOD val 单列以验证泛化，避免随机划分掩盖过拟合 | ✓ Good |
| 首轮规模 3000 样本，并发 ≤10 | API 速率友好；先打通闭环再扩量 | ✓ Good |
| GGUF 同时导出 fp16 与 q4_K_M | 部署灵活；q4_K_M 需单独评测以防量化崩塌 | ✓ Good |
| v4.0 回退 4B 而不是继续 9B | Qwen3.5-9B 本机训练太慢；4B 已验证可训练可部署，且符合本地小模型 Core Value | ✓ Good |
| Phase 12 使用 Phase 11 GO q4_K_M 生成 `reality_test.log` | 需要以最新训练模型输出替换 reality.log 旧输出，同时保留显式思考过程 | ✓ Good |
| v4.1 只做项目清理与最小复现包 | 用户对 v4.0 的 Qwen3-4B 9k 训练效果满意，当前痛点是项目文件夹过杂、影响他人复现 | ✓ Good |

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
*Last updated: 2026-05-12 after v4.1 milestone completion*
