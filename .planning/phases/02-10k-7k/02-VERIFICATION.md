---
phase: 02-10k-7k
verified: 2026-05-08T16:29:01Z
status: gaps_found
score: 5/8 must-haves verified
overrides_applied: 0
gaps:
  - truth: "GPT-5.5 high full labeling completed for at least 7K new Phase 2 inputs"
    status: failed
    reason: "Only 50-sample smoke artifacts exist; full labeled_new.jsonl and rejected_new.jsonl are missing, so there is no evidence of >=7K attempted/completed new labels."
    artifacts:
      - path: "data/v3/phase2/labeled_new.jsonl"
        issue: "Missing full accepted-label JSONL"
      - path: "data/v3/phase2/rejected_new.jsonl"
        issue: "Missing full rejected-label JSONL"
    missing:
      - "Run human-approved full Phase 2 labeling against data/v3/phase2/inputs_all.jsonl with GPT-5.5 high."
      - "Produce append-only data/v3/phase2/labeled_new.jsonl and data/v3/phase2/rejected_new.jsonl with >=7000 attempted new samples and source coverage."
  - truth: "Final merged dataset contains at least 9000 valid samples after hard-constraint lint"
    status: failed
    reason: "Merge gate cannot pass without full new labels; labeled_merged.jsonl and merge_report.json are missing, and an attempted merge reports new_valid=0 and merged_valid=3000."
    artifacts:
      - path: "data/v3/phase2/labeled_merged.jsonl"
        issue: "Missing final merged dataset"
      - path: "data/v3/phase2/merge_report.json"
        issue: "Missing final merge report"
    missing:
      - "After full labeling, run scripts/run_v3_phase2_merge.sh or scripts/run_v3_phase2_all.sh full."
      - "Produce merge_report.json with ok=true, new_valid>=6000, merged_valid>=9000, old_new_overlap=0, all_new_lint_ok=true."
  - truth: "Full-run checkpoint evidence exists for each 500 attempted samples through completion"
    status: failed
    reason: "The checkpointing wrapper exists, but no full-run checkpoint outputs or final merge evidence exist because full labeling was not run."
    artifacts:
      - path: "scripts/run_v3_phase2_all.sh"
        issue: "Wrapper implements chunk checks, but runtime checkpoint evidence is absent"
    missing:
      - "Run full mode after explicit approval and retain/inspect checkpoint output for old SHA, workers<=10, counts, reject rate, and duplicate IDs."
---

# Phase 2: 数据扩量到 10K（教师只标新增 7K） Verification Report

**Phase Goal:** 在不动 v1.0 `data/labeled.jsonl` 字节的前提下，扩展合成输入分布、用 GPT-5.5 high 并发标注新增 ≥7K 输入，过硬约束 lint 后与 v1.0 合并得到 ≥9000 valid 训练集。
**Verified:** 2026-05-08T16:29:01Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 三源输入 reservoir 已生成，且 >=7K、去重、与 v1.0 不重叠 | VERIFIED | `data/v3/phase2/inputs_all.jsonl` 存在 7500 行；source counts 为 `same_dist=5250`, `ood=1500`, `targeted=750`；unique IDs=7500；old overlap=0；`datagen_manifest.json` 记录 overlap=0、self_duplicate_count=0。 |
| 2 | 生成器/包装器保持 v1.0 `data/labeled.jsonl` 字节不变 | VERIFIED | `git diff --quiet -- data/labeled.jsonl` 返回 0；当前 SHA 为 `2214301555f22640e542234abcd9c5f0e3f6982df08c894124af45367ad30809`，与 manifest before/after 相同。 |
| 3 | Labeler 实现支持 GPT-5.5 high、worker<=10、append JSONL、resume skip、lint-drop | VERIFIED | `tsc_cycle/teacher/labeler.py` 有 `build_parser`/`run_labeling`，`--model gpt-5.5`、`--effort high` 默认，`_worker_count` 拒绝 >10，读 labeled/rejected/exclude done IDs 后再提交；`tests/test_v3_labeler.py` 通过。 |
| 4 | 50-sample smoke 证明 live API 路径可用 | VERIFIED | `labeled_new.smoke.jsonl` 47 行，`rejected_new.smoke.jsonl` 3 行；抽样 accepted 记录含 `model=gpt-5.5` 和 `reasoning.effort=high`，且 result solution 通过 labeler lint gate 后写入。 |
| 5 | GPT-5.5 high full labeling completed for at least 7K new Phase 2 inputs | FAILED | `data/v3/phase2/labeled_new.jsonl` 与 `data/v3/phase2/rejected_new.jsonl` 均不存在；只有 smoke 50 样本，不满足 roadmap “标注新增 >=7K 输入”。 |
| 6 | Full accepted outputs are re-linted and failed outputs discarded, with final new_valid>=6000 | FAILED | Merge gate dry-run失败：missing full JSONL, `new_valid=0`, `source_attempted_counts={}`；代码机制存在但无全量数据证据。 |
| 7 | Final merged dataset exists with >=9000 valid samples | FAILED | `data/v3/phase2/labeled_merged.jsonl` 和 `data/v3/phase2/merge_report.json` 不存在；merge dry-run显示 `merged_valid=3000 < 9000`。 |
| 8 | Operational wrapper protects full paid run with approval stop and 500-attempt checkpoints | VERIFIED | `scripts/run_v3_phase2_all.sh` has modes `generate/smoke/full/merge/all`; `all` stops after smoke; `full` uses `CHUNK_SIZE=500`, checks old SHA, workers, accepted/rejected/attempted, reject rate, duplicate IDs, append files, and source coverage before merge. Runtime evidence still absent because full run was not executed. |

**Score:** 5/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tsc_cycle/sample_inputs.py` | Three-source reservoir builder and CLI | VERIFIED | `build_v3_phase2_reservoir` exists and is exercised by tests. |
| `scripts/generate_v3_phase2_inputs.sh` | Reproducible reservoir generation wrapper | VERIFIED | Uses `${PYTHON} -m tsc_cycle.sample_inputs --v3-phase2`; syntax passes; generated artifacts exist. |
| `data/v3/phase2/inputs_all.jsonl` | >=7000 new input reservoir | VERIFIED | 7500 records, zero self duplicates, zero old overlap. |
| `data/v3/phase2/datagen_manifest.json` | Source counts and SHA evidence | VERIFIED | Counts and SHA fields present and green. |
| `tsc_cycle/teacher/labeler.py` | Phase 2-safe labeler | VERIFIED | Worker cap, high effort, cache-dir, protected output, resume and lint-drop present. |
| `scripts/run_v3_phase2_label_smoke.sh` | 50-sample smoke wrapper | VERIFIED | Uses `--limit 50`, workers 5, isolated paths, baseline diff guard. |
| `scripts/run_v3_phase2_label_full.sh` | Full labeling wrapper | VERIFIED | Uses workers 10, isolated full paths, baseline diff guard. |
| `tsc_cycle/v3_gates/phase2_datagen_report.py` | Fail-closed merge/report gate | VERIFIED | Exports `build_phase2_report`/`main`, validates accepted new labels and thresholds. |
| `scripts/run_v3_phase2_merge.sh` | Merge wrapper | VERIFIED | Uses min-new-valid 6000, min-merged-valid 9000, old baseline path, diff guard. |
| `data/v3/phase2/labeled_new.jsonl` | Full accepted new labels | MISSING | Blocking gap. |
| `data/v3/phase2/rejected_new.jsonl` | Full rejected new labels | MISSING | Blocking gap. |
| `data/v3/phase2/labeled_merged.jsonl` | Phase 3 raw merged dataset | MISSING | Blocking gap. |
| `data/v3/phase2/merge_report.json` | Final Phase 2 evidence report | MISSING | Blocking gap. |
| `scripts/run_v3_phase2_all.sh` | Operational orchestrator | VERIFIED | Implements safe all/full behavior and chunk checks. |
| `data/v3/phase2/README.phase2.txt` | Artifact contract | VERIFIED | Lists required artifacts and frozen baseline contract. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/generate_v3_phase2_inputs.sh` | `tsc_cycle/sample_inputs.py` | Python module invocation | VERIFIED | Manual check: lines 7-8 use `${PYTHON} -m tsc_cycle.sample_inputs --v3-phase2`. SDK pattern was too literal because it expected `python -m` text. |
| `tsc_cycle/sample_inputs.py` | `data/labeled.jsonl` | exclude-labeled read-only identity set | VERIFIED | `_old_ids_from_labeled` reads old IDs; v3 CLI uses `--exclude-labeled`; outputs under `data/v3/phase2`. |
| `tsc_cycle/teacher/labeler.py` | `TeacherClient` | cache_dir and reasoning_effort args | VERIFIED | `client_factory(model=args.model, reasoning_effort=args.effort, cache_dir=Path(args.cache_dir))`. |
| `tsc_cycle/teacher/labeler.py` | `constraint_lint.validate` | accept/reject gate | VERIFIED | `validate(s, res.solution or {})` before accepted append. |
| `phase2_datagen_report.py` | `constraint_lint.validate` | all accepted new records revalidated | VERIFIED | Each new row is validated before `valid_new_rows`. |
| `run_v3_phase2_merge.sh` | `data/labeled.jsonl` | read-only old labels path | VERIFIED | Uses `--old-labeled data/labeled.jsonl` plus before/after git diff guard. |
| `run_v3_phase2_all.sh` | `run_v3_phase2_label_full.sh` | full labeling step | VERIFIED_WITH_ALTERNATIVE | Frontmatter link names the full wrapper, but actual orchestrator directly calls `python -m tsc_cycle.teacher.labeler` in 500-attempt chunks. This matches plan task text allowing wrapper-controlled chunks via the underlying labeler and is not a goal blocker. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `inputs_all.jsonl` | Reservoir rows | `build_v3_phase2_reservoir` from prior + OOD mutations + targeted eval seeds | Yes | FLOWING |
| `labeled_new.smoke.jsonl` | Accepted smoke labels | `run_v3_phase2_label_smoke.sh` -> labeler -> `TeacherClient` | Yes, 47 accepted smoke rows | FLOWING_SMOKE_ONLY |
| `labeled_new.jsonl` | Full accepted labels | Full labeler run | No artifact | DISCONNECTED/MISSING |
| `labeled_merged.jsonl` | Old + new valid rows | `build_phase2_report` | No artifact because full new labels missing | DISCONNECTED/MISSING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 2 unit tests | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q tests/test_v3_datagen_inputs.py tests/test_v3_labeler.py tests/test_v3_datagen_merge.py` | 17 passed | PASS |
| Script syntax | `bash -n` on all Phase 2 scripts | all passed | PASS |
| Reservoir count/overlap | Python JSONL count script | 7500 rows, counts 5250/1500/750, unique 7500, old overlap 0 | PASS |
| Merge gate with current artifacts | `python -m tsc_cycle.v3_gates.phase2_datagen_report ...` | exit 1; missing `labeled_new.jsonl`/`rejected_new.jsonl`, `new_valid=0`, `merged_valid=3000` | FAIL_EXPECTED_GAP |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| DATAGEN-01 | 02-01, 02-02, 02-04, 02-05 | 三类合成输入分布 | SATISFIED | 7500 reservoir contains same_dist=5250, ood=1500, targeted=750; targeted provenance implemented. |
| DATAGEN-02 | 02-01, 02-02, 02-04, 02-05 | >=7K new inputs, no v1 overlap | SATISFIED | inputs_all has 7500 unique sample IDs, old overlap 0. |
| DATAGEN-03 | 02-01, 02-03, 02-04, 02-05 | GPT-5.5 high, worker<=10, retry/client behavior | PARTIAL | Code/wrappers/smoke prove mechanism and 50-sample path; full >=7K labeling not completed. |
| DATAGEN-04 | 02-01, 02-03, 02-04, 02-05 | Lint pass accepted, failures discarded not regenerated | PARTIAL | Labeler and merge gate implement lint/drop; smoke has accepted/rejected artifacts; no full output to prove final all-new lint pass. |
| DATAGEN-05 | 02-01, 02-03, 02-04, 02-05 | JSONL append resume no duplicate calls | PARTIAL | Unit tests and code prove mechanism; no full-run append artifacts/checkpoints exist. |
| DATAGEN-06 | 02-01, 02-04, 02-05 | v1 valid ∪ new lint-pass, >=9000 valid | BLOCKED | `labeled_merged.jsonl` and `merge_report.json` missing; dry-run `merged_valid=3000`. |
| DATAGEN-07 | 02-01, 02-04, 02-05 | v1 data bytes unchanged | SATISFIED | `git diff --quiet -- data/labeled.jsonl` returns 0; SHA unchanged. |

No orphaned Phase 2 DATAGEN IDs were found in `.planning/REQUIREMENTS.md`; all DATAGEN-01..07 appear in plan frontmatter and are accounted for above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `tsc_cycle/teacher/labeler.py` | 25 | “placeholder estimate” cost comment | INFO | Cost estimate only; does not affect labeling correctness, lint, or resume safety. |
| `tsc_cycle/v3_gates/phase2_datagen_report.py` | 38-53, 138 | Empty return values for missing/malformed artifacts | INFO | Fail-closed error handling; not a stub because fatal failures are recorded and CLI exits nonzero. |

### Human Verification Required

Because status is already `gaps_found`, these are follow-up checks after the blocking gaps are closed:

1. **Approve and observe paid full labeling**
   - **Test:** Run `/home/samuel/TSC_CYCLE/scripts/run_v3_phase2_all.sh full` only after smoke approval and with `OPENAI_API_KEY` exported.
   - **Expected:** Every 500-attempt checkpoint reports unchanged old SHA, workers<=10, monotonic accepted/rejected counts, zero duplicate IDs, and understandable reject rate.
   - **Why human:** Paid external API execution and budget approval cannot be automated by verification.

2. **Inspect final merge report**
   - **Test:** Open `/home/samuel/TSC_CYCLE/data/v3/phase2/merge_report.json` after full run.
   - **Expected:** `ok=true`, `new_valid>=6000`, `merged_valid>=9000`, `old_new_overlap=0`, `all_new_lint_ok=true`, DATAGEN-01..07 covered, worker cap true, duplicate done IDs zero.
   - **Why human:** Requires post-paid-run artifact review and operational decision if reject rate exhausts reservoir.

### Gaps Summary

The implementation and smoke path are substantial: reservoir generation, labeler safety, smoke artifacts, merge gate, and operational wrapper all exist and are wired. However the roadmap goal is not merely “wrappers exist”; it requires actual GPT-5.5 high labeling of >=7K new inputs and a final >=9000 valid merged dataset. Those full-run artifacts are absent, and the fail-closed merge gate correctly fails with `new_valid=0` and `merged_valid=3000`. Phase 2 must not be treated as achieved until the paid full run and final merge report are completed.

---

_Verified: 2026-05-08T16:29:01Z_
_Verifier: Claude (gsd-verifier)_
