"""Merge HF / GGUF-bf16 / GGUF-q4 parity JSONs into a single report.

Reads three independent backend output JSONs (written by parity_hf and
parity_gguf), aligns by ``sample_id``, computes per-prompt and overall
mean absolute error of q4 vs HF bf16 final-green decisions, and writes
``parity_report.json``.

If ``overall_mae_q4_vs_hf`` exceeds ``--mae-threshold``, appends a flag
line to STATE.md as a backlog reminder (imatrix re-quantize candidate).

Exit code 0 unless parse failures > 25%, in which case 1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_results(path: Path) -> tuple[dict[str, dict], dict[str, Any]]:
    """Load a backend JSON; return (by_sample_id, raw)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {r["sample_id"]: r for r in raw["results"]}, raw


def _phase_mae(a: dict[str, int] | None, b: dict[str, int] | None) -> float | None:
    if a is None or b is None:
        return None
    common = sorted(set(a.keys()) & set(b.keys()))
    if not common:
        return None
    diffs = [abs(int(a[k]) - int(b[k])) for k in common]
    return sum(diffs) / len(diffs)


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge three parity backend JSONs into a report")
    ap.add_argument("--hf-json", default="runs/20260507T032419Z/gguf/parity_hf.json")
    ap.add_argument("--bf16-json", default="runs/20260507T032419Z/gguf/parity_gguf_bf16.json")
    ap.add_argument("--q4-json", default="runs/20260507T032419Z/gguf/parity_gguf_q4.json")
    ap.add_argument("--out", default="runs/20260507T032419Z/gguf/parity_report.json")
    ap.add_argument("--mae-threshold", type=float, default=3.0)
    ap.add_argument("--state-md", default=".planning/STATE.md")
    args = ap.parse_args()

    hf_by_id, hf_raw = _load_results(Path(args.hf_json))
    bf16_by_id, bf16_raw = _load_results(Path(args.bf16_json))
    q4_by_id, q4_raw = _load_results(Path(args.q4_json))

    sample_ids = list(hf_by_id.keys())  # preserve HF order (id-first then ood)
    n = len(sample_ids)

    per_prompt: list[dict] = []
    parse_failures: list[dict] = []
    for sid in sample_ids:
        hf_r = hf_by_id.get(sid, {})
        bf_r = bf16_by_id.get(sid, {})
        q4_r = q4_by_id.get(sid, {})
        hf_sol = hf_r.get("solution")
        bf_sol = bf_r.get("solution")
        q4_sol = q4_r.get("solution")

        if hf_sol is None or q4_sol is None:
            parse_failures.append({
                "sample_id": sid,
                "split_hint": hf_r.get("split_hint"),
                "hf_parse_error": hf_r.get("parse_error"),
                "bf16_parse_error": bf_r.get("parse_error"),
                "q4_parse_error": q4_r.get("parse_error"),
            })
            # still record the row but with mae=None for traceability
            mae_q4 = None
            mae_bf16 = None
        else:
            mae_q4 = _phase_mae(q4_sol, hf_sol)
            mae_bf16 = _phase_mae(bf_sol, hf_sol)

        per_prompt.append({
            "sample_id": sid,
            "split_hint": hf_r.get("split_hint"),
            "hf_solution": hf_sol,
            "bf16_solution": bf_sol,
            "q4_solution": q4_sol,
            "mae_q4_vs_hf": mae_q4,
            "mae_bf16_vs_hf": mae_bf16,
            "hf_tail": hf_r.get("tail", "")[-200:],
            "bf16_tail": bf_r.get("tail", "")[-200:],
            "q4_tail": q4_r.get("tail", "")[-200:],
        })

    valid_q4 = [r["mae_q4_vs_hf"] for r in per_prompt if r["mae_q4_vs_hf"] is not None]
    valid_bf16 = [r["mae_bf16_vs_hf"] for r in per_prompt if r["mae_bf16_vs_hf"] is not None]
    overall_mae_q4 = sum(valid_q4) / len(valid_q4) if valid_q4 else float("nan")
    overall_mae_bf16 = sum(valid_bf16) / len(valid_bf16) if valid_bf16 else float("nan")
    mae_exceeded = (overall_mae_q4 == overall_mae_q4) and overall_mae_q4 > args.mae_threshold  # NaN-safe

    report = {
        "n_prompts": n,
        "n_parse_failures": len(parse_failures),
        "parse_failures": parse_failures,
        "overall_mae_q4_vs_hf": overall_mae_q4,
        "overall_mae_bf16_vs_hf": overall_mae_bf16,
        "mae_threshold": args.mae_threshold,
        "mae_exceeded": bool(mae_exceeded),
        "per_prompt": per_prompt,
        "timing": {
            "hf_total_sec": hf_raw.get("total_sec"),
            "gguf_bf16_total_sec": bf16_raw.get("total_sec"),
            "gguf_q4_total_sec": q4_raw.get("total_sec"),
        },
        "backends": {
            "hf": {"merged_hf": hf_raw.get("merged_hf"), "n_predict": hf_raw.get("n_predict")},
            "gguf_bf16": {"gguf_path": bf16_raw.get("gguf_path"), "ngl": bf16_raw.get("ngl")},
            "gguf_q4": {"gguf_path": q4_raw.get("gguf_path"), "ngl": q4_raw.get("ngl")},
        },
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[PARITY-MERGE] wrote {out_path} overall_mae_q4_vs_hf={overall_mae_q4:.3f} parse_failures={len(parse_failures)}")

    if mae_exceeded:
        state_md = Path(args.state_md)
        flag_line = f"- [FLAG] Phase 5 parity MAE q4 vs hf = {overall_mae_q4:.2f}s (>{args.mae_threshold:.1f}s); backlog: imatrix re-quantize.\n"
        if state_md.exists():
            with state_md.open("a", encoding="utf-8") as fh:
                fh.write(flag_line)
            print(f"[PARITY-MERGE] FLAG appended to {state_md}: {flag_line.strip()}", file=sys.stderr)
        else:
            print(f"[PARITY-MERGE] FLAG (no STATE.md to append): {flag_line.strip()}", file=sys.stderr)

    fail_ratio = len(parse_failures) / n if n else 0.0
    if fail_ratio > 0.25:
        print(f"[PARITY-MERGE] FAIL: parse_failure ratio {fail_ratio:.2%} > 25%", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
