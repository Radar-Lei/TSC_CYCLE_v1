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

from tsc_cycle.prompt_builder import build_assistant_prefill, build_user_prompt
from tsc_cycle.student.tokenize_sanity import build_gguf_bpe_tokenizer, encode_gguf, encode_hf
from tsc_cycle.v3_gates.tokenizer_parity_v3 import first_diff, parse_llama_tokenize_ids

PROJECT_ROOT = Path("/home/samuel/TSC_CYCLE")
RUN_ROOT = PROJECT_ROOT / "runs" / "v4.0-4B-20260509T184844Z"
DEFAULT_MERGED_HF = RUN_ROOT / "merged_hf"
DEFAULT_GGUF = RUN_ROOT / "gguf" / "model.fp16.gguf"
DEFAULT_LLAMA_TOKENIZE = Path("/home/samuel/projects/EvoProgTSC/llama.cpp/llama-tokenize")
DEFAULT_PROMPT_FIXTURE = RUN_ROOT / "gguf" / "tokenizer_parity_prompts.jsonl"
DEFAULT_OUT = RUN_ROOT / "gguf" / "tokenizer_parity.json"
DEFAULT_GGUF_PY = Path("/home/samuel/projects/EvoProgTSC/llama.cpp/gguf-py")
DEFAULT_N = 20
DEFAULT_SEED = 42
TIMEOUT_SECONDS = 120

REQUIREMENTS_COVERED = ["GGUF4B-02", "GGUF4B-03"]


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _tail(text: str, limit: int = 2000) -> str:
    return text[-limit:]


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"malformed JSONL at {path}:{line_no}: {exc}") from exc
            if isinstance(parsed, dict):
                yield parsed


def _record_input(record: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(record.get("input"), dict):
        return record["input"]
    if isinstance(record.get("prediction"), dict):
        return {"prediction": record["prediction"]}
    return None


def _split_hint(record: dict[str, Any], default: str) -> str:
    for key in ("split_hint", "split", "source"):
        value = record.get(key)
        if value:
            return str(value)
    return default


def _sample_id(record: dict[str, Any], fallback: str) -> str:
    for key in ("sample_id", "input_id", "id"):
        value = record.get(key)
        if value:
            return str(value)
    return fallback


def _synthetic_inputs() -> list[dict[str, Any]]:
    return [
        {
            "sample_id": "phase10-synthetic-0001",
            "split_hint": "synthetic_boundary",
            "input": {
                "prediction": {
                    "as_of": "2026-05-11 00:00:00",
                    "phase_waits": [
                        {"phase_id": 1, "pred_wait": 0.0, "pred_saturation": 0.0, "min_green": 1, "max_green": 5, "capacity": 1},
                        {"phase_id": 2, "pred_wait": 999.0, "pred_saturation": 1.0, "min_green": 120, "max_green": 180, "capacity": 999},
                    ],
                }
            },
        },
        {
            "sample_id": "phase10-synthetic-0002",
            "split_hint": "synthetic_boundary",
            "input": {
                "prediction": {
                    "as_of": "2026-05-11 00:01:00",
                    "phase_waits": [
                        {"phase_id": 10, "pred_wait": 12.5, "pred_saturation": 0.3333, "min_green": 15, "max_green": 30, "capacity": 48},
                        {"phase_id": 20, "pred_wait": 42.0, "pred_saturation": 0.875, "min_green": 45, "max_green": 80, "capacity": 40},
                        {"phase_id": 30, "pred_wait": 0.0, "pred_saturation": 0.125, "min_green": 50, "max_green": 120, "capacity": 32},
                    ],
                }
            },
        },
        {
            "sample_id": "phase10-synthetic-0003",
            "split_hint": "synthetic_boundary",
            "input": {
                "prediction": {
                    "as_of": "2026-05-11 00:02:00",
                    "phase_waits": [
                        {"phase_id": 1, "pred_wait": 1.0, "pred_saturation": 0.0083, "min_green": 2, "max_green": 2, "capacity": 500},
                        {"phase_id": 2, "pred_wait": 300.0, "pred_saturation": 0.9999, "min_green": 90, "max_green": 180, "capacity": 1},
                    ],
                }
            },
        },
    ]


def _candidate_records() -> list[dict[str, Any]]:
    paths = [
        (PROJECT_ROOT / "data" / "v4" / "phase8" / "splits" / "ood_val.index.jsonl", "ood_val"),
        (PROJECT_ROOT / "data" / "v4" / "phase8" / "splits" / "val.index.jsonl", "val"),
        (PROJECT_ROOT / "data" / "v4" / "phase8" / "splits" / "train.index.jsonl", "train"),
        (PROJECT_ROOT / "data" / "v4" / "phase8" / "labeled_merged.jsonl", "merged"),
        (PROJECT_ROOT / "data" / "labeled.jsonl", "legacy_labeled"),
    ]
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path, default_split in paths:
        for record in _read_jsonl(path):
            payload = _record_input(record)
            if payload is None:
                continue
            sid = _sample_id(record, f"{path.name}:{len(candidates):06d}")
            key = _json_dumps(payload)
            if key in seen:
                continue
            seen.add(key)
            candidates.append({"sample_id": sid, "split_hint": _split_hint(record, default_split), "input": payload})
    for record in _synthetic_inputs():
        key = _json_dumps(record["input"])
        if key not in seen:
            seen.add(key)
            candidates.append(record)
    candidates.sort(key=lambda row: (str(row["split_hint"]), str(row["sample_id"]), _json_dumps(row["input"])))
    return candidates


def build_phase10_prompt_fixture(out: Path | dict[str, Any], n: int = DEFAULT_N, seed: int = DEFAULT_SEED) -> list[dict[str, Any]] | dict[str, Any]:
    if isinstance(out, dict):
        record = out
        prediction_input = _record_input(record)
        if prediction_input is None:
            raise ValueError("record must contain input or prediction")
        return {
            "sample_id": _sample_id(record, "phase10-fixture-0000"),
            "split_hint": _split_hint(record, "unknown"),
            "input": prediction_input,
            "prompt": build_user_prompt(prediction_input),
            "assistant_prefill": build_assistant_prefill(),
            "requirements_covered": REQUIREMENTS_COVERED,
        }

    out = Path(out)
    candidates = _candidate_records()
    if len(candidates) < n:
        base = len(candidates)
        synth = _synthetic_inputs()
        for idx in range(n - base):
            src = synth[idx % len(synth)]
            candidates.append(
                {
                    "sample_id": f"phase10-synthetic-repeat-{idx:04d}",
                    "split_hint": src["split_hint"],
                    "input": src["input"],
                }
            )
    selected = random.Random(seed).sample(candidates, n)
    rows = [build_phase10_prompt_fixture(row) for row in selected]
    rows.sort(key=lambda row: str(row["sample_id"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return rows


def compare_tokenizer_parity(
    prompt: dict[str, Any],
    hf_token_ids: list[int],
    llama_token_ids: list[int],
    stdout: str = "",
    stderr: str = "",
    parse_error: str | None = None,
) -> dict[str, Any]:
    diff_index = None if parse_error else first_diff(hf_token_ids, llama_token_ids)
    match = parse_error is None and diff_index is None
    diagnostics: list[dict[str, Any]] = []
    if parse_error is not None:
        diagnostics.append({"kind": "parse_failed", "reason": parse_error})
    elif diff_index is not None:
        if diff_index < min(len(hf_token_ids), len(llama_token_ids)):
            diagnostics.append(
                {
                    "kind": "id_mismatch",
                    "index": diff_index,
                    "hf_id": hf_token_ids[diff_index],
                    "llama_id": llama_token_ids[diff_index],
                }
            )
        if len(hf_token_ids) != len(llama_token_ids):
            diagnostics.append(
                {
                    "kind": "length_mismatch",
                    "index": diff_index,
                    "hf_len": len(hf_token_ids),
                    "llama_len": len(llama_token_ids),
                }
            )
    return {
        "ok": match,
        "match": match,
        "sample_id": prompt.get("sample_id") or prompt.get("prompt_id"),
        "split_hint": prompt.get("split_hint"),
        "first_diff_index": diff_index,
        "hf_token_ids": hf_token_ids,
        "llama_token_ids": llama_token_ids,
        "hf_ids_sample": hf_token_ids[:64],
        "llama_ids_sample": llama_token_ids[:64],
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
        "parse_error": parse_error,
        "mismatch_diagnostics": diagnostics,
        "requirements_covered": ["GGUF4B-03"],
    }


def _load_fixture(path: Path) -> list[dict[str, Any]]:
    rows = list(_read_jsonl(path))
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row.get("sample_id"), str) or not isinstance(row.get("prompt"), str):
            raise ValueError(f"malformed tokenizer parity fixture row {idx} in {path}")
    return rows


def _fail_report(reason: str, merged_hf: Path, gguf: Path, llama_tokenize: Path, fixture: Path, out: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "n": 0,
        "matched": 0,
        "mismatched": 0,
        "parse_failed": 0,
        "fixture": str(fixture),
        "merged_hf": str(merged_hf),
        "gguf": str(gguf),
        "llama_tokenize": str(llama_tokenize),
        "fatal_failures": [{"gate": "runtime_paths", "reason": reason}],
        "requirements_covered": ["GGUF4B-03"],
        "results": [],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _validate_paths(merged_hf: Path, gguf: Path, llama_tokenize: Path, fixture: Path, out: Path) -> None:
    if not merged_hf.exists() or not merged_hf.is_dir():
        raise FileNotFoundError(f"missing merged HF tokenizer directory: {merged_hf}")
    if not gguf.exists() or not gguf.is_file():
        raise FileNotFoundError(f"missing GGUF file: {gguf}")
    if not llama_tokenize.exists() or not llama_tokenize.is_file():
        raise FileNotFoundError(f"missing llama-tokenize tool: {llama_tokenize}")
    if not llama_tokenize.stat().st_mode & 0o111:
        raise PermissionError(f"llama-tokenize tool is not executable: {llama_tokenize}")
    if fixture.resolve() == out.resolve():
        raise ValueError("fixture and out paths must differ")


def _llama_command(tool: Path, gguf: Path, prompt: str) -> list[str]:
    name = tool.name
    if name == "llama-cli":
        return [
            str(tool),
            "--model",
            str(gguf),
            "--prompt",
            prompt,
            "--predict",
            "0",
            "--verbose-prompt",
            "--no-display-prompt",
            "--no-warmup",
            "--log-disable",
        ]
    return [str(tool), "--model", str(gguf), "--prompt", prompt, "--ids", "--no-bos", "--log-disable"]


def _parse_llama_ids(stdout: str, stderr: str) -> list[int]:
    try:
        return parse_llama_tokenize_ids(stdout)
    except ValueError:
        pass
    text = stdout + "\n" + stderr
    candidates = [
        r"prompt eval token ids:\s*(\[[\s\d,\-]+\])",
        r"tokens?:\s*(\[[\s\d,\-]+\])",
    ]
    for pattern in candidates:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        parsed = ast.literal_eval(match.group(1))
        if isinstance(parsed, list) and all(isinstance(item, int) for item in parsed):
            return parsed
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if re.fullmatch(r"[-+]?\d+(?:\s+[-+]?\d+)+", line):
            return [int(part) for part in line.split()]
    raise ValueError("no token ids parseable from llama tokenizer output")


def run_llama_tokenize_parity(merged_hf: Path, gguf: Path, llama_tokenize: Path, fixture: Path, out: Path, gguf_py_path: Path = DEFAULT_GGUF_PY) -> dict[str, Any]:
    merged_hf = Path(merged_hf)
    gguf = Path(gguf)
    llama_tokenize = Path(llama_tokenize)
    fixture = Path(fixture)
    out = Path(out)

    if not fixture.exists():
        build_phase10_prompt_fixture(fixture, n=DEFAULT_N, seed=DEFAULT_SEED)
    try:
        if not merged_hf.exists() or not merged_hf.is_dir():
            raise FileNotFoundError(f"missing merged HF tokenizer directory: {merged_hf}")
        if not gguf.exists() or not gguf.is_file():
            raise FileNotFoundError(f"missing GGUF file: {gguf}")
        if fixture.resolve() == out.resolve():
            raise ValueError("fixture and out paths must differ")
    except Exception as exc:
        return _fail_report(str(exc), merged_hf, gguf, llama_tokenize, fixture, out)

    prompts = _load_fixture(fixture)

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(str(merged_hf))
    bpe, gmeta = build_gguf_bpe_tokenizer(str(gguf), str(gguf_py_path))
    results: list[dict[str, Any]] = []
    matched = 0
    mismatched = 0
    parse_failed = 0

    for row in prompts:
        prompt_text = row["prompt"]
        hf_ids = encode_hf(tokenizer, prompt_text)
        llama_ids: list[int] = []
        parse_error: str | None = None
        stdout = ""
        stderr = ""
        try:
            llama_ids = encode_gguf(bpe, prompt_text)
        except Exception as exc:
            parse_error = str(exc)
        result = compare_tokenizer_parity(row, hf_ids, llama_ids, stdout=stdout, stderr=stderr, parse_error=parse_error)
        if result["match"]:
            matched += 1
        elif parse_error is not None:
            parse_failed += 1
        else:
            mismatched += 1
        results.append(result)

    ok = matched == len(prompts) and mismatched == 0 and parse_failed == 0
    payload = {
        "ok": ok,
        "all_match": ok,
        "n": len(prompts),
        "matched": matched,
        "mismatched": mismatched,
        "parse_failed": parse_failed,
        "fixture": str(fixture),
        "merged_hf": str(merged_hf),
        "gguf": str(gguf),
        "llama_tokenize": str(llama_tokenize),
        "tokenizer_source": "gguf_metadata_bpe",
        "gguf_tokenizer_model": gmeta.get("model"),
        "gguf_pre_tokenizer": gmeta.get("pre") or None,
        "requirements_covered": ["GGUF4B-03"],
        "fatal_failures": [] if ok else [{"gate": "tokenizer_parity", "reason": "HF tokenizer IDs differ from GGUF metadata tokenizer IDs or could not be parsed"}],
        "results": results,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def evaluate_tokenizer_parity(report_path: Path) -> dict[str, Any]:
    report_path = Path(report_path)
    data = json.loads(report_path.read_text(encoding="utf-8"))
    ok = bool(data.get("ok")) and data.get("matched") == data.get("n") and data.get("mismatched") == 0 and data.get("parse_failed") == 0
    return {
        "ok": ok,
        "report_path": str(report_path),
        "n": data.get("n", 0),
        "matched": data.get("matched", 0),
        "mismatched": data.get("mismatched", 0),
        "parse_failed": data.get("parse_failed", 0),
        "requirements_covered": data.get("requirements_covered", ["GGUF4B-03"]),
        "fatal_failures": [] if ok else data.get("fatal_failures", [{"gate": "tokenizer_parity", "reason": "tokenizer parity report is red"}]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 10 HF tokenizer vs llama.cpp GGUF tokenizer parity gate")
    parser.add_argument("--merged-hf", type=Path, default=DEFAULT_MERGED_HF)
    parser.add_argument("--gguf", type=Path, default=DEFAULT_GGUF)
    parser.add_argument("--llama-tokenize", type=Path, default=DEFAULT_LLAMA_TOKENIZE)
    parser.add_argument("--prompt-fixture", type=Path, default=DEFAULT_PROMPT_FIXTURE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--gguf-py-path", type=Path, default=DEFAULT_GGUF_PY)
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not Path(args.prompt_fixture).exists():
        build_phase10_prompt_fixture(Path(args.prompt_fixture), n=args.n, seed=args.seed)
    payload = run_llama_tokenize_parity(args.merged_hf, args.gguf, args.llama_tokenize, args.prompt_fixture, args.out, args.gguf_py_path)
    if not payload.get("ok"):
        print(
            f"[PHASE10-TOKENIZER-PARITY] FAIL matched={payload.get('matched')} mismatched={payload.get('mismatched')} parse_failed={payload.get('parse_failed')} -> {args.out}",
            file=sys.stderr,
        )
        return 1
    print(f"[PHASE10-TOKENIZER-PARITY] OK matched={payload['matched']}/{payload['n']} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
