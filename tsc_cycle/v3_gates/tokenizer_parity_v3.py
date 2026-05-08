from __future__ import annotations

import argparse
import ast
import json
import random
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

from tsc_cycle.prompt_builder import build_user_prompt

DEFAULT_MODEL = "Qwen/Qwen3.5-9B"
DEFAULT_LABELED = Path("data/labeled.jsonl")
DEFAULT_OOD_INPUTS = Path("data/ood_inputs.jsonl")
DEFAULT_PROMPT_FIXTURE = Path("artifacts/v3/phase1/tokenizer_parity_prompts.jsonl")
DEFAULT_OUT = Path("artifacts/v3/phase1/tokenizer_parity.json")
DEFAULT_N = 100
DEFAULT_SEED = 42


def _iter_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"[TOKENIZER-PARITY] malformed JSON at {path}:{line_no}: {exc}") from exc


def _record_input(record: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(record.get("input"), dict):
        return record["input"]
    if isinstance(record.get("prediction"), dict):
        return {"prediction": record["prediction"]}
    return None


def _stable_prompt_id(source: str, record: dict[str, Any], fallback: str) -> str:
    for key in ("sample_id", "input_id", "id"):
        value = record.get(key)
        if value:
            return f"{source}:{value}"
    return f"{source}:{fallback}"


def _synthetic_boundary_inputs() -> list[dict[str, Any]]:
    return [
        {
            "prediction": {
                "as_of": "2026-05-08 00:00:00",
                "phase_waits": [
                    {
                        "phase_id": 1,
                        "pred_wait": 0.0,
                        "pred_saturation": 0.0,
                        "min_green": 1,
                        "max_green": 5,
                        "capacity": 1,
                    },
                    {
                        "phase_id": 2,
                        "pred_wait": 999.0,
                        "pred_saturation": 1.0,
                        "min_green": 120,
                        "max_green": 180,
                        "capacity": 999,
                    },
                ],
            }
        },
        {
            "prediction": {
                "as_of": "2026-05-08 00:01:00",
                "phase_waits": [
                    {
                        "phase_id": 10,
                        "pred_wait": 12.5,
                        "pred_saturation": 0.3333,
                        "min_green": 15,
                        "max_green": 30,
                        "capacity": 48,
                    },
                    {
                        "phase_id": 20,
                        "pred_wait": 42.0,
                        "pred_saturation": 0.875,
                        "min_green": 45,
                        "max_green": 80,
                        "capacity": 40,
                    },
                    {
                        "phase_id": 30,
                        "pred_wait": 0.0,
                        "pred_saturation": 0.125,
                        "min_green": 50,
                        "max_green": 120,
                        "capacity": 32,
                    },
                ],
            }
        },
        {
            "prediction": {
                "as_of": "2026-05-08 00:02:00",
                "phase_waits": [
                    {
                        "phase_id": 1,
                        "pred_wait": 1.0,
                        "pred_saturation": 0.0083,
                        "min_green": 2,
                        "max_green": 2,
                        "capacity": 500,
                    },
                    {
                        "phase_id": 2,
                        "pred_wait": 300.0,
                        "pred_saturation": 0.9999,
                        "min_green": 90,
                        "max_green": 180,
                        "capacity": 1,
                    },
                ],
            }
        },
    ]


def _candidate_prompts(labeled_path: Path, ood_inputs_path: Path | None) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(prompt_id: str, source: str, payload: dict[str, Any]) -> None:
        if prompt_id in seen:
            return
        seen.add(prompt_id)
        candidates.append(
            {
                "prompt_id": prompt_id,
                "source": source,
                "text": build_user_prompt(payload),
            }
        )

    for line_no, record in _iter_jsonl(labeled_path):
        payload = _record_input(record)
        if payload is None:
            continue
        add(_stable_prompt_id("labeled", record, str(line_no)), "labeled", payload)

    if ood_inputs_path is not None:
        for line_no, record in _iter_jsonl(ood_inputs_path):
            payload = _record_input(record)
            if payload is None:
                continue
            add(_stable_prompt_id("ood", record, str(line_no)), "ood", payload)

    for idx, payload in enumerate(_synthetic_boundary_inputs()):
        add(f"synthetic_boundary:{idx:03d}", "synthetic_boundary", payload)

    candidates.sort(key=lambda row: row["prompt_id"])
    return candidates


def build_prompt_fixture(
    labeled_path: Path = DEFAULT_LABELED,
    ood_inputs_path: Path | None = DEFAULT_OOD_INPUTS,
    out_path: Path = DEFAULT_PROMPT_FIXTURE,
    n: int = DEFAULT_N,
    seed: int = DEFAULT_SEED,
) -> list[dict[str, str]]:
    candidates = _candidate_prompts(labeled_path, ood_inputs_path)
    if len(candidates) < n:
        base = len(candidates)
        for idx in range(n - base):
            payload = _synthetic_boundary_inputs()[idx % len(_synthetic_boundary_inputs())]
            record = {
                "prompt_id": f"synthetic_boundary:repeat:{idx:03d}",
                "source": "synthetic_boundary",
                "text": build_user_prompt(payload),
            }
            candidates.append(record)
        candidates.sort(key=lambda row: row["prompt_id"])

    selected = random.Random(seed).sample(candidates, n)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for row in selected:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            fh.write("\n")
    return selected


def parse_llama_tokenize_ids(stdout: str) -> list[int]:
    for match in re.finditer(r"\[[\s\d,\-]+\]", stdout):
        try:
            parsed = ast.literal_eval(match.group(0))
        except (SyntaxError, ValueError):
            continue
        if isinstance(parsed, list) and parsed and all(isinstance(item, int) for item in parsed):
            return parsed
        if parsed == []:
            return []

    stripped = stdout.strip()
    if re.fullmatch(r"[-+]?\d+(?:\s+[-+]?\d+)*", stripped):
        return [int(part) for part in stripped.split()]

    raise ValueError("no token ids parseable from llama-tokenize stdout")


def first_diff(a: list[int], b: list[int]) -> int | None:
    for idx, (left, right) in enumerate(zip(a, b, strict=False)):
        if left != right:
            return idx
    if len(a) != len(b):
        return min(len(a), len(b))
    return None


def _tail(text: str, limit: int = 2000) -> str:
    return text[-limit:]


def _load_fixture(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line_no, record in _iter_jsonl(path):
        prompt_id = record.get("prompt_id")
        text = record.get("text")
        if not isinstance(prompt_id, str) or not isinstance(text, str):
            raise SystemExit(f"[TOKENIZER-PARITY] malformed fixture row at {path}:{line_no}")
        rows.append({"prompt_id": prompt_id, "source": str(record.get("source", "")), "text": text})
    return rows


def _binary_requires_model(binary: Path) -> bool:
    res = subprocess.run([str(binary), "--help"], capture_output=True, text=True, check=False, timeout=30)
    help_text = f"{res.stdout}\n{res.stderr}"
    return "--model" in help_text or " -m" in help_text or "<model" in help_text.lower()


def _validate_runtime_paths(llama_tokenize: Path, gguf: Path | None, require_gguf: bool) -> tuple[Path, Path | None]:
    llama_tokenize = llama_tokenize.expanduser().resolve()
    if not llama_tokenize.exists():
        raise SystemExit(f"[TOKENIZER-PARITY] llama-tokenize missing: {llama_tokenize}")
    if not llama_tokenize.is_file():
        raise SystemExit(f"[TOKENIZER-PARITY] llama-tokenize is not a file: {llama_tokenize}")
    if not llama_tokenize.stat().st_mode & 0o111:
        raise SystemExit(f"[TOKENIZER-PARITY] llama-tokenize is not executable: {llama_tokenize}")

    resolved_gguf: Path | None = None
    if gguf is not None:
        resolved_gguf = gguf.expanduser().resolve()

    model_required = require_gguf or _binary_requires_model(llama_tokenize)
    if model_required:
        if resolved_gguf is None:
            raise SystemExit("[TOKENIZER-PARITY] --gguf is required when --require-gguf is active or llama-tokenize requires --model")
        if not resolved_gguf.exists() or not resolved_gguf.is_file():
            raise SystemExit(f"[TOKENIZER-PARITY] required GGUF fixture missing: {resolved_gguf}")
    return llama_tokenize, resolved_gguf


def _run_llama_tokenize(llama_tokenize: Path, text: str, gguf: Path | None) -> subprocess.CompletedProcess[str]:
    if gguf is not None:
        cmd = [str(llama_tokenize), "--model", str(gguf), "--prompt", text, "--ids", "--no-bos", "--log-disable"]
    else:
        cmd = [str(llama_tokenize), "--prompt", text, "--ids", "--no-bos", "--log-disable"]
    return subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)


def run_parity(args: argparse.Namespace) -> dict[str, Any]:
    prompt_fixture = Path(args.prompt_fixture)
    if not prompt_fixture.exists():
        build_prompt_fixture(
            labeled_path=Path(args.labeled),
            ood_inputs_path=Path(args.ood_inputs) if args.ood_inputs else None,
            out_path=prompt_fixture,
            n=args.n,
            seed=args.seed,
        )
    prompts = _load_fixture(prompt_fixture)
    if len(prompts) != args.n:
        raise SystemExit(f"[TOKENIZER-PARITY] fixture has {len(prompts)} prompts; expected {args.n}")

    llama_tokenize, gguf = _validate_runtime_paths(
        Path(args.llama_tokenize), Path(args.gguf) if args.gguf else None, args.require_gguf
    )

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model)

    results: list[dict[str, Any]] = []
    matched = 0
    mismatched = 0
    parse_failed = 0

    for row in prompts:
        text = row["text"]
        hf_ids = list(tokenizer.encode(text, add_special_tokens=False))
        proc = _run_llama_tokenize(llama_tokenize, text, gguf)
        llama_ids: list[int] = []
        parse_error: str | None = None
        if proc.returncode == 0:
            try:
                llama_ids = parse_llama_tokenize_ids(proc.stdout)
            except ValueError as exc:
                parse_error = str(exc)
        else:
            parse_error = f"llama-tokenize exited {proc.returncode}"

        diff_index = first_diff(hf_ids, llama_ids) if parse_error is None else None
        is_match = parse_error is None and diff_index is None
        if is_match:
            matched += 1
        elif parse_error is not None:
            parse_failed += 1
        else:
            mismatched += 1

        results.append(
            {
                "prompt_id": row["prompt_id"],
                "matched": is_match,
                "first_diff_index": diff_index,
                "hf_ids_sample": hf_ids[:32],
                "llama_ids_sample": llama_ids[:32],
                "stdout_tail": _tail(proc.stdout),
                "stderr_tail": _tail(proc.stderr),
                "parse_error": parse_error,
            }
        )

    ok = matched == args.n and mismatched == 0 and parse_failed == 0
    payload = {
        "ok": ok,
        "n": args.n,
        "matched": matched,
        "mismatched": mismatched,
        "parse_failed": parse_failed,
        "fixture": str(prompt_fixture),
        "llama_tokenize": str(llama_tokenize),
        "gguf": str(gguf) if gguf is not None else None,
        "require_gguf": bool(args.require_gguf),
        "results": results,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Qwen3.5 HF tokenizer vs llama-tokenize exact parity gate")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--labeled", type=Path, default=DEFAULT_LABELED)
    parser.add_argument("--ood-inputs", type=Path, default=DEFAULT_OOD_INPUTS)
    parser.add_argument("--prompt-fixture", type=Path, default=DEFAULT_PROMPT_FIXTURE)
    parser.add_argument("--llama-tokenize", required=True, help="absolute llama-tokenize path recorded by gguf_microconvert.json")
    parser.add_argument("--gguf", type=Path, default=None, help="GGUF tokenizer/model fixture path")
    parser.add_argument("--require-gguf", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_parity(args)
    if not payload["ok"]:
        print(
            f"[TOKENIZER-PARITY] FAIL matched={payload['matched']} mismatched={payload['mismatched']} parse_failed={payload['parse_failed']} -> {payload['fixture']}",
            file=sys.stderr,
        )
        return 1
    print(f"[TOKENIZER-PARITY] OK matched={payload['matched']}/{payload['n']} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
