"""Tokenizer assertions for Qwen3-4B-Thinking-2507.

Two invariants:
  1. The four custom tags MUST be split into multiple sub-tokens (i.e. NOT in
     the vocabulary as single added tokens). This is what gives us a clean
     learning signal — the model can't just memorize an ID, it has to learn
     the multi-token sequence.
  2. The native Qwen3 thinking tokens (<think>=151667, </think>=151668) MUST
     remain single tokens in the vocab AND MUST NOT appear in any training
     sample. They are pre-trained with a reasoning persona that conflicts
     with our SFT objective.
"""

from __future__ import annotations

from dataclasses import dataclass

from tsc_cycle.prompt_builder import (
    TAG_SOLUTION_CLOSE,
    TAG_SOLUTION_OPEN,
    TAG_THINK_CLOSE,
    TAG_THINK_OPEN,
)

CUSTOM_TAGS = (TAG_THINK_OPEN, TAG_THINK_CLOSE, TAG_SOLUTION_OPEN, TAG_SOLUTION_CLOSE)
NATIVE_THINK_OPEN_ID = 151667   # <think>
NATIVE_THINK_CLOSE_ID = 151668  # </think>
EXPECTED_VOCAB_SIZE = 151936    # Qwen3-4B-Thinking-2507


@dataclass
class CheckResult:
    ok: bool
    details: dict


def check_tokenizer(tokenizer) -> CheckResult:
    """Run all invariants on a HF tokenizer instance."""
    details: dict = {"custom_tags": {}, "native_think": {}, "vocab_size": None}

    details["vocab_size"] = len(tokenizer)

    # 1. Custom tags must each split into ≥2 sub-tokens with add_special_tokens=False.
    bad_custom: list[str] = []
    for tag in CUSTOM_TAGS:
        ids = tokenizer.encode(tag, add_special_tokens=False)
        details["custom_tags"][tag] = ids
        if len(ids) < 2:
            bad_custom.append(tag)

    # 2. Native <think> / </think> must each be a single token at the known IDs.
    open_ids = tokenizer.encode("<think>", add_special_tokens=False)
    close_ids = tokenizer.encode("</think>", add_special_tokens=False)
    details["native_think"] = {
        "<think>": open_ids,
        "</think>": close_ids,
        "expected_open_id": NATIVE_THINK_OPEN_ID,
        "expected_close_id": NATIVE_THINK_CLOSE_ID,
    }

    bad_native = []
    if open_ids != [NATIVE_THINK_OPEN_ID]:
        bad_native.append(f"<think> = {open_ids} (want [{NATIVE_THINK_OPEN_ID}])")
    if close_ids != [NATIVE_THINK_CLOSE_ID]:
        bad_native.append(f"</think> = {close_ids} (want [{NATIVE_THINK_CLOSE_ID}])")

    ok = not bad_custom and not bad_native
    details["bad_custom_tags"] = bad_custom
    details["bad_native_think"] = bad_native
    return CheckResult(ok=ok, details=details)


def assert_no_native_think_in_ids(token_ids: list[int]) -> None:
    """Raise AssertionError if either native think token id appears."""
    if NATIVE_THINK_OPEN_ID in token_ids:
        raise AssertionError(f"native <think> id {NATIVE_THINK_OPEN_ID} present in token_ids")
    if NATIVE_THINK_CLOSE_ID in token_ids:
        raise AssertionError(f"native </think> id {NATIVE_THINK_CLOSE_ID} present in token_ids")
