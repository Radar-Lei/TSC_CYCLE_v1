---
phase: 07
plan: 01
subsystem: prompt-protocol
tags: [protocol, tags, parser, sft]
requires:
  - reality.log 协议字面值参考（未变）
provides:
  - tsc_cycle.prompt_builder.TAG_THINK_CLOSE = "<end_working_out>"
  - parse_assistant_output 旧标签拒绝分支
  - tokenize_sanity.CUSTOM_TAGS 通过 import 共享 single source of truth
affects:
  - tsc_cycle/eval/metrics_reasoning.py（docstring 一致性）
tech-stack:
  added: []
  patterns:
    - "字面值常量集中在 prompt_builder，下游全部 import（D-08 / T-07-03 反 spoofing）"
key-files:
  created:
    - .planning/phases/07/07-01-SUMMARY.md
  modified:
    - tsc_cycle/prompt_builder.py
    - tsc_cycle/eval/metrics_reasoning.py
    - tsc_cycle/student/tokenize_sanity.py
    - tests/test_prompt_builder.py
decisions:
  - "TAG_THINK_CLOSE 从 </end_working_out> 改为 <end_working_out>，与 reality.log 协议锁定值一致"
  - "parse_assistant_output 在函数体首部增加 OLD_THINK_CLOSE 拒绝分支，旧样本进 lint_ok=False"
  - "tokenize_sanity.CUSTOM_TAGS 改为 import prompt_builder 常量，消除字面值重复"
metrics:
  duration: ~15min
  completed: 2026-05-08
---

# Phase 07 Plan 01: 标签协议全链路迁移 Summary

**One-liner:** 把思考结束标签从 `</end_working_out>` 切换到 `<end_working_out>`，并让 parser 显式拒绝旧标签字面值；下游 tokenize_sanity 改为 import 常量。

## Tasks Executed

| Task | Name | Commit |
|------|------|--------|
| 1 | 扩展 tests 覆盖 D-07 全部场景（RED） | `0158eb0` |
| 2 | 迁移协议常量、parser 拒绝分支、字面值同步（GREEN） | `440ab73` |
| 3 | 全仓 grep 守门 + 全测试 + tokenizer 验证（无文件改动） | — |

## Diff Stats

```
 tests/test_prompt_builder.py         | 52 +++++++++++++++++++++++++++++++++---
 tsc_cycle/eval/metrics_reasoning.py  |  2 +-
 tsc_cycle/prompt_builder.py          | 18 ++++++++-----
 tsc_cycle/student/tokenize_sanity.py | 19 ++++++++-----
 4 files changed, 75 insertions(+), 16 deletions(-)
```

## Verification Outputs

### Task 1 — RED 状态确认

`pytest tests/test_prompt_builder.py -q` 报告 7 个 FAILED：
- `test_user_prompt_contains_required_blocks`（断言新标签存在）
- `test_parse_with_prefill_only`（prefill 用例已切到新字面值）
- `test_constants_match_protocol`
- `test_parse_rejects_old_close_tag`
- `test_parse_old_close_in_prefill_form`
- `test_user_prompt_no_old_close_tag`
- `test_full_assistant_uses_new_close_tag`

证明测试有约束力。

### Task 2 — GREEN

```
$ pytest tests/test_prompt_builder.py -q
............                                                             [100%]
```

12 PASS（7 原有 + 5 新增）。

### Task 3 — Phase Gate

**步骤 1 D-08 grep 守门**

```
$ grep -rn '</end_working_out>' tsc_cycle scripts
tsc_cycle/prompt_builder.py:96:    # 注意：<end_working_out> 不是 </end_working_out> 的子串...
tsc_cycle/prompt_builder.py:97:    OLD_THINK_CLOSE = "</end_working_out>"
```

仅 2 处合法命中，均位于 parse_assistant_output 拒绝分支（一行注释 + 一行常量定义）。✓

`tests/test_prompt_builder.py` 中的旧字面值命中均位于 4 个反例测试函数体内或注释中（已用 `OLD/REJECT/NEGATIVE` 标记）。✓

**步骤 2 全测试套件**

```
$ pytest tests/ -q
.............................                                            [100%]
```

29 PASS，无 regression。

**步骤 3 tokenizer multi-token 验证**

```
'<start_working_out>'  ids=[27, 2468, 81101, 6068, 29]  len=5  multi_token=True
'<end_working_out>'    ids=[27, 408, 81101, 6068, 29]   len=5  multi_token=True
'<SOLUTION>'           ids=[18858, 45977, 29]           len=3  multi_token=True
'</SOLUTION>'          ids=[522, 50, 45977, 29]         len=4  multi_token=True
PASS: new close tag is multi-token; native think ids unchanged
```

新闭标签 `<end_working_out>` 拆成 5 个 sub-token，无 added token 注册；原生 `<think>` (151667) / `</think>` (151668) id 未变（D-05 / D-06 满足）。

## 已审查未改动文件

per RESEARCH File Change Map 与 D-08 范围最小化原则，下列文件经审查无字面值改动需要：

| 文件 | 原因 |
|------|------|
| `tsc_cycle/tokenizer_check.py` | 通过 `from tsc_cycle.prompt_builder import` 自动随动 |
| `tsc_cycle/student/train.py` | 通过常量符号引用，无字面值 |
| `tsc_cycle/student/dataset.py` | docstring 中无 `</end_working_out>` 字面值 |
| `tsc_cycle/eval/metrics_constraints.py` | 通过 `parse_assistant_output` 间接联动；solution=None 即 lint_ok=False，旧样本自动失败 |
| `data/labeled.jsonl` | reasoning 字段无标签字面值；prompt 字段在运行时由 build_user_prompt 重新生成（per RESEARCH 验证） |

## Deviations from Plan

None — 计划严格按 RESEARCH File Change Map 执行。

## Threat Surface Recap

| Threat ID | Status |
|-----------|--------|
| T-07-01 (parser tampering) | mitigated — OLD_THINK_CLOSE 拒绝分支 + 反例测试覆盖 |
| T-07-02 (tokenizer drift) | mitigated — tokenizer_check 输出 multi_token=True，原生 think id 未变 |
| T-07-03 (literal duplication) | mitigated — tokenize_sanity 改为 import 常量；grep 守门 |
| T-07-04 (test laxity) | mitigated — test_constants_match_protocol + 4 个反例测试 |
| T-07-05 (DoS / Elev) | accept — 范围外 |

## Self-Check: PASSED

- 文件存在：
  - `tsc_cycle/prompt_builder.py` ✓
  - `tsc_cycle/eval/metrics_reasoning.py` ✓
  - `tsc_cycle/student/tokenize_sanity.py` ✓
  - `tests/test_prompt_builder.py` ✓
  - `.planning/phases/07/07-01-SUMMARY.md` ✓
- 提交存在：
  - `0158eb0` test(07-01): add failing tests ✓
  - `440ab73` feat(07-01): migrate think-close tag ✓
