# Phase 3: 数据组装、训练验证与模型导出 - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

将 Phase 2 的 GLM-5 生成结果组装为标准 SFT 训练数据（messages 格式），运行 1 epoch 训练验证数据质量，并导出 Q4_K_M、Q8_0、F16 三种 GGUF 量化模型。训练和导出在 Docker 容器中执行。

</domain>

<decisions>
## Implementation Decisions

### 数据组装
- 输入：`outputs/glm5/results.jsonl`（Phase 2 产出，每行含 prompt/prediction/think/solution/metadata）
- 输出：`outputs/sft/sft_train.jsonl`（messages 格式 [{role: system, content: SYSTEM_PROMPT}, {role: user, content: prompt}, {role: assistant, content: <start_working_out>think<end_working_out><SOLUTION>solution</SOLUTION>}]）
- 复用现有 `src/data_generator/prompt_builder.py` 中的 SYSTEM_PROMPT
- 组装脚本放在 `src/glm5/assembler.py`，CLI 入口

### 训练验证
- 使用现有 `src/sft/train.py` + `docker/sft_train.sh`
- 需要修改 `config/config.json` 中 SFT 相关路径指向新数据
- 训练 1 epoch（已配置为 2 epochs，需临时调整或验证当前配置）
- 训练在 Docker 容器中执行，需用户手动触发

### 模型导出
- 使用现有 `src/export_gguf.py` + `docker/convert_gguf.sh`
- 导出 Q4_K_M、Q8_0、F16 三种格式
- 导出也在 Docker 容器中执行

### Claude's Discretion
- 组装脚本的具体错误处理方式
- config.json 修改的细节

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/sft/train.py`: 完整的 SFT 训练管道（model setup, data loading, training, saving）
- `src/export_gguf.py`: GGUF 导出脚本
- `docker/sft_train.sh`: Docker 中执行 SFT 训练
- `docker/convert_gguf.sh`: Docker 中执行 GGUF 转换
- `src/data_generator/prompt_builder.py`: SYSTEM_PROMPT 常量
- `src/scripts/generate_sft_data.py`: 现有 SFT 数据组装脚本（prepare/assemble 子命令）

### Established Patterns
- messages 格式: [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]
- assistant 内容: `<start_working_out>...<end_working_out><SOLUTION>...</SOLUTION>`
- JSONL 格式一行一个 JSON

### Integration Points
- 输入: `outputs/glm5/results.jsonl`（Phase 2）
- 中间: `outputs/sft/sft_train.jsonl`（组装后的训练数据）
- 输出: `outputs/sft/model/`（训练后模型）+ GGUF 文件
- 配置: `config/config.json`（SFT 训练参数）

</code_context>

<specifics>
## Specific Ideas

- 训练和导出步骤需要 Docker 环境，是 checkpoint 类型任务
- 组装脚本可自动化执行

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
