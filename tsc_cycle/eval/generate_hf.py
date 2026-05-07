"""HF bf16 generation runner for the EVL eval suite.

Loads the merged_bf16 HF model **once**, runs deterministic greedy decoding
over `eval_prompts.jsonl`, and writes one JSON file per sample under
``gen_cache/hf_bf16/{sample_id}.json``. Resumable: existing cache files are
skipped without reloading the model when nothing remains to generate.

Invoked via ``python -m tsc_cycle.eval.generate_hf`` inside a
``scripts/dgx_spark/run_safe.sh`` wrapper. The script exits cleanly so that
CUDA / unified memory is fully released before the next wave-2/3 plan runs.

Reuses ``tsc_cycle.student.parity_hf._hf_generate`` as the greedy decode
template (do_sample=False, temperature=0.0, top_k=1, n_predict=384).
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from tsc_cycle.prompt_builder import build_user_prompt, parse_assistant_output
from tsc_cycle.student.parity_hf import _hf_generate


def _load_records(prompts_path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in prompts_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="HF bf16 EVL generation runner (single backend, exits to free GPU)"
    )
    ap.add_argument(
        "--merged-hf",
        default="runs/20260507T032419Z/merged_bf16",
        help="Path to merged_bf16 HF directory",
    )
    ap.add_argument(
        "--prompts",
        default="runs/20260507T032419Z/eval/eval_prompts.jsonl",
        help="Frozen eval prompts JSONL (sample_id, split_hint, input, ...)",
    )
    ap.add_argument(
        "--cache-dir",
        default="runs/20260507T032419Z/eval/gen_cache/hf_bf16",
        help="Per-sample JSON cache directory (idempotent, resumable)",
    )
    ap.add_argument("--n-predict", type=int, default=384)
    args = ap.parse_args()

    prompts_path = Path(args.prompts)
    if not prompts_path.exists():
        print(f"[GEN-HF] FAIL: prompts file missing: {prompts_path}", file=sys.stderr)
        return 2

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    records = _load_records(prompts_path)
    n_total = len(records)
    todo = [r for r in records if not (cache_dir / f"{r['sample_id']}.json").exists()]
    n_cached = n_total - len(todo)
    print(
        f"[GEN-HF] resume: {n_cached} cached, {len(todo)} to generate (total={n_total})",
        file=sys.stderr,
    )

    if not todo:
        print(f"[GEN-HF] OK all-cached n={n_total}")
        return 0

    print(f"[GEN-HF] loading merged_bf16 from {args.merged_hf}", file=sys.stderr)
    tok = AutoTokenizer.from_pretrained(args.merged_hf)
    model = AutoModelForCausalLM.from_pretrained(
        args.merged_hf,
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
        device_map={"": 0},
    )
    model.eval()
    torch.manual_seed(42)

    n_todo = len(todo)
    t0 = time.time()
    n_done = 0
    n_err = 0

    with torch.inference_mode():
        for i, rec in enumerate(todo, 1):
            sid = rec["sample_id"]
            split = rec.get("split_hint", "?")
            try:
                user_prompt = build_user_prompt(rec["input"])
                text = _hf_generate(model, tok, user_prompt, args.n_predict)
                _, sol = parse_assistant_output(text)
                err = None if sol is not None else "solution_unparseable"
                out = {
                    "sample_id": sid,
                    "split_hint": split,
                    "backend": "hf_bf16",
                    "solution": sol,
                    "parse_error": err,
                    "raw_text": text,
                    "n_predict": args.n_predict,
                    "seed": 42,
                }
            except Exception as exc:  # pragma: no cover — defensive, single-sample isolation
                n_err += 1
                out = {
                    "sample_id": sid,
                    "split_hint": split,
                    "backend": "hf_bf16",
                    "solution": None,
                    "parse_error": f"exception: {type(exc).__name__}: {exc}",
                    "raw_text": "",
                    "n_predict": args.n_predict,
                    "seed": 42,
                }

            (cache_dir / f"{rec['sample_id']}.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            n_done += 1
            if i % 10 == 0 or i == n_todo:
                elapsed = time.time() - t0
                rate = i / elapsed if elapsed > 0 else 0.0
                eta = (n_todo - i) / rate if rate > 0 else 0.0
                print(
                    f"[GEN-HF] progress {i}/{n_todo} elapsed={elapsed:.1f}s "
                    f"rate={rate:.2f}/s eta={eta:.0f}s err={n_err}",
                    file=sys.stderr,
                )

    total_sec = time.time() - t0
    print(
        f"[GEN-HF] OK generated={n_done} total_cached={n_cached + n_done} "
        f"errors={n_err} total_sec={total_sec:.1f}"
    )

    # Explicit GPU release before exit (paranoid; subprocess exit also frees).
    del model
    del tok
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
