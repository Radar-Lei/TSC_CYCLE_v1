"""Content-addressed hashing for sample IDs and prompt cache keys."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    """Stable JSON encoding: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sample_id(input_obj: Any) -> str:
    """Sample ID = sha256 of the canonical input JSON. Stable across runs."""
    return sha256_hex(canonical_json(input_obj))


def prompt_hash(prompt: str, model: str, effort: str) -> str:
    """Cache key for teacher response. Includes model + effort so we can
    invalidate when either changes."""
    payload = canonical_json({"prompt": prompt, "model": model, "effort": effort})
    return sha256_hex(payload)
