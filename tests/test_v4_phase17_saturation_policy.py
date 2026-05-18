from __future__ import annotations

import ast
import builtins
import importlib
import math
from pathlib import Path

import pytest

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
FORBIDDEN_COLLECTION_IMPORTS = {"torch", "transformers", "peft", "bitsandbytes", "vllm", "flash_attn", "openai"}


@pytest.fixture(autouse=True)
def _phase17_modules_are_lazy(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = importlib.import_module

    def guarded_import(name: str, package: str | None = None):
        root = name.split(".", 1)[0]
        if root in FORBIDDEN_COLLECTION_IMPORTS:
            raise AssertionError(f"Phase 17 contract imported heavyweight dependency during test execution: {name}")
        return real_import(name, package)

    monkeypatch.setattr(importlib, "import_module", guarded_import)


def _policy_contract():
    return importlib.import_module("tsc_cycle.v4_gates.saturation_policy")


def test_phase17_policy_module_does_not_import_heavy_model_stacks(monkeypatch: pytest.MonkeyPatch) -> None:
    module_path = PROJECT_ROOT / "tsc_cycle" / "v4_gates" / "saturation_policy.py"
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert imported_roots.isdisjoint(FORBIDDEN_COLLECTION_IMPORTS)
    assert source.count("def classify_saturation_band(") == 1

    real_import = builtins.__import__

    def guarded_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):
        root = name.split(".", 1)[0]
        if root in FORBIDDEN_COLLECTION_IMPORTS:
            raise AssertionError(f"Phase 17 implementation imported heavyweight dependency during module import: {name}")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    importlib.import_module("tsc_cycle.v4_gates.saturation_policy")


def test_saturation_band_boundaries() -> None:
    mod = _policy_contract()

    assert mod.classify_saturation_band(0.1999) == mod.BAND_NEAR_MIN
    assert mod.classify_saturation_band(0.2) == mod.BAND_INTERPOLATED
    assert mod.classify_saturation_band(0.5999) == mod.BAND_INTERPOLATED
    assert mod.classify_saturation_band(0.6) == mod.BAND_HIGH_NOT_MAX
    assert mod.classify_saturation_band(0.9999) == mod.BAND_HIGH_NOT_MAX
    assert mod.classify_saturation_band(1.0) == mod.BAND_ALLOWED_MAX
    assert mod.classify_saturation_band(1.5) == mod.BAND_ALLOWED_MAX

    for bad in (None, "not-a-number", float("nan"), float("inf"), -float("inf")):
        with pytest.raises(ValueError, match="finite"):
            mod.classify_saturation_band(bad)

    low_max = {
        "pred_saturation": 0.1,
        "min_green": 10,
        "max_green": 50,
        "final_green": 50,
    }
    assert mod.classify_violation(low_max) == mod.VIOLATION_UNSATURATED_MAX_GREEN

    saturated_max = {**low_max, "pred_saturation": 1.0}
    assert mod.classify_violation(saturated_max) == mod.VIOLATION_ALLOWED_SATURATED_MAX_GREEN

    forced = {**low_max, "min_green": 40, "max_green": 40, "final_green": 40}
    assert mod.classify_violation(forced) == mod.VIOLATION_FORCED_TRIVIAL_RANGE

    normal = {**low_max, "final_green": 20}
    assert mod.classify_violation(normal) == mod.VIOLATION_NONE
    assert "POLICY-01" in mod.REQUIREMENTS_COVERED
