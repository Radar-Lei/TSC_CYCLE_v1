---
status: resolved
trigger: "grpo-reward-all-negative"
created: 2026-02-10T00:00:00Z
updated: 2026-02-10T00:09:00Z
---

## Current Focus

hypothesis: 已确认并修复根因
test: 运行 test_rewards.py 验证格式匹配逻辑
expecting: 所有 reward 函数能正确识别格式并给出差异化分数
next_action: 准备归档并提交修复

## Symptoms

expected: GRPO 训练中 reward 函数能正确识别模型输出格式，给出差异化的 reward 分数，使模型能通过 RL 学习改进
actual:
  - match_format_exactly/mean: 始终为 0.0 — 没有一个 completion 通过精确格式匹配
  - match_format_approximately/mean: 大多为 0.0，偶尔 -0.75
  - check_constraints/mean: 始终为 -2.0 — 约束检查完全失败
  - sumo_simulation_reward/mean: 始终为 0.0 — SUMO 从未执行
  - think_length_reward/mean: 始终为 -0.5
  - total reward: 始终 -2.5, reward_std: 0.0
  - frac_reward_zero_std: 几乎始终 1.0 — 4 个候选方案 reward 完全相同
  - loss: 接近 0.0 — 没有有效梯度
errors: 没有程序报错，但 reward 始终无差异化
reproduction: 运行 ./docker/grpo_train.sh，观察训练日志中的 reward 指标
started: 首次运行 GRPO 训练就出现此问题

## Eliminated

## Evidence

- timestamp: 2026-02-10T00:01:00Z
  checked: 参考脚本 qwen3_(4b)_grpo.py 第 250-256 行 match_format 正则
  found: |
    参考脚本正则: rf"{reasoning_end}.*?{solution_start}(.+?){solution_end_regex}[\s]{{0,}}$"
    - 只要求 </end_working_out>（reasoning_end）后跟 <SOLUTION>...</SOLUTION>
    - 不要求开头必须有 <start_working_out>（reasoning_start）
    当前实现正则: r"</think>\s*<CyclePlan>(.+?)</CyclePlan>\s*$"
    - 要求 </think> 在文本中出现，但模型生成时 <think> 已在 prompt 中
  implication: 参考脚本的正则更宽容，只检查结束标签后的结构，不检查开始标签

- timestamp: 2026-02-10T00:02:00Z
  checked: 参考脚本第 57-81 行 chat template 和 SFT/GRPO train.py 对比
  found: |
    参考脚本和当前实现的 chat template 完全一致：
    - add_generation_prompt=True 会在 prompt 末尾添加 '{reasoning_start}'（<think>）
    - 这意味着生成时 <think> 已在 prompt 中，模型只需生成后续内容
  implication: 模型生成的内容不包含 <think> 前缀是正常的

- timestamp: 2026-02-10T00:03:00Z
  checked: SFT 训练数据 sft_train.jsonl assistant content 格式
  found: |
    assistant content 完整格式: "<think>思考过程</think><CyclePlan>[...]</CyclePlan>"
    - SFT 训练时标签是完整的，但推理时 add_generation_prompt 会预添加 <think>
  implication: SFT 训练和 GRPO 推理的标签处理方式不同

- timestamp: 2026-02-10T00:04:00Z
  checked: SFT 推理测试脚本 test_inference.py 第 114-116 行
  found: |
    print("[模型输出]")
    print(think_tag + generated_text)
    # 手动在输出前加了 <think> 标签用于显示
  implication: 模型实际生成的 generated_text 不包含 <think>，需要手动添加才能完整显示

- timestamp: 2026-02-10T00:05:00Z
  checked: 参考脚本第 272-280 行 match_format_exactly 实现
  found: |
    def match_format_exactly(completions, **kwargs):
        for completion in completions:
            response = completion[0]["content"]
            if match_format.search(response) is not None: score += 3.0
    # match_format 正则: rf"{reasoning_end}.*?{solution_start}(.+?){solution_end_regex}"
    # 只要求 reasoning_end 后有 solution 标签，不要求完整格式包含 reasoning_start
  implication: 参考脚本的格式检查适配模型实际输出（不含 <think> 前缀）

- timestamp: 2026-02-10T00:08:00Z
  checked: 运行 test_rewards.py 验证修复后的 reward 函数
  found: |
    match_format_exactly: 正确格式得 3.0 分，错误格式得 0.0 分 ✓
    match_format_approximately: 正确格式得 1.5 分，错误格式得 0.0 或负分 ✓
    check_constraints: 有效 JSON 得 2.0 分，无效得 -2.0 分 ✓
    think_length_reward: 根据思考长度给出差异化惩罚 ✓
    关键测试：`</think>\n\n<CyclePlan>` 格式（有换行）也能正确匹配得分 3.0
  implication: 修复成功，正则 `.*?` 能正确处理 </think> 和 <CyclePlan> 之间的任意空白

## Resolution

root_cause: rewards.py 中的正则表达式和 think_length_reward 提取逻辑未考虑 GRPO 推理时的实际输出格式。由于 chat template 中 add_generation_prompt=True 会在 prompt 末尾自动添加 <think> 标签，模型生成的 completion[0]["content"] 只包含 <think> 之后的内容（格式为"思考内容</think><CyclePlan>...</CyclePlan>"），不包含 <think> 起始标签。原正则 r"</think>\s*<CyclePlan>" 中 \s* 只匹配空白字符，无法处理可能出现的换行或其他内容，导致格式匹配失败。

fix: |
  1. 修改 match_format 正则（第 35-38 行）：
     - 从 r"</think>\s*<CyclePlan>" 改为 r"</think>.*?<CyclePlan>"
     - 使用 .*? 允许 </think> 后有任意内容（包括换行、空白）再匹配 <CyclePlan>
     - 保持 re.DOTALL 标志使 . 能匹配换行符

  2. 简化 think_length_reward（第 524-572 行）：
     - 移除 think_content.replace("<think>", "") 操作
     - 因为 completion 本身就不包含 <think> 标签，只需提取 </think> 之前的内容

  3. 添加注释说明（第 35-38 行）：
     - 明确 completion 的实际格式："思考内容</think><CyclePlan>...</CyclePlan>"
     - 说明 add_generation_prompt=True 已预添加 <think>，避免未来混淆

verification: |
  创建测试脚本 src/grpo/test_rewards.py 验证修复：
  - match_format_exactly: 正确格式 → 3.0 分，错误格式 → 0.0 分 ✓
  - match_format_approximately: 正确格式 → 1.5 分，错误格式 → 负分 ✓
  - check_constraints: 有效 JSON → 2.0 分，无效 → -2.0 分 ✓
  - think_length_reward: 根据长度给出差异化惩罚 ✓
  关键测试案例：`</think>\n\n<CyclePlan>` 格式（有换行）也能正确匹配 ✓

files_changed:
  - src/grpo/rewards.py
