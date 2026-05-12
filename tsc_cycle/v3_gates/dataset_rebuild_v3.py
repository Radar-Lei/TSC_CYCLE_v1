from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tsc_cycle.hashing import canonical_json, sha256_hex
from tsc_cycle.prompt_builder import TAG_SOLUTION_CLOSE, build_full_assistant, build_user_prompt
from tsc_cycle.tokenizer_check import assert_no_native_think_in_ids, native_think_token_ids

DEFAULT_SEED = 42
DEFAULT_TRAIN_SIZE = 7601
DEFAULT_VAL_SIZE = 950
DEFAULT_OOD_VAL_SIZE = 950
DEFAULT_MAX_SEQ_LENGTH = 2048
REQUIREMENTS_SPLIT = ["DATA-01", "DATA-04"]
REQUIREMENTS_ALL = ["DATA-01", "DATA-02", "DATA-03", "DATA-04"]


@dataclass(frozen=True)
class DatasetRebuildConfig:
    merged_input: Path = Path("data/v3/phase2/labeled_merged.jsonl")
    split_dir: Path = Path("data/splits/v3")
    tokenized_dir: Path = Path("data/tokenized/v3")
    seed: int = DEFAULT_SEED
    max_seq_length: int = DEFAULT_MAX_SEQ_LENGTH
    model_name: str = "Qwen/Qwen3.5-9B"
    phase2_report: Path = Path("data/v3/phase2/merge_report.json")
    memory_budget: Path = Path("artifacts/v3/phase1/memory_budget.json")
    tokenizer_audit: Path = Path("artifacts/v3/phase1/tokenizer_audit.json")
    report_out: Path = Path("data/splits/v3/rebuild_report.json")
    expected_train: int = DEFAULT_TRAIN_SIZE
    expected_val: int = DEFAULT_VAL_SIZE
    expected_ood_val: int = DEFAULT_OOD_VAL_SIZE
    max_truncation_rate: float = 0.05

    @property
    def merged_jsonl(self) -> Path:
        return self.merged_input

    @property
    def splits_dir(self) -> Path:
        return self.split_dir


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"missing JSONL artifact: {path}"]
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"malformed JSONL {path}:{line_no}: {exc}")
            continue
        if not isinstance(row, dict):
            errors.append(f"JSONL row must be an object {path}:{line_no}")
            continue
        rows.append(row)
    return rows, errors


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")


def _add_gate(gates: dict[str, Any], fatal_failures: list[dict[str, str]], name: str, ok: bool, reason: str | None = None, data: dict[str, Any] | None = None) -> None:
    gates[name] = {"ok": bool(ok), "reason": reason, "data": data or {}}
    if not ok:
        fatal_failures.append({"gate": name, "reason": reason or "failed"})


def _record_input(record: dict[str, Any]) -> dict[str, Any]:
    candidate = record.get("input")
    return candidate if isinstance(candidate, dict) else record


def _record_result(record: dict[str, Any]) -> dict[str, Any]:
    result = record.get("result")
    return result if isinstance(result, dict) else record


def _record_sample_id(record: dict[str, Any]) -> str | None:
    for container in (record, _record_input(record)):
        value = container.get("sample_id") if isinstance(container, dict) else None
        if value is not None:
            return str(value)
    return None


def _record_lineage(record: dict[str, Any]) -> str:
    for container in (record, _record_input(record), record.get("metadata") if isinstance(record.get("metadata"), dict) else {}):
        if not isinstance(container, dict):
            continue
        for key in ("lineage", "milestone", "version"):
            value = container.get(key)
            if value:
                return str(value)
    sample_id = _record_sample_id(record) or ""
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
    return str(value) if value is not None else ""


def _record_solution(record: dict[str, Any]) -> dict[str, int]:
    result = _record_result(record)
    value = result.get("solution", {})
    if not isinstance(value, dict):
        return {}
    return {str(k): int(v) for k, v in value.items()}


def _has_explicit_source(record: dict[str, Any]) -> bool:
    for container in (record, _record_input(record)):
        if isinstance(container, dict) and container.get("source") is not None:
            return True
    return False


def _split_hint(record: dict[str, Any]) -> str:
    for container in (record, _record_input(record)):
        if isinstance(container, dict) and container.get("split_hint") is not None:
            return str(container["split_hint"])
    return "unknown"


def _is_v1(record: dict[str, Any]) -> bool:
    lineage = _record_lineage(record).lower()
    sample_id = _record_sample_id(record) or ""
    if "v1" in lineage or sample_id.startswith("v1-"):
        return True
    if "v3" in lineage or sample_id.startswith("v3-"):
        return False
    return not _has_explicit_source(record)


def _is_ood(record: dict[str, Any]) -> bool:
    return _split_hint(record).lower() == "ood" or _record_source(record).lower() == "ood"


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
        "record_hash": sha256_hex(canonical_json(record)),
        "input_hash": sha256_hex(canonical_json(input_obj)),
        "solution_hash": sha256_hex(canonical_json(solution)),
        "prompt_hash": sha256_hex(prompt),
        "assistant_hash": sha256_hex(assistant),
        "raw_index": raw_index,
        "seed": seed,
        "is_v1_ood": _is_v1(record) and _is_ood(record),
    }


def _artifact_hashes(paths: dict[str, Path]) -> dict[str, str]:
    return {name: _sha256_file(path) for name, path in paths.items() if path.exists()}


def _write_split_artifacts(config: DatasetRebuildConfig, split_rows: dict[str, list[tuple[int, dict[str, Any]]]], report: dict[str, Any]) -> None:
    paths: dict[str, Path] = {}
    for split_name, rows in split_rows.items():
        index_rows = [_index_row(row, split_name, raw_index, config.seed) for raw_index, row in rows]
        path = config.split_dir / f"{split_name}.index.jsonl"
        _write_jsonl(path, index_rows)
        paths[f"{split_name}_index"] = path

    alignment_path = config.split_dir / "v1_ood_alignment.json"
    _write_json(alignment_path, report["v1_ood_alignment"])
    paths["v1_ood_alignment"] = alignment_path

    manifest_path = config.split_dir / "manifest.json"
    manifest = {
        "ok": True,
        "seed": config.seed,
        "input_sha256": report["input_sha256"],
        "split_sizes": report["split_sizes"],
        "requirements_covered": REQUIREMENTS_SPLIT,
        "gates": report["gates"],
        "v1_ood_alignment": report["v1_ood_alignment"],
        "paths": {name: str(path) for name, path in paths.items()},
    }
    _write_json(manifest_path, manifest)
    paths["manifest"] = manifest_path
    manifest["artifact_hashes"] = _artifact_hashes(paths)
    _write_json(manifest_path, manifest)


def _coerce_config(value: DatasetRebuildConfig | list[dict[str, Any]]) -> tuple[DatasetRebuildConfig, list[dict[str, Any]], list[str]]:
    if isinstance(value, DatasetRebuildConfig):
        rows, errors = _read_jsonl(value.merged_input)
        return value, rows, errors
    return DatasetRebuildConfig(), value, []


def build_split_plan(config_or_rows: DatasetRebuildConfig | list[dict[str, Any]], *, seed: int | None = None) -> dict[str, Any]:
    config, rows, read_errors = _coerce_config(config_or_rows)
    seed = config.seed if seed is None else seed
    fatal_failures: list[dict[str, str]] = []
    gates: dict[str, Any] = {}

    for error in read_errors:
        fatal_failures.append({"gate": "jsonl_read", "reason": error})

    ids = [_record_sample_id(row) for row in rows]
    missing_ids = sum(1 for sample_id in ids if sample_id is None)
    duplicate_ids = sorted({sample_id for sample_id in ids if sample_id is not None and ids.count(sample_id) > 1})
    _add_gate(gates, fatal_failures, "sample_ids_present", missing_ids == 0, None if missing_ids == 0 else f"missing sample_id count={missing_ids}")
    _add_gate(gates, fatal_failures, "unique_sample_ids", not duplicate_ids, None if not duplicate_ids else f"duplicate sample_id count={len(duplicate_ids)}", {"duplicate_ids_sample": duplicate_ids[:10]})

    indexed_rows = [(idx, row) for idx, row in enumerate(rows)]
    v1_ood_rows = [(idx, row) for idx, row in indexed_rows if _is_v1(row) and _is_ood(row)]
    new_ood_rows = [(idx, row) for idx, row in indexed_rows if not _is_v1(row) and _is_ood(row)]
    _add_gate(gates, fatal_failures, "v1_ood_count", len(v1_ood_rows) == 300, None if len(v1_ood_rows) == 300 else f"v1 OOD count {len(v1_ood_rows)} != 300", {"v1_ood_count": len(v1_ood_rows)})
    _add_gate(gates, fatal_failures, "new_ood_pool", len(new_ood_rows) >= 650, None if len(new_ood_rows) >= 650 else f"new OOD count {len(new_ood_rows)} < 650", {"new_ood_count": len(new_ood_rows)})

    split_rows: dict[str, list[tuple[int, dict[str, Any]]]] = {"train": [], "val": [], "ood_val": []}
    split_ids: dict[str, list[str]] = {"train": [], "val": [], "ood_val": []}
    if not fatal_failures:
        rng = random.Random(seed)
        sorted_new_ood = sorted(new_ood_rows, key=lambda item: _record_sample_id(item[1]) or "")
        sampled_new_ood = rng.sample(sorted_new_ood, 650)
        ood_val_key = {idx for idx, _ in [*v1_ood_rows, *sampled_new_ood]}
        remaining = [(idx, row) for idx, row in indexed_rows if idx not in ood_val_key]
        sorted_remaining = sorted(remaining, key=lambda item: _record_sample_id(item[1]) or "")
        val_rows = rng.sample(sorted_remaining, config.expected_val)
        val_key = {idx for idx, _ in val_rows}
        train_rows = [(idx, row) for idx, row in sorted_remaining if idx not in val_key]
        split_rows = {
            "train": train_rows,
            "val": sorted(val_rows, key=lambda item: _record_sample_id(item[1]) or ""),
            "ood_val": sorted([*v1_ood_rows, *sampled_new_ood], key=lambda item: _record_sample_id(item[1]) or ""),
        }
        split_ids = {name: [_record_sample_id(row) or "" for _, row in rows_for_split] for name, rows_for_split in split_rows.items()}
        overlap_count = sum(len(set(split_ids[a]) & set(split_ids[b])) for a, b in (("train", "val"), ("train", "ood_val"), ("val", "ood_val")))
        split_sizes_ok = split_ids and len(split_ids["train"]) == config.expected_train and len(split_ids["val"]) == config.expected_val and len(split_ids["ood_val"]) == config.expected_ood_val
        _add_gate(gates, fatal_failures, "split_sizes", split_sizes_ok, None if split_sizes_ok else "split sizes do not match expected counts")
        _add_gate(gates, fatal_failures, "split_overlap", overlap_count == 0, None if overlap_count == 0 else f"split overlap count={overlap_count}")

    v1_ood_ids = sorted(_record_sample_id(row) or "" for _, row in split_rows.get("ood_val", []) if _is_v1(row) and _is_ood(row))
    new_ood_ids = sorted(_record_sample_id(row) or "" for _, row in split_rows.get("ood_val", []) if not _is_v1(row) and _is_ood(row))
    alignment = {
        "all_v1_ood_in_ood_val": len(v1_ood_ids) == 300,
        "v1_ood_count": len(v1_ood_ids),
        "new_ood_count": len(new_ood_ids),
        "expected_v1_ood_count": 300,
        "observed_v1_ood_count": len([1 for _, row in v1_ood_rows]),
        "missing_v1_ood_ids": [],
        "ood_val_v1_ood_count": len(v1_ood_ids),
        "v1_ood_sample_ids_sha256": sha256_hex(canonical_json(v1_ood_ids)),
    }

    ok = not fatal_failures
    input_sha = _sha256_file(config.merged_input) if isinstance(config_or_rows, DatasetRebuildConfig) and config.merged_input.exists() else ""
    report = {
        "ok": ok,
        "seed": seed,
        "input_sha256": input_sha,
        "split_sizes": {name: len(values) for name, values in split_ids.items()},
        "split_ids": split_ids,
        "split_counts": {name: len(values) for name, values in split_ids.items()},
        "v1_ood_alignment": alignment,
        "gates": gates,
        "fatal_failures": fatal_failures,
        "requirements_covered": REQUIREMENTS_SPLIT,
        "_split_rows": split_rows,
    }
    if ok and isinstance(config_or_rows, DatasetRebuildConfig):
        _write_split_artifacts(config, split_rows, report)
    return report


def tokenize_record(record: dict[str, Any], tokenizer: Any, *, max_seq_length: int, split: str = "train") -> dict[str, Any]:
    input_obj = _record_input(record)
    solution = _record_solution(record)
    prompt = build_user_prompt(input_obj)
    assistant = build_full_assistant(_record_reasoning(record), solution)
    full_text = prompt + assistant
    raw_ids = list(tokenizer(full_text, add_special_tokens=False)["input_ids"])
    try:
        assert_no_native_think_in_ids(raw_ids, native_think_token_ids(tokenizer))
    except AssertionError:
        return {"ok": False, "error": "native_think_token_leak", "sample_id": _record_sample_id(record), "split": split}

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
        "solution_close_present": TAG_SOLUTION_CLOSE in assistant,
    }


def write_arrow_split(path: Path, rows_tok: list[dict[str, Any]]) -> None:
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


def _load_tokenizer(model_name: str) -> Any:
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model_name)


def _validate_phase1_max_seq(config: DatasetRebuildConfig) -> tuple[bool, dict[str, Any]]:
    if not config.memory_budget.exists():
        return True, {"path": str(config.memory_budget), "checked": False}
    payload = _read_json(config.memory_budget)
    selected = payload.get("selected_max_seq")
    return selected == config.max_seq_length, {"path": str(config.memory_budget), "selected_max_seq": selected, "expected": config.max_seq_length}


def build_phase3_dataset(config: DatasetRebuildConfig, *, tokenizer: Any | None = None, write_tokenized: bool = True) -> dict[str, Any]:
    split_report = build_split_plan(config)
    if not split_report["ok"]:
        return split_report

    tokenizer = tokenizer if tokenizer is not None else _load_tokenizer(config.model_name)
    gates = dict(split_report["gates"])
    fatal_failures: list[dict[str, str]] = []
    max_seq_ok, max_seq_data = _validate_phase1_max_seq(config)
    _add_gate(gates, fatal_failures, "max_seq_length", max_seq_ok, None if max_seq_ok else "Phase 1 selected_max_seq does not match Phase 3 max_seq_length", max_seq_data)

    tokenized_by_split: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "ood_val": []}
    token_failures: list[dict[str, Any]] = []
    raw_lengths: list[int] = []
    truncated_ids: list[str] = []
    for split_name, rows in split_report["_split_rows"].items():
        for _, record in rows:
            row_tok = tokenize_record(record, tokenizer=tokenizer, max_seq_length=config.max_seq_length, split=split_name)
            if not row_tok["ok"]:
                token_failures.append(row_tok)
                continue
            raw_lengths.append(int(row_tok["raw_length"]))
            if row_tok["truncated"]:
                truncated_ids.append(str(row_tok["sample_id"]))
            tokenized_by_split[split_name].append(row_tok)

    over_length_count = len(truncated_ids)
    total = sum(len(rows) for rows in tokenized_by_split.values()) + len(token_failures)
    over_length_rate = over_length_count / total if total else 0.0
    _add_gate(gates, fatal_failures, "native_think_leak", not token_failures, None if not token_failures else f"tokenization failures count={len(token_failures)}", {"failures_sample": token_failures[:10]})
    _add_gate(gates, fatal_failures, "truncation_rate", over_length_rate <= config.max_truncation_rate, None if over_length_rate <= config.max_truncation_rate else f"truncation rate {over_length_rate:.6f} > {config.max_truncation_rate}", {"over_length_count": over_length_count, "total": total})

    report = {
        **{k: v for k, v in split_report.items() if k != "_split_rows"},
        "ok": not fatal_failures,
        "requirements_covered": REQUIREMENTS_ALL,
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
            "rate": over_length_rate,
            "truncated_sample_ids_sample": truncated_ids[:25],
            "max_raw_length": max(raw_lengths) if raw_lengths else 0,
        },
    }
    if report["ok"] and write_tokenized:
        for split_name, rows_tok in tokenized_by_split.items():
            write_arrow_split(config.tokenized_dir / f"{split_name}.arrow", rows_tok)
    return report


def _artifact_manifest(config: DatasetRebuildConfig, report: dict[str, Any]) -> dict[str, Any]:
    paths = {
        "train_index": config.split_dir / "train.index.jsonl",
        "val_index": config.split_dir / "val.index.jsonl",
        "ood_val_index": config.split_dir / "ood_val.index.jsonl",
        "v1_ood_alignment": config.split_dir / "v1_ood_alignment.json",
        "rebuild_report": config.report_out,
        "train_arrow": config.tokenized_dir / "train.arrow",
        "val_arrow": config.tokenized_dir / "val.arrow",
        "ood_val_arrow": config.tokenized_dir / "ood_val.arrow",
    }
    return {"paths": {name: str(path) for name, path in paths.items()}, "sha256": _artifact_hashes(paths), "ok": report.get("ok") is True}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild v3 Phase 3 splits and Qwen3.5 tokenized Arrow artifacts")
    parser.add_argument("--merged-jsonl", "--merged-input", dest="merged_input", default="data/v3/phase2/labeled_merged.jsonl")
    parser.add_argument("--phase2-report", default="data/v3/phase2/merge_report.json")
    parser.add_argument("--memory-budget", default="artifacts/v3/phase1/memory_budget.json")
    parser.add_argument("--tokenizer-audit", default="artifacts/v3/phase1/tokenizer_audit.json")
    parser.add_argument("--splits-dir", "--split-dir", dest="split_dir", default="data/splits/v3")
    parser.add_argument("--tokenized-dir", default="data/tokenized/v3")
    parser.add_argument("--report-out", default="data/splits/v3/rebuild_report.json")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--expected-train", type=int, default=DEFAULT_TRAIN_SIZE)
    parser.add_argument("--expected-val", type=int, default=DEFAULT_VAL_SIZE)
    parser.add_argument("--expected-ood-val", type=int, default=DEFAULT_OOD_VAL_SIZE)
    parser.add_argument("--max-seq-length", type=int, default=DEFAULT_MAX_SEQ_LENGTH)
    parser.add_argument("--max-truncation-rate", type=float, default=0.05)
    parser.add_argument("--model-name", default="Qwen/Qwen3.5-9B")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = DatasetRebuildConfig(
        merged_input=Path(args.merged_input),
        split_dir=Path(args.split_dir),
        tokenized_dir=Path(args.tokenized_dir),
        seed=args.seed,
        max_seq_length=args.max_seq_length,
        model_name=args.model_name,
        phase2_report=Path(args.phase2_report),
        memory_budget=Path(args.memory_budget),
        tokenizer_audit=Path(args.tokenizer_audit),
        report_out=Path(args.report_out),
        expected_train=args.expected_train,
        expected_val=args.expected_val,
        expected_ood_val=args.expected_ood_val,
        max_truncation_rate=args.max_truncation_rate,
    )
    phase2_report = _read_json(config.phase2_report)
    if config.phase2_report.exists() and (phase2_report.get("ok") is not True or int(phase2_report.get("merged_valid", 0)) != 9501):
        report = {"ok": False, "fatal_failures": [{"gate": "phase2_report", "reason": "Phase 2 report must have ok=true and merged_valid=9501"}], "requirements_covered": REQUIREMENTS_ALL}
    else:
        report = build_phase3_dataset(config, write_tokenized=not args.dry_run)
    report["artifact_manifest"] = _artifact_manifest(config, report)
    if report.get("ok") is True:
        manifest_path = config.split_dir / "manifest.json"
        if manifest_path.exists():
            manifest = _read_json(manifest_path)
            manifest["requirements_covered"] = REQUIREMENTS_ALL
            manifest["tokenized_outputs"] = report.get("tokenized_paths", {})
            manifest["artifact_hashes"] = report["artifact_manifest"]["sha256"]
            _write_json(manifest_path, manifest)
    _write_json(config.report_out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
