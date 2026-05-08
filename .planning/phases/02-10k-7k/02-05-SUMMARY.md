---
phase: 02-10k-7k
plan: "05"
subsystem: datagen
tags: [operational-wrapper, runbook, jsonl, checkpointing, frozen-baseline]
requires:
  - phase: 02-10k-7k
    provides: Phase 2 input reservoir, smoke/full labeler wrappers, and merge/report gate
provides:
  - Safe end-to-end Phase 2 operational wrapper with generate, smoke, full, merge, and all modes
  - Full-labeling 500-attempt chunk checkpoints before merge
  - Plain-text Phase 2 artifact contract for downstream Phase 3 consumption
affects: [02-10k-7k, DATAGEN-01, DATAGEN-02, DATAGEN-03, DATAGEN-04, DATAGEN-05, DATAGEN-06, DATAGEN-07, 03-dataset-rebuild]
tech-stack:
  added: []
  patterns:
    - shell orchestration around existing Phase 2 scripts without printing secret values
    - Python-based JSONL checkpoint counts instead of shell wc parsing
    - frozen baseline guard before and after each operational mode
key-files:
  created:
    - scripts/run_v3_phase2_all.sh
    - data/v3/phase2/README.phase2.txt
  modified: []
key-decisions:
  - "All mode intentionally stops after smoke and prints the approved full-run command instead of triggering paid labeling."
  - "Full mode labels through wrapper-controlled 500-attempt chunks and only merges after attempted/accepted targets or safe reservoir exhaustion handling."
patterns-established:
  - "Use scripts/run_v3_phase2_all.sh all for generate+smoke, then scripts/run_v3_phase2_all.sh full only after explicit operator approval."
  - "Use data/v3/phase2/README.phase2.txt as the Phase 2 artifact contract consumed by operators and Phase 3 planning."
requirements-completed: [DATAGEN-01, DATAGEN-02, DATAGEN-03, DATAGEN-04, DATAGEN-05, DATAGEN-06, DATAGEN-07]
duration: 3 min
completed: 2026-05-08
---

# Phase 02 Plan 05: Phase 2 Operational Wrapper and Artifact Contract Summary

**Safe Phase 2 run wrapper and artifact contract gating paid GPT-5.5 full labeling behind smoke approval and 500-attempt checkpoints**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-08T15:49:39Z
- **Completed:** 2026-05-08T15:52:55Z
- **Tasks:** 2 non-live tasks completed; Task 3 remains a paid human-verification checkpoint
- **Files modified:** 2

## Accomplishments

- Added `scripts/run_v3_phase2_all.sh` with explicit `generate`, `smoke`, `full`, `merge`, and `all` modes.
- Made `all` mode safe by running only generate and smoke, then stopping with an instruction to rerun `full` after approval.
- Implemented `full` mode as a wrapper-controlled 500-attempt chunk loop with old SHA, accepted/rejected/attempted totals, reject-rate, duplicate-ID, malformed-line, append-file, and worker-cap checks.
- Added `data/v3/phase2/README.phase2.txt` listing required Phase 2 artifacts and downstream Phase 3 consumption rules.
- Preserved the frozen baseline guard with `git diff --quiet -- data/labeled.jsonl` before and after operational modes.

## Task Commits

Each non-live task was committed atomically:

1. **Task 1: Add end-to-end Phase 2 orchestrator with safe checkpoints** - `83f59ce` (feat)
2. **Task 2: Add Phase 2 artifact contract text file** - `e0ce198` (docs)

**Plan metadata:** committed after this summary.

## Files Created/Modified

- `scripts/run_v3_phase2_all.sh` - End-to-end operational wrapper for Phase 2 safe modes and full-run chunk checkpointing.
- `data/v3/phase2/README.phase2.txt` - Plain-text artifact contract naming required Phase 2 outputs and downstream rules.

## Decisions Made

- Did not run paid full labeling in this execution; the plan and user instructions require stopping before live full spend unless explicit approval is given.
- Kept the existing smoke/full/merge scripts as primitives and added chunk checkpoint enforcement in the new wrapper.
- Used Python snippets for line/count/checkpoint evidence to avoid brittle shell `wc` parsing.

## Deviations from Plan

None - non-live plan tasks executed exactly as written.

**Total deviations:** 0 auto-fixed.
**Impact on plan:** No scope change.

## Issues Encountered

- The execution environment initially exposed a temporary worktree, while the user requested the main working tree. Work was performed and committed in `/home/samuel/TSC_CYCLE` as requested.
- Existing unrelated Phase 1 modifications and untracked smoke artifacts were left unstaged/uncommitted.

## Verification

- `bash -n /home/samuel/TSC_CYCLE/scripts/run_v3_phase2_all.sh` passed.
- `test -f /home/samuel/TSC_CYCLE/data/v3/phase2/README.phase2.txt` passed.
- `grep -v '^#' /home/samuel/TSC_CYCLE/data/v3/phase2/README.phase2.txt | grep -c 'data/labeled.jsonl is frozen'` returned `1`.
- Acceptance checks confirmed the wrapper contains modes `generate`, `smoke`, `full`, `merge`, and `all`.
- Acceptance checks confirmed `all` mode does not call `run_v3_phase2_label_full.sh` and instead prints a rerun-with-`full` approval instruction.
- Acceptance checks confirmed the wrapper runs `git diff --quiet -- data/labeled.jsonl`, contains `CHUNK_SIZE=500`, and includes checkpoint checks for accepted/rejected/attempted totals, reject rate, duplicate IDs, worker cap, append files, and unchanged old SHA.
- Acceptance checks confirmed the artifact contract contains `Phase 3 consumes only data/v3/phase2/labeled_merged.jsonl`, `lint-failed samples are discarded, not regenerated`, and `checkpointed every 500 attempted samples`.
- `git diff --quiet -- data/labeled.jsonl` passed; the frozen baseline was not mutated.

## Known Stubs

None. Stub-pattern scan of files created by this plan found no TODO/FIXME/placeholders or hardcoded empty UI values.

## Threat Flags

None. The security-relevant surfaces in this plan are operational wrapper logs, paid API spend gating, and frozen-baseline guards; all are covered by the plan threat model and mitigated by not echoing secrets, stopping `all` before full paid labeling, enforcing worker cap checks, and rechecking `data/labeled.jsonl`.

## Auth Gates

None during non-live execution. Full labeling still requires `OPENAI_API_KEY` in the operator shell and explicit approval after smoke.

## User Setup Required

- Review smoke outputs before any paid full run.
- Export or source `OPENAI_API_KEY` locally before running `/home/samuel/TSC_CYCLE/scripts/run_v3_phase2_all.sh full`.
- Do not paste API keys into chat or commit them to files.

## Checkpoint / Live Run Status

Task 3 is intentionally not executed here because it requires paid full GPT-5.5 labeling and human approval. The created wrapper/runbook is ready for that future checkpoint.

## Next Phase Readiness

Phase 2 non-live operational wrapper and artifact contract are complete. After explicit full-run approval and successful `merge_report.json`, Phase 3 should consume only `data/v3/phase2/labeled_merged.jsonl`.

## Self-Check: PASSED

- Found `/home/samuel/TSC_CYCLE/scripts/run_v3_phase2_all.sh`.
- Found `/home/samuel/TSC_CYCLE/data/v3/phase2/README.phase2.txt`.
- Found task commits `83f59ce` and `e0ce198` in git log.
- Verified wrapper syntax, artifact contract strings, and frozen `data/labeled.jsonl` diff guard.

---
*Phase: 02-10k-7k*
*Completed: 2026-05-08*
