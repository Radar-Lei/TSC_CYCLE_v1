from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

FROZEN_V1_ROOT = Path("/home/samuel/TSC_CYCLE/runs/20260507T032419Z")
DEFAULT_PHASE7_REPORT = Path("artifacts/v4/phase7/phase7_gate_report.json")
DEFAULT_SOURCE_MANIFEST = Path("artifacts/v4/phase8/source_manifest.json")
DEFAULT_CLEANING_REPORT = Path("artifacts/v4/phase8/cleaning_report.json")
DEFAULT_REBUILD_REPORT = Path("artifacts/v4/phase8/rebuild_report.json")
DEFAULT_DATASET_CARD = Path("data/dataset_card.md")
DEFAULT_OUT = Path("artifacts/v4/phase8/phase8_gate_report.json")
DEFAULT_SPLIT_DIR = Path("data/v4/phase8/splits")
DEFAULT_TOKENIZED_DIR = Path("data/v4/phase8/tokenized")
REQUIREMENTS_EXPECTED = ["DATA4B-01", "DATA4B-02", "DATA4B-03", "DATA4B-04", "DATA4B-05"]
NON_CARD_REQUIREMENTS = ["DATA4B-01", "DATA4B-02", "DATA4B-03", "DATA4B-04"]
DATASET_CARD_HEADINGS = (
    "## v4.0 Phase 8 — 4B dataset rebuild",
    "## v4 Phase 8 Dataset Rebuild",
)
DATASET_CARD_HEADING = DATASET_CARD_HEADINGS[0]
DATASET_CARD_REQUIRED_PHRASES = ("source", "split", "normalization", "artifact")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _assert_not_frozen_output(path: Path) -> None:
    if _is_relative_to(path, FROZEN_V1_ROOT):
        raise ValueError(f"refusing to write Phase 8 artifact under frozen v1 baseline root: {path}")


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"missing artifact: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON {path}: {exc}"
    if not isinstance(payload, dict):
        return None, f"malformed JSON {path}: expected object"
    return payload, None


def _add_failure(fatal_failures: list[dict[str, str]], gate: str, reason: str) -> None:
    fatal_failures.append({"gate": gate, "reason": reason})


def _gate(ok: bool, reason: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": bool(ok), "reason": reason, "data": data or {}}


def _json_artifact_gate(
    *,
    name: str,
    path: Path,
    required_requirements: set[str] | None = None,
    fatal_failures: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any] | None, set[str]]:
    payload, err = _load_json(path)
    covered: set[str] = set()
    reasons: list[str] = []
    if err:
        reasons.append(err)
        _add_failure(fatal_failures, name, err)
    if payload is not None:
        covered.update(str(req) for req in payload.get("requirements_covered", []))
        for warning in payload.get("warnings", []):
            warnings.append({"gate": name, "warning": str(warning)})
        for failure in payload.get("fatal_failures", []) or []:
            if isinstance(failure, dict):
                reason = str(failure.get("reason", "sub-gate failed"))
                warnings.append({"gate": str(failure.get("gate", name)), "warning": reason})
        if payload.get("ok") is not True:
            reasons.append(f"{name} ok is not true")
            _add_failure(fatal_failures, name, f"{name} ok is not true")
        if required_requirements is not None:
            missing = sorted(required_requirements - covered)
            if missing:
                reason = f"missing requirements: {', '.join(missing)}"
                reasons.append(reason)
                _add_failure(fatal_failures, name, reason)
    reason_text = "; ".join(reasons) if reasons else None
    return _gate(reason_text is None, reason_text, payload), payload, covered


def _phase7_gate(path: Path, fatal_failures: list[dict[str, str]], warnings: list[dict[str, str]]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    gate, payload, _covered = _json_artifact_gate(name="phase7_handoff", path=path, fatal_failures=fatal_failures, warnings=warnings)
    if payload is None:
        return gate, payload
    reasons: list[str] = []
    if payload.get("next_phase_allowed") is not True:
        reasons.append("Phase 7 next_phase_allowed is not true")
        _add_failure(fatal_failures, "phase7_next_phase_allowed", reasons[-1])
    token_ids = payload.get("native_think_token_ids")
    if token_ids is None:
        token_ids = (((payload.get("gates") or {}).get("tokenizer_audit") or {}).get("data") or {}).get("native_think_token_ids")
    if not token_ids:
        reasons.append("Phase 7 native_think_token_ids are missing")
        _add_failure(fatal_failures, "phase7_native_think_token_ids", reasons[-1])
    if reasons:
        return _gate(False, "; ".join([gate["reason"]] if gate["reason"] else [] + reasons), payload), payload
    return gate, payload


def _cleaning_invariants(payload: dict[str, Any] | None, fatal_failures: list[dict[str, str]]) -> dict[str, Any]:
    if payload is None:
        return _gate(False, "cleaning report missing", {})
    reasons: list[str] = []
    if payload.get("native_think_occurrences", 0) not in (0, None):
        reasons.append("native think text occurrences remain")
    if payload.get("forbidden_native_think_rows"):
        reasons.append("forbidden native think rows remain")
    if payload.get("malformed_close_remaining", 0) not in (0, None):
        reasons.append("malformed close tags remain")
    if payload.get("forbidden_malformed_close_after_normalization"):
        reasons.append("malformed close tags remain after normalization")
    if not isinstance(payload.get("malformed_think_close_replacements"), int):
        reasons.append("normalization replacement count is missing")
    for reason in reasons:
        _add_failure(fatal_failures, "cleaning_invariants", reason)
    return _gate(not reasons, "; ".join(reasons) if reasons else None, {"malformed_think_close_replacements": payload.get("malformed_think_close_replacements")})


def _rebuild_invariants(payload: dict[str, Any] | None, fatal_failures: list[dict[str, str]]) -> dict[str, Any]:
    if payload is None:
        return _gate(False, "rebuild report missing", {})
    reasons: list[str] = []
    truncation = payload.get("truncation") if isinstance(payload.get("truncation"), dict) else {}
    over_rate = truncation.get("over_length_rate")
    max_allowed = truncation.get("max_allowed_rate", 0.05)
    if over_rate is None or float(over_rate) > float(max_allowed):
        reasons.append(f"truncation rate {over_rate} exceeds {max_allowed}")
    gates = payload.get("gates") if isinstance(payload.get("gates"), dict) else {}
    native_gate = gates.get("native_think_token_leak") if isinstance(gates.get("native_think_token_leak"), dict) else None
    if native_gate is not None and native_gate.get("ok") is not True:
        reasons.append("native think token leak gate is red")
    if not payload.get("native_think_token_ids"):
        reasons.append("native think token IDs missing")
    v1_ood = payload.get("v1_ood_alignment") if isinstance(payload.get("v1_ood_alignment"), dict) else {}
    if not v1_ood:
        reasons.append("v1 OOD alignment evidence is missing")
    elif v1_ood.get("all_v1_ood_in_ood_val") is not True:
        reasons.append("v1 OOD alignment is false")
    elif int(v1_ood.get("v1_ood_count") or 0) <= 0:
        reasons.append("v1 OOD alignment evidence is empty")
    elif int(v1_ood.get("ood_val_v1_ood_count") or 0) != int(v1_ood.get("v1_ood_count") or 0):
        reasons.append("v1 OOD alignment count mismatch")
    v3_ood = payload.get("v3_extended_ood") if isinstance(payload.get("v3_extended_ood"), dict) else {}
    if v3_ood and "selected_count" in v3_ood and int(v3_ood.get("selected_count") or 0) <= 0:
        reasons.append("v3 extended OOD alignment is empty")
    split_counts = payload.get("split_counts") if isinstance(payload.get("split_counts"), dict) else {}
    if not all(int(split_counts.get(name, 0) or 0) > 0 for name in ("train", "val", "ood_val")):
        reasons.append("split counts are incomplete")
    for reason in reasons:
        _add_failure(fatal_failures, "rebuild_invariants", reason)
    return _gate(not reasons, "; ".join(reasons) if reasons else None, {"truncation": truncation, "v1_ood_alignment": v1_ood, "v3_extended_ood": v3_ood, "split_counts": split_counts})


def _artifact_paths_gate(
    *,
    source_manifest_path: Path,
    cleaning_report_path: Path,
    rebuild_report_path: Path,
    dataset_card_path: Path,
    split_dir: Path,
    tokenized_dir: Path,
    phase8_report_path: Path | None,
    fatal_failures: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    paths: dict[str, str] = {
        "source_manifest": str(source_manifest_path),
        "cleaning_report": str(cleaning_report_path),
        "rebuild_report": str(rebuild_report_path),
        "dataset_card": str(dataset_card_path),
        "train_index": str(split_dir / "train.index.jsonl"),
        "val_index": str(split_dir / "val.index.jsonl"),
        "ood_val_index": str(split_dir / "ood_val.index.jsonl"),
        "split_manifest": str(split_dir / "manifest.json"),
        "v1_ood_alignment": str(split_dir / "v1_ood_alignment.json"),
    }
    for split_name in ("train", "val", "ood_val"):
        arrow = tokenized_dir / f"{split_name}.arrow"
        if arrow.exists():
            paths[f"{split_name}_arrow"] = str(arrow)
    sha256 = {name: _sha256_file(Path(path)) for name, path in paths.items() if Path(path).is_file()}
    reasons: list[str] = []
    required_existing = [source_manifest_path, cleaning_report_path, rebuild_report_path, split_dir / "manifest.json", split_dir / "train.index.jsonl", split_dir / "val.index.jsonl", split_dir / "ood_val.index.jsonl"]
    missing = [str(path) for path in required_existing if not path.exists()]
    if missing:
        reasons.append(f"missing required artifact paths: {', '.join(missing)}")
    frozen = [str(path) for path in paths.values() if _is_relative_to(Path(path), FROZEN_V1_ROOT)]
    if frozen:
        reasons.append(f"artifact paths under frozen v1 root: {', '.join(frozen)}")
    for reason in reasons:
        _add_failure(fatal_failures, "artifact_paths", reason)
    manifest = {"paths": paths, "sha256": sha256}
    return _gate(not reasons, "; ".join(reasons) if reasons else None, manifest), manifest


def _dataset_card_section(text: str) -> tuple[str, str | None]:
    starts = [(heading, text.find(heading)) for heading in DATASET_CARD_HEADINGS]
    starts = [(heading, start) for heading, start in starts if start >= 0]
    if not starts:
        return "", None
    heading, start = min(starts, key=lambda item: item[1])
    rest = text[start:]
    next_heading = rest.find("\n## ", len(heading))
    if next_heading >= 0:
        return rest[:next_heading], heading
    return rest, heading


def _dataset_card_gate(path: Path, fatal_failures: list[dict[str, str]]) -> dict[str, Any]:
    if not path.exists():
        reason = f"missing dataset card: {path}"
        _add_failure(fatal_failures, "dataset_card_phase8_section", reason)
        return _gate(False, reason, {"path": str(path)})
    text = path.read_text(encoding="utf-8")
    section, heading = _dataset_card_section(text)
    reasons: list[str] = []
    if not section:
        reasons.append(f"missing heading {DATASET_CARD_HEADING}")
    else:
        section_lower = section.lower()
        missing = [phrase for phrase in DATASET_CARD_REQUIRED_PHRASES if phrase not in section_lower]
        if missing:
            reasons.append(f"missing dataset card evidence text: {', '.join(missing)}")
        if "PENDING" in section:
            reasons.append("dataset card Phase 8 section contains PENDING")
    if "PENDING" in text and not section:
        reasons.append("dataset card contains PENDING")
    for reason in reasons:
        _add_failure(fatal_failures, "dataset_card_v4_section", reason)
    return _gate(not reasons, "; ".join(reasons) if reasons else None, {"path": str(path), "heading": heading or DATASET_CARD_HEADING, "section_length": len(section)})


def evaluate_phase8_report(
    *,
    phase7_gate_report: Path = DEFAULT_PHASE7_REPORT,
    phase7_report: Path | None = None,
    source_manifest: Path = DEFAULT_SOURCE_MANIFEST,
    cleaning_report: Path = DEFAULT_CLEANING_REPORT,
    rebuild_report: Path = DEFAULT_REBUILD_REPORT,
    dataset_card: Path = DEFAULT_DATASET_CARD,
    out_path: Path | None = None,
) -> dict[str, Any]:
    if phase7_report is not None:
        phase7_gate_report = phase7_report
    fatal_failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    gates: dict[str, Any] = {}
    covered: set[str] = set()

    gates["phase7_handoff"], _phase7 = _phase7_gate(Path(phase7_gate_report), fatal_failures, warnings)
    gates["phase7_next_phase_allowed"] = _gate(gates["phase7_handoff"]["ok"], gates["phase7_handoff"]["reason"], gates["phase7_handoff"].get("data", {}))

    gates["source_manifest"], source_payload, source_covered = _json_artifact_gate(name="source_manifest", path=Path(source_manifest), required_requirements={"DATA4B-01"}, fatal_failures=fatal_failures, warnings=warnings)
    gates["cleaning_report"], cleaning_payload, cleaning_covered = _json_artifact_gate(name="cleaning_report", path=Path(cleaning_report), required_requirements={"DATA4B-01"}, fatal_failures=fatal_failures, warnings=warnings)
    gates["rebuild_report"], rebuild_payload, rebuild_covered = _json_artifact_gate(name="rebuild_report", path=Path(rebuild_report), required_requirements={"DATA4B-02", "DATA4B-03", "DATA4B-04"}, fatal_failures=fatal_failures, warnings=warnings)
    covered.update(source_covered)
    covered.update(cleaning_covered)
    covered.update(rebuild_covered)

    gates["cleaning_invariants"] = _cleaning_invariants(cleaning_payload, fatal_failures)
    gates["rebuild_invariants"] = _rebuild_invariants(rebuild_payload, fatal_failures)

    missing_non_card = sorted(set(NON_CARD_REQUIREMENTS) - covered)
    if missing_non_card:
        _add_failure(fatal_failures, "requirements_coverage", f"missing requirements: {', '.join(missing_non_card)}")
    gates["requirements_coverage"] = _gate(not missing_non_card, None if not missing_non_card else f"missing requirements: {', '.join(missing_non_card)}", {"covered_without_card": sorted(covered), "expected_without_card": NON_CARD_REQUIREMENTS})

    gates["dataset_card_phase8_section"] = _dataset_card_gate(Path(dataset_card), fatal_failures)
    gates["dataset_card_v4_section"] = gates["dataset_card_phase8_section"]
    if gates["dataset_card_phase8_section"]["ok"]:
        covered.add("DATA4B-05")

    artifact_gate, artifact_manifest = _artifact_paths_gate(
        source_manifest_path=Path(source_manifest),
        cleaning_report_path=Path(cleaning_report),
        rebuild_report_path=Path(rebuild_report),
        dataset_card_path=Path(dataset_card),
        split_dir=Path(rebuild_report).parent.parent.parent / "data/v4/phase8/splits" if False else DEFAULT_SPLIT_DIR,
        tokenized_dir=DEFAULT_TOKENIZED_DIR,
        phase8_report_path=Path(out_path) if out_path is not None else None,
        fatal_failures=fatal_failures,
    )
    gates["artifact_paths"] = artifact_gate

    ok = not fatal_failures
    report = {
        "ok": ok,
        "next_phase_allowed": ok,
        "requirements_expected": REQUIREMENTS_EXPECTED,
        "requirements_covered": [req for req in REQUIREMENTS_EXPECTED if req in covered],
        "gates": gates,
        "fatal_failures": fatal_failures,
        "warnings": warnings,
        "artifact_manifest": artifact_manifest,
    }
    if out_path is not None:
        out = Path(out_path)
        _assert_not_frozen_output(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        report["artifact_manifest"]["paths"]["phase8_gate_report"] = str(out)
        report["artifact_manifest"]["sha256"]["phase8_gate_report"] = "self-referential-report"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate v4 Phase 8 dataset rebuild handoff gate")
    parser.add_argument("--phase7-gate-report", default=str(DEFAULT_PHASE7_REPORT))
    parser.add_argument("--source-manifest", default=str(DEFAULT_SOURCE_MANIFEST))
    parser.add_argument("--cleaning-report", default=str(DEFAULT_CLEANING_REPORT))
    parser.add_argument("--rebuild-report", default=str(DEFAULT_REBUILD_REPORT))
    parser.add_argument("--dataset-card", default=str(DEFAULT_DATASET_CARD))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = evaluate_phase8_report(
        phase7_gate_report=Path(args.phase7_gate_report),
        source_manifest=Path(args.source_manifest),
        cleaning_report=Path(args.cleaning_report),
        rebuild_report=Path(args.rebuild_report),
        dataset_card=Path(args.dataset_card),
        out_path=Path(args.out),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
