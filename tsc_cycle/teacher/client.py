"""GPT-5.5 high teacher client.

Adapted from EvoProgTSC's `evoprog/llm/client.py`:
  - Uses `client.chat.completions.create` with `reasoning_effort="high"` (kept for
    compat with that codebase; OpenAI SDK ≥1.50 also accepts the field on Chat
    Completions).
  - Structured-output via JSON Schema strict mode for the teacher's output.
  - On `BadRequestError` from structured-output, falls back to plain Chat with
    explicit format instructions in the prompt.
  - Exponential backoff on `APITimeoutError` / `APIConnectionError` / `APIError`.
  - `RateLimitError` honored with `Retry-After` header (defaults to 60s) and
    NOT counted against the per-request retry budget.

Cache: every successful response is written to `raw_responses/{prompt_hash}.json`
via atomic rename. The labeling pipeline (in `tsc_cycle.teacher.labeler`) is
the one that does concurrency / sample iteration; this module is a thin client.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from tsc_cycle.hashing import prompt_hash, sha256_hex

# JSON Schema for the teacher's structured output. The teacher's response wraps
# this in <SOLUTION>...</SOLUTION>; structured mode lets us short-circuit the
# tag detection in the cleanest case (reduces parse-failure rate).
SOLUTION_SCHEMA = {
    "name": "tsc_cycle_solution",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["reasoning", "solution"],
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "Step-by-step thinking content",
            },
            "solution": {
                "type": "object",
                "description": "Mapping phase_id (string) -> integer green seconds. Keys must be the digit-string phase IDs from the input.",
                "additionalProperties": {"type": "integer"},
            },
        },
    },
}


@dataclass
class TeacherResult:
    success: bool
    reasoning: str = ""
    solution: dict[str, int] | None = None
    raw: dict | None = None
    usage: dict | None = None
    error: str = ""
    attempt_count: int = 0
    elapsed_s: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "reasoning": self.reasoning,
            "solution": self.solution,
            "raw": self.raw,
            "usage": self.usage,
            "error": self.error,
            "attempt_count": self.attempt_count,
            "elapsed_s": self.elapsed_s,
        }


@dataclass
class TeacherClient:
    model: str = "gpt-5.5"
    reasoning_effort: str = "high"
    timeout: float = 300.0
    max_retries: int = 3
    base_backoff: float = 2.0
    cache_dir: Path = field(default_factory=lambda: Path("raw_responses"))
    use_structured: bool = True
    api_key: str | None = None
    base_url: str | None = None
    require_reasoning_tokens_min: int = 100  # TCH-02

    def __post_init__(self) -> None:
        kwargs: dict[str, Any] = {}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ----- cache helpers -----

    def cache_path(self, prompt: str) -> Path:
        ph = prompt_hash(prompt, self.model, self.reasoning_effort)
        return self.cache_dir / f"{ph}.json"

    def _load_cache(self, prompt: str) -> dict | None:
        p = self.cache_path(prompt)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def _store_cache(self, prompt: str, payload: dict) -> None:
        p = self.cache_path(prompt)
        tmp = p.with_suffix(".json.tmp." + sha256_hex(str(time.time()))[:8])
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, p)

    # ----- API call -----

    def _call_structured(self, prompt: str) -> tuple[dict, dict]:
        """Returns (parsed_solution_dict, raw_response_dict)."""
        msgs = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": msgs,
            "timeout": self.timeout,
            "response_format": {"type": "json_schema", "json_schema": SOLUTION_SCHEMA},
        }
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        resp = self._client.chat.completions.create(**kwargs)
        choice = resp.choices[0].message.content or "{}"
        parsed = json.loads(choice)
        raw = resp.model_dump()
        return parsed, raw

    def _call_plain(self, prompt: str) -> tuple[dict, dict]:
        """Fallback when structured output is rejected. Parse <SOLUTION>...</SOLUTION>."""
        msgs = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": msgs,
            "timeout": self.timeout,
        }
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort
        resp = self._client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        # Use prompt_builder's parser
        from tsc_cycle.prompt_builder import parse_assistant_output
        reasoning, solution = parse_assistant_output(text)
        if solution is None:
            raise ValueError("plain-mode: no SOLUTION block found in response")
        parsed = {"reasoning": reasoning, "solution": solution, "_raw_text": text}
        raw = resp.model_dump()
        return parsed, raw

    def call(self, prompt: str, force: bool = False) -> TeacherResult:
        """One teacher call with retry + cache. Validation is the caller's job."""
        if not force:
            cached = self._load_cache(prompt)
            if cached:
                return TeacherResult(
                    success=True,
                    reasoning=cached["parsed"]["reasoning"],
                    solution=cached["parsed"]["solution"],
                    raw=cached["raw"],
                    usage=cached["raw"].get("usage"),
                )

        start = time.time()
        last_err = ""
        attempts = 0
        for attempt in range(self.max_retries):
            attempts = attempt + 1
            try:
                if self.use_structured:
                    try:
                        parsed, raw = self._call_structured(prompt)
                    except BadRequestError as e:
                        last_err = f"structured-rejected:{e!s}"
                        parsed, raw = self._call_plain(prompt)
                else:
                    parsed, raw = self._call_plain(prompt)

                usage = raw.get("usage") or {}
                # TCH-02: assert reasoning_tokens > threshold
                rsn_toks = (
                    usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0)
                    if isinstance(usage.get("completion_tokens_details"), dict)
                    else usage.get("reasoning_tokens", 0)
                )
                if rsn_toks is not None and rsn_toks < self.require_reasoning_tokens_min:
                    return TeacherResult(
                        success=False,
                        error=f"reasoning_tokens={rsn_toks} below {self.require_reasoning_tokens_min} (silent-downcast)",
                        raw=raw,
                        usage=usage,
                        attempt_count=attempts,
                        elapsed_s=time.time() - start,
                    )

                payload = {"parsed": parsed, "raw": raw}
                self._store_cache(prompt, payload)
                return TeacherResult(
                    success=True,
                    reasoning=parsed["reasoning"],
                    solution={str(k): int(v) for k, v in parsed["solution"].items()},
                    raw=raw,
                    usage=usage,
                    attempt_count=attempts,
                    elapsed_s=time.time() - start,
                )

            except RateLimitError as e:
                # Honor Retry-After if available; do NOT count against retry budget
                wait = 60.0
                hdrs = getattr(getattr(e, "response", None), "headers", None) or {}
                if hdrs.get("Retry-After"):
                    try:
                        wait = float(hdrs["Retry-After"])
                    except ValueError:
                        pass
                last_err = f"ratelimit:{e!s}"
                time.sleep(min(wait, 120.0))
                # do not increment effective retry count for ratelimits
                attempts -= 1
                continue
            except (APITimeoutError, APIConnectionError, APIError) as e:
                last_err = f"{type(e).__name__}:{e!s}"
                if attempt + 1 < self.max_retries:
                    time.sleep(self.base_backoff * (2**attempt))
                continue
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                last_err = f"parse:{type(e).__name__}:{e!s}"
                if attempt + 1 < self.max_retries:
                    time.sleep(self.base_backoff * (2**attempt))
                continue

        return TeacherResult(
            success=False,
            error=last_err or "exhausted retries",
            attempt_count=attempts,
            elapsed_s=time.time() - start,
        )
