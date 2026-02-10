# Milestones

## v1.0 MVP (Shipped: 2026-02-10)

**Phases completed:** 3 phases, 6 plans, 12 tasks
**Timeline:** 6 days (2026-02-04 → 2026-02-10)

**Key accomplishments:**
- 分层抽样策略从 1588 条数据中抽取 100 条代表性 SFT 样本，覆盖全部 34 个交叉口
- AI 逐条手工撰写 100 条中文短 think 内容，组装为完整 SFT 训练数据集
- 基于 unsloth + LoRA 的 SFT 训练流水线，让 Qwen3-4B-Base 学会输出格式
- GRPO 数据准备：1588 条 prompt + state_file 关联，支持实时 SUMO 仿真
- 三层 reward 函数体系（L1 格式匹配 + L2 渐进式约束 + L3 SUMO 仿真 reward）
- 完整 GRPO 训练流水线（Docker 容器化，多进程并行 SUMO 仿真）

**Delivered:** 完整的交通信号配时优化大模型微调流水线，涵盖 SFT 数据生成、SFT 训练、GRPO 数据准备、GRPO 训练全流程。

---

