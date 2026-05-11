from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
FROZEN_BASELINE_ROOT = PROJECT_ROOT / "runs" / "20260507T032419Z"
PHASE9_RUN_ROOT = PROJECT_ROOT / "runs" / "v4.0-4B-20260509T184844Z"
DEFAULT_LLAMA_CPP = Path("/home/samuel/projects/EvoProgTSC/llama.cpp")
DEFAULT_PHASE9_REPORT = PHASE9_RUN_ROOT / "phase9_sft_report.json"
REQUIREMENTS_COVERED = ["GGUF4B-01"]


class Phase10ExportError(RuntimeError):
    """Fail-closed Phase 10 export planning/evidence error."""


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise Phase10ExportError(f"phase9 handoff report missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise Phase10ExportError(f"phase9 handoff report is not an object: {path}")
    return payload


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def is_forbidden_output_path(path: Path) -> bool:
    return _is_under(Path(path), FROZEN_BASELINE_ROOT)


def _require_output_path(path: Path, *, run_root: Path) -> None:
    if is_forbidden_output_path(path):
        raise Phase10ExportError(f"refusing to write under frozen read-only baseline 20260507T032419Z: {path}")
    if not _is_under(path, run_root):
        raise Phase10ExportError(f"phase10 output path must stay under run root {run_root}: {path}")


def _adapter_sha_from_report(report: dict[str, Any]) -> str | None:
    manifest = report.get("artifact_manifest") if isinstance(report.get("artifact_manifest"), dict) else {}
    sha = manifest.get("sha256") if isinstance(manifest.get("sha256"), dict) else {}
    value = sha.get("adapter_sha256")
    return value if isinstance(value, str) and value else None


def _adapter_path_from_report(report: dict[str, Any]) -> Path | None:
    for key in ("adapter_path",):
        value = report.get(key)
        if isinstance(value, str) and value:
            return Path(value)
    manifest = report.get("artifact_manifest") if isinstance(report.get("artifact_manifest"), dict) else {}
    paths = manifest.get("paths") if isinstance(manifest.get("paths"), dict) else {}
    value = paths.get("adapter")
    if isinstance(value, str) and value:
        return Path(value)
    gates = report.get("gates") if isinstance(report.get("gates"), dict) else {}
    handoff = gates.get("phase10_handoff") if isinstance(gates.get("phase10_handoff"), dict) else {}
    data = handoff.get("data") if isinstance(handoff.get("data"), dict) else {}
    value = data.get("adapter_path")
    return Path(value) if isinstance(value, str) and value else None


def load_phase9_handoff(report_path: Path) -> dict[str, Any]:
    report = _load_json(Path(report_path))
    if report.get("ok") is not True:
        raise Phase10ExportError("phase9 handoff report ok=false; refusing export")
    if report.get("next_phase_allowed") is not True:
        raise Phase10ExportError("phase9 handoff next_phase_allowed is not true; refusing export")

    adapter_path = _adapter_path_from_report(report)
    expected_sha = _adapter_sha_from_report(report)
    if adapter_path is None:
        raise Phase10ExportError("phase9 handoff adapter path is missing")
    if not expected_sha:
        raise Phase10ExportError("phase9 handoff adapter sha is missing")

    adapter_model = adapter_path / "adapter_model.safetensors"
    adapter_config = adapter_path / "adapter_config.json"
    if not adapter_model.is_file() or not adapter_config.is_file():
        raise Phase10ExportError(f"phase9 handoff adapter files missing under {adapter_path}")
    actual_sha = sha256_file(adapter_model)
    if actual_sha != expected_sha:
        raise Phase10ExportError(f"phase9 handoff adapter sha mismatch: expected {expected_sha}, got {actual_sha}")

    run_root = Path(str(report.get("run_root") or adapter_path.parent))
    return {
        "ok": True,
        "next_phase_allowed": True,
        "report_path": str(Path(report_path)),
        "run_root": str(run_root),
        "adapter_path": str(adapter_path),
        "adapter_sha256": actual_sha,
        "adapter_files": {
            "adapter_model": str(adapter_model),
            "adapter_config": str(adapter_config),
        },
        "requirements_covered": list(REQUIREMENTS_COVERED),
    }


def _tool(path: Path, name: str, fatal_failures: list[dict[str, str]]) -> str:
    ok = path.is_file() and (name.endswith(".py") or path.stat().st_size > 0)
    if not ok:
        fatal_failures.append({"gate": name, "reason": f"missing llama.cpp tool: {path}"})
    return str(path)


def plan_phase10_export(
    *,
    phase9_report: Path = DEFAULT_PHASE9_REPORT,
    run_root: Path = PHASE9_RUN_ROOT,
    llama_cpp_dir: Path = DEFAULT_LLAMA_CPP,
    merged_dir: Path | None = None,
    fp16_gguf: Path | None = None,
    q4_gguf: Path | None = None,
    report: Path | None = None,
) -> dict[str, Any]:
    run_root = Path(run_root)
    if is_forbidden_output_path(run_root):
        raise Phase10ExportError(f"refusing frozen read-only run root 20260507T032419Z: {run_root}")

    merged_dir = Path(merged_dir) if merged_dir is not None else run_root / "merged_hf"
    fp16_gguf = Path(fp16_gguf) if fp16_gguf is not None else run_root / "gguf" / "model.fp16.gguf"
    q4_gguf = Path(q4_gguf) if q4_gguf is not None else run_root / "gguf" / "model.q4_K_M.gguf"
    export_report = Path(report) if report is not None else run_root / "phase10_export_report.json"
    for output_path in (merged_dir, fp16_gguf, q4_gguf, export_report):
        _require_output_path(output_path, run_root=run_root)

    fatal_failures: list[dict[str, str]] = []
    try:
        handoff = load_phase9_handoff(Path(phase9_report))
    except Exception as exc:
        handoff = {"ok": False, "error": str(exc)}
        fatal_failures.append({"gate": "phase9_handoff", "reason": str(exc)})

    llama_cpp_dir = Path(llama_cpp_dir)
    convert = Path(_tool(llama_cpp_dir / "convert_hf_to_gguf.py", "convert_hf_to_gguf.py", fatal_failures))
    quantize = Path(_tool(llama_cpp_dir / "llama-quantize", "llama-quantize", fatal_failures))
    tokenize = Path(_tool(llama_cpp_dir / "llama-tokenize", "llama-tokenize", fatal_failures))
    server = Path(_tool(llama_cpp_dir / "llama-server", "llama-server", fatal_failures))

    commands = {
        "convert_fp16": [sys.executable, str(convert), str(merged_dir), "--outfile", str(fp16_gguf), "--outtype", "f16"],
        "quantize_q4_K_M": [str(quantize), str(fp16_gguf), str(q4_gguf), "Q4_K_M"],
    }

    return {
        "ok": not fatal_failures,
        "requirements_covered": list(REQUIREMENTS_COVERED),
        "phase9_report": str(Path(phase9_report)),
        "run_root": str(run_root),
        "adapter_path": handoff.get("adapter_path"),
        "adapter_sha256": handoff.get("adapter_sha256"),
        "phase9_handoff": handoff,
        "paths": {
            "merged_hf": str(merged_dir),
            "gguf_fp16": str(fp16_gguf),
            "gguf_q4_K_M": str(q4_gguf),
            "export_report": str(export_report),
        },
        "llama_cpp": {
            "root": str(llama_cpp_dir),
            "convert": str(convert),
            "quantize": str(quantize),
            "tokenize": str(tokenize),
            "server": str(server),
        },
        "commands": commands,
        "fatal_failures": fatal_failures,
    }


def build_export_plan(run_root: Path, llama_cpp: Path) -> dict[str, Any]:
    return plan_phase10_export(phase9_report=Path(run_root) / "phase9_sft_report.json", run_root=Path(run_root), llama_cpp_dir=Path(llama_cpp))


def _artifact_record(path: Path, *, required: bool = True) -> tuple[dict[str, Any], list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    record: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    if path.is_file():
        size = path.stat().st_size
        record.update({"size_bytes": size, "sha256": sha256_file(path) if size > 0 else None})
        if required and size <= 0:
            failures.append({"gate": "artifact_size", "reason": f"zero-byte artifact: {path}"})
    elif required:
        failures.append({"gate": "artifact_exists", "reason": f"missing artifact: {path}"})
    return record, failures


def _directory_manifest(root: Path, patterns: tuple[str, ...]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    if not root.is_dir():
        return records, [{"gate": "merged_hf", "reason": f"missing merged HF directory: {root}"}]
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                record, record_failures = _artifact_record(path)
                records.append(record)
                failures.extend(record_failures)
    if not records:
        failures.append({"gate": "merged_hf_safetensors", "reason": f"no safetensors found under {root}"})
    return records, failures


def write_export_report(run_root: Path, export_plan: dict[str, Any], out: Path) -> dict[str, Any]:
    paths = export_plan.get("paths") if isinstance(export_plan.get("paths"), dict) else {}
    merged_hf = Path(str(paths.get("merged_hf", Path(run_root) / "merged_hf")))
    fp16 = Path(str(paths.get("gguf_fp16", Path(run_root) / "gguf" / "model.fp16.gguf")))
    q4 = Path(str(paths.get("gguf_q4_K_M", Path(run_root) / "gguf" / "model.q4_K_M.gguf")))

    fatal_failures = list(export_plan.get("fatal_failures", [])) if isinstance(export_plan.get("fatal_failures"), list) else []
    merged_records, merged_failures = _directory_manifest(merged_hf, ("*.safetensors",))
    fatal_failures.extend(merged_failures)
    fp16_record, fp16_failures = _artifact_record(fp16)
    q4_record, q4_failures = _artifact_record(q4)
    fatal_failures.extend(fp16_failures)
    fatal_failures.extend(q4_failures)

    tokenizer_files = []
    for name in ("tokenizer.json", "tokenizer.model", "tokenizer_config.json", "special_tokens_map.json", "vocab.json", "merges.txt"):
        p = merged_hf / name
        if p.exists():
            record, _ = _artifact_record(p, required=False)
            tokenizer_files.append(record)
    if not tokenizer_files:
        fatal_failures.append({"gate": "merged_hf_tokenizer", "reason": f"no tokenizer evidence found under {merged_hf}"})

    report = {
        "ok": not fatal_failures,
        "next_phase_allowed": not fatal_failures,
        "requirements_covered": list(REQUIREMENTS_COVERED),
        "run_root": str(run_root),
        "phase9_report": export_plan.get("phase9_report"),
        "phase9_handoff": export_plan.get("phase9_handoff"),
        "paths": paths,
        "llama_cpp": export_plan.get("llama_cpp"),
        "commands": export_plan.get("commands"),
        "artifacts": {
            "merged_hf_safetensors": merged_records,
            "merged_hf_tokenizer": tokenizer_files,
            "gguf_fp16": fp16_record,
            "gguf_q4_K_M": q4_record,
        },
        "fatal_failures": fatal_failures,
        "warnings": [],
    }
    out = Path(out)
    _require_output_path(out, run_root=Path(run_root))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def evaluate_export_report(report_path: Path) -> dict[str, Any]:
    report = _load_json(Path(report_path))
    fatal_failures = list(report.get("fatal_failures", [])) if isinstance(report.get("fatal_failures"), list) else []
    if report.get("ok") is not True:
        fatal_failures.append({"gate": "export_report", "reason": "export report is red"})
    if "GGUF4B-01" not in report.get("requirements_covered", []):
        fatal_failures.append({"gate": "requirements_covered", "reason": "GGUF4B-01 missing"})
    text = json.dumps(report, ensure_ascii=False)
    for needle in ("merged_hf", "model.fp16.gguf", "model.q4_K_M.gguf", "sha256", "convert_hf_to_gguf.py", "llama-quantize"):
        if needle not in text:
            fatal_failures.append({"gate": "report_content", "reason": f"missing {needle}"})
    result = dict(report)
    result["ok"] = not fatal_failures
    result["fatal_failures"] = fatal_failures
    return result


def phase10_wrapper_commands(run_root: Path = PHASE9_RUN_ROOT, llama_cpp_dir: Path = DEFAULT_LLAMA_CPP) -> list[dict[str, Any]]:
    run_root = Path(run_root)
    llama_cpp_dir = Path(llama_cpp_dir)
    return [
        {
            "env": {"LLAMA_CPP_DIR": str(llama_cpp_dir)},
            "argv": [
                str(PROJECT_ROOT / ".venv" / "bin" / "python"),
                "-m",
                "tsc_cycle.student.export_gguf",
                "--phase9-report",
                str(run_root / "phase9_sft_report.json"),
                "--run-root",
                str(run_root),
                "--llama-cpp",
                str(llama_cpp_dir),
                "--merged-dir",
                str(run_root / "merged_hf"),
                "--fp16-gguf",
                str(run_root / "gguf" / "model.fp16.gguf"),
                "--q4-gguf",
                str(run_root / "gguf" / "model.q4_K_M.gguf"),
                "--report",
                str(run_root / "phase10_export_report.json"),
            ],
            "tools": {
                "convert": str(llama_cpp_dir / "convert_hf_to_gguf.py"),
                "quantize": str(llama_cpp_dir / "llama-quantize"),
            },
        }
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate v4 Phase 10 export evidence")
    parser.add_argument("--phase9-report", default=str(DEFAULT_PHASE9_REPORT))
    parser.add_argument("--run-root", default=str(PHASE9_RUN_ROOT))
    parser.add_argument("--llama-cpp", default=str(DEFAULT_LLAMA_CPP))
    parser.add_argument("--merged-dir", default=None)
    parser.add_argument("--fp16-gguf", default=None)
    parser.add_argument("--q4-gguf", default=None)
    parser.add_argument("--report", default=None)
    parser.add_argument("--evaluate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = Path(args.report) if args.report else Path(args.run_root) / "phase10_export_report.json"
    if args.evaluate_only:
        result = evaluate_export_report(out)
    else:
        plan = plan_phase10_export(
            phase9_report=Path(args.phase9_report),
            run_root=Path(args.run_root),
            llama_cpp_dir=Path(args.llama_cpp),
            merged_dir=Path(args.merged_dir) if args.merged_dir else None,
            fp16_gguf=Path(args.fp16_gguf) if args.fp16_gguf else None,
            q4_gguf=Path(args.q4_gguf) if args.q4_gguf else None,
            report=out,
        )
        result = write_export_report(Path(args.run_root), plan, out)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("ok") is True else 1


__all__ = [
    "FROZEN_BASELINE_ROOT",
    "PHASE9_RUN_ROOT",
    "load_phase9_handoff",
    "build_export_plan",
    "plan_phase10_export",
    "write_export_report",
    "evaluate_export_report",
    "phase10_wrapper_commands",
    "is_forbidden_output_path",
    "build_parser",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
