# Phase 1: SFT 数据与训练 - Context

**Gathered:** 2026-02-09
**Status:** Ready for planning

<domain>
## Phase Boundary

构造约 100 条 SFT 样本让 Qwen3-4B-Base 学会 `<think>...<think><solution>...<solution>` 输出格式，并完成 LoRA 微调训练。样本包含中文短思考和满足硬约束的 final 绿灯时长。GRPO 数据准备和 GRPO 训练属于后续阶段。

</domain>

<decisions>
## Implementation Decisions

### 思考链内容设计
- 风格：简洁分析型——分析每个相位饱和度、比较大小、简要说明分配思路
- 语言：中英混合，专业术语可直接用英文（如 saturation, capacity）
- 内容深度：只说定性方向不算数，如"相位0 saturation 较高应多分配"，不需要具体数值计算过程
- think 内容由 AI 直接手工生成，不用代码程序生成

### 样本抽取策略
- 综合策略：先确保覆盖所有交叉口，再按饱和度分布补充
- 数量：约 100 条，可灵活调整（90-120 范围均可）
- 流程：程序脚本完成抽取，AI 逐条生成 think + solution 内容

### SFT 训练配置
- 超参数：参考 qwen3_(4b)_grpo.py 中的做法，所有超参数统一写入 config.json
- chat template：参考 qwen3_(4b)_grpo.py 中 SFT 的处理方式
- Docker 脚本：docker/sft_train.sh 与 data.sh 基本一致，可微调细节
- 模型保存：合并 LoRA 保存完整模型到 outputs/sft/model

### final 值生成逻辑
- 质量要求：满足硬约束即可（min_green ≤ final ≤ max_green），不需要模拟专家最优判断，GRPO 阶段会优化质量
- 总周期约束：SFT 阶段不重要，各相位独立分配即可
- 约束校验：AI 生成时注意约束 + 程序双重校验
- min_green/max_green 来源：已写在每条样本的 prediction 中，直接使用即可

### Claude's Discretion
- think 内部的具体结构模板（是否逐相位分析、是否有总结句等）
- 是否刻意包含极端饱和度场景
- final 值的具体生成策略（按饱和度比例分配、线性映射等）
- 具体的 LoRA 超参数调优

</decisions>

<specifics>
## Specific Ideas

- SFT 只教格式，不追求方案最优——"学会说话"而非"学会思考"
- think 内容手写不用代码，保证自然语言质量
- 程序抽取样本确保分布合理，AI 生成内容确保格式正确

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-sft-data-and-training*
*Context gathered: 2026-02-09*
