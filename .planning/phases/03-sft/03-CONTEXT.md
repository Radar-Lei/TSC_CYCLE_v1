# Phase 3: SFT 训练迁移 - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

完成 GLM-4.7-Flash 的 SFT 训练流程迁移，产出可用的微调模型。包括模型加载、LoRA 适配器配置、端到端训练流程、以及训练后的推理验证。

**关键变更**：原计划使用 GLM-4.7-Flash-FP8-Dynamic，经训练验证发现问题，现改为 `unsloth/GLM-4.7-Flash`（标准 BF16）。

</domain>

<decisions>
## Implementation Decisions

### 模型选择
- 模型：`unsloth/GLM-4.7-Flash`（BF16 精度，非 FP8-Dynamic）
- 参考：Unsloth GLM Flash A100 notebook 官方推荐配置
- 兼容性：必须保持与现有 Qwen3 SFT 管道的兼容

### LoRA 配置
- LoRA rank: 16
- LoRA alpha: 16
- LoRA dropout: 0
- bias: "none"
- target_modules: `["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]`（LLaMA-style 架构，与 Qwen3 相同）
- use_gradient_checkpointing: "unsloth"

### 训练数据
- 使用 Phase 2 已生成的增强训练数据
- 数据路径：`data/sft/train.jsonl`
- 无需重新生成数据

### 推理验证方式
- 使用现有 `sft_test.sh` 脚本进行测试
- 验证关注点：基本生成能力（模型能否正常输出）
- 评估方式：人工检查输出质量
- 通过标准：输出格式正确即视为迁移成功

### Claude's Discretion
- 训练超参数微调（learning rate、batch size、gradient accumulation）
- 训练监控策略（检查点保存频率、日志记录、早停机制）
- 恢复训练逻辑

</decisions>

<specifics>
## Specific Ideas

- 沿用现有 `sft_test.sh` 测试流程，无需额外开发验证工具
- 验证标准简单明确：格式正确 = 成功
- 参考 Unsloth 官方 notebook 配置，确保训练稳定性

</specifics>

<deferred>
## Deferred Ideas

None — 讨论保持在阶段范围内

</deferred>

---

*Phase: 03-sft*
*Context gathered: 2026-02-19*
