---
phase: 01-sft-data-and-training
plan: 02
subsystem: sft-data-generation
tags: [sft, data-assembly, ai-generation, validation]
dependency_graph:
  requires: [01-01-sample-selection]
  provides: [sft-training-dataset]
  affects: [01-03-sft-training]
tech_stack:
  added: []
  patterns: [ai-generated-think, dual-validation, saturation-based-allocation]
key_files:
  created:
    - outputs/sft/think_workspace.jsonl
    - outputs/sft/sft_train.jsonl
  modified:
    - src/scripts/generate_sft_data.py
decisions:
  - think 内容由 AI 直接手工生成，非程序化模板生成
  - 使用 <think><solution> 标签格式（重复开标签作为关闭标签）
  - solution 值基于 saturation 线性映射到 [min_green, max_green] 范围
  - 双重校验确保约束满足和 think 非空
metrics:
  duration: 497s
  tasks_completed: 2
  files_created: 3
  lines_added: 422
  completed_date: 2026-02-09T12:36:00Z
---

# Phase 01 Plan 02: SFT 数据组装与 AI 内容生成 Summary

**一句话:** AI 逐条手工撰写 100 条中文 think 内容，组装为包含 <think><solution> 格式的完整 SFT 训练数据集，所有约束校验通过。

## 完成的工作

### Task 1: 创建 SFT 数据组装与校验脚本
- 创建 `src/scripts/generate_sft_data.py` 脚本（222 行）
- 实现 `prepare` 子命令：基于 saturation 线性映射生成 solution 值
- 实现 `assemble` 子命令：组装 JSONL 格式 + 双重校验
- 生成 `think_workspace.jsonl`（100 条数据框架）
- 所有 solution 值满足硬约束 `min_green <= final <= max_green`

**关键逻辑:**
```python
# Solution 生成：saturation 越高分配越接近 max_green
ratio = sat / max_sat
final = min_green + ratio * (max_green - min_green)
final = max(min_green, min(max_green, int(round(final))))
```

**提交:** `30409b3` - feat(01-02): create SFT data assembly and validation script

### Task 2: AI 逐条生成 think 内容并组装最终数据
- AI 手工撰写 100 条 think 内容（每条 50-200 token，平均 79 字符）
- Think 风格：简洁分析型，中文，定性分析饱和度大小关系
- 示例: "phase 0 的 saturation 为 1.2551，超过容量需求，应分配最大绿灯 119s。phase 2 的 saturation 为 0.6548，相对较低，可按比例分配绿灯时间。优先满足高饱和度相位需求。"
- 运行 `assemble` 子命令组装最终 SFT 数据
- 输出 `sft_train.jsonl`（100 条，每条包含 3 个 messages）

**验证结果:**
- 总条数: 100
- Think 平均长度: 79 字符
- 约束违反数: 0 ✓
- 空 Think 数: 0 ✓
- 格式校验: 全部通过 ✓

**提交:** `a918ed4` - feat(01-02): generate SFT training data with AI-written think content

## 输出文件

### outputs/sft/sft_train.jsonl (204KB, 100 条)
最终 SFT 训练数据，格式:
```json
{
  "messages": [
    {"role": "system", "content": "你是交通信号配时优化专家。"},
    {"role": "user", "content": "【cycle_predict_input_json】..."},
    {"role": "assistant", "content": "<think>...<think><solution>[...]<solution>"}
  ]
}
```

### outputs/sft/think_workspace.jsonl (56KB, 100 条)
中间工作区文件，包含 phase_waits、solution、think 字段，供后续分析使用。

## Deviations from Plan

无偏差 - 计划执行完全按预期进行。

## 验证

执行计划中的验证脚本:
```bash
python3 -c "
import json, re
pattern = re.compile(r'<think>.+<think><solution>\[.+\]<solution>', re.DOTALL)
with open('outputs/sft/sft_train.jsonl') as f:
    for i, line in enumerate(f):
        d = json.loads(line)
        assert len(d['messages']) == 3
        assert d['messages'][0]['role'] == 'system'
        assert d['messages'][1]['role'] == 'user'
        assert d['messages'][2]['role'] == 'assistant'
        assert pattern.search(d['messages'][2]['content'])
print('All checks passed')
"
```

结果: **All checks passed** ✓

## Self-Check

检查关键文件是否存在:
```bash
[PASSED] outputs/sft/sft_train.jsonl exists (204488 bytes)
[PASSED] outputs/sft/think_workspace.jsonl exists (56117 bytes)
[PASSED] src/scripts/generate_sft_data.py exists (222 lines)
```

检查提交是否存在:
```bash
[PASSED] Commit 30409b3 exists (Task 1)
[PASSED] Commit a918ed4 exists (Task 2)
```

## Self-Check: PASSED

所有文件和提交均已验证存在。

## 下一步

继续执行 Phase 1 Plan 03: SFT 模型训练。
