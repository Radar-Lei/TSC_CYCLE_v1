"""Deterministic EVL dataset selector for the evaluation suite (Phase 06).

Reads ``data/labeled.jsonl`` and picks ``--n-id`` (default 300) + ``--n-ood``
(default 300) records using ``random.Random(seed=42)`` so the three wave-2
generation backends (HF / GGUF bf16 / GGUF q4_K_M) consume an *identical*
prompt set. Output goes to ``runs/<TS>/eval/eval_prompts.jsonl``.

Determinism guarantees:

* Single ``random.Random(42)`` (Plan 06-01 spec; differs from 05-02 which split
  the seed across two buckets — here we honour the plan literally and rely on
  the bucket *ordering* being stable via sample_id sort.)
* Each bucket is sorted by ``sample_id`` before sampling so filesystem
  iteration order does not perturb the result.
* Output JSON is written with ``sort_keys=False`` and a fixed key order so
  byte-level reproducibility (md5) holds across reruns.

Schema (per output line)::

    {
      "sample_id": str,
      "split_hint": "id" | "ood",
      "input": dict,                # full input record (incl. prediction)
      "teacher_solution": dict,     # phase_id (str) -> green seconds (int)
      "phase_count": int,           # = len(input.prediction.phase_waits)
      "trivial": bool,
    }
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Iterator


def _iter_records(labeled_path: Path) -> Iterator[dict]:
    with labeled_path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(
                    f"[EVAL-PROMPTS] malformed json at {labeled_path}:{line_no}: {exc}"
                ) from exc


def _phase_count(input_record: dict[str, Any]) -> int:
    """Return number of phases in the input.

    Plan-spec fallback chain: ``input["phases"]`` → ``input["phase_min_green"]``
    → (actual schema) ``input["prediction"]["phase_waits"]``. The first two
    keys do not exist in the current Phase 3 output, so the third path is the
    real one; we keep all three for forward compatibility.
    """
    if "phases" in input_record:
        return len(input_record["phases"])
    if "phase_min_green" in input_record:
        return len(input_record["phase_min_green"])
    prediction = input_record.get("prediction") or {}
    waits = prediction.get("phase_waits") or []
    return len(waits)


def select_eval_records(
    labeled_path: Path,
    n_id: int,
    n_ood: int,
    seed: int,
) -> tuple[list[dict], list[dict]]:
    id_pool: list[dict] = []
    ood_pool: list[dict] = []
    for record in _iter_records(labeled_path):
        split = record.get("split_hint")
        if split == "id":
            id_pool.append(record)
        elif split == "ood":
            ood_pool.append(record)

    if len(id_pool) < n_id:
        print(
            f"[EVAL-PROMPTS] insufficient id samples: have {len(id_pool)}, need {n_id}",
            file=sys.stderr,
        )
        sys.exit(2)
    if len(ood_pool) < n_ood:
        print(
            f"[EVAL-PROMPTS] insufficient ood samples: have {len(ood_pool)}, need {n_ood}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Stable bucket ordering before random.sample so that filesystem-driven
    # iteration order cannot affect the chosen subset.
    id_pool.sort(key=lambda r: r.get("sample_id", ""))
    ood_pool.sort(key=lambda r: r.get("sample_id", ""))

    rng = random.Random(seed)
    id_picked = rng.sample(id_pool, n_id)
    ood_picked = rng.sample(ood_pool, n_ood)
    return id_picked, ood_picked


def _project_record(record: dict) -> dict:
    """Project a labeled-record into the EVL line schema (fixed key order)."""
    input_rec = record.get("input") or {}
    result = record.get("result") or {}
    teacher_solution = result.get("solution")
    return {
        "sample_id": record["sample_id"],
        "split_hint": record["split_hint"],
        "input": input_rec,
        "teacher_solution": teacher_solution,
        "phase_count": _phase_count(input_rec),
        "trivial": bool(record.get("trivial", False)),
    }


def write_jsonl(out_path: Path, records: list[dict]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for record in records:
            # sort_keys=False preserves the explicit insertion order in
            # _project_record, which is part of the determinism contract.
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=False))
            fh.write("\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labeled", type=Path, default=Path("data/labeled.jsonl"))
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("runs/20260507T032419Z/eval/eval_prompts.jsonl"),
    )
    parser.add_argument("--n-id", type=int, default=300)
    parser.add_argument("--n-ood", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    id_picked, ood_picked = select_eval_records(
        labeled_path=args.labeled,
        n_id=args.n_id,
        n_ood=args.n_ood,
        seed=args.seed,
    )

    # Plan 06-01: id 在前 ood 在后；不要 shuffle 混合。
    selected = [_project_record(r) for r in id_picked] + [
        _project_record(r) for r in ood_picked
    ]
    write_jsonl(args.out, selected)

    print(
        f"[EVAL-PROMPTS] OK n_id={len(id_picked)} n_ood={len(ood_picked)} out={args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
