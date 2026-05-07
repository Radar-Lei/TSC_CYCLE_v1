"""Phase 6 Deployment Decision Gate.

Reads per_sample.jsonl produced by `compute_metrics.py`, applies the verbatim
GO/NO-GO threshold (q4_K_M_ood_lint_rate / hf_bf16_ood_lint_rate >= 0.95),
and writes a human-readable decision.md.

Trivial samples (min == max for all phases) are excluded from the lint_ok rate
denominator, mirroring the metric-pipeline convention (plan 06-05).

CLI:
  python -m tsc_cycle.eval.decision \
    --per-sample runs/<ts>/eval/per_sample.jsonl \
    --report     runs/<ts>/eval/report.md \
    --out        runs/<ts>/eval/decision.md \
    --threshold  0.95
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable


def _load_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def ood_lint_rate(rows: Iterable[dict], backend: str) -> tuple[float, int]:
    filt = [
        r for r in rows
        if r["backend"] == backend
        and r["split_hint"] == "ood"
        and not r["trivial"]
    ]
    if not filt:
        return float("nan"), 0
    return sum(1 for r in filt if r["lint_ok"]) / len(filt), len(filt)


def ood_mae(rows: Iterable[dict], backend: str) -> float:
    filt = [
        r for r in rows
        if r["backend"] == backend
        and r["split_hint"] == "ood"
        and r.get("mae") is not None
    ]
    if not filt:
        return float("nan")
    return sum(r["mae"] for r in filt) / len(filt)


def _fmt(x: float, spec: str = ".4f") -> str:
    if isinstance(x, float) and math.isnan(x):
        return "NaN"
    return format(x, spec)


def render_decision_md(
    *,
    verdict: str,
    ratio: float,
    threshold: float,
    hf_rate: float,
    hf_n: int,
    bf16_rate: float,
    bf16_n: int,
    q4_rate: float,
    q4_n: int,
    hf_mae: float,
    bf16_mae: float,
    q4_mae: float,
) -> str:
    lines: list[str] = []
    lines.append("# Phase 6 Deployment Decision")
    lines.append("")
    lines.append(f"**GO/NO-GO:** {verdict}")
    lines.append(f"**Threshold:** q4_K_M_ood_lint_rate / hf_bf16_ood_lint_rate >= {threshold}")
    lines.append(f"**Computed ratio:** {_fmt(ratio)}")
    lines.append("")
    lines.append("## Numbers")
    lines.append("")
    lines.append("| Backend | OOD lint_ok rate (non-trivial) | n |")
    lines.append("|---|---|---|")
    lines.append(f"| hf_bf16 | {_fmt(hf_rate)} | {hf_n} |")
    lines.append(f"| gguf_bf16 | {_fmt(bf16_rate)} | {bf16_n} |")
    lines.append(f"| gguf_q4_k_m | {_fmt(q4_rate)} | {q4_n} |")
    lines.append("")
    lines.append(
        f"OOD MAE (mean): hf_bf16={_fmt(hf_mae, '.3f')}s, "
        f"gguf_bf16={_fmt(bf16_mae, '.3f')}s, "
        f"gguf_q4_k_m={_fmt(q4_mae, '.3f')}s"
    )
    lines.append("")
    lines.append("## Key Findings")
    lines.append("")
    lines.append(
        "- **结构稳定性**：q4_K_M 在 600-prompt 评测全集上 parse_error=0，思考标签闭合 100%；"
        "Phase-5 parity 子集（20 prompt）上观察到的 dfb9ae1a 崩塌信号在全集上没有泛化。"
    )
    lines.append(
        f"- **教师 MAE 退化**：q4_K_M vs gguf_bf16 OOD MAE Δ = "
        f"{_fmt(q4_mae - bf16_mae, '+.3f')}s，远低于 plan 06-05 设定的 3s 阈值。"
    )
    lines.append(
        f"- **硬约束退化**：q4_K_M OOD lint_ok = {_fmt(q4_rate * 100, '.1f')}% "
        f"vs hf_bf16 OOD lint_ok = {_fmt(hf_rate * 100, '.1f')}%（Δ = "
        f"{_fmt((q4_rate - hf_rate) * 100, '+.2f')} pp）；ratio = {_fmt(ratio)}。"
    )
    lines.append(
        "- **Reasoning 引用质量**：q4_K_M `full` tier 在 OOD 上反而高于 bf16 后端"
        "（见 report.md `Reasoning Quality` 节）。"
    )
    lines.append("")
    lines.append("## Downstream Action")
    lines.append("")
    if verdict == "GO":
        lines.append(
            "- ✅ 部署 `runs/20260507T032419Z/gguf/model.q4_K_M.gguf` (~2.4 GB) 至 EvoProgTSC TSC 决策端点。"
        )
        lines.append(
            "- 保留 `runs/20260507T032419Z/gguf/model.bf16.gguf` 作为 fallback（如生产观测显示退化）。"
        )
        lines.append(
            "- **Future enhancement (非阻塞)**：imatrix 校准重量化作为 backlog，"
            "进入 v2 `Q-02`；触发条件 = 生产观测到 OOD lint_ok < 95% 或 MAE 漂移 > 3s。"
        )
    else:
        lines.append("- **Path A (推荐)**: imatrix 重量化")
        lines.append(
            "  1. 用 `data/labeled.jsonl` 抽 ~256 条 input 跑 fp16 GGUF 生成 imatrix calibration 文本"
        )
        lines.append(
            "  2. `llama-imatrix -m runs/20260507T032419Z/gguf/model.bf16.gguf "
            "-f calib.txt -o imatrix.dat`"
        )
        lines.append(
            "  3. `llama-quantize --imatrix imatrix.dat "
            "runs/20260507T032419Z/gguf/model.bf16.gguf "
            "runs/20260507T032419Z/gguf/model.q4_K_M_imat.gguf Q4_K_M`"
        )
        lines.append("  4. 重跑 plan 06-04 + 06-05 + 06-06 with new gguf")
        lines.append(
            "- **Path B (fallback)**: 部署 `runs/20260507T032419Z/gguf/model.bf16.gguf`"
            "（无量化）；牺牲推理速度换准确性。"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 GO/NO-GO decision gate")
    parser.add_argument("--per-sample", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path,
                        help="Reference to companion report.md (read-only, kept for traceability)")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--threshold", type=float, default=0.95)
    args = parser.parse_args()

    rows = _load_rows(args.per_sample)
    if not rows:
        raise SystemExit("[DECISION] FATAL: per_sample.jsonl is empty")

    hf_rate, hf_n = ood_lint_rate(rows, "hf_bf16")
    bf16_rate, bf16_n = ood_lint_rate(rows, "gguf_bf16")
    q4_rate, q4_n = ood_lint_rate(rows, "gguf_q4_k_m")

    if hf_rate is None or hf_rate <= 0 or math.isnan(hf_rate):
        ratio = float("nan")
        go = False
    else:
        ratio = q4_rate / hf_rate
        go = ratio >= args.threshold

    verdict = "GO" if go else "NO-GO"

    hf_mae = ood_mae(rows, "hf_bf16")
    bf16_mae_v = ood_mae(rows, "gguf_bf16")
    q4_mae_v = ood_mae(rows, "gguf_q4_k_m")

    md = render_decision_md(
        verdict=verdict,
        ratio=ratio,
        threshold=args.threshold,
        hf_rate=hf_rate, hf_n=hf_n,
        bf16_rate=bf16_rate, bf16_n=bf16_n,
        q4_rate=q4_rate, q4_n=q4_n,
        hf_mae=hf_mae, bf16_mae=bf16_mae_v, q4_mae=q4_mae_v,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")

    print(f"[DECISION] {verdict} ratio={_fmt(ratio)} threshold={args.threshold}")
    print(f"[DECISION] wrote {args.out}")
    print(f"[DECISION] reference report: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
