---
phase: 02
slug: 10k-7k
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-08
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 |
| **Config file** | `pyproject.toml` (`testpaths=["tests"]`, `addopts="-q"`) |
| **Quick run command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_hashing.py tests/test_constraint_lint.py tests/test_prompt_builder.py` |
| **Full suite command** | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q` |
| **Estimated runtime** | ~30-120 seconds, excluding live OpenAI labeling |

---

## Sampling Rate

- **After every task commit:** Run the focused pytest file(s) touched by that task plus the quick command above.
- **After every plan wave:** Run `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q`.
- **Before full API run:** Run a 50-sample smoke with isolated output/cache and verify no `data/labeled.jsonl` SHA change.
- **During full API run:** Checkpoint every 500 attempted samples: workers ≤10, append files grow, reject rate is reported, and old SHA remains unchanged.
- **Before `/gsd-verify-work`:** Full suite and Phase 2 manifest gates must be green.
- **Max feedback latency:** <120 seconds for automated code tests; API labeling checkpoints are long-running operational gates.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-W0-01 | Wave 0 tests | 0 | DATAGEN-01 | — | N/A | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_datagen_inputs.py::test_three_source_reservoir_counts` | ❌ W0 | ⬜ pending |
| 02-W0-02 | Wave 0 tests | 0 | DATAGEN-01 | — | N/A | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_datagen_inputs.py::test_targeted_seed_provenance` | ❌ W0 | ⬜ pending |
| 02-W0-03 | Wave 0 tests | 0 | DATAGEN-02 | T-02-baseline-tamper | Baseline IDs are excluded from new reservoir | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_datagen_inputs.py::test_no_overlap_with_v1_labeled` | ❌ W0 | ⬜ pending |
| 02-W0-04 | Wave 0 tests | 0 | DATAGEN-03 | T-02-api-key | Does not log or persist API key; workers are capped | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_labeler.py::test_workers_capped_and_effort_high` | ❌ W0 | ⬜ pending |
| 02-W0-05 | Wave 0 tests | 0 | DATAGEN-04 | T-02-malformed-output | Invalid teacher outputs are rejected, not accepted or retried | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_labeler.py::test_lint_failure_dropped_not_retried` | ❌ W0 | ⬜ pending |
| 02-W0-06 | Wave 0 tests | 0 | DATAGEN-05 | T-02-budget-replay | Done IDs are skipped on resume to avoid duplicate API calls | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_labeler.py::test_resume_skips_done_ids` | ❌ W0 | ⬜ pending |
| 02-W0-07 | Wave 0 tests | 0 | DATAGEN-06 | — | N/A | integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_datagen_merge.py::test_merged_valid_count_gate` | ❌ W0 | ⬜ pending |
| 02-W0-08 | Wave 0 tests | 0 | DATAGEN-07 | T-02-baseline-tamper | `data/labeled.jsonl` bytes remain unchanged | integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_datagen_merge.py::test_v1_labeled_sha_unchanged` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_v3_datagen_inputs.py` — stubs and fixtures for DATAGEN-01/02 reservoir ratios, targeted provenance, and dedupe.
- [ ] `tests/test_v3_labeler.py` — stubs and mock teacher client coverage for DATAGEN-03/04/05.
- [ ] `tests/test_v3_datagen_merge.py` — stubs and fixtures for DATAGEN-06/07 merge and SHA invariants.
- [ ] `tests/conftest.py` — shared mini v1 labeled records, mini per-sample eval rows, and fake teacher outputs if reusable fixtures are not already present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `OPENAI_API_KEY` availability before live labeling | DATAGEN-03 | Secret presence cannot be committed or mocked for the real run | User exports `OPENAI_API_KEY`; executor checks presence without printing value before live smoke/full run. |
| 50-sample live GPT-5.5 high smoke | DATAGEN-03, DATAGEN-04, DATAGEN-05 | Requires paid external API and real rate-limit behavior | Run isolated 50-sample labeler command; inspect reject stats, cache writes, append files, and old SHA report before full run. |
| Full ≥7K live labeling | DATAGEN-03, DATAGEN-06 | Long-running paid external API operation | Run with workers ≤10 and checkpoint every 500 attempted samples; stop for user decision if reserve exhausts before ≥6000 new valid. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency <120s for local automated checks
- [ ] `nyquist_compliant: true` set in frontmatter after Wave 0 tests are implemented and mapped

**Approval:** pending
