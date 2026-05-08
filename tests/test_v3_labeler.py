from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tsc_cycle.hashing import sample_id
from tsc_cycle.prompt_builder import build_user_prompt

SENTINEL_API_KEY = "sk-test-secret-must-not-serialize"


def _labeler_module():
    return importlib.import_module("tsc_cycle.teacher.labeler")


def build_parser():
    return getattr(_labeler_module(), "build_parser")()


def run_labeling(args, *, client_factory):
    return getattr(_labeler_module(), "run_labeling")(args, client_factory=client_factory)


def _sample(as_of: str = "2026-05-02 00:00:00", *, min_green: int = 20, max_green: int = 60) -> dict:
    item = {
        "prediction": {
            "as_of": as_of,
            "phase_waits": [
                {
                    "phase_id": 1,
                    "pred_wait": 3.0,
                    "pred_saturation": 0.10,
                    "min_green": min_green,
                    "max_green": max_green,
                    "capacity": 30,
                },
                {
                    "phase_id": 2,
                    "pred_wait": 4.0,
                    "pred_saturation": 0.20,
                    "min_green": min_green,
                    "max_green": max_green,
                    "capacity": 40,
                },
            ],
        }
    }
    item["sample_id"] = sample_id(item)
    item["source"] = "same_dist"
    return item


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


class FakeResult:
    def __init__(self, *, success: bool = True, solution: dict[str, int] | None = None, error: str = ""):
        self.success = success
        self.solution = solution or {"1": 30, "2": 35}
        self.error = error
        self.reasoning = "fake reasoning"
        self.raw = {"id": "fake-response"}
        self.usage = {"input_tokens": 1, "output_tokens": 2, "output_tokens_details": {"reasoning_tokens": 101}}
        self.attempt_count = 1
        self.elapsed_s = 0.01
        self.response_id = "fake-response"

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


class FakeClient:
    def __init__(self, result: FakeResult | None = None):
        self.result = result or FakeResult()
        self.prompts: list[str] = []

    def call(self, prompt: str):
        assert SENTINEL_API_KEY not in prompt
        self.prompts.append(prompt)
        return self.result


def test_workers_capped_and_effort_high_defaults():
    parser = build_parser()
    args = parser.parse_args([])

    assert args.model == "gpt-5.5"
    assert args.effort == "high"

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["--workers", "11"])
    assert excinfo.value.code != 0  # workers > 10 must be rejected by CLI/config


def test_input_exclude_cache_paths_and_protected_labeled_output_rejected(tmp_path: Path):
    input_path = _write_jsonl(tmp_path / "inputs.jsonl", [_sample()])
    old_labeled = _write_jsonl(tmp_path / "old_labeled.jsonl", [])
    rejected = tmp_path / "rejected_new.jsonl"
    cache_dir = tmp_path / "cache"
    args = build_parser().parse_args(
        [
            "--input-files",
            str(input_path),
            "--exclude-labeled",
            str(old_labeled),
            "--labeled",
            "data/labeled.jsonl",
            "--rejected",
            str(rejected),
            "--cache-dir",
            str(cache_dir),
        ]
    )
    made_clients: list[dict] = []

    def factory(**kwargs):
        made_clients.append(kwargs)
        return FakeClient()

    with pytest.raises((SystemExit, ValueError)):
        run_labeling(args, client_factory=factory)
    assert made_clients == []


def test_resume_skips_done_ids_from_labeled_and_rejected(tmp_path: Path):
    first = _sample("2026-05-02 00:00:00")
    second = _sample("2026-05-02 00:01:00")
    third = _sample("2026-05-02 00:02:00")
    input_path = _write_jsonl(tmp_path / "inputs.jsonl", [first, second, third])
    labeled = _write_jsonl(tmp_path / "labeled_new.jsonl", [{"sample_id": first["sample_id"], "result": {"success": True}}])
    rejected = _write_jsonl(tmp_path / "rejected_new.jsonl", [{"sample_id": second["sample_id"], "reject_reason": "prior_failure"}])
    old_labeled = _write_jsonl(tmp_path / "old_labeled.jsonl", [])
    cache_dir = tmp_path / "cache"
    fake = FakeClient()
    factory_kwargs: list[dict] = []

    def factory(**kwargs):
        factory_kwargs.append(kwargs)
        return fake

    args = build_parser().parse_args(
        [
            "--input-files",
            str(input_path),
            "--exclude-labeled",
            str(old_labeled),
            "--labeled",
            str(labeled),
            "--rejected",
            str(rejected),
            "--cache-dir",
            str(cache_dir),
            "--workers",
            "1",
        ]
    )

    run_labeling(args, client_factory=factory)

    assert len(fake.prompts) == 1
    assert fake.prompts[0] == build_user_prompt(third)
    assert factory_kwargs[0]["model"] == "gpt-5.5"
    assert factory_kwargs[0]["reasoning_effort"] == "high"
    assert Path(factory_kwargs[0]["cache_dir"]) == cache_dir
    assert SENTINEL_API_KEY not in labeled.read_text(encoding="utf-8")
    assert SENTINEL_API_KEY not in rejected.read_text(encoding="utf-8")


def test_lint_failure_dropped_not_retried(tmp_path: Path):
    sample = _sample(min_green=20, max_green=60)
    input_path = _write_jsonl(tmp_path / "inputs.jsonl", [sample])
    old_labeled = _write_jsonl(tmp_path / "old_labeled.jsonl", [])
    labeled = tmp_path / "labeled_new.jsonl"
    rejected = tmp_path / "rejected_new.jsonl"
    fake = FakeClient(FakeResult(solution={"1": 10, "2": 35}))

    args = build_parser().parse_args(
        [
            "--input-files",
            str(input_path),
            "--exclude-labeled",
            str(old_labeled),
            "--labeled",
            str(labeled),
            "--rejected",
            str(rejected),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--workers",
            "1",
        ]
    )

    run_labeling(args, client_factory=lambda **_: fake)

    rejected_rows = [json.loads(line) for line in rejected.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert fake.prompts == [build_user_prompt(sample)]
    assert (not labeled.exists()) or labeled.read_text(encoding="utf-8") == ""
    assert len(rejected_rows) == 1
    assert rejected_rows[0]["sample_id"] == sample["sample_id"]
    assert rejected_rows[0]["reject_reason"] == "constraint_violation"
    assert SENTINEL_API_KEY not in json.dumps(rejected_rows, ensure_ascii=False)
