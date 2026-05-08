---
status: findings_found
phase: 07-标签协议全链路迁移
date: 2026-05-08
depth: standard
critical: 0
warning: 3
info: 2
---

# Phase 07 代码审查报告

## Summary

无 blocker。3 条 warning 围绕 parser 拒绝分支边界覆盖与反例测试断言强度；2 条 info 为非阻塞改进建议。

## Warnings

### WR-01: 同时含新旧标签时被静默接受
- **File:** `tsc_cycle/prompt_builder.py` (parse_assistant_output)
- **Issue:** 拒绝条件 `if OLD in text and NEW not in text` 在 text 同时含新旧两个闭标签时不命中，违反 D-02/D-03 "旧标签即反例" 语义。
- **Fix:** 收紧为 `if LEGACY_THINK_CLOSE in text: return "", None`，并补 "both present" 反例测试。

### WR-02: 反例 prefill 测试断言强度不足
- **File:** `tests/test_prompt_builder.py::test_parse_old_close_in_prefill_form`
- **Issue:** 仅断言 `s is None`，未约束 `r == ""`，TAG-02 回归保护不足。
- **Fix:** 增加 `assert r == ""`。

### WR-03: OLD_THINK_CLOSE 局部字面值违反 SSOT 主张
- **File:** `tsc_cycle/prompt_builder.py:97`
- **Issue:** 函数内局部 `OLD_THINK_CLOSE = "..."` 应提升为模块级常量 `LEGACY_THINK_CLOSE`，并在 docstring 标注用途为反例。
- **Fix:** 提升为 module-level，命名为 `LEGACY_THINK_CLOSE`。

## Info

### IN-01: grep 守门未制度化
- 当前 `</end_working_out>` 守门是手动 phase gate；建议未来加 pre-commit hook。非阻塞。

### IN-02: metrics_reasoning.py 仅改 docstring
- 实现未审。非阻塞，建议未来加回归测试。

## REVIEW COMPLETE
