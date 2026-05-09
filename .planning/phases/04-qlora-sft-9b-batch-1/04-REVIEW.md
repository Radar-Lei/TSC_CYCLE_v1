---
phase: 04-qlora-sft-9b-batch-1
reviewed: 2026-05-09T00:00:00Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - tests/test_v3_sft_config.py
  - tests/test_v3_sft_arrow_loader.py
  - tests/test_v3_sft_dry_run.py
  - tests/test_v3_sft_grad_gate.py
  - tests/test_v3_sft_frozen.py
  - tests/test_v3_sft_artifacts.py
  - tsc_cycle/student/sft_v3.py
  - tsc_cycle/student/train.py
  - tsc_cycle/v3_gates/sft_dry_run_v3.py
  - tsc_cycle/v3_gates/sft_report_v3.py
  - scripts/run_v3_phase4_dry_run.sh
  - scripts/run_v3_phase4_full.sh
findings:
  critical: 7
  warning: 1
  info: 0
  total: 8
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-09T00:00:00Z  
**Depth:** standard  
**Files Reviewed:** 12  
**Status:** issues_found

## Summary

审查重点覆盖 Phase 4 SFT 配置、训练入口、dry-run/full-run gate、聚合报告和 DGX Spark wrapper。实现仍存在多处会导致训练 gate 假绿、硬约束漏检、路径隔离不完整或 wrapper 不可复现的问题，不能直接进入长训或下游交付。

## Critical Issues

### CR-01: BLOCKER — LoRA 覆盖报告可被基础模块名假绿

**File:** `/home/samuel/TSC_CYCLE/tsc_cycle/student/sft_v3.py:368-389`  
**Issue:** `build_lora_coverage_report()` 同时扫描所有 `model.named_modules()` 和 LoRA 名称，并用基础模块名里的 `attention/deltanet` 统计覆盖层。即使 LoRA 只注入少数模块，只要基础模型本身包含这些层名，24/8 层覆盖也可能被报告为通过。  
**Fix:** 只从 trainable LoRA 参数/模块反推出被注入的 base projection；每层必须有可训练 LoRA projection 证据，不能用基础模块名代替。

### CR-02: BLOCKER — 聚合 gate 会为缺失训练参数和 LoRA 参数自动补默认值

**File:** `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/sft_report_v3.py:239-264,301-331`  
**Issue:** `_check_lora_coverage()` 和 `_check_sft02/_check_sft03()` 在证据缺失但 manifest `ok=true` 时自动填入 r=64、alpha=64、batch=1、packing=False 等默认值。这会让报告在没有机器证据的情况下通过 SFT-01/02/03。  
**Fix:** `train.py` 写入真实 `training_args` 与 LoRA config；report gate 删除所有“manifest ok 则补默认值”的逻辑，缺字段必须 fail closed。

### CR-03: BLOCKER — dry-run 硬约束 lint 会截断非整数输出

**File:** `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/sft_dry_run_v3.py:275`  
**Issue:** dry-run 使用 `parse_assistant_output()` 的解析结果进行 lint；该解析函数会把 solution value 强制 `int(v)`，因此模型输出 `20.9` 可能被截断成 `20` 后通过 min/max/整数检查，造成 OOD hard-constraint pass rate 假绿。  
**Fix:** 解析 SOLUTION 时保留原始 JSON 数值类型；lint 前不得 coercion。非整数 float/string 必须作为 violation 进入 pass-rate 计算。

### CR-04: BLOCKER — dry-run 1 小时 gate 没有统计 OOD 生成耗时

**File:** `/home/samuel/TSC_CYCLE/scripts/run_v3_phase4_dry_run.sh:89-106` and `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/sft_dry_run_v3.py:139-147,365`  
**Issue:** wrapper 在训练结束后立即计算 `elapsed_seconds`，随后才执行 500 条 OOD generation/lint；gate 只检查传入的训练耗时，不检查 `wall_clock_generation_seconds`。dry-run 总耗时超过 3600 秒仍可能通过。  
**Fix:** 在 wrapper 中用同一个 timer 包住训练 + dry-run gate generation，或在 `evaluate_dry_run_gate()` 中检查 `elapsed_seconds + wall_clock_generation_seconds <= 3600`。

### CR-05: BLOCKER — 聚合报告允许缺失 OOD pass rate 的 dry-run 报告通过

**File:** `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/sft_report_v3.py:344-355`  
**Issue:** `_check_sft04()` 中 `pass_rate_ok = (not pass_rate_present) or ...`，导致 `ood_hard_constraint_pass_rate` 缺失时仍可通过，只要 dry report 自称 `ok=true/full_run_allowed=true/sample_count=500`。  
**Fix:** 要求 pass rate 字段存在、可解析为 finite float，且 `>=0.95`；缺失或 NaN 必须 fail closed。

### CR-06: BLOCKER — 聚合报告允许缺失有限 loss 证据的 grad gate 通过

**File:** `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/sft_report_v3.py:392-407`  
**Issue:** `_check_sft06()` 允许 `loss_finite is None` 通过，且没有检查 `grad_norm_finite`。伪造或不完整的 grad gate 只要有 `ok=true/observed_steps>=200/p99<3` 就可绿。  
**Fix:** 强制要求 `loss_finite is True`、`grad_norm_finite is True`，并拒绝任何缺字段或 fatal failures。

### CR-07: BLOCKER — adapter/best checkpoint 只检查路径存在，不检查可用权重文件

**File:** `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/sft_report_v3.py:372-387`  
**Issue:** SFT-05 只要求 `adapter.exists()` 和 `best.exists()`，目录为空或只包含无关文件也能满足路径存在条件，导致 Phase 5 可能接收到不可用 adapter。  
**Fix:** 要求 PEFT adapter 至少包含 `adapter_model.safetensors` 和 `adapter_config.json`；best checkpoint 也必须包含可加载的 checkpoint/adapter 权重文件，并将这些文件 hash 纳入必需 gate。

## Warnings

### WR-01: WARNING — 训练入口依赖调用者 CWD，绝对路径 wrapper 从其它目录运行会失败

**File:** `/home/samuel/TSC_CYCLE/tsc_cycle/student/train.py:53,371` and `/home/samuel/TSC_CYCLE/scripts/run_v3_phase4_dry_run.sh:3-8`  
**Issue:** wrapper 使用绝对 `ROOT/PY`，但没有 `cd "$ROOT"`；`train.py` 中 `V1_ROOT = Path("runs/20260507T032419Z")` 是相对路径。从非项目根目录执行 wrapper 时，前置 shell 检查使用绝对 v1 root 可通过，但 Python 训练入口会查找错误的相对 `runs/...`。  
**Fix:** wrapper 开头执行 `cd "$ROOT"`，并将 `V1_ROOT` 改为基于项目根的绝对路径或从 CLI 显式传入。
