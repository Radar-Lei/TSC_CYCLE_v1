import json
from pathlib import Path

import pytest

from tsc_cycle.prompt_builder import parse_assistant_output
from tsc_cycle.v4_gates.phase7_protocol import evaluate_protocol_fixtures, main


VALID_FULL = '<start_working_out>reasoning</end_working_out><SOLUTION>{"1":60}</SOLUTION>'
VALID_PREFILL = 'reasoning</end_working_out><SOLUTION>{"1":60}</SOLUTION>'


def test_accepts_slash_close_full_output():
    reasoning, solution = parse_assistant_output(VALID_FULL)
    assert reasoning == "reasoning"
    assert solution == {"1": 60}


def test_accepts_slash_close_prefill_output():
    reasoning, solution = parse_assistant_output(VALID_PREFILL)
    assert reasoning == "reasoning"
    assert solution == {"1": 60}


@pytest.mark.parametrize(
    "body",
    [
        '<start_working_out>reasoning<end_working_out><SOLUTION>{"1":60}</SOLUTION>',
        'reasoning<end_working_out><SOLUTION>{"1":60}</SOLUTION>',
        '<start_working_out>bad <think> leak</end_working_out><SOLUTION>{"1":60}</SOLUTION>',
        '<start_working_out>bad </think> leak</end_working_out><SOLUTION>{"1":60}</SOLUTION>',
        '<start_working_out>a<end_working_out>b</end_working_out><SOLUTION>{"1":60}</SOLUTION>',
    ],
)
def test_rejects_malformed_or_native_think(body):
    reasoning, solution = parse_assistant_output(body)
    assert reasoning == ""
    assert solution is None


def test_protocol_fixture_payload_contract():
    payload = evaluate_protocol_fixtures()
    assert payload["ok"] is True
    assert payload["accepted_fixture"]["ok"] is True
    assert payload["chat_template_used"] is False
    assert payload["requirements_covered"] == ["TAG-01", "TAG-02", "TAG-03"]
    assert payload["fatal_failures"] == []
    rejected = {item["name"]: item for item in payload["rejected_fixtures"]}
    assert set(rejected) == {"bare_close", "native_think_open", "native_think_close", "mixed_close"}
    assert all(item["rejected"] is True for item in rejected.values())


def test_protocol_gate_writes_json(tmp_path):
    out = tmp_path / "protocol_fixture.json"
    assert main(["--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["chat_template_used"] is False


def test_protocol_gate_rejects_frozen_root_output():
    frozen = Path("/home/samuel/TSC_CYCLE/runs/20260507T032419Z/protocol_fixture.json")
    with pytest.raises(ValueError):
        main(["--out", str(frozen)])
