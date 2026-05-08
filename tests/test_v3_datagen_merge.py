from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path


def build_phase2_report(**kwargs):
    module = importlib.import_module("tsc_cycle.v3_gates.phase2_datagen_report")
    return getattr(module, "build_phase2_report")(**kwargs)


def _sample(sample_id: str, *, source: str = "same_dist", min_green: int = 20, max_green: int = 60) -> dict:
    return {
        "sample_id": sample_id,
        "source": source,
        "input": {
            "sample_id": sample_id,
            "source": source,
            "prediction": {
                "as_of": f"2026-05-03 00:00:{int(sample_id[-2:], 16) % 60:02d}",
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
            },
        },
        "result": {"success": True, "solution": {"1": min_green + 5, "2": min_green + 10}},
    }


def _row(prefix: str, index: int, *, source: str = "same_dist", **kwargs) -> dict:
    return _sample(f"{prefix}{index:060x}"[-64:], source=source, **kwargs)


def _rows(prefix: str, count: int, *, source: str, offset: int = 0) -> list[dict]:
    return [_row(prefix, offset + i, source=source) for i in range(count)]


def _write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_paths(
    tmp_path: Path,
    *,
    new_rows: list[dict] | None = None,
    rejected_rows: list[dict] | None = None,
    manifest_counts: dict[str, int] | None = None,
) -> dict[str, Path]:
    old_rows = [_row("a", i) for i in range(3000)]
    if new_rows is None:
        new_rows = [
            *_rows("b", 4250, source="same_dist"),
            *_rows("c", 1250, source="ood"),
            *_rows("d", 500, source="targeted"),
        ]
    if rejected_rows is None:
        rejected_rows = [
            *_rows("e", 1000, source="same_dist"),
            *_rows("f", 250, source="ood"),
            *_rows("0", 250, source="targeted"),
        ]
    if manifest_counts is None:
        manifest_counts = {"same_dist": 5250, "ood": 1500, "targeted": 750}
    old_labels = _write_jsonl(tmp_path / "old_labeled.jsonl", old_rows)
    new_labels = _write_jsonl(tmp_path / "labeled_new.jsonl", new_rows)
    rejects = _write_jsonl(tmp_path / "rejected_new.jsonl", rejected_rows)
    manifest = tmp_path / "datagen_manifest.json"
    manifest.write_text(
        json.dumps({"phase": "02", "sources": ["same_dist", "ood", "targeted"], "counts_written": manifest_counts}),
        encoding="utf-8",
    )
    return {
        "old_labeled_path": old_labels,
        "new_labeled_path": new_labels,
        "rejected_path": rejects,
        "manifest_path": manifest,
        "merged_out_path": tmp_path / "labeled_merged.jsonl",
        "report_out_path": tmp_path / "merge_report.json",
    }


def test_merged_valid_count_gate(tmp_path: Path):
    paths = _build_paths(tmp_path)
    old_sha = _sha(paths["old_labeled_path"])

    report = build_phase2_report(
        **paths,
        old_sha_before=old_sha,
        old_sha_after=old_sha,
    )

    assert report["old_sha_before"] == old_sha
    assert report["old_sha_after"] == old_sha
    assert report["old_count"] == 3000
    assert report["new_valid"] == 6000
    assert report["merged_valid"] == 9000
    assert report["old_new_overlap"] == 0
    assert report["all_new_lint_ok"] is True
    assert report["ok"] is True
    assert report["requirements_covered"] == [
        "DATAGEN-01",
        "DATAGEN-02",
        "DATAGEN-03",
        "DATAGEN-04",
        "DATAGEN-05",
        "DATAGEN-06",
        "DATAGEN-07",
    ]
    assert paths["merged_out_path"].exists()
    assert paths["report_out_path"].exists()


def test_v1_labeled_sha_unchanged(tmp_path: Path):
    paths = _build_paths(tmp_path)
    old_sha_before = _sha(paths["old_labeled_path"])
    paths["old_labeled_path"].write_text(paths["old_labeled_path"].read_text(encoding="utf-8") + "\n", encoding="utf-8")
    old_sha_after = _sha(paths["old_labeled_path"])

    report = build_phase2_report(
        **paths,
        old_sha_before=old_sha_before,
        old_sha_after=old_sha_after,
    )

    assert report["old_sha_before"] == old_sha_before
    assert report["old_sha_after"] == old_sha_after
    assert report["ok"] is False


def test_new_lint_violation_fails_gate(tmp_path: Path):
    invalid = _row("b", 0, min_green=20, max_green=60)
    invalid["result"]["solution"] = {"1": 10, "2": 30}
    new_rows = [invalid] + [
        *_rows("b", 4249, source="same_dist", offset=1),
        *_rows("c", 1250, source="ood"),
        *_rows("d", 500, source="targeted"),
    ]
    rejected_rows = [
        *_rows("e", 1000, source="same_dist"),
        *_rows("f", 250, source="ood"),
        *_rows("0", 250, source="targeted"),
    ]
    paths = _build_paths(tmp_path, new_rows=new_rows, rejected_rows=rejected_rows)
    old_sha = _sha(paths["old_labeled_path"])

    report = build_phase2_report(
        **paths,
        old_sha_before=old_sha,
        old_sha_after=old_sha,
    )

    assert report["new_valid"] == 5999
    assert report["merged_valid"] == 8999
    assert report["all_new_lint_ok"] is False
    assert report["ok"] is False


def test_source_attempted_coverage_gate_blocks_partial_targeted_reservoir(tmp_path: Path):
    new_rows = [
        *_rows("b", 5000, source="same_dist"),
        *_rows("c", 1500, source="ood"),
        *_rows("d", 500, source="targeted"),
    ]
    paths = _build_paths(tmp_path, new_rows=new_rows, rejected_rows=[])
    old_sha = _sha(paths["old_labeled_path"])

    report = build_phase2_report(
        **paths,
        old_sha_before=old_sha,
        old_sha_after=old_sha,
    )

    assert report["new_valid"] == 7000
    assert report["source_attempted_counts"]["targeted"] == 500
    assert report["gates"]["source_attempted_coverage"]["ok"] is False
    assert report["ok"] is False
    assert not paths["merged_out_path"].exists()


def test_source_reservoir_coverage_gate_blocks_bad_manifest(tmp_path: Path):
    paths = _build_paths(tmp_path, manifest_counts={"same_dist": 5250, "ood": 1500, "targeted": 250})
    old_sha = _sha(paths["old_labeled_path"])

    report = build_phase2_report(
        **paths,
        old_sha_before=old_sha,
        old_sha_after=old_sha,
    )

    assert report["manifest_source_counts"]["targeted"] == 250
    assert report["gates"]["source_reservoir_coverage"]["ok"] is False
    assert report["ok"] is False
    assert not paths["merged_out_path"].exists()


def test_merge_gate_does_not_write_production_labeled_jsonl(tmp_path: Path):
    paths = _build_paths(tmp_path)
    before = Path("data/labeled.jsonl").read_bytes() if Path("data/labeled.jsonl").exists() else b""
    old_sha = _sha(paths["old_labeled_path"])

    build_phase2_report(
        **paths,
        old_sha_before=old_sha,
        old_sha_after=old_sha,
    )

    after = Path("data/labeled.jsonl").read_bytes() if Path("data/labeled.jsonl").exists() else b""
    assert after == before
