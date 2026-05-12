import json
from pathlib import Path

import pytest

from tsc_cycle.prompt_builder import TAG_SOLUTION_CLOSE, TAG_SOLUTION_OPEN, TAG_THINK_CLOSE, TAG_THINK_OPEN
from tsc_cycle.v4_gates.phase7_tokenizer import EXPECTED_MODEL_ID, evaluate_tokenizer_audit, main


class FakeTokenizer:
    def __init__(self, mapping, vocab_size=8192):
        self.mapping = mapping
        self.vocab_size = vocab_size

    def __len__(self):
        return self.vocab_size

    def encode(self, text, add_special_tokens=False):
        assert add_special_tokens is False
        return list(self.mapping[text])


def _mapping(custom_close=None, native_open=None, native_close=None):
    return {
        TAG_THINK_OPEN: [1, 2, 3],
        TAG_THINK_CLOSE: custom_close or [4, 5, 6],
        TAG_SOLUTION_OPEN: [7, 8, 9],
        TAG_SOLUTION_CLOSE: [10, 11, 12],
        "<think>": native_open or [901],
        "</think>": native_close or [902],
    }


def test_fake_tokenizer_payload_contract_uses_corrected_tags_and_dynamic_ids():
    tokenizer = FakeTokenizer(_mapping())
    payload = evaluate_tokenizer_audit(tokenizer=tokenizer)
    assert payload["ok"] is True
    assert payload["model_id"] == EXPECTED_MODEL_ID
    assert payload["custom_tags"][TAG_THINK_CLOSE] == [4, 5, 6]
    assert set(payload["custom_tags"]) == {TAG_THINK_OPEN, TAG_THINK_CLOSE, TAG_SOLUTION_OPEN, TAG_SOLUTION_CLOSE}
    assert payload["native_think"] == {"<think>": [901], "</think>": [902]}
    assert payload["native_think_token_ids"] == [901, 902]
    assert payload["chat_template_used"] is False
    assert payload["requirements_covered"] == ["TAG-04", "TAG-03", "TAG-01"]
    assert payload["fatal_failures"] == []


def test_custom_tag_with_too_few_subtokens_fails():
    tokenizer = FakeTokenizer(_mapping(custom_close=[4, 5]))
    payload = evaluate_tokenizer_audit(tokenizer=tokenizer)
    assert payload["ok"] is False
    assert payload["fatal_failures"]
    assert "</end_working_out>" in payload["bad_custom_tags"]


def test_native_ids_are_not_hardcoded():
    tokenizer = FakeTokenizer(_mapping(native_open=[321], native_close=[654]))
    payload = evaluate_tokenizer_audit(tokenizer=tokenizer)
    assert payload["native_think_token_ids"] == [321, 654]
    assert payload["native_think_token_ids"] != [151667, 151668]


def test_rejects_qwen35_model_id():
    tokenizer = FakeTokenizer(_mapping())
    payload = evaluate_tokenizer_audit(tokenizer=tokenizer, model_id="Qwen/Qwen3.5-9B")
    assert payload["ok"] is False
    assert payload["fatal_failures"]


def test_rejects_qwen35_model_id_without_loading_tokenizer(monkeypatch):
    def fail_loader(model_id):
        raise AssertionError(f"should not load {model_id}")

    monkeypatch.setattr("tsc_cycle.v4_gates.phase7_tokenizer._load_tokenizer", fail_loader)
    payload = evaluate_tokenizer_audit(model_id="Qwen/Qwen3.5-9B")
    assert payload["ok"] is False
    assert payload["fatal_failures"]
    assert payload["native_think_token_ids"] == []


def test_main_writes_json_with_fake_loader(tmp_path, monkeypatch):
    out = tmp_path / "tokenizer_audit.json"

    def fake_loader(model_id):
        assert model_id == EXPECTED_MODEL_ID
        return FakeTokenizer(_mapping())

    monkeypatch.setattr("tsc_cycle.v4_gates.phase7_tokenizer._load_tokenizer", fake_loader)
    assert main(["--out", str(out)]) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["native_think_token_ids"] == [901, 902]


def test_main_rejects_frozen_root_output():
    frozen = Path("/home/samuel/TSC_CYCLE/runs/20260507T032419Z/tokenizer_audit.json")
    with pytest.raises(ValueError):
        main(["--out", str(frozen)])
