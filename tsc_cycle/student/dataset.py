"""Tokenize labeled.jsonl → arrow datasets with loss-masked labels.

Splits:
  - val_ood — every sample whose split_hint == "ood"
  - val_id  — 10% of split_hint == "id" by sample_id-hash bucket
  - train   — remaining 90% of split_hint == "id"

Loss masking: labels = -100 for everything except the assistant content (the
text from <start_working_out> through </SOLUTION>, inclusive).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from transformers import AutoTokenizer

from tsc_cycle.prompt_builder import (
    TAG_SOLUTION_CLOSE,
    TAG_THINK_OPEN,
    build_full_assistant,
    build_user_prompt,
)
from tsc_cycle.tokenizer_check import (
    assert_no_native_think_in_ids,
    check_tokenizer,
    native_think_token_ids,
)

MODEL_NAME = "Qwen/Qwen3-4B-Thinking-2507"


def split_bucket(sample_id: str, n: int = 10) -> int:
    """0..n-1 deterministic bucket from sample_id."""
    h = hashlib.sha256(sample_id.encode()).digest()
    return int.from_bytes(h[:8], "big") % n


DATASET_RAW_TEXT_PATH = "prompt_builder.build_user_prompt+build_full_assistant"
CHAT_TEMPLATE_USED = False


def dataset_wiring_metadata() -> dict[str, str | bool]:
    """Evidence that v3 SFT data uses raw prompt text, not chat templates."""
    return {
        "chat_template_used": CHAT_TEMPLATE_USED,
        "dataset_raw_text_path": DATASET_RAW_TEXT_PATH,
    }


def build_text(input_obj: dict, reasoning: str, solution: dict[str, int]) -> tuple[str, str]:
    """Returns raw (prompt_text, assistant_text); no tokenizer chat template is used."""
    prompt = build_user_prompt(input_obj)
    assistant = build_full_assistant(reasoning, solution)
    return prompt, assistant


def tokenize_one(tokenizer, prompt: str, assistant: str, max_length: int) -> dict[str, list[int] | bool | dict]:
    """Tokenize prompt+assistant raw text; mask prompt with -100 in labels."""
    native_ids = native_think_token_ids(tokenizer)
    full = prompt + "\n" + assistant + tokenizer.eos_token
    enc = tokenizer(full, truncation=True, max_length=max_length, add_special_tokens=False)
    input_ids = enc["input_ids"]

    # Find the boundary: tokenize prompt-only (with the trailing \n), then assistant text begins after.
    pre = tokenizer(prompt + "\n", add_special_tokens=False)["input_ids"]
    n_prompt = len(pre)

    labels = [-100] * len(input_ids)
    for i in range(n_prompt, len(input_ids)):
        labels[i] = input_ids[i]

    # Native think token id leakage check: must NOT appear anywhere in input_ids.
    assert_no_native_think_in_ids(input_ids, native_ids=native_ids)

    metadata = dataset_wiring_metadata()
    return {
        "input_ids": input_ids,
        "attention_mask": [1] * len(input_ids),
        "labels": labels,
        "chat_template_used": metadata["chat_template_used"],
        "metadata": metadata,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labeled", default="data/labeled.jsonl")
    ap.add_argument("--out-dir", default="data/tokenized")
    ap.add_argument("--max-length-cap", type=int, default=4096, help="hard cap for max_length")
    ap.add_argument("--p99-buffer", type=int, default=64, help="buffer added to p99 token length")
    ap.add_argument("--model", default=MODEL_NAME)
    ap.add_argument("--card", default="data/dataset_card.md")
    args = ap.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    res = check_tokenizer(tokenizer)
    if not res.ok:
        raise SystemExit(f"tokenizer_check failed: {res.details}")
    print(f"tokenizer OK: vocab {len(tokenizer)}, custom tags multi-token, native think single-token")

    rows = []
    for line in Path(args.labeled).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("result", {}).get("success") is False:
            continue
        sol = rec["result"]["solution"]
        rsn = rec["result"]["reasoning"]
        prompt, assistant = build_text(rec["input"], rsn, sol)
        rows.append({
            "sample_id": rec["sample_id"],
            "split_hint": rec["split_hint"],
            "trivial": rec.get("trivial", False),
            "prompt": prompt,
            "assistant": assistant,
        })
    print(f"loaded {len(rows)} valid samples from {args.labeled}")

    # First pass: tokenize all to estimate p99 length
    print("estimating max_length from p99 of full sequences...")
    raw_lens = []
    for r in rows:
        ids = tokenizer(r["prompt"] + "\n" + r["assistant"] + tokenizer.eos_token,
                       add_special_tokens=False)["input_ids"]
        raw_lens.append(len(ids))
    raw_lens.sort()
    p99 = raw_lens[int(len(raw_lens) * 0.99)] if raw_lens else args.max_length_cap
    max_length = min(p99 + args.p99_buffer, args.max_length_cap)
    print(f"p99 token length = {p99}; using max_length = {max_length} (cap {args.max_length_cap})")

    # Split assignment
    splits: dict[str, list[dict]] = {"train": [], "val_id": [], "val_ood": []}
    for r in rows:
        if r["split_hint"] == "ood":
            splits["val_ood"].append(r)
        else:
            b = split_bucket(r["sample_id"], 10)
            if b < 1:  # 10%
                splits["val_id"].append(r)
            else:
                splits["train"].append(r)

    # Sample-id integrity check
    train_ids = {r["sample_id"] for r in splits["train"]}
    val_id_ids = {r["sample_id"] for r in splits["val_id"]}
    val_ood_ids = {r["sample_id"] for r in splits["val_ood"]}
    assert not (train_ids & val_id_ids), "train ∩ val_id leakage"
    assert not (train_ids & val_ood_ids), "train ∩ val_ood leakage"
    assert not (val_id_ids & val_ood_ids), "val_id ∩ val_ood leakage"
    print(f"split sizes: train={len(splits['train'])} val_id={len(splits['val_id'])} val_ood={len(splits['val_ood'])}")

    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    phase_count_dist: dict[str, Counter] = {k: Counter() for k in splits}
    ood_dim_dist: Counter[str] = Counter()

    for split, items in splits.items():
        rows_tok: list[dict[str, Any]] = []
        for r in items:
            tok = tokenize_one(tokenizer, r["prompt"], r["assistant"], max_length=max_length)
            rows_tok.append({**tok, "sample_id": r["sample_id"], "trivial": r["trivial"]})
            # phase_count from input
            n_phase = len(json.loads(r["prompt"][r["prompt"].index("【cycle_predict_input_json】") + len("【cycle_predict_input_json】"):r["prompt"].index("【/cycle_predict_input_json】")])["prediction"]["phase_waits"])
            phase_count_dist[split][n_phase] += 1

        table = pa.table({
            "sample_id": [r["sample_id"] for r in rows_tok],
            "input_ids": [r["input_ids"] for r in rows_tok],
            "attention_mask": [r["attention_mask"] for r in rows_tok],
            "labels": [r["labels"] for r in rows_tok],
            "trivial": [r["trivial"] for r in rows_tok],
        })
        sp_dir = out_root / split
        sp_dir.mkdir(exist_ok=True)
        pq.write_table(table, sp_dir / "data.parquet")
        print(f"wrote {sp_dir}/data.parquet ({len(rows_tok)} rows)")

    # Dataset card
    lengths = sorted(raw_lens)
    card_lines = [
        "# Dataset Card",
        "",
        f"**Tokenizer:** {args.model}  ",
        f"**max_length:** {max_length} (p99={p99}, buffer={args.p99_buffer}, cap={args.max_length_cap})",
        "",
        "## Splits",
        "| split | n | trivial |",
        "|---|---|---|",
    ]
    for split, items in splits.items():
        n_triv = sum(1 for r in items if r["trivial"])
        card_lines.append(f"| {split} | {len(items)} | {n_triv} |")
    card_lines += [
        "",
        "## Token length distribution (full sequence)",
        f"min={lengths[0] if lengths else '-'} p50={lengths[len(lengths)//2] if lengths else '-'} "
        f"p90={lengths[int(len(lengths)*0.9)] if lengths else '-'} "
        f"p99={p99} max={lengths[-1] if lengths else '-'}",
        "",
        "## Phase count distribution per split",
    ]
    for split, ctr in phase_count_dist.items():
        card_lines.append(f"- {split}: " + ", ".join(f"{k}->{v}" for k, v in sorted(ctr.items())))
    Path(args.card).write_text("\n".join(card_lines) + "\n", encoding="utf-8")
    print(f"wrote dataset card: {args.card}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
