"""Eval metrics orchestrator (plan 06-05).

Reads:
  - eval_prompts.jsonl  (sample_id, input, teacher_solution, phase_count, trivial, split_hint)
  - gen_cache/{backend}/{sample_id}.json  for each backend in BACKENDS

Writes:
  - per_sample.jsonl  (one row per sample × backend; 600 × 3 = 1800)
  - report.md  with sections:
      ## Summary
      ## Constraint Satisfaction
      ## Teacher MAE
      ## OOD Gap
      ## Reasoning Quality
      ## Latency p99
      ## Top-20 Failure Cases
      ## Quantization Degradation

Strict integer math for MAE; trivial samples excluded from constraint denominator.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from tsc_cycle.eval.metrics_constraints import score_constraint
from tsc_cycle.eval.metrics_mae import score_mae
from tsc_cycle.eval.metrics_ood_gap import compute_ood_gap
from tsc_cycle.eval.metrics_reasoning import score_reasoning

BACKENDS = ["hf_bf16", "gguf_bf16", "gguf_q4_k_m"]
SPLITS = ["id", "ood"]
PHASE_BUCKETS = [2, 3, 4, 5, 6]


# ---------------------------- aggregation helpers ---------------------------- #

def _rate(rows: list[dict], key: str, exclude_trivial: bool = False) -> tuple[float, int]:
    if exclude_trivial:
        rows = [r for r in rows if not r.get("trivial")]
    if not rows:
        return float("nan"), 0
    return sum(1 for r in rows if r.get(key)) / len(rows), len(rows)


def _mean_mae(rows: list[dict]) -> tuple[float, int]:
    vals = [r["mae"] for r in rows if r.get("mae") is not None]
    if not vals:
        return float("nan"), 0
    return sum(vals) / len(vals), len(vals)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    idx = min(len(s) - 1, int(p * len(s)))
    return s[idx]


def _fmt_pct(x: float) -> str:
    return f"{x*100:.1f}%" if not math.isnan(x) else "n/a"


def _fmt_float(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}" if not math.isnan(x) else "n/a"


# ---------------------------- main pipeline ---------------------------- #

def build_per_sample(prompts: dict[str, dict], cache_root: Path) -> list[dict]:
    rows: list[dict] = []
    for backend in BACKENDS:
        backend_dir = cache_root / backend
        for sid, prompt in prompts.items():
            cache_file = backend_dir / f"{sid}.json"
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
            sol = cache.get("solution")
            raw = cache.get("raw_text", "") or ""
            c = score_constraint(prompt["input"], sol)
            m = score_mae(sol, prompt["teacher_solution"])
            r = score_reasoning(raw, prompt["input"])
            rows.append({
                "sample_id": sid,
                "backend": backend,
                "split_hint": prompt["split_hint"],
                "phase_count": prompt["phase_count"],
                "trivial": prompt["trivial"],
                "solution": sol,
                "parse_error": cache.get("parse_error"),
                "elapsed_sec": cache.get("elapsed_sec"),
                "lint_ok": c["lint_ok"],
                "violations": c["violations"],
                "mae": m["mae"],
                "exact_match": m["exact_match"],
                "n_phases": m["n_phases"],
                "per_phase_abs_err": m["per_phase_abs_err"],
                "reasoning_tier": r["reasoning_tier"],
                "hit_count": r["hit_count"],
                "keywords_found": r["keywords_found"],
                "numbers_found": r["numbers_found"],
            })
    return rows


def write_per_sample(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


# ---------------------------- report sections ---------------------------- #

def _section_summary(rows: list[dict]) -> str:
    n_total = len(rows)
    n_samples = len({r["sample_id"] for r in rows})
    backends = sorted({r["backend"] for r in rows})
    splits = sorted({r["split_hint"] for r in rows})
    return (
        "## Summary\n\n"
        f"- per-sample rows: **{n_total}** ({n_samples} samples × {len(backends)} backends)\n"
        f"- backends: {', '.join(backends)}\n"
        f"- splits: {', '.join(splits)}\n"
        f"- metrics: constraint_satisfaction, teacher_mae+exact_match, "
        f"ood_gap, reasoning_tier, latency_p99\n"
    )


def _section_constraint(rows: list[dict]) -> str:
    out = ["## Constraint Satisfaction",
           "",
           "Hard-constraint pass rate (trivial samples — `min==max` for all phases — excluded).",
           "",
           "| backend | split | lint_ok rate | n (non-trivial) |",
           "|---|---|---|---|"]
    for backend in BACKENDS:
        for split in SPLITS:
            sub = [r for r in rows if r["backend"] == backend and r["split_hint"] == split]
            rate, n = _rate(sub, "lint_ok", exclude_trivial=True)
            out.append(f"| {backend} | {split} | {_fmt_pct(rate)} | {n} |")
    out.append("")
    out.append("### Phase-count buckets (non-trivial, both splits combined)")
    out.append("")
    out.append("| backend | " + " | ".join(f"phases={pc}" for pc in PHASE_BUCKETS) + " |")
    out.append("|---|" + "|".join("---" for _ in PHASE_BUCKETS) + "|")
    for backend in BACKENDS:
        cells = []
        for pc in PHASE_BUCKETS:
            sub = [r for r in rows if r["backend"] == backend and r["phase_count"] == pc]
            rate, n = _rate(sub, "lint_ok", exclude_trivial=True)
            cells.append(f"{_fmt_pct(rate)} (n={n})")
        out.append(f"| {backend} | " + " | ".join(cells) + " |")
    out.append("")
    return "\n".join(out)


def _section_mae(rows: list[dict]) -> str:
    out = ["## Teacher MAE",
           "",
           "Mean of `abs(int(student_phase) - int(teacher_phase))` averaged per sample, "
           "then averaged across samples. Samples with mae=None (unparseable / missing phase) "
           "excluded from MAE denominator.",
           "",
           "| backend | split | mean MAE (s) | n (mae available) | exact_match rate | n (all) |",
           "|---|---|---|---|---|---|"]
    for backend in BACKENDS:
        for split in SPLITS:
            sub = [r for r in rows if r["backend"] == backend and r["split_hint"] == split]
            mae, n_mae = _mean_mae(sub)
            em_rate, n_em = _rate(sub, "exact_match", exclude_trivial=False)
            out.append(
                f"| {backend} | {split} | {_fmt_float(mae)} | {n_mae} | "
                f"{_fmt_pct(em_rate)} | {n_em} |"
            )
    out.append("")
    return "\n".join(out)


def _section_ood_gap(rows: list[dict]) -> str:
    out = ["## OOD Gap",
           "",
           "`gap = id - ood`. For rate metrics positive gap = OOD degradation; "
           "for MAE positive gap = OOD numerically worse (mean MAE higher on OOD → ood>id → gap negative).",
           "",
           "| backend | metric | id | ood | gap (id - ood) |",
           "|---|---|---|---|---|"]
    for backend in BACKENDS:
        for metric in ["lint_ok", "exact_match", "mae"]:
            g = compute_ood_gap(rows, backend, metric)
            fmt = _fmt_pct if metric in ("lint_ok", "exact_match") else _fmt_float
            out.append(
                f"| {backend} | {metric} | {fmt(g['id'])} | {fmt(g['ood'])} | {fmt(g['gap'])} |"
            )
    out.append("")
    return "\n".join(out)


def _section_reasoning(rows: list[dict]) -> str:
    out = ["## Reasoning Quality",
           "",
           "Rule-based tier from in-reasoning hits (KEYWORDS + min/max integers). "
           "0 → miss · 1-2 → partial · ≥3 → full.",
           "",
           "| backend | split | full | partial | miss | n |",
           "|---|---|---|---|---|---|"]
    for backend in BACKENDS:
        for split in SPLITS:
            sub = [r for r in rows if r["backend"] == backend and r["split_hint"] == split]
            n = len(sub)
            ctr = Counter(r["reasoning_tier"] for r in sub)
            full = ctr.get("full", 0) / n if n else float("nan")
            partial = ctr.get("partial", 0) / n if n else float("nan")
            miss = ctr.get("miss", 0) / n if n else float("nan")
            out.append(
                f"| {backend} | {split} | {_fmt_pct(full)} | {_fmt_pct(partial)} | "
                f"{_fmt_pct(miss)} | {n} |"
            )
    out.append("")
    return "\n".join(out)


def _section_latency(rows: list[dict]) -> str:
    out = ["## Latency p99",
           "",
           "Per-prompt wall time (seconds). hf_bf16 cache has no `elapsed_sec` field "
           "and is reported as N/A.",
           "",
           "| backend | n (with elapsed_sec) | mean (s) | p99 (s) |",
           "|---|---|---|---|"]
    for backend in BACKENDS:
        sub = [r["elapsed_sec"] for r in rows
               if r["backend"] == backend and r.get("elapsed_sec") is not None]
        if not sub:
            out.append(f"| {backend} | 0 | N/A | N/A |")
        else:
            mean_v = sum(sub) / len(sub)
            p99 = _percentile(sub, 0.99)
            out.append(f"| {backend} | {len(sub)} | {mean_v:.3f} | {p99:.3f} |")
    out.append("")
    return "\n".join(out)


def _section_top_failures(rows: list[dict]) -> str:
    # Failure if !lint_ok OR mae>5. Sort by (lint_ok asc → fails first), then mae desc.
    failed = [
        r for r in rows
        if (not r["lint_ok"]) or (r.get("mae") is not None and r["mae"] > 5)
    ]
    failed.sort(key=lambda r: (
        0 if not r["lint_ok"] else 1,
        -(r["mae"] if r.get("mae") is not None else 0.0),
    ))
    top = failed[:20]
    out = ["## Top-20 Failure Cases",
           "",
           "Failure = `lint_ok=False` OR `mae > 5`. Sorted: lint failures first, then by MAE desc.",
           "",
           f"Total failures: **{len(failed)}** / {len(rows)} rows.",
           "",
           "| sample_id | backend | split | violations | mae | exact_match |",
           "|---|---|---|---|---|---|"]
    if not top:
        out.append("| (none) | | | | | |")
    else:
        for r in top:
            sid = r["sample_id"][:12]
            viols = ",".join(r["violations"]) if r["violations"] else "-"
            mae = "n/a" if r.get("mae") is None else f"{r['mae']:.2f}"
            out.append(
                f"| `{sid}` | {r['backend']} | {r['split_hint']} | {viols} | "
                f"{mae} | {r['exact_match']} |"
            )
    out.append("")
    return "\n".join(out)


def _section_quantization(rows: list[dict]) -> str:
    out = ["## Quantization Degradation", ""]

    def metrics_for(backend: str, split: str) -> tuple[float, float, float]:
        sub = [r for r in rows if r["backend"] == backend and r["split_hint"] == split]
        lint, _ = _rate(sub, "lint_ok", exclude_trivial=True)
        mae, _ = _mean_mae(sub)
        em, _ = _rate(sub, "exact_match", exclude_trivial=False)
        return lint, mae, em

    paragraph: list[str] = []
    for split in SPLITS:
        bf16_lint, bf16_mae, bf16_em = metrics_for("gguf_bf16", split)
        q4_lint, q4_mae, q4_em = metrics_for("gguf_q4_k_m", split)
        d_lint = q4_lint - bf16_lint
        d_mae = q4_mae - bf16_mae
        d_em = q4_em - bf16_em
        paragraph.append(
            f"**Split={split}** — gguf_bf16 vs gguf_q4_k_m: "
            f"lint_ok Δ={_fmt_pct(d_lint)} ({_fmt_pct(bf16_lint)} → {_fmt_pct(q4_lint)}); "
            f"MAE Δ={_fmt_float(d_mae)}s ({_fmt_float(bf16_mae)} → {_fmt_float(q4_mae)}); "
            f"exact_match Δ={_fmt_pct(d_em)} ({_fmt_pct(bf16_em)} → {_fmt_pct(q4_em)})."
        )

    # Verdict against Phase-5 known signal: q4_K_M MAE > 3s → degradation flag.
    q4_ood_mae, _ = _mean_mae([r for r in rows
                               if r["backend"] == "gguf_q4_k_m" and r["split_hint"] == "ood"])
    bf16_ood_mae, _ = _mean_mae([r for r in rows
                                 if r["backend"] == "gguf_bf16" and r["split_hint"] == "ood"])
    if not math.isnan(q4_ood_mae) and not math.isnan(bf16_ood_mae):
        delta = q4_ood_mae - bf16_ood_mae
        if delta > 3.0:
            verdict = (
                f"**Verdict (matches Phase-5 signal):** q4_K_M OOD MAE exceeds gguf_bf16 by "
                f"{delta:.2f}s (>3s threshold) → quantization degradation **confirmed**; "
                f"recommend `--imatrix` re-quantization in plan 06-06."
            )
        else:
            verdict = (
                f"**Verdict:** q4_K_M OOD MAE delta = {delta:.2f}s (<3s threshold) → "
                f"quantization degradation within tolerance; no imatrix re-quantization required."
            )
    else:
        verdict = "**Verdict:** insufficient mae-available samples to score quantization delta."

    out.extend(paragraph)
    out.append("")
    out.append(verdict)
    out.append("")
    return "\n".join(out)


def write_report(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sections = [
        _section_summary(rows),
        _section_constraint(rows),
        _section_mae(rows),
        _section_ood_gap(rows),
        _section_reasoning(rows),
        _section_latency(rows),
        _section_top_failures(rows),
        _section_quantization(rows),
    ]
    path.write_text("\n".join(sections) + "\n", encoding="utf-8")


# ---------------------------- CLI ---------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--cache-root", required=True)
    ap.add_argument("--out-jsonl", required=True)
    ap.add_argument("--out-report", required=True)
    args = ap.parse_args()

    prompts_path = Path(args.prompts)
    cache_root = Path(args.cache_root)
    out_jsonl = Path(args.out_jsonl)
    out_report = Path(args.out_report)

    prompts: dict[str, dict[str, Any]] = {}
    for line in prompts_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        prompts[obj["sample_id"]] = obj
    assert len(prompts) == 600, f"expected 600 prompts, got {len(prompts)}"

    rows = build_per_sample(prompts, cache_root)
    expected = 600 * len(BACKENDS)
    assert len(rows) == expected, f"expected {expected} rows, got {len(rows)}"

    write_per_sample(rows, out_jsonl)
    write_report(rows, out_report)

    print(f"[METRICS] OK per_sample={len(rows)} report={out_report}")


if __name__ == "__main__":
    main()
