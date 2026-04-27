#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Root cause 聚合分析模块。

汇总多次 validate.py 运行结果，量化失配模式分布，归因到 reward/data-target/training-config，
输出 Phase 12 可直接消费的 candidate causes。
"""

import argparse
import json
import os
from typing import Any, Dict, List


HIGH_CLOSENESS_FAIL_THRESHOLD = 0.8
NEAR_THRESHOLD_MIN = 0.05
NEAR_THRESHOLD_MAX = 0.2


def _deviation_bucket(dev: float) -> str:
    if dev <= 0.1:
        return "match"
    if dev <= 0.3:
        return "near_miss"
    return "large_deviation"


def _pred_sat_bucket(pred_sat: float) -> str:
    if pred_sat <= 0.3:
        return "low"
    if pred_sat <= 0.7:
        return "mid"
    return "high"


def _closeness_from_deviation(dev: float) -> float:
    return max(0.0, 1.0 - dev)


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _run_snapshot(run: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "total_samples": run["total_samples"],
        "saturation_match_rate": run["saturation_match_rate"],
        "saturation_deviation": run["saturation_deviation"],
        "saturation_samples_evaluated": run["saturation_samples_evaluated"],
        "sample_manifest": run.get("sample_manifest", {}),
        "failure_buckets": run.get("root_cause", {}).get("failure_buckets", {}),
    }


def _validate_run_metadata(runs: Dict[str, Dict[str, Any]]) -> None:
    expected_sample_mode = None
    for run_name, run in runs.items():
        manifest = run.get("sample_manifest", {})
        if manifest.get("manifest_size") != run.get("total_samples"):
            raise ValueError(f"run {run_name} manifest_size 与 total_samples 不一致")
        sample_mode = manifest.get("sample_mode")
        if expected_sample_mode is None:
            expected_sample_mode = sample_mode
        elif sample_mode != expected_sample_mode:
            raise ValueError(f"run {run_name} sample_mode 与其他 runs 不一致")


def compare_sample_runs(runs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    _validate_run_metadata(runs)
    sorted_run_keys = sorted(runs.keys(), key=lambda k: runs[k]["total_samples"])
    smallest_run_key = sorted_run_keys[0]
    smallest_match_rate = runs[smallest_run_key]["saturation_match_rate"]

    comparison = {}
    for key in sorted_run_keys:
        run = runs[key]
        comparison[key] = {
            "total_samples": run["total_samples"],
            "saturation_match_rate": run["saturation_match_rate"],
            "saturation_deviation": run["saturation_deviation"],
            "saturation_samples_evaluated": run["saturation_samples_evaluated"],
            "match_rate_delta_vs_smallest_run": round(
                run["saturation_match_rate"] - smallest_match_rate, 2
            ),
            "sample_manifest": run.get("sample_manifest", {}),
        }
    return comparison


def build_root_cause_report(
    runs: Dict[str, Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    sorted_run_keys = sorted(runs.keys(), key=lambda k: runs[k]["total_samples"])

    phase_deviation_distribution = {}
    pred_saturation_buckets = {}
    constraint_vs_saturation_split = {}
    clip_sensitive_summary = {}
    reward_threshold_alignment = {}
    preserved_failure_examples = {}

    for key in sorted_run_keys:
        run = runs[key]
        details = run["root_cause"]["details_preview"]
        buckets = run["root_cause"]["failure_buckets"]

        dev_dist = {"match": 0, "near_miss": 0, "large_deviation": 0}
        sat_buckets = {
            "low": {"total": 0, "match": 0, "mismatch": 0},
            "mid": {"total": 0, "match": 0, "mismatch": 0},
            "high": {"total": 0, "match": 0, "mismatch": 0},
        }
        clip_count = 0
        clip_mismatch = 0

        high_closeness_hard_fail = []
        low_closeness_hard_pass = []
        near_threshold_count = 0
        closeness_values = []

        for detail in details:
            failure_bucket = detail.get("failure_bucket", "")
            if failure_bucket in ("format_failure", "constraint_failure"):
                continue

            deviation = detail.get("normalized_deviation")
            if deviation is None:
                continue

            dev_dist[_deviation_bucket(deviation)] += 1

            pred_sat = float(detail.get("pred_saturation", 0.0))
            pred_sat_bucket = _pred_sat_bucket(pred_sat)
            sat_buckets[pred_sat_bucket]["total"] += 1
            if detail.get("is_match"):
                sat_buckets[pred_sat_bucket]["match"] += 1
            else:
                sat_buckets[pred_sat_bucket]["mismatch"] += 1

            if detail.get("is_clip_sensitive"):
                clip_count += 1
                if not detail.get("is_match"):
                    clip_mismatch += 1

            closeness = _closeness_from_deviation(deviation)
            closeness_values.append(closeness)

            if closeness > HIGH_CLOSENESS_FAIL_THRESHOLD and not detail.get("is_match"):
                high_closeness_hard_fail.append(
                    {
                        "sample_id": detail["sample_id"],
                        "phase_id": detail["phase_id"],
                        "normalized_deviation": round(deviation, 4),
                        "closeness": round(closeness, 4),
                    }
                )

            if closeness < 0.5 and detail.get("is_match"):
                low_closeness_hard_pass.append(
                    {
                        "sample_id": detail["sample_id"],
                        "phase_id": detail["phase_id"],
                        "normalized_deviation": round(deviation, 4),
                        "closeness": round(closeness, 4),
                    }
                )

            if NEAR_THRESHOLD_MIN <= deviation <= NEAR_THRESHOLD_MAX:
                near_threshold_count += 1

        evaluable = len(
            [
                detail
                for detail in details
                if detail.get("failure_bucket") not in ("format_failure", "constraint_failure")
            ]
        )

        phase_deviation_distribution[key] = dev_dist
        pred_saturation_buckets[key] = sat_buckets
        constraint_vs_saturation_split[key] = {
            "format_failure": buckets.get("format_failure", 0),
            "constraint_failure": buckets.get("constraint_failure", 0),
            "saturation_mismatch": buckets.get("saturation_mismatch", 0),
            "saturation_match": buckets.get("saturation_match", 0),
        }
        clip_sensitive_summary[key] = {
            "clip_sensitive_count": clip_count,
            "clip_sensitive_mismatch": clip_mismatch,
        }

        mean_closeness = sum(closeness_values) / len(closeness_values) if closeness_values else 0.0
        reward_threshold_alignment[key] = {
            "high_closeness_hard_fail_count": len(high_closeness_hard_fail),
            "low_closeness_hard_pass_count": len(low_closeness_hard_pass),
            "near_threshold_share": round(
                near_threshold_count / evaluable if evaluable else 0.0, 2
            ),
            "mean_closeness": round(mean_closeness, 4),
            "examples": {
                "high_closeness_hard_fail": high_closeness_hard_fail[:5],
                "low_closeness_hard_pass": low_closeness_hard_pass[:5],
            },
        }

        preserved_failure_examples[key] = run["root_cause"].get("failure_examples", {})

    grpo_cfg = config.get("training", {}).get("grpo_simple", {})

    target_definition_findings = {
        "formula": "round(max_green * pred_saturation)",
        "clip_rule": "clip_to_[min_green,max_green]",
        "note": "pred_saturation > 1.0 clips to max_green; very low pred_saturation clips to min_green",
    }

    training_config_findings = {
        "num_train_epochs": grpo_cfg.get("num_train_epochs"),
        "max_steps": grpo_cfg.get("max_steps"),
        "learning_rate": grpo_cfg.get("learning_rate"),
    }

    recommended_phase12_inputs = [
        {
            "candidate_cause": "reward_threshold_misalignment",
            "description": "Reward uses continuous closeness but validation uses hard 0.1 threshold",
            "evidence_keys": ["reward_threshold_alignment"],
        },
        {
            "candidate_cause": "target_definition_round_clip",
            "description": "calculate_target_green clips to [min,max] after rounding, creating boundary effects",
            "evidence_keys": ["clip_sensitive_summary", "target_definition_findings"],
        },
        {
            "candidate_cause": "training_config_undertraining",
            "description": "num_train_epochs=1 and max_steps=5000 may be insufficient",
            "evidence_keys": ["training_config_findings"],
        },
    ]

    return {
        "run_comparison": compare_sample_runs(runs),
        "phase_deviation_distribution": phase_deviation_distribution,
        "pred_saturation_buckets": pred_saturation_buckets,
        "constraint_vs_saturation_split": constraint_vs_saturation_split,
        "clip_sensitive_summary": clip_sensitive_summary,
        "reward_threshold_alignment": reward_threshold_alignment,
        "target_definition_findings": target_definition_findings,
        "training_config_findings": training_config_findings,
        "preserved_failure_examples": preserved_failure_examples,
        "recommended_phase12_inputs": recommended_phase12_inputs,
    }


def _render_markdown_report(report: Dict[str, Any]) -> str:
    lines = [
        "# Root Cause Report",
        "",
        "## Run Comparison",
        "",
        "| Run | Samples | Match Rate | Delta vs Smallest |",
        "|-----|---------|------------|-------------------|",
    ]
    for run_name, summary in report["run_comparison"].items():
        lines.append(
            f"| {run_name} | {summary['total_samples']} | {summary['saturation_match_rate']:.4f} | {summary['match_rate_delta_vs_smallest_run']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Candidate Causes",
            "",
        ]
    )
    for item in report["recommended_phase12_inputs"]:
        lines.append(
            f"- **{item['candidate_cause']}**: {item['description']} (evidence: {', '.join(item['evidence_keys'])})"
        )

    lines.extend(
        [
            "",
            "## Training Config Findings",
            "",
            f"- num_train_epochs: {report['training_config_findings']['num_train_epochs']}",
            f"- max_steps: {report['training_config_findings']['max_steps']}",
            f"- learning_rate: {report['training_config_findings']['learning_rate']}",
            "",
            "## Target Definition Findings",
            "",
            f"- formula: {report['target_definition_findings']['formula']}",
            f"- clip_rule: {report['target_definition_findings']['clip_rule']}",
            f"- note: {report['target_definition_findings']['note']}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate GRPO simple root-cause runs")
    parser.add_argument("--config", required=True, help="配置文件路径")
    parser.add_argument(
        "--run",
        action="append",
        default=[],
        help="单个 run，格式 name=path/to/result.json，可重复传入",
    )
    parser.add_argument("--json-output", default=None, help="聚合 JSON 输出路径")
    parser.add_argument("--markdown-output", default=None, help="Markdown 摘要输出路径")
    args = parser.parse_args()

    if not args.run:
        raise SystemExit("至少提供一个 --run name=path")

    runs = {}
    for item in args.run:
        if "=" not in item:
            raise SystemExit(f"非法 --run 参数: {item}")
        name, path = item.split("=", 1)
        runs[name] = _load_json(path)

    config = _load_json(args.config)
    report = build_root_cause_report(runs=runs, config=config)

    if args.json_output:
        os.makedirs(os.path.dirname(args.json_output) or ".", exist_ok=True)
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    if args.markdown_output:
        os.makedirs(os.path.dirname(args.markdown_output) or ".", exist_ok=True)
        with open(args.markdown_output, "w", encoding="utf-8") as f:
            f.write(_render_markdown_report(report))

    if not args.json_output and not args.markdown_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
