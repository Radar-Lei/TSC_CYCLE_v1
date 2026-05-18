# Roadmap: TSC-CYCLE

## Overview

v4.2 repairs the low-saturation max-green failure observed in the latest v4.0 4B model outputs. The milestone first makes the failure measurable and gates it offline, then rebuilds calibrated training data without changing the final deployment system/inference prompt, retrains the existing Qwen3-4B QLoRA route, exports merged HF and GGUF artifacts, and finishes with a new gated `reality_test.log` replay.

## Milestones

- Shipped: **v1.0 Initial 4B Distillation Pipeline** — shipped 2026-05-07; archived in `milestones/v1.0-ROADMAP.md`
- Abandoned: **v2.0 Label Migration** — abandoned 2026-05-08; archived in `.planning/milestones/v2.0-abandoned/`
- Stopped: **v3.0 Qwen3.5-9B Route** — stopped 2026-05-10 after Phase 1–3; 9B local training was too slow
- Shipped: **v4.0 4B 回退 + 扩展数据重训 + 标签协议修复** — Phases 7–12 shipped 2026-05-11; archived in `milestones/v4.0-ROADMAP.md`
- Shipped: **v4.1 项目清理 / v4 最小复现包** — Phases 13–16 shipped 2026-05-12; archived in `milestones/v4.1-ROADMAP.md`
- Planned: **v4.2 饱和度-绿灯策略校准 / 教师标签重建** — Phases 17–20

## Phases

<details>
<summary>v4.0 4B 回退 + 扩展数据重训 + 标签协议修复 (Phases 7–12) — SHIPPED 2026-05-11</summary>

- [x] Phase 7: 4B baseline/label protocol gate (4/4 plans) — completed 2026-05-10
- [x] Phase 8: v3 扩展数据 → 4B dataset rebuild (4/4 plans) — completed 2026-05-10
- [x] Phase 9: 4B QLoRA retrain (4/4 plans) — completed 2026-05-11
- [x] Phase 10: merge + GGUF export (4/4 plans) — completed 2026-05-11
- [x] Phase 11: eval matrix + decision (4/4 plans) — completed 2026-05-11
- [x] Phase 12: reality.log → reality_test.log replay (3/3 plans) — completed 2026-05-11

Full details: `milestones/v4.0-ROADMAP.md`

</details>

<details>
<summary>v4.1 项目清理 / v4 最小复现包 (Phases 13–16) — SHIPPED 2026-05-12</summary>

- [x] Phase 13: Inventory & Cleanup Boundaries (2/2 plans) — completed 2026-05-12
- [x] Phase 14: Canonical v4 Reproduction Package (1/1 plan) — completed 2026-05-12
- [x] Phase 15: Safe Cleanup Execution (2/2 plans) — completed 2026-05-12
- [x] Phase 16: Verification & Handoff (1/1 plan) — completed 2026-05-12

Full details: `milestones/v4.1-ROADMAP.md`

</details>

- [x] **Phase 17: Audit & Saturation Policy Gate** - Quantify existing low-saturation max-green failures and establish the offline saturation gate without changing deployment prompts.
- [ ] **Phase 18: Calibrated Dataset Rebuild** - Filter or relabel v4 examples into a calibrated v4.2 training dataset with reproducible reports and splits.
- [ ] **Phase 19: 4B QLoRA Retrain & Export** - Retrain the existing Qwen3-4B QLoRA route and export merged HF plus fp16/q4_K_M GGUF artifacts.
- [ ] **Phase 20: Evaluation & Reality Replay Handoff** - Evaluate v4.2 against hard constraints, output protocol, saturation policy, and produce a new gated `reality_test.log`.

## Phase Details

### Phase 17: Audit & Saturation Policy Gate

**Goal**: Maintainer can measure the saturation/green mismatch, inspect representative failures, and run an offline policy gate that protects data, evaluation, and replay outputs while preserving the unchanged v4 deployment prompt protocol.
**Depends on**: Phase 16
**Requirements**: AUDIT-01, AUDIT-02, POLICY-01, POLICY-02, POLICY-03
**Success Criteria** (what must be TRUE):

  1. Maintainer can generate banded statistics showing how often v4 teacher labels set `final == max_green` when `pred_saturation < 1.0`, broken down by saturation band, split, and source.
  2. Maintainer can inspect representative failure examples from both `data/v4/phase8/labeled_merged.jsonl` and `reality_test.log` with sample id, phase id, saturation, min/max green, final green, and violation category.
  3. Maintainer can run a saturation policy gate that classifies phase decisions into the intended saturation bands and fails outputs that exceed configured low-saturation max-green thresholds.
  4. Maintainer can verify that final deployment system/inference prompts remain byte-for-byte aligned with the v4 inference protocol and do not explicitly include the saturation band rule.

**Plans**: 2 plans
Plans:
**Wave 1**

- [x] 17-01-PLAN.md — Build canonical saturation classifier, per-phase projectors, banded audit statistics, and representative examples.

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 17-02-PLAN.md — Add safe offline CLI/report gate, configured threshold failures, and v4 prompt protocol guard.

### Phase 18: Calibrated Dataset Rebuild

**Goal**: Maintainer can build and review a calibrated v4.2 dataset that removes or repairs saturation-policy violations while preserving protocol format, hard constraints, provenance, hashes, and deterministic splits.
**Depends on**: Phase 17
**Requirements**: DATA-01, DATA-02
**Success Criteria** (what must be TRUE):

  1. Maintainer can rebuild the v4.2 training dataset from v4 sources with violating examples either rejected or relabelled according to the offline saturation policy gate.
  2. Maintainer can confirm rebuilt examples preserve the required `<start_working_out>...</end_working_out><SOLUTION>...</SOLUTION>` protocol and all hard constraints.
  3. Maintainer can review a reconstruction report showing source counts, rejected/relabelled counts, policy-pass rates, hard-constraint pass rates, dataset hashes, and split artifacts.

**Plans**: TBD

### Phase 19: 4B QLoRA Retrain & Export

**Goal**: Maintainer can retrain the latest 4B student on the calibrated v4.2 dataset using the existing DGX Spark-safe QLoRA stack, then export reproducible merged HF and GGUF artifacts.
**Depends on**: Phase 18
**Requirements**: TRAIN-01, TRAIN-02
**Success Criteria** (what must be TRUE):

  1. Maintainer can launch v4.2 QLoRA SFT for `Qwen/Qwen3-4B-Thinking-2507` through the existing DGX Spark-safe stack without introducing a new base model or training framework.
  2. Maintainer can inspect the training report and confirm it references the calibrated v4.2 dataset, expected protocol, and reproducible run paths.
  3. Maintainer can export the calibrated adapter into merged HF, GGUF fp16, and GGUF q4_K_M artifacts with recorded paths, hashes, and export reports.

**Plans**: TBD

### Phase 20: Evaluation & Reality Replay Handoff

**Goal**: Maintainer can decide whether v4.2 is better than v4.0 by evaluating hard constraints, output protocol, saturation policy behavior, and a new `reality.log` replay without rewarding reproduction of bad teacher labels.
**Depends on**: Phase 19
**Requirements**: EVAL-01, EVAL-02, EVAL-03
**Success Criteria** (what must be TRUE):

  1. Maintainer can evaluate the calibrated model with hard-constraint, parse/lint, protocol, and saturation policy gates while the old teacher-MAE metric is demoted or replaced.
  2. Maintainer can replay `reality.log` with the calibrated q4_K_M GGUF model and generate a new `reality_test.log` that passes parse, lint, protocol, and saturation policy gates.
  3. Maintainer can compare v4.0 and v4.2 outputs and confirm low-saturation max-green failures are removed or reduced to the approved threshold without regressing hard-constraint validity.
  4. Maintainer can hand off the accepted v4.2 HF/GGUF artifacts, reports, and new replay log as the latest reproducible calibration result.

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 17 → 18 → 19 → 20

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 7. 4B baseline/label protocol gate | v4.0 | 4/4 | Complete | 2026-05-10 |
| 8. v3 扩展数据 → 4B dataset rebuild | v4.0 | 4/4 | Complete | 2026-05-10 |
| 9. 4B QLoRA retrain | v4.0 | 4/4 | Complete | 2026-05-11 |
| 10. merge + GGUF export | v4.0 | 4/4 | Complete | 2026-05-11 |
| 11. eval matrix + decision | v4.0 | 4/4 | Complete | 2026-05-11 |
| 12. reality.log → reality_test.log replay | v4.0 | 3/3 | Complete | 2026-05-11 |
| 13. Inventory & Cleanup Boundaries | v4.1 | 2/2 | Complete | 2026-05-12 |
| 14. Canonical v4 Reproduction Package | v4.1 | 1/1 | Complete | 2026-05-12 |
| 15. Safe Cleanup Execution | v4.1 | 2/2 | Complete | 2026-05-12 |
| 16. Verification & Handoff | v4.1 | 1/1 | Complete | 2026-05-12 |
| 17. Audit & Saturation Policy Gate | v4.2 | 2/2 | Complete | 2026-05-18 |
| 18. Calibrated Dataset Rebuild | v4.2 | 0/TBD | Not started | - |
| 19. 4B QLoRA Retrain & Export | v4.2 | 0/TBD | Not started | - |
| 20. Evaluation & Reality Replay Handoff | v4.2 | 0/TBD | Not started | - |
