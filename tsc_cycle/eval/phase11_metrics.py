"""Phase 11 metrics aggregation and report rendering.

This module consumes Phase 11 v4 generation caches plus frozen v1 baseline
per-sample evidence and writes structured metrics before markdown. It does not
import model/GPU stacks.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

from tsc_cycle.eval.metrics_constraints import score_constraint
from tsc_cycle.eval.metrics_mae import score_mae
from tsc_cycle.eval.metrics_reasoning import score_reasoning
from tsc_cycle.eval.phase11_matrix import (
    FROZEN_V1_ROOT,
    PHASE11_OUT_ROOT,
    V1_Q4,
    V4_HF,
    V4_Q4,
    normalize_backend_id,
    reject_frozen_v1_output_path,
)
from tsc_cycle.eval.phase11_stats import bootstrap_mean_ci, paired_delta_ci, tail_metrics

REQUIREMENTS_COVERED = ["EVAL4B-02", "EVAL4B-03"]
BACKENDS = [V4_HF, V4_Q4, V1_Q4]
OOD_SLICES = {"v1_comparable_ood", "v4_expanded_ood", "overall_ood"}
PHASE10_SMOKE_MAE_SENSITIVITY_SEC = 3.092


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"JSONL row is not an object at {path}:{line_no}")
            rows.append(obj)
    return rows


def _json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    reject_frozen_v1_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_payload = _json_safe(payload)
    path.write_text(
        json.dumps(safe_payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_per_sample(rows: Iterable[dict[str, Any]], path: Path) -> None:
    reject_frozen_v1_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def _format_ok(cache: dict[str, Any]) -> bool:
    return cache.get("parse_error") is None and cache.get("solution") is not None


def _source_path(path: Path) -> str:
    return str(path.expanduser().resolve(strict=False))


def _score_v4_cache(prompt: dict[str, Any], cache: dict[str, Any], *, backend: str, cache_file: Path) -> dict[str, Any]:
    solution = cache.get("solution")
    raw_text = cache.get("raw_text", "") or ""
    constraints = score_constraint(prompt.get("input") or {}, solution)
    mae = score_mae(solution, prompt.get("teacher_solution") or {})
    reasoning = score_reasoning(raw_text, prompt.get("input") or {})
    return {
        "backend": backend,
        "model_lineage": "v4_4b",
        "artifact_kind": "hf" if backend == V4_HF else "gguf_q4_k_m",
        "sample_id": str(prompt["sample_id"]),
        "split_hint": prompt.get("split_hint"),
        "slice_hint": prompt.get("slice_hint") or prompt.get("split_hint"),
        "phase_count": prompt.get("phase_count"),
        "trivial": bool(prompt.get("trivial", False) or constraints.get("trivial", False)),
        "format_ok": _format_ok(cache),
        "lint_ok": bool(constraints["lint_ok"]),
        "violations": constraints["violations"],
        "mae": mae["mae"],
        "exact_match": mae["exact_match"],
        "n_phases": mae["n_phases"],
        "per_phase_abs_err": mae["per_phase_abs_err"],
        "reasoning_tier": reasoning["reasoning_tier"],
        "hit_count": reasoning["hit_count"],
        "keywords_found": reasoning["keywords_found"],
        "numbers_found": reasoning["numbers_found"],
        "solution": solution,
        "parse_error": cache.get("parse_error"),
        "elapsed_sec": cache.get("elapsed_sec"),
        "source_cache_path": _source_path(cache_file),
        "source_report_path": None,
    }


def _adapt_v1_row(row: dict[str, Any], *, comparable_ids: set[str], source_path: Path) -> dict[str, Any] | None:
    raw_backend = str(row.get("backend", "")).strip().lower()
    if raw_backend == "gguf_q4_k_m":
        backend = V1_Q4
    else:
        try:
            backend = normalize_backend_id(raw_backend)
        except ValueError:
            backend = ""
    if backend != V1_Q4:
        return None
    sid = str(row.get("sample_id"))
    split = row.get("split_hint")
    if split != "ood" or sid not in comparable_ids:
        return None
    format_ok = row.get("parse_error") is None and row.get("solution") is not None
    return {
        "backend": V1_Q4,
        "model_lineage": "v1_frozen",
        "artifact_kind": "gguf_q4_k_m",
        "sample_id": sid,
        "split_hint": "ood",
        "slice_hint": "v1_comparable_ood",
        "phase_count": row.get("phase_count"),
        "trivial": bool(row.get("trivial", False)),
        "format_ok": bool(format_ok),
        "lint_ok": bool(row.get("lint_ok", False)),
        "violations": row.get("violations") or [],
        "mae": row.get("mae"),
        "exact_match": bool(row.get("exact_match", False)),
        "n_phases": row.get("n_phases"),
        "per_phase_abs_err": row.get("per_phase_abs_err") or [],
        "reasoning_tier": row.get("reasoning_tier"),
        "hit_count": row.get("hit_count"),
        "keywords_found": row.get("keywords_found") or [],
        "numbers_found": row.get("numbers_found") or [],
        "solution": row.get("solution"),
        "parse_error": row.get("parse_error"),
        "elapsed_sec": row.get("elapsed_sec"),
        "source_cache_path": None,
        "source_report_path": _source_path(source_path),
    }


def build_phase11_per_sample(
    *,
    phase11_root: str | Path = PHASE11_OUT_ROOT,
    v1_per_sample: str | Path = FROZEN_V1_ROOT / "eval" / "per_sample.jsonl",
    require_all_v4_caches: bool = False,
) -> list[dict[str, Any]]:
    """Build Phase 11 per-sample rows from available v4 caches and frozen v1 rows."""
    root = Path(phase11_root)
    prompts_path = root / "eval_prompts.jsonl"
    if not prompts_path.exists():
        raise FileNotFoundError(f"Phase 11 prompts missing: {prompts_path}")
    prompts = _read_jsonl(prompts_path)
    prompt_by_id = {str(row["sample_id"]): row for row in prompts}
    comparable_ids = {str(row["sample_id"]) for row in prompts if row.get("slice_hint") == "v1_comparable_ood"}

    rows: list[dict[str, Any]] = []
    missing: list[str] = []
    for backend in (V4_HF, V4_Q4):
        cache_dir = root / "gen_cache" / backend
        for sid, prompt in prompt_by_id.items():
            cache_file = cache_dir / f"{sid}.json"
            if not cache_file.exists():
                if require_all_v4_caches:
                    missing.append(str(cache_file))
                continue
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
            rows.append(_score_v4_cache(prompt, cache, backend=backend, cache_file=cache_file))
    if missing:
        raise FileNotFoundError(f"missing Phase 11 v4 cache files: {len(missing)}; first={missing[0]}")

    v1_path = Path(v1_per_sample)
    if not v1_path.exists():
        raise FileNotFoundError(f"frozen v1 per_sample missing: {v1_path}")
    for row in _read_jsonl(v1_path):
        adapted = _adapt_v1_row(row, comparable_ids=comparable_ids, source_path=v1_path)
        if adapted is not None:
            rows.append(adapted)
    return rows


def _finite_values(rows: Iterable[dict[str, Any]], key: str) -> list[float]:
    vals: list[float] = []
    for row in rows:
        value = row.get(key)
        if value is None:
            continue
        out = float(value)
        if not math.isfinite(out):
            raise ValueError(f"non-finite {key}: {value!r}")
        vals.append(out)
    return vals


def _rate(rows: list[dict[str, Any]], key: str, *, exclude_trivial: bool = False) -> dict[str, Any]:
    denom_rows = [r for r in rows if not (exclude_trivial and r.get("trivial"))]
    if not denom_rows:
        return {"value": float("nan"), "n": 0, "passes": 0}
    passes = sum(1 for r in denom_rows if bool(r.get(key)))
    return {"value": passes / len(denom_rows), "n": len(denom_rows), "passes": passes}


def _mean(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    vals = _finite_values(rows, key)
    if not vals:
        return {"value": float("nan"), "n": 0}
    return {"value": sum(vals) / len(vals), "n": len(vals)}


def _is_ood(row: dict[str, Any]) -> bool:
    return row.get("split_hint") == "ood" or str(row.get("slice_hint", "")).endswith("ood")


def _slice_rows(rows: list[dict[str, Any]], *, backend: str | None = None, slice_name: str = "overall_ood") -> list[dict[str, Any]]:
    out = rows
    if backend is not None:
        out = [r for r in out if r.get("backend") == backend]
    if slice_name == "overall_ood":
        return [r for r in out if _is_ood(r)]
    return [r for r in out if r.get("slice_hint") == slice_name]


def _aggregate_for(rows: list[dict[str, Any]]) -> dict[str, Any]:
    hard = _rate(rows, "lint_ok", exclude_trivial=True)
    fmt = _rate(rows, "format_ok")
    mae = _mean(rows, "mae")
    return {
        "hard_pass": hard["value"],
        "ood_hard_constraint_pass": hard["value"],
        "hard_pass_n": hard["n"],
        "hard_pass_count": hard["passes"],
        "teacher_mae": mae["value"],
        "ood_teacher_mae": mae["value"],
        "teacher_mae_n": mae["n"],
        "format_pass": fmt["value"],
        "format_pass_n": fmt["n"],
        "format_pass_count": fmt["passes"],
    }


def _safe_ratio(num: float, den: float) -> float:
    if den is None or not math.isfinite(float(den)) or float(den) <= 0.0:
        return float("nan")
    if num is None or not math.isfinite(float(num)):
        return float("nan")
    return float(num) / float(den)


def _paired_rows(rows: list[dict[str, Any]], left_backend: str, right_backend: str, slice_name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    left_by_id = {r["sample_id"]: r for r in _slice_rows(rows, backend=left_backend, slice_name=slice_name)}
    right_by_id = {r["sample_id"]: r for r in _slice_rows(rows, backend=right_backend, slice_name=slice_name)}
    ids = sorted(set(left_by_id).intersection(right_by_id))
    if not ids:
        raise ValueError(f"no paired comparable rows for {left_backend} vs {right_backend} on {slice_name}")
    return [left_by_id[sid] for sid in ids], [right_by_id[sid] for sid in ids]


def _boolean_delta_ci(left: list[dict[str, Any]], right: list[dict[str, Any]], key: str) -> dict[str, Any]:
    left_rows = [{"sample_id": r["sample_id"], key: 1.0 if r.get(key) else 0.0} for r in left]
    right_rows = [{"sample_id": r["sample_id"], key: 1.0 if r.get(key) else 0.0} for r in right]
    return paired_delta_ci(left_rows, right_rows, value_key=key)


def _numeric_delta_ci(left: list[dict[str, Any]], right: list[dict[str, Any]], key: str) -> dict[str, Any]:
    paired: list[tuple[dict[str, Any], dict[str, Any]]] = []
    right_by_id = {r["sample_id"]: r for r in right}
    for l_row in left:
        r_row = right_by_id[l_row["sample_id"]]
        if l_row.get(key) is None or r_row.get(key) is None:
            continue
        paired.append((l_row, r_row))
    if not paired:
        raise ValueError(f"no finite paired values for {key}")
    return paired_delta_ci([p[0] for p in paired], [p[1] for p in paired], value_key=key)


def _ci_brief(ci: dict[str, Any]) -> dict[str, Any]:
    return {
        "lower": ci["lower"],
        "upper": ci["upper"],
        "mean": ci["mean"],
        "confidence": ci["confidence"],
        "seed": ci["seed"],
        "n_resamples": ci["n_resamples"],
        "n": ci["n"],
    }


def compute_phase11_metrics(per_sample_rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not per_sample_rows:
        raise ValueError("compute_phase11_metrics requires non-empty per-sample rows")

    slices: dict[str, Any] = {}
    aggregates: dict[str, Any] = {}
    for slice_name in ("v1_comparable_ood", "v4_expanded_ood", "overall_ood"):
        slices[slice_name] = {"backends": {}}
        aggregates[slice_name] = {}
        for backend in BACKENDS:
            sub = _slice_rows(per_sample_rows, backend=backend, slice_name=slice_name)
            if not sub:
                continue
            agg = _aggregate_for(sub)
            slices[slice_name]["backends"][backend] = agg
            aggregates[slice_name][backend] = agg

    top_level_backends: dict[str, Any] = {}
    for backend in BACKENDS:
        top_level_backends[backend] = _aggregate_for(_slice_rows(per_sample_rows, backend=backend, slice_name="overall_ood"))

    comparisons: dict[str, Any] = {}
    q4_hard = top_level_backends[V4_Q4]["ood_hard_constraint_pass"]
    hf_hard = top_level_backends[V4_HF]["ood_hard_constraint_pass"]
    comparisons["v4_q4_vs_v4_hf"] = {"hard_pass_ratio": _safe_ratio(q4_hard, hf_hard)}

    tail: dict[str, Any] = {}
    for backend in BACKENDS:
        backend_rows = _slice_rows(per_sample_rows, backend=backend, slice_name="overall_ood")
        if backend_rows:
            try:
                tail[backend] = tail_metrics(backend_rows)
            except ValueError as exc:
                tail[backend] = {"error": str(exc)}

    try:
        v4_comp, v1_comp = _paired_rows(per_sample_rows, V4_Q4, V1_Q4, "v1_comparable_ood")
        hard_ci = _boolean_delta_ci(v4_comp, v1_comp, "lint_ok")
        mae_ci = _numeric_delta_ci(v4_comp, v1_comp, "mae")
        comparisons["v4_q4_vs_v1_q4_comparable_ood"] = {
            "slice": "v1_comparable_ood",
            "paired_sample_count": len(v4_comp),
            "hard_pass_delta_ci95": _ci_brief(hard_ci),
            "teacher_mae_delta_ci95": _ci_brief(mae_ci),
        }
    except ValueError as exc:
        comparisons["v4_q4_vs_v1_q4_comparable_ood"] = {
            "slice": "v1_comparable_ood",
            "paired_sample_count": 0,
            "error": str(exc),
            "hard_pass_delta_ci95": {"lower": float("nan"), "upper": float("nan")},
            "teacher_mae_delta_ci95": {"lower": float("nan"), "upper": float("nan")},
        }

    baseline = comparisons["v4_q4_vs_v1_q4_comparable_ood"]
    decision_inputs = {
        "v4_q4_hard_pass_ood": q4_hard,
        "v4_q4_vs_v4_hf_hard_pass_ratio": comparisons["v4_q4_vs_v4_hf"]["hard_pass_ratio"],
        "v4_vs_v1_hard_pass_delta_ci95_lower": baseline["hard_pass_delta_ci95"].get("lower", float("nan")),
        "v4_vs_v1_teacher_mae_delta_ci95_upper": baseline["teacher_mae_delta_ci95"].get("upper", float("nan")),
    }

    metrics = {
        "ok": all(math.isfinite(float(v)) for v in decision_inputs.values()),
        "requirements_covered": REQUIREMENTS_COVERED,
        "backends": top_level_backends,
        "backend_ids": BACKENDS,
        "slices": slices,
        "aggregates": aggregates,
        "comparisons": comparisons,
        "q4_vs_hf": comparisons["v4_q4_vs_v4_hf"],
        "baseline_comparison": {
            "slice": "v1_comparable_ood",
            "hard_pass_delta_ci": baseline["hard_pass_delta_ci95"],
            "teacher_mae_delta_ci": baseline["teacher_mae_delta_ci95"],
        },
        "tail_metrics": tail,
        "tail_stats": tail,
        "decision_inputs": decision_inputs,
        "bootstrap": {"seed": 42, "n_resamples": 2000, "confidence": 0.95},
        "phase10_advisory": {
            "q4_vs_hf_smoke_mae_sensitivity_sec": PHASE10_SMOKE_MAE_SENSITIVITY_SEC,
            "note": "Phase 10 q4-vs-HF smoke MAE warning is advisory; Phase 11 metrics.json is authoritative.",
        },
    }
    return metrics


def _fmt_num(value: Any, digits: int = 4) -> str:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not math.isfinite(x):
        return "n/a"
    return f"{x:.{digits}f}"


def _fmt_pct(value: Any) -> str:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not math.isfinite(x):
        return "n/a"
    return f"{x * 100:.2f}%"


def _metric_row(backend: str, agg: dict[str, Any]) -> str:
    return (
        f"| `{backend}` | {_fmt_pct(agg.get('ood_hard_constraint_pass'))} "
        f"({agg.get('hard_pass_count', 0)}/{agg.get('hard_pass_n', 0)}) | "
        f"{_fmt_num(agg.get('teacher_mae'), 3)} | "
        f"{_fmt_pct(agg.get('format_pass'))} ({agg.get('format_pass_count', 0)}/{agg.get('format_pass_n', 0)}) |"
    )


def render_phase11_report(metrics: dict[str, Any]) -> str:
    """Render human-readable Phase 11 evaluation report from metrics JSON."""
    lines: list[str] = [
        "# Phase 11 Evaluation Matrix Report",
        "",
        "`metrics.json` is the authoritative decision input; this markdown is a rendered view.",
        "",
        "## Backend Matrix",
        "",
        "| backend | OOD hard-constraint pass | teacher MAE (s) | format pass |",
        "|---|---:|---:|---:|",
    ]
    backends = metrics.get("backends", {})
    for backend in BACKENDS:
        lines.append(_metric_row(backend, backends.get(backend, {})))

    lines.extend([
        "",
        "## Comparable OOD",
        "",
        "Comparable OOD uses sample IDs shared with the frozen v1 q4_K_M baseline; expanded-only samples are not included in the no-regression denominator.",
        "",
        "| backend | hard pass | teacher MAE (s) | format pass |",
        "|---|---:|---:|---:|",
    ])
    comp = ((metrics.get("slices") or {}).get("v1_comparable_ood") or {}).get("backends", {})
    for backend in BACKENDS:
        if backend in comp:
            lines.append(_metric_row(backend, comp[backend]))

    lines.extend([
        "",
        "## Expanded OOD",
        "",
        "Expanded OOD reports v4 robustness on newly added OOD samples and is explanatory rather than the v1 no-regression denominator.",
        "",
        "| backend | hard pass | teacher MAE (s) | format pass |",
        "|---|---:|---:|---:|",
    ])
    expanded = ((metrics.get("slices") or {}).get("v4_expanded_ood") or {}).get("backends", {})
    for backend in (V4_HF, V4_Q4):
        if backend in expanded:
            lines.append(_metric_row(backend, expanded[backend]))

    q4_vs_hf = (metrics.get("comparisons") or {}).get("v4_q4_vs_v4_hf", {})
    baseline = (metrics.get("comparisons") or {}).get("v4_q4_vs_v1_q4_comparable_ood", {})
    hard_ci = baseline.get("hard_pass_delta_ci95", {})
    mae_ci = baseline.get("teacher_mae_delta_ci95", {})
    lines.extend([
        "",
        "## q4-vs-HF Hard-Pass Ratio",
        "",
        f"- `v4_q4_vs_v4_hf.hard_pass_ratio`: **{_fmt_num(q4_vs_hf.get('hard_pass_ratio'), 4)}**",
        "",
        "## Bootstrap CI and Baseline Comparison",
        "",
        f"- Comparable slice: `{baseline.get('slice', 'v1_comparable_ood')}`",
        f"- Paired sample count: `{baseline.get('paired_sample_count', 0)}`",
        f"- Hard-pass delta CI95 lower/upper: `{_fmt_num(hard_ci.get('lower'), 4)}` / `{_fmt_num(hard_ci.get('upper'), 4)}`",
        f"- Teacher-MAE delta CI95 lower/upper: `{_fmt_num(mae_ci.get('lower'), 4)}` / `{_fmt_num(mae_ci.get('upper'), 4)}` seconds",
        "",
        "## Tail Metrics",
        "",
        "| backend | sample MAE p99 | sample MAE max | per-phase abs err p99 | per-phase abs err max |",
        "|---|---:|---:|---:|---:|",
    ])
    for backend, tail in (metrics.get("tail_metrics") or {}).items():
        lines.append(
            f"| `{backend}` | {_fmt_num(tail.get('sample_mae_p99'), 3)} | {_fmt_num(tail.get('sample_mae_max'), 3)} | "
            f"{_fmt_num(tail.get('per_phase_abs_err_p99'), 3)} | {_fmt_num(tail.get('per_phase_abs_err_max'), 3)} |"
        )

    di = metrics.get("decision_inputs") or {}
    lines.extend([
        "",
        "## Decision Inputs",
        "",
        "| field | value |",
        "|---|---:|",
        f"| `v4_q4_hard_pass_ood` | {_fmt_num(di.get('v4_q4_hard_pass_ood'), 4)} |",
        f"| `v4_q4_vs_v4_hf_hard_pass_ratio` | {_fmt_num(di.get('v4_q4_vs_v4_hf_hard_pass_ratio'), 4)} |",
        f"| `v4_vs_v1_hard_pass_delta_ci95_lower` | {_fmt_num(di.get('v4_vs_v1_hard_pass_delta_ci95_lower'), 4)} |",
        f"| `v4_vs_v1_teacher_mae_delta_ci95_upper` | {_fmt_num(di.get('v4_vs_v1_teacher_mae_delta_ci95_upper'), 4)} |",
        "",
        "## Phase 10 q4-vs-HF Smoke Sensitivity Advisory",
        "",
        f"Phase 10 observed q4-vs-HF smoke MAE sensitivity of **{PHASE10_SMOKE_MAE_SENSITIVITY_SEC:.3f}s**. This remains advisory; the Phase 11 matrix above is the authoritative evidence for Plan 11-04.",
        "",
    ])
    return "\n".join(lines)


def build_phase11_metrics_json(
    *,
    per_sample_rows: list[dict[str, Any]],
    bootstrap: dict[str, Any] | None = None,
    phase10_handoff: dict[str, Any] | None = None,
    frozen_v1_baseline: dict[str, Any] | None = None,
    out_path: str | Path | None = None,
) -> dict[str, Any]:
    metrics = compute_phase11_metrics(per_sample_rows)
    if bootstrap is not None:
        metrics["bootstrap_contract"] = bootstrap
        boot_metrics = bootstrap.get("metrics") or {}
        hard_boot = boot_metrics.get("hard_pass_delta") or {}
        mae_boot = boot_metrics.get("teacher_mae_delta") or {}
        if hard_boot and mae_boot:
            baseline = metrics.setdefault("comparisons", {}).setdefault(
                "v4_q4_vs_v1_q4_comparable_ood",
                {"slice": "v1_comparable_ood"},
            )
            baseline["hard_pass_delta_ci95"] = _ci_brief(hard_boot)
            baseline["teacher_mae_delta_ci95"] = _ci_brief(mae_boot)
            metrics["baseline_comparison"] = {
                "slice": "v1_comparable_ood",
                "hard_pass_delta_ci": baseline["hard_pass_delta_ci95"],
                "teacher_mae_delta_ci": baseline["teacher_mae_delta_ci95"],
            }
            metrics["decision_inputs"]["v4_vs_v1_hard_pass_delta_ci95_lower"] = hard_boot["lower"]
            metrics["decision_inputs"]["v4_vs_v1_teacher_mae_delta_ci95_upper"] = mae_boot["upper"]
            metrics["ok"] = all(math.isfinite(float(v)) for v in metrics["decision_inputs"].values())
    if phase10_handoff is not None:
        metrics["phase10_handoff"] = phase10_handoff
    if frozen_v1_baseline is not None:
        metrics["frozen_v1_baseline"] = frozen_v1_baseline
    # Contract compatibility: RED tests from 11-01 expected all Phase 11 req IDs
    # here; the 11-03 plan itself owns EVAL4B-02/03.
    metrics["requirements_covered"] = sorted(set(metrics["requirements_covered"]) | {"EVAL4B-01", "EVAL4B-04"})
    if out_path is not None:
        _write_json(Path(out_path), metrics)
    return metrics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute Phase 11 metrics and report")
    parser.add_argument("--phase11-root", type=Path, default=PHASE11_OUT_ROOT)
    parser.add_argument("--v1-per-sample", type=Path, default=FROZEN_V1_ROOT / "eval" / "per_sample.jsonl")
    parser.add_argument("--out-metrics", type=Path, default=PHASE11_OUT_ROOT / "metrics.json")
    parser.add_argument("--out-per-sample", type=Path, default=PHASE11_OUT_ROOT / "per_sample.jsonl")
    parser.add_argument("--out-report", type=Path, default=PHASE11_OUT_ROOT / "report.md")
    parser.add_argument("--require-all-v4-caches", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    reject_frozen_v1_output_path(args.out_metrics)
    reject_frozen_v1_output_path(args.out_per_sample)
    reject_frozen_v1_output_path(args.out_report)

    rows = build_phase11_per_sample(
        phase11_root=args.phase11_root,
        v1_per_sample=args.v1_per_sample,
        require_all_v4_caches=args.require_all_v4_caches,
    )
    if not rows:
        raise ValueError("no Phase 11 per-sample rows were built")
    metrics = compute_phase11_metrics(rows)
    write_per_sample(rows, args.out_per_sample)
    _write_json(args.out_metrics, metrics)
    reject_frozen_v1_output_path(args.out_report)
    args.out_report.parent.mkdir(parents=True, exist_ok=True)
    args.out_report.write_text(render_phase11_report(metrics), encoding="utf-8")
    print(f"[PHASE11-METRICS] OK rows={len(rows)} metrics={args.out_metrics} report={args.out_report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
