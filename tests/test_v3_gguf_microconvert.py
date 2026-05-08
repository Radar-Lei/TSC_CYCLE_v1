from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tsc_cycle.v3_gates.gguf_microconvert_v3 import (
    DEFAULT_LLAMA_CPP,
    assert_qwen35_config,
    resolve_llama_cpp_paths,
    resolve_llama_tokenize,
)


def _write_config(tmp_path: Path, **payload: object) -> Path:
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "config.json").write_text(json.dumps(payload), encoding="utf-8")
    return cfg


def _write_executable(path: Path) -> Path:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_assert_qwen35_config_accepts_qwen35_causal_lm(tmp_path: Path) -> None:
    cfg = _write_config(
        tmp_path,
        architectures=["Qwen3_5ForCausalLM"],
        model_type="qwen3_5",
    )

    result = assert_qwen35_config(cfg)

    assert result.architecture == "Qwen3_5ForCausalLM"
    assert result.model_type == "qwen3_5"


@pytest.mark.parametrize(
    "architecture,model_type",
    [
        ("GPT2LMHeadModel", "gpt2"),
        ("LlamaForCausalLM", "llama"),
        ("Qwen3ForCausalLM", "qwen3"),
        ("Qwen3_5ForConditionalGeneration", "qwen3_5"),
        ("Qwen3_5VisionForCausalLM", "qwen3_5_vl"),
    ],
)
def test_assert_qwen35_config_rejects_non_qwen35_fixtures(
    tmp_path: Path, architecture: str, model_type: str
) -> None:
    cfg = _write_config(
        tmp_path,
        architectures=[architecture],
        model_type=model_type,
    )

    with pytest.raises(ValueError, match="Qwen3.5 causal LM"):
        assert_qwen35_config(cfg)


def test_assert_qwen35_config_rejects_conditional_generation_text(tmp_path: Path) -> None:
    cfg = _write_config(
        tmp_path,
        architectures=["Qwen3_5ForConditionalGeneration"],
        model_type="qwen3_5",
    )

    with pytest.raises(ValueError, match="ConditionalGeneration"):
        assert_qwen35_config(cfg)


def test_assert_qwen35_config_rejects_vision_config(tmp_path: Path) -> None:
    cfg = _write_config(
        tmp_path,
        architectures=["Qwen3_5ForCausalLM"],
        model_type="qwen3_5",
        vision_config={"hidden_size": 128},
    )

    with pytest.raises(ValueError, match="vision"):
        assert_qwen35_config(cfg)


def test_resolve_llama_cpp_paths_requires_core_tools_and_tokenize(tmp_path: Path) -> None:
    llama_cpp = tmp_path / "llama.cpp"
    llama_cpp.mkdir()
    (llama_cpp / "convert_hf_to_gguf.py").write_text("# convert_hf_to_gguf.py\n", encoding="utf-8")
    _write_executable(llama_cpp / "llama-quantize")
    _write_executable(llama_cpp / "llama-cli")
    _write_executable(llama_cpp / "llama-tokenize")

    resolved = resolve_llama_cpp_paths(llama_cpp)

    assert resolved["convert"].name == "convert_hf_to_gguf.py"
    assert resolved["quantize"].name == "llama-quantize"
    assert resolved["llama_cli"].name == "llama-cli"
    assert resolved["llama_tokenize"].name == "llama-tokenize"
    assert resolved["llama_tokenize_source"] == "llama_cpp_dir"
    assert all(path.is_absolute() for key, path in resolved.items() if key != "llama_tokenize_source")


def test_resolve_llama_tokenize_records_fallback_provenance(tmp_path: Path) -> None:
    llama_cpp = tmp_path / "llama.cpp"
    llama_cpp.mkdir()
    fallback = _write_executable(tmp_path / "fallback-tokenize")

    token_path, source = resolve_llama_tokenize(llama_cpp, fallback)

    assert token_path == fallback.resolve()
    assert source == "fallback"


def test_resolve_llama_cpp_paths_fails_when_tokenize_missing(tmp_path: Path) -> None:
    llama_cpp = tmp_path / "llama.cpp"
    llama_cpp.mkdir()
    (llama_cpp / "convert_hf_to_gguf.py").write_text("# convert\n", encoding="utf-8")
    _write_executable(llama_cpp / "llama-quantize")
    _write_executable(llama_cpp / "llama-cli")

    with pytest.raises(FileNotFoundError, match="llama-tokenize"):
        resolve_llama_cpp_paths(llama_cpp, llama_tokenize_fallback=tmp_path / "missing")


def test_default_llama_cpp_path_is_evoprogtsc_path() -> None:
    assert DEFAULT_LLAMA_CPP == Path("/home/samuel/projects/EvoProgTSC/llama.cpp")
