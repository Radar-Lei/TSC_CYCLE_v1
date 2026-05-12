# Requirements: TSC-CYCLE v4.1 项目清理 / v4 最小复现包

**Defined:** 2026-05-12
**Core Value:** 学生模型在 OOD 上仍满足硬约束，并在数值决策上接近 GPT-5.5 high 教师 — 不过拟合到 reality.log。

## v4.1 Requirements

### Inventory

- [x] **INV-01**: Maintainer can view a generated inventory that classifies current root, data, artifacts, runs, planning, and tests files as v4 reproduction source, v4 evidence, archived legacy, temporary, or removable.
- [x] **INV-02**: Maintainer can see explicit keep/archive/remove rationale for every high-impact file group before destructive cleanup is applied.

### Reproduction Package

- [x] **REPRO-01**: Reproducer can identify the canonical v4.0 Qwen3-4B 9k inputs, manifests, reports, final q4_K_M GGUF artifact, and `reality_test.log` without inspecting historical phase directories.
- [x] **REPRO-02**: Reproducer can run or follow a documented minimal verification path that confirms the retained v4 package still matches the shipped v4.0 result gates.
- [x] **REPRO-03**: Reproducer can distinguish required reproduction assets from optional audit artifacts and from obsolete v1/v2/v3/v4 intermediate files.

### Cleanup Execution

- [x] **CLEAN-01**: Maintainer can safely archive or remove files unrelated to v4.0 Qwen3-4B reproduction without deleting canonical v4 assets or breaking source code imports.
- [x] **CLEAN-02**: Maintainer can rerun the relevant test and validation subset after cleanup and see that the repository remains internally consistent.
- [x] **CLEAN-03**: Maintainer can inspect git status after cleanup and see a reviewable, intentionally scoped change set rather than mixed historical clutter.

### Documentation

- [x] **DOC-01**: Reproducer can start from a concise repo-level reproduction guide or manifest that names the canonical artifacts, expected hashes/counts, and verification commands.
- [x] **DOC-02**: Maintainer can understand where legacy v1/v2/v3 artifacts went and why they are no longer part of the main v4 reproduction path.

## Future Requirements

### Deployment

- **DEPLOY-01**: EvoProgTSC can call the v4 q4_K_M artifact through a deployment endpoint and validate end-to-end traffic signal decisions.

### Additional Experiments

- **EXP-01**: Maintainer can evaluate imatrix or q5_K_M fallback if future deployment shows q4_K_M sensitivity.
- **EXP-02**: Maintainer can run thinking on/off ablations to quantify the marginal benefit of explicit reasoning tags.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Re-training Qwen3-4B | User is satisfied with v4.0 Qwen3-4B 9k training result; v4.1 is cleanup only. |
| New model capability or dataset generation | Would expand beyond the goal of making existing v4 reproducible. |
| imatrix/q5_K_M or thinking on/off experiments | Deferred until a later experimental milestone. |
| EvoProgTSC deployment integration | Deferred until after the repository is clean enough to hand off. |
| Destructive cleanup without prior inventory | Cleanup must preserve canonical v4 assets and remain reviewable. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INV-01 | Phase 13 | Complete |
| INV-02 | Phase 13 | Complete |
| REPRO-01 | Phase 14 | Complete |
| REPRO-02 | Phase 16 | Complete |
| REPRO-03 | Phase 14 | Complete |
| CLEAN-01 | Phase 15 | Complete |
| CLEAN-02 | Phase 16 | Complete |
| CLEAN-03 | Phase 15 | Complete |
| DOC-01 | Phase 14 | Complete |
| DOC-02 | Phase 15 | Complete |

**Coverage:**
- v4.1 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0

---
*Requirements defined: 2026-05-12*
*Last updated: 2026-05-12 after Phase 16 verification handoff completion*
