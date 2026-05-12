from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tsc_cycle.tokenizer_check import check_tokenizer, native_think_token_ids

EXPECTED_MODEL_ID = "Qwen/Qwen3-4B-Thinking-2507"
FROZEN_BASELINE_ROOT = Path("/home/samuel/TSC_CYCLE/runs/20260507T032419Z")
DEFAULT_OUT = Path("artifacts/v4/phase7/tokenizer_audit.json")
REQUIREMENTS_COVERED = ["TAG-04", "TAG-03", "TAG-01"]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _assert_not_frozen_output(path: Path) -> None:
    if _is_relative_to(path, FROZEN_BASELINE_ROOT):
        raise ValueError(f"refusing to write Phase 7 artifact under frozen v1 baseline root: {path}")


def _load_tokenizer(model_id: str):
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(model_id)


def _validate_model_id(model_id: str) -> list[dict[str, str]]:
    if model_id != EXPECTED_MODEL_ID or "Qwen3.5" in model_id or "qwen3.5" in model_id:
        return [{"gate": "model_id", "reason": f"expected {EXPECTED_MODEL_ID}, got {model_id}"}]
    return []


def evaluate_tokenizer_audit(tokenizer=None, model_id: str = EXPECTED_MODEL_ID) -> dict[str, Any]:
    fatal_failures = _validate_model_id(model_id)
    if fatal_failures and tokenizer is None:
        return {
            "ok": False,
            "model_id": model_id,
            "custom_tags": {},
            "native_think": {},
            "native_think_token_ids": [],
            "min_custom_subtokens": 3,
            "bad_custom_tags": [],
            "bad_native_think": [],
            "vocab_size": None,
            "chat_template_used": False,
            "fatal_failures": fatal_failures,
            "warnings": [],
            "requirements_covered": REQUIREMENTS_COVERED,
        }
    if tokenizer is None:
        tokenizer = _load_tokenizer(model_id)

    result = check_tokenizer(tokenizer, min_custom_subtokens=3)
    details = result.details
    if not result.ok:
        for tag in details.get("bad_custom_tags", []):
            fatal_failures.append({"gate": "custom_tag_subtokens", "reason": f"{tag} encodes to fewer than 3 subtokens"})
        for tag in details.get("bad_native_think", []):
            fatal_failures.append({"gate": "native_think_single_token", "reason": f"{tag} does not encode to one token"})

    native_ids = sorted(native_think_token_ids(tokenizer))
    payload = {
        "ok": not fatal_failures,
        "model_id": model_id,
        "custom_tags": details["custom_tags"],
        "native_think": details["native_think"],
        "native_think_token_ids": native_ids,
        "min_custom_subtokens": details["min_custom_subtokens"],
        "bad_custom_tags": details["bad_custom_tags"],
        "bad_native_think": details["bad_native_think"],
        "vocab_size": details["vocab_size"],
        "chat_template_used": False,
        "fatal_failures": fatal_failures,
        "warnings": [],
        "requirements_covered": REQUIREMENTS_COVERED,
    }
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run v4 Phase 7 Qwen3-4B tokenizer audit")
    parser.add_argument("--model-id", default=EXPECTED_MODEL_ID)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = Path(args.out)
    _assert_not_frozen_output(out)
    payload = evaluate_tokenizer_audit(model_id=args.model_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
