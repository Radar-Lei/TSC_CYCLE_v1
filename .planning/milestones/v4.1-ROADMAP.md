# Roadmap: TSC-CYCLE

## Overview

v4.1 turns the shipped v4.0 Qwen3-4B result into a clean, minimal reproduction package. The work starts with a non-destructive inventory and cleanup boundary, then defines the canonical v4 package, safely archives/removes unrelated clutter, and finally proves the retained repository still verifies the shipped v4 result.

## Milestones

- Shipped: **v1.0 Initial 4B Distillation Pipeline** — shipped 2026-05-07; archived in `milestones/v1.0-ROADMAP.md`
- Abandoned: **v2.0 Label Migration** — abandoned 2026-05-08; archived in `.planning/milestones/v2.0-abandoned/`
- Stopped: **v3.0 Qwen3.5-9B Route** — stopped 2026-05-10 after Phase 1–3; 9B local training was too slow
- Shipped: **v4.0 4B 回退 + 扩展数据重训 + 标签协议修复** — Phases 7–12 shipped 2026-05-11; archived in `milestones/v4.0-ROADMAP.md`
- Planned: **v4.1 项目清理 / v4 最小复现包** — Phases 13–16

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

- [x] **Phase 13: Inventory & Cleanup Boundaries** - Non-destructively classify current files and define keep/archive/remove rationale before cleanup. (completed 2026-05-12)
- [x] **Phase 14: Canonical v4 Reproduction Package** - Make the v4.0 reproduction assets identifiable without historical phase archaeology. (completed 2026-05-12)
- [x] **Phase 15: Safe Cleanup Execution** - Archive or remove unrelated clutter while preserving canonical v4 assets and a reviewable change set. (completed 2026-05-12)
- [x] **Phase 16: Verification & Handoff** - Prove the cleaned package still matches shipped v4 gates and is ready for the next milestone. (completed 2026-05-12)

## Phase Details

### Phase 13: Inventory & Cleanup Boundaries
**Goal**: Maintainer has a complete, non-destructive cleanup map for the current repository before any archive/remove action.
**Depends on**: Phase 12 (v4.0 shipped)
**Requirements**: INV-01, INV-02
**Success Criteria** (what must be TRUE):
  1. Maintainer can open an inventory that classifies root, data, artifacts, runs, planning, and tests file groups as v4 reproduction source, v4 evidence, archived legacy, temporary, or removable.
  2. Maintainer can see explicit keep/archive/remove rationale for every high-impact file group before destructive cleanup begins.
  3. Maintainer can identify the canonical v4 assets that must not be deleted and the legacy/temporary areas that require later archive or removal.
**Plans**: 2 plans
Plans:
**Wave 1**
- [x] 13-01-PLAN.md — Create read-only inventory tests, generator, and machine-readable inventory JSON.

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 13-02-PLAN.md — Generate maintainer-facing Markdown cleanup boundary report and checkpoint rationale review.

### Phase 14: Canonical v4 Reproduction Package
**Goal**: Reproducer can locate and understand the minimal v4.0 Qwen3-4B 9k reproduction package without inspecting historical phase directories.
**Depends on**: Phase 13
**Requirements**: REPRO-01, REPRO-03, DOC-01
**Success Criteria** (what must be TRUE):
  1. Reproducer can start from a repo-level manifest or guide and find the canonical v4.0 Qwen3-4B inputs, manifests, reports, final q4_K_M GGUF artifact, and `reality_test.log`.
  2. Reproducer can distinguish required reproduction assets from optional audit artifacts and obsolete v1/v2/v3/v4 intermediate outputs.
  3. Reproducer can see expected hashes, counts, final artifact names, and minimal verification commands from the manifest.
  4. Reproducer can follow the package boundary without using `.planning/phases/` history as the source of truth.
**Plans**: 1 plan
Plans:
**Wave 1**
- [x] 14-01-PLAN.md — Build and validate the repo-level v4.0 Qwen3-4B 9k reproduction manifest and guide.

### Phase 15: Safe Cleanup Execution
**Goal**: Maintainer can safely archive or remove non-v4 clutter while preserving canonical v4 reproduction assets and reviewability.
**Depends on**: Phase 14
**Requirements**: CLEAN-01, CLEAN-03, DOC-02
**Success Criteria** (what must be TRUE):
  1. Maintainer can archive or remove only files marked safe by Phase 13 boundaries while canonical v4 assets remain in their expected manifest locations.
  2. Maintainer can inspect legacy archive/removal notes explaining where v1/v2/v3 artifacts and obsolete v4 intermediate files went and why.
  3. Maintainer can inspect git status and see an intentionally scoped cleanup change set rather than mixed historical clutter.
  4. Maintainer can confirm retained source paths needed by the v4 reproduction package were not broken by cleanup.
**Plans**: 2 plans
Plans:
**Wave 1**
- [x] 15-01-PLAN.md — Capture preflight status, enforce Phase 13 archive allowlist, and archive exactly four legacy directories.

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 15-02-PLAN.md — Write cleanup notes, run final validation, and complete maintainer scope review checkpoint.

### Phase 16: Verification & Handoff
**Goal**: Reproducer and maintainer can verify the cleaned repository still reproduces the shipped v4.0 evidence path.
**Depends on**: Phase 15
**Requirements**: REPRO-02, CLEAN-02
**Success Criteria** (what must be TRUE):
  1. Reproducer can run or follow the documented minimal verification path and see that retained v4 assets match the shipped v4.0 result gates.
  2. Maintainer can rerun the relevant test and validation subset after cleanup and see the selected checks pass.
  3. Maintainer can compare retained artifacts against manifest hashes/counts and confirm no canonical v4 asset is missing.
  4. Maintainer can hand off the cleaned repository with no active cleanup blockers in roadmap/state.
**Plans**: 1 plan
Plans:
**Wave 1**
- [x] 16-01-PLAN.md — Run final no-cache manifest/test validation and write handoff evidence.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 7. 4B baseline/label protocol gate | 4/4 | Complete | 2026-05-10 |
| 8. v3 扩展数据 → 4B dataset rebuild | 4/4 | Complete | 2026-05-10 |
| 9. 4B QLoRA retrain | 4/4 | Complete | 2026-05-11 |
| 10. merge + GGUF export | 4/4 | Complete | 2026-05-11 |
| 11. eval matrix + decision | 4/4 | Complete | 2026-05-11 |
| 12. reality.log → reality_test.log replay | 3/3 | Complete | 2026-05-11 |
| 13. Inventory & Cleanup Boundaries | 2/2 | Complete    | 2026-05-12 |
| 14. Canonical v4 Reproduction Package | 1/1 | Complete   | 2026-05-12 |
| 15. Safe Cleanup Execution | 2/2 | Complete   | 2026-05-12 |
| 16. Verification & Handoff | 1/1 | Complete   | 2026-05-12 |
