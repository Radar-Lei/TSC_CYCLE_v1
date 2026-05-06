# TSC-CYCLE State

**Last Activity:** 2026-05-07
**Current Milestone:** v1.0
**Status:** 全自动 pipeline 后台运行中（PID 2743735，nohup 不依赖会话）

## Phase Status

| Phase | Status | Notes |
|---|---|---|
| 1. Environment + Foundations | ✓ executed | venv + foundations + 24/24 tests + tokenizer check + dist_prior |
| 2. Synthetic Data Generation | ✓ executed | 2700 + 300 inputs, KS report passes |
| 3. Teacher Labeling | ⚙ running | GPT-5.5 high via codex proxy http://148.135.118.86:8080. 50-sample 烟雾 100% pass。全量后台跑中（rate ~30/min） |
| 4. Dataset + QLoRA SFT | ⚙ queued | 自动接力 P3 完成后 |
| 5. Merge + GGUF Export | ⚙ queued | 自动接力 P4 完成后 |
| 6. Evaluation Suite | ⚙ queued | 自动接力 P5 完成后 |

## Background Process

```
PID:    2743735
Driver: scripts/run_pipeline_bg.sh
Log:    runs/20260506T212001Z_pipeline.log
TS:     20260506T212001Z
```

## Monitor Progress

```bash
# Live log
tail -f runs/20260506T212001Z_pipeline.log

# Sample counts
wc -l data/labeled.jsonl data/rejected.jsonl

# PID alive?
ps -p 2743735 -o pid,etime,cmd

# When done, the final artifact:
ls -lh runs/20260506T212001Z/gguf/model.q4_K_M.gguf
```

## Final Artifact (the GGUF user is waiting for)

**Path:** `runs/20260506T212001Z/gguf/model.q4_K_M.gguf`

Other artifacts at the same TS:
- `runs/20260506T212001Z/gguf/model.bf16.gguf` — fp16 fallback
- `runs/20260506T212001Z/eval/report.md` — 3 backend × 4 metric × 2 split matrix
- `runs/20260506T212001Z/eval/decision.md` — go/no-go gate

## Recover from crash

The pipeline driver `scripts/run_pipeline_bg.sh` is idempotent. Each phase
checks for its outputs before running. To resume after any crash:

```bash
TS=20260506T212001Z bash scripts/run_pipeline_bg.sh
```

(Or pick a new TS to start a fresh run.)

## Time Budget

| Phase | Est. wallclock | Actual rate |
|---|---|---|
| 3 (label) | ~80 min | 30 samples/min @ 10 worker, $0.45/50 samples |
| 4a (tokenize) | ~5 min | – |
| 4b (SFT) | ~6 h | 4B QLoRA r=64, ~2700 samples × 2 epoch |
| 5 (merge+gguf) | ~15 min | – |
| 6 (eval) | ~30 min | – |
| **Total** | **~7-8 hours from now** | |

