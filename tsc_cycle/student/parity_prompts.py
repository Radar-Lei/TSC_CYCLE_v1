"""Deterministic parity prompt selector.

Reads ``data/labeled.jsonl`` (the teacher-labeled dataset produced by Phase 3),
samples a fixed (seed=42) set of N same-distribution + M OOD records based on the
``split_hint`` field, and writes them as a JSONL file consumed by Plan 03's parity
runner (``runs/<TS>/gguf/parity_prompts.jsonl``).

Why a frozen file: Plan 03 must compare HF / GGUF bf16 / GGUF q4_K_M on the
*identical* set of prompts to detect quantization regressions. The frozen file
also documents which sample_ids participated in the parity test (audit trail).

Determinism: two independent ``random.Random`` instances (seed and seed+1) sample
from the id and ood buckets respectively, so a small ood pool never silently
borrows from the id pool.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Iterator


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
                    f"[PARITY-PROMPTS] malformed json at {labeled_path}:{line_no}: {exc}"
                ) from exc


def select_parity_records(
    labeled_path: Path,
    n_id: int,
    n_ood: int,
    seed: int,
    exclude_trivial: bool,
) -> tuple[list[dict], list[dict]]:
    id_bucket: list[dict] = []
    ood_bucket: list[dict] = []
    for record in _iter_records(labeled_path):
        if exclude_trivial and record.get("trivial") is True:
            continue
        split = record.get("split_hint")
        if split == "id":
            id_bucket.append(record)
        elif split == "ood":
            ood_bucket.append(record)

    if len(id_bucket) < n_id:
        raise SystemExit(
            f"[PARITY-PROMPTS] insufficient samples in bucket id: have {len(id_bucket)}, need {n_id}"
        )
    if len(ood_bucket) < n_ood:
        raise SystemExit(
            f"[PARITY-PROMPTS] insufficient samples in bucket ood: have {len(ood_bucket)}, need {n_ood}"
        )

    # Sort each bucket by sample_id so input order into random.sample is itself
    # deterministic across filesystem-driven iteration order changes.
    id_bucket.sort(key=lambda r: r.get("sample_id", ""))
    ood_bucket.sort(key=lambda r: r.get("sample_id", ""))

    rng_id = random.Random(seed)
    rng_ood = random.Random(seed + 1)
    id_picks = rng_id.sample(id_bucket, n_id)
    ood_picks = rng_ood.sample(ood_bucket, n_ood)
    return id_picks, ood_picks


def write_jsonl(out_path: Path, records: list[dict]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            fh.write("\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labeled", type=Path, default=Path("data/labeled.jsonl"))
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("runs/20260507T032419Z/gguf/parity_prompts.jsonl"),
    )
    parser.add_argument("--n-id", type=int, default=10)
    parser.add_argument("--n-ood", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--include-trivial",
        action="store_true",
        help="Include records with trivial=True (default excludes them).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    exclude_trivial = not args.include_trivial

    id_picks, ood_picks = select_parity_records(
        labeled_path=args.labeled,
        n_id=args.n_id,
        n_ood=args.n_ood,
        seed=args.seed,
        exclude_trivial=exclude_trivial,
    )

    selected = id_picks + ood_picks
    write_jsonl(args.out, selected)

    id_short = ", ".join(r.get("sample_id", "")[:8] for r in id_picks)
    ood_short = ", ".join(r.get("sample_id", "")[:8] for r in ood_picks)
    print(
        f"[PARITY-PROMPTS] selected {len(id_picks)} id + {len(ood_picks)} ood = "
        f"{len(selected)} samples"
    )
    print("[PARITY-PROMPTS] sample_ids:")
    print(f"  id:  {id_short}")
    print(f"  ood: {ood_short}")
    print(f"[PARITY-PROMPTS] wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
