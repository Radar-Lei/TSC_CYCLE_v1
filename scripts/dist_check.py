"""KS test report for sampled inputs vs reality.log empirical distribution.

Writes data/dist_check_report.md.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from scipy import stats  # type: ignore[import-not-found]

from tsc_cycle.distribution_fit import iter_prompts


def collect_log_values(log_path: Path) -> dict[str, list[float]]:
    out: dict[str, list[float]] = defaultdict(list)
    for _crossing, pred in iter_prompts(log_path):
        for w in pred.get("prediction", {}).get("phase_waits", []):
            for k in ("min_green", "max_green", "capacity", "pred_wait", "pred_saturation"):
                v = w.get(k)
                if isinstance(v, (int, float)):
                    out[k].append(float(v))
    return dict(out)


def collect_jsonl_values(path: Path) -> dict[str, list[float]]:
    out: dict[str, list[float]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        for w in obj.get("prediction", {}).get("phase_waits", []):
            for k in ("min_green", "max_green", "capacity", "pred_wait", "pred_saturation"):
                v = w.get(k)
                if isinstance(v, (int, float)):
                    out[k].append(float(v))
    return dict(out)


def ks_report(label: str, sample: dict[str, list[float]], reference: dict[str, list[float]]) -> list[dict]:
    rows = []
    for k in sorted(sample):
        s = sample[k]
        r = reference.get(k, [])
        if not s or not r:
            rows.append({"field": k, "n_sample": len(s), "n_ref": len(r), "ks": None, "p": None})
            continue
        ks_stat, p_val = stats.ks_2samp(s, r)
        rows.append({
            "field": k,
            "n_sample": len(s),
            "n_ref": len(r),
            "ks": float(ks_stat),
            "p": float(p_val),
            "label": label,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default="data/inputs.jsonl")
    ap.add_argument("--ood", default="data/ood_inputs.jsonl")
    ap.add_argument("--log", default="reality.log")
    ap.add_argument("--out", default="data/dist_check_report.md")
    args = ap.parse_args()

    ref = collect_log_values(Path(args.log))
    id_vals = collect_jsonl_values(Path(args.id))
    ood_vals = collect_jsonl_values(Path(args.ood))

    id_rows = ks_report("same_dist", id_vals, ref)
    ood_rows = ks_report("ood", ood_vals, ref)

    # OOD per-sample dimension summary
    ood_dim_count: dict[str, int] = defaultdict(int)
    for line in Path(args.ood).read_text(encoding="utf-8").splitlines():
        obj = json.loads(line)
        for d in obj.get("ood_dims", []):
            ood_dim_count[d] += 1

    lines = [
        "# Distribution Check Report",
        "",
        f"Reference: `{args.log}`",
        f"Same-dist: `{args.id}` ({sum(r['n_sample'] for r in id_rows[:1])} samples worth of values per field)",
        f"OOD:       `{args.ood}`",
        "",
        "## Same-dist KS test (target: p > 0.05 on every field)",
        "",
        "| Field | n_sample | n_ref | KS | p-value | pass |",
        "|---|---|---|---|---|---|",
    ]
    for r in id_rows:
        passed = "✓" if r.get("p") is not None and r["p"] > 0.05 else "✗"
        lines.append(f"| {r['field']} | {r['n_sample']} | {r['n_ref']} | {r.get('ks'):.4f} | {r.get('p'):.4g} | {passed} |"
                     if r.get("p") is not None else
                     f"| {r['field']} | {r['n_sample']} | {r['n_ref']} | – | – | – |")

    lines += [
        "",
        "## OOD KS test (target: at least one field with p < 0.01 OR per-sample ood_dims marker)",
        "",
        "| Field | n_sample | n_ref | KS | p-value | OOD? |",
        "|---|---|---|---|---|---|",
    ]
    for r in ood_rows:
        is_ood = "✓" if r.get("p") is not None and r["p"] < 0.01 else "·"
        lines.append(f"| {r['field']} | {r['n_sample']} | {r['n_ref']} | {r.get('ks'):.4f} | {r.get('p'):.4g} | {is_ood} |"
                     if r.get("p") is not None else
                     f"| {r['field']} | {r['n_sample']} | {r['n_ref']} | – | – | – |")

    lines += [
        "",
        "## OOD per-dimension activation count",
        "",
        "| Dimension | Samples |",
        "|---|---|",
    ]
    for k, v in sorted(ood_dim_count.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {k} | {v} |")

    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(f"same-dist passing fields: {sum(1 for r in id_rows if r.get('p') and r['p'] > 0.05)}/{len(id_rows)}")
    print(f"OOD distinguishing fields: {sum(1 for r in ood_rows if r.get('p') and r['p'] < 0.01)}/{len(ood_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
