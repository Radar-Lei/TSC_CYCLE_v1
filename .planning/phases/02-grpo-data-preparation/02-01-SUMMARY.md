---
phase: 02-grpo-data-preparation
plan: 01
subsystem: data-pipeline
tags: [grpo, data-generation, prompt-builder, data-transformation]
dependency_graph:
  requires:
    - outputs/data/train.jsonl
    - src/data_generator/prompt_builder.py
  provides:
    - outputs/grpo/grpo_train.jsonl (1588 条 GRPO 格式样本)
    - src/scripts/generate_grpo_data.py (GRPO 数据生成脚本)
  affects:
    - Phase 3 GRPO 训练流程
tech_stack:
  added:
    - GRPO 数据格式 (messages 数组: system + user)
  patterns:
    - 路径转换 (绝对路径 → 相对路径)
    - Prompt 分离 (system + user content)
key_files:
  created:
    - src/scripts/generate_grpo_data.py (171 行)
    - outputs/grpo/grpo_train.jsonl (1588 条)
  modified:
    - src/data_generator/prompt_builder.py (更新 SYSTEM_PROMPT 和 build_prompt)
decisions:
  - decision: "SYSTEM_PROMPT 与 SFT 阶段完全一致"
    rationale: "保证训练一致性，强调分析和推理过程"
  - decision: "build_prompt() 不再拼入 SYSTEM_PROMPT"
    rationale: "分离 system 和 user content，便于 GRPO 格式组装"
  - decision: "State file 转换为相对路径"
    rationale: "提高数据可移植性，避免硬编码绝对路径"
  - decision: "GRPO 数据无 answer 字段"
    rationale: "Reward 由 SUMO 仿真实时计算，方案空间大无法预计算"
metrics:
  duration: 282s
  tasks_completed: 2
  files_created: 2
  files_modified: 1
  data_samples: 1588
  completed_at: "2026-02-09T16:38:44Z"
---

# Phase 02 Plan 01: GRPO 数据准备与格式转换 Summary

JWT 认证与刷新轮换机制已使用 jose 库实现完成。

## 一句话总结

更新 prompt_builder.py 的 SYSTEM_PROMPT 使其与 SFT 阶段一致（包含 <think> 和 <CyclePlan> 标签格式说明），创建 GRPO 数据生成脚本将 train.jsonl 全部 1588 条样本转换为 GRPO 训练格式（prompt messages + state_file 相对路径关联）。

## 目标达成

为 Phase 3 的 GRPO 训练准备好格式正确的数据，包含：
- 更新后的 prompt_builder.py，SYSTEM_PROMPT 与 SFT 阶段保持一致
- 新的 generate_grpo_data.py 脚本，实现数据格式转换
- outputs/grpo/grpo_train.jsonl，包含全部 1588 条 GRPO 格式样本

## 任务执行记录

### Task 1: 更新 prompt_builder.py 的 SYSTEM_PROMPT 和 build_prompt 方法
**Status:** ✅ 完成
**Commit:** c490733
**Files:** src/data_generator/prompt_builder.py

**实现细节:**
1. 更新 SYSTEM_PROMPT 常量（第 18-23 行）:
   - 从简单的 "你是交通信号配时优化专家。" 扩展为包含完整格式说明
   - 包含 <think> 和 <CyclePlan> 标签使用说明
   - 强调分析和推理过程
   - 与 SFT 训练脚本 train.py 第 91-96 行和 generate_sft_data.py 第 172 行保持一致

2. 修改 build_prompt() 方法（第 123-127 行）:
   - prompt_parts 列表不再包含 self.SYSTEM_PROMPT
   - 仅返回 user content 部分：prediction JSON + TASK_TEMPLATE
   - SYSTEM_PROMPT 保留为类常量供外部使用

**验证结果:**
- ✅ SYSTEM_PROMPT 包含 '<think>' 标签
- ✅ SYSTEM_PROMPT 包含 '<CyclePlan>' 标签
- ✅ build_prompt() 返回值不包含 system prompt 文本
- ✅ TASK_TEMPLATE 未被修改

### Task 2: 创建 GRPO 数据生成脚本并生成 grpo_train.jsonl
**Status:** ✅ 完成
**Commit:** 77f31dd
**Files:** src/scripts/generate_grpo_data.py, outputs/grpo/grpo_train.jsonl

**实现细节:**

1. **脚本结构** (171 行):
   - 命令行接口：argparse，支持 --input、--output、--config 参数
   - SYSTEM_PROMPT 常量：与 Task 1 更新后的内容完全一致
   - convert_state_file_to_relative(): 路径转换函数
   - convert_to_grpo_format(): 格式转换核心函数
   - generate_grpo_data(): 主处理流程
   - 统计输出：总样本数、场景分布、路径转换结果

2. **数据转换逻辑**:
   - User content 提取：`lines = sample['prompt'].split('\n')` → `user_content = '\n'.join(lines[1:])`
   - State file 路径转换：查找 "outputs/states/" 标记并截取相对路径
   - Messages 组装：`[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': user_content}]`
   - Metadata 组装：`{'state_file': relative_path, **sample['metadata']}`

3. **数据生成结果**:
   - 总样本数: 1588 条
   - 场景分布: arterial4x4_10 (800 条), chengdu (788 条)
   - State file 路径转换: 1588 条全部成功转换为相对路径
   - 输出文件: outputs/grpo/grpo_train.jsonl

**验证结果:**
- ✅ 全部 1588 条样本验证通过
- ✅ 每条样本 prompt 为 list 类型
- ✅ 每条样本 prompt 包含 2 条 messages (system + user)
- ✅ System message 包含 '<think>' 和 '<CyclePlan>' 标签
- ✅ State file 全部为相对路径（不以 '/' 开头）
- ✅ Metadata 包含 state_file、tl_id、sim_time、date、cycle_count
- ✅ 无 answer 字段

## Deviations from Plan

无。计划执行完全按照规范进行，未发现需要自动修复的问题或阻塞性问题。

## 技术实现亮点

1. **数据格式一致性**: SYSTEM_PROMPT 在 prompt_builder.py、generate_grpo_data.py 和 SFT 训练脚本中完全一致，确保训练流程的统一性。

2. **路径可移植性**: State file 从绝对路径（/home/samuel/SCU_TSC/outputs/...）转换为相对路径（outputs/...），提高数据可移植性。

3. **清晰的职责分离**:
   - prompt_builder.py 的 build_prompt() 专注于生成 user content
   - SYSTEM_PROMPT 作为类常量供外部使用
   - generate_grpo_data.py 负责组装完整的 GRPO 格式

4. **完整的统计输出**: 脚本输出详细的统计信息，包括场景分布、路径转换结果，便于数据质量监控。

## Key Decisions Made

1. **SYSTEM_PROMPT 与 SFT 阶段完全一致**
   - 内容："你是交通信号配时优化专家。\n请认真分析预测得到的下个周期各个相位的交通状态，给出下个周期的配时方案，并给出你的推理过程。\n将推理过程放在 <think> 和 </think> 之间。\n然后，将你的最终方案放在 <CyclePlan> 和 </CyclePlan> 之间。"
   - 理由：保证训练一致性，强调"分析"和"推理过程"（而非"学习格式"）

2. **build_prompt() 不再拼入 SYSTEM_PROMPT**
   - 原因：分离 system 和 user content，便于 GRPO 格式组装
   - 影响：外部调用时需要显式使用 SYSTEM_PROMPT 常量构造 system message

3. **State file 转换为相对路径**
   - 转换逻辑：查找 "outputs/states/" 标记并截取
   - 好处：提高数据可移植性，避免硬编码绝对路径
   - 结果：1588 条全部成功转换

4. **GRPO 数据无 answer 字段**
   - 理由：Reward 由 SUMO 仿真实时计算，方案空间大无法预计算
   - 影响：GRPO 训练流程需要实时调用 SUMO 仿真获取 reward

## Output Artifacts

### 创建的文件

1. **src/scripts/generate_grpo_data.py** (171 行)
   - GRPO 数据生成脚本
   - 支持命令行参数：--input、--output、--config
   - 实现路径转换、格式转换、统计输出

2. **outputs/grpo/grpo_train.jsonl** (1588 条)
   - GRPO 训练数据
   - 每条样本格式：`{"prompt": [system_msg, user_msg], "metadata": {...}}`
   - State file 全部为相对路径

### 修改的文件

1. **src/data_generator/prompt_builder.py**
   - SYSTEM_PROMPT 更新为包含 <think> 和 <CyclePlan> 标签说明
   - build_prompt() 不再拼入 SYSTEM_PROMPT

## Next Steps

1. 继续执行 Phase 2 后续计划
2. Phase 3 GRPO 训练时使用 outputs/grpo/grpo_train.jsonl 作为训练数据
3. GRPO 训练脚本需要实现 SUMO 仿真调用以获取 reward

## Self-Check: PASSED

验证已创建的文件:
```bash
# 检查文件存在性
[ -f "src/scripts/generate_grpo_data.py" ] && echo "FOUND: src/scripts/generate_grpo_data.py" || echo "MISSING: src/scripts/generate_grpo_data.py"
# Output: FOUND: src/scripts/generate_grpo_data.py

[ -f "outputs/grpo/grpo_train.jsonl" ] && echo "FOUND: outputs/grpo/grpo_train.jsonl" || echo "MISSING: outputs/grpo/grpo_train.jsonl"
# Output: FOUND: outputs/grpo/grpo_train.jsonl

[ -f "src/data_generator/prompt_builder.py" ] && echo "FOUND: src/data_generator/prompt_builder.py" || echo "MISSING: src/data_generator/prompt_builder.py"
# Output: FOUND: src/data_generator/prompt_builder.py

# 检查提交存在性
git log --oneline --all | grep -q "c490733" && echo "FOUND: c490733" || echo "MISSING: c490733"
# Output: FOUND: c490733

git log --oneline --all | grep -q "77f31dd" && echo "FOUND: 77f31dd" || echo "MISSING: 77f31dd"
# Output: FOUND: 77f31dd

# 数据验证
python3 -c "
import json
count = 0
with open('outputs/grpo/grpo_train.jsonl', 'r') as f:
    for line in f:
        count += 1
assert count == 1588, f'Expected 1588, got {count}'
print(f'Data sample count: {count}')
"
# Output: Data sample count: 1588
```

所有验证项通过。
