"""Concurrent GPT-5.5 high teacher labeler.

Phase 2 hardening keeps v1.0 labels immutable while labeling only isolated
candidate inputs. The orchestration is append-only and resume-safe: done IDs
from accepted, rejected, and excluded JSONL files are skipped before any API
submission.
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
from typing import Callable

from tsc_cycle.constraint_lint import validate
from tsc_cycle.prompt_builder import build_user_prompt
from tsc_cycle.teacher.client import TeacherClient

# GPT-5.5 high pricing (USD per 1M tokens) — placeholder estimate; user can override
PRICE_INPUT_PER_M = float(os.environ.get("GPT5_5_INPUT_PER_M", "1.25"))
PRICE_OUTPUT_PER_M = float(os.environ.get("GPT5_5_OUTPUT_PER_M", "10.00"))
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTECTED_LABELED = (PROJECT_ROOT / "data" / "labeled.jsonl").resolve()


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


def _worker_count(value: str) -> int:
    workers = int(value)
    if workers > 10:
        raise argparse.ArgumentTypeError("workers must be <= 10")
    if workers < 1:
        raise argparse.ArgumentTypeError("workers must be >= 1")
    return workers


def _resolve_for_guard(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (PROJECT_ROOT / path).resolve()


def _is_protected_labeled_path(path: Path) -> bool:
    return _resolve_for_guard(path) == PROTECTED_LABELED


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default="data/inputs.jsonl")
    ap.add_argument("--ood-inputs", default="data/ood_inputs.jsonl")
    ap.add_argument("--input-files", nargs="+", default=None)
    ap.add_argument("--exclude-labeled", nargs="*", default=[])
    ap.add_argument("--cache-dir", default="raw_responses")
    ap.add_argument("--labeled", default="data/labeled.jsonl")
    ap.add_argument("--rejected", default="data/rejected.jsonl")
    ap.add_argument("--cost-out", default="runs/latest/teacher_cost.json")
    ap.add_argument("--reject-stats", default="runs/latest/teacher_reject_stats.json")
    ap.add_argument("--workers", type=_worker_count, default=10)
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit; useful for 50-sample smoke")
    ap.add_argument("--model", default="gpt-5.5")
    ap.add_argument("--effort", default="high")
    return ap


def _input_paths(args: argparse.Namespace) -> list[Path]:
    if args.input_files:
        return [Path(p) for p in args.input_files]
    return [Path(args.inputs), Path(args.ood_inputs)]


def run_labeling(
    args: argparse.Namespace,
    *,
    client_factory: Callable[..., TeacherClient] = TeacherClient,
) -> int:
    labeled_path = Path(args.labeled)
    rejected_path = Path(args.rejected)

    if _is_protected_labeled_path(labeled_path):
        print("ERROR: refusing to write protected data/labeled.jsonl", file=sys.stderr)
        raise ValueError("refusing to write protected data/labeled.jsonl")

    if args.workers > 10:
        print("ERROR: workers must be <= 10", file=sys.stderr)
        return 2

    if client_factory is TeacherClient and not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY is not set; aborting.", file=sys.stderr)
        return 2

    Path(args.cost_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.reject_stats).parent.mkdir(parents=True, exist_ok=True)
    labeled_path.parent.mkdir(parents=True, exist_ok=True)
    rejected_path.parent.mkdir(parents=True, exist_ok=True)

    all_inputs: list[dict] = []
    for path in _input_paths(args):
        all_inputs.extend(_read_jsonl(path))

    done = _read_done_ids(
        labeled_path,
        rejected_path,
        *(Path(p) for p in getattr(args, "exclude_labeled", []) or []),
    )
    pending = [s for s in all_inputs if s["sample_id"] not in done]
    if args.limit:
        pending = pending[: args.limit]
    print(f"total inputs: {len(all_inputs)}; done: {len(done)}; pending: {len(pending)}")

    client = client_factory(
        model=args.model,
        reasoning_effort=args.effort,
        cache_dir=Path(args.cache_dir),
    )

    lab_lock = threading.Lock()
    rej_lock = threading.Lock()

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
            "source": s.get("source"),
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

    with labeled_path.open("a", encoding="utf-8") as lab_f, rejected_path.open("a", encoding="utf-8") as rej_f:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(process, s) for s in pending]
            for i, fut in enumerate(as_completed(futs)):
                r = fut.result()
                rec = r["record"]
                u = (rec["result"].get("usage") or {})
                total_input_tokens += u.get("input_tokens", 0) or 0
                total_completion_tokens += u.get("output_tokens", 0) or 0
                rsn = ((u.get("output_tokens_details") or {}).get("reasoning_tokens") or 0)
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
                    print(
                        f"[{i+1}/{len(futs)}] ok={n_ok} rej={n_rej} "
                        f"rsn_avg={total_reasoning_tokens/max(n_ok+n_rej,1):.0f} "
                        f"elapsed={time.time()-t0:.0f}s"
                    )

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
    Path(args.reject_stats).write_text(json.dumps(dict(reject_kinds), indent=2), encoding="utf-8")
    print(f"\nDONE: ok={n_ok}/{len(pending)} ({n_ok/max(len(pending),1)*100:.1f}%), rej={n_rej} ({cost['reject_rate']*100:.1f}%)")
    print(f"~$ {cost['estimated_usd_total']:.2f}; wallclock {elapsed/60:.1f}min")
    return 0 if cost["reject_rate"] < 0.20 else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_labeling(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
