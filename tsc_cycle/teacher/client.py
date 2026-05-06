"""GPT-5.5 high teacher client — Responses API.

Adapted to the codex proxy at http://148.135.118.86:8080:
  - `wire_api = "responses"` — use `client.responses.create(...)` not chat.completions
  - reasoning passed as `reasoning={"effort": "high"}`
  - response payload: `r.output[0].content[0].text`
  - usage: `r.usage.output_tokens_details.reasoning_tokens` (TCH-02 gate)

Behavior preserved from prior version:
  - exponential backoff on transient errors
  - RateLimit honored with Retry-After (does not consume retry budget)
  - content-addressed cache via prompt_hash, atomic rename
  - `require_reasoning_tokens_min` (default 100) drops responses where the model
    silently downcasted to low-effort

Cache: every successful response is written to `raw_responses/{prompt_hash}.json`
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
    response_id: str = ""

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
            "response_id": self.response_id,
        }


@dataclass
class TeacherClient:
    model: str = "gpt-5.5"
    reasoning_effort: str = "high"
    timeout: float = 300.0
    max_retries: int = 3
    base_backoff: float = 2.0
    cache_dir: Path = field(default_factory=lambda: Path("raw_responses"))
    api_key: str | None = None
    base_url: str | None = None
    require_reasoning_tokens_min: int = 100  # TCH-02

    def __post_init__(self) -> None:
        kwargs: dict[str, Any] = {}
        kwargs["api_key"] = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not kwargs["api_key"]:
            raise RuntimeError("OPENAI_API_KEY not set")
        kwargs["base_url"] = self.base_url or os.environ.get("OPENAI_BASE_URL")
        kwargs["timeout"] = self.timeout
        self._client = OpenAI(**{k: v for k, v in kwargs.items() if v is not None})
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

    # ----- API call (Responses API) -----

    def _call_responses(self, prompt: str) -> tuple[str, dict, dict]:
        """Return (output_text, raw_dict, usage_dict)."""
        resp = self._client.responses.create(
            model=self.model,
            input=prompt,
            reasoning={"effort": self.reasoning_effort},
        )
        raw = resp.model_dump()
        # Extract assistant message text
        text = ""
        for o in resp.output:
            if getattr(o, "type", None) == "message":
                for c in (getattr(o, "content", None) or []):
                    if getattr(c, "type", None) == "output_text":
                        text += c.text or ""
        usage = raw.get("usage") or {}
        return text, raw, usage

    def call(self, prompt: str, force: bool = False) -> TeacherResult:
        """One teacher call with retry + cache. Validation is the caller's job."""
        if not force:
            cached = self._load_cache(prompt)
            if cached:
                p = cached["parsed"]
                return TeacherResult(
                    success=True,
                    reasoning=p["reasoning"],
                    solution=p["solution"],
                    raw=cached["raw"],
                    usage=cached["raw"].get("usage"),
                    response_id=cached["raw"].get("id", ""),
                )

        from tsc_cycle.prompt_builder import parse_assistant_output  # local import to avoid cycles

        start = time.time()
        last_err = ""
        attempts = 0
        for attempt in range(self.max_retries):
            attempts = attempt + 1
            try:
                text, raw, usage = self._call_responses(prompt)

                # TCH-02: reasoning_tokens gate
                rsn_toks = (
                    (usage.get("output_tokens_details") or {}).get("reasoning_tokens")
                    if isinstance(usage.get("output_tokens_details"), dict)
                    else 0
                )
                if rsn_toks is not None and rsn_toks < self.require_reasoning_tokens_min:
                    return TeacherResult(
                        success=False,
                        error=f"reasoning_tokens={rsn_toks} < {self.require_reasoning_tokens_min} (silent-downcast)",
                        raw=raw,
                        usage=usage,
                        attempt_count=attempts,
                        elapsed_s=time.time() - start,
                        response_id=raw.get("id", ""),
                    )

                reasoning, solution = parse_assistant_output(text)
                if solution is None:
                    raise ValueError(f"no parseable SOLUTION block in response (text head: {text[:200]!r})")

                parsed = {"reasoning": reasoning, "solution": {str(k): int(v) for k, v in solution.items()}}
                payload = {"parsed": parsed, "raw": raw}
                self._store_cache(prompt, payload)
                return TeacherResult(
                    success=True,
                    reasoning=parsed["reasoning"],
                    solution=parsed["solution"],
                    raw=raw,
                    usage=usage,
                    attempt_count=attempts,
                    elapsed_s=time.time() - start,
                    response_id=raw.get("id", ""),
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
                attempts -= 1  # do not count
                continue
            except (APITimeoutError, APIConnectionError, APIError, BadRequestError) as e:
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
