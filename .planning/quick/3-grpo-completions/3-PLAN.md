# Quick Task 3: 修复 GRPO 奖励函数 completions 参数格式不兼容问题

## 问题分析

### 根因
`data_loader.py` 的 `prepare_grpo_dataset` 把 `prompt` 字段设为已格式化的字符串（调用 `tokenizer.apply_chat_template(..., tokenize=False)`），TRL 的 `is_conversational()` 检测到 `prompt` 是字符串而非 `List[Dict]`，判定为非 conversational 模式。

非 conversational 模式下，TRL 把 `completions` 作为 `List[str]` 传给奖励函数，但 `format_reward.py` 的函数期望 `List[List[Dict]]`，导致 `msg.get("role")` 报错 `'str' object has no attribute 'get'`。

### 修复策略
修改 `prepare_grpo_dataset` 让 `prompt` 保持 messages 格式 `List[Dict]`（不预先 apply chat_template），让 TRL 自行处理模板。同时更新所有奖励函数适配 conversational 格式（`completions` 变为 `List[List[Dict]]`），即保持现有的 `List[List[Dict]]` 签名不变。

`simulation_reward.py` 的 `compute_simulation_reward` 当前签名是 `completions: List[str]`，需要修改为从 `List[List[Dict]]` 中提取 content。

## 任务

### Task 1: 修改 data_loader.py — prompt 改为 messages 格式
- `prepare_grpo_dataset` 中把 `prompt` 改为 `[{role: "system", content: ...}, {role: "user", content: ...}]`
- 移除 `tokenizer.apply_chat_template(...)` 调用
- 参数 `tokenizer` 不再需要，但保留以维持接口兼容

### Task 2: 修改 simulation_reward.py — 适配 conversational completions
- `compute_simulation_reward` 的 `completions` 参数从 `List[str]` 改为 `List[List[Dict]]`
- 提取 assistant 消息的 content 后再解析

### Task 3: 验证 format_reward.py 无需修改
- `graded_format_reward` 和 `check_phase_validity` 已经是 `List[List[Dict]]` 签名
- 确认无需修改
