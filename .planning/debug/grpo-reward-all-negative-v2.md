---
status: fixing
trigger: "Continue debugging grpo-reward-all-negative. The previous fix (changing \\s* to .*? in regex) did NOT work — reward is still -2.5 across all steps."
created: 2026-02-10T00:00:00Z
updated: 2026-02-10T04:00:00Z
---

## Current Focus

hypothesis: SFT模型训练正确,但需要验证推理输出是否包含`</think>`标签
test: 运行修改后的test_inference.py脚本,检查模型输出
expecting: 如果模型正确,输出应包含`</think>`;如果不包含,说明SFT训练有问题
next_action: 让用户运行 python3 src/sft/test_inference.py 查看输出

## Symptoms

expected: GRPO训练中reward应该有变化，反映不同completion的质量差异
actual: 所有step的reward都是-2.5，完全没有变化（match_format_exactly=0, check_constraints=-2.0, reward=-2.5, reward_std=0.0）
errors: 无错误消息，但reward完全静态
reproduction: 运行grpo_train.sh，观察reward指标
started: 之前的修复（将正则表达式从\\s*改为.*?）没有任何效果

## Eliminated

- hypothesis: 正则表达式\\s*无法匹配标签之间的内容
  evidence: 将\\s*改为.*?后，reward指标完全相同，没有任何变化
  timestamp: 2026-02-10T00:00:00Z

## Evidence

- timestamp: 2026-02-10T00:00:00Z
  checked: 之前的修复尝试
  found: 正则表达式修复无效
  implication: 问题不在正则表达式本身，而是我们不知道模型实际生成了什么内容

- timestamp: 2026-02-10T00:01:00Z
  checked: rewards.py, qwen3_(4b)_grpo.py, train.py (SFT and GRPO)
  found: |
    1. rewards.py使用正则: r"</think>.*?<CyclePlan>(.+?)</CyclePlan>\s*$"
    2. qwen3_(4b)_grpo.py使用: rf"{reasoning_end}.*?{solution_start}(.+?){solution_end_regex}[\s]{0,}$"
    3. 两者基本等价，但参考脚本有EOS token处理
    4. 关键发现：chat template中add_generation_prompt会预置<think>，completion从<think>后开始
    5. 参考脚本在match_format_exactly中直接打印response用于调试
  implication: 需要查看实际completion内容，可能模型生成格式与预期不符

- timestamp: 2026-02-10T00:02:00Z
  checked: 修改rewards.py添加诊断性打印
  found: |
    在match_format_exactly()开头添加了详细的调试打印：
    - completion类型和结构
    - response的前500字符和后200字符
    - 关键标签的存在情况和计数
    - 正则匹配结果
  implication: 下次运行训练时会看到模型实际生成的内容

- timestamp: 2026-02-10T04:00:00Z
  checked: 深度分析SFT数据格式,chat template逻辑,对比参考脚本
  found: |
    **关键发现:**

    1. SFT数据格式 (src/scripts/generate_sft_data.py line 167):
       assistant_content = "<think>{think_text}</think><CyclePlan>{solution_json}</CyclePlan>"
       这和参考脚本的逻辑完全一致!

    2. SFT训练时(tokenize=False, add_generation_prompt未指定, 默认False):
       完整文本: "系统<eos>用户<think>思考</think><CyclePlan>...</CyclePlan><eos>"
       ✓ 没有双重<think>问题

    3. GRPO推理时(add_generation_prompt=True):
       Prompt: "系统<eos>用户<think>"
       期望输出: "思考</think><CyclePlan>...</CyclePlan>"

    4. 参考脚本使用相同逻辑:
       - SFT数据: "<start_working_out>思考</end_working_out><SOLUTION>答案</SOLUTION>"
       - 推理时prompt末尾: "<start_working_out>"
       - 期望输出: "思考</end_working_out><SOLUTION>...</SOLUTION>"

    **结论:** 我们的设计逻辑正确,和参考脚本一致!

    **疑问:** 那为什么模型不输出`</think>`?

    可能原因:
    a) SFT训练时间/数据量不足,模型没学好
    b) 标签`</think>`的tokenization有问题
    c) 模型训练过程中出现其他问题

    **下一步:** 测试实际SFT模型的推理输出
  implication: 需要运行test_inference.py验证SFT模型是否正确学习了格式

## Resolution

root_cause: |
  待确认 - 等待SFT模型推理测试结果。

  已确认:
  - SFT数据格式设计正确,与参考脚本逻辑一致
  - Chat template配置正确
  - 用户报告模型不输出`</think>`标签

  待验证假设:
  1. SFT训练不充分(epochs/steps不足)
  2. 标签tokenization问题
  3. 其他训练问题

fix: |
  等待test_inference.py测试结果后确定修复方案。

  可能的修复路径:
  - 如果模型确实不输出`</think>`: 增加SFT训练轮数,或检查训练配置
  - 如果模型输出正常: 问题在GRPO inference设置,需要检查GRPO chat template配置

verification: |
  步骤1: 运行 python3 src/sft/test_inference.py
  - 查看模型输出是否包含`</think>`标签
  - 查看格式匹配是否成功

  步骤2: 根据结果决定下一步行动

files_changed: ["src/sft/test_inference.py"]
