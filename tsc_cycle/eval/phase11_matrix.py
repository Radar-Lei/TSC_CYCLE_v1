"""Phase 11 evaluation matrix builder.

This module is intentionally lightweight: it prepares the Phase 11 prompt
matrix and manifest, while heavy HF/GGUF generation remains in the existing
``tsc_cycle.eval.generate_hf`` and ``tsc_cycle.eval.generate_gguf`` modules.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
V4_RUN_ROOT = PROJECT_ROOT / "runs" / "v4.0-4B-20260509T184844Z"
PHASE11_OUT_ROOT = V4_RUN_ROOT / "eval_phase11"
FROZEN_V1_ROOT = PROJECT_ROOT / "runs" / "20260507T032419Z"
V4_HF = "v4_hf"
V4_Q4 = "v4_gguf_q4_k_m"
V1_Q4 = "v1_gguf_q4_k_m"
REQUIRED_BACKENDS = (V4_HF, V4_Q4, V1_Q4)


@dataclass(frozen=True)
class BackendConfig:
    id: str
    label: str
    artifact_path: str | None
    cache_dir: str | None
    read_only: bool
    generate: bool
    source_paths: dict[str, str]


@dataclass(frozen=True)
class Phase11MatrixConfig:
    run_root: str
    out_root: str
    prompts_path: str
    manifest_path: str
    frozen_v1_root: str
    backends: dict[str, BackendConfig]


def _is_under(path: Path, root: Path) -> bool:
    path = Path(path).expanduser().resolve(strict=False)
    root = Path(root).expanduser().resolve(strict=False)
    return path == root or root in path.parents


def normalize_backend_id(raw: str) -> str:
    """Normalize external/backend artifact labels to Phase 11 IDs."""
    key = str(raw).strip().lower().replace("-", "_")
    collapsed = "_".join(key.replace("/", " ").split())
    aliases = {
        "hf": V4_HF,
        "hf_bf16": V4_HF,
        "v4_hf": V4_HF,
        "v4 hf": V4_HF,
        "v4_hf_bf16": V4_HF,
        "gguf_q4_k_m": V4_Q4,
        "gguf_q4_k_m": V4_Q4,
        "q4_k_m": V4_Q4,
        "v4_gguf_q4_k_m": V4_Q4,
        "v4 q4_k_m": V4_Q4,
        "v4_q4_k_m": V4_Q4,
        "v1": V1_Q4,
        "v1_q4": V1_Q4,
        "v1_q4_k_m": V1_Q4,
        "v1_gguf_q4_k_m": V1_Q4,
        "frozen_v1_q4_k_m": V1_Q4,
    }
    if key in aliases:
        return aliases[key]
    if collapsed in aliases:
        return aliases[collapsed]
    raise ValueError(f"unknown or unsupported Phase 11 backend label: {raw}")


def reject_frozen_v1_output_path(path: str | Path) -> Path:
    """Reject any would-be output path under the frozen v1 run root."""
    candidate = Path(path).expanduser()
    if _is_under(candidate, FROZEN_V1_ROOT):
        raise ValueError(
            "refusing to write under frozen read-only v1 baseline "
            f"20260507T032419Z: {candidate}"
        )
    return candidate


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON file is not an object: {path}")
    return payload


def _require_existing(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")


def validate_phase10_handoff(
    report_path: str | Path = V4_RUN_ROOT / "phase10_gguf_report.json",
    *,
    run_root: str | Path = V4_RUN_ROOT,
) -> dict[str, Any]:
    """Validate Phase 10 green handoff and expected v4 artifact paths."""
    report_path = Path(report_path)
    run_root = Path(run_root)
    _require_existing(report_path, "Phase 10 handoff report")
    report = _load_json(report_path)
    failures: list[str] = []
    if report.get("ok") is not True:
        failures.append("phase10 report ok is not true")
    if report.get("next_phase_allowed") is not True:
        failures.append("phase10 next_phase_allowed is not true")
    phase11_handoff = report.get("phase11_handoff") or {}
    if phase11_handoff.get("allowed") is not True:
        failures.append("phase10 phase11_handoff.allowed is not true")

    paths = (report.get("artifact_manifest") or {}).get("paths") or {}
    expected = {
        "merged_hf": run_root / "merged_hf",
        "gguf_q4_K_M": run_root / "gguf" / "model.q4_K_M.gguf",
    }
    for key, expected_path in expected.items():
        actual = Path(str(paths.get(key, ""))) if paths.get(key) else None
        if actual != expected_path:
            failures.append(f"phase10 artifact {key} expected {expected_path}, got {actual}")
        else:
            _require_existing(actual, f"Phase 10 artifact {key}")

    if failures:
        raise ValueError("Phase 10 handoff is not green for Phase 11: " + "; ".join(failures))
    return report


def build_phase11_matrix_config(
    *,
    run_root: str | Path = V4_RUN_ROOT,
    frozen_v1_root: str | Path = FROZEN_V1_ROOT,
    out_root: str | Path = PHASE11_OUT_ROOT,
) -> Phase11MatrixConfig:
    run_root = Path(run_root)
    frozen_v1_root = Path(frozen_v1_root)
    out_root = reject_frozen_v1_output_path(out_root)
    prompts_path = reject_frozen_v1_output_path(out_root / "eval_prompts.jsonl")
    manifest_path = reject_frozen_v1_output_path(out_root / "matrix_manifest.json")
    return Phase11MatrixConfig(
        run_root=str(run_root),
        out_root=str(out_root),
        prompts_path=str(prompts_path),
        manifest_path=str(manifest_path),
        frozen_v1_root=str(frozen_v1_root),
        backends={
            V4_HF: BackendConfig(
                id=V4_HF,
                label="v4 HF merged_hf",
                artifact_path=str(run_root / "merged_hf"),
                cache_dir=str(out_root / "gen_cache" / V4_HF),
                read_only=False,
                generate=True,
                source_paths={},
            ),
            V4_Q4: BackendConfig(
                id=V4_Q4,
                label="v4 GGUF q4_K_M",
                artifact_path=str(run_root / "gguf" / "model.q4_K_M.gguf"),
                cache_dir=str(out_root / "gen_cache" / V4_Q4),
                read_only=False,
                generate=True,
                source_paths={},
            ),
            V1_Q4: BackendConfig(
                id=V1_Q4,
                label="frozen v1 GGUF q4_K_M baseline",
                artifact_path=str(frozen_v1_root / "gguf" / "model.q4_K_M.gguf"),
                cache_dir=str(frozen_v1_root / "eval" / "gen_cache" / "gguf_q4_k_m"),
                read_only=True,
                generate=False,
                source_paths={
                    "eval_prompts": str(frozen_v1_root / "eval" / "eval_prompts.jsonl"),
                    "per_sample": str(frozen_v1_root / "eval" / "per_sample.jsonl"),
                    "gen_cache": str(frozen_v1_root / "eval" / "gen_cache" / "gguf_q4_k_m"),
                },
            ),
        },
    )


def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"malformed JSONL at {path}:{line_no}: {exc}") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"JSONL row is not an object at {path}:{line_no}")
            yield obj


def _phase_count(input_record: dict[str, Any]) -> int:
    if "phases" in input_record:
        return len(input_record["phases"])
    if "phase_min_green" in input_record:
        return len(input_record["phase_min_green"])
    prediction = input_record.get("prediction") or {}
    waits = prediction.get("phase_waits") or []
    return len(waits)


def _project_prompt(record: dict[str, Any], *, slice_hint: str) -> dict[str, Any]:
    input_rec = record.get("input") or {}
    result = record.get("result") or {}
    return {
        "sample_id": record["sample_id"],
        "split_hint": record.get("split_hint"),
        "slice_hint": slice_hint,
        "input": input_rec,
        "teacher_solution": result.get("solution"),
        "phase_count": _phase_count(input_rec),
        "trivial": bool(record.get("trivial", False)),
    }


def _alignment_ids(alignment_path: Path) -> list[str]:
    payload = _load_json(alignment_path)
    ids = payload.get("v1_ood_sample_ids")
    if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
        raise ValueError(f"alignment file lacks v1_ood_sample_ids list: {alignment_path}")
    return ids


def build_phase11_prompts(
    *,
    labeled_path: str | Path = PROJECT_ROOT / "data" / "v4" / "phase8" / "labeled_merged.jsonl",
    alignment_path: str | Path = PROJECT_ROOT / "data" / "v4" / "phase8" / "splits" / "v1_ood_alignment.json",
    out_path: str | Path = PHASE11_OUT_ROOT / "eval_prompts.jsonl",
    seed: int = 42,
    n_id: int = 300,
    n_expanded_ood: int = 300,
) -> list[dict[str, Any]]:
    """Build deterministic Phase 11 prompt JSONL.

    Output contains three slices: sampled ID, v1-comparable OOD, and sampled
    v4-expanded OOD. The comparable IDs come directly from the frozen alignment
    manifest; expanded OOD excludes those IDs.
    """
    labeled_path = Path(labeled_path)
    alignment_path = Path(alignment_path)
    out_path = reject_frozen_v1_output_path(out_path)
    _require_existing(labeled_path, "v4 labeled merged JSONL")
    _require_existing(alignment_path, "v1 OOD alignment JSON")

    comparable_ids = set(_alignment_ids(alignment_path))
    by_id: dict[str, dict[str, Any]] = {}
    id_pool: list[dict[str, Any]] = []
    expanded_ood_pool: list[dict[str, Any]] = []
    for record in _iter_jsonl(labeled_path):
        sid = str(record.get("sample_id", ""))
        if not sid:
            continue
        by_id[sid] = record
        split = record.get("split_hint")
        if split == "id":
            id_pool.append(record)
        elif split == "ood" and sid not in comparable_ids:
            expanded_ood_pool.append(record)

    missing = sorted(comparable_ids.difference(by_id))
    if missing:
        raise ValueError(f"v1 comparable OOD IDs missing from v4 labeled data: {len(missing)}")
    if len(id_pool) < n_id:
        raise ValueError(f"insufficient id samples: have {len(id_pool)}, need {n_id}")
    if len(expanded_ood_pool) < n_expanded_ood:
        raise ValueError(
            f"insufficient expanded ood samples: have {len(expanded_ood_pool)}, need {n_expanded_ood}"
        )

    id_pool.sort(key=lambda r: r.get("sample_id", ""))
    expanded_ood_pool.sort(key=lambda r: r.get("sample_id", ""))
    rng = random.Random(seed)
    id_picked = rng.sample(id_pool, n_id)
    expanded_picked = rng.sample(expanded_ood_pool, n_expanded_ood)
    comparable_picked = [by_id[sid] for sid in sorted(comparable_ids)]

    prompts = (
        [_project_prompt(r, slice_hint="v4_id") for r in id_picked]
        + [_project_prompt(r, slice_hint="v1_comparable_ood") for r in comparable_picked]
        + [_project_prompt(r, slice_hint="v4_expanded_ood") for r in expanded_picked]
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for record in prompts:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=False))
            fh.write("\n")
    return prompts


def _public_config(config: Phase11MatrixConfig) -> dict[str, Any]:
    return asdict(config)


def build_matrix_manifest(
    *,
    config: Phase11MatrixConfig | None = None,
    prompts: list[dict[str, Any]] | None = None,
    out_path: str | Path | None = None,
    phase10_report_path: str | Path = V4_RUN_ROOT / "phase10_gguf_report.json",
) -> dict[str, Any]:
    config = config or build_phase11_matrix_config()
    manifest_path = reject_frozen_v1_output_path(out_path or config.manifest_path)
    phase10 = validate_phase10_handoff(phase10_report_path, run_root=config.run_root)

    prompt_rows = prompts
    if prompt_rows is None and Path(config.prompts_path).exists():
        prompt_rows = list(_iter_jsonl(Path(config.prompts_path)))
    prompt_rows = prompt_rows or []
    slice_counts: dict[str, int] = {}
    for record in prompt_rows:
        key = str(record.get("slice_hint") or record.get("split_hint") or "unknown")
        slice_counts[key] = slice_counts.get(key, 0) + 1

    manifest = {
        "ok": True,
        "requirements_covered": ["EVAL4B-01"],
        "seed": 42,
        "config": _public_config(config),
        "backends": _public_config(config)["backends"],
        "prompt_count": len(prompt_rows),
        "slice_counts": slice_counts,
        "phase10_handoff": {
            "ok": True,
            "report_path": str(phase10_report_path),
            "artifact_paths": (phase10.get("artifact_manifest") or {}).get("paths") or {},
        },
        "frozen_v1_baseline": {
            "read_only": True,
            "generate": False,
            "root": config.frozen_v1_root,
            "per_sample": config.backends[V1_Q4].source_paths["per_sample"],
            "gen_cache": config.backends[V1_Q4].source_paths["gen_cache"],
        },
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 11 eval matrix prompts and manifest")
    parser.add_argument("--run-root", type=Path, default=V4_RUN_ROOT)
    parser.add_argument("--out-root", type=Path, default=PHASE11_OUT_ROOT)
    parser.add_argument("--frozen-v1-root", type=Path, default=FROZEN_V1_ROOT)
    parser.add_argument("--labeled", type=Path, default=PROJECT_ROOT / "data" / "v4" / "phase8" / "labeled_merged.jsonl")
    parser.add_argument("--alignment", type=Path, default=PROJECT_ROOT / "data" / "v4" / "phase8" / "splits" / "v1_ood_alignment.json")
    parser.add_argument("--phase10-report", type=Path, default=V4_RUN_ROOT / "phase10_gguf_report.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-id", type=int, default=300)
    parser.add_argument("--n-expanded-ood", type=int, default=300)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = build_phase11_matrix_config(
        run_root=args.run_root,
        frozen_v1_root=args.frozen_v1_root,
        out_root=args.out_root,
    )
    prompts = build_phase11_prompts(
        labeled_path=args.labeled,
        alignment_path=args.alignment,
        out_path=config.prompts_path,
        seed=args.seed,
        n_id=args.n_id,
        n_expanded_ood=args.n_expanded_ood,
    )
    manifest = build_matrix_manifest(
        config=config,
        prompts=prompts,
        out_path=config.manifest_path,
        phase10_report_path=args.phase10_report,
    )
    print(
        "[PHASE11-MATRIX] OK "
        f"prompts={manifest['prompt_count']} slices={manifest['slice_counts']} "
        f"out={config.prompts_path} manifest={config.manifest_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
