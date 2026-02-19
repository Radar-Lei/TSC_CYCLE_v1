---
phase: quick-1-sft-test-sh-gguf
plan: 1
subsystem: docker
tags: [bash, testing, gguf, inference]
requires: []
provides: [sft_test.sh --gguf 选项]
affects: [docker/sft_test.sh]
tech-stack:
  added: [bash parameter parsing]
  patterns: [flag-based mode switching]
key-files:
  created: []
  modified:
    - docker/sft_test.sh
decisions: []
metrics:
  duration: 2 minutes
  completed_date: 2026-02-19
  tasks_completed: 1
  files_modified: 1
---

# Quick Task 1: SFT Test Script GGUF Option

## Summary

为 `docker/sft_test.sh` 脚本添加 `--gguf` 选项，允许用户选择使用 GGUF 量化模型进行推理测试，无需大量 GPU 显存。

## One-liner

添加 `--gguf` 参数到 sft_test.sh，支持在 PyTorch 和 GGUF 测试模式间切换。

## Changes

### Task 1: 添加 --gguf 选项到 sft_test.sh

**Files modified:**
- `docker/sft_test.sh`

**Changes:**
1. 添加命令行参数解析（bash while/case）
2. 支持 `--gguf` 标志（无值，作为开关）
3. 支持 `[NUM_SAMPLES]` 位置参数（默认 5）
4. 根据 `USE_GGUF` 变量选择执行脚本：
   - GGUF 模式: `src/test_gguf.py`
   - PyTorch 模式: `src/sft/test_inference.py`（默认）
5. 更新输出显示当前测试模式
6. 更新脚本头部注释说明用法

**Usage:**
```bash
# PyTorch 模式（默认）
./docker/sft_test.sh 3

# GGUF 模式
./docker/sft_test.sh --gguf 3
./docker/sft_test.sh --gguf  # 使用默认 5 条样本
```

## Deviations from Plan

None - plan executed exactly as written.

## Verification

All verification checks passed:
- [x] `bash -n docker/sft_test.sh` - 语法检查通过
- [x] `USE_GGUF` 变量存在
- [x] `test_gguf.py` 引用存在
- [x] `--gguf` 选项说明存在

## Success Criteria

- [x] `docker/sft_test.sh` 支持 `--gguf` 参数
- [x] `./docker/sft_test.sh 3` 使用 PyTorch 模式（默认）
- [x] `./docker/sft_test.sh --gguf 3` 使用 GGUF 模式
- [x] 脚本语法正确（bash -n 通过）
- [x] 输出显示当前测试模式

## Commit

- `6bf4f50`: feat(quick-1): add --gguf option to sft_test.sh
