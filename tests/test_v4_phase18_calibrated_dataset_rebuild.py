from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
FROZEN_V1_ROOT = PROJECT_ROOT / "runs" / "20260507T032419Z"


def _contract():
    from tsc_cycle.v4_gates.calibrated_dataset_rebuild import (  # noqa: PLC0415
        Phase18DatasetConfig,
        build_calibrated_dataset,
        build_parser,
        reject_unsafe_phase18_output_path,
    )

    return {
        "Phase18DatasetConfig": Phase18DatasetConfig,
        "build_calibrated_dataset": build_calibrated_dataset,
        "build_parser": build_parser,
        "reject_unsafe_phase18_output_path": reject_unsafe_phase18_output_path,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sample(
    sample_id: str,
    *,
    split: str,
    sat: float,
    final: int,
    min_green: int = 10,
    max_green: int = 90,
    source: str = "same_dist",
    lineage: str = "v3.0",
) -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "lineage": lineage,
        "source": source,
        "split": split,
        "split_hint": source,
        "input": {
            "sample_id": sample_id,
            "lineage": lineage,
            "source": source,
            "split": split,
            "split_hint": source,
            "prediction": {
                "as_of": "2026-05-18 00:00:00",
                "phase_waits": [
                    {
                        "phase_id": 1,
                        "pred_wait": 3.0,
                        "pred_saturation": sat,
                        "min_green": min_green,
                        "max_green": max_green,
                        "capacity": 40,
                    },
                    {
                        "phase_id": 2,
                        "pred_wait": 4.0,
                        "pred_saturation": 0.30,
                        "min_green": 10,
                        "max_green": 90,
                        "capacity": 40,
                    },
                ],
            },
        },
        "result": {
            "success": True,
            "reasoning": f"Reasoning for {sample_id}.",
            "solution": {"1": final, "2": 30},
        },
    }


def _fixture_paths(tmp_path: Path) -> tuple[Path, Path, list[dict[str, Any]]]:
    rows = [
        _sample("reject-low-max", split="train", sat=0.10, final=90, source="same_dist"),
        _sample("keep-low-not-max", split="train", sat=0.10, final=30, source="same_dist"),
        _sample("keep-saturated-max", split="val", sat=1.00, final=90, source="same_dist"),
        _sample("keep-forced-trivial", split="ood_val", sat=0.05, final=40, min_green=40, max_green=40, source="ood", lineage="v1.0"),
        _sample("reject-hard-invalid", split="ood_val", sat=0.80, final=100, source="ood", lineage="v1.0"),
        _sample("reject-float-label", split="val", sat=0.30, final=30.9, source="same_dist"),
    ]
    rows[3].pop("lineage")
    rows[3]["input"].pop("lineage")
    dataset_path = _write_jsonl(tmp_path / "data" / "v4" / "phase8" / "labeled_merged.jsonl", rows)
    split_dir = tmp_path / "data" / "v4" / "phase8" / "splits"
    for split in ("train", "val", "ood_val"):
        split_rows = []
        for raw_index, row in enumerate(rows):
            if split == row["split"]:
                source_origin = "v1_valid" if row["sample_id"] == "keep-forced-trivial" else "fixture"
                split_rows.append({"sample_id": row["sample_id"], "split": split, "source": row["source"], "source_origin": source_origin, "raw_index": raw_index})
        _write_jsonl(split_dir / f"{split}.index.jsonl", split_rows)
    return dataset_path, split_dir, rows


def _config(tmp_path: Path, dataset_path: Path, split_dir: Path):
    Phase18DatasetConfig = _contract()["Phase18DatasetConfig"]
    return Phase18DatasetConfig(
        source_dataset=dataset_path,
        source_split_dir=split_dir,
        output_dataset=tmp_path / "data" / "v4_2" / "phase18" / "labeled_calibrated.jsonl",
        output_split_dir=tmp_path / "data" / "v4_2" / "phase18" / "splits",
        artifacts_dir=tmp_path / "artifacts" / "v4_2" / "phase18",
        seed=42,
    )


def test_filter_mode_removes_unsaturated_max_green_violations(tmp_path: Path) -> None:
    dataset_path, split_dir, _rows = _fixture_paths(tmp_path)
    report = _contract()["build_calibrated_dataset"](_config(tmp_path, dataset_path, split_dir))

    assert report["ok"] is True
    assert report["requirements_covered"] == ["DATA-01", "DATA-02"]
    retained_rows = _read_jsonl(tmp_path / "data" / "v4_2" / "phase18" / "labeled_calibrated.jsonl")
    retained_ids = {row["sample_id"] for row in retained_rows}
    assert "reject-low-max" not in retained_ids
    assert "reject-hard-invalid" not in retained_ids
    assert "reject-float-label" not in retained_ids
    assert {"keep-low-not-max", "keep-saturated-max", "keep-forced-trivial"} <= retained_ids
    assert report["counts"]["rejected_rows"] == 3
    assert report["counts"]["relabelled_rows"] == 0
    assert any(item["sample_id"] == "reject-low-max" and item["reason"] == "saturation_policy_violation" for item in report["representative_rejections"])


def test_retained_rows_preserve_hard_constraints_and_protocol(tmp_path: Path) -> None:
    from tsc_cycle.constraint_lint import validate  # noqa: PLC0415
    from tsc_cycle.prompt_builder import build_full_assistant, build_user_prompt  # noqa: PLC0415

    dataset_path, split_dir, _rows = _fixture_paths(tmp_path)
    _contract()["build_calibrated_dataset"](_config(tmp_path, dataset_path, split_dir))

    for row in _read_jsonl(tmp_path / "data" / "v4_2" / "phase18" / "labeled_calibrated.jsonl"):
        assert validate(row["input"], row["result"]["solution"]).ok is True
        prompt = build_user_prompt(row["input"])
        assistant = build_full_assistant(row["result"]["reasoning"], row["result"]["solution"])
        assert "<start_working_out>" in prompt
        assert "</end_working_out>" in prompt
        assert assistant.startswith("<start_working_out>")
        assert "</end_working_out><SOLUTION>" in assistant
        assert assistant.endswith("</SOLUTION>")


def test_split_indexes_preserve_retained_membership_and_hashes(tmp_path: Path) -> None:
    dataset_path, split_dir, _rows = _fixture_paths(tmp_path)
    report = _contract()["build_calibrated_dataset"](_config(tmp_path, dataset_path, split_dir))

    train = _read_jsonl(tmp_path / "data" / "v4_2" / "phase18" / "splits" / "train.index.jsonl")
    val = _read_jsonl(tmp_path / "data" / "v4_2" / "phase18" / "splits" / "val.index.jsonl")
    ood = _read_jsonl(tmp_path / "data" / "v4_2" / "phase18" / "splits" / "ood_val.index.jsonl")
    assert [row["sample_id"] for row in train] == ["keep-low-not-max"]
    assert [row["sample_id"] for row in val] == ["keep-saturated-max"]
    assert [row["sample_id"] for row in ood] == ["keep-forced-trivial"]
    for row in [*train, *val, *ood]:
        assert {"record_hash", "input_hash", "solution_hash", "prompt_hash", "assistant_hash", "source", "source_origin"} <= set(row)
    assert ood[0]["source_origin"] == "v1_valid"
    assert ood[0]["lineage"] == "v1.0"
    manifest = _read_json(tmp_path / "data" / "v4_2" / "phase18" / "splits" / "manifest.json")
    assert manifest["split_counts"] == {"train": 1, "val": 1, "ood_val": 1}
    assert set(manifest["split_ids_sha256"]) == {"train", "val", "ood_val"}
    assert report["splits"]["split_counts"] == manifest["split_counts"]


def test_reconstruction_report_contains_counts_hashes_and_policy_pass_rates(tmp_path: Path) -> None:
    dataset_path, split_dir, _rows = _fixture_paths(tmp_path)
    report = _contract()["build_calibrated_dataset"](_config(tmp_path, dataset_path, split_dir))
    saved = _read_json(tmp_path / "artifacts" / "v4_2" / "phase18" / "reconstruction_report.json")

    assert saved == report
    assert report["ok"] is True
    assert report["next_phase_allowed"] is True
    assert report["counts"] == {
        "source_rows": 6,
        "retained_rows": 3,
        "rejected_rows": 3,
        "relabelled_rows": 0,
        "policy_rejected_rows": 1,
        "hard_constraint_rejected_rows": 2,
        "malformed_rejected_rows": 0,
    }
    assert report["policy"]["post_gate"]["ok"] is True
    assert report["policy"]["post_gate"]["gates"]["data_malformed_row_rate"]["denominator"] == 3
    assert report["policy"]["post_gate"]["gates"]["data_missing_output_rate"]["denominator"] == 3
    assert report["hard_constraints"]["retained_pass_rate"] == 1.0
    assert len(report["dataset_hashes"]["calibrated_jsonl_sha256"]) == 64
    assert len(report["dataset_hashes"]["sample_hash_digest"]) == 64
    assert {"merged_jsonl", "reconstruction_report", "split_manifest"} <= set(report["paths"])
    assert report["representative_rejections"]


def test_cli_defaults_and_path_guards_keep_phase18_outputs_isolated(tmp_path: Path) -> None:
    parser = _contract()["build_parser"]()
    args = parser.parse_args([])

    assert args.source_dataset == Path("data/v4/phase8/labeled_merged.jsonl")
    assert args.source_split_dir == Path("data/v4/phase8/splits")
    assert args.output_dataset == Path("data/v4_2/phase18/labeled_calibrated.jsonl")
    assert args.output_split_dir == Path("data/v4_2/phase18/splits")
    assert args.artifacts_dir == Path("artifacts/v4_2/phase18")
    assert args.mode == "filter"

    reject = _contract()["reject_unsafe_phase18_output_path"]
    safe = tmp_path / "data" / "v4_2" / "phase18" / "ok.jsonl"
    assert reject(safe) == safe.resolve(strict=False)
    for unsafe in (
        FROZEN_V1_ROOT / "bad.json",
        PROJECT_ROOT,
        PROJECT_ROOT / "data" / "v4" / "phase8" / "labeled_merged.jsonl",
        PROJECT_ROOT / "artifacts" / "v4" / "phase8" / "rebuild_report.json",
    ):
        try:
            reject(unsafe)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe Phase 18 path accepted: {unsafe}")
