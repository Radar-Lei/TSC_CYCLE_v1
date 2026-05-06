# Phase 3 SUMMARY — Teacher Labeling (script-ready)

**Status:** Script ready; awaiting `OPENAI_API_KEY` to execute.

## Implementation
- `tsc_cycle/teacher/client.py` — GPT-5.5 high client (structured + plain fallback, indexponential retry, RateLimit honoring Retry-After, content-addressed cache, reasoning_tokens > 100 gate per TCH-02)
- `tsc_cycle/teacher/labeler.py` — concurrent (≤10 worker), resume-safe (reads existing labeled+rejected sample_ids), validates each via `constraint_lint`, writes labeled.jsonl / rejected.jsonl / cost.json / reject_stats.json
- `scripts/teacher_smoke.py` — 5-prompt warmup with 3000-sample budget extrapolation

## Run
```bash
export OPENAI_API_KEY=sk-...
source scripts/dgx_spark/env.sh
PYTHONPATH=. python -m tsc_cycle.teacher.labeler --limit 50  # smoke first
PYTHONPATH=. python -m tsc_cycle.teacher.labeler              # full
```
