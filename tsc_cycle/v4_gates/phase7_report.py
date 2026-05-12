from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

FROZEN_BASELINE_ROOT = Path("/home/samuel/TSC_CYCLE/runs/20260507T032419Z")
DEFAULT_ARTIFACTS = Path("artifacts/v4/phase7")
DEFAULT_OUT = DEFAULT_ARTIFACTS / "phase7_gate_report.json"
REQUIREMENTS_COVERED = ["BASE-01", "BASE-02", "BASE-03", "TAG-01", "TAG-02", "TAG-03", "TAG-04"]
GATE_ARTIFACTS = {
    "protocol_fixture": "protocol_fixture.json",
    "environment": "environment.json",
    "baseline_readonly": "baseline_readonly.json",
    "tokenizer_audit": "tokenizer_audit.json",
}


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _assert_not_frozen_output(path: Path) -> None:
    if _is_relative_to(path, FROZEN_BASELINE_ROOT):
        raise ValueError(f"refusing to write Phase 7 artifact under frozen v1 baseline root: {path}")


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"missing artifact: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"malformed JSON {path}: expected object"
    return payload, None


def _gate_payload(name: str, payload: dict[str, Any] | None, reason: str | None) -> dict[str, Any]:
    return {"ok": reason is None and payload is not None and payload.get("ok") is True, "reason": reason, "data": payload or {}}


def evaluate_gates(artifacts: str | Path = DEFAULT_ARTIFACTS) -> dict[str, Any]:
    artifacts = Path(artifacts)
    gates: dict[str, Any] = {}
    fatal_failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    covered: set[str] = set()

    for gate_name, file_name in GATE_ARTIFACTS.items():
        payload, err = _load_json(artifacts / file_name)
        reason = err
        if payload is not None:
            covered.update(str(requirement) for requirement in payload.get("requirements_covered", []))
            for warning in payload.get("warnings", []):
                warnings.append({"gate": gate_name, "warning": str(warning)})
            if payload.get("ok") is not True:
                reason = f"{gate_name} ok is not true"
                sub_failures = payload.get("fatal_failures") or []
                if sub_failures:
                    for failure in sub_failures:
                        if isinstance(failure, dict):
                            fatal_failures.append({"gate": str(failure.get("gate", gate_name)), "reason": str(failure.get("reason", reason))})
                        else:
                            fatal_failures.append({"gate": gate_name, "reason": str(failure)})
                else:
                    fatal_failures.append({"gate": gate_name, "reason": reason})
        if err:
            fatal_failures.append({"gate": gate_name, "reason": err})
        gates[gate_name] = _gate_payload(gate_name, payload, reason)

    missing = [requirement for requirement in REQUIREMENTS_COVERED if requirement not in covered]
    if missing:
        fatal_failures.append({"gate": "requirements_covered", "reason": f"missing requirements: {', '.join(missing)}"})

    ok = not fatal_failures
    return {
        "ok": ok,
        "fatal_failures": fatal_failures,
        "warnings": warnings,
        "gates": gates,
        "requirements_covered": REQUIREMENTS_COVERED,
        "next_phase_allowed": ok,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate v4 Phase 7 gate report")
    parser.add_argument("--artifacts", default=str(DEFAULT_ARTIFACTS))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = evaluate_gates(args.artifacts)
    out = Path(args.out)
    _assert_not_frozen_output(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
