from __future__ import annotations

import json
from pathlib import Path

from tsc_cycle.v3_gates.phase1_report import evaluate_gates


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def passing_artifacts(tmp_path: Path) -> tuple[Path, Path]:
    artifacts = tmp_path / "artifacts"
    gguf = tmp_path / "gguf_microconvert.json"
    exe = tmp_path / "llama-tokenize"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    exe.chmod(0o755)
    tokenizer_gguf = tmp_path / "tokenizer.gguf"
    q4_gguf = tmp_path / "model.q4_K_M.gguf"
    tokenizer_gguf.write_text("gguf", encoding="utf-8")
    q4_gguf.write_text("gguf", encoding="utf-8")

    write_json(
        artifacts / "env_smoke.json",
        {"ok": True, "model_class": "Qwen3_5ForCausalLM", "architectures": ["Qwen3_5ForCausalLM"], "vision_param_count": 0},
    )
    write_json(
        artifacts / "run_safe_scope.json",
        {"ok": True, "swap_disabled": True, "memory_max": str(100 * 1024**3), "memory_swap_max": "0"},
    )
    write_json(
        artifacts / "tokenizer_audit.json",
        {
            "ok": True,
            "min_custom_subtokens": 3,
            "native_think": {"<think>": [248068], "</think>": [248069]},
            "chat_template_used": False,
            "dataset_raw_text_path": "prompt_builder.build_user_prompt+build_full_assistant",
        },
    )
    write_json(
        artifacts / "tokenizer_parity.json",
        {"ok": True, "matched": 100, "mismatched": 0, "parse_failed": 0, "gguf": str(tokenizer_gguf)},
    )
    write_json(
        artifacts / "memory_budget.json",
        {
            "ok": True,
            "selected_max_seq": 2048,
            "results": [{"seq": 2048, "status": "ok", "peak_reserved_gb": 38.41}],
        },
    )
    write_json(artifacts / "train_100step.json", {"ok": True, "seq": 2048, "steps": 100, "peak_reserved_gb": 37.518})
    write_json(
        gguf,
        {
            "ok": True,
            "fixture_architecture": "Qwen3_5ForCausalLM",
            "dummy_lora_created": True,
            "dummy_lora_merged": True,
            "q4_gguf": str(q4_gguf),
            "tokenizer_gguf": str(tokenizer_gguf),
            "llama_tokenize": str(exe),
        },
    )
    return artifacts, gguf


def test_all_gates_passing_allows_next_phase(tmp_path: Path):
    artifacts, gguf = passing_artifacts(tmp_path)

    report = evaluate_gates(artifacts, gguf)

    assert report["ok"] is True
    assert report["next_phase_allowed"] is True
    assert report["fatal_failures"] == []
    assert report["requirements_covered"] == [
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


def test_tokenizer_parity_99_fails(tmp_path: Path):
    artifacts, gguf = passing_artifacts(tmp_path)
    write_json(artifacts / "tokenizer_parity.json", {"ok": True, "matched": 99, "mismatched": 1, "parse_failed": 0, "gguf": "x"})

    report = evaluate_gates(artifacts, gguf)

    assert report["ok"] is False
    assert any(item["gate"] == "tokenizer_parity" for item in report["fatal_failures"])


def test_env_vision_param_count_fails(tmp_path: Path):
    artifacts, gguf = passing_artifacts(tmp_path)
    write_json(artifacts / "env_smoke.json", {"ok": True, "model_class": "Qwen3_5ForCausalLM", "vision_param_count": 1})

    report = evaluate_gates(artifacts, gguf)

    assert report["ok"] is False
    assert any(item["gate"] == "env_smoke" and "vision_param_count" in item["reason"] for item in report["fatal_failures"])


def test_memory_peak_85_is_strict_failure(tmp_path: Path):
    artifacts, gguf = passing_artifacts(tmp_path)
    write_json(artifacts / "memory_budget.json", {"ok": True, "selected_max_seq": 2048, "results": [{"seq": 2048, "peak_reserved_gb": 85.0, "status": "ok"}]})

    report = evaluate_gates(artifacts, gguf)

    assert report["ok"] is False
    assert any(item["gate"] == "memory_budget" for item in report["fatal_failures"])


def test_missing_run_safe_scope_fails(tmp_path: Path):
    artifacts, gguf = passing_artifacts(tmp_path)
    (artifacts / "run_safe_scope.json").unlink()

    report = evaluate_gates(artifacts, gguf)

    assert report["ok"] is False
    assert any(item["gate"] == "run_safe_scope" for item in report["fatal_failures"])
