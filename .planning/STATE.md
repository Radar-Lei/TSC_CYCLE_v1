---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: 强化版
status: planning
last_updated: "2026-05-08T04:53:05.026Z"
last_activity: 2026-05-08
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# TSC-CYCLE State

**Last Activity:** 2026-05-07
**Current Milestone:** v1.0
**Status:** Milestone complete

## Active Background Processes (setsid-detached, survives shell exit)

- Train (P4b SFT): PID **3041752** — `python -m tsc_cycle.student.train --batch-size 1 --grad-accum 32`
  - Output dir: `runs/20260507T032419Z/train`
  - Log: `runs/20260507T032419Z_train.log`
  - 154 optimizer steps × 2 epoch（micro-batch=1, ga=32）
  - Save strategy: epoch（adapter 在 epoch 末写出）
- Watchdog (P5 export + P6 eval): PID **3041884** — `bash scripts/run_export_eval_watchdog.sh`
  - Log: `runs/20260507T032419Z_watchdog.log`
  - Polls every 60s for `runs/20260507T032419Z/train/adapter/adapter_model.safetensors`
  - Auto-runs export_gguf → parity → run_eval after adapter ready

## Phase Status

| Phase | Status | Notes |
|---|---|---|
| 1. Environment + Foundations | ✓ done | venv + foundations + 24/24 tests + tokenizer check + dist_prior |
| 2. Synthetic Data Generation | ✓ done | 2700 + 300 inputs, KS report passes |
| 3. Teacher Labeling | ✓ done | 3000/3000 通过 lint，0 reject，cost ~$23.22 |
| 4a. Tokenize | ✓ done | train=4761, val_id=521, val_ood=596, max_length=1164 |
| 4b. QLoRA SFT | ⚙ running | TS=20260507T032419Z, bs=1×ga32, peak <80GB |
| 5. Merge + GGUF Export | ⚠ done-with-flag | parity MAE=4.51s >3s; imatrix backlog; report: runs/20260507T032419Z/PHASE05_REPORT.md |
| 6. Evaluation Suite | ✓ done | decision=GO; q4_K_M ood lint ratio=0.9933 (98.7%/99.3%); per_sample.jsonl + report.md + decision.md 落盘 |

## Final Artifact (the GGUF user is waiting for)

**Path:** `runs/20260507T032419Z/gguf/model.q4_K_M.gguf`

## Why bs=1 grad_accum=32

之前 bs=4 训练在 step 1 后崩。降到 bs=1 + ga=32：

- effective batch 仍为 32（梯度同质量）
- per-step activation 内存 ~4× 降低
- 整体峰值估计 50–60 GB（远低于 80GB 上限）

## Monitor Progress

```bash
tail -f runs/20260507T032419Z_train.log
tail -f runs/20260507T032419Z_watchdog.log
ps -p 2934829 -o pid,etime,cmd
ls -lh runs/20260507T032419Z/gguf/model.q4_K_M.gguf
```

## Recover from crash

```bash
TS=20260507T032419Z bash scripts/run_pipeline_bg.sh
```

## Time Budget

| Phase | Est. wallclock |
|---|---|
| 4b (SFT, bs=1×ga32) | ~3-4 h |
| 5 (merge+gguf) | ~15 min |
| 6 (eval) | ~30 min |
| **Total ETA** | **~4-5 hours from launch** |

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-05-08 — Milestone v2.0 started
