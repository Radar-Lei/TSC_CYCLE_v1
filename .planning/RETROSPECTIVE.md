# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v4.0 — 4B 回退 + 扩展数据重训 + 标签协议修复

**Shipped:** 2026-05-11
**Phases:** 6 | **Plans:** 23 | **Tasks:** 26

### What Was Built

- Restored the project to the validated Qwen3-4B-Thinking-2507 path after the Qwen3.5-9B route proved too slow locally.
- Rebuilt the v4 Qwen3-4B dataset from v1 valid data plus v3 lint-pass extension data with protocol normalization and native-think leakage gates.
- Completed 4B QLoRA retraining, merge, GGUF fp16/q4_K_M export, tokenizer parity checks, and Phase 11 GO evaluation.
- Generated `reality_test.log` from 426 `reality.log` inputs using the Phase 11 GO q4_K_M model, with 426/426 parse/lint/protocol pass.

### What Worked

- Early Phase 7 protocol and tokenizer gates prevented more training time being spent on the wrong base model or wrong thinking tags.
- Fail-closed JSON reports made phase handoffs auditable: each downstream phase consumed an explicit upstream green artifact.
- Keeping v1 artifacts read-only preserved a stable baseline for regression decisions.

### What Was Inefficient

- The abandoned v3/9B route left documentation and verification residue that required cleanup during milestone close.
- Nyquist validation coverage was uneven: Phase 8–10 shipped with green verification evidence but missing `VALIDATION.md` files.
- Some tooling expected phase-prefixed verification filenames, while Phase 7 used a nonstandard `VERIFICATION.md` name.

### Patterns Established

- Treat model-size pivots as milestone boundaries, not as in-place phase edits.
- Make protocol labels a hard gate before dataset rebuild or training.
- Use q4_K_M as the deployment target only after comparing it against HF/fp16 and the prior shipped q4_K_M baseline.

### Key Lessons

1. On DGX Spark, the 4B route is the current practical sweet spot; larger local baselines should be justified by a separate compute plan first.
2. Dataset reuse across model families is safe only after retokenization, protocol normalization, split hashing, and leakage checks.
3. A final replay artifact like `reality_test.log` should be generated only from a GO decision artifact, not from a manually chosen checkpoint.

### Cost Observations

- Sessions: multi-session milestone with one long training/export/eval chain.
- Notable: front-loading gates saved GPU time by preventing training on known-bad protocol/base-model combinations.

---

## Milestone: v4.1 — 项目清理 / v4 最小复现包

**Shipped:** 2026-05-12
**Phases:** 4 | **Plans:** 6 | **Tasks:** 15

### What Was Built

- Built a read-only cleanup inventory and human-readable cleanup boundary report for root/data/artifacts/runs/planning/tests.
- Published repo-level `reproduction/` manifest and guide for the canonical v4.0 Qwen3-4B 9k package.
- Removed non-v4 legacy/cache clutter from the active project tree while preserving the canonical v4 model, reports, data source, and `reality_test.log`.
- Added final no-cache handoff verification proving the cleaned repository still validates the retained v4 package.

### What Worked

- Manifest-driven cleanup made it clear which paths were required, optional, obsolete, or local-only.
- Direct maintainer clarification corrected the initial over-conservative archive-in-place approach.
- No-cache/no-bytecode verification avoids recreating cache clutter while proving reproducibility.

### What Was Inefficient

- Phase 15 initially archived legacy payloads inside the project, which did not satisfy the real goal of reducing folder clutter.
- `audit-open` flagged a passed UAT file with zero pending scenarios, requiring a milestone-audit note to distinguish tooling noise from an actual blocker.

### Patterns Established

- For cleanup milestones, prefer deleting clearly non-required clutter after manifest validation instead of retaining large in-project archives.
- Reproduction handoff commands should avoid generating cache directories when the milestone goal is a clean working tree.
- Repo-level `reproduction/` files are the source of truth; `.planning/phases/` remains provenance only.

### Key Lessons

1. Clarify whether “archive” means inside the repo, outside the repo, or delete; those produce very different cleanup outcomes.
2. Optional rebuild caches should not be retained in a minimal reproduction package when deterministic source inputs remain.
3. Final cleanup verification should check both required asset presence and targeted clutter absence.

### Cost Observations

- Sessions: short cleanup/packaging milestone after v4.0 shipped.
- Notable: the main rework came from correcting cleanup policy from archive-only to direct deletion.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Key Change |
|-----------|--------|------------|
| v1.0 | 6 | Established the first complete 4B QLoRA → GGUF deployment loop |
| v2.0 | 1 executed | Identified label-protocol direction needed correction |
| v3.0 | 3 executed | Produced reusable extended data but stopped 9B local training route |
| v4.0 | 6 | Returned to 4B, reused extended data safely, and shipped q4_K_M replay artifact |
| v4.1 | 4 | Turned the shipped v4 result into a clean minimal reproduction package |

### Top Lessons

1. Keep the deployment artifact and the evaluation decision artifact coupled.
2. Preserve baseline artifacts as read-only references once a milestone ships.
3. Close each milestone with archived requirements before starting the next requirement set.
4. Cleanup milestones need explicit policy for delete vs archive, and final verification should avoid regenerating cache clutter.
