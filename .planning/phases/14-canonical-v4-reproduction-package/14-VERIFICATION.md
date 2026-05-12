---
phase: 14-canonical-v4-reproduction-package
verified: 2026-05-12T04:48:00Z
status: human_needed
score: 8/8 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Guide clarity for a new reproducer"
    expected: "A human reproducer can read reproduction/v4.0-qwen3-4b-9k-guide.md and understand required vs optional assets and minimal verification steps without opening .planning/phases/."
    why_human: "Automated checks verify paths, hashes, categories, and commands, but cannot fully judge reader clarity."
---

# Phase 14: Canonical v4 Reproduction Package Verification Report

**Phase Goal:** Reproducer can locate and understand the minimal v4.0 Qwen3-4B 9k reproduction package without inspecting historical phase directories.
**Verified:** 2026-05-12T04:48:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Reproducer can start from a repo-level manifest or guide and find the canonical v4.0 Qwen3-4B inputs, manifests, reports, final q4_K_M GGUF artifact, and `reality_test.log`. | VERIFIED | `reproduction/v4.0-qwen3-4b-9k-manifest.json` and `reproduction/v4.0-qwen3-4b-9k-guide.md` exist outside `.planning/phases/`; manifest `required_evidence` has 9 canonical entries including final q4_K_M, `reality_test.log`, phase 8/9/10/11/12 reports, phase12 manifest, and per-sample JSONL; `required_source` has v4 labeled and split inputs. |
| 2 | Reproducer can distinguish required reproduction assets from optional audit artifacts and obsolete v1/v2/v3/v4 intermediate outputs. | VERIFIED | Manifest assets are split into `required_evidence`, `required_source`, `optional_rebuild_cache`, `optional_audit`, `obsolete_legacy`, and `local_temporary`; guide renders matching sections and states obsolete legacy/local temporary entries are not the v4 target. |
| 3 | Reproducer can see expected hashes, counts, final artifact names, and minimal verification commands from the manifest. | VERIFIED | Manifest includes SHA-256 and sizes for required files, final artifact `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf`, Phase 12 count 426, labeled row count 9501, split counts 7601/950/950, and commands for `python -m tsc_cycle.reproduction_manifest --check ...` plus pytest. |
| 4 | Reproducer can follow the package boundary without using `.planning/phases/` history as the source of truth. | VERIFIED | `source_of_truth` points to repo-level `reproduction/` manifest and guide; guide says `do not use .planning/phases/ as the source of truth`; `.planning/phases/` appears only as provenance inputs. |
| 5 | Reproducer can start from repo-level reproduction/v4.0-qwen3-4b-9k-manifest.json or reproduction/v4.0-qwen3-4b-9k-guide.md and find the canonical v4.0 Qwen3-4B 9k package without opening .planning/phases/ as the source of truth. | VERIFIED | Same repo-level source-of-truth evidence as truths 1 and 4; both files are under `/home/samuel/TSC_CYCLE/reproduction/`, not historical phase directories. |
| 6 | Reproducer can identify required v4 evidence, required v4 data/source inputs, optional rebuild caches, obsolete legacy artifacts, and local temporary paths as separate categories. | VERIFIED | Manifest category list exactly includes required evidence/source, optional rebuild cache/audit, obsolete legacy, and local temporary; local temporary entries are metadata-only. |
| 7 | Reproducer can see current SHA-256 hashes, sizes, line/count facts, final artifact names, and verification commands for the canonical v4 package. | VERIFIED | `--check` passed against current disk facts; tests recompute hashes/sizes/line counts; manifest contains final artifacts and verification commands. |
| 8 | Phase 14 code recomputes hashes/counts from disk and performs no delete, archive, move, retrain, dataset regeneration, or model inference action. | VERIFIED | `tsc_cycle/reproduction_manifest.py` uses chunked `hashlib.sha256`, line counts, JSON report parsing, and stdlib manifest writing; AST/destructive-token scan found no destructive calls, shell calls, model inference, retraining, or dataset regeneration. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tests/test_v4_reproduction_package.py` | Fail-closed pytest contract for REPRO-01, REPRO-03, DOC-01, and T-14 constraints | VERIFIED | Exists and substantive; imports builder/validator, recomputes hashes/counts, checks categories, source-of-truth wording, non-destructive behavior, and path guard. |
| `tsc_cycle/reproduction_manifest.py` | Deterministic stdlib manifest/guide builder and validator CLI | VERIFIED | Exports `build_package_manifest`, `write_manifest_json`, `write_guide_markdown`, `validate_manifest_against_disk`, and `main`; `--check` validates current manifest. |
| `reproduction/v4.0-qwen3-4b-9k-manifest.json` | Repo-level machine-readable canonical v4.0 reproduction package boundary | VERIFIED | Exists outside `.planning/phases/`; validator passed; contains required categories, facts, provenance, and commands. |
| `reproduction/v4.0-qwen3-4b-9k-guide.md` | Repo-level human reproduction entry point | VERIFIED | Exists outside `.planning/phases/`; names package, final artifact/hash, counts, commands, and package categories. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `tsc_cycle/reproduction_manifest.py` | `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json` | Read-only Phase 13 inventory input | WIRED | `DEFAULT_INVENTORY_PATH` points to Phase 13 inventory and `_load_inventory()` reads it through repo-root guard. |
| `reproduction/v4.0-qwen3-4b-9k-manifest.json` | `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf` | Required final q4_K_M asset entry with recomputed sha256 | WIRED | Manual JSON inspection confirmed required evidence entry and `final_artifacts.q4_K_M`; gsd pattern check false-negative due escaped regex search against JSON text. |
| `tests/test_v4_reproduction_package.py` | `tsc_cycle/reproduction_manifest.py` | Pytest imports builder/validator and recomputes disk facts | WIRED | Tests import `build_package_manifest`, `write_guide_markdown`, `validate_manifest_against_disk`, and `_resolve_repo_path`; pytest passed. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `reproduction/v4.0-qwen3-4b-9k-manifest.json` | `assets`, `final_artifacts`, `verification_commands` | `build_package_manifest()` reads Phase 13 inventory, v4 report JSON, split manifest, and disk files | Yes | VERIFIED |
| `reproduction/v4.0-qwen3-4b-9k-guide.md` | Rendered category tables and final target summary | `write_guide_markdown(manifest, ...)` renders from manifest entries | Yes | VERIFIED |
| `tsc_cycle/reproduction_manifest.py --check` | Validation errors | `validate_manifest_against_disk()` recomputes size, SHA-256, line counts, and semantic counts from disk | Yes | VERIFIED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Manifest matches current disk package facts | `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.reproduction_manifest --check reproduction/v4.0-qwen3-4b-9k-manifest.json` | `OK: /home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json` | PASS |
| Phase 14 and Phase 13 inventory contracts pass | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_v4_reproduction_package.py tests/test_cleanup_inventory.py -q` | `..................... [100%]` | PASS |
| Validator rejects stale/forged hashes | Temporary tampered manifest checked with `python -m tsc_cycle.reproduction_manifest --check` | return code 1 and output contained `sha256 mismatch` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| REPRO-01 | 14-01-PLAN.md | Reproducer can identify canonical v4.0 inputs, manifests, reports, final q4_K_M GGUF artifact, and `reality_test.log` without inspecting historical phase directories. | SATISFIED | Repo-level manifest/guide list all canonical required evidence/source entries and mark `.planning/phases/` as provenance only. |
| REPRO-03 | 14-01-PLAN.md | Reproducer can distinguish required reproduction assets from optional audit artifacts and obsolete v1/v2/v3/v4 intermediate files. | SATISFIED | Manifest and guide categories separate required, optional rebuild cache/audit, obsolete legacy, and local temporary entries. |
| DOC-01 | 14-01-PLAN.md | Reproducer can start from a concise repo-level reproduction guide or manifest that names canonical artifacts, expected hashes/counts, and verification commands. | SATISFIED | Guide and manifest include final q4_K_M path/hash, counts, categories, and verification commands. |

No orphaned Phase 14 requirements found in `.planning/REQUIREMENTS.md`; traceability maps REPRO-01, REPRO-03, and DOC-01 to Phase 14.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `tsc_cycle/reproduction_manifest.py` | 213, 219, 426 | `return {}` / `return []` | INFO | Benign default/empty-return branches for assets without semantic counts or non-dict manifests; not user-visible stubs and covered by tests. |

### Human Verification Required

#### 1. Guide clarity for a new reproducer

**Test:** Open `/home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-guide.md` as a new reproducer.
**Expected:** The reader can understand required vs optional assets and minimal verification steps without opening `.planning/phases/`.
**Why human:** Automated tests verify required text, paths, hashes, counts, and commands, but cannot fully judge readability and clarity.

### Gaps Summary

No automated blocker gaps found. All roadmap and plan must-haves are verified in codebase artifacts and behavioral checks. Overall status is `human_needed` only because guide clarity is a manual user-facing documentation judgment.

---

_Verified: 2026-05-12T04:48:00Z_
_Verifier: Claude (gsd-verifier)_
