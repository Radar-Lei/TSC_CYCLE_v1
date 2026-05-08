from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REQUIREMENTS_COVERED = [
    "ENV-01",
    "ENV-02",
    "ENV-03",
    "TOK-01",
    "TOK-02",
    "TOK-03",
    "TOK-04",
    "MEM-01",
    "MEM-02",
    "MEM-03",
]


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"missing artifact: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON {path}: {exc}"


def _gate(name: str, passed: bool, reason: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": bool(passed), "reason": reason, "data": data or {}}


def _selected_memory_record(memory: dict[str, Any]) -> dict[str, Any] | None:
    selected = memory.get("selected_max_seq")
    for record in memory.get("results", []):
        if record.get("seq") == selected:
            return record
    return None


def _add_result(gates: dict[str, Any], failures: list[dict[str, str]], name: str, passed: bool, reason: str | None, data: dict[str, Any] | None = None) -> None:
    gates[name] = _gate(name, passed, reason, data)
    if not passed:
        failures.append({"gate": name, "reason": reason or "failed"})


def evaluate_gates(artifacts: str | Path, gguf_report: str | Path) -> dict[str, Any]:
    artifacts = Path(artifacts)
    gguf_report = Path(gguf_report)
    gates: dict[str, Any] = {}
    failures: list[dict[str, str]] = []
    warnings: list[str] = []

    env, err = _load_json(artifacts / "env_smoke.json")
    if err:
        _add_result(gates, failures, "env_smoke", False, err)
    else:
        arch = " ".join(str(x) for x in env.get("architectures", []))
        identity_ok = env.get("model_class") == "Qwen3_5ForCausalLM" or "Qwen3_5ForCausalLM" in arch
        vision_count = env.get("vision_param_count")
        passed = env.get("ok") is True and identity_ok and vision_count == 0
        reason = None if passed else f"ok/model identity/vision_param_count failed: ok={env.get('ok')} identity_ok={identity_ok} vision_param_count={vision_count}"
        _add_result(gates, failures, "env_smoke", passed, reason, env)

    scope, err = _load_json(artifacts / "run_safe_scope.json")
    if err:
        _add_result(gates, failures, "run_safe_scope", False, err)
    else:
        memory_max = str(scope.get("memory_max", "")).upper()
        memory_swap_max = str(scope.get("memory_swap_max", "")).lower()
        memory_ok = memory_max == "100G" or memory_max == str(100 * 1024**3)
        swap_ok = memory_swap_max in {"0", "0b", "0bytes"}
        passed = scope.get("ok") is True and scope.get("swap_disabled") is True and memory_ok and swap_ok
        reason = None if passed else "run_safe_scope requires ok=true, swap_disabled=true, memory_max=100G, memory_swap_max=0"
        _add_result(gates, failures, "run_safe_scope", passed, reason, scope)

    audit, err = _load_json(artifacts / "tokenizer_audit.json")
    if err:
        _add_result(gates, failures, "tokenizer_audit", False, err)
    else:
        native = audit.get("native_think") or {}
        passed = (
            audit.get("ok") is True
            and int(audit.get("min_custom_subtokens", 0)) >= 3
            and bool(native.get("<think>"))
            and bool(native.get("</think>"))
            and audit.get("chat_template_used") is False
            and bool(audit.get("dataset_raw_text_path"))
        )
        reason = None if passed else "tokenizer audit requires custom tags>=3, native think IDs, raw text path, and no chat template"
        _add_result(gates, failures, "tokenizer_audit", passed, reason, audit)

    parity, err = _load_json(artifacts / "tokenizer_parity.json")
    if err:
        _add_result(gates, failures, "tokenizer_parity", False, err)
    else:
        passed = parity.get("ok") is True and parity.get("matched") == 100 and parity.get("mismatched") == 0 and parity.get("parse_failed") == 0 and bool(parity.get("gguf"))
        reason = None if passed else f"tokenizer parity requires matched == 100, mismatched == 0, parse_failed == 0; got matched={parity.get('matched')}"
        _add_result(gates, failures, "tokenizer_parity", passed, reason, parity)

    memory, err = _load_json(artifacts / "memory_budget.json")
    if err:
        _add_result(gates, failures, "memory_budget", False, err)
    else:
        selected = _selected_memory_record(memory) or {}
        peak = selected.get("peak_reserved_gb")
        passed = memory.get("ok") is True and memory.get("selected_max_seq") is not None and peak is not None and float(peak) < 85.0
        reason = None if passed else f"memory budget requires selected peak_reserved_gb <85.0; got {peak}"
        _add_result(gates, failures, "memory_budget", passed, reason, {"selected_max_seq": memory.get("selected_max_seq"), "selected": selected})

    dry, err = _load_json(artifacts / "train_100step.json")
    if err:
        _add_result(gates, failures, "train_100step", False, err)
    else:
        passed = dry.get("ok") is True and int(dry.get("steps", 0)) >= 100
        reason = None if passed else f"train_100step requires ok=true and steps>=100; got steps={dry.get('steps')}"
        _add_result(gates, failures, "train_100step", passed, reason, dry)

    gguf, err = _load_json(gguf_report)
    if err:
        _add_result(gates, failures, "gguf_microconvert", False, err)
    else:
        q4 = Path(str(gguf.get("q4_gguf", "")))
        tokenizer = Path(str(gguf.get("tokenizer_gguf", "")))
        llama_tokenize = Path(str(gguf.get("llama_tokenize", "")))
        passed = (
            gguf.get("ok") is True
            and gguf.get("fixture_architecture") == "Qwen3_5ForCausalLM"
            and gguf.get("dummy_lora_created") is True
            and gguf.get("dummy_lora_merged") is True
            and q4.is_file()
            and tokenizer.is_file()
            and llama_tokenize.is_file()
            and os.access(llama_tokenize, os.X_OK)
        )
        reason = None if passed else "gguf microconvert requires Qwen3.5 fixture, dummy LoRA create/merge, q4/tokenizer GGUF, executable llama_tokenize"
        _add_result(gates, failures, "gguf_microconvert", passed, reason, gguf)

    ok = not failures
    return {
        "ok": ok,
        "fatal_failures": failures,
        "warnings": warnings,
        "gates": gates,
        "requirements_covered": REQUIREMENTS_COVERED,
        "next_phase_allowed": ok,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate v3 Phase 1 fatal gate report")
    parser.add_argument("--artifacts", default="artifacts/v3/phase1")
    parser.add_argument("--gguf-report", default="runs/v3.0-gates/gguf_microconvert/gguf_microconvert.json")
    parser.add_argument("--out", default="artifacts/v3/phase1/phase1_gate_report.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = evaluate_gates(args.artifacts, args.gguf_report)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
