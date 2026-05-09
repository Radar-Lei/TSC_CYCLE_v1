from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tsc_cycle.prompt_builder import parse_assistant_output

FROZEN_BASELINE_ROOT = Path("/home/samuel/TSC_CYCLE/runs/20260507T032419Z")
DEFAULT_OUT = Path("artifacts/v4/phase7/protocol_fixture.json")
REQUIREMENTS_COVERED = ["TAG-01", "TAG-02", "TAG-03"]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _assert_not_frozen_output(path: Path) -> None:
    if _is_relative_to(path, FROZEN_BASELINE_ROOT):
        raise ValueError(f"refusing to write Phase 7 artifact under frozen v1 baseline root: {path}")


def _accepted(name: str, text: str) -> dict[str, Any]:
    reasoning, solution = parse_assistant_output(text)
    ok = reasoning == "reasoning" and solution == {"1": 60}
    return {"name": name, "ok": ok, "reasoning": reasoning, "solution": solution}


def _rejected(name: str, text: str) -> dict[str, Any]:
    reasoning, solution = parse_assistant_output(text)
    rejected = reasoning == "" and solution is None
    return {"name": name, "rejected": rejected, "reasoning": reasoning, "solution": solution}


def evaluate_protocol_fixtures() -> dict[str, Any]:
    accepted_fixture = _accepted(
        "slash_close_full",
        '<start_working_out>reasoning</end_working_out><SOLUTION>{"1":60}</SOLUTION>',
    )
    rejected_fixtures = [
        _rejected("bare_close", '<start_working_out>reasoning<end_working_out><SOLUTION>{"1":60}</SOLUTION>'),
        _rejected("native_think_open", '<start_working_out>reasoning <think></end_working_out><SOLUTION>{"1":60}</SOLUTION>'),
        _rejected("native_think_close", '<start_working_out>reasoning </think></end_working_out><SOLUTION>{"1":60}</SOLUTION>'),
        _rejected("mixed_close", '<start_working_out>a<end_working_out>b</end_working_out><SOLUTION>{"1":60}</SOLUTION>'),
    ]

    fatal_failures: list[dict[str, str]] = []
    if not accepted_fixture["ok"]:
        fatal_failures.append({"gate": "accepted_fixture", "reason": "slash-close fixture did not parse"})
    for item in rejected_fixtures:
        if not item["rejected"]:
            fatal_failures.append({"gate": item["name"], "reason": "malformed/native fixture was accepted"})

    ok = not fatal_failures
    return {
        "ok": ok,
        "accepted_fixture": accepted_fixture,
        "rejected_fixtures": rejected_fixtures,
        "chat_template_used": False,
        "fatal_failures": fatal_failures,
        "warnings": [],
        "requirements_covered": REQUIREMENTS_COVERED,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run v4 Phase 7 protocol fixture gate")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = Path(args.out)
    _assert_not_frozen_output(out)
    payload = evaluate_protocol_fixtures()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
