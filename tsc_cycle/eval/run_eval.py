"""Phase 6 evaluation suite — three backends × four metrics × two splits.

Backends:
  - hf_bf16   : merged HF bf16 weights via transformers
  - gguf_bf16 : llama-cli on bf16 GGUF
  - gguf_q4   : llama-cli on q4_K_M GGUF

Metrics:
  - constraint_satisfaction (constraint_lint pass rate; phase_count buckets;
    trivial samples excluded)
  - teacher_mae / teacher_exact (vs hold-out teacher labels in val_id/val_ood)
  - ood_gap (id_metric - ood_metric)
  - reasoning_keyword (rule-based: pred_saturation / min_green / max_green / pred_wait)

Outputs:
  - runs/{ts}/eval/per_sample.jsonl
  - runs/{ts}/eval/report.md
  - runs/{ts}/eval/decision.md (go/no-go)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import torch

from tsc_cycle.constraint_lint import is_trivial, validate
from tsc_cycle.prompt_builder import (
    build_assistant_prefill,
    build_user_prompt,
    parse_assistant_output,
)

KEYWORDS = ("pred_saturation", "min_green", "max_green", "pred_wait")


def hf_generate(model, tokenizer, prompt: str, device: str = "cuda", max_new: int = 768) -> str:
    full = prompt + "\n" + build_assistant_prefill()
    enc = tokenizer(full, return_tensors="pt").to(device)
    out = model.generate(**enc, max_new_tokens=max_new, do_sample=False, temperature=0.0)
    new_ids = out[0][enc["input_ids"].shape[1]:]
    return build_assistant_prefill() + tokenizer.decode(new_ids, skip_special_tokens=False)


def gguf_generate(llama_cli: Path, gguf: Path, prompt: str, n_predict: int = 768) -> str:
    full = prompt + "\n" + build_assistant_prefill()
    cmd = [
        str(llama_cli), "-m", str(gguf), "-p", full,
        "-n", str(n_predict), "--temp", "0", "--top-k", "1", "--seed", "42",
        "--no-display-prompt",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=180)
    return build_assistant_prefill() + res.stdout


def reasoning_keyword_score(reasoning: str) -> float:
    """0..1 fraction of keywords that appear in the reasoning."""
    return sum(1 for k in KEYWORDS if k in reasoning) / len(KEYWORDS)


def aggregate_metrics(per_sample: list[dict], variant: str) -> dict:
    rows = [r for r in per_sample if r["variant"] == variant]
    out: dict = {
        "variant": variant,
        "n": len(rows),
        "by_split": {},
    }
    for split in ("val_id", "val_ood"):
        rs = [r for r in rows if r["split"] == split]
        rs_nontriv = [r for r in rs if not r["trivial"]]
        n = len(rs_nontriv)
        cs = sum(1 for r in rs_nontriv if r["constraint_ok"]) / n if n else 0.0
        mae = [r["teacher_mae"] for r in rs_nontriv if r["teacher_mae"] is not None]
        exact = sum(1 for r in rs_nontriv if r.get("teacher_exact")) / n if n else 0.0
        rk = sum(r["reasoning_keyword"] for r in rs_nontriv) / n if n else 0.0
        # Phase-count buckets
        bucket: dict[int, dict[str, float]] = defaultdict(lambda: {"n": 0, "ok": 0})
        for r in rs_nontriv:
            b = bucket[r["n_phase"]]
            b["n"] += 1
            b["ok"] += int(r["constraint_ok"])
        bucket_out = {str(k): {"n": v["n"], "satisfaction": v["ok"] / v["n"] if v["n"] else 0.0}
                      for k, v in sorted(bucket.items())}
        out["by_split"][split] = {
            "n_nontrivial": n,
            "constraint_satisfaction": cs,
            "teacher_mae_mean": (sum(mae) / len(mae)) if mae else None,
            "teacher_exact_rate": exact,
            "reasoning_keyword_mean": rk,
            "by_phase_count": bucket_out,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged-hf", required=True)
    ap.add_argument("--gguf-bf16", required=True)
    ap.add_argument("--gguf-q4", required=True)
    ap.add_argument("--labeled", default="data/labeled.jsonl")
    ap.add_argument("--tokenized-dir", default="data/tokenized")
    ap.add_argument("--llama-cli", default=os.environ.get("LLAMA_CLI", "/home/samuel/projects/EvoProgTSC/llama.cpp/llama-cli"))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--cache", default="gen_cache")
    ap.add_argument("--variants", nargs="+", default=["hf_bf16", "gguf_bf16", "gguf_q4"])
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = Path(args.cache)
    cache.mkdir(exist_ok=True)

    # Build sample_id → input + teacher_solution map from labeled.jsonl
    teacher_map: dict[str, dict] = {}
    for line in Path(args.labeled).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("result", {}).get("success") is False:
            continue
        teacher_map[rec["sample_id"]] = {
            "input": rec["input"],
            "teacher_solution": rec["result"]["solution"],
            "split_hint": rec["split_hint"],
        }

    # Use sample_ids from val_id and val_ood parquet to pick the eval set
    import pyarrow.parquet as pq
    eval_ids = {"val_id": [], "val_ood": []}
    for split in ("val_id", "val_ood"):
        t = pq.read_table(Path(args.tokenized_dir) / split / "data.parquet", columns=["sample_id", "trivial"])
        for sid, triv in zip(t["sample_id"].to_pylist(), t["trivial"].to_pylist()):
            eval_ids[split].append((sid, triv))
    print(f"eval set: val_id={len(eval_ids['val_id'])} val_ood={len(eval_ids['val_ood'])}")

    per_sample: list[dict] = []

    # --- HF bf16 ---
    if "hf_bf16" in args.variants:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        tok = AutoTokenizer.from_pretrained(args.merged_hf)
        model = AutoModelForCausalLM.from_pretrained(args.merged_hf, torch_dtype=torch.bfloat16,
                                                     attn_implementation="sdpa", device_map={"": 0})
        model.eval()
        for split, items in eval_ids.items():
            for sid, triv in items:
                if sid not in teacher_map:
                    continue
                cpath = cache / "hf_bf16" / f"{sid}.json"
                cpath.parent.mkdir(parents=True, exist_ok=True)
                if cpath.exists():
                    out = json.loads(cpath.read_text(encoding="utf-8"))
                else:
                    inp = teacher_map[sid]["input"]
                    text = hf_generate(model, tok, build_user_prompt(inp))
                    rsn, sol = parse_assistant_output(text)
                    out = {"text": text, "reasoning": rsn, "solution": sol}
                    cpath.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
                per_sample.append(_eval_row("hf_bf16", split, sid, triv, teacher_map[sid], out))
        del model
        torch.cuda.empty_cache()

    # --- GGUF variants ---
    for variant, gguf_path in (("gguf_bf16", args.gguf_bf16), ("gguf_q4", args.gguf_q4)):
        if variant not in args.variants:
            continue
        for split, items in eval_ids.items():
            for sid, triv in items:
                if sid not in teacher_map:
                    continue
                cpath = cache / variant / f"{sid}.json"
                cpath.parent.mkdir(parents=True, exist_ok=True)
                if cpath.exists():
                    out = json.loads(cpath.read_text(encoding="utf-8"))
                else:
                    inp = teacher_map[sid]["input"]
                    text = gguf_generate(Path(args.llama_cli), Path(gguf_path), build_user_prompt(inp))
                    rsn, sol = parse_assistant_output(text)
                    out = {"text": text, "reasoning": rsn, "solution": sol}
                    cpath.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
                per_sample.append(_eval_row(variant, split, sid, triv, teacher_map[sid], out))

    # Save per_sample
    psf = out_dir / "per_sample.jsonl"
    with psf.open("w", encoding="utf-8") as f:
        for r in per_sample:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {psf} ({len(per_sample)} rows)")

    # Aggregates
    aggs = [aggregate_metrics(per_sample, v) for v in args.variants]

    report = ["# Phase 6 Eval Report", ""]
    for a in aggs:
        report += [f"## Variant: {a['variant']} (n={a['n']})", ""]
        for split, m in a["by_split"].items():
            report += [f"### split: {split}",
                       f"- n_nontrivial: {m['n_nontrivial']}",
                       f"- constraint_satisfaction: {m['constraint_satisfaction']:.3f}",
                       f"- teacher_mae_mean: {m['teacher_mae_mean']}",
                       f"- teacher_exact_rate: {m['teacher_exact_rate']:.3f}",
                       f"- reasoning_keyword_mean: {m['reasoning_keyword_mean']:.3f}",
                       f"- by_phase_count: {m['by_phase_count']}",
                       ""]
    (out_dir / "report.md").write_text("\n".join(report), encoding="utf-8")

    # Go/no-go: q4 OOD constraint_satisfaction ≥ 0.95 × hf_bf16 OOD constraint_satisfaction
    hf_a = next((a for a in aggs if a["variant"] == "hf_bf16"), None)
    q4_a = next((a for a in aggs if a["variant"] == "gguf_q4"), None)
    decision_lines = ["# Deployment decision (go/no-go)", ""]
    if hf_a and q4_a:
        hf_ood = hf_a["by_split"]["val_ood"]["constraint_satisfaction"]
        q4_ood = q4_a["by_split"]["val_ood"]["constraint_satisfaction"]
        ratio = q4_ood / hf_ood if hf_ood > 0 else 0
        go = ratio >= 0.95
        decision_lines += [
            f"hf_bf16 val_ood satisfaction: {hf_ood:.3f}",
            f"gguf_q4 val_ood satisfaction: {q4_ood:.3f}",
            f"ratio q4 / hf = {ratio:.3f} (gate: ≥ 0.95)",
            "",
            f"**Decision: {'GO' if go else 'NO-GO — fall back to fp16 GGUF or run imatrix recalibration'}**",
        ]
    else:
        decision_lines.append("Not enough variants present to issue a decision.")
    (out_dir / "decision.md").write_text("\n".join(decision_lines) + "\n", encoding="utf-8")

    print("wrote", out_dir / "report.md", out_dir / "decision.md")
    return 0


def _eval_row(variant: str, split: str, sid: str, trivial: bool, teacher: dict, out: dict) -> dict:
    inp = teacher["input"]
    sol = out["solution"]
    rsn = out.get("reasoning", "") or ""
    cl = validate(inp, sol or {})
    teacher_sol = teacher["teacher_solution"]
    mae = None
    exact = None
    if isinstance(sol, dict) and isinstance(teacher_sol, dict):
        keys = set(sol) & set(teacher_sol)
        if keys:
            mae = sum(abs(int(sol[k]) - int(teacher_sol[k])) for k in keys) / len(keys)
            exact = all(int(sol[k]) == int(teacher_sol[k]) for k in keys) and (set(sol) == set(teacher_sol))
    return {
        "variant": variant,
        "split": split,
        "sample_id": sid,
        "trivial": trivial,
        "n_phase": len(inp.get("prediction", {}).get("phase_waits", [])),
        "constraint_ok": cl.ok,
        "violations": cl.violations,
        "teacher_mae": mae,
        "teacher_exact": exact,
        "reasoning_keyword": reasoning_keyword_score(rsn),
    }


if __name__ == "__main__":
    raise SystemExit(main())
