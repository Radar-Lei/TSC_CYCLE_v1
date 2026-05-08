from __future__ import annotations

import importlib
import json
from collections import Counter
from pathlib import Path

from tsc_cycle.hashing import sample_id


def build_v3_phase2_reservoir(*args, **kwargs):
    module = importlib.import_module("tsc_cycle.sample_inputs")
    return getattr(module, "build_v3_phase2_reservoir")(*args, **kwargs)


def _old_ids(path: Path) -> set[str]:
    return {
        json.loads(line)["sample_id"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def test_three_source_reservoir_counts(
    mini_phase2_prior: dict,
    mini_old_labeled_jsonl: Path,
    mini_per_sample_eval_jsonl: Path,
):
    reservoir = build_v3_phase2_reservoir(
        prior=mini_phase2_prior,
        old_labeled_path=mini_old_labeled_jsonl,
        per_sample_eval_path=mini_per_sample_eval_jsonl,
        same_dist_count=6,
        ood_count=3,
        targeted_count=2,
        seed=123,
    )

    counts = Counter(row["source"] for row in reservoir)

    assert counts == {"same_dist": 6, "ood": 3, "targeted": 2}
    assert len(reservoir) == 11


def test_new_records_have_stable_ids_sources_and_no_v1_overlap(
    mini_phase2_prior: dict,
    mini_old_labeled_jsonl: Path,
    mini_per_sample_eval_jsonl: Path,
):
    reservoir = build_v3_phase2_reservoir(
        prior=mini_phase2_prior,
        old_labeled_path=mini_old_labeled_jsonl,
        per_sample_eval_path=mini_per_sample_eval_jsonl,
        same_dist_count=6,
        ood_count=3,
        targeted_count=2,
        seed=456,
    )
    old_ids = _old_ids(mini_old_labeled_jsonl)
    new_ids = [row["sample_id"] for row in reservoir]

    assert len(new_ids) == len(set(new_ids))
    assert set(new_ids).isdisjoint(old_ids)
    for row in reservoir:
        assert len(row["sample_id"]) == 64
        assert row["sample_id"] == sample_id({"prediction": row["prediction"]})
        assert row["source"] in {"same_dist", "ood", "targeted"}


def test_targeted_seed_provenance_uses_lint_fail_or_mae_gt_10_without_reusing_seed_id(
    mini_phase2_prior: dict,
    mini_old_labeled_jsonl: Path,
    mini_per_sample_eval_jsonl: Path,
):
    # The targeted selector must use seeds where lint_ok=false or mae > 10.0,
    # then perturb them so it never copies a seed sample_id verbatim.
    reservoir = build_v3_phase2_reservoir(
        prior=mini_phase2_prior,
        old_labeled_path=mini_old_labeled_jsonl,
        per_sample_eval_path=mini_per_sample_eval_jsonl,
        same_dist_count=0,
        ood_count=0,
        targeted_count=2,
        seed=789,
    )
    eval_rows = [
        json.loads(line)
        for line in mini_per_sample_eval_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    allowed_seed_ids = {
        row["sample_id"]
        for row in eval_rows
        if row.get("lint_ok") is False or (row.get("mae") or 0.0) > 10.0
    }
    benign_seed_ids = {row["sample_id"] for row in eval_rows} - allowed_seed_ids

    assert {row["source"] for row in reservoir} == {"targeted"}
    assert {row["targeted_seed_id"] for row in reservoir} <= allowed_seed_ids
    assert all(row["targeted_seed_id"] not in benign_seed_ids for row in reservoir)
    assert all(row["sample_id"] != row["targeted_seed_id"] for row in reservoir)
    assert all(row.get("targeted_reason") in {"lint_ok=false", "mae > 10.0"} for row in reservoir)


def test_reservoir_builder_never_writes_production_labeled_jsonl(
    mini_phase2_prior: dict,
    mini_old_labeled_jsonl: Path,
    mini_per_sample_eval_jsonl: Path,
):
    before = Path("data/labeled.jsonl").read_bytes() if Path("data/labeled.jsonl").exists() else b""

    build_v3_phase2_reservoir(
        prior=mini_phase2_prior,
        old_labeled_path=mini_old_labeled_jsonl,
        per_sample_eval_path=mini_per_sample_eval_jsonl,
        same_dist_count=1,
        ood_count=1,
        targeted_count=1,
        seed=42,
    )

    after = Path("data/labeled.jsonl").read_bytes() if Path("data/labeled.jsonl").exists() else b""
    assert after == before
