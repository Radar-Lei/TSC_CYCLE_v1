---
phase: 06-evaluation-suite
plan: 03
subsystem: evaluation
tags: [evaluation, gguf, llama-server, generation, bf16]
requires: [06-01, 06-02]
provides:
  - tsc_cycle/eval/generate_gguf.py
  - runs/20260507T032419Z/eval/gen_cache/gguf_bf16/  # 600 cache files
affects: [06-04, 06-05]
tech-stack:
  added: []
  patterns:
    - "llama-server single-load + urllib POST /completion"
    - "Per-sample JSON cache with resume on existence"
    - "Parameterized backend label (bf16 / q4_K_M reuse)"
key-files:
  created:
    - tsc_cycle/eval/generate_gguf.py
    - runs/20260507T032419Z/eval/gen_cache/gguf_bf16/{600 files}
    - runs/20260507T032419Z/eval/gen_cache/server_gguf_bf16.log
    - runs/20260507T032419Z/eval/gen_gguf_bf16.log
  modified: []
decisions:
  - "Reuse parity_gguf helpers via import (not copy) — single source of truth for server lifecycle"
  - "Per-sample JSON files (not aggregated) to match generate_hf.py schema and enable resume"
  - "n_predict=384, temperature=0, top_k=1, seed=42 — identical to hf_bf16 backend for parity"
metrics:
  duration_min: 53
  tasks: 2
  cache_files: 600
completed: 2026-05-07
---

# Phase 06 Plan 03: gguf_bf16 EVL Generation Summary

GGUF bf16 backend EVL runner — 基于 `parity_gguf.py` 的 llama-server 单次启动模式改造为参数化 600-prompt
generation runner，产出 `gen_cache/gguf_bf16/` 共 600 个 cache 文件。

## What was built

`tsc_cycle/eval/generate_gguf.py`：通用 GGUF backend EVL generation runner（194 行）。
- argparse 参数化：`--gguf-path`、`--backend-label`、`--cache-dir`、`--n-predict` 等
- 复用 `tsc_cycle.student.parity_gguf` 的 `_spawn_server / _wait_health / _post_completion / _kill_server / _find_free_port`
- 启动 once：`/home/samuel/llama.cpp/build/bin/llama-server` (CUDA build)，参数 `-ngl 99 -t 4 -c 4096 --no-webui`
- POST `/completion`：`{"prompt", "n_predict": 384, "temperature": 0.0, "top_k": 1, "seed": 42, "cache_prompt": True, "stream": False}`
- 断点续跑：`gen_cache/<label>/{sample_id}.json` 已存在则跳过；全 cached 时打印 `OK all-cached` 立即返回
- 每 10 prompt 进度打印；`finally` 段 SIGTERM 回收 server

同一脚本将在 plan 06-04 复用（`--gguf-path runs/.../gguf/model.q4_K_M.gguf --backend-label gguf_q4_K_M --cache-dir runs/.../eval/gen_cache/gguf_q4_K_M`）。

## Generation parameters

- n_predict=384, temperature=0.0, top_k=1, seed=42, cache_prompt=true, stream=false
- 解析 `<SOLUTION>{json}</SOLUTION>` 经由 `parse_assistant_output`；失败时 `parse_error` 记录原因，`raw_text` 保留
- pad/eos/seed 与 plan 06-02 (`hf_bf16`) 完全一致 → backend parity 可比

## Cache schema

```json
{
  "sample_id": "<sha256>",
  "split_hint": "id|ood",
  "backend": "gguf_bf16",
  "solution": {...} | null,
  "parse_error": null | "...",
  "raw_text": "...",
  "elapsed_sec": <float>,
  "n_predict": 384,
  "seed": 42
}
```

## Verification

- `ls runs/20260507T032419Z/eval/gen_cache/gguf_bf16/*.json | wc -l` = **600** ✓
- `total=600 parsed=600 parse_errors=0`（全 600 sample 的 `<SOLUTION>{json}</SOLUTION>` 都 lint-clean 解析）
- 任一 cache 的 `backend` 字段 == `"gguf_bf16"` ✓
- `runs/20260507T032419Z/eval/gen_cache/server_gguf_bf16.log` 存在（4.2 MB）✓
- 无残留 `llama-server` 进程（脚本 `finally` 段 SIGTERM 回收）✓

## Timing

| Stage | Wall time |
|-------|-----------|
| Server startup (/health 200) | 4.0 s |
| Inference 600 prompts | 3177.1 s (~52.95 s / 10 prompts → 5.30 s/prompt) |
| **Total** | **53.0 min** |

与 plan 5 GGUF bf16 实测 5.2 s/prompt（20-prompt parity 子集）一致。

## Acceptance criteria — Task 1

- ✅ `tsc_cycle/eval/generate_gguf.py` 存在 194 行 (≥100)
- ✅ grep `/home/samuel/llama.cpp/build/bin/llama-server` 命中
- ✅ grep `from tsc_cycle.student.parity_gguf import` 命中
- ✅ `backend_label` 出现 3 次（≥3）
- ✅ `all-cached` 命中（断点续跑分支）
- ✅ `EvoProgTSC/llama.cpp` 出现 0 次（避免 CPU build）
- ✅ `python -c "import ast; ast.parse(...)"` 解析通过

## Acceptance criteria — Task 2

- ✅ 600 cache 文件
- ✅ `backend == "gguf_bf16"`
- ✅ server log 文件存在
- ✅ 无残留 server 进程

## Commits

- `c418ab8` feat(06-03): add gguf eval generation runner

## Notes / Deviations

- 无 Rule 1/2/3 自动修复；plan 直接执行无偏差
- parse_errors=0 → bf16 GGUF 在 600 prompt 上结构稳定；为 plan 06-04 的 q4_K_M 量化对比提供干净基线
- llama-server 在 `finally` 段干净退出，GPU 已释放，可让 plan 06-04 立即启动 q4_K_M 生成

## Self-Check: PASSED

- ✅ `tsc_cycle/eval/generate_gguf.py` 存在
- ✅ `runs/20260507T032419Z/eval/gen_cache/gguf_bf16/` 含 600 文件
- ✅ commit `c418ab8` 在 git log
