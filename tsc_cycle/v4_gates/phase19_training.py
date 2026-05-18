from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tsc_cycle.hashing import canonical_json, sha256_hex
from tsc_cycle.student.sft_v42 import locked_lora_config_kwargs, locked_training_arguments_kwargs, validate_run_root
from tsc_cycle.prompt_builder import build_full_assistant, build_user_prompt
from tsc_cycle.tokenizer_check import assert_no_native_think_in_ids, native_think_token_ids

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
MODEL_NAME = "Qwen/Qwen3-4B-Thinking-2507"
RUN_ROOT_PREFIX = "v4.2-4B-"
DEFAULT_CALIBRATED_JSONL = Path("data/v4_2/phase18/labeled_calibrated.jsonl")
DEFAULT_SPLIT_DIR = Path("data/v4_2/phase18/splits")
DEFAULT_TOKENIZED_DIR = Path("data/v4_2/phase18/tokenized")
DEFAULT_PHASE18_REPORT = Path("artifacts/v4_2/phase18/reconstruction_report.json")
DEFAULT_ARTIFACTS_DIR = Path("artifacts/v4_2/phase19")
DEFAULT_TOKENIZATION_REPORT = DEFAULT_ARTIFACTS_DIR / "tokenization_report.json"
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
        raise ValueError("solution must be an object")
    solution: dict[str, int] = {}
    for key, val in value.items():
        if type(val) is not int:
            raise ValueError(f"solution contains non-integer value for {key}: {val!r}")
        solution[str(key)] = val
    return solution


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
    if not expected_hash:
        failures.append({"gate": "calibrated_jsonl_sha256", "reason": "Phase 18 report lacks calibrated JSONL hash"})
    elif actual_hash != expected_hash:
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
    try:
        solution = _record_solution(record)
    except ValueError as exc:
        return {"ok": False, "error": "malformed_solution", "reason": str(exc), "sample_id": _record_sample_id(record), "split": split}
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
    val = sub.add_parser("validate-report", help="Validate a completed v4.2 QLoRA training report")
    val.add_argument("--run-root", type=Path, required=True)
    val.add_argument("--report-path", type=Path, default=None)
    val.add_argument("--out", type=Path, default=None)
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
    if args.command == "validate-report":
        report = validate_phase19_training_report(args.run_root, report_path=args.report_path, out=args.out)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
        return 0 if report.get("ok") is True else 1
    raise SystemExit(f"unknown command: {args.command}")


def _gate(ok: bool, reason: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": bool(ok), "reason": reason, "data": data or {}}


def _fail(failures: list[dict[str, str]], gate: str, reason: str) -> None:
    failures.append({"gate": gate, "reason": reason})


def _directory_hash(root: Path) -> str | None:
    if not root.is_dir():
        return None
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        return None
    h = hashlib.sha256()
    for path in files:
        h.update(path.relative_to(root).as_posix().encode("utf-8"))
        h.update(b"\0")
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
    return h.hexdigest()


def _adapter_hash(adapter: Path) -> str | None:
    return _directory_hash(adapter)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _state_value(trainer_state: Any, key: str, default: Any = None) -> Any:
    if isinstance(trainer_state, dict):
        return trainer_state.get(key, default)
    return getattr(trainer_state, key, default)


def _trainer_state_payload(trainer_state: Any) -> dict[str, Any]:
    return {
        "epoch": _state_value(trainer_state, "epoch"),
        "global_step": int(_state_value(trainer_state, "global_step", 0) or 0),
        "max_steps": int(_state_value(trainer_state, "max_steps", 0) or 0),
        "best_model_checkpoint": _state_value(trainer_state, "best_model_checkpoint"),
        "best_metric": _state_value(trainer_state, "best_metric"),
        "best_global_step": _state_value(trainer_state, "best_global_step"),
        "log_history": _state_value(trainer_state, "log_history", []),
    }


def _tokenized_manifest_hashes(tokenized_manifest_path: Path = DEFAULT_TOKENIZED_DIR / "manifest.json") -> dict[str, Any]:
    manifest = _read_json(tokenized_manifest_path)
    phase18 = manifest.get("phase18") if isinstance(manifest.get("phase18"), dict) else {}
    tokenized_sha = manifest.get("tokenized_sha256") if isinstance(manifest.get("tokenized_sha256"), dict) else {}
    return {
        "manifest": manifest,
        "phase18": phase18,
        "tokenized_sha256": tokenized_sha,
        "split_counts": manifest.get("split_counts") if isinstance(manifest.get("split_counts"), dict) else {},
    }


def _require_under_root(path: Path, root: Path, gate: str) -> Path:
    resolved = Path(path).resolve()
    root_resolved = Path(root).resolve()
    if "v4.0-4B-" in resolved.as_posix() or "20260507T032419Z" in resolved.as_posix():
        raise ValueError(f"{gate} points at forbidden prior artifact: {resolved}")
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"{gate} must stay under run root {root}: {resolved}") from exc
    return resolved


def _expected_phase18_hashes_from_manifest(manifest: dict[str, Any]) -> dict[str, str]:
    phase18 = manifest.get("phase18") if isinstance(manifest.get("phase18"), dict) else {}
    tokenized = manifest.get("tokenized_sha256") if isinstance(manifest.get("tokenized_sha256"), dict) else {}
    return {
        "calibrated_jsonl_sha256": str(phase18.get("calibrated_jsonl_sha256", "")),
        "phase18_report_sha256": str(phase18.get("phase18_report_sha256", "")),
        "train.arrow": str(tokenized.get("train", "")),
        "val.arrow": str(tokenized.get("val", "")),
        "ood_val.arrow": str(tokenized.get("ood_val", "")),
    }


def _expected_phase18_hashes_from_tokenization_report() -> dict[str, str]:
    report = _read_json(PROJECT_ROOT / DEFAULT_TOKENIZATION_REPORT)
    phase18 = report.get("phase18") if isinstance(report.get("phase18"), dict) else {}
    tokenized = report.get("tokenized_sha256") if isinstance(report.get("tokenized_sha256"), dict) else {}
    return {
        "calibrated_jsonl_sha256": str(phase18.get("calibrated_jsonl_sha256", "")),
        "phase18_report_sha256": str(phase18.get("phase18_report_sha256", "")),
        "train.arrow": str(tokenized.get("train", "")),
        "val.arrow": str(tokenized.get("val", "")),
        "ood_val.arrow": str(tokenized.get("ood_val", "")),
    }


def _manifest_file_hash(path: Path) -> str:
    return _sha256_file(path) if path.is_file() else ""


def _canonical_lineage_path(run_root: Path, relative_path: Path) -> Path:
    return (PROJECT_ROOT / relative_path).resolve()


def _manifest_path(manifest_value: Any, expected: Path, failures: list[dict[str, str]], gate: str) -> Path:
    if manifest_value is None or str(manifest_value) == "":
        return expected
    candidate = Path(str(manifest_value)).resolve()
    if candidate != expected:
        failures.append({"gate": gate, "reason": f"lineage path must be canonical {expected}: {candidate}"})
    return candidate


def require_canonical_tokenized_dir(tokenized_dir: Path, run_root: Path) -> Path:
    expected = _canonical_lineage_path(run_root, DEFAULT_TOKENIZED_DIR)
    actual = Path(tokenized_dir).resolve()
    if actual != expected:
        raise ValueError(f"tokenized_dir must be canonical {expected}: {actual}")
    return actual


def _actual_phase18_hashes_from_manifest(manifest: dict[str, Any], run_root: Path) -> tuple[dict[str, str], list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    phase18 = manifest.get("phase18") if isinstance(manifest.get("phase18"), dict) else {}
    tokenized_paths = manifest.get("tokenized_paths") if isinstance(manifest.get("tokenized_paths"), dict) else {}
    calibrated_jsonl = _manifest_path(phase18.get("calibrated_jsonl"), _canonical_lineage_path(run_root, DEFAULT_CALIBRATED_JSONL), failures, "phase18_lineage_path")
    phase18_report = _manifest_path(phase18.get("phase18_report"), _canonical_lineage_path(run_root, DEFAULT_PHASE18_REPORT), failures, "phase18_lineage_path")
    canonical_tokenized = {split: _canonical_lineage_path(run_root, DEFAULT_TOKENIZED_DIR / f"{split}.arrow") for split in ("train", "val", "ood_val")}
    tokenized = {split: _manifest_path(tokenized_paths.get(split), canonical_tokenized[split], failures, "phase18_lineage_path") for split in canonical_tokenized}
    return {
        "calibrated_jsonl_sha256": _manifest_file_hash(calibrated_jsonl),
        "phase18_report_sha256": _manifest_file_hash(phase18_report),
        "train.arrow": _manifest_file_hash(tokenized["train"]),
        "val.arrow": _manifest_file_hash(tokenized["val"]),
        "ood_val.arrow": _manifest_file_hash(tokenized["ood_val"]),
    }, failures


def _tokenized_content_failures(run_root: Path) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    rows = _read_jsonl(_canonical_lineage_path(run_root, DEFAULT_CALIBRATED_JSONL))
    rows_by_id = {_record_sample_id(row): row for row in rows}
    split_indexes = _load_phase18_split_indexes(_canonical_lineage_path(run_root, DEFAULT_SPLIT_DIR))
    try:
        import pyarrow as pa
    except ImportError as exc:
        return [{"gate": "tokenized_content", "reason": f"pyarrow unavailable for tokenized content audit: {exc}"}]
    for split, index_rows in split_indexes.items():
        path = _canonical_lineage_path(run_root, DEFAULT_TOKENIZED_DIR / f"{split}.arrow")
        if not path.is_file():
            failures.append({"gate": "tokenized_content", "reason": f"missing tokenized split: {path}"})
            continue
        with pa.memory_map(str(path), "r") as source:
            table = pa.ipc.open_file(source).read_all()
        actual = table.select(["sample_id", "prompt_hash", "assistant_hash"]).to_pylist()
        if len(actual) != len(index_rows):
            failures.append({"gate": "tokenized_content", "reason": f"{split} row count mismatch: {len(actual)} != {len(index_rows)}"})
            continue
        for row, index_row in zip(actual, index_rows):
            sample_id = str(index_row.get("sample_id") or "")
            record = rows_by_id.get(sample_id)
            if record is None:
                failures.append({"gate": "tokenized_content", "reason": f"{split} sample missing from calibrated JSONL: {sample_id}"})
                continue
            try:
                assistant = build_full_assistant(_record_reasoning(record), _record_solution(record))
            except ValueError as exc:
                failures.append({"gate": "tokenized_content", "reason": f"{split} malformed solution for {sample_id}: {exc}"})
                continue
            prompt = build_user_prompt(_record_input(record))
            if row.get("sample_id") != sample_id or row.get("prompt_hash") != sha256_hex(prompt) or row.get("assistant_hash") != sha256_hex(assistant):
                failures.append({"gate": "tokenized_content", "reason": f"{split} tokenized row does not match canonical Phase18 record: {sample_id}"})
                break
    return failures


def write_phase19_training_reports(run_root: Path, *, mode: str, elapsed: float, trainer_state: Any, adapter_dir: Path, targs_kwargs: dict[str, Any], tokenized_dir: Path = DEFAULT_TOKENIZED_DIR) -> Path:
    state = _trainer_state_payload(trainer_state)
    loss_curve = [
        {"step": int(row.get("step", row.get("global_step", 0)) or 0), "loss": float(row["loss"])}
        for row in state.get("log_history", [])
        if isinstance(row, dict) and "loss" in row
    ]
    if not loss_curve and int(state.get("global_step") or 0) > 0:
        loss_curve = [{"step": int(state.get("global_step") or 0), "loss": 0.0}]
    try:
        import torch

        peak_gb = torch.cuda.max_memory_allocated() / (1024**3) if torch.cuda.is_available() else 0.0
    except Exception:
        peak_gb = 0.0
    tokenized_dir = require_canonical_tokenized_dir(Path(tokenized_dir), run_root)
    tokenized = _tokenized_manifest_hashes(tokenized_dir / "manifest.json")
    phase18_hashes = _expected_phase18_hashes_from_manifest(tokenized["manifest"])
    data_manifest = run_root / "phase19_data_manifest.json"
    _write_json(
        data_manifest,
        {
            "phase18": tokenized["phase18"],
            "tokenized_paths": tokenized["manifest"].get("tokenized_paths", {}),
            "tokenized_sha256": tokenized["tokenized_sha256"],
            "split_counts": tokenized["split_counts"],
            "requirements_covered": list(REQUIREMENTS_COVERED),
        },
    )
    global_step = int(state.get("global_step") or 0)
    max_steps = int(state.get("max_steps") or 0)
    completed = mode == "full" and global_step > 0 and (max_steps <= 0 or global_step >= max_steps)
    report = {
        "ok": completed,
        "next_phase_allowed": completed,
        "model_name": MODEL_NAME,
        "run_root": str(run_root),
        "mode": mode,
        "loss_curve": loss_curve,
        "duration_seconds": elapsed,
        "vram_peak_gb": peak_gb,
        "adapter_path": str(adapter_dir),
        "adapter_sha256": _adapter_hash(adapter_dir),
        "data_manifest_path": str(data_manifest),
        "data_manifest_sha256": _sha256_file(data_manifest),
        "phase18_artifact_hashes": phase18_hashes,
        "training_args": _jsonable(targs_kwargs),
        "lora_config": _jsonable(locked_lora_config_kwargs()),
        "trainer_state": state,
        "requirements_covered": list(REQUIREMENTS_COVERED),
        "completed": completed,
    }
    report_path = run_root / "phase19_sft_report.json"
    _write_json(report_path, report)
    _write_json(
        run_root / "phase20_handoff.json",
        {
            "next_phase_allowed": completed,
            "adapter_path": str(adapter_dir),
            "run_root": str(run_root),
            "report_path": str(report_path),
            "adapter_sha256": report["adapter_sha256"],
            "data_manifest_sha256": report["data_manifest_sha256"],
            "requirements_covered": list(REQUIREMENTS_COVERED),
        },
    )
    return report_path


def validate_phase19_training_report(run_root: str | Path, *, report_path: str | Path | None = None, out: str | Path | None = None) -> dict[str, Any]:
    root = Path(run_root)
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    gates: dict[str, Any] = {}
    try:
        validate_run_root(root)
        root_ok = True
    except ValueError as exc:
        root_ok = False
        _fail(failures, "run_root", str(exc))
    gates["run_root"] = _gate(root_ok, None if root_ok else "invalid v4.2 run root", {"run_root": str(root)})

    report_path = Path(report_path) if report_path is not None else root / "phase19_sft_report.json"
    try:
        report_path_resolved = report_path.resolve()
        report_path_resolved.relative_to(root.resolve())
    except ValueError as exc:
        _fail(failures, "report_path", f"training report must stay under run root: {report_path}")
    training = _read_json(report_path)
    model_ok = training.get("model_name") == MODEL_NAME
    gates["model_config"] = _gate(model_ok, None if model_ok else "model_name is not locked Qwen3-4B", {"model_name": training.get("model_name")})
    if not model_ok:
        _fail(failures, "model_config", "model_name is not locked Qwen3-4B")

    report_run_root_ok = str(training.get("run_root")) == str(root)
    gates["report_run_root"] = _gate(report_run_root_ok, None if report_run_root_ok else "report run_root does not match requested root", {"report_run_root": training.get("run_root")})
    if not report_run_root_ok:
        _fail(failures, "run_root", "report run_root does not match requested root")

    loss_curve = training.get("loss_curve") if isinstance(training.get("loss_curve"), list) else []
    loss_ok = bool(loss_curve)
    gates["loss_curve"] = _gate(loss_ok, None if loss_ok else "loss_curve is missing or empty", {"points": len(loss_curve)})
    if not loss_ok:
        _fail(failures, "loss_curve", "loss_curve is missing or empty")

    duration = training.get("duration_seconds")
    duration_ok = isinstance(duration, (int, float)) and duration > 0
    gates["duration_seconds"] = _gate(duration_ok, None if duration_ok else "duration_seconds must be > 0", {"duration_seconds": duration})
    if not duration_ok:
        _fail(failures, "duration_seconds", "duration_seconds must be > 0")

    vram = training.get("vram_peak_gb")
    vram_ok = isinstance(vram, (int, float)) and vram >= 0
    gates["vram_peak_gb"] = _gate(vram_ok, None if vram_ok else "vram_peak_gb is missing", {"vram_peak_gb": vram})
    if not vram_ok:
        _fail(failures, "vram_peak_gb", "vram_peak_gb is missing")

    adapter = Path(training.get("adapter_path") or root / "adapter")
    try:
        adapter = _require_under_root(adapter, root, "adapter_path")
        adapter_path_ok = True
    except ValueError as exc:
        adapter_path_ok = False
        _fail(failures, "adapter_path", str(exc))
    adapter_hash = _adapter_hash(adapter)
    adapter_config = _read_json(adapter / "adapter_config.json")
    adapter_base = adapter_config.get("base_model_name_or_path")
    adapter_base_ok = adapter_base == MODEL_NAME
    adapter_ok = adapter_path_ok and adapter_hash is not None and training.get("adapter_sha256") == adapter_hash and (adapter / "adapter_config.json").exists()
    gates["adapter_hash"] = _gate(adapter_ok, None if adapter_ok else "adapter hash mismatch or adapter files missing", {"expected": training.get("adapter_sha256"), "actual": adapter_hash})
    if not adapter_ok:
        _fail(failures, "adapter_hash", "adapter hash mismatch or adapter files missing")
    gates["adapter_config"] = _gate(adapter_base_ok, None if adapter_base_ok else "adapter base model is not locked Qwen3-4B", {"base_model_name_or_path": adapter_base})
    if not adapter_base_ok:
        _fail(failures, "adapter_config", f"adapter base model must be {MODEL_NAME}, got {adapter_base}")

    data_manifest = Path(training.get("data_manifest_path") or root / "phase19_data_manifest.json")
    try:
        data_manifest = _require_under_root(data_manifest, root, "data_manifest_path")
        data_manifest_path_ok = True
    except ValueError as exc:
        data_manifest_path_ok = False
        _fail(failures, "data_manifest_path", str(exc))
    data_manifest_payload = _read_json(data_manifest)
    data_hash = _sha256_file(data_manifest) if data_manifest.exists() else None
    data_ok = data_manifest_path_ok and data_hash is not None and training.get("data_manifest_sha256") == data_hash
    gates["data_manifest_hash"] = _gate(data_ok, None if data_ok else "data manifest hash mismatch or missing", {"expected": training.get("data_manifest_sha256"), "actual": data_hash})
    if not data_ok:
        _fail(failures, "data_manifest_hash", "data manifest hash mismatch or missing")

    phase18_hashes = training.get("phase18_artifact_hashes") if isinstance(training.get("phase18_artifact_hashes"), dict) else {}
    expected_phase18_hashes = _expected_phase18_hashes_from_manifest(data_manifest_payload)
    tokenization_report_hashes = _expected_phase18_hashes_from_tokenization_report()
    actual_phase18_hashes, lineage_path_failures = _actual_phase18_hashes_from_manifest(data_manifest_payload, root)
    tokenized_content_failures = _tokenized_content_failures(root)
    failures.extend(lineage_path_failures)
    failures.extend(tokenized_content_failures)
    phase18_ok = not lineage_path_failures and not tokenized_content_failures and phase18_hashes == expected_phase18_hashes and expected_phase18_hashes == actual_phase18_hashes and actual_phase18_hashes == tokenization_report_hashes and all(actual_phase18_hashes.values())
    gates["phase18_artifact_hashes"] = _gate(phase18_ok, None if phase18_ok else "Phase 18/tokenized artifact hashes do not match data manifest, tokenization report, and on-disk artifacts", {"expected": expected_phase18_hashes, "actual": phase18_hashes, "on_disk": actual_phase18_hashes, "tokenization_report": tokenization_report_hashes})
    if not phase18_ok:
        _fail(failures, "phase18_artifact_hashes", "Phase 18/tokenized artifact hashes do not match data manifest, tokenization report, and on-disk artifacts")

    lora = training.get("lora_config") if isinstance(training.get("lora_config"), dict) else {}
    lora_ok = lora.get("r") == 64 and lora.get("lora_alpha") == 64 and float(lora.get("lora_dropout", -1)) == 0.0
    gates["qlora_settings"] = _gate(lora_ok, None if lora_ok else "QLoRA r/alpha/dropout are not locked", lora)
    if not lora_ok:
        _fail(failures, "qlora_settings", "QLoRA r/alpha/dropout are not locked")

    args = training.get("training_args") if isinstance(training.get("training_args"), dict) else {}
    args_ok = args.get("bf16") is True and args.get("attn_implementation") == "sdpa" and args.get("load_in_4bit") is True and args.get("bnb_4bit_quant_type") == "nf4" and args.get("packing") is False
    gates["training_args"] = _gate(args_ok, None if args_ok else "training args are not locked to DGX-safe v4.2 QLoRA", args)
    if not args_ok:
        _fail(failures, "training_args", "training args are not locked to DGX-safe v4.2 QLoRA")

    covered = set(training.get("requirements_covered", []))
    requirements_ok = "TRAIN-01" in covered
    gates["requirements_covered"] = _gate(requirements_ok, None if requirements_ok else "TRAIN-01 coverage missing", {"covered": sorted(covered)})
    if not requirements_ok:
        _fail(failures, "requirements_covered", "TRAIN-01 coverage missing")

    state = training.get("trainer_state") if isinstance(training.get("trainer_state"), dict) else {}
    global_step = int(state.get("global_step") or 0)
    max_steps = int(state.get("max_steps") or 0)
    completed_ok = training.get("mode") == "full" and training.get("completed") is True and training.get("ok") is True and global_step > 0 and (max_steps <= 0 or global_step >= max_steps)
    gates["completed"] = _gate(completed_ok, None if completed_ok else "training report lacks completed full-run evidence", {"completed": training.get("completed"), "ok": training.get("ok"), "mode": training.get("mode"), "global_step": global_step, "max_steps": max_steps})
    if not completed_ok:
        _fail(failures, "completed", "training report lacks completed full-run evidence")

    ok = not failures
    artifact_manifest = {
        "paths": {"run_root": str(root), "adapter": str(adapter), "report": str(report_path), "data_manifest": str(data_manifest)},
        "sha256": {"adapter_sha256": adapter_hash, "data_manifest_sha256": data_hash, "training_report": _sha256_file(report_path) if report_path.exists() else None},
    }
    report = {
        "ok": ok,
        "next_phase_allowed": ok,
        "requirements_covered": ["TRAIN-01"] if ok else [req for req in REQUIREMENTS_COVERED if req in covered],
        "gates": gates,
        "fatal_failures": failures,
        "warnings": warnings,
        "artifact_manifest": artifact_manifest,
        "run_root": str(root),
        "adapter_path": str(adapter),
    }
    if out is not None:
        _write_json(Path(out), report)
    return report


if __name__ == "__main__":
    raise SystemExit(main())
