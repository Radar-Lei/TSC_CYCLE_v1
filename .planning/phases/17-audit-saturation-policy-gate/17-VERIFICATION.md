---
phase: 17-audit-saturation-policy-gate
verified: 2026-05-18T07:57:54Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 5/8
  gaps_closed:
    - "Prompt guard now uses independent frozen v4 prompt fixture/hash and simulated pre-import drift fails with prompt_byte_for_byte."
    - "Artifact root/output path safety now rejects broad roots such as repo root, data/, tsc_cycle/, artifacts/, and artifacts/v4 before writes."
    - "Top-level saturation_audit_report.json representative_examples now include both dataset:labeled_merged.jsonl and replay:phase12 origins with required fields."
  gaps_remaining: []
  regressions: []
---

# Phase 17: Audit & Saturation Policy Gate Verification Report

**Phase Goal:** Maintainer can measure the saturation/green mismatch, inspect representative failures, and run an offline policy gate that protects data, evaluation, and replay outputs while preserving the unchanged v4 deployment prompt protocol.
**Verified:** 2026-05-18T07:57:54Z
**Status:** passed
**Re-verification:** Yes — after gap closure and code review fixes

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Maintainer can generate banded statistics showing how often v4 teacher labels set `final == max_green` when `pred_saturation < 1.0`, broken down by saturation band, split, and source. | VERIFIED | `/home/samuel/TSC_CYCLE/artifacts/v4/phase17/saturation_audit_report.json` contains non-empty `bands`, `by_split`, `by_source`, and `by_origin` metrics with counts/rates. |
| 2 | Maintainer can inspect representative failure examples from both `data/v4/phase8/labeled_merged.jsonl` and `reality_test.log` with sample id, phase id, saturation, min/max green, final green, and violation category. | VERIFIED | Top-level `representative_examples` includes `dataset:labeled_merged.jsonl` and `replay:phase12`; verifier probe confirmed all examples include required fields. |
| 3 | Maintainer can run a saturation policy gate that classifies phase decisions into the intended saturation bands and fails outputs that exceed configured low-saturation max-green thresholds. | VERIFIED | `evaluate_saturation_policy_gate` applies band threshold keys; regenerated CLI report exits 1 with `ok:false`, `next_phase_allowed:false`, and 6 fatal threshold failures for current evidence. |
| 4 | Maintainer can verify that final deployment system/inference prompts remain byte-for-byte aligned with the v4 inference protocol and do not explicitly include the saturation band rule. | VERIFIED | `phase17_audit.py` loads `v4_prompt_protocol_golden.json`; verifier simulated pre-import `build_user_prompt` drift and guard returned `ok:false` with `prompt_byte_for_byte`. Prompt report has no forbidden snippets. |
| 5 | Maintainer can classify every phase decision into the required saturation band intervals. | VERIFIED | `classify_saturation_band` implements `<0.2`, `<0.6`, `<1.0`, and `>=1.0`; regression tests passed. |
| 6 | Maintainer can quantify v4 teacher final==max_green while pred_saturation<1.0 by band, split, and source. | VERIFIED | Audit report includes `final_equals_max_when_unsaturated` metrics under `bands`, `by_split`, and `by_source`. |
| 7 | Maintainer can run one offline CLI that writes Phase 17 audit, gate, and prompt-protocol JSON reports. | VERIFIED | CLI regeneration wrote all three reports under `/home/samuel/TSC_CYCLE/artifacts/v4/phase17/`; exit 1 was expected red policy gate. |
| 8 | Maintainer CLI writes safe Phase 17 JSON reports under `artifacts/v4/phase17/` only. | VERIFIED | Verifier probe confirmed broad roots `/home/samuel/TSC_CYCLE`, `data`, `tsc_cycle`, `artifacts`, `artifacts/v4` are rejected; writes to `data/`, `tsc_cycle/`, and phase12 artifact paths are rejected. |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/saturation_policy.py` | Canonical saturation classifier, projectors, audit aggregation, per-origin representative examples | VERIFIED | Exists, substantive, imported by `phase17_audit.py`, tests exercise classifier/projection/audit/example behavior. |
| `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/phase17_audit.py` | CLI/report orchestration, threshold gate, path guard, prompt protocol guard | VERIFIED | Exists, substantive, CLI runnable, loads frozen fixture, validates artifact roots, writes safe JSON reports. |
| `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/fixtures/v4_prompt_protocol_golden.json` | Independent frozen prompt text/hash fixture | VERIFIED | Exists; verifier confirmed stored sha256 matches stored prompt text and code does not derive expected prompt from `build_user_prompt`. |
| `/home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py` | Phase 17 regression tests | VERIFIED | 76 tests passed together with adjacent regressions. Includes prompt drift, broad-root rejection, and replay representative coverage tests. |
| `/home/samuel/TSC_CYCLE/artifacts/v4/phase17/saturation_audit_report.json` | Maintainer-facing audit report | VERIFIED | Regenerated; contains band/split/source/origin metrics and both dataset and replay representative examples. |
| `/home/samuel/TSC_CYCLE/artifacts/v4/phase17/saturation_policy_gate.json` | Offline policy gate report | VERIFIED | Regenerated; `ok:false` and `next_phase_allowed:false` with fatal failures for current evidence, preserving protective red gate behavior. |
| `/home/samuel/TSC_CYCLE/artifacts/v4/phase17/prompt_protocol_report.json` | Prompt protocol report | VERIFIED | Regenerated; `ok:true`, expected and actual prompt hashes match, no forbidden policy snippets. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `phase17_audit.py` | `v4_prompt_protocol_golden.json` | frozen fixture load before comparing rendered prompt | WIRED | GSD key-link verifier passed; code loads fixture at import and uses runtime `build_user_prompt` only for actual rendered prompt. |
| `phase17_audit.py` | `artifacts/v4/phase17/*.json` | validated artifact root plus per-output safe path check | WIRED | GSD key-link verifier passed; CLI root validation and `_write_json` path guard both active. |
| `saturation_policy.py` | `saturation_audit_report.json` | `compute_saturation_audit` representative examples consumed by `evaluate_phase17_audit` | WIRED | GSD key-link verifier passed; regenerated report includes expected examples. |
| `phase17_audit.py` | data/replay/eval policy gate | `evaluate_saturation_policy_gate` | WIRED | Data and replay threshold reports appear in regenerated policy gate; eval JSONL path is tested. |
| `phase17_audit.py` | prompt helper surfaces | forbidden-snippet scan | WIRED | Prompt report lists scanned in-repo surfaces with hashes and empty forbidden findings. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `saturation_policy.py` | projected audit rows | Phase 8 dataset JSONL and Phase 12 manifest/per_sample | Yes | FLOWING |
| `phase17_audit.py` | audit/policy reports | projectors plus `compute_saturation_audit` and `evaluate_saturation_policy_gate` | Yes | FLOWING |
| `phase17_audit.py` | prompt protocol report | frozen fixture plus runtime `build_user_prompt` rendered prompt | Yes | FLOWING |
| `saturation_audit_report.json` | representative examples | current dataset and replay evidence | Yes | FLOWING; includes both required origins |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Phase 17 and adjacent regression tests | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest /home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py /home/samuel/TSC_CYCLE/tests/test_phase12_reality_log_generation.py /home/samuel/TSC_CYCLE/tests/test_v4_phase8_dataset_rebuild.py -q` | `76 passed` | PASS |
| Frozen fixture/hash and prompt drift guard | custom Python probe importing with monkeypatched `build_user_prompt` before re-import | `fixture_hash_matches True`, `no_self_referential_assignment True`, `drift_ok False`, `drift_gates ['prompt_byte_for_byte']` | PASS |
| Artifact-root/path safety | custom Python probe over broad roots and non-Phase-17 paths | Repo root, data, tsc_cycle, artifacts, artifacts/v4 rejected; writes to data/tsc_cycle/phase12 rejected | PASS |
| Audit representative origin coverage | custom Python probe over top-level audit JSON | origins `['dataset:labeled_merged.jsonl', 'replay:phase12']`; required fields present | PASS |

### Probe Execution

| Probe | Command | Result | Status |
|---|---|---|---|
| Phase 17 CLI/report generation | `PYTHONPATH=/home/samuel/TSC_CYCLE /home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.v4_gates.phase17_audit` | Exit code 1 as expected; all three reports exist; gate `ok:false`, `next_phase_allowed:false`, 6 fatal failures; prompt `ok:true`; audit includes both origins | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| AUDIT-01 | 17-01, 17-02 | Quantify `final == max_green` when `pred_saturation < 1.0`, broken down by bands and split/source | SATISFIED | Audit JSON and `compute_saturation_audit` expose band/split/source/origin metrics. |
| AUDIT-02 | 17-01, 17-03 | Inspect representative failures from both dataset and reality/replay with required fields | SATISFIED | Top-level audit examples include `dataset:labeled_merged.jsonl` and `replay:phase12`; required fields verified. |
| POLICY-01 | 17-01, 17-02 | Classify phase decisions into intended saturation bands | SATISFIED | Canonical classifier and tests cover half-open boundaries. |
| POLICY-02 | 17-02 | Fail data/model-eval/replay outputs when thresholds exceeded | SATISFIED | Regenerated policy gate fails current data/replay evidence red with fatal threshold failures; eval path covered by tests. |
| POLICY-03 | 17-02, 17-03 | Final deployment prompts unchanged and no explicit band rule | SATISFIED | Frozen fixture/hash guard and forbidden-snippet scan pass; simulated drift fails. |

No orphaned Phase 17 requirement IDs found: AUDIT-01, AUDIT-02, POLICY-01, POLICY-02, and POLICY-03 all appear in plan frontmatter and REQUIREMENTS traceability.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---:|---|---|---|
| `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/saturation_policy.py` | 113, 116 | `return {}` | Info | Empty fallback for missing split index; not a stub because real dataset/replay rows still flow and are tested. |
| `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/phase17_audit.py` | 228 | `return {}` | Info | Empty excluded-count fallback; not a stub because gate computes real reports and tests cover failure paths. |

No unreferenced `TBD`, `FIXME`, or `XXX` blocker markers found in modified implementation/test files.

### Human Verification Required

None.

### Gaps Summary

All three previous verification gaps are closed. The prompt guard is now independent of the runtime prompt builder, path safety no longer broadens trust to the repository/data/source roots, and the maintainer-facing audit report exposes representative failures from both dataset and replay/reality origins. The Phase 17 policy gate remains red for current v4 evidence, which is the intended protective behavior and does not block Phase 17 goal achievement.

---

_Verified: 2026-05-18T07:57:54Z_
_Verifier: Claude (gsd-verifier)_
