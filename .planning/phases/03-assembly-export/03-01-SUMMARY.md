---
phase: 03-assembly-export
plan: 01
subsystem: data-pipeline
tags: [jsonl, sft, assembler, messages-format]

requires:
  - phase: 02-batch-generation
    provides: "outputs/glm5/results.jsonl (GLM-5 生成结果)"
provides:
  - "src/glm5/assembler.py — results.jsonl 到 sft_train.jsonl 的组装脚本"
  - "outputs/sft/sft_train.jsonl — SFT 训练数据 (messages 格式)"
affects: [03-02, 03-03, sft-training]

tech-stack:
  added: []
  patterns: ["BatchGenerator 格式兼容: 支持 sample 嵌套和 status 过滤"]

key-files:
  created:
    - src/glm5/assembler.py
    - tests/test_assembler.py
  modified: []

key-decisions:
  - "assemble_sft_record 同时兼容 BatchGenerator 格式和简化格式，提高鲁棒性"
  - "solution JSON 使用紧凑序列化 (separators=(',',':'))，节省 token 长度"

patterns-established:
  - "双格式兼容: 通过检测 sample 字段区分 BatchGenerator 和简化格式"

requirements-completed: [ASM-01, ASM-02, ASM-03]

duration: 6min
completed: 2026-03-25
---

# Phase 03 Plan 01: SFT Data Assembly Summary

**results.jsonl 到 sft_train.jsonl 的组装脚本，支持 BatchGenerator 双格式兼容和 status 过滤**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-25T09:08:34Z
- **Completed:** 2026-03-25T09:14:33Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- 创建 `src/glm5/assembler.py`，包含 `assemble_sft_record()` 核心函数和 `main()` CLI 入口
- 兼容 BatchGenerator 输出格式（`think_text`, `sample.prompt`, `status` 过滤）和简化格式
- 11 个单元测试全部通过，覆盖正常/异常/格式兼容 case
- 端到端管线验证：合成 10 条数据通过组装和格式校验

## Task Commits

Each task was committed atomically:

1. **Task 1: 创建 SFT 数据组装脚本 (TDD)** - `ca06407` (feat)
2. **Task 1 fix: 适配 BatchGenerator 实际输出格式** - `099736a` (fix)

Task 2 无代码改动（运行组装 + 验证输出，数据文件在 .gitignore 中）。

## Files Created/Modified
- `src/glm5/assembler.py` - GLM-5 结果到 SFT 训练数据的组装脚本，支持双格式输入
- `tests/test_assembler.py` - 组装逻辑 11 个单元测试

## Decisions Made
- assemble_sft_record 同时兼容 BatchGenerator 格式（含 `sample` 嵌套结构和 `status` 字段）和 plan 中定义的简化格式
- solution JSON 使用紧凑序列化 `separators=(',',':')`，减少 token 开销

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan 接口与 BatchGenerator 实际输出格式不匹配**
- **Found during:** Task 1 实现后、Task 2 执行前
- **Issue:** Plan 定义的输入格式 `{prompt, think, solution}` 与 BatchGenerator 实际输出 `{status, think_text, solution, sample: {prompt, ...}}` 不匹配
- **Fix:** assemble_sft_record 通过检测 `sample` 字段自动切换格式，同时新增 `status` 过滤逻辑
- **Files modified:** src/glm5/assembler.py, tests/test_assembler.py
- **Verification:** 11 个测试全部通过
- **Committed in:** 099736a

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** 必要的接口适配修复，保证组装脚本能正确处理 Phase 2 的实际输出。

## Issues Encountered
- `outputs/glm5/results.jsonl` 不存在（Phase 2 GLM-5 API 调用尚未执行），使用合成数据完成端到端验证。真实数据生成后需重新运行组装。

## Known Stubs
None - 所有功能均已完整实现，无占位符代码。

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- assembler.py 已就绪，等待 Phase 2 GLM-5 API 调用产出真实 results.jsonl 后即可组装最终训练数据
- 下游 Plan 03-02 (SFT 训练) 和 03-03 (GGUF 导出) 可在真实数据组装后执行

---
*Phase: 03-assembly-export*
*Completed: 2026-03-25*
