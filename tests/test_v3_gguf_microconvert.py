from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from tsc_cycle.v3_gates.gguf_microconvert_v3 import (
    DEFAULT_LLAMA_CPP,
    QWEN35_BASE_TOKENIZER_HASH,
    assert_qwen35_config,
    prepare_converter_script,
    resolve_llama_cpp_paths,
    resolve_llama_tokenize,
    run_gate,
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


def test_assert_qwen35_config_accepts_official_text_config_shape(tmp_path: Path) -> None:
    cfg = _write_config(
        tmp_path,
        architectures=["Qwen3_5ForConditionalGeneration"],
        model_type="qwen3_5",
        vision_config={"hidden_size": 128},
        vision_start_token_id=151652,
        vision_end_token_id=151653,
    )

    result = assert_qwen35_config(cfg)

    assert result.architecture == "Qwen3_5ForCausalLM"
    assert result.model_type == "qwen3_5"
    assert result.architectures == ["Qwen3_5ForConditionalGeneration"]


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


def test_prepare_converter_script_patches_qwen35_base_hash_without_mutating_source(tmp_path: Path) -> None:
    source = tmp_path / "convert_hf_to_gguf.py"
    source.write_text(
        "#!/usr/bin/env python3\n"
        "if chkhsh == \"d30d75d9059f1aa2c19359de71047b3ae408c70875e8a3ccf8c5fba56c9d8af4\":\n"
        "    # ref: https://huggingface.co/Qwen/Qwen3.5-9B-Instruct\n"
        "    res = \"qwen35\"\n",
        encoding="utf-8",
    )

    prepared, patched = prepare_converter_script(source, tmp_path / "prepared")

    assert patched is True
    assert prepared != source
    assert QWEN35_BASE_TOKENIZER_HASH in prepared.read_text(encoding="utf-8")
    assert QWEN35_BASE_TOKENIZER_HASH not in source.read_text(encoding="utf-8")


def test_run_gate_fails_when_q4_tokenizer_or_dummy_lora_outputs_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_config(
        tmp_path,
        architectures=["Qwen3_5ForCausalLM"],
        model_type="qwen3_5",
    )
    llama_cpp = tmp_path / "llama.cpp"
    llama_cpp.mkdir()
    (llama_cpp / "convert_hf_to_gguf.py").write_text("# convert\n", encoding="utf-8")
    _write_executable(llama_cpp / "llama-quantize")
    _write_executable(llama_cpp / "llama-cli")
    _write_executable(llama_cpp / "llama-tokenize")

    monkeypatch.setattr(
        "tsc_cycle.v3_gates.gguf_microconvert_v3.create_dummy_lora_adapter",
        lambda source, adapter_dir: adapter_dir,
    )
    monkeypatch.setattr(
        "tsc_cycle.v3_gates.gguf_microconvert_v3.merge_dummy_lora_to_hf",
        lambda source, adapter_dir, merged_hf: merged_hf,
    )
    monkeypatch.setattr(
        "tsc_cycle.v3_gates.gguf_microconvert_v3._run_command",
        lambda cmd, timeout=None: {"argv": cmd, "returncode": 0, "stdout_tail": "ok", "stderr_tail": ""},
    )

    args = Namespace(
        model="Qwen/Qwen3.5-9B",
        llama_cpp=str(llama_cpp),
        llama_tokenize_fallback=str(tmp_path / "missing-tokenize"),
        out=str(tmp_path / "out"),
        n_predict=5,
        fixture_hf=str(fixture),
        tokenizer_gguf=str(tmp_path / "out" / "tokenizer.gguf"),
    )

    payload = run_gate(args)

    assert payload["ok"] is False
    assert payload["dummy_lora_created"] is False
    assert payload["dummy_lora_merged"] is False
    assert "missing" in payload["error"] or "No such file" in payload["error"]
    artifact = Path(args.out) / "gguf_microconvert.json"
    saved = json.loads(artifact.read_text(encoding="utf-8"))
    assert saved["commands"][0]["returncode"] == 0
    assert saved["llama_tokenize"].endswith("llama-tokenize")


def test_run_gate_records_success_artifact_with_required_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _write_config(
        tmp_path,
        architectures=["Qwen3_5ForCausalLM"],
        model_type="qwen3_5",
    )
    llama_cpp = tmp_path / "llama.cpp"
    llama_cpp.mkdir()
    (llama_cpp / "convert_hf_to_gguf.py").write_text("# convert\n", encoding="utf-8")
    _write_executable(llama_cpp / "llama-quantize")
    _write_executable(llama_cpp / "llama-cli")
    _write_executable(llama_cpp / "llama-tokenize")

    def fake_create_dummy_lora(source: object, adapter_dir: Path) -> Path:
        adapter_dir.mkdir(parents=True)
        (adapter_dir / "adapter_config.json").write_text("{}", encoding="utf-8")
        return adapter_dir

    def fake_merge_dummy_lora(source: object, adapter_dir: Path, merged_hf: Path) -> Path:
        merged_hf.mkdir(parents=True)
        (merged_hf / "config.json").write_text("{}", encoding="utf-8")
        return merged_hf

    def fake_run_command(cmd: list[str], timeout: int | None = None) -> dict[str, object]:
        if "--outfile" in cmd:
            Path(cmd[cmd.index("--outfile") + 1]).write_text("gguf", encoding="utf-8")
        elif cmd and cmd[-1] == "Q4_K_M":
            Path(cmd[-2]).write_text("q4", encoding="utf-8")
        return {"argv": cmd, "returncode": 0, "stdout_tail": "tail", "stderr_tail": ""}

    monkeypatch.setattr(
        "tsc_cycle.v3_gates.gguf_microconvert_v3.create_dummy_lora_adapter", fake_create_dummy_lora
    )
    monkeypatch.setattr(
        "tsc_cycle.v3_gates.gguf_microconvert_v3.merge_dummy_lora_to_hf", fake_merge_dummy_lora
    )
    monkeypatch.setattr("tsc_cycle.v3_gates.gguf_microconvert_v3._run_command", fake_run_command)

    args = Namespace(
        model="Qwen/Qwen3.5-9B",
        llama_cpp=str(llama_cpp),
        llama_tokenize_fallback=str(tmp_path / "missing-tokenize"),
        out=str(tmp_path / "out"),
        n_predict=5,
        fixture_hf=str(fixture),
        tokenizer_gguf=str(tmp_path / "out" / "tokenizer.gguf"),
    )

    payload = run_gate(args)

    assert payload["ok"] is True
    assert payload["dummy_lora_created"] is True
    assert payload["dummy_lora_merged"] is True
    assert Path(payload["q4_gguf"]).exists()
    assert Path(payload["tokenizer_gguf"]).exists()
    assert payload["llama_tokenize"] == str((llama_cpp / "llama-tokenize").resolve())
    assert [cmd["name"] for cmd in payload["commands"]] == [
        "convert_hf_to_gguf.py",
        "llama-quantize",
        "llama-cli",
    ]
    infer_argv = payload["commands"][2]["argv"]
    assert "-st" in infer_argv
    assert infer_argv[infer_argv.index("-c") + 1] == "512"
    saved = json.loads((Path(args.out) / "gguf_microconvert.json").read_text(encoding="utf-8"))
    assert saved["commands"][1]["argv"][-1] == "Q4_K_M"
    assert saved["inference_tail"] == "tail"
