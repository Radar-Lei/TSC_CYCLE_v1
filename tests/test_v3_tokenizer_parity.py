from __future__ import annotations

import json
from pathlib import Path

import pytest

from tsc_cycle.v3_gates.tokenizer_parity_v3 import (
    build_prompt_fixture,
    first_diff,
    parse_llama_tokenize_ids,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")


def _input(sample_id: int, min_green: int = 15, max_green: int = 45) -> dict:
    return {
        "sample_id": f"sample-{sample_id:03d}",
        "input": {
            "prediction": {
                "as_of": f"2026-05-08 00:{sample_id % 60:02d}:00",
                "phase_waits": [
                    {
                        "phase_id": 1,
                        "pred_wait": float(sample_id),
                        "pred_saturation": 0.25,
                        "min_green": min_green,
                        "max_green": max_green,
                        "capacity": 48,
                    }
                ],
            }
        },
    }


def test_build_prompt_fixture_is_deterministic_with_seed_42(tmp_path: Path) -> None:
    labeled = tmp_path / "labeled.jsonl"
    _write_jsonl(labeled, [_input(i) for i in range(120)])

    out_a = tmp_path / "a.jsonl"
    out_b = tmp_path / "b.jsonl"

    rows_a = build_prompt_fixture(labeled_path=labeled, out_path=out_a, n=100, seed=42)
    rows_b = build_prompt_fixture(labeled_path=labeled, out_path=out_b, n=100, seed=42)

    assert [row["prompt_id"] for row in rows_a] == [row["prompt_id"] for row in rows_b]
    assert out_a.read_text(encoding="utf-8") == out_b.read_text(encoding="utf-8")
    assert len(rows_a) == 100


def test_build_prompt_fixture_adds_boundary_min_green_and_max_green_prompts(tmp_path: Path) -> None:
    labeled = tmp_path / "labeled.jsonl"
    _write_jsonl(labeled, [_input(i) for i in range(2)])

    rows = build_prompt_fixture(labeled_path=labeled, out_path=tmp_path / "fixture.jsonl", n=10, seed=42)
    boundary_rows = [row for row in rows if row["source"] == "synthetic_boundary"]

    assert boundary_rows
    assert any("min_green" in row["text"] and "max_green" in row["text"] for row in boundary_rows)
    assert any('"min_green": 1' in row["text"] for row in boundary_rows)
    assert any('"max_green": 180' in row["text"] for row in boundary_rows)


def test_parse_llama_tokenize_ids_accepts_representative_output() -> None:
    assert parse_llama_tokenize_ids("[1, 2, 3]\n") == [1, 2, 3]
    assert parse_llama_tokenize_ids("tokens: [151, 260, 42]\n") == [151, 260, 42]
    assert parse_llama_tokenize_ids("1 2 3\n") == [1, 2, 3]


def test_parse_llama_tokenize_ids_fail_closes_when_no_ids_are_parseable() -> None:
    with pytest.raises(ValueError, match="no token ids"):
        parse_llama_tokenize_ids("llama-tokenize produced no ids")


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ([1, 2, 3], [1, 2, 3], None),
        ([1, 2, 3], [1, 9, 3], 1),
        ([1, 2], [1, 2, 3], 2),
        ([1, 2, 3], [1, 2], 2),
    ],
)
def test_first_diff(left: list[int], right: list[int], expected: int | None) -> None:
    assert first_diff(left, right) == expected
