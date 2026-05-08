"""Qwen3.5 causal-LM environment smoke gate for v3.0 Phase 1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

DEFAULT_MODEL = "Qwen/Qwen3.5-9B"
DEFAULT_OUT = "artifacts/v3/phase1/env_smoke.json"
DEFAULT_PROMPT = "DGX Spark Qwen3.5 smoke test"
EXPECTED_VENV = "/home/samuel/TSC_CYCLE/.venv/bin/python"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Qwen3.5 causal-LM NF4+SDPA smoke gate.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    return parser


def _config_list(config: Any, attr: str) -> list[str]:
    value = getattr(config, attr, None)
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _model_identity_terms(model: Any) -> list[str]:
    config = getattr(model, "config", None)
    terms = [model.__class__.__name__]
    if config is not None:
        terms.extend(_config_list(config, "architectures"))
        model_type = getattr(config, "model_type", None)
        if model_type is not None:
            terms.append(str(model_type))
    return terms


def assert_qwen35_causal_lm(model: Any) -> None:
    """Fail unless class/config explicitly identify a Qwen3.5 text causal LM."""
    terms = _model_identity_terms(model)
    lowered = [term.lower() for term in terms]
    joined = " ".join(lowered)

    forbidden = ("conditionalgeneration", "vision", "visual", "imagetext", "image_text")
    if any(token in joined for token in forbidden):
        raise AssertionError(f"model identity includes forbidden non-causal-LM path: {terms}")

    class_ok = model.__class__.__name__ == "Qwen3_5ForCausalLM"
    arch_ok = any(term == "Qwen3_5ForCausalLM" for term in terms)
    model_type_ok = any(term in {"qwen3_5", "qwen3.5", "qwen3_5_text"} for term in lowered)
    causal_ok = any("causallm" in term.replace("_", "") for term in lowered)

    if not (class_ok or arch_ok or (model_type_ok and causal_ok)):
        raise AssertionError(f"model is not an explicit Qwen3.5 causal LM: {terms}")


def _is_vision_param_name(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered.startswith("vision")
        or ".vision" in lowered
        or "vision_tower" in lowered
        or lowered.startswith("visual")
        or ".visual" in lowered
    )


def count_vision_params(named_parameters: Iterable[tuple[str, Any]]) -> tuple[int, list[str]]:
    """Count parameters whose namespace indicates vision/visual modules."""
    names: list[str] = []
    count = 0
    for name, _param in named_parameters:
        if _is_vision_param_name(name):
            count += 1
            if len(names) < 20:
                names.append(name)
    return count, names


def _json_safe(value: Any) -> Any:
    if isinstance(value, torch.Size):
        return list(value)
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return value


def _write_payload(out_path: Path, payload: dict[str, Any]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _base_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "ok": False,
        "model": args.model,
        "model_class": None,
        "architectures": [],
        "model_type": None,
        "torch_version": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "logits_shape": None,
        "vision_param_count": None,
        "vision_params_sample": [],
        "attn_implementation": "sdpa",
        "quantization": {
            "load_in_4bit": True,
            "bnb_4bit_quant_type": "nf4",
            "bnb_4bit_compute_dtype": "bfloat16",
            "bnb_4bit_use_double_quant": True,
        },
        "sys_executable": sys.executable,
        "expected_venv": EXPECTED_VENV,
        "error": None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out_path = Path(args.out)
    payload = _base_payload(args)

    try:
        if sys.executable != EXPECTED_VENV:
            raise RuntimeError(f"must run with {EXPECTED_VENV}; got {sys.executable}")
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available to PyTorch")

        tokenizer = AutoTokenizer.from_pretrained(args.model)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        tokenizer.padding_side = "right"

        bnb_cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            quantization_config=bnb_cfg,
            attn_implementation="sdpa",
            torch_dtype=torch.bfloat16,
            device_map={"": 0},
        )
        model.eval()

        config = getattr(model, "config", None)
        payload["model_class"] = model.__class__.__name__
        payload["architectures"] = _config_list(config, "architectures") if config is not None else []
        payload["model_type"] = str(getattr(config, "model_type", None)) if config is not None else None

        assert_qwen35_causal_lm(model)
        vision_count, vision_sample = count_vision_params(model.named_parameters())
        payload["vision_param_count"] = vision_count
        payload["vision_params_sample"] = vision_sample
        if vision_count != 0:
            raise RuntimeError(f"vision/visual parameters found: {vision_sample}")

        inputs = tokenizer(args.prompt, return_tensors="pt").to("cuda")
        with torch.no_grad():
            outputs = model(**inputs)
        payload["logits_shape"] = list(outputs.logits.shape)
        payload["ok"] = True
        _write_payload(out_path, payload)
        return 0
    except Exception as exc:  # noqa: BLE001 - gate writes failure artifact before exiting.
        payload["error"] = f"{type(exc).__name__}: {exc}"
        _write_payload(out_path, payload)
        print(f"[ENV-SMOKE-V3] FAIL: {payload['error']}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
