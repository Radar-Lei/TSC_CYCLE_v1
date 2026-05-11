---
phase: 12-home-samuel-tsc-cycle-reality-log-reality-test-log
plan: "01"
subsystem: testing
tags: [pytest, red-contracts, reality-log, gguf, phase12]
requires:
  - phase: 11-eval-matrix-decision
    provides: Phase 11 GO 推荐的 v4 q4_K_M GGUF 部署产物
provides:
  - Phase 12 reality.log 重放的 RED 契约测试
  - 输入只来自 framed prompt JSON 的防污染合同
  - v4 q4_K_M 默认产物选择、协议、报告、路径安全、原子写入合同
affects: [phase12-reality-test, phase12-report, reality_test.log]
tech-stack:
  added: []
  patterns: [lazy-import pytest contracts, fail-closed report gates, atomic final-write contract]
key-files:
  created:
    - tests/test_phase12_reality_log_generation.py
  modified: []
key-decisions:
  - "Phase 12 RED 契约通过 lazy import 指向 tsc_cycle.v4_gates.phase12_reality_test 与 phase12_report，避免测试收集阶段加载 GPU/模型栈。"
  - "默认模型产物锁定 Phase 11 推荐的 v4 q4_K_M GGUF，显式排除冻结 v1 baseline。"
  - "最终 reality_test.log 只有 parse、协议、lint、报告 gate 全部通过后才能原子写入。"
patterns-established:
  - "reality.log 只能解析 type=prompt 块中的 【cycle_predict_input_json】 framed JSON。"
  - "RAW 必须保留完整 <start_working_out>...</end_working_out><SOLUTION>...</SOLUTION> 协议，禁止 native <think> 与 malformed <end_working_out>。"
requirements-completed: [PHASE12-GOAL]
duration: 2min
completed: 2026-05-11
---

# Phase 12 Plan 01: Reality Log Generation RED Contracts Summary

**Phase 12 的 reality.log 输入重放、v4 q4_K_M 产物选择、协议解析、fail-closed 报告与原子写入行为已用 RED pytest 合同锁定。**

## Performance

- **Duration:** 2min
- **Started:** 2026-05-11T12:05:48Z
- **Completed:** 2026-05-11T12:07:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- 新增 `tests/test_phase12_reality_log_generation.py`，覆盖 Phase 12 parser、artifact selection、protocol、path-safety、report、atomic-write RED 合同。
- 测试显式证明 only framed prompt JSON 是输入事实来源，旧 `type=result`、`RAW:`、`REASONING:`、`PARSED:` 不能污染新输出。
- 测试锁定默认模型为 `/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf`，并排除冻结 v1 baseline。
- 测试要求报告 payload 具备 `ok`、`next_phase_allowed`、计数、模型路径、输入/输出 hash 等审计字段，且 parse/lint/protocol 失败时 fail closed。

## Task Commits

Each task was committed atomically:

1. **Task 1: Write RED parser and artifact-selection contracts** - `9e78eab` (test)
2. **Task 2: Write RED protocol, report, and atomic-write contracts** - `9e78eab` (test)

**Plan metadata:** pending final docs commit

_Note: 两个 TDD RED 任务扩展同一个合同测试文件，因此按计划合并到同一个 test commit 中提交。_

## Files Created/Modified

- `tests/test_phase12_reality_log_generation.py` - Phase 12 RED 合同测试，覆盖输入提取、产物选择、协议渲染、路径安全、报告 gate、原子写入与 parser 默认参数。

## Decisions Made

- 使用 lazy import 指向 `tsc_cycle.v4_gates.phase12_reality_test` 与 `tsc_cycle.v4_gates.phase12_report`，确保 pytest collection 不加载 torch/transformers/peft/bitsandbytes/vllm/flash_attn。
- 将 Phase 11 GO 推荐的 v4 q4_K_M artifact 作为唯一默认部署产物，并通过测试明确不选择 v1 frozen artifact。
- 将最终文件写入定义为 fail-closed：任一样本 parse、lint、reasoning/protocol 或 hash 证据失败，最终 `reality_test.log` 不应出现。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] 修正 RED 合同自检的字符串误报**
- **Found during:** Task 1/2 RED verification
- **Issue:** 自检直接搜索 `"tsc_cycle.student"`，会匹配测试自身的断言字符串，导致 RED 失败原因混入非目标 AssertionError。
- **Fix:** 改为拼接 `"tsc_cycle." + "student"` 后再断言，使 RED 失败面集中在缺失的 Phase 12 implementation modules。
- **Files modified:** `tests/test_phase12_reality_log_generation.py`
- **Verification:** `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_phase12_reality_log_generation.py -q` 非零退出，grep 命中 `ModuleNotFoundError` for `phase12_reality_test` / `phase12_report`。
- **Committed in:** `9e78eab`

---

**Total deviations:** 1 auto-fixed (Rule 1 bug)
**Impact on plan:** 修复仅确保 RED 证据指向计划中的缺失实现合同，没有改变 Phase 12 合同范围。

## Issues Encountered

- RED 验证按预期失败，因为 `tsc_cycle.v4_gates.phase12_reality_test` 与 `tsc_cycle.v4_gates.phase12_report` 尚未由后续计划实现。
- `state.record-metric` 与 `state.add-decision` SDK 调用在当前 CLI 参数形式下返回参数错误；已通过其他可用 SDK 命令更新 plan position/progress/session，后续 orchestrator 可重算最终状态。
- `requirements.mark-complete PHASE12-GOAL` 未在 REQUIREMENTS.md 找到对应 ID；SUMMARY 仍按 PLAN frontmatter 记录该 requirement。

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - 本计划只新增 RED 合同测试，没有引入会阻断目标的生产 stub。

## Next Phase Readiness

- Plan 12-02 可以实现 `tsc_cycle.v4_gates.phase12_reality_test`，使 parser、默认模型选择、路径安全、渲染和原子写入合同转绿。
- Plan 12-03 可以实现 `tsc_cycle.v4_gates.phase12_report` 与最终 artifact gate，使 426 条 `reality.log` 输入生成 `reality_test.log` 前具备完整审计证据。

## TDD Gate Compliance

- RED gate commit exists: `9e78eab` (`test(12-01): add Phase 12 RED contracts`)
- GREEN gate commit intentionally absent: Plan 12-01 is RED-only by design; production modules are reserved for later Phase 12 plans.

## Self-Check: PASSED

- `tests/test_phase12_reality_log_generation.py` exists and was committed in `9e78eab`.
- `12-01-SUMMARY.md` created at `/home/samuel/TSC_CYCLE/.planning/phases/12-home-samuel-tsc-cycle-reality-log-reality-test-log/12-01-SUMMARY.md`.
- RED verification fails for missing `phase12_reality_test` / `phase12_report` contracts, not syntax errors.

---
*Phase: 12-home-samuel-tsc-cycle-reality-log-reality-test-log*
*Completed: 2026-05-11*
