from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tsc_cycle.constraint_lint import validate

REQUIREMENTS_COVERED = [
    "DATAGEN-01",
    "DATAGEN-02",
    "DATAGEN-03",
    "DATAGEN-04",
    "DATAGEN-05",
    "DATAGEN-06",
    "DATAGEN-07",
]
DEFAULT_MIN_SOURCE_ATTEMPTED = {"same_dist": 5250, "ood": 1500, "targeted": 750}


PathLike = str | Path


def _coalesce_path(*values: PathLike | None, name: str) -> Path:
    for value in values:
        if value is not None:
            return Path(value)
    raise TypeError(f"missing required path: {name}")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, f"missing JSON artifact: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, f"malformed JSON {path}: {exc}"
    if not isinstance(payload, dict):
        return {}, f"JSON artifact must be an object: {path}"
    return payload, None


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


def _record_sample_id(record: dict[str, Any]) -> str | None:
    sample_id = record.get("sample_id")
    if sample_id is None and isinstance(record.get("input"), dict):
        sample_id = record["input"].get("sample_id")
    return str(sample_id) if sample_id is not None else None


def _record_input(record: dict[str, Any]) -> dict[str, Any]:
    candidate = record.get("input")
    if isinstance(candidate, dict):
        return candidate
    return record


def _record_solution(record: dict[str, Any]) -> Any:
    result = record.get("result")
    if isinstance(result, dict):
        return result.get("solution")
    return record.get("solution")


def _record_result_success(record: dict[str, Any]) -> bool:
    result = record.get("result")
    if isinstance(result, dict) and "success" in result:
        return result.get("success") is True
    return _record_solution(record) is not None


def _record_source(record: dict[str, Any]) -> str:
    for container in (record, _record_input(record)):
        if not isinstance(container, dict):
            continue
        for key in ("source", "source_tag", "split_hint"):
            value = container.get(key)
            if value:
                return str(value)
        metadata = container.get("metadata")
        if isinstance(metadata, dict):
            for key in ("source", "source_tag"):
                value = metadata.get(key)
                if value:
                    return str(value)
    return "unknown"


def _duplicate_ids(ids: list[str]) -> list[str]:
    counts = Counter(ids)
    return sorted(sample_id for sample_id, count in counts.items() if count > 1)


def _failure(gate: str, reason: str) -> dict[str, str]:
    return {"gate": gate, "reason": reason}


def _normalize_source_minimums(minimums: Mapping[str, Any] | None) -> dict[str, int]:
    if minimums is None:
        return dict(DEFAULT_MIN_SOURCE_ATTEMPTED)
    normalized: dict[str, int] = {}
    for source, minimum in minimums.items():
        normalized[str(source)] = int(minimum)
    return normalized


def _source_counts_from_manifest(manifest: dict[str, Any]) -> dict[str, int]:
    source_counts = manifest.get("source_counts") or manifest.get("counts_written") or manifest.get("counts") or {}
    if not isinstance(source_counts, dict):
        return {}
    normalized: dict[str, int] = {}
    for source, count in source_counts.items():
        try:
            normalized[str(source)] = int(count)
        except (TypeError, ValueError):
            continue
    return normalized


def _source_attempted_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(_record_source(row) for row in rows)
    return {source: int(count) for source, count in counts.items()}


def _add_gate(
    gates: dict[str, Any],
    fatal_failures: list[dict[str, str]],
    name: str,
    passed: bool,
    reason: str | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    gates[name] = {"ok": bool(passed), "reason": reason, "data": data or {}}
    if not passed:
        fatal_failures.append(_failure(name, reason or "failed"))


def build_phase2_report(
    old_labeled: PathLike | None = None,
    new_labeled: PathLike | None = None,
    rejected: PathLike | None = None,
    datagen_manifest: PathLike | None = None,
    merged_out: PathLike | None = None,
    report_out: PathLike | None = None,
    expected_old_sha: str | None = None,
    min_new_valid: int = 6000,
    min_merged_valid: int = 9000,
    labeler_model: str = "gpt-5.5",
    labeler_effort: str = "high",
    workers_max: int = 10,
    min_source_attempted: Mapping[str, Any] | None = None,
    *,
    old_labeled_path: PathLike | None = None,
    new_labeled_path: PathLike | None = None,
    rejected_path: PathLike | None = None,
    manifest_path: PathLike | None = None,
    merged_out_path: PathLike | None = None,
    report_out_path: PathLike | None = None,
    old_sha_before: str | None = None,
    old_sha_after: str | None = None,
) -> dict[str, Any]:
    """Build the Phase 2 merge report and write the merged JSONL only if all gates pass."""

    old_path = _coalesce_path(old_labeled, old_labeled_path, name="old_labeled")
    new_path = _coalesce_path(new_labeled, new_labeled_path, name="new_labeled")
    rejected_path_final = _coalesce_path(rejected, rejected_path, name="rejected")
    manifest_path_final = _coalesce_path(datagen_manifest, manifest_path, name="datagen_manifest")
    merged_path = _coalesce_path(merged_out, merged_out_path, name="merged_out")
    report_path = Path(report_out if report_out is not None else report_out_path) if (report_out is not None or report_out_path is not None) else None

    fatal_failures: list[dict[str, str]] = []
    gates: dict[str, Any] = {}

    actual_old_sha_before = _sha256_file(old_path) if old_path.exists() else ""
    old_rows, old_errors = _read_jsonl(old_path)
    new_rows, new_errors = _read_jsonl(new_path)
    rejected_rows, rejected_errors = _read_jsonl(rejected_path_final)
    manifest, manifest_error = _read_json(manifest_path_final)

    for error in old_errors + new_errors + rejected_errors:
        fatal_failures.append(_failure("jsonl_read", error))
    if manifest_error:
        fatal_failures.append(_failure("datagen_manifest", manifest_error))

    old_sha_before_final = old_sha_before or actual_old_sha_before
    old_sha_after_final = old_sha_after or (_sha256_file(old_path) if old_path.exists() else "")

    old_ids_all = [_record_sample_id(row) for row in old_rows]
    new_ids_all = [_record_sample_id(row) for row in new_rows]
    rejected_ids_all = [_record_sample_id(row) for row in rejected_rows]
    missing_old_ids = sum(1 for sample_id in old_ids_all if sample_id is None)
    missing_new_ids = sum(1 for sample_id in new_ids_all if sample_id is None)
    missing_rejected_ids = sum(1 for sample_id in rejected_ids_all if sample_id is None)

    if missing_old_ids or missing_new_ids or missing_rejected_ids:
        fatal_failures.append(
            _failure(
                "sample_ids_present",
                f"missing sample_id counts: old={missing_old_ids}, new={missing_new_ids}, rejected={missing_rejected_ids}",
            )
        )

    old_ids = {sample_id for sample_id in old_ids_all if sample_id is not None}
    new_ids = {sample_id for sample_id in new_ids_all if sample_id is not None}
    old_new_overlap_ids = sorted(old_ids & new_ids)
    source_minimums = _normalize_source_minimums(min_source_attempted)
    manifest_source_counts = _source_counts_from_manifest(manifest)

    valid_new_rows: list[dict[str, Any]] = []
    lint_failures: list[dict[str, Any]] = []
    for index, row in enumerate(new_rows):
        sample_id = _record_sample_id(row) or f"row:{index}"
        if not _record_result_success(row):
            lint_failures.append({"sample_id": sample_id, "violations": [{"kind": "result_not_success"}]})
            continue
        lint_result = validate(_record_input(row), _record_solution(row))
        if lint_result.ok:
            valid_new_rows.append(row)
        else:
            lint_failures.append({"sample_id": sample_id, "violations": lint_result.violations})

    new_valid = len(valid_new_rows)
    rejected_count = len(rejected_rows)
    merged_valid = len(old_rows) + new_valid
    source_counts = dict(Counter(_record_source(row) for row in valid_new_rows))
    attempted_rows = [*new_rows, *rejected_rows]
    source_attempted_counts = _source_attempted_counts(attempted_rows)
    source_attempted_failures = {
        source: {"attempted": source_attempted_counts.get(source, 0), "minimum": minimum}
        for source, minimum in source_minimums.items()
        if source_attempted_counts.get(source, 0) < minimum
    }
    source_reservoir_failures = {
        source: {"manifest_count": manifest_source_counts.get(source, 0), "minimum": minimum}
        for source, minimum in source_minimums.items()
        if manifest_source_counts.get(source, 0) < minimum
    }

    done_ids = [sample_id for sample_id in [*new_ids_all, *rejected_ids_all] if sample_id is not None]
    duplicate_done_id_list = _duplicate_ids(done_ids)
    duplicate_api_attempt_ids = duplicate_done_id_list

    labeler_evidence = {
        "model": labeler_model,
        "effort": labeler_effort,
        "workers_max": workers_max,
        "workers_within_cap": workers_max <= 10,
        "attempted_new": len(new_rows) + rejected_count,
        "accepted_new": len(new_rows),
        "rejected_new": rejected_count,
    }
    resume_evidence = {
        "done_ids_total": len(done_ids),
        "duplicate_done_ids": len(duplicate_done_id_list),
        "duplicate_api_attempt_ids": duplicate_api_attempt_ids,
        "append_outputs_present": new_path.exists() and rejected_path_final.exists(),
    }

    _add_gate(
        gates,
        fatal_failures,
        "old_sha_unchanged",
        bool(old_sha_before_final) and old_sha_before_final == old_sha_after_final,
        None if old_sha_before_final == old_sha_after_final else "old labeled SHA changed during merge evidence window",
        {"old_sha_before": old_sha_before_final, "old_sha_after": old_sha_after_final},
    )
    if expected_old_sha is not None:
        _add_gate(
            gates,
            fatal_failures,
            "expected_old_sha",
            old_sha_before_final == expected_old_sha and old_sha_after_final == expected_old_sha,
            None if old_sha_before_final == expected_old_sha and old_sha_after_final == expected_old_sha else "old labeled SHA does not match expected_old_sha",
            {"expected_old_sha": expected_old_sha},
        )
    _add_gate(
        gates,
        fatal_failures,
        "old_new_overlap",
        len(old_new_overlap_ids) == 0,
        None if not old_new_overlap_ids else f"old/new sample_id overlap count={len(old_new_overlap_ids)}",
        {"overlap_ids_sample": old_new_overlap_ids[:10]},
    )
    _add_gate(
        gates,
        fatal_failures,
        "all_new_lint_ok",
        len(lint_failures) == 0,
        None if not lint_failures else f"accepted new lint failures count={len(lint_failures)}",
        {"lint_failures_sample": lint_failures[:10]},
    )
    _add_gate(
        gates,
        fatal_failures,
        "min_new_valid",
        new_valid >= min_new_valid,
        None if new_valid >= min_new_valid else f"new_valid {new_valid} < min_new_valid {min_new_valid}",
        {"new_valid": new_valid, "min_new_valid": min_new_valid},
    )
    _add_gate(
        gates,
        fatal_failures,
        "min_merged_valid",
        merged_valid >= min_merged_valid,
        None if merged_valid >= min_merged_valid else f"merged_valid {merged_valid} < min_merged_valid {min_merged_valid}",
        {"merged_valid": merged_valid, "min_merged_valid": min_merged_valid},
    )
    _add_gate(
        gates,
        fatal_failures,
        "source_reservoir_coverage",
        not source_reservoir_failures,
        None if not source_reservoir_failures else f"manifest source counts below minimums: {source_reservoir_failures}",
        {"manifest_source_counts": manifest_source_counts, "min_source_attempted": source_minimums},
    )
    _add_gate(
        gates,
        fatal_failures,
        "source_attempted_coverage",
        not source_attempted_failures,
        None if not source_attempted_failures else f"attempted source counts below minimums: {source_attempted_failures}",
        {"source_attempted_counts": source_attempted_counts, "min_source_attempted": source_minimums},
    )
    _add_gate(
        gates,
        fatal_failures,
        "labeler_model",
        labeler_model == "gpt-5.5",
        None if labeler_model == "gpt-5.5" else f"labeler_model must be gpt-5.5, got {labeler_model}",
    )
    _add_gate(
        gates,
        fatal_failures,
        "labeler_effort",
        labeler_effort == "high",
        None if labeler_effort == "high" else f"labeler_effort must be high, got {labeler_effort}",
    )
    _add_gate(
        gates,
        fatal_failures,
        "worker_cap",
        workers_max <= 10,
        None if workers_max <= 10 else f"workers_max {workers_max} exceeds cap 10",
        {"workers_max": workers_max},
    )
    _add_gate(
        gates,
        fatal_failures,
        "resume_no_duplicates",
        not duplicate_done_id_list,
        None if not duplicate_done_id_list else f"duplicate done IDs count={len(duplicate_done_id_list)}",
        {"duplicate_done_ids_sample": duplicate_done_id_list[:10]},
    )
    _add_gate(
        gates,
        fatal_failures,
        "append_outputs_present",
        resume_evidence["append_outputs_present"],
        None if resume_evidence["append_outputs_present"] else "accepted and rejected append outputs must both exist",
    )

    ok = not fatal_failures
    merged_written = False
    if ok:
        merged_path.parent.mkdir(parents=True, exist_ok=True)
        with merged_path.open("w", encoding="utf-8") as fh:
            for row in [*old_rows, *valid_new_rows]:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        merged_written = True

    report = {
        "ok": ok,
        "fatal_failures": fatal_failures,
        "old_sha_before": old_sha_before_final,
        "old_sha_after": old_sha_after_final,
        "expected_old_sha": expected_old_sha,
        "old_count": len(old_rows),
        "new_valid": new_valid,
        "rejected_count": rejected_count,
        "merged_valid": merged_valid,
        "old_new_overlap": len(old_new_overlap_ids),
        "old_new_overlap_ids_sample": old_new_overlap_ids[:10],
        "source_counts": source_counts,
        "source_attempted_counts": source_attempted_counts,
        "min_source_attempted": source_minimums,
        "manifest_source_counts": manifest_source_counts,
        "all_new_lint_ok": len(lint_failures) == 0,
        "lint_failures_sample": lint_failures[:10],
        "labeler_evidence": labeler_evidence,
        "resume_evidence": resume_evidence,
        "requirements_covered": REQUIREMENTS_COVERED,
        "gates": gates,
        "paths": {
            "old_labeled": str(old_path),
            "new_labeled": str(new_path),
            "rejected": str(rejected_path_final),
            "datagen_manifest": str(manifest_path_final),
            "merged_out": str(merged_path),
            "report_out": str(report_path) if report_path is not None else None,
        },
        "merged_written": merged_written,
    }

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Phase 2 v3 datagen merge report and fail-closed merged JSONL")
    parser.add_argument("--old-labeled", default="data/labeled.jsonl")
    parser.add_argument("--new-labeled", default="data/v3/phase2/labeled_new.jsonl")
    parser.add_argument("--rejected", default="data/v3/phase2/rejected_new.jsonl")
    parser.add_argument("--datagen-manifest", default="data/v3/phase2/datagen_manifest.json")
    parser.add_argument("--merged-out", default="data/v3/phase2/labeled_merged.jsonl")
    parser.add_argument("--report-out", default="data/v3/phase2/merge_report.json")
    parser.add_argument("--min-new-valid", type=int, default=6000)
    parser.add_argument("--min-merged-valid", type=int, default=9000)
    parser.add_argument("--expected-old-sha")
    parser.add_argument("--labeler-model", default="gpt-5.5")
    parser.add_argument("--labeler-effort", default="high")
    parser.add_argument("--workers-max", type=int, default=10)
    parser.add_argument(
        "--min-source-attempted",
        default=json.dumps(DEFAULT_MIN_SOURCE_ATTEMPTED, sort_keys=True),
        help="JSON object of required attempted counts per source; use '{}' to disable source coverage gate",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        min_source_attempted = json.loads(args.min_source_attempted)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--min-source-attempted must be a JSON object: {exc}") from exc
    if not isinstance(min_source_attempted, dict):
        raise SystemExit("--min-source-attempted must be a JSON object")
    report = build_phase2_report(
        old_labeled=args.old_labeled,
        new_labeled=args.new_labeled,
        rejected=args.rejected,
        datagen_manifest=args.datagen_manifest,
        merged_out=args.merged_out,
        report_out=args.report_out,
        expected_old_sha=args.expected_old_sha,
        min_new_valid=args.min_new_valid,
        min_merged_valid=args.min_merged_valid,
        labeler_model=args.labeler_model,
        labeler_effort=args.labeler_effort,
        workers_max=args.workers_max,
        min_source_attempted=min_source_attempted,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
