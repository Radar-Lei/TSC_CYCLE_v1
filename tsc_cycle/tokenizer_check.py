"""Tokenizer safety assertions for TSC-CYCLE thinking protocol.

The custom SFT protocol uses project-owned text tags such as
``<start_working_out>`` and must not train on model-native ``<think>`` token IDs.
Native IDs are model/tokenizer specific, so v4 gates derive them from the active
Qwen3-4B tokenizer instead of trusting fixed constants.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from tsc_cycle.prompt_builder import (
    TAG_SOLUTION_CLOSE,
    TAG_SOLUTION_OPEN,
    TAG_THINK_CLOSE,
    TAG_THINK_OPEN,
)

CUSTOM_TAGS = (TAG_THINK_OPEN, TAG_THINK_CLOSE, TAG_SOLUTION_OPEN, TAG_SOLUTION_CLOSE)
NATIVE_THINK_TAGS = ("<think>", "</think>")
MIN_CUSTOM_TAG_SUBTOKENS = 3


@dataclass
class CheckResult:
    ok: bool
    details: dict


def _encode_no_special(tokenizer, text: str) -> list[int]:
    """Encode text with special-token injection disabled."""
    return list(tokenizer.encode(text, add_special_tokens=False))


def lookup_native_think_ids(tokenizer) -> dict[str, list[int]]:
    """Return tokenizer-derived encodings for native thinking tags."""
    return {tag: _encode_no_special(tokenizer, tag) for tag in NATIVE_THINK_TAGS}


def native_think_token_ids(tokenizer) -> set[int]:
    """Return native think IDs only for tags that encode as a single token."""
    ids: set[int] = set()
    for encoded in lookup_native_think_ids(tokenizer).values():
        if len(encoded) == 1:
            ids.add(encoded[0])
    return ids


def check_tokenizer(tokenizer, min_custom_subtokens: int = MIN_CUSTOM_TAG_SUBTOKENS) -> CheckResult:
    """Run tokenizer invariants for custom tags and native think tokens."""
    details: dict = {
        "custom_tags": {},
        "native_think": {},
        "vocab_size": len(tokenizer),
        "min_custom_subtokens": min_custom_subtokens,
        "bad_custom_tags": [],
        "bad_native_think": [],
    }

    bad_custom: list[str] = []
    for tag in CUSTOM_TAGS:
        ids = _encode_no_special(tokenizer, tag)
        details["custom_tags"][tag] = ids
        if len(ids) < min_custom_subtokens:
            bad_custom.append(tag)

    native = lookup_native_think_ids(tokenizer)
    details["native_think"] = native
    bad_native = [tag for tag, ids in native.items() if len(ids) != 1]

    details["bad_custom_tags"] = bad_custom
    details["bad_native_think"] = bad_native
    return CheckResult(ok=not bad_custom and not bad_native, details=details)


def assert_no_native_think_in_ids(token_ids: Iterable[int], native_ids: set[int] | frozenset[int] | None = None) -> None:
    """Raise AssertionError if any caller-supplied native think token ID appears.

    ``native_ids`` is intentionally required. Falling back to Qwen3-4B v1.0
    constants would make Qwen3.5 gates look safe while checking the wrong IDs.
    """
    if native_ids is None:
        raise ValueError("native_ids must be provided from native_think_token_ids(tokenizer)")

    found = set(token_ids) & set(native_ids)
    if found:
        bad = min(found)
        raise AssertionError(f"native think token id {bad} present in token_ids")
