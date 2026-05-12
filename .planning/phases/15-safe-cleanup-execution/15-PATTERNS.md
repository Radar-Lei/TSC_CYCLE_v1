# Phase 15: Safe Cleanup Execution - Pattern Map

**Mapped:** 2026-05-12
**Files/actions analyzed:** 7
**Analogs found:** 7 / 7

## File Classification

| New/Modified File or Path | Role | Data Flow | Closest Analog | Match Quality |
|---------------------------|------|-----------|----------------|---------------|
| `.planning/phases/15-safe-cleanup-execution/pre_cleanup_git_status.txt` | documentation / audit snapshot | file-I/O, batch | `tsc_cycle/cleanup_inventory.py` + `15-VALIDATION.md` | role-match |
| `.planning/phases/15-safe-cleanup-execution/post_cleanup_git_status.txt` | documentation / audit snapshot | file-I/O, batch | `tsc_cycle/cleanup_inventory.py` + `15-VALIDATION.md` | role-match |
| `.planning/phases/15-safe-cleanup-execution/15-CLEANUP-NOTES.md` | documentation | transform, batch | `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.md` | exact-doc |
| `artifacts/v3 -> runs/_legacy_archive/phase15-safe-cleanup/artifacts-v3` | filesystem archive operation | file-I/O, batch | `tsc_cycle/cleanup_inventory.py` | partial |
| `data/v3 -> runs/_legacy_archive/phase15-safe-cleanup/data-v3` | filesystem archive operation | file-I/O, batch | `tsc_cycle/cleanup_inventory.py` | partial |
| `raw_responses -> runs/_legacy_archive/phase15-safe-cleanup/raw_responses` | filesystem archive operation | file-I/O, batch | `tsc_cycle/cleanup_inventory.py` | partial |
| `runs/v3.0-gates -> runs/_legacy_archive/phase15-safe-cleanup/runs-v3.0-gates` | filesystem archive operation | file-I/O, batch | `tsc_cycle/cleanup_inventory.py` | partial |

## Pattern Assignments

### `.planning/phases/15-safe-cleanup-execution/pre_cleanup_git_status.txt` (documentation / audit snapshot, file-I/O batch)

**Analog:** `tsc_cycle/cleanup_inventory.py` and `.planning/phases/15-safe-cleanup-execution/15-VALIDATION.md`

**Git status capture pattern** (`tsc_cycle/cleanup_inventory.py` lines 128-157):
```python
def _git_status(repo_root: Path) -> dict[str, str]:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "status",
                "--porcelain",
                "--untracked-files=normal",
                "--ignored=matching",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return {}
    statuses: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line:
            continue
        raw_status = line[:2]
        status = "ignored" if raw_status == "!!" else raw_status.strip() or "clean"
        raw_path = line[3:] if len(line) > 3 else ""
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        if raw_path:
            statuses[raw_path.rstrip("/")] = status
    return statuses
```

**Validation placement pattern** (`15-VALIDATION.md` lines 27-33, 51-55):
```markdown
- **Before archive execution:** Run the quick manifest check, the full phase subset, and capture baseline `git status --short --untracked-files=normal`.
- **After every archive move batch:** Run the quick manifest check and inspect `git status --short --untracked-files=normal`.
- **After cleanup documentation:** Run the full phase subset and review cleanup notes against archived/deferred paths.
- **Before `/gsd-verify-work`:** Quick manifest check, full phase subset, cleanup-note review, and scoped git status review must pass or be documented.

## Wave 0 Requirements

- [ ] `/home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/pre_cleanup_git_status.txt` — baseline status snapshot for CLEAN-03.
- [ ] `/home/samuel/TSC_CYCLE/.planning/phases/15-safe-cleanup-execution/15-CLEANUP-NOTES.md` — covers DOC-02 and maps archived/deferred legacy paths.
- [ ] Guarded archive action list or helper script/command sequence — covers CLEAN-01 by enforcing `phase15_allowed == archive_only`.
```

**Apply:** Snapshot files should store command output only, not payload content. Use absolute `git -C /home/samuel/TSC_CYCLE status --short --untracked-files=normal` from research, but keep contents as status lines.

---

### `.planning/phases/15-safe-cleanup-execution/post_cleanup_git_status.txt` (documentation / audit snapshot, file-I/O batch)

**Analog:** `tsc_cycle/cleanup_inventory.py` and `.planning/phases/15-safe-cleanup-execution/15-VALIDATION.md`

**Status propagation pattern** (`tsc_cycle/cleanup_inventory.py` lines 160-173):
```python
def _status_for(path: str, statuses: dict[str, str]) -> str:
    normalized = path.rstrip("/")
    if normalized in statuses:
        return statuses[normalized]
    prefix = normalized + "/"
    child_states = sorted({state for rel, state in statuses.items() if rel.startswith(prefix)})
    if child_states:
        return ",".join(child_states)
    parts = normalized.split("/")
    for depth in range(len(parts) - 1, 0, -1):
        ancestor = "/".join(parts[:depth])
        if ancestor in statuses:
            return statuses[ancestor]
    return "clean"
```

**Reviewability rule** (`15-VALIDATION.md` lines 59-64):
```markdown
| Reviewable cleanup scope | CLEAN-03 | Automated tests can validate canonical assets, but maintainers must judge whether the final git status is an intentionally scoped cleanup change set versus unrelated historical clutter | Inspect `pre_cleanup_git_status.txt`, `post_cleanup_git_status.txt`, and `git status --short --untracked-files=normal`; confirm only planned archive/documentation/status snapshot paths changed beyond pre-existing dirty state |
```

**Apply:** Post snapshot should be comparable to pre snapshot and cleanup notes. Do not include directory listings, secret values, or large payload metadata beyond git status lines.

---

### `.planning/phases/15-safe-cleanup-execution/15-CLEANUP-NOTES.md` (documentation, transform/batch)

**Analog:** `.planning/phases/13-inventory-cleanup-boundaries/inventory/inventory.md`

**Document scope and guardrail pattern** (`inventory.md` lines 5-9):
```markdown
## Scope and Non-Destructive Guarantee

Phase 13 is non-destructive: this report only mirrors the JSON inventory and does not delete, move, archive, or rewrite repository assets.
Phase 15 must consume this inventory before any archive or deletion action, and no entry below expands beyond its JSON `recommended_action` or `phase15_allowed` values.
```

**Table shape for action rationale** (`inventory.md` lines 40-45):
```markdown
## High-Impact Cleanup Boundaries

Every high-impact entry exposes `classification`, `recommended_action`, `phase15_allowed`, `rationale`, `risk_if_deleted`, and `evidence_paths` before Phase 15 cleanup planning.

| path | group | classification | recommended_action | phase15_allowed | rationale | risk_if_deleted | evidence_paths |
|------|-------|----------------|--------------------|-----------------|-----------|-----------------|----------------|
```

**Legacy/deferred candidate pattern** (`inventory.md` lines 79-96):
```markdown
## Legacy / Temporary / Removable Candidates

These entries are candidates for later archive or manual review only as allowed by their JSON fields; ambiguous v1/v3/raw/model-output groups remain archive or manual-review candidates, not immediate deletion instructions.

| path | group | classification | recommended_action | phase15_allowed | rationale | risk_if_deleted | evidence_paths |
|------|-------|----------------|--------------------|-----------------|-----------|-----------------|----------------|
| artifacts/v3 | artifacts | archived legacy | archive_candidate | archive_only | v3 reports are historical audit evidence and should be archived rather than deleted blindly. | Loss of this path could remove reproduction lineage, baseline comparison, or canonical v4 evidence before Phase 14/15 decisions. | .planning/PROJECT.md, .planning/STATE.md |
| data/v3 | data | archived legacy | archive_candidate | archive_only | v3 expanded data is lineage for v4 but not the final v4.1 reproduction target. | Loss of this path could remove reproduction lineage, baseline comparison, or canonical v4 evidence before Phase 14/15 decisions. | .planning/PROJECT.md, .planning/STATE.md |
| raw_responses | root | archived legacy | archive_candidate | archive_only | Raw teacher/API response outputs are legacy evidence and must be archived before any later deletion is considered. | Deleting this directory without review may remove audit evidence, generated outputs, or local workflow state. | .planning/phases/13-inventory-cleanup-boundaries/13-RESEARCH.md |
| reality.log | root | archived legacy | keep_or_archive | manual_review_required | Root-level file requires role-based review before cleanup; untracked or modified status alone is not a deletion signal. | Deleting root files before review may remove documentation, logs, or user-facing evidence. | .planning/phases/13-inventory-cleanup-boundaries/13-RESEARCH.md |
| runs/20260507T032419Z | runs | archived legacy | keep_or_archive | manual_review_required | v1 q4_K_M baseline is a read-only historical reference, not the v4.1 target. | Loss of this path could remove reproduction lineage, baseline comparison, or canonical v4 evidence before Phase 14/15 decisions. | .planning/PROJECT.md, .planning/STATE.md |
| runs/v3.0-gates | runs | archived legacy | archive_candidate | archive_only | v3 gate outputs are bulky legacy artifacts outside the v4.0 Qwen3-4B reproduction target. | Loss of this path could remove reproduction lineage, baseline comparison, or canonical v4 evidence before Phase 14/15 decisions. | .planning/PROJECT.md, .planning/STATE.md |
```

**Secret-safe local metadata pattern** (`reproduction/v4.0-qwen3-4b-9k-guide.md` lines 91-99, 101-105):
```markdown
### Local Temporary Metadata Only

| path | category | exists |
|------|----------|--------|
| .claude | local_temporary | True |
| .env | local_temporary | True |
| .pytest_cache | local_temporary | True |
| .venv | local_temporary | True |
| tsc_cycle/__pycache__ | local_temporary | True |

## Scope

Non-destructive metadata packaging only: no delete, archive, move, retrain, dataset regeneration, or model inference.

The manifest/guide recompute disk metadata and serialize metadata only; they do not include file payloads, secrets, cache payloads, or local environment payloads.
```

**Apply:** Cleanup notes should include at least sections for: scope, archived paths, deferred/manual-review paths, preserved canonical v4 paths, validation commands/results, and git status snapshot paths. Do not serialize `.env`, `.claude`, `.venv`, cache payloads, or directory contents.

---

### `artifacts/v3 -> runs/_legacy_archive/phase15-safe-cleanup/artifacts-v3` (filesystem archive operation, file-I/O batch)

**Analog:** `tsc_cycle/cleanup_inventory.py`

**Allowlist source pattern** (`cleanup_inventory.py` lines 426-453):
```python
def _extra_version_entries(repo_root: Path, statuses: dict[str, str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    version_paths = {
        "data/v4/phase8": ("data", "v4 reproduction source", "keep_or_archive", "manual_review_required", "v4 Phase 8 dataset rebuild outputs are reproduction candidates pending Phase 14 package selection."),
        "data/v3": ("data", "archived legacy", "archive_candidate", "archive_only", "v3 expanded data is lineage for v4 but not the final v4.1 reproduction target."),
        "artifacts/v3": ("artifacts", "archived legacy", "archive_candidate", "archive_only", "v3 reports are historical audit evidence and should be archived rather than deleted blindly."),
        "runs/v3.0-gates": ("runs", "archived legacy", "archive_candidate", "archive_only", "v3 gate outputs are bulky legacy artifacts outside the v4.0 Qwen3-4B reproduction target."),
        "runs/20260507T032419Z": ("runs", "archived legacy", "keep_or_archive", "manual_review_required", "v1 q4_K_M baseline is a read-only historical reference, not the v4.1 target."),
        "runs/v4.0-4B-20260509T184844Z": ("runs", "v4 evidence", "keep", "no_delete", "v4.0 training/export/eval run root contains canonical q4 model and required reports."),
    }
```

**Path guard pattern** (`cleanup_inventory.py` lines 94-104):
```python
def resolve_repo_path(path: Path | str, repo_root: Path | str = Path.cwd()) -> Path:
    root = Path(repo_root).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes repository root: {path}") from exc
    return resolved
```

**No-delete canonical pattern** (`tests/test_cleanup_inventory.py` lines 95-107):
```python
def test_canonical_v4_assets_are_no_delete():
    inventory = _build_inventory()
    by_path = _entries_by_path(inventory)

    missing = CANONICAL_V4_ASSETS - set(by_path)
    assert not missing

    for path in CANONICAL_V4_ASSETS:
        entry = by_path[path]
        assert entry["classification"] == "v4 evidence"
        assert entry["recommended_action"] == "keep"
        assert entry["phase15_allowed"] == "no_delete"
```

**Apply:** Move only if the inventory entry for `artifacts/v3` has `phase15_allowed == "archive_only"` and `recommended_action == "archive_candidate"`. Do not move parent `artifacts/`. Preserve v4 children under `artifacts/v4/`.

---

### `data/v3 -> runs/_legacy_archive/phase15-safe-cleanup/data-v3` (filesystem archive operation, file-I/O batch)

**Analog:** `tsc_cycle/cleanup_inventory.py` + `tsc_cycle/reproduction_manifest.py`

**Required v4 source preservation pattern** (`reproduction_manifest.py` lines 16-28):
```python
REQUIRED_SOURCE_PATHS = {
    "data/v4/phase8/labeled_merged.jsonl": "Merged v4 labeled dataset used for Qwen3-4B 9k SFT.",
    "data/v4/phase8/splits/manifest.json": "v4 Phase 8 split manifest with train/val/OOD counts.",
    "data/v4/phase8/splits/train.index.jsonl": "v4 Phase 8 train split index.",
    "data/v4/phase8/splits/val.index.jsonl": "v4 Phase 8 validation split index.",
    "data/v4/phase8/splits/ood_val.index.jsonl": "v4 Phase 8 OOD validation split index.",
}

OPTIONAL_REBUILD_CACHE_PATHS = {
    "data/v4/phase8/tokenized/train.arrow": "Tokenized train Arrow cache; useful when skipping tokenization, not required source.",
    "data/v4/phase8/tokenized/val.arrow": "Tokenized validation Arrow cache; useful when skipping tokenization, not required source.",
    "data/v4/phase8/tokenized/ood_val.arrow": "Tokenized OOD validation Arrow cache; useful when skipping tokenization, not required source.",
}
```

**Manifest validation pattern** (`reproduction_manifest.py` lines 454-498):
```python
def validate_manifest_against_disk(manifest: dict[str, Any], repo_root: Path | str) -> list[str]:
    root = Path(repo_root).resolve()
    errors: list[str] = []
    errors.extend(_validate_manifest_structure(manifest))
    required_categories = {"required_evidence", "required_source"}
    assets_by_category = manifest.get("assets") if isinstance(manifest.get("assets"), dict) else {}
    for category, assets in assets_by_category.items():
        if not isinstance(assets, list):
            errors.append(f"assets.{category} must be a list")
            continue
        for asset in assets:
            if not isinstance(asset, dict):
                errors.append(f"invalid asset in {category}: expected JSON object")
                continue
            rel_path = asset.get("path")
            if not isinstance(rel_path, str):
                errors.append(f"missing path in {category}")
                continue
            try:
                path = _resolve_repo_path(root, rel_path)
            except ValueError as exc:
                errors.append(f"{rel_path}: {exc}")
                continue
            if category in required_categories and not path.exists():
                errors.append(f"{rel_path}: required asset missing")
                continue
```

**Apply:** Move only exact `data/v3`. Do not move `data/` or `data/v4/phase8`. Run manifest check after move because `data/v4/phase8/*` required source must remain present.

---

### `raw_responses -> runs/_legacy_archive/phase15-safe-cleanup/raw_responses` (filesystem archive operation, file-I/O batch)

**Analog:** `tsc_cycle/cleanup_inventory.py` and `.gitignore`

**Top-level archive-only directory pattern** (`cleanup_inventory.py` lines 45-52):
```python
EXTRA_TOP_LEVEL_DIRS = {
    "raw_responses": (
        "root",
        "archived legacy",
        "archive_candidate",
        "archive_only",
        "Raw teacher/API response outputs are legacy evidence and must be archived before any later deletion is considered.",
    ),
```

**Ignored archive root rationale pattern** (`.gitignore` lines 4-6, 12-15):
```gitignore
runs/
gen_cache/
raw_responses/
*.gguf
wandb/
reality.log
.env
```

**Secret-safe test pattern** (`tests/test_cleanup_inventory.py` lines 111-127):
```python
def test_inventory_generator_is_read_only_and_secret_metadata_only():
    import tsc_cycle.cleanup_inventory as cleanup_inventory

    source = inspect.getsource(cleanup_inventory)
    destructive_tokens = ["unlink(", "rmtree(", "remove(", "rename(", "replace("]
    for token in destructive_tokens:
        assert token not in source, f"destructive call is forbidden: {token}"

    inventory = _build_inventory()
    by_path = _entries_by_path(inventory)
    serialized = json.dumps(inventory, ensure_ascii=False)

    assert "OPENAI_API_KEY=" not in serialized
    assert "sk-" not in serialized
    assert "file_contents" not in serialized
    assert "content" not in serialized
```

**Apply:** Archive move can be a filesystem operation, but cleanup notes must not expose raw response payload contents, prompts, or API metadata beyond source path, destination, action, and rationale.

---

### `runs/v3.0-gates -> runs/_legacy_archive/phase15-safe-cleanup/runs-v3.0-gates` (filesystem archive operation, file-I/O batch)

**Analog:** `tsc_cycle/cleanup_inventory.py`, `reproduction/v4.0-qwen3-4b-9k-guide.md`

**Runs parent manual-review pattern** (`cleanup_inventory.py` lines 288-301):
```python
if group == "runs":
    return _entry(
        rel_path=rel_path,
        repo_root=repo_root,
        statuses=statuses,
        group=group,
        classification="v4 evidence",
        recommended_action="keep_or_archive",
        phase15_allowed="manual_review_required",
        rationale="Runs contains the canonical v4 q4_K_M artifact, v4 training/export reports, v1 baseline, and bulky legacy outputs requiring per-path review.",
        risk_if_deleted="Deleting runs wholesale would destroy the shipped v4 deployment artifact and historical baselines.",
        evidence_paths=[".planning/STATE.md", ".planning/phases/13-inventory-cleanup-boundaries/13-RESEARCH.md"],
        high_impact=True,
    )
```

**Final v4 target preservation pattern** (`reproduction/v4.0-qwen3-4b-9k-guide.md` lines 8-15):
```markdown
## Final v4 Target

- Final q4_K_M GGUF: `runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf`
- SHA-256: `e290829b52b06e8a28a17e6d752f24dcc08ecd4317e9177a360187243d67d99a`
- Final replay output: `reality_test.log`
- Phase 12 replay outputs: `426`
- v4 labeled merged rows: `9501`
- v1/v3/raw outputs are not the v4 target; the v1 q4_K_M file is historical only.
```

**Verification command pattern** (`reproduction/v4.0-qwen3-4b-9k-guide.md` lines 17-32):
```markdown
## Verification Commands

```bash
python -m tsc_cycle.reproduction_manifest --check reproduction/v4.0-qwen3-4b-9k-manifest.json
```

```bash
pytest tests/test_v4_reproduction_package.py tests/test_cleanup_inventory.py -q
```
```

**Apply:** Move only exact `runs/v3.0-gates`. Do not move `runs/`, `runs/20260507T032419Z`, or `runs/v4.0-4B-20260509T184844Z`. Same-filesystem directory move is preferred over tar/copy to avoid duplicating tens of GB.

## Shared Patterns

### Inventory-driven allowlist before any file move

**Source:** `tsc_cycle/cleanup_inventory.py` lines 481-498 and `inventory.json` lines 162-179, 293-310, 346-361, 435-451

```python
def build_inventory(repo_root: Path | str = Path.cwd()) -> dict[str, Any]:
    root = resolve_repo_path(Path(repo_root), repo_root).resolve()
    statuses = _git_status(root)
    entries: list[dict[str, Any]] = []
    entries.extend(_discover_top_level_entries(root, statuses))
    entries.extend(_extra_version_entries(root, statuses))
    entries.extend(_canonical_entry(rel_path, root, statuses) for rel_path in sorted(CANONICAL_V4_ASSETS))
    entries.extend(_ensure_local_entries(root, statuses))

    deduped = {entry["path"]: entry for entry in entries}
    ordered_entries = [deduped[path] for path in sorted(deduped)]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "repo_root": str(root),
        "groups": _groups_summary(ordered_entries),
        "entries": ordered_entries,
    }
```

**Apply to:** All archive operations. Candidate set must be exactly:
- `artifacts/v3`
- `data/v3`
- `raw_responses`
- `runs/v3.0-gates`

### Repo-relative path safety

**Source:** `tsc_cycle/cleanup_inventory.py` lines 94-104; `tests/test_cleanup_inventory.py` lines 138-147; `tests/test_v4_reproduction_package.py` lines 268-277

```python
def resolve_repo_path(path: Path | str, repo_root: Path | str = Path.cwd()) -> Path:
    root = Path(repo_root).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes repository root: {path}") from exc
    return resolved
```

**Apply to:** Any generated command sequence or helper script. Reject archive source/destination paths that escape `/home/samuel/TSC_CYCLE`.

### Canonical v4 no-delete guard

**Source:** `tsc_cycle/cleanup_inventory.py` lines 18-28; `tests/test_cleanup_inventory.py` lines 95-107

```python
CANONICAL_V4_ASSETS = {
    "runs/v4.0-4B-20260509T184844Z/gguf/model.q4_K_M.gguf": "Phase 11 recommended q4_K_M deployment artifact and Phase 12 replay model.",
    "reality_test.log": "Final Phase 12 reality replay output with 426/426 parse, lint, and protocol gate successes.",
    "artifacts/v4/phase8/phase8_gate_report.json": "v4 Phase 8 dataset rebuild gate report named by state as key evidence.",
    "runs/v4.0-4B-20260509T184844Z/phase9_sft_report.json": "v4 QLoRA SFT report and Phase 10 handoff evidence.",
    "runs/v4.0-4B-20260509T184844Z/phase10_gguf_report.json": "v4 GGUF export report containing fp16/q4 paths and q4 checksum.",
    "artifacts/v4/phase11/phase11_gate_report.json": "v4 eval matrix GO decision report.",
    "artifacts/v4/phase12/phase12_report.json": "Final replay report with model/output hashes and success counts.",
    "artifacts/v4/phase12/manifest.json": "Phase 12 replay manifest supporting final reality_test.log evidence.",
    "artifacts/v4/phase12/per_sample.jsonl": "Phase 12 per-sample replay evidence supporting final gate counts.",
}
```

**Apply to:** All plans. None of these paths, nor the no-delete root `runs/v4.0-4B-20260509T184844Z`, may be moved, deleted, archived, or rewritten in Phase 15.

### Manifest validation before and after cleanup

**Source:** `tsc_cycle/reproduction_manifest.py` lines 501-523

```python
if args.check:
    check_path = _resolve_repo_path(repo_root, args.check)
    manifest = _load_json(check_path)
    if not isinstance(manifest, dict):
        print(f"invalid manifest: {check_path}")
        return 2
    errors = validate_manifest_against_disk(manifest, repo_root)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"OK: {check_path}")
    return 0
```

**Apply to:** Preflight, after archive move batch, final validation. Use `/home/samuel/TSC_CYCLE/.venv/bin/python -m tsc_cycle.reproduction_manifest --check reproduction/v4.0-qwen3-4b-9k-manifest.json` rather than system `python3`.

### Documentation output style

**Source:** `tsc_cycle/reproduction_manifest.py` lines 353-419 and `tsc_cycle/cleanup_inventory.py` lines 538-614

```python
def _md_cell(value: Any) -> str:
    text = ", ".join(str(item) for item in value) if isinstance(value, list) else str(value)
    return text.translate({ord("|"): "\\|", ord("\n"): " "})
```

**Apply to:** `15-CLEANUP-NOTES.md` tables. Escape `|` and newlines in table cells; use repo-relative paths in tables; avoid absolute paths inside reproducer-facing sections unless referring to Phase 15 snapshot files.

### No payload or secret serialization

**Source:** `tests/test_v4_reproduction_package.py` lines 193-215

```python
for asset in manifest["assets"]["local_temporary"]:
    assert set(asset) == LOCAL_TEMPORARY_METADATA_KEYS
    assert asset["category"] == "local_temporary"
    assert "sha256" not in asset
    assert "line_count" not in asset
    assert "size_bytes" not in asset

for forbidden in FORBIDDEN_SERIALIZED_TEXT:
    assert forbidden not in serialized
assert "file_contents" not in serialized
assert "content" not in serialized
```

**Apply to:** Cleanup notes and status snapshots. Never include `.env` values, `.claude` payloads, `.venv` contents, raw response bodies, or cache payload dumps.

## No Analog Found

The codebase has no existing destructive or archive-move executor. Existing cleanup modules are intentionally read-only and tests assert they do not contain destructive calls.

| File/Action | Role | Data Flow | Reason |
|-------------|------|-----------|--------|
| Guarded physical archive move implementation | filesystem archive operation | file-I/O, batch | No existing module performs `rename`, `replace`, `shutil.move`, or deletion; planner should use explicit command sequence or a very small guarded helper derived from inventory patterns, not copy a destructive implementation. |

## Metadata

**Analog search scope:** `/home/samuel/TSC_CYCLE/tsc_cycle`, `/home/samuel/TSC_CYCLE/tests`, `/home/samuel/TSC_CYCLE/.planning/phases/13-inventory-cleanup-boundaries`, `/home/samuel/TSC_CYCLE/reproduction`, `/home/samuel/TSC_CYCLE/.gitignore`, `/home/samuel/TSC_CYCLE/pyproject.toml`
**Files scanned:** 12 primary analog candidates
**Project skills:** No `.claude/skills/` or `.agents/skills/` directory found in the main worktree; `.claude/` exists only as local agent/worktree state.
**Pattern extraction date:** 2026-05-12
