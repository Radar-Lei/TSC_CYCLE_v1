---
phase: 02-batch-generation
plan: 02
subsystem: data-generation
tags: [glm5, batch, concurrent, resume, jsonl]

# Dependency graph
requires:
  - phase: 01-api
    provides: GLM5Client (call_single, call_batch, shutdown)
  - phase: 02-batch-generation/01
    provides: build_glm5_prompts, parse_glm5_output, validate_constraints
provides:
  - BatchGenerator 批量生成编排器 (断点续传 + 约束重试 + 实时进度)
  - CLI 入口 run_generate.py (--input/--output/--max-retries)
affects: [03-training, 02-batch-generation]

# Tech tracking
tech-stack:
  added: []
  patterns: [thread-safe-append-write, checkpoint-resume-via-jsonl-scan]

key-files:
  created:
    - src/glm5/generator.py
    - src/glm5/run_generate.py
  modified:
    - src/glm5/__init__.py

key-decisions:
  - "ThreadPoolExecutor 使用 client.max_concurrent 作为 worker 数，与 API 并发一致"
  - "线程安全写入使用 threading.Lock + flush，保证崩溃后文件完整"

patterns-established:
  - "Checkpoint resume: 启动时扫描 output jsonl 恢复已完成 ID 集合"
  - "Per-sample retry: 约束违反最多重试 3 次，全部失败记录 constraint_failed 并跳过"

requirements-completed: [GEN-05, GEN-06, PROG-01, PROG-02, PROG-03]

# Metrics
duration: 3min
completed: 2026-03-25
---

# Phase 02 Plan 02: Batch Generator Summary

**BatchGenerator 编排器: ThreadPoolExecutor 并发调用 GLM-5，含断点续传、约束校验重试(3次)、逐条追加写入和实时进度显示**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-25T08:53:58Z
- **Completed:** 2026-03-25T08:57:29Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- BatchGenerator 实现完整批量生成流程: 断点续传 + 约束校验重试 + 失败跳过记录 + 实时进度 + 逐条追加写入
- CLI 入口 run_generate.py 支持 --input/--output/--max-retries 参数
- __init__.py 导出 BatchGenerator

## Task Commits

Each task was committed atomically:

1. **Task 1: 实现批量生成编排器 BatchGenerator** - `3eaa0d1` (feat)
2. **Task 2: 创建 CLI 入口并更新模块导出** - `8301133` (feat)

## Files Created/Modified
- `src/glm5/generator.py` - BatchGenerator 类: 断点续传、约束重试、并发处理、实时进度、逐条写入
- `src/glm5/run_generate.py` - CLI 入口: argparse 参数解析、GLM5Client 创建、生成流程启动
- `src/glm5/__init__.py` - 更新 __all__ 导出 BatchGenerator

## Decisions Made
- ThreadPoolExecutor 使用 client.max_concurrent (默认 4) 作为 max_workers，与 API 并发限制一致
- 线程安全写入使用 threading.Lock + file flush，保证中断后文件完整可恢复
- _sample_id 使用 "tl_id:as_of" 格式作为唯一标识，与输出 results.jsonl 的 id 字段一致

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- BatchGenerator 就绪，用户可通过 `python -m src.glm5.run_generate` 启动批量生成
- 需要 GLM_API_KEY 环境变量和 outputs/glm5/sampled_5000.jsonl 输入文件
- 下一步: Phase 3 训练验证或后续数据组装

---
*Phase: 02-batch-generation*
*Completed: 2026-03-25*
