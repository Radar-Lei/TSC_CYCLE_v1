"""5-prompt teacher smoke test.

Pulls 5 prompts from `data/dist_prior.json` (or builds them from per_position
modes if needed), calls GPT-5.5 high, validates each via constraint_lint, and
extrapolates 3000-sample budget.

Pre-requisites:
  - OPENAI_API_KEY is set in env.
  - `data/dist_prior.json` exists.

Usage:
  python scripts/teacher_smoke.py [--n 5] [--model gpt-5.5]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

from tsc_cycle.constraint_lint import validate
from tsc_cycle.prompt_builder import build_user_prompt
from tsc_cycle.teacher.client import TeacherClient


def synth_input(seed: int, prior: dict) -> dict:
    rng = random.Random(seed)
    pc = list(map(int, prior["phase_count_distribution"].keys()))
    pc_w = list(prior["phase_count_distribution"].values())
    n_phase = rng.choices(pc, weights=pc_w, k=1)[0]

    waits = []
    range_modes = prior["range_modes_top"]
    for i in range(n_phase):
        rmode = rng.choices(range_modes, weights=[r["count"] for r in range_modes], k=1)[0]
        # Sample pred_saturation / pred_wait from per_position[i] if available
        per_pos = prior["per_position"].get(str(i), {})
        sat_vals = (per_pos.get("pred_saturation", {}) or {}).get("values_sample") or [0.05]
        wait_vals = (per_pos.get("pred_wait", {}) or {}).get("values_sample") or [1.0]
        cap_vals = (per_pos.get("capacity", {}) or {}).get("values_sample") or [40]
        waits.append({
            "phase_id": i + 1,
            "pred_wait": rng.choice(wait_vals),
            "pred_saturation": rng.choice(sat_vals),
            "min_green": rmode["min_green"],
            "max_green": rmode["max_green"],
            "capacity": rng.choice(cap_vals),
        })
    return {"prediction": {"as_of": "2026-04-27 00:00:00", "phase_waits": waits}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--model", default="gpt-5.5")
    ap.add_argument("--prior", default="data/dist_prior.json")
    ap.add_argument("--out", default="runs/teacher_smoke.json")
    ap.add_argument("--effort", default="high")
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set; aborting smoke test.", file=sys.stderr)
        return 2

    prior = json.loads(Path(args.prior).read_text(encoding="utf-8"))
    inputs = [synth_input(seed=i, prior=prior) for i in range(args.n)]

    client = TeacherClient(model=args.model, reasoning_effort=args.effort)

    results = []
    valid = 0
    total_rsn_tokens = 0
    total_completion_tokens = 0
    total_input_tokens = 0
    t0 = time.time()
    for i, inp in enumerate(inputs):
        prompt = build_user_prompt(inp)
        res = client.call(prompt)
        ok = res.success
        constraint_ok = False
        if ok and res.solution is not None:
            cl = validate(inp, res.solution)
            constraint_ok = cl.ok
            if cl.ok:
                valid += 1
        u = res.usage or {}
        rsn_toks = ((u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0)
        ctok = u.get("completion_tokens", 0)
        ptok = u.get("prompt_tokens", 0)
        total_rsn_tokens += rsn_toks or 0
        total_completion_tokens += ctok or 0
        total_input_tokens += ptok or 0
        print(f"[{i+1}/{args.n}] success={ok} constraints={constraint_ok} "
              f"rsn_tokens={rsn_toks} elapsed={res.elapsed_s:.1f}s")
        if not ok:
            print(f"    error: {res.error}")
        results.append({
            "input": inp,
            "result": res.to_dict(),
            "constraints_ok": constraint_ok,
        })
    elapsed = time.time() - t0

    avg_rsn = total_rsn_tokens / max(args.n, 1)
    avg_completion = total_completion_tokens / max(args.n, 1)
    avg_input = total_input_tokens / max(args.n, 1)

    # Extrapolate 3000-sample budget
    extrap = {
        "n": args.n,
        "valid": valid,
        "elapsed_s": elapsed,
        "avg_per_call_s": elapsed / max(args.n, 1),
        "extrapolated_3000_wallclock_s": (elapsed / max(args.n, 1)) * 3000,
        "avg_reasoning_tokens": avg_rsn,
        "avg_completion_tokens": avg_completion,
        "avg_input_tokens": avg_input,
        "extrapolated_3000_input_tokens": avg_input * 3000,
        "extrapolated_3000_completion_tokens": avg_completion * 3000,
        "extrapolated_3000_reasoning_tokens": avg_rsn * 3000,
    }

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    payload = {"results": results, "extrap": extrap, "model": args.model, "effort": args.effort}
    Path(args.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("=== smoke summary ===")
    print(f"valid: {valid}/{args.n}")
    print(f"avg reasoning_tokens: {avg_rsn:.0f}  (TCH-02 requires > 100)")
    print(f"avg call: {extrap['avg_per_call_s']:.1f}s")
    print(f"extrapolate 3000 samples: ~{extrap['extrapolated_3000_wallclock_s']/60:.0f} min single-thread, "
          f"~{extrap['extrapolated_3000_wallclock_s']/600:.0f} min @ 10 worker")
    print(f"saved: {args.out}")

    if valid != args.n or avg_rsn < 100:
        print("WARNING: smoke did not fully pass — see results above")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
