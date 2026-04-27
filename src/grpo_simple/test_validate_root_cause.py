import copy
import json
import sys
import types

import pytest


if "unsloth" not in sys.modules:
    unsloth_stub = types.ModuleType("unsloth")
    unsloth_stub.FastLanguageModel = object()
    sys.modules["unsloth"] = unsloth_stub

if "src.grpo_simple.train" not in sys.modules:
    train_stub = types.ModuleType("src.grpo_simple.train")
    train_stub.setup_chat_template = lambda tokenizer: tokenizer
    sys.modules["src.grpo_simple.train"] = train_stub

from src.grpo_simple import validate


LEGACY_TOP_LEVEL_KEYS = {
    "total_samples",
    "format_pass_rate",
    "format_details",
    "constraint_pass_rate",
    "constraint_details",
    "saturation_match_rate",
    "saturation_deviation",
    "saturation_samples_evaluated",
    "overall",
}

REQUIRED_DETAIL_FIELDS = {
    "sample_id",
    "phase_id",
    "pred_saturation",
    "min_green",
    "max_green",
    "raw_target",
    "target_green",
    "final",
    "normalized_deviation",
    "match_threshold_hit",
    "is_match",
    "is_clip_sensitive",
    "constraint_status",
    "failure_bucket",
}


@pytest.fixture
def official_4000_summary():
    with open(
        "/home/samuel/TSC_CYCLE/outputs/grpo_simple/qwen3-8b/validation_results.json",
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


@pytest.fixture
def fake_config():
    return {
        "paths": {
            "grpo_simple_data_dir": "unused",
            "grpo_simple_output": "unused",
        }
    }


@pytest.fixture
def fake_samples():
    return [
        {
            "sample_id": "sample-format-fail",
            "prompt": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "phase_waits": [
                                {
                                    "phase_id": 0,
                                    "pred_saturation": 0.25,
                                    "min_green": 10,
                                    "max_green": 40,
                                }
                            ]
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        },
        {
            "sample_id": "sample-constraint-fail",
            "prompt": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "phase_waits": [
                                {
                                    "phase_id": 1,
                                    "pred_saturation": 0.50,
                                    "min_green": 20,
                                    "max_green": 60,
                                }
                            ]
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        },
        {
            "sample_id": "sample-saturation-mismatch",
            "prompt": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "phase_waits": [
                                {
                                    "phase_id": 2,
                                    "pred_saturation": 0.75,
                                    "min_green": 10,
                                    "max_green": 50,
                                },
                                {
                                    "phase_id": 3,
                                    "pred_saturation": 1.00,
                                    "min_green": 10,
                                    "max_green": 40,
                                },
                            ]
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        },
    ]


@pytest.fixture
def fake_completions():
    return [
        "missing-solution-tags",
        "<start_working_out>reasoning<end_working_out><SOLUTION>"
        '[{"phase_id": 1, "final": 10}]'
        "</SOLUTION>",
        "<start_working_out>reasoning<end_working_out><SOLUTION>"
        '[{"phase_id": 2, "final": 20}, {"phase_id": 3, "final": 40}]'
        "</SOLUTION>",
    ]


@pytest.fixture
def patched_validation(monkeypatch, fake_samples, fake_completions):
    monkeypatch.setattr(validate, "load_test_data", lambda *args, **kwargs: copy.deepcopy(fake_samples))
    monkeypatch.setattr(validate, "load_model", lambda *args, **kwargs: (object(), object()))
    monkeypatch.setattr(
        validate,
        "generate_completions",
        lambda *args, **kwargs: list(fake_completions),
    )


def test_run_validation_preserves_legacy_summary_and_adds_root_cause_schema(
    patched_validation, fake_config, official_4000_summary
):
    result = validate.run_validation(fake_config, num_samples=3, seed=7)

    assert LEGACY_TOP_LEVEL_KEYS.issubset(result.keys())
    assert LEGACY_TOP_LEVEL_KEYS.issubset(official_4000_summary.keys())
    assert result["format_details"].keys() == official_4000_summary["format_details"].keys()
    assert result["constraint_details"].keys() == official_4000_summary["constraint_details"].keys()

    assert result["sampled_cases"] == 3
    assert result["sample_manifest"]["seed"] == 7
    assert result["sample_manifest"]["manifest_size"] == 3
    assert result["sample_manifest"]["sample_mode"] == "random"

    assert result["root_cause"]["detail_schema"] == sorted(REQUIRED_DETAIL_FIELDS)
    assert REQUIRED_DETAIL_FIELDS.issubset(result["root_cause"]["details_preview"][0].keys())
    assert "failure_examples" in result["root_cause"]


def test_failure_buckets_do_not_count_constraint_failures_as_saturation_mismatch(
    patched_validation, fake_config
):
    result = validate.run_validation(fake_config, num_samples=3, seed=13)

    buckets = result["root_cause"]["failure_buckets"]
    assert buckets["format_failure"] == 1
    assert buckets["constraint_failure"] == 1
    assert buckets["saturation_mismatch"] == 1
    assert result["root_cause"]["saturation_evaluable"] == 1

    detail_buckets = {
        (detail["sample_id"], detail["phase_id"]): detail["failure_bucket"]
        for detail in result["root_cause"]["details_preview"]
    }
    assert detail_buckets[("sample-format-fail", 0)] == "format_failure"
    assert detail_buckets[("sample-constraint-fail", 1)] == "constraint_failure"
    assert detail_buckets[("sample-saturation-mismatch", 2)] == "saturation_mismatch"
    assert detail_buckets[("sample-saturation-mismatch", 3)] == "saturation_match"


def test_details_are_recorded_per_phase_not_single_representative_row(
    patched_validation, fake_config
):
    result = validate.run_validation(fake_config, num_samples=3, seed=21)

    details = result["root_cause"]["details_preview"]
    sample_phase_counts = {}
    for detail in details:
        sample_phase_counts.setdefault(detail["sample_id"], 0)
        sample_phase_counts[detail["sample_id"]] += 1

    assert sample_phase_counts["sample-format-fail"] == 1
    assert sample_phase_counts["sample-constraint-fail"] == 1
    assert sample_phase_counts["sample-saturation-mismatch"] == 2

    mismatch_detail = next(
        detail
        for detail in details
        if detail["sample_id"] == "sample-saturation-mismatch" and detail["phase_id"] == 2
    )
    match_detail = next(
        detail
        for detail in details
        if detail["sample_id"] == "sample-saturation-mismatch" and detail["phase_id"] == 3
    )

    assert mismatch_detail["raw_target"] == 38
    assert mismatch_detail["target_green"] == 38
    assert mismatch_detail["match_threshold_hit"] is False
    assert mismatch_detail["constraint_status"] == "constraint_pass"
    assert mismatch_detail["failure_bucket"] == "saturation_mismatch"

    assert match_detail["raw_target"] == 40
    assert match_detail["target_green"] == 40
    assert match_detail["match_threshold_hit"] is True
    assert match_detail["constraint_status"] == "constraint_pass"
    assert match_detail["failure_bucket"] == "saturation_match"

    failure_examples = result["root_cause"]["failure_examples"]
    assert failure_examples["large_deviation"][0]["sample_id"] == "sample-saturation-mismatch"
    assert failure_examples["clip_sensitive"][0]["phase_id"] == 3


def test_validate_exposes_near_threshold_and_clip_sensitive_stats(
    patched_validation, fake_config
):
    result = validate.run_validation(fake_config, num_samples=3, seed=33)

    stats = result["root_cause"]["analysis_summary"]
    assert stats["near_threshold_phase_count"] == 0
    assert stats["clip_sensitive_phase_count"] == 2
    assert stats["clip_sensitive_match_count"] == 1


@pytest.mark.parametrize("sample_size", [50, 2000, 4000])
def test_sampling_metadata_semantics_are_consistent_across_run_sizes(
    monkeypatch, fake_config, fake_samples, fake_completions, sample_size
):
    expanded_samples = [
        {
            **copy.deepcopy(fake_samples[index % len(fake_samples)]),
            "sample_id": f"case-{index}",
        }
        for index in range(sample_size)
    ]
    expanded_completions = [fake_completions[index % len(fake_completions)] for index in range(sample_size)]

    monkeypatch.setattr(validate, "load_test_data", lambda *args, **kwargs: expanded_samples)
    monkeypatch.setattr(validate, "load_model", lambda *args, **kwargs: (object(), object()))
    monkeypatch.setattr(validate, "generate_completions", lambda *args, **kwargs: expanded_completions)

    result = validate.run_validation(fake_config, num_samples=sample_size, seed=99)

    assert result["total_samples"] == sample_size
    assert result["sampled_cases"] == sample_size
    assert result["sample_manifest"]["manifest_size"] == sample_size
    assert result["sample_manifest"]["requested_samples"] == sample_size
    assert result["saturation_samples_evaluated"] == result["root_cause"]["saturation_evaluable"]
