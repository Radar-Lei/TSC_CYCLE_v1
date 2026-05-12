# Phase 13: Inventory & Cleanup Boundaries - Research

**Researched:** 2026-05-12  
**Domain:** Repository inventory, cleanup boundary classification, v4.0 reproduction asset preservation  
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, INV-01/INV-02, success criteria, and existing project state to guide decisions.

### Scope Constraints
- Phase 13 is inventory-only and must not perform destructive cleanup.
- Preserve canonical v4.0 Qwen3-4B reproduction assets and source imports.
- Treat old/uncommitted `.planning/phases/` content as inventory targets, not already-archived evidence.
- v4.1 does not retrain, add model capabilities, run imatrix/q5_K_M experiments, perform thinking ablations, or integrate EvoProgTSC deployment.

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, INV-01/INV-02, success criteria, and existing project state to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
## Deferred Ideas

- Destructive archive/remove actions are deferred to Phase 15.
- Minimal reproduction guide/package documentation is deferred to Phase 14.
- Post-cleanup verification and handoff are deferred to Phase 16.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INV-01 | Maintainer can view a generated inventory that classifies current root, data, artifacts, runs, planning, and tests files as v4 reproduction source, v4 evidence, archived legacy, temporary, or removable. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | Use a generated inventory manifest grouped by root, `data/`, `artifacts/`, `runs/`, `.planning/`, and `tests/`, with one required classification field per group. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; VERIFIED: repository file audit] |
| INV-02 | Maintainer can see explicit keep/archive/remove rationale for every high-impact file group before destructive cleanup is applied. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | Require every high-impact group to include `recommended_action`, `rationale`, `risk_if_deleted`, `evidence_paths`, and `phase15_allowed` fields. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md; ASSUMED] |
</phase_requirements>

## Summary

Phase 13 should produce a non-destructive, reviewable cleanup map rather than performing cleanup. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/13-CONTEXT.md] The inventory must classify file groups across root, `data/`, `artifacts/`, `runs/`, `.planning/`, and `tests/` as `v4 reproduction source`, `v4 evidence`, `archived legacy`, `temporary`, or `removable`. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] The planner should therefore create tasks that inspect and document repository state, generate a durable inventory artifact, and validate that all INV-01/INV-02 categories are covered before Phase 15 can perform any archive/remove action. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]

The canonical v4.0 preservation boundary is already partly defined by `.planning/STATE.md` and Phase 13 context: `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf`, `reality_test.log`, `artifacts/v4/phase8/phase8_gate_report.json`, `runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json`, `runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json`, `artifacts/v4/phase11/phase11_gate_report.json`, and `artifacts/v4/phase12/phase12_report.json` are explicitly named as canonical v4 assets or key reports. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md; VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/13-CONTEXT.md] Phase 13 should also flag supporting v4 assets such as v4 Phase 8 split/tokenized data, v4 run reports, and Phase 11/12 per-sample evidence for human review rather than deciding deletion automatically. [VERIFIED: repository file audit; ASSUMED]

**Primary recommendation:** Build a read-only inventory generator plus a human-readable inventory report that defaults ambiguous or high-impact groups to `keep` or `archive_candidate`, never `remove`, until Phase 14 defines the canonical reproduction package and Phase 15 executes cleanup. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md; ASSUMED]

## Project Constraints (from CLAUDE.md)

- Always reply in Simplified Chinese. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Do not include `Co-Authored-By` lines in git commit messages. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- The machine is DGX Spark and vLLM is temporarily unavailable. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- ARIS default difficulty is nightmare. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Do not directly read or send an entire PDF upstream; split by page if PDFs are involved. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Before file-changing work, use GSD workflow entry points; this phase itself is planning/research inventory and must remain non-destructive. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md; VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/13-CONTEXT.md]
- v4.1 is cleanup/reproduction packaging only and must not retrain, add model capabilities, run imatrix/q5_K_M, perform thinking ablations, or integrate EvoProgTSC deployment. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/PROJECT.md; VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Repository inventory generation | Local tooling / Developer workstation | Git index | Inventory is a local filesystem and git-status audit, not model/runtime behavior. [VERIFIED: repository file audit; CITED: https://git-scm.com/docs/git-status] |
| Cleanup classification policy | Planning artifacts | Maintainer review | Classification decisions are consumed by Phase 14/15 planning artifacts and must be human-reviewable before destructive cleanup. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| Canonical v4 asset preservation | Filesystem artifacts | Planning state | Canonical artifacts live in `runs/`, `artifacts/`, `data/`, and root files, while preservation rationale is recorded in `.planning/STATE.md` and Phase 13 inventory. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md; VERIFIED: repository file audit] |
| Validation of inventory completeness | Test suite / pytest | Manual review | `pyproject.toml` configures pytest under `tests`, and Phase 13 can add fast tests for inventory schema/completeness without running training. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml; CITED: https://docs.pytest.org/en/stable/how-to/usage.html] |

## Standard Stack

### Core
| Library / Tool | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| Python stdlib `pathlib` | Python 3.12.3 in project venv | Traverse repository paths, inspect file/dir status, collect metadata. | `Path.iterdir`, `glob`, `rglob`, `walk`, `is_file`, `is_dir`, and `stat` are documented filesystem primitives. [VERIFIED: `/home/samuel/TSC_CYCLE/.venv/bin/python --version`; CITED: https://docs.python.org/3/library/pathlib.html] |
| Python stdlib `json` + `hashlib` | Python 3.12.3 in project venv | Emit machine-readable inventory and hash canonical asset references. | Existing project already uses stable JSON and SHA-256 helpers in `tsc_cycle/hashing.py`. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/hashing.py] |
| Git CLI | 2.43.0 | Distinguish tracked modified, untracked, ignored, and generated files. | `git status --porcelain` has stable script-oriented output and reports `??` for untracked paths. [VERIFIED: local `git --version`; CITED: https://git-scm.com/docs/git-status] |
| pytest | 9.0.3 in project venv | Validate inventory schema and requirement coverage. | Project config sets `testpaths = ["tests"]` and `addopts = "-q"`; pytest supports full-suite and file/path invocation. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml; VERIFIED: `/home/samuel/TSC_CYCLE/.venv/bin/pytest --version`; CITED: https://docs.pytest.org/en/stable/how-to/usage.html] |

### Supporting
| Library / Tool | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| `du` | GNU coreutils 9.4 | Summarize high-impact directory sizes during read-only audit. | Use for reporting size/risk of large groups such as `runs/`, `data/`, `.venv`, and `.claude/worktrees`. [VERIFIED: local `du --version`; VERIFIED: repository size audit] |
| `find` | bfs 4.1 on this machine | Enumerate file groups by path depth and extension. | Use in manual audit commands, but prefer Python `pathlib` for committed inventory logic. [VERIFIED: local `find --version`; CITED: https://docs.python.org/3/library/pathlib.html] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python stdlib inventory script | Shell-only `find`/`du` pipeline | Shell pipelines are quick for exploration but harder to unit test and less portable for schema validation. [ASSUMED] |
| JSON inventory plus markdown summary | Markdown-only checklist | Markdown is readable, but JSON is easier to test for INV-01/INV-02 coverage and future Phase 15 automation. [ASSUMED] |
| Git status integration | Filesystem-only scan | Filesystem-only scans miss whether a file is tracked, modified, ignored, or untracked; `git status --porcelain` directly exposes these states. [CITED: https://git-scm.com/docs/git-status] |

**Installation:** No new package installation is required for Phase 13 because the recommended stack uses the project venv, Python stdlib, git, and pytest already present locally. [VERIFIED: local environment probes; VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml]

**Version verification:** Local probes found Python 3.12.3 and pytest 9.0.3 in `/home/samuel/TSC_CYCLE/.venv`, git 2.43.0, GNU `du` 9.4, and bfs `find` 4.1. [VERIFIED: local environment probes]

## Architecture Patterns

### System Architecture Diagram

```text
Repository root
  |
  v
Read-only filesystem scan (pathlib / git status / size metadata)
  |
  v
Group normalizer
  |-- root files
  |-- data/
  |-- artifacts/
  |-- runs/
  |-- .planning/
  |-- tests/
  |-- source/scripts/local temp
  |
  v
Classification rules
  |-- known canonical v4 assets -> v4 evidence / v4 reproduction source
  |-- source imports and tests -> v4 reproduction source or legacy source candidate
  |-- old milestones / v1-v3 outputs -> archived legacy candidate
  |-- caches / pycache / venv / worktrees -> temporary/removable candidate
  |-- ambiguous high-impact data/model outputs -> review required
  |
  v
Outputs
  |-- machine-readable inventory JSON
  |-- human-readable inventory markdown/table
  |-- validation tests for INV-01/INV-02 coverage
  |
  v
Phase 14 consumes canonical package candidates; Phase 15 consumes cleanup boundaries
```

This flow should be read-only and must not call delete, move, archive, or rewrite operations. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/13-CONTEXT.md]

### Recommended Project Structure

```text
.planning/phases/13-inventory-cleanup-boundaries/
├── 13-RESEARCH.md                 # this research artifact [VERIFIED: requested output path]
├── 13-01-PLAN.md                  # planner-created task plan [ASSUMED]
└── inventory/                     # optional generated outputs, if planner chooses file output [ASSUMED]
    ├── inventory.json             # machine-readable classification [ASSUMED]
    └── inventory.md               # maintainer-facing review table [ASSUMED]

tsc_cycle/
└── cleanup_inventory.py           # optional reusable inventory generator, if code artifact is chosen [ASSUMED]

tests/
└── test_cleanup_inventory.py      # optional tests for schema and coverage [ASSUMED]
```

The planner may choose to keep generated inventory under the phase directory so Phase 13 stays non-invasive and reviewable. [ASSUMED]

### Pattern 1: Inventory Schema with Explicit Review Fields
**What:** Each inventory entry should include path/group, category, recommended action, rationale, evidence source, git status, size, and risk fields. [ASSUMED]  
**When to use:** Use for every high-impact file group and every canonical asset candidate. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]  
**Example:**
```json
{
  "path": "runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf",
  "classification": "v4 evidence",
  "recommended_action": "keep",
  "rationale": "Phase 11 recommended deployment artifact and Phase 12 replay model.",
  "risk_if_deleted": "Breaks v4.0 shipped result verification.",
  "evidence_paths": [
    ".planning/STATE.md",
    "artifacts/v4/phase12/phase12_report.json"
  ],
  "phase15_allowed": "no_delete"
}
```
Source: `.planning/STATE.md` and `artifacts/v4/phase12/phase12_report.json`. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md; VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase12/phase12_report.json]

### Pattern 2: Conservative Default for Ambiguous Groups
**What:** Any group not proven temporary/removable should be classified as `review_required` with `recommended_action = keep_or_archive`, not `remove`. [ASSUMED]  
**When to use:** Use for large or historically meaningful groups such as `raw_responses/`, v3 data, v1/v3 run directories, and old `.planning/phases/` files. [VERIFIED: repository file audit; VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]  
**Why:** Phase 15 is the destructive cleanup phase, so Phase 13 should only define boundaries and rationale. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]

### Pattern 3: Separate Classification from Action
**What:** Store classification (`v4 evidence`, `archived legacy`, `temporary`) separately from action (`keep`, `archive_candidate`, `remove_candidate`, `no_delete`). [ASSUMED]  
**When to use:** Use everywhere, because a legacy item may still require archive rather than deletion. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]

### Anti-Patterns to Avoid
- **Deleting during inventory:** Phase 13 explicitly forbids destructive cleanup. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/13-CONTEXT.md]
- **Treating untracked as removable:** Current `git status --short` reports many untracked Phase 7-13 planning, artifact, test, and source files; untracked status alone does not mean a file is safe to delete. [VERIFIED: local `git status --short`; CITED: https://git-scm.com/docs/git-status]
- **Collapsing v4 evidence into one file:** Phase 12 success depends on model artifact, `reality_test.log`, manifest/per-sample/report files, and upstream Phase 8-11 reports. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase12/phase12_report.json; VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]
- **Using `.planning/phases/` as the canonical reproduction source:** Phase 14 must make v4 assets identifiable without historical phase archaeology. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]

## Current Repository Inventory Findings

### Top-Level Size and Count Snapshot

| Group | Files | Approx Size | Initial Classification Guidance |
|-------|-------|-------------|---------------------------------|
| `runs/` | 3749 | ~94G | High-impact: contains canonical v4 model, v1 baseline, v3 microconvert artifacts, logs, and checkpoints; classify subgroups individually. [VERIFIED: repository size audit] |
| `.venv/` | 65275 | ~7.8G | Temporary/local environment; likely removable from repository cleanup scope but do not delete in Phase 13. [VERIFIED: repository size audit; VERIFIED: /home/samuel/TSC_CYCLE/.gitignore] |
| `.claude/` | 2657 | ~951M | Local agent/worktree state; likely temporary/removable candidate after review. [VERIFIED: repository size audit; VERIFIED: repository file audit] |
| `data/` | 48 | ~559M | High-impact: contains v4 Phase 8 labeled/split/tokenized data and legacy v1/v3 data; classify by version path. [VERIFIED: repository size audit] |
| `raw_responses/` | 9551 | ~39M | Legacy teacher raw outputs; likely archived legacy or optional audit evidence, not canonical v4 package unless Phase 14 chooses otherwise. [VERIFIED: repository size audit; ASSUMED] |
| `artifacts/` | 454 | ~7.0M | Contains v4 Phase 8/11/12 reports and legacy v3 Phase 1 reports; classify by milestone/version. [VERIFIED: repository size audit] |
| `.planning/` | 170 | ~2.3M | Contains current roadmap/state plus old phase artifacts; keep current milestone state, inventory old phases as archive candidates. [VERIFIED: repository size audit; VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md] |
| `tests/` | 85 | ~1.5M | Source validation; retain tests that protect v4 reproduction and classify v3-only tests as legacy candidates after dependency review. [VERIFIED: repository size audit; ASSUMED] |
| `tsc_cycle/` | 134 | ~1.8M | Source package; must preserve imports needed for v4 reproduction and validation. [VERIFIED: repository size audit; VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md] |
| `scripts/` | 29 | ~148K | Operational entry points for v3/v4 gates; preserve v4 scripts and classify v3 scripts as legacy archive candidates. [VERIFIED: repository file audit; ASSUMED] |

### Canonical v4 Assets That Must Not Be Deleted

| Asset | Role | Evidence |
|-------|------|----------|
| `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf` | Recommended deployment artifact; Phase 12 model artifact. | `model_sha256=e290829b52b06e8a28a17e6d752f24dcc08ecd4317e9177a360187243d67d99a`. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md; VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase12/phase12_report.json] |
| `reality_test.log` | Final replay output from Phase 12. | Phase 12 report lists 426 input/output, parse, lint, and protocol successes. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase12/phase12_report.json] |
| `artifacts/v4/phase8/phase8_gate_report.json` | v4 dataset rebuild gate report. | Named in Phase 13 context and STATE as a key v4 report. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md] |
| `runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json` | v4 SFT gate report. | Report shows `ok: true`, Qwen3-4B model config, and Phase 10 handoff. [VERIFIED: /home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json] |
| `runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json` | v4 GGUF export gate report. | Report records fp16/q4 paths and q4 SHA-256. [VERIFIED: /home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json] |
| `artifacts/v4/phase11/phase11_gate_report.json` | v4 eval matrix GO decision. | Report records verdict `GO` and recommended artifact path. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json] |
| `artifacts/v4/phase12/phase12_report.json` | final reality replay gate report. | Report records `ok: true`, 426/426 parse/lint/protocol counts, output hash, and model hash. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase12/phase12_report.json] |
| `artifacts/v4/phase12/manifest.json` and `artifacts/v4/phase12/per_sample.jsonl` | supporting Phase 12 replay evidence. | Referenced by Phase 12 report under `reports`. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase12/phase12_report.json] |

### Likely v4 Reproduction Source / Evidence Candidates

- `data/v4/phase8/labeled_merged.jsonl`, `data/v4/phase8/splits/*.jsonl`, `data/v4/phase8/splits/manifest.json`, and `data/v4/phase8/tokenized/*.arrow` are v4 Phase 8 data outputs and should be classified as v4 reproduction source or v4 evidence pending Phase 14 package decisions. [VERIFIED: repository file audit; VERIFIED: /home/samuel/TSC_CYCLE/.planning/PROJECT.md]
- `runs/v4.0-4B-20260509T184844Z/adapter/`, `merged_hf/`, `gguf/model.fp16.gguf`, `gguf/model.q4_K_M.gguf`, `eval_phase11/`, and reports under the same run root are v4 training/export/eval outputs; q4 model and reports are canonical, while fp16/merged/adapter/checkpoint assets require explicit keep/archive rationale because they are large. [VERIFIED: repository file audit; VERIFIED: /home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json]
- `tsc_cycle/v4_gates/*`, `tsc_cycle/eval/phase11_*`, `tsc_cycle/v4_gates/phase12_*`, `scripts/run_v4_*`, and `scripts/run_phase12_reality_test.sh` are likely v4 reproduction source entry points and should not be removed without import/test validation. [VERIFIED: repository file audit; ASSUMED]

### Legacy / Temporary / Removable Candidates Requiring Later Review

- `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` is a v1.0 baseline retained as read-only historical reference, not the v4.1 reproduction target unless Phase 13 classifies it as optional legacy evidence. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]
- `runs/v3.0-gates/gguf_microconvert/` contains very large v3 microconvert artifacts including ~17.9G bf16/tokenizer GGUF files and ~5.6G q4 file; classify as archived legacy candidate, not v4 canonical evidence. [VERIFIED: repository file audit]
- `data/v3/`, `data/tokenized/v3/`, `data/splits/v3/`, and `artifacts/v3/` are legacy v3 route outputs; classify as archived legacy candidates unless Phase 14 needs them to explain v4 Phase 8 source lineage. [VERIFIED: repository file audit; VERIFIED: /home/samuel/TSC_CYCLE/.planning/PROJECT.md]
- `.pytest_cache/`, `__pycache__/`, `.venv/`, `.claude/worktrees/`, and generated local caches are temporary/removable candidates, but Phase 13 must only inventory them. [VERIFIED: repository file audit; VERIFIED: /home/samuel/TSC_CYCLE/.gitignore]
- `.env` is ignored and present at repository root; classify as secret/local config and never include contents in inventory output. [VERIFIED: /home/samuel/TSC_CYCLE/.gitignore; VERIFIED: repository file audit]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Filesystem traversal | Ad-hoc string path parsing | `pathlib.Path` | Handles paths, recursion, metadata, and path type checks through documented APIs. [CITED: https://docs.python.org/3/library/pathlib.html] |
| Git state detection | Guess tracked/untracked from `.gitignore` manually | `git status --porcelain` | Porcelain output is stable for scripts and reports untracked/modified states directly. [CITED: https://git-scm.com/docs/git-status] |
| Inventory verification | Manual eyeballing only | pytest schema/coverage tests | pytest can run file-specific or full test commands and project config already uses pytest. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml; CITED: https://docs.pytest.org/en/stable/how-to/usage.html] |
| Hashing canonical assets | Custom checksum format | existing `tsc_cycle.hashing` or SHA-256 | Project already uses canonical JSON and SHA-256 helpers. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/hashing.py] |

**Key insight:** Phase 13 is a boundary-definition phase; custom cleanup actions are riskier than standardized read-only scans plus explicit rationale because deletion is intentionally deferred to Phase 15. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md; ASSUMED]

## Common Pitfalls

### Pitfall 1: Untracked Does Not Mean Safe to Delete
**What goes wrong:** The planner treats `??` files as clutter and marks them removable. [ASSUMED]  
**Why it happens:** `git status --short` uses `??` for untracked files, and the current repository has many untracked Phase 7-13 planning/source/test/artifact files. [VERIFIED: local `git status --short`; CITED: https://git-scm.com/docs/git-status]  
**How to avoid:** Inventory must include git state but classify by role/evidence, not git state alone. [ASSUMED]  
**Warning signs:** Any rule that maps all `??` to `remove_candidate`. [ASSUMED]

### Pitfall 2: Deleting Large Files Before Identifying Canonical Evidence
**What goes wrong:** Large GGUF, safetensors, tokenized Arrow, or v3/v4 intermediate files are removed because they dominate disk usage. [ASSUMED]  
**Why it happens:** `runs/` is ~94G and contains both canonical v4 assets and legacy bulky outputs. [VERIFIED: repository size audit]  
**How to avoid:** Require explicit `risk_if_deleted` and evidence source for every large group before recommending archive/remove. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; ASSUMED]  
**Warning signs:** Inventory groups all of `runs/` under one action. [ASSUMED]

### Pitfall 3: Making `.planning/phases/` the Reproduction Source of Truth
**What goes wrong:** Future users must inspect historical plans/reviews to find final v4 assets. [ASSUMED]  
**Why it happens:** Old phase directories contain many reports and summaries across v1-v4. [VERIFIED: repository file audit]  
**How to avoid:** Phase 13 should inventory `.planning/phases/` as history, while Phase 14 creates a canonical v4 manifest outside historical archaeology. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]  
**Warning signs:** Inventory says “see Phase 11/12 plan history” instead of naming asset paths and hashes. [ASSUMED]

### Pitfall 4: Leaking Secrets or Local Machine State
**What goes wrong:** Inventory includes `.env` content, local venv internals, or `.claude/worktrees` details beyond path/size/category. [ASSUMED]  
**Why it happens:** Read-only file scans can accidentally collect file contents rather than metadata. [ASSUMED]  
**How to avoid:** Inventory should record metadata only for secret/local groups and should never read or serialize `.env` contents. [VERIFIED: /home/samuel/TSC_CYCLE/.gitignore; ASSUMED]  
**Warning signs:** Any inventory output includes API keys, environment variable values, or full local worktree internals. [ASSUMED]

## Code Examples

Verified patterns from official and local sources:

### Read-only Inventory Traversal Skeleton
```python
from pathlib import Path

ROOT = Path("/home/samuel/TSC_CYCLE")
SKIP_CONTENT = {".git", ".env"}

for path in sorted(ROOT.rglob("*")):
    rel = path.relative_to(ROOT)
    if rel.parts and rel.parts[0] in SKIP_CONTENT:
        continue
    stat = path.stat()
    record = {
        "path": str(rel),
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
        "size_bytes": stat.st_size,
    }
```
Source: Python pathlib docs for `Path.rglob`, `Path.stat`, `Path.is_file`, and `Path.is_dir`. [CITED: https://docs.python.org/3/library/pathlib.html]

### Git Status Capture for Inventory Metadata
```bash
git -C /home/samuel/TSC_CYCLE status --porcelain
```
Source: Git status docs for stable porcelain output and `??` untracked status. [CITED: https://git-scm.com/docs/git-status]

### Fast Validation Commands
```bash
/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_cleanup_inventory.py -q
/home/samuel/TSC_CYCLE/.venv/bin/pytest -q
```
Source: Project pytest config and pytest usage docs. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml; CITED: https://docs.pytest.org/en/stable/how-to/usage.html]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Treat cleanup as manual deletion after a milestone | Generate inventory and cleanup boundaries before destructive actions | v4.1 roadmap, 2026-05-12 | Phase 15 must consume Phase 13 boundaries rather than deleting ad hoc. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| Use historical phase directories to discover shipped assets | Create a canonical reproduction package and manifest | Planned Phase 14 | Phase 13 must identify candidates but not replace Phase 14 documentation. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| Keep all milestone artifacts equally prominent | Separate v4 canonical evidence from v1/v2/v3 legacy evidence | v4.1 roadmap, 2026-05-12 | Inventory should classify v1/v3 outputs as legacy/reference unless required for v4 lineage. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md] |

**Deprecated/outdated:**
- Treating `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` as the deployment target is outdated for v4.1; it is a read-only v1 baseline while the v4 target is `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf`. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]
- Continuing the v3 9B route is out of scope because v3.0 was stopped after 9B local training was too slow. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/PROJECT.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Inventory should use JSON plus markdown, not markdown-only. | Standard Stack / Architecture Patterns | Planner might create only human-readable output and make automated INV-01/INV-02 validation harder. |
| A2 | Ambiguous high-impact groups should default to keep/archive candidate, not remove. | Summary / Architecture Patterns | Inventory may be too conservative and defer more decisions to Phase 15, but avoids destructive mistakes. |
| A3 | `tsc_cycle/v4_gates/*`, `scripts/run_v4_*`, and Phase 11/12 eval modules are v4 reproduction source entry points. | Current Repository Inventory Findings | Some files may be optional rather than required; Phase 14 should tighten the canonical set. |
| A4 | `raw_responses/` is likely legacy or optional audit evidence rather than canonical v4 package content. | Current Repository Inventory Findings | If Phase 14 requires teacher-output provenance, raw responses may need archive retention. |
| A5 | `.venv/`, `.claude/worktrees/`, caches, and pycache are temporary/removable candidates. | Current Repository Inventory Findings | Local workflows may depend on them operationally, so Phase 15 should confirm before deletion. |
| A6 | Planner may place generated inventory under the Phase 13 directory and optionally add code under `tsc_cycle/`. | Recommended Project Structure | A different artifact location could still satisfy INV-01/INV-02 if documented. |

## Open Questions (RESOLVED)

1. **RESOLVED — Phase 13 creates both committed JSON and Markdown inventory artifacts.**  
   - What we know: INV-01/INV-02 require a generated inventory and explicit rationale. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]  
   - Decision: Generate machine-readable JSON for automated validation and human-readable Markdown for maintainer review under the Phase 13 inventory artifact directory. [RESOLVED: planner decision]

2. **RESOLVED — v3 lineage remains visible as archive/optional audit evidence, not removable clutter.**  
   - What we know: v4.0 reused v3 lint-pass expanded data rebuilt under the Qwen3-4B tokenizer. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/PROJECT.md]  
   - Decision: Mark v3 source lineage as `archive_candidate` or `optional_audit_evidence`, not `remove_candidate`, until Phase 14 defines the minimal reproduction package. [RESOLVED: planner decision]

3. **RESOLVED — `.claude/worktrees` is local temporary state requiring manual review before removal.**  
   - What we know: `.claude/worktrees` exists and `.claude/` is ~951M. [VERIFIED: repository size audit]  
   - Decision: Inventory it as local temporary state with `manual_review_before_remove`; Phase 13 does not delete it, and Phase 15 must not remove it without maintainer confirmation. [RESOLVED: planner decision]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python project venv | Inventory script and tests | ✓ | 3.12.3 | System Python exists but is 3.14.4; prefer project venv. [VERIFIED: local environment probes] |
| pytest project venv | Validation Architecture | ✓ | 9.0.3 | System pytest 9.0.2 exists, but prefer project venv. [VERIFIED: local environment probes] |
| git | Tracked/untracked/modified state | ✓ | 2.43.0 | Filesystem-only scan possible but loses git state. [VERIFIED: local environment probes; CITED: https://git-scm.com/docs/git-status] |
| `du` | Size audit | ✓ | GNU coreutils 9.4 | Python `stat().st_size` aggregation. [VERIFIED: local environment probes; CITED: https://docs.python.org/3/library/pathlib.html] |
| `find` | Manual path audit | ✓ | bfs 4.1 | Python `Path.rglob` / `Path.walk`. [VERIFIED: local environment probes; CITED: https://docs.python.org/3/library/pathlib.html] |

**Missing dependencies with no fallback:** None found for Phase 13 inventory work. [VERIFIED: local environment probes]

**Missing dependencies with fallback:** None found for required Phase 13 work. [VERIFIED: local environment probes]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 in `/home/samuel/TSC_CYCLE/.venv` [VERIFIED: local environment probe] |
| Config file | `/home/samuel/TSC_CYCLE/pyproject.toml` [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |
| Quick run command | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_cleanup_inventory.py -q` [ASSUMED] |
| Full suite command | `/home/samuel/TSC_CYCLE/.venv/bin/pytest -q` [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml; CITED: https://docs.pytest.org/en/stable/how-to/usage.html] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INV-01 | Generated inventory contains entries for root, data, artifacts, runs, planning, and tests groups and each entry has one allowed classification. | unit/schema | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_cleanup_inventory.py::test_inventory_covers_required_groups -q` | ❌ Wave 0 [VERIFIED: tests file audit] |
| INV-02 | Every high-impact group has explicit action, rationale, risk, and evidence fields before cleanup. | unit/schema | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_cleanup_inventory.py::test_high_impact_groups_have_rationale -q` | ❌ Wave 0 [VERIFIED: tests file audit] |
| INV-02 | Canonical v4 no-delete assets are present and marked `keep`/`no_delete`. | unit/schema | `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_cleanup_inventory.py::test_canonical_v4_assets_are_no_delete -q` | ❌ Wave 0 [VERIFIED: tests file audit] |

### Sampling Rate
- **Per task commit:** `/home/samuel/TSC_CYCLE/.venv/bin/pytest tests/test_cleanup_inventory.py -q` after inventory code/test exists. [ASSUMED]
- **Per wave merge:** `/home/samuel/TSC_CYCLE/.venv/bin/pytest -q`. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml]
- **Phase gate:** Inventory artifact exists, covers INV-01 groups, includes INV-02 rationales, and no destructive file operations were performed. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/13-CONTEXT.md]

### Wave 0 Gaps
- [ ] `tests/test_cleanup_inventory.py` — covers INV-01/INV-02 inventory schema and canonical no-delete assets. [VERIFIED: tests file audit]
- [ ] Inventory artifact path decision — likely `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json` and `.md`. [ASSUMED]
- [ ] Optional `tsc_cycle/cleanup_inventory.py` — reusable read-only generator if planner chooses a source module. [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No authentication is implemented in Phase 13. [VERIFIED: phase scope from CONTEXT.md] |
| V3 Session Management | no | No sessions are implemented in Phase 13. [VERIFIED: phase scope from CONTEXT.md] |
| V4 Access Control | no | No runtime access-control surface is implemented; repository write/delete is deferred. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| V5 Input Validation | yes | Validate inventory paths remain under repository root and skip secret contents such as `.env`. [VERIFIED: /home/samuel/TSC_CYCLE/.gitignore; ASSUMED] |
| V6 Cryptography | yes | Use SHA-256 only for integrity identifiers; do not implement custom crypto. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/hashing.py] |

### Known Threat Patterns for Repository Inventory

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Secret disclosure from `.env` or local config | Information Disclosure | Record metadata only; do not read or serialize secret file contents. [VERIFIED: /home/samuel/TSC_CYCLE/.gitignore; ASSUMED] |
| Path traversal outside repository root | Tampering / Information Disclosure | Resolve paths relative to repository root and reject paths outside root. [CITED: https://docs.python.org/3/library/pathlib.html; ASSUMED] |
| Accidental deletion disguised as inventory | Tampering | Phase 13 code must be read-only and avoid move/delete/archive operations. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/13-CONTEXT.md] |
| Misclassification of canonical v4 assets | Tampering / Repudiation | Test that canonical no-delete assets from STATE/Phase reports are present in inventory with keep rationale. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md; ASSUMED] |

## Sources

### Primary (HIGH confidence)
- `/home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/13-CONTEXT.md` — Phase boundary, scope constraints, canonical v4 asset seeds. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md` — INV-01 and INV-02 definitions. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.planning/STATE.md` — v4.1 current state, preserved v4.0 context, cleanup blockers. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.planning/ROADMAP.md` — Phase 13-16 sequencing and success criteria. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.planning/PROJECT.md` — v4.0 shipped context and v4.1 goals. [VERIFIED]
- `/home/samuel/TSC_CYCLE/CLAUDE.md` — project constraints. [VERIFIED]
- `/home/samuel/TSC_CYCLE/artifacts/v4/phase12/phase12_report.json` — final replay counts, hashes, canonical q4 model path. [VERIFIED]
- `/home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json` — GO decision and recommended artifact. [VERIFIED]
- `/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json` — SFT report and handoff. [VERIFIED]
- `/home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json` — GGUF export report and hashes. [VERIFIED]
- Local repository audits with `find`, `du`, `git status`, and Python metadata summarization. [VERIFIED]

### Secondary (MEDIUM confidence)
- Python pathlib documentation — traversal and metadata APIs. [CITED: https://docs.python.org/3/library/pathlib.html]
- pytest usage documentation — command-line test selection and full suite invocation. [CITED: https://docs.pytest.org/en/stable/how-to/usage.html]
- Git status documentation — porcelain/short output and untracked semantics. [CITED: https://git-scm.com/docs/git-status]

### Tertiary (LOW confidence)
- Assumptions about exact inventory output location and optional implementation module names. [ASSUMED]
- Assumptions about whether v3 lineage/raw responses are optional audit evidence or canonical package inputs. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — local tool versions and official docs were checked; no new dependency is required. [VERIFIED: local environment probes; CITED: https://docs.python.org/3/library/pathlib.html]
- Architecture: HIGH — Phase 13/14/15 responsibilities are explicit in ROADMAP and CONTEXT; only exact file output names are assumed. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md; VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/13-CONTEXT.md]
- Pitfalls: HIGH — major risks are directly visible in repository state: large `runs/`, untracked files, ignored local env/secret paths, and mixed old phase directories. [VERIFIED: repository file audit; VERIFIED: local `git status --short`; VERIFIED: /home/samuel/TSC_CYCLE/.gitignore]

**Research date:** 2026-05-12  
**Valid until:** 2026-06-11, unless repository cleanup or v4 package boundaries change sooner. [ASSUMED]
