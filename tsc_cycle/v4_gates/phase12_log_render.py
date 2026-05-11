"""Shared canonical rendering helpers for Phase 12 reality_test.log evidence."""

from __future__ import annotations

import json
from typing import Any, Iterable

from tsc_cycle.constraint_lint import validate
from tsc_cycle.prompt_builder import build_user_prompt, parse_assistant_output

DEFAULT_BACKEND_LABEL = "tsc-cycle-v4-q4_K_M"
SEPARATOR = "-" * 80


def lint_phase12_payload(prediction_input: dict[str, Any], solution: dict[str, int] | None) -> dict[str, Any]:
    """Recompute Phase 12 constraint lint from the audited input and parsed solution."""
    if solution is None:
        return {"ok": False, "violations": [{"kind": "unparseable"}]}
    lint = validate(prediction_input, solution)
    return {"ok": bool(lint.ok), "violations": lint.violations}


def ensure_phase12_output_passes(record: dict[str, Any], output: dict[str, Any]) -> None:
    """Fail closed unless raw_text parses and lints against the matching current input."""
    if output.get("sample_id") != record.get("sample_id"):
        raise ValueError(f"Phase 12 sample_id mismatch: {output.get('sample_id')} != {record.get('sample_id')}")
    if output.get("input_sha256") and output.get("input_sha256") != record.get("input_sha256"):
        raise ValueError(f"Phase 12 input hash mismatch for {record.get('sample_id')}")
    raw = str(output.get("raw_text") or "")
    reasoning, solution = parse_assistant_output(raw)
    if not reasoning or solution is None:
        raise ValueError(f"Phase 12 protocol/parse gate failed for {record.get('sample_id')}")
    lint_payload = lint_phase12_payload(record["input"], solution)
    if lint_payload.get("ok") is not True:
        raise ValueError(f"Phase 12 lint gate failed for {record.get('sample_id')}: {lint_payload}")


def render_reality_test_log(
    records: Iterable[dict[str, Any]],
    outputs: Iterable[dict[str, Any]],
    *,
    backend_label: str = DEFAULT_BACKEND_LABEL,
) -> str:
    """Render the canonical Phase 12 final log from audited inputs and raw outputs."""
    recs = list(records)
    outs = list(outputs)
    if len(recs) != len(outs):
        raise ValueError(f"cannot render Phase 12 log with count mismatch: {len(recs)} != {len(outs)}")
    chunks: list[str] = []
    for record, output in zip(recs, outs, strict=True):
        ensure_phase12_output_passes(record, output)
        timestamp = record.get("timestamp") or record.get("as_of") or "unknown-time"
        crossing = record.get("crossing_id") or "unknown"
        prompt = build_user_prompt(record["input"])
        _, parsed = parse_assistant_output(str(output.get("raw_text") or ""))
        lint_payload = lint_phase12_payload(record["input"], parsed)
        chunks.append(f"{timestamp}|INFO|type=prompt|crossing_id={crossing}|sample_id={record['sample_id']}\n\n{prompt}\n{SEPARATOR}")
        chunks.append(
            f"{timestamp}|INFO|type=result|engine={backend_label}|crossing_id={crossing}|sample_id={record['sample_id']}\n"
            f"RAW:\n{output['raw_text']}\n"
            f"PARSED:\n{json.dumps(parsed, ensure_ascii=False, sort_keys=True)}\n"
            f"LINT:\n{json.dumps(lint_payload, ensure_ascii=False, sort_keys=True)}\n"
            f"{SEPARATOR}"
        )
    return "\n".join(chunks) + ("\n" if chunks else "")
