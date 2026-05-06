# Phase 3 SUMMARY — Teacher Labeling

**Status:** Running in background.

## Endpoint
- Provider: OpenAI Responses API via codex proxy `http://148.135.118.86:8080/v1`
- Model: `gpt-5.5`
- Reasoning: `effort="high"`
- Auth: `OPENAI_API_KEY` from `.codex/auth.json`

## Smoke (50 samples)
- 50/50 success (0 reject)
- avg reasoning_tokens=665 (≥100 gate ✓)
- elapsed 1.9 min @ 10 workers
- ~$0.45 input/output combined

## Full run config
- workers=10, model=gpt-5.5, effort=high
- cache: `raw_responses/{prompt_hash}.json` (atomic rename, resume-safe)
- gate: drop responses with reasoning_tokens<100 (TCH-02 silent-downcast detection)

## Files
- `tsc_cycle/teacher/client.py` — Responses API client (rewritten from chat.completions)
- `tsc_cycle/teacher/labeler.py` — concurrent + resume-safe + reject_stats
- `.env` — `OPENAI_API_KEY` + `OPENAI_BASE_URL` (gitignored)
