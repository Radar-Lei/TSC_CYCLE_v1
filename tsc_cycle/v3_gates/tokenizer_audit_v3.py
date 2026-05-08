"""Qwen3.5 tokenizer audit gate for v3.0 Phase 1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer

from tsc_cycle.student.dataset import dataset_wiring_metadata
from tsc_cycle.tokenizer_check import MIN_CUSTOM_TAG_SUBTOKENS, check_tokenizer

DEFAULT_MODEL = "Qwen/Qwen3.5-9B"
DEFAULT_OUT = "artifacts/v3/phase1/tokenizer_audit.json"


def build_audit_payload(model: str, tokenizer) -> dict[str, Any]:
    """Build tokenizer and dataset wiring evidence for TOK-01/TOK-02/TOK-04."""
    result = check_tokenizer(tokenizer, min_custom_subtokens=3)
    dataset_meta = dataset_wiring_metadata()
    chat_template_used = bool(dataset_meta.get("chat_template_used", True))
    dataset_raw_text_path = str(dataset_meta.get("dataset_raw_text_path", ""))

    ok = bool(result.ok and not chat_template_used and dataset_raw_text_path)
    error = None
    if not result.ok:
        error = "tokenizer_check failed"
    elif chat_template_used:
        error = "dataset wiring indicates chat_template use"
    elif not dataset_raw_text_path:
        error = "dataset raw-text path evidence missing"

    details = result.details
    return {
        "ok": ok,
        "model": model,
        "vocab_size": details.get("vocab_size"),
        "custom_tags": details.get("custom_tags", {}),
        "native_think": details.get("native_think", {}),
        "min_custom_subtokens": details.get("min_custom_subtokens", MIN_CUSTOM_TAG_SUBTOKENS),
        "chat_template_used": chat_template_used,
        "dataset_raw_text_path": dataset_raw_text_path,
        "bad_custom_tags": details.get("bad_custom_tags", []),
        "bad_native_think": details.get("bad_native_think", []),
        "error": error,
    }


def write_audit(payload: dict[str, Any], out: str | Path) -> None:
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit Qwen3.5 tokenizer protocol invariants for v3.0")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    payload = build_audit_payload(args.model, tokenizer)
    write_audit(payload, args.out)

    if not payload["ok"]:
        print(f"tokenizer audit failed: {payload['error']}")
        return 1
    print(f"tokenizer audit OK: wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
