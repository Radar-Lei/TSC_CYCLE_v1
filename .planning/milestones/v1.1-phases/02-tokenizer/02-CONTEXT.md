# Phase 2: Tokenizer 验证与数据准备 - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

确认 GLM tokenizer 与自定义标签兼容性，并生成增强版 SFT 训练数据。目标是让思考链长度达到 300-400 token，提升模型推理能力。

</domain>

<decisions>
## Implementation Decisions

### Tokenizer 验证策略
- **跳过专门验证**：SFT 训练足够快，若 tokenizer 有问题会在训练中暴露
- 不做额外的 tokenizer 词表分析或编码解码测试
- 若训练出现标签输出异常，再回退排查 tokenizer 问题

### 数据增强策略
- **执行者**：Claude 直接生成增强数据，不调用外部 LLM API
- **生成方式**：串行逐条处理，每条数据生成后立即保存
- **扩展风格**：自由生成，不做结构化模板约束
- **扩展重点**：均衡扩展思考链各环节，不侧重某一特定部分

### 数据验证
- **自动化校验**：脚本检查 JSON 结构、标签格式、token 长度
- **人工审核**：5% 抽样（约 50 条），快速确认整体质量

### 数据管理
- 备份原有 `train.jsonl` 为 `train.jsonl.bak`
- 新生成的数据直接覆盖原文件

</decisions>

<specifics>
## Specific Ideas

- 目标 token 长度：300-400 token（从现有较短的思考链扩展）
- 参考现有数据格式，保持 JSON 结构一致性

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-tokenizer*
*Context gathered: 2026-02-18*
