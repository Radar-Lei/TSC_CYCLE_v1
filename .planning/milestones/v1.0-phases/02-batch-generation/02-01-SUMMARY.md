---
phase: 02-batch-generation
plan: 01
subsystem: data-generation
tags: [glm5, prompt, validator, parsing, constraints]

requires:
  - phase: 01-api
    provides: GLM5Client, GLM5Response, sampler
provides:
  - build_glm5_prompts: 构建 GLM-5 system/user prompt 对
  - parse_glm5_output: 从 GLM-5 输出解析 think 链和 solution
  - validate_constraints: 相位顺序/绿灯范围/整数约束校验
  - ParsedOutput: 解析结果 dataclass
affects: [02-02-batch-generator]

tech-stack:
  added: []
  patterns: [tag-based-parsing, constraint-validation]

key-files:
  created:
    - src/glm5/prompt.py
    - src/glm5/validator.py
    - tests/test_glm5_prompt.py
    - tests/test_glm5_validator.py
  modified: []

key-decisions:
  - "GLM5_SYSTEM_PROMPT 基于原始 SYSTEM_PROMPT 追加 ~500 token think 链长度引导"
  - "validate_constraints 采用严格模式: 遇到第一个违反立即返回错误"

patterns-established:
  - "GLM-5 模块复用现有 PromptBuilder 和 models，不重复实现"
  - "约束校验返回 (bool, str) 元组，错误信息为中文"

requirements-completed: [GEN-01, GEN-02, GEN-03, GEN-04]

duration: 4min
completed: 2026-03-25
---

# Phase 02 Plan 01: Prompt & Validator Summary

**GLM-5 prompt 构建器复用 PromptBuilder 并追加 ~500 token think 链引导，输出解析器提取标签内容并校验相位顺序/绿灯范围/整数约束**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-25T08:46:31Z
- **Completed:** 2026-03-25T08:50:50Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- build_glm5_prompts 返回 (system_prompt, user_prompt) 元组，system_prompt 含 ~500 token think 链长度引导
- parse_glm5_output 支持带/不带 <start_working_out> 两种格式，提取 think 链和 solution JSON
- validate_constraints 检测相位顺序/绿灯范围/整数类型三种约束违反，返回中文错误信息
- 17 个单元测试全部通过

## Task Commits

Each task was committed atomically:

1. **Task 1: 创建 GLM-5 prompt 构建模块** - `9bff0af` (test) + `f632f6c` (feat)
2. **Task 2: 创建 GLM-5 输出解析和约束校验模块** - `6a6d662` (test) + `0690c93` (feat)

_Note: TDD tasks have two commits each (test + feat)_

## Files Created/Modified
- `src/glm5/prompt.py` - GLM-5 prompt 构建，复用 PromptBuilder + think 链长度引导
- `src/glm5/validator.py` - 输出解析 (ParsedOutput) 和约束校验 (validate_constraints)
- `tests/test_glm5_prompt.py` - prompt 构建 6 个单测
- `tests/test_glm5_validator.py` - 解析和校验 11 个单测

## Decisions Made
- GLM5_SYSTEM_PROMPT 在原始 SYSTEM_PROMPT 后追加 think 链长度引导文本，不修改原始常量
- validate_constraints 采用 fail-fast 模式，遇到第一个约束违反立即返回

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- prompt.py 和 validator.py 提供 Plan 02 批量生成器所需的全部接口
- build_glm5_prompts 可直接传入 GLM5Client.call_single
- parse_glm5_output + validate_constraints 组合用于输出校验和丢弃重试

---
*Phase: 02-batch-generation*
*Completed: 2026-03-25*
