# TSC-CYCLE State

**Last Activity:** 2026-05-07 10:04
**Current Milestone:** v1.0
**Status:** P4b 重启（bs=1, grad_accum=32，effective batch 32 不变；显著降低 per-step 内存）。Watchdog 监听 adapter，就绪后自动跑 P5 export → P6 eval。

## Active Background Processes (setsid-detached, survives shell exit)

- Train (P4b SFT): PID **2934829** — `python -m tsc_cycle.student.train --batch-size 1 --grad-accum 32`
  - Output dir: `runs/20260507T020310Z/train`
  - Log: `runs/20260507T020310Z_train.log`
  - 154 optimizer steps × 2 epoch（micro-batch=1, ga=32）
  - Save strategy: epoch（adapter 在 epoch 末写出）
- Watchdog (P5 export + P6 eval): PID **2935791** — `bash scripts/run_export_eval_watchdog.sh`
  - Log: `runs/20260507T020310Z_watchdog.log`
  - Polls every 60s for `runs/20260507T020310Z/train/adapter/adapter_model.safetensors`
  - Auto-runs export_gguf → parity → run_eval after adapter ready

## Phase Status

| Phase | Status | Notes |
|---|---|---|
| 1. Environment + Foundations | ✓ done | venv + foundations + 24/24 tests + tokenizer check + dist_prior |
| 2. Synthetic Data Generation | ✓ done | 2700 + 300 inputs, KS report passes |
| 3. Teacher Labeling | ✓ done | 3000/3000 通过 lint，0 reject，cost ~$23.22 |
| 4a. Tokenize | ✓ done | train=4761, val_id=521, val_ood=596, max_length=1164 |
| 4b. QLoRA SFT | ⚙ running | TS=20260507T020310Z, bs=1×ga32, peak <80GB |
| 5. Merge + GGUF Export | ⚙ queued (watchdog) | watchdog 自动触发 |
| 6. Evaluation Suite | ⚙ queued (watchdog) | watchdog 自动触发 |

## Final Artifact (the GGUF user is waiting for)

**Path:** `runs/20260507T020310Z/gguf/model.q4_K_M.gguf`

## Why bs=1 grad_accum=32

之前 bs=4 训练在 step 1 后崩。降到 bs=1 + ga=32：
- effective batch 仍为 32（梯度同质量）
- per-step activation 内存 ~4× 降低
- 整体峰值估计 50–60 GB（远低于 80GB 上限）

## Monitor Progress

```bash
tail -f runs/20260507T020310Z_train.log
tail -f runs/20260507T020310Z_watchdog.log
ps -p 2934829 -o pid,etime,cmd
ls -lh runs/20260507T020310Z/gguf/model.q4_K_M.gguf
```

## Recover from crash

```bash
TS=20260507T020310Z bash scripts/run_pipeline_bg.sh
```

## Time Budget

| Phase | Est. wallclock |
|---|---|
| 4b (SFT, bs=1×ga32) | ~3-4 h |
| 5 (merge+gguf) | ~15 min |
| 6 (eval) | ~30 min |
| **Total ETA** | **~4-5 hours from launch** |
