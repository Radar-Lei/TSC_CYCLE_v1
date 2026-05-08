"""Synthetic input sampler — 同分布 + OOD."""

from __future__ import annotations

import argparse
import copy
import json
import random
from collections.abc import Mapping
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


def _canonical_input(record: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return the prediction input object used for sample_id hashing."""
    candidate: Any = record.get("input") if isinstance(record, Mapping) else None
    if isinstance(candidate, Mapping) and isinstance(candidate.get("prediction"), Mapping):
        return copy.deepcopy(dict(candidate))
    if isinstance(record.get("prediction"), Mapping):
        return {"prediction": copy.deepcopy(record["prediction"])}
    return None


def _read_jsonl_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _old_ids_from_labeled(path: Path | None) -> set[str]:
    old_ids: set[str] = set()
    for row in _read_jsonl_rows(path):
        if isinstance(row.get("sample_id"), str):
            old_ids.add(row["sample_id"])
        inp = _canonical_input(row)
        if inp is not None:
            old_ids.add(sample_id(inp))
    return old_ids


def _attach_sample_metadata(sample_obj: dict[str, Any], *, source: str, split_hint: str) -> dict[str, Any]:
    record = copy.deepcopy(sample_obj)
    sid = sample_id(record)
    record["sample_id"] = sid
    record["split_hint"] = split_hint
    record["trivial"] = is_trivial(record)
    record["source"] = source
    return record


def _candidate_seed_inputs(per_sample_path: Path | None, lookup_paths: list[Path] | None = None) -> list[dict[str, Any]]:
    eval_rows = _read_jsonl_rows(per_sample_path)
    wanted: dict[str, str] = {}
    for row in eval_rows:
        sid = row.get("sample_id")
        if not isinstance(sid, str):
            continue
        reason: str | None = None
        if row.get("lint_ok") is False:
            reason = "lint_ok=false"
        elif (row.get("mae") or 0.0) > 10.0:
            reason = "mae > 10.0"
        if reason is not None:
            wanted.setdefault(sid, reason)

    seeds: list[dict[str, Any]] = []
    seen_seed_ids: set[str] = set()
    for row in eval_rows:
        sid = row.get("sample_id")
        if sid not in wanted or sid in seen_seed_ids:
            continue
        inp = _canonical_input(row)
        if inp is None:
            continue
        seeds.append({"sample_id": sid, "input": inp, "reason": wanted[sid]})
        seen_seed_ids.add(sid)

    for path in lookup_paths or []:
        if not wanted:
            break
        for row in _read_jsonl_rows(path):
            inp = _canonical_input(row)
            sid = row.get("sample_id") if isinstance(row.get("sample_id"), str) else None
            if sid is None and inp is not None:
                sid = sample_id(inp)
            if sid not in wanted or sid in seen_seed_ids or inp is None:
                continue
            seeds.append({"sample_id": sid, "input": inp, "reason": wanted[sid]})
            seen_seed_ids.add(sid)
    return seeds


def _perturb_targeted_seed(rng: random.Random, seed_input: dict[str, Any]) -> tuple[dict[str, Any], str]:
    sample_obj = copy.deepcopy(seed_input)
    waits = sample_obj["prediction"]["phase_waits"]
    if not waits:
        raise ValueError("targeted seed has no phase_waits")
    phase = rng.choice(waits)
    numeric_fields = ["pred_wait", "pred_saturation", "min_green", "max_green", "capacity"]
    field = rng.choice(numeric_fields)
    if field == "pred_wait":
        phase[field] = round(max(0.001, float(phase[field]) * rng.uniform(0.85, 1.20) + rng.uniform(-1.5, 1.5)), 4)
    elif field == "pred_saturation":
        phase[field] = round(min(0.99, max(0.0001, float(phase[field]) + rng.uniform(-0.08, 0.08))), 4)
    elif field == "capacity":
        phase[field] = max(1, int(phase[field]) + rng.choice([-10, -5, 5, 10]))
    elif field == "min_green":
        max_green = int(phase["max_green"])
        phase[field] = max(1, min(max_green - 1, int(phase[field]) + rng.choice([-5, -2, 2, 5])))
    elif field == "max_green":
        min_green = int(phase["min_green"])
        phase[field] = max(min_green + 1, int(phase[field]) + rng.choice([-5, -2, 2, 5]))
    return sample_obj, field


def build_v3_phase2_reservoir(
    prior: dict[str, Any],
    counts: Mapping[str, int] | None = None,
    seed: int = 42,
    exclude_ids: set[str] | None = None,
    per_sample_path: Path | None = None,
    *,
    old_labeled_path: Path | None = None,
    per_sample_eval_path: Path | None = None,
    same_dist_count: int | None = None,
    ood_count: int | None = None,
    targeted_count: int | None = None,
    seed_lookup_paths: list[Path] | None = None,
) -> list[dict[str, Any]]:
    """Build deterministic v3 Phase 2 same-dist/OOD/targeted candidate records."""
    if counts is None:
        counts = {
            "same_dist": int(same_dist_count or 0),
            "ood": int(ood_count or 0),
            "targeted": int(targeted_count or 0),
        }
    expected = {"same_dist", "ood", "targeted"}
    if set(counts) != expected:
        raise ValueError(f"counts must have exact keys {sorted(expected)}")

    per_sample = per_sample_path or per_sample_eval_path
    if seed_lookup_paths is None:
        root = Path(__file__).resolve().parents[1]
        seed_lookup_paths = [
            root / "data/inputs.jsonl",
            root / "data/ood_inputs.jsonl",
            root / "data/labeled.jsonl",
        ]
    seen: set[str] = set(exclude_ids or set()) | _old_ids_from_labeled(old_labeled_path)
    out: list[dict[str, Any]] = []
    rng = random.Random(seed)

    def add_record(record: dict[str, Any]) -> bool:
        sid = record["sample_id"]
        if sid in seen:
            return False
        seen.add(sid)
        out.append(record)
        return True

    same_dist_written = 0
    while same_dist_written < int(counts["same_dist"]):
        rng_local = random.Random(rng.random())
        record = _attach_sample_metadata(
            _sample_in_distribution(rng_local, prior), source="same_dist", split_hint="id"
        )
        if add_record(record):
            same_dist_written += 1

    ood_written = 0
    while ood_written < int(counts["ood"]):
        rng_local = random.Random(rng.random())
        base = _sample_in_distribution(rng_local, prior)
        mutated, dims = _apply_ood_mutations(rng_local, base, prior)
        record = _attach_sample_metadata(mutated, source="ood", split_hint="ood")
        record["ood_dims"] = dims
        if add_record(record):
            ood_written += 1

    targeted_seeds = _candidate_seed_inputs(per_sample, seed_lookup_paths)
    if int(counts["targeted"]) and not targeted_seeds:
        raise ValueError("no targeted seeds found from lint_ok=false or mae > 10.0 rows")
    targeted_written = 0
    targeted_attempts = 0
    while targeted_written < int(counts["targeted"]):
        targeted_attempts += 1
        if targeted_attempts > max(1000, int(counts["targeted"]) * 100):
            raise RuntimeError("could not produce enough unique targeted samples")
        rng_local = random.Random(rng.random())
        seed_row = targeted_seeds[targeted_written % len(targeted_seeds)] if len(targeted_seeds) <= 1 else rng.choice(targeted_seeds)
        targeted_input, changed_field = _perturb_targeted_seed(rng_local, seed_row["input"])
        sid = sample_id(targeted_input)
        if sid == seed_row["sample_id"]:
            continue
        record = _attach_sample_metadata(targeted_input, source="targeted", split_hint="ood")
        record["targeted_seed_id"] = seed_row["sample_id"]
        record["targeted_reason"] = seed_row["reason"]
        record["targeted_mutation"] = changed_field
        if add_record(record):
            targeted_written += 1

    return out


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
