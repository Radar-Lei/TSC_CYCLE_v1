---
phase: 06-evaluation-suite
plan: 04
subsystem: evaluation
tags: [evaluation, gguf, q4_k_m, llama-server, generation]
requires: [06-01, 06-03]
provides:
  - runs/20260507T032419Z/eval/gen_cache/gguf_q4_k_m/  # 600 cache files
affects: [06-05]
tech-stack:
  added: []
  patterns:
    - "Reuse generate_gguf.py with --backend-label gguf_q4_k_m and quantized GGUF path"
key-files:
  created:
    - runs/20260507T032419Z/eval/gen_cache/gguf_q4_k_m/{600 files}
    - runs/20260507T032419Z/eval/gen_cache/server_gguf_q4_k_m.log
    - runs/20260507T032419Z/eval/gen_gguf_q4_k_m.log
  modified: []
decisions:
  - "Zero source changes — plan 06-03 已参数化 generate_gguf.py，仅切 --gguf-path / --backend-label / --cache-dir 三参数"
  - "n_predict=384, temperature=0, top_k=1, seed=42 与 hf_bf16 / gguf_bf16 完全一致 → 三 backend parity 可比"
metrics:
  duration_min: 25
  tasks: 1
  cache_files: 600
completed: 2026-05-07
---

# Phase 06 Plan 04: gguf_q4_k_m EVL Generation Summary

GGUF q4_K_M backend EVL runner — 直接复用 plan 06-03 的 `tsc_cycle/eval/generate_gguf.py`，仅切
模型路径与 backend label，跑同样 600 prompt，产出 `gen_cache/gguf_q4_k_m/` 共 600 个 cache 文件。
完成 wave 2 第三（也是最后一个）backend，metrics 阶段（plan 06-05）可启动。

## What was built

无新代码 — 100% 复用 plan 06-03 已锁定的 `tsc_cycle/eval/generate_gguf.py`：

```bash
/home/samuel/dgx-spark-setup/.venv/bin/python -m tsc_cycle.eval.generate_gguf \
    --gguf-path runs/20260507T032419Z/gguf/model.q4_K_M.gguf \
    --backend-label gguf_q4_k_m \
    --prompts runs/20260507T032419Z/eval/eval_prompts.jsonl \
    --cache-dir runs/20260507T032419Z/eval/gen_cache/gguf_q4_k_m \
    --n-predict 384
```

Server: `/home/samuel/llama.cpp/build/bin/llama-server -ngl 99 -t 4 -c 4096 --no-webui`
（CUDA build；模型 2.4 GB，全卸载到 GB10 VRAM）。

## Generation parameters

- n_predict=384, temperature=0.0, top_k=1, seed=42, cache_prompt=true, stream=false
- 与 plan 06-02 (`hf_bf16`) 与 plan 06-03 (`gguf_bf16`) 完全一致 → 三 backend parity 可比

## Verification

- `ls runs/20260507T032419Z/eval/gen_cache/gguf_q4_k_m/*.json | wc -l` = **600** ✓
- `total=600 parsed=600 parse_errors=0`（全 600 sample 的 `<SOLUTION>{json}</SOLUTION>` 都成功解析）✓
- 任一 cache 的 `backend` 字段 == `"gguf_q4_k_m"` ✓
- 任一 cache 的 `n_predict` == 384，`seed` == 42 ✓
- `runs/20260507T032419Z/eval/gen_cache/server_gguf_q4_k_m.log` 存在（4.0 MB）✓
- 无残留 `llama-server` 进程（`finally` 段 SIGTERM 回收）✓
- **三 backend cache 文件总数：1800 = 600 × 3** ✓ (`ls runs/.../gen_cache/*/*.json | wc -l`)

## Timing

| Stage | Wall time |
|-------|-----------|
| Server startup (/health 200) | 2.0 s |
| Inference 600 prompts | 1451.2 s (~24.2 min → 2.42 s/prompt) |
| **Total** | **~24.2 min** |

q4_K_M 比 gguf_bf16（5.30 s/prompt @ plan 06-03）快 ~2.2× — 量化模型在同一 server 上的预期收益。

## Acceptance criteria — Task 1

- ✅ `runs/20260507T032419Z/eval/gen_cache/gguf_q4_k_m/*.json` 600 个文件
- ✅ `backend` 字段 == `"gguf_q4_k_m"`
- ✅ `n_predict` == 384，`seed` == 42
- ✅ `server_gguf_q4_k_m.log` 存在
- ✅ 脚本退出后无残留 `llama-server` 进程
- ✅ 三 backend cache 文件总数 == 1800

## Notes / Deviations

- 无 Rule 1/2/3 自动修复；plan 直接执行无偏差
- **意外好结果**：parse_errors = 0/600。Phase 5 parity（20-prompt 子集）显示 q4_K_M 对 HF bf16
  数值 MAE = 4.51s（>3s 阈值），且 OOD 上有相位绿灯 158s 的崩塌信号。但**结构层面**
  （`<start_working_out>...<SOLUTION>{json}</SOLUTION>` 标签 + JSON 可解析）在 600 prompt
  上 100% 稳定 — 量化没有破坏输出 schema。
- 数值层面的退化（min/max/相位覆盖 lint 通过率、与 hf_bf16 的 MAE）将由 plan 06-05 metrics
  + plan 06-06 decision 评估，触发条件成立则启动 imatrix 重量化。
- llama-server 干净退出，GPU 已释放，wave 3（plan 06-05 metrics）可立即启动。

## Self-Check

- ✅ `runs/20260507T032419Z/eval/gen_cache/gguf_q4_k_m/` 含 600 文件
- ✅ `runs/20260507T032419Z/eval/gen_cache/server_gguf_q4_k_m.log` 存在
- ✅ `ls runs/.../gen_cache/*/*.json | wc -l` == 1800
- ✅ `pgrep -f llama-server` 无残留输出

## Self-Check: PASSED
