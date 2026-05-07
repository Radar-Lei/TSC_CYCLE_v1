# TSC-CYCLE State

**Last Activity:** 2026-05-07 11:24
**Current Milestone:** v1.0
**Status:** P4b 第三次重启。前一次（TS=20260507T020310Z）epoch 1 smoke 通过（5/5, native_leak=0），但 epoch 末尾 Trainer eval+save 内存峰值杀进程。已禁用 eval_strategy 与 trainer save_strategy，改由 SmokeCallback 在 epoch 末写 `adapter_epochN/` 快照，最终 adapter 由 main() 末尾保存到 `adapter/`。

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
| 5. Merge + GGUF Export | ⚙ queued (watchdog) | watchdog 自动触发 |
| 6. Evaluation Suite | ⚙ queued (watchdog) | watchdog 自动触发 |

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
