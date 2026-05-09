"""Phase 4 dry-run gate evaluator for Qwen3.5-9B SFT.

The dry-run gate is intentionally fail-closed: full SFT is allowed only when
500 deterministic OOD generations pass hard-constraint lint and the trainer's
callback-produced grad_gate.json proves first-200-step gradient stability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from tsc_cycle import constraint_lint
from tsc_cycle.constraint_lint import validate
from tsc_cycle.prompt_builder import build_assistant_prefill, build_user_prompt, parse_assistant_output
from tsc_cycle.student.sft_v3 import evaluate_grad_gate, validate_run_root
from tsc_cycle.tokenizer_check import native_think_token_ids

REQUIREMENTS_COVERED = ["SFT-04", "SFT-06"]
DEFAULT_SAMPLE_COUNT = 500
MIN_OOD_PASS_RATE = 0.95
MAX_DRY_RUN_SECONDS = 3600
DEFAULT_MERGED_JSONL = Path("data/v3/phase2/labeled_merged.jsonl")
DEFAULT_OOD_INDEX = Path("data/splits/v3/ood_val.index.jsonl")
DEFAULT_EVIDENCE_NAME = "dry_run_ood_generations.jsonl"
DEFAULT_REPORT_NAME = "dry_run_report.json"


def _failure(gate: str, reason: str) -> dict[str, str]:
    return {"gate": gate, "reason": reason}


def _gate(ok: bool, *, expected: Any = None, observed: Any = None, reason: str | None = None) -> dict[str, Any]:
    return {"ok": bool(ok), "expected": expected, "observed": observed, "reason": reason}


def _json_sha256(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"JSONL row must be an object {path}:{line_no}")
            rows.append(payload)
    return rows


def _record_input(record: dict[str, Any]) -> dict[str, Any]:
    candidate = record.get("input")
    return candidate if isinstance(candidate, dict) else record


def _record_sample_id(record: dict[str, Any]) -> str | None:
    for container in (record, _record_input(record)):
        if isinstance(container, dict) and container.get("sample_id") is not None:
            return str(container["sample_id"])
    return None


def _load_grad_gate(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {
            "ok": False,
            "status": "missing",
            "observed_steps": 0,
            "grad_norm_p99": None,
            "loss_finite": False,
            "fatal_failures": [_failure("grad_gate.json", "missing grad_gate.json path")],
        }
    grad_gate_path = Path(path)
    if not grad_gate_path.exists():
        return {
            "ok": False,
            "status": "missing",
            "observed_steps": 0,
            "grad_norm_p99": None,
            "loss_finite": False,
            "fatal_failures": [_failure("grad_gate.json", f"missing grad_gate.json: {grad_gate_path}")],
        }
    payload = _read_json(grad_gate_path)
    if "loss_rows" in payload or "grad_norm_rows" in payload:
        rows_by_step: dict[int, dict[str, Any]] = {}
        for row in payload.get("loss_rows", []):
            if isinstance(row, dict):
                rows_by_step.setdefault(int(row.get("step", 0) or 0), {"step": int(row.get("step", 0) or 0)}).update({"loss": row.get("loss")})
        for row in payload.get("grad_norm_rows", []):
            if isinstance(row, dict):
                rows_by_step.setdefault(int(row.get("step", 0) or 0), {"step": int(row.get("step", 0) or 0)}).update({"grad_norm": row.get("grad_norm")})
        evaluated = evaluate_grad_gate(rows_by_step.values(), gate_steps=200, p99_limit=3.0, stopped_early=bool(payload.get("stopped_early")))
        if payload.get("ok") is not True:
            evaluated["ok"] = False
            evaluated["status"] = "fail"
            evaluated.setdefault("fatal_failures", []).extend(payload.get("fatal_failures", []))
        return evaluated
    return payload


def evaluate_dry_run_gate(report: dict[str, Any]) -> dict[str, Any]:
    """Evaluate SFT-04/SFT-06 dry-run permission from a dry-run report dict."""

    fatal_failures: list[dict[str, str]] = []
    gates: dict[str, Any] = {}

    sample_count = int(report.get("sample_count", 0) or 0)
    sample_count_ok = sample_count == 500
    gates["sample_count"] = _gate(sample_count_ok, expected=500, observed=sample_count)
    if not sample_count_ok:
        fatal_failures.append(_failure("sample_count", f"sample_count {sample_count} != 500"))

    pass_rate_value = report.get("ood_hard_constraint_pass_rate")
    try:
        pass_rate = float(pass_rate_value)
    except (TypeError, ValueError):
        pass_rate = math.nan
    pass_rate_ok = math.isfinite(pass_rate) and pass_rate >= 0.95
    gates["ood_hard_constraint_pass_rate"] = _gate(pass_rate_ok, expected=">=0.95", observed=pass_rate_value)
    if not pass_rate_ok:
        fatal_failures.append(_failure("ood_hard_constraint_pass_rate", f"OOD hard-constraint pass rate {pass_rate_value} < 0.95"))

    elapsed_value = report.get("elapsed_seconds", 0)
    try:
        elapsed_seconds = float(elapsed_value)
    except (TypeError, ValueError):
        elapsed_seconds = math.inf
    elapsed_ok = math.isfinite(elapsed_seconds) and elapsed_seconds <= 3600
    gates["elapsed_seconds"] = _gate(elapsed_ok, expected="<=3600", observed=elapsed_value)
    if not elapsed_ok:
        fatal_failures.append(_failure("elapsed_seconds", f"dry-run elapsed_seconds {elapsed_value} exceeds 3600"))

    adapter_recorded = bool(report.get("dry_run_adapter_recorded") or report.get("dry_run_adapter_path") or report.get("adapter_path") or report.get("checkpoint_path"))
    gates["dry_run_adapter_recorded"] = _gate(adapter_recorded, expected=True, observed=adapter_recorded)
    if not adapter_recorded:
        fatal_failures.append(_failure("dry_run_adapter_recorded", "dry-run adapter/checkpoint path missing"))

    native_leak_count = int(report.get("native_think_leak_count", 0) or 0)
    native_leak_ok = native_leak_count == 0
    gates["native_think_leak"] = _gate(native_leak_ok, expected=0, observed=native_leak_count)
    if not native_leak_ok:
        fatal_failures.append(_failure("native_think_leak", f"native <think> leakage count={native_leak_count}"))

    grad_gate_report = report.get("grad_gate") if isinstance(report.get("grad_gate"), dict) else _load_grad_gate(report.get("grad_gate_path"))
    grad_norm_p99 = grad_gate_report.get("grad_norm_p99")
    observed_steps = int(grad_gate_report.get("observed_steps", grad_gate_report.get("steps", 0)) or 0)
    loss_finite = bool(grad_gate_report.get("loss_finite"))
    grad_norm_finite = grad_gate_report.get("grad_norm_finite", True) is True
    try:
        grad_p99_float = float(grad_norm_p99)
    except (TypeError, ValueError):
        grad_p99_float = math.nan
    grad_gate_ok = (
        grad_gate_report.get("ok") is True
        and observed_steps >= 200
        and math.isfinite(grad_p99_float)
        and grad_p99_float < 3.0
        and loss_finite
        and grad_norm_finite
        and not grad_gate_report.get("fatal_failures")
    )
    gates["grad_gate"] = _gate(
        grad_gate_ok,
        expected="ok=true, observed_steps>=200, grad_norm_p99<3.0, finite losses",
        observed={
            "ok": grad_gate_report.get("ok"),
            "observed_steps": observed_steps,
            "grad_norm_p99": grad_norm_p99,
            "loss_finite": loss_finite,
            "grad_norm_finite": grad_norm_finite,
            "fatal_failures": grad_gate_report.get("fatal_failures", []),
        },
    )
    if not grad_gate_ok:
        fatal_failures.append(_failure("grad_gate", "callback-produced grad_gate.json did not pass first-200-step stability gates"))

    for item in report.get("fatal_failures", []):
        if isinstance(item, dict) and "gate" in item:
            fatal_failures.append({"gate": str(item["gate"]), "reason": str(item.get("reason", "reported fatal failure"))})

    ok = not fatal_failures
    return {
        "ok": ok,
        "full_run_allowed": ok,
        "gates": gates,
        "fatal_failures": fatal_failures,
        "requirements_covered": REQUIREMENTS_COVERED,
        "sample_count": sample_count,
        "ood_hard_constraint_pass_rate": pass_rate if math.isfinite(pass_rate) else pass_rate_value,
        "elapsed_seconds": elapsed_seconds if math.isfinite(elapsed_seconds) else elapsed_value,
        "grad_gate_path": str(report.get("grad_gate_path", "")),
        "grad_gate_status": "pass" if grad_gate_ok else "fail",
        "grad_norm_p99": grad_norm_p99,
        "native_think_leak_count": native_leak_count,
    }


def recover_ood_samples(index_path: Path, merged_jsonl_path: Path, *, sample_count: int = DEFAULT_SAMPLE_COUNT) -> list[dict[str, Any]]:
    index_rows = _read_jsonl(index_path)
    raw_rows = _read_jsonl(merged_jsonl_path)
    recovered: list[dict[str, Any]] = []
    for index_row in index_rows[:sample_count]:
        raw_index = int(index_row["raw_index"])
        raw_record = raw_rows[raw_index]
        sample_id = str(index_row["sample_id"])
        if _record_sample_id(raw_record) != sample_id:
            raise ValueError(f"OOD index/raw sample_id mismatch at raw_index={raw_index}: {sample_id} != {_record_sample_id(raw_record)}")
        prediction_input = _record_input(raw_record)
        recovered.append(
            {
                "sample_id": sample_id,
                "raw_index": raw_index,
                "prediction_input": prediction_input,
                "input_hash": index_row.get("input_hash") or _json_sha256(prediction_input),
                "prompt_hash": index_row.get("prompt_hash"),
                "record_hash": index_row.get("record_hash"),
            }
        )
    return recovered


def _load_generation_stack(adapter_path: Path):
    from peft import AutoPeftModelForCausalLM
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(adapter_path)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoPeftModelForCausalLM.from_pretrained(adapter_path, device_map={"": 0}, torch_dtype="auto", attn_implementation="sdpa")
    model.eval()
    return model, tokenizer


def generate_and_lint_ood(
    *,
    model: Any,
    tokenizer: Any,
    samples: Iterable[dict[str, Any]],
    evidence_path: Path,
    max_new_tokens: int = 512,
) -> dict[str, Any]:
    native_ids = native_think_token_ids(tokenizer)
    evidence_rows: list[dict[str, Any]] = []
    pass_count = 0
    native_leak_count = 0
    violation_counter: Counter[str] = Counter()
    for sample in samples:
        prompt = build_user_prompt(sample["prediction_input"]) + "\n" + build_assistant_prefill()
        encoded = tokenizer(prompt, return_tensors="pt")
        if hasattr(encoded, "to"):
            encoded = encoded.to(getattr(model, "device", "cuda"))
        output = model.generate(**encoded, max_new_tokens=max_new_tokens, do_sample=False)
        input_len = encoded["input_ids"].shape[1]
        generated_ids = output[0][input_len:].tolist()
        generated_text = tokenizer.decode(generated_ids, skip_special_tokens=False)
        native_leak = bool(set(generated_ids) & native_ids) or "<think>" in generated_text or "</think>" in generated_text
        if native_leak:
            native_leak_count += 1
        _reasoning, parsed_solution = parse_assistant_output(build_assistant_prefill() + generated_text)
        lint_result = validate(sample["prediction_input"], parsed_solution)
        if lint_result.ok and not native_leak:
            pass_count += 1
        for violation in lint_result.violations:
            violation_counter[str(violation.get("kind", "unknown"))] += 1
        row = {
            "sample_id": sample["sample_id"],
            "raw_index": sample["raw_index"],
            "prediction_input": sample["prediction_input"],
            "generated_text": generated_text,
            "generated_token_ids": generated_ids,
            "parsed_solution": parsed_solution,
            "native_think_leak": native_leak,
            "lint_result": {"ok": lint_result.ok and not native_leak, "violations": lint_result.violations},
        }
        evidence_rows.append(row)
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    with evidence_path.open("w", encoding="utf-8") as fh:
        for row in evidence_rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    sample_count = len(evidence_rows)
    pass_rate = pass_count / sample_count if sample_count else 0.0
    return {
        "sample_count": sample_count,
        "passed_lint_count": pass_count,
        "failed_lint_count": sample_count - pass_count,
        "ood_hard_constraint_pass_rate": pass_rate,
        "native_think_leak_count": native_leak_count,
        "violation_counts": dict(sorted(violation_counter.items())),
        "evidence_jsonl": str(evidence_path),
        "sample_ids_sha256": _json_sha256([row["sample_id"] for row in evidence_rows]),
    }


def build_dry_run_report(
    *,
    run_root: Path,
    grad_gate_path: Path,
    adapter_path: Path,
    evidence_path: Path,
    elapsed_seconds: float,
    merged_jsonl_path: Path = DEFAULT_MERGED_JSONL,
    ood_index_path: Path = DEFAULT_OOD_INDEX,
    sample_count: int = DEFAULT_SAMPLE_COUNT,
    max_new_tokens: int = 512,
) -> dict[str, Any]:
    run_root = validate_run_root(run_root)
    started = time.time()
    samples = recover_ood_samples(ood_index_path, merged_jsonl_path, sample_count=sample_count)
    if not grad_gate_path.exists():
        generation_report = {
            "sample_count": 0,
            "passed_lint_count": 0,
            "failed_lint_count": 0,
            "ood_hard_constraint_pass_rate": 0.0,
            "native_think_leak_count": 0,
            "violation_counts": {},
            "evidence_jsonl": str(evidence_path),
            "sample_ids_sha256": _json_sha256([sample["sample_id"] for sample in samples]),
            "fatal_failures": [_failure("grad_gate.json", f"missing grad_gate.json: {grad_gate_path}")],
        }
    elif not adapter_path.exists():
        generation_report = {
            "sample_count": 0,
            "passed_lint_count": 0,
            "failed_lint_count": 0,
            "ood_hard_constraint_pass_rate": 0.0,
            "native_think_leak_count": 0,
            "violation_counts": {},
            "evidence_jsonl": str(evidence_path),
            "sample_ids_sha256": _json_sha256([sample["sample_id"] for sample in samples]),
            "fatal_failures": [_failure("dry_run_adapter_recorded", f"missing adapter path: {adapter_path}")],
        }
    else:
        model, tokenizer = _load_generation_stack(adapter_path)
        generation_report = generate_and_lint_ood(
            model=model,
            tokenizer=tokenizer,
            samples=samples,
            evidence_path=evidence_path,
            max_new_tokens=max_new_tokens,
        )
    report = {
        **generation_report,
        "run_root": str(run_root),
        "dry_run_adapter_path": str(adapter_path),
        "dry_run_adapter_recorded": adapter_path.exists(),
        "grad_gate_path": str(grad_gate_path),
        "elapsed_seconds": elapsed_seconds,
        "wall_clock_generation_seconds": time.time() - started,
        "requirements_covered": REQUIREMENTS_COVERED,
        "sample_source": {
            "merged_jsonl": str(merged_jsonl_path),
            "ood_val_index": str(ood_index_path),
            "sample_count_requested": sample_count,
        },
    }
    report = {**report, **evaluate_dry_run_gate(report)}
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate Phase 4 500-sample dry-run gate")
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--grad-gate", default=None, help="defaults to <run-root>/reports/dry-run/grad_gate.json")
    parser.add_argument("--adapter-path", default=None, help="defaults to <run-root>/adapter")
    parser.add_argument("--merged-jsonl", default=str(DEFAULT_MERGED_JSONL))
    parser.add_argument("--ood-index", default=str(DEFAULT_OOD_INDEX))
    parser.add_argument("--evidence-out", default=None)
    parser.add_argument("--report-out", default=None)
    parser.add_argument("--elapsed-seconds", type=float, required=True)
    parser.add_argument("--sample-count", type=int, default=DEFAULT_SAMPLE_COUNT)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_root = validate_run_root(Path(args.run_root))
    grad_gate_path = Path(args.grad_gate) if args.grad_gate else run_root / "reports" / "dry-run" / "grad_gate.json"
    adapter_path = Path(args.adapter_path) if args.adapter_path else run_root / "adapter"
    evidence_path = Path(args.evidence_out) if args.evidence_out else run_root / "reports" / "dry-run" / DEFAULT_EVIDENCE_NAME
    report_path = Path(args.report_out) if args.report_out else run_root / "reports" / "dry-run" / DEFAULT_REPORT_NAME
    try:
        report = build_dry_run_report(
            run_root=run_root,
            grad_gate_path=grad_gate_path,
            adapter_path=adapter_path,
            evidence_path=evidence_path,
            elapsed_seconds=args.elapsed_seconds,
            merged_jsonl_path=Path(args.merged_jsonl),
            ood_index_path=Path(args.ood_index),
            sample_count=args.sample_count,
            max_new_tokens=args.max_new_tokens,
        )
    except Exception as exc:  # fail closed for wrapper consumption
        report = {
            "ok": False,
            "full_run_allowed": False,
            "requirements_covered": REQUIREMENTS_COVERED,
            "fatal_failures": [_failure("dry_run_gate_exception", str(exc))],
            "gates": {},
            "run_root": str(run_root),
            "grad_gate_path": str(grad_gate_path),
            "dry_run_adapter_path": str(adapter_path),
            "elapsed_seconds": args.elapsed_seconds,
        }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.get("ok") is True and report.get("full_run_allowed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
