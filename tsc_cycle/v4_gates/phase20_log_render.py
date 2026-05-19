from __future__ import annotations

import json
from typing import Any, Iterable

from tsc_cycle.constraint_lint import validate
from tsc_cycle.prompt_builder import build_user_prompt, parse_assistant_output
from tsc_cycle.v4_gates.phase17_audit import evaluate_saturation_policy_gate
from tsc_cycle.v4_gates.saturation_policy import classify_saturation_band, classify_violation, is_trivial_phase_range

DEFAULT_BACKEND_LABEL = "tsc-cycle-v4.2-q4_K_M"
SEPARATOR = "-" * 80


def lint_phase20_payload(prediction_input: dict[str, Any], solution: dict[str, int] | None) -> dict[str, Any]:
    if solution is None:
        return {"ok": False, "violations": [{"kind": "unparseable"}]}
    lint = validate(prediction_input, solution)
    return {"ok": bool(lint.ok), "violations": lint.violations}


def _phase_rows(record: dict[str, Any], solution: dict[str, int]) -> list[dict[str, Any]]:
    waits = record.get("input", {}).get("prediction", {}).get("phase_waits", [])
    if not isinstance(waits, list):
        raise ValueError(f"Phase 20 replay phase_waits is not a list for {record.get('sample_id')}")
    rows: list[dict[str, Any]] = []
    for wait in waits:
        if not isinstance(wait, dict):
            raise ValueError(f"Phase 20 replay phase_waits entry is not an object for {record.get('sample_id')}")
        phase_id = str(wait.get("phase_id"))
        row = {
            "origin_artifact": "phase20_reality_replay",
            "sample_id": str(record.get("sample_id")),
            "phase_id": phase_id,
            "pred_saturation": wait.get("pred_saturation"),
            "min_green": wait.get("min_green"),
            "max_green": wait.get("max_green"),
            "final_green": solution.get(phase_id),
            "split": "replay",
            "source": DEFAULT_BACKEND_LABEL,
            "source_origin": "phase20_reality_replay",
        }
        row["saturation_band"] = classify_saturation_band(row["pred_saturation"])
        row["trivial_range"] = is_trivial_phase_range(row)
        row["violation_category"] = classify_violation(row)
        rows.append(row)
    return rows


def ensure_phase20_output_passes(record: dict[str, Any], output: dict[str, Any]) -> None:
    if output.get("sample_id") != record.get("sample_id"):
        raise ValueError(f"Phase 20 sample_id mismatch: {output.get('sample_id')} != {record.get('sample_id')}")
    if output.get("input_sha256") and output.get("input_sha256") != record.get("input_sha256"):
        raise ValueError(f"Phase 20 input hash mismatch for {record.get('sample_id')}")
    raw = str(output.get("raw_text") or "")
    reasoning, solution = parse_assistant_output(raw)
    if not reasoning or solution is None:
        raise ValueError(f"Phase 20 protocol/parse gate failed for {record.get('sample_id')}")
    lint_payload = lint_phase20_payload(record["input"], solution)
    if lint_payload.get("ok") is not True:
        raise ValueError(f"Phase 20 lint gate failed for {record.get('sample_id')}: {lint_payload}")
    policy = evaluate_saturation_policy_gate({"ok": True, "input_count": 1, "rows": _phase_rows(record, solution), "excluded_counts": {}}, source_type="replay")
    if policy.get("ok") is not True:
        raise ValueError(f"Phase 20 saturation policy gate failed for {record.get('sample_id')}: {policy.get('fatal_failures')}")


def render_phase20_reality_test_log(
    records: Iterable[dict[str, Any]],
    outputs: Iterable[dict[str, Any]],
    *,
    backend_label: str = DEFAULT_BACKEND_LABEL,
) -> str:
    recs = list(records)
    outs = list(outputs)
    if len(recs) != len(outs):
        raise ValueError(f"cannot render Phase 20 log with count mismatch: {len(recs)} != {len(outs)}")
    chunks: list[str] = []
    for record, output in zip(recs, outs, strict=True):
        ensure_phase20_output_passes(record, output)
        timestamp = record.get("timestamp") or record.get("as_of") or "unknown-time"
        crossing = record.get("crossing_id") or "unknown"
        prompt = build_user_prompt(record["input"])
        _, parsed = parse_assistant_output(str(output.get("raw_text") or ""))
        lint_payload = lint_phase20_payload(record["input"], parsed)
        chunks.append(f"{timestamp}|INFO|type=prompt|crossing_id={crossing}|sample_id={record['sample_id']}\n\n{prompt}\n{SEPARATOR}")
        chunks.append(
            f"{timestamp}|INFO|type=result|engine={backend_label}|crossing_id={crossing}|sample_id={record['sample_id']}\n"
            f"RAW:\n{output['raw_text']}\n"
            f"PARSED:\n{json.dumps(parsed, ensure_ascii=False, sort_keys=True)}\n"
            f"LINT:\n{json.dumps(lint_payload, ensure_ascii=False, sort_keys=True)}\n"
            f"{SEPARATOR}"
        )
    return "\n".join(chunks) + ("\n" if chunks else "")
