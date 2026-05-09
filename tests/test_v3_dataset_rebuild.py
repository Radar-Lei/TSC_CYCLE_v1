from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _dataset_contract():
    from tsc_cycle.v3_gates.dataset_rebuild_v3 import (  # noqa: PLC0415
        DEFAULT_MAX_SEQ_LENGTH,
        DEFAULT_SEED,
        DatasetRebuildConfig,
        build_phase3_dataset,
        build_split_plan,
        tokenize_record,
    )

    return {
        "DEFAULT_MAX_SEQ_LENGTH": DEFAULT_MAX_SEQ_LENGTH,
        "DEFAULT_SEED": DEFAULT_SEED,
        "DatasetRebuildConfig": DatasetRebuildConfig,
        "build_phase3_dataset": build_phase3_dataset,
        "build_split_plan": build_split_plan,
        "tokenize_record": tokenize_record,
    }


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
    return path


def _sample(
    sample_id: str,
    *,
    lineage: str,
    split_hint: str = "same_dist",
    reasoning: str = "Allocate green time inside every phase bound.",
    solution: dict[str, int] | None = None,
) -> dict[str, Any]:
    phase_ids = [1, 2, 3]
    if solution is None:
        solution = {str(phase_id): 25 + phase_id for phase_id in phase_ids}
    return {
        "sample_id": sample_id,
        "lineage": lineage,
        "source": split_hint,
        "split_hint": split_hint,
        "input": {
            "sample_id": sample_id,
            "lineage": lineage,
            "source": split_hint,
            "split_hint": split_hint,
            "prediction": {
                "as_of": "2026-05-09 00:00:00",
                "phase_waits": [
                    {
                        "phase_id": phase_id,
                        "pred_wait": float((int(sample_id[-4:], 16) + phase_id) % 50),
                        "pred_saturation": 0.10 + phase_id / 100,
                        "min_green": 10,
                        "max_green": 90,
                        "capacity": 40 + phase_id,
                    }
                    for phase_id in phase_ids
                ],
            },
        },
        "result": {
            "success": True,
            "reasoning": reasoning,
            "solution": solution,
        },
    }


def _synthetic_phase3_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx in range(3000):
        split_hint = "ood" if idx < 300 else "same_dist"
        rows.append(_sample(f"v1-{idx:04d}", lineage="v1.0", split_hint=split_hint))
    for idx in range(6501):
        if idx < 1906:
            split_hint = "ood"
        elif idx < 4251:
            split_hint = "same_dist"
        else:
            split_hint = "targeted"
        rows.append(_sample(f"v3-{idx:04d}", lineage="v3.0", split_hint=split_hint))
    assert len(rows) == 9501
    return rows


def _config(tmp_path: Path, merged_path: Path, *, max_seq_length: int | None = None):
    contract = _dataset_contract()
    DatasetRebuildConfig = contract["DatasetRebuildConfig"]
    if max_seq_length is None:
        max_seq_length = contract["DEFAULT_MAX_SEQ_LENGTH"]
    return DatasetRebuildConfig(
        merged_input=merged_path,
        split_dir=tmp_path / "data" / "splits" / "v3",
        tokenized_dir=tmp_path / "data" / "tokenized" / "v3",
        seed=contract["DEFAULT_SEED"],
        max_seq_length=max_seq_length,
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_split_exact_sizes_and_v1_ood_alignment(tmp_path: Path) -> None:
    contract = _dataset_contract()
    merged = _write_jsonl(tmp_path / "labeled_merged.jsonl", _synthetic_phase3_rows())
    config = _config(tmp_path, merged)

    first = contract["build_split_plan"](config)
    second = contract["build_split_plan"](config)

    assert first["ok"] is True
    assert first["split_sizes"] == {"train": 7601, "val": 950, "ood_val": 950}
    assert second["split_sizes"] == first["split_sizes"]
    assert second["split_ids"] == first["split_ids"]
    assert first["seed"] == 42

    train_ids = set(first["split_ids"]["train"])
    val_ids = set(first["split_ids"]["val"])
    ood_val_ids = set(first["split_ids"]["ood_val"])
    assert train_ids.isdisjoint(val_ids)
    assert train_ids.isdisjoint(ood_val_ids)
    assert val_ids.isdisjoint(ood_val_ids)

    v1_ood = {f"v1-{idx:04d}" for idx in range(300)}
    new_ood = {sample_id for sample_id in ood_val_ids if sample_id.startswith("v3-")}
    assert v1_ood <= ood_val_ids
    assert len(new_ood) == 650
    assert first["v1_ood_alignment"]["all_v1_ood_in_ood_val"] is True
    assert first["v1_ood_alignment"]["v1_ood_count"] == 300
    assert first["v1_ood_alignment"]["new_ood_count"] == 650

    duplicate_rows = _synthetic_phase3_rows()
    duplicate_rows[-1]["sample_id"] = duplicate_rows[0]["sample_id"]
    duplicate_rows[-1]["input"]["sample_id"] = duplicate_rows[0]["sample_id"]
    duplicate_path = _write_jsonl(tmp_path / "duplicate_labeled_merged.jsonl", duplicate_rows)
    duplicate_config = _config(tmp_path / "duplicate", duplicate_path)
    duplicate_report = contract["build_split_plan"](duplicate_config)

    assert duplicate_report["ok"] is False
    assert duplicate_report["gates"]["unique_sample_ids"]["ok"] is False
    assert not (duplicate_config.split_dir / "train.index.jsonl").exists()
    assert not (duplicate_config.split_dir / "val.index.jsonl").exists()
    assert not (duplicate_config.split_dir / "ood_val.index.jsonl").exists()


def test_split_indices_persist_hashes_and_manifest(tmp_path: Path) -> None:
    contract = _dataset_contract()
    merged = _write_jsonl(tmp_path / "labeled_merged.jsonl", _synthetic_phase3_rows())
    config = _config(tmp_path, merged)

    report = contract["build_split_plan"](config)

    assert report["ok"] is True
    assert report["input_sha256"] == _sha(merged)
    for split_name, expected_count in {"train": 7601, "val": 950, "ood_val": 950}.items():
        index_path = config.split_dir / f"{split_name}.index.jsonl"
        assert index_path.exists()
        rows = _read_jsonl(index_path)
        assert len(rows) == expected_count
        assert all(row["split"] == split_name for row in rows)
        for row in rows[:25]:
            assert row["sample_id"]
            assert row["lineage"] in {"v1.0", "v3.0"}
            assert len(row["record_hash"]) == 64
            assert len(row["prompt_hash"]) == 64
            assert len(row["assistant_hash"]) == 64
            assert row["seed"] == 42

    manifest = json.loads((config.split_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["ok"] is True
    assert manifest["seed"] == 42
    assert manifest["input_sha256"] == _sha(merged)
    assert manifest["split_sizes"] == {"train": 7601, "val": 950, "ood_val": 950}
    assert manifest["requirements_covered"] == ["DATA-01", "DATA-04"]

    alignment = json.loads((config.split_dir / "v1_ood_alignment.json").read_text(encoding="utf-8"))
    assert alignment["all_v1_ood_in_ood_val"] is True
    assert alignment["v1_ood_count"] == 300
    assert alignment["new_ood_count"] == 650
    assert len(alignment["v1_ood_sample_ids_sha256"]) == 64
