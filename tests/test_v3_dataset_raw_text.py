import pytest

from tsc_cycle.student.dataset import build_text, dataset_wiring_metadata, tokenize_one
from tsc_cycle.prompt_builder import TAG_THINK_OPEN, build_full_assistant, build_user_prompt


EX_INPUT = {
    "prediction": {
        "as_of": "2026-04-27 00:02:27",
        "phase_waits": [
            {"phase_id": 1, "pred_wait": 0.4, "pred_saturation": 0.0083, "min_green": 50, "max_green": 80, "capacity": 48},
        ],
    }
}


class FakeTokenizer:
    eos_token = "<eos>"

    def __init__(self):
        self.chat_template_used = False

    def apply_chat_template(self, *args, **kwargs):
        self.chat_template_used = True
        raise AssertionError("apply_chat_template must not be used for v3 SFT raw-text assembly")

    def encode(self, text, add_special_tokens=False):
        assert add_special_tokens is False
        if text == "<think>":
            return [99]
        if text == "</think>":
            return [100]
        return [ord(ch) + 1000 for ch in text]

    def __call__(self, text, truncation=False, max_length=None, add_special_tokens=False):
        ids = []
        i = 0
        while i < len(text):
            if text.startswith("<think>", i):
                ids.append(99)
                i += len("<think>")
            elif text.startswith("</think>", i):
                ids.append(100)
                i += len("</think>")
            else:
                ids.append(ord(text[i]) + 1000)
                i += 1
        if truncation and max_length is not None:
            ids = ids[:max_length]
        return {"input_ids": ids}


def test_build_text_uses_raw_prompt_builder_strings_not_chat_template():
    tokenizer = FakeTokenizer()

    prompt, assistant = build_text(EX_INPUT, "reasoning", {"1": 55})
    tok = tokenize_one(tokenizer, prompt, assistant, max_length=4096)

    assert prompt == build_user_prompt(EX_INPUT)
    assert assistant == build_full_assistant("reasoning", {"1": 55})
    assert tokenizer.chat_template_used is False
    assert tok["chat_template_used"] is False
    assert tok["metadata"]["chat_template_used"] is False
    assert tok["metadata"]["dataset_raw_text_path"] == "prompt_builder.build_user_prompt+build_full_assistant"
    assert tok["labels"].count(-100) > 0


def test_tokenize_one_rejects_dynamic_native_think_ids_from_tokenizer():
    tokenizer = FakeTokenizer()
    prompt = build_user_prompt(EX_INPUT)
    assistant = TAG_THINK_OPEN + "bad native <think> leakage<end_working_out><SOLUTION>{\"1\":55}</SOLUTION>"

    with pytest.raises(AssertionError, match="native think token id 99"):
        tokenize_one(tokenizer, prompt, assistant, max_length=4096)

    assert tokenizer.chat_template_used is False


def test_dataset_wiring_metadata_proves_raw_text_no_chat_template_mode():
    metadata = dataset_wiring_metadata()

    assert metadata["chat_template_used"] is False
    assert metadata["dataset_raw_text_path"] == "prompt_builder.build_user_prompt+build_full_assistant"
