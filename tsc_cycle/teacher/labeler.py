"""Concurrent teacher labeler — Phase 3.

Reads inputs.jsonl + ood_inputs.jsonl, calls GPT-5.5 high (≤10 worker), validates
each response via constraint_lint, and writes:
  - data/labeled.jsonl   — accepted samples
  - data/rejected.jsonl  — failed samples (validation OR API error OR usage gate)
  - raw_responses/*.json — content-addressed cache (already written by client)
  - runs/{ts}/teacher_cost.json — usage / $ / time aggregates
  - runs/{ts}/teacher_reject_stats.json — reject distribution

Resume-safe: every successful sample is appended to labeled.jsonl as soon as it
returns; reject is appended on failure. On restart we read labeled+rejected
sample_ids and skip them. Cache prevents re-spending tokens for repeated keys.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tsc_cycle.constraint_lint import validate
from tsc_cycle.prompt_builder import build_user_prompt
from tsc_cycle.teacher.client import TeacherClient

# GPT-5.5 high pricing (USD per 1M tokens) — placeholder estimate; user can override
PRICE_INPUT_PER_M = float(os.environ.get("GPT5_5_INPUT_PER_M", "1.25"))
PRICE_OUTPUT_PER_M = float(os.environ.get("GPT5_5_OUTPUT_PER_M", "10.00"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_done_ids(*paths: Path) -> set[str]:
    ids: set[str] = set()
    for p in paths:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                if "sample_id" in obj:
                    ids.add(obj["sample_id"])
            except json.JSONDecodeError:
                continue
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default="data/inputs.jsonl")
    ap.add_argument("--ood-inputs", default="data/ood_inputs.jsonl")
    ap.add_argument("--labeled", default="data/labeled.jsonl")
    ap.add_argument("--rejected", default="data/rejected.jsonl")
    ap.add_argument("--cost-out", default="runs/latest/teacher_cost.json")
    ap.add_argument("--reject-stats", default="runs/latest/teacher_reject_stats.json")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit; useful for 50-sample smoke")
    ap.add_argument("--model", default="gpt-5.5")
    ap.add_argument("--effort", default="high")
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set; aborting.", file=sys.stderr)
        return 2

    Path(args.cost_out).parent.mkdir(parents=True, exist_ok=True)

    # Load all inputs (id + ood). Skip already-done sample_ids.
    in_id = _read_jsonl(Path(args.inputs))
    in_ood = _read_jsonl(Path(args.ood_inputs))
    all_inputs = in_id + in_ood

    done = _read_done_ids(Path(args.labeled), Path(args.rejected))
    pending = [s for s in all_inputs if s["sample_id"] not in done]
    if args.limit:
        pending = pending[: args.limit]
    print(f"total inputs: {len(all_inputs)}; done: {len(done)}; pending: {len(pending)}")

    client = TeacherClient(model=args.model, reasoning_effort=args.effort)

    lab_lock = threading.Lock()
    rej_lock = threading.Lock()
    lab_f = open(args.labeled, "a", encoding="utf-8")
    rej_f = open(args.rejected, "a", encoding="utf-8")

    reject_kinds: Counter[str] = Counter()
    total_input_tokens = 0
    total_completion_tokens = 0
    total_reasoning_tokens = 0
    n_ok = 0
    n_rej = 0
    t0 = time.time()

    def process(s: dict) -> dict:
        prompt = build_user_prompt(s)
        res = client.call(prompt)
        record = {
            "sample_id": s["sample_id"],
            "split_hint": s.get("split_hint", "id"),
            "trivial": s.get("trivial", False),
            "ood_dims": s.get("ood_dims", []),
            "input": s,
            "result": res.to_dict(),
        }
        if not res.success:
            record["reject_reason"] = res.error or "api_failure"
            return {"ok": False, "record": record, "reject_kind": "api_or_usage"}
        cl = validate(s, res.solution or {})
        if not cl.ok:
            record["reject_reason"] = "constraint_violation"
            record["violations"] = cl.violations
            return {"ok": False, "record": record, "reject_kind": cl.violations[0]["kind"] if cl.violations else "unknown"}
        return {"ok": True, "record": record, "reject_kind": None}

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(process, s) for s in pending]
            for i, fut in enumerate(as_completed(futs)):
                r = fut.result()
                rec = r["record"]
                u = (rec["result"].get("usage") or {})
                total_input_tokens += u.get("prompt_tokens", 0) or 0
                total_completion_tokens += u.get("completion_tokens", 0) or 0
                rsn = ((u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
                total_reasoning_tokens += rsn
                if r["ok"]:
                    with lab_lock:
                        lab_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        lab_f.flush()
                    n_ok += 1
                else:
                    reject_kinds[r["reject_kind"] or "unknown"] += 1
                    with rej_lock:
                        rej_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        rej_f.flush()
                    n_rej += 1
                if (i + 1) % 25 == 0 or (i + 1) == len(futs):
                    print(f"[{i+1}/{len(futs)}] ok={n_ok} rej={n_rej} "
                          f"rsn_avg={total_reasoning_tokens/max(n_ok+n_rej,1):.0f} "
                          f"elapsed={time.time()-t0:.0f}s")
    finally:
        lab_f.close()
        rej_f.close()

    elapsed = time.time() - t0
    cost_in = total_input_tokens / 1_000_000 * PRICE_INPUT_PER_M
    cost_out = total_completion_tokens / 1_000_000 * PRICE_OUTPUT_PER_M
    cost = {
        "model": args.model,
        "effort": args.effort,
        "elapsed_s": elapsed,
        "n_ok": n_ok,
        "n_rej": n_rej,
        "reject_rate": n_rej / max(n_ok + n_rej, 1),
        "input_tokens": total_input_tokens,
        "completion_tokens": total_completion_tokens,
        "reasoning_tokens": total_reasoning_tokens,
        "estimated_usd_input": cost_in,
        "estimated_usd_output": cost_out,
        "estimated_usd_total": cost_in + cost_out,
    }
    Path(args.cost_out).write_text(json.dumps(cost, indent=2), encoding="utf-8")
    Path(args.reject_stats).parent.mkdir(parents=True, exist_ok=True)
    Path(args.reject_stats).write_text(json.dumps(dict(reject_kinds), indent=2), encoding="utf-8")
    print(f"\nDONE: ok={n_ok}/{len(pending)} ({n_ok/max(len(pending),1)*100:.1f}%), rej={n_rej} ({cost['reject_rate']*100:.1f}%)")
    print(f"~$ {cost['estimated_usd_total']:.2f}; wallclock {elapsed/60:.1f}min")
    return 0 if cost["reject_rate"] < 0.20 else 1


if __name__ == "__main__":
    raise SystemExit(main())
