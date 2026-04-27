import json

from src.grpo_simple.root_cause_analysis import build_root_cause_report


def _make_run(summary, details_preview, failure_examples=None):
    return {
        "total_samples": summary["total_samples"],
        "saturation_match_rate": summary["saturation_match_rate"],
        "saturation_deviation": summary["saturation_deviation"],
        "saturation_samples_evaluated": summary["saturation_samples_evaluated"],
        "sample_manifest": summary["sample_manifest"],
        "root_cause": {
            "details_preview": details_preview,
            "failure_examples": failure_examples or {},
            "failure_buckets": summary["root_cause"]["failure_buckets"],
            "saturation_evaluable": summary["root_cause"]["saturation_evaluable"],
        },
    }


def test_build_root_cause_report_compares_runs_and_outputs_required_sections():
    run_50 = _make_run(
        {
            "total_samples": 50,
            "saturation_match_rate": 0.98,
            "saturation_deviation": {"mean": 0.03, "median": 0.02, "max": 0.18},
            "saturation_samples_evaluated": 2,
            "sample_manifest": {
                "seed": 11,
                "requested_samples": 50,
                "manifest_size": 50,
                "sample_mode": "random",
            },
            "root_cause": {
                "failure_buckets": {
                    "format_failure": 0,
                    "constraint_failure": 0,
                    "saturation_mismatch": 1,
                    "saturation_match": 1,
                },
                "saturation_evaluable": 2,
            },
        },
        [
            {
                "sample_id": "run50-a",
                "phase_id": 1,
                "pred_saturation": 0.25,
                "min_green": 10,
                "max_green": 40,
                "target_green": 10,
                "final": 10,
                "normalized_deviation": 0.0,
                "is_match": True,
                "is_clip_sensitive": True,
                "failure_bucket": "saturation_match",
            },
            {
                "sample_id": "run50-b",
                "phase_id": 2,
                "pred_saturation": 0.78,
                "min_green": 10,
                "max_green": 50,
                "target_green": 39,
                "final": 32,
                "normalized_deviation": 0.175,
                "is_match": False,
                "is_clip_sensitive": False,
                "failure_bucket": "saturation_mismatch",
            },
        ],
        {
            "large_deviation": [{"sample_id": "run50-b", "phase_id": 2}],
            "clip_sensitive": [{"sample_id": "run50-a", "phase_id": 1}],
        },
    )

    run_4000 = _make_run(
        {
            "total_samples": 4000,
            "saturation_match_rate": 0.55,
            "saturation_deviation": {"mean": 0.19, "median": 0.06, "max": 1.25},
            "saturation_samples_evaluated": 3,
            "sample_manifest": {
                "seed": 42,
                "requested_samples": 4000,
                "manifest_size": 4000,
                "sample_mode": "random",
            },
            "root_cause": {
                "failure_buckets": {
                    "format_failure": 0,
                    "constraint_failure": 1,
                    "saturation_mismatch": 2,
                    "saturation_match": 1,
                },
                "saturation_evaluable": 3,
            },
        },
        [
            {
                "sample_id": "run4000-a",
                "phase_id": 3,
                "pred_saturation": 0.25,
                "min_green": 10,
                "max_green": 40,
                "target_green": 10,
                "final": 12,
                "normalized_deviation": 0.0667,
                "is_match": True,
                "is_clip_sensitive": True,
                "failure_bucket": "saturation_match",
            },
            {
                "sample_id": "run4000-b",
                "phase_id": 4,
                "pred_saturation": 0.82,
                "min_green": 10,
                "max_green": 50,
                "target_green": 41,
                "final": 29,
                "normalized_deviation": 0.3,
                "is_match": False,
                "is_clip_sensitive": False,
                "failure_bucket": "saturation_mismatch",
            },
            {
                "sample_id": "run4000-c",
                "phase_id": 5,
                "pred_saturation": 1.0,
                "min_green": 10,
                "max_green": 40,
                "target_green": 40,
                "final": 28,
                "normalized_deviation": 0.4,
                "is_match": False,
                "is_clip_sensitive": True,
                "failure_bucket": "saturation_mismatch",
            },
            {
                "sample_id": "run4000-d",
                "phase_id": 6,
                "pred_saturation": 0.5,
                "min_green": 20,
                "max_green": 60,
                "target_green": 30,
                "final": 10,
                "normalized_deviation": 0.5,
                "is_match": False,
                "is_clip_sensitive": False,
                "failure_bucket": "constraint_failure",
            },
        ],
        {
            "large_deviation": [
                {"sample_id": "run4000-b", "phase_id": 4},
                {"sample_id": "run4000-c", "phase_id": 5},
            ],
            "clip_sensitive": [
                {"sample_id": "run4000-a", "phase_id": 3},
                {"sample_id": "run4000-c", "phase_id": 5},
            ],
        },
    )

    report = build_root_cause_report(
        runs={"50": run_50, "4000": run_4000},
        config={
            "training": {
                "grpo_simple": {
                    "num_train_epochs": 1,
                    "max_steps": 5000,
                    "learning_rate": 5e-6,
                }
            }
        },
    )

    required_keys = {
        "run_comparison",
        "phase_deviation_distribution",
        "pred_saturation_buckets",
        "constraint_vs_saturation_split",
        "clip_sensitive_summary",
        "reward_threshold_alignment",
        "target_definition_findings",
        "training_config_findings",
        "preserved_failure_examples",
        "recommended_phase12_inputs",
    }
    assert required_keys.issubset(report.keys())

    assert report["run_comparison"]["50"]["saturation_match_rate"] == 0.98
    assert report["run_comparison"]["4000"]["saturation_match_rate"] == 0.55
    assert report["run_comparison"]["4000"]["match_rate_delta_vs_smallest_run"] == -0.43

    assert "50" in report["phase_deviation_distribution"]
    assert "4000" in report["phase_deviation_distribution"]
    assert report["pred_saturation_buckets"]["4000"]["high"]["total"] >= 2
    assert report["constraint_vs_saturation_split"]["4000"]["constraint_failure"] == 1
    assert report["constraint_vs_saturation_split"]["4000"]["saturation_mismatch"] == 2
    assert report["clip_sensitive_summary"]["4000"]["clip_sensitive_count"] == 2


def test_build_root_cause_report_quantifies_reward_threshold_misalignment():
    run = _make_run(
        {
            "total_samples": 3,
            "saturation_match_rate": 0.33,
            "saturation_deviation": {"mean": 0.18, "median": 0.12, "max": 0.25},
            "saturation_samples_evaluated": 3,
            "sample_manifest": {
                "seed": 7,
                "requested_samples": 3,
                "manifest_size": 3,
                "sample_mode": "random",
            },
            "root_cause": {
                "failure_buckets": {
                    "format_failure": 0,
                    "constraint_failure": 0,
                    "saturation_mismatch": 2,
                    "saturation_match": 1,
                },
                "saturation_evaluable": 3,
            },
        },
        [
            {
                "sample_id": "high-close-fail",
                "phase_id": 1,
                "pred_saturation": 0.8,
                "min_green": 10,
                "max_green": 50,
                "target_green": 40,
                "final": 35,
                "normalized_deviation": 0.125,
                "is_match": False,
                "is_clip_sensitive": False,
                "failure_bucket": "saturation_mismatch",
            },
            {
                "sample_id": "low-close-pass",
                "phase_id": 2,
                "pred_saturation": 0.5,
                "min_green": 28,
                "max_green": 32,
                "target_green": 30,
                "final": 30,
                "normalized_deviation": 0.0,
                "is_match": True,
                "is_clip_sensitive": False,
                "failure_bucket": "saturation_match",
            },
            {
                "sample_id": "low-close-fail",
                "phase_id": 3,
                "pred_saturation": 1.0,
                "min_green": 10,
                "max_green": 40,
                "target_green": 40,
                "final": 34,
                "normalized_deviation": 0.2,
                "is_match": False,
                "is_clip_sensitive": True,
                "failure_bucket": "saturation_mismatch",
            },
        ],
        {
            "large_deviation": [{"sample_id": "low-close-fail", "phase_id": 3}],
            "clip_sensitive": [{"sample_id": "low-close-fail", "phase_id": 3}],
        },
    )

    report = build_root_cause_report(
        runs={"analysis": run},
        config={
            "training": {
                "grpo_simple": {
                    "num_train_epochs": 1,
                    "max_steps": 5000,
                    "learning_rate": 5e-6,
                }
            }
        },
    )

    alignment = report["reward_threshold_alignment"]["analysis"]
    assert alignment["high_closeness_hard_fail_count"] == 1
    assert alignment["low_closeness_hard_pass_count"] == 0
    assert alignment["near_threshold_share"] == 0.67
    assert alignment["mean_closeness"] < 1.0
    assert alignment["examples"]["high_closeness_hard_fail"][0]["sample_id"] == "high-close-fail"


def test_build_root_cause_report_rejects_inconsistent_run_metadata():
    run_a = _make_run(
        {
            "total_samples": 10,
            "saturation_match_rate": 0.5,
            "saturation_deviation": {"mean": 0.1, "median": 0.1, "max": 0.2},
            "saturation_samples_evaluated": 1,
            "sample_manifest": {
                "seed": 1,
                "requested_samples": 10,
                "manifest_size": 10,
                "sample_mode": "random",
            },
            "root_cause": {
                "failure_buckets": {
                    "format_failure": 0,
                    "constraint_failure": 0,
                    "saturation_mismatch": 0,
                    "saturation_match": 1,
                },
                "saturation_evaluable": 1,
            },
        },
        [
            {
                "sample_id": "a",
                "phase_id": 1,
                "pred_saturation": 0.2,
                "min_green": 10,
                "max_green": 40,
                "raw_target": 8,
                "target_green": 10,
                "final": 10,
                "normalized_deviation": 0.0,
                "match_threshold_hit": True,
                "is_match": True,
                "is_clip_sensitive": True,
                "constraint_status": "constraint_pass",
                "failure_bucket": "saturation_match",
            }
        ],
    )
    run_b = _make_run(
        {
            "total_samples": 20,
            "saturation_match_rate": 0.4,
            "saturation_deviation": {"mean": 0.2, "median": 0.2, "max": 0.3},
            "saturation_samples_evaluated": 1,
            "sample_manifest": {
                "seed": 2,
                "requested_samples": 20,
                "manifest_size": 20,
                "sample_mode": "stratified",
            },
            "root_cause": {
                "failure_buckets": {
                    "format_failure": 0,
                    "constraint_failure": 0,
                    "saturation_mismatch": 1,
                    "saturation_match": 0,
                },
                "saturation_evaluable": 1,
            },
        },
        [
            {
                "sample_id": "b",
                "phase_id": 2,
                "pred_saturation": 0.8,
                "min_green": 10,
                "max_green": 50,
                "raw_target": 40,
                "target_green": 40,
                "final": 30,
                "normalized_deviation": 0.25,
                "match_threshold_hit": False,
                "is_match": False,
                "is_clip_sensitive": False,
                "constraint_status": "constraint_pass",
                "failure_bucket": "saturation_mismatch",
            }
        ],
    )

    import pytest

    with pytest.raises(ValueError, match="sample_mode"):
        build_root_cause_report(
            runs={"a": run_a, "b": run_b},
            config={"training": {"grpo_simple": {}}},
        )


def test_build_root_cause_report_embeds_target_and_training_findings_and_preserves_examples():
    run = _make_run(
        {
            "total_samples": 2,
            "saturation_match_rate": 0.5,
            "saturation_deviation": {"mean": 0.21, "median": 0.21, "max": 0.42},
            "saturation_samples_evaluated": 2,
            "sample_manifest": {
                "seed": 19,
                "requested_samples": 2,
                "manifest_size": 2,
                "sample_mode": "random",
            },
            "root_cause": {
                "failure_buckets": {
                    "format_failure": 0,
                    "constraint_failure": 0,
                    "saturation_mismatch": 1,
                    "saturation_match": 1,
                },
                "saturation_evaluable": 2,
            },
        },
        [
            {
                "sample_id": "clip-case",
                "phase_id": 10,
                "pred_saturation": 1.2,
                "min_green": 10,
                "max_green": 40,
                "target_green": 40,
                "final": 28,
                "normalized_deviation": 0.4,
                "is_match": False,
                "is_clip_sensitive": True,
                "failure_bucket": "saturation_mismatch",
            },
            {
                "sample_id": "large-dev-case",
                "phase_id": 11,
                "pred_saturation": 0.2,
                "min_green": 10,
                "max_green": 40,
                "target_green": 10,
                "final": 10,
                "normalized_deviation": 0.0,
                "is_match": True,
                "is_clip_sensitive": True,
                "failure_bucket": "saturation_match",
            },
        ],
        {
            "large_deviation": [{"sample_id": "clip-case", "phase_id": 10}],
            "clip_sensitive": [
                {"sample_id": "clip-case", "phase_id": 10},
                {"sample_id": "large-dev-case", "phase_id": 11},
            ],
        },
    )

    report = build_root_cause_report(
        runs={"focus": run},
        config={
            "training": {
                "grpo_simple": {
                    "num_train_epochs": 1,
                    "max_steps": 5000,
                    "learning_rate": 5e-6,
                }
            }
        },
    )

    target_findings = report["target_definition_findings"]
    assert "round(max_green * pred_saturation)" in target_findings["formula"]
    assert target_findings["clip_rule"] == "clip_to_[min_green,max_green]"

    training_findings = report["training_config_findings"]
    assert training_findings["num_train_epochs"] == 1
    assert training_findings["max_steps"] == 5000
    assert training_findings["learning_rate"] == 5e-6

    preserved = report["preserved_failure_examples"]["focus"]
    assert preserved["large_deviation"][0]["sample_id"] == "clip-case"
    assert preserved["clip_sensitive"][0]["sample_id"] == "clip-case"

    recommendations = report["recommended_phase12_inputs"]
    assert len(recommendations) == 3
    assert {item["candidate_cause"] for item in recommendations} == {
        "reward_threshold_misalignment",
        "target_definition_round_clip",
        "training_config_undertraining",
    }

    json.dumps(report, ensure_ascii=False)
