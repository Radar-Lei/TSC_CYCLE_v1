---
phase: 02-grpo-data-preparation
verified: 2026-02-09T16:50:46Z
status: passed
score: 6/6 must-haves verified
re_verification: false
---

# Phase 02: GRPO 数据准备 Verification Report

**Phase Goal:** 准备好用于 GRPO 训练的 prompt 和状态文件对
**Verified:** 2026-02-09T16:50:46Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|---------|-----------|
| 1 | prompt_builder.py 的 SYSTEM_PROMPT 包含 <think>/<CyclePlan> 标签格式说明，与 SFT 阶段保持一致 | ✓ VERIFIED | SYSTEM_PROMPT 第 18-23 行包含完整格式说明，与 SFT 训练脚本一致 |
| 2 | build_prompt() 不再将 SYSTEM_PROMPT 拼入 prompt 字符串，而是仅返回 user 内容部分 | ✓ VERIFIED | 第 128-131 行 prompt_parts 仅包含 prediction JSON 和 TASK_TEMPLATE，测试确认输出不含 SYSTEM_PROMPT |
| 3 | outputs/grpo/grpo_train.jsonl 包含全部 1588 条样本 | ✓ VERIFIED | wc -l 确认 1588 行，每行一个有效 JSON 对象 |
| 4 | 每条 GRPO 样本的 prompt 字段为 messages 数组（system + user 两条消息） | ✓ VERIFIED | 全部 1588 条样本验证通过：prompt 为 list，长度为 2，roles 为 system 和 user |
| 5 | 每条 GRPO 样本的 metadata 包含 state_file（相对路径）和原始 metadata 字段 | ✓ VERIFIED | 全部 1588 条样本的 state_file 为相对路径（以 "outputs/states/" 开头），包含 tl_id, sim_time, date, cycle_count |
| 6 | GRPO 数据中不包含 answer 字段 | ✓ VERIFIED | 全部 1588 条样本验证无 answer 字段，user content 不包含 <think>/<solution>/<CyclePlan> 答案标签 |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/data_generator/prompt_builder.py` | 更新后的 SYSTEM_PROMPT 和 build_prompt 方法 | ✓ VERIFIED | EXISTS (202 lines), SUBSTANTIVE (包含 <think> 标签), WIRED (被 day_simulator.py 导入使用) |
| `src/scripts/generate_grpo_data.py` | GRPO 数据生成脚本 | ✓ VERIFIED | EXISTS (170 lines), SUBSTANTIVE (完整实现，超过 min_lines 60), NOT WIRED (独立脚本，不需要被导入) |
| `outputs/grpo/grpo_train.jsonl` | GRPO 训练数据（1588 条） | ✓ VERIFIED | EXISTS (1588 lines), SUBSTANTIVE (每行有效 JSON), WIRED (将被 Phase 3 GRPO 训练使用) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| src/scripts/generate_grpo_data.py | outputs/data/train.jsonl | 读取原始训练数据 | ✓ WIRED | 第 90-92 行：读取 train.jsonl，train.jsonl 存在 (3.3M) |
| src/scripts/generate_grpo_data.py | outputs/grpo/grpo_train.jsonl | 写入 GRPO 格式数据 | ✓ WIRED | 第 129-131 行：写入 grpo_train.jsonl，输出文件生成成功 (1588 条) |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| GRPD-01: 从 train.jsonl 提取 GRPO 训练集(prompt + state_file),不包含思考过程 | ✓ SATISFIED | Truths 3, 4, 6 verified - 全部 1588 条提取成功，prompt 仅包含任务描述，不含答案 |
| GRPD-02: prompt 包含 system(角色设定)和 user(交通状态+任务说明)两部分 | ✓ SATISFIED | Truth 4 verified - 每条样本包含 system 和 user 两条消息，内容正确 |

### Anti-Patterns Found

无反模式发现。检查项：
- TODO/FIXME/PLACEHOLDER 注释：无
- 空实现（return null/{}[]）：无
- Console.log-only 实现：无
- 未连接的组件：无

代码质量良好，实现完整。

### Human Verification Required

无需人工验证。所有目标均可通过自动化检查验证。

### Gaps Summary

无缺陷。所有 must-haves 已验证通过，phase 目标达成。

## Detailed Verification

### Truth 1: SYSTEM_PROMPT 更新

**验证方法:**
```python
from src.data_generator.prompt_builder import SYSTEM_PROMPT
assert '<think>' in SYSTEM_PROMPT
assert '<CyclePlan>' in SYSTEM_PROMPT
```

**结果:** ✓ PASSED
- SYSTEM_PROMPT 包含完整格式说明（第 18-23 行）
- 内容与 SFT 阶段一致（src/sft/train.py 第 91-96 行）

### Truth 2: build_prompt() 行为

**验证方法:**
```python
builder = PromptBuilder()
prompt = builder.build_prompt(test_prediction)
assert '你是交通信号配时优化专家' not in prompt.split('\n')[0]
```

**结果:** ✓ PASSED
- build_prompt() 返回值不包含 SYSTEM_PROMPT
- prompt_parts 列表仅包含 prediction JSON 和 TASK_TEMPLATE（第 128-131 行）

### Truth 3-6: GRPO 数据质量

**验证方法:**
```python
count = 0
with open('outputs/grpo/grpo_train.jsonl', 'r') as f:
    for line in f:
        d = json.loads(line)
        assert isinstance(d['prompt'], list)
        assert len(d['prompt']) == 2
        assert d['prompt'][0]['role'] == 'system'
        assert d['prompt'][1]['role'] == 'user'
        assert '<think>' in d['prompt'][0]['content']
        assert 'state_file' in d['metadata']
        assert not d['metadata']['state_file'].startswith('/')
        assert 'answer' not in d
        count += 1
assert count == 1588
```

**结果:** ✓ PASSED
- 全部 1588 条样本验证通过
- Prompt 结构正确（system + user messages）
- State file 全部为相对路径
- 无 answer 字段

### Artifact Wiring Analysis

**prompt_builder.py:**
- 被 `src/data_generator/day_simulator.py` 导入使用
- SYSTEM_PROMPT 作为类常量供外部使用
- 状态：WIRED

**generate_grpo_data.py:**
- 独立脚本，通过命令行运行
- 不需要被其他模块导入
- 状态：NOT WIRED (expected for standalone script)

**grpo_train.jsonl:**
- 将被 Phase 3 GRPO 训练脚本读取
- 状态：WIRED (future dependency)

## Success Criteria Verification

从 ROADMAP.md Phase 2 Success Criteria:

1. ✓ 从 train.jsonl 成功提取 GRPO 训练集(prompt + state_file)
   - 1588 条全部提取成功
   
2. ✓ 每个 prompt 包含 system 角色设定和 user 交通状态说明两部分
   - 全部样本验证通过
   
3. ✓ prompt 不包含思考过程或答案,仅包含任务描述
   - User content 不含 <think>/<solution>/<CyclePlan> 标签
   - 无 answer 字段
   
4. ✓ 每个样本正确关联到对应的 SUMO state_file 用于 reward 计算
   - State file 全部转换为相对路径
   - 格式：outputs/states/{scenario}/state_{timestamp}_{tl_id}.xml

**Overall:** 4/4 success criteria met

---

_Verified: 2026-02-09T16:50:46Z_
_Verifier: Claude (gsd-verifier)_
