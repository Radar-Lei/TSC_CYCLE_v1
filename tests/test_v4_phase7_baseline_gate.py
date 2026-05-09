import json
from pathlib import Path

import pytest

from tsc_cycle.v4_gates.phase7_baseline import (
    EXPECTED_MODEL_ID,
    assert_model_id,
    assert_output_not_in_frozen_root,
    evaluate_baseline_gate,
    main,
    snapshot_baseline_root,
)

FROZEN_ROOT = Path("/home/samuel/TSC_CYCLE/runs/20260507T032419Z")


def test_model_lock_accepts_only_qwen3_4b():
    assert assert_model_id(EXPECTED_MODEL_ID) == EXPECTED_MODEL_ID
    with pytest.raises(ValueError):
        assert_model_id("Qwen/Qwen3.5-9B")
    with pytest.raises(ValueError):
        assert_model_id("Qwen/Qwen3.5-9B-Thinking")
    with pytest.raises(ValueError):
        assert_model_id("Qwen/Qwen3-4B")


def test_output_path_guard_rejects_frozen_root():
    with pytest.raises(ValueError):
        assert_output_not_in_frozen_root(FROZEN_ROOT / "x.json")


def test_snapshot_baseline_root_records_q4_artifact_and_cache():
    snapshot = snapshot_baseline_root(FROZEN_ROOT)
    assert snapshot["root"].endswith("runs/20260507T032419Z")
    assert snapshot["exists"] is True
    assert snapshot["file_count"] > 0
    assert snapshot["q4_artifact"]["path"].endswith("gguf/model.q4_K_M.gguf")
    assert snapshot["q4_artifact"]["exists"] is True
    assert snapshot["documented_cache"]["path"].endswith("eval/gen_cache/gguf_q4km")
    assert "discovered_q4_caches" in snapshot


def test_evaluate_baseline_gate_payload_contract(tmp_path):
    env_out = tmp_path / "environment.json"
    baseline_out = tmp_path / "baseline_readonly.json"
    payload = evaluate_baseline_gate(environment_out=env_out, baseline_out=baseline_out)
    assert payload["ok"] is True
    assert payload["environment"]["requirements_covered"] == ["BASE-01", "BASE-02"]
    assert payload["environment"]["model"] == {
        "expected": EXPECTED_MODEL_ID,
        "selected": EXPECTED_MODEL_ID,
        "ok": True,
    }
    assert payload["environment"]["mutation_actions"] == []
    assert payload["baseline_readonly"]["requirements_covered"] == ["BASE-03"]
    assert payload["baseline_readonly"]["unchanged"] is True
    assert env_out.is_file()
    assert baseline_out.is_file()
    assert json.loads(env_out.read_text(encoding="utf-8"))["ok"] is True
    assert json.loads(baseline_out.read_text(encoding="utf-8"))["ok"] is True


def test_main_writes_aggregate_compatible_artifacts(tmp_path):
    env_out = tmp_path / "environment.json"
    baseline_out = tmp_path / "baseline_readonly.json"
    assert main(["--environment-out", str(env_out), "--baseline-out", str(baseline_out)]) == 0
    env = json.loads(env_out.read_text(encoding="utf-8"))
    baseline = json.loads(baseline_out.read_text(encoding="utf-8"))
    for payload in (env, baseline):
        assert "ok" in payload
        assert "fatal_failures" in payload
        assert "warnings" in payload
        assert "requirements_covered" in payload
    assert env["requirements_covered"] == ["BASE-01", "BASE-02"]
    assert baseline["requirements_covered"] == ["BASE-03"]


def test_main_rejects_output_under_frozen_root():
    with pytest.raises(ValueError):
        main([
            "--environment-out",
            str(FROZEN_ROOT / "environment.json"),
            "--baseline-out",
            "/tmp/baseline_readonly.json",
        ])
