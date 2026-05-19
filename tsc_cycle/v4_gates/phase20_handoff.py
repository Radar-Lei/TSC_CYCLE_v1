from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from tsc_cycle.v4_gates.phase20_eval import validate_phase20_eval_report
from tsc_cycle.v4_gates.phase20_reality_test import validate_phase20_replay_report
from tsc_cycle.v4_gates.phase20_comparison import validate_phase20_comparison_report

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
DEFAULT_RUN_ROOT = PROJECT_ROOT / "runs" / "v4.2-4B-20260518T111519Z"
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "v4_2" / "phase20"
HANDOFF_MANIFEST_PATH = ARTIFACT_ROOT / "handoff_manifest.json"
REQUIREMENTS_COVERED = ["EVAL-01", "EVAL-02", "EVAL-03"]


def sha256_file(path: str | Path) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _write_json(path: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def _is_under(path: Path, root: Path) -> bool:
    candidate = path.expanduser().resolve(strict=False)
    root = root.expanduser().resolve(strict=False)
    return candidate == root or root in candidate.parents


def _required_paths(run_root: Path, artifact_root: Path) -> dict[str, Path]:
    return {
        "training_report": run_root / "phase19_sft_report.json",
        "export_report": run_root / "phase19_export_report.json",
        "q4_gguf": run_root / "gguf" / "model.q4_K_M.gguf",
        "eval_report": artifact_root / "eval_report.json",
        "replay_log": artifact_root / "reality_test.log",
        "replay_report": artifact_root / "reality_replay_report.json",
        "comparison_report": artifact_root / "comparison_report.json",
    }


def _artifact_record(name: str, path: Path, run_root: Path, artifact_root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    allowed = _is_under(path, run_root) or _is_under(path, artifact_root)
    if not allowed or "v4.0-4B-" in path.as_posix() or "/artifacts/v4/" in path.as_posix():
        failures.append({"gate": "artifact_scope", "reason": f"accepted artifact path is out of Phase 20 scope: {path}", "artifact": name})
    record: dict[str, Any] = {"path": str(path), "exists": path.is_file()}
    if path.is_file():
        size = path.stat().st_size
        record.update({"size_bytes": size, "sha256": sha256_file(path) if size > 0 else None})
        if size <= 0:
            failures.append({"gate": "artifact_size", "reason": f"zero-byte artifact: {path}", "artifact": name})
    else:
        failures.append({"gate": "artifact_exists", "reason": f"missing artifact: {path}", "artifact": name})
    return record, failures


def _upstream_gates(run_root: Path, artifact_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    eval_report = validate_phase20_eval_report(report_path=artifact_root / "eval_report.json", run_root=run_root)
    replay_report = validate_phase20_replay_report(artifact_root / "reality_replay_report.json", run_root=run_root, eval_report_path=artifact_root / "eval_report.json")
    comparison_report = validate_phase20_comparison_report(artifact_root / "comparison_report.json", run_root=run_root, eval_report_path=artifact_root / "eval_report.json", replay_report_path=artifact_root / "reality_replay_report.json")
    gates = {
        "eval_report": {"ok": eval_report.get("ok") is True, "data": eval_report},
        "replay_report": {"ok": replay_report.get("ok") is True, "data": replay_report},
        "comparison_report": {"ok": comparison_report.get("ok") is True, "data": comparison_report},
    }
    failures: list[dict[str, Any]] = []
    for gate, report in (("eval_report", eval_report), ("replay_report", replay_report), ("comparison_report", comparison_report)):
        if report.get("ok") is not True or report.get("next_phase_allowed") is not True:
            failures.append({"gate": gate, "reason": f"{gate} is not accepted", "details": report.get("fatal_failures", [])})
    return gates, failures


def _manifest_artifact_records(manifest: dict[str, Any]) -> dict[str, Any]:
    artifacts = manifest.get("artifacts")
    return artifacts if isinstance(artifacts, dict) else {}


def write_phase20_handoff(
    *,
    run_root: str | Path = DEFAULT_RUN_ROOT,
    artifact_root: str | Path = ARTIFACT_ROOT,
    manifest_path: str | Path = HANDOFF_MANIFEST_PATH,
) -> dict[str, Any]:
    run_root = Path(run_root)
    artifact_root = Path(artifact_root)
    artifacts: dict[str, Any] = {}
    fatal_failures: list[dict[str, Any]] = []
    for name, path in _required_paths(run_root, artifact_root).items():
        record, failures = _artifact_record(name, path, run_root, artifact_root)
        artifacts[name] = record
        fatal_failures.extend(failures)
    gates, gate_failures = _upstream_gates(run_root, artifact_root)
    fatal_failures.extend(gate_failures)
    ok = not fatal_failures
    manifest = {
        "ok": ok,
        "next_phase_allowed": ok,
        "requirements_covered": list(REQUIREMENTS_COVERED) if ok else [],
        "gates": gates,
        "fatal_failures": fatal_failures,
        "warnings": [],
        "run_root": str(run_root),
        "artifact_root": str(artifact_root),
        "artifacts": artifacts,
        "reports": {
            "eval_report": str(artifact_root / "eval_report.json"),
            "replay_report": str(artifact_root / "reality_replay_report.json"),
            "comparison_report": str(artifact_root / "comparison_report.json"),
            "handoff_manifest": str(manifest_path),
        },
    }
    return _write_json(manifest_path, manifest)


def validate_phase20_handoff(
    *,
    manifest_path: str | Path = HANDOFF_MANIFEST_PATH,
    run_root: str | Path = DEFAULT_RUN_ROOT,
    artifact_root: str | Path = ARTIFACT_ROOT,
) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    run_root = Path(run_root)
    artifact_root = Path(artifact_root)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"ok": False, "next_phase_allowed": False, "requirements_covered": [], "fatal_failures": [{"gate": "manifest_json", "reason": str(exc)}], "report_path": str(manifest_path)}
    if not isinstance(manifest, dict):
        return {"ok": False, "next_phase_allowed": False, "requirements_covered": [], "fatal_failures": [{"gate": "manifest_json", "reason": "manifest must be an object"}], "report_path": str(manifest_path)}

    failures = list(manifest.get("fatal_failures", [])) if isinstance(manifest.get("fatal_failures"), list) else [{"gate": "fatal_failures", "reason": "fatal_failures must be a list"}]
    reported_artifacts = _manifest_artifact_records(manifest)
    for name, expected_path in _required_paths(run_root, artifact_root).items():
        reported = reported_artifacts.get(name) if isinstance(reported_artifacts.get(name), dict) else {}
        path_value = reported.get("path") if isinstance(reported.get("path"), str) else str(expected_path)
        path = Path(path_value)
        actual, artifact_failures = _artifact_record(name, path, run_root, artifact_root)
        failures.extend(artifact_failures)
        if path.resolve(strict=False) != expected_path.resolve(strict=False):
            failures.append({"gate": "artifact_path", "reason": f"{name} path does not match expected Phase 20 artifact", "artifact": name})
        if reported.get("sha256") != actual.get("sha256") or reported.get("size_bytes") != actual.get("size_bytes"):
            failures.append({"gate": "artifact_hash", "reason": f"{name} hash/size does not match disk", "artifact": name})

    gates, gate_failures = _upstream_gates(run_root, artifact_root)
    failures.extend(gate_failures)
    if manifest.get("ok") is not True or manifest.get("next_phase_allowed") is not True:
        failures.append({"gate": "manifest_green", "reason": "handoff manifest is not green"})
    covered = manifest.get("requirements_covered", [])
    if not isinstance(covered, list) or [str(item) for item in covered] != REQUIREMENTS_COVERED:
        failures.append({"gate": "requirements_covered", "reason": "handoff must cover exactly EVAL-01/EVAL-02/EVAL-03"})

    out = dict(manifest)
    out.update({
        "ok": not failures,
        "next_phase_allowed": not failures,
        "requirements_covered": list(REQUIREMENTS_COVERED) if not failures else [],
        "gates": gates,
        "fatal_failures": failures,
        "report_path": str(manifest_path),
    })
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write or validate the final Phase 20 handoff manifest")
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--artifact-root", type=Path, default=ARTIFACT_ROOT)
    parser.add_argument("--manifest", type=Path, default=HANDOFF_MANIFEST_PATH)
    parser.add_argument("--validate", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.validate:
        result = validate_phase20_handoff(manifest_path=args.manifest, run_root=args.run_root, artifact_root=args.artifact_root)
    else:
        result = write_phase20_handoff(run_root=args.run_root, artifact_root=args.artifact_root, manifest_path=args.manifest)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    sys.exit(main())
