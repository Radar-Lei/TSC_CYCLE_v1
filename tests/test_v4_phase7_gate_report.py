import json
from pathlib import Path

import pytest

from tsc_cycle.v4_gates.phase7_report import REQUIREMENTS_COVERED, evaluate_gates, main


GATE_FIXTURES = {
    "protocol_fixture.json": {
        "ok": True,
        "fatal_failures": [],
        "warnings": [],
        "requirements_covered": ["TAG-01", "TAG-02", "TAG-03"],
    },
    "environment.json": {
        "ok": True,
        "fatal_failures": [],
        "warnings": ["environment warning"],
        "requirements_covered": ["BASE-01", "BASE-02"],
    },
    "baseline_readonly.json": {
        "ok": True,
        "fatal_failures": [],
        "warnings": ["baseline warning"],
        "requirements_covered": ["BASE-03"],
        "unchanged": True,
    },
    "tokenizer_audit.json": {
        "ok": True,
        "fatal_failures": [],
        "warnings": [],
        "requirements_covered": ["TAG-04", "TAG-03", "TAG-01"],
        "native_think_token_ids": [151667, 151668],
    },
}


def _write_fixture_set(path: Path, fixtures=None):
    fixtures = fixtures or GATE_FIXTURES
    path.mkdir(parents=True, exist_ok=True)
    for name, payload in fixtures.items():
        (path / name).write_text(json.dumps(payload), encoding="utf-8")


def test_evaluate_gates_passes_when_all_subgates_cover_requirements(tmp_path):
    _write_fixture_set(tmp_path)
    payload = evaluate_gates(tmp_path)
    assert payload["ok"] is True
    assert payload["next_phase_allowed"] is True
    assert payload["fatal_failures"] == []
    assert payload["requirements_covered"] == REQUIREMENTS_COVERED
    assert set(payload["gates"]) == {"protocol_fixture", "environment", "baseline_readonly", "tokenizer_audit"}
    assert payload["warnings"] == [
        {"gate": "environment", "warning": "environment warning"},
        {"gate": "baseline_readonly", "warning": "baseline warning"},
    ]


def test_evaluate_gates_fails_closed_for_missing_artifact(tmp_path):
    _write_fixture_set(tmp_path)
    (tmp_path / "tokenizer_audit.json").unlink()
    payload = evaluate_gates(tmp_path)
    assert payload["ok"] is False
    assert payload["next_phase_allowed"] is False
    assert any(failure["gate"] == "tokenizer_audit" for failure in payload["fatal_failures"])


def test_evaluate_gates_fails_closed_for_malformed_artifact(tmp_path):
    _write_fixture_set(tmp_path)
    (tmp_path / "environment.json").write_text("{", encoding="utf-8")
    payload = evaluate_gates(tmp_path)
    assert payload["ok"] is False
    assert payload["next_phase_allowed"] is False
    assert any(failure["gate"] == "environment" and "malformed JSON" in failure["reason"] for failure in payload["fatal_failures"])


def test_evaluate_gates_fails_closed_for_red_subgate(tmp_path):
    fixtures = json.loads(json.dumps(GATE_FIXTURES))
    fixtures["protocol_fixture.json"]["ok"] = False
    fixtures["protocol_fixture.json"]["fatal_failures"] = [{"gate": "protocol", "reason": "native think accepted"}]
    _write_fixture_set(tmp_path, fixtures)
    payload = evaluate_gates(tmp_path)
    assert payload["ok"] is False
    assert payload["next_phase_allowed"] is False
    assert {"gate": "protocol", "reason": "native think accepted"} in payload["fatal_failures"]


def test_evaluate_gates_fails_closed_for_missing_requirement(tmp_path):
    fixtures = json.loads(json.dumps(GATE_FIXTURES))
    fixtures["environment.json"]["requirements_covered"] = ["BASE-01"]
    _write_fixture_set(tmp_path, fixtures)
    payload = evaluate_gates(tmp_path)
    assert payload["ok"] is False
    assert payload["next_phase_allowed"] is False
    assert {"gate": "requirements_covered", "reason": "missing requirements: BASE-02"} in payload["fatal_failures"]


def test_main_writes_report_and_rejects_frozen_root(tmp_path):
    _write_fixture_set(tmp_path)
    out = tmp_path / "phase7_gate_report.json"
    assert main(["--artifacts", str(tmp_path), "--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["next_phase_allowed"] is True

    frozen = "/home/samuel/TSC_CYCLE/runs/20260507T032419Z/phase7_gate_report.json"
    with pytest.raises(ValueError):
        main(["--artifacts", str(tmp_path), "--out", frozen])


def test_wrapper_uses_fixed_safe_commands():
    script = Path("/home/samuel/TSC_CYCLE/scripts/run_v4_phase7_gate.sh")
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert 'PY="$ROOT/.venv/bin/python"' in text
    assert 'ART="$ROOT/artifacts/v4/phase7"' in text
    assert "tsc_cycle.v4_gates.phase7_protocol" in text
    assert "tsc_cycle.v4_gates.phase7_baseline" in text
    assert "tsc_cycle.v4_gates.phase7_tokenizer" in text
    assert "tsc_cycle.v4_gates.phase7_report" in text
    forbidden = ["pip install", "uv pip", "sudo", "eval"]
    assert not any(term in text for term in forbidden)
    assert "runs/20260507T032419Z" not in text
