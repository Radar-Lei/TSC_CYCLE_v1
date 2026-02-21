# Milestones

## v1.0 Benchmark 统计优化 (Shipped: 2026-02-18)

**Phases completed:** 1 phase, 1 plan, 5 tasks

**Key accomplishments:**
- 实现加权平均统计 `calculate_weighted_average()` 和 `calculate_weighted_metrics()`，按周期时长加权确保模型比较公平
- 添加 throughput（吞吐量）指标到 comparison CSV 和终端输出
- TDD 完整覆盖：21 个单元测试全部通过，覆盖边界条件和端到端流程
- 向后兼容设计：`weighted_summary` 参数可选

**Git range:** d2a4a89 → 1be90f2
**Duration:** 14 days

---


## v1.1 模型训练与导出 (Shipped: 2026-02-21)

**Phases completed:** 3 phases + 3 quick tasks, 6 plans, ~14 tasks

**Key accomplishments:**
- 增强 SFT 训练数据 — 思考链从 85 字符扩展到 300-400 token，覆盖交通分析和配时推理
- Qwen3-4B SFT 训练完成 — LoRA 微调 (r=16/alpha=16)，解决响应掩码和模型权重合并问题
- 双格式 GGUF 导出 — F16 (7.5GB, 398 tensors) 和 Q4_K_M (2.4GB) 均成功生成
- GGUF 测试与部署 — sft_test.sh 支持 --gguf 选项，LM Studio 符号链接就绪
- GLM 迁移探索 — 完成代码迁移和 tokenizer 兼容性检查框架（最终转向 Qwen3）

**Scope change:** 原计划迁移到 GLM-4.7-Flash，因 FP8 兼容性问题转向 Qwen3-4B，通过 Quick Tasks 完成全部需求（13/13）

**Git range:** 00a29b6 → bce8288
**Timeline:** 4 天 (2026-02-18 → 2026-02-21)
**Codebase:** src ~7,796 LOC Python + docker ~1,762 LOC Shell
**Files changed:** 97 (6019 insertions, 8350 deletions)

---

