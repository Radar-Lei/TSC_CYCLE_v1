from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tsc_cycle.hashing import canonical_json, sha256_hex
from tsc_cycle.prompt_builder import (
    MALFORMED_THINK_CLOSE,
    NATIVE_THINK_TAGS,
    TAG_THINK_CLOSE,
    build_full_assistant,
    build_user_prompt,
)
from tsc_cycle.tokenizer_check import assert_no_native_think_in_ids, native_think_token_ids

EXPECTED_MODEL_NAME = "Qwen/Qwen3-4B-Thinking-2507"
FROZEN_V1_ROOT = Path("/home/samuel/TSC_CYCLE/runs/20260507T032419Z")
DEFAULT_MERGED_OUTPUT = Path("data/v4/phase8/labeled_merged.jsonl")
DEFAULT_SPLIT_DIR = Path("data/v4/phase8/splits")
DEFAULT_TOKENIZED_DIR = Path("data/v4/phase8/tokenized")
DEFAULT_ARTIFACTS_DIR = Path("artifacts/v4/phase8")
DEFAULT_PHASE7_REPORT = Path("artifacts/v4/phase7/phase7_gate_report.json")
V3_MERGED_ONLY_SOURCE = Path("data/v3/phase2/labeled_merged.jsonl")
REQUIREMENTS_SOURCE = ["DATA4B-01"]
REQUIREMENTS_REBUILD = ["DATA4B-02", "DATA4B-03", "DATA4B-04", "DATA4B-05"]


@dataclass(frozen=True, init=False)
class Phase8DatasetConfig:
    v1_valid_labeled: Path
    v3_new_lint_pass_labeled: Path
    merged_output: Path
    split_dir: Path
    tokenized_dir: Path
    artifacts_dir: Path
    phase7_gate_report: Path
    seed: int
    max_seq_length: int
    model_name: str
    max_truncation_rate: float
    merged_input: Path | None
    expected_train: int | None
    expected_val: int | None
    expected_ood_val: int | None

    def __init__(
        self,
        v1_valid_labeled: Path | str | None = None,
        v3_new_lint_pass_labeled: Path | str | None = None,
        *,
        v1_valid_labeled_jsonl: Path | str | None = None,
        v3_new_lint_pass_labeled_jsonl: Path | str | None = None,
        merged_output: Path | str | None = None,
        merged_input: Path | str | None = None,
        split_dir: Path | str = DEFAULT_SPLIT_DIR,
        tokenized_dir: Path | str = DEFAULT_TOKENIZED_DIR,
        artifacts_dir: Path | str = DEFAULT_ARTIFACTS_DIR,
        phase7_gate_report: Path | str = DEFAULT_PHASE7_REPORT,
        seed: int = 42,
        max_seq_length: int = 2048,
        model_name: str = EXPECTED_MODEL_NAME,
        max_truncation_rate: float = 0.05,
        expected_train: int | None = None,
        expected_val: int | None = None,
        expected_ood_val: int | None = None,
    ) -> None:
        v1 = v1_valid_labeled if v1_valid_labeled is not None else v1_valid_labeled_jsonl
        v3 = v3_new_lint_pass_labeled if v3_new_lint_pass_labeled is not None else v3_new_lint_pass_labeled_jsonl
        if v1 is None:
            v1 = Path("data/labeled.jsonl")
        if v3 is None:
            v3 = Path("data/v3/phase2/labeled_new.jsonl")
        split_path = Path(split_dir)
        if merged_output is None:
            merged_path = split_path / "labeled_merged.normalized.jsonl"
        else:
            merged_path = Path(merged_output)
        object.__setattr__(self, "v1_valid_labeled", Path(v1))
        object.__setattr__(self, "v3_new_lint_pass_labeled", Path(v3))
        object.__setattr__(self, "merged_output", merged_path)
        object.__setattr__(self, "split_dir", split_path)
        object.__setattr__(self, "tokenized_dir", Path(tokenized_dir))
        object.__setattr__(self, "artifacts_dir", Path(artifacts_dir))
        object.__setattr__(self, "phase7_gate_report", Path(phase7_gate_report))
        object.__setattr__(self, "seed", int(seed))
        object.__setattr__(self, "max_seq_length", int(max_seq_length))
        object.__setattr__(self, "model_name", str(model_name))
        object.__setattr__(self, "max_truncation_rate", float(max_truncation_rate))
        object.__setattr__(self, "merged_input", Path(merged_input) if merged_input is not None else None)
        object.__setattr__(self, "expected_train", expected_train)
        object.__setattr__(self, "expected_val", expected_val)
        object.__setattr__(self, "expected_ood_val", expected_ood_val)

    @property
    def v1_valid_labeled_jsonl(self) -> Path:
        return self.v1_valid_labeled

    @property
    def v3_new_lint_pass_labeled_jsonl(self) -> Path:
        return self.v3_new_lint_pass_labeled

    @property
    def merged_jsonl(self) -> Path:
        return self.merged_output


@dataclass(frozen=True)
class _PreparedSource:
    rows: list[dict[str, Any]]
    report: dict[str, Any]
    cleaning_report: dict[str, Any]
    fatal_failures: list[dict[str, str]]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _assert_not_frozen_output(path: Path) -> None:
    if _is_relative_to(path, FROZEN_V1_ROOT):
        raise ValueError(f"refusing to write v4 Phase 8 artifact under frozen v1 baseline root: {path}")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _assert_not_frozen_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"missing JSONL artifact: {path}"]
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"malformed JSONL {path}:{line_no}: {exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"JSONL row must be an object {path}:{line_no}")
            continue
        rows.append(value)
    return rows, errors


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _assert_not_frozen_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")


def _add_gate(
    gates: dict[str, Any],
    fatal_failures: list[dict[str, str]],
    name: str,
    ok: bool,
    reason: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    gates[name] = {"ok": bool(ok), "reason": reason, "data": data or {}}
    if not ok:
        fatal_failures.append({"gate": name, "reason": reason or "failed"})


def _record_input(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("input")
    return value if isinstance(value, dict) else record


def _record_result(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("result")
    return value if isinstance(value, dict) else record


def _record_sample_id(record: dict[str, Any]) -> str:
    for container in (record, _record_input(record), record.get("metadata") if isinstance(record.get("metadata"), dict) else {}):
        if isinstance(container, dict) and container.get("sample_id") is not None:
            return str(container["sample_id"])
    return sha256_hex(canonical_json(_record_input(record)))


def _record_lineage(record: dict[str, Any]) -> str:
    for container in (record, _record_input(record), record.get("metadata") if isinstance(record.get("metadata"), dict) else {}):
        if not isinstance(container, dict):
            continue
        for key in ("lineage", "milestone", "version"):
            value = container.get(key)
            if value:
                return str(value)
    sample_id = _record_sample_id(record)
    if sample_id.startswith("v1-"):
        return "v1.0"
    if sample_id.startswith("v3-"):
        return "v3.0"
    return "unknown"


def _record_source(record: dict[str, Any]) -> str:
    for container in (record, _record_input(record), record.get("metadata") if isinstance(record.get("metadata"), dict) else {}):
        if not isinstance(container, dict):
            continue
        for key in ("split_hint", "source", "source_tag"):
            value = container.get(key)
            if value:
                return str(value)
    return "unknown"


def _record_reasoning(record: dict[str, Any]) -> str:
    result = _record_result(record)
    value = result.get("reasoning", "")
    return "" if value is None else str(value)


def _record_solution(record: dict[str, Any]) -> dict[str, int]:
    result = _record_result(record)
    value = result.get("solution", {})
    if not isinstance(value, dict):
        return {}
    return {str(key): int(val) for key, val in value.items()}


def _is_v1(record: dict[str, Any]) -> bool:
    lineage = _record_lineage(record).lower()
    sample_id = _record_sample_id(record)
    if "v1" in lineage or sample_id.startswith("v1-"):
        return True
    if "v3" in lineage or sample_id.startswith("v3-"):
        return False
    return False


def _is_ood(record: dict[str, Any]) -> bool:
    return _record_source(record).lower() == "ood"


def _normalize_value(value: Any) -> tuple[Any, int]:
    if isinstance(value, str):
        count = value.count(MALFORMED_THINK_CLOSE)
        return value.replace(MALFORMED_THINK_CLOSE, TAG_THINK_CLOSE), count
    if isinstance(value, list):
        out: list[Any] = []
        total = 0
        for item in value:
            normalized, count = _normalize_value(item)
            out.append(normalized)
            total += count
        return out, total
    if isinstance(value, dict):
        out_dict: dict[str, Any] = {}
        total = 0
        for key, item in value.items():
            normalized, count = _normalize_value(item)
            out_dict[str(key)] = normalized
            total += count
        return out_dict, total
    return value, 0


def _without_lineage(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _without_lineage(v) for k, v in value.items() if k not in {"lineage", "milestone", "version"}}
    if isinstance(value, list):
        return [_without_lineage(item) for item in value]
    return value


def _dedupe_hash(record: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(_without_lineage(record)))


def _manifest_hash(record: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(record))


def _phase7_allowed(config: Phase8DatasetConfig) -> tuple[bool, dict[str, Any]]:
    report = _read_json(config.phase7_gate_report)
    ok = report.get("ok") is True and report.get("next_phase_allowed") is True
    return ok, {"path": str(config.phase7_gate_report), "ok": report.get("ok"), "next_phase_allowed": report.get("next_phase_allowed")}


def _explicit_sources_ok(config: Phase8DatasetConfig) -> tuple[bool, str | None, dict[str, Any]]:
    data = {
        "v1_valid_labeled_jsonl": str(config.v1_valid_labeled),
        "v3_new_lint_pass_labeled_jsonl": str(config.v3_new_lint_pass_labeled),
        "merged_input_provided": config.merged_input is not None,
    }
    if config.merged_input is not None:
        return False, "DATA4B-01 requires explicit v1 valid and v3 new lint-pass sources, not a merged_input shortcut", data
    missing = [str(path) for path in (config.v1_valid_labeled, config.v3_new_lint_pass_labeled) if not path.exists()]
    if missing:
        return False, f"missing explicit source files: {missing}", data
    try:
        same_file = config.v1_valid_labeled.resolve() == config.v3_new_lint_pass_labeled.resolve()
    except FileNotFoundError:
        same_file = False
    if same_file:
        return False, "v1 and v3 source paths must be distinct", data
    if config.v1_valid_labeled.as_posix().endswith(V3_MERGED_ONLY_SOURCE.as_posix()) or config.v3_new_lint_pass_labeled.as_posix().endswith(V3_MERGED_ONLY_SOURCE.as_posix()):
        data["legacy_merged_source_rejected"] = True
        return False, "the prior merged source is not an allowed Phase 8 source", data
    return True, None, data


def _source_label(source_name: str) -> str:
    return "v1_valid" if source_name == "v1_valid_labeled_jsonl" else "v3_new_lint_pass"


def _prepare_source(config: Phase8DatasetConfig) -> _PreparedSource:
    for path in (config.merged_output, config.artifacts_dir / "source_manifest.json", config.artifacts_dir / "cleaning_report.json"):
        _assert_not_frozen_output(path)

    fatal_failures: list[dict[str, str]] = []
    gates: dict[str, Any] = {}
    phase7_ok, phase7_data = _phase7_allowed(config)
    _add_gate(gates, fatal_failures, "phase7_next_phase_allowed", phase7_ok, None if phase7_ok else "Phase 7 report must have ok=true and next_phase_allowed=true", phase7_data)
    explicit_ok, explicit_reason, explicit_data = _explicit_sources_ok(config)
    _add_gate(gates, fatal_failures, "explicit_two_sources", explicit_ok, explicit_reason, explicit_data)

    source_rows: dict[str, list[dict[str, Any]]] = {"v1_valid_labeled_jsonl": [], "v3_new_lint_pass_labeled_jsonl": []}
    read_errors: list[str] = []
    if explicit_ok:
        for source_name, path in (
            ("v1_valid_labeled_jsonl", config.v1_valid_labeled),
            ("v3_new_lint_pass_labeled_jsonl", config.v3_new_lint_pass_labeled),
        ):
            rows, errors = _read_jsonl(path)
            source_rows[source_name] = rows
            read_errors.extend(errors)
    _add_gate(gates, fatal_failures, "jsonl_read", not read_errors, None if not read_errors else "; ".join(read_errors[:5]), {"error_count": len(read_errors)})

    normalized_by_source: dict[str, list[dict[str, Any]]] = {"v1_valid_labeled_jsonl": [], "v3_new_lint_pass_labeled_jsonl": []}
    malformed_replacements = 0
    native_rows: list[str] = []
    malformed_remaining_rows: list[str] = []
    for source_name, rows in source_rows.items():
        for row in rows:
            normalized, count = _normalize_value(row)
            assert isinstance(normalized, dict)
            malformed_replacements += count
            text = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
            sample_id = _record_sample_id(normalized)
            if any(tag in text for tag in NATIVE_THINK_TAGS):
                native_rows.append(sample_id)
            if MALFORMED_THINK_CLOSE in text:
                malformed_remaining_rows.append(sample_id)
            normalized_by_source[source_name].append(normalized)

    _add_gate(gates, fatal_failures, "native_think_text_absent", not native_rows, None if not native_rows else f"native think text rows={len(native_rows)}", {"sample_ids": native_rows[:25]})
    _add_gate(gates, fatal_failures, "malformed_close_normalized", not malformed_remaining_rows, None if not malformed_remaining_rows else f"malformed close remains rows={len(malformed_remaining_rows)}", {"sample_ids": malformed_remaining_rows[:25]})

    kept: dict[str, tuple[str, dict[str, Any]]] = {}
    duplicate_samples: list[dict[str, Any]] = []
    duplicate_counts = {"total_duplicate_rows": 0, "v1_duplicate_rows": 0, "v3_duplicate_rows": 0}
    for source_name in ("v1_valid_labeled_jsonl", "v3_new_lint_pass_labeled_jsonl"):
        short_source = _source_label(source_name)
        for row in normalized_by_source[source_name]:
            key = _dedupe_hash(row)
            sample_id = _record_sample_id(row)
            if key not in kept:
                kept[key] = (short_source, row)
                continue
            kept_source, _kept_row = kept[key]
            dropped_source = short_source
            if short_source == "v1_valid" and kept_source != "v1_valid":
                dropped_source = kept_source
                kept[key] = (short_source, row)
            duplicate_counts["total_duplicate_rows"] += 1
            if dropped_source == "v1_valid":
                duplicate_counts["v1_duplicate_rows"] += 1
            if dropped_source == "v3_new_lint_pass":
                duplicate_counts["v3_duplicate_rows"] += 1
            duplicate_samples.append({"sample_id": sample_id, "kept_source": kept[key][0], "dropped_source": dropped_source, "dedupe_hash": key})

    merged_rows = [row for _source, row in sorted(kept.values(), key=lambda item: _record_sample_id(item[1]))]
    sample_hashes = sorted(_manifest_hash(row) for row in merged_rows)
    source_counts = {"v1_valid": len(source_rows["v1_valid_labeled_jsonl"]), "v3_new_lint_pass": len(source_rows["v3_new_lint_pass_labeled_jsonl"])}
    source_sha = {
        "v1_valid": _sha256_file(config.v1_valid_labeled) if config.v1_valid_labeled.exists() else "",
        "v3_new_lint_pass": _sha256_file(config.v3_new_lint_pass_labeled) if config.v3_new_lint_pass_labeled.exists() else "",
    }
    ok = not fatal_failures
    cleaning_report = {
        "ok": ok,
        "malformed_think_close_replacements": malformed_replacements,
        "malformed_close_replacements": malformed_replacements,
        "native_think_occurrences": len(native_rows),
        "malformed_close_remaining": len(malformed_remaining_rows),
        "forbidden_native_think_rows": native_rows,
        "forbidden_malformed_close_after_normalization": malformed_remaining_rows,
        "requirements_covered": REQUIREMENTS_SOURCE,
        "gates": gates,
        "fatal_failures": fatal_failures,
    }
    manifest = {
        "ok": ok,
        "allowed_sources": ["v1_valid_labeled", "v3_new_lint_pass_labeled"],
        "sources": {
            "v1_valid_labeled_jsonl": str(config.v1_valid_labeled),
            "v3_new_lint_pass_labeled_jsonl": str(config.v3_new_lint_pass_labeled),
        },
        "source_counts": source_counts,
        "source_sha256": source_sha,
        "merged_count": len(merged_rows),
        "deduped_count": len(merged_rows),
        "duplicate_count": duplicate_counts["total_duplicate_rows"],
        "duplicate_counts": duplicate_counts,
        "duplicate_samples": duplicate_samples[:100],
        "dedupe_key": "canonical_normalized_record_sha256",
        "sample_hashes": sample_hashes,
        "sample_hash_digest": sha256_hex(canonical_json(sample_hashes)),
        "requirements_covered": REQUIREMENTS_SOURCE,
        "gates": gates,
        "fatal_failures": fatal_failures,
        "paths": {
            "merged_jsonl": str(config.merged_output),
            "source_manifest": str(config.artifacts_dir / "source_manifest.json"),
            "cleaning_report": str(config.artifacts_dir / "cleaning_report.json"),
        },
    }
    report = {
        "ok": ok,
        "requirements_covered": REQUIREMENTS_SOURCE,
        "source_counts": source_counts,
        "deduped_count": len(merged_rows),
        "duplicates": {"v3_duplicate_rows": duplicate_counts["v3_duplicate_rows"], "v1_duplicate_rows": duplicate_counts["v1_duplicate_rows"], "total_duplicate_rows": duplicate_counts["total_duplicate_rows"]},
        "source_manifest_path": str(config.artifacts_dir / "source_manifest.json"),
        "cleaning_report_path": str(config.artifacts_dir / "cleaning_report.json"),
        "merged_jsonl_path": str(config.merged_output),
        "gates": gates,
        "fatal_failures": fatal_failures,
        "source_manifest": manifest,
        "cleaning_report": cleaning_report,
    }
    return _PreparedSource(rows=merged_rows, report=report, cleaning_report=cleaning_report, fatal_failures=fatal_failures)


def build_v4_source_dataset(config: Phase8DatasetConfig) -> dict[str, Any]:
    prepared = _prepare_source(config)
    _write_json(config.artifacts_dir / "cleaning_report.json", prepared.cleaning_report)
    _write_json(config.artifacts_dir / "source_manifest.json", prepared.report["source_manifest"])
    if prepared.report["ok"]:
        _write_jsonl(config.merged_output, prepared.rows)
    return prepared.report


def _split_targets(total: int, config: Phase8DatasetConfig) -> tuple[int, int, int]:
    if config.expected_train is not None and config.expected_val is not None and config.expected_ood_val is not None:
        return int(config.expected_train), int(config.expected_val), int(config.expected_ood_val)
    ood = round(total * 0.10)
    val = round(total * 0.10)
    train = total - val - ood
    return train, val, ood


def _make_split_rows(rows: list[dict[str, Any]], config: Phase8DatasetConfig) -> tuple[dict[str, list[tuple[int, dict[str, Any]]]], dict[str, Any], list[dict[str, str]]]:
    fatal_failures: list[dict[str, str]] = []
    indexed = list(enumerate(rows))
    train_target, val_target, ood_target = _split_targets(len(indexed), config)
    v1_ood = [(idx, row) for idx, row in indexed if _is_v1(row) and _is_ood(row)]
    v3_ood = [(idx, row) for idx, row in indexed if not _is_v1(row) and _is_ood(row)]
    gates: dict[str, Any] = {}
    _add_gate(gates, fatal_failures, "v1_ood_fits_target", len(v1_ood) <= ood_target, None if len(v1_ood) <= ood_target else f"v1 OOD rows {len(v1_ood)} > ood target {ood_target}")
    needed_v3_ood = max(0, ood_target - len(v1_ood))
    _add_gate(gates, fatal_failures, "v3_extended_ood_pool", len(v3_ood) >= needed_v3_ood, None if len(v3_ood) >= needed_v3_ood else f"v3 OOD pool {len(v3_ood)} < needed {needed_v3_ood}")
    selected_v3_ood: list[tuple[int, dict[str, Any]]] = []
    split_rows: dict[str, list[tuple[int, dict[str, Any]]]] = {"train": [], "val": [], "ood_val": []}
    if not fatal_failures:
        rng = random.Random(config.seed)
        sorted_v3_ood = sorted(v3_ood, key=lambda item: _record_sample_id(item[1]))
        selected_v3_ood = rng.sample(sorted_v3_ood, needed_v3_ood) if needed_v3_ood else []
        ood_indices = {idx for idx, _row in [*v1_ood, *selected_v3_ood]}
        remaining = [(idx, row) for idx, row in indexed if idx not in ood_indices]
        sorted_remaining = sorted(remaining, key=lambda item: _record_sample_id(item[1]))
        if len(sorted_remaining) < val_target:
            fatal_failures.append({"gate": "val_pool", "reason": f"remaining rows {len(sorted_remaining)} < val target {val_target}"})
        else:
            val_rows = rng.sample(sorted_remaining, val_target) if val_target else []
            val_indices = {idx for idx, _row in val_rows}
            train_rows = [(idx, row) for idx, row in sorted_remaining if idx not in val_indices]
            if len(train_rows) != train_target:
                fatal_failures.append({"gate": "split_sizes", "reason": f"train size {len(train_rows)} != target {train_target}"})
            split_rows = {
                "train": sorted(train_rows, key=lambda item: _record_sample_id(item[1])),
                "val": sorted(val_rows, key=lambda item: _record_sample_id(item[1])),
                "ood_val": sorted([*v1_ood, *selected_v3_ood], key=lambda item: _record_sample_id(item[1])),
            }
    split_ids = {name: [_record_sample_id(row) for _idx, row in split_rows[name]] for name in ("train", "val", "ood_val")}
    overlaps = sum(len(set(split_ids[a]) & set(split_ids[b])) for a, b in (("train", "val"), ("train", "ood_val"), ("val", "ood_val")))
    if overlaps:
        fatal_failures.append({"gate": "split_overlap", "reason": f"split overlap count={overlaps}"})
    metadata = {
        "seed": config.seed,
        "targets": {"train": train_target, "val": val_target, "ood_val": ood_target},
        "split_ids": split_ids,
        "split_counts": {name: len(ids) for name, ids in split_ids.items()},
        "v1_ood_alignment": {
            "all_v1_ood_in_ood_val": set(_record_sample_id(row) for _idx, row in v1_ood) <= set(split_ids["ood_val"]),
            "v1_ood_count": len(v1_ood),
            "ood_val_v1_ood_count": sum(1 for _idx, row in split_rows["ood_val"] if _is_v1(row) and _is_ood(row)),
            "v1_ood_sample_ids": sorted(_record_sample_id(row) for _idx, row in v1_ood),
            "v1_ood_sample_ids_sha256": sha256_hex(canonical_json(sorted(_record_sample_id(row) for _idx, row in v1_ood))),
        },
        "v3_extended_ood": {
            "selected_count": len(selected_v3_ood),
            "sample_ids": sorted(_record_sample_id(row) for _idx, row in selected_v3_ood),
        },
        "gates": gates,
    }
    return split_rows, metadata, fatal_failures


def _index_row(record: dict[str, Any], split: str, raw_index: int, seed: int) -> dict[str, Any]:
    input_obj = _record_input(record)
    solution = _record_solution(record)
    prompt = build_user_prompt(input_obj)
    assistant = build_full_assistant(_record_reasoning(record), solution)
    return {
        "sample_id": _record_sample_id(record),
        "split": split,
        "lineage": _record_lineage(record),
        "source": _record_source(record),
        "record_hash": _manifest_hash(record),
        "input_hash": sha256_hex(canonical_json(input_obj)),
        "solution_hash": sha256_hex(canonical_json(solution)),
        "prompt_hash": sha256_hex(prompt),
        "assistant_hash": sha256_hex(assistant),
        "raw_index": raw_index,
        "seed": seed,
        "is_v1_ood": _is_v1(record) and _is_ood(record),
    }


def _write_split_indexes(config: Phase8DatasetConfig, split_rows: dict[str, list[tuple[int, dict[str, Any]]]], report: dict[str, Any]) -> None:
    for path in (
        config.split_dir / "train.index.jsonl",
        config.split_dir / "val.index.jsonl",
        config.split_dir / "ood_val.index.jsonl",
        config.split_dir / "v1_ood_alignment.json",
        config.split_dir / "manifest.json",
    ):
        _assert_not_frozen_output(path)
    for split_name, rows in split_rows.items():
        _write_jsonl(config.split_dir / f"{split_name}.index.jsonl", [_index_row(row, split_name, raw_index, config.seed) for raw_index, row in rows])
    _write_json(config.split_dir / "v1_ood_alignment.json", report["v1_ood_alignment"])
    manifest = {
        "ok": report["ok"],
        "seed": config.seed,
        "split_counts": report["split_counts"],
        "split_ids_sha256": {name: sha256_hex(canonical_json(ids)) for name, ids in report["split_ids"].items()},
        "requirements_covered": REQUIREMENTS_REBUILD,
        "v1_ood_alignment": report["v1_ood_alignment"],
        "v3_extended_ood": report["v3_extended_ood"],
        "paths": {
            "train_index": str(config.split_dir / "train.index.jsonl"),
            "val_index": str(config.split_dir / "val.index.jsonl"),
            "ood_val_index": str(config.split_dir / "ood_val.index.jsonl"),
        },
    }
    _write_json(config.split_dir / "manifest.json", manifest)


def _load_tokenizer(model_name: str) -> Any:
    if model_name != EXPECTED_MODEL_NAME:
        raise ValueError(f"expected tokenizer model {EXPECTED_MODEL_NAME}, got {model_name}")
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model_name)


def _tokenize_record(record: dict[str, Any], tokenizer: Any, *, native_ids: set[int], max_seq_length: int, split: str) -> dict[str, Any]:
    input_obj = _record_input(record)
    solution = _record_solution(record)
    prompt = build_user_prompt(input_obj)
    assistant = build_full_assistant(_record_reasoning(record), solution)
    full_text = prompt + assistant
    raw_ids = list(tokenizer(full_text, add_special_tokens=False)["input_ids"])
    try:
        assert_no_native_think_in_ids(raw_ids, native_ids)
    except AssertionError as exc:
        return {"ok": False, "error": "native_think_token_leak", "reason": str(exc), "sample_id": _record_sample_id(record), "split": split}
    prompt_ids = list(tokenizer(prompt, add_special_tokens=False)["input_ids"])
    input_ids = raw_ids[:max_seq_length]
    assistant_ids = raw_ids[len(prompt_ids):]
    labels = ([-100] * len(prompt_ids) + assistant_ids)[:max_seq_length]
    return {
        "ok": True,
        "sample_id": _record_sample_id(record),
        "input_ids": input_ids,
        "attention_mask": [1] * len(input_ids),
        "labels": labels,
        "raw_length": len(raw_ids),
        "truncated": len(raw_ids) > max_seq_length,
        "prompt_hash": sha256_hex(prompt),
        "assistant_hash": sha256_hex(assistant),
        "split": split,
    }


def _write_arrow_split(path: Path, rows_tok: list[dict[str, Any]]) -> None:
    _assert_not_frozen_output(path)
    import pyarrow as pa

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "sample_id": [row["sample_id"] for row in rows_tok],
            "input_ids": [row["input_ids"] for row in rows_tok],
            "attention_mask": [row["attention_mask"] for row in rows_tok],
            "labels": [row["labels"] for row in rows_tok],
            "raw_length": [row["raw_length"] for row in rows_tok],
            "truncated": [row["truncated"] for row in rows_tok],
            "prompt_hash": [row["prompt_hash"] for row in rows_tok],
            "assistant_hash": [row["assistant_hash"] for row in rows_tok],
        }
    )
    with pa.OSFile(str(path), "wb") as sink:
        with pa.ipc.new_file(sink, table.schema) as writer:
            writer.write_table(table)


def build_v4_splits_and_tokenized(config: Phase8DatasetConfig, *, tokenizer: Any | None = None, write_tokenized: bool = True) -> dict[str, Any]:
    for path in (config.tokenized_dir / "train.arrow", config.tokenized_dir / "val.arrow", config.tokenized_dir / "ood_val.arrow", config.artifacts_dir / "rebuild_report.json"):
        _assert_not_frozen_output(path)
    source_report = build_v4_source_dataset(config)
    if source_report["ok"] and config.merged_output.exists():
        rows, read_errors = _read_jsonl(config.merged_output)
    else:
        prepared = _prepare_source(config)
        rows, read_errors = prepared.rows, []

    fatal_failures: list[dict[str, str]] = []
    gates: dict[str, Any] = {}
    _add_gate(gates, fatal_failures, "source_dataset", source_report.get("ok") is True, None if source_report.get("ok") is True else "source dataset gates failed", {"fatal_failures": source_report.get("fatal_failures", [])[:10]})
    _add_gate(gates, fatal_failures, "merged_jsonl_read", not read_errors, None if not read_errors else "; ".join(read_errors[:5]), {"error_count": len(read_errors)})
    model_ok = config.model_name == EXPECTED_MODEL_NAME
    _add_gate(gates, fatal_failures, "model_name", model_ok, None if model_ok else f"expected {EXPECTED_MODEL_NAME}, got {config.model_name}")

    split_rows, split_meta, split_failures = _make_split_rows(rows, config)
    for failure in split_failures:
        fatal_failures.append(failure)
    gates.update(split_meta.get("gates", {}))

    tokenizer = tokenizer if tokenizer is not None else _load_tokenizer(config.model_name)
    native_ids = set(native_think_token_ids(tokenizer))
    _add_gate(gates, fatal_failures, "native_think_token_ids_checked_before_truncation", bool(native_ids), None if native_ids else "native think token IDs must be derived from tokenizer before truncation", {"native_think_token_ids": sorted(native_ids)})

    tokenized_by_split: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "ood_val": []}
    token_failures: list[dict[str, Any]] = []
    raw_lengths: list[int] = []
    truncated_ids: list[str] = []
    for split_name, split_items in split_rows.items():
        for _raw_index, record in split_items:
            row_tok = _tokenize_record(record, tokenizer, native_ids=native_ids, max_seq_length=config.max_seq_length, split=split_name)
            if not row_tok["ok"]:
                token_failures.append(row_tok)
                continue
            raw_lengths.append(int(row_tok["raw_length"]))
            if row_tok["truncated"]:
                truncated_ids.append(str(row_tok["sample_id"]))
            tokenized_by_split[split_name].append(row_tok)

    total_considered = sum(len(items) for items in split_rows.values())
    over_length_count = len(truncated_ids)
    over_length_rate = over_length_count / total_considered if total_considered else 0.0
    _add_gate(gates, fatal_failures, "native_think_token_leak", not token_failures, None if not token_failures else f"native think token leak count={len(token_failures)}", {"failures_sample": token_failures[:10]})
    _add_gate(gates, fatal_failures, "truncation_rate", over_length_rate <= config.max_truncation_rate, None if over_length_rate <= config.max_truncation_rate else f"truncation rate {over_length_rate:.6f} > {config.max_truncation_rate}", {"over_length_count": over_length_count, "total": total_considered})

    report = {
        "ok": not fatal_failures,
        "seed": config.seed,
        "requirements_covered": REQUIREMENTS_REBUILD,
        "source_report_path": source_report.get("source_manifest_path"),
        "split_ids": split_meta["split_ids"],
        "split_counts": split_meta["split_counts"],
        "v1_ood_alignment": split_meta["v1_ood_alignment"],
        "v3_extended_ood": split_meta["v3_extended_ood"],
        "native_think_token_ids": sorted(native_ids),
        "gates": gates,
        "fatal_failures": fatal_failures,
        "tokenized_paths": {
            "train": str(config.tokenized_dir / "train.arrow"),
            "val": str(config.tokenized_dir / "val.arrow"),
            "ood_val": str(config.tokenized_dir / "ood_val.arrow"),
        },
        "truncation": {
            "max_seq_length": config.max_seq_length,
            "over_length_count": over_length_count,
            "over_length_rate": over_length_rate,
            "max_allowed_rate": config.max_truncation_rate,
            "truncated_sample_ids_sample": truncated_ids[:25],
            "max_raw_length": max(raw_lengths) if raw_lengths else 0,
        },
    }
    _write_split_indexes(config, split_rows, report)
    _write_json(config.artifacts_dir / "rebuild_report.json", report)
    if report["ok"] and write_tokenized:
        for split_name, rows_tok in tokenized_by_split.items():
            _write_arrow_split(config.tokenized_dir / f"{split_name}.arrow", rows_tok)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild v4 Phase 8 Qwen3-4B dataset splits and tokenized Arrow artifacts")
    parser.add_argument("--v1-valid-labeled-jsonl", "--v1-valid-labeled", dest="v1_valid_labeled_jsonl", default="data/labeled.jsonl")
    parser.add_argument("--v3-new-lint-pass-labeled-jsonl", "--v3-new-lint-pass-labeled", dest="v3_new_lint_pass_labeled_jsonl", default="data/v3/phase2/labeled_new.jsonl")
    parser.add_argument("--merged-output", default=str(DEFAULT_MERGED_OUTPUT))
    parser.add_argument("--split-dir", "--splits-dir", dest="split_dir", default=str(DEFAULT_SPLIT_DIR))
    parser.add_argument("--tokenized-dir", default=str(DEFAULT_TOKENIZED_DIR))
    parser.add_argument("--artifacts-dir", default=str(DEFAULT_ARTIFACTS_DIR))
    parser.add_argument("--phase7-gate-report", default=str(DEFAULT_PHASE7_REPORT))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--max-truncation-rate", type=float, default=0.05)
    parser.add_argument("--model-name", default=EXPECTED_MODEL_NAME)
    parser.add_argument("--expected-train", type=int, default=None)
    parser.add_argument("--expected-val", type=int, default=None)
    parser.add_argument("--expected-ood-val", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = Phase8DatasetConfig(
        v1_valid_labeled_jsonl=Path(args.v1_valid_labeled_jsonl),
        v3_new_lint_pass_labeled_jsonl=Path(args.v3_new_lint_pass_labeled_jsonl),
        merged_output=Path(args.merged_output),
        split_dir=Path(args.split_dir),
        tokenized_dir=Path(args.tokenized_dir),
        artifacts_dir=Path(args.artifacts_dir),
        phase7_gate_report=Path(args.phase7_gate_report),
        seed=args.seed,
        max_seq_length=args.max_seq_length,
        model_name=args.model_name,
        max_truncation_rate=args.max_truncation_rate,
        expected_train=args.expected_train,
        expected_val=args.expected_val,
        expected_ood_val=args.expected_ood_val,
    )
    report = build_v4_splits_and_tokenized(config, write_tokenized=not args.dry_run)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
