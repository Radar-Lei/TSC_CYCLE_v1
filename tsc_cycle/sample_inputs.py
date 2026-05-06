"""Synthetic input sampler — 同分布 + OOD."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from tsc_cycle.constraint_lint import is_trivial
from tsc_cycle.hashing import sample_id

# OOD ranges from data/ood_spec.md
OOD_PHASE_COUNTS = [2, 6, 7, 8]
OOD_MIN_VALUES = [5, 10, 90, 100, 120]
OOD_MAX_VALUES = [25, 35, 60, 110, 150]
OOD_SATURATION_LOW = (0.0001, 0.001)
OOD_SATURATION_HIGH = (0.5, 0.95)
OOD_WAIT_LOW = (0.001, 0.05)
OOD_WAIT_HIGH = (50.0, 200.0)
OOD_CAPACITY_VALUES = [1, 5, 200, 500]
OOD_DIMENSIONS = (
    "phase_count", "range_combo", "saturation", "wait", "capacity",
    "narrow_range", "wide_range",
)


def _sample_in_distribution(rng: random.Random, prior: dict[str, Any], crossing_id: int = 1) -> dict:
    pc_keys = list(map(int, prior["phase_count_distribution"].keys()))
    pc_w = list(prior["phase_count_distribution"].values())
    n_phase = rng.choices(pc_keys, weights=pc_w, k=1)[0]

    range_modes = prior["range_modes_top"][:10]
    range_w = [r["count"] for r in range_modes]

    waits = []
    for i in range(n_phase):
        rmode = rng.choices(range_modes, weights=range_w, k=1)[0]
        per_pos = prior["per_position"].get(str(i), {}) or {}
        # Prefer values_all (frequency-preserving) so KS test against log passes; fall back to bounded sample
        sat_vals = (per_pos.get("pred_saturation", {}) or {}).get("values_all") \
            or (per_pos.get("pred_saturation", {}) or {}).get("values_sample") or [0.05]
        wait_vals = (per_pos.get("pred_wait", {}) or {}).get("values_all") \
            or (per_pos.get("pred_wait", {}) or {}).get("values_sample") or [1.0]
        cap_vals = (per_pos.get("capacity", {}) or {}).get("values_all") \
            or (per_pos.get("capacity", {}) or {}).get("values_sample") or [40]
        waits.append({
            "phase_id": i + 1,
            "pred_wait": rng.choice(wait_vals),
            "pred_saturation": rng.choice(sat_vals),
            "min_green": int(rmode["min_green"]),
            "max_green": int(rmode["max_green"]),
            "capacity": int(rng.choice(cap_vals)),
        })

    return {"prediction": {"as_of": _ts(rng), "phase_waits": waits, "_crossing_id": crossing_id}}


def _apply_ood_mutations(rng: random.Random, sample: dict, prior: dict) -> tuple[dict, list[str]]:
    """Mutate an in-distribution sample to satisfy ≥1 OOD dimension."""
    mutations: list[str] = []
    waits = sample["prediction"]["phase_waits"]
    n_dims = rng.randint(1, 2)
    chosen = rng.sample(OOD_DIMENSIONS, k=n_dims)

    for dim in chosen:
        if dim == "phase_count":
            target_n = rng.choice(OOD_PHASE_COUNTS)
            # Either truncate or pad
            if target_n < len(waits):
                waits = waits[:target_n]
            else:
                # pad with copies of the last (re-id)
                template = waits[-1].copy()
                while len(waits) < target_n:
                    template = template.copy()
                    waits.append(template)
            for i, w in enumerate(waits):
                w["phase_id"] = i + 1
        elif dim == "range_combo":
            # All-new (min, max) combo absent in log
            seen_combos = {(r["min_green"], r["max_green"]) for r in prior["range_modes_top"]}
            for w in waits:
                while True:
                    mn = rng.choice(OOD_MIN_VALUES)
                    mx = rng.choice(OOD_MAX_VALUES)
                    if mn < mx and (mn, mx) not in seen_combos:
                        w["min_green"], w["max_green"] = mn, mx
                        break
        elif dim == "saturation":
            band = rng.choice([OOD_SATURATION_LOW, OOD_SATURATION_HIGH])
            for w in waits:
                w["pred_saturation"] = round(rng.uniform(*band), 4)
        elif dim == "wait":
            band = rng.choice([OOD_WAIT_LOW, OOD_WAIT_HIGH])
            for w in waits:
                w["pred_wait"] = round(rng.uniform(*band), 4)
        elif dim == "capacity":
            for w in waits:
                w["capacity"] = int(rng.choice(OOD_CAPACITY_VALUES))
        elif dim == "narrow_range":
            for w in waits:
                base = max(rng.randint(15, 70), 5)
                w["min_green"] = base
                w["max_green"] = base + rng.randint(0, 4)  # < 5
        elif dim == "wide_range":
            for w in waits:
                w["min_green"] = rng.randint(5, 15)
                w["max_green"] = w["min_green"] + rng.randint(85, 145)  # > 80
        mutations.append(dim)

    sample["prediction"]["phase_waits"] = waits
    sample["prediction"]["_ood_dims"] = mutations
    return sample, mutations


def _ts(rng: random.Random) -> str:
    yyyy = 2026
    mm = rng.randint(4, 6)
    dd = rng.randint(1, 28)
    hh = rng.randint(0, 23)
    mi = rng.randint(0, 59)
    se = rng.randint(0, 59)
    return f"{yyyy}-{mm:02d}-{dd:02d} {hh:02d}:{mi:02d}:{se:02d}"


def sample(prior: dict, n_id: int, n_ood: int, seed: int = 42) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    id_samples: list[dict] = []
    ood_samples: list[dict] = []
    seen: set[str] = set()

    # Same-dist
    while len(id_samples) < n_id:
        rng_local = random.Random(rng.random())
        s = _sample_in_distribution(rng_local, prior)
        sid = sample_id(s)
        if sid in seen:
            continue
        seen.add(sid)
        s["sample_id"] = sid
        s["split_hint"] = "id"
        s["trivial"] = is_trivial(s)
        id_samples.append(s)

    # OOD
    while len(ood_samples) < n_ood:
        rng_local = random.Random(rng.random())
        base = _sample_in_distribution(rng_local, prior)
        mutated, dims = _apply_ood_mutations(rng_local, base, prior)
        sid = sample_id(mutated)
        if sid in seen:
            continue
        seen.add(sid)
        mutated["sample_id"] = sid
        mutated["split_hint"] = "ood"
        mutated["trivial"] = is_trivial(mutated)
        mutated["ood_dims"] = dims
        ood_samples.append(mutated)

    return id_samples, ood_samples


def write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prior", default="data/dist_prior.json")
    ap.add_argument("--n-id", type=int, default=2700)
    ap.add_argument("--n-ood", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-id", default="data/inputs.jsonl")
    ap.add_argument("--out-ood", default="data/ood_inputs.jsonl")
    args = ap.parse_args()

    prior = json.loads(Path(args.prior).read_text(encoding="utf-8"))
    id_samples, ood_samples = sample(prior, args.n_id, args.n_ood, seed=args.seed)
    write_jsonl(Path(args.out_id), id_samples)
    write_jsonl(Path(args.out_ood), ood_samples)
    n_triv_id = sum(1 for s in id_samples if s["trivial"])
    n_triv_ood = sum(1 for s in ood_samples if s["trivial"])
    print(f"wrote {args.out_id}: {len(id_samples)} samples ({n_triv_id} trivial)")
    print(f"wrote {args.out_ood}: {len(ood_samples)} samples ({n_triv_ood} trivial)")
    print(f"all unique sample_ids: {len({s['sample_id'] for s in id_samples + ood_samples}) == len(id_samples) + len(ood_samples)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
