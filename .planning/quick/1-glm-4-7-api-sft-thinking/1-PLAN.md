---
phase: quick
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - src/scripts/backfill_thinking.py
  - src/scripts/generate_training_data.py
autonomous: true

must_haves:
  truths:
    - "SFT 训练数据 outputs/sft/train.jsonl 中每条记录的 assistant content 包含非空的 <think>...</think> 推理过程"
    - "thinking 内容由 GLM-4.7 API 生成，是对交通信号配时决策的合理分析"
    - "thinking 之后的 JSON 答案部分保持不变（与原始 SFT 数据一致）"
  artifacts:
    - path: "src/scripts/backfill_thinking.py"
      provides: "独立的 thinking 回填脚本，调用 GLM-4.7 API 为 SFT 数据生成 thinking"
    - path: "outputs/sft/train.jsonl"
      provides: "更新后的 SFT 训练数据，包含真实 thinking 内容"
  key_links:
    - from: "src/scripts/backfill_thinking.py"
      to: "GLM-4.7 API"
      via: "requests POST to https://open.bigmodel.cn/api/paas/v4/chat/completions"
    - from: "src/scripts/backfill_thinking.py"
      to: "outputs/sft/train.jsonl"
      via: "读取现有 SFT JSONL，替换 thinking 部分，写入新文件"
---

<objective>
为 SFT 训练数据的 9576 条样本生成真实的 thinking 推理内容，替换当前的空 `<think>\n\n</think>` 占位符。

Purpose: 高质量的 CoT (Chain-of-Thought) 训练数据需要真实的推理过程。通过 GLM-4.7 API 为每个样本生成合理的信号配时分析思考过程，使 SFT 训练能教会模型"如何思考"而不仅是"输出什么"。

Output:
- `src/scripts/backfill_thinking.py` — 独立可重跑的回填脚本
- `outputs/sft/train.jsonl` — 更新后的 SFT 数据（thinking 部分已填充）
</objective>

<execution_context>
@/home/samuel/.claude/get-shit-done/workflows/execute-plan.md
@/home/samuel/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/scripts/generate_training_data.py (convert_to_sft_format 函数，第 224-339 行)
@config/config.json (paths 配置)
@data/training/train.jsonl (原始训练数据，9576 条)
@outputs/sft/train.jsonl (当前 SFT 数据，thinking 为空占位符)
</context>

<tasks>

<task type="auto">
  <name>Task 1: 创建 GLM-4.7 thinking 回填脚本</name>
  <files>src/scripts/backfill_thinking.py</files>
  <action>
创建独立脚本 `src/scripts/backfill_thinking.py`，功能如下：

**核心逻辑：**
1. 读取 `outputs/sft/train.jsonl`，逐行解析
2. 对每条记录，提取 user content（交通信号输入）和 assistant content 中的 JSON 答案部分（`<think>...</think>` 之后的 JSON 数组）
3. 构造 GLM-4.7 API 请求，prompt 设计为：
   - system: "你是交通信号配时优化专家。请根据输入数据和已知的最终配时结果，生成简短的分析思考过程。"
   - user: 包含原始输入数据和已知答案，要求生成导向该答案的分析推理。prompt 模板如下：
     ```
     以下是一个交通信号配时任务的输入和已知正确答案。
     请生成简短的分析思考过程（3-5句话），说明如何根据各相位的饱和度(pred_saturation)、min_green、max_green 得出该答案。
     只输出思考过程文本，不要输出 <think> 标签，不要输出 JSON。

     【输入数据】
     {user_content 中的 cycle_predict_input_json 部分}

     【正确答案】
     {assistant content 中的 JSON 数组}
     ```
4. 解析 GLM-4.7 返回的 thinking 文本
5. 重新组装 assistant content: `<think>\n{thinking_text}\n</think>\n{original_json_answer}`
6. 写入新的 SFT JSONL 文件

**API 调用细节：**
- Endpoint: `https://open.bigmodel.cn/api/paas/v4/chat/completions`
- Model: `glm-4.7`
- API Key: `d8318666ab424416b427231b9d503f75.NYYiQKROscMtungx`
- Headers: `Authorization: Bearer {API_KEY}`, `Content-Type: application/json`
- 使用 `requests` 库（已安装，不用 openai SDK）
- temperature: 0.7, max_tokens: 300（thinking 不需要太长）

**健壮性设计：**
- **断点续跑**: 使用进度文件 `outputs/sft/.backfill_progress.json` 记录已处理的行号。重跑时跳过已完成的行。输出写入 `outputs/sft/train_with_thinking.jsonl`（临时文件），完成后原子替换 `train.jsonl`。
- **重试机制**: 每个 API 调用最多重试 3 次，指数退避（1s, 2s, 4s）。捕获网络错误和非 200 状态码。
- **速率控制**: 每次请求间 sleep 0.1 秒（避免触发 rate limit）。
- **并发**: 使用 `concurrent.futures.ThreadPoolExecutor`，默认 5 个并发线程（可通过 `--concurrency` 参数调整）。
- **进度显示**: 每 100 条打印一次进度 `[已完成/总数] xx%`，打印预估剩余时间。
- **错误处理**: API 返回异常时记录错误但继续处理（将该条的 thinking 保留为空），最后汇总报告失败数。

**命令行参数：**
- `--input`: SFT JSONL 输入路径（默认 `outputs/sft/train.jsonl`）
- `--output`: 输出路径（默认 `outputs/sft/train_with_thinking.jsonl`）
- `--concurrency`: 并发线程数（默认 5）
- `--max-samples`: 最大处理样本数（可选，用于测试，如 `--max-samples 10`）
- `--dry-run`: 仅处理前 3 条并打印结果，不写文件

注意：API Key 直接硬编码在脚本中（项目内部使用，不是公开库）。也支持环境变量 `GLM_API_KEY` 覆盖。
  </action>
  <verify>
运行 dry-run 模式验证 API 调用正常：
```bash
python -m src.scripts.backfill_thinking --dry-run
```
应能看到 3 条样本的 thinking 输出，内容是关于交通信号配时的合理分析。
  </verify>
  <done>
- `src/scripts/backfill_thinking.py` 存在且可执行
- dry-run 模式成功调用 GLM-4.7 API 并返回合理的 thinking 文本
- thinking 文本是中文，3-5 句话，涉及饱和度分析和绿灯时间决策
  </done>
</task>

<task type="auto">
  <name>Task 2: 执行全量回填并更新 SFT 数据</name>
  <files>outputs/sft/train.jsonl</files>
  <action>
1. 运行回填脚本处理全部 9576 条样本：
   ```bash
   python -m src.scripts.backfill_thinking --concurrency 5
   ```
2. 等待脚本完成（预估：9576 条 / 5 并发 / ~1s 每条 ≈ ~32 分钟）
3. 验证输出文件 `outputs/sft/train_with_thinking.jsonl` 行数与原文件一致（9576 行）
4. 抽查 5 条记录确认 thinking 内容非空且合理
5. 将 `train_with_thinking.jsonl` 替换 `train.jsonl`：
   ```bash
   cp outputs/sft/train.jsonl outputs/sft/train_empty_thinking.jsonl.bak
   mv outputs/sft/train_with_thinking.jsonl outputs/sft/train.jsonl
   ```
6. 清理进度文件

注意：如果脚本中途失败或被中断，直接重跑即可（断点续跑机制会跳过已处理的行）。
  </action>
  <verify>
```bash
# 验证行数一致
wc -l outputs/sft/train.jsonl
# 应输出 9576

# 验证无空 thinking
python3 -c "
import json
empty = 0
total = 0
with open('outputs/sft/train.jsonl') as f:
    for line in f:
        total += 1
        msg = json.loads(line)
        content = msg['messages'][2]['content']
        if '<think>\n\n</think>' in content:
            empty += 1
print(f'Total: {total}, Empty thinking: {empty}, Filled: {total - empty}')
assert empty == 0, f'{empty} samples still have empty thinking!'
print('ALL PASSED: Every sample has non-empty thinking content')
"
```
  </verify>
  <done>
- outputs/sft/train.jsonl 包含 9576 条记录
- 所有记录的 `<think>...</think>` 中包含非空的推理文本
- JSON 答案部分与原始数据一致（未被修改）
- 原始空 thinking 版本已备份为 train_empty_thinking.jsonl.bak
  </done>
</task>

</tasks>

<verification>
1. `outputs/sft/train.jsonl` 行数 = 9576
2. 每条记录的 assistant content 格式为 `<think>\n{非空文本}\n</think>\n[JSON数组]`
3. JSON 数组部分与回填前完全一致
4. thinking 内容是中文，涉及交通信号配时分析
</verification>

<success_criteria>
- SFT 训练数据中 100% 的样本包含由 GLM-4.7 生成的真实 thinking 推理过程
- thinking 内容质量合理：基于饱和度分析各相位绿灯时间决策
- 数据总量不变（9576 条）
- 脚本可重跑（断点续跑 + 幂等）
</success_criteria>

<output>
完成后，创建 `.planning/quick/1-glm-4-7-api-sft-thinking/1-SUMMARY.md`
</output>
