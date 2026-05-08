from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import pytest

from tsc_cycle.hashing import sample_id


def _prediction(
    *,
    as_of: str,
    waits: list[tuple[int, float, float, int, int, int]],
    crossing_id: int = 1,
) -> dict:
    return {
        "prediction": {
            "as_of": as_of,
            "phase_waits": [
                {
                    "phase_id": phase_id,
                    "pred_wait": pred_wait,
                    "pred_saturation": pred_saturation,
                    "min_green": min_green,
                    "max_green": max_green,
                    "capacity": capacity,
                }
                for phase_id, pred_wait, pred_saturation, min_green, max_green, capacity in waits
            ],
            "_crossing_id": crossing_id,
        }
    }


def write_jsonl(path: Path, rows: Iterable[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


@pytest.fixture
def mini_phase2_prior() -> dict:
    return {
        "phase_count_distribution": {"2": 3, "3": 2, "4": 1},
        "range_modes_top": [
            {"min_green": 20, "max_green": 60, "count": 4},
            {"min_green": 30, "max_green": 90, "count": 3},
            {"min_green": 15, "max_green": 45, "count": 2},
        ],
        "per_position": {
            "0": {
                "pred_saturation": {"values_all": [0.05, 0.12, 0.25]},
                "pred_wait": {"values_all": [1.0, 3.5, 8.0]},
                "capacity": {"values_all": [30, 40, 60]},
            },
            "1": {
                "pred_saturation": {"values_all": [0.08, 0.18, 0.32]},
                "pred_wait": {"values_all": [2.0, 4.5, 9.0]},
                "capacity": {"values_all": [35, 45, 65]},
            },
            "2": {
                "pred_saturation": {"values_all": [0.10, 0.22]},
                "pred_wait": {"values_all": [5.0, 10.0]},
                "capacity": {"values_all": [50, 70]},
            },
            "3": {
                "pred_saturation": {"values_all": [0.15, 0.35]},
                "pred_wait": {"values_all": [6.0, 12.0]},
                "capacity": {"values_all": [55, 80]},
            },
        },
    }


@pytest.fixture
def mini_old_labeled_jsonl(tmp_path: Path) -> Path:
    baseline_inputs = [
        _prediction(
            as_of="2026-05-01 00:00:00",
            waits=[
                (1, 1.0, 0.05, 20, 60, 40),
                (2, 2.0, 0.10, 20, 60, 40),
            ],
        ),
        _prediction(
            as_of="2026-05-01 00:01:00",
            waits=[
                (1, 5.0, 0.20, 30, 90, 50),
                (2, 6.0, 0.30, 30, 90, 50),
            ],
        ),
    ]
    rows = []
    for item in baseline_inputs:
        rows.append(
            {
                "sample_id": sample_id(item),
                "input": item,
                "result": {"success": True, "solution": {"1": 30, "2": 35}},
            }
        )
    return write_jsonl(tmp_path / "old_labeled.jsonl", rows)


@pytest.fixture
def mini_per_sample_eval_jsonl(tmp_path: Path) -> Path:
    lint_seed = _prediction(
        as_of="2026-05-01 00:02:00",
        waits=[
            (1, 100.0, 0.90, 5, 150, 100),
            (2, 90.0, 0.80, 5, 150, 100),
        ],
        crossing_id=7,
    )
    high_mae_seed = _prediction(
        as_of="2026-05-01 00:03:00",
        waits=[
            (1, 60.0, 0.60, 10, 140, 100),
            (2, 30.0, 0.40, 10, 140, 100),
            (3, 20.0, 0.30, 10, 140, 100),
        ],
        crossing_id=8,
    )
    benign_seed = _prediction(
        as_of="2026-05-01 00:04:00",
        waits=[
            (1, 1.0, 0.05, 20, 60, 40),
            (2, 2.0, 0.10, 20, 60, 40),
        ],
        crossing_id=9,
    )
    rows = [
        {"sample_id": sample_id(lint_seed), "input": lint_seed, "lint_ok": False, "mae": 0.0},
        {"sample_id": sample_id(high_mae_seed), "input": high_mae_seed, "lint_ok": True, "mae": 12.5},
        {"sample_id": sample_id(benign_seed), "input": benign_seed, "lint_ok": True, "mae": 1.0},
    ]
    return write_jsonl(tmp_path / "per_sample_eval.jsonl", rows)
