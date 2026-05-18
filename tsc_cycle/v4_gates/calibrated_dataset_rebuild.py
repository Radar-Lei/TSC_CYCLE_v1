from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tsc_cycle.constraint_lint import validate
from tsc_cycle.hashing import canonical_json, sha256_hex
from tsc_cycle.prompt_builder import build_full_assistant, build_user_prompt
from tsc_cycle.v4_gates.phase17_audit import DEFAULT_THRESHOLDS, evaluate_saturation_policy_gate
from tsc_cycle.v4_gates.saturation_policy import (
    VIOLATION_UNSATURATED_MAX_GREEN,
    classify_saturation_band,
    classify_violation,
    compute_saturation_audit,
)

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
FROZEN_V1_ROOT = PROJECT_ROOT / "runs" / "20260507T032419Z"
DEFAULT_SOURCE_DATASET = Path("data/v4/phase8/labeled_merged.jsonl")
DEFAULT_SOURCE_SPLIT_DIR = Path("data/v4/phase8/splits")
DEFAULT_OUTPUT_DATASET = Path("data/v4_2/phase18/labeled_calibrated.jsonl")
DEFAULT_OUTPUT_SPLIT_DIR = Path("data/v4_2/phase18/splits")
DEFAULT_TOKENIZED_DIR = Path("data/v4_2/phase18/tokenized")
DEFAULT_ARTIFACTS_DIR = Path("artifacts/v4_2/phase18")
REQUIREMENTS_COVERED = ["DATA-01", "DATA-02"]


@dataclass(frozen=True)
class Phase18DatasetConfig:
    source_dataset: Path = DEFAULT_SOURCE_DATASET
    source_split_dir: Path = DEFAULT_SOURCE_SPLIT_DIR
    output_dataset: Path = DEFAULT_OUTPUT_DATASET
    output_split_dir: Path = DEFAULT_OUTPUT_SPLIT_DIR
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR
    tokenized_dir: Path = DEFAULT_TOKENIZED_DIR
    seed: int = 42
    mode: str = "filter"


def _is_under(path: Path, root: Path) -> bool:
    candidate = path.expanduser().resolve(strict=False)
    root = root.expanduser().resolve(strict=False)
    return candidate == root or root in candidate.parents


def reject_unsafe_phase18_output_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    forbidden_roots = [
        FROZEN_V1_ROOT,
        PROJECT_ROOT / "data" / "v4" / "phase8",
        PROJECT_ROOT / "artifacts" / "v4" / "phase8",
        PROJECT_ROOT / "tsc_cycle",
    ]
    if candidate == PROJECT_ROOT.resolve(strict=False) or candidate == (PROJECT_ROOT / "data").resolve(strict=False) or candidate == (PROJECT_ROOT / "artifacts").resolve(strict=False):
        raise ValueError(f"Phase 18 output path is not allowed: {candidate}")
    if any(_is_under(candidate, root) for root in forbidden_roots):
        raise ValueError(f"Phase 18 output path is not allowed: {candidate}")
    return candidate


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    safe_path = reject_unsafe_phase18_output_path(path)
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    safe_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL row must be an object {path}:{line_no}")
            rows.append(payload)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    safe_path = reject_unsafe_phase18_output_path(path)
    safe_path.parent.mkdir(parents=True, exist_ok=True)
    with safe_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")


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


def _record_source_origin(record: dict[str, Any]) -> str:
    for container in (record, record.get("metadata") if isinstance(record.get("metadata"), dict) else {}, _record_input(record)):
        if isinstance(container, dict) and container.get("source_origin"):
            return str(container["source_origin"])
    return "unknown"


def _record_lineage(record: dict[str, Any]) -> str:
    for container in (record, _record_input(record), record.get("metadata") if isinstance(record.get("metadata"), dict) else {}):
        if not isinstance(container, dict):
            continue
        for key in ("lineage", "milestone", "version"):
            if container.get(key):
                return str(container[key])
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
            if container.get(key):
                return str(container[key])
    return "unknown"


def _record_reasoning(record: dict[str, Any]) -> str:
    value = _record_result(record).get("reasoning", "")
    return "" if value is None else str(value)


def _record_solution(record: dict[str, Any]) -> dict[str, int]:
    value = _record_result(record).get("solution", {})
    if not isinstance(value, dict):
        return {}
    return {str(key): int(val) for key, val in value.items()}


def _manifest_hash(record: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(record))


def _is_v1(record: dict[str, Any]) -> bool:
    lineage = _record_lineage(record).lower()
    sample_id = _record_sample_id(record)
    return "v1" in lineage or sample_id.startswith("v1-")


def _is_ood(record: dict[str, Any]) -> bool:
    return _record_source(record).lower() == "ood"


def _load_split_index(split_dir: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for split in ("train", "val", "ood_val"):
        path = split_dir / f"{split}.index.jsonl"
        if not path.exists():
            continue
        for row in _read_jsonl(path):
            sample_id = str(row.get("sample_id") or "")
            if sample_id:
                index[sample_id] = {**row, "split": split}
    return index


def _phase_rows_for_record(record: dict[str, Any], split_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    sample_id = _record_sample_id(record)
    input_obj = _record_input(record)
    solution = _record_solution(record)
    waits = input_obj.get("prediction", {}).get("phase_waits", [])
    if not isinstance(waits, list):
        raise ValueError("phase_waits is not a list")
    split_row = split_index.get(sample_id, {})
    rows: list[dict[str, Any]] = []
    for wait in waits:
        if not isinstance(wait, dict):
            raise ValueError("phase_waits entry is not an object")
        phase_id = str(wait["phase_id"])
        row = {
            "origin_artifact": "dataset:labeled_merged.jsonl",
            "sample_id": sample_id,
            "phase_id": phase_id,
            "pred_saturation": float(wait["pred_saturation"]),
            "min_green": int(wait["min_green"]),
            "max_green": int(wait["max_green"]),
            "final_green": int(solution[phase_id]),
            "split": str(split_row.get("split") or record.get("split") or record.get("split_hint") or "unknown"),
            "source": str(split_row.get("source") or _record_source(record)),
            "source_origin": str(split_row.get("source_origin") or _record_source_origin(record)),
        }
        row["saturation_band"] = classify_saturation_band(row["pred_saturation"])
        row["trivial_range"] = row["min_green"] == row["max_green"]
        row["violation_category"] = classify_violation(row)
        rows.append(row)
    return rows


def _index_row(record: dict[str, Any], split: str, raw_index: int, seed: int) -> dict[str, Any]:
    input_obj = _record_input(record)
    solution = _record_solution(record)
    prompt = build_user_prompt(input_obj)
    assistant = build_full_assistant(_record_reasoning(record), solution)
    return {
        "sample_id": _record_sample_id(record),
        "split": split,
        "lineage": _record_lineage(record),
        "source_origin": _record_source_origin(record),
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


def _split_rows(retained: list[tuple[int, dict[str, Any]]], split_index: dict[str, dict[str, Any]], seed: int) -> dict[str, list[dict[str, Any]]]:
    output = {"train": [], "val": [], "ood_val": []}
    for raw_index, record in retained:
        sample_id = _record_sample_id(record)
        split = str(split_index.get(sample_id, {}).get("split") or record.get("split") or record.get("split_hint") or "train")
        if split == "ood":
            split = "ood_val"
        if split not in output:
            split = "train"
        output[split].append(_index_row(record, split, raw_index, seed))
    for rows in output.values():
        rows.sort(key=lambda row: str(row["sample_id"]))
    return output


def _write_split_indexes(config: Phase18DatasetConfig, split_rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    split_ids = {name: [str(row["sample_id"]) for row in rows] for name, rows in split_rows.items()}
    for split, rows in split_rows.items():
        _write_jsonl(config.output_split_dir / f"{split}.index.jsonl", rows)
    manifest = {
        "ok": True,
        "seed": config.seed,
        "split_counts": {name: len(ids) for name, ids in split_ids.items()},
        "split_ids_sha256": {name: sha256_hex(canonical_json(ids)) for name, ids in split_ids.items()},
        "requirements_covered": ["DATA-02"],
        "paths": {
            "train_index": str(config.output_split_dir / "train.index.jsonl"),
            "val_index": str(config.output_split_dir / "val.index.jsonl"),
            "ood_val_index": str(config.output_split_dir / "ood_val.index.jsonl"),
        },
    }
    _write_json(config.output_split_dir / "manifest.json", manifest)
    return manifest


def _rejection_from_phase_row(row: dict[str, Any], reason: str) -> dict[str, Any]:
    fields = [
        "sample_id",
        "phase_id",
        "pred_saturation",
        "saturation_band",
        "min_green",
        "max_green",
        "final_green",
        "split",
        "source",
        "source_origin",
    ]
    return {"reason": reason, **{field: row.get(field) for field in fields}}


def build_calibrated_dataset(config: Phase18DatasetConfig) -> dict[str, Any]:
    if config.mode != "filter":
        raise ValueError(f"unsupported Phase 18 calibration mode: {config.mode}")
    for output_path in (config.output_dataset, config.output_split_dir / "manifest.json", config.artifacts_dir / "reconstruction_report.json"):
        reject_unsafe_phase18_output_path(output_path)

    source_rows = _read_jsonl(config.source_dataset)
    split_index = _load_split_index(config.source_split_dir)
    retained: list[tuple[int, dict[str, Any]]] = []
    retained_policy_rows: list[dict[str, Any]] = []
    source_policy_rows: list[dict[str, Any]] = []
    representative_rejections: list[dict[str, Any]] = []
    rejected_counts: Counter[str] = Counter()
    hard_constraint_pass_count = 0

    for raw_index, record in enumerate(source_rows):
        try:
            input_obj = _record_input(record)
            solution = _record_solution(record)
            lint = validate(input_obj, solution)
            phase_rows = _phase_rows_for_record(record, split_index)
        except (KeyError, TypeError, ValueError) as exc:
            rejected_counts["malformed_rejected_rows"] += 1
            representative_rejections.append({"sample_id": _record_sample_id(record), "reason": "malformed_row", "error": str(exc)})
            continue
        source_policy_rows.extend(phase_rows)
        if not lint.ok:
            rejected_counts["hard_constraint_rejected_rows"] += 1
            example = _rejection_from_phase_row(phase_rows[0], "hard_constraint_invalid") if phase_rows else {"sample_id": _record_sample_id(record), "reason": "hard_constraint_invalid"}
            example["violations"] = lint.violations
            representative_rejections.append(example)
            continue
        hard_constraint_pass_count += 1
        violating_rows = [row for row in phase_rows if row["violation_category"] == VIOLATION_UNSATURATED_MAX_GREEN]
        if violating_rows:
            rejected_counts["policy_rejected_rows"] += 1
            representative_rejections.append(_rejection_from_phase_row(violating_rows[0], "saturation_policy_violation"))
            continue
        retained.append((raw_index, record))
        retained_policy_rows.extend(phase_rows)

    retained_rows = [record for _raw_index, record in retained]
    _write_jsonl(config.output_dataset, retained_rows)
    split_rows = _split_rows(retained, split_index, config.seed)
    split_manifest = _write_split_indexes(config, split_rows)

    pre_audit = compute_saturation_audit(source_policy_rows, excluded_counts=dict(rejected_counts)) if source_policy_rows else {"ok": True, "total_rows": 0, "excluded_counts": dict(rejected_counts)}
    post_audit = compute_saturation_audit(retained_policy_rows, excluded_counts={}) if retained_policy_rows else {"ok": True, "total_rows": 0, "excluded_counts": {}}
    post_gate = evaluate_saturation_policy_gate(retained_policy_rows, thresholds=DEFAULT_THRESHOLDS, source_type="data")
    sample_hashes = sorted(_manifest_hash(row) for row in retained_rows)
    source_count = len(source_rows)
    retained_count = len(retained_rows)
    report = {
        "ok": post_gate.get("ok") is True,
        "next_phase_allowed": post_gate.get("ok") is True,
        "mode": config.mode,
        "requirements_covered": list(REQUIREMENTS_COVERED),
        "counts": {
            "source_rows": source_count,
            "retained_rows": retained_count,
            "rejected_rows": source_count - retained_count,
            "relabelled_rows": 0,
            "policy_rejected_rows": int(rejected_counts.get("policy_rejected_rows", 0)),
            "hard_constraint_rejected_rows": int(rejected_counts.get("hard_constraint_rejected_rows", 0)),
            "malformed_rejected_rows": int(rejected_counts.get("malformed_rejected_rows", 0)),
        },
        "policy": {
            "pre_audit": pre_audit,
            "post_audit": post_audit,
            "post_gate": post_gate,
        },
        "hard_constraints": {
            "source_pass_count": hard_constraint_pass_count,
            "source_pass_rate": hard_constraint_pass_count / source_count if source_count else 0.0,
            "retained_pass_count": retained_count,
            "retained_pass_rate": 1.0 if retained_count else 0.0,
        },
        "dataset_hashes": {
            "source_jsonl_sha256": _sha256_file(config.source_dataset) if config.source_dataset.exists() else "",
            "calibrated_jsonl_sha256": _sha256_file(config.output_dataset),
            "sample_hash_digest": sha256_hex(canonical_json(sample_hashes)),
            "sample_hashes": sample_hashes,
        },
        "splits": {
            "split_counts": split_manifest["split_counts"],
            "split_ids_sha256": split_manifest["split_ids_sha256"],
        },
        "representative_rejections": representative_rejections[:25],
        "paths": {
            "source_dataset": str(config.source_dataset),
            "source_split_dir": str(config.source_split_dir),
            "merged_jsonl": str(config.output_dataset),
            "split_manifest": str(config.output_split_dir / "manifest.json"),
            "tokenized_dir": str(config.tokenized_dir),
            "reconstruction_report": str(config.artifacts_dir / "reconstruction_report.json"),
        },
        "gates": {
            "post_policy_gate": {"ok": post_gate.get("ok") is True},
            "retained_hard_constraints": {"ok": retained_count == len(retained)},
        },
        "fatal_failures": list(post_gate.get("fatal_failures") or []),
        "warnings": [],
    }
    _write_json(config.artifacts_dir / "reconstruction_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild calibrated v4.2 Phase 18 dataset from v4 Phase 8 sources")
    parser.add_argument("--source-dataset", type=Path, default=DEFAULT_SOURCE_DATASET)
    parser.add_argument("--source-split-dir", type=Path, default=DEFAULT_SOURCE_SPLIT_DIR)
    parser.add_argument("--output-dataset", type=Path, default=DEFAULT_OUTPUT_DATASET)
    parser.add_argument("--output-split-dir", type=Path, default=DEFAULT_OUTPUT_SPLIT_DIR)
    parser.add_argument("--tokenized-dir", type=Path, default=DEFAULT_TOKENIZED_DIR)
    parser.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--mode", choices=["filter"], default="filter")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_calibrated_dataset(
        Phase18DatasetConfig(
            source_dataset=args.source_dataset,
            source_split_dir=args.source_split_dir,
            output_dataset=args.output_dataset,
            output_split_dir=args.output_split_dir,
            tokenized_dir=args.tokenized_dir,
            artifacts_dir=args.artifacts_dir,
            seed=args.seed,
            mode=args.mode,
        )
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    sys.exit(main())
