from __future__ import annotations

import os
from pathlib import Path


V1_RUN = "20260507T032419Z"


def _make_v1_tree(tmp_path: Path) -> Path:
    root = tmp_path / "runs" / V1_RUN
    (root / "gguf").mkdir(parents=True)
    (root / "gguf" / "model.q4_K_M.gguf").write_bytes(b"frozen-baseline")
    (root / "eval" / "gen_cache" / "gguf_q4km").mkdir(parents=True)
    (root / "eval" / "gen_cache" / "gguf_q4km" / "sample.json").write_text("{}\n", encoding="utf-8")
    return root


def _write_bits(path: Path) -> int:
    return path.stat().st_mode & 0o222


def test_sft_08_d11_ensure_v1_frozen_writes_marker_chmod_and_evidence(tmp_path: Path) -> None:
    from tsc_cycle.student.sft_v3 import ensure_v1_frozen  # noqa: PLC0415

    root = _make_v1_tree(tmp_path)
    evidence = ensure_v1_frozen(root)

    frozen = root / "FROZEN.md"
    assert frozen.exists()
    assert V1_RUN in evidence["root"]
    assert evidence["frozen_marker"] == str(frozen)
    assert evidence["pre"]
    assert evidence["post"]
    assert evidence["write_bits_removed"] is True
    assert evidence["ok"] is True
    for path in [root, root / "gguf", root / "gguf" / "model.q4_K_M.gguf"]:
        assert _write_bits(path) == 0


def test_sft_08_d11_ensure_v1_frozen_preserves_existing_artifact_evidence(tmp_path: Path) -> None:
    from tsc_cycle.student.sft_v3 import ensure_v1_frozen  # noqa: PLC0415

    root = _make_v1_tree(tmp_path)
    before_size = (root / "gguf" / "model.q4_K_M.gguf").stat().st_size
    evidence = ensure_v1_frozen(root)
    after_size = (root / "gguf" / "model.q4_K_M.gguf").stat().st_size

    assert before_size == after_size
    assert evidence["pre"]["artifact_count"] == evidence["post"]["artifact_count"]
    assert evidence["pre"]["content_sha256"] == evidence["post"]["content_sha256"]


def test_sft_07_d10_validate_run_root_accepts_only_v3_9b_isolated_roots(tmp_path: Path) -> None:
    from tsc_cycle.student.sft_v3 import validate_run_root  # noqa: PLC0415

    accepted = validate_run_root(tmp_path / "runs" / "v3.0-9B-20260509T000000Z")

    assert accepted.name == "v3.0-9B-20260509T000000Z"


def test_sft_07_d10_validate_run_root_rejects_v1_timestamp_generic_and_shell_paths(tmp_path: Path) -> None:
    from tsc_cycle.student.sft_v3 import validate_run_root  # noqa: PLC0415

    bad_roots = [
        tmp_path / "runs" / V1_RUN,
        tmp_path / "runs" / "20260509T000000Z",
        Path(os.sep) / "tmp" / "outside-v3.0-9B-20260509T000000Z",
        tmp_path / "runs" / "v3.0-9B-20260509T000000Z;rm-rf",
        tmp_path / "runs" / "v3.0-9B-20260509T000000Z$(touch bad)",
    ]

    for bad_root in bad_roots:
        try:
            validate_run_root(bad_root)
        except ValueError:
            pass
        else:  # pragma: no cover - RED contract should fail closed here once implementation exists.
            raise AssertionError(f"unsafe run root accepted: {bad_root}")


def test_d09_d10_wrapper_command_contract_uses_fixed_run_safe_argv() -> None:
    from tsc_cycle.student.sft_v3 import phase4_wrapper_command  # noqa: PLC0415

    argv = phase4_wrapper_command("dry-run", "runs/v3.0-9B-20260509T000000Z")

    # D-09/D-10/T-04-05: wrappers must use fixed argv, not user-provided shell snippets.
    assert argv[:3] == ["scripts/dgx_spark/run_safe.sh", "100G", "--"]
    assert "/home/samuel/TSC_CYCLE/.venv/bin/python" in argv
    assert "tsc_cycle.student.train" in argv
    assert not any(";" in part or "$" in part or "&&" in part for part in argv)
