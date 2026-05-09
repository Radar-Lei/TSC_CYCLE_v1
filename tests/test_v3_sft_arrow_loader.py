from __future__ import annotations

from pathlib import Path


PHASE3_COLUMNS = {
    "sample_id",
    "input_ids",
    "attention_mask",
    "labels",
    "raw_length",
    "truncated",
    "prompt_hash",
    "assistant_hash",
}
MODEL_COLUMNS = ["input_ids", "attention_mask", "labels"]


def _write_tiny_arrow(path: Path) -> None:
    import pyarrow as pa

    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table(
        {
            "sample_id": ["sft-red-1", "sft-red-2"],
            "input_ids": [[101, 102, 103], [201, 202]],
            "attention_mask": [[1, 1, 1], [1, 1]],
            "labels": [[-100, 102, 103], [-100, 202]],
            "raw_length": [3, 2],
            "truncated": [False, False],
            "prompt_hash": ["p" * 64, "q" * 64],
            "assistant_hash": ["a" * 64, "b" * 64],
        }
    )
    with pa.OSFile(str(path), "wb") as sink:
        with pa.ipc.new_file(sink, table.schema) as writer:
            writer.write_table(table)


def test_arrow_loader_keeps_only_model_columns_by_default(tmp_path: Path) -> None:
    from tsc_cycle.student.sft_v3 import MODEL_COLUMNS as CONTRACT_MODEL_COLUMNS, load_arrow_split  # noqa: PLC0415

    arrow_path = tmp_path / "data" / "tokenized" / "v3" / "train.arrow"
    _write_tiny_arrow(arrow_path)

    dataset = load_arrow_split(arrow_path, keep_metadata=False)

    assert CONTRACT_MODEL_COLUMNS == MODEL_COLUMNS
    assert list(dataset.column_names) == MODEL_COLUMNS
    assert len(dataset) == 2
    assert dataset[0]["input_ids"] == [101, 102, 103]
    assert "sample_id" not in dataset.column_names
    assert "prompt_hash" not in dataset.column_names


def test_arrow_loader_can_preserve_phase3_metadata_for_reports(tmp_path: Path) -> None:
    from tsc_cycle.student.sft_v3 import load_arrow_split  # noqa: PLC0415

    arrow_path = tmp_path / "data" / "tokenized" / "v3" / "ood_val.arrow"
    _write_tiny_arrow(arrow_path)

    dataset = load_arrow_split(arrow_path, keep_metadata=True)

    assert set(dataset.column_names) == PHASE3_COLUMNS
    assert dataset[1]["sample_id"] == "sft-red-2"
    assert dataset[1]["assistant_hash"] == "b" * 64


def test_arrow_loader_does_not_require_legacy_parquet_layout(tmp_path: Path) -> None:
    from tsc_cycle.student.sft_v3 import load_arrow_split  # noqa: PLC0415

    arrow_path = tmp_path / "data" / "tokenized" / "v3" / "val.arrow"
    legacy_parquet_path = tmp_path / "data" / "tokenized" / "train" / "data.parquet"
    _write_tiny_arrow(arrow_path)

    dataset = load_arrow_split(arrow_path, keep_metadata=False)

    # T-04-02 / SFT Arrow contract: Phase 4 must not depend on legacy data.parquet paths.
    assert len(dataset) == 2
    assert not legacy_parquet_path.exists()
