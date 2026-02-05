---
phase: 05-docker-部署环境
plan: 02
subsystem: infra
tags: [bash, shell, logging, checkpoint, docker]

# Dependency graph
requires:
  - phase: 05-01
    provides: config.json 配置文件和验证脚本
provides:
  - Shell 函数库:检查点管理、日志记录、阶段摘要
  - 原子检查点写入机制(mktemp + mv)
  - 按阶段分离的日志系统(tee + PIPESTATUS)
  - 三阶段(data/sft/grpo)统计摘要
affects: [05-03-refactor-publish]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "原子文件写入: mktemp + mv 防止部分写入"
    - "日志双路输出: tee -a 同时写控制台和文件"
    - "退出码保留: PIPESTATUS[0] 获取管道前命令退出码"
    - "阶段检查点: 状态文件 + 输出文件双重验证"

key-files:
  created:
    - docker/lib/checkpoint.sh
    - docker/lib/logging.sh
    - docker/lib/summary.sh
  modified: []

key-decisions:
  - "检查点验证采用双重检查:状态文件 + 输出文件存在性"
  - "日志按阶段分离到独立文件,便于调试和分析"
  - "使用 PIPESTATUS[0] 而非 $? 保留管道中命令的真实退出码"

patterns-established:
  - "原子检查点写入: mktemp 临时文件 + mv 原子替换"
  - "阶段日志分离: logs/${DATE}-${stage_name}.log 命名模式"
  - "统计信息动态计算: 从日志和输出文件实时提取,不依赖检查点缓存"

# Metrics
duration: 5min
completed: 2026-02-05
---

# Phase 05 Plan 02: Shell 函数库 Summary

**提供检查点管理、日志记录和阶段摘要的 Shell 函数库,使用原子写入和双路输出模式**

## Performance

- **Duration:** 5分15秒
- **Started:** 2026-02-05T18:47:44+08:00
- **Completed:** 2026-02-05T18:52:59+08:00
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- 创建检查点管理函数库,使用 mktemp + mv 实现原子写入
- 创建日志管理函数库,使用 tee + PIPESTATUS 实现双路输出和退出码保留
- 创建阶段摘要函数库,支持 data/sft/grpo 三个阶段的专门统计

## Task Commits

每个任务都被原子提交:

1. **Task 1: 创建检查点管理函数库** - `704855b` (feat)
2. **Task 2: 创建日志管理函数库** - `fbadea1` (feat)
3. **Task 3: 创建阶段摘要函数库** - `3502f3a` (feat)

## Files Created/Modified

- `docker/lib/checkpoint.sh` - 检查点管理函数(write/read/check/clear)
- `docker/lib/logging.sh` - 日志管理函数(init/run_with_logging/log_info/log_error/log_stage_start/log_stage_end)
- `docker/lib/summary.sh` - 阶段摘要函数(show_stage_summary/show_final_summary/format_duration)

## Decisions Made

1. **检查点双重验证策略**:
   - 不仅检查 `.checkpoints/${stage}.checkpoint` 状态文件
   - 还验证实际输出文件存在(data: *.jsonl 非空,sft: adapter_model.safetensors,grpo: final/ 目录)
   - 理由: 防止检查点文件与实际输出不一致导致的误判

2. **日志按阶段分离**:
   - 使用 `logs/${DATE}-${stage_name}.log` 命名模式
   - 理由: 便于调试单个阶段,日志文件更小,支持并行分析

3. **使用 PIPESTATUS[0] 而非 $?**:
   - 在 `run_with_logging` 中使用 `${PIPESTATUS[0]}` 获取管道前命令退出码
   - 理由: tee 总是返回 0,必须从 PIPESTATUS 数组获取真实命令的退出码

4. **统计信息动态计算**:
   - 阶段摘要从日志文件和输出目录实时计算统计信息
   - 不在检查点文件中缓存统计数据
   - 理由: 避免检查点与实际输出不同步,保证统计准确性

## Deviations from Plan

None - 计划执行完全符合规范。

## Issues Encountered

None - 所有函数按预期实现,语法验证和功能测试全部通过。

## User Setup Required

None - 无需外部服务配置。

## Next Phase Readiness

**已就绪:**
- Shell 函数库可以被 `publish.sh` source 引入
- 所有函数通过语法检查和类型验证
- 检查点、日志、摘要三大功能完整实现

**准备下一阶段(05-03):**
- 重构 `docker/publish.sh` 使用这些函数库
- 实现智能恢复、日志持久化和阶段摘要

**技术细节:**
- `checkpoint.sh`: 提供 4 个函数 (write/read/check/clear)
- `logging.sh`: 提供 6 个函数 (init/run_with_logging/log_info/log_error/log_stage_start/log_stage_end)
- `summary.sh`: 提供 3 个主函数 + 3 个内部函数 (show_stage_summary/show_final_summary/format_duration)

**关键模式:**
- **原子写入**: `mktemp` 创建临时文件 → 写入内容 → `mv` 原子替换
- **双路输出**: `command | tee -a log.txt` + `PIPESTATUS[0]` 保留退出码
- **阶段验证**: 检查点状态 + 输出文件存在性双重检查

---
*Phase: 05-docker-部署环境*
*Completed: 2026-02-05*
