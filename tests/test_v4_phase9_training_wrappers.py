from __future__ import annotations

from pathlib import Path

ROOT = Path("/home/samuel/TSC_CYCLE")
SCRIPT = ROOT / "scripts" / "run_v4_phase9_train.sh"
RUN_SAFE = ROOT / "scripts" / "dgx_spark" / "run_safe.sh"
FORBIDDEN = [
    "eval ",
    "pip install",
    "uv pip install",
    "conda install",
    "flash-attn",
    "flash_attn",
    "vllm",
    "unsloth",
    "axolotl",
    "torch install",
    "transformers install",
    "runs/20260507T032419Z",
    "runs/v3.0-",
    "Qwen/Qwen3.5-9B",
]


def _script_text() -> str:
    assert SCRIPT.exists(), "Phase 9 training wrapper must exist before full training can run"
    return SCRIPT.read_text(encoding="utf-8")


def test_wrapper_exists_and_routes_through_run_safe_100g() -> None:
    text = _script_text()
    assert "scripts/dgx_spark/run_safe.sh" in text
    assert "100G --" in text
    assert "MemorySwapMax=0" not in text, "wrapper should inherit swap protection from run_safe.sh rather than bypassing it"

    run_safe = RUN_SAFE.read_text(encoding="utf-8")
    assert "systemd-run --scope" in run_safe
    assert '-p "MemoryMax=$MEMORY_MAX"' in run_safe
    assert "-p MemorySwapMax=0" in run_safe


def test_wrapper_uses_fixed_project_venv_and_module_argv() -> None:
    text = _script_text()
    assert 'PY="$ROOT/.venv/bin/python"' in text or "PY=\"/home/samuel/TSC_CYCLE/.venv/bin/python\"" in text
    assert "tsc_cycle.student.sft_v4" in text
    assert "--model-name Qwen/Qwen3-4B-Thinking-2507" in text
    assert "--tokenized-dir data/v4/phase8/tokenized" in text
    assert "--phase8-gate-report artifacts/v4/phase8/phase8_gate_report.json" in text
    assert "--output-root runs/v4.0-4B-" in text or "v4.0-4B-$(" in text or "v4.0-4B-${" in text


def test_wrapper_writes_only_v4_4b_run_root_and_refuses_frozen_or_v3_roots() -> None:
    text = _script_text()
    assert "runs/v4.0-4B-" in text
    assert "validate_run_root" in text or "v4.0-4B-" in text
    assert "runs/20260507T032419Z" not in text
    assert "runs/v3.0-" not in text
    assert "data/v3" not in text
    assert "data/tokenized/v3" not in text


def test_wrapper_forbids_stack_upgrades_dynamic_eval_and_wrong_runtime() -> None:
    text = _script_text().lower()
    for forbidden in FORBIDDEN:
        assert forbidden.lower() not in text
    assert "apply_chat_template" not in text
    assert "packing=true" not in text
    assert "packing true" not in text


def test_smoke_wrapper_contract_is_cpu_first_and_short_if_present() -> None:
    smoke = ROOT / "scripts" / "run_v4_phase9_smoke.sh"
    assert smoke.exists(), "Phase 9 smoke wrapper must exist before full training wrapper"
    text = smoke.read_text(encoding="utf-8")
    assert "scripts/dgx_spark/run_safe.sh" in text
    assert "100G --" in text
    assert "--max-steps 1" in text or "--smoke" in text
    assert "runs/v4.0-4B-" in text
    for forbidden in FORBIDDEN:
        assert forbidden.lower() not in text.lower()
