# TSC-CYCLE State

**Last Activity:** 2026-05-07
**Current Milestone:** v1.0
**Status:** Pipeline scaffolded; Phases 1-2 executed; Phases 3-6 scripted, awaiting OPENAI_API_KEY

## Phase Status

| Phase | Status | Notes |
|---|---|---|
| 1. Environment + Foundations | ✓ executed | venv + foundation modules + dist_prior + 24/24 tests |
| 2. Synthetic Data Generation | ✓ executed | 2700 + 300 inputs, KS report passes |
| 3. Teacher Labeling | ⏸ blocked | Script ready: `tsc_cycle/teacher/labeler.py`. Needs `OPENAI_API_KEY` |
| 4. Dataset + QLoRA SFT | ⏸ blocked on P3 | Script ready: `tsc_cycle/student/{dataset.py,train.py}` |
| 5. Merge + GGUF Export | ⏸ blocked on P4 | Script ready: `tsc_cycle/student/export_gguf.py` |
| 6. Evaluation Suite | ⏸ blocked on P5 | Script ready: `tsc_cycle/eval/run_eval.py` |

## Resume

```bash
export OPENAI_API_KEY=sk-...
bash scripts/run_pipeline.sh
```

The driver `scripts/run_pipeline.sh` is idempotent — each phase only runs if its outputs are missing.

## Outputs

- Final GGUF: `runs/<TS>/gguf/model.q4_K_M.gguf`
- Eval report: `runs/<TS>/eval/report.md`
- Decision: `runs/<TS>/eval/decision.md`
