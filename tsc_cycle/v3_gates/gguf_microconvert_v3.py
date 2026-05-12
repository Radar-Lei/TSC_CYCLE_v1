"""Qwen3.5 llama.cpp micro-convert hard gate for v3.0 Phase 1.

This module deliberately fails closed: only Qwen3.5 causal-LM configs are
accepted, all llama.cpp tool paths are resolved before runtime, and the JSON
artifact records enough evidence for ENV-02 replay/debugging.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "Qwen/Qwen3.5-9B"
DEFAULT_LLAMA_CPP = Path("/home/samuel/projects/EvoProgTSC/llama.cpp")
DEFAULT_LLAMA_TOKENIZE_FALLBACK = Path("/home/samuel/llama.cpp/build/bin/llama-tokenize")
DEFAULT_OUT = Path("runs/v3.0-gates/gguf_microconvert")
DEFAULT_TOKENIZER_GGUF = DEFAULT_OUT / "tokenizer.gguf"
CONVERT_SCRIPT = "convert_hf_to_gguf.py"
QUANTIZE_BINARY = "llama-quantize"
LLAMA_CLI_BINARY = "llama-cli"
LLAMA_TOKENIZE_BINARY = "llama-tokenize"
CUSTOM_SMOKE_PROMPT = "<start_working_out>smoke"
Q4_KIND = "Q4_K_M"
QWEN35_BASE_TOKENIZER_HASH = "1444df51289cfa8063b96f0e62b1125440111bc79a52003ea14b6eac7016fd5f"
QWEN35_INSTRUCT_TOKENIZER_HASH = "d30d75d9059f1aa2c19359de71047b3ae408c70875e8a3ccf8c5fba56c9d8af4"


@dataclass(frozen=True)
class Qwen35ConfigInfo:
    """Validated Qwen3.5 causal-LM config identity."""

    config_source: str
    architecture: str
    model_type: str | None
    architectures: list[str]


def _read_config_json(config_dir_or_model_id: str | Path) -> tuple[dict[str, Any], str]:
    source = Path(config_dir_or_model_id)
    if source.exists():
        config_path = source / "config.json" if source.is_dir() else source
        if not config_path.exists():
            raise FileNotFoundError(f"config.json not found for fixture: {source}")
        return json.loads(config_path.read_text(encoding="utf-8")), str(config_path.resolve())

    try:
        from transformers import AutoConfig
    except Exception as exc:  # pragma: no cover - depends on optional runtime deps
        raise RuntimeError("transformers is required to resolve remote model configs") from exc

    cfg = AutoConfig.from_pretrained(str(config_dir_or_model_id), trust_remote_code=False)
    return cfg.to_dict(), str(config_dir_or_model_id)


def _as_architectures(raw: Any) -> list[str]:
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def assert_qwen35_config(config_dir_or_model_id: str | Path) -> Qwen35ConfigInfo:
    """Require a text-only Qwen3.5 causal LM config.

    Generic tiny fixtures, Qwen3 4B configs, ConditionalGeneration configs, and
    vision/multimodal configs are rejected so ENV-02 cannot be satisfied by an
    unrelated minimal model.
    """

    cfg, source = _read_config_json(config_dir_or_model_id)
    architectures = _as_architectures(cfg.get("architectures"))
    joined_arch = " ".join(architectures)
    model_type = cfg.get("model_type")
    model_type_s = str(model_type).lower() if model_type is not None else None

    if model_type_s and model_type_s not in {"qwen3_5", "qwen3.5", "qwen3_5_text"}:
        raise ValueError(
            f"not a Qwen3.5 causal LM config: model_type={model_type!r} is not qwen3_5"
        )

    vision_keys = sorted(key for key in cfg if "vision" in key.lower() or "visual" in key.lower())
    has_causal_arch = "Qwen3_5ForCausalLM" in architectures
    has_official_text_arch = (
        model_type_s == "qwen3_5"
        and "Qwen3_5ForConditionalGeneration" in architectures
        and "vision_config" in vision_keys
    )

    forbidden_arch_markers = ["Vision", "VL", "Image", "MultiModal"]
    for marker in forbidden_arch_markers:
        if marker.lower() in joined_arch.lower():
            raise ValueError(
                f"not a Qwen3.5 causal LM config: architecture contains forbidden marker {marker!r}"
            )

    if not (has_causal_arch or has_official_text_arch):
        raise ValueError(
            "not a Qwen3.5 causal LM config: expected architectures to include "
            "Qwen3_5ForCausalLM or official Qwen3_5ForConditionalGeneration text config"
        )

    if vision_keys and not has_official_text_arch:
        raise ValueError(f"not a Qwen3.5 causal LM config: vision fields present {vision_keys}")

    return Qwen35ConfigInfo(
        config_source=source,
        architecture="Qwen3_5ForCausalLM",
        model_type=str(model_type) if model_type is not None else None,
        architectures=architectures,
    )


def _require_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"required {label} missing: {resolved}")
    return resolved


def _require_executable(path: Path, label: str) -> Path:
    resolved = _require_file(path, label)
    if not os.access(resolved, os.X_OK):
        raise PermissionError(f"required {label} is not executable: {resolved}")
    return resolved


def resolve_llama_tokenize(
    llama_cpp_dir: str | Path,
    fallback: str | Path | None = DEFAULT_LLAMA_TOKENIZE_FALLBACK,
) -> tuple[Path, str]:
    """Resolve llama-tokenize and return (absolute path, provenance)."""

    llama_cpp = Path(llama_cpp_dir).expanduser().resolve()
    primary = llama_cpp / LLAMA_TOKENIZE_BINARY
    if primary.is_file() and os.access(primary, os.X_OK):
        return primary.resolve(), "llama_cpp_dir"

    if fallback is not None:
        fallback_path = Path(fallback).expanduser().resolve()
        if fallback_path.is_file() and os.access(fallback_path, os.X_OK):
            return fallback_path, "fallback"

    path_candidate = shutil.which(LLAMA_TOKENIZE_BINARY)
    if path_candidate:
        return Path(path_candidate).resolve(), "PATH"

    raise FileNotFoundError(
        "usable llama-tokenize binary not found: checked "
        f"{primary}, fallback={fallback}, and PATH"
    )


def resolve_llama_cpp_paths(
    llama_cpp_dir: str | Path = DEFAULT_LLAMA_CPP,
    llama_tokenize_fallback: str | Path | None = DEFAULT_LLAMA_TOKENIZE_FALLBACK,
) -> dict[str, Path | str]:
    """Resolve all llama.cpp tools required by ENV-02."""

    llama_cpp = Path(llama_cpp_dir).expanduser().resolve()
    if not llama_cpp.is_dir():
        raise FileNotFoundError(f"llama.cpp directory missing: {llama_cpp}")

    llama_tokenize, llama_tokenize_source = resolve_llama_tokenize(
        llama_cpp, llama_tokenize_fallback
    )
    return {
        "llama_cpp": llama_cpp,
        "convert": _require_file(llama_cpp / CONVERT_SCRIPT, CONVERT_SCRIPT),
        "quantize": _require_executable(llama_cpp / QUANTIZE_BINARY, QUANTIZE_BINARY),
        "llama_cli": _require_executable(llama_cpp / LLAMA_CLI_BINARY, LLAMA_CLI_BINARY),
        "llama_tokenize": llama_tokenize,
        "llama_tokenize_source": llama_tokenize_source,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_converter_script(source: Path, out_dir: Path) -> tuple[Path, bool]:
    text = source.read_text(encoding="utf-8")
    if QWEN35_BASE_TOKENIZER_HASH in text:
        return source, False

    match = re.search(rf'(?m)^(?P<indent>\s*)if chkhsh == "{QWEN35_INSTRUCT_TOKENIZER_HASH}":', text)
    if match is None:
        return source, False

    indent = match.group("indent")
    patch = (
        f'{indent}if chkhsh == "{QWEN35_BASE_TOKENIZER_HASH}":\n'
        f'{indent}    # ref: https://huggingface.co/Qwen/Qwen3.5-9B\n'
        f'{indent}    res = "qwen35"\n'
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    prepared = out_dir / source.name
    prepared.write_text(text[: match.start()] + patch + text[match.start() :], encoding="utf-8")
    prepared.chmod(source.stat().st_mode)
    gguf_py = source.parent / "gguf-py"
    if gguf_py.exists() and not (out_dir / "gguf-py").exists():
        (out_dir / "gguf-py").symlink_to(gguf_py, target_is_directory=True)
    return prepared, True


def _run_command(cmd: list[str], timeout: int | None = None) -> dict[str, Any]:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=timeout)
    return {
        "argv": cmd,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def create_dummy_lora_adapter(
    model_or_fixture: str | Path,
    adapter_dir: Path,
    *,
    r: int = 2,
    lora_alpha: int = 4,
) -> Path:
    """Create a tiny LoRA adapter for the validated Qwen3.5 source."""

    try:
        import torch
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as exc:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("torch, transformers, and peft are required for dummy LoRA creation") from exc

    adapter_dir.mkdir(parents=True, exist_ok=True)
    model = AutoModelForCausalLM.from_pretrained(
        str(model_or_fixture),
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
        device_map="auto",
        trust_remote_code=False,
    )
    lora_cfg = LoraConfig(
        r=r,
        lora_alpha=lora_alpha,
        lora_dropout=0.0,
        bias="none",
        target_modules="all-linear",
        task_type="CAUSAL_LM",
    )
    peft_model = get_peft_model(model, lora_cfg)
    peft_model.save_pretrained(adapter_dir)
    tokenizer = AutoTokenizer.from_pretrained(str(model_or_fixture), trust_remote_code=False)
    tokenizer.save_pretrained(adapter_dir)
    return adapter_dir


def merge_dummy_lora_to_hf(
    model_or_fixture: str | Path,
    adapter_dir: Path,
    merged_hf_dir: Path,
) -> Path:
    """Merge the dummy LoRA adapter into an HF output directory."""

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as exc:  # pragma: no cover - runtime dependency guard
        raise RuntimeError("torch, transformers, and peft are required for LoRA merge") from exc

    base = AutoModelForCausalLM.from_pretrained(
        str(model_or_fixture),
        torch_dtype=torch.bfloat16,
        attn_implementation="sdpa",
        device_map="auto",
        trust_remote_code=False,
    )
    peft_model = PeftModel.from_pretrained(base, adapter_dir)
    merged = peft_model.merge_and_unload()
    merged_hf_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(merged_hf_dir, safe_serialization=True)
    tokenizer = AutoTokenizer.from_pretrained(str(model_or_fixture), trust_remote_code=False)
    tokenizer.save_pretrained(merged_hf_dir)
    return merged_hf_dir


def _copy_tokenizer_fixture(bf16_gguf: Path, tokenizer_gguf: Path) -> bool:
    tokenizer_gguf.parent.mkdir(parents=True, exist_ok=True)
    if bf16_gguf.resolve() == tokenizer_gguf.resolve():
        return tokenizer_gguf.exists()
    shutil.copy2(bf16_gguf, tokenizer_gguf)
    return tokenizer_gguf.exists()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--llama-cpp", default=str(DEFAULT_LLAMA_CPP))
    parser.add_argument("--llama-tokenize-fallback", default=str(DEFAULT_LLAMA_TOKENIZE_FALLBACK))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--n-predict", type=int, default=5)
    parser.add_argument("--fixture-hf", default=None)
    parser.add_argument("--tokenizer-gguf", default=str(DEFAULT_TOKENIZER_GGUF))
    return parser


def _initial_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "ok": False,
        "model": args.model,
        "fixture_hf": args.fixture_hf,
        "fixture_architecture": None,
        "llama_cpp": None,
        "convert": None,
        "convert_source": None,
        "convert_patched": False,
        "quantize": None,
        "llama_cli": None,
        "llama_tokenize": None,
        "llama_tokenize_source": None,
        "dummy_lora_created": False,
        "dummy_lora_dir": None,
        "dummy_lora_merged": False,
        "merged_hf": None,
        "bf16_or_fp16_gguf": None,
        "q4_gguf": None,
        "tokenizer_gguf": None,
        "commands": [],
        "inference_tail": "",
        "error": None,
    }


def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = Path(args.out)
    artifact_path = out_dir / "gguf_microconvert.json"
    payload = _initial_payload(args)

    try:
        source = Path(args.fixture_hf).expanduser().resolve() if args.fixture_hf else args.model
        cfg_info = assert_qwen35_config(source)
        payload["fixture_architecture"] = cfg_info.architecture

        paths = resolve_llama_cpp_paths(args.llama_cpp, args.llama_tokenize_fallback)
        prepared_convert, convert_patched = prepare_converter_script(
            Path(str(paths["convert"])), out_dir / "patched_converter"
        )
        payload.update(
            {
                "llama_cpp": str(paths["llama_cpp"]),
                "convert": str(prepared_convert),
                "convert_source": str(paths["convert"]),
                "convert_patched": convert_patched,
                "quantize": str(paths["quantize"]),
                "llama_cli": str(paths["llama_cli"]),
                "llama_tokenize": str(paths["llama_tokenize"]),
                "llama_tokenize_source": paths["llama_tokenize_source"],
            }
        )

        dummy_lora_dir = out_dir / "dummy_lora"
        merged_hf = out_dir / "merged_hf"
        bf16_gguf = out_dir / "model.bf16.gguf"
        q4_gguf = out_dir / "model.q4_K_M.gguf"
        tokenizer_gguf = Path(args.tokenizer_gguf)

        create_dummy_lora_adapter(source, dummy_lora_dir)
        payload["dummy_lora_created"] = dummy_lora_dir.exists()
        payload["dummy_lora_dir"] = str(dummy_lora_dir)

        merge_dummy_lora_to_hf(source, dummy_lora_dir, merged_hf)
        payload["dummy_lora_merged"] = merged_hf.exists()
        payload["merged_hf"] = str(merged_hf)

        convert_cmd = [
            sys.executable,
            str(prepared_convert),
            str(merged_hf),
            "--outfile",
            str(bf16_gguf),
            "--outtype",
            "bf16",
        ]
        convert_res = _run_command(convert_cmd, timeout=3600)
        payload["commands"].append({"name": "convert_hf_to_gguf.py", **convert_res})
        if convert_res["returncode"] != 0:
            raise RuntimeError("convert_hf_to_gguf.py failed")
        payload["bf16_or_fp16_gguf"] = str(bf16_gguf)

        _copy_tokenizer_fixture(bf16_gguf, tokenizer_gguf)
        payload["tokenizer_gguf"] = str(tokenizer_gguf)

        quant_cmd = [str(paths["quantize"]), str(bf16_gguf), str(q4_gguf), Q4_KIND]
        quant_res = _run_command(quant_cmd, timeout=3600)
        payload["commands"].append({"name": "llama-quantize", **quant_res})
        if quant_res["returncode"] != 0:
            raise RuntimeError("llama-quantize failed")
        payload["q4_gguf"] = str(q4_gguf)

        infer_cmd = [
            str(paths["llama_cli"]),
            "-m",
            str(q4_gguf),
            "-c",
            "512",
            "-st",
            "-n",
            str(args.n_predict),
            "-p",
            CUSTOM_SMOKE_PROMPT,
            "--no-display-prompt",
        ]
        infer_res = _run_command(infer_cmd, timeout=600)
        payload["commands"].append({"name": "llama-cli", **infer_res})
        payload["inference_tail"] = infer_res["stdout_tail"][-1000:]
        if infer_res["returncode"] != 0:
            raise RuntimeError("llama-cli failed")

        required_ok = [
            payload["dummy_lora_created"],
            payload["dummy_lora_merged"],
            q4_gguf.exists(),
            tokenizer_gguf.exists(),
            Path(str(paths["llama_tokenize"])).is_file(),
            os.access(Path(str(paths["llama_tokenize"])), os.X_OK),
        ]
        if not all(required_ok):
            raise RuntimeError("required ENV-02 outputs are missing")

        payload["ok"] = True
        return payload
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
        return payload
    finally:
        _write_json(artifact_path, payload)


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    payload = run_gate(args)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
