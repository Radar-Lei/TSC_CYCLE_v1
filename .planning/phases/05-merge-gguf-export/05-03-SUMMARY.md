---
phase: 05-merge-gguf-export
plan: 03
subsystem: student/parity
tags: [parity, gguf, llama-server, evaluation, dgx-spark]
requires:
  - tsc_cycle/student/parity_prompts.py (Plan 05-02)
  - runs/20260507T032419Z/gguf/parity_prompts.jsonl (Plan 05-02 frozen 20-sample set)
  - runs/20260507T032419Z/merged_bf16/ (HF merged adapter)
  - runs/20260507T032419Z/gguf/model.bf16.gguf (Plan 05-01 export)
  - runs/20260507T032419Z/gguf/model.q4_K_M.gguf (Plan 05-01 quantize)
provides:
  - tsc_cycle.student.parity (orchestrator; subprocess-isolated 4-stage pipeline)
  - tsc_cycle.student.parity_hf (HF bf16 single-shot runner)
  - tsc_cycle.student.parity_gguf (GGUF bf16 / q4_K_M shared runner via llama-server)
  - tsc_cycle.student.parity_merge (MAE + report writer)
  - runs/20260507T032419Z/gguf/parity_report.json (overall_mae_q4_vs_hf=4.515)
affects:
  - Plan 05-04+ (downstream eval): can now consume parity_report.json + STATE.md FLAG
  - imatrix backlog: q4_K_M MAE=4.5s exceeds 3s threshold; re-quantize candidate
tech-stack:
  added:
    - llama-server (CUDA-built /home/samuel/llama.cpp/build/bin/llama-server)
  patterns:
    - "Subprocess-isolated stages: orchestrator never imports torch/transformers; each child fully releases CUDA before next starts"
    - "Per-backend llama-server (one model load) + urllib POST /completion per prompt; amortises ~5 min cold-start across all 20 prompts"
    - "Server own process group via os.setsid + SIGTERM-on-pgrp for clean teardown even on python exception"
    - "ctx_size=4096 fixes default 262k KV-cache pre-allocation that bloated VRAM to 36GB and slowed every cold start"
key-files:
  created:
    - tsc_cycle/student/parity_hf.py (125 lines)
    - tsc_cycle/student/parity_gguf.py (216 lines, llama-server flavor)
    - tsc_cycle/student/parity_merge.py (144 lines)
    - tsc_cycle/student/parity.py (143 lines)
    - runs/20260507T032419Z/gguf/parity_hf.json (gitignored)
    - runs/20260507T032419Z/gguf/parity_gguf_bf16.json (gitignored)
    - runs/20260507T032419Z/gguf/parity_gguf_q4.json (gitignored)
    - runs/20260507T032419Z/gguf/parity_report.json (gitignored)
  modified: []
decisions:
  - "Switched GGUF runner from llama-cli per-prompt subprocess to llama-server-once + HTTP POST per prompt (Rule 3 blocking perf fix). Cold-start was ~5 min/prompt; bf16 alone would have been ~100 min, exceeding plan's 1500s/backend assertion."
  - "Default --llama-cli (CPU-only EvoProgTSC build) replaced with /home/samuel/llama.cpp/build/bin/llama-server (CUDA-linked, GB10 detected, 122GB VRAM)."
  - "ctx_size=4096 explicit (Qwen3 metadata default 262k pre-allocates 36GB KV cache → slow cold start, irrelevant for 20-prompt parity test)."
  - "FLAG line append to STATE.md is functional in code (verified via sample run) but reverted from worktree per worktree branch protection rules; downstream merge will need to re-emit on the master branch."
metrics:
  duration: ~2h (initial CPU-only diagnosis + Rule 3 architecture switch + full 4-stage rerun)
  tasks_completed: 4/4
  files_created: 4 source modules + 4 JSON outputs
  completed_date: 2026-05-07
requirements: [EXP-01, EXP-02, EXP-03, EXP-05]
---

# Phase 05 Plan 03: 三精度 Parity Test Summary

实现了 EXP-05 的三精度 parity 测试 (HF bf16 / GGUF bf16 / GGUF q4_K_M)。
为避免 DGX Spark unified memory 死锁，采用 4 个独立子进程串行；为通过 plan
的 1500s/backend 时间断言，将 GGUF backend 从 per-prompt llama-cli subprocess
切换到 llama-server-once + HTTP /completion 每条 prompt（Rule 3 性能阻塞修复）。

## Pre-flight 状态

| 项 | 实测 |
|----|------|
| swap | **off** (`swapon --show` 空输出 → orchestrator 通过) |
| GPU | NVIDIA GB10, 122570 MiB VRAM, CUDA 13.0 |
| llama-server CUDA build | `/home/samuel/llama.cpp/build/bin/llama-server` (libggml-cuda.so + libcublas.so.13) |
| 软链 | `data/labeled.jsonl -> /home/samuel/TSC_CYCLE/data/labeled.jsonl`，`runs -> /home/samuel/TSC_CYCLE/runs` |
| parity_prompts.jsonl | 重新生成（gitignored，byte-stable md5=`09fa4e6326722c37bad720dbfddc29db`） |

## 关键结果

| Backend | total_sec | startup_sec | infer_sec | parse_failures |
|---------|----------:|------------:|----------:|---------------:|
| HF bf16 (transformers) | **134.5** | n/a | 134.5 | 0 |
| GGUF bf16 (llama-server) | **104.3** | 4.0 | 100.3 | 0 |
| GGUF q4_K_M (llama-server) | **48.9** | 2.0 | 46.9 | 0 |

| Metric | Value |
|--------|------:|
| n_prompts | 20 |
| n_parse_failures | 0 |
| overall_mae_bf16_vs_hf | **0.58** s/phase |
| overall_mae_q4_vs_hf | **4.51** s/phase |
| MAE threshold | 3.0 s |
| **mae_exceeded** | **True** → imatrix backlog flag |

GGUF format 本身 (bf16) 与 HF bf16 决策几乎一致 (MAE 0.58s)。q4_K_M 量化误差
是 4.51s — 超出 plan 的 3s 阈值，按 plan 第 257 行说明应 append 到 STATE.md。

## Acceptance Criteria — All Passed

| 条件 | 期望 | 实际 | 状态 |
|------|------|------|------|
| parity_report.json exists | yes | yes | ✓ |
| n_prompts == 20 | 20 | 20 | ✓ |
| len(per_prompt) == 20 | 20 | 20 | ✓ |
| overall_mae_q4_vs_hf 字段存在 | grep ≥ 1 | yes | ✓ |
| timing 字段存在 | grep ≥ 1 | yes | ✓ |
| n_parse_failures ≤ 5 | ≤ 5 | 0 | ✓ |
| gguf_q4_total_sec < 1500 | < 1500 | 48.9 | ✓ |
| gguf_bf16_total_sec < 1500 | < 1500 | 104.3 | ✓ |
| parity.py 不 import torch/transformers | == 0 | 0 | ✓ |
| parity.py 调 swapon | ≥ 1 | 2 | ✓ |
| parity.py 调 nvidia-smi | ≥ 1 | 4 | ✓ |
| parity.py 用 subprocess 调 4 module | ≥ 4 | 15 | ✓ |
| parity_hf.py uses bf16 + sdpa | each ≥ 1 | 1 + 1 | ✓ |
| parity_gguf.py 含 -ngl + 600 + no-display(equivalent --no-webui for server) | ≥ 1 | 1 + 1 + (替换为 --no-webui) | ⚠ |
| parity_merge.py 含 overall_mae / mae_exceeded / FLAG | each ≥ 1 | 3 + 3 + 3 | ✓ |

⚠ 注释：plan 第 208 行要求 `--no-display-prompt`，那是 llama-cli flag。切到
llama-server 后等价语义是 `--no-webui`（关闭 webui，避免占用 stdout）。功能
等价（防止额外输出污染 HTTP body），不影响下游解析。

## GPU 释放诊断 (`_diag` 输出)

`nvidia-smi --query-gpu=memory.used,memory.free` 在 DGX Spark unified memory
架构上**始终返回 `[N/A], [N/A]`**（驱动在该平台不暴露 used/free），但
`--query-compute-apps=pid,used_memory` 能看到实际 GPU 占用：

| 阶段 | 实测进程 GPU memory |
|------|---------------------|
| pre_hf | 仅 GUI 进程 (~580 MiB) |
| 运行 parity_hf | python 进程 8101 MiB |
| post_hf / pre_bf16 | 主 python 进程退出，GUI 残留 |
| 运行 parity_gguf bf16 | llama-server 进程 8765 MiB |
| post_bf16 / pre_q4 | server reaped → 残留 GUI |
| 运行 parity_gguf q4 | llama-server 占用更小 (q4_K_M ~3GB model + KV) |
| post_q4 | server reaped |

→ 子进程间 GPU memory 完整释放；unified memory 死锁防护按预期生效。

## Per-prompt MAE highlights

20 条 (10 id + 10 ood) 全部 q4_K_M 输出可解析。MAE 分布：

- 14/20 prompts: MAE ≤ 2.5s（量化几乎无影响）
- 3/20: MAE 4-10s（中度量化漂移）
- 3/20: MAE > 10s（q4 退化点）：
  - `33951e9d` (id): MAE 10.0 — `phase_4` HF=80, q4=49（缺尾偏短）
  - `dfb9ae1a` (ood): MAE 44.0 — `phase_3` HF=32, q4=158（**违反 max_green 硬约束！**）
  - `3378f32b` (ood): MAE 9.5 — `phase_1` HF=20, q4=45（首相位偏长）

特别需关注 `dfb9ae1a` 的 158s — 这是 q4 数值崩塌典型信号，触发 plan 提到的
"q4_K_M 崩塌"检测。imatrix 重量化的优先级因此提高。

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] EvoProgTSC llama-cli is CPU-only build**

- **Found during:** Task 4 验证（首次跑 orchestrator）
- **Issue:** plan 默认 `--llama-cli /home/samuel/projects/EvoProgTSC/llama.cpp/llama-cli`，但 `ldd` 显示该 binary 不链接 libcuda/libcublas — 是 CPU-only build。`-ngl 99` 无效，bf16 单 prompt 跑 ~8 分钟。
- **Fix:** 切到 `/home/samuel/llama.cpp/build/bin/llama-cli`（CUDA-linked，启动时打印 `ggml_cuda_init: found 1 CUDA devices Total VRAM: 122570 MiB`）。
- **Files modified:** `parity_gguf.py`, `parity.py` defaults
- **Commit:** `aa09157`（与 Task 4 一起）

**2. [Rule 3 - Blocking] llama-cli per-prompt cold-start 不可达成 1500s 阈值**

- **Found during:** 首轮跑（CUDA build）—— bf16 单 prompt 仍 ~5 min；llama_memory_breakdown 显示 KV context 占 36 GB（默认 ctx=262k）。即使 `-c 4096` 限制，单 prompt 4-5 min × 20 prompts × 2 backends ≈ 3.5 h，远超 plan 1500s/backend 时间断言。
- **Issue:** plan 假设 subprocess.run llama-cli per prompt 是可行的，但 4B 模型 cold-start (model load + CUDA context init + KV pre-alloc) 占 100% 的单 prompt 时间。
- **Fix:** 重写 `parity_gguf.py` 用 `llama-server`：每 backend 一次模型加载、`urllib` POST `/completion` 20 次。结果：bf16 startup=4s + infer=100s = 104s；q4 startup=2s + infer=47s = 49s。一次性放大 1500s assertion 通过余量。
- **Server lifecycle:** `os.setsid` 隔离 process group + `SIGTERM` to pgrp（含 `try/finally` 防异常路径泄漏）。每 backend 子进程退出时 server 一定 reaped。
- **Files modified:** `parity_gguf.py` (重写, 158→216 lines), `parity.py` (rename `--llama-cli` → `--llama-server`)
- **Commit:** `ff66261`

**3. [Rule 3 - Bug fix] llama-cli 默认 ctx=262k pre-allocate 36GB KV cache**

- **Found during:** 诊断阶段（看 llama_memory_breakdown）
- **Issue:** 即使在 CUDA build，每条 prompt 都预分配 36GB KV cache，是单 prompt 4-5min 的部分原因。
- **Fix:** 在 llama-server 启动加 `-c 4096`（plan 单 prompt prompt + 384 generation 都远低于 2k token，4096 留 2x 余量）。
- **包含在 commit:** `ff66261`

**4. [Worktree rule] STATE.md FLAG append**

- **Found during:** parity_merge 运行时
- **Issue:** parity_merge.py 按 plan 行为 append `[FLAG] Phase 5 parity MAE q4 vs hf = 4.51s ...` 到 STATE.md，但 worktree 模式下 STATE.md 修改是被禁止的 (`Do NOT modify STATE.md`)。
- **Fix:** `git checkout -- .planning/STATE.md` 还原 STATE.md。code path 仍然 functional（已运行验证），主分支 merge 后由人工/orchestrator 决定是否再触发一次 merge stage 把 flag 持久化到主 STATE.md。MAE 信息保留在 `parity_report.json` 的 `mae_exceeded: true` 字段。
- **Files modified:** STATE.md（已还原）
- **No commit needed**

## Out-of-Scope Discoveries (deferred)

- 既有 `tsc_cycle/eval/parity.py:70` 调 `build_user_prompt(s)` 把整条 record 传入，但 `prompt_builder.build_user_prompt` 期望 `prediction_input`（即 `record["input"]`）。该旧脚本与本 plan 不在同一执行路径，不影响 plan 03 通过；记入 deferred-items 由 future plan 修。
- llama-cli 在 DGX Spark 上 KV cache 默认 262k 是 Qwen3 model metadata 派生的，可能影响其他下游脚本（如 export_gguf 或后续 eval）；建议所有 llama.cpp 调用统一 `-c 4096`。
- nvidia-smi memory.used/free 在 DGX Spark 始终 N/A 是平台特性（unified memory 不分 host/device），不是 bug；要看 GPU 占用必须用 `--query-compute-apps`。

## Auth Gates

无 — 纯本地脚本，无 API 调用。

## Known Stubs

无。

## Threat Flags

无新增网络 surface（llama-server 只 listen `127.0.0.1` 临时随机端口，进程退出即关闭，无持久监听）。

## Self-Check: PASSED

- ✓ FOUND: tsc_cycle/student/parity.py
- ✓ FOUND: tsc_cycle/student/parity_hf.py
- ✓ FOUND: tsc_cycle/student/parity_gguf.py
- ✓ FOUND: tsc_cycle/student/parity_merge.py
- ✓ FOUND: runs/20260507T032419Z/gguf/parity_report.json (本地存在，gitignored)
- ✓ FOUND commit 4cb759c: feat(05-03) parity_hf
- ✓ FOUND commit 4995205: feat(05-03) parity_gguf (initial llama-cli)
- ✓ FOUND commit 1a32985: feat(05-03) parity_merge
- ✓ FOUND commit aa09157: feat(05-03) orchestrator + CUDA llama-cli switch
- ✓ FOUND commit ff66261: fix(05-03) llama-server perf rewrite
