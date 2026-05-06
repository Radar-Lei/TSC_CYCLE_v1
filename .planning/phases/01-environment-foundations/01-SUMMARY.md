# Phase 1 SUMMARY — Environment + Foundations

**Status:** Mostly complete (1 gate pending OPENAI_API_KEY)
**Date:** 2026-05-07

## Outcomes

| Requirement | Status | Evidence |
|---|---|---|
| ENV-01 venv clone + scripts injected | ✓ | `.venv/`、`scripts/dgx_spark/{env.sh,verify.py,run_safe.sh}` |
| ENV-02 verify.py 全绿 | ✓ | `python scripts/dgx_spark/verify.py` → "OK: DGX Spark training environment is ready" |
| ENV-03 flash_attn ImportError | ✓ | verify 输出 `flash_attn installed: False` |
| ENV-04 增量包 pin | ✓ | `pyproject.toml` + `uv pip install` 落 trl 1.3.0 / peft 0.19.1 / bnb 0.48.0 / openai 2.34.0 |
| ENV-05 run_safe.sh 包裹 | ✓ | `scripts/dgx_spark/run_safe.sh` 来自 dgx-spark-training skill |
| FND-01 prompt_builder 单一来源 | ✓ | `tsc_cycle/prompt_builder.py`，与 reality.log 字面一致 |
| FND-02 constraint_lint | ✓ | `tsc_cycle/constraint_lint.py` + 11 tests pass |
| FND-03 tokenizer_check | ✓ | `tsc_cycle/tokenizer_check.py`；Qwen3-4B-Thinking-2507 实测：自定义标签 3-5 sub-tokens，原生 `<think>=151667`/`</think>=151668` 单 token |
| FND-04 hashing | ✓ | `tsc_cycle/hashing.py` + 6 tests pass |
| FND-05 manifest | ✓ | `tsc_cycle/manifest.py`（git_sha + config_hash + stage 状态） |
| FND-06 单元测试 | ✓ | `pytest tests/` → 24/24 pass |
| DGEN-01 dist_prior | ✓ | `data/dist_prior.json`（n_prompts=426, n_crossings=2, phase_count={3:90,4:271,5:65}） |
| 5-prompt teacher smoke | ⏸ | `scripts/teacher_smoke.py` ready；阻塞于 `OPENAI_API_KEY` 未设置 |

## Files Created

```
pyproject.toml
tsc_cycle/__init__.py
tsc_cycle/hashing.py
tsc_cycle/prompt_builder.py
tsc_cycle/constraint_lint.py
tsc_cycle/tokenizer_check.py
tsc_cycle/manifest.py
tsc_cycle/distribution_fit.py
tsc_cycle/teacher/__init__.py
tsc_cycle/teacher/client.py
tests/__init__.py
tests/test_hashing.py
tests/test_constraint_lint.py
tests/test_prompt_builder.py
scripts/teacher_smoke.py
scripts/dgx_spark/{env.sh, verify.py, run_safe.sh}  # via skill
data/dist_prior.json
```

## Open Items / Carry-over

- **TCH smoke test**: 待 `OPENAI_API_KEY` 设置后跑：
  ```bash
  source scripts/dgx_spark/env.sh
  PYTHONPATH=. python scripts/teacher_smoke.py --n 5
  ```
- 版本漂移记录：transformers 5.8.0 / trl 1.3.0（CLAUDE.md 锚点 4.56.2 / 0.22.2 已过时；Phase 4 训练入口需用 TRL 1.x API 写）
