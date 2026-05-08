from __future__ import annotations

import pytest

from tsc_cycle.v3_gates import env_smoke_v3, run_safe_scope_check_v3


class FakeConfig:
    def __init__(self, architectures=None, model_type="qwen3_5"):
        self.architectures = architectures or []
        self.model_type = model_type


class FakeModel:
    def __init__(self, config):
        self.config = config


Qwen3_5ForCausalLM = type("Qwen3_5ForCausalLM", (FakeModel,), {})
Qwen3_5ForConditionalGeneration = type("Qwen3_5ForConditionalGeneration", (FakeModel,), {})
Qwen3_5VisionModel = type("Qwen3_5VisionModel", (FakeModel,), {})


def test_env_smoke_parser_defaults():
    args = env_smoke_v3.build_parser().parse_args([])
    assert args.model == "Qwen/Qwen3.5-9B"
    assert args.out == "artifacts/v3/phase1/env_smoke.json"
    assert args.prompt == "DGX Spark Qwen3.5 smoke test"


def test_run_safe_parser_default_out():
    args = run_safe_scope_check_v3.build_parser().parse_args([])
    assert args.out == "artifacts/v3/phase1/run_safe_scope.json"


def test_count_vision_params_counts_known_names():
    count, sample = env_smoke_v3.count_vision_params(
        [
            ("vision.foo", object()),
            ("model.vision_tower.bar", object()),
            ("model.visual.patch_embed", object()),
            ("model.layers.0.mlp.down_proj.weight", object()),
        ]
    )
    assert count == 3
    assert "vision.foo" in sample
    assert "model.vision_tower.bar" in sample
    assert "model.visual.patch_embed" in sample


def test_assert_qwen35_causal_lm_accepts_architecture():
    model = FakeModel(FakeConfig(architectures=["Qwen3_5ForCausalLM"]))
    env_smoke_v3.assert_qwen35_causal_lm(model)


def test_assert_qwen35_causal_lm_accepts_matching_class():
    model = Qwen3_5ForCausalLM(FakeConfig())
    env_smoke_v3.assert_qwen35_causal_lm(model)


@pytest.mark.parametrize(
    "model",
    [
        Qwen3_5ForConditionalGeneration(FakeConfig(architectures=["Qwen3_5ForConditionalGeneration"])),
        Qwen3_5VisionModel(FakeConfig(architectures=["Qwen3_5VisionModel"])),
        FakeModel(FakeConfig(architectures=["Qwen3_5ForVisionCausalLM"])),
    ],
)
def test_assert_qwen35_causal_lm_rejects_conditional_generation_or_vision(model):
    with pytest.raises(AssertionError):
        env_smoke_v3.assert_qwen35_causal_lm(model)


def test_memory_scope_helpers_accept_systemd_byte_values():
    assert run_safe_scope_check_v3._memory_max_is_100g(str(100 * 1024 * 1024 * 1024))
    assert run_safe_scope_check_v3._memory_max_is_100g("100G")
    assert run_safe_scope_check_v3._memory_swap_is_zero("0")
