from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from tsc_cycle.constraint_lint import validate
from tsc_cycle.prompt_builder import MALFORMED_THINK_CLOSE, NATIVE_THINK_TAGS, TAG_SOLUTION_CLOSE, TAG_SOLUTION_OPEN, TAG_THINK_CLOSE, TAG_THINK_OPEN, parse_assistant_output
from tsc_cycle.student.sft_v4 import validate_run_root

REQUIRED_DATA4B = {"DATA4B-01", "DATA4B-02", "DATA4B-03", "DATA4B-04", "DATA4B-05"}


def _gate(ok: bool, reason: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": bool(ok), "reason": reason, "data": data or {}}


def _add_failure(fatal_failures: list[dict[str, str]], gate: str, reason: str) -> None:
    fatal_failures.append({"gate": gate, "reason": reason})


def _phase8_gate(report: dict[str, Any], fatal_failures: list[dict[str, str]]) -> dict[str, Any]:
    phase8 = report.get("phase8_gate") if isinstance(report.get("phase8_gate"), dict) else {}
    covered = set(phase8.get("requirements_covered", []))
    ok = phase8.get("ok") is True and phase8.get("next_phase_allowed") is True and REQUIRED_DATA4B <= covered
    reason = None if ok else "Phase 8 handoff is not green or lacks DATA4B coverage"
    if not ok:
        _add_failure(fatal_failures, "phase8_handoff", reason)
    return _gate(ok, reason, {"requirements_covered": sorted(covered), "ok": phase8.get("ok"), "next_phase_allowed": phase8.get("next_phase_allowed")})


def _tokenizer_gate(report: dict[str, Any], fatal_failures: list[dict[str, str]]) -> dict[str, Any]:
    payload = report.get("tokenizer_leakage") if isinstance(report.get("tokenizer_leakage"), dict) else {}
    ok = (
        int(payload.get("native_think_text_count", -1) or 0) == 0
        and int(payload.get("native_think_token_id_count", -1) or 0) == 0
        and bool(payload.get("checked_untruncated_ids"))
        and bool(payload.get("native_think_token_ids"))
    )
    reason = None if ok else "native think text/token leakage evidence is red or incomplete"
    if not ok:
        _add_failure(fatal_failures, "tokenizer_leakage", reason)
    return _gate(ok, reason, payload)


def _sample_format_gate(report: dict[str, Any], fatal_failures: list[dict[str, str]]) -> dict[str, Any]:
    payload = report.get("sample_format") if isinstance(report.get("sample_format"), dict) else {}
    ok = (
        int(payload.get("examples_checked", 0) or 0) > 0
        and payload.get("raw_text_protocol") is True
        and int(payload.get("malformed_close_tag_count", 0) or 0) == 0
        and int(payload.get("native_think_text_count", 0) or 0) == 0
        and payload.get("contains_start_working_out") is True
        and payload.get("contains_end_working_out_close") is True
        and payload.get("contains_solution_tags") is True
        and payload.get("packing") is False
        and payload.get("chat_template_used") is False
    )
    reason = None if ok else "sample format evidence is red or incomplete"
    if not ok:
        _add_failure(fatal_failures, "sample_format", reason)
    return _gate(ok, reason, payload)


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _minimal_train_gate(report: dict[str, Any], fatal_failures: list[dict[str, str]]) -> dict[str, Any]:
    payload = report.get("minimal_train_step") if isinstance(report.get("minimal_train_step"), dict) else {}
    adapter_path = str(payload.get("adapter_path", ""))
    checkpoint_path = str(payload.get("checkpoint_path", ""))
    valid_roots: set[Path] = set()
    invalid_path_seen = False
    for candidate in (adapter_path, checkpoint_path):
        candidate_valid = False
        parts = Path(candidate).parts
        for idx, part in enumerate(parts):
            if part == "runs" and idx + 1 < len(parts):
                try:
                    valid_roots.add(validate_run_root(Path(*parts[: idx + 2])))
                    candidate_valid = True
                except ValueError:
                    continue
        invalid_path_seen = invalid_path_seen or not candidate_valid
    root_ok = len(valid_roots) == 1 and not invalid_path_seen
    ok = (
        payload.get("ran") is True
        and int(payload.get("global_step", 0) or 0) >= 1
        and _finite(payload.get("loss"))
        and payload.get("finite_loss") is True
        and payload.get("saved") is True
        and root_ok
        and "/smoke/" in adapter_path
    )
    reason = None if ok else "minimal train step evidence is red or incomplete"
    if not ok:
        _add_failure(fatal_failures, "minimal_train_step", reason)
    return _gate(ok, reason, payload)


def _solution_gate(report: dict[str, Any], fatal_failures: list[dict[str, str]]) -> dict[str, Any]:
    rows = report.get("generated_outputs") if isinstance(report.get("generated_outputs"), list) else []
    failures: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            failures.append("generated row is not an object")
            continue
        text = str(row.get("text") or row.get("generated_text") or "")
        if MALFORMED_THINK_CLOSE in text or any(tag in text for tag in NATIVE_THINK_TAGS):
            failures.append(f"parse failed for {row.get('sample_id', '<unknown>')}: forbidden tags")
            continue
        if not (TAG_THINK_OPEN in text and TAG_THINK_CLOSE in text and TAG_SOLUTION_OPEN in text and TAG_SOLUTION_CLOSE in text):
            failures.append(f"parse failed for {row.get('sample_id', '<unknown>')}: missing protocol tags")
            continue
        _reasoning, solution = parse_assistant_output(text)
        if solution is None:
            failures.append(f"parse failed for {row.get('sample_id', '<unknown>')}")
            continue
        prediction_input = row.get("input") or row.get("prediction_input")
        lint = validate(prediction_input if isinstance(prediction_input, dict) else {}, solution)
        if not lint.ok:
            failures.append(f"lint failed for {row.get('sample_id', '<unknown>')}: {lint.violations}")
    ok = bool(rows) and not failures
    reason = None if ok else "; ".join(failures[:5]) if failures else "missing generated outputs"
    if not ok:
        _add_failure(fatal_failures, "solution_parse_and_lint", reason)
    return _gate(ok, reason, {"checked": len(rows), "failures": failures[:10]})


def evaluate_pretrain_smoke_report(report: dict[str, Any]) -> dict[str, Any]:
    fatal_failures: list[dict[str, str]] = []
    gates = {
        "phase8_handoff": _phase8_gate(report, fatal_failures),
        "tokenizer_leakage": _tokenizer_gate(report, fatal_failures),
        "sample_format": _sample_format_gate(report, fatal_failures),
        "minimal_train_step": _minimal_train_gate(report, fatal_failures),
        "solution_parse_and_lint": _solution_gate(report, fatal_failures),
    }
    ok = not fatal_failures
    return {
        "ok": ok,
        "next_phase_allowed": ok,
        "full_train_allowed": ok,
        "requirements_covered": ["SFT4B-02"] if ok else [],
        "gates": gates,
        "fatal_failures": fatal_failures,
        "warnings": [],
        "run_root": report.get("run_root"),
        "data_manifest_sha256": report.get("data_manifest_sha256"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate v4 Phase 9 pretrain smoke evidence")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    payload = evaluate_pretrain_smoke_report(report)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
