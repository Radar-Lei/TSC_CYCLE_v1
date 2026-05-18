from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tsc_cycle.hashing import canonical_json, sha256_hex
from tsc_cycle.prompt_builder import build_full_assistant, build_user_prompt
from tsc_cycle.tokenizer_check import assert_no_native_think_in_ids, native_think_token_ids

MODEL_NAME = "Qwen/Qwen3-4B-Thinking-2507"
RUN_ROOT_PREFIX = "v4.2-4B-"
DEFAULT_CALIBRATED_JSONL = Path("data/v4_2/phase18/labeled_calibrated.jsonl")
DEFAULT_SPLIT_DIR = Path("data/v4_2/phase18/splits")
DEFAULT_TOKENIZED_DIR = Path("data/v4_2/phase18/tokenized")
DEFAULT_PHASE18_REPORT = Path("artifacts/v4_2/phase18/reconstruction_report.json")
DEFAULT_ARTIFACTS_DIR = Path("artifacts/v4_2/phase19")
REQUIREMENTS_COVERED = ["TRAIN-01"]


@dataclass(frozen=True)
class Phase19TrainingConfig:
    calibrated_jsonl: Path = DEFAULT_CALIBRATED_JSONL
    split_dir: Path = DEFAULT_SPLIT_DIR
    tokenized_dir: Path = DEFAULT_TOKENIZED_DIR
    phase18_report: Path = DEFAULT_PHASE18_REPORT
    artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR
    max_seq_length: int = 2048
    model_name: str = MODEL_NAME


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


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


def _record_reasoning(record: dict[str, Any]) -> str:
    value = _record_result(record).get("reasoning", "")
    return "" if value is None else str(value)


def _record_solution(record: dict[str, Any]) -> dict[str, int]:
    value = _record_result(record).get("solution", {})
    if not isinstance(value, dict):
        return {}
    return {str(key): int(val) for key, val in value.items()}


def _load_phase18_split_indexes(split_dir: Path) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "ood_val": []}
    for split in output:
        path = split_dir / f"{split}.index.jsonl"
        if not path.exists():
            raise FileNotFoundError(path)
        output[split] = _read_jsonl(path)
    return output


def _phase18_counts(report: dict[str, Any], split_manifest: dict[str, Any]) -> dict[str, int]:
    counts = report.get("splits", {}).get("split_counts") if isinstance(report.get("splits"), dict) else None
    if not isinstance(counts, dict):
        counts = split_manifest.get("split_counts") if isinstance(split_manifest.get("split_counts"), dict) else {}
    return {str(key): int(value) for key, value in counts.items() if key in {"train", "val", "ood_val"}}


def validate_phase18_handoff(config: Phase19TrainingConfig) -> tuple[bool, dict[str, Any], list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    report = _read_json(config.phase18_report)
    split_manifest = _read_json(config.split_dir / "manifest.json")
    if report.get("ok") is not True or report.get("next_phase_allowed") is not True:
        failures.append({"gate": "phase18_handoff", "reason": "Phase 18 reconstruction report is not green"})
    covered = set(report.get("requirements_covered", []))
    if not {"DATA-01", "DATA-02"} <= covered:
        failures.append({"gate": "phase18_requirements", "reason": "Phase 18 report lacks DATA-01/DATA-02 coverage"})
    actual_hash = _sha256_file(config.calibrated_jsonl) if config.calibrated_jsonl.exists() else ""
    expected_hash = str(report.get("dataset_hashes", {}).get("calibrated_jsonl_sha256", "")) if isinstance(report.get("dataset_hashes"), dict) else ""
    if expected_hash and actual_hash != expected_hash:
        failures.append({"gate": "calibrated_jsonl_sha256", "reason": "calibrated JSONL hash does not match Phase 18 report"})
    try:
        split_indexes = _load_phase18_split_indexes(config.split_dir)
    except FileNotFoundError as exc:
        failures.append({"gate": "split_indexes", "reason": f"missing split index: {exc}"})
        split_indexes = {"train": [], "val": [], "ood_val": []}
    expected_counts = _phase18_counts(report, split_manifest)
    actual_counts = {split: len(rows) for split, rows in split_indexes.items()}
    if expected_counts and actual_counts != expected_counts:
        failures.append({"gate": "split_counts", "reason": f"split counts differ: expected {expected_counts}, actual {actual_counts}"})
    data = {
        "report": report,
        "split_manifest": split_manifest,
        "split_indexes": split_indexes,
        "actual_hash": actual_hash,
        "expected_hash": expected_hash,
        "expected_counts": expected_counts,
        "actual_counts": actual_counts,
    }
    return not failures, data, failures


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
    assistant_ids = raw_ids[len(prompt_ids) :]
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


def tokenize_phase18_handoff(config: Phase19TrainingConfig | None = None, *, tokenizer: Any | None = None, write_tokenized: bool = True) -> dict[str, Any]:
    config = config or Phase19TrainingConfig()
    fatal_failures: list[dict[str, str]] = []
    gates: dict[str, Any] = {}
    handoff_ok, handoff, handoff_failures = validate_phase18_handoff(config)
    fatal_failures.extend(handoff_failures)
    gates["phase18_handoff"] = {"ok": handoff_ok, "reason": None if handoff_ok else "Phase 18 handoff validation failed"}

    if tokenizer is None:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(config.model_name)
    native_ids = set(native_think_token_ids(tokenizer))
    gates["native_think_token_ids"] = {"ok": bool(native_ids), "data": {"native_think_token_ids": sorted(native_ids)}}
    if not native_ids:
        fatal_failures.append({"gate": "native_think_token_ids", "reason": "native think IDs must be derivable from tokenizer"})

    rows = _read_jsonl(config.calibrated_jsonl) if config.calibrated_jsonl.exists() else []
    rows_by_id = {_record_sample_id(row): row for row in rows}
    tokenized_by_split: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "ood_val": []}
    token_failures: list[dict[str, Any]] = []
    raw_lengths: list[int] = []
    truncated_ids: list[str] = []
    for split, index_rows in handoff["split_indexes"].items():
        for index_row in index_rows:
            sample_id = str(index_row.get("sample_id") or "")
            record = rows_by_id.get(sample_id)
            if record is None:
                fatal_failures.append({"gate": "split_membership", "reason": f"sample_id missing from calibrated JSONL: {sample_id}"})
                continue
            row_tok = _tokenize_record(record, tokenizer, native_ids=native_ids, max_seq_length=config.max_seq_length, split=split)
            if not row_tok["ok"]:
                token_failures.append(row_tok)
                continue
            raw_lengths.append(int(row_tok["raw_length"]))
            if row_tok["truncated"]:
                truncated_ids.append(str(row_tok["sample_id"]))
            tokenized_by_split[split].append(row_tok)
    if token_failures:
        fatal_failures.append({"gate": "native_think_token_leak", "reason": f"native think token leak count={len(token_failures)}"})
    gates["native_think_token_leak"] = {"ok": not token_failures, "data": {"failures_sample": token_failures[:10]}}

    split_counts = {split: len(items) for split, items in tokenized_by_split.items()}
    expected_counts = handoff["expected_counts"]
    split_ok = not expected_counts or split_counts == expected_counts
    gates["split_counts"] = {"ok": split_ok, "data": {"expected": expected_counts, "actual": split_counts}}
    if not split_ok:
        fatal_failures.append({"gate": "split_counts", "reason": f"tokenized counts differ: expected {expected_counts}, actual {split_counts}"})

    ok = not fatal_failures
    tokenized_sha256: dict[str, str] = {}
    if ok and write_tokenized:
        for split, rows_tok in tokenized_by_split.items():
            path = config.tokenized_dir / f"{split}.arrow"
            _write_arrow_split(path, rows_tok)
            tokenized_sha256[split] = _sha256_file(path)
        manifest = {
            "ok": True,
            "requirements_covered": list(REQUIREMENTS_COVERED),
            "model_name": config.model_name,
            "max_seq_length": config.max_seq_length,
            "split_counts": split_counts,
            "tokenized_paths": {split: str(config.tokenized_dir / f"{split}.arrow") for split in tokenized_by_split},
            "tokenized_sha256": tokenized_sha256,
            "phase18": {
                "calibrated_jsonl": str(config.calibrated_jsonl),
                "calibrated_jsonl_sha256": handoff["actual_hash"],
                "phase18_report": str(config.phase18_report),
                "phase18_report_sha256": _sha256_file(config.phase18_report),
                "split_manifest": str(config.split_dir / "manifest.json"),
                "split_manifest_sha256": _sha256_file(config.split_dir / "manifest.json") if (config.split_dir / "manifest.json").exists() else "",
            },
        }
        _write_json(config.tokenized_dir / "manifest.json", manifest)
    report = {
        "ok": ok,
        "requirements_covered": list(REQUIREMENTS_COVERED) if ok else [],
        "model_name": config.model_name,
        "split_counts": split_counts,
        "tokenized_dir": str(config.tokenized_dir),
        "tokenized_sha256": tokenized_sha256,
        "phase18": {
            "calibrated_jsonl": str(config.calibrated_jsonl),
            "calibrated_jsonl_sha256": handoff["actual_hash"],
            "phase18_report": str(config.phase18_report),
            "phase18_report_sha256": _sha256_file(config.phase18_report) if config.phase18_report.exists() else "",
            "split_manifest": str(config.split_dir / "manifest.json"),
        },
        "truncation": {"max_seq_length": config.max_seq_length, "over_length_count": len(truncated_ids), "truncated_sample_ids_sample": truncated_ids[:25], "max_raw_length": max(raw_lengths) if raw_lengths else 0},
        "gates": gates,
        "fatal_failures": fatal_failures,
    }
    config.artifacts_dir.mkdir(parents=True, exist_ok=True)
    _write_json(config.artifacts_dir / "tokenization_report.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 19 v4.2 training handoff and report gates")
    sub = parser.add_subparsers(dest="command")
    tok = sub.add_parser("tokenize", help="Tokenize Phase 18 calibrated splits for v4.2 QLoRA training")
    tok.add_argument("--calibrated-jsonl", type=Path, default=DEFAULT_CALIBRATED_JSONL)
    tok.add_argument("--split-dir", type=Path, default=DEFAULT_SPLIT_DIR)
    tok.add_argument("--tokenized-dir", type=Path, default=DEFAULT_TOKENIZED_DIR)
    tok.add_argument("--phase18-report", type=Path, default=DEFAULT_PHASE18_REPORT)
    tok.add_argument("--artifacts-dir", type=Path, default=DEFAULT_ARTIFACTS_DIR)
    tok.add_argument("--max-seq-length", type=int, default=2048)
    tok.add_argument("--model-name", default=MODEL_NAME)
    tok.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in {None, "tokenize"}:
        config = Phase19TrainingConfig(
            calibrated_jsonl=args.calibrated_jsonl,
            split_dir=args.split_dir,
            tokenized_dir=args.tokenized_dir,
            phase18_report=args.phase18_report,
            artifacts_dir=args.artifacts_dir,
            max_seq_length=args.max_seq_length,
            model_name=args.model_name,
        )
        report = tokenize_phase18_handoff(config, write_tokenized=not args.dry_run)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
        return 0 if report.get("ok") is True else 1
    raise SystemExit(f"unknown command: {args.command}")


# Task 3 adds training report validation/writing.
def write_phase19_training_reports(*args: Any, **kwargs: Any) -> Path:
    raise NotImplementedError("Task 3 implements Phase 19 training reports")


if __name__ == "__main__":
    raise SystemExit(main())
