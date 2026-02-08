---
type: quick-task-summary
task_number: 3
title: 修复 GRPO 奖励函数 completions 参数格式不兼容问题
tags: [grpo, bug-fix, trl, reward-function]
completed: 2026-02-08T14:50:26Z
duration: 1.4 min
---

# Quick Task 3: 修复 GRPO 奖励函数 completions 参数格式不兼容问题

**一句话总结:** 修复 data_loader 的 prompt 格式，从预格式化字符串改为 messages 列表，使 TRL 识别为 conversational 模式，同时更新 simulation_reward 支持提取 assistant 消息内容。

## 问题根因

`prepare_grpo_dataset` 在 `data_loader.py` 中将 `prompt` 字段转换为预格式化字符串（通过 `tokenizer.apply_chat_template(..., tokenize=False)`），导致 TRL 的 `is_conversational()` 检测返回 `False`。

在非 conversational 模式下，TRL 将 `completions` 作为 `List[str]` 传递给奖励函数，但 `format_reward.py` 和 `simulation_reward.py` 期望 `List[List[Dict]]` 格式，导致运行时错误：`'str' object has no attribute 'get'`。

## 修复策略

1. **data_loader.py**: 保持 `prompt` 为 messages 格式 `List[Dict]`，不预先调用 `apply_chat_template`，让 TRL 自行处理
2. **simulation_reward.py**: 更新 `compute_simulation_reward` 支持两种格式的 completions，提取 assistant 消息内容

## 执行的任务

### Task 1: 修改 data_loader.py
**文件:** src/grpo/data_loader.py
**修改位置:** prepare_grpo_dataset 函数（lines 136-156）

**变更:**
- 移除了 `tokenizer.apply_chat_template(...)` 调用
- 将 `grpo_item["prompt"]` 从 `formatted_prompt`（字符串）改为 `messages`（List[Dict]）
- 保留 `tokenizer` 参数以维持接口兼容性，尽管不再内部使用

**提交:** 0a92a19

### Task 2: 修改 simulation_reward.py
**文件:** src/grpo/simulation_reward.py
**修改位置:** compute_simulation_reward 函数（lines 139-200）

**变更:**
- 更新类型注解：`completions: List[str]` → `completions: List[Any]`
- 添加内容提取逻辑：
  - 如果 completion 是 list (conversational 模式)：遍历查找 `role="assistant"` 的消息并提取 content
  - 如果 completion 是 str (非 conversational 模式)：直接使用
- 更新文档字符串，说明支持两种模式

**提交:** 0a92a19

### Task 3: 验证 format_reward.py
**验证结果:** format_reward.py 的 `graded_format_reward` 和 `check_phase_validity` 已经使用 `List[List[Dict]]` 签名，无需修改。

## 技术细节

### TRL Conversational 模式检测
TRL 通过检查 dataset 的 `prompt` 字段是否为 `List[Dict]` 来判断是否启用 conversational 模式：
- `prompt` 是 `List[Dict]` → conversational 模式 → completions 为 `List[List[Dict]]`
- `prompt` 是 `str` → 非 conversational 模式 → completions 为 `List[str]`

### 向后兼容
simulation_reward.py 的修改同时支持两种格式，确保在不同模式下都能正常工作。

## 影响分析

### 修改的文件
- src/grpo/data_loader.py
- src/grpo/simulation_reward.py

### 未修改的文件
- src/grpo/format_reward.py (已经是正确的格式)

### 数据流变化
**之前:**
```
prepare_grpo_dataset → prompt: str (formatted)
→ TRL (non-conversational)
→ completions: List[str]
→ reward functions (期望 List[List[Dict]]) ❌
```

**现在:**
```
prepare_grpo_dataset → prompt: List[Dict] (messages)
→ TRL (conversational)
→ completions: List[List[Dict]]
→ reward functions (期望 List[List[Dict]]) ✅
```

## 验证状态

### 代码验证
- [x] data_loader.py 正确构建 messages 格式
- [x] simulation_reward.py 正确提取 assistant 内容
- [x] 类型注解更新为 List[Any]

### 运行时验证
- [ ] 需要运行 GRPO 训练验证修复效果

## 依赖关系

### 影响的组件
- GRPO 训练流程（docker/grpo.sh, src/scripts/train_grpo.py）
- 所有奖励函数（simulation_reward.py, format_reward.py）

### 上游依赖
- Phase 2 数据生成输出格式（未变化）

### 下游影响
- GRPO 训练现在应该能够正确传递 completions 给奖励函数

## 自检结果

### 文件存在性检查
```bash
[x] src/grpo/data_loader.py 存在且已修改
[x] src/grpo/simulation_reward.py 存在且已修改
```

### 提交验证
```bash
[x] 提交 0a92a19 存在
[x] 仅包含两个文件的修改
```

## Self-Check: PASSED

所有文件和提交都已验证存在。
