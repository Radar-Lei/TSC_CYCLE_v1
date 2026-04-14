---
phase: 05-simple-grpo-train
verified: 2026-04-01T16:21:01Z
status: passed
score: 5/5 must-haves verified
---

# Phase 5: 简化版训练入口与验证 Verification Report

**Phase Goal:** 基于 Unsloth Docker 提供独立的简化版 GRPO 数据生成、训练入口、输出目录和基础测试。  
**Verified:** 2026-04-01T16:21:01Z  
**Status:** passed

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 简化版 GRPO 数据直接来自 `outputs/data/train.jsonl` | ✓ VERIFIED | `src/scripts/generate_grpo_simple_data.py` 默认输入该文件；Docker 数据脚本已实际跑通 |
| 2 | 训练入口位于新目录，不覆盖旧版 `src/grpo/` | ✓ VERIFIED | 新增 `src/grpo_simple/train.py`，未替换旧版 `src/grpo/train.py` |
| 3 | 数据生成与训练都通过 Unsloth Docker 执行 | ✓ VERIFIED | `docker/grpo_simple_data.sh` 与 `docker/grpo_simple_train.sh` 都使用 `qwen3-tsc-grpo:latest` |
| 4 | checkpoints 与模型输出默认写入 `outputs/grpo_simple/` | ✓ VERIFIED | `config.paths`、训练脚本和 Docker 脚本均指向 `outputs/grpo_simple/checkpoints`、`outputs/grpo_simple/model` |
| 5 | 基础 reward 验证可复用于简化版训练链路 | ✓ VERIFIED | `tests/test_grpo_simple_rewards.py` 通过，满足 VERI-01 对命中/偏离/越界/格式错误的验证要求 |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/scripts/generate_grpo_simple_data.py` | 数据生成脚本 | ✓ EXISTS + SUBSTANTIVE | 读取原始 train.jsonl，输出 GRPO messages + metadata |
| `src/grpo_simple/train.py` | 简化版训练入口 | ✓ EXISTS + SUBSTANTIVE | 加载 SFT 模型、GRPO-simple 数据、reward 函数与隔离输出目录 |
| `docker/grpo_simple_data.sh` | Docker 数据生成入口 | ✓ EXISTS + SUBSTANTIVE | 实际执行成功，生成 16,788 条数据 |
| `docker/grpo_simple_train.sh` | Docker 训练入口 | ✓ EXISTS + SUBSTANTIVE | 包含模型/数据前置检查与日志输出 |
| `config/config.json` | `training.grpo_simple` / `paths.grpo_simple_*` | ✓ EXISTS + SUBSTANTIVE | 配置初始化模型、reward、数据与输出路径 |

**Artifacts:** 5/5 verified

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `docker/grpo_simple_data.sh` | `src.scripts.generate_grpo_simple_data` | `python3 -m` | ✓ WIRED | Docker 脚本直接调用模块入口，默认输出到 `outputs/grpo_simple/grpo_train.jsonl` |
| `src/grpo_simple/train.py` | `outputs/sft/model` | `ensure_model` | ✓ WIRED | 训练前强制检查初始化模型路径 |
| `src/grpo_simple/train.py` | `outputs/grpo_simple/*` | `config.paths` | ✓ WIRED | 数据、checkpoints、合并模型均指向隔离目录 |
| `docker/grpo_simple_train.sh` | `src.grpo_simple.train` | `python3 -m` | ✓ WIRED | Docker 训练脚本以独立模块入口启动训练 |

**Wiring:** 4/4 connections verified

## Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| PIPE-00 | ✓ SATISFIED | - |
| PIPE-01 | ✓ SATISFIED | - |
| PIPE-02 | ✓ SATISFIED | - |
| PIPE-03 | ✓ SATISFIED | - |
| VERI-01 | ✓ SATISFIED | - |

**Coverage:** 5/5 requirements satisfied

## Anti-Patterns Found

None blocking.

## Human Verification Required

None — phase目标聚焦在管线搭建与入口验证，已通过脚本执行、文件检查和测试覆盖完成验证。

## Gaps Summary

**No gaps found.** Phase goal achieved. Ready to proceed.

## Verification Metadata

**Verification approach:** Goal-backward from ROADMAP + PLAN must-haves  
**Automated checks:** 5 passed, 0 failed

- `pytest -q tests/test_grpo_simple_rewards.py`
- `python -m py_compile src/grpo_simple/rewards.py tests/test_grpo_simple_rewards.py src/grpo_simple/train.py src/scripts/generate_grpo_simple_data.py`
- `python -m src.scripts.generate_grpo_simple_data --input outputs/data/train.jsonl --output /tmp/grpo_simple_preview.jsonl`
- `bash -n docker/grpo_simple_data.sh docker/grpo_simple_train.sh`
- `bash docker/grpo_simple_data.sh`

**Human checks required:** 0  
**Total verification time:** 8 min

---
*Verified: 2026-04-01T16:21:01Z*
*Verifier: the agent*
