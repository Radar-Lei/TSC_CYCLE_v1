# Phase 17: Audit & Saturation Policy Gate - Research

**Researched:** 2026-05-18 [VERIFIED: system context]
**Domain:** Offline JSONL/log audit, saturation policy classification, fail-closed gate reporting, prompt protocol regression protection [VERIFIED: ROADMAP.md + REQUIREMENTS.md]
**Confidence:** HIGH [VERIFIED: codebase Read/Bash]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
No explicit locked decisions were present under `## Implementation Decisions`; the phase boundary is copied verbatim below. [VERIFIED: 17-CONTEXT.md]

Maintainer can measure the saturation/green mismatch, inspect representative failures, and run an offline policy gate that protects data, evaluation, and replay outputs while preserving the unchanged v4 deployment prompt protocol. [VERIFIED: 17-CONTEXT.md]

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions. [VERIFIED: 17-CONTEXT.md]

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped. [VERIFIED: 17-CONTEXT.md]
</user_constraints>

## Summary

Phase 17 should be implemented as a lightweight offline Python gate under `tsc_cycle/v4_gates/`, not as model/training code. [VERIFIED: codebase pattern in `tsc_cycle/v4_gates/*` and tests] The standard implementation should read existing v4 artifacts, project them to per-phase decision rows, classify each row into the required saturation bands, emit banded statistics and representative examples, and write fail-closed JSON reports under `artifacts/v4/phase17/`. [VERIFIED: REQUIREMENTS.md + ROADMAP.md + existing Phase 8/11/12 gate patterns]

Current v4 artifacts already contain the exact inputs/outputs needed: `data/v4/phase8/labeled_merged.jsonl` has 9,501 labeled rows and 38,272 phase decisions, while Phase 12 replay evidence has 426 records/outputs and 1,679 phase decisions. [VERIFIED: codebase Bash JSON audit] The mismatch is present in both sources: examples include low-saturation `final == max_green` rows in both the merged dataset and `reality_test.log` evidence. [VERIFIED: codebase Bash JSON audit]

**Primary recommendation:** Build `tsc_cycle/v4_gates/saturation_policy.py` plus a Phase 17 CLI/report wrapper that reuses existing prompt parsing, hard-constraint lint, split indexes, Phase 12 manifest/per-sample evidence, and path-safety conventions. [VERIFIED: codebase Read]

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUDIT-01 | Maintainer can quantify how often existing v4 teacher labels assign `final == max_green` when `pred_saturation < 1.0`, broken down by saturation bands and split/source. [VERIFIED: REQUIREMENTS.md] | Use per-phase projection from `labeled_merged.jsonl` plus split indexes; current schema exposes `input.prediction.phase_waits[*]`, `result.solution`, `source_origin`, `source`, and `split_hint`. [VERIFIED: codebase Bash JSON audit] |
| AUDIT-02 | Maintainer can inspect representative failure examples from both `data/v4/phase8/labeled_merged.jsonl` and `reality_test.log`, including sample id, phase id, saturation, min/max green, final green, and violation category. [VERIFIED: REQUIREMENTS.md] | Use deterministic sampling from violation rows; Phase 12 manifest/per-sample provides replay sample IDs, inputs, solutions, and raw text. [VERIFIED: artifacts/v4/phase12/manifest.json + per_sample.jsonl] |
| POLICY-01 | Maintainer can run a saturation policy gate that classifies each phase decision against intended bands: `sat < 0.2` near min, `0.2 <= sat < 0.6` interpolated, `0.6 <= sat < 1.0` high but not max, and `sat >= 1.0` allowed max. [VERIFIED: REQUIREMENTS.md] | Implement one canonical classifier function and one canonical violation-category function in `saturation_policy.py`. [ASSUMED] |
| POLICY-02 | Maintainer can fail data, model evaluation, or replay outputs when low-saturation max-green behavior exceeds configured thresholds. [VERIFIED: REQUIREMENTS.md] | Use config-driven thresholds with fail-closed defaults and nonzero CLI exit when report `ok=false`. [VERIFIED: existing Phase 8/11/12 fail-closed pattern; threshold defaults ASSUMED] |
| POLICY-03 | Final deployment prompts remain unchanged from the v4 inference protocol and do not explicitly include the saturation band rule. [VERIFIED: REQUIREMENTS.md] | Add byte-for-byte golden prompt tests for `build_user_prompt()` and forbidden-band-rule checks against deployment prompt text. [VERIFIED: prompt_builder.py; test approach ASSUMED] |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Student model remains `Qwen/Qwen3-4B-Thinking-2507`; Phase 17 should not introduce a new base model. [VERIFIED: CLAUDE.md]
- DGX Spark training constraints exist, but Phase 17 should stay CPU/offline and avoid GPU/training imports. [VERIFIED: CLAUDE.md + Phase 11/12 lazy-import tests]
- Final deployment prompt protocol is the v4 protocol in `tsc_cycle/prompt_builder.py`. [VERIFIED: CLAUDE.md + prompt_builder.py]
- Hard constraints remain `min_green ≤ final ≤ max_green`, integer seconds, phase order, and phase coverage. [VERIFIED: CLAUDE.md + constraint_lint.py]
- Teacher/API generation concurrency and budget constraints are out of scope for Phase 17 because Phase 17 audits existing artifacts and does not call OpenAI. [VERIFIED: ROADMAP.md + CONTEXT.md]
- Do not use vLLM on this machine. [VERIFIED: global user instruction]
- No project skill directories were found under `.claude/skills/` or `.agents/skills/`; `.claude/` exists but contains worktree/scheduler files, not skills. [VERIFIED: Bash ls]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Saturation band classification | API / Backend offline gate | Database / Storage | Classification is deterministic business logic over persisted JSONL/log evidence. [VERIFIED: REQUIREMENTS.md + codebase artifact schema] |
| Dataset mismatch audit | API / Backend offline gate | Database / Storage | Reads `data/v4/phase8/labeled_merged.jsonl` and split indexes; writes report artifacts only. [VERIFIED: codebase Bash audit] |
| Replay mismatch audit | API / Backend offline gate | Database / Storage | Reads Phase 12 manifest/per-sample and optionally canonical `reality_test.log`; no deployment service call is needed. [VERIFIED: phase12_reality_test.py + phase12_report.py] |
| Policy failure gate | API / Backend offline gate | CI/Test runner | Existing gates return structured `ok`, `next_phase_allowed`, and `fatal_failures`; Phase 17 should follow the same fail-closed pattern. [VERIFIED: phase8_report.py/phase11_eval_report.py/phase12_report.py patterns] |
| Prompt protocol preservation | API / Backend prompt module | Test runner | `prompt_builder.py` is the single source of truth; tests should guard byte-for-byte output and absence of band-rule text. [VERIFIED: prompt_builder.py] |
| Human inspection report | API / Backend offline gate | Filesystem artifacts | Maintainers consume JSON/markdown-like report artifacts generated from deterministic samples. [VERIFIED: existing v4 report patterns] |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `json` | Python 3.12 stdlib [VERIFIED: local `.venv` + CITED: docs.python.org/3/library/json.html] | Parse JSONL artifacts and serialize reports. [CITED: docs.python.org/3/library/json.html] | Existing project gates use stdlib JSON and avoid heavy dependencies for audit/report paths. [VERIFIED: codebase Read] |
| Python stdlib `argparse` | Python 3.12 stdlib [VERIFIED: local `.venv` + CITED: docs.python.org/3/library/argparse.html] | Provide a maintainer CLI with explicit input/report paths. [CITED: docs.python.org/3/library/argparse.html] | Existing Phase 8/11/12 CLIs use `argparse`. [VERIFIED: codebase Read] |
| Python stdlib `pathlib.Path` | Python 3.12 stdlib [VERIFIED: local `.venv` + CITED: docs.python.org/3/library/pathlib.html] | Resolve and constrain filesystem paths. [CITED: docs.python.org/3/library/pathlib.html] | Existing path-safety helpers use `Path.resolve(strict=False)` and allowed-root checks. [VERIFIED: phase11_matrix.py + phase12_report.py] |
| `pytest` | 9.0.3 installed in project venv [VERIFIED: Bash] | Contract tests for classifiers, reports, path safety, and prompt preservation. [CITED: docs.pytest.org/en/stable/] | Project test suite already uses pytest with `pyproject.toml` config. [VERIFIED: pyproject.toml + tests/] |
| Existing `tsc_cycle.prompt_builder` | project module [VERIFIED: prompt_builder.py] | Canonical v4 deployment prompt rendering and parsing. [VERIFIED: prompt_builder.py] | POLICY-03 requires prompt stability against this module. [VERIFIED: REQUIREMENTS.md] |
| Existing `tsc_cycle.constraint_lint` | project module [VERIFIED: constraint_lint.py] | Validate output hard constraints before policy interpretation. [VERIFIED: constraint_lint.py] | Policy findings should not conflate hard-constraint failures with saturation-policy failures. [ASSUMED] |
| Existing Phase 12 parsers/artifacts | project modules/files [VERIFIED: phase12_reality_test.py + artifacts/v4/phase12/*] | Extract replay inputs and outputs for `reality_test.log` audit. [VERIFIED: codebase Read] | Reusing Phase 12 evidence avoids brittle parsing of rendered logs. [ASSUMED] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python stdlib `hashlib` | Python 3.12 stdlib [VERIFIED: existing code + local venv] | Report input/output hash evidence. [VERIFIED: phase12_report.py] | Use when Phase 17 reports need reproducibility fields. [ASSUMED] |
| Python stdlib `collections.Counter` | Python 3.12 stdlib [VERIFIED: local venv] | Aggregate band/source/split counts. [ASSUMED] | Use for AUDIT-01 banded statistics. [ASSUMED] |
| Existing `tsc_cycle.hashing` | project module [VERIFIED: dataset_rebuild.py imports] | Canonical JSON hashes where sample identity/report hashing needs existing conventions. [VERIFIED: dataset_rebuild.py] | Use if reports need canonical digests consistent with Phase 8. [ASSUMED] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib JSON/Counter loops [VERIFIED: codebase pattern] | pandas [ASSUMED] | Pandas would simplify tables but adds an unnecessary dependency and package audit surface. [ASSUMED] |
| Phase 12 manifest/per-sample evidence [VERIFIED: artifacts/v4/phase12/*] | Parse `reality_test.log` result blocks directly [ASSUMED] | Direct log parsing is brittle; Phase 12 already stores structured records/outputs and canonical-log checks. [VERIFIED: phase12_report.py] |
| Project `prompt_builder.py` golden tests [VERIFIED: prompt_builder.py] | Duplicate prompt strings in Phase 17 module [ASSUMED] | Duplicating prompt text risks drift; `prompt_builder.py` is already the v4 protocol source. [VERIFIED: prompt_builder.py] |

**Installation:**
```bash
# No new packages required. [VERIFIED: pyproject.toml + local venv]
```

**Version verification:** Local checks found Python 3.12.3 in `/home/samuel/TSC_CYCLE/.venv/bin/python` and pytest 9.0.3. [VERIFIED: Bash]

## Package Legitimacy Audit

No external packages should be installed for Phase 17. [VERIFIED: Standard Stack above] The Package Legitimacy Gate is not required because the recommended implementation uses Python stdlib plus existing project modules. [VERIFIED: pyproject.toml + codebase Read]

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| none | — | — | — | — | — | No install planned. [VERIFIED: research recommendation] |

**Packages removed due to slopcheck [SLOP] verdict:** none. [VERIFIED: no packages recommended]
**Packages flagged as suspicious [SUS]:** none. [VERIFIED: no packages recommended]

## Architecture Patterns

### System Architecture Diagram

```text
[data/v4/phase8/labeled_merged.jsonl]
        │  read rows + result.solution + phase_waits [VERIFIED: codebase Bash audit]
        ▼
[Dataset per-phase projector] ─────┐
                                   │
[data/v4/phase8/splits/*.index.jsonl] ─► enrich split/source [VERIFIED: split manifest]
                                   │
                                   ▼
                         [Saturation classifier]
                                   │
                                   ├─► [Band statistics by band/split/source]
                                   │
                                   └─► [Representative violations]

[artifacts/v4/phase12/manifest.json + per_sample.jsonl]
        │  read records + solutions [VERIFIED: Phase 12 artifacts]
        ▼
[Replay per-phase projector] ─► [Saturation classifier] ─► [Replay examples/stats]

[Policy config thresholds]
        │
        ▼
[Fail-closed gate]
        │
        ├─ ok=true only if thresholds pass [VERIFIED: existing gate pattern]
        ├─ ok=false + fatal_failures + nonzero CLI exit on excess [VERIFIED: existing gate pattern]
        └─ writes artifacts/v4/phase17/*.json only [ASSUMED]

[prompt_builder.build_user_prompt]
        │
        ▼
[Golden prompt + forbidden band-rule tests] ─► POLICY-03 evidence [VERIFIED: prompt_builder.py]
```

### Recommended Project Structure

```text
tsc_cycle/
├── v4_gates/
│   ├── saturation_policy.py          # canonical bands, per-phase rows, violation categories, threshold gate [ASSUMED]
│   └── phase17_audit.py              # CLI/report wrapper for AUDIT/POLICY requirements [ASSUMED]
└── prompt_builder.py                 # unchanged v4 prompt source of truth [VERIFIED: prompt_builder.py]

tests/
└── test_v4_phase17_saturation_policy.py  # classifier, report, path safety, prompt-stability contracts [ASSUMED]

artifacts/v4/phase17/
├── saturation_audit_report.json      # band counts + representative examples [ASSUMED]
├── saturation_policy_gate.json       # thresholds, pass/fail, fatal_failures [ASSUMED]
└── prompt_protocol_report.json       # prompt hashes and forbidden-rule checks [ASSUMED]
```

### Pattern 1: Per-Phase Decision Projection
**What:** Convert sample-level artifacts into one row per phase with `sample_id`, `phase_id`, `pred_saturation`, `min_green`, `max_green`, `final_green`, `split`, `source`, and `origin_artifact`. [VERIFIED: requirements + artifact schemas]
**When to use:** Use before every statistic, example extraction, and policy gate so dataset and replay evidence share the same logic. [ASSUMED]
**Example:**
```python
# Source: existing schemas verified in data/v4/phase8/labeled_merged.jsonl and Phase 12 artifacts.
def iter_phase_decisions(record: dict, solution: dict[str, int], *, split: str, source: str):
    for wait in record["input"]["prediction"]["phase_waits"]:
        phase_id = str(wait["phase_id"])
        yield {
            "sample_id": str(record["sample_id"]),
            "phase_id": phase_id,
            "pred_saturation": float(wait["pred_saturation"]),
            "min_green": int(wait["min_green"]),
            "max_green": int(wait["max_green"]),
            "final_green": int(solution[phase_id]),
            "split": split,
            "source": source,
        }
```

### Pattern 2: Canonical Band and Violation Classification
**What:** One module owns the band labels and violation categories used by audit reports and gates. [ASSUMED]
**When to use:** Use for AUDIT-01, AUDIT-02, POLICY-01, and POLICY-02 to prevent stats/gates from drifting. [ASSUMED]
**Example:**
```python
# Source: band boundaries are locked in REQUIREMENTS.md.
def classify_band(sat: float) -> str:
    if sat < 0.2:
        return "sat_lt_0.2_near_min"
    if sat < 0.6:
        return "sat_0.2_0.6_interpolated"
    if sat < 1.0:
        return "sat_0.6_1.0_high_not_max"
    return "sat_ge_1.0_allowed_max"
```

### Pattern 3: Fail-Closed Report Shape
**What:** Return JSON with `ok`, `next_phase_allowed`, `requirements_covered`, `gates`, `fatal_failures`, `warnings`, and `reports`. [VERIFIED: phase8_report.py + phase11_eval_report.py + phase12_report.py]
**When to use:** Use for `saturation_policy_gate.json` so future data/eval/replay phases can depend on it. [ASSUMED]
**Example:**
```python
# Source: existing Phase 11/12 gate report shape.
payload = {
    "ok": not fatal_failures,
    "next_phase_allowed": not fatal_failures,
    "requirements_covered": ["AUDIT-01", "AUDIT-02", "POLICY-01", "POLICY-02", "POLICY-03"],
    "gates": gates,
    "fatal_failures": fatal_failures,
    "reports": {"audit": str(audit_report), "policy_gate": str(policy_report)},
}
```

### Anti-Patterns to Avoid
- **Putting saturation band rules into `prompt_builder.py`:** This violates POLICY-03; keep policy offline-only. [VERIFIED: REQUIREMENTS.md]
- **Counting sample-level failures instead of per-phase failures:** A single sample can have multiple phase decisions, and the requirements ask for phase decision categories. [VERIFIED: requirements wording + artifact schema]
- **Parsing rendered `reality_test.log` when Phase 12 structured evidence exists:** Structured manifest/per-sample data is less brittle and already hash-backed. [VERIFIED: phase12_report.py]
- **Using only aggregate rates without examples:** AUDIT-02 explicitly requires representative examples from both dataset and replay. [VERIFIED: REQUIREMENTS.md]
- **Allowing report writes under frozen v1 or arbitrary roots:** Existing gates reject unsafe output paths and protect baseline artifacts. [VERIFIED: phase11_matrix.py + phase12_report.py]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON parsing/serialization | Custom JSONL parser | Python `json.loads` / `json.dumps` [CITED: docs.python.org/3/library/json.html] | Stdlib JSON is authoritative and already used across the project. [VERIFIED: codebase Read] |
| CLI parsing | Manual `sys.argv` parsing | `argparse` [CITED: docs.python.org/3/library/argparse.html] | Existing project CLIs use `argparse`; it keeps defaults inspectable in tests. [VERIFIED: codebase Read] |
| Prompt rendering | Duplicated prompt templates | `tsc_cycle.prompt_builder.build_user_prompt` [VERIFIED: prompt_builder.py] | POLICY-03 requires byte-for-byte v4 protocol preservation. [VERIFIED: REQUIREMENTS.md] |
| Hard constraints | New min/max/order validator | `tsc_cycle.constraint_lint.validate` [VERIFIED: constraint_lint.py] | Existing validator already returns typed violations for hard constraints. [VERIFIED: constraint_lint.py] |
| Replay input extraction | Regex-only parser for `reality_test.log` | Phase 12 `manifest.json` and `per_sample.jsonl`; optionally `extract_reality_inputs()` for source log. [VERIFIED: phase12_reality_test.py + artifacts] | Structured evidence avoids false positives from RAW/PARSED blocks. [VERIFIED: tests/test_phase12_reality_log_generation.py] |
| Path safety | Ad hoc path strings | Existing `_is_under` / allowed-root pattern with `Path.resolve(strict=False)`. [VERIFIED: phase11_matrix.py + phase12_report.py] | Prevents writes to frozen baseline or unrelated files. [VERIFIED: tests] |

**Key insight:** The hard part is not computing rates; it is preserving one canonical interpretation of phase-level policy while preventing offline policy text from leaking into deployment prompts. [ASSUMED]

## Common Pitfalls

### Pitfall 1: False prompt regression
**What goes wrong:** The saturation band rule is added to `USER_TEMPLATE` to make the model behave better. [ASSUMED]
**Why it happens:** The policy is useful for training/evaluation, but POLICY-03 says final deployment prompts must remain unchanged. [VERIFIED: REQUIREMENTS.md]
**How to avoid:** Add a golden prompt hash/string test and explicit forbidden-band-rule checks over `build_user_prompt()` output. [ASSUMED]
**Warning signs:** `prompt_builder.py` contains literal strings like `sat < 0.2`, `0.2 <= sat < 0.6`, or `sat >= 1.0`. [ASSUMED]

### Pitfall 2: Trivial phases counted as policy failures
**What goes wrong:** Rows with `min_green == max_green` are flagged as `final == max_green` even though no other value is possible. [VERIFIED: codebase observed example in Bash audit]
**Why it happens:** Existing data includes forced intervals such as `min_green == max_green`; `constraint_lint.is_trivial()` already recognizes all-phases-trivial samples. [VERIFIED: constraint_lint.py + Bash audit]
**How to avoid:** Add a violation category like `forced_max_trivial_range` or exclude trivial per-phase rows from threshold denominators, but still report counts. [ASSUMED]
**Warning signs:** Low-saturation max-green examples show equal min/max bounds. [VERIFIED: codebase Bash audit]

### Pitfall 3: Dataset split/source attribution drift
**What goes wrong:** AUDIT-01 reports only `record.split_hint`, missing Phase 8 deterministic split indexes. [ASSUMED]
**Why it happens:** `labeled_merged.jsonl` has source fields, while `data/v4/phase8/splits/*.index.jsonl` has final train/val/ood_val membership. [VERIFIED: codebase Bash audit]
**How to avoid:** Build `sample_id -> split` from split index JSONL and use record source/source_origin separately. [VERIFIED: codebase Bash audit]
**Warning signs:** Reports contain `same_dist/ood` but not `train/val/ood_val`. [ASSUMED]

### Pitfall 4: Saturation gate hides parse/lint failures
**What goes wrong:** Unparseable or hard-constraint-invalid outputs are silently skipped, making policy rates look better. [ASSUMED]
**Why it happens:** Saturation policy depends on a valid per-phase final value. [ASSUMED]
**How to avoid:** Run/record parse and hard-constraint lint first; fail closed if any required output lacks a valid solution. [VERIFIED: phase12_report.py pattern]
**Warning signs:** Denominators differ from expected phase decision counts without an explicit `excluded_count` section. [ASSUMED]

### Pitfall 5: Floating point boundary mistakes
**What goes wrong:** `sat == 0.2`, `sat == 0.6`, or `sat == 1.0` is put into the wrong band. [ASSUMED]
**Why it happens:** Requirements define half-open intervals. [VERIFIED: REQUIREMENTS.md]
**How to avoid:** Unit-test exact boundaries: `0.1999`, `0.2`, `0.5999`, `0.6`, `0.9999`, `1.0`. [ASSUMED]
**Warning signs:** Boundary tests absent from `test_v4_phase17_saturation_policy.py`. [ASSUMED]

## Code Examples

### Boundary-safe band classifier
```python
# Source: REQUIREMENTS.md POLICY-01.
def classify_saturation_band(sat: float) -> str:
    if sat < 0.2:
        return "sat_lt_0.2_near_min"
    if sat < 0.6:
        return "sat_0.2_0.6_interpolated"
    if sat < 1.0:
        return "sat_0.6_1.0_high_not_max"
    return "sat_ge_1.0_allowed_max"
```

### Fail-closed path guard
```python
# Source: phase12_report.py and phase11_matrix.py patterns.
def reject_unsafe_phase17_output_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    artifact_root = (PROJECT_ROOT / "artifacts" / "v4" / "phase17").resolve(strict=False)
    if candidate == artifact_root or artifact_root in candidate.parents:
        return candidate
    raise ValueError(f"Phase 17 report output path is not allowed: {candidate}")
```

### Prompt protocol guard
```python
# Source: prompt_builder.py and POLICY-03.
FORBIDDEN_POLICY_SNIPPETS = ("sat < 0.2", "0.2 <= sat < 0.6", "0.6 <= sat < 1.0", "sat >= 1.0")
prompt = build_user_prompt(fixture_prediction)
assert prompt == EXPECTED_V4_PROMPT
assert all(snippet not in prompt for snippet in FORBIDDEN_POLICY_SNIPPETS)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hard-constraint and teacher-MAE-only evaluation. [VERIFIED: Phase 11 metrics code] | Add offline saturation-policy audit/gate before data rebuild, evaluation, and replay. [VERIFIED: v4.2 REQUIREMENTS.md] | v4.2 roadmap created 2026-05-18. [VERIFIED: ROADMAP.md] | Prevents rewarding reproduction of bad low-saturation teacher labels. [VERIFIED: REQUIREMENTS.md] |
| Prompt-level steering for every decision rule. [ASSUMED] | Keep final deployment prompt unchanged and use policy only offline. [VERIFIED: REQUIREMENTS.md] | v4.2 requirements. [VERIFIED: REQUIREMENTS.md] | Model must learn calibrated behavior through data/training, not a changed inference prompt. [VERIFIED: REQUIREMENTS.md] |
| Sample-level reports only. [ASSUMED] | Per-phase decision rows with band/split/source breakdown. [VERIFIED: AUDIT-01/AUDIT-02] | Phase 17. [VERIFIED: ROADMAP.md] | Exposes which phase decisions violate saturation policy. [ASSUMED] |

**Deprecated/outdated:**
- Treating old teacher MAE as the primary success metric is deprecated for v4.2 because the metric can reward reproducing bad teacher labels. [VERIFIED: REQUIREMENTS.md]
- Adding saturation band rules to final deployment prompts is out of scope and forbidden for Phase 17. [VERIFIED: REQUIREMENTS.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Implement one canonical classifier/report module named `saturation_policy.py` plus wrapper `phase17_audit.py`. | Architecture Patterns / Project Structure | File names may differ, but centralizing logic remains necessary. |
| A2 | Use config-driven default thresholds; exact default threshold numbers are not locked by user decisions. | Phase Requirements / Policy Gate | Planner must choose or require human confirmation for threshold defaults. |
| A3 | Exclude or separately categorize per-phase trivial ranges where `min_green == max_green`. | Common Pitfalls | Wrong denominator can make the policy gate too strict or too lenient. |
| A4 | JSON reports under `artifacts/v4/phase17/` are the right artifact location. | Project Structure | Different artifact path would require test/path guard adjustment. |
| A5 | Golden prompt tests are sufficient to prove byte-for-byte prompt preservation. | POLICY-03 / Code Examples | If deployment uses another prompt path, planner must add that path to the verification set. |

## Open Questions

1. **What exact default thresholds should the policy gate enforce?**
   - What we know: POLICY-02 requires configured thresholds and current v4 data/replay exceed any strict low-saturation max-green zero-tolerance threshold. [VERIFIED: REQUIREMENTS.md + Bash audit]
   - What's unclear: The user did not lock numeric thresholds for allowed violation rates. [VERIFIED: CONTEXT.md]
   - Recommendation: Planner should add a checkpoint or choose conservative defaults with config override; threshold values remain [ASSUMED].

2. **Should `min_green == max_green` phase rows be excluded from policy failure denominators?**
   - What we know: Such rows exist in the current dataset audit examples. [VERIFIED: Bash audit]
   - What's unclear: Requirements do not explicitly define trivial forced ranges. [VERIFIED: REQUIREMENTS.md]
   - Recommendation: Report them separately and exclude from low-saturation max-green threshold failure by default. [ASSUMED]

3. **Which deployment prompt surfaces need byte-for-byte checks besides `prompt_builder.build_user_prompt()`?**
   - What we know: `prompt_builder.py` is documented as the single source of truth for teacher/student/eval prompt format. [VERIFIED: prompt_builder.py]
   - What's unclear: External deployment integration is out of scope and may use a separate prompt later. [VERIFIED: REQUIREMENTS.md out-of-scope]
   - Recommendation: Phase 17 should guard project prompt builder and any in-repo inference prompt helpers found by grep. [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `/home/samuel/TSC_CYCLE/.venv/bin/python` | Phase 17 CLI/tests | ✓ [VERIFIED: Bash] | Python 3.12.3 [VERIFIED: Bash] | Use project venv, not system Python 3.14.4. [VERIFIED: Bash] |
| `pytest` in project venv | Validation Architecture | ✓ [VERIFIED: Bash] | 9.0.3 [VERIFIED: Bash] | None needed. [VERIFIED: Bash] |
| `rg` | Codebase audit during planning/execution | ✓ [VERIFIED: Bash] | path `/usr/bin/rg` [VERIFIED: Bash] | Python file walking. [ASSUMED] |
| `node` / `gsd-sdk` | GSD init/graph tooling | ✓ [VERIFIED: Bash] | Node v24.12.0 path available; `gsd-sdk` path available. [VERIFIED: Bash] | Not required for Phase 17 runtime. [ASSUMED] |
| Context7 CLI `ctx7` | Documentation lookup | ✗ [VERIFIED: Bash] | — | Official Python/pytest docs via WebFetch were used. [VERIFIED: WebFetch] |
| Knowledge graph | graph context | ✗ [VERIFIED: Bash] | — | Codebase search/read was used. [VERIFIED: Bash/Read] |

**Missing dependencies with no fallback:** none for Phase 17 runtime. [VERIFIED: environment audit]

**Missing dependencies with fallback:** Context7 CLI is missing; official docs were fetched directly. [VERIFIED: Bash + WebFetch]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 in project venv [VERIFIED: Bash] |
| Config file | `/home/samuel/TSC_CYCLE/pyproject.toml` with `testpaths = ["tests"]` and `addopts = "-q"`. [VERIFIED: pyproject.toml] |
| Quick run command | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py -q` [ASSUMED] |
| Full suite command | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q` [VERIFIED: pyproject.toml + pytest availability] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUDIT-01 | Dataset banded stats by band/split/source include counts and max-when-unsaturated rates. [VERIFIED: REQUIREMENTS.md] | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py::test_dataset_audit_bands_by_split_and_source -q` [ASSUMED] | ❌ Wave 0 |
| AUDIT-02 | Representative dataset and replay failures include required fields and violation categories. [VERIFIED: REQUIREMENTS.md] | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py::test_representative_failures_include_dataset_and_replay_fields -q` [ASSUMED] | ❌ Wave 0 |
| POLICY-01 | Boundary classifier maps exact saturation intervals correctly. [VERIFIED: REQUIREMENTS.md] | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py::test_saturation_band_boundaries -q` [ASSUMED] | ❌ Wave 0 |
| POLICY-02 | Gate fails closed when configured low-saturation thresholds are exceeded and writes structured `fatal_failures`. [VERIFIED: REQUIREMENTS.md] | unit/integration | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py::test_policy_gate_fails_closed_on_threshold_excess -q` [ASSUMED] | ❌ Wave 0 |
| POLICY-03 | `build_user_prompt()` remains byte-for-byte v4 protocol and contains no explicit saturation band rule. [VERIFIED: REQUIREMENTS.md + prompt_builder.py] | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py::test_prompt_protocol_unchanged_and_no_band_rule -q` [ASSUMED] | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py -q` [ASSUMED]
- **Per wave merge:** `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v4_phase17_saturation_policy.py tests/test_phase12_reality_log_generation.py tests/test_v4_phase8_dataset_rebuild.py -q` [ASSUMED]
- **Phase gate:** Full suite green before `/gsd:verify-work`. [VERIFIED: GSD workflow]

### Wave 0 Gaps
- [ ] `/home/samuel/TSC_CYCLE/tests/test_v4_phase17_saturation_policy.py` — covers AUDIT-01, AUDIT-02, POLICY-01, POLICY-02, POLICY-03. [ASSUMED]
- [ ] `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/saturation_policy.py` — canonical classifier/projector/gate logic. [ASSUMED]
- [ ] `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/phase17_audit.py` — CLI/report orchestration. [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no [VERIFIED: offline local CLI scope] | Not applicable; no user login/session is introduced. [VERIFIED: phase scope] |
| V3 Session Management | no [VERIFIED: offline local CLI scope] | Not applicable. [VERIFIED: phase scope] |
| V4 Access Control | yes [VERIFIED: existing path-safety patterns] | Restrict report writes to `artifacts/v4/phase17/` and reject frozen baseline/output roots. [VERIFIED: phase11_matrix.py + phase12_report.py pattern] |
| V5 Input Validation | yes [VERIFIED: JSONL/log ingestion requirements] | Validate JSON object shape, required fields, finite numeric saturation, integer final values, and expected sample/output alignment. [VERIFIED: existing gate patterns; finite saturation checks ASSUMED] |
| V6 Cryptography | yes [VERIFIED: hash evidence pattern] | Use `hashlib.sha256` only for integrity/report hashes; do not implement custom crypto. [VERIFIED: phase12_report.py] |

### Known Threat Patterns for offline audit stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal / accidental overwrite | Tampering | Allowed-root path guard using resolved `Path` objects. [VERIFIED: phase11_matrix.py + phase12_report.py] |
| Stale or mismatched replay evidence | Tampering / Repudiation | Check sample ID order, input/output counts, and hashes where available. [VERIFIED: phase12_report.py] |
| Malformed JSONL row hides bad output | Tampering | Fail closed on malformed JSON, missing fields, or non-finite values. [ASSUMED] |
| Prompt policy leakage | Information Disclosure / Tampering | Golden prompt test and forbidden band-rule string checks. [VERIFIED: POLICY-03; implementation ASSUMED] |
| Metric denominator manipulation | Tampering | Report included/excluded counts, trivial-range counts, and denominators per band/source/split. [ASSUMED] |

## Sources

### Primary (HIGH confidence)
- `/home/samuel/TSC_CYCLE/.planning/phases/17-audit-saturation-policy-gate/17-CONTEXT.md` — phase boundary and discretion scope. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md` — AUDIT-01, AUDIT-02, POLICY-01, POLICY-02, POLICY-03. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/.planning/ROADMAP.md` — Phase 17 goal, success criteria, and dependencies. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/.planning/STATE.md` — v4.2 current focus and accumulated decisions. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/CLAUDE.md` — project constraints and stack context. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py` — v4 prompt protocol, tags, parser. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tsc_cycle/constraint_lint.py` — hard-constraint validator and trivial sample helper. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/phase12_reality_test.py` — replay input extraction, generation evidence, path safety, manifest writing. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tsc_cycle/v4_gates/phase12_report.py` — Phase 12 fail-closed report shape and canonical final-log checks. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tsc_cycle/eval/phase11_matrix.py` and `phase11_metrics.py` — eval matrix, path safety, aggregate metrics patterns. [VERIFIED: Read]
- Bash JSON audits over `data/v4/phase8/labeled_merged.jsonl` and `artifacts/v4/phase12/*` — current schema/counts/examples. [VERIFIED: Bash]
- Python docs for `json`, `argparse`, and `pathlib`; pytest docs. [CITED: docs.python.org + docs.pytest.org]

### Secondary (MEDIUM confidence)
- Existing Phase 8/11/12 tests — contract style, lazy imports, path guards, report assertions. [VERIFIED: Read]

### Tertiary (LOW confidence)
- None from WebSearch. [VERIFIED: no WebSearch used]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Phase 17 needs no new packages and uses stdlib/existing project modules verified in code. [VERIFIED: pyproject.toml + codebase Read]
- Architecture: HIGH — Existing v4 gates already establish report shape, path safety, and fail-closed patterns. [VERIFIED: codebase Read]
- Pitfalls: MEDIUM — Prompt leakage and denominator issues are inferred from requirements and observed artifacts; exact threshold policy remains user/plan dependent. [VERIFIED: requirements + Bash audit; thresholds ASSUMED]

**Research date:** 2026-05-18 [VERIFIED: system context]
**Valid until:** 2026-06-17 for internal codebase patterns; revisit if v4 artifacts or requirements change. [ASSUMED]
