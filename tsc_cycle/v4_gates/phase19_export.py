from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from tsc_cycle.student.sft_v42 import validate_run_root
from tsc_cycle.v4_gates.phase19_training import validate_phase19_training_report

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
DEFAULT_RUN_ROOT = PROJECT_ROOT / "runs" / "v4.2-4B-20260518T111519Z"
DEFAULT_PHASE19_REPORT = DEFAULT_RUN_ROOT / "phase19_sft_report.json"
DEFAULT_LLAMA_CPP = Path("/home/samuel/projects/EvoProgTSC/llama.cpp")
FROZEN_BASELINE_ROOT = PROJECT_ROOT / "runs" / "20260507T032419Z"
REQUIREMENTS_COVERED = ["TRAIN-02"]
FORBIDDEN_ROOT_NAMES = {"20260507T032419Z"}
MERGED_HF_REQUIRED_FILES = ("config.json",)
MERGED_HF_OPTIONAL_FILES = ("generation_config.json", "model.safetensors.index.json")


class Phase19ExportError(RuntimeError):
    """Fail-closed Phase 19 export planning/evidence error."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not Path(path).is_file():
        return {}
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _is_under(path: Path, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def _is_broad_root(path: Path) -> bool:
    resolved = Path(path).resolve()
    broad_roots = {
        PROJECT_ROOT.resolve(),
        (PROJECT_ROOT / "runs").resolve(),
        (PROJECT_ROOT / "data").resolve(),
        (PROJECT_ROOT / "artifacts").resolve(),
        (PROJECT_ROOT / "data" / "v4_2").resolve(),
        (PROJECT_ROOT / "artifacts" / "v4_2").resolve(),
    }
    return resolved in broad_roots


def is_forbidden_output_path(path: Path) -> bool:
    candidate = Path(path)
    return _is_under(candidate, FROZEN_BASELINE_ROOT) or "v4.0-4B-" in candidate.as_posix()


def _require_v42_run_root(run_root: Path) -> Path:
    root = validate_run_root(run_root)
    if root.name in FORBIDDEN_ROOT_NAMES or "v4.0-4B-" in root.as_posix():
        raise ValueError(f"Phase 19 export run root must be v4.2 only: {root}")
    if _is_broad_root(root):
        raise ValueError(f"Phase 19 export run root is too broad: {root}")
    return root


def _require_output_path(path: Path, *, run_root: Path) -> None:
    output = Path(path)
    if is_forbidden_output_path(output):
        raise ValueError(f"refusing forbidden Phase 19 export output path: {output}")
    if _is_broad_root(output):
        raise ValueError(f"refusing broad Phase 19 export output path: {output}")
    if not _is_under(output, run_root):
        raise ValueError(f"Phase 19 export output must stay under run root {run_root}: {output}")


def _tool(path: Path, name: str, failures: list[dict[str, str]], *, required: bool = True) -> str:
    path = Path(path)
    name_ok = path.name == name
    ok = name_ok and path.is_file() and path.stat().st_size > 0 and (name.endswith(".py") or os.access(path, os.X_OK))
    if required and not ok:
        failures.append({"gate": name, "reason": f"missing or non-executable llama.cpp tool: {path}"})
    return str(path)


def _same_path(left: Any, right: Any) -> bool:
    try:
        return Path(str(left)).resolve() == Path(str(right)).resolve()
    except (OSError, RuntimeError):
        return str(left) == str(right)


def load_phase19_handoff(run_root: Path, phase19_report: Path | None = None) -> dict[str, Any]:
    report_path = Path(phase19_report) if phase19_report is not None else Path(run_root) / "phase19_sft_report.json"
    validation = validate_phase19_training_report(run_root, report_path=report_path)
    if validation.get("ok") is not True or validation.get("next_phase_allowed") is not True:
        return {
            "ok": False,
            "next_phase_allowed": False,
            "report_path": str(report_path),
            "run_root": str(run_root),
            "requirements_covered": [],
            "fatal_failures": validation.get("fatal_failures", []),
        }
    return {
        "ok": True,
        "next_phase_allowed": True,
        "report_path": str(report_path),
        "run_root": str(run_root),
        "adapter_path": validation.get("adapter_path"),
        "adapter_sha256": validation.get("artifact_manifest", {}).get("sha256", {}).get("adapter_sha256"),
        "training_report_sha256": validation.get("artifact_manifest", {}).get("sha256", {}).get("training_report"),
        "data_manifest_sha256": validation.get("artifact_manifest", {}).get("sha256", {}).get("data_manifest_sha256"),
        "requirements_covered": ["TRAIN-01"],
        "training_validation": validation,
    }


def phase19_wrapper_commands(run_root: Path = DEFAULT_RUN_ROOT, llama_cpp_dir: Path = DEFAULT_LLAMA_CPP) -> list[dict[str, Any]]:
    run_root = Path(run_root)
    llama_cpp_dir = Path(llama_cpp_dir)
    return [
        {
            "env": {"LLAMA_CPP_DIR": str(llama_cpp_dir), "TRITON_PTXAS_PATH": "/usr/local/cuda/bin/ptxas"},
            "launcher": str(PROJECT_ROOT / "scripts" / "dgx_spark" / "run_safe.sh"),
            "argv": [
                str(PROJECT_ROOT / "scripts" / "dgx_spark" / "run_safe.sh"),
                "100G",
                "--",
                str(PROJECT_ROOT / ".venv" / "bin" / "python"),
                "-m",
                "tsc_cycle.student.export_gguf",
                "--export-phase",
                "phase19",
                "--phase19-report",
                str(run_root / "phase19_sft_report.json"),
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
                str(run_root / "phase19_export_report.json"),
            ],
            "tools": {
                "convert": str(llama_cpp_dir / "convert_hf_to_gguf.py"),
                "quantize": str(llama_cpp_dir / "llama-quantize"),
            },
        }
    ]


def build_export_plan(
    *,
    run_root: Path = DEFAULT_RUN_ROOT,
    phase19_report: Path | None = None,
    llama_cpp_dir: Path = DEFAULT_LLAMA_CPP,
    merged_dir: Path | None = None,
    fp16_gguf: Path | None = None,
    q4_gguf: Path | None = None,
    report: Path | None = None,
) -> dict[str, Any]:
    root = _require_v42_run_root(Path(run_root))
    merged_dir = Path(merged_dir) if merged_dir is not None else root / "merged_hf"
    fp16_gguf = Path(fp16_gguf) if fp16_gguf is not None else root / "gguf" / "model.fp16.gguf"
    q4_gguf = Path(q4_gguf) if q4_gguf is not None else root / "gguf" / "model.q4_K_M.gguf"
    export_report = Path(report) if report is not None else root / "phase19_export_report.json"
    for output_path in (merged_dir, fp16_gguf, q4_gguf, export_report):
        _require_output_path(output_path, run_root=root)

    fatal_failures: list[dict[str, str]] = []
    handoff = load_phase19_handoff(root, phase19_report)
    if handoff.get("ok") is not True or "TRAIN-01" not in handoff.get("requirements_covered", []):
        fatal_failures.append({"gate": "phase19_handoff", "reason": "Phase 19 training handoff is not green or lacks TRAIN-01 coverage"})

    llama_cpp_dir = Path(llama_cpp_dir)
    convert = Path(_tool(llama_cpp_dir / "convert_hf_to_gguf.py", "convert_hf_to_gguf.py", fatal_failures))
    quantize = Path(_tool(llama_cpp_dir / "llama-quantize", "llama-quantize", fatal_failures))
    tokenize_path = llama_cpp_dir / "llama-tokenize"
    if not tokenize_path.exists():
        tokenize_path = llama_cpp_dir / "llama-cli"
    tokenize = Path(_tool(tokenize_path, "llama-tokenize", fatal_failures, required=False))
    server = Path(_tool(llama_cpp_dir / "llama-server", "llama-server", fatal_failures, required=False))

    commands = {
        "merge_hf": [sys.executable, "-m", "tsc_cycle.student.export_gguf", "--export-phase", "phase19", "--phase19-report", str(Path(phase19_report) if phase19_report else root / "phase19_sft_report.json"), "--run-root", str(root), "--merged-dir", str(merged_dir)],
        "convert_fp16": [sys.executable, str(convert), str(merged_dir), "--outfile", str(fp16_gguf), "--outtype", "f16"],
        "quantize_q4_K_M": [str(quantize), str(fp16_gguf), str(q4_gguf), "Q4_K_M"],
    }

    return {
        "ok": not fatal_failures,
        "next_phase_allowed": not fatal_failures,
        "requirements_covered": list(REQUIREMENTS_COVERED),
        "phase19_report": str(Path(phase19_report) if phase19_report else root / "phase19_sft_report.json"),
        "run_root": str(root),
        "adapter_path": handoff.get("adapter_path"),
        "adapter_sha256": handoff.get("adapter_sha256"),
        "phase19_handoff": handoff,
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
        "wrapper_commands": phase19_wrapper_commands(root, llama_cpp_dir),
        "fatal_failures": fatal_failures,
        "warnings": [],
    }


def _artifact_record(path: Path, *, required: bool = True) -> tuple[dict[str, Any], list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    record: dict[str, Any] = {"path": str(path), "exists": Path(path).exists()}
    if Path(path).is_file():
        size = Path(path).stat().st_size
        record.update({"size_bytes": size, "sha256": sha256_file(Path(path)) if size > 0 else None})
        if required and size <= 0:
            failures.append({"gate": "artifact_size", "reason": f"zero-byte artifact: {path}"})
    elif required:
        failures.append({"gate": "artifact_exists", "reason": f"missing artifact: {path}"})
    return record, failures


def _directory_manifest(root: Path, patterns: tuple[str, ...]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    if not Path(root).is_dir():
        return records, [{"gate": "merged_hf", "reason": f"missing merged HF directory: {root}"}]
    for pattern in patterns:
        for path in sorted(Path(root).glob(pattern)):
            if path.is_file():
                record, record_failures = _artifact_record(path)
                records.append(record)
                failures.extend(record_failures)
    if not records:
        failures.append({"gate": "merged_hf_safetensors", "reason": f"no safetensors found under {root}"})
    return records, failures


def _hf_materializer_manifest(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    records: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    if not Path(root).is_dir():
        return records, [{"gate": "merged_hf_materializer", "reason": f"missing merged HF directory: {root}"}]
    for name in MERGED_HF_REQUIRED_FILES:
        path = Path(root) / name
        record, record_failures = _artifact_record(path)
        records.append(record)
        failures.extend(record_failures)
    for name in MERGED_HF_OPTIONAL_FILES:
        path = Path(root) / name
        if path.exists():
            record, record_failures = _artifact_record(path, required=False)
            records.append(record)
            failures.extend(record_failures)
    return records, failures


def _records_match(reported_records: Any, actual_records: list[dict[str, Any]], gate: str, label: str) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    reported = reported_records if isinstance(reported_records, list) else []
    actual_by_path = {record.get("path"): record for record in actual_records if isinstance(record.get("path"), str)}
    reported_paths: set[str] = set()
    for item in reported:
        if not isinstance(item, dict):
            failures.append({"gate": gate, "reason": f"malformed {label} record"})
            continue
        item_path = item.get("path")
        if not isinstance(item_path, str) or not item_path:
            failures.append({"gate": gate, "reason": f"malformed {label} path"})
            continue
        reported_paths.add(item_path)
        actual = actual_by_path.get(item_path)
        if actual is None or item.get("sha256") != actual.get("sha256"):
            failures.append({"gate": gate, "reason": f"sha256 mismatch for {label}: {item_path}"})
    if reported_paths != set(actual_by_path):
        failures.append({"gate": gate, "reason": f"{label} report does not match on-disk artifacts"})
    return failures


def write_export_report(run_root: Path, export_plan: dict[str, Any], out: Path) -> dict[str, Any]:
    root = _require_v42_run_root(Path(run_root))
    paths = export_plan.get("paths") if isinstance(export_plan.get("paths"), dict) else {}
    merged_hf = Path(str(paths.get("merged_hf", root / "merged_hf")))
    fp16 = Path(str(paths.get("gguf_fp16", root / "gguf" / "model.fp16.gguf")))
    q4 = Path(str(paths.get("gguf_q4_K_M", root / "gguf" / "model.q4_K_M.gguf")))
    out = Path(out)
    for output_path in (merged_hf, fp16, q4, out):
        _require_output_path(output_path, run_root=root)

    fatal_failures = list(export_plan.get("fatal_failures", [])) if isinstance(export_plan.get("fatal_failures"), list) else []
    merged_records, merged_failures = _directory_manifest(merged_hf, ("*.safetensors",))
    hf_materializer_records, hf_materializer_failures = _hf_materializer_manifest(merged_hf)
    fatal_failures.extend(merged_failures)
    fatal_failures.extend(hf_materializer_failures)
    fp16_record, fp16_failures = _artifact_record(fp16)
    q4_record, q4_failures = _artifact_record(q4)
    fatal_failures.extend(fp16_failures)
    fatal_failures.extend(q4_failures)

    tokenizer_files: list[dict[str, Any]] = []
    tokenizer_materializer_ok = ((merged_hf / "tokenizer.json").is_file() and (merged_hf / "tokenizer.json").stat().st_size > 0) or ((merged_hf / "tokenizer.model").is_file() and (merged_hf / "tokenizer.model").stat().st_size > 0) or ((merged_hf / "vocab.json").is_file() and (merged_hf / "vocab.json").stat().st_size > 0 and (merged_hf / "merges.txt").is_file() and (merged_hf / "merges.txt").stat().st_size > 0)
    if not tokenizer_materializer_ok:
        fatal_failures.append({"gate": "merged_hf_tokenizer", "reason": f"no complete tokenizer materializer evidence found under {merged_hf}"})
    for name in ("tokenizer.json", "tokenizer.model", "tokenizer_config.json", "special_tokens_map.json", "vocab.json", "merges.txt"):
        path = merged_hf / name
        if path.exists():
            record, _ = _artifact_record(path, required=False)
            tokenizer_files.append(record)
    if not tokenizer_files:
        fatal_failures.append({"gate": "merged_hf_tokenizer", "reason": f"no tokenizer/materializer evidence found under {merged_hf}"})

    report = {
        "ok": not fatal_failures,
        "next_phase_allowed": not fatal_failures,
        "requirements_covered": list(REQUIREMENTS_COVERED) if not fatal_failures else [],
        "run_root": str(root),
        "phase19_report": export_plan.get("phase19_report"),
        "phase19_handoff": export_plan.get("phase19_handoff"),
        "paths": dict(paths),
        "llama_cpp": export_plan.get("llama_cpp"),
        "commands": export_plan.get("commands"),
        "wrapper_commands": export_plan.get("wrapper_commands"),
        "artifacts": {
            "merged_hf_safetensors": merged_records,
            "merged_hf_materializer": hf_materializer_records,
            "merged_hf_tokenizer": tokenizer_files,
            "gguf_fp16": fp16_record,
            "gguf_q4_K_M": q4_record,
        },
        "fatal_failures": fatal_failures,
        "warnings": [],
    }
    _write_json(out, report)
    return report


def validate_phase19_export_report(run_root: Path, report_path: Path | None = None, out: Path | None = None) -> dict[str, Any]:
    root = _require_v42_run_root(Path(run_root))
    path = Path(report_path) if report_path is not None else root / "phase19_export_report.json"
    gates: dict[str, Any] = {}
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        failures = [{"gate": "report_path", "reason": f"export report must stay under run root: {path}"}]
        result = {"ok": False, "next_phase_allowed": False, "requirements_covered": [], "gates": gates, "fatal_failures": failures, "report_path": str(path)}
        if out is not None:
            _write_json(Path(out), result)
        return result
    report = _read_json(path)
    failures = list(report.get("fatal_failures", [])) if isinstance(report.get("fatal_failures"), list) else []
    if "fatal_failures" in report and not isinstance(report.get("fatal_failures"), list):
        failures.append({"gate": "fatal_failures", "reason": "fatal_failures must be a list"})
    elif failures:
        failures.append({"gate": "fatal_failures", "reason": "export report contains fatal_failures"})

    report_green_ok = report.get("ok") is True and report.get("next_phase_allowed") is True
    gates["report_green"] = {"ok": report_green_ok, "data": {"ok": report.get("ok"), "next_phase_allowed": report.get("next_phase_allowed")}}
    if not report_green_ok:
        failures.append({"gate": "next_phase_allowed", "reason": "export report ok and next_phase_allowed must both be true"})

    report_run_root_ok = str(report.get("run_root")) == str(root)
    gates["run_root"] = {"ok": report_run_root_ok, "data": {"run_root": report.get("run_root")}}
    if not report_run_root_ok:
        failures.append({"gate": "run_root", "reason": "report run_root does not match requested v4.2 root"})

    covered_raw = report.get("requirements_covered", [])
    if not isinstance(covered_raw, list):
        failures.append({"gate": "requirements_covered", "reason": "requirements_covered must be a list"})
        covered = set()
    else:
        covered = {str(item) for item in covered_raw}
    requirements_ok = "TRAIN-02" in covered
    gates["requirements_covered"] = {"ok": requirements_ok, "data": {"covered": sorted(covered)}}
    if not requirements_ok:
        failures.append({"gate": "requirements_covered", "reason": "TRAIN-02 coverage missing"})

    phase19_report = Path(report.get("phase19_report")) if isinstance(report.get("phase19_report"), str) else root / "phase19_sft_report.json"
    training_validation = validate_phase19_training_report(root, report_path=phase19_report)
    handoff = report.get("phase19_handoff") if isinstance(report.get("phase19_handoff"), dict) else {}
    training_sha = training_validation.get("artifact_manifest", {}).get("sha256", {}) if isinstance(training_validation.get("artifact_manifest"), dict) else {}
    expected_handoff = {
        "adapter_path": training_validation.get("adapter_path"),
        "adapter_sha256": training_sha.get("adapter_sha256"),
        "training_report_sha256": training_sha.get("training_report"),
        "data_manifest_sha256": training_sha.get("data_manifest_sha256"),
    }
    handoff_matches = _same_path(handoff.get("adapter_path"), expected_handoff["adapter_path"]) and handoff.get("adapter_sha256") == expected_handoff["adapter_sha256"] and handoff.get("training_report_sha256") == expected_handoff["training_report_sha256"] and handoff.get("data_manifest_sha256") == expected_handoff["data_manifest_sha256"]
    handoff_ok = training_validation.get("ok") is True and "TRAIN-01" in training_validation.get("requirements_covered", []) and handoff_matches
    gates["phase19_handoff"] = {"ok": handoff_ok, "data": {"report_path": str(phase19_report), "requirements_covered": training_validation.get("requirements_covered", []), "reported_requirements_covered": handoff.get("requirements_covered", []), "expected_handoff": expected_handoff, "reported_handoff": {key: handoff.get(key) for key in expected_handoff}}}
    if not handoff_ok:
        failures.append({"gate": "phase19_handoff", "reason": "accepted export report must revalidate green TRAIN-01 training handoff and matching artifact evidence"})

    paths = report.get("paths") if isinstance(report.get("paths"), dict) else {}
    validated_paths: dict[str, Path] = {}
    for key in ("merged_hf", "gguf_fp16", "gguf_q4_K_M", "export_report"):
        value = paths.get(key)
        if not isinstance(value, str) or not value:
            failures.append({"gate": "paths", "reason": f"missing export path: {key}"})
            continue
        candidate = Path(value)
        try:
            _require_output_path(candidate, run_root=root)
            validated_paths[key] = candidate
        except ValueError as exc:
            failures.append({"gate": "paths", "reason": str(exc)})

    commands = report.get("commands") if isinstance(report.get("commands"), dict) else {}
    commands_text = json.dumps(commands, ensure_ascii=False).lower()
    for forbidden in ("pip install", "uv pip install", "vllm", "flash-attn", "unsloth", "axolotl", "git worktree", "runs/20260507t032419z", "runs/v4.0-4b-"):
        if forbidden in commands_text:
            failures.append({"gate": "commands", "reason": f"forbidden command evidence marker: {forbidden}"})

    llama_cpp = report.get("llama_cpp") if isinstance(report.get("llama_cpp"), dict) else {}
    llama_root_value = llama_cpp.get("root")
    llama_root = Path(llama_root_value) if isinstance(llama_root_value, str) and llama_root_value else None
    if llama_root is None or not llama_root.is_dir():
        failures.append({"gate": "llama_cpp", "reason": "missing llama.cpp root evidence"})
    tool_paths: dict[str, Path] = {}
    for key, tool_name in (("convert", "convert_hf_to_gguf.py"), ("quantize", "llama-quantize")):
        tool_path = llama_cpp.get(key)
        if not isinstance(tool_path, str) or not tool_path:
            failures.append({"gate": tool_name, "reason": f"missing llama.cpp tool evidence: {key}"})
            continue
        candidate = Path(tool_path)
        tool_paths[key] = candidate
        if llama_root is not None:
            try:
                if candidate.resolve() != (llama_root / tool_name).resolve():
                    failures.append({"gate": tool_name, "reason": f"llama.cpp tool path must be under reported root: {candidate}"})
            except OSError as exc:
                failures.append({"gate": tool_name, "reason": f"invalid llama.cpp tool path: {exc}"})
        _tool(candidate, tool_name, failures)

    merge_cmd = commands.get("merge_hf") if isinstance(commands.get("merge_hf"), list) else []
    convert_cmd = commands.get("convert_fp16") if isinstance(commands.get("convert_fp16"), list) else []
    quantize_cmd = commands.get("quantize_q4_K_M") if isinstance(commands.get("quantize_q4_K_M"), list) else []
    merged_cmd_path = Path(str(convert_cmd[2])) if len(convert_cmd) > 2 else None
    fp16_out_idx = convert_cmd.index("--outfile") + 1 if "--outfile" in convert_cmd and convert_cmd.index("--outfile") + 1 < len(convert_cmd) else None
    fp16_cmd_path = Path(str(convert_cmd[fp16_out_idx])) if fp16_out_idx is not None else None
    export_phase_idx = merge_cmd.index("--export-phase") + 1 if "--export-phase" in merge_cmd and merge_cmd.index("--export-phase") + 1 < len(merge_cmd) else None
    phase19_report_idx = merge_cmd.index("--phase19-report") + 1 if "--phase19-report" in merge_cmd and merge_cmd.index("--phase19-report") + 1 < len(merge_cmd) else None
    run_root_idx = merge_cmd.index("--run-root") + 1 if "--run-root" in merge_cmd and merge_cmd.index("--run-root") + 1 < len(merge_cmd) else None
    merged_dir_idx = merge_cmd.index("--merged-dir") + 1 if "--merged-dir" in merge_cmd and merge_cmd.index("--merged-dir") + 1 < len(merge_cmd) else None
    outtype_idx = convert_cmd.index("--outtype") + 1 if "--outtype" in convert_cmd and convert_cmd.index("--outtype") + 1 < len(convert_cmd) else None
    command_checks = [
        ("-m" in merge_cmd and "tsc_cycle.student.export_gguf" in merge_cmd, "merge_hf must invoke tsc_cycle.student.export_gguf"),
        (export_phase_idx is not None and str(merge_cmd[export_phase_idx]) == "phase19", "merge_hf must use export phase19"),
        (phase19_report_idx is not None and _same_path(merge_cmd[phase19_report_idx], phase19_report), "merge_hf must use reported phase19 report"),
        (run_root_idx is not None and _same_path(merge_cmd[run_root_idx], root), "merge_hf must use reported run_root"),
        (merged_dir_idx is not None and "merged_hf" in validated_paths and _same_path(merge_cmd[merged_dir_idx], validated_paths["merged_hf"]), "merge_hf must write reported merged_hf path"),
        (len(convert_cmd) > 1 and "convert" in tool_paths and _same_path(convert_cmd[1], tool_paths["convert"]), "convert_fp16 must use reported convert tool"),
        (merged_cmd_path is not None and "merged_hf" in validated_paths and _same_path(merged_cmd_path, validated_paths["merged_hf"]), "convert_fp16 must use reported merged_hf path"),
        (fp16_cmd_path is not None and "gguf_fp16" in validated_paths and _same_path(fp16_cmd_path, validated_paths["gguf_fp16"]), "convert_fp16 must write reported fp16 path"),
        (outtype_idx is not None and str(convert_cmd[outtype_idx]) == "f16", "convert_fp16 must use f16 outtype"),
        (len(quantize_cmd) > 0 and "quantize" in tool_paths and _same_path(quantize_cmd[0], tool_paths["quantize"]), "quantize_q4_K_M must use reported quantize tool"),
        (len(quantize_cmd) > 1 and "gguf_fp16" in validated_paths and _same_path(quantize_cmd[1], validated_paths["gguf_fp16"]), "quantize_q4_K_M must read reported fp16 path"),
        (len(quantize_cmd) > 2 and "gguf_q4_K_M" in validated_paths and _same_path(quantize_cmd[2], validated_paths["gguf_q4_K_M"]), "quantize_q4_K_M must write reported q4_K_M path"),
        (len(quantize_cmd) > 3 and str(quantize_cmd[3]) == "Q4_K_M", "quantize_q4_K_M must use Q4_K_M quantization"),
    ]
    for ok, reason in command_checks:
        if not ok:
            failures.append({"gate": "commands", "reason": reason})

    artifacts = report.get("artifacts") if isinstance(report.get("artifacts"), dict) else {}
    merged_path = validated_paths.get("merged_hf")
    actual_merged, merged_failures = _directory_manifest(merged_path, ("*.safetensors",)) if merged_path is not None else ([], [{"gate": "paths", "reason": "invalid merged_hf path; skipped artifact reads"}])
    actual_hf_materializer, hf_materializer_failures = _hf_materializer_manifest(merged_path) if merged_path is not None else ([], [])
    failures.extend(merged_failures)
    failures.extend(hf_materializer_failures)
    failures.extend(_records_match(artifacts.get("merged_hf_safetensors"), actual_merged, "artifact_hash", "merged HF safetensors"))
    failures.extend(_records_match(artifacts.get("merged_hf_materializer"), actual_hf_materializer, "artifact_hash", "merged HF materializer"))

    for key, path_key in (("gguf_fp16", "gguf_fp16"), ("gguf_q4_K_M", "gguf_q4_K_M")):
        artifact_path = validated_paths.get(path_key)
        if artifact_path is None:
            actual_record = {}
            failures.append({"gate": "paths", "reason": f"invalid {path_key} path; skipped artifact reads"})
        else:
            actual_record, actual_failures = _artifact_record(artifact_path)
            failures.extend(actual_failures)
        record = artifacts.get(key) if isinstance(artifacts.get(key), dict) else {}
        if not record.get("sha256"):
            failures.append({"gate": "artifact_hash", "reason": f"missing sha256 for {key}"})
        if record.get("exists") is not True:
            failures.append({"gate": "artifact_exists", "reason": f"missing artifact for {key}"})
        if record.get("sha256") != actual_record.get("sha256"):
            failures.append({"gate": "artifact_hash", "reason": f"sha256 mismatch for {key}"})

    tokenizer_records = artifacts.get("merged_hf_tokenizer") if isinstance(artifacts.get("merged_hf_tokenizer"), list) else []
    actual_tokenizer_records: list[dict[str, Any]] = []
    tokenizer_materializer_ok = False
    if merged_path is not None:
        tokenizer_materializer_ok = ((merged_path / "tokenizer.json").is_file() and (merged_path / "tokenizer.json").stat().st_size > 0) or ((merged_path / "tokenizer.model").is_file() and (merged_path / "tokenizer.model").stat().st_size > 0) or ((merged_path / "vocab.json").is_file() and (merged_path / "vocab.json").stat().st_size > 0 and (merged_path / "merges.txt").is_file() and (merged_path / "merges.txt").stat().st_size > 0)
    if not tokenizer_materializer_ok:
        failures.append({"gate": "artifact_hash", "reason": "missing complete tokenizer materializer evidence"})
    if merged_path is not None:
        for name in ("tokenizer.json", "tokenizer.model", "tokenizer_config.json", "special_tokens_map.json", "vocab.json", "merges.txt"):
            token_path = merged_path / name
            if token_path.exists():
                token_record, _ = _artifact_record(token_path, required=False)
                actual_tokenizer_records.append(token_record)
    if not tokenizer_records or not actual_tokenizer_records:
        failures.append({"gate": "artifact_hash", "reason": "missing merged HF tokenizer/materializer evidence"})
    else:
        failures.extend(_records_match(tokenizer_records, actual_tokenizer_records, "artifact_hash", "tokenizer evidence"))

    result = dict(report)
    result.update({
        "ok": not failures,
        "next_phase_allowed": not failures,
        "requirements_covered": list(REQUIREMENTS_COVERED) if not failures else [req for req in REQUIREMENTS_COVERED if req in covered],
        "gates": gates,
        "fatal_failures": failures,
        "report_path": str(path),
    })
    if out is not None:
        _write_json(Path(out), result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan or validate v4.2 Phase 19 merged HF/GGUF export evidence")
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--phase19-report", type=Path, default=None)
    parser.add_argument("--llama-cpp", type=Path, default=DEFAULT_LLAMA_CPP)
    parser.add_argument("--merged-dir", type=Path, default=None)
    parser.add_argument("--fp16-gguf", type=Path, default=None)
    parser.add_argument("--q4-gguf", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--evaluate-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = args.report or args.run_root / "phase19_export_report.json"
    if args.evaluate_only:
        result = validate_phase19_export_report(args.run_root, report_path=out)
    else:
        plan = build_export_plan(
            run_root=args.run_root,
            phase19_report=args.phase19_report,
            llama_cpp_dir=args.llama_cpp,
            merged_dir=args.merged_dir,
            fp16_gguf=args.fp16_gguf,
            q4_gguf=args.q4_gguf,
            report=out,
        )
        result = write_export_report(args.run_root, plan, out)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    return 0 if result.get("ok") is True else 1


__all__ = [
    "DEFAULT_LLAMA_CPP",
    "DEFAULT_PHASE19_REPORT",
    "DEFAULT_RUN_ROOT",
    "FROZEN_BASELINE_ROOT",
    "Phase19ExportError",
    "build_export_plan",
    "build_parser",
    "is_forbidden_output_path",
    "load_phase19_handoff",
    "main",
    "phase19_wrapper_commands",
    "sha256_file",
    "validate_phase19_export_report",
    "write_export_report",
]


if __name__ == "__main__":
    raise SystemExit(main())
