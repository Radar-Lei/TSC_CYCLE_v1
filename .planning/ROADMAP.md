# Roadmap: TSC-CYCLE

## Overview

v4.1 has shipped as a clean, minimal reproduction package for the v4.0 Qwen3-4B 9k result. The repository now preserves the canonical v4 inputs, manifests, reports, final q4_K_M GGUF artifact, and `reality_test.log`, while non-v4 legacy/cache clutter has been removed from the active project tree.

## Milestones

- Shipped: **v1.0 Initial 4B Distillation Pipeline** — shipped 2026-05-07; archived in `milestones/v1.0-ROADMAP.md`
- Abandoned: **v2.0 Label Migration** — abandoned 2026-05-08; archived in `.planning/milestones/v2.0-abandoned/`
- Stopped: **v3.0 Qwen3.5-9B Route** — stopped 2026-05-10 after Phase 1–3; 9B local training was too slow
- Shipped: **v4.0 4B 回退 + 扩展数据重训 + 标签协议修复** — Phases 7–12 shipped 2026-05-11; archived in `milestones/v4.0-ROADMAP.md`
- Shipped: **v4.1 项目清理 / v4 最小复现包** — Phases 13–16 shipped 2026-05-12; archived in `milestones/v4.1-ROADMAP.md`

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

## Progress

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
