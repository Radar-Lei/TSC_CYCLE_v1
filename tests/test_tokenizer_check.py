import pytest

from tsc_cycle.prompt_builder import TAG_SOLUTION_CLOSE, TAG_SOLUTION_OPEN, TAG_THINK_CLOSE, TAG_THINK_OPEN
from tsc_cycle.tokenizer_check import (
    CheckResult,
    assert_no_native_think_in_ids,
    check_tokenizer,
    lookup_native_think_ids,
    native_think_token_ids,
)


class FakeTokenizer:
    def __init__(self, mapping, vocab_size=4096):
        self.mapping = mapping
        self.vocab_size = vocab_size

    def __len__(self):
        return self.vocab_size

    def encode(self, text, add_special_tokens=False):
        assert add_special_tokens is False
        return list(self.mapping[text])


def test_custom_tag_with_two_ids_fails_when_min_custom_subtokens_is_three():
    tokenizer = FakeTokenizer(
        {
            TAG_THINK_OPEN: [1, 2],
            TAG_THINK_CLOSE: [3, 4, 5],
            TAG_SOLUTION_OPEN: [6, 7, 8],
            TAG_SOLUTION_CLOSE: [9, 10, 11],
            "<think>": [99],
            "</think>": [100],
        }
    )

    result = check_tokenizer(tokenizer, min_custom_subtokens=3)

    assert isinstance(result, CheckResult)
    assert result.ok is False
    assert result.details["min_custom_subtokens"] == 3
    assert result.details["bad_custom_tags"] == [TAG_THINK_OPEN]
    assert result.details["custom_tags"][TAG_THINK_OPEN] == [1, 2]


def test_native_think_ids_are_reported_dynamically_without_v1_constants():
    tokenizer = FakeTokenizer(
        {
            TAG_THINK_OPEN: [1, 2, 3],
            TAG_THINK_CLOSE: [4, 5, 6],
            TAG_SOLUTION_OPEN: [7, 8, 9],
            TAG_SOLUTION_CLOSE: [10, 11, 12],
            "<think>": [99],
            "</think>": [100],
        }
    )

    assert lookup_native_think_ids(tokenizer) == {"<think>": [99], "</think>": [100]}
    assert native_think_token_ids(tokenizer) == {99, 100}

    result = check_tokenizer(tokenizer, min_custom_subtokens=3)

    assert result.ok is True
    assert result.details["native_think"] == {"<think>": [99], "</think>": [100]}
    assert "expected_open_id" not in result.details["native_think"]
    assert "expected_close_id" not in result.details["native_think"]


def test_native_think_that_is_not_single_token_is_reported_but_not_compared_to_constants():
    tokenizer = FakeTokenizer(
        {
            TAG_THINK_OPEN: [1, 2, 3],
            TAG_THINK_CLOSE: [4, 5, 6],
            TAG_SOLUTION_OPEN: [7, 8, 9],
            TAG_SOLUTION_CLOSE: [10, 11, 12],
            "<think>": [99, 101],
            "</think>": [100],
        }
    )

    result = check_tokenizer(tokenizer, min_custom_subtokens=3)

    assert result.ok is False
    assert result.details["bad_native_think"] == ["<think>"]
    assert native_think_token_ids(tokenizer) == {100}


def test_assert_no_native_think_in_ids_accepts_dynamic_native_id_set():
    assert_no_native_think_in_ids([1, 2, 3], native_ids={99, 100})

    with pytest.raises(AssertionError, match="native think token id 99"):
        assert_no_native_think_in_ids([1, 99, 3], native_ids={99, 100})


def test_assert_no_native_think_requires_dynamic_native_ids():
    with pytest.raises(ValueError, match="native_ids must be provided"):
        assert_no_native_think_in_ids([151667])
