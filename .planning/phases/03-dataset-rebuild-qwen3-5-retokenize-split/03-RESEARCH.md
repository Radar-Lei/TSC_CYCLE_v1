# Phase 3: Dataset Rebuild（Qwen3.5 retokenize + split） - Research

**Researched:** 2026-05-09  
**Domain:** deterministic ML dataset splitting, Qwen3.5 tokenization, Arrow artifact generation  
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

None explicitly locked — discuss phase was skipped per workflow setting. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/03-dataset-rebuild-qwen3-5-retokenize-split/03-CONTEXT.md]

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, requirements, Phase 1 gate outputs, Phase 2 merged dataset, and codebase conventions to guide decisions.

### Deferred Ideas (OUT OF SCOPE)
None — discuss phase skipped.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | 80/10/10 split (train/val/ood_val), seed=42；OOD val 包含 v1.0 OOD val 全集 + 新增 OOD subset。 | Use exact deterministic sizes `train=7601`, `val=950`, `ood_val=950` for 9501 merged samples; put all 300 v1.0 OOD rows plus 650 seed=42-sampled new OOD rows in `ood_val`. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; VERIFIED: local compact JSONL count] |
| DATA-02 | retokenize 用 Qwen3.5 tokenizer，输出到 `data/tokenized/v3/{train,val,ood_val}.arrow`。 | Use `AutoTokenizer.from_pretrained("Qwen/Qwen3.5-9B")`, existing raw-text prompt builder, and PyArrow IPC `.arrow` files. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/tokenizer_audit.json; CITED: Context7 /huggingface/transformers; CITED: Context7 Apache Arrow docs] |
| DATA-03 | 截断率 ≤5%（max_seq_length 由 MEM-01 决定）。 | Phase 1 selected `max_seq_length=2048`; Phase 3 must compute untruncated sequence lengths first and fail closed if `length > 2048` exceeds 5%. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json] |
| DATA-04 | split 索引文件持久化（含哈希），便于评测复现。 | Persist per-split JSONL indices plus manifest with sample IDs, source lineage, record hash, prompt hash, assistant hash, seed, input file SHA, and v1 OOD alignment evidence. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/hashing.py; ASSUMED] |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- User-facing output must be Simplified Chinese. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Git commit messages must not include `Co-Authored-By`. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Host is DGX Spark, and vLLM is currently unavailable. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Phase work must follow DGX Spark constraints: no cu12 flash-attn, use SDPA, protect against swap/OOM, and reuse known-good venv. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]
- Teacher API constraints from project context are not used by Phase 3 because Phase 3 is local dataset rebuild only. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md; VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]
- Training thinking labels must remain multi-sub-token and must not collide with native `<think>`. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md; VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/tokenizer_audit.json]
- Existing GSD instruction requires starting file-changing work through GSD; this research was initialized with `gsd-sdk query init.phase-op "03"`. [VERIFIED: gsd-sdk init.phase-op output]

## Summary

Phase 3 should be implemented as a fail-closed local rebuild gate over the Phase 2 merged dataset at `/home/samuel/TSC_CYCLE/data/v3/phase2/labeled_merged.jsonl`, which contains 9501 valid rows with 3000 old v1 rows and 6501 new rows. [VERIFIED: /home/samuel/TSC_CYCLE/data/v3/phase2/merge_report.json; VERIFIED: /home/samuel/TSC_CYCLE/.planning/phases/02-10k-7k/02-VERIFICATION.md] The merged dataset has 2206 rows whose root `split_hint` is `ood`: 300 from v1.0 and 1906 from v3.0 new data. [VERIFIED: local compact JSONL count]

The recommended split contract is exact-size 80/10/10 over 9501 rows: `train=7601`, `val=950`, `ood_val=950`. [VERIFIED: local arithmetic over Phase 2 count] To preserve cross-milestone comparability, `ood_val` must include every v1.0 row with `split_hint="ood"` and add exactly 650 v3.0 OOD rows sampled with `random.Random(42)` from sorted candidate IDs. [VERIFIED: local compact JSONL count; ASSUMED] The `val` split should be sampled from remaining ID rows with the same seed discipline; all remaining rows go to `train`. [ASSUMED]

Tokenization should reuse the existing raw-text path in `tsc_cycle.student.dataset` and `tsc_cycle.prompt_builder`, but Phase 3 should write new v3 artifacts rather than reusing the v1 Parquet layout. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py; VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py] The output requirement names single `.arrow` files, so use PyArrow IPC file writing for `data/tokenized/v3/train.arrow`, `val.arrow`, and `ood_val.arrow`. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md; CITED: Context7 Apache Arrow docs]

**Primary recommendation:** Build one tested CLI, `tsc_cycle.v3_gates.dataset_rebuild_v3`, that reads Phase 2 merged JSONL, creates deterministic split index artifacts under `data/splits/v3/`, tokenizes with Qwen3.5 at max length 2048, writes Arrow IPC files under `data/tokenized/v3/`, and emits a manifest/report that fails if any DATA-01..04 invariant is broken. [VERIFIED: project v3 gate pattern in `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates`; ASSUMED]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Split selection and reproducibility | Data preprocessing / Local CLI | Filesystem artifacts | This phase transforms local JSONL records into deterministic split indices and persists hashes for later eval. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| Qwen3.5 tokenization | Data preprocessing / Local CLI | Hugging Face tokenizer library | Token IDs are produced before training and consumed later by Trainer. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py] |
| Truncation gate | Data validation / Local CLI | Phase 1 memory artifact | The allowed `max_seq_length` is decided by Phase 1 MEM-01, while Phase 3 measures actual dataset lengths. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json] |
| Cross-milestone OOD comparability | Evaluation data contract | Split manifest | Phase 6 needs comparable OOD subsets; Phase 3 owns selecting and recording them. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| Arrow serialization | Data preprocessing / Local CLI | PyArrow | Phase success criteria require `.arrow` tokenized split files. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12.3 system / project requires `>=3.12,<3.13` | CLI implementation and tests | Project pyproject locks Python 3.12 range; local `/usr/bin/python` reports 3.12.3. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml; VERIFIED: local version probe] |
| Transformers | local `.venv`: 5.8.0; pyproject: `>=4.56.2,<5.0` | Qwen3.5 tokenizer loading | `AutoTokenizer.from_pretrained` is the project’s existing tokenizer entrypoint; note local version exceeds pyproject constraint, so do not reinstall during Phase 3. [VERIFIED: local importlib.metadata; VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml; CITED: Context7 /huggingface/transformers] |
| Datasets | local `.venv`: 4.8.5; pyproject: `>=3.1.0` | Optional in-memory Dataset construction / future Trainer compatibility | HF Datasets supports creating datasets from dict/list and local Arrow-backed persistence; use only if it simplifies testing, not as final `.arrow` writer. [VERIFIED: local importlib.metadata; VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml; CITED: Context7 /huggingface/datasets] |
| PyArrow | local `.venv`: 24.0.0; pyproject: `>=15.0.0` | Write exact `.arrow` IPC files | Apache Arrow docs show `pa.ipc.new_file` / `RecordBatchFileWriter` for writing Arrow IPC files. [VERIFIED: local importlib.metadata; VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml; CITED: Context7 Apache Arrow docs] |
| pytest | local `.venv`: 9.0.3; dev dependency `>=8.0.0` | RED/GREEN validation for split/tokenization invariants | Existing project tests use pytest and pyproject sets `testpaths=["tests"]`. [VERIFIED: local importlib.metadata; VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |

### Supporting
| Library / Module | Version | Purpose | When to Use |
|------------------|---------|---------|-------------|
| `tsc_cycle.prompt_builder` | in-repo | Build raw prompt and assistant text | Use for every tokenized sample to preserve v1/v3 protocol format. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py] |
| `tsc_cycle.student.dataset` | in-repo | Existing raw-text tokenization and label masking | Reuse `build_text`, metadata convention, and masking logic; harden native-ID check against untruncated IDs in Phase 3. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py] |
| `tsc_cycle.hashing` | in-repo | Canonical JSON and SHA-256 helpers | Use for persisted record/input/prompt/assistant hashes. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/hashing.py] |
| `tsc_cycle.constraint_lint` | in-repo | Optional fail-closed re-lint of split inputs/solutions | Use as a final guard that all selected records remain valid before tokenization. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase2_datagen_report.py] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyArrow IPC `.arrow` files | Existing Parquet writer under `data/tokenized/{split}/data.parquet` | Parquet matches v1 code but contradicts Phase 3 success criterion requiring `data/tokenized/v3/{train,val,ood_val}.arrow`. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py; VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| Exact-size seeded split | Hash-bucket split from existing `split_bucket(sample_id, 10)` | Hash buckets are deterministic but do not guarantee exact 80/10/10 and would put all `split_hint=ood` rows into OOD, which is too large for a 10% OOD split in v3. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py; VERIFIED: local compact JSONL count] |
| Single monolithic tokenized dataset | Three split-specific Arrow files | Split-specific files match the explicit output paths and simplify Phase 4/6 consumption. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |

**Installation:** no new install should be planned; use `/home/samuel/TSC_CYCLE/.venv` and avoid reinstalling torch/transformers/vLLM. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]

**Version verification:** package versions were verified with `importlib.metadata` in the project `.venv`; npm is not applicable because this is a Python-only phase. [VERIFIED: local version probe]

## Architecture Patterns

### System Architecture Diagram

```text
Phase 1 artifacts
  memory_budget.json(selected_max_seq=2048)
  tokenizer_audit.json(Qwen3.5 tags/native IDs)
        |
        v
Phase 2 merged JSONL (9501 valid rows) -----> load + schema/lint checks
        |                                           |
        |                                           v
        |                               classify lineage: v1 old / v3 new
        |                                           |
        v                                           v
sort candidate sample_ids ---------------> seed=42 deterministic selectors
        |                                           |
        |                  +------------------------+------------------------+
        |                  |                                                 |
        v                  v                                                 v
  ood_val index     val index from ID rows                           train index remainder
(v1 OOD all +       (950 rows)                                      (7601 rows)
650 new OOD)
        |                  |                                                 |
        +------------------+------------------------+------------------------+
                                                   |
                                                   v
                         build raw prompt + assistant via prompt_builder
                                                   |
                                                   v
                     untruncated tokenizer length + native-think leak gate
                              |                    |
                              | fail if truncation rate >5%
                              v
                     truncate to max_seq_length=2048 + loss-mask labels
                                                   |
                                                   v
                 write data/tokenized/v3/{train,val,ood_val}.arrow
                                                   |
                                                   v
                 write split manifests, hashes, truncation report, dataset card
```

All arrows and components above are local filesystem / Python preprocessing operations. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md; VERIFIED: codebase source layout]

### Recommended Project Structure

```text
tsc_cycle/v3_gates/
└── dataset_rebuild_v3.py       # Phase 3 split + retokenize + report CLI [ASSUMED]

tests/
└── test_v3_dataset_rebuild.py  # DATA-01..04 RED/GREEN invariant tests [ASSUMED]

data/splits/v3/
├── train.index.jsonl           # sample_id + hashes + lineage [ASSUMED]
├── val.index.jsonl             # sample_id + hashes + lineage [ASSUMED]
├── ood_val.index.jsonl         # includes all v1 OOD sample_ids [ASSUMED]
├── manifest.json               # seed, sizes, source SHAs, truncation stats [ASSUMED]
└── v1_ood_alignment.json       # old OOD subset proof [ASSUMED]

data/tokenized/v3/
├── train.arrow                 # Arrow IPC table [VERIFIED: ROADMAP output path]
├── val.arrow                   # Arrow IPC table [VERIFIED: ROADMAP output path]
└── ood_val.arrow               # Arrow IPC table [VERIFIED: ROADMAP output path]
```

### Pattern 1: Exact-size deterministic split
**What:** Sort candidate rows by `sample_id`, sample with `random.Random(42)`, and persist the selected IDs plus input SHA. [ASSUMED]  
**When to use:** Use for Phase 3 because the requirement names seed=42 and exact 80/10/10 split. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]  
**Example:**
```python
# Source: Python stdlib random.Random behavior [ASSUMED]
rng = random.Random(42)
new_ood_subset = rng.sample(sorted(new_ood_ids), 650)
val_ids = rng.sample(sorted(remaining_id_ids), 950)
train_ids = all_ids - set(new_ood_subset) - set(v1_ood_ids) - set(val_ids)
```

### Pattern 2: Tokenize raw text, not chat templates
**What:** Build prompt/assistant with `build_user_prompt` and `build_full_assistant`; tokenize `prompt + "\n" + assistant + eos`. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py]  
**When to use:** Use for all SFT data so native Qwen `<think>` chat-template semantics are not injected. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/tokenizer_audit.json]  
**Example:**
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py
prompt, assistant = build_text(record["input"], record["result"]["reasoning"], record["result"]["solution"])
encoded = tokenizer(prompt + "\n" + assistant + tokenizer.eos_token, add_special_tokens=False)
```

### Pattern 3: Measure truncation before truncating
**What:** Compute `raw_len` with `add_special_tokens=False` and no truncation; count `raw_len > max_seq_length` before calling tokenizer with truncation. [CITED: Context7 /huggingface/transformers]  
**When to use:** Required because DATA-03 is about truncation rate, not just successful writing. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md]  
**Example:**
```python
# Source: Context7 /huggingface/transformers tokenizer truncation docs
raw_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"]
truncated = len(raw_ids) > max_seq_length
enc = tokenizer(full_text, add_special_tokens=False, truncation=True, max_length=max_seq_length)
```

### Pattern 4: Arrow IPC file output
**What:** Build a `pyarrow.Table` with list columns and write it with `pa.ipc.new_file`. [CITED: Context7 Apache Arrow docs]  
**When to use:** Required for exact `.arrow` output paths. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]  
**Example:**
```python
# Source: Context7 Apache Arrow docs
with pa.OSFile(str(out_path), "wb") as sink:
    with pa.ipc.new_file(sink, table.schema) as writer:
        writer.write_table(table)
```

### Anti-Patterns to Avoid
- **Reusing v1 `data/tokenized/{train,val_id,val_ood}/data.parquet`:** It uses Qwen3-4B tokenizer and the old split names, so it does not satisfy Phase 3 Qwen3.5 `.arrow` output. [VERIFIED: /home/samuel/TSC_CYCLE/data/dataset_card.md; VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]
- **Putting all 2206 OOD rows into `ood_val`:** That would make `ood_val` about 23.2% of 9501 and violate the 80/10/10 target. [VERIFIED: local compact JSONL count]
- **Changing `max_seq_length` during Phase 3:** MEM-01 selected 2048, so Phase 3 should fail closed rather than silently selecting a different cap. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json]
- **Checking native `<think>` only after truncation:** A native-think leak beyond the truncation boundary could be missed; check untruncated IDs before writing. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py; ASSUMED]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tokenizer implementation | Custom BPE/token splitting | `transformers.AutoTokenizer` | Phase 1 tokenizer audit is tied to Qwen3.5 HF tokenizer behavior. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/tokenizer_audit.json; CITED: Context7 /huggingface/transformers] |
| Arrow serialization | Manual binary `.arrow` writer | `pyarrow.ipc.new_file` | Arrow IPC has a documented writer and schema handling. [CITED: Context7 Apache Arrow docs] |
| JSON canonicalization | Ad-hoc `json.dumps` variants | `tsc_cycle.hashing.canonical_json` | Project already defines stable sorted-key no-whitespace canonical JSON. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/hashing.py] |
| Constraint validation | New min/max/phase checker | `tsc_cycle.constraint_lint.validate` | Phase 2 merge gate already uses it to prove accepted rows are valid. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase2_datagen_report.py] |
| Eval split selection semantics | Unrecorded random sampling | Persisted index files with hashes | DATA-04 requires reproducibility and later v1 OOD alignment checks. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md] |

**Key insight:** The hard part is not tokenizing 9501 rows; the hard part is preserving a reproducible evaluation contract across v1/v3 while preventing silent drift in tokenizer, max sequence length, OOD subset membership, and hashes. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md; ASSUMED]

## Common Pitfalls

### Pitfall 1: OOD split ratio conflict
**What goes wrong:** All rows with `split_hint="ood"` are assigned to `ood_val`, producing 2206 OOD validation rows instead of a 10% split. [VERIFIED: local compact JSONL count]  
**Why it happens:** Existing v1 dataset code maps every `split_hint="ood"` row to `val_ood`. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py]  
**How to avoid:** Treat `split_hint="ood"` as an OOD-candidate flag; force all v1 OOD into `ood_val`, sample only enough new OOD to reach 950, and put remaining rows into train. [ASSUMED]  
**Warning signs:** `data/splits/v3/ood_val.index.jsonl` has 2206 rows or `train+val+ood_val != 9501`. [VERIFIED: local compact JSONL count]

### Pitfall 2: Off-by-one split sizing
**What goes wrong:** Rounding 9501 by ratios independently can produce totals not equal to 9501. [ASSUMED]  
**Why it happens:** 9501 × 0.10 = 950.1. [VERIFIED: local arithmetic]  
**How to avoid:** Lock `val=950`, `ood_val=950`, and `train=9501-950-950=7601`. [VERIFIED: local arithmetic]  
**Warning signs:** Manifest lacks exact split sizes or only stores ratios. [ASSUMED]

### Pitfall 3: Tokenization output format drift
**What goes wrong:** Existing code writes Parquet directories, but Phase 3 success criteria require `.arrow` files. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py; VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]  
**Why it happens:** v1 training code uses `pyarrow.parquet` and split names `val_id`/`val_ood`. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py]  
**How to avoid:** Write v3-specific Arrow IPC files and plan a Phase 4 reader update if needed. [ASSUMED]  
**Warning signs:** New artifacts appear under `data/tokenized/v3/train/data.parquet` instead of `data/tokenized/v3/train.arrow`. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]

### Pitfall 4: Truncation silently corrupts assistant/SOLUTION labels
**What goes wrong:** Truncation can remove closing tags or solution tokens while still producing arrays. [ASSUMED]  
**Why it happens:** `tokenizer(..., truncation=True, max_length=...)` clips long sequences to `max_length`. [CITED: Context7 /huggingface/transformers]  
**How to avoid:** Compute raw lengths first, record truncated sample IDs, fail if truncation rate >5%, and include a smoke assertion that every untruncated source text contains `</SOLUTION>`. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md; ASSUMED]  
**Warning signs:** `labels` end before `</SOLUTION>` tokenization, or truncation report has more than 475 truncated rows. [VERIFIED: local arithmetic]

### Pitfall 5: Local dependency mismatch hidden by pyproject
**What goes wrong:** Planner assumes pyproject versions are installed, but the local venv reports `transformers 5.8.0` while pyproject says `<5.0`. [VERIFIED: local importlib.metadata; VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml]  
**Why it happens:** Project reuses a DGX Spark venv rather than reinstalling from pyproject. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]  
**How to avoid:** Do not run dependency resolution in Phase 3; use the existing venv and test the tokenizer path directly. [ASSUMED]  
**Warning signs:** A plan contains `uv pip install -r` or attempts to downgrade/upgrade Transformers. [ASSUMED]

## Code Examples

Verified patterns from official and local sources:

### Build raw SFT text
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py
prompt = build_user_prompt(input_obj)
assistant = build_full_assistant(reasoning, solution)
full = prompt + "\n" + assistant + tokenizer.eos_token
```

### Loss-mask prompt tokens
```python
# Source: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py
pre = tokenizer(prompt + "\n", add_special_tokens=False)["input_ids"]
labels = [-100] * len(input_ids)
for i in range(len(pre), len(input_ids)):
    labels[i] = input_ids[i]
```

### Write Arrow IPC file
```python
# Source: Context7 Apache Arrow docs
with pa.OSFile(str(path), "wb") as sink:
    with pa.ipc.new_file(sink, table.schema) as writer:
        writer.write_table(table)
```

### Save Hugging Face Dataset locally when a directory format is acceptable
```python
# Source: Context7 /huggingface/datasets
encoded_dataset.save_to_disk("path/of/my/dataset/directory")
```

Use the PyArrow IPC example for Phase 3 because the required output path is a `.arrow` file, not a dataset directory. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Qwen3-4B tokenizer with `data/tokenized/{train,val_id,val_ood}/data.parquet` | Qwen3.5 tokenizer with `data/tokenized/v3/{train,val,ood_val}.arrow` | v3.0 Phase 3 | Planner must create new v3 artifacts and not overwrite v1 tokenized data. [VERIFIED: /home/samuel/TSC_CYCLE/data/dataset_card.md; VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| Hash-bucket ID split and all OOD held out | Exact-size 80/10/10 with v1 OOD pinned and v3 OOD subset sampled | v3.0 Phase 3 | Planner must handle OOD candidates separately from exact split sizes. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py; VERIFIED: local compact JSONL count; ASSUMED] |
| p99-derived max length 1164 under v1 | Phase 1 MEM-01 max length 2048 under Qwen3.5-9B | v3.0 Phase 1 | Phase 3 must use 2048 and report truncation against that fixed cap. [VERIFIED: /home/samuel/TSC_CYCLE/data/dataset_card.md; VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json] |

**Deprecated/outdated:**
- `MODEL_NAME = "Qwen/Qwen3-4B-Thinking-2507"` in `tsc_cycle.student.dataset` is outdated for Phase 3; use `Qwen/Qwen3.5-9B` from Phase 1 artifacts. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py; VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/tokenizer_audit.json]
- `val_id` / `val_ood` names are v1-era names; Phase 3 success criteria call the splits `train`, `val`, and `ood_val`. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py; VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `ood_val` should be exactly 950 rows: all 300 v1 OOD rows plus 650 sampled new OOD rows. | Summary / Phase Requirements | If the user expected all 2206 OOD rows held out, train/eval sizes and comparability contract would change. |
| A2 | Remaining OOD rows not selected for `ood_val` may be used for training. | Summary / Common Pitfalls | If OOD rows must never train, exact 80/10/10 is impossible with current OOD counts without discarding data. |
| A3 | Phase 3 should introduce `tsc_cycle.v3_gates.dataset_rebuild_v3`. | Architecture Patterns | Planner could instead refactor `tsc_cycle.student.dataset`, but a v3 gate module better matches existing v3 patterns. |
| A4 | Hash manifest should include record/prompt/assistant hashes beyond sample_id. | Phase Requirements / Don’t Hand-Roll | If only sample_id is required, extra hashes add implementation work but improve reproducibility. |
| A5 | Native think leakage should be checked on untruncated IDs before truncation. | Anti-Patterns / Pitfalls | If omitted, a leak beyond 2048 tokens could evade the check. |

## Open Questions

1. **Should `ood_val` be exact 10% or include every v3 OOD row?**
   - What we know: Roadmap says 80/10/10 and says OOD val includes v1.0 OOD full set plus v3.0 new OOD subset. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md]
   - What's unclear: Whether “subset” is intended to be the minimum needed for 10%, or a larger held-out subset. [ASSUMED]
   - Recommendation: Plan exact 10% unless user overrides, because it satisfies both 80/10/10 and v1 OOD inclusion. [ASSUMED]

2. **Should Phase 4 consume `.arrow` files directly or require a compatibility Parquet/dataset-directory mirror?**
   - What we know: Current train loader reads Parquet from `data/tokenized/{split}/data.parquet`. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/student/train.py]
   - What's unclear: Phase 4 plan may update the reader or request a compatibility output. [ASSUMED]
   - Recommendation: Phase 3 should write required `.arrow` files and optionally document a reader update needed in Phase 4, not create extra formats unless planner decides it is necessary. [ASSUMED]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `/home/samuel/TSC_CYCLE/.venv` Python packages | Tokenization and tests | ✓ | transformers 5.8.0, datasets 4.8.5, pyarrow 24.0.0, pytest 9.0.3 | No install; fail if missing. [VERIFIED: local importlib.metadata] |
| Python | CLI runtime | ✓ | 3.12.3 system; pyproject requires `>=3.12,<3.13` | Use project `.venv/bin/python`. [VERIFIED: local version probe; VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |
| uv | Avoiding dependency drift if needed | ✓ | 0.9.10 | Should not be used unless a dependency is unexpectedly absent. [VERIFIED: local version probe; VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md] |
| Git | SHA/diff checks and GSD workflow | ✓ | 2.43.0 | None needed. [VERIFIED: local version probe] |
| GPU / CUDA | Not required by Phase 3 | — | — | Tokenization should run CPU-only. [ASSUMED] |
| vLLM | Not required and unavailable | ✗ / not probed | — | Do not use. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md] |

**Missing dependencies with no fallback:** None found for Phase 3. [VERIFIED: local probes]

**Missing dependencies with fallback:** vLLM is unavailable but not needed. [VERIFIED: /home/samuel/TSC_CYCLE/CLAUDE.md]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 local `.venv`; pyproject dev dependency `pytest>=8.0.0`. [VERIFIED: local importlib.metadata; VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |
| Config file | `/home/samuel/TSC_CYCLE/pyproject.toml` with `testpaths=["tests"]` and `addopts="-q"`. [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |
| Quick run command | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py -q` [ASSUMED] |
| Full suite command | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest -q` [VERIFIED: /home/samuel/TSC_CYCLE/pyproject.toml] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| DATA-01 | Exact 80/10/10 sizes, seed=42 determinism, no overlap, all v1 OOD included, new OOD subset included | unit + integration fixture | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py::test_split_exact_sizes_and_v1_ood_alignment -q` | ❌ Wave 0 [ASSUMED] |
| DATA-02 | Tokenized outputs are `train.arrow`, `val.arrow`, `ood_val.arrow` with expected columns | unit + integration fixture | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py::test_writes_arrow_ipc_files -q` | ❌ Wave 0 [ASSUMED] |
| DATA-03 | Truncation rate computed from untruncated Qwen3.5 lengths and fails above 5% | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py::test_truncation_rate_gate_fails_closed -q` | ❌ Wave 0 [ASSUMED] |
| DATA-04 | Split index files include sample_id and hashes; manifest includes source SHAs and seed | unit | `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py::test_split_indices_persist_hashes_and_manifest -q` | ❌ Wave 0 [ASSUMED] |

### Sampling Rate
- **Per task commit:** `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py -q` [ASSUMED]
- **Per wave merge:** `/home/samuel/TSC_CYCLE/.venv/bin/python -m pytest tests/test_v3_dataset_rebuild.py tests/test_v3_dataset_raw_text.py tests/test_hashing.py -q` [ASSUMED]
- **Phase gate:** Full suite plus real CLI over `/home/samuel/TSC_CYCLE/data/v3/phase2/labeled_merged.jsonl` before `/gsd-verify-work`. [VERIFIED: Phase 2 artifact path]

### Wave 0 Gaps
- [ ] `/home/samuel/TSC_CYCLE/tests/test_v3_dataset_rebuild.py` — covers DATA-01..04. [ASSUMED]
- [ ] `/home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/dataset_rebuild_v3.py` — implementation target for the tests. [ASSUMED]
- [ ] Reader smoke for `.arrow` files using PyArrow IPC. [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | No auth path in local dataset rebuild. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| V3 Session Management | no | No session state in local dataset rebuild. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md] |
| V4 Access Control | no | Local file paths are fixed project artifacts; no multi-user API is introduced. [ASSUMED] |
| V5 Input Validation | yes | Fail-closed JSONL parsing, record schema checks, duplicate ID checks, constraint lint, and tokenizer audit reuse. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase2_datagen_report.py; VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/tokenizer_audit.json] |
| V6 Cryptography | yes, non-security hashing only | Use SHA-256 for reproducibility hashes, not for authentication or integrity trust against an adversary. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/hashing.py; ASSUMED] |

### Known Threat Patterns for local dataset rebuild

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed JSONL row causes partial artifact write | Tampering / DoS | Parse all inputs first and write outputs only after gates pass, following Phase 2 report pattern. [VERIFIED: /home/samuel/TSC_CYCLE/tsc_cycle/v3_gates/phase2_datagen_report.py] |
| Duplicate sample IDs leak across splits | Tampering | Build global ID sets, fail on duplicates/overlap, and persist split membership. [ASSUMED] |
| Path typo overwrites v1 data | Tampering | Default outputs under `data/splits/v3/` and `data/tokenized/v3/`; never write `data/labeled.jsonl` or `data/tokenized/` v1 paths. [VERIFIED: /home/samuel/TSC_CYCLE/.planning/ROADMAP.md; ASSUMED] |
| Native `<think>` token leakage | Integrity | Use Phase 1 dynamic native IDs and check untruncated token IDs. [VERIFIED: /home/samuel/TSC_CYCLE/artifacts/v3/phase1/tokenizer_audit.json; ASSUMED] |

## Sources

### Primary (HIGH confidence)
- `/home/samuel/TSC_CYCLE/.planning/phases/03-dataset-rebuild-qwen3-5-retokenize-split/03-CONTEXT.md` — Phase boundary and discretion status. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.planning/REQUIREMENTS.md` — DATA-01..04 requirement text. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.planning/ROADMAP.md` — Phase 3 goal and success criteria. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.planning/phases/01-tokenizer-llama-cpp/01-02-SUMMARY.md` — raw-text tokenization and tokenizer audit evidence. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.planning/phases/01-tokenizer-llama-cpp/01-04-SUMMARY.md` — selected `max_seq_length=2048`. [VERIFIED]
- `/home/samuel/TSC_CYCLE/artifacts/v3/phase1/memory_budget.json` — MEM-01 artifact with selected max seq. [VERIFIED]
- `/home/samuel/TSC_CYCLE/artifacts/v3/phase1/tokenizer_audit.json` — Qwen3.5 tokenizer custom/native ID evidence. [VERIFIED]
- `/home/samuel/TSC_CYCLE/.planning/phases/02-10k-7k/02-VERIFICATION.md` — Phase 2 merged dataset evidence. [VERIFIED]
- `/home/samuel/TSC_CYCLE/data/v3/phase2/merge_report.json` — 9501 merged valid rows and source counts. [VERIFIED]
- `/home/samuel/TSC_CYCLE/tsc_cycle/student/dataset.py` — existing tokenization/masking/split behavior. [VERIFIED]
- `/home/samuel/TSC_CYCLE/tsc_cycle/prompt_builder.py` — canonical prompt and assistant format. [VERIFIED]
- `/home/samuel/TSC_CYCLE/tsc_cycle/hashing.py` — canonical JSON and SHA helpers. [VERIFIED]
- Context7 `/huggingface/transformers` — tokenizer truncation/max_length docs. [CITED]
- Context7 `/huggingface/datasets` — Dataset construction and save-to-disk docs. [CITED]
- Context7 Apache Arrow docs — PyArrow IPC writer examples. [CITED]

### Secondary (MEDIUM confidence)
- Local compact JSONL probes over Phase 2 files — counts for old/new/OOD/source split; verified in session without fully reading huge file into prompt. [VERIFIED]
- Local `importlib.metadata` and CLI version probes — environment availability. [VERIFIED]

### Tertiary (LOW confidence)
- Exact choice to put non-held-out OOD rows into train — reasoned from 80/10/10 plus “new OOD subset” wording, needs user confirmation if policy-sensitive. [ASSUMED]

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — local pyproject, local installed versions, and Context7 docs were checked. [VERIFIED]
- Architecture: HIGH — phase inputs/outputs and codebase v3 gate patterns are explicit, with only the exact OOD residual policy assumed. [VERIFIED; ASSUMED]
- Pitfalls: MEDIUM — major pitfalls are grounded in existing v1 code and Phase 2 counts; native-leak-before-truncation is a preventive assumption. [VERIFIED; ASSUMED]

**Research date:** 2026-05-09  
**Valid until:** 2026-06-08 for local code/artifact facts; re-check package APIs if Transformers/Datasets are reinstalled. [ASSUMED]
