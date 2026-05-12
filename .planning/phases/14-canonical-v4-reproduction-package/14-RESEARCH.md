# Phase 14: Canonical v4 Reproduction Package - Research

**Researched:** 2026-05-12 [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]
**Domain:** repo-level reproducibility manifest/guide, artifact boundary validation, and non-destructive v4.0 package documentation [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md]
**Confidence:** HIGH [VERIFIED: codebase inspection]

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP Phase 14 goal, REPRO-01, REPRO-03, DOC-01, Phase 13 inventory artifacts, and existing project state to guide decisions.

### Phase 13 Inputs
- Use `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json` as the machine-readable cleanup-boundary input.
- Use `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.md` as the maintainer-facing rationale input.
- Preserve the Phase 13 decision that canonical v4.0 evidence paths are `keep`/`no_delete` and local/legacy/temporary paths require conservative handling.

### Scope Constraints
- Phase 14 documents and packages the reproduction boundary; it does not delete, archive, move, retrain, regenerate datasets, or create new model capabilities.
- Phase 14 must not rely on `.planning/phases/` history as the reproducer-facing source of truth, though it may read phase artifacts as inputs while generating the repo-level manifest.
- Cleanup execution remains deferred to Phase 15.
- Post-cleanup verification remains deferred to Phase 16.

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP Phase 14 goal, REPRO-01, REPRO-03, DOC-01, Phase 13 inventory artifacts, and existing project state to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
## Deferred Ideas

- Destructive archive/remove actions are deferred to Phase 15.
- Full post-cleanup verification and handoff are deferred to Phase 16.
- Deployment integration, imatrix/q5_K_M fallback, and thinking ablations remain out of scope for v4.1.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REPRO-01 | Reproducer can identify the canonical v4.0 Qwen3-4B 9k inputs, manifests, reports, final q4_K_M GGUF artifact, and `reality_test.log` without inspecting historical phase directories. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | Use a repo-level source-of-truth manifest plus guide outside `.planning/phases/`, seeded from Phase 13 inventory and enriched with hashes/counts from current canonical artifacts. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| REPRO-03 | Reproducer can distinguish required reproduction assets from optional audit artifacts and obsolete v1/v2/v3/v4 intermediate files. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | Preserve Phase 13 classifications (`v4 evidence`, `v4 reproduction source`, `archived legacy`, `temporary`) and expose them in a reproducer-facing boundary table. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| DOC-01 | Reproducer can start from a concise repo-level reproduction guide or manifest that names the canonical artifacts, expected hashes/counts, and verification commands. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | Generate a concise repo-level guide/manifest that names artifact paths, SHA-256 hashes, counts, final artifact names, and lightweight verification/test commands. [VERIFIED: codebase inspection] |
</phase_requirements>

## Summary

Phase 14 is a documentation-and-validation phase, not a data/model generation phase: it should create a repo-level canonical v4.0 reproduction package manifest/guide and tests around that boundary, while leaving all existing files in place. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md] The planner should treat Phase 13 inventory as the authoritative cleanup-boundary input and enrich it with current hashes/counts from v4.0 artifacts, not infer package membership from historical `.planning/phases/` files. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]

The canonical no-delete evidence set already contains the final q4_K_M GGUF, `reality_test.log`, Phase 8/9/10/11/12 reports, Phase 12 manifest, and Phase 12 per-sample replay evidence. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] The v4 dataset reproduction source is broader than the no-delete evidence set: `data/v4/phase8` is classified as a v4 reproduction source pending Phase 14 package selection, and its split manifest shows 9,501 total rows split as 7,601 train / 950 val / 950 ood_val. [VERIFIED: /home/samuel/TSC_CYCLE/data/v4/phase8/splits/manifest.json]

**Primary recommendation:** Implement a small stdlib-based manifest builder/validator that reads Phase 13 inventory and current v4 reports, writes a repo-level canonical package manifest plus concise guide outside `.planning/phases/`, and adds pytest coverage that fails closed on missing assets, stale hashes/counts, or reproducer-facing references to `.planning/phases/` as source of truth. [VERIFIED: codebase inspection]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Canonical package manifest generation | Source / CLI | Filesystem | A deterministic Python module should read JSON/log/model artifacts and emit reproducible metadata without modifying source assets. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py] |
| Repo-level reproducer guide | Documentation | Source / CLI | The guide is the human entry point and should point to the machine-readable manifest for exact hashes/counts. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] |
| Asset boundary classification | Source / CLI | Planning input | Phase 13 inventory already classifies required, optional, legacy, and temporary paths; Phase 14 should consume it rather than reclassify from scratch. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |
| Hash/count validation | Test suite | Source / CLI | Existing tests validate contracts with pytest, and Phase 14 should add tests that recompute SHA-256 and row counts against the manifest. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |
| Cleanup/deletion decisions | Deferred Phase 15 | — | Phase 14 explicitly must not delete, archive, move, retrain, or regenerate artifacts. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md] |

## Project Constraints (from CLAUDE.md)

- Always reply in Simplified Chinese. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Never include `Co-Authored-By` lines in git commit messages. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- The machine is DGX Spark and vLLM is temporarily unavailable. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Project stack constraints include Qwen3-4B-Thinking-2507, QLoRA r=64, OpenAI GPT-5.5 high teacher API, and llama.cpp GGUF export, but Phase 14 must not retrain or regenerate those assets. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- DGX Spark training constraints forbid flash-attn cu12/vLLM reliance and require SDPA/OOM safeguards for training phases; Phase 14 should avoid GPU/model imports entirely because it is manifest/validation work. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Teacher API concurrency, budget, tokenizer safety, and lint constraints remain project constraints but are not active implementation dependencies for Phase 14 because no new data generation or training is in scope. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md]
- Before repo edits, work should start through a GSD command; `gsd-sdk query init.phase-op "14"` was run for this research. [VERIFIED: gsd-sdk query init.phase-op]

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `json` / `hashlib` / `pathlib` / `argparse` | Python 3.12.3 in project venv | Read reports, compute SHA-256, write deterministic JSON/Markdown, expose CLI. | Existing project utilities use stdlib-first deterministic JSON and hashing patterns. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/hashing.py] |
| pytest | 9.0.3 in project venv; dev dependency `pytest>=8.0.0` | Contract tests for manifest consistency, asset existence, hashes, counts, and boundary wording. | Existing project test infrastructure is pytest-based with `tests` as the configured test path. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |
| Existing `tsc_cycle.cleanup_inventory` | local module | Consume/reuse Phase 13 classification constants and inventory patterns. | It already defines canonical v4 asset paths and read-only inventory semantics. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uv | 0.9.10 installed | Run project venv tooling or install dev dependencies if needed. | Use only if the test environment is missing pytest or project deps. [VERIFIED: command -v uv && uv --version] |
| pyarrow | `>=15.0.0` declared | Existing tokenized `.arrow` dataset verification if Phase 14 chooses to validate row counts from Arrow files. | Prefer JSONL/split manifest counts for fast tests; use Arrow only for deeper optional validation. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Deterministic local JSON manifest | Markdown-only guide | Markdown is easy to read but brittle for automated hash/count validation. [VERIFIED: codebase inspection] |
| Python stdlib builder | External manifest/schema package | External dependencies add maintenance cost without solving a problem beyond JSON/hash/path checks. [ASSUMED] |
| Reusing Phase 13 inventory constants | Duplicating canonical path lists in Phase 14 | Duplication risks drift between cleanup boundaries and reproducer-facing package membership. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py] |

**Installation:**
```bash
# No new runtime package is required for Phase 14. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml]
# If the project venv lacks test tooling, use the existing project workflow:
uv pip install -e '.[dev]'
```

**Version verification:** Python 3.12.3, pytest 9.0.3, and uv 0.9.10 were available in the environment during research. [VERIFIED: python/pytest/uv version probes]

## Architecture Patterns

### System Architecture Diagram

```text
Phase 13 inventory JSON/MD
        |
        v
Manifest builder (stdlib Python)
        |
        +--> read canonical no-delete evidence paths from inventory
        |
        +--> read v4 report metadata and dataset split manifests
        |
        +--> compute SHA-256 / sizes / line counts for selected assets
        |
        v
Repo-level machine manifest (outside .planning/phases/)
        |
        +--> Repo-level human guide (concise starting point)
        |
        v
Pytest validation
        |
        +--> asset exists? hashes match? counts match?
        +--> required vs optional vs obsolete categories explicit?
        +--> guide does not require .planning/phases/ archaeology?
```

This design keeps `.planning/phases/` as build-time input only and makes the repo-level manifest/guide the reproducer-facing source of truth. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md]

### Recommended Project Structure

```text
reproduction/                         # recommended repo-level reproducer entry point [ASSUMED]
├── v4.0-qwen3-4b-9k-manifest.json    # machine-readable canonical package manifest [ASSUMED]
└── v4.0-qwen3-4b-9k-guide.md         # concise human guide [ASSUMED]

tsc_cycle/
└── reproduction_manifest.py           # deterministic builder/validator CLI [ASSUMED]

tests/
└── test_v4_reproduction_package.py    # manifest/guide contract tests [ASSUMED]
```

Recommended file names are assumptions because no repo-level reproduction package path convention currently exists. [ASSUMED]

### Pattern 1: Deterministic hash/count manifest
**What:** Store repo-relative path, role, required/optional/obsolete classification, size, SHA-256, count fields, source report, and verification command per asset. [VERIFIED: codebase inspection]
**When to use:** Use for every required canonical asset and for selected optional/obsolete boundary entries that a reproducer must distinguish. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]
**Example:**
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/hashing.py and codebase inspection
import hashlib
from pathlib import Path

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
```

### Pattern 2: Fail-closed contract tests
**What:** Tests should recompute manifest facts from disk and fail if a required asset is missing, hash/count is stale, or category wording is ambiguous. [VERIFIED: /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py]
**When to use:** Use for manifest and guide validation before Phase 15 cleanup depends on this boundary. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]
**Example:**
```python
# Source: /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py pattern
assert entry["classification"] == "v4 evidence"
assert entry["recommended_action"] == "keep"
assert entry["phase15_allowed"] == "no_delete"
```

### Pattern 3: Separate required reproduction assets from optional audit assets
**What:** Required assets should be enough to locate the shipped v4.0 model/evidence path; optional audit assets explain lineage but should not be mistaken for the current target. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]
**When to use:** Use in both manifest schema and guide tables. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md]
**Example categories:** `required`, `required_source`, `optional_audit`, `obsolete_legacy`, `local_temporary`. [ASSUMED]

### Anti-Patterns to Avoid
- **Markdown-only source of truth:** Prose alone cannot reliably prove hashes/counts before cleanup; use JSON as the source and Markdown as a rendered guide. [ASSUMED]
- **Historical phase archaeology:** The reproducer-facing path must not require opening `.planning/phases/` files. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md]
- **Regeneration disguised as verification:** Phase 14 should not rebuild datasets, retrain, or rerun model inference. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md]
- **Whole-directory keep claims without child-level required assets:** `runs/` and `data/` include legacy and canonical content, so the manifest must name exact canonical paths. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File hashing | Custom hash algorithm or ad-hoc checksum text | `hashlib.sha256` | Project already uses SHA-256 for reports and manifests. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/hashing.py] |
| JSON serialization | Non-deterministic pretty printers for machine contract | `json.dumps(..., sort_keys=True, ensure_ascii=False)` where stable output matters | Existing project hashing uses sorted compact JSON for stable IDs. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/hashing.py] |
| Cleanup classification | New independent classifier | Phase 13 inventory JSON and `tsc_cycle.cleanup_inventory` constants | Phase 13 is the approved non-destructive cleanup boundary input. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md] |
| Verification framework | Custom shell test harness | pytest | Project test discovery is already configured for pytest. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |

**Key insight:** Phase 14's risk is drift and ambiguity, not algorithmic complexity; the safest implementation is deterministic metadata extraction plus fail-closed tests. [VERIFIED: codebase inspection]

## Common Pitfalls

### Pitfall 1: Treating `.planning/phases/` as the reproducer source of truth
**What goes wrong:** External reproducers must inspect historical planning artifacts to understand which files matter. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md]
**Why it happens:** Phase 13 inventory and prior phase reports contain the richest context, so it is tempting to link users back to them directly. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.md]
**How to avoid:** Generate a repo-level manifest/guide that may cite Phase 13 as provenance but does not require it for normal reproduction navigation. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md]
**Warning signs:** Guide text says “see `.planning/phases/...` for the canonical package” or omits hashes/counts from the repo-level manifest. [ASSUMED]

### Pitfall 2: Confusing final v4 q4_K_M with frozen v1 q4_K_M
**What goes wrong:** The reproducer may use `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` instead of the v4.0 deployment artifact. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]
**Why it happens:** Both are q4_K_M GGUF artifacts, but v1 is only a historical baseline. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/PROJECT.md]
**How to avoid:** Manifest should mark `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf` as `required` and v1 as `optional_audit` or `obsolete_legacy`, with explicit “not the v4 target” wording. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]
**Warning signs:** Verification commands or guide examples mention `runs/20260507T032419Z` as a model input. [VERIFIED: /home/samuel/TSC_CYCLE/tests/test_phase12_reality_log_generation.py]

### Pitfall 3: Omitting dataset inputs from a “minimal” package
**What goes wrong:** The package identifies final reports/model but not the Qwen3-4B 9k dataset inputs and split manifests. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]
**Why it happens:** Phase 13 canonical no-delete evidence set focuses on final evidence, while `data/v4/phase8` is classified as reproduction source pending Phase 14 selection. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]
**How to avoid:** Include `data/v4/phase8/splits/manifest.json`, split index JSONL files, `data/v4/phase8/labeled_merged.jsonl`, and tokenized Arrow paths as required or required-source assets depending on final package boundary. [VERIFIED: /home/samuel/TSC_CYCLE/data/v4/phase8/splits/manifest.json]
**Warning signs:** Manifest contains only `artifacts/v4/` and `runs/v4.0...` paths. [ASSUMED]

### Pitfall 4: Stale hashes after user modifications
**What goes wrong:** The manifest records hashes that no longer match the current working tree. [VERIFIED: command hash probes]
**Why it happens:** Many canonical assets are modified in the current git status snapshot, including v4 reports and `reality_test.log`. [VERIFIED: initial gitStatus]
**How to avoid:** Compute hashes at generation time and add tests that compare manifest hashes to current file contents. [VERIFIED: codebase inspection]
**Warning signs:** Manifest hash differs from `phase12_report.json` values for `model_sha256` or `output_sha256`. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase12/phase12_report.json]

## Code Examples

Verified patterns from current codebase:

### Read Phase 13 inventory by path
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py
from pathlib import Path
import json

inventory_path = Path(".planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json")
inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
canonical = [
    entry for entry in inventory["entries"]
    if entry["classification"] == "v4 evidence" and entry["phase15_allowed"] == "no_delete"
]
```

### Stable JSON output pattern
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
```

### Current required v4 evidence hashes observed during research
```text
runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf sha256=e290829b52b06e8a28a17e6d752f24dcc08ecd4317e9177a360187243d67d99a [VERIFIED: command hash probe]
reality_test.log sha256=c784ef2c789c185fd1c0064565d52f4597be7f8d6848cbd53891471c2735ecb2 [VERIFIED: command hash probe]
artifacts/v4/phase12/per_sample.jsonl lines=426 sha256=ae244958dd8fb955d1635de25209633a23e5d36c5e9455fc347fdb068d1cfbb5 [VERIFIED: command hash probe]
```

## Canonical Asset Facts to Preserve

| Asset | Role | Current fact |
|-------|------|--------------|
| `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf` | Final deployment artifact | SHA-256 `e290829b52b06e8a28a17e6d752f24dcc08ecd4317e9177a360187243d67d99a`, size 2,497,280,160 bytes. [VERIFIED: command hash probe] |
| `reality_test.log` | Final replay output | SHA-256 `c784ef2c789c185fd1c0064565d52f4597be7f8d6848cbd53891471c2735ecb2`, 32,176 lines. [VERIFIED: command hash probe] |
| `artifacts/v4/phase12/phase12_report.json` | Final replay report | 426 input/output/parse/lint/protocol successes, timeout count 0, model hash matches final GGUF hash. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase12/phase12_report.json] |
| `artifacts/v4/phase12/manifest.json` | Phase 12 replay manifest | 426 records and same input/model/output hashes as Phase 12 report. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase12/manifest.json] |
| `artifacts/v4/phase12/per_sample.jsonl` | Per-sample replay evidence | 426 JSONL lines. [VERIFIED: command line-count probe] |
| `data/v4/phase8/splits/manifest.json` | Dataset split manifest | 7,601 train / 950 val / 950 ood_val; split hash IDs recorded. [VERIFIED: /home/samuel/TSC_CYCLE/data/v4/phase8/splits/manifest.json] |
| `data/v4/phase8/labeled_merged.jsonl` | Merged v4 labeled dataset | 9,501 JSONL lines. [VERIFIED: command line-count probe] |
| `artifacts/v4/phase11/phase11_gate_report.json` | GO decision report | Recommended artifact is final v4 q4_K_M; v4 q4 hard pass value 1.0 at threshold 0.98. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase11/phase11_gate_report.json] |
| `runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json` | GGUF export report | `ok=true`, `next_phase_allowed=true`, `q4_collapse=false`, `q5_K_M_decision_required=false`. [VERIFIED: /home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json] |
| `runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json` | SFT handoff report | `ok=true`, `next_phase_allowed=true`, run root is `runs/v4.0-4B-20260509T184844Z`. [VERIFIED: /home/samuel/TSC_CYCLE/runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json] |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Reproducer opens historical phase files to learn what matters | Reproducer starts from repo-level manifest/guide outside `.planning/phases/` | Phase 14 target in v4.1 | Makes package handoff understandable without GSD archaeology. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| Cleanup boundary exists only as maintainer inventory | Boundary is promoted into reproducer-facing required/optional/obsolete categories | Phase 14 target in v4.1 | Lets Phase 15 cleanup consume an explicit package boundary. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| v1 q4_K_M baseline visible near v4 outputs | v1 baseline is marked historical/optional and not the v4 target | Phase 13 inventory | Reduces wrong-artifact risk. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json] |

**Deprecated/outdated:**
- Using `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` as the active reproduction target is outdated; it is a v1 historical baseline. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]
- Treating `raw_responses`, `data/v3`, `artifacts/v3`, or `runs/v3.0-gates` as required v4.0 package assets is outdated; Phase 13 classifies them as archived legacy or archive candidates. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | External dependency packages beyond stdlib/pytest are unnecessary for Phase 14. | Standard Stack | Planner might omit a schema/rendering package that the user expected. |
| A2 | Recommended repo-level directory names `reproduction/`, `v4.0-qwen3-4b-9k-manifest.json`, and `v4.0-qwen3-4b-9k-guide.md` are acceptable. | Recommended Project Structure | User may prefer root-level file names or existing documentation paths. |
| A3 | Manifest categories `required`, `required_source`, `optional_audit`, `obsolete_legacy`, and `local_temporary` are acceptable names. | Architecture Patterns | Tests/guide may need renaming if user expects Phase 13 labels verbatim. |
| A4 | Markdown-only is insufficient as the authoritative package source. | Anti-Patterns | If the user wants no new machine-readable file, implementation scope changes. |

## Open Questions (RESOLVED)

1. **RESOLVED — repo-level manifest/guide live under `reproduction/`.**
   - What we know: It must be outside `.planning/phases/`. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md]
   - Decision: Use `reproduction/v4.0-qwen3-4b-9k-manifest.json` and `reproduction/v4.0-qwen3-4b-9k-guide.md` as the reproducer-facing source-of-truth artifacts. [RESOLVED: planner decision]

2. **RESOLVED — tokenized Arrow files are rebuildable cache, not minimal required source.**
   - What we know: `data/v4/phase8/tokenized/{train,val,ood_val}.arrow` are listed by the Phase 8 gate report and dataset split outputs. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v4/phase8/phase8_gate_report.json]
   - Decision: Mark split manifest/index/labeled merged data as `required_source`; mark tokenized Arrow files as `optional_rebuild_cache` or `required_if_skipping_tokenization` with explicit guide wording. [RESOLVED: planner decision]

3. **RESOLVED — Phase 14 includes a small builder/validator CLI.**
   - What we know: Existing pattern favors generated artifacts with source modules and tests. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py]
   - Decision: Add `tsc_cycle/reproduction_manifest.py` so hashes/counts/guide can be regenerated reproducibly before Phase 15. [RESOLVED: planner decision]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python in project venv | Manifest builder/tests | ✓ | 3.12.3 | System `python3` exists but is 3.14.4; prefer project venv for pyproject compatibility. [VERIFIED: version probes] |
| pytest in project venv | Validation Architecture | ✓ | 9.0.3 | Install dev extra via `uv pip install -e '.[dev]'` if absent. [VERIFIED: version probes] |
| uv | Dependency/bootstrap fallback | ✓ | 0.9.10 | Use existing venv if uv is unavailable. [VERIFIED: version probes] |
| Final q4_K_M GGUF file | Manifest hash validation | ✓ | SHA-256 `e290829b...d99a` | No fallback; missing file blocks REPRO-01. [VERIFIED: command hash probe] |

**Missing dependencies with no fallback:** None found for Phase 14 manifest/test work. [VERIFIED: environment probes]

**Missing dependencies with fallback:** None found. [VERIFIED: environment probes]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 in project venv; pyproject declares `pytest>=8.0.0`. [VERIFIED: version probes and /home/samuel/TSC_CYCLE/pyproject.toml] |
| Config file | `/home/samuel/TSC_CYCLE/pyproject.toml` with `testpaths = ["tests"]` and `addopts = "-q"`. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |
| Quick run command | `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py -q` [VERIFIED: environment probes] |
| Full suite command | `/home/samuel/TSC_CYCLE/.venv/bin/pytest -q` [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| REPRO-01 | Manifest names canonical v4.0 Qwen3-4B 9k inputs, reports, final q4_K_M GGUF, and `reality_test.log` without requiring `.planning/phases/`. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | unit/contract | `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py::test_manifest_lists_required_v4_assets -q` | ❌ Wave 0 |
| REPRO-03 | Manifest/guide distinguish required reproduction assets from optional audit and obsolete legacy assets. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | unit/contract | `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py::test_manifest_classifies_required_optional_and_obsolete_assets -q` | ❌ Wave 0 |
| DOC-01 | Guide/manifest expose expected hashes, counts, final artifact names, and minimal verification commands. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] | unit/contract | `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py::test_guide_exposes_hashes_counts_and_commands -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py -q` [VERIFIED: project pytest setup]
- **Per wave merge:** `/home/samuel/TSC_CYCLE/.venv/bin/pytest /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py /home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py -q` [VERIFIED: existing inventory tests]
- **Phase gate:** Full suite green before `/gsd-verify-work`: `/home/samuel/TSC_CYCLE/.venv/bin/pytest -q` [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml]

### Wave 0 Gaps
- [ ] `/home/samuel/TSC_CYCLE/tests/test_v4_reproduction_package.py` — covers REPRO-01, REPRO-03, DOC-01. [VERIFIED: tests listing]
- [ ] `/home/samuel/TSC_CYCLE/tsc_cycle/reproduction_manifest.py` — deterministic builder/validator module if planner chooses the CLI path. [ASSUMED]
- [ ] `/home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-manifest.json` — repo-level machine-readable package boundary. [ASSUMED]
- [ ] `/home/samuel/TSC_CYCLE/reproduction/v4.0-qwen3-4b-9k-guide.md` — repo-level human entry point. [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | No authentication flow is implemented in Phase 14. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md] |
| V3 Session Management | no | No sessions are implemented in Phase 14. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md] |
| V4 Access Control | no | Local filesystem reads/writes only; use repo-root path guards if builder accepts paths. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py] |
| V5 Input Validation | yes | Validate repo-relative paths stay under repo root and reject missing/malformed manifest entries. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py] |
| V6 Cryptography | yes | Use SHA-256 via stdlib `hashlib`; do not invent custom checksums. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/hashing.py] |

### Known Threat Patterns for local manifest tooling

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal from user-supplied manifest/output paths | Tampering | Use a repo-root resolver like `resolve_repo_path` that rejects paths escaping the repository. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py] |
| Secret leakage from local ignored files | Information Disclosure | Do not serialize file contents from `.env`, `.venv`, `.claude`, caches, or worktrees. [VERIFIED: /home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py] |
| Stale or forged artifact hashes | Tampering | Recompute SHA-256 from disk in tests and compare to manifest/report fields. [VERIFIED: codebase inspection] |
| Accidental destructive cleanup in Phase 14 | Tampering | Tests should assert the builder does not call destructive APIs and Phase 14 plans must not delete/archive/move. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md] |

## Sources

### Primary (HIGH confidence)
- `/home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md` — Phase boundary, constraints, specific canonical seed assets. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.json` — machine-readable cleanup-boundary and no-delete asset classifications. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.md` — maintainer-facing Phase 13 rationale and Phase 15 preconditions. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md` — REPRO-01, REPRO-03, DOC-01 definitions. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/.planning/ROADMAP.md` — Phase 14 goal and success criteria. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/.planning/STATE.md` — preserved v4.0 artifact context and current position. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/.planning/PROJECT.md` — v4.0 shipped context and v4.1 active scope. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/CLAUDE.md` — project constraints. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tsc_cycle/cleanup_inventory.py` — existing inventory constants, read-only patterns, path guard. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tsc_cycle/hashing.py` — stable JSON/hash helpers. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/tests/test_cleanup_inventory.py` — current contract-test patterns. [VERIFIED: Read]
- `/home/samuel/TSC_CYCLE/pyproject.toml` — pytest configuration and dependency declarations. [VERIFIED: Read]

### Secondary (MEDIUM confidence)
- Direct hash/count probes run during research — current working-tree artifact hashes, sizes, and JSONL line counts. [VERIFIED: Bash probes]
- Environment probes for Python, pytest, and uv versions. [VERIFIED: Bash probes]

### Tertiary (LOW confidence)
- None; assumptions are explicitly listed in the Assumptions Log. [VERIFIED: research process]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Phase 14 needs only existing Python/pytest patterns and no new external package was identified. [VERIFIED: codebase inspection]
- Architecture: HIGH — Phase 13 inventory, Phase 14 context, and existing tests strongly define the manifest/guide/validation pattern. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/14-canonical-v4-reproduction-package/14-CONTEXT.md]
- Pitfalls: HIGH — Wrong source-of-truth, wrong q4 artifact, stale hashes, and dataset omission are all visible in current project state. [VERIFIED: codebase inspection]

**Research date:** 2026-05-12 [VERIFIED: /home/samuel/TSC_CYCLE/.planning/STATE.md]
**Valid until:** 2026-06-11 for codebase-only package-boundary facts, but regenerate hashes immediately before implementation if canonical assets change. [ASSUMED]
